from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class DoubleSphereCamera:
    """Double Sphere fisheye camera model.

    Camera convention follows the calibrated camera frame: optical axis +Z,
    image X to the right and image Y downward unless a different extrinsic
    convention is explicitly supplied by the rig calibration.

    ``pixel_center_offset`` states whether array pixel index ``0`` corresponds
    to model coordinate ``0`` (usual NADIR/OpenCV-style use) or ``0.5`` (the
    released MVS-GI ``mvs_utils`` pixel-center convention). The projection
    equations themselves remain in the calibrated model coordinate system.
    """

    xi: float
    alpha: float
    fx: float
    fy: float
    cx: float
    cy: float
    width: int
    height: int
    pixel_center_offset: float = 0.0
    eps: float = 1e-9

    def __post_init__(self) -> None:
        if not (0.0 <= self.alpha <= 1.0):
            raise ValueError("alpha must be in [0, 1]")
        if not np.isfinite(self.xi):
            raise ValueError("xi must be finite")
        if self.fx <= 0.0 or self.fy <= 0.0:
            raise ValueError("fx and fy must be positive")
        if self.width <= 0 or self.height <= 0:
            raise ValueError("width and height must be positive")
        if not np.isfinite(self.pixel_center_offset) or not (
            0.0 <= self.pixel_center_offset < 1.0
        ):
            raise ValueError("pixel_center_offset must be finite and in [0, 1)")
        if self.eps <= 0.0:
            raise ValueError("eps must be positive")

        w1 = self._w1()
        disc = 2.0 * w1 * self.xi + self.xi * self.xi + 1.0
        if disc <= self.eps:
            raise ValueError("Double Sphere parameters yield an invalid projection domain")

    def _w1(self) -> float:
        if self.alpha <= 0.5:
            return self.alpha / (1.0 - self.alpha)
        return (1.0 - self.alpha) / self.alpha

    def _w2(self) -> float:
        w1 = self._w1()
        return (w1 + self.xi) / np.sqrt(
            2.0 * w1 * self.xi + self.xi * self.xi + 1.0
        )

    def _bounds_mask(self, u: np.ndarray, v: np.ndarray) -> np.ndarray:
        o = self.pixel_center_offset
        return (
            (u >= o)
            & (u <= (self.width - 1) + o)
            & (v >= o)
            & (v <= (self.height - 1) + o)
        )

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
        d1 = np.sqrt(x * x + y * y + z * z)
        nonzero = d1 > self.eps
        domain_ok = nonzero & (z > -self._w2() * d1)

        z1 = self.xi * d1 + z
        d2 = np.sqrt(x * x + y * y + z1 * z1)
        denom = self.alpha * d2 + (1.0 - self.alpha) * z1
        denom_ok = np.abs(denom) > self.eps
        safe = domain_ok & denom_ok

        u = np.full_like(denom, np.nan, dtype=np.float64)
        v = np.full_like(denom, np.nan, dtype=np.float64)
        u[safe] = self.fx * x[safe] / denom[safe] + self.cx
        v[safe] = self.fy * y[safe] / denom[safe] + self.cy

        finite = np.isfinite(u) & np.isfinite(v)
        valid = safe & finite
        if check_bounds:
            valid &= self._bounds_mask(u, v)

        uv = np.stack((u, v), axis=-1)
        uv = np.where(valid[..., None], uv, np.nan)
        return uv, valid

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
        mx = (u - self.cx) / self.fx
        my = (v - self.cy) / self.fy
        r2 = mx * mx + my * my

        sqrt_arg = 1.0 - (2.0 * self.alpha - 1.0) * r2
        domain_ok = sqrt_arg >= 0.0
        sqrt_term = np.sqrt(np.maximum(sqrt_arg, 0.0))
        denom = self.alpha * sqrt_term + (1.0 - self.alpha)
        denom_ok = np.abs(denom) > self.eps

        mz = np.full_like(mx, np.nan)
        ok = domain_ok & denom_ok
        mz[ok] = (1.0 - self.alpha * self.alpha * r2[ok]) / denom[ok]

        inner = mz * mz + (1.0 - self.xi * self.xi) * r2
        inner_ok = inner >= 0.0
        scale_denom = mz * mz + r2
        scale_ok = scale_denom > self.eps
        valid = ok & inner_ok & scale_ok

        k = np.full_like(mx, np.nan)
        k[valid] = (
            mz[valid] * self.xi + np.sqrt(np.maximum(inner[valid], 0.0))
        ) / scale_denom[valid]

        x = k * mx
        y = k * my
        z = k * mz - self.xi
        rays = np.stack((x, y, z), axis=-1)
        norms = np.linalg.norm(rays, axis=-1)
        norm_ok = np.isfinite(norms) & (norms > self.eps)
        valid &= norm_ok
        rays = np.divide(
            rays,
            norms[..., None],
            out=np.full_like(rays, np.nan),
            where=norm_ok[..., None],
        )

        if check_bounds:
            valid &= self._bounds_mask(u, v)

        rays = np.where(valid[..., None], rays, np.nan)
        return rays, valid
