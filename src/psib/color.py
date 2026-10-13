"""Colour space utilities. All images are RGB, uint8, shape (H, W, 3)."""
from __future__ import annotations

import cv2
import numpy as np
from skimage.color import rgb2hsv


def to_gray(rgb: np.ndarray) -> np.ndarray:
    """ITU-R 601 luma: Y = 0.299 R + 0.587 G + 0.114 B (uint8)."""
    return cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)


def split_channels(rgb: np.ndarray):
    """Return the R, G, B planes as separate 2-D uint8 arrays."""
    return rgb[..., 0], rgb[..., 1], rgb[..., 2]


def rgb_to_hsv(rgb: np.ndarray):
    """Return H (degrees, 0-360), S (0-1), V (0-1) as float arrays."""
    hsv = rgb2hsv(rgb)
    return hsv[..., 0] * 360.0, hsv[..., 1], hsv[..., 2]
