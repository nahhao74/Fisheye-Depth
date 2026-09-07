from __future__ import annotations

import numpy as np


def transform_points(T_ab: np.ndarray, points_b: np.ndarray) -> np.ndarray:
    """Transform points from frame B to frame A using a 4x4 homogeneous transform."""
    T = np.asarray(T_ab, dtype=np.float64)
    p = np.asarray(points_b, dtype=np.float64)
    if T.shape != (4, 4):
        raise ValueError("T_ab must be 4x4")
    if p.shape[-1] != 3:
        raise ValueError("points_b must have shape (..., 3)")
    return p @ T[:3, :3].T + T[:3, 3]


def rotate_rays(R_ab: np.ndarray, rays_b: np.ndarray) -> np.ndarray:
    """Rotate and renormalize unit rays from frame B to frame A."""
    R = np.asarray(R_ab, dtype=np.float64)
    r = np.asarray(rays_b, dtype=np.float64)
    if R.shape != (3, 3):
        raise ValueError("R_ab must be 3x3")
    if r.shape[-1] != 3:
        raise ValueError("rays_b must have shape (..., 3)")
    out = r @ R.T
    norm = np.linalg.norm(out, axis=-1, keepdims=True)
    return out / norm
