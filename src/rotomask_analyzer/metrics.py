"""Pure per-frame Soft IoU and temporal metric functions."""

import numpy as np


def compute_soft_iou(manual: np.ndarray, roto: np.ndarray) -> float:
    manual = np.asarray(manual, dtype=np.float64)
    roto = np.asarray(roto, dtype=np.float64)
    if manual.shape != roto.shape:
        raise ValueError("Manuelle und Roto-Maske müssen dieselbe Form besitzen.")
    if manual.ndim != 2:
        raise ValueError("Alpha-Masken müssen zweidimensional sein.")
    if not np.isfinite(manual).all() or not np.isfinite(roto).all():
        raise ValueError("Alpha-Masken müssen ausschließlich endliche Werte enthalten.")
    if np.any((manual < 0) | (manual > 1)) or np.any((roto < 0) | (roto > 1)):
        raise ValueError("Alpha-Maskenwerte müssen in [0, 1] liegen.")

    soft_union = float(np.maximum(manual, roto).sum(dtype=np.float64))
    if soft_union == 0.0:
        return 1.0
    soft_intersection = float(np.minimum(manual, roto).sum(dtype=np.float64))
    return soft_intersection / soft_union


def temporal_metrics(soft_ious: list[float]) -> list[tuple[float | None, float | None]]:
    if not soft_ious:
        return []
    result: list[tuple[float | None, float | None]] = [(None, None)]
    for previous, current in zip(soft_ious, soft_ious[1:], strict=False):
        delta = round(float(current) - float(previous), 15)
        result.append((delta, abs(delta)))
    return result
