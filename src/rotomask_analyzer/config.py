"""Project configuration contract and deterministic schema migration."""

from __future__ import annotations

import copy
import json
import math
from collections.abc import Callable
from contextlib import suppress
from pathlib import Path
from typing import Any

DEFAULT_CONFIG: dict[str, Any] = {
    "schema_version": "2.0",
    "problem_frame_thresholds": {
        "soft_iou_below": 0.70,
        "soft_iou_change_above": 0.10,
    },
}

LEGACY_TOP_KEYS = {"mask_threshold", "problem_frame_thresholds"}
LEGACY_THRESHOLD_KEYS = {
    "iou_below",
    "iou_change_above",
    "false_positive_ref_ratio_above",
    "false_negative_ref_ratio_above",
}


class ConfigError(ValueError):
    """Raised when a project configuration violates the fixed schema."""


def validate_config(config: object) -> dict[str, Any]:
    if not isinstance(config, dict):
        raise ConfigError("Die Konfiguration muss ein JSON-Objekt sein.")

    _require_exact_keys(
        config,
        {"schema_version", "problem_frame_thresholds"},
        "Konfiguration",
    )
    if config["schema_version"] != "2.0":
        raise ConfigError("schema_version muss exakt 2.0 sein.")

    thresholds = config["problem_frame_thresholds"]
    if not isinstance(thresholds, dict):
        raise ConfigError("problem_frame_thresholds muss ein JSON-Objekt sein.")
    expected_thresholds = {"soft_iou_below", "soft_iou_change_above"}
    _require_exact_keys(thresholds, expected_thresholds, "problem_frame_thresholds")

    normalized_thresholds = {
        name: _finite_number(thresholds[name], name) for name in sorted(expected_thresholds)
    }
    for name, value in normalized_thresholds.items():
        _require_unit_interval(value, name)
    return {
        "schema_version": "2.0",
        "problem_frame_thresholds": normalized_thresholds,
    }


def load_config(
    path: Path,
    *,
    create_if_missing: bool = False,
    on_migration: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    path = Path(path)
    if not path.exists():
        if not create_if_missing:
            raise ConfigError(f"Konfigurationsdatei fehlt: {path}")
        defaults = copy.deepcopy(DEFAULT_CONFIG)
        save_config(path, defaults)
        return defaults
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ConfigError(f"ungültiges JSON in {path.name}: {exc.msg}") from exc
    except OSError as exc:
        raise ConfigError(f"Konfiguration kann nicht gelesen werden: {exc}") from exc

    if _is_exact_legacy_schema(data):
        migrated = _migrate_legacy(data)
        save_config(path, migrated)
        if on_migration is not None:
            on_migration("project_config.json wurde von Schema 1 auf Schema 2.0 migriert.")
        return migrated
    return validate_config(data)


def save_config(path: Path, config: object) -> None:
    normalized = validate_config(config)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.temporary")
    try:
        temporary.write_text(
            json.dumps(normalized, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        temporary.replace(path)
    except OSError as exc:
        with suppress(OSError):
            temporary.unlink(missing_ok=True)
        raise ConfigError(f"Konfiguration kann nicht gespeichert werden: {exc}") from exc


def _is_exact_legacy_schema(data: object) -> bool:
    return (
        isinstance(data, dict)
        and set(data) == LEGACY_TOP_KEYS
        and isinstance(data.get("problem_frame_thresholds"), dict)
        and set(data["problem_frame_thresholds"]) == LEGACY_THRESHOLD_KEYS
    )


def _migrate_legacy(data: dict[str, Any]) -> dict[str, Any]:
    old = data["problem_frame_thresholds"]
    migrated = copy.deepcopy(DEFAULT_CONFIG)
    for old_name, new_name in (
        ("iou_below", "soft_iou_below"),
        ("iou_change_above", "soft_iou_change_above"),
    ):
        try:
            value = _finite_number(old[old_name], old_name)
            _require_unit_interval(value, old_name)
        except ConfigError:
            continue
        migrated["problem_frame_thresholds"][new_name] = value
    return migrated


def _require_exact_keys(mapping: dict[str, Any], expected: set[str], label: str) -> None:
    actual = set(mapping)
    missing = sorted(expected - actual)
    unknown = sorted(actual - expected)
    if missing:
        raise ConfigError(f"Fehlende Schlüssel in {label}: {', '.join(missing)}")
    if unknown:
        raise ConfigError(f"Unbekannte Schlüssel in {label}: {', '.join(unknown)}")


def _finite_number(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ConfigError(f"{name} muss eine Zahl sein.")
    number = float(value)
    if not math.isfinite(number):
        raise ConfigError(f"{name} muss endlich sein.")
    return number


def _require_unit_interval(value: float, name: str) -> None:
    if not 0.0 <= value <= 1.0:
        raise ConfigError(f"{name} muss in [0, 1] liegen.")
