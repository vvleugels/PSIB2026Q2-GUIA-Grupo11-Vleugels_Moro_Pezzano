"""Spatial smoothing filters (uint8 in, uint8 out)."""
from __future__ import annotations

import cv2
import numpy as np


def mean_filter(img: np.ndarray, k: int) -> np.ndarray:
    return cv2.blur(img, (k, k))


def median_filter(img: np.ndarray, k: int) -> np.ndarray:
    if k % 2 == 0:
        raise ValueError("median kernel size must be odd")
    return cv2.medianBlur(img, k)


def gaussian_filter(img: np.ndarray, sigma: float) -> np.ndarray:
    """Gaussian smoothing; kernel size is derived from sigma by OpenCV."""
    return cv2.GaussianBlur(img, (0, 0), sigma)


def apply_named_filter(img: np.ndarray, name: str, k: int = 5, sigma: float = 1.5) -> np.ndarray:
    """Dispatch by name: 'mean' | 'median' | 'gaussian'."""
    if name == "mean":
        return mean_filter(img, k)
    if name == "median":
        return median_filter(img, k)
    if name == "gaussian":
        return gaussian_filter(img, sigma)
    raise ValueError(f"Unknown filter: {name!r}")
