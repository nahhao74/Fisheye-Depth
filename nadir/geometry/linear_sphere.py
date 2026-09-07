from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class LinearSphereCamera:
    """Equidistant/linear spherical fisheye model used by MVS-GI source images.

    This mirrors the public ``mvs_utils.LinearSphere`` geometry:

    - image center is ``(W/2, H/2)``;
    - image-plane radius is linear in incidence angle;
    - the circular image radius ``W/2`` corresponds to ``FoV/2``;
    - rays beyond 90 degrees are valid whenever ``FoV > 180``.

    The official implementation requires a square image; NADIR keeps the same
    restriction instead of silently changing source-camera semantics.
    """

    fov_degree: float
    width: int
    height: int
    eps: float = 1e-12

    def __post_init__(self) -> None:
        if not np.isfinite(self.fov_degree) or not (0.0 < self.fov_degree <= 360.0):
            raise ValueError("fov_degree must be finite and in (0, 360]")
        if self.width <= 0 or self.height <= 0:
            raise ValueError("width and height must be positive")
        if self.width != self.height:
            raise ValueError("LinearSphereCamera requires a square image")
        if self.eps <= 0.0:
            raise ValueError("eps must be positive")

    @property
    def fov_rad(self) -> float:
        return float(np.deg2rad(self.fov_degree))

    @property
    def cx(self) -> float:
        return self.width / 2.0

    @property
    def cy(self) -> float:
        return self.height / 2.0

    def unproject(
        self,
        uv: np.ndarray,
        *,
        check_bounds: bool = True,
    ) -> tuple[np.ndarray, np.ndarray]:
        """Unproject native fisheye pixels to unit camera-frame rays."""

        q = np.asarray(uv, dtype=np.float64)
        if q.shape[-1] != 2:
            raise ValueError("uv must have shape (..., 2)")

        u, v = np.moveaxis(q, -1, 0)
        mx = u - self.cx
        my = v - self.cy
        radius_px = np.sqrt(mx * mx + my * my)

        azimuth = np.arctan2(my, mx)
        incidence = radius_px * self.fov_rad / float(self.width)
        valid = np.isfinite(incidence) & (np.abs(incidence) <= self.fov_rad / 2.0)

        sin_i = np.sin(incidence)
        x = sin_i * np.cos(azimuth)
        y = sin_i * np.sin(azimuth)
        z = np.cos(incidence)
        rays = np.stack((x, y, z), axis=-1)

        if check_bounds:
            valid &= (
                np.isfinite(u)
                & np.isfinite(v)
                & (u >= 0.0)
                & (u < self.width)
                & (v >= 0.0)
                & (v < self.height)
            )

        rays = np.where(valid[..., None], rays, np.nan)
        return rays, valid

    def project(
        self,
        xyz: np.ndarray,
        *,
        check_bounds: bool = True,
    ) -> tuple[np.ndarray, np.ndarray]:
        """Project camera-frame 3-D point(s) to native fisheye pixels."""

        p = np.asarray(xyz, dtype=np.float64)
        if p.shape[-1] != 3:
            raise ValueError("xyz must have shape (..., 3)")

        x, y, z = np.moveaxis(p, -1, 0)
        norm = np.sqrt(x * x + y * y + z * z)
        nonzero = np.isfinite(norm) & (norm > self.eps)

        cos_incidence = np.divide(
            z,
            norm,
            out=np.full_like(norm, np.nan),
            where=nonzero,
        )
        incidence = np.arccos(np.clip(cos_incidence, -1.0, 1.0))
        azimuth = np.arctan2(y, x)
        radius_px = incidence * float(self.width) / self.fov_rad

        u = radius_px * np.cos(azimuth) + self.cx
        v = radius_px * np.sin(azimuth) + self.cy

        valid = (
            nonzero
            & np.isfinite(u)
            & np.isfinite(v)
            & (incidence <= self.fov_rad / 2.0 + self.eps)
        )
        if check_bounds:
            valid &= (
                (u >= 0.0)
                & (u < self.width)
                & (v >= 0.0)
                & (v < self.height)
            )

        uv_out = np.stack((u, v), axis=-1)
        uv_out = np.where(valid[..., None], uv_out, np.nan)
        return uv_out, valid
