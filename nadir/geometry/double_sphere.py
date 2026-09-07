from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class DoubleSphereCamera:
    """Double Sphere fisheye camera model.

    Camera convention follows the calibrated camera frame: optical axis +Z,
    image X to the right and image Y downward unless a different extrinsic
    convention is explicitly supplied by the rig calibration.

    No pinhole rectification is performed. Rays with camera-frame z < 0 can be
    represented when the calibrated Double Sphere parameters permit them.
    """

    xi: float
    alpha: float
    fx: float
    fy: float
    cx: float
    cy: float
    width: int
    height: int
    eps: float = 1e-9

    def project(self, xyz: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Project camera-frame 3-D point(s) to native fisheye pixels."""
        p = np.asarray(xyz, dtype=np.float64)
        if p.shape[-1] != 3:
            raise ValueError("xyz must have shape (..., 3)")

        x, y, z = np.moveaxis(p, -1, 0)
        d1 = np.sqrt(x * x + y * y + z * z)
        z1 = self.xi * d1 + z
        d2 = np.sqrt(x * x + y * y + z1 * z1)
        denom = self.alpha * d2 + (1.0 - self.alpha) * z1

        safe = np.abs(denom) > self.eps
        u = np.full_like(denom, np.nan, dtype=np.float64)
        v = np.full_like(denom, np.nan, dtype=np.float64)
        u[safe] = self.fx * x[safe] / denom[safe] + self.cx
        v[safe] = self.fy * y[safe] / denom[safe] + self.cy

        uv = np.stack((u, v), axis=-1)
        in_bounds = (u >= 0.0) & (u < self.width) & (v >= 0.0) & (v < self.height)
        valid = safe & np.isfinite(u) & np.isfinite(v) & in_bounds & (d1 > self.eps)
        return uv, valid

    def unproject(self, uv: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
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

        in_bounds = (u >= 0.0) & (u < self.width) & (v >= 0.0) & (v < self.height)
        valid &= in_bounds
        return rays, valid
