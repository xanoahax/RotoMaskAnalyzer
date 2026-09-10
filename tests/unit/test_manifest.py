import json
from datetime import UTC, datetime

from rotomask_analyzer.config import DEFAULT_CONFIG
from rotomask_analyzer.domain import ClipValidation, ValidationResult
from rotomask_analyzer.manifest import build_manifest, write_manifest


def test_manifest_schema_2_contains_only_soft_alpha_definitions(tmp_path):
    validation = ValidationResult(
        project_path=tmp_path / "MyProject",
        project_name="MyProject",
        validated_at=datetime(2026, 8, 26, 10, 0, tzinfo=UTC),
        clips=[ClipValidation("clip_01", frame_count=2)],
        issues=[],
        config=DEFAULT_CONFIG,
    )

    manifest = build_manifest(
        validation,
        DEFAULT_CONFIG,
        analyzed_at=datetime(2026, 8, 26, 10, 5, tzinfo=UTC),
        software_version="2.0.0",
    )

    assert manifest == {
        "schema_version": "2.0",
        "analysis_timestamp": "2026-08-26T10:05:00+00:00",
        "project_name": "MyProject",
        "clips": [{"clip_id": "clip_01", "frame_count": 2}],
        "thresholds": DEFAULT_CONFIG,
        "variants": ["manual", "roto_raw", "roto_corrected"],
        "metric_definitions": {
            "soft_iou": "sum(min(M, R)) / sum(max(M, R)); bei Union 0 gilt 1.0",
            "soft_iou_delta": "soft_iou(t) - soft_iou(t-1)",
            "soft_iou_change": "abs(soft_iou_delta)",
        },
        "problem_frames": {
            "rules": [
                "soft_iou < soft_iou_below",
                "soft_iou_change > soft_iou_change_above",
            ],
            "reason_codes": ["low_soft_iou", "high_soft_iou_change"],
        },
        "problem_sequence_rule": (
            "maximale Folge direkt aufeinanderfolgender problematischer Frame-Nummern "
            "pro Clip und Variante"
        ),
        "ground_truth_role": "manual dient als Ground Truth der Auswertung",
        "validation": {"status": "valid", "validated_at": "2026-08-26T10:00:00+00:00"},
        "software_version": "2.0.0",
    }

    serialized = json.dumps(manifest, ensure_ascii=False).lower()
    for obsolete in (
        "reference",
        "original",
        "mask_threshold",
        "false_positive",
        "false_negative",
        "binar",
    ):
        assert obsolete not in serialized

    path = tmp_path / "analysis_manifest.json"
    write_manifest(path, manifest)
    assert path.read_text(encoding="utf-8").endswith("\n")
