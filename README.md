# Fisheye-Depth

## NADIR — Native-fisheye Adaptive Depth Inference from Rig

NADIR is a research project targeting **fast approximate metric radial range + confidence** from a synchronized downward-facing three-fisheye UAV rig.

> **Current scientific status: `GATE_A_NOT_YET_PROVEN`.**
>
> The repository contains geometry/data tooling and experimental baselines, but it does **not** yet demonstrate that the final `3 × ~225°` NADIR pipeline works. The active task remains real-data feasibility and geometry identification. See `docs/VALIDATION_STATUS.md`.

The canonical downstream design is now:

- `docs/FINAL_RESEARCH_ARCHITECTURE.md` — full final research architecture;
- `docs/LATENCY_FIRST_ARCHITECTURE.md` — latency-first design rationale;
- `docs/IMPLEMENTATION_PLAN.md` — staged implementation/benchmark plan;
- `docs/VALIDATION_STATUS.md` — authoritative statement of what is actually proven.

## Research priority

NADIR is explicitly **latency-first**:

```text
1. P95 end-to-end latency
2. robustness / catastrophic near-far error avoidance
3. coarse metric-range accuracy + near/new-structure recall
4. fine depth accuracy
```

The target is not sub-centimeter reconstruction. A coarse range delivered early can be more useful than a more precise estimate delivered too late.

Current engineering targets remain:

- hard target: `>= 15 FPS` and P95 capture-to-range `< 80 ms`;
- design target: `>= 20 FPS` and P95 `< 60 ms`;
- stretch target: `30 FPS`.

These are targets, not measured QCS8550 claims.

## Target sensing stack

```text
3 × synchronized native fisheye cameras (~225° FoV)
+ calibrated intrinsics/extrinsics
+ IMU
+ GNSS/RTK when available
+ optional barometer prior
                    |
                    v
       approximate metric radial range
                + confidence
```

This is the target architecture, not the current validated implementation.

## Non-negotiable geometry rule

**Do not flatten, stitch or globally rectify the fisheye RGB views before stereo.**

The three cameras retain separate physical centers. Calibrated ray lookups, local spherical signals and common output-ray representations are permitted, but parallax must not be destroyed by collapsing the rig into one virtual optical center.

Output semantics are radial range from a selected rig reference origin:

```text
P_i = O_R + rho_i r_i,   ||r_i|| = 1
```

Navigation/global state uses NED; rig/body uses FRD; camera frames remain native.

## Current task — Gate A

Gate A asks whether:

```text
known native camera models
+ known physical camera-center baselines
+ real synchronized multi-view correspondences
        |
        v
metric generalized-camera triangulation
        |
        v
radial range consistent with released GT
```

The first bootstrap dataset is MVS-GI because its released setup is close to the required three-camera same-facing topology. Its public raw-camera configuration is ~195° and therefore **cannot validate** the final `97.5°–112.5°` annulus of a 225° lens.

Gate A measures sparse generalized-camera triangulation, closest-ray gap, triangulation angle/conditioning, reprojection error and metric range error against released GT. No automatic scientific PASS threshold is frozen.

## Status vocabulary

- `SOURCE_VERIFIED` — supported by released source/data semantics;
- `MATH_UNIT_VERIFIED` — controlled math/unit tests only;
- `REAL_MEASURED` — measured on actual downloaded payloads;
- `ACCEPTED` — owner-reviewed evidence passes a frozen contract;
- `HYPOTHESIS_NOT_VALIDATED` — retained candidate, not an accepted pipeline block.

Code existence does not imply empirical validation.

## What is implemented now

- MVS-GI source-layout, calibration and compressed-distance adapters;
- native LinearSphere and DoubleSphere projection/unprojection;
- explicit MVS-GI half-pixel-center handling;
- frame graph / camera extrinsic conversion;
- calibrated `CameraRig` with physical camera centers and baselines;
- generalized two-ray triangulation primitives;
- lower-hemisphere ray/visibility/observability/LUT tooling;
- metric error/profiling utilities;
- sparse Gate A harness: `scripts/run_gate_a_sparse.py`;
- older dense photometric sphere-sweep prototype retained as `HYPOTHESIS_NOT_VALIDATED`;
- unit tests and GitHub Actions CI.

## Final research architecture — hypothesis only

After Gate A, the current final design direction combines selected ideas from the reviewed spherical DSP matcher and the LAWGRAPH research concept, but only where they directly help depth/range inference.

```text
L0  Geometry / static law layer
    RayLUT + solid angle + extrinsics + visibility + static quality
                         |
L1  Fast sensory buffer
    current images + timestamps + IMU synchronization
                         |
L2  Typed temporal predictor
    previous range + uncertainty + provenance + relative SE(3)
                         |
L3  Surprise / uncertainty / deadline scheduler
    decide WHEN, WHERE and HOW MUCH compute to spend
                         |
L4  Local native-ray measurement
    reuse / Census-Hamming / spherical DSP / tiny learned fallback
    + direct-depth / inverse-depth / lambda search
                         |
L5  Three-camera pair manager
    best pair first -> second if needed -> third-pair fallback
                         |
L6  Belief update
    range + sensor uncertainty + model uncertainty + status
                         |
L7  Multi-timescale memory
    sensory buffer + working range memory + persistent spatial state
                         |
L8  Runtime assurance / rebootstrap
    UNKNOWN rather than fabricated depth
```

