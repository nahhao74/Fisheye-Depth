# NADIR Architecture Specification v1.0

## 1. Status

NADIR targets fast approximate metric radial range from a synchronized three-camera fisheye UAV rig.

This specification is a **research architecture hypothesis**, not an accepted scientific result. The active task remains:

```text
GATE_A_NOT_YET_PROVEN
```

`FINAL_RESEARCH_ARCHITECTURE.md` is the canonical full architecture. `VALIDATION_STATUS.md` is authoritative for proven status.

## 2. Optimization priority

```text
1. P95 end-to-end latency
2. robustness / catastrophic near-far error avoidance
3. coarse metric-range accuracy + near/new-structure recall
4. fine depth accuracy
```

A fine-accuracy improvement that materially worsens P95 latency is rejected unless isolated to a bounded low-rate path.

## 3. Coordinate and output semantics

- navigation/global: NED;
- body/rig: FRD;
- cameras: native calibrated frames;
- depth matching: native generalized-camera ray geometry;
- temporal motion: relative `SE(3)` derived from navigation state.

Output:

```text
P_i = O_R + rho_i r_i,   ||r_i|| = 1
```

where `rho_i` is radial range from selected rig reference origin `O_R`.

## 4. Native fisheye contract

Do not blend, stitch, globally rectify or flatten the three RGB views before stereo.

Per-camera calibration may be compiled into:

```text
RayLUT[c, pixel] = {
    ray_C,
    solid_angle,
    valid,
    optional_static_quality
}
```

Downstream modules may become camera-model agnostic only after this calibrated ray representation, while preserving camera identity and physical center.

## 5. Canonical layered structure

```text
L0 Geometry / static law layer
   RayLUT + extrinsics + visibility + conditioning

L1 Fast sensory buffer
   current native images + timestamps + IMU synchronization

L2 Typed temporal predictor
   previous range/point + uncertainty + source + age + relative SE(3)

L3 Surprise / uncertainty / deadline scheduler
   decide WHEN / WHERE / HOW MUCH to compute

L4 Local native-ray measurement
   reuse / Census-Hamming / spherical DSP / tiny learned fallback
   + direct-depth / inverse-depth / lambda search

L5 Three-camera pair manager
   best pair first -> second if ambiguous -> third fallback

L6 Belief update
   range + sensor noise + model error + status/provenance

L7 Multi-timescale memory
   sensory ring buffer + working range memory + persistent sparse support

L8 Runtime assurance / rebootstrap
   fail-closed UNKNOWN + stale/OOD/pose-jump/scene-change handling
```

The matcher is one component. The primary architecture goal is to avoid invoking expensive matching unnecessarily.

## 6. Equation-first / structured-compute rule

Known structure should be implemented directly:

- camera projection/unprojection;
- baselines and extrinsics;
- visibility;
- `SE(3)` temporal transforms;
- pairwise epipolar/native-sphere geometry;
- basic covariance propagation.

A learned model is reserved for unresolved visual/model residuals or uncertainty correction if deterministic methods are insufficient.

## 7. Typed range state

Candidate state contract:

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

This state is used for future prediction and scheduling, not merely logging.

## 8. Temporal prediction

Given previous point/range state and relative pose:

```text
P_t^- = T_Bt_Bt-1 * P_t-1
rho_t^- = ||P_t^-||
r_t^- = P_t^- / ||P_t^-||
```

The temporal prior should reduce search width and/or active-ray count.

IMU is expected to help short-term rotation/de-rotation. RTK/GNSS is covariance/status gated for metric translation support.

## 9. Predictive innovation / surprise

Compare predicted current evidence with actual current evidence:

```text
epsilon = observed - predicted
```

Candidate normalized surprise:

```text
S = epsilon^T Sigma^-1 epsilon
```

or a cheaper calibrated approximation.

Small innovation should permit reuse/cheap verification; large innovation should request more evidence. The exact statistic is not frozen until benchmarked.

## 10. Scheduler

Candidate priority inputs:

- surprise / temporal change;
- range uncertainty;
- depth edge / local curvature;
- newly visible region;
- stale age;
- near-range / TTC priority;
- pair disagreement;
- static geometry/information quality.

The scheduler controls:

```text
N_active_rays
x N_search_candidates
x N_camera_pairs
x N_signal_bands_or_feature_channels
```

It is constrained by a hard per-frame deadline rather than maximum-detail reconstruction.

## 11. Progressive model complexity

```text
LEVEL 0  temporal reuse
LEVEL 1  cheap consistency / Census-Hamming
LEVEL 2  low-order / low-band spherical DSP
LEVEL 3  fuller DSP refinement or second pair
LEVEL 4  tiny learned fallback if justified
```

