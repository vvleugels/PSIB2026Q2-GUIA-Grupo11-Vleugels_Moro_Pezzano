"""Quick estimate of the light-stimulus time from the global brightness of the video."""
from __future__ import annotations

import numpy as np
from scipy.ndimage import uniform_filter1d


def detect_stimulus_onset(t: np.ndarray, brightness: np.ndarray, kind: str, smooth_frames: int = 5) -> dict:
    """Time of the largest brightness step.

    kind 'A' (dark -> light): largest positive derivative.
    kind 'B' (light -> dark): largest negative derivative.
    This is only a *preview* for sanity-checking the recordings: camera
    auto-exposure also changes the global brightness, so the definitive
    stimulus time should be confirmed on the images (Module 3).
    """
    b = uniform_filter1d(np.asarray(brightness, dtype=float), size=max(1, smooth_frames), mode="nearest")
    db = np.gradient(b, t)
    i = int(np.argmax(db)) if kind == "A" else int(np.argmin(db))
    return {"onset_s": float(t[i]), "step_gray_levels": float(b[min(i + 3, len(b) - 1)] - b[max(i - 3, 0)])}
