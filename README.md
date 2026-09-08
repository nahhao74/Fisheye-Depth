# Fisheye-Depth

## NADIR — Native-fisheye Adaptive Depth Inference from Rig

NADIR is a research project targeting a **metric radial depth map** from a synchronized downward-facing multi-fisheye UAV rig.

> **Current scientific status: `GATE_A_NOT_YET_PROVEN`.**
>
> The repository contains geometry/data tooling and experimental baselines, but it does **not** yet demonstrate that the final 3 × 225° NADIR depth pipeline works. The active task is real-data feasibility and geometry identification. See `docs/VALIDATION_STATUS.md`.

## Target sensing stack

```text
3 × synchronized fisheye cameras (~225° FoV)
+ calibrated intrinsics/extrinsics
+ IMU
+ GNSS/RTK when available
+ optional barometer prior
                    │
                    ▼
          metric radial depth map
```

This is the **target**, not the current validated implementation. The present Gate A scope uses camera geometry and real/released stereo evidence only; IMU/RTK and learned dense inference are downstream hypotheses.

The project is limited to depth generation. Landing, obstacle avoidance, semantic hazard reasoning, mapping and control are outside NADIR-Core.

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

Only after Gate A is accepted should dense classical MVS and learned feature matching be promoted.

## Target architecture hypothesis — not accepted yet

The longer-term hypothesis remains:

```text
C0 fisheye ─┐
C1 fisheye ─┼─► shared lightweight encoder ───────────┐
C2 fisheye ─┘                                         │
                                                      │
Calibration ─► ray geometry ─► visibility/quality ────┤
                                                      │
Previous depth ─┐                                     │
IMU ────────────┼─► navigation state ─► relative SE(3)┤
RTK/GNSS ───────┘                                     │
                                                      ▼
                                        adaptive radial hypotheses
                                                      │
                                                      ▼
                                         native-fisheye MVS
                                                      │
                                                      ▼
                                            metric radial depth
```

Every block in this diagram after Gate A is a research hypothesis until measured and promoted.

## Future modules

- **NADIR-PERF** — latency/FPS/memory instrumentation.
- **NADIR-CAL** — target 225° calibration characterization.
- **NADIR-RAY** — common lower-hemisphere ray representation.
- **NADIR-VIS** — overlap, baseline and triangulation observability.
- **NADIR-CQ / QMAP** — measured camera-quality characterization, not assumed radial edge degradation.
- **NADIR-TRI** — classical generalized-camera triangulation; currently the active Gate A core.
- **NADIR-LUT** — fixed-rig projection/sampling tables; currently tooling only.
- **NADIR-MVS** — dense native-fisheye MVS candidate; frozen until Gate A review.
- **NADIR-GI** — geometry-informed candidate selection; future hypothesis.
- **NADIR-MOTION** — IMU-conditioned temporal prior; future hypothesis.
- **NADIR-RTK** — RTK/GNSS-conditioned temporal baseline; future hypothesis.
- **NADIR-EDGE** — QCS8550/QNN deployment; future hypothesis.

## Runtime targets — not measured claims

Future deployment acceptance goals are:

- hard target: >= 15 FPS and P95 capture-to-depth < 80 ms;
- design target: >= 20 FPS and P95 < 60 ms;
- stretch target: 30 FPS.

These are engineering targets only. No QCS8550/QNN measurement has been produced yet.

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

1. pull this repository to the Ubuntu machine;
2. keep downloaded MVS-GI/sample artifacts under `/media/nahhao74/KINGSTON`;
3. inspect one actual released sample;
4. run `scripts/run_gate_a_sparse.py` with no optional geometry thresholds first;
5. review the raw failure distributions;
6. freeze any acceptance/filter criteria only after seeing the evidence;
7. decide whether Gate A is supported, unsupported or still underidentified.

See `DEVELOPMENT.md` and `docs/VALIDATION_STATUS.md` for the authoritative current boundary.
