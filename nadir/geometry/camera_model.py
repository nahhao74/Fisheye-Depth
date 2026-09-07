from __future__ import annotations

from typing import Protocol, runtime_checkable

import numpy as np


@runtime_checkable
class NativeCameraModel(Protocol):
    """Minimal native-camera contract required by NADIR geometry.

    ``project``/``unproject`` operate in the camera model's own continuous pixel
    coordinate convention. ``pixel_center_offset`` states where array pixel
    index ``0`` lies in that model convention:

    - ``0.0``: array index 0 is pixel-center coordinate 0;
    - ``0.5``: array index 0 is pixel-center coordinate 0.5.

    Making this explicit prevents a silent half-pixel error when adapting the
    public MVS-GI ``mvs_utils`` models, whose generated pixel centers use a 0.5
    shift.
    """

    width: int
    height: int
    pixel_center_offset: float

    def project(
        self,
        xyz: np.ndarray,
        *,
        check_bounds: bool = True,
    ) -> tuple[np.ndarray, np.ndarray]:
        """Project native-camera 3-D points to model pixel coordinates."""
        ...

    def unproject(
        self,
        uv: np.ndarray,
        *,
        check_bounds: bool = True,
    ) -> tuple[np.ndarray, np.ndarray]:
        """Unproject model pixel coordinates to unit rays."""
        ...
