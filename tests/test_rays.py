import numpy as np

from nadir.geometry import make_lower_hemisphere_grid


def test_lower_hemisphere_grid_unit_norm_and_frd_sign():
    grid = make_lower_hemisphere_grid(128, 64)
    assert grid.rays.shape == (64, 128, 3)
    norms = np.linalg.norm(grid.rays, axis=-1)
    np.testing.assert_allclose(norms, 1.0, atol=1e-12)
    assert np.min(grid.rays[..., 2]) >= -1e-12
    np.testing.assert_allclose(grid.rays[0, :, :2], 0.0, atol=1e-12)
    np.testing.assert_allclose(grid.rays[0, :, 2], 1.0, atol=1e-12)
