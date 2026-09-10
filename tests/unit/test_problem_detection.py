from rotomask_analyzer.domain import FrameMetric
from rotomask_analyzer.problem_detection import build_problem_sequences, detect_problem_reasons

THRESHOLDS = {
    "soft_iou_below": 0.70,
    "soft_iou_change_above": 0.10,
}


def _metric(
    frame,
    *,
    soft_iou=0.8,
    change=0.0,
    variant="roto_raw",
    problematic=False,
    reasons=(),
):
    return FrameMetric(
        clip_id="clip_01",
        variant=variant,
        frame_number=frame,
        filename=f"frame_{frame:04d}.png",
        soft_iou=soft_iou,
        soft_iou_delta=None if frame == 1 else change,
        soft_iou_change=None if frame == 1 else abs(change),
        is_problematic=problematic,
        problem_reasons=tuple(reasons),
    )


def test_both_problem_rules_and_reason_order_are_deterministic():
    metric = _metric(2, soft_iou=0.6, change=0.2)

    assert detect_problem_reasons(metric, THRESHOLDS) == (
        "low_soft_iou",
        "high_soft_iou_change",
    )


def test_exact_thresholds_do_not_trigger_strict_rules():
    metric = _metric(2, soft_iou=0.70, change=0.10)

    assert detect_problem_reasons(metric, THRESHOLDS) == ()


def test_first_frame_cannot_trigger_change_rule():
    metric = _metric(1, soft_iou=0.8, change=10.0)

    assert detect_problem_reasons(metric, THRESHOLDS) == ()


def test_reason_changes_do_not_split_sequence_and_reasons_are_ordered():
    metrics = [
        _metric(1, soft_iou=0.6, problematic=True, reasons=("low_soft_iou",)),
        _metric(
            2,
            soft_iou=0.8,
            change=0.2,
            problematic=True,
            reasons=("high_soft_iou_change",),
        ),
        _metric(3, problematic=False),
        _metric(4, soft_iou=0.5, problematic=True, reasons=("low_soft_iou",)),
    ]

    sequences = build_problem_sequences(metrics)

    assert [
        (item.sequence_id, item.start_frame, item.end_frame, item.length)
        for item in sequences
    ] == [(1, 1, 2, 2), (2, 4, 4, 1)]
    assert sequences[0].trigger_reasons == ("low_soft_iou", "high_soft_iou_change")
    assert sequences[0].min_soft_iou == 0.6
    assert sequences[0].max_soft_iou_change == 0.2
    assert sequences[1].trigger_reasons == ("low_soft_iou",)


def test_sequence_containing_only_first_frame_has_missing_max_change():
    sequences = build_problem_sequences(
        [_metric(1, soft_iou=0.5, problematic=True, reasons=("low_soft_iou",)), _metric(2)]
    )

    assert len(sequences) == 1
    assert sequences[0].max_soft_iou_change is None


def test_sequence_ids_restart_for_separate_variant_calls():
    raw = build_problem_sequences(
        [_metric(2, problematic=True, reasons=("low_soft_iou",))]
    )
    corrected = build_problem_sequences(
        [
            _metric(
                2,
                variant="roto_corrected",
                problematic=True,
                reasons=("low_soft_iou",),
            )
        ]
    )

    assert raw[0].sequence_id == corrected[0].sequence_id == 1
