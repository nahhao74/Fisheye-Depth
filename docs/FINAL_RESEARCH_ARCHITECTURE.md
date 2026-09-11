# NADIR Final Research Architecture v1.0 — Latency-First Native-Fisheye Depth

## Status

This document is the **canonical final research architecture** for the current NADIR design direction.

It is a design contract, **not a claim that the pipeline is scientifically validated**. The current execution boundary remains:

```text
GATE_A_NOT_YET_PROVEN
```

Gate A must first establish real synchronized three-fisheye metric-stereo feasibility. Every layer after that remains `HYPOTHESIS_NOT_VALIDATED` until measured and promoted through the validation process.

The architecture incorporates selected ideas from the reviewed spherical DSP matcher and from the LAWGRAPH research concept, but only where they directly support NADIR's depth/range objective. NADIR does not become a general world model, CFD solver, controller or planner.

---

# 1. Primary objective

NADIR estimates **fast approximate metric radial range with confidence** from a synchronized three-camera fisheye UAV rig.

Optimization priority is frozen as:

```text
1. P95 end-to-end latency
2. robustness / catastrophic near-far error avoidance
3. coarse metric-range accuracy and near/new-structure recall
4. fine depth accuracy
```

The intended product is not sub-centimeter reconstruction. A result such as `2.4 m ± 0.4 m` may be preferable to a more precise result delivered too late.

Current engineering targets are:

- hard target: `>= 15 FPS`, P95 capture-to-range `< 80 ms`;
- design target: `>= 20 FPS`, P95 `< 60 ms`;
- stretch target: `30 FPS`.

These are engineering goals, not measured QCS8550 results.

---

# 2. Non-negotiable geometry contract

1. **No RGB panorama/stitch/flatten before stereo.**
2. Each camera keeps its own physical optical center and native calibrated model.
3. Native observations are generalized-camera rays `(O_c, r_c)`.
4. Output semantics are radial range from rig reference origin `O_R`:

   ```text
   P_i = O_R + rho_i r_i,   ||r_i|| = 1
   ```

5. Navigation/global state uses NED; rig/body uses FRD; camera frames remain native.
6. Relative motion enters the depth core as relative `SE(3)`, not as anonymous neural sensor features.
7. Camera-model mathematics should be compiled into lookup/static geometry where possible rather than relearned by a network.

---

# 3. Core design principle

NADIR follows a restricted equation-first principle:

```text
known geometry / known transforms / known uncertainty propagation
                    +
small learned or DSP measurement only where needed
```

Do not ask a learned model to rediscover:

- calibrated fisheye projection/unprojection;
- camera centers/baselines;
- rigid-body `SE(3)` transforms;
- visibility;
- epipolar/native-sphere search geometry;
- basic uncertainty propagation.

Learned components are candidates only for unresolved visual/model mismatch or feature representation, and only if they improve the latency/robustness Pareto frontier.

---

# 4. Canonical end-to-end structure

