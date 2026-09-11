# NADIR Validation Status

## Current task boundary

The active task is **not** to build or claim the final NADIR depth pipeline.

The active task is:

> **Gate A — real-data feasibility and geometry identification for synchronized three-fisheye metric stereo.**

The scientific question is whether known camera models + known camera-center baselines + real multi-view correspondences can produce metric 3-D/radial range that is consistent with ground truth, and how that consistency changes with range, viewing angle and triangulation conditioning.

Until Gate A is reviewed and accepted, downstream adaptive/DSP/temporal/learned architecture is not promoted.

`FINAL_RESEARCH_ARCHITECTURE.md` is the canonical design document. This file remains authoritative for **what has actually been proven**.

## Status vocabulary

- `SOURCE_VERIFIED`: supported by released source code/data documentation, but not yet measured by NADIR.
- `MATH_UNIT_VERIFIED`: equations/code pass controlled synthetic or unit tests only.
- `REAL_MEASURED`: measured on downloaded real/released payloads.
- `ACCEPTED`: owner-reviewed evidence satisfies a frozen acceptance contract.
- `HYPOTHESIS_NOT_VALIDATED`: plausible candidate retained for later falsification; not part of an accepted scientific pipeline.

## Current status by block

| Block | Status | Meaning |
| --- | --- | --- |
| MVS-GI file/metadata semantics | `SOURCE_VERIFIED` | Loader follows released layout/source semantics. |
| MVS-GI compressed float distance decoding | `SOURCE_VERIFIED` + `MATH_UNIT_VERIFIED` | Byte reinterpretation and tests exist; real payload still needs execution in the target workflow. |
| MVS-GI raw distance meaning | `SOURCE_VERIFIED` | Released `RayMaker.make_rays_from_grid_distance` multiplies unit native-camera rays by the provided distance values, so raw distance is treated as radial range along the reference ray, not camera-Z depth. |
| LinearSphere/DoubleSphere projection | `MATH_UNIT_VERIFIED` | Round-trip and >90° geometry tests exist. This does not prove real-lens calibration quality. |
| Frame graph / extrinsics | `MATH_UNIT_VERIFIED` | Transform convention is implemented and tested; real-data residuals are not yet characterized. |
| Generalized two-ray triangulation | `MATH_UNIT_VERIFIED` | Synthetic intersections/degenerate rays are tested. |
| Sparse ORB matching | `HYPOTHESIS_NOT_VALIDATED` | Gate A falsification baseline only. |
| Dense photometric sphere sweep | `HYPOTHESIS_NOT_VALIDATED` | Frozen as a later candidate; not an accepted NADIR depth algorithm. |
| Native RayLUT + solid-angle representation | `HYPOTHESIS_NOT_VALIDATED` | Downstream design candidate; exact NADIR contract/performance not yet implemented/measured. |
| Census/Hamming local matcher | `HYPOTHESIS_NOT_VALIDATED` | Candidate low-cost DSP matcher after Gate A. |
| Local spherical harmonic/Fourier-Bessel matcher | `HYPOTHESIS_NOT_VALIDATED` | Reviewed external/internal idea; not yet reproduced as NADIR evidence. |
| `lambda = B/d` pairwise search | `HYPOTHESIS_NOT_VALIDATED` | Candidate search coordinate to compare with direct depth/inverse depth. |
| Jacobian/Fisher-guided candidate allocation | `HYPOTHESIS_NOT_VALIDATED` | Candidate mechanism for reducing search; no NADIR runtime/accuracy evidence yet. |
| Best-pair-first / 3-pair consensus / peeling | `HYPOTHESIS_NOT_VALIDATED` | Candidate three-camera compute/fusion strategy; occlusion failure modes require testing. |
| Typed range state `(range, uncertainty, time, source, status)` | `HYPOTHESIS_NOT_VALIDATED` | LAWGRAPH-inspired state contract for temporal scheduling; not implemented/validated. |
| Predictive coding / normalized surprise | `HYPOTHESIS_NOT_VALIDATED` | Candidate trigger using observed-vs-predicted evidence; exact residual/statistic not frozen. |
| Progressive compute levels | `HYPOTHESIS_NOT_VALIDATED` | Candidate hierarchy: reuse -> cheap check -> DSP refine -> learned fallback. |
| Persistent temporal range/uncertainty memory | `HYPOTHESIS_NOT_VALIDATED` | Candidate steady-state compute reduction mechanism. |
| Multi-timescale sensory/working/spatial memory | `HYPOTHESIS_NOT_VALIDATED` | Candidate bounded-memory organization; no runtime evidence yet. |
| Adaptive active-ray / AMR-like scheduler | `HYPOTHESIS_NOT_VALIDATED` | Numerical compute-allocation analogy only; no Navier-Stokes/CFD solver is proposed. |
| Learned residual/uncertainty correction | `HYPOTHESIS_NOT_VALIDATED` | Candidate role for a small network after deterministic structure; not an accepted direct-depth model. |
| Offline parameter/symbolic compression | `HYPOTHESIS_NOT_VALIDATED` | Late optional idea to replace learned quality/scheduler residuals with compact validated equations; not current scope. |
| Learned CNN/groupwise MVS | `HYPOTHESIS_NOT_VALIDATED` | Candidate only if deterministic baselines are insufficient on the latency/robustness Pareto frontier. |
| Exact 225° target rig/data | not measured | MVS-GI ~195° cannot validate the 97.5°–112.5° annulus. |
| IMU/RTK temporal priors | not implemented/validated | Out of current Gate A scope; later goal is search compression/de-rotation, not arbitrary sensor concatenation. |
| QCS8550/QNN deployment | not implemented/validated | No onboard FPS/latency claim is allowed yet. |

