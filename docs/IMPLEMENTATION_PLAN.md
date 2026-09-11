# NADIR Implementation Plan

## 1. Guiding rule

The current scientific task remains **Gate A real-data geometry feasibility**. Downstream architecture work is documented as hypothesis only until Gate A is reviewed.

After Gate A, implementation is **latency-first**:

```text
1. P95 latency
2. robustness / catastrophic-error avoidance
3. coarse metric-range accuracy
4. fine accuracy
```

Do not begin with a large neural model. Do not flatten or stitch fisheye RGB before stereo.

Every milestone must report both scientific and computational performance, with P95 latency treated as the primary deployment metric.

## 2. Real-time contract

### Hard target

- throughput >= 15 FPS;
- P95 capture-to-depth latency < 80 ms;
- no uncontrolled memory growth;
- no unexpected CPU fallback in deployed accelerated graphs.

### Design target

- >= 20 FPS;
- P95 latency < 60 ms.

### Stretch target

- 30 FPS.

These are engineering targets, not measured results.

## 3. Current active milestone — Gate A

The immediate task is not dense depth optimization. It is to establish or falsify:

```text
known native fisheye camera models
+ known physical camera-center baselines
+ real synchronized correspondences
    -> metric triangulated range consistent with GT
```

Use the existing sparse harness first:

```bash
python scripts/run_gate_a_sparse.py /path/to/MVS_GI_ROOT \
  --sample-index 0 \
  --json-out /media/nahhao74/KINGSTON/nadir_gate_a/sample0.json
```

No downstream matcher/scheduler is promoted before this evidence is understood.

## 4. Post-Gate-A milestone sequence

### M0 — NADIR-PERF

Build/extend profiling before optimization.

Per-frame timing should include at least:

```text
capture_ms
preprocess_ms
geometry_ms
signal_or_descriptor_ms
scheduler_ms
temporal_warp_ms
candidate_generation_ms
matching_ms
pair_consensus_ms
memory_update_ms
total_ms
fps
memory_mb
```

Also record:

```text
active_ray_fraction
mean_candidates_per_active_ray
mean_pairs_per_active_ray
mean_signal_bands_or_channels
bootstrap_or_track_mode
```

Reports must include P50/P95 latency, not only mean FPS.

### M1 — NADIR-RAYLUT

Compile calibration into per-camera native-ray lookup tables:

```text
ray_C
solid_angle
valid
```

Later optional fields may include measured static quality. This layer must preserve camera identity and physical centers.

Required tests:

- project/unproject round trip;
- solid-angle numerical consistency;
- explicit >90° incidence coverage;
- camera-model replacement without changing downstream ray-domain contracts.

### M2 — NADIR-OBS

For every candidate output ray/region, characterize:

- visibility mask;
- available camera pairs;
- effective baseline;
- triangulation angle/conditioning;
- projection validity;
- incidence region.

Pre-rank camera pairs where possible.

### M3 — NADIR-CQ

Measure real optical/matching quality versus angular position:

- calibration residual;
- sharpness/MTF proxy;
- contrast/SNR;
- vignetting/exposure clipping;
- feature repeatability;
- pairwise correspondence quality.

Do not assume monotonic edge degradation.

### M4 — NADIR-MATCH-BENCH

Benchmark candidate local measurement engines on the same native-ray geometry:

#### A. ORB / classical sparse reference

Retain as an interpretable geometry baseline.

#### B. Census / Hamming

Cheap DSP-friendly local comparison with projected native-ray hypotheses.

#### C. Spherical DSP signal

Evaluate a local steerable harmonic/Fourier-Bessel representation inspired by the reviewed spherical signal matcher. Important variables:

- number of active anchors;
- angular orders used;
- number of radial-frequency bands;
- local pool radius;
- progressive band loading;
- early-rejection rate;
- signal construction cost.

Do **not** assume a full high-order/high-band representation is suitable for all pixels.

#### D. Tiny learned feature

Only after deterministic baselines exist. Keep it small and shared across cameras.

Required comparison:

| Matcher | coarse range error | catastrophic error | near/new recall | P50 ms | P95 ms | peak RAM |
|---|---:|---:|---:|---:|---:|---:|
| ORB/ref | | | | | | |
| Census | | | | | | |
| spherical DSP | | | | | | |
| tiny learned | | | | | | |

### M5 — NADIR-LAMBDA

Benchmark pairwise search variables:

- direct radial depth;
- inverse depth;
- `lambda = B / d`.

For the lambda formulation, use the native-sphere epipolar hypothesis and Jacobian `J_lambda` to test:

- adaptive coarse spacing;
- local refinement;
- conditioning/information scoring;
- candidate-count reduction.

