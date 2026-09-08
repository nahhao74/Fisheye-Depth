# NADIR Validation Status

## Current task boundary

The active task is **not** to build or claim the final NADIR depth pipeline.

The active task is:

> **Gate A — real-data feasibility and geometry identification for synchronized three-fisheye metric stereo.**

The scientific question is whether known camera models + known camera-center baselines + real multi-view correspondences can produce metric 3-D/radial depth that is consistent with ground truth, and how that consistency changes with range, viewing angle and triangulation conditioning.

Until Gate A is reviewed and accepted, downstream dense/learned architecture is not promoted.

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
| LinearSphere/DoubleSphere projection | `MATH_UNIT_VERIFIED` | Round-trip and >90° geometry tests exist. This does not prove real-lens calibration quality. |
| Frame graph / extrinsics | `MATH_UNIT_VERIFIED` | Transform convention is implemented and tested; real-data residuals are not yet characterized. |
| Generalized two-ray triangulation | `MATH_UNIT_VERIFIED` | Synthetic intersections/degenerate rays are tested. |
| Sparse ORB matching | `HYPOTHESIS_NOT_VALIDATED` | Gate A falsification baseline only. |
| Dense photometric sphere sweep | `HYPOTHESIS_NOT_VALIDATED` | Frozen as a later candidate; not an accepted NADIR depth algorithm. |
| K=4/8/16/32 candidate selection | `HYPOTHESIS_NOT_VALIDATED` | Do not optimize until Gate A supports metric stereo feasibility. |
| Learned CNN/groupwise MVS | `HYPOTHESIS_NOT_VALIDATED` | Out of current task scope. |
| Exact 225° target rig/data | not measured | MVS-GI ~195° cannot validate the 97.5°–112.5° annulus. |
| IMU/RTK temporal priors | not implemented/validated | Out of current Gate A scope. |
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

## Required Gate A evidence

A reviewable Gate A report should contain at least:

- camera model identities and physical baseline matrix;
- keypoint/match counts by pair;
- forward/numerically valid triangulation counts;
- closest-ray gap distribution;
- triangulation-angle distribution;
- reprojection-error distribution;
- metric depth absolute/relative error against GT;
- error stratified by incidence bins, especially `0–60°`, `60–90°`, and `>90°` for the MVS-GI bootstrap;
- exact matcher/filter parameters;
- clear separation between source-derived parameters and experiment-chosen parameters.

Gate A remains `NOT_YET_PROVEN` until real payload results exist and the owner reviews a frozen acceptance criterion. The harness must not declare PASS on its own.

## Explicitly out of scope until Gate A review

Do not promote or optimize:

- dense photometric sphere sweep as the final method;
- CNN/ResNet/attention feature encoders;
- geometry-informed learned candidate selection;
- learned camera-quality weighting;
- IMU/RTK temporal fusion;
- recurrent/temporal neural models;
- final 225° claims;
- QCS8550/QNN performance claims.

These may remain documented as future hypotheses, but they are not current implementation milestones.

## Data/storage note

Large downloaded datasets, runtime outputs and experiment artifacts should be kept under `/media/nahhao74/KINGSTON` on the user's Ubuntu machine rather than under `/home`.