Runtime should stop at the lowest level that gives sufficient confidence.

## 12. Candidate local measurement engines

### Census / Hamming

Cheap binary local descriptor and XOR/popcount-style comparison.

### Local spherical DSP

Active-anchor harmonic/Fourier-Bessel representation `W_mn` with candidate advantages:

- native sphere, no panorama;
- analytic gauge rotation;
- progressive bands;
- coarse-to-fine refinement;
- analytic measurement-noise model;
- explicit rejection.

Do not assume full high-order/high-band evaluation for every ray.

### Tiny learned residual/feature

Only if it improves the latency/robustness Pareto frontier. Preferred roles are unresolved visual representation, model-mismatch correction or uncertainty calibration.

## 13. Search coordinate

Benchmark:

```text
direct radial depth
inverse depth
lambda = B_ij / d
```

For the lambda candidate:

```text
q_j(lambda) = normalize(R_ji q_i + lambda * t_hat_ji)
J_lambda = d q_j / d lambda
```

Potential uses:

- adaptive candidate spacing;
- local refinement;
- pair conditioning;
- Fisher/information-style scoring;
- deciding whether more refinement is worth latency.

## 14. Three-camera pair strategy

Pairs: `01`, `02`, `12`.

Default candidate policy:

```text
best pair first
-> early exit if sufficient
-> second pair if ambiguous
-> third pair only as fallback / consistency evidence
```

Pair disagreement can indicate occlusion or different visible surfaces; peeling is not automatic.

## 15. Belief and uncertainty

A measurement should return:

```text
range
sigma_sensor
sigma_model
status
source/provenance
```

Uncertainty controls future compute. Theoretical measurement covariance must be calibrated against real residuals; model mismatch is tracked separately.

## 16. Multi-timescale memory

### Sensory

Fixed-size recent-frame/IMU ring buffer.

### Working range

Typed range states for prediction and local correction.

### Persistent spatial support

Optional sparse points/surfels/lightweight voxel-hash for stable geometry reuse. This is internal depth support, not a requirement to become a full mapping product.

## 17. Adaptive spatial resolution

AMR-like principle only:

```text
stable/smooth/high-confidence -> coarse or reuse
changing/edge/uncertain/new   -> refine
```

NADIR does not solve Navier-Stokes and does not infer aerodynamic flow inside the depth core.

## 18. Fail-closed behavior

```text
UNKNOWN > fabricated depth
```

Candidate triggers:

- low evidence;
- stale history;
- unsupported camera region;
- pair disagreement without resolution;
- search rail;
- pose jump;
- RTK degradation;
- excessive model residual;
- out-of-support condition.

## 19. Bootstrap / track / rebootstrap

### BOOTSTRAP

Broad coverage/search to initialize range state.

### TRACK / UPDATE

Prediction first, active regions only, narrow search, best-pair-first, progressive evidence, early exit.

### REBOOTSTRAP

Trigger on confidence collapse, scene transition, pose discontinuity, excessive dynamics, stale uncertainty or repeated disagreement.

## 20. Optional offline compression

After enough runtime logs exist, learned quality/uncertainty/scheduler residuals may be tested for replacement by simpler identified/symbolic equations.

Promotion requires equal-or-better robustness, lower runtime cost and explicit validity-region evidence.

This is a late optional stage, not part of Gate A.

## 21. Runtime acceptance

Engineering targets:

- hard: `>=15 FPS`, P95 `<80 ms`;
- design: `>=20 FPS`, P95 `<60 ms`;
- stretch: `30 FPS`.

Mandatory downstream metrics include:

```text
P50/P95 latency
FPS
peak RAM
active-ray fraction
candidates per active ray
pairs per active ray
signal bands/channels
history-reuse fraction
progressive-level distribution
bootstrap/steady-state latency
rebootstrap frequency
catastrophic-range-error rate
near/new-structure recall
coarse range error
UNKNOWN/abstention rate
```

## 22. Scientific gate order

```text
A  real 3-camera native-fisheye metric geometry
B  local matcher benchmark
C  search coordinate / Jacobian / information allocation
D  best-pair-first + 3-camera consensus
E  typed temporal state + geometric prediction
F  predictive surprise + progressive compute
G  adaptive spatial scheduling
H  IMU search compression
I  RTK covariance-conditioned search compression
J  learned residual only if needed
K  QCS8550 deployment
L  optional offline equation/parameter compression
```

No gate is promoted because it is elegant; it is promoted only by measured evidence.
