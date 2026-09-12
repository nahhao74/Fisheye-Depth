# NADIR Implementation Plan v1.1

## 1. Guiding rule

The current scientific task remains **Gate A real-data geometry feasibility**. Downstream architecture work is documented as hypothesis only until Gate A is reviewed.

The canonical downstream design is `FINAL_RESEARCH_ARCHITECTURE.md`. The latest concise snapshot is `CURRENT_PIPELINE_STATUS.md`. The radial-range-to-point-cloud contract is defined separately in `POINTCLOUD_OUTPUT.md`.

After Gate A, implementation is latency-first:

```text
1. P95 latency
2. robustness / catastrophic near-far error avoidance
3. coarse metric-range accuracy + near/new-structure recall
4. fine depth accuracy
```

Do not begin with a large neural model. Do not flatten or stitch fisheye RGB before stereo. Do not introduce a slow module unless it can be bypassed by a valid fast fallback path.

## 2. Real-time contract

### Hard target

- throughput `>= 15 FPS`;
- P95 capture-to-range latency `< 80 ms`;
- no uncontrolled memory growth;
- no unexpected CPU fallback in deployed accelerated graphs.

### Design target

- `>= 20 FPS`;
- P95 latency `< 60 ms`.

### Stretch target

- `30 FPS`.

These are engineering targets, not measured results.

## 3. Current active milestone — Gate A

