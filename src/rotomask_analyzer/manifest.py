"""Stable analysis manifest schema."""

import copy
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .domain import ValidationResult


def build_manifest(
    validation: ValidationResult,
    config: dict[str, Any],
    *,
    analyzed_at: datetime,
    software_version: str,
) -> dict[str, Any]:
    if not validation.valid:
        raise ValueError("Ein Manifest darf nur nach erfolgreicher Validierung entstehen.")
    return {
        "schema_version": "2.0",
        "analysis_timestamp": analyzed_at.isoformat(),
        "project_name": validation.project_name,
        "clips": [
            {"clip_id": clip.clip_id, "frame_count": clip.frame_count}
            for clip in validation.clips
        ],
        "thresholds": copy.deepcopy(config),
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
        "validation": {
            "status": "valid",
            "validated_at": validation.validated_at.isoformat(),
        },
        "software_version": software_version,
    }


def write_manifest(path: Path, manifest: dict[str, Any]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
