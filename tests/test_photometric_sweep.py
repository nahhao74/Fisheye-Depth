import numpy as np

from nadir.geometry.lut import ProjectionLUT
from nadir.stereo import bilinear_sample, photometric_sphere_sweep


def test_bilinear_sample_center_value():
    image = np.array([[0.0, 1.0], [1.0, 0.0]], dtype=np.float32)
    values, valid = bilinear_sample(image, np.array([[0.5, 0.5]], dtype=np.float32))
    assert valid[0]
    np.testing.assert_allclose(values[0, 0], 0.5, atol=1e-6)


def test_photometric_sweep_selects_lowest_variance_depth():
    # Two 1x3 images. Candidate 0 samples u=0 and disagrees across views;
    # candidate 1 samples u=1 and agrees exactly.
    images = [
        np.array([[0.0, 1.0, 0.0]], dtype=np.float32),
        np.array([[1.0, 1.0, 0.0]], dtype=np.float32),
    ]

    uv_px = np.array(
        [
            [[[[0.0, 0.0], [1.0, 0.0]]]],
            [[[[0.0, 0.0], [1.0, 0.0]]]],
        ],
        dtype=np.float32,
    ).reshape(2, 1, 2, 2)
    valid = np.ones((2, 1, 2), dtype=bool)
    lut = ProjectionLUT(
        uv_px=uv_px,
        uv_normalized=np.zeros_like(uv_px),
        valid=valid,
        depths_m=np.array([1.0, 2.0], dtype=np.float32),
    )

    result = photometric_sphere_sweep(images, lut)
    assert result.valid[0]
    assert result.best_index[0] == 1
    np.testing.assert_allclose(result.depth_m[0], 2.0)
    assert result.cost[0, 1] < result.cost[0, 0]


def test_photometric_sweep_requires_stereo_visibility():
    images = [
        np.array([[0.0, 1.0]], dtype=np.float32),
        np.array([[0.0, 1.0]], dtype=np.float32),
    ]
    uv_px = np.zeros((2, 1, 1, 2), dtype=np.float32)
    valid = np.array([[[True]], [[False]]])
    lut = ProjectionLUT(
        uv_px=uv_px,
        uv_normalized=np.zeros_like(uv_px),
        valid=valid,
        depths_m=np.array([1.0], dtype=np.float32),
    )

    result = photometric_sphere_sweep(images, lut, min_views=2)
    assert not result.valid[0]
    assert np.isnan(result.depth_m[0])
    assert result.best_index[0] == -1
