# NADIR Architecture Specification

## 1. Problem definition

NADIR estimates a dense metric radial depth field from a synchronized three-camera fisheye rig mounted on a UAV.

Inputs at time `t`:

- `I_t^0, I_t^1, I_t^2`: native fisheye RGB images;
- fixed camera intrinsics/extrinsics;
- IMU measurements/state;
- GNSS/RTK position/velocity and covariance when available;
- previous depth `D_{t-1}` when temporal inference is enabled.

Primary output:

`D_t(i) = rho_i`, where each output cell corresponds to a unit ray `r_i` in the rig/body frame and

`P_i = O_R + rho_i r_i`.

Depth semantics are therefore **radial range**, not per-camera optical-axis Z depth.

## 2. Coordinate frames

Freeze the following convention:

- global/navigation frame: **NED** (`X=North, Y=East, Z=Down`);
- vehicle/rig frame: **FRD/body** (`X=Forward, Y=Right, Z=Down`);
- camera frames: native calibrated camera coordinates;
- depth matching: performed in rig/body coordinates;
- temporal navigation state: represented in NED and converted to relative SE(3) before entering the depth pipeline.

Raw IMU remains in body coordinates. RTK/GNSS is converted to a local NED frame. The navigation layer estimates `T_NB(t)`. The depth layer consumes relative motion such as

`T_Bt_Bt-1 = inv(T_NB(t)) * T_NB(t-1)`.

## 3. Spatial stereo core

The three RGB images must not be blended into a panorama before matching. Their view identity and parallax are preserved.

For each output ray `r_i` and radial candidate `rho_k`:

1. construct a 3D hypothesis
   `P_ik = O_R + rho_k r_i`;
2. transform into camera `c`;
3. project with the native fisheye model
   `p_cik = Pi_c(T_CcR P_ik)`;
4. sample learned/native features `f_cik`;
5. compare features from valid camera pairs;
6. aggregate a compact cost `C(i,k)`;
7. select/refine the most likely `rho`.

For a probability distribution over candidates:

`p_ik = softmax(-C_ik)`

and an expectation decoder may use

`rho_hat_i = sum_k p_ik rho_k`.

## 4. Fisheye camera models

Because the target FoV is approximately 225°, rays beyond 90° incidence are expected. Candidate models to validate are:

- Double Sphere;
- Kannala-Brandt / equidistant family;
- EUCM.

Selection is empirical, based on reprojection error versus incidence angle, especially in the outer region approaching the 112.5° half-angle.

The common API is:

```python
class CameraModel:
    def project(self, xyz): ...
    def unproject(self, uv): ...
```

No global pinhole undistortion is required for the depth core.

## 5. Visibility and observability

For each output ray, precompute:

- visible cameras;
- available camera pairs;
- effective baseline;
- triangulation angle / conditioning;
- lens-incidence region;
- validity mask.

A compact 3-bit visibility mask is sufficient for three cameras. Bitmasks are an engineering representation, not an accuracy contribution by themselves.

Stereo observability is a geometric condition. Overlap alone is insufficient if the effective baseline or triangulation angle is weak.

## 6. Camera-quality characterization

The claim that fisheye information necessarily decreases monotonically toward the edge is **not accepted as a prior fact**.

NADIR-CQ measures, versus angular position:

- calibration residual;
- local sharpness/MTF proxy;
- contrast/SNR;
- vignetting/exposure clipping;
- feature repeatability;
- stereo correspondence quality.

Only measured evidence may justify edge weighting.

A later quality-aware pair weight may have the form

`W_ab = Q_a Q_b G_ab`,

where `Q` is measured visual quality and `G` is geometric quality. Piecewise radial weighting or view peeling remain hypotheses until ablation validates them.

## 7. IMU and RTK/GNSS conditioning

IMU/RTK are permitted to participate directly in depth generation.

The intended role is not to concatenate arbitrary sensor vectors into a heavy neural network. Instead they constrain geometry and the candidate search space.

Given previous depth point

`P_{t-1} = rho_{t-1} r_{t-1}`

and relative pose from the navigation layer, propagate the point into the current rig frame and obtain

`rho_t^prior = ||P_t^prior||`.

This prior can narrow the candidate interval around the predicted range.

IMU is expected to be strongest for short-term rotation/de-rotation. Accelerometer-only translation integration is not trusted without an estimator because of drift.

RTK is confidence-gated:

- FIX: strong metric translation prior;
- FLOAT: broaden the search according to covariance;
- LOST/unreliable: do not constrain stereo with RTK.

## 8. Runtime-oriented model design

Initial learned baseline should prefer:

- one shared encoder for all cameras;
- MobileNet/MBConv/depthwise-separable style blocks;
- low-channel feature maps;
- small candidate count (`K≈8–16` initially);
- pairwise/groupwise correlation;
- compact 2D regularization rather than a large 3D CNN cost volume;
- fixed shapes and precomputed rig geometry;
- QNN/INT8-friendly operators.

The rig is fixed, so projection/sampling tables for fixed output rays and global depth candidates should be precomputed offline whenever possible.

## 9. Acceptance philosophy

An architecture change is accepted only when it has measured benefit relative to a baseline in both scientific and runtime terms.

Required evidence includes:

- depth error change;
- failure modes by angular/range bin;
- latency P50/P95;
- throughput;
- peak memory;
- deployment backend coverage.

Accuracy-only improvement is insufficient if runtime becomes unusable.