Establish or falsify:

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
temporal_predict_ms
cheap_change_ms
scheduler_ms
signal_or_descriptor_ms
candidate_generation_ms
matching_ms
pair_consensus_ms
belief_update_ms
pointcloud_ms              # only when point-cloud adapter enabled
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
fraction_reusing_history
fraction_reaching_each_compute_level
bootstrap_or_track_mode
pointcloud_valid_count      # when enabled
pointcloud_density_summary  # when enabled
```

Reports must include P50/P95 latency, not only mean FPS.

### M1 — NADIR-RAYLUT

Compile calibration into per-camera native-ray lookup tables:

```text
ray_C
solid_angle
valid
optional_static_quality
```

Required tests:

- project/unproject round trip;
- solid-angle numerical consistency;
- explicit >90° incidence coverage;
- camera-model replacement without changing downstream ray-domain contracts;
- preservation of camera identity and physical center.

### M2 — NADIR-OBS

For every candidate output ray/region, characterize:

- visibility mask;
- available camera pairs;
- effective baseline;
- triangulation angle/conditioning;
- projection validity;
- incidence region;
- pre-rank pair quality where possible.

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

Benchmark candidate local measurement engines on identical native-ray geometry:

```text
A. ORB / classical sparse reference
B. Census / Hamming
C. spherical harmonic / Fourier-Bessel DSP
D. tiny learned feature/residual
```

For spherical DSP measure:

- active-anchor count;
- angular orders;
- radial-frequency bands;
- pool radius;
- progressive-band loading;
- early-rejection rate;
- signal construction cost.

Do not assume the full high-order/high-band source configuration is appropriate for dense use.

Required comparison:

| Matcher | coarse range error | catastrophic error | near/new recall | P50 ms | P95 ms | peak RAM |
|---|---:|---:|---:|---:|---:|---:|
| ORB/ref | | | | | | |
| Census | | | | | | |
| spherical DSP | | | | | | |
| tiny learned | | | | | | |

### M5 — NADIR-SEARCH

Benchmark pairwise search variables:

- direct radial depth;
- inverse depth;
- `lambda = B / d`.

For the lambda formulation, evaluate native-sphere epipolar hypothesis + `J_lambda` for:

- adaptive coarse spacing;
- local refinement;
- conditioning/Fisher-style information score;
- candidate-count reduction.

Choose the winner by measured latency/robustness Pareto evidence.

### M6 — NADIR-PAIR

Exploit physical camera pairs `01`, `02`, `12` without paying for all three by default.

Compare:

```text
all-pairs always
best-pair only
best-pair-first adaptive
2-of-3 robust consensus / median
information-weighted fusion
occlusion-aware peeling/fallback
```

Candidate runtime policy:

```text
best pair first
-> early exit if sufficient
-> second pair if ambiguous
-> third pair only as fallback/consistency evidence
```

### M7 — NADIR-TYPED-STATE

Introduce typed range state before a learned temporal model.

Store at least:

```text
range_or_point
sigma_sensor
sigma_model
timestamp
age
observation_count
source_pair_or_cameras
status
static_or_dynamic_state
optional_modes
```

The state contract must preserve units/frame/provenance where applicable and remain bounded in memory.

### M8 — NADIR-TEMPORAL

Add geometric temporal propagation using relative `SE(3)`.

Compare:

- frame-independent full search;
- history prior only;
- history + cheap consistency check;
- history + local correction.

Primary question: does steady-state P95 latency fall without unacceptable catastrophic errors?

### M9 — NADIR-SURPRISE

Add predictive-coding style innovation before a full scheduler.

Candidate signals:

- image/feature residual;
- Census mismatch;
- predicted-vs-measured range residual;
- pair disagreement;
- normalized surprise such as `epsilon^T Sigma^-1 epsilon` when appropriate.

Do not freeze thresholds from design discussion. Sweep and calibrate them on held-out sequences.

### M10 — NADIR-PROGRESSIVE

Implement progressive compute levels:

```text
L0 temporal reuse
L1 cheap consistency / Census
L2 low-order low-band spherical DSP
L3 fuller DSP refinement or second pair
L4 tiny learned fallback if justified
```

Measure how often each level is entered and whether early exits actually reduce P95 latency.

### M11 — NADIR-SCHED

Add adaptive spatial/deadline scheduling.

Priority candidates:

- surprise;
- propagated uncertainty;
- depth edge/local curvature;
- newly visible region;
- stale age;
- near-range / TTC priority;
- pair disagreement.

The AMR analogy is limited to adaptive resolution:

```text
smooth/stable/high-confidence -> coarse/reuse
changing/boundary/uncertain/new -> refine
```

Required active-ray ablation examples:

```text
100%
50%
25%
12.5%
```

Report P95 latency, catastrophic error, near/new recall and rebootstrap rate.

### M12 — NADIR-MEMORY

Split memory by timescale:

```text
sensory ring buffer
working typed range memory
optional persistent sparse spatial support
```

Compare sparse points, surfels and lightweight voxel/hash storage only if needed. Avoid turning NADIR into a general mapping system.

### M12.5 — NADIR-CLOUD

Implement the deterministic radial-range-to-point output adapter only after a trustworthy typed range state exists.

Canonical relation:

```text
P_i = O_R + rho_i * r_i
```

If output is required in world/NED coordinates:

```text
P_i^N = R_NB * P_i^B + p_B^N
```

Required tests:

- rig/body coordinate-frame correctness;
- NED transform correctness with timestamp-consistent pose;
- invalid/`UNKNOWN` range suppression or explicit status handling;
- uncertainty propagation sanity;
- current cloud composed from propagated valid history + fresh corrections;
- conversion latency and emitted valid-point count;
- memory/runtime of optional point/surfel/voxel support;
- failure under pose error and dynamic objects.

The adapter is an output/spatial-memory representation, **not** a new depth estimator and not a separate reason to move the scientific boundary past Gate A.

Heavy operations such as ICP, global registration, dense meshing or generic point-cloud SLAM are outside the default fast path unless separately justified.

### M13 — NADIR-IMU

Add IMU only after camera/history temporal geometry works.

Use IMU/state information to:

- de-rotate temporal correspondence;
- improve pose prediction;
- stabilize short-term propagation;
- reduce active search width.

Success means lower total matching compute / P95 latency at acceptable robustness.

### M14 — NADIR-RTK

Add RTK/GNSS translation constraints with covariance/status-aware gating.

Ablations:

- camera/history only;
- + IMU;
- + IMU + RTK FIX;
- degraded/FLOAT/LOST GNSS.

### M15 — NADIR-RESIDUAL

Only if deterministic/DSP structure remains insufficient, add a tiny learned residual or uncertainty correction.

Preferred roles:

- local visual residual feature;
- model mismatch correction;
- uncertainty calibration;
- static quality estimation.

Do not let the network relearn calibrated projection/extrinsics.

### M16 — NADIR-EDGE

Deploy and profile the surviving pipeline on the target QCS8550-class device.

Potential accelerated pieces:

- static ray/geometry LUT access;
- image/DSP preprocessing;
- Census/Hamming;
- vectorized spherical signal operations;
- compact learned blocks if retained;
- pair consensus / belief update;
- range-to-point conversion if enabled.

For learned components only:

```text
host baseline
-> ONNX
-> QNN-compatible graph
-> FP16 / PTQ INT8
-> QAT INT8 only if necessary
```

Do not infer target latency from desktop host timings.

### M17 — NADIR-LAW-COMPRESSION (optional, late)

After sufficient runtime logs exist, test whether learned quality/scheduler/uncertainty residuals can be replaced by compact identified or symbolic equations.

Possible tools:

- least squares / recursive least squares;
- sparse regression;
- symbolic regression;
- weak/integral identification where appropriate.

Promotion requirements:

```text
same or better robustness
lower runtime cost
cross-session validation
dimensional / sign / boundary sanity
explicit validity region
```

This is an optional late-stage experiment, not a requirement for the core depth pipeline.

## 5. Bootstrap / track / rebootstrap contract

### BOOTSTRAP

Use wider coverage/search to initialize typed history. It may be slower than steady state but must be separately timed and bounded.

### TRACK / UPDATE

Use prediction, narrow search, active anchors, best-pair-first evaluation, progressive evidence and early exit.

### REBOOTSTRAP

Trigger on confidence/coverage collapse, large scene change, pose jump, excessive dynamics, repeated pair disagreement or stale uncertainty.

Report rebootstrap frequency because a fast steady state that constantly reboots is not useful.

## 6. Fail-closed contract

When evidence is insufficient:

```text
UNKNOWN > fabricated range
```

Track abstention rate explicitly. A system that is fast only because it silently emits bad depth is rejected.

Point-cloud output must not silently convert `UNKNOWN` or invalid range states into plausible-looking XYZ points.

## 7. Acceptance metrics

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
fraction reusing history
fraction reaching each progressive level
bootstrap latency
steady-state latency
rebootstrap frequency
catastrophic-range-error rate
near/new-structure recall
coarse range error
UNKNOWN/abstention rate
```

When point-cloud output is enabled, additionally report:

```text
pointcloud_ms
valid_point_count / density summary
pointcloud memory
persistent-fusion time/memory if enabled
```

Fine MAE/RMSE/AbsRel may still be reported for diagnosis, but they do not dominate latency-first decisions.

## 8. Immediate work order

The design is frozen on paper, but execution remains conservative:

1. obtain/inspect one actual MVS-GI sample under `/media/nahhao74/KINGSTON`;
2. run the current Gate A sparse geometry harness without optional filters;
3. understand geometry/GT residuals and freeze Gate A interpretation;
4. only after Gate A review, implement M0 profiling and the M4 matcher benchmark rather than jumping to a dense CNN;
5. implement the point-cloud adapter only after trustworthy range state exists; it is not a substitute for validating the depth geometry;
6. keep `FINAL_RESEARCH_ARCHITECTURE.md`, `CURRENT_PIPELINE_STATUS.md`, and `POINTCLOUD_OUTPUT.md` as the downstream design references.
