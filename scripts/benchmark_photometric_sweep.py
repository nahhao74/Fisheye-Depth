from __future__ import annotations

import argparse

import numpy as np

from nadir.geometry import CameraRig, DoubleSphereCamera, RigCamera, build_projection_lut, make_lower_hemisphere_grid
from nadir.perf import PerfRecorder
from nadir.stereo import photometric_sphere_sweep, uniform_inverse_depth_candidates


def make_synthetic_rig(size: int) -> CameraRig:
    model = DoubleSphereCamera(
        xi=0.5,
        alpha=0.55,
        fx=size * 0.48,
        fy=size * 0.48,
        cx=(size - 1) / 2.0,
        cy=(size - 1) / 2.0,
        width=size,
        height=size,
    )

    centers = [(-0.10, -0.06, 0.0), (0.10, -0.06, 0.0), (0.0, 0.11, 0.0)]
    cameras = []
    for i, center in enumerate(centers):
        # Cameras are parallel for this synthetic compute-only benchmark.
        T_C_B = np.eye(4, dtype=np.float64)
        T_C_B[:3, 3] = -np.asarray(center)
        cameras.append(RigCamera(name=f"c{i}", model=model, T_C_B=T_C_B))
    return CameraRig(tuple(cameras))


def make_images(size: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    y, x = np.meshgrid(
        np.linspace(0.0, 1.0, size, dtype=np.float32),
        np.linspace(0.0, 1.0, size, dtype=np.float32),
        indexing="ij",
    )
    base = np.stack((x, y, 0.5 * (x + y)), axis=-1)
    return base, np.roll(base, 2, axis=1), np.roll(base, -2, axis=0)


def main() -> None:
    parser = argparse.ArgumentParser(description="NADIR photometric sphere-sweep microbenchmark")
    parser.add_argument("--image-size", type=int, default=384)
    parser.add_argument("--azimuth", type=int, default=128)
    parser.add_argument("--polar", type=int, default=64)
    parser.add_argument("--candidates", type=int, default=8)
    parser.add_argument("--frames", type=int, default=30)
    args = parser.parse_args()

    grid = make_lower_hemisphere_grid(args.azimuth, args.polar)
    rays = grid.rays.reshape(-1, 3)
    depths = uniform_inverse_depth_candidates(0.5, 20.0, args.candidates)
    rig = make_synthetic_rig(args.image_size)
    lut = build_projection_lut(rig, rays, depths)
    images = make_images(args.image_size)

    recorder = PerfRecorder()
    last = None
    for frame_id in range(args.frames):
        recorder.begin_frame(frame_id)
        with recorder.stage("sampling_matching"):
            last = photometric_sphere_sweep(images, lut)
        recorder.end_frame()

    print({
        "note": "synthetic host microbenchmark; not QCS8550 and not end-to-end depth FPS",
        "rays": int(rays.shape[0]),
        "candidates": int(depths.shape[0]),
        "stereo_valid_rays": int(np.count_nonzero(last.valid)) if last is not None else 0,
        **recorder.summary(warmup=min(5, max(args.frames - 1, 0))),
    })


if __name__ == "__main__":
    main()
