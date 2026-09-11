# NADIR Latency-First Adaptive Architecture

## Status

This document records the **post-Gate-A research direction**. It is not a validated implementation and it does not change the current scientific state:

```text
GATE_A_NOT_YET_PROVEN
```

The active task remains real-data geometry feasibility. The architecture below is a hypothesis to test only after the spatial metric-stereo premise is supported.

## 1. Primary objective

NADIR is optimized in this order:

```text
1. P95 latency
2. robustness / catastrophic-error avoidance
3. coarse metric-range accuracy
4. fine depth accuracy
```

The target is not sub-centimeter reconstruction. The useful product is a fast estimate of approximate metric range with confidence, especially for near or changing structure.

A module that improves fine accuracy while materially worsening P95 latency is rejected unless it runs only on a bootstrap/background path.

Current engineering targets remain:

- hard target: >= 15 FPS and P95 capture-to-depth < 80 ms;
- design target: >= 20 FPS and P95 < 60 ms;
- stretch target: 30 FPS.

These are targets, not measured claims.

## 2. Non-negotiable geometry rule

**Do not flatten, stitch or globally rectify the three fisheye images before stereo.**

The cameras remain separate native views. Each calibrated pixel is represented by a physical camera center and a unit ray. A per-camera lookup may additionally store the pixel solid angle and measured quality metadata:

```text
RayLUT[c, pixel] = {
    ray_C,
    solid_angle,
    valid,
    optional_quality
}
```

The purpose of the RayLUT is to make downstream processing camera-model agnostic without destroying parallax.

## 3. System-level difference from a pairwise matcher

A pairwise matcher answers:

> Given this anchor and this camera pair, what range best explains the two observations?

NADIR must answer three cheaper questions first:

```text
WHEN should this region be recomputed?
WHERE should compute be spent?
HOW MUCH matching evidence is required before stopping?
```

Only then should a local pairwise depth measurement run.

## 4. Layered architecture

```text
L0  GEOMETRY
    native fisheye RayLUT / solid angle / extrinsics / visibility
                         |
L1  TEMPORAL MEMORY + POSE
    previous range/confidence + IMU/RTK relative SE(3)
                         |
L2  COMPUTE SCHEDULER
    active region? best pair? search width? signal complexity?
                         |
L3  LOCAL MEASUREMENT
    DSP spherical signal OR Census/Hamming OR tiny learned feature
    + lambda search / local refinement
                         |
L4  MULTI-PAIR CONSENSUS
    01 / 02 / 12 agreement, robust fusion, peeling/fallback
                         |
L5  MEMORY UPDATE
    range + uncertainty + age + source + change state
```

The reviewed spherical DSP matcher is therefore treated as a **candidate L3 measurement engine**, not as the whole NADIR pipeline.

## 5. Pairwise search variable

For camera pair `(i,j)` with physical baseline magnitude `B_ij`, a useful search variable is

```text
lambda = B_ij / d
```

with the corresponding native-sphere epipolar hypothesis

```text
q_j(lambda) = normalize(R_ji q_i + lambda * t_hat_ji)
```

where `t_hat_ji = t_ji / ||t_ji||`.

This separates baseline scale from the search coordinate and gives a direct Jacobian

```text
J_lambda = d q_j / d lambda
```

that can be used for:

- geometry-driven candidate spacing;
- local refinement;
- pair conditioning;
- approximate Fisher/information scoring;
- deciding whether further refinement is worth its latency.

This formulation is a hypothesis for NADIR until benchmarked against direct radial-depth search.

## 6. Candidate local measurement engines

Three families must be benchmarked rather than assumed:

### A. Census / Hamming

Very cheap DSP-friendly native-image descriptor. Candidate projection remains ray-based; only the local comparison uses Census/Hamming.

### B. Local spherical harmonic / Fourier-Bessel signal

For an anchor ray `q`, collect nearby native rays and summarize the local angular texture into compact complex coefficients `W_{m,n}`. Candidate advantages include:

- no panorama resampling;
- steerable gauge rotation between camera views;
- analytic measurement-noise propagation;
- progressive frequency-band loading;
- coarse-to-fine local refinement.

NADIR must **not** assume that the full high-order/high-band configuration is fast enough. The key latency hypothesis is to compute the signal only for active anchors and to stop at low order/band count when confidence is already sufficient.

### C. Tiny learned feature

A small shared encoder remains a candidate fallback/competitor. It should be tested only if it improves the latency/robustness Pareto frontier over deterministic DSP baselines.

No L3 engine is currently accepted.

## 7. Progressive evidence instead of fixed compute

Matching complexity should be adaptive in multiple dimensions:

```text
N_active_rays
x N_lambda_candidates
x N_camera_pairs
x N_signal_bands_or_channels
```

NADIR should reduce each factor independently.

Example policy:

```text
stable + high confidence
    -> reuse temporal prediction / cheap consistency check

moderate uncertainty
    -> best pair only, narrow lambda window, low-order signal

high uncertainty / new obstacle / depth boundary
    -> denser anchors, wider search, second pair, more bands

persistent disagreement
    -> third-pair fallback or mark UNKNOWN
```

