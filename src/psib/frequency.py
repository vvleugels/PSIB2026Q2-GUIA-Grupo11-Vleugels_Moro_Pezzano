"""2-D Fourier analysis: spectra, magnitude/phase reconstruction, PSD, frequency-domain filters.

Frequencies are expressed in cycles/pixel, so the Nyquist limit is 0.5.
"""
from __future__ import annotations

import numpy as np
from .acceleration import fft2, ifft2


# ---------------------------------------------------------------- transform
def fft2c(gray: np.ndarray) -> np.ndarray:
    """Centred 2-D DFT (zero frequency in the middle)."""
    return np.fft.fftshift(fft2(gray.astype(np.float64)))


def ifft2c(F: np.ndarray) -> np.ndarray:
    """Inverse of :func:`fft2c` (real part)."""
    return ifft2(np.fft.ifftshift(F)).real


def log_magnitude(F: np.ndarray) -> np.ndarray:
    return np.log1p(np.abs(F))


def phase(F: np.ndarray) -> np.ndarray:
    return np.angle(F)


def recon_magnitude_only(F: np.ndarray) -> np.ndarray:
    """Inverse DFT keeping |F| and forcing phase = 0."""
    return ifft2c(np.abs(F))


def recon_phase_only(F: np.ndarray) -> np.ndarray:
    """Inverse DFT keeping the phase and forcing |F| = 1."""
    return ifft2c(np.exp(1j * np.angle(F)))


def recon_cross(F_magnitude: np.ndarray, F_phase: np.ndarray) -> np.ndarray:
    """Magnitude of one image combined with the phase of another (same size)."""
    if F_magnitude.shape != F_phase.shape:
        raise ValueError("Both spectra must have the same shape")
    return ifft2c(np.abs(F_magnitude) * np.exp(1j * np.angle(F_phase)))


# ---------------------------------------------------------------------- PSD
def freq_radius(shape) -> np.ndarray:
    """Radial frequency (cycles/pixel) of every bin of a centred spectrum."""
    h, w = shape
    fy = np.fft.fftshift(np.fft.fftfreq(h))
    fx = np.fft.fftshift(np.fft.fftfreq(w))
    FX, FY = np.meshgrid(fx, fy)
    return np.sqrt(FX ** 2 + FY ** 2)


def psd2d(gray: np.ndarray, window: bool = True) -> np.ndarray:
    """2-D power spectral density |F|^2 (mean removed, optional Hann window against leakage)."""
    g = gray.astype(np.float64)
    g = g - g.mean()
    h, w = g.shape
    win = np.outer(np.hanning(h), np.hanning(w)) if window else np.ones_like(g)
    F = fft2c(g * win)
    return np.abs(F) ** 2 / np.sum(win ** 2)


def radial_profile(P: np.ndarray, nbins: int | None = None):
    """Radially averaged spectrum. Returns (frequency in cycles/pixel, mean power)."""
    h, w = P.shape
    nb = nbins or min(h, w) // 2
    D = freq_radius(P.shape).ravel()
    edges = np.linspace(0.0, 0.5, nb + 1)
    idx = np.digitize(D, edges) - 1
    ok = (idx >= 0) & (idx < nb)
    sums = np.bincount(idx[ok], weights=P.ravel()[ok], minlength=nb)
    counts = np.bincount(idx[ok], minlength=nb)
    centers = 0.5 * (edges[:-1] + edges[1:])
    keep = counts > 0
    return centers[keep], sums[keep] / counts[keep]


# ------------------------------------------------------------------ filters
def lowpass_filter(shape, cutoff: float, kind: str = "gaussian", order: int = 2) -> np.ndarray:
    """Transfer function H(u, v) of a low-pass filter (kind: ideal | gaussian | butterworth)."""
    D = freq_radius(shape)
    if kind == "ideal":
        return (D <= cutoff).astype(np.float64)
    if kind == "gaussian":
        return np.exp(-(D ** 2) / (2.0 * cutoff ** 2))
    if kind == "butterworth":
        return 1.0 / (1.0 + (D / cutoff) ** (2 * order))
    raise ValueError(f"Unknown filter kind: {kind!r}")


def highpass_filter(shape, cutoff: float, kind: str = "gaussian", order: int = 2) -> np.ndarray:
    return 1.0 - lowpass_filter(shape, cutoff, kind, order)


def gaussian_lowpass_from_sigma(shape, sigma_px: float) -> np.ndarray:
    """Frequency response equivalent to a spatial Gaussian of std ``sigma_px`` pixels:
    H = exp(-2 pi^2 sigma^2 (u^2 + v^2))."""
    D = freq_radius(shape)
    return np.exp(-2.0 * np.pi ** 2 * sigma_px ** 2 * D ** 2)


def apply_freq_filter(gray: np.ndarray, H: np.ndarray) -> np.ndarray:
    """Filter in the frequency domain. Returns a float image (not clipped)."""
    return ifft2c(fft2c(gray) * H)