```text
                      3 SYNCHRONIZED NATIVE FISHEYES
                                  |
                                  v
+------------------------------------------------------------------+
| L0  GEOMETRY / STATIC LAW LAYER                                  |
| RayLUT, solid angle, intrinsics, extrinsics, visibility, quality |
+------------------------------------------------------------------+
                                  |
                                  v
+------------------------------------------------------------------+
| L1  FAST SENSORY BUFFER                                           |
| current/preprocessed images, timestamps, IMU synchronization     |
+------------------------------------------------------------------+
                                  |
                    +-------------+-------------+
                    |                           |
                    v                           v
+--------------------------------+   +--------------------------------+
| L2  TEMPORAL PREDICTOR         |   | CURRENT OBSERVATION SUMMARY    |
| previous typed range state     |   | cheap gradients/change/Census  |
| + relative SE(3)               |   | or other low-cost evidence     |
| -> predicted current state     |   +--------------------------------+
+--------------------------------+                 |
                    |                              |
                    +---------------+--------------+
                                    v
+------------------------------------------------------------------+
| L3  SURPRISE / UNCERTAINTY / DEADLINE SCHEDULER                  |
| decide WHEN, WHERE, HOW MUCH compute to spend                    |
+------------------------------------------------------------------+
        |                    |                    |              |
        v                    v                    v              v
      REUSE             CHEAP CHECK          DSP REFINE      LEARNED FALLBACK
   temporal state       Census/Hamming       spherical W     tiny residual/feature
        \                    |                    |              /
         +-------------------+--------------------+-------------+
                                    |
                                    v
+------------------------------------------------------------------+
| L4  LOCAL NATIVE-RAY MEASUREMENT ENGINE                          |
| pairwise lambda/depth search, progressive candidates/bands       |
+------------------------------------------------------------------+
                                    |
                                    v
+------------------------------------------------------------------+
| L5  THREE-CAMERA PAIR MANAGER                                    |
| best pair first -> second pair if needed -> third pair fallback  |
| robust consensus / occlusion-aware disagreement handling         |
+------------------------------------------------------------------+
                                    |
                                    v
+------------------------------------------------------------------+
| L6  BELIEF UPDATE / TYPED RANGE STATE                            |
| range + sensor noise + model error + status + provenance         |
+------------------------------------------------------------------+
                                    |
                                    v
+------------------------------------------------------------------+
| L7  MULTI-TIMESCALE MEMORY                                      |
| sensory buffer / working range memory / persistent spatial state |
+------------------------------------------------------------------+
                                    |
                                    v
+------------------------------------------------------------------+
| L8  RUNTIME ASSURANCE / REBOOTSTRAP                              |
| fail-closed UNKNOWN, stale/OOD/pose-jump/scene-change handling   |
+------------------------------------------------------------------+
                                    |
                                    v
                    approximate metric radial range + confidence
```

The expensive local matcher is therefore only one layer. The primary architectural contribution is **avoiding unnecessary matching**.

---

# 5. L0 — Geometry / static law layer

For each camera, compile calibration into:

```text
RayLUT[c, pixel] = {
    ray_C,
    solid_angle,
    valid,
    optional_static_quality
}
```

The runtime geometry layer also exposes:

```text
camera center O_c
T_C_B / T_B_C
pair baseline B_ij
candidate projection validity
visibility mask
triangulation angle / conditioning
effective perpendicular baseline
incidence region
```

Static tables may pre-rank the three camera pairs `01`, `02`, `12` for each ray/region.

The purpose is to convert expensive repeated geometry into cheap lookup where possible while preserving exact camera identity.

---

# 6. L1 — Fast sensory buffer

Maintain a fixed-size ring buffer for the highest-rate data needed by depth:

```text
native image / preprocessed image
frame timestamp
exposure metadata if available
IMU samples covering exposure interval
latest navigation pose + covariance
```

This memory is short-lived and bounded. It supports:

- synchronization;
- de-rotation / rolling-shutter correction if required;
- temporal image residuals;
- optical-flow/TTC cues if later retained.

The fast buffer must never grow with mission duration.

---

# 7. L2 — Typed temporal state and predictor

Each retained range element is not just a scalar depth. It should carry typed state:

```text
RangeState_i = {
    ray_or_point,
    range,
    sigma_sensor,
    sigma_model,
    timestamp,
    age,
    observation_count,
    source_pair_or_cameras,
    status,
    static_or_dynamic_state,
    optional_modes
}
```

This adopts the useful LAWGRAPH idea that state should retain meaning, uncertainty, time and provenance rather than becoming an anonymous vector.

Given previous 3-D point/range state and relative motion:

```text
P_t^- = T_Bt_Bt-1 * P_t-1
rho_t^- = ||P_t^-||
r_t^- = P_t^- / ||P_t^-||
```

The predictor produces a prior range and covariance. History is used to **narrow future search**, not merely appended to a neural network input.

---

# 8. Predictive coding / innovation

The architecture should compare predicted current evidence with actual current evidence.

Generic residual:

```text
epsilon = observed - predicted
```

A normalized surprise candidate is:

```text
S = epsilon^T Sigma^-1 epsilon
```

or a cheaper calibrated approximation.

Possible evidence includes:

