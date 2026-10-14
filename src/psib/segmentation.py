"""Pupil segmentation comparisons, morphology and manual-reference evaluation."""
import cv2
import numpy as np
from skimage import filters, measure, morphology, segmentation
from scipy import ndimage as ndi
from .calibration import physical_measurements


def select_component(mask, center_xy):
    """Keep the component containing the pupil seed, or the nearest component."""
    labels = measure.label(mask)
    props = measure.regionprops(labels)
    if not props:
        return np.zeros(mask.shape, dtype=bool)
    x, y = np.rint(center_xy).astype(int)
    if not (0 <= x < mask.shape[1] and 0 <= y < mask.shape[0]):
        raise ValueError("Pupil center must lie inside the ROI")
    label = labels[y, x]
    if not label:
        label = min(props, key=lambda p: np.linalg.norm(np.array(p.centroid) - [y, x])).label
    return labels == label


def segment_methods(rgb, center_xy, radius_px, clusters=(2, 3, 4, 5), snake_iterations=250):
    """All methods share an explicit seed/initial contour; coordinates are ROI-local."""
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    smooth = filters.gaussian(gray, sigma=1.5)
    h, w = gray.shape
    x, y = center_xy
    if radius_px <= 0 or not (0 <= x < w and 0 <= y < h):
        raise ValueError("Invalid pupil initialization")
    results = {"otsu": select_component(gray <= filters.threshold_otsu(gray), center_xy),
               "local_otsu": local_pupil_mask(rgb, center_xy, radius_px)}
    lab = cv2.cvtColor(rgb, cv2.COLOR_RGB2LAB).reshape(-1, 3).astype(np.float32)
    for k in clusters:
        cv2.setRNGSeed(0)
        _, labels, centers = cv2.kmeans(lab, int(k), None,
            (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 100, 0.2), 3, cv2.KMEANS_PP_CENTERS)
        dark = int(np.argmin(centers[:, 0]))
        results[f"kmeans_{k}"] = select_component(labels.reshape(h, w) == dark, center_xy)
    theta = np.linspace(0, 2*np.pi, 200, endpoint=False)
    contour = np.column_stack([y + radius_px*np.sin(theta), x + radius_px*np.cos(theta)])
    contour[:, 0] = np.clip(contour[:, 0], 0, h-1)
    contour[:, 1] = np.clip(contour[:, 1], 0, w-1)
    snake = segmentation.active_contour(smooth, contour, alpha=0.02, beta=5,
        gamma=0.01, w_line=0, w_edge=1, max_num_iter=snake_iterations)
    mask = np.zeros((h, w), np.uint8)
    cv2.fillPoly(mask, [np.rint(snake[:, ::-1]).astype(np.int32)], 1)
    results["snake"] = mask.astype(bool)
    yy, xx = np.mgrid[:h, :w]
    distance = np.hypot(xx-x, yy-y)
    markers = np.zeros((h, w), np.int32)
    markers[distance <= max(2, radius_px*0.25)] = 1
    markers[distance >= radius_px*1.8] = 2
    results["watershed"] = segmentation.watershed(filters.sobel(smooth), markers) == 1
    return results


def morphology_variants(mask, radius=2, min_size=30):
    se = morphology.disk(radius)
    opened = morphology.opening(mask, se)
    closed = morphology.closing(opened, se)
    labels = measure.label(closed)
    sizes = np.bincount(labels.ravel())
    keep = sizes >= min_size
    keep[0] = False
    cleaned = ndi.binary_fill_holes(keep[labels])
    return {"original": mask, "erosion": morphology.erosion(mask, se),
            "dilation": morphology.dilation(mask, se), "opening": opened,
            "closing": morphology.closing(mask, se), "opening_closing_filled": cleaned,
            "contour_skeleton": morphology.skeletonize(segmentation.find_boundaries(cleaned, mode="inner"))}


def overlap_metrics(mask, reference):
    a, b = np.asarray(mask, bool), np.asarray(reference, bool)
    if a.shape != b.shape:
        raise ValueError("Reference and prediction shapes differ")
    intersection = np.count_nonzero(a & b)
    total = a.sum()+b.sum()
    union = np.count_nonzero(a | b)
    return {"Dice": 2*intersection/total if total else 1.0,
            "IoU": intersection/union if union else 1.0}


def mask_measurements(mask, scale=None):
    area = int(np.count_nonzero(mask))
    perimeter = float(measure.perimeter(mask, neighborhood=8))
    result = physical_measurements(area, perimeter, scale)
    yy, xx = np.nonzero(mask)
    result.update(centroid_x_px=float(xx.mean()) if area else np.nan,
                  centroid_y_px=float(yy.mean()) if area else np.nan,
                  valid=bool(area))
    return result


def polygon_mask(shape, points_xy):
    p = np.asarray(points_xy, dtype=float)
    if p.ndim != 2 or p.shape[1] != 2 or len(p) < 3 or not np.isfinite(p).all():
        raise ValueError("A reference polygon needs at least three finite points")
    mask = np.zeros(shape[:2], np.uint8)
    cv2.fillPoly(mask, [np.rint(p).astype(np.int32)], 1)
    return mask.astype(bool)


def local_pupil_mask(rgb, center_xy, radius_px, classes=3, search_radius_factor=1.8, min_size=30):
    """Keep the darkest local intensity group near the pupil seed.

    This supplements global Otsu for illumination-dependent pupil/iris contrast;
    it remains a candidate requiring manual-reference validation.
    """
    gray=filters.gaussian(cv2.cvtColor(rgb,cv2.COLOR_RGB2GRAY),sigma=1.5)
    x,y=center_xy
    if radius_px<=0 or not (0<=x<gray.shape[1] and 0<=y<gray.shape[0]):
        raise ValueError('Invalid local pupil initialization')
    yy,xx=np.mgrid[:gray.shape[0],:gray.shape[1]]
    search=np.hypot(xx-x,yy-y)<=radius_px*search_radius_factor
    values=gray[search]
    if not values.size or values.max()==values.min():
        return np.zeros(gray.shape,bool)
    classes=min(int(classes),len(np.unique(np.rint(values*255))))
    threshold=filters.threshold_multiotsu(values,classes=classes)[0] if classes>2 else filters.threshold_otsu(values)
    labels=measure.label((gray<=threshold)&search)
    sizes=np.bincount(labels.ravel());keep=sizes>=min_size;keep[0]=False
    return select_component(keep[labels],center_xy)
