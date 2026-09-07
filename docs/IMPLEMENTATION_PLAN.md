# NADIR Implementation Plan

## 1. Guiding rule

Implementation proceeds from measurable geometry and runtime baselines toward learned and sensor-conditioned depth.

Do not begin with a large neural model.

Every milestone must report both:

- scientific performance;
- computational performance.

## 2. Real-time contract

### Hard gate

- throughput >= 15 FPS;
- P95 capture-to-depth latency < 80 ms;
- no uncontrolled memory growth;
- no unexpected CPU fallback in deployed neural graph.

### Design target

- >= 20 FPS;
- P95 latency < 60 ms.

### Stretch target

- 30 FPS.

These are current engineering acceptance targets, not measured results.

## 3. Milestone sequence

### M0 — NADIR-PERF

Build the profiling harness before the model.

Per-frame timing fields should include at least:

```text
capture_ms
geometry_ms
encoder_ms
sampling_ms
matching_ms
regularizer_ms
refine_ms
sensor_prior_ms
total_ms
fps
memory_mb
```

Reports should include P50/P95 latency and rolling FPS.

### M1 — NADIR-CAL

Implement camera-model abstraction and calibration ingestion.

Initial model priority:

1. Double Sphere;
2. Kannala-Brandt/equidistant;
3. EUCM.

Required tests:

- project/unproject round-trip;
- reprojection error versus incidence angle;
- explicit validation beyond 90° incidence.

### M2 — NADIR-RAY

Create a regular lower-hemisphere ray grid for the common output domain.

Start with a QNN-friendly regular angular tensor rather than a graph representation.

Initial candidate size can be approximately 8k rays for geometry development, but final resolution must be chosen from accuracy/runtime measurements.

### M3 — NADIR-VIS

For every output ray, precompute:

- visibility mask;
- available camera pairs;
- effective baseline;
- triangulation angle/conditioning;
- valid projection domain.

This milestone determines where metric spatial stereo is actually observable.

### M4 — NADIR-CQ / QMAP

Characterize whether and how image/matching quality changes across the 225° FoV.

Do not assume monotonic edge degradation.

Measure:

- calibration residual;
- sharpness/contrast;
- vignetting/SNR proxy;
- feature repeatability;
- pairwise stereo match quality.

Only then evaluate quality weighting, piecewise weighting, best-view selection, or view peeling.

### M5 — NADIR-TRI

Build a classical sparse geometry baseline.

Suggested progression:

- ORB/SIFT or another robust detector;
- pair matching + geometric rejection;
- generalized-ray triangulation;
- SVD/QR solution;
- error versus range and incidence angle.

The purpose is to prove metric observability before relying on a neural model.

### M6 — NADIR-LUT

Precompute fixed-rig projection/sampling maps for the common ray grid and fixed candidate depths.

Conceptual shapes:

- projection LUT: `[camera, ray, candidate, uv]`;
- validity LUT: `[camera, ray, candidate]`.

Benchmark dynamic projection versus LUT sampling.

### M7 — NADIR-MVS-V0

First dense learned baseline.

Initial architecture direction:

```text
3 native fisheye RGB images
        ↓
shared lightweight encoder
        ↓
small feature maps
        ↓
K = 8 or 16 radial hypotheses
        ↓
LUT-based sampling
        ↓
pairwise/groupwise correlation
        ↓
compact 2D regularizer
        ↓
metric radial depth
```

Avoid a large 3D CNN cost volume in V0.

Suggested parameter target: < 5–10M parameters unless experiments justify more.

### M8 — NADIR-GI

Evaluate candidate sampling schemes:

- uniform depth;
- inverse depth;
- geometry-informed candidate selection;
- later local/adaptive refinement.

Required table for each candidate count `K`:

| K | AbsRel | RMSE | bad-depth | FPS | P95 ms | peak RAM |
|---:|---:|---:|---:|---:|---:|---:|
| 4 | | | | | | |
| 8 | | | | | | |
| 16 | | | | | | |
| 32 | | | | | | |

Only Pareto-useful configurations should remain.

### M9 — NADIR-MOTION

Add temporal conditioning only after spatial MVS is validated.

Use IMU/state information to:

- de-rotate temporal correspondence;
- propagate previous depth;
- narrow candidate ranges.

A desirable outcome is that sensor conditioning reduces, rather than increases, total matching compute.

### M10 — NADIR-RTK

Add RTK/GNSS translation constraints with uncertainty-aware gating.

Ablations must separate:

- camera-only;
- camera + IMU;
- camera + IMU + RTK.

### M11 — NADIR-EDGE

Deploy and profile on the target QCS8550-class device.

Flow:

```text
PyTorch/host baseline
    ↓
ONNX
    ↓
QNN-compatible graph
    ↓
FP16 / PTQ INT8
    ↓
QAT INT8 if required
    ↓
target-device profiling
```

## 4. Immediate work order

The next implementation work should be:

1. obtain and inspect MVS-GI data/configuration;
2. implement the common dataset loader;
3. implement NADIR-PERF;
4. implement Double Sphere project/unproject;
5. build the lower-hemisphere ray grid;
6. generate visibility/observability maps;
7. build a simple sphere/ray sweep before introducing a large learned model.

The first success criterion is a single synchronized 3-fisheye sample producing a geometry-correct metric depth estimate with ground truth comparison and timing measurements.