# NADIR Research Method and Anti-Bias Rules

## 1. Purpose

NADIR must not promote an idea because it sounds plausible or because it was suggested by either the project owner or the assistant.

Every significant design claim should be treated as falsifiable.

## 2. Evidence states

Each proposed mechanism should be assigned one of these states:

- **HYPOTHESIS** — plausible but unproven;
- **GEOMETRY-SUPPORTED** — supported by derivation/conditioning analysis;
- **LITERATURE-SUPPORTED** — supported by relevant published work;
- **RIG-MEASURED** — measured on the actual or exact-target rig/data;
- **ACCEPTED** — passes scientific and runtime acceptance gates.

Do not silently jump from HYPOTHESIS to ACCEPTED.

## 3. Required review template

For every nontrivial algorithmic proposal, answer:

1. **Claim** — what improvement is expected?
2. **Mechanism** — why should it work mathematically/physically?
3. **Counterexample** — when could it fail?
4. **Compute cost** — what latency/memory/deployment cost does it add?
5. **Baseline** — what simpler method must it beat?
6. **Minimal falsification experiment** — what is the smallest experiment that could show it is not useful?
7. **Verdict** — TRY / DEFER / REJECT / ACCEPT.

## 4. Current examples

### Claim: image quality always decreases toward the fisheye edge

Status: **HYPOTHESIS**.

Reason:

- optical quality may degrade near the edge on a real lens;
- however projection sampling itself does not imply a universal monotonic loss of angular information;
- actual MTF, calibration residual, vignetting, blur, and correspondence repeatability must be measured.

Required experiment:

- measure quality versus incidence angle and azimuth;
- compare visual quality and stereo matching repeatability;
- only then evaluate radial/angle weighting.

### Claim: piecewise edge weighting improves depth

Status: **HYPOTHESIS**.

Potential benefit:

- very low runtime cost;
- may reduce contribution from measured low-quality angular bands.

Failure mode:

- if quality is not monotonic with radius, a fixed radial rule may suppress good evidence.

Verdict: TRY only after NADIR-CQ produces evidence.

### Claim: view peeling improves 3-camera matching

Status: **HYPOTHESIS**.

Potential benefit:

- reject a genuinely corrupted/occluded observation.

Failure modes:

- disagreement may come from occlusion geometry, repeated texture, dynamic objects, or a valid viewpoint change rather than a bad camera;
- with only three cameras, removing one view can significantly weaken triangulation.

Verdict: DEFER until visibility/quality evidence exists.

### Claim: bitmasks improve depth accuracy

Status: **ENGINEERING REPRESENTATION**, not an algorithmic contribution.

Bitmasks compactly encode visibility/usable-view state but do not inherently improve geometry or matching.

### Claim: NED should be used everywhere

Status: **REJECT AS STATED**.

Correct formulation:

- NED is appropriate for the navigation/state layer;
- spatial depth matching is naturally performed in rig/body coordinates;
- the depth core should consume relative SE(3), not absolute North/East position unless specifically required.

### Claim: IMU improves depth

Status: **GEOMETRY-SUPPORTED, EXPERIMENT REQUIRED**.

Strongest expected mechanism:

- short-term rotation/de-rotation;
- temporal depth propagation;
- candidate narrowing.

Caution:

- accelerometer-only translation integration drifts rapidly.

### Claim: RTK always improves depth

Status: **REJECT AS STATED**.

RTK is useful only when timing, covariance, update rate, and motion provide informative translation constraints. FIX/FLOAT/LOST must be treated differently.

## 5. Runtime anti-bias rule

A more accurate model is not automatically a better NADIR model.

Every accepted change must report:

- depth metrics;
- latency P50/P95;
- FPS;
- peak memory;
- target backend execution/fallback state.

If an accuracy improvement pushes runtime below the hard real-time gate, the change is rejected or deferred for redesign.

## 6. Ablation discipline

Add one causal mechanism at a time whenever possible.

Preferred progression:

```text
camera-only geometry baseline
    ↓
lightweight learned MVS
    ↓
geometry-informed candidates
    ↓
quality-aware view handling
    ↓
IMU temporal prior
    ↓
RTK-conditioned translation prior
```

Required sensor ablation later:

- camera only;
- camera + IMU;
- camera + IMU + RTK.

This prevents an improvement from being attributed to the wrong subsystem.

## 7. Reporting rule

When evidence is incomplete, use explicit wording such as:

- `PROPOSED_NOT_MEASURED`;
- `SUPPORTED_BY_GEOMETRY_ONLY`;
- `PUBLIC_DATASET_ONLY`;
- `NOT_VALIDATED_AT_225_DEG`;
- `TARGET_DEVICE_NOT_PROFILED`.

Do not silently turn design targets into measured results.