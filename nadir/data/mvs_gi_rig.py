from __future__ import annotations

from pathlib import Path
from typing import Sequence

import numpy as np

from nadir.geometry import CameraRig, DoubleSphereCamera, LinearSphereCamera, RigCamera
from nadir.geometry.camera_model import NativeCameraModel

from .mvs_gi import MvsGiLayoutError, read_manifest_summary
from .mvs_gi_pose import read_camera_image_poses

MVS_GI_PIXEL_CENTER_OFFSET = 0.5


def _shape_hw(spec: dict) -> tuple[int, int]:
    shape = spec.get("shape_struct")
    if not isinstance(shape, dict):
        raise MvsGiLayoutError("camera model spec must contain shape_struct object")
    h = shape.get("H")
    w = shape.get("W")
    if not isinstance(h, int) or not isinstance(w, int) or h <= 0 or w <= 0:
        raise MvsGiLayoutError("shape_struct must contain positive integer H and W")
    return h, w


def camera_model_from_mvs_gi_spec(spec: dict) -> NativeCameraModel:
    """Construct a native NADIR camera model from one MVS-GI manifest spec.

    The released ``mvs_utils`` camera grid is generated with pixel centers at
    ``n + 0.5``. NADIR records that source convention explicitly and converts to
    array-index coordinates only when building a sampling LUT.
    """

    if not isinstance(spec, dict):
        raise MvsGiLayoutError("camera model spec must be an object")
    model_type = spec.get("type")
    if not isinstance(model_type, str):
        raise MvsGiLayoutError("camera model spec lacks string type")

    h, w = _shape_hw(spec)

    if model_type == "LinearSphere":
        fov = spec.get("fov_degree")
        if not isinstance(fov, (int, float)):
            raise MvsGiLayoutError("LinearSphere spec lacks numeric fov_degree")
        return LinearSphereCamera(
            fov_degree=float(fov),
            width=w,
            height=h,
            pixel_center_offset=MVS_GI_PIXEL_CENTER_OFFSET,
        )

    if model_type == "DoubleSphere":
        required = ("xi", "alpha", "fx", "fy", "cx", "cy")
        missing = [key for key in required if not isinstance(spec.get(key), (int, float))]
        if missing:
            raise MvsGiLayoutError(
                f"DoubleSphere spec lacks numeric field(s): {sorted(missing)}"
            )
        return DoubleSphereCamera(
            xi=float(spec["xi"]),
            alpha=float(spec["alpha"]),
            fx=float(spec["fx"]),
            fy=float(spec["fy"]),
            cx=float(spec["cx"]),
            cy=float(spec["cy"]),
            width=w,
            height=h,
            pixel_center_offset=MVS_GI_PIXEL_CENTER_OFFSET,
        )

    raise MvsGiLayoutError(
        f"unsupported native MVS-GI camera model {model_type!r}; "
        "do not substitute an approximate projection model"
    )


def _invert_rigid(T_A_B: np.ndarray) -> np.ndarray:
    T = np.asarray(T_A_B, dtype=np.float64)
    if T.shape != (4, 4):
        raise ValueError("rigid transform must be 4x4")
    R = T[:3, :3]
    t = T[:3, 3]
    if not np.allclose(R @ R.T, np.eye(3), atol=1e-6):
        raise ValueError("rigid transform rotation must be orthonormal")
    out = np.eye(4, dtype=np.float64)
    out[:3, :3] = R.T
    out[:3, 3] = -(R.T @ t)
    return out


def build_mvs_gi_rig(
    root: str | Path,
    *,
    camera_keys: Sequence[str] = ("cam0", "cam1", "cam2"),
    body_frame: str = "rbf",
) -> CameraRig:
    """Build a calibrated NADIR rig directly from released MVS-GI metadata."""

    if len(camera_keys) != 3:
        raise ValueError("current NADIR MVS-GI baseline requires exactly 3 cameras")

    root = Path(root)
    summary = read_manifest_summary(root / "manifest.json")
    poses_B_C = read_camera_image_poses(
        root,
        camera_keys=camera_keys,
        body_frame=body_frame,
    )

    cameras: list[RigCamera] = []
    for camera_key in camera_keys:
        model_key = summary.camera_to_model_key.get(camera_key)
        if model_key is None:
            raise MvsGiLayoutError(
                f"manifest lacks native camera-model binding for {camera_key!r}"
            )
        model = camera_model_from_mvs_gi_spec(summary.camera_model_specs[model_key])
        T_B_C = poses_B_C[camera_key]
        cameras.append(
            RigCamera(
                name=camera_key,
                model=model,
                T_C_B=_invert_rigid(T_B_C),
            )
        )

    return CameraRig(cameras=tuple(cameras))
