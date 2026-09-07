# NADIR Development Baseline v0.3

This baseline now reaches the first dense **non-neural native-fisheye sphere/ray sweep** substrate. The goal remains to prove geometry, observability, depth semantics and runtime structure before a learned feature encoder is introduced.

## Included

- `nadir.perf`: backend-independent per-frame/stage profiler and the initial NADIR real-time gate.
- `nadir.geometry.double_sphere`: native-fisheye Double Sphere projection/unprojection with explicit valid projection domain, including tests beyond 90° incidence.
- `nadir.geometry.rays`: regular lower-hemisphere ray tensor in Rig/Body FRD coordinates.
- `nadir.geometry.transforms`: explicit point/ray frame transforms.
- `nadir.geometry.rig`: calibrated multi-camera rig with explicit `T_C_B` semantics and rigid-transform validation.
- `nadir.geometry.lut`: fixed-rig projection LUT over ray/depth hypotheses, candidate-aware validity, visibility bitmask and view count.
- `nadir.geometry.observability`: physical baseline, effective perpendicular baseline, candidate-range triangulation angle and pair projection validity without arbitrary scientific thresholds.
- `nadir.stereo.candidates`: uniform-depth and uniform-inverse-depth baseline candidate generators.
- `nadir.stereo.photometric`: first non-neural multi-view photometric variance sweep using native fisheye LUT sampling.
- `nadir.eval`: metric radial-depth MAE/RMSE/AbsRel with optional explicitly supplied bad-depth threshold.
- `nadir.data.manifest`: dataset-independent three-camera sample contract.
- dataset-tree inspection and geometry/sweep microbenchmark scripts.
- unit tests covering geometry, profiler contract, LUT/observability, candidate generation, metrics and photometric depth selection.
- GitHub Actions test workflow added for repository-level regression checks.

## Coordinate convention

- Navigation/global state: NED.
- UAV body/rig: FRD (`+X forward`, `+Y right`, `+Z down`).
- Each camera keeps its calibrated native camera frame.
- `T_C_B` transforms Body/Rig coordinates into camera coordinates.
- Dense depth is radial range from the rig reference origin along a rig-frame unit ray.

## Important correction: visibility is depth-dependent

A three-camera fisheye rig is a generalized camera: the camera centers are spatially separated. Therefore a common output direction alone is not the authoritative visibility state for a finite point.

The implementation now uses:

```text
visibility[camera, ray, depth_candidate]
```

and derives a compact per-hypothesis bitmask from it. A direction-only visibility map may still be used as an approximate/far-field diagnostic, but not as the final geometry contract.

## Real-time contract

Initial hard gate:

- mean-latency-derived throughput >= 15 FPS;
- P95 end-to-end latency <= 80 ms.

Design target remains >= 20 FPS; stretch target remains 30 FPS. These are engineering acceptance gates, not claimed QCS8550 measurements.

The new `scripts/benchmark_photometric_sweep.py` measures the NumPy sampling/matching substrate on synthetic geometry. Its output must be labelled as a **host microbenchmark**, not as onboard or end-to-end depth FPS.

## Scientific status of the photometric sweep

The first sweep intentionally uses raw multi-view photometric variance. It is not expected to be robust to:

- exposure differences;
- weak/repeated texture;
- occlusion boundaries;
- view-dependent appearance;
- real fisheye optical degradation.

Its role is to falsify geometry and LUT errors. If a synthetic or controlled sample with known geometry cannot select the correct radial hypothesis, a neural matcher must not be introduced to hide that failure.

## Double Sphere verification

The projection/unprojection implementation follows the Double Sphere model equations and now enforces the valid 3-D projection domain rather than treating a finite projection denominator as sufficient. A >90° ray roundtrip is covered explicitly because the target 225° lens requires rays with camera-frame `z < 0`.

## MVS-GI data status

The repository remains manifest-driven because the final MVS-GI adapter must be based on inspected file/calibration semantics rather than guessed paths. Public MVS-GI documentation confirms the released dataset uses 3 fisheye cameras facing the same direction, while the released code uses a 195° camera configuration; this dataset is therefore a bootstrap source, not evidence for the final 225° edge region.

## Local validation commands

```bash
python -m pip install -e '.[dev]'
pytest
python scripts/build_ray_grid.py
python scripts/benchmark_geometry.py
python scripts/benchmark_photometric_sweep.py --candidates 8
```

## Next milestone

1. download/inspect a small MVS-GI validation/sample subset and freeze the exact calibration + image + GT semantics;
2. implement a verified MVS-GI -> `nadir.sample_manifest.v1` adapter;
3. convert/compare the dataset GT to NADIR radial-range semantics on the common ray grid;
4. run the non-neural sphere sweep on one real dataset sample and produce an error + latency report;
5. compare `K = 4/8/16/32`, uniform depth vs inverse depth, before introducing a learned encoder;
6. only after the geometry baseline is trustworthy, begin `NADIR-MVS-V0` with a shared lightweight feature encoder.
