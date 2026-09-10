import json

import pytest
from conftest import write_rgba_mask
from PIL import Image

from rotomask_analyzer.validation import validate_project


def test_valid_project_with_different_clip_resolutions_passes_and_writes_report(project_factory):
    project = project_factory(
        clips=("clip_01", "clip_02"),
        sizes={"clip_01": (4, 3), "clip_02": (8, 6)},
    )

    result = validate_project(project)

    assert result.valid
    assert [(clip.clip_id, clip.frame_count) for clip in result.clips] == [
        ("clip_01", 2),
        ("clip_02", 2),
    ]
    assert result.clips[0].resolutions == [(4, 3)]
    assert result.clips[1].resolutions == [(8, 6)]
    report = (project / "validation_report.txt").read_text(encoding="utf-8")
    assert "Gesamtstatus: GÜLTIG" in report
    assert "Geprüfte Pflichtordner: manual, roto_raw, roto_corrected" in report
    assert "schema_version=2.0" in report


def test_validation_reports_live_file_progress_in_order(project_factory):
    project = project_factory()
    progress = []

    try:
        result = validate_project(
            project,
            progress_callback=lambda percent, message: progress.append((percent, message)),
        )
    except TypeError as exc:
        pytest.fail(f"Validierung unterstützt keinen Fortschritts-Callback: {exc}")

    assert result.valid
    assert progress[0] == (0, "Projektstruktur wird geprüft …")
    file_messages = [message for _, message in progress if "frame_" in message]
    assert file_messages == [
        "clip_01 – Frame 1 – manual – frame_0001.png",
        "clip_01 – Frame 1 – roto_raw – frame_0001.png",
        "clip_01 – Frame 1 – roto_corrected – frame_0001.png",
        "clip_01 – Frame 2 – manual – frame_0002.png",
        "clip_01 – Frame 2 – roto_raw – frame_0002.png",
        "clip_01 – Frame 2 – roto_corrected – frame_0002.png",
    ]
    assert [percent for percent, _ in progress] == sorted(percent for percent, _ in progress)
    assert progress[-1] == (100, "Validierung abgeschlossen: gültig.")


def test_original_folder_is_completely_ignored(project_factory):
    project = project_factory()
    original = project / "clip_01/original/unmatched_9999.png"
    original.parent.mkdir()
    Image.new("L", (99, 99)).save(original)

    result = validate_project(project)

    assert result.valid
    report = (project / "validation_report.txt").read_text(encoding="utf-8")
    assert "unmatched_9999.png" not in report
    assert "Pflichtordner: original" not in report


def test_resolution_mismatch_blocks_project_and_reports_exact_file(project_factory):
    project = project_factory()
    changed = project / "clip_01/roto_raw/frame_0002.png"
    write_rgba_mask(changed, size=(5, 3))

    result = validate_project(project)

    assert not result.valid
    assert any(issue.code == "resolution_mismatch" for issue in result.issues)
    report = (project / "validation_report.txt").read_text(encoding="utf-8")
    assert "resolution_mismatch" in report
    assert "frame_0002.png" in report


def test_resolution_mismatch_lists_variant_specific_filenames(project_factory):
    project = project_factory(frames=())
    clip = project / "clip_01"
    for frame_number in (0, 1):
        write_rgba_mask(clip / "manual" / f"clip_02_manual_{frame_number:05d}.png")
        write_rgba_mask(clip / "roto_raw" / f"clip_02_roto_raw_{frame_number:05d}.png")
        write_rgba_mask(
            clip / "roto_corrected" / f"clip_02_roto_corrected_{frame_number:05d}.png"
        )
    write_rgba_mask(clip / "roto_raw/clip_02_roto_raw_00001.png", size=(5, 3))

    result = validate_project(project)

    assert not result.valid
    report = (project / "validation_report.txt").read_text(encoding="utf-8")
    assert "manual=clip_02_manual_00001.png" in report
    assert "roto_raw=clip_02_roto_raw_00001.png" in report
    assert "roto_corrected=clip_02_roto_corrected_00001.png" in report


def test_corrupt_png_blocks_project(project_factory):
    project = project_factory()
    corrupt = project / "clip_01/manual/frame_0001.png"
    corrupt.write_bytes(b"not a png")

    result = validate_project(project)

    assert not result.valid
    assert any(
        issue.code == "unreadable_png" and issue.filename == corrupt.name
        for issue in result.issues
    )


def test_non_rgba_png_blocks_project(project_factory):
    project = project_factory()
    changed = project / "clip_01/roto_corrected/frame_0001.png"
    Image.new("RGB", (4, 3), (1, 2, 3)).save(changed)

    result = validate_project(project)

    assert not result.valid
    assert any(issue.code == "mask_must_be_rgba" for issue in result.issues)


def test_legacy_config_is_migrated_as_visible_nonblocking_warning(project_factory):
    project = project_factory()
    legacy = {
        "mask_threshold": 0.5,
        "problem_frame_thresholds": {
            "iou_below": 0.62,
            "iou_change_above": 0.08,
            "false_positive_ref_ratio_above": 0.15,
            "false_negative_ref_ratio_above": 0.15,
        },
    }
    (project / "project_config.json").write_text(json.dumps(legacy), encoding="utf-8")

    result = validate_project(project)

    assert result.valid
    migration = [issue for issue in result.issues if issue.code == "config_migrated"]
    assert len(migration) == 1
    assert migration[0].severity == "warning"
    report = (project / "validation_report.txt").read_text(encoding="utf-8")
    assert "config_migrated" in report
    migrated = json.loads((project / "project_config.json").read_text(encoding="utf-8"))
    assert migrated["problem_frame_thresholds"]["soft_iou_below"] == 0.62


def test_missing_project_is_invalid_without_attempting_report_write(tmp_path):
    missing = tmp_path / "missing"

    result = validate_project(missing)

    assert not result.valid
    assert [issue.code for issue in result.issues] == ["project_not_found"]
    assert not (missing / "validation_report.txt").exists()


def test_discovery_error_is_returned_as_validation_issue(project_factory):
    project = project_factory(clips=("clip_01", "clip_03"))

    result = validate_project(project)

    assert not result.valid
    assert any(issue.code == "clip_number_gap" for issue in result.issues)
    assert "Gesamtstatus: UNGÜLTIG" in (project / "validation_report.txt").read_text(
        encoding="utf-8"
    )
