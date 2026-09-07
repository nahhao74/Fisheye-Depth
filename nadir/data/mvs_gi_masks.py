from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import numpy as np

from .mvs_gi import MvsGiLayoutError


@dataclass(frozen=True)
class MvsGiMaskPaths:
    """Resolved released source-mask paths indexed by raw camera key."""

    paths: dict[str, Path]
    augmented: bool


def discover_mvs_gi_mask_paths(
    root: str | Path,
    *,
    mask_path: str | Path = "masks.json",
    camera_keys: Sequence[str] = ("cam0", "cam1", "cam2"),
    augmented: bool = False,
) -> MvsGiMaskPaths:
    """Parse MVS-GI's released ``masks.json`` without decoding image payloads.

    The official loader uses entries shaped as ``{raw_camera, mask}`` under
    ``masks`` and optionally ``masks_augmented``. NADIR defaults to the ordinary
    physical/source masks; augmented masks are never enabled implicitly.
    """

    root = Path(root)
    config_path = Path(mask_path)
    if not config_path.is_absolute():
        config_path = root / config_path
    if not config_path.is_file():
        raise MvsGiLayoutError(f"required mask config is missing: {config_path}")

    with config_path.open("r", encoding="utf-8") as f:
        obj = json.load(f)
    if not isinstance(obj, dict):
        raise MvsGiLayoutError("masks.json root must be an object")

    section = "masks_augmented" if augmented else "masks"
    entries = obj.get(section)
    if not isinstance(entries, list):
        raise MvsGiLayoutError(f"masks.json must contain a {section!r} list")

    resolved: dict[str, Path] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            raise MvsGiLayoutError(f"{section} entries must be objects")
        camera = entry.get("raw_camera")
        path_value = entry.get("mask")
        if not isinstance(camera, str) or not isinstance(path_value, str) or not path_value:
            raise MvsGiLayoutError(
                f"{section} entry must contain string raw_camera and mask fields"
            )
        if camera in resolved:
            raise MvsGiLayoutError(f"duplicate mask entry for camera {camera!r}")
        p = Path(path_value.replace("\\", "/"))
        if not p.is_absolute():
            p = root / p
        resolved[camera] = p

    missing = [camera for camera in camera_keys if camera not in resolved]
    if missing:
        raise MvsGiLayoutError(f"mask config lacks requested camera(s): {missing}")

    return MvsGiMaskPaths(
        paths={camera: resolved[camera] for camera in camera_keys},
        augmented=augmented,
    )


def read_mvs_gi_masks(
    root: str | Path,
    *,
    mask_path: str | Path = "masks.json",
    camera_keys: Sequence[str] = ("cam0", "cam1", "cam2"),
    augmented: bool = False,
) -> tuple[np.ndarray, ...]:
    """Decode released MVS-GI binary source masks in camera order.

    Official ``mvs_utils.read_mask`` defines a valid source pixel as grayscale
    value exactly 255. NADIR mirrors that semantic; it does not invent a new
    threshold. OpenCV remains an optional dataset dependency.
    """

    try:
        import cv2  # type: ignore
    except ImportError as exc:  # pragma: no cover - dependency-specific
        raise RuntimeError(
            "OpenCV is required to read MVS-GI masks; install the 'mvs-gi' optional dependency"
        ) from exc

    paths = discover_mvs_gi_mask_paths(
        root,
        mask_path=mask_path,
        camera_keys=camera_keys,
        augmented=augmented,
    )
    masks: list[np.ndarray] = []
    for camera in camera_keys:
        p = paths.paths[camera]
        image = cv2.imread(str(p), cv2.IMREAD_GRAYSCALE)
        if image is None:
            raise FileNotFoundError(f"failed to read MVS-GI mask for {camera}: {p}")
        masks.append(np.asarray(image == 255, dtype=bool))
    return tuple(masks)
