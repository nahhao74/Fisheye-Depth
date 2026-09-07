from __future__ import annotations

import json
from collections import deque
from dataclasses import dataclass
from pathlib import Path

import numpy as np


def _rotation_from_quaternion_xyzw(data: dict) -> np.ndarray:
    x = float(data["x"])
    y = float(data["y"])
    z = float(data["z"])
    w = float(data["w"])
    norm = np.sqrt(x * x + y * y + z * z + w * w)
    if not np.isfinite(norm) or norm <= 0.0:
        raise ValueError("quaternion must have finite non-zero norm")
    x, y, z, w = x / norm, y / norm, z / norm, w / norm
    return np.array(
        [
            [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
            [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
            [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
        ],
        dtype=np.float64,
    )


def _parse_orientation(obj: dict) -> np.ndarray:
    kind = obj.get("type")
    if kind == "rotation_matrix":
        R = np.asarray(obj.get("data"), dtype=np.float64).reshape(3, 3)
    elif kind == "quaternion":
        data = obj.get("data")
        if not isinstance(data, dict):
            raise ValueError("quaternion orientation data must be an object")
        R = _rotation_from_quaternion_xyzw(data)
    else:
        raise ValueError(f"unsupported orientation type: {kind!r}")

    if not np.all(np.isfinite(R)):
        raise ValueError("rotation contains non-finite values")
    if not np.allclose(R.T @ R, np.eye(3), atol=1e-5) or not np.isclose(
        np.linalg.det(R), 1.0, atol=1e-5
    ):
        raise ValueError("orientation is not a valid SO(3) rotation")
    return R


def _parse_pose(obj: dict) -> np.ndarray:
    position = np.asarray(obj.get("position"), dtype=np.float64)
    if position.shape != (3,):
        raise ValueError("pose position must contain exactly three values")
    orientation = obj.get("orientation")
    if not isinstance(orientation, dict):
        raise ValueError("pose orientation must be an object")
    R = _parse_orientation(orientation)
    T = np.eye(4, dtype=np.float64)
    T[:3, :3] = R
    T[:3, 3] = position
    return T


@dataclass(frozen=True)
class FrameTransformGraph:
    """Minimal NumPy frame graph with the same transform direction as FTensor.

    ``query_transform(f0, f1)`` returns ``T_f0_f1``: the pose of frame ``f1``
    with respect to frame ``f0``, measured in ``f0``. Therefore a point written
    in ``f1`` is mapped to ``f0`` by ``p_f0 = T_f0_f1 @ p_f1``.
    """

    frames: frozenset[str]
    edges: dict[str, tuple[tuple[str, np.ndarray], ...]]

    def query_transform(self, f0: str, f1: str) -> np.ndarray:
        if f0 not in self.frames:
            raise KeyError(f"unknown target/reference frame: {f0}")
        if f1 not in self.frames:
            raise KeyError(f"unknown source/target frame: {f1}")
        if f0 == f1:
            return np.eye(4, dtype=np.float64)

        # Queue entries carry T_current_f1, mapping original f1 coordinates into current.
        queue = deque([(f1, np.eye(4, dtype=np.float64))])
        visited = {f1}
        while queue:
            current, T_current_f1 = queue.popleft()
            for neighbor, T_neighbor_current in self.edges.get(current, ()):
                if neighbor in visited:
                    continue
                T_neighbor_f1 = T_neighbor_current @ T_current_f1
                if neighbor == f0:
                    return T_neighbor_f1
                visited.add(neighbor)
                queue.append((neighbor, T_neighbor_f1))
        raise KeyError(f"no transform path between {f0!r} and {f1!r}")


def load_frame_graph(path: str | Path) -> FrameTransformGraph:
    """Load the JSON layout used by MVS-GI/mvs_utils ``read_frame_graph``."""

    path = Path(path)
    with path.open("r", encoding="utf-8") as f:
        obj = json.load(f)
    if not isinstance(obj, dict):
        raise ValueError("frame graph root must be a JSON object")

    frames_obj = obj.get("frames")
    typical_obj = obj.get("typical_poses")
    transforms_obj = obj.get("transforms")
    if not isinstance(frames_obj, list):
        raise ValueError("frame graph frames must be a list")
    if not isinstance(typical_obj, dict):
        raise ValueError("frame graph typical_poses must be an object")
    if not isinstance(transforms_obj, list):
        raise ValueError("frame graph transforms must be a list")

    frames = {str(entry["name"]) for entry in frames_obj if isinstance(entry, dict)}
    typical: dict[str, np.ndarray] = {}
    for key, value in typical_obj.items():
        if not isinstance(value, dict):
            raise ValueError(f"typical pose {key!r} must be an object")
        typical[str(key)] = _parse_pose(value)

    adjacency: dict[str, list[tuple[str, np.ndarray]]] = {frame: [] for frame in frames}
    for entry in transforms_obj:
        if not isinstance(entry, dict):
            raise ValueError("transform entries must be objects")
        f0 = str(entry["f0"])
        f1 = str(entry["f1"])
        if f0 not in frames or f1 not in frames:
            raise ValueError(f"transform references undeclared frame: {f0!r}, {f1!r}")
        pose = entry.get("pose")
        if not isinstance(pose, dict):
            raise ValueError("transform pose must be an object")
        pose_type = pose.get("type")
        if pose_type == "create":
            T_f0_f1 = _parse_pose(pose)
        elif pose_type == "reference":
            key = pose.get("key")
            if not isinstance(key, str) or key not in typical:
                raise ValueError(f"unknown typical pose reference: {key!r}")
            T_f0_f1 = typical[key].copy()
        else:
            raise ValueError(f"unsupported pose type: {pose_type!r}")

        adjacency[f1].append((f0, T_f0_f1))
        adjacency[f0].append((f1, np.linalg.inv(T_f0_f1)))

    return FrameTransformGraph(
        frames=frozenset(frames),
        edges={key: tuple(value) for key, value in adjacency.items()},
    )
