import numpy as np

from nadir.geometry import LinearSphereCamera


def camera(fov_degree: float = 195.0) -> LinearSphereCamera:
    return LinearSphereCamera(fov_degree=fov_degree, width=1024, height=1024)


def test_principal_point_unprojects_to_optical_axis():
    rays, valid = camera().unproject(np.array([[512.0, 512.0]]))
    assert valid[0]
    np.testing.assert_allclose(rays[0], [0.0, 0.0, 1.0], atol=1e-12)


def test_linear_radius_matches_source_model_definition():
    cam = camera(195.0)
    incidence = np.deg2rad(60.0)
    radius = incidence * cam.width / cam.fov_rad
    uv = np.array([[cam.cx + radius, cam.cy]])
    rays, valid = cam.unproject(uv)
    assert valid[0]
    expected = np.array([np.sin(incidence), 0.0, np.cos(incidence)])
    np.testing.assert_allclose(rays[0], expected, atol=1e-10)


def test_projection_roundtrip_in_valid_circle():
    cam = camera()
    incidence = np.deg2rad(np.array([0.0, 20.0, 60.0, 90.0, 97.0]))
    azimuth = np.deg2rad(np.array([0.0, 45.0, -70.0, 130.0, -150.0]))
    rays = np.stack(
        (
            np.sin(incidence) * np.cos(azimuth),
            np.sin(incidence) * np.sin(azimuth),
            np.cos(incidence),
        ),
        axis=-1,
    )
    uv, valid = cam.project(rays)
    assert np.all(valid)
    rays2, valid2 = cam.unproject(uv)
    assert np.all(valid2)
    np.testing.assert_allclose(rays2, rays, atol=1e-10)


def test_fov_greater_than_180_supports_negative_z_rays():
    cam = camera(225.0)
    incidence = np.deg2rad(110.0)
    ray = np.array([[np.sin(incidence), 0.0, np.cos(incidence)]])
    assert ray[0, 2] < 0.0
    uv, valid = cam.project(ray)
    assert valid[0]
    ray2, valid2 = cam.unproject(uv)
    assert valid2[0]
    np.testing.assert_allclose(ray2[0], ray[0], atol=1e-10)


def test_outside_circular_fov_is_invalid_even_if_inside_square_bounds():
    cam = camera(195.0)
    # Square-corner pixels are physically outside the circular fisheye FoV.
    rays, valid = cam.unproject(np.array([[100.0, 100.0]]))
    assert not valid[0]
    assert np.all(np.isnan(rays[0]))


def test_non_square_source_is_rejected_to_match_official_contract():
    try:
        LinearSphereCamera(fov_degree=195.0, width=1024, height=768)
    except ValueError as exc:
        assert "square" in str(exc)
    else:
        raise AssertionError("expected non-square LinearSphereCamera to be rejected")
