from time import perf_counter

import numpy as np
import png
import pytest
from conftest import write_rgba_mask
from PIL import Image

from rotomask_analyzer.mask_io import MaskFormatError, read_mask
from rotomask_analyzer.validation import validate_project


def _write_png16_rgba(path, rows):
    height = len(rows)
    width = len(rows[0]) // 4
    with path.open("wb") as output:
        png.Writer(
            width=width,
            height=height,
            greyscale=False,
            alpha=True,
            bitdepth=16,
        ).write(output, rows)


def test_rgba_uses_alpha_even_when_rgb_is_colored(tmp_path):
    path = tmp_path / "mask.png"
    Image.fromarray(
        np.array(
            [[[10, 20, 30, 0], [200, 2, 90, 128], [4, 5, 6, 255]]],
            dtype=np.uint8,
        ),
        mode="RGBA",
    ).save(path)

    mask = read_mask(path)

    np.testing.assert_allclose(mask.alpha, [[0.0, 128 / 255, 1.0]])
    assert mask.bit_depth == 8


def test_8_bit_1080p_mask_decodes_within_interactive_budget(tmp_path):
    path = tmp_path / "mask_1080p.png"
    rgba = np.zeros((1080, 1920, 4), dtype=np.uint8)
    rgba[:, :, :3] = (10, 20, 30)
    rgba[180:900, 500:1420, 3] = 255
    Image.fromarray(rgba, mode="RGBA").save(path)

    started_at = perf_counter()
    mask = read_mask(path)
    elapsed = perf_counter() - started_at

    assert elapsed < 0.25
    assert mask.alpha.shape == (1080, 1920)
    assert mask.alpha[500, 900] == 1.0


@pytest.mark.parametrize("alpha", [0, 255])
def test_uniform_alpha_is_used_without_rgb_fallback(tmp_path, alpha):
    path = tmp_path / f"uniform_{alpha}.png"
    Image.new("RGBA", (2, 1), (10, 20, 30, alpha)).save(path)

    np.testing.assert_allclose(read_mask(path).alpha, alpha / 255)


def test_16_bit_rgba_alpha_is_used_without_precision_loss(tmp_path):
    path = tmp_path / "rgba16.png"
    _write_png16_rgba(
        path,
        [[
            65535,
            0,
            1234,
            32767,
            1,
            2,
            3,
            32768,
            9,
            8,
            7,
            65535,
        ]],
    )

    mask = read_mask(path)

    assert mask.bit_depth == 16
    np.testing.assert_allclose(
        mask.alpha,
        [[32767 / 65535, 32768 / 65535, 1.0]],
    )


@pytest.mark.parametrize("mode", ["L", "LA", "RGB", "P"])
def test_every_non_rgba_layout_is_rejected(tmp_path, mode):
    path = tmp_path / f"{mode}.png"
    Image.new(mode, (2, 1)).save(path)

    with pytest.raises(MaskFormatError, match="RGBA") as raised:
        read_mask(path)

    assert raised.value.code == "mask_must_be_rgba"


def test_empty_and_full_manual_alpha_are_valid(project_factory):
    project = project_factory()
    write_rgba_mask(project / "clip_01/manual/frame_0001.png", alpha_value=0)
    write_rgba_mask(project / "clip_01/manual/frame_0002.png", alpha_value=255)
    write_rgba_mask(project / "clip_01/roto_raw/frame_0001.png", alpha_value=0)
    write_rgba_mask(project / "clip_01/roto_corrected/frame_0002.png", alpha_value=0)

    result = validate_project(project)

    assert result.valid
    assert not [issue for issue in result.issues if issue.severity == "error"]
