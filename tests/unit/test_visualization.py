from PIL import Image

from rotomask_analyzer import visualization
from rotomask_analyzer.aggregation import aggregate_variant
from rotomask_analyzer.domain import FrameMetric


def _metric(variant, frame, value, delta=None, problematic=False):
    return FrameMetric(
        clip_id="clip_01",
        variant=variant,
        frame_number=frame,
        filename=f"f{frame}.png",
        soft_iou=value,
        soft_iou_delta=delta,
        soft_iou_change=None if delta is None else abs(delta),
        is_problematic=problematic,
        problem_reasons=("low_soft_iou",) if problematic else (),
    )


def test_soft_iou_timeline_is_a_readable_nonempty_png(tmp_path):
    raw = [
        _metric("roto_raw", 1, 0.8),
        _metric("roto_raw", 2, 0.6, -0.2, True),
    ]
    corrected = [
        _metric("roto_corrected", 1, 0.9),
        _metric("roto_corrected", 2, 0.85, -0.05),
    ]
    path = tmp_path / "soft_iou_timeline.png"

    visualization.write_soft_iou_timeline(
        path,
        "clip_01",
        raw + corrected,
        [aggregate_variant(raw), aggregate_variant(corrected)],
        soft_iou_below=0.7,
    )

    with Image.open(path) as image:
        assert image.format == "PNG"
        assert image.width > 100 and image.height > 100
