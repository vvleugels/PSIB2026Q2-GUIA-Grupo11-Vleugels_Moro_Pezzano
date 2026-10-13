"""Synthetic noise models (uint8 in, uint8 out)."""
from __future__ import annotations

import numpy as np

from .utils import to_uint8


def add_gaussian_noise(img: np.ndarray, sigma: float, seed: int = 0) -> np.ndarray:
    """Additive zero-mean Gaussian noise, std ``sigma`` in gray levels."""
    rng = np.random.default_rng(seed)
    return to_uint8(img.astype(np.float64) + rng.normal(0.0, sigma, img.shape))


def add_salt_pepper(img: np.ndarray, amount: float, seed: int = 0) -> np.ndarray:
    """Impulsive noise: a fraction ``amount`` of the pixels set to 0 or 255 (half/half)."""
    rng = np.random.default_rng(seed)
    out = img.copy()
    r = rng.random(img.shape[:2])
    out[r < amount / 2] = 0
    out[r > 1 - amount / 2] = 255
    return out


def add_speckle(img: np.ndarray, sigma: float, seed: int = 0) -> np.ndarray:
    """Multiplicative noise: g = f + f * n,  n ~ N(0, sigma^2)."""
    rng = np.random.default_rng(seed)
    f = img.astype(np.float64)
    return to_uint8(f + f * rng.normal(0.0, sigma, img.shape))
