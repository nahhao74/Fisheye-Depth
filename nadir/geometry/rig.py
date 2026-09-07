from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations

import numpy as np

from .double_sphere import DoubleSphereCamera
from .transforms import transform_points


@dataclass(frozen=True)
class RigCamera:
    """One calibrated camera in the Rig/Body frame.

    T_C_B maps a point expressed in Body/Rig coordinates into this camera frame.
    """

    name: str
    model: DoubleSphereCamera
    T_C_B: np.ndarray

    def __post_init__(self) -> None:
        T = np.asarray(self.T_C_B, dtype=np.float64)
        if T.shape != (4, 4):
            raise ValueError("T_C_B must be 4x4")
        object.__setattr__(self, "T_C_B", T)

    @property
    def T_B_C(self) -> np.ndarray:
        return np.linalg.inv(self.T_C_B)

    @property
    def center_B(self) -> np.ndarray:
        return self.T_B_C[:3, 3]

    def project_body_points(self, points_B: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        points_C = transform_points(self.T_C_B, points_B)
        return self.model.project(points_C)


@dataclass(frozen=True)
class CameraRig:
    cameras: tuple[RigCamera, ...]

    def __post_init__(self) -> None:
        if len(self.cameras) < 2:
            raise ValueError("A stereo rig requires at least two cameras")
        names = [c.name for c in self.cameras]
        if len(set(names)) != len(names):
            raise ValueError("Camera names must be unique")

    def pair_indices(self) -> tuple[tuple[int, int], ...]:
        return tuple(combinations(range(len(self.cameras)), 2))

    def baseline_matrix_m(self) -> np.ndarray:
        n = len(self.cameras)
        out = np.zeros((n, n), dtype=np.float64)
        centers = [c.center_B for c in self.cameras]
        for a, b in self.pair_indices():
            d = float(np.linalg.norm(centers[a] - centers[b]))
            out[a, b] = out[b, a] = d
        return out