- image/feature residual;
- Census mismatch;
- projected-range consistency;
- pair disagreement;
- motion inconsistency.

The exact surprise function is a research hypothesis and must be benchmarked. The architectural role is fixed: **small innovation should permit low compute; large innovation should request more evidence**.

---

# 9. L3 — Latency-budgeted scheduler

The scheduler answers before expensive stereo:

```text
WHEN must a region be recomputed?
WHERE should computation be allocated?
HOW MUCH evidence is enough?
```

Candidate priority score:

```text
U_i =
    w_s * surprise_i
  + w_u * uncertainty_i
  + w_e * depth_edge_or_curvature_i
  + w_n * newly_visible_i
  + w_a * stale_age_i
  + w_t * near_or_TTC_priority_i
  + w_p * pair_disagreement_i
```

This is a candidate form, not a frozen numerical policy.

The scheduler is constrained by a per-frame compute/deadline budget rather than maximizing detail everywhere.

Compute complexity is controlled in four main dimensions:

```text
N_active_rays
x N_search_candidates
x N_camera_pairs
x N_signal_bands_or_feature_channels
```

A useful scheduler must reduce **end-to-end P95 latency**, not merely operation counts.

---

# 10. Progressive model complexity

NADIR uses the cheapest level that produces sufficient evidence.

```text
LEVEL 0  temporal reuse only
LEVEL 1  cheap consistency / Census-Hamming
LEVEL 2  low-order / low-band spherical DSP
LEVEL 3  fuller DSP refinement or second-pair measurement
LEVEL 4  tiny learned feature/residual fallback if justified
```

The full high-order representation or learned model should not run for all rays by default.

This is the main LAWGRAPH-derived progressive-complexity principle retained in NADIR.

---

# 11. L4 — Candidate local measurement engines

Three measurement families are retained for controlled benchmark.

## 11.1 Census / Hamming

Cheap native-image local descriptor using binary comparisons and XOR/popcount-style matching.

Strengths to test:

- very low compute;
- deterministic behavior;
- DSP/SIMD friendliness.

## 11.2 Local spherical harmonic / Fourier-Bessel DSP

For active anchor `q`, summarize local angular texture into complex coefficients `W_mn`.

Potential useful properties from the reviewed matcher:

- no panorama flattening;
- local gauge rotation handled analytically;
- progressive frequency-band loading;
- coarse-to-fine local refinement;
- analytic measurement-noise propagation;
- explicit rejection states.

The full source configuration must not be assumed fast enough for dense all-ray execution. NADIR specifically tests **active-anchor and progressive-band use**.

## 11.3 Tiny learned feature / residual

A small shared learned component remains a fallback/competitor. Preferred roles are:

- unresolved local visual descriptor;
- model-mismatch correction;
- confidence / uncertainty correction;
- quality estimation.

It should not relearn known camera geometry.

---

# 12. Search coordinate and information-aware refinement

For pair `(i,j)`, benchmark:

```text
direct radial depth
inverse depth
lambda = B_ij / d
```

For the lambda candidate:

```text
q_j(lambda) = normalize(R_ji q_i + lambda * t_hat_ji)
```

with Jacobian:

```text
J_lambda = d q_j / d lambda
```

Candidate uses:

- adaptive coarse spacing;
- local refinement;
- approximate Fisher/information score;
- pair conditioning;
- deciding whether further refinement is worth latency.

A temporal prior can narrow the search interval around the predicted `lambda` or range.

No search coordinate is accepted until benchmarked.

---

# 13. L5 — Three-camera pair manager

Physical pairs are:

```text
01
02
12
```

Default strategy is **not all-pairs always**.

Candidate runtime policy:

```text
1. select geometrically best available pair
2. evaluate it
3. early-exit if confidence is sufficient
4. evaluate second pair if ambiguous
5. evaluate third pair only for fallback/consistency
```

Fusion candidates:

- median/robust statistics;
- information weighting;
- two-agree/one-disagrees peeling;
- multimodal retention near occlusion.

Pair disagreement is not automatically an outlier. It may represent occlusion, a different visible surface, repeated texture or calibration error.

---

