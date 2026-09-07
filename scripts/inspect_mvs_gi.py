#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np

from nadir.data.mvs_gi import discover_csv_sources, load_samples, read_compressed_float


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate the public MVS-GI source layout before NADIR conversion."
    )
    parser.add_argument("root", type=Path, help="MVS-GI dataset root")
    parser.add_argument("--split", default="validate")
    parser.add_argument("--max-samples", type=int, default=3)
    parser.add_argument(
        "--allow-missing-payloads",
        action="store_true",
        help="inspect CSV semantics without requiring every referenced image to exist",
    )
    parser.add_argument(
        "--decode-first-gt",
        action="store_true",
        help="decode the first compressed float32 GT image (requires .[mvs-gi])",
    )
    args = parser.parse_args()

    sources = discover_csv_sources(args.root, split=args.split)
    samples = load_samples(
        args.root,
        split=args.split,
        strict_paths=not args.allow_missing_payloads,
    )

    print(f"root: {args.root}")
    print(f"split: {args.split}")
    print(f"trajectory_csv_count: {len(sources)}")
    print(f"sample_count: {len(samples)}")

    for sample in samples[: max(args.max_samples, 0)]:
        print("-")
        print(f"sample_id: {sample.sample_id}")
        for ci, p in enumerate(sample.image_paths):
            print(f"cam{ci}: {p}")
        print(f"distance_gt: {sample.distance_gt_path}")
        print(f"source_csv: {sample.source_csv}")

    if args.decode_first_gt:
        if not samples:
            raise RuntimeError("cannot decode GT: no samples were discovered")
        distance = read_compressed_float(samples[0].distance_gt_path)
        finite = np.isfinite(distance)
        print("-")
        print(f"gt_shape: {distance.shape}")
        print(f"gt_dtype: {distance.dtype}")
        print(f"gt_finite_fraction: {float(np.mean(finite)):.6f}")
        if np.any(finite):
            print(f"gt_min_m: {float(np.min(distance[finite])):.6f}")
            print(f"gt_max_m: {float(np.max(distance[finite])):.6f}")


if __name__ == "__main__":
    main()
