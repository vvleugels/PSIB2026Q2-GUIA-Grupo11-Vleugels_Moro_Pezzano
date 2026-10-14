"""Manual ruler calibration on full, upright frames (before any resizing)."""
import os
import cv2
import numpy as np
from .gui import prepare_gui_fonts


def select_points(frame_rgb, count=2, title="Select ruler endpoints 1 cm apart", preview_circle=False):
    """Enlarged selection preview; return coordinates in ORIGINAL image pixels.

    Left click adds points; Space/R clears, right click/Backspace undoes,
    Enter confirms a complete selection and Esc cancels. Desktop required.
    """
    if os.environ.get("PSIB_NONINTERACTIVE") == "1":
        raise RuntimeError("This run requires prepared selections; point selection is disabled.")
    prepare_gui_fonts()
    points = []
    original_h, original_w = frame_rgb.shape[:2]
    zoom = min(1000 / original_w, 650 / original_h)
    width, height = max(1, round(original_w * zoom)), max(1, round(original_h * zoom))
    sx, sy = width / original_w, height / original_h
    image = cv2.resize(cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR), (width, height),
                       interpolation=cv2.INTER_LINEAR if zoom > 1 else cv2.INTER_AREA)
    footer_height = 78
    message = ''

    def click(event, x, y, flags, param):
        if event == cv2.EVENT_RBUTTONDOWN:
            if points:
                points.pop()
        elif event == cv2.EVENT_LBUTTONDOWN and 0 <= x < width and 0 <= y < height:
            if count is None or len(points) < count:
                points.append((min(x / sx, original_w - 1), min(y / sy, original_h - 1)))

    # Fixed rendered size avoids ambiguous mouse coordinates when a native
    # window scales/letterboxes its image. The enlarged canvas supplies zoom.
    cv2.namedWindow(title, cv2.WINDOW_AUTOSIZE)
    try:
        cv2.setMouseCallback(title, click)
        while True:
            canvas = np.zeros((height + footer_height, max(width, 850), 3), dtype=np.uint8)
            canvas[:height, :width] = image
            display_points = [tuple(np.rint([x * sx, y * sy]).astype(int)) for x, y in points]
            for index, point in enumerate(display_points):
                cv2.drawMarker(canvas, point, (0, 255, 0), cv2.MARKER_CROSS, 16, 1)
                cv2.putText(canvas, str(index + 1), (point[0] + 8, point[1] - 8),
                            cv2.FONT_HERSHEY_SIMPLEX, .55, (0, 255, 0), 1)
            if len(points) > 1:
                cv2.polylines(canvas, [np.array(display_points)], count is None, (0, 255, 0), 1)
                if preview_circle and len(points) == 2:
                    radius = float(np.linalg.norm(np.array(points[1]) - points[0]))
                    cv2.ellipse(canvas, display_points[0], (round(radius * sx), round(radius * sy)),
                                0, 0, 360, (0, 255, 255), 1)
            if preview_circle and len(points) == 2:
                details = f"Center: ({points[0][0]:.1f}, {points[0][1]:.1f}) | Radius: {radius:.1f} original px"
            else:
                details = f"Points: {len(points)}" + (f" / {count}" if count is not None else " (at least 3)")
            for row, text in enumerate(("SPACE/R: reset | Right click/Backspace: undo | ENTER: accept | ESC: cancel",
                                        details, message)):
                cv2.putText(canvas, text, (8, height + 20 + row * 23),
                            cv2.FONT_HERSHEY_SIMPLEX, .45, (230, 230, 230), 1)
            cv2.imshow(title, canvas)
            key = cv2.waitKey(30) & 255
            if key == 27 or cv2.getWindowProperty(title, cv2.WND_PROP_VISIBLE) < 1:
                raise RuntimeError("Point selection cancelled")
            if key in (32, ord('r'), ord('R')):
                points.clear()
                message = 'Selection reset. Click new points.'
            elif key in (8, 127):
                if points:
                    points.pop()
                message = ''
            elif key in (10, 13):
                complete = len(points) >= 3 if count is None else len(points) == count
                if complete:
                    return points.copy()
                message = 'Selection incomplete: add the required points, then press Enter.'
    finally:
        cv2.destroyWindow(title)


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
