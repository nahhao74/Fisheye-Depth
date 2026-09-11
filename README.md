# Fisheye-Depth

## NADIR — Native-fisheye Adaptive Depth Inference from Rig

NADIR is a research project targeting a **fast metric radial-range estimate** from a synchronized downward-facing multi-fisheye UAV rig.

> **Current scientific status: `GATE_A_NOT_YET_PROVEN`.**
>
> The repository contains geometry/data tooling and experimental baselines, but it does **not** yet demonstrate that the final 3 × 225° NADIR depth pipeline works. The active task is real-data feasibility and geometry identification. See `docs/VALIDATION_STATUS.md`.

## Research priority

NADIR is now explicitly **latency-first**:

```text
1. P95 latency
2. robustness / catastrophic-error avoidance
3. coarse metric-range accuracy
4. fine depth accuracy
```

The intended output does not require absolute sub-centimeter reconstruction. It must estimate useful approximate range quickly and avoid catastrophic near/far mistakes. Accuracy improvements that materially worsen P95 latency are rejected unless they run only on a bootstrap/background path.

Current engineering targets remain:

- hard target: >= 15 FPS and P95 capture-to-depth < 80 ms;
- design target: >= 20 FPS and P95 < 60 ms;
- stretch target: 30 FPS.

These are targets, not measured QCS8550 claims.

## Target sensing stack

```text
3 × synchronized fisheye cameras (~225° FoV)
+ calibrated intrinsics/extrinsics
+ IMU
+ GNSS/RTK when available
+ optional barometer prior
                    │
                    ▼
       metric radial range + confidence
```

This is the **target**, not the current validated implementation. The present Gate A scope uses camera geometry and real/released stereo evidence only; IMU/RTK and adaptive temporal inference are downstream hypotheses.

The project is limited to depth/range generation. Landing, obstacle avoidance, semantic hazard reasoning, mapping and control are outside NADIR-Core.

## Non-negotiable geometry rule

**Do not flatten, stitch or globally rectify the three fisheye images before stereo.**

The three native fisheye views remain separate because their physical camera-center offsets/parallax are the metric depth evidence. Downstream code may use calibrated ray lookup tables, spherical/local signal representations or common output rays, but not a panorama that collapses the rig into one virtual optical center.

## Current task — Gate A

Gate A asks whether:

```text
known camera models
+ known physical camera-center baselines
+ real synchronized multi-view correspondences
        │
        ▼
metric triangulated 3-D / radial range
        │
        ▼
consistent with metric ground truth
```

The first bootstrap dataset is MVS-GI because its released setup is close to the required three-camera same-facing topology. Its public raw-camera configuration is ~195° and therefore **cannot validate** the final 97.5°–112.5° annulus of a 225° lens.

Gate A measures sparse generalized-camera triangulation, closest-ray gap, triangulation angle/conditioning, reprojection error and metric depth error against released GT. No automatic scientific PASS threshold is currently frozen.

## Status categories

- `SOURCE_VERIFIED` — supported by released source/data semantics.
- `MATH_UNIT_VERIFIED` — controlled math/unit tests only.
- `REAL_MEASURED` — measured on actual downloaded payloads.
- `ACCEPTED` — owner-reviewed evidence passes a frozen contract.
- `HYPOTHESIS_NOT_VALIDATED` — retained candidate, not an accepted pipeline block.

Most current implementation is in the first two categories. Real-data Gate A evidence has not yet been produced.

## Geometry contract

1. **Do not stitch RGB before stereo.** Separate camera centers/parallax are the primary spatial depth evidence.
2. **Preserve native fisheye geometry.** Do not silently replace a >180° fisheye model with pinhole geometry.
3. **Use generalized-camera rays.** Each observation is `(O_c, r_c)` with its own physical camera center.
4. **Dense target semantics are radial range** from a selected rig reference origin:

   `P_i = O_R + rho_i * r_i`, with `||r_i|| = 1`.

5. **Body/Rig depth geometry is distinct from later navigation state.** FRD is the intended body/rig convention; NED is reserved for navigation-state fusion when motion priors are introduced later.
6. A calibrated per-camera `RayLUT` may cache native ray direction, solid angle, validity and later measured quality metadata, but it must preserve camera identity.

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
- an older dense photometric sphere-sweep prototype retained as `HYPOTHESIS_NOT_VALIDATED`;
- unit tests and GitHub Actions CI.

Code existence does **not** imply empirical validation.

## Gate A run sequence

```text
MVS-GI real sample
      ↓
verify manifest / camera model / extrinsics / masks / GT semantics
      ↓
ORB sparse matches on native fisheye images
      ↓
pixel → native ray → Body/Rig ray
      ↓
generalized two-ray triangulation
      ↓
ray gap + angle + conditioning + reprojection diagnostics
      ↓
project triangulated point into released rig-reference GT
      ↓
metric radial error vs GT
      ↓
error vs incidence angle / baseline geometry
      ↓
owner review of Gate A evidence
```

Only after Gate A is accepted should downstream local matchers, temporal reuse and adaptive scheduling be promoted.

## Post-Gate-A architecture hypothesis — latency-first

The current research direction is **not** “run a full dense network every frame.” It is:

