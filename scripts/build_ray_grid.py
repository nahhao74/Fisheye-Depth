#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np

from nadir.geometry import make_lower_hemisphere_grid


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--azimuth", type=int, default=128)
    parser.add_argument("--polar", type=int, default=64)
    parser.add_argument("--output", type=Path, default=Path("artifacts/ray_grid_128x64.npz"))
    args = parser.parse_args()

    grid = make_lower_hemisphere_grid(args.azimuth, args.polar)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        args.output,
        rays=grid.rays.astype(np.float32),
        azimuth_rad=grid.azimuth_rad.astype(np.float32),
        polar_from_down_rad=grid.polar_from_down_rad.astype(np.float32),
    )
    print(f"saved {grid.shape[0]}x{grid.shape[1]} rays -> {args.output}")


if __name__ == "__main__":
    main()
