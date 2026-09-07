import numpy as np

from nadir.geometry import DoubleSphereCamera


def camera() -> DoubleSphereCamera:
    return DoubleSphereCamera(
        xi=0.5,
        alpha=0.55,
        fx=300.0,
        fy=300.0,
        cx=320.0,
        cy=320.0,
        width=640,
        height=640,
    )


def test_principal_point_unprojects_to_optical_axis():
    rays, valid = camera().unproject(np.array([[320.0, 320.0]]))
    assert valid[0]
    np.testing.assert_allclose(rays[0], [0.0, 0.0, 1.0], atol=1e-10)


def test_pixel_roundtrip_in_valid_region():
    cam = camera()
    u = np.linspace(120.0, 520.0, 9)
    v = np.linspace(120.0, 520.0, 9)
    uu, vv = np.meshgrid(u, v)
    uv = np.stack([uu.ravel(), vv.ravel()], axis=-1)
    rays, valid = cam.unproject(uv)
    assert np.all(valid)
    uv2, valid2 = cam.project(rays)
    assert np.all(valid2)
    np.testing.assert_allclose(uv2, uv, atol=1e-8)


def test_projection_supports_valid_rays_beyond_90_degrees():
    cam = camera()
    theta = np.deg2rad(100.0)
    ray = np.array([[np.sin(theta), 0.0, np.cos(theta)]])
    uv, valid = cam.project(ray, check_bounds=False)
    assert valid[0]
    assert np.all(np.isfinite(uv[0]))

    ray2, valid2 = cam.unproject(uv, check_bounds=False)
    assert valid2[0]
    np.testing.assert_allclose(ray2[0], ray[0], atol=1e-9)


def test_projection_rejects_points_outside_double_sphere_domain():
    cam = camera()
    theta = np.deg2rad(170.0)
    ray = np.array([[np.sin(theta), 0.0, np.cos(theta)]])
    uv, valid = cam.project(ray, check_bounds=False)
    assert not valid[0]
    assert np.all(np.isnan(uv[0]))
