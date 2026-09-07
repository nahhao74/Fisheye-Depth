from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations

import numpy as np

from .double_sphere import DoubleSphereCamera
from .transforms import transform_points


@dataclass(frozen=True)
class RigCamera:
    """One fisheye camera rigidly attached to the UAV body/rig.

    ``T_C_B`` maps points from Body/Rig FRD frame B into this camera frame C.
    The camera optical center in B is derived from the inverse transform.
    """

    name: str
    model: DoubleSphereCamera
    T_C_B: np.ndarray

    def __post_init__(self) -> None:
        T = np.asarray(self.T_C_B, dtype=np.float64)
        if T.shape != (4, 4):
            raise ValueError("T_C_B must have shape (4, 4)")
        if not np.all(np.isfinite(T)):
            raise ValueError("T_C_B must be finite")
        if not np.allclose(T[3], [0.0, 0.0, 0.0, 1.0], atol=1e-9):
            raise ValueError("T_C_B must be a homogeneous rigid transform")

        R = T[:3, :3]
        if not np.allclose(R @ R.T, np.eye(3), atol=1e-6):
            raise ValueError("T_C_B rotation must be orthonormal")
        if np.linalg.det(R) <= 0.0:
            raise ValueError("T_C_B rotation must have positive determinant")

        object.__setattr__(self, "T_C_B", T)

    @property
    def center_B(self) -> np.ndarray:
        """Camera optical center expressed in Body/Rig frame B."""
        R_C_B = self.T_C_B[:3, :3]
        t_C_B = self.T_C_B[:3, 3]
        return -(R_C_B.T @ t_C_B)


@dataclass(frozen=True)
class ProjectionSweep:
    """Projection of common rig-ray depth hypotheses into all cameras."""

    uv: np.ndarray  # [C, N, K, 2]
    valid: np.ndarray  # [C, N, K]
    visibility_mask: np.ndarray  # [N, K], camera c represented by bit (1 << c)
    points_B: np.ndarray  # [N, K, 3]


@dataclass(frozen=True)
class PairObservability:
    camera_a: str
    camera_b: str
    baseline_m: float
    effective_baseline_m: np.ndarray  # [N]
    triangulation_angle_rad: np.ndarray  # [N, K]
    geometry_score: np.ndarray  # [N, K], sin(triangulation angle)
    valid: np.ndarray  # [N, K]


