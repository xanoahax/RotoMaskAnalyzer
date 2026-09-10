"""Windows smoke test for the bundled one-file executable."""

from __future__ import annotations

import os
import subprocess
import tempfile
import time
from pathlib import Path

import numpy as np
from PIL import Image


def _create_project(root: Path, *, valid: bool) -> Path:
    project = root / ("valid_project" if valid else "invalid_project")
    for folder in ("manual", "roto_raw", "roto_corrected"):
        for frame in (0, 1):
            path = project / "clip_01" / folder / f"clip_01_{folder}_{frame:05d}.png"
            path.parent.mkdir(parents=True, exist_ok=True)
            data = np.zeros((6, 8, 4), dtype=np.uint8)
            data[:, :, :3] = (20, 40, 60)
            data[1:4, 2:6, 3] = 255
            Image.fromarray(data, mode="RGBA").save(path)
    original = project / "clip_01/original/clip_01_original_00000.png"
    original.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (8, 6), (20, 40, 60)).save(original)
    if not valid:
        (project / "clip_01/roto_raw/clip_01_roto_raw_00001.png").unlink()
    return project


def _bundled_runtime_environment() -> dict[str, str]:
    environment = os.environ.copy()
    environment.pop("PYTHONHOME", None)
    environment.pop("PYTHONPATH", None)
    windows_root = environment.get("SystemRoot", r"C:\Windows")
    environment["PATH"] = os.pathsep.join(
        [str(Path(windows_root) / "System32"), windows_root]
    )
    environment["QT_QPA_PLATFORM"] = "offscreen"
    return environment


def _run_core_smoke(executable: Path, project: Path, expected_code: int) -> None:
    environment = _bundled_runtime_environment()
    completed = subprocess.run(
        [str(executable), "--packaging-smoke-project", str(project)],
        env=environment,
        timeout=180,
        check=False,
    )
    if completed.returncode != expected_code:
        raise RuntimeError(
            f"EXE-Smoke-Test für {project.name}: Exitcode {completed.returncode}, "
            f"erwartet {expected_code}."
        )


def _terminate_process_tree(process: subprocess.Popen) -> None:
    subprocess.run(
        ["taskkill", "/PID", str(process.pid), "/T", "/F"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    process.wait(timeout=30)


def main() -> int:
    project_root = Path(__file__).resolve().parents[1]
    executable = project_root / "dist" / "RotoMaskAnalyzer.exe"
    if not executable.is_file():
        raise FileNotFoundError(f"EXE fehlt: {executable}")

    environment = _bundled_runtime_environment()
    process = subprocess.Popen([str(executable)], env=environment)
    time.sleep(5)
    if process.poll() is not None:
        raise RuntimeError(f"GUI-Start fehlgeschlagen; vorzeitiger Exitcode {process.returncode}.")
    _terminate_process_tree(process)

    with tempfile.TemporaryDirectory(prefix="rotomask_exe_smoke_") as temporary:
        root = Path(temporary)
        valid_project = _create_project(root, valid=True)
        invalid_project = _create_project(root, valid=False)
        _run_core_smoke(executable, valid_project, 0)
        run_dirs = list((valid_project / "results").iterdir())
        if len(run_dirs) != 1 or not (run_dirs[0] / "analysis_manifest.json").is_file():
            raise RuntimeError("Gültiger EXE-Smoke-Test erzeugte keinen vollständigen Lauf.")
        _run_core_smoke(executable, invalid_project, 2)
        if (invalid_project / "results").exists():
            raise RuntimeError("Ungültiges Projekt durfte keinen Ergebnisordner erzeugen.")
    print("EXE-Smoke-Test erfolgreich: GUI-Start, gültiges Projekt, ungültiges Projekt.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