# 14. L6 — Belief update and uncertainty

A local measurement should return at least:

```text
range
sigma_sensor
sigma_model
status
source/provenance
```

Total uncertainty may be tracked approximately as:

```text
sigma_total^2 = sigma_prior^2 + sigma_sensor^2 + sigma_model^2
```

with a proper filter/fusion law chosen according to the experiment.

A Kalman-like scalar fusion is a candidate when assumptions are appropriate:

```text
K = P^- / (P^- + R)
rho^+ = rho^- + K (rho_meas - rho^-)
P^+ = (1-K) P^-
```

Theoretical DSP covariance must be calibrated against real residuals; model mismatch is tracked separately rather than hidden inside sensor noise.

Uncertainty is a **control variable** for future compute, not only an output metric.

---

# 15. L7 — Multi-timescale memory

NADIR retains only the LAWGRAPH memory ideas useful for perception.

## 15.1 Sensory memory

Timescale: a few frames / tens to hundreds of milliseconds.

Purpose:

- synchronization;
- temporal residual;
- short-term flow/de-rotation.

## 15.2 Working range memory

Timescale: approximately sub-second to several seconds depending on motion.

Stores typed range states needed for prediction and local correction.

## 15.3 Persistent spatial memory

Longer-lived static scene support, potentially represented by:

- sparse points;
- surfels;
- lightweight voxel/hash structure.

The representation is internal support for fast range inference, not a requirement to build a full mapping product.

Stable smooth background can be stored sparsely; near, changing and boundary regions retain more detail.

---

# 16. Adaptive spatial resolution

The useful CFD/AMR analogy is limited to compute allocation:

```text
stable/smooth/high-confidence -> coarse or reuse
changing/edge/uncertain/new   -> refine
```

No Navier-Stokes equation or aerodynamic field is solved inside NADIR.

A hierarchical tile/ray implementation should prefer a small set of predefined resolutions/active masks on embedded hardware rather than uncontrolled dynamic tensor shapes.

---

# 17. IMU and RTK/GNSS roles

Sensors are introduced only if they reduce search or improve robustness.

## IMU

Preferred uses:

- short-term rotation propagation;
- de-rotation;
- temporal correspondence stabilization;
- pose-prediction improvement.

Do not trust accelerometer-only translation double integration without estimator support.

## RTK/GNSS

Use covariance/status gating:

```text
FIX   -> strong metric translation prior if covariance supports it
FLOAT -> wider prior
LOST  -> do not constrain stereo
```

The success criterion is not “sensor fusion exists”; it is **less matching work at acceptable failure rate and lower P95 latency**.

---

# 18. Learn only unresolved parts

A learned component should preferably model a residual:

```text
measurement = deterministic_geometry_DSP + learned_residual
```

or uncertainty correction:

```text
R_total = R_geometry * exp(s_theta(features))
```

rather than directly predicting all depth from RGB if a smaller structured model is sufficient.

Before adding a neural block, attempt:

1. calibration/parameter identification;
2. deterministic geometry/DSP;
3. simple statistical correction;
4. only then a learned residual.

This is a design preference to falsify experimentally, not an assumption that neural methods cannot win.

---

# 19. Offline law/parameter compression — optional later stage

A restricted LAWGRAPH-style offline stage may be useful after sufficient runtime logs exist.

Possible targets:

- camera-quality function;
- uncertainty calibration;
- scheduler thresholds/priority model;
- simple residual corrections.

Workflow:

```text
runtime logs
   -> residual analysis
   -> parameter identification / sparse regression / symbolic regression
   -> candidate compact equation
   -> cross-session validation
   -> runtime benchmark
   -> promote only if simpler/faster and equally robust
```

This stage must not modify the runtime scientific model without explicit validation. SINDy/symbolic regression are **not current Gate A tasks**.

---

# 20. Fail-closed and runtime assurance

If evidence is insufficient:

```text
UNKNOWN > invented depth
```

Candidate fail-closed cases:

- stale history;
- unsupported/extrapolated camera region;
- pair disagreement without resolution;
- low signal evidence;
- search hits rail/boundary;
- pose jump;
- RTK status degradation;
- excessive model residual;
- out-of-support condition.

