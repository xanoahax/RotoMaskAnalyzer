import copy
import json
import math

import pytest

from rotomask_analyzer.config import (
    DEFAULT_CONFIG,
    ConfigError,
    load_config,
    save_config,
    validate_config,
)

EXPECTED_CONFIG = {
    "schema_version": "2.0",
    "problem_frame_thresholds": {
        "soft_iou_below": 0.70,
        "soft_iou_change_above": 0.10,
    },
}


def test_defaults_are_schema_2_soft_iou_only():
    assert DEFAULT_CONFIG == EXPECTED_CONFIG


def test_missing_config_is_created_with_exact_defaults(tmp_path):
    config_path = tmp_path / "project_config.json"

    loaded = load_config(config_path, create_if_missing=True)

    assert loaded == EXPECTED_CONFIG
    assert json.loads(config_path.read_text(encoding="utf-8")) == loaded


def test_save_and_load_preserve_valid_config(tmp_path):
    config_path = tmp_path / "project_config.json"
    config = {
        "schema_version": "2.0",
        "problem_frame_thresholds": {
            "soft_iou_below": 0.8,
            "soft_iou_change_above": 0.2,
        },
    }

    save_config(config_path, config)

    assert load_config(config_path) == config
    assert config_path.read_text(encoding="utf-8").endswith("\n")


@pytest.mark.parametrize("name", ["soft_iou_below", "soft_iou_change_above"])
@pytest.mark.parametrize(
    ("value", "message"),
    [
        (True, "muss eine Zahl sein"),
        (math.nan, "muss endlich sein"),
        (math.inf, "muss endlich sein"),
        (-0.01, r"muss in \[0, 1\] liegen"),
        (1.01, r"muss in \[0, 1\] liegen"),
    ],
)
def test_thresholds_must_be_finite_unit_interval(name, value, message):
    config = copy.deepcopy(EXPECTED_CONFIG)
    config["problem_frame_thresholds"][name] = value

    with pytest.raises(ConfigError, match=message):
        validate_config(config)


@pytest.mark.parametrize(
    ("config", "message"),
    [
        ({}, "schema_version"),
        (
            {
                "schema_version": "1.0",
                "problem_frame_thresholds": EXPECTED_CONFIG["problem_frame_thresholds"],
            },
            "schema_version muss exakt 2.0 sein",
        ),
        (
            {
                "schema_version": "2.0",
                "problem_frame_thresholds": {
                    **EXPECTED_CONFIG["problem_frame_thresholds"],
                    "extra": 1,
                },
            },
            "Unbekannte Schlüssel",
        ),
    ],
)
def test_invalid_schema_is_rejected_with_concrete_reason(config, message):
    with pytest.raises(ConfigError, match=message):
        validate_config(config)


def test_exact_legacy_schema_is_migrated_and_reported(tmp_path):
    config_path = tmp_path / "project_config.json"
    config_path.write_text(
        json.dumps(
            {
                "mask_threshold": 0.5,
                "problem_frame_thresholds": {
                    "iou_below": 0.62,
                    "iou_change_above": 0.08,
                    "false_positive_ref_ratio_above": 0.15,
                    "false_negative_ref_ratio_above": 0.15,
                },
            }
        ),
        encoding="utf-8",
    )
    notes: list[str] = []

    loaded = load_config(config_path, on_migration=notes.append)

    assert loaded == {
        "schema_version": "2.0",
        "problem_frame_thresholds": {
            "soft_iou_below": 0.62,
            "soft_iou_change_above": 0.08,
        },
    }
    assert notes == ["project_config.json wurde von Schema 1 auf Schema 2.0 migriert."]
    assert json.loads(config_path.read_text(encoding="utf-8")) == loaded


def test_invalid_legacy_shared_values_fall_back_to_new_defaults(tmp_path):
    config_path = tmp_path / "project_config.json"
    config_path.write_text(
        json.dumps(
            {
                "mask_threshold": 0.5,
                "problem_frame_thresholds": {
                    "iou_below": 1.5,
                    "iou_change_above": "invalid",
                    "false_positive_ref_ratio_above": 0.15,
                    "false_negative_ref_ratio_above": 0.15,
                },
            }
        ),
        encoding="utf-8",
    )

    assert load_config(config_path) == EXPECTED_CONFIG


def test_invalid_json_is_reported(tmp_path):
    config_path = tmp_path / "project_config.json"
    config_path.write_text("{not json", encoding="utf-8")

    with pytest.raises(ConfigError, match="ungültiges JSON"):
        load_config(config_path)


def test_arbitrary_unknown_schema_is_not_migrated(tmp_path):
    config_path = tmp_path / "project_config.json"
    config_path.write_text(
        json.dumps({**EXPECTED_CONFIG, "extra": 1}),
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="Unbekannte Schlüssel"):
        load_config(config_path)
