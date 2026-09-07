from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from nadir.geometry.lut import ProjectionLUT


@dataclass(frozen=True)
class PhotometricSweepResult:
    """Result of the first non-neural native-fisheye sphere/ray sweep baseline."""

    cost: np.ndarray  # [N, K], lower is better
    depth_m: np.ndarray  # [N]
    best_index: np.ndarray  # [N]
    valid: np.ndarray  # [N]
    view_count: np.ndarray  # [N, K]


def _as_float_channels(image: np.ndarray) -> np.ndarray:
    arr = np.asarray(image)
    if arr.ndim == 2:
        arr = arr[..., None]
    if arr.ndim != 3:
        raise ValueError("image must have shape (H, W) or (H, W, C)")

    if np.issubdtype(arr.dtype, np.integer):
        info = np.iinfo(arr.dtype)
        scale = float(info.max) if info.max > 0 else 1.0
        return arr.astype(np.float32) / scale
    return arr.astype(np.float32)


def bilinear_sample(
    image: np.ndarray,
    uv_px: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Sample an image at pixel coordinates with bilinear interpolation.

    Parameters
    ----------
    image:
        ``(H, W)`` or ``(H, W, C)`` image.
    uv_px:
        Coordinates with final dimension ``(..., 2)`` storing ``(u, v)``.

    Returns
    -------
    samples:
        ``(..., C)`` float32 samples.
    valid:
        ``(...)`` mask indicating finite coordinates inside image bounds.
    """
    img = _as_float_channels(image)
    uv = np.asarray(uv_px, dtype=np.float64)
    if uv.shape[-1] != 2:
        raise ValueError("uv_px must have shape (..., 2)")

    h, w, channels = img.shape
    u = uv[..., 0]
    v = uv[..., 1]
    valid = (
        np.isfinite(u)
        & np.isfinite(v)
        & (u >= 0.0)
        & (u <= w - 1)
        & (v >= 0.0)
        & (v <= h - 1)
    )

    # Safe temporary coordinates for invalid samples; output is masked later.
    u_safe = np.where(valid, u, 0.0)
    v_safe = np.where(valid, v, 0.0)

    x0 = np.floor(u_safe).astype(np.int64)
    y0 = np.floor(v_safe).astype(np.int64)
    x1 = np.minimum(x0 + 1, w - 1)
    y1 = np.minimum(y0 + 1, h - 1)

    du = (u_safe - x0)[..., None].astype(np.float32)
    dv = (v_safe - y0)[..., None].astype(np.float32)

    i00 = img[y0, x0]
    i10 = img[y0, x1]
    i01 = img[y1, x0]
    i11 = img[y1, x1]

    top = i00 * (1.0 - du) + i10 * du
    bottom = i01 * (1.0 - du) + i11 * du
    sample = top * (1.0 - dv) + bottom * dv
    sample = sample.reshape(uv.shape[:-1] + (channels,))
    sample = np.where(valid[..., None], sample, np.nan).astype(np.float32)
    return sample, valid


def photometric_sphere_sweep(
    images: tuple[np.ndarray, ...] | list[np.ndarray],
    lut: ProjectionLUT,
    *,
    min_views: int = 2,
) -> PhotometricSweepResult:
    """Run a raw photometric multi-view sweep over fixed radial hypotheses.

    This is intentionally a *geometry validation baseline*, not the final NADIR
    matcher. It keeps the three native fisheye images separate, samples them via
    the calibrated fixed-rig LUT, and scores each depth hypothesis by multi-view
    photometric variance.

    The baseline is useful for falsifying geometry mistakes before introducing a
    learned feature encoder. It is expected to fail on illumination changes,
    weak texture, occlusions and view-dependent appearance; those failure modes
    are precisely why later NADIR-MVS stages use learned/groupwise features.
    """
    if len(images) != lut.valid.shape[0]:
        raise ValueError("number of images must match LUT camera count")
    if min_views < 2 or min_views > len(images):
        raise ValueError("min_views must be between 2 and the camera count")

    sampled: list[np.ndarray] = []
    valid_views: list[np.ndarray] = []
    channels: int | None = None

    for ci, image in enumerate(images):
        values, sampling_valid = bilinear_sample(image, lut.uv_px[ci])
        if channels is None:
            channels = values.shape[-1]
        elif values.shape[-1] != channels:
            raise ValueError("all input images must have the same channel count")

        valid = lut.valid[ci] & sampling_valid
        sampled.append(values)
        valid_views.append(valid)

    values_all = np.stack(sampled, axis=0)  # [C, N, K, D]
    valid_all = np.stack(valid_views, axis=0)  # [C, N, K]
    view_count = np.sum(valid_all, axis=0, dtype=np.uint8)

    weights = valid_all[..., None].astype(np.float32)
    safe_values = np.nan_to_num(values_all, nan=0.0)
    denom = np.maximum(view_count.astype(np.float32), 1.0)[..., None]
    mean = np.sum(safe_values * weights, axis=0) / denom

    residual2 = (safe_values - mean[None, ...]) ** 2
    weighted_residual2 = residual2 * weights
    channel_count = float(channels or 1)
    cost = np.sum(weighted_residual2, axis=(0, 3)) / (
        np.maximum(view_count.astype(np.float32), 1.0) * channel_count
    )

    candidate_valid = view_count >= min_views
    cost = np.where(candidate_valid, cost, np.inf).astype(np.float32)

    any_valid = np.any(np.isfinite(cost), axis=1)
    safe_cost = np.where(np.isfinite(cost), cost, np.inf)
    best_index = np.argmin(safe_cost, axis=1).astype(np.int32)
    depth = lut.depths_m[best_index].astype(np.float32)
    depth = np.where(any_valid, depth, np.nan).astype(np.float32)
    best_index = np.where(any_valid, best_index, -1).astype(np.int32)

    return PhotometricSweepResult(
        cost=cost,
        depth_m=depth,
        best_index=best_index,
        valid=any_valid,
        view_count=view_count,
    )
