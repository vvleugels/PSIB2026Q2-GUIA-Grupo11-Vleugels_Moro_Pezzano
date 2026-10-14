"""Prepare fonts for OpenCV's Qt windows using installed system fonts."""
import os
from pathlib import Path


def prepare_gui_fonts():
    """Replace a missing bundled Qt font directory before opening a window."""
    current = os.environ.get("QT_QPA_FONTDIR")
    if current and Path(current).is_dir():
        return
    for folder in (Path('/usr/share/fonts/truetype/dejavu'),
                   Path('/usr/share/fonts/truetype/liberation2')):
        if folder.is_dir() and any(folder.glob('*.ttf')):
            os.environ['QT_QPA_FONTDIR'] = str(folder)
            return
