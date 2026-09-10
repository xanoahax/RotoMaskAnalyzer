"""Headless Soft-IoU timeline rendering."""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
from matplotlib import pyplot as plt  # noqa: E402

from .domain import FrameMetric, VariantSummary


def write_soft_iou_timeline(
    path: Path,
    clip_id: str,
    metrics: list[FrameMetric],
    summaries: list[VariantSummary],
    *,
    soft_iou_below: float,
) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    by_variant = {
        variant: sorted(
            (metric for metric in metrics if metric.variant == variant),
            key=lambda metric: metric.frame_number,
        )
        for variant in ("roto_raw", "roto_corrected")
    }
    summaries_by_variant = {summary.variant: summary for summary in summaries}
    figure, axes = plt.subplots(figsize=(10, 5.5), dpi=130)
    colors = {"roto_raw": "#d55e00", "roto_corrected": "#0072b2"}
    labels = {"roto_raw": "Roto Raw", "roto_corrected": "Roto Corrected"}
    for variant in ("roto_raw", "roto_corrected"):
        rows = by_variant[variant]
        axes.plot(
            [row.frame_number for row in rows],
            [row.soft_iou for row in rows],
            marker="o",
            linewidth=1.8,
            markersize=3,
            color=colors[variant],
            label=labels[variant],
        )
        problem_rows = [row for row in rows if row.is_problematic]
        axes.scatter(
            [row.frame_number for row in problem_rows],
            [row.soft_iou for row in problem_rows],
            marker="X",
            s=55,
            color=colors[variant],
            edgecolor="black",
            linewidth=0.5,
            zorder=3,
        )
    axes.axhline(
        soft_iou_below,
        color="#555555",
        linestyle="--",
        label=f"Soft-IoU-Schwelle {soft_iou_below:.2f}",
    )
    raw = summaries_by_variant["roto_raw"]
    corrected = summaries_by_variant["roto_corrected"]
    axes.set_title(
        f"{clip_id} – mittlere Soft IoU Raw {raw.mean_soft_iou:.3f}, "
        f"Corrected {corrected.mean_soft_iou:.3f}\n"
        f"Problemframes Raw {raw.problem_frame_count}, "
        f"Corrected {corrected.problem_frame_count}"
    )
    axes.set_xlabel("Frame-Nummer")
    axes.set_ylabel("Soft IoU")
    axes.set_ylim(0, 1)
    axes.grid(True, alpha=0.25)
    axes.legend()
    figure.tight_layout()
    try:
        figure.savefig(path, format="png")
    finally:
        plt.close(figure)
