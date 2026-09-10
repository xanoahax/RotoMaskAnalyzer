"""Complete headless analysis orchestration."""

from __future__ import annotations

import shutil
import traceback
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from .aggregation import aggregate_variant, compare_correction
from .config import save_config
from .discovery import discover_clips, discover_frames
from .domain import FrameMetric
from .manifest import build_manifest, write_manifest
from .mask_io import read_mask
from .metrics import compute_soft_iou, temporal_metrics
from .outputs import (
    write_batch_summary,
    write_clip_summary,
    write_correction_summary,
    write_frame_metrics,
    write_problem_sequences,
)
from .problem_detection import build_problem_sequences, detect_problem_reasons
from .run_logging import RunLogger
from .validation import validate_project
from .version import __version__
from .visualization import write_soft_iou_timeline


@dataclass(frozen=True)
class AnalysisRunResult:
    status: str
    run_dir: Path


class AnalysisCancelled(RuntimeError):
    def __init__(self, run_dir: Path):
        super().__init__("Analyse wurde abgebrochen.")
        self.run_dir = run_dir


class AnalysisFailed(RuntimeError):
    def __init__(self, run_dir: Path, message: str):
        super().__init__(message)
        self.run_dir = run_dir


class ValidationBlocked(RuntimeError):
    """Raised when the mandatory safety revalidation fails."""


class _CancellationSignal(RuntimeError):
    pass


class AnalysisService:
    def __init__(self, *, now: Callable[[], datetime] | None = None):
        self.now = now or (lambda: datetime.now().astimezone())

    def run(
        self,
        project_path: Path,
        config: dict[str, Any],
        *,
        cancel_check: Callable[[], bool] | None = None,
        progress_callback: Callable[[int, str], None] | None = None,
        fault_injector: Callable[[str], None] | None = None,
    ) -> AnalysisRunResult:
        project_path = Path(project_path)
        save_config(project_path / "project_config.json", config)
        validation = validate_project(project_path)
        if not validation.valid:
            codes = ", ".join(issue.code for issue in validation.issues)
            raise ValidationBlocked(f"Projektvalidierung fehlgeschlagen: {codes}")

        started_at = self.now()
        run_dir = _allocate_run_directory(project_path / "results", started_at)
        temporary = run_dir / ".temporary"
        temporary.mkdir()
        logger = RunLogger(run_dir / "analysis_log.txt")
        logger.write(f"Startzeit: {started_at.isoformat()}")
        logger.write(f"Projektname: {project_path.name}")
        logger.write(f"Projektpfad: {project_path}")
        logger.write(f"Softwareversion: {__version__}")
        logger.write(f"Erkannte Clips: {', '.join(clip.clip_id for clip in validation.clips)}")
        logger.write(f"Konfiguration: {config}")
        logger.write("Validierungsstatus: gültig")

        cancel_check = cancel_check or (lambda: False)
        progress_callback = progress_callback or (lambda _percent, _status: None)
        fault_injector = fault_injector or (lambda _event: None)
        try:
            clips = discover_clips(project_path)
            total_pairs = sum(len(discover_frames(clip.path)) * 2 for clip in clips)
            completed_pairs = 0
            batch_rows = []
            for clip in clips:
                frames = discover_frames(clip.path)
                all_metrics: list[FrameMetric] = []
                metrics_by_variant: dict[str, list[FrameMetric]] = {}
                for variant in ("roto_raw", "roto_corrected"):
                    variant_metrics: list[FrameMetric] = []
                    scored_frames: list[tuple[object, float]] = []
                    for position, frame in enumerate(frames, start=1):
                        _raise_if_cancelled(cancel_check)
                        manual = read_mask(frame.paths["manual"]).alpha
                        roto = read_mask(frame.paths[variant]).alpha
                        scored_frames.append((frame, compute_soft_iou(manual, roto)))
                        completed_pairs += 1
                        status = f"{clip.clip_id} – Frame {position}/{len(frames)} – {variant}"
                        percent = min(95, int(completed_pairs / total_pairs * 95))
                        progress_callback(percent, status)
                        logger.write(f"Fortschritt: {percent}% – {status}")
                        fault_injector("after_frame")

                    temporal = temporal_metrics(
                        [soft_iou for _, soft_iou in scored_frames]
                    )
                    for (frame, soft_iou), (soft_iou_delta, soft_iou_change) in zip(
                        scored_frames, temporal, strict=True
                    ):
                        metric = FrameMetric(
                            clip_id=clip.clip_id,
                            variant=variant,
                            frame_number=frame.number,
                            filename=frame.filenames[variant],
                            soft_iou=soft_iou,
                            soft_iou_delta=soft_iou_delta,
                            soft_iou_change=soft_iou_change,
                        )
                        metric.problem_reasons = detect_problem_reasons(
                            metric, config["problem_frame_thresholds"]
                        )
                        metric.is_problematic = bool(metric.problem_reasons)
                        variant_metrics.append(metric)
                    metrics_by_variant[variant] = variant_metrics
                    all_metrics.extend(variant_metrics)

                _raise_if_cancelled(cancel_check)
                raw_summary = aggregate_variant(metrics_by_variant["roto_raw"])
                corrected_summary = aggregate_variant(metrics_by_variant["roto_corrected"])
                correction = compare_correction(raw_summary, corrected_summary)
                summaries = [raw_summary, corrected_summary]
                sequences = build_problem_sequences(metrics_by_variant["roto_raw"])
                sequences += build_problem_sequences(metrics_by_variant["roto_corrected"])
                clip_output = temporary / clip.clip_id
                _raise_if_cancelled(cancel_check)
                write_frame_metrics(clip_output / "frame_metrics.csv", all_metrics)
                _raise_if_cancelled(cancel_check)
                write_clip_summary(clip_output / "clip_summary.csv", summaries)
                _raise_if_cancelled(cancel_check)
                write_problem_sequences(clip_output / "problem_sequences.csv", sequences)
                _raise_if_cancelled(cancel_check)
                write_correction_summary(clip_output / "correction_summary.csv", correction)
                _raise_if_cancelled(cancel_check)
                write_soft_iou_timeline(
                    clip_output / "visualizations/soft_iou_timeline.png",
                    clip.clip_id,
                    all_metrics,
                    summaries,
                    soft_iou_below=config["problem_frame_thresholds"]["soft_iou_below"],
                )
                fault_injector("after_clip_outputs")
                batch_rows.append((raw_summary, corrected_summary, correction))

            _raise_if_cancelled(cancel_check)
            write_batch_summary(temporary / "batch_summary.csv", batch_rows)
            _raise_if_cancelled(cancel_check)
            manifest = build_manifest(
                validation,
                config,
                analyzed_at=self.now(),
                software_version=__version__,
            )
            write_manifest(temporary / "analysis_manifest.json", manifest)
            fault_injector("before_verification")
            _raise_if_cancelled(cancel_check)
            _verify_output_tree(temporary, [clip.clip_id for clip in clips])
            for child in temporary.iterdir():
                child.replace(run_dir / child.name)
            temporary.rmdir()
            ended_at = self.now()
            logger.write("Abschlussstatus: erfolgreich")
            logger.write(f"Endzeit: {ended_at.isoformat()}")
            progress_callback(100, "Analyse erfolgreich abgeschlossen.")
            return AnalysisRunResult("success", run_dir)
        except _CancellationSignal as exc:
            _cleanup_partial_run(run_dir)
            logger.write("Abschlussstatus: abgebrochen")
            logger.write(f"Endzeit: {self.now().isoformat()}")
            raise AnalysisCancelled(run_dir) from exc
        except Exception as exc:
            technical_traceback = traceback.format_exc()
            _cleanup_partial_run(run_dir)
            logger.write("Abschlussstatus: fehlgeschlagen")
            logger.write(f"Fehlertyp: {type(exc).__name__}")
            logger.write(f"Fehler: {exc}")
            logger.write(f"Technische Rückverfolgung:\n{technical_traceback}")
            logger.write(f"Endzeit: {self.now().isoformat()}")
            raise AnalysisFailed(run_dir, f"Analyse fehlgeschlagen: {exc}") from exc


