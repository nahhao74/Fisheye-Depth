# NADIR Development Baseline v0.5 — Gate A + Latency-First Research Direction

The repository contains substantial geometry/tooling code, but the **scientific pipeline is not yet proven**. Current execution remains intentionally bounded to **Gate A: real-data feasibility and geometry identification for synchronized three-fisheye metric stereo**.

The downstream architecture has been updated on paper to be **latency-first, history-aware and adaptive**, but this does not move the current validation boundary.

See `docs/VALIDATION_STATUS.md` for authoritative status and `docs/LATENCY_FIRST_ARCHITECTURE.md` for the post-Gate-A research direction.

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

## Post-Gate-A design priority

If Gate A supports the metric-stereo premise, downstream work uses this priority:

```text
1. P95 latency
2. robustness / catastrophic-error avoidance
3. coarse metric-range accuracy
4. fine depth accuracy
```

The desired steady-state pipeline is not a dense full-search network on every frame. It is expected to combine:

- native fisheye RayLUT/solid-angle geometry;
- persistent range + uncertainty memory;
- IMU/RTK pose-conditioned prediction;
- active-region scheduling;
- best-pair-first evaluation across pairs `01`, `02`, `12`;
- a low-cost local measurement engine;
- early exit and robust pair consensus;
- local refinement only where information/uncertainty justifies the latency.

Candidate local measurement engines after Gate A are:

- Census/Hamming;
- local spherical harmonic/Fourier-Bessel DSP signal;
- tiny learned features only if they beat deterministic baselines on the latency/robustness Pareto frontier.

A reviewed spherical DSP matcher contributes useful hypotheses such as native ray + solid-angle lookup, `lambda = B/d` search, Jacobian-driven spacing, progressive band loading, analytic noise estimates and explicit rejection states. None of those results are transferred into NADIR as evidence until reproduced in this repository.

## Frozen downstream hypotheses

The following remain **not accepted milestones** before Gate A owner review:

- spherical DSP matcher for NADIR;
- Census/Hamming dense/local matcher;
- `lambda = B/d` search;
- Fisher/Jacobian candidate allocation;
- best-pair-first / 3-pair consensus / peeling;
- persistent temporal range memory;
- adaptive active-ray/AMR-like scheduling;
- shared CNN/ResNet/attention feature encoders;
- IMU/RTK temporal priors;
- QCS8550/QNN deployment claims.

The existing dense photometric code remains `HYPOTHESIS_NOT_VALIDATED`; it should not be interpreted as the final NADIR algorithm.

## Coordinate/semantic contract

- Navigation/global state: NED when navigation is introduced later.
- UAV body/rig: FRD (`+X forward`, `+Y right`, `+Z down`).
- Each camera retains its native calibrated frame.
- `T_C_B` maps Body/Rig points into a camera frame.
- Sparse triangulation uses distinct physical camera centers; cameras are never collapsed to a single optical center.
- Fisheye RGB is not flattened/panoramically stitched before stereo.
- Final depth/range semantics remain radial range from the chosen rig reference origin.

## Runtime contract for later stages

Current engineering targets, not measured claims:

- hard: >= 15 FPS and P95 capture-to-depth < 80 ms;
- design: >= 20 FPS and P95 < 60 ms;
- stretch: 30 FPS.

Later experiments must report P50/P95 latency, active-ray fraction, candidates per active ray, evaluated pairs per active ray, signal bands/channels, bootstrap vs steady-state latency, catastrophic-range-error rate and near/new-structure recall.

The AMR/CFD analogy is limited to adaptive spatial resolution. NADIR does **not** solve Navier-Stokes or use aerodynamic CFD in its depth core.

## Current validation level

- source semantics: substantially audited;
- projection/transform/triangulation mathematics: unit/synthetic tested;
- real MVS-GI sparse metric-stereo evidence: **not yet produced**;
- exact 225° real evidence: **not available**;
- spherical DSP/Census/tiny-CNN matcher comparison: **not measured**;
- temporal/history scheduler benefit: **not measured**;
- IMU/RTK compute reduction: **not measured**;
- QCS8550 latency/FPS: **not measured**.

Therefore the scientific status remains:

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
7. owner reviews Gate A evidence;
8. only then begin the latency-first matcher benchmark described in `docs/IMPLEMENTATION_PLAN.md`.
