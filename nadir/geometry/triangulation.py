from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .rig import RigCamera


@dataclass(frozen=True)
class TwoRayTriangulation:
    """Closest-point triangulation result for two generalized-camera rays.

    The two observations are represented by camera centers ``O_a/O_b`` and
    unit directions ``d_a/d_b`` in the common Body/Rig frame. No epipolar,
    reprojection, gap or angle acceptance threshold is embedded here: those are
    experiment-level decisions and must be reported explicitly by callers.
    """

    point_B: np.ndarray
    point_a_B: np.ndarray
    point_b_B: np.ndarray
    lambda_a_m: np.ndarray
    lambda_b_m: np.ndarray
    closest_gap_m: np.ndarray
    angle_rad: np.ndarray
    sin_angle: np.ndarray
    condition_number: np.ndarray
    numerically_valid: np.ndarray
    forward_valid: np.ndarray


def array_pixels_to_body_rays(
    camera: RigCamera,
    uv_array: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Convert image-array coordinates to Body/Rig rays for one rig camera.

    OpenCV/keypoint coordinates are array-index pixel-center coordinates. Camera
    models may use a shifted continuous convention (MVS-GI uses +0.5), so the
    offset is added before native unprojection.
    """

    uv = np.asarray(uv_array, dtype=np.float64)
    if uv.shape[-1] != 2:
        raise ValueError("uv_array must have shape (..., 2)")

    uv_model = uv + float(camera.model.pixel_center_offset)
    rays_C, valid = camera.model.unproject(uv_model)
    R_B_C = camera.T_B_C[:3, :3]
    rays_B = rays_C @ R_B_C.T
    norms = np.linalg.norm(rays_B, axis=-1)
    norm_ok = np.isfinite(norms) & (norms > 0.0)
    valid &= norm_ok
    rays_B = np.divide(
        rays_B,
        norms[..., None],
        out=np.full_like(rays_B, np.nan),
        where=norm_ok[..., None],
    )
    rays_B = np.where(valid[..., None], rays_B, np.nan)
    return rays_B, valid


def project_body_points_to_array(
    camera: RigCamera,
    points_B: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Project Body/Rig points to image-array coordinates for one camera."""

    uv_model, valid = camera.project_body_points(points_B)
    uv_array = uv_model - float(camera.model.pixel_center_offset)
    uv_array = np.where(valid[..., None], uv_array, np.nan)
    return uv_array, valid


def triangulate_two_rays(
    origin_a_B: np.ndarray,
    direction_a_B: np.ndarray,
    origin_b_B: np.ndarray,
    direction_b_B: np.ndarray,
    *,
    eps: float = 1e-12,
) -> TwoRayTriangulation:
    """Triangulate the midpoint of the closest segment between two 3-D rays.

    Inputs broadcast over any leading shape and must end in dimension 3. The
    returned ``lambda_a_m`` and ``lambda_b_m`` are signed distances along the
    normalized rays. ``forward_valid`` requires both to be strictly positive;
    this is a geometric visibility condition rather than a tuned threshold.

    Near-parallel rays are reported as numerically invalid instead of silently
    returning an unstable very-far point.
    """

    Oa, da, Ob, db = np.broadcast_arrays(
        np.asarray(origin_a_B, dtype=np.float64),
        np.asarray(direction_a_B, dtype=np.float64),
        np.asarray(origin_b_B, dtype=np.float64),
        np.asarray(direction_b_B, dtype=np.float64),
    )
    if Oa.shape[-1] != 3:
        raise ValueError("ray inputs must have shape (..., 3)")
    if eps <= 0.0:
        raise ValueError("eps must be positive")

    na = np.linalg.norm(da, axis=-1)
    nb = np.linalg.norm(db, axis=-1)
    finite = (
        np.all(np.isfinite(Oa), axis=-1)
        & np.all(np.isfinite(Ob), axis=-1)
        & np.all(np.isfinite(da), axis=-1)
        & np.all(np.isfinite(db), axis=-1)
    )
    nonzero = (na > eps) & (nb > eps)

    da_u = np.divide(
        da,
        na[..., None],
        out=np.full_like(da, np.nan),
        where=nonzero[..., None],
    )
    db_u = np.divide(
        db,
        nb[..., None],
        out=np.full_like(db, np.nan),
        where=nonzero[..., None],
    )

    cos_angle = np.sum(da_u * db_u, axis=-1)
    cos_angle = np.clip(cos_angle, -1.0, 1.0)
    angle = np.arccos(cos_angle)
    sin_angle = np.sqrt(np.maximum(0.0, 1.0 - cos_angle * cos_angle))

    # Closest points on lines Oa+s*da and Ob+t*db.
    w0 = Oa - Ob
    a = np.sum(da_u * da_u, axis=-1)
    b = np.sum(da_u * db_u, axis=-1)
    c = np.sum(db_u * db_u, axis=-1)
    d = np.sum(da_u * w0, axis=-1)
    e = np.sum(db_u * w0, axis=-1)
    denom = a * c - b * b

    numerically_valid = finite & nonzero & np.isfinite(denom) & (denom > eps)
    lambda_a = np.full(denom.shape, np.nan, dtype=np.float64)
    lambda_b = np.full(denom.shape, np.nan, dtype=np.float64)
    lambda_a[numerically_valid] = (
        b[numerically_valid] * e[numerically_valid]
        - c[numerically_valid] * d[numerically_valid]
    ) / denom[numerically_valid]
    lambda_b[numerically_valid] = (
        a[numerically_valid] * e[numerically_valid]
        - b[numerically_valid] * d[numerically_valid]
    ) / denom[numerically_valid]

    point_a = Oa + lambda_a[..., None] * da_u
    point_b = Ob + lambda_b[..., None] * db_u
    point = 0.5 * (point_a + point_b)
    gap = np.linalg.norm(point_a - point_b, axis=-1)

    # For unit ray columns [da, -db], singular values squared are 1 +/- |cos|.
    abs_cos = np.abs(cos_angle)
    condition = np.full(abs_cos.shape, np.inf, dtype=np.float64)
    cond_ok = numerically_valid & ((1.0 - abs_cos) > eps)
    condition[cond_ok] = np.sqrt(
        (1.0 + abs_cos[cond_ok]) / (1.0 - abs_cos[cond_ok])
    )

    forward_valid = numerically_valid & (lambda_a > 0.0) & (lambda_b > 0.0)
    point = np.where(numerically_valid[..., None], point, np.nan)
    point_a = np.where(numerically_valid[..., None], point_a, np.nan)
    point_b = np.where(numerically_valid[..., None], point_b, np.nan)
    gap = np.where(numerically_valid, gap, np.nan)

    return TwoRayTriangulation(
        point_B=point,
        point_a_B=point_a,
        point_b_B=point_b,
        lambda_a_m=lambda_a,
        lambda_b_m=lambda_b,
        closest_gap_m=gap,
        angle_rad=angle,
        sin_angle=sin_angle,
        condition_number=condition,
        numerically_valid=numerically_valid,
        forward_valid=forward_valid,
    )
