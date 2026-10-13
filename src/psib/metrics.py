"""Image quality and descriptive metrics. Images are uint8 arrays with identical shapes."""
from __future__ import annotations

import cv2
import numpy as np
import pandas as pd
from skimage.metrics import peak_signal_noise_ratio, structural_similarity

from .intensity import histogram


def psnr(ref: np.ndarray, test: np.ndarray) -> float:
    """Peak signal-to-noise ratio in dB (8-bit data, peak = 255). inf if identical."""
    return float(peak_signal_noise_ratio(ref, test, data_range=255))


def ssim(ref: np.ndarray, test: np.ndarray) -> float:
    """Mean structural similarity (7x7 uniform window; channels averaged for colour)."""
    axis = -1 if ref.ndim == 3 else None
    return float(structural_similarity(ref, test, data_range=255, channel_axis=axis))


def compare(ref: np.ndarray, variants: dict[str, np.ndarray]) -> pd.DataFrame:
    """PSNR / SSIM of each variant against ``ref`` (rows = variants)."""
    rows = [{"variant": k, "PSNR_dB": psnr(ref, v), "SSIM": ssim(ref, v)} for k, v in variants.items()]
    return pd.DataFrame(rows).set_index("variant")


def entropy(gray: np.ndarray) -> float:
    """Shannon entropy of the gray-level histogram (bits/pixel)."""
    p = histogram(gray).astype(np.float64)
    p = p[p > 0] / p.sum()
    return float(-(p * np.log2(p)).sum())


def laplacian_variance(gray: np.ndarray) -> float:
    """Variance of the Laplacian: high for sharp or noisy images (used as an artefact indicator)."""
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def edge_strength(gray: np.ndarray, top_percent: float = 5.0) -> float:
    """Mean Sobel magnitude over the strongest ``top_percent``% of pixels
    (proxy for how well the main edges survive a filter)."""
    gx = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
    gy = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
    mag = np.hypot(gx, gy)
    thr = np.percentile(mag, 100.0 - top_percent)
    return float(mag[mag >= thr].mean())


def describe(gray: np.ndarray) -> dict:
    """Basic statistics of a gray image."""
    return {"mean": float(gray.mean()), "std": float(gray.std()),
            "min": int(gray.min()), "max": int(gray.max()), "entropy_bits": entropy(gray),
            "clipped_%": 100.0 * float(np.mean((gray == 0) | (gray == 255)))}
