"""Manual ruler calibration on full, upright frames (before any resizing)."""
import cv2
import numpy as np


def select_points(frame_rgb, count=2, title="Select ruler endpoints 1 cm apart"):
    """Left click points; Enter accepts, R resets, Esc cancels (desktop required)."""
    points = []
    image = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)
    def click(event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN and (count is None or len(points) < count):
            points.append((x, y))
    cv2.namedWindow(title)
    cv2.setMouseCallback(title, click)
    try:
        while True:
            canvas = image.copy()
            for p in points:
                cv2.circle(canvas, p, 4, (0, 255, 0), -1)
            if len(points) > 1:
                cv2.polylines(canvas, [np.array(points)], count is None, (0, 255, 0), 2)
            cv2.imshow(title, canvas)
            key = cv2.waitKey(30) & 255
            if key == 27 or cv2.getWindowProperty(title, cv2.WND_PROP_VISIBLE) < 1:
                raise RuntimeError("Point selection cancelled")
            if key in (ord('r'), ord('R')):
                points.clear()
            if key in (10, 13) and ((count is None and len(points) >= 3) or len(points) == count):
                return points
    finally:
        cv2.destroyAllWindows()


def pixels_per_cm(points, distance_cm=1.0):
    p = np.asarray(points, dtype=float)
    if p.shape != (2, 2) or not np.isfinite(p).all() or distance_cm <= 0:
        raise ValueError("Use two finite (x, y) points and a positive ruler distance")
    length = float(np.linalg.norm(p[1] - p[0]))
    if length <= 0:
        raise ValueError("Ruler endpoints must be different")
    return length / distance_cm


def physical_measurements(area_px, perimeter_px, scale):
    """Scale lengths and areas; equivalent diameter uses a circle of equal area."""
    d = float(np.sqrt(4 * area_px / np.pi))
    result = {"area_px2": float(area_px), "perimeter_px": float(perimeter_px),
              "equivalent_diameter_px": d}
    if scale is not None:
        if not np.isfinite(scale) or scale <= 0:
            raise ValueError("pixels_per_cm must be positive and finite")
        result.update(area_cm2=area_px / scale**2, area_mm2=100 * area_px / scale**2,
                      perimeter_mm=10 * perimeter_px / scale, equivalent_diameter_mm=10 * d / scale)
    return result
