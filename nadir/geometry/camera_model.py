from __future__ import annotations

from typing import Protocol, runtime_checkable

import numpy as np


@runtime_checkable
class NativeCameraModel(Protocol):
    """Minimal camera-model contract required by NADIR geometry.

    NADIR deliberately depends on projection behaviour rather than a concrete
    fisheye class. This keeps the rig compatible with Double Sphere now and
    Kannala-Brandt/EUCM/LinearSphere adapters when experiments require them.
    """

    width: int
    height: int

    def project(
        self,
        xyz: np.ndarray,
        *,
        check_bounds: bool = True,
    ) -> tuple[np.ndarray, np.ndarray]:
        """Project native-camera 3-D points to pixels and return validity."""
        ...

    def unproject(self, uv: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Unproject native pixels to unit rays and return validity."""
        ...
