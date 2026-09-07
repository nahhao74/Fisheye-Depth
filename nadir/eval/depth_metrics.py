from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class DepthMetrics:
    valid_count: int
    mae_m: float
    rmse_m: float
    abs_rel: float
    bad_rate: float | None = None
    bad_rel_threshold: float | None = None


def compute_depth_metrics(
    predicted_m: np.ndarray,
    ground_truth_m: np.ndarray,
    *,
    mask: np.ndarray | None = None,
    bad_rel_threshold: float | None = None,
) -> DepthMetrics:
    """Compute basic metric radial-depth errors without embedding acceptance gates.

    Only finite positive ground-truth values and finite predictions are evaluated.
    ``bad_rel_threshold`` is optional because the project has not yet frozen a
    scientific bad-depth threshold; callers must state the value explicitly.
    """
    pred = np.asarray(predicted_m, dtype=np.float64)
    gt = np.asarray(ground_truth_m, dtype=np.float64)
    if pred.shape != gt.shape:
        raise ValueError("predicted_m and ground_truth_m must have the same shape")

    valid = np.isfinite(pred) & np.isfinite(gt) & (gt > 0.0)
    if mask is not None:
        user_mask = np.asarray(mask, dtype=bool)
        if user_mask.shape != pred.shape:
            raise ValueError("mask must match depth shape")
        valid &= user_mask

    count = int(np.count_nonzero(valid))
    if count == 0:
        return DepthMetrics(
            valid_count=0,
            mae_m=float("nan"),
            rmse_m=float("nan"),
            abs_rel=float("nan"),
            bad_rate=None if bad_rel_threshold is None else float("nan"),
            bad_rel_threshold=bad_rel_threshold,
        )

    err = pred[valid] - gt[valid]
    abs_err = np.abs(err)
    rel = abs_err / gt[valid]

    bad_rate: float | None = None
    if bad_rel_threshold is not None:
        if bad_rel_threshold <= 0.0:
            raise ValueError("bad_rel_threshold must be > 0 when provided")
        bad_rate = float(np.mean(rel > bad_rel_threshold))

    return DepthMetrics(
        valid_count=count,
        mae_m=float(np.mean(abs_err)),
        rmse_m=float(np.sqrt(np.mean(err * err))),
        abs_rel=float(np.mean(rel)),
        bad_rate=bad_rate,
        bad_rel_threshold=bad_rel_threshold,
    )
