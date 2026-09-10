from datetime import UTC, datetime

import pytest

from rotomask_analyzer.config import DEFAULT_CONFIG


def test_cancelled_run_leaves_only_log_and_marks_status(project_factory):
    from rotomask_analyzer.analysis_service import AnalysisCancelled, AnalysisService

    project = project_factory(frames=("f_0001.png", "f_0002.png", "f_0003.png"))
    checks = 0

    def cancel_check():
        nonlocal checks
        checks += 1
        return checks >= 4

    service = AnalysisService(now=lambda: datetime(2026, 8, 19, 13, 0, tzinfo=UTC))

    with pytest.raises(AnalysisCancelled) as raised:
        service.run(project, DEFAULT_CONFIG, cancel_check=cancel_check)

    run_dir = raised.value.run_dir
    assert [path.name for path in run_dir.iterdir()] == ["analysis_log.txt"]
    log = (run_dir / "analysis_log.txt").read_text(encoding="utf-8")
    assert "Abschlussstatus: abgebrochen" in log
    assert "Endzeit:" in log
