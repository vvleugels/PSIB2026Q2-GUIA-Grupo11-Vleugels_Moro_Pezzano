"""Spatial resolution (sampling) and amplitude resolution (quantisation)."""
from __future__ import annotations

import cv2
import numpy as np


def image_info(img: np.ndarray) -> dict:
    h, w = img.shape[:2]
    channels = 1 if img.ndim == 2 else img.shape[2]
    bits = img.dtype.itemsize * 8
    return {"width": w, "height": h, "channels": channels, "dtype": str(img.dtype),
            "bit_depth": bits, "gray_levels": 2 ** bits}


def downsample(img: np.ndarray, factor: float) -> np.ndarray:
    """Reduce resolution by ``factor`` (0.5 -> half the width and height). Area averaging."""
    h, w = img.shape[:2]
    size = (max(1, int(round(w * factor))), max(1, int(round(h * factor))))
    return cv2.resize(img, size, interpolation=cv2.INTER_AREA)


def upsample_to(small: np.ndarray, shape, nearest: bool = True) -> np.ndarray:
    """Bring a downsampled image back to ``shape`` (h, w). Nearest = show real pixels."""
    h, w = shape[:2]
    interp = cv2.INTER_NEAREST if nearest else cv2.INTER_LINEAR
    return cv2.resize(small, (w, h), interpolation=interp)


def quantize(img: np.ndarray, bits: int) -> np.ndarray:
    """Uniform requantisation to ``2**bits`` levels.

    The result is mapped back to the 0-255 range so it can be displayed and
    compared with the original (levels are spread evenly: 0 ... 255).
    """
    levels = 2 ** bits
    step = 256.0 / levels
    q = np.floor(img.astype(np.float64) / step)           # integer level 0 .. levels-1
    return np.rint(q * 255.0 / (levels - 1)).astype(np.uint8)
