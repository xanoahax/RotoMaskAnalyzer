import pytest

from rotomask_analyzer.aggregation import aggregate_variant, compare_correction
from rotomask_analyzer.domain import FrameMetric


def _metric(frame, soft_iou, change, problematic, *, variant="roto_raw"):
    return FrameMetric(
        clip_id="clip_01",
        variant=variant,
        frame_number=frame,
        filename=f"f{frame}.png",
        soft_iou=soft_iou,
        soft_iou_delta=change,
        soft_iou_change=None if change is None else abs(change),
        is_problematic=problematic,
        problem_reasons=("low_soft_iou",) if problematic else (),
    )


def test_variant_aggregate_uses_population_std_and_ignores_first_temporal_value():
    metrics = [
        _metric(1, 1.0, None, False),
        _metric(2, 0.5, -0.5, True),
        _metric(3, 0.0, -0.5, True),
    ]

    summary = aggregate_variant(metrics)

    assert summary.frame_count == 3
    assert summary.mean_soft_iou == 0.5
    assert summary.median_soft_iou == 0.5
    assert summary.min_soft_iou == 0.0
    assert summary.max_soft_iou == 1.0
    assert summary.std_soft_iou == pytest.approx(0.408248290463863)
    assert summary.mean_soft_iou_change == 0.5
    assert summary.max_soft_iou_change == 0.5
    assert summary.problem_frame_count == 2
    assert summary.problem_frame_ratio == pytest.approx(2 / 3)
    assert summary.longest_problem_sequence == 2


def test_no_problem_sequence_has_zero_longest_length():
    summary = aggregate_variant([_metric(1, 1.0, None, False)])

    assert summary.longest_problem_sequence == 0
    assert summary.mean_soft_iou_change is None
    assert summary.max_soft_iou_change is None


def test_correction_comparison_contains_only_soft_iou_and_problem_reductions():
    raw = aggregate_variant(
        [_metric(1, 0.4, None, True), _metric(2, 0.6, 0.2, True)]
    )
    corrected = aggregate_variant(
        [
            _metric(1, 0.8, None, False, variant="roto_corrected"),
            _metric(2, 1.0, 0.2, False, variant="roto_corrected"),
        ]
    )

    comparison = compare_correction(raw, corrected)

    assert comparison.mean_soft_iou_improvement == pytest.approx(0.4)
    assert comparison.problem_frame_reduction == 2
    assert comparison.problem_frame_ratio_reduction == 1.0
    assert set(vars(comparison)) == {
        "clip_id",
        "mean_soft_iou_improvement",
        "problem_frame_reduction",
        "problem_frame_ratio_reduction",
    }