## Gate A experiment

Use one real MVS-GI sample first, then extend only after the first run is understood.

For each camera pair:

1. detect sparse features on the native fisheye image;
2. match descriptors without panorama stitching;
3. convert matched pixels to native camera rays;
4. transform rays and camera centers into the common rig/body frame;
5. triangulate the closest point between the two generalized-camera rays;
6. record signed ray distances, closest-ray gap, triangulation angle/conditioning and reprojection error;
7. project the triangulated point into the released rig-reference distance image;
8. compare predicted radial range against released metric ground truth;
9. stratify error by source incidence angle.

The initial harness is `scripts/run_gate_a_sparse.py`.

No scientific acceptance threshold is hard-coded. Optional filters such as minimum triangulation angle, maximum closest-ray gap or maximum reprojection error must be supplied explicitly and reported as experiment settings.

### Ground-truth sampling note

The released MVS-GI training loader resamples distance with its `INTER_BLENDED` path and a dedicated blend function. The current Gate A harness samples the **raw** reference distance image with NADIR's simple bilinear sampler when evaluating a projected sparse point. Therefore:

- radial-distance semantics are source-verified;
- the exact sub-pixel interpolation implementation is **not yet source-equivalent**;
- depth errors near discontinuities must not be over-interpreted until nearest/bilinear/source-blended GT sampling is compared.

This interpolation difference is an explicit validation item, not something to hide inside the acceptance result.

## Required Gate A evidence

A reviewable Gate A report should contain at least:

- camera model identities and physical baseline matrix;
- keypoint/match counts by pair;
- forward/numerically valid triangulation counts;
- closest-ray gap distribution;
- triangulation-angle distribution;
- reprojection-error distribution;
- metric range absolute/relative error against GT;
- error stratified by incidence bins, especially `0–60°`, `60–90°`, and `>90°` for the MVS-GI bootstrap;
- exact matcher/filter parameters;
- clear separation between source-derived parameters and experiment-chosen parameters;
- GT sampling method used for the comparison.

Gate A remains `NOT_YET_PROVEN` until real payload results exist and the owner reviews a frozen acceptance criterion. The harness must not declare PASS on its own.

## Downstream priority if Gate A is supported

```text
1. P95 latency
2. robustness / catastrophic near-far error avoidance
3. coarse metric-range accuracy + near/new-structure recall
4. fine depth accuracy
```

The canonical downstream principle is:

```text
predict
-> verify cheaply
-> spend compute only where information is needed
-> stop when range is good enough
```

Candidate downstream work must be evaluated as a falsification sequence, not promoted from design discussion alone.

## Explicitly out of scope until Gate A review

Do not promote or optimize as accepted pipeline blocks:

- dense photometric sphere sweep as the final method;
- Census/Hamming or spherical DSP matchers;
- `lambda = B/d` search or Fisher/Jacobian scheduling;
- best-pair-first / 3-pair consensus / peeling;
- typed temporal state and predictive surprise;
- progressive matcher complexity;
- persistent/multi-timescale range memory;
- adaptive active-ray/event-triggered scheduling;
- learned residual/quality/uncertainty modules;
- CNN/ResNet/attention feature encoders;
- IMU/RTK temporal fusion;
- recurrent/temporal neural models;
- symbolic/SINDy-style runtime-law compression;
- final 225° claims;
- QCS8550/QNN performance claims.

These may remain documented as future hypotheses, but they are not current implementation milestones.

## Runtime policy for future experiments

Once Gate A permits downstream execution, every experiment must report at least:

```text
P50 total latency
P95 total latency
FPS
peak memory
active-ray fraction
mean candidates per active ray
mean evaluated camera pairs per active ray
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

Fine MAE/RMSE/AbsRel may still be diagnostic metrics, but they do not override latency-first decisions.

## Data/storage note

Large downloaded datasets, runtime outputs and experiment artifacts should be kept under `/media/nahhao74/KINGSTON` on the user's Ubuntu machine rather than under `/home`.
