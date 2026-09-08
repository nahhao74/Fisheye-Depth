#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import time
from itertools import combinations
from pathlib import Path

import numpy as np

from nadir.data import (
    build_mvs_gi_rig,
    load_mvs_gi_samples,
    read_compressed_float,
    read_mvs_gi_masks,
    read_mvs_gi_rig_reference,
)
from nadir.geometry import (
    array_pixels_to_body_rays,
    project_body_points_to_array,
    triangulate_two_rays,
)
from nadir.geometry.transforms import transform_points
from nadir.stereo.photometric import bilinear_sample


def _read_color(path: Path) -> np.ndarray:
    try:
        import cv2  # type: ignore
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("install the 'mvs-gi' optional dependency") from exc

    image = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
    if image is None:
        raise FileNotFoundError(f"failed to read image: {path}")
    if image.ndim == 2:
        return image
    if image.shape[2] == 4:
        image = image[..., :3]
    return image


def _gray(image: np.ndarray) -> np.ndarray:
    try:
        import cv2  # type: ignore
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("install the 'mvs-gi' optional dependency") from exc

    if image.ndim == 2:
        return image
    return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)


def _native_incidence_deg(camera, uv_array: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    uv_model = np.asarray(uv_array, dtype=np.float64) + float(camera.model.pixel_center_offset)
    rays_C, valid = camera.model.unproject(uv_model)
    z = rays_C[..., 2]
    incidence = np.rad2deg(np.arccos(np.clip(z, -1.0, 1.0)))
    incidence = np.where(valid, incidence, np.nan)
    return incidence, valid


def _rigid_inverse(T_A_B: np.ndarray) -> np.ndarray:
    T = np.asarray(T_A_B, dtype=np.float64)
    R = T[:3, :3]
    t = T[:3, 3]
    out = np.eye(4, dtype=np.float64)
    out[:3, :3] = R.T
    out[:3, 3] = -(R.T @ t)
    return out


def _summary(values: np.ndarray) -> dict:
    x = np.asarray(values, dtype=np.float64)
    x = x[np.isfinite(x)]
    if x.size == 0:
        return {"count": 0, "mean": None, "median": None, "p95": None, "max": None}
    return {
        "count": int(x.size),
        "mean": float(np.mean(x)),
        "median": float(np.median(x)),
        "p95": float(np.quantile(x, 0.95)),
        "max": float(np.max(x)),
    }


def _parse_bins(text: str) -> list[float]:
    values = [float(v.strip()) for v in text.split(",") if v.strip()]
    if len(values) < 2 or any(not np.isfinite(v) for v in values):
        raise ValueError("incidence bins require at least two finite edges")
    if any(b <= a for a, b in zip(values, values[1:])):
        raise ValueError("incidence bin edges must be strictly increasing")
    return values


def _bin_depth_error(incidence_deg: np.ndarray, abs_error_m: np.ndarray, edges: list[float]) -> list[dict]:
    out: list[dict] = []
    inc = np.asarray(incidence_deg, dtype=np.float64)
    err = np.asarray(abs_error_m, dtype=np.float64)
    for lo, hi in zip(edges, edges[1:]):
        mask = np.isfinite(inc) & np.isfinite(err) & (inc >= lo) & (inc < hi)
        stats = _summary(err[mask])
        out.append({"lo_deg": lo, "hi_deg": hi, "depth_abs_error_m": stats})
    return out


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "NADIR Gate A: sparse real-data generalized-camera triangulation. "
            "This harness generates evidence; it does not auto-promote the final pipeline."
        )
    )
    parser.add_argument("root", type=Path, help="local MVS-GI dataset root")
    parser.add_argument("--split", default="validate")
    parser.add_argument("--sample-index", type=int, default=0)
    parser.add_argument("--nfeatures", type=int, default=4000)
    parser.add_argument(
        "--max-matches-per-pair",
        type=int,
        default=0,
        help="0 keeps all ORB cross-check matches; positive value is a compute cap, not an acceptance gate",
    )
    parser.add_argument(
        "--no-source-masks",
        action="store_true",
        help="explicitly disable the released MVS-GI source masks",
    )
    parser.add_argument("--min-triangulation-angle-deg", type=float, default=None)
    parser.add_argument("--max-closest-gap-m", type=float, default=None)
    parser.add_argument("--max-reprojection-px", type=float, default=None)
    parser.add_argument(
        "--incidence-bins-deg",
        default="0,60,90,97.5,112.5,180",
        help="reporting bins only; not pass/fail thresholds",
    )
    parser.add_argument("--json-out", type=Path, default=None)
    args = parser.parse_args()

    if args.sample_index < 0:
        raise ValueError("sample-index must be non-negative")
    if args.nfeatures < 1:
        raise ValueError("nfeatures must be positive")
    if args.max_matches_per_pair < 0:
        raise ValueError("max-matches-per-pair must be >= 0")
    for name in ("min_triangulation_angle_deg", "max_closest_gap_m", "max_reprojection_px"):
        value = getattr(args, name)
        if value is not None and value <= 0.0:
            raise ValueError(f"{name.replace('_', '-')} must be > 0 when supplied")
    incidence_bins = _parse_bins(args.incidence_bins_deg)

    try:
        import cv2  # type: ignore
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("install the 'mvs-gi' optional dependency") from exc

    samples = load_mvs_gi_samples(args.root, split=args.split, strict_paths=True)
    if args.sample_index >= len(samples):
        raise IndexError(
            f"sample-index {args.sample_index} outside split containing {len(samples)} samples"
        )
    sample = samples[args.sample_index]
    rig = build_mvs_gi_rig(args.root)
    rig_ref = read_mvs_gi_rig_reference(args.root)

    images = tuple(_read_color(path) for path in sample.image_paths)
    masks = None if args.no_source_masks else read_mvs_gi_masks(args.root)
    for ci, (camera, image) in enumerate(zip(rig.cameras, images)):
        if image.shape[:2] != (camera.model.height, camera.model.width):
            raise ValueError(
                f"{camera.name} image shape {image.shape[:2]} does not match camera model "
                f"{(camera.model.height, camera.model.width)}"
            )
        if masks is not None and masks[ci].shape != image.shape[:2]:
            raise ValueError(f"source mask shape mismatch for {camera.name}")

    gt_native = read_compressed_float(sample.distance_gt_path)
    detector = cv2.ORB_create(nfeatures=args.nfeatures)

    keypoints = []
    descriptors = []
    detect_t0 = time.perf_counter_ns()
    for ci, image in enumerate(images):
        mask_u8 = None
        if masks is not None:
            mask_u8 = (masks[ci].astype(np.uint8) * 255)
        kp, des = detector.detectAndCompute(_gray(image), mask_u8)
        keypoints.append(kp or [])
        descriptors.append(des)
    detect_ms = (time.perf_counter_ns() - detect_t0) / 1e6

    pair_reports: list[dict] = []
    aggregate_abs_error: list[np.ndarray] = []
    aggregate_rel_error: list[np.ndarray] = []
    aggregate_incidence: list[np.ndarray] = []
    aggregate_gap: list[np.ndarray] = []
    aggregate_reprojection: list[np.ndarray] = []
    aggregate_angle: list[np.ndarray] = []

    matcher = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
    T_R_B = _rigid_inverse(rig_ref.T_B_R)

    pair_t0 = time.perf_counter_ns()
    for ia, ib in combinations(range(len(rig.cameras)), 2):
        cam_a = rig.cameras[ia]
        cam_b = rig.cameras[ib]
        des_a = descriptors[ia]
        des_b = descriptors[ib]
        kp_a = keypoints[ia]
        kp_b = keypoints[ib]

        if des_a is None or des_b is None or len(kp_a) == 0 or len(kp_b) == 0:
            pair_reports.append(
                {
                    "pair": [cam_a.name, cam_b.name],
                    "raw_match_count": 0,
                    "reason": "no_descriptors",
                }
            )
            continue

        matches = sorted(matcher.match(des_a, des_b), key=lambda m: m.distance)
        if args.max_matches_per_pair > 0:
            matches = matches[: args.max_matches_per_pair]
        if not matches:
            pair_reports.append(
                {
                    "pair": [cam_a.name, cam_b.name],
                    "raw_match_count": 0,
                    "reason": "no_crosscheck_matches",
                }
            )
            continue

        uv_a = np.asarray([kp_a[m.queryIdx].pt for m in matches], dtype=np.float64)
        uv_b = np.asarray([kp_b[m.trainIdx].pt for m in matches], dtype=np.float64)
        descriptor_distance = np.asarray([m.distance for m in matches], dtype=np.float64)

        rays_a_B, valid_a = array_pixels_to_body_rays(cam_a, uv_a)
        rays_b_B, valid_b = array_pixels_to_body_rays(cam_b, uv_b)
        incidence_a, incidence_valid_a = _native_incidence_deg(cam_a, uv_a)
        incidence_b, incidence_valid_b = _native_incidence_deg(cam_b, uv_b)
        source_max_incidence = np.maximum(incidence_a, incidence_b)

        tri = triangulate_two_rays(
            np.broadcast_to(cam_a.center_B, rays_a_B.shape),
            rays_a_B,
            np.broadcast_to(cam_b.center_B, rays_b_B.shape),
            rays_b_B,
        )

        uv_a_re, proj_a = project_body_points_to_array(cam_a, tri.point_B)
        uv_b_re, proj_b = project_body_points_to_array(cam_b, tri.point_B)
        reproj_a = np.linalg.norm(uv_a_re - uv_a, axis=-1)
        reproj_b = np.linalg.norm(uv_b_re - uv_b, axis=-1)
        max_reproj = np.maximum(reproj_a, reproj_b)

        geometry_valid = (
            valid_a
            & valid_b
            & incidence_valid_a
            & incidence_valid_b
            & tri.forward_valid
            & proj_a
            & proj_b
            & np.isfinite(max_reproj)
        )

        selected = geometry_valid.copy()
        if args.min_triangulation_angle_deg is not None:
            selected &= np.rad2deg(tri.angle_rad) >= args.min_triangulation_angle_deg
        if args.max_closest_gap_m is not None:
            selected &= tri.closest_gap_m <= args.max_closest_gap_m
        if args.max_reprojection_px is not None:
            selected &= max_reproj <= args.max_reprojection_px

        points_R = transform_points(T_R_B, tri.point_B)
        uv_gt_model, gt_projectable = rig_ref.model.project(points_R)
        uv_gt_array = uv_gt_model - float(rig_ref.model.pixel_center_offset)
        gt_sampled, gt_sample_valid = bilinear_sample(gt_native, uv_gt_array)
        gt_distance = gt_sampled[..., 0]
        pred_distance = np.linalg.norm(points_R, axis=-1)
        gt_valid = (
            gt_projectable
            & gt_sample_valid
            & np.isfinite(gt_distance)
            & (gt_distance > 0.0)
            & np.isfinite(pred_distance)
            & (pred_distance > 0.0)
        )
        evaluated = selected & gt_valid

        abs_error = np.full(pred_distance.shape, np.nan, dtype=np.float64)
        rel_error = np.full(pred_distance.shape, np.nan, dtype=np.float64)
        abs_error[evaluated] = np.abs(pred_distance[evaluated] - gt_distance[evaluated])
        rel_error[evaluated] = abs_error[evaluated] / gt_distance[evaluated]

        aggregate_abs_error.append(abs_error[evaluated])
        aggregate_rel_error.append(rel_error[evaluated])
        aggregate_incidence.append(source_max_incidence[evaluated])
        aggregate_gap.append(tri.closest_gap_m[geometry_valid])
        aggregate_reprojection.append(max_reproj[geometry_valid])
        aggregate_angle.append(np.rad2deg(tri.angle_rad[geometry_valid]))

        pair_reports.append(
            {
                "pair": [cam_a.name, cam_b.name],
                "baseline_m": float(np.linalg.norm(cam_a.center_B - cam_b.center_B)),
                "keypoints": [len(kp_a), len(kp_b)],
                "raw_match_count": len(matches),
                "geometry_forward_valid_count": int(np.count_nonzero(geometry_valid)),
                "selected_by_explicit_filters_count": int(np.count_nonzero(selected)),
                "gt_evaluated_count": int(np.count_nonzero(evaluated)),
                "descriptor_hamming": _summary(descriptor_distance),
                "closest_ray_gap_m": _summary(tri.closest_gap_m[geometry_valid]),
                "reprojection_px_max_of_pair": _summary(max_reproj[geometry_valid]),
                "triangulation_angle_deg": _summary(np.rad2deg(tri.angle_rad[geometry_valid])),
                "source_max_incidence_deg": _summary(source_max_incidence[geometry_valid]),
                "depth_abs_error_m": _summary(abs_error[evaluated]),
                "depth_abs_rel": _summary(rel_error[evaluated]),
                "depth_error_by_source_incidence": _bin_depth_error(
                    source_max_incidence[evaluated], abs_error[evaluated], incidence_bins
                ),
            }
        )

    pair_ms = (time.perf_counter_ns() - pair_t0) / 1e6

    def concat(parts: list[np.ndarray]) -> np.ndarray:
        nonempty = [np.asarray(p) for p in parts if np.asarray(p).size > 0]
        return np.concatenate(nonempty) if nonempty else np.empty((0,), dtype=np.float64)

    all_abs = concat(aggregate_abs_error)
    all_rel = concat(aggregate_rel_error)
    all_incidence = concat(aggregate_incidence)
    all_gap = concat(aggregate_gap)
    all_reproj = concat(aggregate_reprojection)
    all_angle = concat(aggregate_angle)

    report = {
        "task": "NADIR_GATE_A_REAL_GEOMETRY_VALIDATION",
        "scientific_status": (
            "EVIDENCE_GENERATED_OWNER_REVIEW_REQUIRED" if all_abs.size > 0 else "INSUFFICIENT_EVIDENCE"
        ),
        "automatic_pass_fail": False,
        "sample_id": sample.sample_id,
        "source": "MVS-GI bootstrap dataset; does not validate the target 225-degree annulus",
        "matcher": {
            "detector_descriptor": "ORB",
            "matcher": "BF_HAMMING_CROSSCHECK",
            "nfeatures_per_camera": args.nfeatures,
            "max_matches_per_pair": args.max_matches_per_pair,
            "released_source_masks_applied": not args.no_source_masks,
        },
        "explicit_experiment_filters": {
            "min_triangulation_angle_deg": args.min_triangulation_angle_deg,
            "max_closest_gap_m": args.max_closest_gap_m,
            "max_reprojection_px": args.max_reprojection_px,
        },
        "camera_models": [type(camera.model).__name__ for camera in rig.cameras],
        "camera_baseline_matrix_m": rig.baseline_matrix_m().tolist(),
        "keypoint_detection_ms_host": float(detect_ms),
        "matching_triangulation_gt_ms_host": float(pair_ms),
        "pair_reports": pair_reports,
        "aggregate_correspondence_level": {
            "gt_evaluated_count": int(all_abs.size),
            "depth_abs_error_m": _summary(all_abs),
            "depth_abs_rel": _summary(all_rel),
            "closest_ray_gap_m": _summary(all_gap),
            "reprojection_px_max_of_pair": _summary(all_reproj),
            "triangulation_angle_deg": _summary(all_angle),
            "depth_error_by_source_incidence": _bin_depth_error(all_incidence, all_abs, incidence_bins),
        },
        "incidence_reporting_bins_deg": incidence_bins,
        "limitations": [
            "No Gate A acceptance threshold has been frozen; this script cannot declare PASS.",
            "ORB cross-check is a sparse falsification baseline, not the final matcher.",
            "Aggregate rows are correspondence-level and may include the same scene point in more than one camera pair.",
            "MVS-GI public source configuration is a ~195-degree bootstrap and cannot validate the 97.5-112.5 degree target annulus.",
            "Host timing is not QCS8550/QNN timing.",
        ],
    }

    text = json.dumps(report, indent=2, sort_keys=True)
    print(text)
    if args.json_out is not None:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(text + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
