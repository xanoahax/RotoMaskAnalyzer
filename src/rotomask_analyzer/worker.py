"""Qt worker that keeps analysis work away from the GUI thread."""

from __future__ import annotations

from pathlib import Path
from threading import Event
from typing import Any

from PySide6.QtCore import QObject, Signal, Slot

from .analysis_service import AnalysisCancelled, AnalysisFailed


class ValidationWorker(QObject):
    progress = Signal(int, str)
    succeeded = Signal(object)
    failed = Signal(str)
    finished = Signal()

    def __init__(self, validator: Any, project_path: Path):
        super().__init__()
        self._validator = validator
        self._project_path = Path(project_path)

    @Slot()
    def run(self) -> None:
        try:
            self.succeeded.emit(
                self._validator(
                    self._project_path,
                    progress_callback=self.progress.emit,
                )
            )
        except Exception as exc:  # safety boundary between validation and GUI
            self.failed.emit(f"{type(exc).__name__}: {exc}")
        finally:
            self.finished.emit()


class AnalysisWorker(QObject):
    progress = Signal(int, str)
    succeeded = Signal(str)
    cancelled = Signal(str)
    failed = Signal(str, str)
    finished = Signal()

    def __init__(self, service: Any, project_path: Path, config: dict[str, Any]):
        super().__init__()
        self._service = service
        self._project_path = Path(project_path)
        self._config = config
        self._cancel_event = Event()

    @Slot()
    def run(self) -> None:
        try:
            result = self._service.run(
                self._project_path,
                self._config,
                cancel_check=self._cancel_event.is_set,
                progress_callback=self.progress.emit,
            )
            self.succeeded.emit(str(result.run_dir))
        except AnalysisCancelled as exc:
            self.cancelled.emit(str(exc.run_dir / "analysis_log.txt"))
        except AnalysisFailed as exc:
            self.failed.emit(str(exc), str(exc.run_dir / "analysis_log.txt"))
        except Exception as exc:  # safety boundary between core and GUI
            self.failed.emit(f"{type(exc).__name__}: {exc}", "")
        finally:
            self.finished.emit()

    @Slot()
    def cancel(self) -> None:
        self._cancel_event.set()