The winner is chosen by latency/robustness Pareto evidence, not elegance.

### M6 — NADIR-PAIR

Exploit the three physical camera pairs `01`, `02`, `12` without paying for all three by default.

Policy to test:

1. best pair first;
2. early exit on sufficient confidence;
3. second pair if ambiguous;
4. third pair only as fallback/consistency evidence.

Compare:

- all-pairs always;
- best-pair only;
- best-pair-first adaptive;
- robust 2-of-3 consensus / median;
- information-weighted fusion;
- view peeling under explicit occlusion tests.

### M7 — NADIR-MEM

Introduce persistent scene/range memory after a trustworthy spatial measurement exists.

Per retained element store at least:

```text
range_or_point
uncertainty
timestamp
age
observation_count
source_pair_or_cameras
static_or_dynamic_state
```

Do not require a dense point cloud every frame. Compare sparse points, surfels and lightweight voxel/hash organization only as needed.

### M8 — NADIR-TEMPORAL

Add geometric temporal propagation before learned temporal models.

Use relative SE(3) to warp previous 3-D/range state into the current rig frame. The resulting prior should narrow the local search interval.

Ablate:

- frame-independent full search;
- history prior only;
- history + cheap consistency check;
- history + local correction.

Primary question: does steady-state P95 latency fall without unacceptable catastrophic errors?

### M9 — NADIR-SCHED

Add event-triggered/adaptive spatial compute allocation.

Priority signals may include:

- temporal innovation/image change;
- propagated uncertainty;
- depth discontinuity/local curvature;
- newly visible region;
- stale age;
- near-range / closing / TTC priority;
- pair disagreement.

The AMR analogy is limited to adaptive resolution:

```text
smooth/stable -> coarse/reuse
changing/boundary/uncertain -> refine
```

Do not introduce Navier-Stokes/CFD simulation into the depth core.

Required ablation examples:

```text
100% active rays
50%
25%
12.5%
```

For each case report P95 latency, catastrophic error, near/new recall and rebootstrap rate.

### M10 — NADIR-MOTION

Add IMU after temporal geometry works camera-only.

Use IMU/state information to:

- de-rotate temporal correspondence;
- improve relative-pose prediction;
- propagate previous range more accurately;
- reduce active search width.

A useful IMU module should reduce total matching compute rather than add a heavy sensor network.

### M11 — NADIR-RTK

Add RTK/GNSS translation constraints with covariance/status-aware gating.

Ablations must separate:

- camera/history only;
- + IMU;
- + IMU + RTK FIX;
- degraded/FLOAT/LOST GNSS cases.

### M12 — NADIR-EDGE

Deploy and profile the surviving pipeline on the target QCS8550-class device.

Potential accelerated pieces include:

- static ray/geometry LUT access;
- image/DSP preprocessing;
- Census/Hamming or vectorized spherical signal operations;
- small learned blocks if retained;
- compact correlation/fusion.

Flow for learned components only:

```text
host baseline
    ↓
ONNX
    ↓
QNN-compatible graph
    ↓
FP16 / PTQ INT8
    ↓
QAT INT8 only if necessary
```

Do not infer target latency from desktop host timings.

## 5. Bootstrap / track / rebootstrap contract

### BOOTSTRAP

Use wider coverage/search to initialize history. It may be slower than steady state but must be separately timed and bounded.

### TRACK / UPDATE

Use prediction, narrow search, active anchors, best-pair-first evaluation and early exit.

### REBOOTSTRAP

Trigger on confidence/coverage collapse, large scene change, pose jump, excessive dynamics or stale uncertainty.

Report rebootstrap frequency because a fast steady state that constantly reboots is not a useful real-time system.

## 6. Acceptance metrics

Every post-Gate-A experiment should report at least:

```text
P50 total latency
P95 total latency
FPS
peak memory
active-ray fraction
mean candidates per active ray
mean evaluated pairs per active ray
mean signal bands/channels used
bootstrap latency
steady-state latency
rebootstrap frequency
catastrophic-range-error rate
near/new-structure recall
coarse range error
```

Fine MAE/RMSE/AbsRel may still be reported for diagnosis, but they are not allowed to dominate latency-first decisions.

## 7. Immediate work order

The architecture has been updated, but the execution order remains conservative:

1. obtain/inspect one actual MVS-GI sample under `/media/nahhao74/KINGSTON`;
2. run the current Gate A sparse geometry harness without optional filters;
3. understand geometry/GT residuals and freeze Gate A interpretation;
4. only after Gate A review, implement the matcher benchmark rather than jumping directly to a dense CNN;
5. keep `docs/LATENCY_FIRST_ARCHITECTURE.md` as the downstream design reference.
