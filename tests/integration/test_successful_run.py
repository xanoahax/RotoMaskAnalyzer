import csv
import json
from datetime import UTC, datetime

import numpy as np
import pytest
from conftest import write_rgba_mask
from PIL import Image

from rotomask_analyzer.config import DEFAULT_CONFIG


def test_successful_run_creates_complete_soft_iou_result_structure(project_factory):
    from rotomask_analyzer.analysis_service import AnalysisService

    project = project_factory(clips=("clip_01", "clip_02"))
    manual_alpha = np.array([[0, 64, 128, 255]] * 3, dtype=np.uint8)
    raw_alpha = np.array([[0, 128, 128, 255]] * 3, dtype=np.uint8)
    write_rgba_mask(
        project / "clip_01/manual/frame_0001.png",
        alpha=manual_alpha,
    )
    write_rgba_mask(
        project / "clip_01/roto_raw/frame_0001.png",
        alpha=raw_alpha,
    )
    write_rgba_mask(
        project / "clip_01/roto_corrected/frame_0001.png",
        alpha=manual_alpha,
    )
    progress = []
    service = AnalysisService(now=lambda: datetime(2026, 8, 26, 12, 34, tzinfo=UTC))

    result = service.run(
        project,
        DEFAULT_CONFIG,
        progress_callback=lambda percent, status: progress.append((percent, status)),
    )

    assert result.status == "success"
    assert result.run_dir.name == "2026-08-26_1234"
    assert {path.name for path in result.run_dir.iterdir()} == {
        "analysis_manifest.json",
        "analysis_log.txt",
        "batch_summary.csv",
        "clip_01",
        "clip_02",
    }
    manifest = json.loads((result.run_dir / "analysis_manifest.json").read_text(encoding="utf-8"))
    assert manifest["schema_version"] == "2.0"
    for clip_id in ("clip_01", "clip_02"):
        clip_dir = result.run_dir / clip_id
        assert {path.name for path in clip_dir.iterdir()} == {
            "clip_summary.csv",
            "frame_metrics.csv",
            "problem_sequences.csv",
            "correction_summary.csv",
            "visualizations",
        }
        timeline = clip_dir / "visualizations/soft_iou_timeline.png"
        assert timeline.is_file()
        assert not (clip_dir / "visualizations/iou_timeline.png").exists()
        with Image.open(timeline) as image:
            assert image.format == "PNG"
        with (clip_dir / "frame_metrics.csv").open(
            encoding="utf-8-sig", newline=""
        ) as source:
            rows = list(csv.DictReader(source, delimiter=";"))
        assert len(rows) == 4
        assert set(rows[0]) == {
            "clip_id",
            "variant",
            "frame_number",
            "filename",
            "soft_iou",
            "soft_iou_delta",
            "soft_iou_change",
            "is_problematic",
            "problem_reasons",
        }
    clip_rows = list(
        csv.DictReader(
            (result.run_dir / "clip_01/frame_metrics.csv").open(
                encoding="utf-8-sig", newline=""
            ),
            delimiter=";",
        )
    )
    raw_first = next(
        row for row in clip_rows if row["variant"] == "roto_raw" and row["frame_number"] == "1"
    )
    corrected_first = next(
        row
        for row in clip_rows
        if row["variant"] == "roto_corrected" and row["frame_number"] == "1"
    )
    assert float(raw_first["soft_iou"].replace(",", ".")) == pytest.approx(
        447 / 511, abs=1e-6
    )
    assert corrected_first["soft_iou"] == "1,000000"
    assert progress[-1] == (100, "Analyse erfolgreich abgeschlossen.")
    assert "Abschlussstatus: erfolgreich" in (result.run_dir / "analysis_log.txt").read_text(
        encoding="utf-8"
    )


def test_same_minute_run_uses_deterministic_suffix_and_never_overwrites(project_factory):
    from rotomask_analyzer.analysis_service import AnalysisService

    project = project_factory()

    def fixed():
        return datetime(2026, 8, 26, 12, 34, tzinfo=UTC)

    service = AnalysisService(now=fixed)

    first = service.run(project, DEFAULT_CONFIG)
    second = service.run(project, DEFAULT_CONFIG)

    assert first.run_dir.name == "2026-08-26_1234"
    assert second.run_dir.name == "2026-08-26_1234_02"
    assert (first.run_dir / "analysis_manifest.json").is_file()
    assert (second.run_dir / "analysis_manifest.json").is_file()


def test_variant_specific_filenames_are_written_to_frame_metrics(project_factory):
    from rotomask_analyzer.analysis_service import AnalysisService

    project = project_factory(frames=())
    clip = project / "clip_01"
    for frame_number in (0, 1):
        write_rgba_mask(clip / "manual" / f"clip_02_manual_{frame_number:05d}.png")
        write_rgba_mask(clip / "roto_raw" / f"clip_02_roto_raw_{frame_number:05d}.png")
        write_rgba_mask(
            clip / "roto_corrected" / f"clip_02_roto_corrected_{frame_number:05d}.png"
        )
    service = AnalysisService(now=lambda: datetime(2026, 8, 29, 12, 0, tzinfo=UTC))

    result = service.run(project, DEFAULT_CONFIG)

    with (result.run_dir / "clip_01/frame_metrics.csv").open(
        encoding="utf-8-sig", newline=""
    ) as source:
        rows = list(csv.DictReader(source, delimiter=";"))
    filenames = {(row["variant"], row["frame_number"]): row["filename"] for row in rows}
    assert filenames == {
        ("roto_raw", "0"): "clip_02_roto_raw_00000.png",
        ("roto_raw", "1"): "clip_02_roto_raw_00001.png",
        ("roto_corrected", "0"): "clip_02_roto_corrected_00000.png",
        ("roto_corrected", "1"): "clip_02_roto_corrected_00001.png",
    }
