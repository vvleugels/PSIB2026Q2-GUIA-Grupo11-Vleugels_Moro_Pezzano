"""Small shared helpers."""
from __future__ import annotations

import numpy as np


def to_uint8(x, mode: str = "clip") -> np.ndarray:
    """Convert any array to uint8.

    mode="clip"   : round and saturate to [0, 255]
    mode="minmax" : linearly stretch [min, max] to [0, 255] (for display of
                    signed / unbounded results such as high-pass outputs)
    """
    x = np.asarray(x, dtype=np.float64)
    if mode == "minmax":
        lo, hi = float(x.min()), float(x.max())
        x = (x - lo) / (hi - lo + 1e-12) * 255.0
    return np.clip(np.rint(x), 0, 255).astype(np.uint8)