def _validate_rays_and_depths(
    rays_B: np.ndarray,
    depths_m: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    rays = np.asarray(rays_B, dtype=np.float64)
    depths = np.asarray(depths_m, dtype=np.float64)
    if rays.ndim != 2 or rays.shape[1] != 3:
        raise ValueError("rays_B must have shape (N, 3)")
    if depths.ndim != 1 or depths.size == 0:
        raise ValueError("depths_m must have shape (K,) with K > 0")
    if np.any(~np.isfinite(rays)) or np.any(~np.isfinite(depths)):
        raise ValueError("rays_B and depths_m must be finite")
    if np.any(depths <= 0.0):
        raise ValueError("all depth hypotheses must be > 0")

    norms = np.linalg.norm(rays, axis=1)
    if not np.allclose(norms, 1.0, atol=1e-6):
        raise ValueError("rays_B must be unit vectors")
    return rays, depths


def build_hypothesis_points(
    rays_B: np.ndarray,
    depths_m: np.ndarray,
    *,
    rig_origin_B: np.ndarray | None = None,
) -> np.ndarray:
    """Create candidate 3-D points ``P = O_R + rho * r`` in rig frame B."""
    rays, depths = _validate_rays_and_depths(rays_B, depths_m)
    origin = np.zeros(3, dtype=np.float64)
    if rig_origin_B is not None:
        origin = np.asarray(rig_origin_B, dtype=np.float64)
        if origin.shape != (3,) or np.any(~np.isfinite(origin)):
            raise ValueError("rig_origin_B must have shape (3,) and be finite")
    return origin[None, None, :] + rays[:, None, :] * depths[None, :, None]


def project_hypotheses(
    cameras: tuple[RigCamera, ...] | list[RigCamera],
    rays_B: np.ndarray,
    depths_m: np.ndarray,
    *,
    rig_origin_B: np.ndarray | None = None,
) -> ProjectionSweep:
    """Project candidate depths into every native fisheye image.

    Visibility is deliberately candidate-aware. With a generalized camera rig,
    camera centers are not co-located with the rig origin, so visibility can
    change with range. A direction-only mask is therefore only a far-field
    approximation and is not used as the authoritative representation here.
    """
    if not cameras:
        raise ValueError("at least one camera is required")
    if len(cameras) > 8:
        raise ValueError("visibility bitmask currently supports at most 8 cameras")

    points_B = build_hypothesis_points(
        rays_B,
        depths_m,
        rig_origin_B=rig_origin_B,
    )
    n_rays, n_depths = points_B.shape[:2]

    uv_all = np.full((len(cameras), n_rays, n_depths, 2), np.nan, dtype=np.float64)
    valid_all = np.zeros((len(cameras), n_rays, n_depths), dtype=bool)

    flat_B = points_B.reshape(-1, 3)
    for camera_index, camera in enumerate(cameras):
        flat_C = transform_points(camera.T_C_B, flat_B)
        uv, valid = camera.model.project(flat_C, check_bounds=True)
        uv_all[camera_index] = uv.reshape(n_rays, n_depths, 2)
        valid_all[camera_index] = valid.reshape(n_rays, n_depths)

    visibility_mask = np.zeros((n_rays, n_depths), dtype=np.uint8)
    for camera_index in range(len(cameras)):
        visibility_mask |= valid_all[camera_index].astype(np.uint8) << camera_index

    return ProjectionSweep(
        uv=uv_all,
        valid=valid_all,
        visibility_mask=visibility_mask,
        points_B=points_B,
    )


def pair_observability(
    cameras: tuple[RigCamera, ...] | list[RigCamera],
    rays_B: np.ndarray,
    depths_m: np.ndarray,
    *,
    rig_origin_B: np.ndarray | None = None,
) -> dict[tuple[int, int], PairObservability]:
    """Compute stereo geometry quality for every camera pair and hypothesis.

    ``geometry_score = sin(triangulation_angle)`` is intentionally only a
    geometry-conditioning proxy. It is not a learned confidence and does not
    encode image texture, blur, calibration residual or occlusion quality.
    """
    rays, depths = _validate_rays_and_depths(rays_B, depths_m)
    sweep = project_hypotheses(
        cameras,
        rays,
        depths,
        rig_origin_B=rig_origin_B,
    )

    result: dict[tuple[int, int], PairObservability] = {}
    eps = 1e-12

    for a, b in combinations(range(len(cameras)), 2):
        Oa = cameras[a].center_B
        Ob = cameras[b].center_B
        baseline_vec = Ob - Oa
        baseline_m = float(np.linalg.norm(baseline_vec))

        # Baseline component orthogonal to the common rig ray. This is a useful
        # direction-only indicator; actual triangulation angle below remains
        # candidate-range dependent.
        parallel = rays @ baseline_vec
        perpendicular = baseline_vec[None, :] - parallel[:, None] * rays
        effective_baseline = np.linalg.norm(perpendicular, axis=1)

        va = sweep.points_B - Oa[None, None, :]
        vb = sweep.points_B - Ob[None, None, :]
        na = np.linalg.norm(va, axis=-1)
        nb = np.linalg.norm(vb, axis=-1)
        norm_ok = (na > eps) & (nb > eps)

        dot = np.zeros_like(na)
        dot[norm_ok] = np.sum(va[norm_ok] * vb[norm_ok], axis=-1) / (
            na[norm_ok] * nb[norm_ok]
        )
        dot = np.clip(dot, -1.0, 1.0)
        angle = np.arccos(dot)
        valid = sweep.valid[a] & sweep.valid[b] & norm_ok
        angle = np.where(valid, angle, np.nan)
        geometry_score = np.where(valid, np.sin(angle), 0.0)

        result[(a, b)] = PairObservability(
            camera_a=cameras[a].name,
            camera_b=cameras[b].name,
            baseline_m=baseline_m,
            effective_baseline_m=effective_baseline,
            triangulation_angle_rad=angle,
            geometry_score=geometry_score,
            valid=valid,
        )

    return result
