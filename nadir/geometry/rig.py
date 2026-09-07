from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations

import numpy as np

from .camera_model import NativeCameraModel
from .transforms import transform_points


@dataclass(frozen=True)
class RigCamera:
    """One calibrated camera in the Rig/Body frame.

    ``T_C_B`` maps a point expressed in Body/Rig FRD coordinates into this
    camera's native calibrated frame. The inverse transform therefore contains
    the camera optical-center pose in B.
    """

    name: str
    model: NativeCameraModel
    T_C_B: np.ndarray

    def __post_init__(self) -> None:
        if not isinstance(self.model, NativeCameraModel):
            raise TypeError("model must implement the NativeCameraModel protocol")

        T = np.asarray(self.T_C_B, dtype=np.float64)
        if T.shape != (4, 4):
            raise ValueError("T_C_B must be 4x4")
        if not np.all(np.isfinite(T)):
            raise ValueError("T_C_B must be finite")
        if not np.allclose(T[3], [0.0, 0.0, 0.0, 1.0], atol=1e-9):
            raise ValueError("T_C_B must be a homogeneous rigid transform")

        R = T[:3, :3]
        if not np.allclose(R @ R.T, np.eye(3), atol=1e-6):
            raise ValueError("T_C_B rotation must be orthonormal")
        det = float(np.linalg.det(R))
        if not np.isclose(det, 1.0, atol=1e-6):
            raise ValueError("T_C_B rotation must have determinant +1")

        object.__setattr__(self, "T_C_B", T)

    @property
    def T_B_C(self) -> np.ndarray:
        # Rigid inverse avoids a generic matrix inversion in geometry hot paths.
        R_C_B = self.T_C_B[:3, :3]
        t_C_B = self.T_C_B[:3, 3]
        T = np.eye(4, dtype=np.float64)
        T[:3, :3] = R_C_B.T
        T[:3, 3] = -(R_C_B.T @ t_C_B)
        return T

    @property
    def center_B(self) -> np.ndarray:
        return self.T_B_C[:3, 3]

    def project_body_points(
        self,
        points_B: np.ndarray,
        *,
        check_bounds: bool = True,
    ) -> tuple[np.ndarray, np.ndarray]:
        points_C = transform_points(self.T_C_B, points_B)
        return self.model.project(points_C, check_bounds=check_bounds)


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
