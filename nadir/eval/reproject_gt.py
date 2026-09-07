from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from nadir.geometry.camera_model import NativeCameraModel
from nadir.geometry.rays import SphericalRayGrid
from nadir.geometry.transforms import transform_points


@dataclass(frozen=True)
class RayGridGroundTruth:
    """Sparse/nearest-angle GT projected onto a NADIR spherical ray grid."""

    depth_m: np.ndarray  # [H, W]
    angular_error_rad: np.ndarray  # [H, W]
    valid: np.ndarray  # [H, W]
    source_pixel_count: int


def _nearest_azimuth_index(azimuth_rad: np.ndarray, n_azimuth: int) -> np.ndarray:
    # Grid azimuths are [-pi, pi) with uniform spacing.
    scaled = (azimuth_rad + np.pi) * n_azimuth / (2.0 * np.pi)
    return np.mod(np.floor(scaled + 0.5).astype(np.int64), n_azimuth)


def _nearest_polar_index(
    polar_rad: np.ndarray,
    polar_grid: np.ndarray,
) -> np.ndarray:
    if polar_grid.ndim != 1 or polar_grid.size < 2:
        raise ValueError("polar grid must be one-dimensional with at least two entries")
    step = float(polar_grid[1] - polar_grid[0])
    if step <= 0.0 or not np.allclose(np.diff(polar_grid), step, atol=1e-12):
        raise ValueError("polar grid must be uniformly increasing")
    idx = np.floor((polar_rad - float(polar_grid[0])) / step + 0.5).astype(np.int64)
    return np.clip(idx, 0, polar_grid.size - 1)


def distance_image_to_ray_grid(
    distance_m: np.ndarray,
    *,
    source_model: NativeCameraModel,
    T_B_C: np.ndarray,
    ray_grid: SphericalRayGrid,
) -> RayGridGroundTruth:
    """Convert a native-camera radial distance image into rig-frame radial GT.

    Every valid source pixel is unprojected through the *native* camera model,
    converted to a 3-D point using its radial distance, transformed into the
    Rig/Body frame, then assigned to the nearest regular lower-hemisphere output
    ray. If several source pixels map to one output cell, the point with the
    smallest angular error to that cell is retained.

    No arbitrary angular-error threshold is applied here. The caller receives
    ``angular_error_rad`` and may freeze an explicit evaluation mask later.
    """

    dist = np.asarray(distance_m, dtype=np.float64)
    if dist.ndim != 2:
        raise ValueError("distance_m must have shape (H, W)")
    if dist.shape != (source_model.height, source_model.width):
        raise ValueError(
            "distance image shape does not match source camera model: "
            f"image={dist.shape}, model={(source_model.height, source_model.width)}"
        )

    h, w = dist.shape
    yy, xx = np.indices((h, w), dtype=np.float64)
    offset = float(source_model.pixel_center_offset)
    uv_model = np.stack((xx + offset, yy + offset), axis=-1).reshape(-1, 2)
    rays_C, ray_valid = source_model.unproject(uv_model, check_bounds=True)

    d = dist.reshape(-1)
    valid = ray_valid & np.isfinite(d) & (d > 0.0)
    if not np.any(valid):
        shape = ray_grid.shape
        return RayGridGroundTruth(
            depth_m=np.full(shape, np.nan, dtype=np.float32),
            angular_error_rad=np.full(shape, np.nan, dtype=np.float32),
            valid=np.zeros(shape, dtype=bool),
            source_pixel_count=0,
        )

    points_C = rays_C[valid] * d[valid, None]
    points_B = transform_points(T_B_C, points_C)
    rho_B = np.linalg.norm(points_B, axis=-1)
    finite_points = np.all(np.isfinite(points_B), axis=-1) & np.isfinite(rho_B) & (rho_B > 0.0)
    points_B = points_B[finite_points]
    rho_B = rho_B[finite_points]

    rays_B = points_B / rho_B[:, None]
    lower = rays_B[:, 2] >= 0.0
    rays_B = rays_B[lower]
    rho_B = rho_B[lower]

    gh, gw = ray_grid.shape
    out_depth = np.full((gh, gw), np.nan, dtype=np.float32)
    out_error = np.full((gh, gw), np.nan, dtype=np.float32)
    out_valid = np.zeros((gh, gw), dtype=bool)
    if rays_B.size == 0:
        return RayGridGroundTruth(
            depth_m=out_depth,
            angular_error_rad=out_error,
            valid=out_valid,
            source_pixel_count=0,
        )

    az = np.arctan2(rays_B[:, 1], rays_B[:, 0])
    polar = np.arccos(np.clip(rays_B[:, 2], -1.0, 1.0))
    ai = _nearest_azimuth_index(az, gw)
    pi = _nearest_polar_index(polar, ray_grid.polar_from_down_rad)

    target_rays = ray_grid.rays[pi, ai]
    dot = np.sum(rays_B * target_rays, axis=-1)
    angular_error = np.arccos(np.clip(dot, -1.0, 1.0))
    cell = pi * gw + ai

    # Lexicographic sort places the smallest angular error first in each cell.
    order = np.lexsort((angular_error, cell))
    cell_sorted = cell[order]
    first = np.ones(cell_sorted.shape, dtype=bool)
    first[1:] = cell_sorted[1:] != cell_sorted[:-1]
    keep = order[first]

    pi_keep = pi[keep]
    ai_keep = ai[keep]
    out_depth[pi_keep, ai_keep] = rho_B[keep].astype(np.float32)
    out_error[pi_keep, ai_keep] = angular_error[keep].astype(np.float32)
    out_valid[pi_keep, ai_keep] = True

    return RayGridGroundTruth(
        depth_m=out_depth,
        angular_error_rad=out_error,
        valid=out_valid,
        source_pixel_count=int(rays_B.shape[0]),
    )
