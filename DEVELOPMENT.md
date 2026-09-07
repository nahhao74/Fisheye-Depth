# NADIR Development Baseline v0.1

This baseline starts implementation with the pieces that must be correct before a learned stereo network is introduced.

## Included

- `nadir.perf`: backend-independent per-frame/stage profiler and the initial NADIR real-time gate.
- `nadir.geometry.double_sphere`: native-fisheye Double Sphere projection/unprojection.
- `nadir.geometry.rays`: regular lower-hemisphere ray tensor in Rig/Body FRD coordinates.
- `nadir.geometry.transforms`: explicit point/ray frame transforms.
- `nadir.data.manifest`: dataset-independent three-camera sample contract.
- geometry and profiler unit tests.
- ray-grid generation and geometry microbenchmark scripts.

## Coordinate convention

- Navigation/global state: NED.
- UAV body/rig: FRD (`+X forward`, `+Y right`, `+Z down`).
- Each camera keeps its calibrated native camera frame.
- Dense depth is radial range from the rig reference origin along a rig-frame unit ray.

## Real-time contract

Initial hard gate:

- mean-latency-derived throughput >= 15 FPS;
- P95 end-to-end latency <= 80 ms.

Design target remains >= 20 FPS. These are engineering acceptance gates, not claimed measurements for QCS8550 yet.

## Why the MVS-GI loader is manifest-driven

The code deliberately does **not** assume an undocumented MVS-GI folder layout. After the dataset is downloaded and inspected, an adapter will produce `nadir.sample_manifest.v1`. This prevents silently binding the implementation to guessed filenames/calibration semantics.

## Local validation

```bash
python -m pip install -e '.[dev]'
pytest
python scripts/build_ray_grid.py
python scripts/benchmark_geometry.py
```

The next implementation milestone is to inspect/download MVS-GI, write a verified adapter, then build `VIS/observability` and the first non-neural sphere-sweep baseline.
