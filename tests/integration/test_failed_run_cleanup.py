from datetime import UTC, datetime

import pytest

from rotomask_analyzer.config import DEFAULT_CONFIG


def test_injected_unexpected_error_leaves_only_log_with_traceback(project_factory):
    from rotomask_analyzer.analysis_service import AnalysisFailed, AnalysisService

    project = project_factory()

    def fault(event):
        if event == "after_frame":
            raise RuntimeError("injected boom")

    service = AnalysisService(now=lambda: datetime(2026, 8, 19, 13, 1, tzinfo=UTC))

    with pytest.raises(AnalysisFailed) as raised:
        service.run(project, DEFAULT_CONFIG, fault_injector=fault)

    run_dir = raised.value.run_dir
    assert [path.name for path in run_dir.iterdir()] == ["analysis_log.txt"]
    log = (run_dir / "analysis_log.txt").read_text(encoding="utf-8")
    assert "Abschlussstatus: fehlgeschlagen" in log
    assert "RuntimeError: injected boom" in log
    assert "Traceback" in log
