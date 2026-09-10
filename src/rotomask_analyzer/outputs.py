"""Deterministic CSV writers for the fixed Soft-IoU result schemas."""

from __future__ import annotations

import csv
from collections.abc import Iterable
from pathlib import Path

from .domain import CorrectionSummary, FrameMetric, ProblemSequence, VariantSummary


def write_frame_metrics(path: Path, metrics: list[FrameMetric]) -> None:
    header = [
        "clip_id",
        "variant",
        "frame_number",
        "filename",
        "soft_iou",
        "soft_iou_delta",
        "soft_iou_change",
        "is_problematic",
        "problem_reasons",
    ]
    ordered = sorted(
        metrics,
        key=lambda item: _metric_sort_key(item.clip_id, item.variant, item.frame_number),
    )
    rows = [
        [
            item.clip_id,
            item.variant,
            item.frame_number,
            item.filename,
            _float(item.soft_iou),
            _float(item.soft_iou_delta),
            _float(item.soft_iou_change),
            "true" if item.is_problematic else "false",
            "|".join(item.problem_reasons),
        ]
        for item in ordered
    ]
    _write_csv(path, header, rows)


def write_clip_summary(path: Path, summaries: list[VariantSummary]) -> None:
    header = [
        "clip_id",
        "variant",
        "frame_count",
        "mean_soft_iou",
        "median_soft_iou",
        "min_soft_iou",
        "max_soft_iou",
        "std_soft_iou",
        "mean_soft_iou_change",
        "max_soft_iou_change",
        "problem_frame_count",
        "problem_frame_ratio",
        "longest_problem_sequence",
    ]
    ordered = sorted(summaries, key=lambda item: _metric_sort_key(item.clip_id, item.variant, 0))
    rows = [
        [
            item.clip_id,
            item.variant,
            item.frame_count,
            _float(item.mean_soft_iou),
            _float(item.median_soft_iou),
            _float(item.min_soft_iou),
            _float(item.max_soft_iou),
            _float(item.std_soft_iou),
            _float(item.mean_soft_iou_change),
            _float(item.max_soft_iou_change),
            item.problem_frame_count,
            _float(item.problem_frame_ratio),
            item.longest_problem_sequence,
        ]
        for item in ordered
    ]
    _write_csv(path, header, rows)


def write_problem_sequences(path: Path, sequences: list[ProblemSequence]) -> None:
    header = [
        "clip_id",
        "variant",
        "sequence_id",
        "start_frame",
        "end_frame",
        "length",
        "trigger_reasons",
        "min_soft_iou",
        "max_soft_iou_change",
    ]
    ordered = sorted(
        sequences,
        key=lambda item: _metric_sort_key(item.clip_id, item.variant, item.sequence_id),
    )
    rows = [
        [
            item.clip_id,
            item.variant,
            item.sequence_id,
            item.start_frame,
            item.end_frame,
            item.length,
            "|".join(item.trigger_reasons),
            _float(item.min_soft_iou),
            _float(item.max_soft_iou_change),
        ]
        for item in ordered
    ]
    _write_csv(path, header, rows)


def write_correction_summary(path: Path, summary: CorrectionSummary) -> None:
    header = [
        "clip_id",
        "mean_soft_iou_improvement",
        "problem_frame_reduction",
        "problem_frame_ratio_reduction",
    ]
    _write_csv(
        path,
        header,
        [[
            summary.clip_id,
            _float(summary.mean_soft_iou_improvement),
            summary.problem_frame_reduction,
            _float(summary.problem_frame_ratio_reduction),
        ]],
    )


def write_batch_summary(
    path: Path,
    rows: list[tuple[VariantSummary, VariantSummary, CorrectionSummary]],
) -> None:
    header = [
        "clip_id",
        "frame_count",
        "raw_mean_soft_iou",
        "corrected_mean_soft_iou",
        "mean_soft_iou_improvement",
        "raw_problem_frame_count",
        "corrected_problem_frame_count",
        "problem_frame_reduction",
    ]
    ordered = sorted(rows, key=lambda row: row[0].clip_id)
    csv_rows = [
        [
            raw.clip_id,
            raw.frame_count,
            _float(raw.mean_soft_iou),
            _float(corrected.mean_soft_iou),
            _float(correction.mean_soft_iou_improvement),
            raw.problem_frame_count,
            corrected.problem_frame_count,
            correction.problem_frame_reduction,
        ]
        for raw, corrected, correction in ordered
    ]
    _write_csv(path, header, csv_rows)


def _write_csv(path: Path, header: list[str], rows: Iterable[list[object]]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as output:
        writer = csv.writer(output, delimiter=";", lineterminator="\r\n")
        writer.writerow(header)
        writer.writerows(rows)


def _float(value: float | None) -> str:
    return "" if value is None else f"{value:.6f}".replace(".", ",")


def _metric_sort_key(clip_id: str, variant: str, number: int) -> tuple[str, int, int]:
    variant_order = {"roto_raw": 0, "roto_corrected": 1}
    return clip_id, variant_order.get(variant, 99), number
