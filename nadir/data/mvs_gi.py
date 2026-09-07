from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Sequence

import numpy as np


class MvsGiLayoutError(RuntimeError):
    """Raised when a local MVS-GI tree violates the verified public layout contract."""


@dataclass(frozen=True)
class MvsGiCsvSource:
    csv_path: Path
    relative_prefix: Path
    environment: str
    collection: str


@dataclass(frozen=True)
class MvsGiSample:
    """One synchronized 3-fisheye MVS-GI sample.

    This adapter intentionally preserves MVS-GI source semantics instead of
    pretending that the public dataset has already been converted into NADIR's
    final calibration contract. ``metadata.json`` and ``frame_graph.json`` are
    carried explicitly until the calibration adapter is validated on downloaded
    data.
    """

    sample_id: str
    image_paths: tuple[Path, Path, Path]
    distance_gt_path: Path
    metadata_path: Path
    frame_graph_path: Path
    source_csv: Path
    environment: str
    collection: str
    row_index: int


def decode_compressed_float_u8(encoded: np.ndarray) -> np.ndarray:
    """Decode MVS-GI/mvs_utils compressed-float pixels.

    The official reader loads a 4-channel uint8 image with OpenCV and then
    reinterprets every group of four bytes as little-endian float32. This
    function mirrors only that byte reinterpretation step. The caller must
    provide the exact 4-channel byte order returned by the image decoder.
    """

    arr = np.asarray(encoded)
    if arr.dtype != np.uint8:
        raise ValueError("encoded must have dtype uint8")
    if arr.ndim != 3 or arr.shape[-1] != 4:
        raise ValueError("encoded must have shape (H, W, 4)")
    arr = np.ascontiguousarray(arr)
    return np.squeeze(arr.view("<f4"), axis=-1).copy()


def read_compressed_float(path: str | Path) -> np.ndarray:
    """Read an MVS-GI distance image using the same OpenCV byte semantics.

    OpenCV is kept as an optional dataset dependency so the NADIR geometry core
    remains lightweight. Install ``.[mvs-gi]`` when reading source data.
    """

    try:
        import cv2  # type: ignore
    except ImportError as exc:  # pragma: no cover - dependency-specific
        raise RuntimeError(
            "OpenCV is required to read MVS-GI compressed-float images; "
            "install the 'mvs-gi' optional dependency"
        ) from exc

    p = Path(path)
    img = cv2.imread(str(p), cv2.IMREAD_UNCHANGED)
    if img is None:
        raise FileNotFoundError(f"failed to read MVS-GI distance image: {p}")
    return decode_compressed_float_u8(img)


def _load_json(path: Path) -> dict:
    if not path.is_file():
        raise MvsGiLayoutError(f"required file is missing: {path}")
    with path.open("r", encoding="utf-8") as f:
        obj = json.load(f)
    if not isinstance(obj, dict):
        raise MvsGiLayoutError(f"expected JSON object in {path}")
    return obj


def _normalize_csv_path(value: str) -> Path:
    # Official MVS-GI code explicitly handles Windows backslashes in CSVs.
    return Path(value.replace("\\", "/"))


