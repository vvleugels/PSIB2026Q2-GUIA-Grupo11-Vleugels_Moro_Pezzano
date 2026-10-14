"""Region of interest (ROI) helpers. ROI is always a tuple ``(x, y, w, h)`` in pixels."""
from __future__ import annotations

import os
import cv2
import numpy as np
from .gui import prepare_gui_fonts


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
    if os.environ.get("PSIB_NONINTERACTIVE") == "1":
        raise RuntimeError("This run requires a prepared ROI; interactive selection is disabled.")
    try:
        prepare_gui_fonts()
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
    if mode == "full_frame":
        return (0, 0, frame_rgb.shape[1], frame_rgb.shape[0])
    if mode == "interactive":
        roi = select_roi_interactive(frame_rgb)
        print(f"Selected ROI -> paste in config.yaml:  x: {roi[0]}  y: {roi[1]}  w: {roi[2]}  h: {roi[3]}")
        return roi
    if mode == "manual":
        return clamp_roi((r["x"], r["y"], r["w"], r["h"]), frame_rgb.shape)
    raise ValueError(f"Unknown roi.mode: {mode!r} (use 'manual' or 'interactive')")


def tracked_frame_rois(frames, roi, tracking_options=None, video_path=None):
    """Follow intervening video frames before extracting comparison crops.

    Preserve the selected ROI dimensions; context margin is used for tracking
    support only, so existing reference-mask dimensions are unchanged.
    """
    from .eye_tracking import EyeTracker
    from .video_io import _open
    if tuple(roi) == (0, 0, frames[0][0].shape[1], frames[0][0].shape[0]):
        return [(frame, tuple(roi)) for frame, _, _ in frames]
    if tracking_options is not None and not tracking_options.get('enabled', True):
        return [(crop(frame, roi), tuple(roi)) for frame, _, _ in frames]
    tracker = EyeTracker(frames[0][0], roi, tracking_options or {})
    locations = {frames[0][2]: tracker.update(frames[0][0])}
    targets = {item[2] for item in frames[1:]}
    if video_path is not None and targets:
        if min(targets) < frames[0][2]:
            raise ValueError('Comparison timestamps must follow the primary reference frame')
        cap = _open(video_path)
        index = 0
        try:
            while index <= max(targets):
                ok, bgr = cap.read()
                if not ok:
                    break
                if index > frames[0][2]:
                    location = tracker.update(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB))
                    if index in targets:
                        locations[index] = location
                index += 1
        finally:
            cap.release()
    else:
        for frame, timestamp, index in frames[1:]:
            locations[index] = tracker.update(frame)
    result = []
    for frame, timestamp, index in frames:
        location = locations.get(index)
        if location is None or not location.valid:
            reason = location.reason if location else 'missing_frame'
            raise RuntimeError(f'Eye tracking failed at {timestamp:.3f}s: {reason}. '
                               'Choose another comparison timestamp or inspect the ROI.')
        x,y,w,h = roi
        moved = (int(round(x+location.shift_xy[0])),int(round(y+location.shift_xy[1])),w,h)
        if moved[0] < 0 or moved[1] < 0 or moved[0]+w > frame.shape[1] or moved[1]+h > frame.shape[0]:
            raise RuntimeError('Selected comparison crop moved outside the frame')
        result.append((crop(frame, moved), moved))
    return result


def pupil_initialization(cfg, rgb, index=0):
    """Select a pupil center and boundary point, or use configured ROI-local values."""
    m2 = cfg['module2']
    if m2.get('initialization_mode', 'manual') == 'interactive':
        from .calibration import select_points
        points = np.asarray(select_points(rgb, title='Click pupil CENTER, then BOUNDARY; Space resets', preview_circle=True), float)
        radius = float(np.linalg.norm(points[1] - points[0]))
        if radius <= 0:
            raise ValueError('Pupil center and boundary must be different')
        init = {'center_xy': points[0].tolist(), 'radius_px': radius}
        print(f'Frame {index} pupil initialization (ROI-local; save in config.yaml): {init}')
        return init
    init = m2['initializations'][index]
    x,y = init['center_xy']
    if not (0 <= x < rgb.shape[1] and 0 <= y < rgb.shape[0]):
        raise ValueError('Configured pupil center lies outside this ROI. Select a new initialization.')
    return init
