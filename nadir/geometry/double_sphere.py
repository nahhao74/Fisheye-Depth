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

    The implementation follows Usenko, Demmel & Cremers (3DV 2018), including
    the valid 3-D projection domain. This matters for >180 degree fisheye lenses:
    a finite denominator alone is not sufficient to declare a back-facing point
    projectable.
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

    def __post_init__(self) -> None:
        if not (0.0 <= self.alpha <= 1.0):
            raise ValueError("alpha must be in [0, 1]")
        if not np.isfinite(self.xi):
            raise ValueError("xi must be finite")
        if self.fx <= 0.0 or self.fy <= 0.0:
            raise ValueError("fx and fy must be positive")
        if self.width <= 0 or self.height <= 0:
            raise ValueError("width and height must be positive")
        if self.eps <= 0.0:
            raise ValueError("eps must be positive")

        # The paper's projection-domain constant requires a real denominator.
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

    def project(
        self,
        xyz: np.ndarray,
        *,
        check_bounds: bool = True,
    ) -> tuple[np.ndarray, np.ndarray]:
        """Project camera-frame 3-D point(s) to native fisheye pixels.

        Returns ``(uv, valid)``. ``valid`` includes the Double Sphere projection
        domain and, by default, physical image bounds. Set ``check_bounds=False``
        for geometry-only tests that intentionally inspect rays outside the
        physical sensor crop.
        """
        p = np.asarray(xyz, dtype=np.float64)
        if p.shape[-1] != 3:
            raise ValueError("xyz must have shape (..., 3)")

        x, y, z = np.moveaxis(p, -1, 0)
        d1 = np.sqrt(x * x + y * y + z * z)
        nonzero = d1 > self.eps

        # Paper Eq. (43): Omega = {x in R^3 | z > -w2*d1}.
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
            valid &= (
                (u >= 0.0)
                & (u < self.width)
                & (v >= 0.0)
                & (v < self.height)
            )

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

        # Paper Eq. (50) domain is encoded by this square-root term.
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
            valid &= (
                (u >= 0.0)
                & (u < self.width)
                & (v >= 0.0)
                & (v < self.height)
            )

        rays = np.where(valid[..., None], rays, np.nan)
        return rays, valid
