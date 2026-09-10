import numpy as np
import pytest

from rotomask_analyzer import metrics


def test_fractional_alpha_uses_min_max_soft_iou():
    manual = np.array([[0.0, 0.25], [0.5, 1.0]])
    roto = np.array([[0.0, 0.75], [0.25, 1.0]])

    result = metrics.compute_soft_iou(manual, roto)

    assert result == pytest.approx(2 / 3)


def test_identical_fractional_masks_have_perfect_soft_iou():
    manual = np.array([[0.1, 0.4], [0.7, 1.0]])

    assert metrics.compute_soft_iou(manual, manual.copy()) == 1.0


def test_both_empty_is_perfect_and_exactly_one_empty_is_zero():
    empty = np.zeros((2, 2))
    nonempty = np.array([[0.0, 0.5], [0.0, 0.0]])

    assert metrics.compute_soft_iou(empty, empty) == 1.0
    assert metrics.compute_soft_iou(empty, nonempty) == 0.0
    assert metrics.compute_soft_iou(nonempty, empty) == 0.0


def test_shape_mismatch_and_non_2d_arrays_are_rejected():
    with pytest.raises(ValueError, match="dieselbe Form"):
        metrics.compute_soft_iou(np.zeros((2, 2)), np.zeros((2, 3)))
    with pytest.raises(ValueError, match="zweidimensional"):
        metrics.compute_soft_iou(np.zeros((1, 2, 2)), np.zeros((1, 2, 2)))


@pytest.mark.parametrize(
    "bad",
    [
        np.array([[np.nan]]),
        np.array([[np.inf]]),
        np.array([[-0.1]]),
        np.array([[1.1]]),
    ],
)
def test_nonfinite_or_out_of_range_values_are_rejected(bad):
    with pytest.raises(ValueError):
        metrics.compute_soft_iou(np.zeros_like(bad), bad)


def test_temporal_metrics_keep_signed_delta_and_absolute_change():
    assert metrics.temporal_metrics([0.8, 0.6, 0.9]) == [
        (None, None),
        (-0.2, 0.2),
        (0.3, 0.3),
    ]


def test_empty_temporal_input_returns_empty_result():
    assert metrics.temporal_metrics([]) == []
