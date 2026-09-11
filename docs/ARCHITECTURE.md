# NADIR Architecture Specification

## 1. Scientific status and problem definition

NADIR targets a fast metric radial-range field from a synchronized three-camera fisheye rig mounted on a UAV.

The final architecture in this document is **not yet scientifically accepted**. The current active task remains Gate A real-data geometry feasibility; see `VALIDATION_STATUS.md`.

Inputs at time `t` may eventually include:

- `I_t^0, I_t^1, I_t^2`: native fisheye RGB images;
- fixed camera intrinsics/extrinsics;
- IMU measurements/state;
- GNSS/RTK position/velocity and covariance when available;
- persistent previous range/depth state when temporal inference is enabled.

Primary output semantics remain radial range from a selected rig reference origin:

`P_i = O_R + rho_i r_i`, with `||r_i|| = 1`.

The deployment objective is **coarse-but-useful metric range with low tail latency**, not absolute maximum depth precision.

## 2. Optimization priority

Architecture decisions are evaluated in this order:

1. P95 end-to-end latency;
2. robustness and catastrophic-error avoidance;
3. coarse metric-range accuracy and near/new-structure recall;
4. fine depth accuracy.

A fine-accuracy improvement that materially worsens P95 latency is rejected unless it belongs to a low-rate bootstrap/background path.

## 3. Coordinate frames

Freeze the following convention:

- global/navigation frame: **NED** (`X=North, Y=East, Z=Down`);
- vehicle/rig frame: **FRD/body** (`X=Forward, Y=Right, Z=Down`);
- camera frames: native calibrated camera coordinates;
- depth matching: performed in camera/rig ray geometry without panorama flattening;
- temporal navigation state: represented in NED and converted to relative SE(3) before entering the depth pipeline.

Raw IMU remains in body coordinates. RTK/GNSS is converted to a local NED frame. The navigation layer estimates `T_NB(t)`. The depth layer consumes relative motion such as

`T_Bt_Bt-1 = inv(T_NB(t)) * T_NB(t-1)`.

## 4. Native fisheye contract

The three RGB images must not be blended, stitched, globally rectified or flattened into a single panorama before stereo.

For each camera, calibration may be compiled into a lookup:

```text
RayLUT[c, pixel] = {
    ray_C,
    solid_angle,
    valid,
    optional_quality
}
```

This permits downstream processing to become camera-model agnostic while retaining distinct physical camera centers and therefore parallax.

Candidate calibrated models include Double Sphere, Kannala-Brandt/equidistant, EUCM and other central fisheye models that survive real reprojection validation beyond 90° incidence.

## 5. Spatial geometry and observability

For every ray/region, precompute or cheaply query:

- visible cameras;
- available camera pairs;
- effective baseline;
- triangulation angle / conditioning;
- lens-incidence region;
- projection validity;
- optional static optical/calibration quality.

A compact 3-bit visibility mask is sufficient for three cameras. Bitmasks are an engineering representation, not an accuracy contribution by themselves.

Stereo observability is a geometric condition. Overlap alone is insufficient if the effective baseline or triangulation angle is weak.

## 6. Pairwise search coordinate

For pair `(i,j)`, a candidate search coordinate to benchmark is

`lambda = B_ij / d`,

where `B_ij = ||t_ji||` is the physical pair baseline and `d` is range along the tested source ray/scene point convention.

The corresponding native-sphere pair hypothesis is

`q_j(lambda) = normalize(R_ji q_i + lambda * t_hat_ji)`.

Its Jacobian

`J_lambda = d q_j / d lambda`

is useful for:

- adaptive coarse-step spacing;
- local refinement;
- conditioning/information scoring;
- deciding whether additional candidates are worth their latency.

This formulation must be benchmarked against direct radial-depth and inverse-depth search before promotion.

## 7. Candidate local measurement engines

NADIR no longer assumes that a learned encoder is the default first solution. Three candidate classes should be compared on the same native-ray geometry.

### 7.1 Census / Hamming

A cheap DSP-friendly baseline. Project a 3-D/range hypothesis into the native cameras, then compare local Census descriptors using XOR/popcount-style cost.

### 7.2 Local spherical DSP signal

A reviewed spherical matcher suggests summarizing local native-fisheye neighborhoods around an anchor `q` into steerable complex coefficients `W_{m,n}` over angular order and radial-frequency band.

Potential advantages:

- no image flattening;
- local gauge rotation can be handled analytically;
- progressive frequency-band loading;
- analytic measurement-noise propagation;
- coarse search followed by local refinement;
- explicit early failure instead of fabricated depth.

The full high-order/high-band representation may be too expensive if computed for every anchor. NADIR therefore treats it as an **active-anchor local measurement engine**, not a dense full-frame transform by default.

### 7.3 Tiny learned feature

A small shared encoder remains a candidate only if it improves the latency/robustness Pareto frontier over deterministic DSP baselines. Large 3-D CNN cost volumes are not the default direction.

No measurement engine is currently accepted.

## 8. Persistent temporal memory

The intended steady-state pipeline is not frame-independent. A retained scene element should carry at least:

