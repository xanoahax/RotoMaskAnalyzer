import csv

from rotomask_analyzer.aggregation import aggregate_variant, compare_correction
from rotomask_analyzer.domain import FrameMetric
from rotomask_analyzer.outputs import (
    write_batch_summary,
    write_clip_summary,
    write_correction_summary,
    write_frame_metrics,
    write_problem_sequences,
)
from rotomask_analyzer.problem_detection import build_problem_sequences


def _metrics(variant):
    return [
        FrameMetric(
            clip_id="clip_01",
            variant=variant,
            frame_number=1,
            filename="shot_0001.png",
            soft_iou=1.0,
            soft_iou_delta=None,
            soft_iou_change=None,
        ),
        FrameMetric(
            clip_id="clip_01",
            variant=variant,
            frame_number=2,
            filename="shot_0002.png",
            soft_iou=0.5,
            soft_iou_delta=-0.5,
            soft_iou_change=0.5,
            is_problematic=True,
            problem_reasons=("low_soft_iou", "high_soft_iou_change"),
        ),
    ]


def _read(path):
    return list(
        csv.reader(
            path.open(encoding="utf-8-sig", newline=""),
            delimiter=";",
        )
    )


def test_frame_metrics_csv_has_exact_soft_schema_order_and_format(tmp_path):
    path = tmp_path / "frame_metrics.csv"

    write_frame_metrics(path, _metrics("roto_corrected") + _metrics("roto_raw"))

    rows = _read(path)
    assert rows[0] == [
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
    assert rows[1] == [
        "clip_01",
        "roto_raw",
        "1",
        "shot_0001.png",
        "1,000000",
        "",
        "",
        "false",
        "",
    ]
    assert rows[2][4:] == [
        "0,500000",
        "-0,500000",
        "0,500000",
        "true",
        "low_soft_iou|high_soft_iou_change",
    ]
    assert len(rows) == 5


def test_csv_uses_german_excel_dialect_and_utf8_bom(tmp_path):
    path = tmp_path / "frame_metrics.csv"

    write_frame_metrics(path, _metrics("roto_raw"))

    raw = path.read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf")
    rows = list(
        csv.reader(
            path.open(encoding="utf-8-sig", newline=""),
            delimiter=";",
        )
    )
    assert len(rows[0]) == 9
    assert rows[1][4] == "1,000000"
    assert rows[2][4:7] == ["0,500000", "-0,500000", "0,500000"]


def test_all_summary_csvs_have_exact_schema_and_derive_batch_values(tmp_path):
    raw_metrics = _metrics("roto_raw")
    corrected_metrics = _metrics("roto_corrected")
    corrected_metrics[1].soft_iou = 0.75
    corrected_metrics[1].soft_iou_delta = -0.25
    corrected_metrics[1].soft_iou_change = 0.25
    corrected_metrics[1].is_problematic = False
    corrected_metrics[1].problem_reasons = ()
    raw = aggregate_variant(raw_metrics)
    corrected = aggregate_variant(corrected_metrics)
    correction = compare_correction(raw, corrected)

    write_clip_summary(tmp_path / "clip_summary.csv", [corrected, raw])
    write_problem_sequences(
        tmp_path / "problem_sequences.csv",
        build_problem_sequences(raw_metrics) + build_problem_sequences(corrected_metrics),
    )
    write_correction_summary(tmp_path / "correction_summary.csv", correction)
    write_batch_summary(tmp_path / "batch_summary.csv", [(raw, corrected, correction)])

    clip_rows = _read(tmp_path / "clip_summary.csv")
    sequence_rows = _read(tmp_path / "problem_sequences.csv")
    correction_rows = _read(tmp_path / "correction_summary.csv")
    batch_rows = _read(tmp_path / "batch_summary.csv")
    assert clip_rows[0] == [
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
    assert sequence_rows[0] == [
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
    assert correction_rows[0] == [
        "clip_id",
        "mean_soft_iou_improvement",
        "problem_frame_reduction",
        "problem_frame_ratio_reduction",
    ]
    assert batch_rows[0] == [
        "clip_id",
        "frame_count",
        "raw_mean_soft_iou",
        "corrected_mean_soft_iou",
        "mean_soft_iou_improvement",
        "raw_problem_frame_count",
        "corrected_problem_frame_count",
        "problem_frame_reduction",
    ]
    assert [row[1] for row in clip_rows[1:]] == ["roto_raw", "roto_corrected"]
    assert len(clip_rows) == 3
    assert len(sequence_rows) == 2
    assert len(correction_rows) == 2
    assert len(batch_rows) == 2
    assert batch_rows[1][2] == clip_rows[1][3]
    assert batch_rows[1][3] == clip_rows[2][3]
    assert batch_rows[1][4] == correction_rows[1][1]
    all_files = (clip_rows, sequence_rows, correction_rows, batch_rows)
    combined = "\n".join(";".join(row) for rows in all_files for row in rows)
    assert "false_positive" not in combined
    assert "false_negative" not in combined


def test_problem_sequence_file_keeps_new_header_when_empty(tmp_path):
    path = tmp_path / "problem_sequences.csv"

    write_problem_sequences(path, [])

    assert _read(path) == [[
        "clip_id",
        "variant",
        "sequence_id",
        "start_frame",
        "end_frame",
        "length",
        "trigger_reasons",
        "min_soft_iou",
        "max_soft_iou_change",
    ]]
