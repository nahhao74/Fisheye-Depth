# NADIR Development Baseline v0.7 — Gate A + Canonical Latency-First Architecture + Point-Cloud Output

The repository contains substantial geometry/tooling code, but the **scientific pipeline is not yet proven**. Current execution remains intentionally bounded to **Gate A: real-data feasibility and geometry identification for synchronized three-fisheye metric stereo**.

The downstream research architecture is frozen on paper as a latency-first, history-aware, uncertainty-driven design with typed temporal state and progressive computation. The latest design addition is a deterministic radial-range-to-point-cloud output contract. This does **not** move the current validation boundary.

Canonical references:

- `docs/FINAL_RESEARCH_ARCHITECTURE.md` — final research architecture hypothesis;
- `docs/CURRENT_PIPELINE_STATUS.md` — latest concise pipeline/status snapshot;
- `docs/POINTCLOUD_OUTPUT.md` — radial-range to point-cloud/spatial-output contract;
- `docs/VALIDATION_STATUS.md` — authoritative scientific status;
- `docs/IMPLEMENTATION_PLAN.md` — staged implementation/benchmark sequence;
- `docs/LATENCY_FIRST_ARCHITECTURE.md` — earlier latency-first design rationale retained for context.

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

These code blocks are tooling/prototypes. They do **not** by themselves establish real 3-camera metric range performance.

The point-cloud output adapter is currently a **design contract**, not an implemented/benchmarked runtime block.

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
- metric range absolute/relative error against GT;
- error by incidence angle.

Important incidence regions for the MVS-GI bootstrap include `0–60°`, `60–90°`, and `90–97.5°`. The final target 225° rig additionally requires dedicated evidence for `97.5–112.5°`; MVS-GI cannot supply that evidence.

## Post-Gate-A final design priority

```text
1. P95 latency
2. robustness / catastrophic near-far error avoidance
3. coarse metric-range accuracy + near/new-structure recall
4. fine depth accuracy
```

The canonical runtime principle is:

```text
PREDICT
-> VERIFY CHEAPLY
-> SPEND COMPUTE ONLY WHERE INFORMATION IS NEEDED
-> STOP AS SOON AS RANGE IS GOOD ENOUGH
```

The expected downstream structure combines:

- native fisheye RayLUT/solid-angle geometry;
- fast sensory ring buffer;
- typed range state carrying uncertainty, timestamp, source and status;
- relative-SE(3) temporal prediction;
- predictive innovation/surprise;
- deadline-aware active-region scheduling;
- progressive measurement complexity;
- best-pair-first evaluation across `01`, `02`, `12`;
- local deterministic DSP before learned fallback;
- explicit sensor/model uncertainty;
- multi-timescale range/spatial memory;
- optional radial-range-to-point-cloud output/spatial representation;
- fail-closed `UNKNOWN` behavior;
- bounded bootstrap/track/rebootstrap state machine.

Selected LAWGRAPH ideas are used only as architecture principles useful to depth: equation-first geometry, typed state, predictive coding, event-driven compute, progressive complexity, multi-timescale memory, learned residuals only for unresolved structure, and optional later equation/parameter compression.

NADIR does **not** become a general world model, controller, planner, CFD solver or Navier-Stokes simulator.

## Latest point-cloud output decision

A valid radial-range state maps directly to a 3-D point:

```text
P_i = O_R + rho_i * r_i
```

where `r_i` is a unit rig/output ray.

The point-cloud path sits **after belief update** and does not replace the canonical range state. It can expose:

```text
current adaptive cloud
working recent cloud
optional persistent point/surfel/voxel support
```

The current cloud may contain both propagated valid history and freshly measured corrections. Stable/far regions may remain sparse while near/new/boundary regions are denser.

Heavy cloud operations such as ICP, meshing, clustering or dense voxel fusion are not part of the default NADIR fast path.

See `docs/POINTCLOUD_OUTPUT.md`.

## Frozen downstream hypotheses

The following remain **not accepted milestones** before Gate A owner review:

- RayLUT + solid-angle runtime contract for NADIR;
- spherical DSP matcher;
- Census/Hamming local matcher;
- `lambda = B/d` search;
- Fisher/Jacobian candidate allocation;
- best-pair-first / 3-pair consensus / peeling;
- typed temporal range state;
- predictive surprise / event-triggered compute;
- progressive matcher complexity;
- persistent/multi-timescale range memory;
- adaptive active-ray/AMR-like scheduling;
- radial-range to point-cloud output adapter and persistent cloud/surfel fusion;
- learned residual/uncertainty correction;
- IMU/RTK temporal priors;
- optional symbolic/parameter compression;
- QCS8550/QNN deployment claims.

The existing dense photometric code remains `HYPOTHESIS_NOT_VALIDATED`; it should not be interpreted as the final NADIR algorithm.

## Coordinate / semantic contract

- Navigation/global state: NED when navigation is introduced later.
- UAV body/rig: FRD (`+X forward`, `+Y right`, `+Z down`).
- Each camera retains its native calibrated frame.
- `T_C_B` maps Body/Rig points into a camera frame.
- Sparse triangulation uses distinct physical camera centers; cameras are never collapsed to a single optical center.
- Fisheye RGB is not flattened/panoramically stitched before stereo.
- Final depth/range semantics remain radial range from the chosen rig reference origin.
- A valid rig-frame range state may be converted to a point by `P = O_R + rho r`.
- A world/NED point may later be formed by `P^N = R_NB P^B + p_B^N` with timestamp-consistent pose/covariance.

## Runtime contract for later stages

Current engineering targets, not measured claims:

- hard: `>= 15 FPS` and P95 capture-to-range `< 80 ms`;
- design: `>= 20 FPS` and P95 `< 60 ms`;
- stretch: `30 FPS`.

Later experiments must report P50/P95 latency, active-ray fraction, candidates per active ray, evaluated pairs per active ray, signal bands/channels, history-reuse fraction, progressive-level distribution, bootstrap vs steady-state latency, rebootstrap frequency, catastrophic-range-error rate, near/new-structure recall and `UNKNOWN`/abstention rate.

If the point-cloud adapter is enabled, report its conversion time, emitted-point count/density and persistent-fusion memory/runtime separately.

## Current validation level

- source semantics: substantially audited;
- projection/transform/triangulation mathematics: unit/synthetic tested;
- real MVS-GI sparse metric-stereo evidence: **not yet produced**;
- exact 225° real evidence: **not available**;
- matcher benchmark: **not measured**;
- typed history / predictive surprise / scheduler benefit: **not measured**;
- point-cloud adapter/persistent cloud runtime: **not measured**;
- IMU/RTK compute reduction: **not measured**;
- learned residual benefit: **not measured**;
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
8. only then begin the latency-first staged benchmarks in `docs/IMPLEMENTATION_PLAN.md`.
