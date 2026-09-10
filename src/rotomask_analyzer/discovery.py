"""Deterministic project, clip, and frame discovery."""

from __future__ import annotations

import re
from pathlib import Path

from .domain import ClipLocation, FrameSet


class DiscoveryError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def discover_clips(project_path: Path) -> list[ClipLocation]:
    project_path = Path(project_path)
    matches: list[ClipLocation] = []
    for child in project_path.iterdir():
        match = re.fullmatch(r"clip_(\d{2})", child.name)
        if child.is_dir() and match:
            matches.append(ClipLocation(child.name, int(match.group(1)), child))
    matches.sort(key=lambda item: item.number)
    if not matches or matches[0].number != 1:
        raise DiscoveryError("missing_clip_01", "Der Pflichtordner clip_01 fehlt.")
    actual = [clip.number for clip in matches]
    expected = list(range(1, len(matches) + 1))
    if actual != expected:
        raise DiscoveryError(
            "clip_number_gap",
            f"Clip-Nummerierung ist nicht lückenlos: gefunden {actual}, erwartet {expected}.",
        )
    return matches


def discover_frames(clip_path: Path) -> list[FrameSet]:
    clip_path = Path(clip_path)
    variants = ("manual", "roto_raw", "roto_corrected")
    missing = [name for name in variants if not (clip_path / name).is_dir()]
    if missing:
        raise DiscoveryError(
            "missing_required_folder",
            f"Fehlende Pflichtordner in {clip_path.name}: {', '.join(missing)}.",
        )

    files_by_number = {
        variant: _index_pngs_by_frame_number(clip_path / variant, variant)
        for variant in variants
    }
    baseline_numbers = set(files_by_number["manual"])
    if any(set(files) != baseline_numbers for files in files_by_number.values()):
        details = "; ".join(
            f"{name}={sorted(files)}" for name, files in files_by_number.items()
        )
        raise DiscoveryError(
            "png_filename_mismatch",
            f"PNG-Frame-Nummern stimmen nicht überein: {details}",
        )

    if len(baseline_numbers) < 2:
        raise DiscoveryError("too_few_frames", "Ein Clip muss mindestens zwei Frames enthalten.")
    sorted_numbers = sorted(baseline_numbers)
    expected = list(range(sorted_numbers[0], sorted_numbers[-1] + 1))
    if sorted_numbers != expected:
        raise DiscoveryError(
            "frame_number_gap",
            f"Frame-Nummerierung ist nicht lückenlos: gefunden {sorted_numbers}.",
        )
    return [
        FrameSet(
            number=number,
            filenames={
                variant: files_by_number[variant][number].name for variant in variants
            },
            paths={variant: files_by_number[variant][number] for variant in variants},
        )
        for number in sorted_numbers
    ]


def _is_png(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() == ".png"


def _index_pngs_by_frame_number(folder: Path, variant: str) -> dict[int, Path]:
    indexed: dict[int, Path] = {}
    for path in sorted(folder.iterdir(), key=lambda item: item.name.casefold()):
        if not _is_png(path):
            continue
        match = re.search(r"(\d+)\.png$", path.name, flags=re.IGNORECASE)
        if not match:
            raise DiscoveryError(
                "missing_frame_number",
                f"Keine terminale Frame-Nummer in {variant}/{path.name}.",
            )
        number = int(match.group(1))
        if number in indexed:
            raise DiscoveryError(
                "duplicate_frame_number",
                f"Doppelte Frame-Nummer {number} in {variant}: "
                f"{indexed[number].name}, {path.name}.",
            )
        indexed[number] = path
    return indexed
