import numpy as np

from nadir.eval import distance_image_to_ray_grid
from nadir.geometry import LinearSphereCamera, make_lower_hemisphere_grid


def test_constant_radial_distance_stays_metric_at_same_origin():
    model = LinearSphereCamera(
        fov_degree=180.0,
        width=128,
        height=128,
        pixel_center_offset=0.5,
    )
    distance = np.full((128, 128), 5.0, dtype=np.float32)
    grid = make_lower_hemisphere_grid(n_azimuth=32, n_polar=16)

    gt = distance_image_to_ray_grid(
        distance,
        source_model=model,
        T_B_C=np.eye(4),
        ray_grid=grid,
    )

    assert gt.source_pixel_count > 0
    assert np.count_nonzero(gt.valid) > grid.rays.shape[1]
    np.testing.assert_allclose(gt.depth_m[gt.valid], 5.0, atol=1e-6)
    assert np.all(np.isfinite(gt.angular_error_rad[gt.valid]))
    assert np.all(gt.angular_error_rad[gt.valid] >= 0.0)


def test_translation_converts_source_distance_to_body_radial_range():
    model = LinearSphereCamera(
        fov_degree=120.0,
        width=64,
        height=64,
        pixel_center_offset=0.5,
    )
    distance = np.full((64, 64), 2.0, dtype=np.float32)
    grid = make_lower_hemisphere_grid(n_azimuth=24, n_polar=12)

    T_B_C = np.eye(4)
    T_B_C[0, 3] = 1.0
    gt = distance_image_to_ray_grid(
        distance,
        source_model=model,
        T_B_C=T_B_C,
        ray_grid=grid,
    )

    assert np.any(gt.valid)
    # A translated camera means the body-origin radial range is no longer the
    # original constant 2 m. This guards against incorrectly copying GT scalars
    # without reconstructing 3-D points first.
    assert np.nanmax(np.abs(gt.depth_m - 2.0)) > 0.1