The target is low **average** compute under a hard tail-latency budget, not maximum-detail processing everywhere.

## 8. Persistent temporal memory

Each retained spatial element should carry more than a 3-D point:

```text
{
    range_or_point,
    uncertainty,
    timestamp,
    age,
    observation_count,
    source_pair_or_cameras,
    static_or_dynamic_state,
    optional_multimodal_hypotheses
}
```

Relative SE(3) from the navigation layer propagates the previous state into the current rig frame. IMU is expected to be most valuable for short-term rotation/de-rotation; RTK/GNSS can improve metric translation when covariance/status is trustworthy.

The temporal prior should narrow the local search rather than merely add another neural input.

Confidence must decay with age/model uncertainty so stale history eventually triggers remeasurement.

## 9. Spatial compute allocation

A dense frame can be used for bootstrap or rebootstrap, but steady-state processing should preferentially recompute regions with high value of information.

Candidate priority terms include:

- temporal innovation / image change;
- range uncertainty;
- depth discontinuity / local curvature;
- newly visible region;
- stale age;
- near-range or closing/TTC priority;
- pair disagreement.

The AMR analogy from numerical PDE/CFD is limited to **adaptive resolution allocation**:

```text
smooth/stable region -> coarse or reused
boundary/change region -> refine
```

NADIR does **not** solve Navier-Stokes and does not use an aerodynamic state model for depth inference.

## 10. Three-camera strategy

There are three physical pairs:

```text
01, 02, 12
```

Do not run all three at full cost by default.

For each ray/region, geometry and static quality can pre-rank the pairs. Runtime policy:

1. evaluate the best pair;
2. stop if confidence is sufficient;
3. query the second pair if ambiguous;
4. use the third pair only as fallback/consistency evidence.

Pair outputs can be fused using robust statistics or information weighting. A two-agree/one-disagrees case is a natural candidate for view peeling, but disagreement must not automatically be labelled as an outlier because occlusion or different visible surfaces are possible.

## 11. Uncertainty as a control variable

Uncertainty is not only an output metric. It controls future compute.

A local measurement may produce

```text
range, sigma_range, status
```

and the temporal predictor produces a prior covariance. The scheduler can then make decisions such as:

```text
low sigma + low innovation -> reuse
sigma increased -> refresh
pair disagreement -> increase evidence budget
all evidence weak -> UNKNOWN, do not invent depth
```

Analytic noise estimates from deterministic DSP measurements are useful, but model mismatch must be measured separately; theoretical covariance must not be trusted without calibration against real residuals.

## 12. Bootstrap / steady-state / rebootstrap

### BOOTSTRAP

Use wider spatial coverage and wider search. This path may be slower than steady state but must still be bounded and profiled.

### TRACK / UPDATE

Use history, narrow search windows, active-anchor selection, best-pair-first evaluation and early exit.

### REBOOTSTRAP

Trigger when coverage/confidence collapses, pose jumps, scene change is large, too many regions become dynamic, or stale uncertainty exceeds a threshold.

The algorithm must not rely indefinitely on old geometry.

## 13. Latency-first evaluation

Every proposed module must report at least:

```text
P50 total latency
P95 total latency
FPS
peak memory
active-ray fraction
mean candidates per active ray
mean evaluated camera pairs per active ray
mean signal bands/channels used
bootstrap latency
steady-state latency
rebootstrap frequency
catastrophic-range-error rate
near/new-structure recall
coarse range error
```

A reduction in active rays is not sufficient evidence by itself. If active rays fall by 70% but P95 latency barely changes, the real bottleneck lies elsewhere.

## 14. Research sequence after Gate A

The proposed sequence is intentionally falsification-driven:

```text
Gate A  real 3-camera native-fisheye geometry feasibility
   |
Gate B  L3 matcher benchmark: ORB/Census vs spherical DSP vs tiny learned feature
   |
Gate C  lambda/Jacobian/information-driven search vs direct depth/inverse-depth search
   |
Gate D  best-pair-first + 3-pair consensus/peeling
   |
Gate E  temporal reuse with previous depth + pose, no learned scheduler
   |
Gate F  adaptive spatial refinement / event-triggered scheduler
   |
Gate G  IMU then RTK covariance-conditioned search compression
   |
Gate H  QCS8550/QNN/accelerator profiling and optimization
```

Promotion requires measured latency benefit and acceptable robustness. Fine-accuracy improvements alone are insufficient.

## 15. Current decision

The architecture direction is therefore:

```text
native fisheye
+ ray-domain geometry
+ local low-cost measurement
+ temporal memory
+ adaptive spatial/search/pair compute
+ uncertainty-driven early exit
```

not:

```text
full dense depth network every frame
```

and not:

```text
fisheye -> panorama/pinhole flattening -> stereo
```

This document records the intended research direction only; `docs/VALIDATION_STATUS.md` remains authoritative for what has actually been proven.
