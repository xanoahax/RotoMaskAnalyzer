"""Single-window user interface."""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QThread
from PySide6.QtWidgets import (
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ..analysis_service import AnalysisService
from ..validation import validate_project
from ..worker import AnalysisWorker, ValidationWorker


class MainWindow(QMainWindow):
    def __init__(
        self,
        *,
        service_factory: Callable[[], object] = AnalysisService,
        validator: Callable = validate_project,
    ):
        super().__init__()
        self._service_factory = service_factory
        self._validator = validator
        self._project_path: Path | None = None
        self._last_validation = None
        self._result_dir: Path | None = None
        self._thread: QThread | None = None
        self._worker: AnalysisWorker | None = None
        self._validation_thread: QThread | None = None
        self._validation_worker: ValidationWorker | None = None
        self.setWindowTitle("RotoMaskAnalyzer")
        self.resize(760, 660)
        self._build_ui()
        self._set_initial_state()

    def _build_ui(self) -> None:
        central = QWidget(self)
        layout = QVBoxLayout(central)

        project_row = QHBoxLayout()
        self.choose_button = QPushButton("Projektordner auswählen")
        self.project_label = QLabel("Kein Projekt ausgewählt")
        self.project_label.setWordWrap(True)
        project_row.addWidget(self.choose_button)
        project_row.addWidget(self.project_label, 1)
        layout.addLayout(project_row)

        thresholds_box = QGroupBox("Schwellenwerte")
        thresholds_layout = QFormLayout(thresholds_box)
        self.threshold_inputs: dict[str, QDoubleSpinBox] = {}
        threshold_definitions = [
            ("soft_iou_below", "Problemframe: Soft IoU unter", 0.0, 1.0, 0.70),
            (
                "soft_iou_change_above",
                "Problemframe: Soft-IoU-Änderung über",
                0.0,
                1.0,
                0.10,
            ),
        ]
        for name, label, minimum, maximum, default in threshold_definitions:
            spin = QDoubleSpinBox()
            spin.setObjectName(name)
            spin.setDecimals(6)
            spin.setRange(minimum, maximum)
            spin.setSingleStep(0.01)
            spin.setValue(default)
            thresholds_layout.addRow(label, spin)
            self.threshold_inputs[name] = spin
        layout.addWidget(thresholds_box)
        self.thresholds_box = thresholds_box

        layout.addWidget(QLabel("Validierungs-Live-Log"))
        self.validation_list = QTextEdit()
        self.validation_list.setReadOnly(True)
        self.validation_list.setMinimumHeight(180)
        layout.addWidget(self.validation_list)

        self.start_button = QPushButton("Analyse starten")
        layout.addWidget(self.start_button)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        layout.addWidget(self.progress_bar)
        self.status_label = QLabel("Bitte Projektordner auswählen.")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)
        action_row = QHBoxLayout()
        self.cancel_button = QPushButton("Analyse abbrechen")
        self.open_results_button = QPushButton("Ergebnisordner öffnen")
        action_row.addWidget(self.cancel_button)
        action_row.addWidget(self.open_results_button)
        layout.addLayout(action_row)
        self.setCentralWidget(central)

        self.choose_button.clicked.connect(self._choose_project)
        self.start_button.clicked.connect(self.start_analysis)
        self.cancel_button.clicked.connect(self.cancel_analysis)
        self.open_results_button.clicked.connect(self.open_results)

    def _set_initial_state(self) -> None:
        self.start_button.setEnabled(False)
        self.cancel_button.setEnabled(False)
        self.open_results_button.setEnabled(False)
        self.progress_bar.setValue(0)

    def _choose_project(self) -> None:
        selected = QFileDialog.getExistingDirectory(self, "Projektordner auswählen")
        if selected:
            self.select_project(Path(selected))

    def select_project(self, project_path: Path) -> None:
        if self._thread is not None or self._validation_thread is not None:
            return
        self._project_path = Path(project_path)
        self._result_dir = None
        self.open_results_button.setEnabled(False)
        self.project_label.setText(str(self._project_path))
        self.status_label.setText("Projekt wird validiert …")
        self.validation_list.clear()
        self.choose_button.setEnabled(False)
        self.start_button.setEnabled(False)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        thread = QThread(self)
        worker = ValidationWorker(self._validator, self._project_path)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.progress.connect(self._on_validation_progress)
        worker.succeeded.connect(self._on_validation_succeeded)
        worker.failed.connect(self._on_validation_failed)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(self._validation_thread_finished)
        thread.finished.connect(thread.deleteLater)
        self._validation_thread = thread
        self._validation_worker = worker
        thread.start()

    def _on_validation_progress(self, percent: int, message: str) -> None:
        self.progress_bar.setValue(percent)
        self.status_label.setText(message)
        self.validation_list.append(f"{percent}% | {message}")

    def _on_validation_succeeded(self, result: object) -> None:
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(100)
        self._last_validation = result
        if result.config is not None:
            self._load_thresholds(result.config)
        lines = []
        for clip in result.clips:
            symbol = "✓" if clip.valid else "✗"
            lines.append(f"{clip.clip_id}   {symbol} {'gültig' if clip.valid else 'ungültig'}")
            for issue in clip.issues:
                lines.append(f"  - {issue.code}: {issue.message}")
        clip_issue_ids = {id(issue) for clip in result.clips for issue in clip.issues}
        for issue in result.issues:
            if id(issue) not in clip_issue_ids:
                lines.append(f"✗ {issue.code}: {issue.message}")
        summary = "\n".join(lines) or "Keine gültigen Clips erkannt."
        self.validation_list.append(f"\nErgebnis\n{summary}")
        self.start_button.setEnabled(result.valid)
        self.status_label.setText("Projekt gültig." if result.valid else "Projekt ungültig.")

    def _on_validation_failed(self, message: str) -> None:
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self._last_validation = None
        self.validation_list.setPlainText(f"✗ validation_failed: {message}")
        self.start_button.setEnabled(False)
        self.status_label.setText(f"Projektvalidierung fehlgeschlagen: {message}")

    def _validation_thread_finished(self) -> None:
        self._validation_thread = None
        self._validation_worker = None
        self.choose_button.setEnabled(True)

    def _load_thresholds(self, config: dict) -> None:
        for name, value in config["problem_frame_thresholds"].items():
            self.threshold_inputs[name].setValue(value)

    def _current_config(self) -> dict:
        return {
            "schema_version": "2.0",
            "problem_frame_thresholds": {
                name: self.threshold_inputs[name].value()
                for name in ("soft_iou_below", "soft_iou_change_above")
            },
        }

    def start_analysis(self) -> None:
        if (
            self._project_path is None
            or self._thread is not None
            or not self.start_button.isEnabled()
        ):
            return
        self._result_dir = None
        self.progress_bar.setValue(0)
        self.status_label.setText("Analyse wird gestartet …")
        self.choose_button.setEnabled(False)
        self.thresholds_box.setEnabled(False)
        self.start_button.setEnabled(False)
        self.cancel_button.setEnabled(True)
        self.open_results_button.setEnabled(False)

        thread = QThread(self)
        worker = AnalysisWorker(self._service_factory(), self._project_path, self._current_config())
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.progress.connect(self._on_progress)
        worker.succeeded.connect(self._on_success)
        worker.cancelled.connect(self._on_cancelled)
        worker.failed.connect(self._on_failed)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(self._thread_finished)
        thread.finished.connect(thread.deleteLater)
        self._thread = thread
        self._worker = worker
        thread.start()

    def cancel_analysis(self) -> None:
        if self._worker is not None:
            self.cancel_button.setEnabled(False)
            self.status_label.setText("Analyse wird abgebrochen …")
            self._worker.cancel()

    def _on_progress(self, percent: int, status: str) -> None:
        self.progress_bar.setValue(percent)
        self.status_label.setText(status)

    def _on_success(self, run_dir: str) -> None:
        self._result_dir = Path(run_dir)
        self.progress_bar.setValue(100)
        self.status_label.setText("Analyse erfolgreich abgeschlossen.")
        self.open_results_button.setEnabled(True)
        self._restore_controls()

    def _on_cancelled(self, _log_path: str) -> None:
        self._result_dir = None
        self.status_label.setText("Analyse wurde abgebrochen.")
        self.open_results_button.setEnabled(False)
        self._restore_controls()

    def _on_failed(self, message: str, log_path: str) -> None:
        self._result_dir = None
        suffix = f" Log: {log_path}" if log_path else ""
        self.status_label.setText(f"Analyse fehlgeschlagen: {message}.{suffix}")
        self.open_results_button.setEnabled(False)
        self._restore_controls()

    def _restore_controls(self) -> None:
        self.choose_button.setEnabled(True)
        self.thresholds_box.setEnabled(True)
        self.cancel_button.setEnabled(False)
        self.start_button.setEnabled(bool(self._last_validation and self._last_validation.valid))

    def _thread_finished(self) -> None:
        self._thread = None
        self._worker = None

    def open_results(self) -> None:
        if self._result_dir is None:
            return
        try:
            os.startfile(self._result_dir)  # type: ignore[attr-defined]
        except OSError as exc:
            QMessageBox.critical(
                self, "Ergebnisordner", f"Ordner konnte nicht geöffnet werden: {exc}"
            )
