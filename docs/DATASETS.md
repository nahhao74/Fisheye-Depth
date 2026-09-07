# Dataset Survey and Data Plan

## 1. Target dataset requirement

The target NADIR dataset ideally provides all of the following simultaneously:

- 3 synchronized fisheye cameras;
- approximately 225° FoV per camera;
- fixed known rig extrinsics;
- metric dense radial depth ground truth;
- enough overlap for multi-view stereo;
- temporal sequences for later IMU/RTK-conditioned depth;
- calibration and timestamps.

At the current research stage, no public dataset has been identified that satisfies the full target combination exactly.

## 2. Public datasets / projects currently prioritized

### MVS-GI / AirLab

Why it matters:

- 3 fisheye cameras;
- same-facing multi-camera topology close to NADIR;
- metric distance/depth supervision;
- geometry-informed candidate selection;
- lightweight omnidirectional stereo focus.

Important limitation:

- the public implementation uses approximately **195° FoV**, not 225°.

This means it cannot validate the target incidence-angle region from 97.5° to 112.5°.

Primary use:

- first 3-camera loader;
- geometry and matching baseline;
- sparse candidate research;
- runtime-oriented architecture development.

Reference:

- https://github.com/castacks/mvs_gi
- https://theairlab.org/gicandidates/

### OmniMVS

Why it matters:

- approximately **220° fisheye FoV**, very close to the 225° target;
- omnidirectional multi-fisheye stereo;
- dense metric depth supervision;
- useful for feature behavior in extreme FoV regions.

Limitation:

- 4-camera omnidirectional layout rather than the target 3-camera same-facing rig.

Primary use:

- pretraining/benchmarking native fisheye features;
- edge-angle analysis;
- spherical/ray-space matching validation near the target FoV.

Reference:

- OmniMVS, ICCV 2019.

### KAIST Sphere Stereo

Why it matters:

- real-time sphere sweeping stereo from multiview fisheye images;
- direct fisheye processing without relying on conventional pinhole rectification;
- strong reference for the runtime side of NADIR.

Primary use:

- classical/non-heavy baseline;
- resolving-power / matching analysis;
- latency/FPS reference.

Reference:

- https://github.com/KAIST-VCLAB/sphere-stereo

### LaFiDa

Why it matters:

- real synchronized 3-fisheye acquisition;
- LiDAR and pose information;
- useful for calibration, synchronization, triangulation, and real-world validation.

Limitation:

- smaller FoV than the NADIR target.

Primary use:

- real-world geometry validation;
- feature repeatability and triangulation experiments;
- calibration/synchronization tests.

## 3. What must not be claimed

Do not treat a model that succeeds on 195° data as validated for 225°.

A 195° lens observes a half-angle of approximately 97.5°, while a 225° lens reaches approximately 112.5°. The outer target region therefore requires dedicated data.

Likewise, warping a 195° image into a nominal 225° image does not create information that the original camera never observed.

## 4. Planned NADIR datasets

### NADIR-SYN225

Purpose: exact-target synthetic dataset before large-scale real capture.

Initial specification:

- 3 synchronized cameras;
- 225° FoV;
- exact target rig extrinsics;
- native fisheye RGB;
- dense radial depth GT;
- camera/rig pose;
- timestamps;
- optional semantic labels only if they do not interfere with the depth scope.

Start with a small geometry-debug set, roughly 100–500 frames. Scale only after projection, triangulation, and sphere-sweep tests are correct.

### NADIR-REAL225

Later real-rig dataset for:

- calibration characterization;
- real edge-quality measurement;
- temporal synchronization;
- sensor-conditioned depth validation;
- final domain-gap evaluation.

## 5. Common internal sample interface

Every dataset should be normalized to a common loader contract similar to:

```python
sample = {
    "images": [I0, I1, I2],
    "intrinsics": [...],
    "extrinsics": [...],
    "depth_gt": depth_gt,
    "timestamp": t,
    "pose": optional_pose,
    "imu": optional_imu,
    "rtk": optional_rtk,
}
```

The internal depth GT must have explicit semantics: radial range versus camera Z depth must never be mixed silently.

## 6. Evaluation bins

All final 225° experiments should report error by incidence angle, not only one global metric.

Recommended initial bins:

- 0°–60°;
- 60°–90°;
- 90°–100°;
- 100°–112.5°.

Also report range bins because stereo conditioning changes strongly with depth.

The exact acceptance thresholds remain **PROPOSED / NOT YET MEASURED** until a baseline dataset and rig geometry are established.