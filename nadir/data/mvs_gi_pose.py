from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Sequence

import numpy as np

from nadir.geometry.frame_graph import load_frame_graph

from .mvs_gi import MvsGiLayoutError


def _camera_index(camera_key: str) -> int:
    match = re.fullmatch(r"cam(\d+)", camera_key)
    if match is None:
        raise ValueError(f"camera key must match 'camN': {camera_key!r}")
    return int(match.group(1))


def read_camera_image_poses(
    root: str | Path,
    *,
    camera_keys: Sequence[str] = ("cam0", "cam1", "cam2"),
    body_frame: str = "rbf",
) -> dict[str, np.ndarray]:
    """Read ``T_B_C`` for the native image frame of each MVS-GI camera.

    The official dataset sampler uses each camera's ``image_frame`` from
    ``metadata.json``. Its frame graph follows FTensor semantics: querying
    ``(f0=body_frame, f1=image_frame)`` returns the pose of the image frame with
    respect to the body/rig frame and maps image-frame points into body-frame
    coordinates.

    NADIR's :class:`RigCamera` stores the inverse convention ``T_C_B``; callers
    must invert these matrices explicitly when constructing a rig.
    """

    root = Path(root)
    metadata_path = root / "metadata.json"
    if not metadata_path.is_file():
        raise MvsGiLayoutError(f"required file is missing: {metadata_path}")
    with metadata_path.open("r", encoding="utf-8") as f:
        metadata = json.load(f)
    if not isinstance(metadata, dict) or not isinstance(metadata.get("cams"), list):
        raise MvsGiLayoutError("metadata.json must contain a cams list")
    cameras = metadata["cams"]

    graph_path = root / "frame_graph.json"
    if not graph_path.is_file():
        raise MvsGiLayoutError(f"required file is missing: {graph_path}")
    graph = load_frame_graph(graph_path)

    poses: dict[str, np.ndarray] = {}
    for camera_key in camera_keys:
        index = _camera_index(camera_key)
        if index >= len(cameras):
            raise MvsGiLayoutError(
                f"metadata contains {len(cameras)} cameras but {camera_key!r} was requested"
            )
        camera = cameras[index]
        if not isinstance(camera, dict):
            raise MvsGiLayoutError(f"metadata camera {index} must be an object")
        image_frame = camera.get("image_frame")
        if not isinstance(image_frame, str) or not image_frame:
            raise MvsGiLayoutError(
                f"metadata camera {index} lacks a non-empty image_frame"
            )
        poses[camera_key] = graph.query_transform(body_frame, image_frame)

    return poses
