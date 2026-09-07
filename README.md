# Fisheye-Depth

## NADIR — Native-fisheye Adaptive Depth Inference from Rig

NADIR is a research pipeline for generating a **metric radial depth map** from a synchronized downward-facing multi-fisheye rig on a UAV.

### Target sensing stack

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

The current goal is depth generation itself. Downstream landing, obstacle avoidance, semantic hazard reasoning, mapping, or control are intentionally outside NADIR-Core until the depth stack is validated.

## Core design principles

1. **Do not stitch RGB before stereo.** The three views remain separate because their parallax is the primary spatial depth evidence.
2. **Native fisheye geometry is preserved.** RGB is not first rectified into a pinhole panorama.
3. **The common output is metric radial range** in a rig/body reference frame:

   `P_i = O_R + rho_i * r_i`, with `||r_i|| = 1`.

4. **NED is the navigation-state frame; FRD/body is the depth-computation frame.** IMU state and RTK/GNSS are fused in NED, then converted to relative SE(3) for temporal depth conditioning.
5. **IMU/RTK are part of depth generation, not only post-processing.** They can de-rotate temporal correspondence, propagate previous depth, and narrow the candidate-depth search range.
6. **Real-time feasibility is a first-class acceptance criterion.** Accuracy improvements that break runtime are rejected.

## Current architecture

```text
C0 fisheye ─┐
C1 fisheye ─┼─► shared lightweight encoder ───────────┐
C2 fisheye ─┘                                         │
                                                      │
Calibration ─► ray geometry ─► visibility/quality ────┤
                                                      │
Previous depth ─┐                                     │
IMU ────────────┼─► NED state ─► relative SE(3) ──────┤
RTK/GNSS ───────┘                                     │
                                                      ▼
                                        adaptive radial hypotheses
                                                      │
                                                      ▼
                                         native-fisheye MVS sweep
                                                      │
                                                      ▼
                                         multi-view feature matching
                                                      │
                                                      ▼
                                         lightweight regularization
                                                      │
                                                      ▼
                                            metric radial depth
```

## Research modules

- **NADIR-PERF** — latency/FPS/memory profiling and real-time gates.
- **NADIR-CAL** — 225° fisheye calibration and projection/unprojection.
- **NADIR-RAY** — common lower-hemisphere ray grid.
- **NADIR-VIS** — visibility, overlap, baseline, and triangulation observability.
- **NADIR-CQ / QMAP** — camera-quality characterization; edge degradation is treated as a hypothesis to measure, not an assumption.
- **NADIR-TRI** — classical multi-ray triangulation baseline.
- **NADIR-LUT** — precomputed fixed-rig projection/sampling tables.
- **NADIR-MVS** — native-fisheye multi-view stereo baseline.
- **NADIR-GI** — geometry-informed sparse candidate selection.
- **NADIR-MOTION** — IMU-conditioned temporal depth prior.
- **NADIR-RTK** — RTK/GNSS-conditioned metric temporal baseline.
- **NADIR-EDGE** — ONNX/QNN/INT8 deployment and QCS8550 profiling.

## Real-time acceptance gate

Minimum gate:

- end-to-end throughput >= **15 FPS**;
- P95 capture-to-depth latency < **80 ms**;
- no uncontrolled CPU fallback in the deployed neural graph.

Design target:

- >= **20 FPS**;
- P95 latency < **60 ms**.

Stretch target:

- **30 FPS**.

No new module is accepted only because it improves accuracy. It must report the change in depth error, latency, memory, and FPS.

## Dataset strategy

No public dataset has yet been identified that simultaneously provides the exact target combination of **3 synchronized fisheye cameras + 225° FoV + dense metric depth ground truth**. The current staged strategy is:

- **MVS-GI** — closest 3-camera same-facing topology; public code uses ~195° FoV.
- **OmniMVS** — ~220° fisheye, useful for near-target extreme-FoV representation and edge behavior.
- **KAIST Sphere Stereo** — multiview fisheye sphere-sweeping and a useful real-time stereo reference.
- **LaFiDa** — real synchronized 3-fisheye data with LiDAR/pose, but smaller FoV.
- **NADIR-SYN225** — planned synthetic exact-target dataset with 3 × 225° fisheye and metric radial GT.
- **NADIR-REAL225** — later real rig capture for calibration and validation.

A model trained on 195° data must not be treated as validated for the 97.5°–112.5° incidence-angle region of a 225° lens.

## Implementation order

```text
PERF
  ↓
CAL
  ↓
RAY
  ↓
VIS
  ↓
CQ / QMAP
  ↓
TRI
  ↓
LUT
  ↓
MVS-V0
  ↓
GI candidates
  ↓
MOTION / IMU
  ↓
RTK
  ↓
EDGE / QCS8550
```

The first scientific objective is not a large neural model. It is a geometry-correct and profiled baseline that converts one synchronized three-fisheye sample into a metric depth map and can be compared directly with ground truth.

See the `docs/` directory for the architecture, dataset plan, implementation plan, and research/anti-bias methodology.