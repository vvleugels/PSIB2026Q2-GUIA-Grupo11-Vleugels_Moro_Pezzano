"""Edge detectors and a simple contour-continuity measure."""
from __future__ import annotations

import cv2
import numpy as np
from skimage import filters as skf
from skimage import measure, morphology


def _norm01(m: np.ndarray) -> np.ndarray:
    return np.clip(m / (np.percentile(m, 99.5) + 1e-12), 0.0, 1.0)


def gradient_maps(gray: np.ndarray) -> dict[str, np.ndarray]:
    """Edge-strength maps (float, normalised to 0-1) for Roberts, Sobel, Prewitt and Laplacian."""
    g = gray.astype(np.float64) / 255.0
    return {
        "Roberts": _norm01(skf.roberts(g)),
        "Sobel": _norm01(skf.sobel(g)),
        "Prewitt": _norm01(skf.prewitt(g)),
        "Laplacian": _norm01(np.abs(skf.laplace(g))),
    }


def canny(gray: np.ndarray, low: float, high: float) -> np.ndarray:
    """Canny edges as a boolean map.

    OpenCV's Canny does not smooth the input, so pass an already pre-filtered
    image if noise should be suppressed first.
    """
    return cv2.Canny(gray, low, high) > 0


def binarize(strength: np.ndarray, percentile: float = 90.0) -> np.ndarray:
    """Keep the strongest (100 - percentile)% pixels of an edge-strength map."""
    return strength >= np.percentile(strength, percentile)


def edge_continuity(binary: np.ndarray) -> dict:
    """Continuity of a binary edge map, measured on its 1-pixel skeleton.

    Fewer, longer connected components mean more continuous contours.
    Returns: edge_px, n_components, largest_px, largest_fraction.
    """
    skel = morphology.skeletonize(binary)
    lab = measure.label(skel, connectivity=2)
    sizes = np.bincount(lab.ravel())[1:]
    edge_px = int(skel.sum())
    largest = int(sizes.max()) if sizes.size else 0
    return {
        "edge_px": edge_px,
        "n_components": int(sizes.size),
        "largest_px": largest,
        "largest_fraction": largest / edge_px if edge_px else 0.0,
    }
