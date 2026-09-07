#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json

import numpy as np

from nadir.geometry import DoubleSphereCamera
from nadir.perf import PerfRecorder


def main() -> None:
    parser = argparse.ArgumentParser(description="Synthetic DS project/unproject microbenchmark")
    parser.add_argument("--frames", type=int, default=200)
    parser.add_argument("--points", type=int, default=8192)
    args = parser.parse_args()

    # Synthetic parameters are for implementation benchmarking only, not a rig calibration.
    cam = DoubleSphereCamera(
        xi=0.5,
        alpha=0.55,
        fx=300.0,
        fy=300.0,
        cx=320.0,
        cy=320.0,
        width=640,
        height=640,
    )
    rng = np.random.default_rng(7)
    uv = np.column_stack(
        [rng.uniform(80, 560, args.points), rng.uniform(80, 560, args.points)]
    )
    recorder = PerfRecorder()

    for frame_id in range(args.frames):
        recorder.begin_frame(frame_id)
        with recorder.stage("unproject"):
            rays, valid = cam.unproject(uv)
        with recorder.stage("project"):
            _, valid2 = cam.project(rays[valid])
        if not np.all(valid2):
            raise RuntimeError("Synthetic roundtrip produced invalid projections")
        recorder.end_frame()

    warmup = min(10, args.frames // 10)
    print(json.dumps(recorder.summary(warmup=warmup), indent=2))
    print(json.dumps(recorder.realtime_gate(warmup=warmup), indent=2))


if __name__ == "__main__":
    main()
