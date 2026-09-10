"""Keep the bundled PySide6 directory in Windows' DLL search path."""

from __future__ import annotations

import os
import sys
from pathlib import Path

_qt_dll_directory = None

if sys.platform == "win32" and hasattr(sys, "_MEIPASS"):
    _qt_dll_directory = os.add_dll_directory(
        str(Path(sys._MEIPASS) / "PySide6")
    )