The expensive matcher is only one layer. The main architectural objective is to **avoid unnecessary matching**.

## LAWGRAPH ideas retained in NADIR

NADIR does not become a general LAWGRAPH world model. It only retains the mechanisms directly useful to fast depth:

- **equation-first geometry** — do not relearn projection, baselines or rigid transforms;
- **typed state** — range carries uncertainty, time, source and status;
- **predictive coding** — predict from history, measure innovation, recompute only where needed;
- **event-driven compute** — compute scales with surprise/uncertainty/risk/deadline;
- **multi-timescale memory** — short sensory buffer, working range memory, longer-lived spatial support;
- **progressive complexity** — temporal reuse -> cheap Census -> spherical DSP -> tiny learned fallback;
- **learn only unresolved residuals** — learned blocks should not relearn known geometry;
- **fail-closed behavior** — insufficient evidence returns `UNKNOWN`, not an invented range.

Optional future offline work may attempt to replace learned quality/uncertainty/scheduler residuals with compact identified or symbolic equations, but that is a late-stage hypothesis, not part of Gate A.

## Compute dimensions

The main downstream workload is treated as approximately:

```text
N_active_rays
× N_search_candidates
× N_camera_pairs
× N_signal_bands_or_feature_channels
```

The scheduler should reduce each factor independently while preserving robustness.

The AMR/CFD analogy is limited to adaptive spatial resolution:

```text
stable/smooth/high-confidence -> coarse or reuse
changing/edge/uncertain/new   -> refine
```

NADIR does **not** solve Navier-Stokes or perform aerodynamic CFD inside the depth pipeline.

## Local measurement candidates

After Gate A, benchmark rather than assume:

1. ORB/classical reference;
2. Census/Hamming;
3. local spherical harmonic/Fourier-Bessel DSP signal;
4. tiny learned feature/residual only if deterministic methods are insufficient.

A useful pairwise candidate coordinate is:

```text
lambda = B_ij / d
```

with native-sphere epipolar Jacobian `J_lambda` for candidate spacing, local refinement and information/conditioning scoring. It must be benchmarked against direct depth and inverse depth before promotion.

## Three-camera strategy

Physical pairs are `01`, `02`, `12`.

Do not run all three at full cost by default:

```text
best pair first
    -> early exit if sufficient
    -> second pair if ambiguous
    -> third pair only as fallback / consistency evidence
```

Disagreement may be occlusion or different visible surfaces, so peeling requires explicit validation.

## Runtime evaluation contract

Every downstream experiment must report at least:

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
fraction reaching each progressive-compute level
bootstrap latency
steady-state latency
rebootstrap frequency
catastrophic-range-error rate
near/new-structure recall
coarse range error
UNKNOWN/abstention rate
```

Reducing operation count alone is not success if P95 end-to-end latency does not materially improve.

## Research gate sequence

```text
Gate A  real native-fisheye 3-camera metric geometry feasibility
Gate B  local measurement benchmark
Gate C  search coordinate / Jacobian / information allocation
Gate D  best-pair-first + 3-camera consensus
Gate E  typed temporal memory + geometric prediction
Gate F  predictive surprise + progressive compute
Gate G  adaptive spatial/active-ray scheduling
Gate H  IMU search compression
Gate I  RTK/GNSS covariance-conditioned search compression
Gate J  tiny learned residual only if still useful
Gate K  QCS8550 deployment / accelerator profiling
Gate L  optional offline equation/parameter compression
```

See `docs/FINAL_RESEARCH_ARCHITECTURE.md` for the complete structure and `docs/VALIDATION_STATUS.md` for the authoritative current boundary.

## Dataset strategy

No public dataset has been identified that simultaneously provides the exact target combination of **3 synchronized fisheye cameras + 225° FoV + dense metric range GT**.

Current source roles:

- **MVS-GI** — Gate A bootstrap for three-camera same-facing geometry; public source configuration ~195°;
- **OmniMVS** — near-target ~220° representation reference, different rig topology;
- **KAIST Sphere Stereo** — multiview fisheye/sphere-sweep reference;
- **LaFiDa** — real synchronized three-fisheye reference with smaller FoV;
- **NADIR-SYN225** — planned exact-target synthetic data;
- **NADIR-REAL225** — planned real target-rig calibration/validation.

A result on 195° data must never be promoted as proof for the 225° extreme annulus.

## Immediate next milestone

The design is now broader on paper, but execution has **not moved past Gate A**:

1. pull this repository to the Ubuntu machine;
2. keep downloaded MVS-GI/sample artifacts under `/media/nahhao74/KINGSTON`;
3. inspect one actual released sample;
4. run `scripts/run_gate_a_sparse.py` with no optional geometry thresholds first;
5. review raw failure distributions;
6. freeze acceptance/filter criteria only after evidence exists;
7. decide whether Gate A is supported, unsupported or still underidentified.
