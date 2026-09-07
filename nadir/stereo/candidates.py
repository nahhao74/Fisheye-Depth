from __future__ import annotations

import numpy as np


def uniform_depth_candidates(min_depth_m: float, max_depth_m: float, count: int) -> np.ndarray:
    """Uniform metric-depth hypotheses, ordered near to far."""
    if min_depth_m <= 0.0 or max_depth_m <= min_depth_m:
        raise ValueError("require 0 < min_depth_m < max_depth_m")
    if count < 2:
        raise ValueError("count must be >= 2")
    return np.linspace(min_depth_m, max_depth_m, count, dtype=np.float32)


def uniform_inverse_depth_candidates(
    min_depth_m: float,
    max_depth_m: float,
    count: int,
) -> np.ndarray:
    """Uniform inverse-depth hypotheses, returned in near-to-far metric order.

    This allocates more candidate density to near range, where stereo disparity
    changes faster with depth. It is a baseline to compare against uniform depth
    and later geometry-informed candidate selection; it is not assumed superior
    before measurement.
    """
    if min_depth_m <= 0.0 or max_depth_m <= min_depth_m:
        raise ValueError("require 0 < min_depth_m < max_depth_m")
    if count < 2:
        raise ValueError("count must be >= 2")

    inv_near = 1.0 / min_depth_m
    inv_far = 1.0 / max_depth_m
    inv = np.linspace(inv_near, inv_far, count, dtype=np.float64)
    return (1.0 / inv).astype(np.float32)
