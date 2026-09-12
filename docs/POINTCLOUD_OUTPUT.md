# NADIR Point-Cloud Output Contract

## Status

This document defines how a validated NADIR radial-range state can be exposed as 3-D points or a lightweight spatial representation.

It does **not** change the scientific boundary:

```text
GATE_A_NOT_YET_PROVEN
```

The deterministic range-to-point relation is part of the geometry contract, but a production point-cloud adapter, persistent fusion policy and runtime cost have not yet been implemented or measured. Treat the output path below as a downstream design contract until validated.

## 1. Core conversion

NADIR's canonical output is radial range from a selected rig reference origin `O_R` along a unit ray `r_i`:

```text
P_i = O_R + rho_i * r_i
||r_i|| = 1
```

If the rig reference origin is the coordinate origin:

```text
P_i = rho_i * r_i
```

Therefore the current radial-range representation can be converted directly into a 3-D point without pinhole back-projection or image flattening.

## 2. Coordinate frames

### Rig/body cloud

If `r_i` and `O_R` are represented in Body/Rig FRD coordinates, then:

```text
P_i^B = O_R^B + rho_i * r_i^B
```

The point-cloud convention is then:

```text
+X Forward
+Y Right
+Z Down
```

### World/NED cloud

Given navigation pose `(R_NB, p_B^N)`:

```text
P_i^N = R_NB * P_i^B + p_B^N
```

This allows valid current-frame points to be accumulated in a navigation/world frame when required.

The world-cloud path must use timestamp-consistent navigation state and must not hide pose uncertainty.

## 3. Position in the NADIR pipeline

Point-cloud conversion is an **output/spatial-memory adapter after the belief update**, not a new depth-estimation algorithm.

```text
L6  BELIEF UPDATE / TYPED RANGE STATE
        |
        +--> range + uncertainty + status + provenance
        |
        v
RANGE-TO-POINT ADAPTER
        |
        +--> current-frame adaptive point cloud
        |
        +--> working recent cloud
        |
        +--> optional persistent point/surfel/voxel support
        |
        v
L7  MULTI-TIMESCALE MEMORY
```

A region reused from temporal prediction can still contribute a current 3-D point if its propagated state remains valid. The cloud is therefore not limited to freshly recomputed rays.

Conceptually:

```text
current valid cloud
    = propagated valid history
    + freshly measured corrections
```

## 4. Adaptive / non-uniform point cloud

NADIR does not require the same point density everywhere.

The scheduler may produce:

```text
stable / far / smooth region  -> sparse points or reused points
near / new / boundary region  -> denser points
uncertain region               -> active remeasurement or UNKNOWN
```

This yields an adaptive non-uniform cloud by design. A dense fixed-grid point cloud every frame is not a requirement.

## 5. Point attributes

A useful point output should preserve more than XYZ where practical:

```text
PointState {
    x
    y
    z
    sigma_range
    confidence
    timestamp
    age
    source_pair_or_cameras
    status
    observation_count
    static_or_dynamic_state
}
```

Optional visualization fields may include RGB sampled from the best supported native camera, but color is not part of the depth scientific contract.

## 6. Uncertainty propagation

If ray direction is treated as fixed and only radial uncertainty is considered:

```text
Sigma_P ~= sigma_rho^2 * r * r^T
```

This means the dominant uncertainty lies along the viewing ray.

For extreme fisheye regions, calibration/angular uncertainty may be significant and should eventually contribute an additional covariance term. The exact 3-D covariance propagation is a later validation item.

## 7. Current cloud versus persistent spatial support

Three output levels are distinguished:

### A. Current-frame adaptive cloud

Generated from current valid typed range states.

Use for:

- visualization;
- local geometry consumers;
- current-frame obstacle/range interfaces.

### B. Working recent cloud

Short-lived accumulation over recent frames using relative pose and uncertainty.

Use for:

- temporal support;
- coverage continuity;
- local consistency checks.

### C. Persistent spatial support

Optional longer-lived representation:

- sparse points;
- surfels;
- lightweight voxel/hash structure.

This exists only to support efficient range inference. NADIR does not become a full mapping/SLAM product by definition.

## 8. Surfels as a possible compressed representation

For stable surfaces, a surfel can represent more structure per element than independent points:

```text
Surfel {
    position
    normal
    radius
    uncertainty
    timestamp / age
}
```

This may compress stable floor/wall regions while retaining denser point/ray coverage near boundaries and newly observed objects.

Whether surfels beat simple sparse points must be measured; this is not yet an accepted runtime choice.

## 9. Runtime cost

The direct conversion

```text
P = O_R + rho * r
```

is `O(N)` and consists mainly of per-point multiply/add operations. It is expected to be much cheaper than stereo matching, whose dominant work scales with active rays, search candidates, camera pairs and signal channels/bands.

However, heavier point-cloud operations can become expensive:

- nearest-neighbor search;
- ICP;
- normal estimation;
- voxel fusion;
- clustering;
- meshing.

These operations are not part of the default NADIR fast depth path and must be separately budgeted if introduced.

## 10. ROS-facing candidate

If a ROS 2 interface is needed later, a natural candidate is `sensor_msgs/PointCloud2` with fields such as:

```text
x
y
z
confidence
sigma_range
age
status
```

The ROS interface is a downstream integration choice, not a validated NADIR scientific result.

## 11. Validation requirements

Before point-cloud output is promoted as an accepted runtime block, verify at least:

- range-to-XYZ coordinate-frame correctness;
- rig/body and NED transform consistency;
- timestamp alignment with navigation pose;
- handling of `UNKNOWN` / invalid range states;
- uncertainty propagation sanity;
- current-cloud coverage when most rays are reused rather than freshly measured;
- conversion latency and memory cost;
- persistent fusion failure modes under pose error and dynamic objects.

## 12. Current decision

Point-cloud conversion is compatible with the existing NADIR representation and does not require changing the depth core.

The canonical relation is:

```text
radial range + unit ray
        ->
3-D point
```

The depth/range state remains the primary inference representation. Point clouds, surfels or voxel/hash structures are downstream output/memory representations chosen according to latency and downstream requirements.
