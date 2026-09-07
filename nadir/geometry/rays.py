from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class SphericalRayGrid:
    """Regular ray tensor in the Rig/Body FRD frame."""

    rays: np.ndarray  # [H, W, 3]
    azimuth_rad: np.ndarray  # [W]
    polar_from_down_rad: np.ndarray  # [H]

    @property
    def shape(self) -> tuple[int, int]:
        return self.rays.shape[:2]


def make_lower_hemisphere_grid(
    n_azimuth: int = 128,
    n_polar: int = 64,
    *,
    include_horizon: bool = True,
) -> SphericalRayGrid:
    """Create a regular lower-hemisphere ray grid in FRD coordinates.

    FRD convention: +X forward, +Y right, +Z down.
    polar_from_down=0 points to nadir (+Z); pi/2 is the horizon.
    """
    if n_azimuth < 2 or n_polar < 2:
        raise ValueError("n_azimuth and n_polar must be >= 2")

    az = np.linspace(-np.pi, np.pi, n_azimuth, endpoint=False, dtype=np.float64)
    polar = np.linspace(
        0.0,
        np.pi / 2.0,
        n_polar,
        endpoint=include_horizon,
        dtype=np.float64,
    )
    pp, aa = np.meshgrid(polar, az, indexing="ij")
    sin_p = np.sin(pp)
    rays = np.stack(
        (
            sin_p * np.cos(aa),
            sin_p * np.sin(aa),
            np.cos(pp),
        ),
        axis=-1,
    )
    return SphericalRayGrid(rays=rays, azimuth_rad=az, polar_from_down_rad=polar)