```text
3 native fisheye
      ↓
RayLUT / geometry / visibility
      ↓
previous range + uncertainty + IMU/RTK pose prior
      ↓
adaptive compute scheduler
      ↓
active anchors only
      ↓
best camera pair first
      ↓
local low-cost matcher
  (Census/Hamming OR spherical DSP OR tiny learned feature)
      ↓
local lambda/depth refinement
      ↓
second/third pair only if needed
      ↓
robust consensus / confidence
      ↓
persistent sparse range memory
```

The scheduler asks three questions before expensive matching:

```text
WHEN must this region be recomputed?
WHERE should compute be spent?
HOW MUCH evidence is enough before stopping?
```

The intended steady-state behavior is prediction → verification → local correction, rather than full-search-from-scratch every frame.

See `docs/LATENCY_FIRST_ARCHITECTURE.md` for the detailed hypothesis.

## DSP/ray-domain matcher direction

A reviewed native-spherical DSP matcher suggests several useful hypotheses for NADIR:

- calibrated `pixel -> unit ray + solid angle` lookup;
- local spherical harmonic/Fourier-Bessel signal instead of flattening the fisheye image;
- pairwise search using `lambda = B / d`;
- Jacobian-driven search spacing/refinement;
- progressive frequency-band loading;
- analytic measurement-noise propagation;
- explicit early rejection rather than inventing a depth value.

These ideas are **not yet NADIR evidence**. They become candidate local measurement engines to benchmark against Census/Hamming and a tiny learned feature matcher.

## Temporal/adaptive compute hypothesis

After a trustworthy range estimate exists, later frames should propagate it using relative SE(3) and uncertainty. Stable regions may be reused or cheaply checked, while new, stale, uncertain, near or discontinuous regions receive more rays/candidates/pairs.

Compute therefore becomes adaptive in roughly four dimensions:

```text
N_active_rays
× N_depth_or_lambda_candidates
× N_camera_pairs
× N_signal_bands_or_feature_channels
```

The goal is to reduce average work while maintaining a hard tail-latency budget. An AMR-like idea may be used only as an **adaptive spatial-resolution strategy**; NADIR does not solve Navier-Stokes or perform aerodynamic CFD inside the depth pipeline.

## Future modules

- **NADIR-PERF** — P50/P95 latency, FPS, memory and active-compute instrumentation.
- **NADIR-CAL** — target 225° calibration characterization.
- **NADIR-RAY** — native per-pixel rays and common lower-hemisphere representation.
- **NADIR-VIS** — overlap, baseline and triangulation observability.
- **NADIR-CQ / QMAP** — measured camera-quality characterization, not assumed radial edge degradation.
- **NADIR-TRI** — classical generalized-camera triangulation; currently the active Gate A core.
- **NADIR-LUT** — fixed-rig projection/ray/solid-angle/visibility tables.
- **NADIR-DSP** — local spherical/Census measurement-engine candidates; future hypothesis.
- **NADIR-SCHED** — latency-budgeted active-ray/pair/search-band scheduler; future hypothesis.
- **NADIR-MEM** — persistent depth/range + uncertainty + age/history state; future hypothesis.
- **NADIR-MOTION** — IMU-conditioned temporal propagation; future hypothesis.
- **NADIR-RTK** — RTK/GNSS-conditioned metric temporal baseline; future hypothesis.
- **NADIR-MVS** — compact learned feature matcher only if it beats deterministic baselines on the Pareto frontier.
- **NADIR-EDGE** — QCS8550/QNN/accelerator profiling; future hypothesis.

## Runtime evaluation contract

Every later module must report at least:

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
catastrophic-range-error rate
near/new-structure recall
coarse range error
```

Reducing ray count alone is not success if P95 latency does not materially improve.

## Dataset strategy

No public dataset has been identified that simultaneously provides the exact target combination of **3 synchronized fisheye cameras + 225° FoV + dense metric depth GT**.

Current source roles:

- **MVS-GI** — Gate A bootstrap for three-camera same-facing geometry; public source configuration ~195°.
- **OmniMVS** — near-target ~220° representation reference, different rig topology.
- **KAIST Sphere Stereo** — multiview fisheye/sphere-sweep reference.
- **LaFiDa** — real synchronized three-fisheye reference with smaller FoV.
- **NADIR-SYN225** — planned exact-target synthetic data.
- **NADIR-REAL225** — planned real target-rig calibration/validation.

A result on 195° data must never be promoted as proof for the 225° extreme annulus.

## Immediate next milestone

The architecture has been expanded on paper, but the execution boundary has **not** moved past Gate A:

1. pull this repository to the Ubuntu machine;
2. keep downloaded MVS-GI/sample artifacts under `/media/nahhao74/KINGSTON`;
3. inspect one actual released sample;
4. run `scripts/run_gate_a_sparse.py` with no optional geometry thresholds first;
5. review the raw failure distributions;
6. freeze any acceptance/filter criteria only after seeing the evidence;
7. decide whether Gate A is supported, unsupported or still underidentified.

See `DEVELOPMENT.md`, `docs/VALIDATION_STATUS.md`, and `docs/LATENCY_FIRST_ARCHITECTURE.md` for the authoritative current boundary and downstream research direction.
