import csv
import json
from pathlib import Path

import numpy as np

from nadir.data.mvs_gi import decode_compressed_float_u8, load_samples


def test_compressed_float_byte_reinterpretation_roundtrip():
    expected = np.array([[0.5, 1.0], [2.5, 100.0]], dtype="<f4")
    encoded = expected[..., None].view(np.uint8).reshape(2, 2, 4)
    decoded = decode_compressed_float_u8(encoded)
    assert decoded.dtype == np.dtype("<f4")
    np.testing.assert_array_equal(decoded, expected)


def _touch(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"")


def test_mvs_gi_partition_meta_csv_contract(tmp_path: Path):
    root = tmp_path / "DSTA_MVS_Dataset_V2"
    root.mkdir()
    (root / "metadata.json").write_text('{"cams": [{}, {}, {}]}', encoding="utf-8")
    (root / "frame_graph.json").write_text(
        '{"frames": [], "typical_poses": {}, "transforms": []}', encoding="utf-8"
    )
    (root / "data_partitions.json").write_text(
        json.dumps({"validate": {"EnvA": ["Trajectory01"]}}), encoding="utf-8"
    )

    traj = root / "EnvA" / "Trajectory01"
    traj.mkdir(parents=True)
    (traj / "meta.json").write_text(
        json.dumps({"selected_file_list": "selected.csv"}), encoding="utf-8"
    )

    row = {
        "cam0_rgb_fisheye": "cam0\\000001.png",
        "cam1_rgb_fisheye": "cam1\\000001.png",
        "cam2_rgb_fisheye": "cam2\\000001.png",
        "rig_dist_fisheye": "rig\\000001.png",
    }
    with (traj / "selected.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(row))
        writer.writeheader()
        writer.writerow(row)

    for rel in (
        "cam0/000001.png",
        "cam1/000001.png",
        "cam2/000001.png",
        "rig/000001.png",
    ):
        _touch(traj / rel)

    samples = load_samples(root, split="validate")
    assert len(samples) == 1
    sample = samples[0]
    assert sample.image_paths == (
        traj / "cam0/000001.png",
        traj / "cam1/000001.png",
        traj / "cam2/000001.png",
    )
    assert sample.distance_gt_path == traj / "rig/000001.png"
    assert sample.metadata_path == root / "metadata.json"
    assert sample.frame_graph_path == root / "frame_graph.json"
    assert sample.sample_id.endswith(":00000000")
