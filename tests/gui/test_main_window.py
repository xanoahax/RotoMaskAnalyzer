from pathlib import Path
from time import monotonic, sleep

from PySide6.QtCore import QTimer

from rotomask_analyzer.analysis_service import AnalysisCancelled, AnalysisFailed
from rotomask_analyzer.config import DEFAULT_CONFIG, save_config
from rotomask_analyzer.gui.main_window import MainWindow
from rotomask_analyzer.validation import validate_project


def select_and_wait(qtbot, window, project) -> None:
    window.select_project(project)
    qtbot.waitUntil(
        lambda: window.status_label.text() != "Projekt wird validiert …", timeout=5000
    )
    qtbot.waitUntil(window.choose_button.isEnabled, timeout=5000)


def test_initial_button_state(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)

    assert window.start_button.isEnabled() is False
    assert window.cancel_button.isEnabled() is False
    assert window.open_results_button.isEnabled() is False


def test_automatic_validation_lists_clip_status_and_controls_start(qtbot, project_factory):
    project = project_factory()
    window = MainWindow()
    qtbot.addWidget(window)

    select_and_wait(qtbot, window, project)

    assert window.start_button.isEnabled() is True
    assert "clip_01" in window.validation_list.toPlainText()
    assert "gültig" in window.validation_list.toPlainText()

    (project / "clip_01/roto_raw/frame_0002.png").unlink()
    select_and_wait(qtbot, window, project)

    assert window.start_button.isEnabled() is False
    assert "png_filename_mismatch" in window.validation_list.toPlainText()


def test_project_validation_does_not_block_the_gui_thread(qtbot, project_factory):
    project = project_factory()

    def slow_validator(project_path, *, progress_callback=None):
        sleep(0.25)
        return validate_project(project_path)

    window = MainWindow(validator=slow_validator)
    qtbot.addWidget(window)
    started_at = monotonic()

    window.select_project(project)

    assert monotonic() - started_at < 0.1
    assert window.status_label.text() == "Projekt wird validiert …"
    assert (window.progress_bar.minimum(), window.progress_bar.maximum()) == (0, 100)
    qtbot.waitUntil(lambda: window.status_label.text() == "Projekt gültig.", timeout=3000)
    qtbot.waitUntil(window.choose_button.isEnabled, timeout=3000)
    assert (window.progress_bar.minimum(), window.progress_bar.maximum()) == (0, 100)
    assert window.progress_bar.value() == 100
    assert window.start_button.isEnabled() is True


def test_validation_progress_is_visible_live_and_retained(qtbot, project_factory):
    project = project_factory()

    def reporting_validator(project_path, *, progress_callback):
        progress_callback(37, "clip_01 – Frame 1 – manual – frame_0001.png")
        sleep(0.25)
        return validate_project(project_path)

    window = MainWindow(validator=reporting_validator)
    qtbot.addWidget(window)

    window.select_project(project)

    qtbot.waitUntil(
        lambda: "frame_0001.png" in window.validation_list.toPlainText(), timeout=3000
    )
    assert window.progress_bar.value() == 37
    assert window.status_label.text() == "clip_01 – Frame 1 – manual – frame_0001.png"
    qtbot.waitUntil(lambda: window.status_label.text() == "Projekt gültig.", timeout=3000)
    assert "37% | clip_01 – Frame 1 – manual – frame_0001.png" in (
        window.validation_list.toPlainText()
    )
    assert "Ergebnis" in window.validation_list.toPlainText()


def test_background_validation_failure_restores_project_selection(qtbot, tmp_path):
    def failing_validator(_project_path, *, progress_callback=None):
        raise OSError("Testprojekt kann nicht gelesen werden")

    window = MainWindow(validator=failing_validator)
    qtbot.addWidget(window)

    window.select_project(tmp_path)

    qtbot.waitUntil(window.choose_button.isEnabled, timeout=3000)
    assert window.status_label.text() == (
        "Projektvalidierung fehlgeschlagen: OSError: Testprojekt kann nicht gelesen werden"
    )
    assert window.start_button.isEnabled() is False


def test_gui_exposes_exactly_two_soft_iou_thresholds(qtbot, project_factory):
    project = project_factory()
    config = {
        "schema_version": "2.0",
        "problem_frame_thresholds": {
            "soft_iou_below": 0.62,
            "soft_iou_change_above": 0.08,
        },
    }
    save_config(project / "project_config.json", config)
    window = MainWindow()
    qtbot.addWidget(window)

    select_and_wait(qtbot, window, project)

    assert set(window.threshold_inputs) == {"soft_iou_below", "soft_iou_change_above"}
    assert window.threshold_inputs["soft_iou_below"].value() == 0.62
    assert window.threshold_inputs["soft_iou_change_above"].value() == 0.08
    assert window._current_config() == config


def test_default_gui_config_matches_schema_2_defaults(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)

    assert window._current_config() == DEFAULT_CONFIG


def test_real_analysis_runs_in_background_updates_state_and_enables_result(qtbot, project_factory):
    project = project_factory()
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()
    select_and_wait(qtbot, window, project)
    heartbeat = []
    QTimer.singleShot(0, lambda: heartbeat.append("responsive"))

    window.start_button.click()

    qtbot.waitUntil(lambda: window.open_results_button.isEnabled(), timeout=15000)
    assert heartbeat == ["responsive"]
    assert window.progress_bar.value() == 100
    assert window.status_label.text() == "Analyse erfolgreich abgeschlossen."
    assert window.choose_button.isEnabled() is True
    assert window.cancel_button.isEnabled() is False


class _SlowCancellableService:
    def run(self, project_path, config, *, cancel_check, progress_callback):
        from time import sleep

        for value in range(1, 100):
            if cancel_check():
                raise AnalysisCancelled(Path(project_path) / "results/cancelled")
            progress_callback(value, f"simuliert {value}")
            sleep(0.005)
        raise AssertionError("Abbruchsignal wurde nicht verarbeitet")


def test_cancel_signal_is_processed_and_no_result_is_offered(qtbot, project_factory):
    project = project_factory()
    window = MainWindow(service_factory=_SlowCancellableService)
    qtbot.addWidget(window)
    select_and_wait(qtbot, window, project)
    window.start_button.click()
    qtbot.waitUntil(lambda: window.cancel_button.isEnabled(), timeout=2000)

    window.cancel_button.click()

    qtbot.waitUntil(
        lambda: window.status_label.text() == "Analyse wurde abgebrochen.", timeout=5000
    )
    assert window.open_results_button.isEnabled() is False
    assert window.start_button.isEnabled() is True


class _FailingService:
    def run(self, project_path, config, *, cancel_check, progress_callback):
        raise AnalysisFailed(Path(project_path) / "results/failed", "kaputt")


def test_worker_failure_shows_message_without_result_folder(qtbot, project_factory):
    project = project_factory()
    window = MainWindow(service_factory=_FailingService)
    qtbot.addWidget(window)
    select_and_wait(qtbot, window, project)

    window.start_button.click()

    qtbot.waitUntil(lambda: "fehlgeschlagen" in window.status_label.text(), timeout=5000)
    assert window.open_results_button.isEnabled() is False
    assert window.start_button.isEnabled() is True
