# NADIR Current Pipeline Status — 2026-09-12

## Scientific boundary

Current status remains:

```text
GATE_A_NOT_YET_PROVEN
```

The repository contains substantial geometry/data tooling and downstream architecture documents, but it does **not** yet demonstrate the final `3 × ~225°` pipeline on real target-rig data.

`docs/VALIDATION_STATUS.md` remains authoritative for what is scientifically proven. `docs/FINAL_RESEARCH_ARCHITECTURE.md` remains the canonical design reference. This file is a concise latest-state snapshot.

## Current objective

NADIR targets fast approximate metric radial range with confidence from three synchronized native fisheye cameras.

Priority is frozen as:

```text
1. P95 end-to-end latency
2. robustness / catastrophic near-far error avoidance
3. coarse metric-range accuracy + near/new-structure recall
4. fine depth accuracy
```

## Canonical pipeline

```text
3 synchronized native fisheyes
        |
        v
L0  Geometry / static law
    RayLUT, solid angle, extrinsics, visibility, quality
        |
        v
L1  Fast sensory buffer
    images, timestamps, IMU synchronization
        |
        +------------------------------+
        |                              |
        v                              v
L2  Typed temporal predictor      cheap current-observation summary
    previous range state          gradients/change/Census/etc.
    + relative SE(3)                   |
        |                              |
        +---------------+--------------+
                        v
L3  Surprise / uncertainty / deadline scheduler
    decide WHEN, WHERE, HOW MUCH compute to spend
        |
        +--> REUSE temporal state when evidence is sufficient
        |
        +--> CHEAP CHECK / Census
        |
        +--> DSP REFINE / spherical local signal
        |
        +--> tiny learned fallback only for hard unresolved cases
                        |
                        v
L5a Pair selection
    best physical pair first
                        |
                        v
L4  Local native-ray measurement
    depth / inverse-depth / lambda candidates
                        |
                        v
    evidence sufficient?
       | yes                     | no
       v                         v
    accept               second/third pair if needed
       |                         |
       +-----------+-------------+
                   v
L5b Pair consensus / occlusion-aware fusion
                   |
                   v
L6  Belief update / typed range state
    range + sensor uncertainty + model uncertainty + provenance
                   |
                   +--> Range-to-point output adapter
                   |    P = O_R + rho * r
                   |    -> current adaptive point cloud
                   |    -> optional working/persistent spatial support
                   |
                   v
L7  Multi-timescale memory
    sensory + working range + optional sparse spatial support
                   |
                   v
L8  Runtime assurance
    valid / UNKNOWN / rebootstrap decision
                   |
                   v
metric radial range + confidence
(+ optional adaptive point cloud)
```

## Latest point-cloud decision

The latest design decision is that radial range can be converted directly into a 3-D point:

```text
P_i = O_R + rho_i * r_i
```

with `||r_i|| = 1`.

This is an output/spatial-memory representation after the belief update, not a new depth estimator.

Important consequences:

- no pinhole back-projection is required for the common range representation;
- the current cloud can contain both propagated valid history and freshly remeasured corrections;
- adaptive point density is allowed by design;
- RGB color is optional visualization metadata;
- heavier cloud operations such as ICP/meshing are outside the default fast path;
- a future ROS 2 `sensor_msgs/PointCloud2` adapter is possible but not yet implemented/validated.

See `docs/POINTCLOUD_OUTPUT.md`.

## Current implemented/tooling blocks

Implemented/tooling-level components include:

- MVS-GI source-layout, calibration and compressed-distance adapters;
- native LinearSphere and DoubleSphere project/unproject;
- explicit MVS-GI half-pixel convention handling;
- frame-graph/extrinsic conversion;
- calibrated camera-rig physical centers/baselines;
- generalized two-ray triangulation;
- lower-hemisphere ray/visibility/observability/LUT utilities;
- metric profiling/error utilities;
- `scripts/run_gate_a_sparse.py`;
- GitHub Actions/unit-test infrastructure.

These blocks do not by themselves prove end-to-end real 3-camera metric range performance.

## Downstream hypotheses still not validated

The following remain research hypotheses until measured:

- RayLUT + solid-angle runtime architecture;
- Census/Hamming local matching;
- local spherical DSP matching;
- `lambda = B/d` search;
- Jacobian/Fisher-guided candidate allocation;
- best-pair-first / three-pair consensus;
- typed temporal range state;
- predictive surprise / event-triggered compute;
- progressive compute levels;
- adaptive active-ray scheduler;
- persistent multi-timescale memory;
- point-cloud output adapter and persistent cloud/surfel fusion;
- IMU/RTK search compression;
- tiny learned residual/uncertainty correction;
- QCS8550/QNN deployment performance;
- optional offline equation/symbolic compression.

## Current active experiment — Gate A

Gate A asks whether real/released synchronized fisheye observations with known camera models and physical baselines produce metric generalized-camera triangulation consistent with ground truth.

Required evidence includes:

```text
camera model / baseline identities
match counts
valid forward triangulation counts
closest-ray gap distribution
triangulation-angle / conditioning distribution
reprojection-error distribution
metric radial-range error vs GT
error vs incidence / range / geometry
exact matcher/filter settings
GT sampling method
```

No automatic scientific PASS threshold is frozen.

## Research sequence

```text
Gate A  real 3-camera native-fisheye metric geometry
Gate B  ORB vs Census vs spherical DSP vs tiny learned matcher
Gate C  depth vs inverse-depth vs lambda/Jacobian/Fisher
Gate D  best-pair-first + 3-camera consensus
Gate E  typed temporal state + SE(3) prediction
Gate F  predictive surprise + progressive compute
Gate G  adaptive spatial / active-ray scheduler
Gate H  IMU search compression
Gate I  RTK covariance-conditioned search
Gate J  tiny learned residual only if still useful
Gate K  QCS8550 deployment
Gate L  optional equation/parameter compression
```

The point-cloud adapter is not a separate depth-science gate. It should be implemented/verified after trustworthy radial range exists, with coordinate-frame, timestamp, uncertainty and runtime checks.

## Immediate next action

Execution remains conservative:

1. place an actual MVS-GI validation/sample payload under `/media/nahhao74/KINGSTON`;
2. inspect released semantics on one real sample;
3. run Gate A sparse geometry without optional filters first;
4. inspect raw failure distributions;
5. freeze acceptance/filter criteria only after evidence exists;
6. only then proceed to downstream matcher and temporal/scheduler experiments.
