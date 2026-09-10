"""Soft-IoU problem-frame rules and contiguous sequence construction."""

from .domain import FrameMetric, ProblemSequence

REASON_ORDER = ("low_soft_iou", "high_soft_iou_change")


def detect_problem_reasons(metric: FrameMetric, thresholds: dict[str, float]) -> tuple[str, ...]:
    reasons: list[str] = []
    if metric.soft_iou < thresholds["soft_iou_below"]:
        reasons.append("low_soft_iou")
    if (
        metric.soft_iou_change is not None
        and metric.soft_iou_change > thresholds["soft_iou_change_above"]
    ):
        reasons.append("high_soft_iou_change")
    return tuple(reasons)


def build_problem_sequences(metrics: list[FrameMetric]) -> list[ProblemSequence]:
    problematic = sorted(
        (metric for metric in metrics if metric.is_problematic),
        key=lambda metric: metric.frame_number,
    )
    if not problematic:
        return []
    groups: list[list[FrameMetric]] = [[problematic[0]]]
    for metric in problematic[1:]:
        if metric.frame_number == groups[-1][-1].frame_number + 1:
            groups[-1].append(metric)
        else:
            groups.append([metric])

    sequences: list[ProblemSequence] = []
    for sequence_id, group in enumerate(groups, start=1):
        present_reasons = {reason for metric in group for reason in metric.problem_reasons}
        changes = [
            metric.soft_iou_change
            for metric in group
            if metric.soft_iou_change is not None
        ]
        sequences.append(
            ProblemSequence(
                clip_id=group[0].clip_id,
                variant=group[0].variant,
                sequence_id=sequence_id,
                start_frame=group[0].frame_number,
                end_frame=group[-1].frame_number,
                length=group[-1].frame_number - group[0].frame_number + 1,
                trigger_reasons=tuple(
                    reason for reason in REASON_ORDER if reason in present_reasons
                ),
                min_soft_iou=min(metric.soft_iou for metric in group),
                max_soft_iou_change=max(changes) if changes else None,
            )
        )
    return sequences
