import json
from pathlib import Path

import numpy as np

from nadir.geometry.frame_graph import load_frame_graph


def test_frame_graph_query_matches_ftensor_direction(tmp_path: Path):
    # T_A_B maps B coordinates into A: p_A = T_A_B @ p_B.
    graph_json = {
        "frames": [
            {"name": "A", "comment": ""},
            {"name": "B", "comment": ""},
            {"name": "C", "comment": ""},
        ],
        "typical_poses": {},
        "transforms": [
            {
                "f0": "A",
                "f1": "B",
                "pose": {
                    "type": "create",
                    "position": [1.0, 0.0, 0.0],
                    "orientation": {
                        "type": "rotation_matrix",
                        "data": [1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0],
                    },
                },
            },
            {
                "f0": "B",
                "f1": "C",
                "pose": {
                    "type": "create",
                    "position": [0.0, 2.0, 0.0],
                    "orientation": {
                        "type": "quaternion",
                        "data": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0},
                    },
                },
            },
        ],
    }
    path = tmp_path / "frame_graph.json"
    path.write_text(json.dumps(graph_json), encoding="utf-8")

    graph = load_frame_graph(path)
    T_A_C = graph.query_transform("A", "C")
    np.testing.assert_allclose(T_A_C[:3, 3], [1.0, 2.0, 0.0], atol=1e-12)

    T_C_A = graph.query_transform("C", "A")
    np.testing.assert_allclose(T_C_A @ T_A_C, np.eye(4), atol=1e-12)
