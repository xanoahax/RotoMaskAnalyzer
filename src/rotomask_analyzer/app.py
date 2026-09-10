"""GUI application entry point."""

import os
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from .analysis_service import AnalysisService, ValidationBlocked
from .config import ConfigError, load_config
from .gui.main_window import MainWindow


def main() -> int:
    smoke_project = os.environ.get("ROTOMASK_ANALYZER_PACKAGING_SMOKE_PROJECT")
    if len(sys.argv) == 3 and sys.argv[1] == "--packaging-smoke-project":
        smoke_project = sys.argv[2]
    if smoke_project:
        return run_packaging_smoke(Path(smoke_project))
    application = QApplication.instance() or QApplication(sys.argv)
    application.setApplicationName("RotoMaskAnalyzer")
    window = MainWindow()
    window.show()
    return application.exec()


def run_packaging_smoke(project_path: Path) -> int:
    """Exercise the bundled core without exposing a second product interface."""
    project_path = Path(project_path)
    try:
        config = load_config(project_path / "project_config.json", create_if_missing=True)
        AnalysisService().run(project_path, config)
    except (ConfigError, ValidationBlocked):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
