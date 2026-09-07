from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from nadir.geometry.camera_model import NativeCameraModel
from nadir.geometry.frame_graph import load_frame_graph

from .mvs_gi import MvsGiLayoutError, read_manifest_summary
from .mvs_gi_rig import camera_model_from_mvs_gi_spec


@dataclass(frozen=True)
class MvsGiRigReference:
    """Native reference camera used by the released MVS-GI rig distance image."""

    model: NativeCameraModel
    T_B_R: np.ndarray
    frame_name: str
    model_key: str


def read_mvs_gi_rig_reference(
    root: str | Path,
    *,
    body_frame: str = "rbf",
    rig_key: str = "rig",
    raw_rig_frame: str = "rif",
) -> MvsGiRigReference:
    """Read the model and pose associated with ``rig_dist_fisheye``.

    The released ``MultiViewCameraModelDataset.find_rig_raw_frame`` currently
    returns ``'rif'`` explicitly. We keep that as an explicit default rather than
    deriving a new frame convention. If a future dataset version changes this,
    callers must pass the new raw frame after verifying its metadata semantics.
    """

    root = Path(root)
    summary = read_manifest_summary(root / "manifest.json")
    model_key = summary.camera_to_model_key.get(rig_key)
    if model_key is None:
        raise MvsGiLayoutError(
            f"manifest lacks native camera-model binding for rig key {rig_key!r}"
        )
    model = camera_model_from_mvs_gi_spec(summary.camera_model_specs[model_key])

    graph_path = root / "frame_graph.json"
    if not graph_path.is_file():
        raise MvsGiLayoutError(f"required file is missing: {graph_path}")
    graph = load_frame_graph(graph_path)
    try:
        T_B_R = graph.query_transform(body_frame, raw_rig_frame)
    except KeyError as exc:
        raise MvsGiLayoutError(
            f"cannot resolve released rig reference frame {raw_rig_frame!r} "
            f"with respect to {body_frame!r}"
        ) from exc

    return MvsGiRigReference(
        model=model,
        T_B_R=T_B_R,
        frame_name=raw_rig_frame,
        model_key=model_key,
    )
