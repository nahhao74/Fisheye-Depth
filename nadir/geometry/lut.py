from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .rig import CameraRig


@dataclass(frozen=True)
class ProjectionLUT:
    """Precomputed native-fisheye sampling coordinates for fixed rig hypotheses."""

    uv_px: np.ndarray  # [C, N, K, 2]
    uv_normalized: np.ndarray  # [C, N, K, 2], [-1, 1]
    valid: np.ndarray  # [C, N, K]
    depths_m: np.ndarray  # [K]

    @property
    def visibility_mask(self) -> np.ndarray:
        """Per-ray/per-depth camera visibility encoded as an unsigned bitmask.

        Camera ``c`` maps to bit ``1 << c``. With the current 3-camera NADIR
        rig, values are in ``0..7``. Visibility remains depth-dependent because
        the camera optical centers are not co-located with the rig origin.
        """
        if self.valid.shape[0] > 8:
            raise ValueError("visibility_mask currently supports at most 8 cameras")
        mask = np.zeros(self.valid.shape[1:], dtype=np.uint8)
        for ci in range(self.valid.shape[0]):
            mask |= self.valid[ci].astype(np.uint8) << ci
        return mask

    @property
    def view_count(self) -> np.ndarray:
        """Number of geometrically valid camera observations for each hypothesis."""
        return np.sum(self.valid, axis=0, dtype=np.uint8)


def build_projection_lut(
    rig: CameraRig,
    rays_B: np.ndarray,
    depths_m: np.ndarray,
) -> ProjectionLUT:
    rays = np.asarray(rays_B, dtype=np.float64)
    depths = np.asarray(depths_m, dtype=np.float64)
    if rays.shape[-1] != 3:
        raise ValueError("rays_B must have shape (..., 3)")
    if depths.ndim != 1 or depths.size == 0 or np.any(depths <= 0.0):
        raise ValueError("depths_m must be a non-empty positive 1-D array")
    if np.any(~np.isfinite(rays)) or np.any(~np.isfinite(depths)):
        raise ValueError("rays_B and depths_m must be finite")

    flat_rays = rays.reshape(-1, 3)
    norms = np.linalg.norm(flat_rays, axis=-1)
    if not np.allclose(norms, 1.0, atol=1e-6):
        raise ValueError("rays_B must be unit vectors")

    points_B = flat_rays[:, None, :] * depths[None, :, None]
    c_count = len(rig.cameras)
    n, k = points_B.shape[:2]
    uv_px = np.full((c_count, n, k, 2), np.nan, dtype=np.float32)
    uv_norm = np.full_like(uv_px, np.nan)
    valid = np.zeros((c_count, n, k), dtype=bool)

    for ci, camera in enumerate(rig.cameras):
        uv, ok = camera.project_body_points(points_B)
        uv_px[ci] = uv.astype(np.float32)
        valid[ci] = ok

        # align_corners=True convention; deployment adapter may convert if required.
        x = 2.0 * uv[..., 0] / max(camera.model.width - 1, 1) - 1.0
        y = 2.0 * uv[..., 1] / max(camera.model.height - 1, 1) - 1.0
        uv_norm[ci, ..., 0] = x.astype(np.float32)
        uv_norm[ci, ..., 1] = y.astype(np.float32)

    return ProjectionLUT(
        uv_px=uv_px,
        uv_normalized=uv_norm,
        valid=valid,
        depths_m=depths.astype(np.float32),
    )
