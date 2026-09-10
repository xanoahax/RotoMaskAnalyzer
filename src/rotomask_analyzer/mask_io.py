"""Lossless four-channel RGBA PNG Alpha decoding.

Pillow provides the fast, sample-exact 8-bit path. PyPNG reads the header and
retains full precision for 16-bit RGB/RGBA PNGs, which Pillow converts to 8-bit.
RGB samples are ignored; only stored Alpha samples form the continuous mask.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import png
from PIL import Image


@dataclass(frozen=True)
class MaskData:
    alpha: np.ndarray
    bit_depth: int


class MaskFormatError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def read_mask(path: Path) -> MaskData:
    path = Path(path)
    try:
        with path.open("rb") as source:
            reader = png.Reader(file=source)
            reader.preamble()
            width = int(reader.width)
            height = int(reader.height)
            greyscale = bool(reader.greyscale)
            alpha_present = bool(reader.alpha)
            planes = int(reader.planes)
            bit_depth = int(reader.bitdepth)
            is_palette = bool(reader.colormap)
        if (
            is_palette
            or greyscale
            or not alpha_present
            or planes != 4
        ):
            raise MaskFormatError(
                "mask_must_be_rgba",
                f"Maske {path.name} muss eine vierkanalige RGBA-PNG sein.",
            )
        if bit_depth not in {8, 16}:
            raise MaskFormatError(
                "unsupported_mask_bit_depth",
                f"Maske {path.name} hat {bit_depth} Bit; erlaubt sind 8 oder 16 Bit.",
            )
        if bit_depth == 8:
            with Image.open(path) as image:
                samples = np.asarray(image, dtype=np.uint8)
            if samples.shape != (height, width, 4):
                raise MaskFormatError(
                    "mask_must_be_rgba",
                    f"Maske {path.name} muss eine vierkanalige RGBA-PNG sein.",
                )
        else:
            _, _, rows, _ = png.Reader(filename=str(path)).read()
            samples = np.vstack([np.asarray(row, dtype=np.uint16) for row in rows])
            samples = samples.reshape(height, width, 4)
    except MaskFormatError:
        raise
    except (OSError, ValueError, png.Error) as exc:
        raise MaskFormatError("unreadable_png", f"PNG nicht lesbar ({path}): {exc}") from exc

    maximum = float((1 << bit_depth) - 1)
    alpha = samples[:, :, 3].astype(np.float64) / maximum
    return MaskData(alpha=alpha, bit_depth=bit_depth)