def discover_csv_sources(root: str | Path, split: str = "validate") -> tuple[MvsGiCsvSource, ...]:
    """Resolve MVS-GI trajectory CSV files from ``data_partitions.json``.

    The logic mirrors the official public loader:

    - root/data_partitions.json selects environments/collections;
    - a collection directory contains meta.json;
    - meta.json points to ``selected_file_list``;
    - alternatively a collection entry may itself be a CSV path.
    """

    root = Path(root)
    _load_json(root / "metadata.json")
    _load_json(root / "frame_graph.json")
    partitions = _load_json(root / "data_partitions.json")

    if split not in partitions:
        raise MvsGiLayoutError(
            f"split {split!r} not present in {root / 'data_partitions.json'}; "
            f"available={sorted(partitions)}"
        )
    split_obj = partitions[split]
    if not isinstance(split_obj, dict):
        raise MvsGiLayoutError(f"partition {split!r} must be a JSON object")

    sources: list[MvsGiCsvSource] = []
    for environment, collections in split_obj.items():
        if not isinstance(collections, list):
            raise MvsGiLayoutError(
                f"partition {split!r}/{environment!r} must be a list of collections"
            )
        for collection_value in collections:
            if not isinstance(collection_value, str):
                raise MvsGiLayoutError("collection entries must be strings")

            collection_path = root / environment / collection_value
            if collection_path.is_dir():
                meta = _load_json(collection_path / "meta.json")
                selected = meta.get("selected_file_list")
                if not isinstance(selected, str) or not selected:
                    raise MvsGiLayoutError(
                        f"{collection_path / 'meta.json'} lacks selected_file_list"
                    )
                csv_path = collection_path / selected
                prefix = Path(environment) / collection_value
            elif collection_path.suffix.lower() == ".csv":
                csv_path = collection_path
                prefix = Path()
            else:
                raise MvsGiLayoutError(
                    f"collection is neither a directory nor CSV path: {collection_path}"
                )

            if not csv_path.is_file():
                raise MvsGiLayoutError(f"selected CSV does not exist: {csv_path}")
            sources.append(
                MvsGiCsvSource(
                    csv_path=csv_path,
                    relative_prefix=prefix,
                    environment=str(environment),
                    collection=str(collection_value),
                )
            )

    return tuple(sources)


def load_samples(
    root: str | Path,
    split: str = "validate",
    *,
    camera_keys: Sequence[str] = ("cam0", "cam1", "cam2"),
    rgb_suffix: str = "_rgb_fisheye",
    rig_key: str = "rig",
    distance_suffix: str = "_dist_fisheye",
    strict_paths: bool = True,
) -> list[MvsGiSample]:
    """Load the verified file-index portion of the public MVS-GI dataset.

    This function does not infer intrinsics/extrinsics. It only freezes the
    source-file semantics that are explicitly present in the official loader.
    """

    if len(camera_keys) != 3:
        raise ValueError("NADIR's current MVS-GI adapter requires exactly 3 camera keys")

    root = Path(root)
    metadata = root / "metadata.json"
    frame_graph = root / "frame_graph.json"
    sources = discover_csv_sources(root, split=split)

    image_columns = tuple(f"{key}{rgb_suffix}" for key in camera_keys)
    distance_column = f"{rig_key}{distance_suffix}"
    required_columns = set(image_columns + (distance_column,))

    samples: list[MvsGiSample] = []
    for source in sources:
        with source.csv_path.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            if reader.fieldnames is None:
                raise MvsGiLayoutError(f"CSV has no header: {source.csv_path}")
            missing = required_columns.difference(reader.fieldnames)
            if missing:
                raise MvsGiLayoutError(
                    f"CSV {source.csv_path} misses required columns: {sorted(missing)}"
                )

            for row_index, row in enumerate(reader):
                def resolve(column: str) -> Path:
                    raw = row.get(column)
                    if not isinstance(raw, str) or not raw:
                        raise MvsGiLayoutError(
                            f"empty {column!r} at {source.csv_path}:{row_index + 2}"
                        )
                    p = _normalize_csv_path(raw)
                    if not p.is_absolute():
                        p = root / source.relative_prefix / p
                    return p

                images = tuple(resolve(column) for column in image_columns)
                distance = resolve(distance_column)

                if strict_paths:
                    missing_paths = [p for p in (*images, distance) if not p.is_file()]
                    if missing_paths:
                        raise MvsGiLayoutError(
                            f"referenced source file(s) are missing; first={missing_paths[0]}"
                        )

                sample_id = (
                    f"{split}:{source.environment}:{source.collection}:{row_index:08d}"
                )
                samples.append(
                    MvsGiSample(
                        sample_id=sample_id,
                        image_paths=images,  # type: ignore[arg-type]
                        distance_gt_path=distance,
                        metadata_path=metadata,
                        frame_graph_path=frame_graph,
                        source_csv=source.csv_path,
                        environment=source.environment,
                        collection=source.collection,
                        row_index=row_index,
                    )
                )

    return samples


def iter_samples(*args, **kwargs) -> Iterator[MvsGiSample]:
    """Iterator convenience wrapper around :func:`load_samples`."""

    yield from load_samples(*args, **kwargs)
