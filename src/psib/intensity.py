"""Intensity transformations on gray images (uint8)."""
from __future__ import annotations

import cv2
import numpy as np


def histogram(gray: np.ndarray) -> np.ndarray:
    """Counts for the 256 gray levels."""
    return np.bincount(gray.ravel(), minlength=256)


def cdf_normalized(gray: np.ndarray) -> np.ndarray:
    h = histogram(gray).astype(np.float64)
    return np.cumsum(h) / h.sum()


def adjust_brightness(img: np.ndarray, offset: int) -> np.ndarray:
    """g = f + offset (saturated to 0-255)."""
    return np.clip(img.astype(np.int16) + int(offset), 0, 255).astype(np.uint8)


def adjust_contrast(img: np.ndarray, factor: float) -> np.ndarray:
    """g = factor * f (saturated to 0-255)."""
    return np.clip(np.rint(img.astype(np.float32) * factor), 0, 255).astype(np.uint8)


def clipped_fraction(img: np.ndarray) -> float:
    """Fraction of samples saturated at 0 or 255."""
    return float(np.mean((img == 0) | (img == 255)))


def percentile_range(gray: np.ndarray, p_low: float, p_high: float) -> tuple[float, float]:
    f1, f2 = np.percentile(gray, [p_low, p_high])
    return float(f1), float(f2)


def linear_range_scaling(gray: np.ndarray, f1: float, f2: float) -> np.ndarray:
    """Map [f1, f2] linearly onto [0, 255]; values outside are saturated."""
    if f2 <= f1:
        raise ValueError("f2 must be greater than f1")
    out = (gray.astype(np.float64) - f1) / (f2 - f1) * 255.0
    return np.clip(np.rint(out), 0, 255).astype(np.uint8)


def equalize_global(gray: np.ndarray) -> np.ndarray:
    return cv2.equalizeHist(gray)


def equalize_clahe(gray: np.ndarray, clip_limit: float = 2.0, tile_grid: int = 8) -> np.ndarray:
    clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=(tile_grid, tile_grid))
    return clahe.apply(gray)
