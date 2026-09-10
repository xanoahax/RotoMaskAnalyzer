"""Append-only analysis run logging."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path


class RunLogger:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, message: str) -> None:
        timestamp = datetime.now().astimezone().isoformat(timespec="seconds")
        with self.path.open("a", encoding="utf-8", newline="") as output:
            output.write(f"{timestamp} {message}\n")