Fallback hierarchy should retain the latest valid typed state with growing uncertainty until refresh/rebootstrap is required.

---

# 21. Bootstrap / track / rebootstrap state machine

## BOOTSTRAP

Purpose: initialize broad scene/range state.

Characteristics:

- broad spatial coverage;
- wider search;
- potentially more camera pairs;
- separately timed latency budget.

## TRACK / UPDATE

Default steady-state mode.

Characteristics:

- prediction first;
- active regions only;
- narrow search;
- best pair first;
- progressive evidence;
- early exit.

## REBOOTSTRAP

Trigger candidates:

- confidence/coverage collapse;
- large pose discontinuity;
- scene transition;
- many newly visible/dynamic regions;
- uncertainty growth beyond threshold;
- repeated matcher disagreement.

Rebootstrap frequency is a mandatory metric.

---

# 22. Runtime accounting contract

Every downstream experiment must report at least:

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
memory_update_ms
total_ms
```

And:

```text
P50 total latency
P95 total latency
FPS
peak RAM
active-ray fraction
mean candidates per active ray
mean evaluated pairs per active ray
mean signal bands/channels used
fraction reusing history
fraction reaching each progressive-compute level
bootstrap latency
steady-state latency
rebootstrap frequency
catastrophic-range-error rate
near/new-structure recall
coarse range error
UNKNOWN/abstention rate
```

A local FLOP reduction is not an architectural win if P95 end-to-end latency does not improve.

---

# 23. Validation / gate sequence

```text
Gate A  Real native-fisheye three-camera metric geometry feasibility
   |
Gate B  Local measurement benchmark
        ORB / Census / spherical DSP / tiny learned
   |
Gate C  Search-coordinate benchmark
        direct depth / inverse depth / lambda + Jacobian/Fisher
   |
Gate D  Three-camera pair policy
        all-pairs vs best-pair-first vs consensus/fallback
   |
Gate E  Typed temporal memory + geometric prediction
        no learned scheduler yet
   |
Gate F  Predictive innovation / surprise + progressive compute
   |
Gate G  Adaptive spatial resolution / active-ray scheduling
   |
Gate H  IMU search compression
   |
Gate I  RTK/GNSS covariance-conditioned search compression
   |
Gate J  Tiny learned residual/uncertainty model only if still useful
   |
Gate K  QCS8550 deployment / accelerator profiling
   |
Gate L  Optional offline equation/parameter compression from runtime logs
```

Each gate must preserve provenance and must not silently promote hypotheses.

---

# 24. Baselines required for scientific comparison

At minimum compare surviving proposals against:

```text
A. frame-independent classical/native sparse geometry baseline
B. full-search deterministic local matcher
C. same matcher + history prior
D. same matcher + best-pair-first
E. same matcher + adaptive scheduler
F. tiny learned alternative if implemented
```

This isolates where latency savings actually come from.

---

# 25. What NADIR explicitly is not

NADIR is not:

- a full LAWGRAPH implementation;
- a general world model;
- a controller/planner;
- a semantic obstacle detector by definition;
- a CFD/aerodynamic simulator;
- a Navier-Stokes solver;
- a panorama-stereo pipeline;
- a dense black-box depth network that must run fully every frame.

---

# 26. Final architecture thesis

The final research direction is:

```text
known native-fisheye geometry
        +
explicit typed uncertainty-aware temporal state
        +
prediction before measurement
        +
surprise/risk/deadline-driven computation
        +
progressive local evidence
        +
best-pair-first three-camera measurement
        +
learned residual only when deterministic structure is insufficient
        +
fail-closed runtime assurance
```

The central runtime principle is:

```text
PREDICT
  -> VERIFY CHEAPLY
  -> SPEND COMPUTE ONLY WHERE INFORMATION IS NEEDED
  -> STOP AS SOON AS THE RANGE IS GOOD ENOUGH
```

The central scientific rule remains:

> No block is accepted because it is elegant. It is accepted only after measured evidence shows that it improves the latency/robustness tradeoff while preserving useful metric range.
