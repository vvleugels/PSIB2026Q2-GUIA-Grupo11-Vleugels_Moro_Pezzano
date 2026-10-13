"""Region of interest (ROI) helpers. ROI is always a tuple ``(x, y, w, h)`` in pixels."""
from __future__ import annotations

import cv2
import numpy as np


def clamp_roi(roi, shape) -> tuple[int, int, int, int]:
    """Clip an ROI so that it lies inside an image of ``shape`` (h, w, ...)."""
    x, y, w, h = (int(v) for v in roi)
    H, W = shape[:2]
    x, y = max(0, min(x, W - 1)), max(0, min(y, H - 1))
    w, h = max(1, min(w, W - x)), max(1, min(h, H - y))
    return x, y, w, h


def crop(img: np.ndarray, roi) -> np.ndarray:
    x, y, w, h = clamp_roi(roi, img.shape)
    return img[y:y + h, x:x + w].copy()


def draw_roi(img_rgb: np.ndarray, roi, color=(0, 255, 0), thickness: int = 3) -> np.ndarray:
    x, y, w, h = clamp_roi(roi, img_rgb.shape)
    out = img_rgb.copy()
    cv2.rectangle(out, (x, y), (x + w, y + h), color, thickness)
    return out


def select_roi_interactive(img_rgb: np.ndarray) -> tuple[int, int, int, int]:
    """Draw the ROI with the mouse (ENTER/SPACE to accept, C to cancel).

    Needs a desktop session and ``opencv-python`` (not ``-headless``). The
    returned values should be pasted into ``config.yaml`` so the choice is
    reproducible.
    """
    try:
        bgr = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2BGR)
        x, y, w, h = cv2.selectROI("Select eye ROI (ENTER = accept)", bgr, showCrosshair=False)
        cv2.destroyAllWindows()
    except cv2.error as exc:  # no display / headless build
        raise RuntimeError(
            "Interactive ROI selection is not available here (no GUI). "
            "Set roi.mode: manual and fill x, y, w, h in config.yaml."
        ) from exc
    if w == 0 or h == 0:
        raise RuntimeError("ROI selection cancelled")
    return int(x), int(y), int(w), int(h)


def get_roi(cfg: dict, frame_rgb: np.ndarray) -> tuple[int, int, int, int]:
    """ROI according to ``cfg['roi']`` (mode manual | interactive)."""
    r = cfg["roi"]
    mode = r.get("mode", "manual")
    if mode == "interactive":
        roi = select_roi_interactive(frame_rgb)
        print(f"Selected ROI -> paste in config.yaml:  x: {roi[0]}  y: {roi[1]}  w: {roi[2]}  h: {roi[3]}")
        return roi
    if mode == "manual":
        return clamp_roi((r["x"], r["y"], r["w"], r["h"]), frame_rgb.shape)
    raise ValueError(f"Unknown roi.mode: {mode!r} (use 'manual' or 'interactive')")
