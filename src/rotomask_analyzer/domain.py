"""Shared immutable domain records used by the analysis core."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ClipLocation:
    clip_id: str
    number: int
    path: Path


@dataclass(frozen=True)
class FrameSet:
    number: int
    filenames: dict[str, str]
    paths: dict[str, Path]

    @property
    def filename(self) -> str:
        """Return the manual filename for backwards-compatible diagnostics."""
        return self.filenames["manual"]


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    message: str
    clip_id: str | None = None
    filename: str | None = None
    frame_number: int | None = None
    severity: str = "error"


@dataclass
class ClipValidation:
    clip_id: str
    frame_count: int = 0
    resolutions: list[tuple[int, int]] = field(default_factory=list)
    bit_depths: list[str] = field(default_factory=list)
    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def valid(self) -> bool:
        return not any(issue.severity == "error" for issue in self.issues)


@dataclass
class ValidationResult:
    project_path: Path
    project_name: str
    validated_at: datetime
    clips: list[ClipValidation]
    issues: list[ValidationIssue]
    config: dict[str, Any] | None

    @property
    def valid(self) -> bool:
        return not any(issue.severity == "error" for issue in self.issues)


@dataclass
class FrameMetric:
    clip_id: str
    variant: str
    frame_number: int
    filename: str
    soft_iou: float
    soft_iou_delta: float | None
    soft_iou_change: float | None
    is_problematic: bool = False
    problem_reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class ProblemSequence:
    clip_id: str
    variant: str
    sequence_id: int
    start_frame: int
    end_frame: int
    length: int
    trigger_reasons: tuple[str, ...]
    min_soft_iou: float
    max_soft_iou_change: float | None


@dataclass(frozen=True)
class VariantSummary:
    clip_id: str
    variant: str
    frame_count: int
    mean_soft_iou: float
    median_soft_iou: float
    min_soft_iou: float
    max_soft_iou: float
    std_soft_iou: float
    mean_soft_iou_change: float | None
    max_soft_iou_change: float | None
    problem_frame_count: int
    problem_frame_ratio: float
    longest_problem_sequence: int


@dataclass(frozen=True)
class CorrectionSummary:
    clip_id: str
    mean_soft_iou_improvement: float
    problem_frame_reduction: int
    problem_frame_ratio_reduction: float
