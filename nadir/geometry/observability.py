from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .rig import CameraRig


@dataclass(frozen=True)
class PairObservability:
    pair_indices: tuple[tuple[int, int], ...]
    baseline_m: np.ndarray  # [P]
    triangulation_angle_rad: np.ndarray  # [P, N, K]
    sin_triangulation_angle: np.ndarray  # [P, N, K]


def compute_pair_observability(
    rig: CameraRig,
    rays_B: np.ndarray,
    depths_m: np.ndarray,
) -> PairObservability:
    """Compute geometry-only stereo observability for candidate 3-D points.

    No arbitrary pass/fail threshold is embedded here. Callers receive physical
    baseline and triangulation angle and must derive thresholds from experiment.
    """
    rays = np.asarray(rays_B, dtype=np.float64).reshape(-1, 3)
    depths = np.asarray(depths_m, dtype=np.float64)
    if depths.ndim != 1 or np.any(depths <= 0.0):
        raise ValueError("depths_m must be positive 1-D")
    if not np.allclose(np.linalg.norm(rays, axis=-1), 1.0, atol=1e-6):
        raise ValueError("rays_B must be unit vectors")

    points = rays[:, None, :] * depths[None, :, None]
    pairs = rig.pair_indices()
    p_count = len(pairs)
    n, k = points.shape[:2]
    angle = np.zeros((p_count, n, k), dtype=np.float64)
    baseline = np.zeros(p_count, dtype=np.float64)

    for pi, (a, b) in enumerate(pairs):
        oa = rig.cameras[a].center_B
        ob = rig.cameras[b].center_B
        baseline[pi] = np.linalg.norm(ob - oa)
        va = points - oa
        vb = points - ob
        va /= np.linalg.norm(va, axis=-1, keepdims=True)
        vb /= np.linalg.norm(vb, axis=-1, keepdims=True)
        dot = np.sum(va * vb, axis=-1)
        angle[pi] = np.arccos(np.clip(dot, -1.0, 1.0))

    return PairObservability(
        pair_indices=pairs,
        baseline_m=baseline,
        triangulation_angle_rad=angle,
        sin_triangulation_angle=np.sin(angle),
    )
