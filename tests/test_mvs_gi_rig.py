import json
from pathlib import Path

import numpy as np

from nadir.data import build_mvs_gi_rig, camera_model_from_mvs_gi_spec
from nadir.geometry import DoubleSphereCamera, LinearSphereCamera


def test_camera_model_factory_supports_verified_models():
    linear = camera_model_from_mvs_gi_spec(
        {
            "type": "LinearSphere",
            "fov_degree": 195,
            "shape_struct": {"H": 1024, "W": 1024},
            "in_to_tensor": True,
            "out_to_numpy": False,
        }
    )
    assert isinstance(linear, LinearSphereCamera)
    assert linear.fov_degree == 195.0

    ds = camera_model_from_mvs_gi_spec(
        {
            "type": "DoubleSphere",
            "xi": -0.2,
            "alpha": 0.6,
            "fx": 300.0,
            "fy": 301.0,
            "cx": 320.0,
            "cy": 321.0,
            "fov_degree": 195,
            "shape_struct": {"H": 640, "W": 640},
        }
    )
    assert isinstance(ds, DoubleSphereCamera)
    assert ds.width == 640


def _pose(position):
    return {
        "type": "create",
        "position": list(position),
        "orientation": {
            "type": "rotation_matrix",
            "data": [1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0],
        },
    }


def test_build_mvs_gi_rig_preserves_ftensor_transform_direction(tmp_path: Path):
    root = tmp_path / "dataset"
    root.mkdir()

    (root / "metadata.json").write_text(
        json.dumps(
            {
                "cams": [
                    {"image_frame": "cif0"},
                    {"image_frame": "cif1"},
                    {"image_frame": "cif2"},
                ]
            }
        ),
        encoding="utf-8",
    )

    frames = [
        {"name": "rbf", "comment": "rig"},
        {"name": "cif0", "comment": "cam0"},
        {"name": "cif1", "comment": "cam1"},
        {"name": "cif2", "comment": "cam2"},
    ]
    centers = ([0.0, 0.0, 0.0], [0.2, 0.0, 0.0], [0.0, 0.3, 0.0])
    transforms = [
        {"f0": "rbf", "f1": f"cif{i}", "pose": _pose(center)}
        for i, center in enumerate(centers)
    ]
    (root / "frame_graph.json").write_text(
        json.dumps({"frames": frames, "typical_poses": {}, "transforms": transforms}),
        encoding="utf-8",
    )

    model_spec = {
        "type": "LinearSphere",
        "fov_degree": 195,
        "shape_struct": {"H": 1024, "W": 1024},
    }
    samplers = [
        {
            "mvs_main_cam_model_for_cam": True,
            "mvs_cam_key": f"cam{i}",
            "sampler": {"cam_model_key": "fisheye"},
        }
        for i in range(3)
    ]
    (root / "manifest.json").write_text(
        json.dumps({"camera_models": {"fisheye": model_spec}, "samplers": samplers}),
        encoding="utf-8",
    )

    rig = build_mvs_gi_rig(root)
    assert len(rig.cameras) == 3
    np.testing.assert_allclose(rig.cameras[0].center_B, centers[0], atol=1e-12)
    np.testing.assert_allclose(rig.cameras[1].center_B, centers[1], atol=1e-12)
    np.testing.assert_allclose(rig.cameras[2].center_B, centers[2], atol=1e-12)

    baseline = rig.baseline_matrix_m()
    np.testing.assert_allclose(baseline[0, 1], 0.2, atol=1e-12)
    np.testing.assert_allclose(baseline[0, 2], 0.3, atol=1e-12)
    np.testing.assert_allclose(baseline[1, 2], np.hypot(0.2, 0.3), atol=1e-12)