def _allocate_run_directory(results_dir: Path, timestamp: datetime) -> Path:
    results_dir.mkdir(parents=True, exist_ok=True)
    base = timestamp.strftime("%Y-%m-%d_%H%M")
    candidate = results_dir / base
    suffix = 2
    while candidate.exists():
        candidate = results_dir / f"{base}_{suffix:02d}"
        suffix += 1
    candidate.mkdir()
    return candidate


def _raise_if_cancelled(cancel_check: Callable[[], bool]) -> None:
    if cancel_check():
        raise _CancellationSignal


def _cleanup_partial_run(run_dir: Path) -> None:
    for child in run_dir.iterdir():
        if child.name == "analysis_log.txt":
            continue
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()


def _verify_output_tree(root: Path, clip_ids: list[str]) -> None:
    expected_root = {"analysis_manifest.json", "batch_summary.csv", *clip_ids}
    actual_root = {item.name for item in root.iterdir()}
    if actual_root != expected_root:
        raise RuntimeError(f"Unvollständige Ergebnisstruktur: {actual_root} != {expected_root}")
    expected_clip = {
        "clip_summary.csv",
        "frame_metrics.csv",
        "problem_sequences.csv",
        "correction_summary.csv",
        "visualizations",
    }
    for clip_id in clip_ids:
        clip_root = root / clip_id
        actual_clip = {item.name for item in clip_root.iterdir()}
        if actual_clip != expected_clip:
            raise RuntimeError(f"Unvollständige Clip-Struktur für {clip_id}: {actual_clip}")
        timeline = clip_root / "visualizations/soft_iou_timeline.png"
        if not timeline.is_file() or timeline.stat().st_size == 0:
            raise RuntimeError(f"Timeline fehlt oder ist leer: {timeline}")
