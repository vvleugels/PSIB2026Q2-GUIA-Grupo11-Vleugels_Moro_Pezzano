"""Automatic pupil seeds from dark, compact regions; estimates require review."""
import cv2
import numpy as np


def estimate_pupil(rgb, min_area=30):
    """Estimate crop-local center/radius without resizing measurement pixels.

    Search several dark intensity levels for enclosed compact components, score
    local darkness/contrast and shape, and reject ambiguous spatial candidates.
    This is a heuristic seed, not an anatomically validated pupil boundary.
    """
    if rgb.dtype != np.uint8 or rgb.ndim != 3 or rgb.shape[2] != 3 or min(rgb.shape[:2]) < 12:
        raise ValueError('Automatic initialization needs an RGB image at least 12 pixels wide/high')
    gray = cv2.GaussianBlur(cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY), (5, 5), 1)
    if np.ptp(gray) < 8:
        raise ValueError('No pupil contrast: use manual pupil selection or a tighter eye ROI')
    h, w = gray.shape
    levels = np.unique(np.r_[np.percentile(gray, [.1, .25, .5, 1, 2, 3, 5, 8, 12, 18, 25, 35]),
                             np.linspace(np.percentile(gray, .1), np.percentile(gray, 35), 16)]).astype(np.uint8)
    candidates = []
    for level in np.unique(levels):
        binary = (gray <= level).astype(np.uint8)*255
        binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for contour in contours:
            area = cv2.contourArea(contour)
            if not min_area <= area <= .25*h*w:
                continue
            x, y, cw, ch = cv2.boundingRect(contour)
            if x <= 1 or y <= 1 or x+cw >= w-1 or y+ch >= h-1:
                continue
            perimeter = cv2.arcLength(contour, True)
            circularity = min(1., 4*np.pi*area/max(perimeter**2, 1))
            solidity = area/max(cv2.contourArea(cv2.convexHull(contour)), 1)
            aspect = min(cw, ch)/max(cw, ch)
            if circularity < .55 or solidity < .8 or aspect < .55:
                continue
            radius = float(np.sqrt(area/np.pi))
            margin = max(3, round(radius*.4))
            left, top = max(0, x-margin), max(0, y-margin)
            right, bottom = min(w, x+cw+margin), min(h, y+ch+margin)
            mask = np.zeros((bottom-top, right-left), np.uint8)
            shifted = contour - np.array([[[left, top]]])
            cv2.drawContours(mask, [shifted], -1, 1, -1)
            ring = cv2.dilate(mask, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2*margin+1, 2*margin+1))).astype(bool) & ~mask.astype(bool)
            patch = gray[top:bottom, left:right]
            if not ring.any():
                continue
            inner, outer = float(np.median(patch[mask > 0])), float(np.median(patch[ring]))
            contrast = outer-inner
            if contrast < 4:
                continue
            moments = cv2.moments(contour)
            cx, cy = moments['m10']/moments['m00'], moments['m01']/moments['m00']
            # A mild spatial prior breaks weak ties without forcing the image center.
            distance = np.hypot((cx-w/2)/w, (cy-h/2)/h)
            position = .75+.25*np.exp(-distance**2/.25)
            score = (contrast/max(outer, 1)+contrast/255)*circularity*solidity*np.sqrt(aspect)*position
            candidates.append(dict(center_xy=[float(cx), float(cy)], radius_px=radius, score=float(score)))
    if not candidates:
        raise ValueError('No plausible pupil found: use manual pupil selection or a tighter eye ROI')
    candidates.sort(key=lambda c: c['score'], reverse=True)
    best = candidates[0]
    for other in candidates[1:]:
        separation = np.linalg.norm(np.array(best['center_xy'])-other['center_xy'])
        if separation > best['radius_px']+other['radius_px'] and other['score'] >= .9*best['score']:
            raise ValueError('Multiple plausible pupils found: select an eye ROI or use manual pupil selection')
    return {key: best[key] for key in ('center_xy', 'radius_px')}


def estimate_comparison_pupils(frames, crops, video_path, tracking_options, min_area=30):
    """Estimate both seeds; follow a local eye support window in full-frame mode.

    The second full-frame search uses the tracked neighborhood of the first
    pupil, avoiding unrelated ruler marks or dark objects elsewhere in the frame.
    Only the detection search is cropped; returned seeds remain measurement-local.
    """
    from .roi import tracked_frame_rois
    first = estimate_pupil(crops[0][0], min_area)
    height, width = frames[0][0].shape[:2]
    full_frame = tuple(crops[0][1]) == (0, 0, width, height)
    if full_frame:
        x, y = first['center_xy']
        margin_x, margin_y = max(80, first['radius_px']*4), max(55, first['radius_px']*2.75)
        left, top = max(0, int(x-margin_x)), max(0, int(y-margin_y))
        right, bottom = min(width, int(x+margin_x)+1), min(height, int(y+margin_y)+1)
        support = tracked_frame_rois(frames, (left, top, right-left, bottom-top), tracking_options, video_path)
        second = estimate_pupil(support[1][0], min_area)
        second['center_xy'] = [second['center_xy'][0]+support[1][1][0], second['center_xy'][1]+support[1][1][1]]
    else:
        second = estimate_pupil(crops[1][0], min_area)
    return [first, second]
