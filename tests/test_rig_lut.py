import numpy as np

from nadir.geometry.double_sphere import DoubleSphereCamera
from nadir.geometry.lut import build_projection_lut
from nadir.geometry.observability import compute_pair_observability
from nadir.geometry.rig import CameraRig, RigCamera


def make_camera(name: str, center_x: float) -> RigCamera:
    model = DoubleSphereCamera(
        xi=0.5,
        alpha=0.55,
        fx=300.0,
        fy=300.0,
        cx=320.0,
        cy=320.0,
        width=640,
        height=640,
    )
    T_C_B = np.eye(4)
    T_C_B[0, 3] = -center_x
    return RigCamera(name=name, model=model, T_C_B=T_C_B)


def test_projection_lut_and_baseline_observability():
    rig = CameraRig((make_camera("c0", -0.1), make_camera("c1", 0.0), make_camera("c2", 0.1)))
    rays = np.array([[0.0, 0.0, 1.0], [0.1, 0.0, 0.9949874371]], dtype=np.float64)
    rays /= np.linalg.norm(rays, axis=-1, keepdims=True)
    depths = np.array([1.0, 2.0, 5.0])

    lut = build_projection_lut(rig, rays, depths)
    assert lut.uv_px.shape == (3, 2, 3, 2)
    assert lut.valid.shape == (3, 2, 3)
    assert np.all(lut.valid)
    assert np.all(lut.visibility_mask == 0b111)
    assert np.all(lut.view_count == 3)

    obs = compute_pair_observability(rig, rays, depths, projection_lut=lut)
    np.testing.assert_allclose(obs.baseline_m, [0.1, 0.2, 0.1], atol=1e-12)
    assert obs.triangulation_angle_rad.shape == (3, 2, 3)
    assert obs.pair_valid.shape == (3, 2, 3)
    assert np.all(obs.pair_valid)

    # Pair (c0, c2) has a 0.2 m x-axis baseline. For the nadir +Z ray,
    # the whole baseline is perpendicular to the viewing direction.
    np.testing.assert_allclose(obs.effective_baseline_m[1, 0], 0.2, atol=1e-12)

    # A fixed physical baseline produces a smaller triangulation angle as range grows.
    assert obs.triangulation_angle_rad[1, 0, 0] > obs.triangulation_angle_rad[1, 0, -1]
    assert obs.sin_triangulation_angle[1, 0, 0] > obs.sin_triangulation_angle[1, 0, -1]


def test_rig_rejects_non_rigid_extrinsic_rotation():
    model = DoubleSphereCamera(
        xi=0.5,
        alpha=0.55,
        fx=300.0,
        fy=300.0,
        cx=320.0,
        cy=320.0,
        width=640,
        height=640,
    )
    bad = np.eye(4)
    bad[0, 0] = 2.0
    try:
        RigCamera(name="bad", model=model, T_C_B=bad)
    except ValueError:
        pass
    else:
        raise AssertionError("non-rigid T_C_B must be rejected")
