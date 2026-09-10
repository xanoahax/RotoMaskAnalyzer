import sys
import tomllib
from pathlib import Path


def test_runtime_and_package_versions_are_consistent():
    from rotomask_analyzer.version import __version__

    package = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))

    assert __version__ == "2.2.1"
    assert package["project"]["version"] == __version__


def test_packaging_smoke_runs_complete_valid_project(project_factory):
    from rotomask_analyzer.app import run_packaging_smoke

    project = project_factory()

    exit_code = run_packaging_smoke(project)

    assert exit_code == 0
    run_dirs = list((project / "results").iterdir())
    assert len(run_dirs) == 1
    assert (run_dirs[0] / "analysis_manifest.json").is_file()


def test_packaging_smoke_rejects_invalid_project(project_factory):
    from rotomask_analyzer.app import run_packaging_smoke

    project = project_factory()
    (project / "clip_01/manual/frame_0002.png").unlink()

    assert run_packaging_smoke(project) == 2
    assert not (project / "results").exists()


def test_main_accepts_explicit_packaging_smoke_argument(monkeypatch, tmp_path):
    import rotomask_analyzer.app as app

    project = tmp_path / "smoke_project"
    observed: list[Path] = []

    monkeypatch.delenv("ROTOMASK_ANALYZER_PACKAGING_SMOKE_PROJECT", raising=False)
    monkeypatch.setattr(
        sys,
        "argv",
        ["RotoMaskAnalyzer.exe", "--packaging-smoke-project", str(project)],
    )
    monkeypatch.setattr(
        app,
        "run_packaging_smoke",
        lambda path: observed.append(path) or 0,
    )
    class UnexpectedGuiApplication:
        @staticmethod
        def instance():
            raise AssertionError("GUI-Pfad wurde gestartet")

    monkeypatch.setattr(app, "QApplication", UnexpectedGuiApplication)

    assert app.main() == 0
    assert observed == [project]
