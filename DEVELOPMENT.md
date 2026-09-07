# NADIR Development Baseline v0.2

This baseline implements the geometry/performance substrate that must be correct before a learned stereo network is introduced.

## Included

- `nadir.perf`: backend-independent per-frame/stage profiler and the initial NADIR real-time gate.
- `nadir.geometry.double_sphere`: native-fisheye Double Sphere projection/unprojection.
- `nadir.geometry.rays`: regular lower-hemisphere ray tensor in Rig/Body FRD coordinates.
- `nadir.geometry.transforms`: explicit point/ray frame transforms.
- `nadir.geometry.rig`: calibrated multi-camera rig with explicit `T_C_B` semantics.
- `nadir.geometry.lut`: fixed-rig projection LUT over ray/depth hypotheses.
- `nadir.geometry.observability`: pair baseline and triangulation-angle metrics without arbitrary acceptance thresholds.
- `nadir.data.manifest`: dataset-independent three-camera sample contract.
- geometry, LUT, observability and profiler unit tests.
- ray-grid generation and geometry microbenchmark scripts.

## Coordinate convention

- Navigation/global state: NED.
- UAV body/rig: FRD (`+X forward`, `+Y right`, `+Z down`).
- Each camera keeps its calibrated native camera frame.
- `T_C_B` transforms Body/Rig coordinates into camera coordinates.
- Dense depth is radial range from the rig reference origin along a rig-frame unit ray.

## Real-time contract

Initial hard gate:

- mean-latency-derived throughput >= 15 FPS;
- P95 end-to-end latency <= 80 ms.

Design target remains >= 20 FPS. These are engineering acceptance gates, not claimed measurements for QCS8550 yet.

## Local validation performed for this baseline

The implementation was exercised with synthetic Double Sphere parameters and synthetic rig geometry before being pushed:

- 5 unit tests passed for projection/unprojection, FRD ray-grid semantics, profiler contract, LUT construction and triangulation geometry.
- A synthetic 8192-point Double Sphere project/unproject microbenchmark measured about 0.83 ms mean and about 1.10 ms P95 on the development container. This is **not** a QCS8550 result and is not an end-to-end depth FPS claim.

## Why the MVS-GI loader is manifest-driven

The code deliberately does **not** assume an undocumented MVS-GI folder layout. After the dataset is downloaded and inspected, an adapter will produce `nadir.sample_manifest.v1`. This prevents silently binding the implementation to guessed filenames/calibration semantics.

## Local validation commands

```bash
python -m pip install -e '.[dev]'
pytest
python scripts/build_ray_grid.py
python scripts/benchmark_geometry.py
```

## Next milestone

1. inspect/download MVS-GI and freeze its actual file/calibration semantics;
2. implement a verified MVS-GI -> `nadir.sample_manifest.v1` adapter;
3. generate per-ray/per-depth camera visibility from the real rig calibration;
4. build the first non-neural native-fisheye sphere-sweep baseline;
5. compare predicted radial depth against GT before any learned feature encoder is introduced.
