import numpy as np

from nadir.geometry import (
    LinearSphereCamera,
    RigCamera,
    array_pixels_to_body_rays,
    project_body_points_to_array,
    triangulate_two_rays,
)


def test_two_ray_triangulation_recovers_exact_intersection():
    Oa = np.array([-0.1, 0.0, 0.0])
    Ob = np.array([0.1, 0.0, 0.0])
    target = np.array([0.0, 0.0, 2.0])
    da = target - Oa
    db = target - Ob

    result = triangulate_two_rays(Oa, da, Ob, db)

    assert bool(result.numerically_valid)
    assert bool(result.forward_valid)
    np.testing.assert_allclose(result.point_B, target, atol=1e-10)
    np.testing.assert_allclose(result.closest_gap_m, 0.0, atol=1e-10)
    assert result.lambda_a_m > 0.0
    assert result.lambda_b_m > 0.0
    assert result.angle_rad > 0.0
    assert np.isfinite(result.condition_number)


def test_parallel_rays_are_reported_numerically_invalid():
    result = triangulate_two_rays(
        np.array([0.0, 0.0, 0.0]),
        np.array([0.0, 0.0, 1.0]),
        np.array([0.1, 0.0, 0.0]),
        np.array([0.0, 0.0, 1.0]),
    )

    assert not bool(result.numerically_valid)
    assert not bool(result.forward_valid)
    assert np.isnan(result.closest_gap_m)


def test_array_pixel_helpers_respect_mvs_gi_half_pixel_convention():
    model = LinearSphereCamera(
        fov_degree=195.0,
        width=1024,
        height=1024,
        pixel_center_offset=0.5,
    )
    camera = RigCamera(name="cam0", model=model, T_C_B=np.eye(4))

    # Optical axis is model coordinate (512, 512), hence array coordinate
    # (511.5, 511.5) when pixel centers are represented as n + 0.5.
    uv_array = np.array([[511.5, 511.5]])
    rays_B, valid = array_pixels_to_body_rays(camera, uv_array)
    assert valid[0]
    np.testing.assert_allclose(rays_B[0], [0.0, 0.0, 1.0], atol=1e-12)

    points_B = rays_B * 3.0
    uv_roundtrip, valid2 = project_body_points_to_array(camera, points_B)
    assert valid2[0]
    np.testing.assert_allclose(uv_roundtrip, uv_array, atol=1e-10)
