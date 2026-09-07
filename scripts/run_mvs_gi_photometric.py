#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np

from nadir.data import (
    build_mvs_gi_rig,
    load_mvs_gi_samples,
    read_compressed_float,
    read_mvs_gi_rig_reference,
)
from nadir.eval import compute_depth_metrics, distance_image_to_ray_grid
from nadir.geometry import build_projection_lut, make_lower_hemisphere_grid
from nadir.perf import PerfRecorder
from nadir.stereo import (
    photometric_sphere_sweep,
    uniform_depth_candidates,
    uniform_inverse_depth_candidates,
)


def _read_image(path: Path) -> np.ndarray:
    try:
        import cv2  # type: ignore
    except ImportError as exc:  # pragma: no cover - dependency-specific
        raise RuntimeError("install the 'mvs-gi' optional dependency to read source images") from exc

    image = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
    if image is None:
        raise FileNotFoundError(f"failed to read image: {path}")
    if image.ndim == 3 and image.shape[2] == 4:
        # RGB source alpha is not a photometric channel. Geometric validity is
        # carried by the camera model and later by the released source masks.
        image = image[..., :3]
    return image


def _percentile_deg(values_rad: np.ndarray, q: float) -> float:
    values = np.asarray(values_rad, dtype=np.float64)
    values = values[np.isfinite(values)]
    if values.size == 0:
        return float("nan")
    return float(np.rad2deg(np.quantile(values, q)))


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Run NADIR's non-neural 3-fisheye photometric sweep on one MVS-GI sample. "
            "This is a geometry-validation baseline, not the final learned matcher."
        )
    )
    parser.add_argument("root", type=Path, help="MVS-GI dataset root")
    parser.add_argument("--split", default="validate")
    parser.add_argument("--sample-index", type=int, default=0)
    parser.add_argument("--min-depth-m", type=float, default=0.5)
    parser.add_argument("--max-depth-m", type=float, default=100.0)
    parser.add_argument("--candidates", type=int, default=8)
    parser.add_argument("--candidate-mode", choices=("depth", "inverse"), default="inverse")
    parser.add_argument("--azimuth", type=int, default=128)
    parser.add_argument("--polar", type=int, default=64)
    parser.add_argument("--min-views", type=int, default=2)
    parser.add_argument("--repeats", type=int, default=10)
    parser.add_argument("--warmup", type=int, default=2)
    parser.add_argument(
        "--max-gt-angular-error-deg",
        type=float,
        default=None,
        help=(
            "Optional explicit mask for nearest-ray GT reprojection. No threshold is applied "
            "unless this option is supplied."
        ),
    )
    parser.add_argument("--json-out", type=Path, default=None)
    args = parser.parse_args()

    if args.sample_index < 0:
        raise ValueError("sample-index must be non-negative")
    if args.repeats < 1 or args.warmup < 0 or args.warmup >= args.repeats:
        raise ValueError("require repeats >= 1 and 0 <= warmup < repeats")

    samples = load_mvs_gi_samples(args.root, split=args.split, strict_paths=True)
    if args.sample_index >= len(samples):
        raise IndexError(
            f"sample-index {args.sample_index} outside dataset split with {len(samples)} samples"
        )
    sample = samples[args.sample_index]

    rig = build_mvs_gi_rig(args.root)
    rig_ref = read_mvs_gi_rig_reference(args.root)
    images = tuple(_read_image(path) for path in sample.image_paths)
    for camera, image in zip(rig.cameras, images):
        if image.shape[:2] != (camera.model.height, camera.model.width):
            raise ValueError(
                f"{camera.name} image shape {image.shape[:2]} does not match native model "
                f"{(camera.model.height, camera.model.width)}"
            )

    grid = make_lower_hemisphere_grid(
        n_azimuth=args.azimuth,
        n_polar=args.polar,
    )
    if args.candidate_mode == "depth":
        depths = uniform_depth_candidates(args.min_depth_m, args.max_depth_m, args.candidates)
    else:
        depths = uniform_inverse_depth_candidates(
            args.min_depth_m, args.max_depth_m, args.candidates
        )

    lut_t0 = time.perf_counter_ns()
    lut = build_projection_lut(rig, grid.rays, depths)
    lut_build_ms = (time.perf_counter_ns() - lut_t0) / 1e6

    recorder = PerfRecorder()
    result = None
    for frame_id in range(args.repeats):
        recorder.begin_frame(frame_id)
        with recorder.stage("photometric_sweep"):
            result = photometric_sphere_sweep(images, lut, min_views=args.min_views)
        recorder.end_frame()
    assert result is not None

    pred_depth = result.depth_m.reshape(grid.shape)
    pred_valid = result.valid.reshape(grid.shape)

    gt_native = read_compressed_float(sample.distance_gt_path)
    gt = distance_image_to_ray_grid(
        gt_native,
        source_model=rig_ref.model,
        T_B_C=rig_ref.T_B_R,
        ray_grid=grid,
    )

    eval_mask = pred_valid & gt.valid
    gt_threshold_deg = args.max_gt_angular_error_deg
    if gt_threshold_deg is not None:
        if gt_threshold_deg <= 0.0:
            raise ValueError("max-gt-angular-error-deg must be > 0")
        eval_mask &= gt.angular_error_rad <= np.deg2rad(gt_threshold_deg)

    metrics = compute_depth_metrics(pred_depth, gt.depth_m, mask=eval_mask)
    perf = recorder.summary(warmup=args.warmup)
    hard_gate = recorder.realtime_gate(warmup=args.warmup)

    valid_gt_errors = gt.angular_error_rad[gt.valid]
    report = {
        "baseline": "NADIR_MVS_GI_PHOTOMETRIC_V0",
        "scientific_role": "geometry_validation_not_final_matcher",
        "sample_id": sample.sample_id,
        "candidate_mode": args.candidate_mode,
        "candidate_count": int(args.candidates),
        "candidate_depths_m": [float(x) for x in depths],
        "ray_grid": {"H": int(grid.shape[0]), "W": int(grid.shape[1])},
        "camera_models": [type(camera.model).__name__ for camera in rig.cameras],
        "camera_baseline_matrix_m": rig.baseline_matrix_m().tolist(),
        "pixel_center_offsets": [float(camera.model.pixel_center_offset) for camera in rig.cameras],
        "lut_build_ms_offline": float(lut_build_ms),
        "stereo_hypothesis_valid_fraction": float(np.mean(lut.view_count >= args.min_views)),
        "predicted_ray_valid_fraction": float(np.mean(pred_valid)),
        "gt_ray_valid_fraction": float(np.mean(gt.valid)),
        "eval_ray_count": int(np.count_nonzero(eval_mask)),
        "gt_reprojection_angular_error_p50_deg": _percentile_deg(valid_gt_errors, 0.50),
        "gt_reprojection_angular_error_p95_deg": _percentile_deg(valid_gt_errors, 0.95),
        "gt_angular_error_mask_deg": gt_threshold_deg,
        "metrics": {
            "valid_count": metrics.valid_count,
            "mae_m": metrics.mae_m,
            "rmse_m": metrics.rmse_m,
            "abs_rel": metrics.abs_rel,
        },
        "host_runtime": perf,
        "host_realtime_gate": hard_gate,
        "runtime_scope": (
            "photometric sweep only; RGB decode, GT conversion and precomputed LUT build are "
            "excluded from per-frame timing"
        ),
        "limitations": {
            "released_source_masks_applied": False,
            "learned_features": False,
            "qcs8550_measurement": False,
            "gt_nearest_ray_reprojection": True,
        },
    }

    text = json.dumps(report, indent=2, sort_keys=True)
    print(text)
    if args.json_out is not None:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(text + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
