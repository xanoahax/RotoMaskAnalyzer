import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
import pytest
from PIL import Image


def write_rgba_mask(
    path: Path,
    *,
    size: tuple[int, int] = (4, 3),
    alpha_value: int = 255,
    alpha: np.ndarray | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rgba = np.zeros((size[1], size[0], 4), dtype=np.uint8)
    rgba[:, :, :3] = (10, 20, 30)
    if alpha is None:
        rgba[:, :, 3] = alpha_value
    else:
        if alpha.shape != (size[1], size[0]):
            raise ValueError("Alpha-Testdaten passen nicht zur angegebenen Größe.")
        rgba[:, :, 3] = alpha
    Image.fromarray(rgba, mode="RGBA").save(path)


@pytest.fixture
def project_factory(tmp_path):
    def create(
        clips: tuple[str, ...] = ("clip_01",),
        frames: tuple[str, ...] = ("frame_0001.png", "frame_0002.png"),
        sizes: dict[str, tuple[int, int]] | None = None,
    ) -> Path:
        project = tmp_path / "ExampleProject"
        for clip_id in clips:
            size = (sizes or {}).get(clip_id, (4, 3))
            for folder in ("manual", "roto_raw", "roto_corrected"):
                for filename in frames:
                    write_rgba_mask(project / clip_id / folder / filename, size=size)
        return project

    return create
