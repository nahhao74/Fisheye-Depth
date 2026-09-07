import numpy as np

from nadir.eval import compute_depth_metrics
from nadir.stereo import uniform_depth_candidates, uniform_inverse_depth_candidates


def test_inverse_depth_candidates_are_near_to_far_and_denser_nearby():
    depths = uniform_inverse_depth_candidates(1.0, 10.0, 5)
    assert np.all(np.diff(depths) > 0.0)
    assert np.isclose(depths[0], 1.0)
    assert np.isclose(depths[-1], 10.0)
    # Metric spacing should grow with range for uniform inverse depth.
    spacing = np.diff(depths)
    assert spacing[0] < spacing[-1]


def test_uniform_depth_candidates_have_constant_metric_spacing():
    depths = uniform_depth_candidates(1.0, 5.0, 5)
    np.testing.assert_allclose(np.diff(depths), 1.0)


def test_depth_metrics_ignore_invalid_values_and_do_not_hide_threshold():
    pred = np.array([1.0, 2.2, np.nan, 8.0])
    gt = np.array([1.0, 2.0, 3.0, 4.0])
    metrics = compute_depth_metrics(pred, gt, bad_rel_threshold=0.2)
    assert metrics.valid_count == 3
    np.testing.assert_allclose(metrics.mae_m, (0.0 + 0.2 + 4.0) / 3.0)
    assert metrics.bad_rel_threshold == 0.2
    np.testing.assert_allclose(metrics.bad_rate, 1.0 / 3.0)
