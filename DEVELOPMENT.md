# NADIR Development Baseline v0.4 — Gate A

The repository contains substantial geometry/tooling code, but the **scientific pipeline is not yet proven**. Current work is intentionally bounded to **Gate A: real-data feasibility and geometry identification for synchronized three-fisheye metric stereo**.

See `docs/VALIDATION_STATUS.md` for the authoritative status vocabulary and task boundary.

## What exists now

- source-driven MVS-GI file/metadata/GT adapters;
- native `LinearSphere` and `DoubleSphere` camera models;
- explicit MVS-GI half-pixel-center handling;
- frame-graph/extrinsic conversion into a common Rig/Body frame;
- lower-hemisphere ray-grid, visibility, observability and LUT tooling;
- generalized two-ray sparse triangulation with closest-ray gap, signed ray distances, triangulation angle and conditioning;
- basic depth metrics and profiling tools;
- an experimental dense photometric sweep retained only as a later falsification candidate;
- unit tests + GitHub Actions regression checks.

These code blocks are tooling/prototypes. They do **not** by themselves establish real 3-camera metric depth performance.

## Current scientific task

The active task is to establish or falsify:

```text
known camera models
+ known camera-center baselines
+ real synchronized multi-view correspondences
    -> metric triangulated 3-D/radial range consistent with GT
```

The first real-data harness is:

```bash
python scripts/run_gate_a_sparse.py /path/to/MVS_GI_ROOT \
  --sample-index 0 \
  --json-out /media/nahhao74/KINGSTON/nadir_gate_a/sample0.json
```

The harness uses native fisheye images and released source masks, ORB + Hamming cross-check as a deliberately simple sparse correspondence baseline, generalized-camera ray triangulation and comparison to the released rig-reference metric distance image.

It does **not** auto-declare PASS. Any optional geometry filters are explicit CLI experiment parameters and are recorded in the report.

## Required Gate A characterization

For each camera pair and in aggregate, measure:

- physical baseline;
- raw feature/match count;
- numerically valid and forward triangulation count;
- closest-ray gap;
- triangulation angle/conditioning;
- pixel reprojection error;
- metric depth absolute/relative error against GT;
- depth error by incidence angle.

Important incidence regions for the MVS-GI bootstrap include `0–60°`, `60–90°`, and `90–97.5°`. The final target 225° rig additionally requires dedicated evidence for `97.5–112.5°`; MVS-GI cannot supply that evidence.

## Frozen downstream hypotheses

The following code/ideas are **not accepted milestones yet** and must not be promoted before Gate A owner review:

- dense photometric sphere sweep;
- `K=4/8/16/32` candidate optimization;
- shared CNN/ResNet/attention feature encoders;
- geometry-informed learned candidate selection;
- learned camera-quality weighting;
- IMU/RTK temporal priors;
- QCS8550/QNN deployment claims.

The existing dense photometric code remains in the repository as `HYPOTHESIS_NOT_VALIDATED`; it should not be interpreted as the final NADIR algorithm.

## Coordinate/semantic contract

- Navigation/global state: NED when navigation is introduced later.
- UAV body/rig: FRD (`+X forward`, `+Y right`, `+Z down`).
- Each camera retains its native calibrated frame.
- `T_C_B` maps Body/Rig points into a camera frame.
- Sparse triangulation uses distinct physical camera centers; cameras are never collapsed to a single optical center.
- Final dense depth semantics remain radial range from the chosen rig reference origin, but dense promotion waits for Gate A evidence.

## Current validation level

- source semantics: substantially audited;
- projection/transform/triangulation mathematics: unit/synthetic tested;
- real MVS-GI sparse metric-stereo evidence: **not yet produced**;
- exact 225° real evidence: **not available**;
- learned depth accuracy: **not measured**;
- QCS8550 latency/FPS: **not measured**.

Therefore the scientific status is currently:

```text
GATE_A_NOT_YET_PROVEN
```

## Immediate next sequence

1. clone/pull this repository on the Ubuntu machine;
2. place a small MVS-GI validation/sample payload under `/media/nahhao74/KINGSTON`;
3. run `scripts/inspect_mvs_gi.py` and verify actual manifest/model/extrinsic semantics;
4. run `scripts/run_gate_a_sparse.py` on exactly one sample with no optional geometry thresholds first;
5. inspect failure distributions and only then propose explicit filters/acceptance criteria;
6. repeat on a small representative sample set after the single-sample interpretation is understood;
7. owner reviews Gate A evidence before any dense/learned architecture is promoted.
