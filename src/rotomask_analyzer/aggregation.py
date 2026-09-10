"""Clip-level Soft-IoU and correction-level aggregation."""

import numpy as np

from .domain import CorrectionSummary, FrameMetric, VariantSummary
from .problem_detection import build_problem_sequences


def aggregate_variant(metrics: list[FrameMetric]) -> VariantSummary:
    if not metrics:
        raise ValueError("Mindestens ein Frame-Messwert ist erforderlich.")
    metrics = sorted(metrics, key=lambda metric: metric.frame_number)
    soft_ious = np.asarray([metric.soft_iou for metric in metrics], dtype=float)
    changes = [
        metric.soft_iou_change
        for metric in metrics
        if metric.soft_iou_change is not None
    ]
    problem_count = sum(metric.is_problematic for metric in metrics)
    sequences = build_problem_sequences(metrics)
    return VariantSummary(
        clip_id=metrics[0].clip_id,
        variant=metrics[0].variant,
        frame_count=len(metrics),
        mean_soft_iou=float(np.mean(soft_ious)),
        median_soft_iou=float(np.median(soft_ious)),
        min_soft_iou=float(np.min(soft_ious)),
        max_soft_iou=float(np.max(soft_ious)),
        std_soft_iou=float(np.std(soft_ious, ddof=0)),
        mean_soft_iou_change=float(np.mean(changes)) if changes else None,
        max_soft_iou_change=float(np.max(changes)) if changes else None,
        problem_frame_count=problem_count,
        problem_frame_ratio=problem_count / len(metrics),
        longest_problem_sequence=max((sequence.length for sequence in sequences), default=0),
    )


def compare_correction(raw: VariantSummary, corrected: VariantSummary) -> CorrectionSummary:
    if raw.clip_id != corrected.clip_id:
        raise ValueError("Raw- und Corrected-Zusammenfassung müssen zum selben Clip gehören.")
    return CorrectionSummary(
        clip_id=raw.clip_id,
        mean_soft_iou_improvement=corrected.mean_soft_iou - raw.mean_soft_iou,
        problem_frame_reduction=raw.problem_frame_count - corrected.problem_frame_count,
        problem_frame_ratio_reduction=(
            raw.problem_frame_ratio - corrected.problem_frame_ratio
        ),
    )