```text
range_or_point
uncertainty
timestamp
age
observation_count
source_camera_or_pair
static_or_dynamic_state
optional_multimodal_hypotheses
```

Given previous point/range state and relative pose, propagate it into the current rig frame to obtain a prior range/search interval.

Confidence must increase or decrease according to actual evidence and must decay with age/model uncertainty so history cannot remain trusted indefinitely.

## 9. IMU and RTK/GNSS conditioning

IMU/RTK are intended to reduce search complexity rather than merely add sensor channels to a network.

IMU is expected to be strongest for short-term rotation/de-rotation. Accelerometer-only translation integration is not trusted without an estimator because of drift.

RTK/GNSS is confidence-gated:

- FIX: narrow metric translation prior when covariance supports it;
- FLOAT: broaden the search according to uncertainty;
- LOST/unreliable: do not constrain stereo with RTK.

A useful sensor contribution should reduce active search while maintaining robustness.

## 10. Latency-budgeted scheduler

Before expensive matching, NADIR should decide:

```text
WHEN must this region be recomputed?
WHERE should compute be spent?
HOW MUCH evidence is sufficient?
```

Candidate scheduler signals:

- temporal innovation/image change;
- propagated range uncertainty;
- depth discontinuity/local curvature;
- newly visible region;
- stale age;
- near-range or closing/TTC priority;
- pair disagreement;
- static geometry/Fisher information.

The scheduler controls multiple compute dimensions:

`N_active_rays × N_candidates × N_pairs × N_signal_bands_or_channels`.

The objective is low average work under a hard P95 latency budget.

## 11. Adaptive spatial resolution

An AMR-like strategy may be used to allocate more anchors/rays to uncertain, changing or discontinuous regions and fewer to smooth stable regions.

This is a numerical-compute strategy only. NADIR does **not** solve Navier-Stokes, infer aerodynamic flow fields or require CFD inside the depth core.

Background compression must not mean deleting all context. Stable planes/surfaces can be represented sparsely while near objects, boundaries and changing regions remain dense enough for reliable range estimation.

## 12. Three-camera pair strategy

The physical camera pairs are:

`01`, `02`, `12`.

Do not evaluate all three at full cost by default.

For each ray/region:

1. pre-rank pair quality from geometry/visibility/static quality;
2. evaluate the best pair;
3. early-exit if confidence is sufficient;
4. query a second pair if ambiguous;
5. use the third pair as fallback/consistency evidence when required.

Pair disagreement may be fused by robust statistics or information weighting. A two-agree/one-disagrees pattern is a natural candidate for view peeling, but disagreement may also arise from occlusion/different visible surfaces and must not be blindly classified as an outlier.

## 13. Uncertainty as a compute-control signal

A local measurement should ideally produce

`range, sigma_range, status`.

Uncertainty is then used in later frames:

```text
low sigma + low innovation -> reuse or cheap check
sigma increased -> refresh
pair disagreement -> increase evidence budget
all evidence weak -> UNKNOWN
```

Analytic measurement-noise estimates are useful for deterministic DSP matchers, but model mismatch must be characterized separately. Theoretical covariance alone is not sufficient evidence.

## 14. Bootstrap, steady state and rebootstrap

### BOOTSTRAP

Use wider spatial coverage and broader search to initialize scene/range memory. This path may be slower than steady state but must still be bounded and profiled.

### TRACK / UPDATE

Use history, narrow search ranges, active-anchor selection, best-pair-first evaluation and early exit.

### REBOOTSTRAP

Trigger when coverage/confidence collapses, pose jumps, image/scene change is large, too many regions become dynamic or stale uncertainty exceeds a threshold.

## 15. Camera-quality characterization

The claim that fisheye information necessarily decreases monotonically toward the edge is not accepted as a prior fact.

NADIR-CQ should measure versus angular position:

- calibration residual;
- local sharpness/MTF proxy;
- contrast/SNR;
- vignetting/exposure clipping;
- feature repeatability;
- stereo correspondence quality.

Only measured evidence may justify edge weighting.

## 16. Runtime acceptance

Current engineering targets:

- hard: >= 15 FPS and P95 capture-to-depth < 80 ms;
- design: >= 20 FPS and P95 < 60 ms;
- stretch: 30 FPS.

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
catastrophic-range-error rate
near/new-structure recall
coarse range error
```

Reducing a local operation count is not enough if end-to-end P95 latency does not materially improve.

## 17. Research ordering

The architecture should be validated in stages:

```text
Gate A  real native-fisheye geometry feasibility
Gate B  local matcher benchmark: ORB/Census vs spherical DSP vs tiny learned feature
Gate C  lambda/Jacobian/information-driven search
Gate D  best-pair-first + 3-pair consensus
Gate E  temporal reuse with previous range + pose
Gate F  adaptive spatial/event-triggered scheduling
Gate G  IMU then RTK covariance-conditioned search compression
Gate H  QCS8550/QNN/accelerator profiling
```

`docs/LATENCY_FIRST_ARCHITECTURE.md` contains the detailed downstream hypothesis. `docs/VALIDATION_STATUS.md` remains authoritative for what is actually proven.
