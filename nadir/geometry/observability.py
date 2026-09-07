from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .lut import ProjectionLUT, build_projection_lut
from .rig import CameraRig


@dataclass(frozen=True)
class PairObservability:
    pair_indices: tuple[tuple[int, int], ...]
    baseline_m: np.ndarray  # [P]
    effective_baseline_m: np.ndarray  # [P, N]
    triangulation_angle_rad: np.ndarray  # [P, N, K]
    sin_triangulation_angle: np.ndarray  # [P, N, K]
    pair_valid: np.ndarray  # [P, N, K]


def compute_pair_observability(
    rig: CameraRig,
    rays_B: np.ndarray,
    depths_m: np.ndarray,
    *,
    projection_lut: ProjectionLUT | None = None,
) -> PairObservability:
    """Compute geometry-only stereo observability for candidate 3-D points.

    No arbitrary pass/fail threshold is embedded here. Callers receive physical
    baseline, effective baseline, triangulation angle and projection validity.
    Thresholds must be derived from measurement rather than hard-coded here.

    Visibility is candidate-aware: a common rig direction does not by itself
    guarantee that all displaced camera centers see the same finite-range point.
    """
    rays = np.asarray(rays_B, dtype=np.float64).reshape(-1, 3)
    depths = np.asarray(depths_m, dtype=np.float64)
    if depths.ndim != 1 or depths.size == 0 or np.any(depths <= 0.0):
        raise ValueError("depths_m must be positive non-empty 1-D")
    if np.any(~np.isfinite(rays)) or np.any(~np.isfinite(depths)):
        raise ValueError("rays_B and depths_m must be finite")
    if not np.allclose(np.linalg.norm(rays, axis=-1), 1.0, atol=1e-6):
        raise ValueError("rays_B must be unit vectors")

    lut = projection_lut
    if lut is None:
        lut = build_projection_lut(rig, rays, depths)
    else:
        if lut.valid.shape[0] != len(rig.cameras):
            raise ValueError("projection_lut camera count does not match rig")
        if lut.valid.shape[1:] != (rays.shape[0], depths.shape[0]):
            raise ValueError("projection_lut shape does not match rays/depths")
        if not np.allclose(lut.depths_m, depths, atol=1e-6):
            raise ValueError("projection_lut depths do not match depths_m")

    points = rays[:, None, :] * depths[None, :, None]
    pairs = rig.pair_indices()
    p_count = len(pairs)
    n, k = points.shape[:2]

    angle = np.full((p_count, n, k), np.nan, dtype=np.float64)
    sin_angle = np.zeros((p_count, n, k), dtype=np.float64)
    pair_valid = np.zeros((p_count, n, k), dtype=bool)
    baseline = np.zeros(p_count, dtype=np.float64)
    effective_baseline = np.zeros((p_count, n), dtype=np.float64)

    eps = 1e-12
    for pi, (a, b) in enumerate(pairs):
        oa = rig.cameras[a].center_B
        ob = rig.cameras[b].center_B
        baseline_vec = ob - oa
        baseline[pi] = np.linalg.norm(baseline_vec)

        # Direction-only perpendicular baseline. This is useful for identifying
        # rays where the physical camera separation produces little parallax.
        parallel = rays @ baseline_vec
        perpendicular = baseline_vec[None, :] - parallel[:, None] * rays
        effective_baseline[pi] = np.linalg.norm(perpendicular, axis=-1)

        va = points - oa[None, None, :]
        vb = points - ob[None, None, :]
        na = np.linalg.norm(va, axis=-1)
        nb = np.linalg.norm(vb, axis=-1)
        norm_ok = (na > eps) & (nb > eps)

        dot = np.zeros((n, k), dtype=np.float64)
        dot[norm_ok] = np.sum(va[norm_ok] * vb[norm_ok], axis=-1) / (
            na[norm_ok] * nb[norm_ok]
        )
        local_angle = np.arccos(np.clip(dot, -1.0, 1.0))
        valid = lut.valid[a] & lut.valid[b] & norm_ok

        angle[pi] = np.where(valid, local_angle, np.nan)
        sin_angle[pi] = np.where(valid, np.sin(local_angle), 0.0)
        pair_valid[pi] = valid

    return PairObservability(
        pair_indices=pairs,
        baseline_m=baseline,
        effective_baseline_m=effective_baseline,
        triangulation_angle_rad=angle,
        sin_triangulation_angle=sin_angle,
        pair_valid=pair_valid,
    )
