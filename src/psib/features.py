"""Morphometry and masked RGB first/second-order texture descriptors."""
import numpy as np
from scipy.stats import skew
from skimage import measure
from .segmentation import mask_measurements


def descriptors(rgb, mask, scale=None, levels=32, distances=(1, 2), offsets=((0, 1), (1, 1), (1, 0), (1, -1))):
    if not 2 <= levels <= 256:
        raise ValueError("Texture levels must be 2..256")
    result = mask_measurements(mask, scale)
    props = measure.regionprops(measure.label(mask))
    if props:
        largest = max(props, key=lambda p: p.area)
        result['eccentricity'] = float(largest.eccentricity)
        result['circularity'] = 4*np.pi*result['area_px2']/result['perimeter_px']**2 if result['perimeter_px'] else np.nan
    for channel, plane in zip('RGB', rgb.transpose(2, 0, 1)):
        values = plane[mask].astype(float)
        q = np.minimum(plane.astype(np.int32)*levels//256, levels-1)
        hist = np.bincount(q[mask], minlength=levels).astype(float)
        p = hist/hist.sum() if hist.sum() else hist
        result.update({f'{channel}_mean': values.mean() if values.size else np.nan,
                       f'{channel}_std': values.std() if values.size else np.nan,
                       f'{channel}_entropy_bits': float(-np.sum(p[p>0]*np.log2(p[p>0]))) if values.size else np.nan,
                       f'{channel}_skewness': float(skew(values)) if values.size and values.std()>0 else np.nan})
        # Count only pairs whose BOTH endpoints belong to the mask. No padding pixels.
        glcm = np.zeros((levels, levels), float)
        h, w = mask.shape
        for distance in distances:
            for dy, dx in offsets:
                dy, dx = dy*distance, dx*distance
                ys, xs = slice(max(0,-dy), min(h,h-dy)), slice(max(0,-dx), min(w,w-dx))
                yt, xt = slice(max(0,dy), min(h,h+dy)), slice(max(0,dx), min(w,w+dx))
                valid = mask[ys,xs] & mask[yt,xt]
                a,b=q[ys,xs][valid],q[yt,xt][valid]
                np.add.at(glcm,(a,b),1)
        glcm += glcm.T.copy()
        if glcm.sum():
            glcm /= glcm.sum()
            i,j=np.mgrid[:levels,:levels]
            mi,mj=(glcm*i).sum(),(glcm*j).sum()
            si,sj=np.sqrt((glcm*(i-mi)**2).sum()),np.sqrt((glcm*(j-mj)**2).sum())
            scores={'contrast':(glcm*(i-j)**2).sum(), 'homogeneity':(glcm/(1+(i-j)**2)).sum(),
                    'energy':np.sqrt((glcm**2).sum()), 'correlation':(glcm*(i-mi)*(j-mj)).sum()/(si*sj) if si*sj>0 else np.nan}
        else:
            scores=dict.fromkeys(['contrast','homogeneity','energy','correlation'],np.nan)
        result.update({f'{channel}_glcm_{k}':float(v) for k,v in scores.items()})
    return result
