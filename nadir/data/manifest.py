from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator


@dataclass(frozen=True)
class NadirSample:
    sample_id: str
    image_paths: tuple[Path, Path, Path]
    depth_gt_path: Path
    calibration_path: Path
    timestamp_ns: int | None = None


class ManifestDataset:
    """Dataset-independent NADIR sample index.

    We intentionally avoid hard-coding an assumed MVS-GI directory structure
    before the downloaded dataset has been inspected. Public datasets are first
    adapted into this manifest contract, then geometry/MVS code consumes the
    same representation.
    """

    def __init__(self, manifest_path: str | Path):
        self.manifest_path = Path(manifest_path)
        self.root = self.manifest_path.parent
        with self.manifest_path.open("r", encoding="utf-8") as f:
            payload = json.load(f)
        if payload.get("schema") != "nadir.sample_manifest.v1":
            raise ValueError("Unsupported manifest schema")
        self._items = payload.get("samples", [])

    def __len__(self) -> int:
        return len(self._items)

    def __iter__(self) -> Iterator[NadirSample]:
        for i in range(len(self)):
            yield self[i]

    def __getitem__(self, index: int) -> NadirSample:
        item = self._items[index]
        cams = item.get("images")
        if not isinstance(cams, list) or len(cams) != 3:
            raise ValueError(f"sample[{index}] must contain exactly 3 image paths")

        def resolve(p: str) -> Path:
            path = Path(p)
            return path if path.is_absolute() else self.root / path

        return NadirSample(
            sample_id=str(item["sample_id"]),
            image_paths=tuple(resolve(p) for p in cams),  # type: ignore[arg-type]
            depth_gt_path=resolve(item["depth_gt"]),
            calibration_path=resolve(item["calibration"]),
            timestamp_ns=item.get("timestamp_ns"),
        )
