"""Complete project validation and report generation."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from .config import ConfigError, load_config
from .discovery import DiscoveryError, discover_clips, discover_frames
from .domain import ClipValidation, ValidationIssue, ValidationResult
from .mask_io import MaskFormatError, read_mask


def validate_project(
    project_path: Path,
    *,
    progress_callback: Callable[[int, str], None] | None = None,
) -> ValidationResult:
    project_path = Path(project_path)
    report_progress = progress_callback or (lambda _percent, _message: None)
    report_progress(0, "Projektstruktur wird geprüft …")
    now = datetime.now().astimezone()
    if not project_path.is_dir():
        issue = ValidationIssue(
            "project_not_found", f"Projektordner nicht gefunden: {project_path}"
        )
        result = ValidationResult(project_path, project_path.name, now, [], [issue], None)
        report_progress(100, "Validierung abgeschlossen: ungültig.")
        return result

    issues: list[ValidationIssue] = []
    clip_results: list[ClipValidation] = []
    config = None
    migration_notes: list[str] = []
    try:
        config = load_config(
            project_path / "project_config.json",
            create_if_missing=True,
            on_migration=migration_notes.append,
        )
        issues.extend(
            ValidationIssue("config_migrated", note, severity="warning")
            for note in migration_notes
        )
    except ConfigError as exc:
        issues.append(ValidationIssue("invalid_config", str(exc)))

    try:
        clips = discover_clips(project_path)
    except (DiscoveryError, OSError) as exc:
        code = exc.code if isinstance(exc, DiscoveryError) else "project_unreadable"
        issues.append(ValidationIssue(code, str(exc)))
        result = ValidationResult(project_path, project_path.name, now, [], issues, config)
        write_validation_report(result)
        report_progress(100, "Validierung abgeschlossen: ungültig.")
        return result

    variants = ("manual", "roto_raw", "roto_corrected")
    total_masks = sum(
        1
        for clip in clips
        for variant in variants
        if (clip.path / variant).is_dir()
        for path in (clip.path / variant).iterdir()
        if path.is_file() and path.suffix.lower() == ".png"
    )
    processed_masks = 0
    for clip in clips:
        clip_result = ClipValidation(clip.clip_id)
        try:
            frames = discover_frames(clip.path)
            clip_result.frame_count = len(frames)
        except (DiscoveryError, OSError) as exc:
            code = exc.code if isinstance(exc, DiscoveryError) else "clip_unreadable"
            issue = ValidationIssue(code, str(exc), clip_id=clip.clip_id)
            clip_result.issues.append(issue)
            issues.append(issue)
            clip_results.append(clip_result)
            continue

        resolutions: set[tuple[int, int]] = set()
        bit_depths: set[str] = set()
        for frame in frames:
            frame_sizes: dict[str, tuple[int, int]] = {}
            for variant, path in frame.paths.items():
                percent = int(processed_masks / max(total_masks, 1) * 99)
                report_progress(
                    percent,
                    f"{clip.clip_id} – Frame {frame.number} – {variant} – {path.name}",
                )
                try:
                    mask = read_mask(path)
                    height, width = mask.alpha.shape
                    frame_sizes[variant] = (width, height)
                    bit_depths.add(f"{mask.bit_depth}-bit")
                except MaskFormatError as exc:
                    issue = ValidationIssue(
                        exc.code,
                        str(exc),
                        clip_id=clip.clip_id,
                        filename=path.name,
                        frame_number=frame.number,
                    )
                    clip_result.issues.append(issue)
                    issues.append(issue)
                finally:
                    processed_masks += 1
            if frame_sizes and len(set(frame_sizes.values())) > 1:
                details = ", ".join(
                    f"{name}={frame.filenames[name]} ({size[0]}x{size[1]})"
                    for name, size in frame_sizes.items()
                )
                issue = ValidationIssue(
                    "resolution_mismatch",
                    f"Auflösungen weichen in Frame {frame.number} ab: {details}",
                    clip_id=clip.clip_id,
                    filename=frame.filename,
                    frame_number=frame.number,
                )
                clip_result.issues.append(issue)
                issues.append(issue)
            elif len(frame_sizes) == len(frame.paths):
                resolutions.add(next(iter(frame_sizes.values())))
        clip_result.resolutions = sorted(resolutions)
        clip_result.bit_depths = sorted(bit_depths)
        clip_results.append(clip_result)

    result = ValidationResult(
        project_path=project_path,
        project_name=project_path.name,
        validated_at=now,
        clips=clip_results,
        issues=issues,
        config=config,
    )
    write_validation_report(result)
    state = "gültig" if result.valid else "ungültig"
    report_progress(100, f"Validierung abgeschlossen: {state}.")
    return result


def write_validation_report(result: ValidationResult) -> Path:
    report_path = result.project_path / "validation_report.txt"
    lines = [
        "RotoMaskAnalyzer – Validierungsbericht",
        f"Prüfzeitpunkt: {result.validated_at.isoformat()}",
        f"Projektpfad: {result.project_path}",
        f"Erkannte Clips: {', '.join(clip.clip_id for clip in result.clips) or '-'}",
        "Geprüfte Pflichtordner: manual, roto_raw, roto_corrected",
        "",
    ]
    for clip in result.clips:
        resolutions = ", ".join(f"{w}x{h}" for w, h in clip.resolutions) or "-"
        bit_depths = ", ".join(clip.bit_depths) or "-"
        state = "gültig" if clip.valid else "ungültig"
        lines.append(
            f"{clip.clip_id}: {state}; Frames={clip.frame_count}; "
            f"Auflösungen={resolutions}; Masken-Bittiefen={bit_depths}"
        )
    lines.extend(["", "Konfiguration:"])
    if result.config is None:
        lines.append("- ungültig oder nicht verfügbar")
    else:
        lines.append(f"- schema_version={result.config['schema_version']}")
        for name, value in result.config["problem_frame_thresholds"].items():
            lines.append(f"- {name}={value}")
    lines.extend(["", f"Gesamtstatus: {'GÜLTIG' if result.valid else 'UNGÜLTIG'}", "Meldungen:"])
    if not result.issues:
        lines.append("- keine")
    for issue in result.issues:
        context = "/".join(
            value
            for value in (
                issue.clip_id,
                str(issue.frame_number) if issue.frame_number is not None else None,
                issue.filename,
            )
            if value
        )
        prefix = f" [{context}]" if context else ""
        lines.append(f"- {issue.severity.upper()} {issue.code}{prefix}: {issue.message}")
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report_path
