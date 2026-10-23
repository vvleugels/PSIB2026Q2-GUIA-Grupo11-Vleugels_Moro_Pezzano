"""Spatial smoothing filters (uint8 in, uint8 out)."""
from __future__ import annotations

import cv2
import numpy as np
from .acceleration import dispatch


def mean_filter(img: np.ndarray, k: int) -> np.ndarray:
    return dispatch('mean_filter', lambda: cv2.blur(img, (k, k)),
                    lambda: cv2.blur(cv2.UMat(img), (k, k)).get())


def median_filter(img: np.ndarray, k: int) -> np.ndarray:
    if k % 2 == 0:
        raise ValueError("median kernel size must be odd")
    return dispatch('median_filter', lambda: cv2.medianBlur(img, k),
                    lambda: cv2.medianBlur(cv2.UMat(img), k).get())


def gaussian_filter(img: np.ndarray, sigma: float) -> np.ndarray:
    """Gaussian smoothing; kernel size is derived from sigma by OpenCV."""
    return dispatch('gaussian_filter', lambda: cv2.GaussianBlur(img, (0, 0), sigma),
                    lambda: cv2.GaussianBlur(cv2.UMat(img), (0, 0), sigma).get())


def apply_named_filter(img: np.ndarray, name: str, k: int = 5, sigma: float = 1.5) -> np.ndarray:
    """Dispatch by name: 'mean' | 'median' | 'gaussian'."""
    if name == "mean":
        return mean_filter(img, k)
    if name == "median":
        return median_filter(img, k)
    if name == "gaussian":
        return gaussian_filter(img, sigma)
    raise ValueError(f"Unknown filter: {name!r}")
