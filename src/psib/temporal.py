"""Timestamp-aware pupil tracking, artifact handling and response estimates."""
import cv2
import numpy as np
import pandas as pd
from skimage import filters, segmentation, measure
from .video_io import _open
from .roi import crop
from .segmentation import morphology_variants, mask_measurements


def track_video(path, roi, center_xy, radius_px, options, scale=None):
    """Track with independent dark-region reacquisition; preserve rejected measurements."""
    cap = _open(path)
    theta=np.linspace(0,2*np.pi,200,endpoint=False)
    x,y=center_xy
    contour=np.column_stack([y+radius_px*np.sin(theta),x+radius_px*np.cos(theta)])
    rows=[]; previews=[]; previous=None; previous_time=None; last_t=-np.inf
    try:
        index=0
        while True:
            ok,bgr=cap.read()
            if not ok: break
            t=cap.get(cv2.CAP_PROP_POS_MSEC)/1000
            if not np.isfinite(t) or t <= last_t:
                raise ValueError("Decoded timestamps must be finite and strictly increasing")
            last_t=t
            rgb=crop(cv2.cvtColor(bgr,cv2.COLOR_BGR2RGB),roi)
            gray=filters.gaussian(cv2.cvtColor(rgb,cv2.COLOR_RGB2GRAY),sigma=1.5)
            if previous is not None:
                x,y=previous['centroid_x_px'],previous['centroid_y_px']
                radius=radius_px
                contour=np.column_stack([y+radius*np.sin(theta),x+radius*np.cos(theta)])
            if options.get('tracking_method') == 'kmeans':
                lab=cv2.cvtColor(rgb,cv2.COLOR_RGB2LAB).reshape(-1,3).astype(np.float32)
                cv2.setRNGSeed(0)
                _,labels,centers=cv2.kmeans(lab,5,None,(cv2.TERM_CRITERIA_EPS+cv2.TERM_CRITERIA_MAX_ITER,50,.5),1,cv2.KMEANS_PP_CENTERS)
                binary=labels.reshape(gray.shape)==int(np.argmin(centers[:,0]))
                components=measure.label(binary)
                candidates=[p for p in measure.regionprops(components) if p.area>=options['min_area_px2']]
                if candidates:
                    selected=min(candidates,key=lambda p: np.hypot(p.centroid[1]-x,p.centroid[0]-y))
                    mask=components==selected.label
                else: mask=np.zeros(gray.shape,bool)
            elif options.get('tracking_method', 'watershed') == 'watershed':
                yy,xx=np.mgrid[:gray.shape[0],:gray.shape[1]]
                radius=radius_px if previous is None else max(previous['equivalent_diameter_px']/2,15)
                distance=np.hypot(xx-x,yy-y)
                markers=np.zeros(gray.shape,np.int32)
                markers[distance<=max(2,radius*.2)]=1
                markers[distance>=radius*1.8]=2
                mask=segmentation.watershed(filters.sobel(gray),markers)==1
            elif options['tracking_method'] == 'snake':
                # Reacquire a dark component independently; do not propagate gradual drift.
                lab=cv2.cvtColor(rgb,cv2.COLOR_RGB2LAB).reshape(-1,3).astype(np.float32)
                cv2.setRNGSeed(0)
                _,labels,centers=cv2.kmeans(lab,5,None,(cv2.TERM_CRITERIA_EPS+cv2.TERM_CRITERIA_MAX_ITER,50,.5),1,cv2.KMEANS_PP_CENTERS)
                components=measure.label(labels.reshape(gray.shape)==int(np.argmin(centers[:,0])))
                candidates=[p for p in measure.regionprops(components) if p.area>=options['min_area_px2']]
                if candidates:
                    selected=min(candidates,key=lambda p: np.hypot(p.centroid[1]-center_xy[0],p.centroid[0]-center_xy[1]))
                    y,x=selected.centroid
                else: x,y=center_xy
                contour=np.column_stack([y+radius_px*np.sin(theta),x+radius_px*np.cos(theta)])
                candidate=segmentation.active_contour(gray,contour,alpha=.02,beta=5,gamma=.01,
                    w_line=0,w_edge=1,max_num_iter=options['snake_iterations'])
                mask=np.zeros(gray.shape,np.uint8)
                cv2.fillPoly(mask,[np.rint(candidate[:,::-1]).astype(np.int32)],1)
                mask=mask.astype(bool)
            else:
                raise ValueError('tracking_method must be kmeans, watershed or snake')
            mask=morphology_variants(mask,options['morphology_radius'],30)['opening_closing_filled']
            metrics=mask_measurements(mask,scale)
            area=metrics['area_px2']; d=metrics['equivalent_diameter_px']
            reasons=[]
            if not options['min_area_px2'] <= area <= options['max_area_px2']: reasons.append('area_bounds')
            if mask[0].any() or mask[-1].any() or mask[:,0].any() or mask[:,-1].any(): reasons.append('roi_border')
            if previous is not None:
                if abs(d-previous['equivalent_diameter_px']) / max(previous['equivalent_diameter_px'],1) > options['max_relative_diameter_step']: reasons.append('diameter_jump')
                move=np.hypot(metrics['centroid_x_px']-previous['centroid_x_px'],metrics['centroid_y_px']-previous['centroid_y_px'])
                if move/max(t-previous_time,1e-6)>options['max_center_speed_px_s']: reasons.append('center_jump')
            ring=morphology_variants(mask,2,30)['dilation'] & ~mask
            raw_gray=cv2.cvtColor(rgb,cv2.COLOR_RGB2GRAY)
            if mask.any() and ring.any() and np.median(raw_gray[ring])-np.median(raw_gray[mask]) < options.get('min_pupil_contrast',2):
                reasons.append('low_pupil_contrast')
            valid=not reasons
            if valid:
                previous=metrics; previous_time=t
            rows.append({'frame_index':index,'timestamp_s':t,**metrics,'accepted':valid,
                         'artifact_reason':'|'.join(reasons),'centroid_full_x_px':metrics['centroid_x_px']+roi[0],
                         'centroid_full_y_px':metrics['centroid_y_px']+roi[1]})
            if index % options['preview_stride']==0:
                previews.append((index,t,rgb.copy(),mask.copy(),valid))
            index+=1
    finally: cap.release()
    return pd.DataFrame(rows),previews


def clean_curve(table, max_gap_s=.15, smooth_window_s=.15):
    """Interpolate only short internal gaps; never extrapolate or bridge long gaps."""
    table=table.copy(); t=table.timestamp_s.to_numpy()
    d=table.equivalent_diameter_px.to_numpy(dtype=float).copy()
    d[~table.accepted.to_numpy()]=np.nan
    interpolated=np.zeros(len(t),bool)
    good=np.flatnonzero(np.isfinite(d))
    for left,right in zip(good[:-1],good[1:]):
        if right>left+1 and t[right]-t[left]<=max_gap_s:
            d[left+1:right]=np.interp(t[left+1:right],t[[left,right]],d[[left,right]])
            interpolated[left+1:right]=True
    smooth=d.copy()
    # Smooth independently within finite runs, so long gaps remain explicit.
    starts=np.flatnonzero(np.isfinite(d) & ~np.r_[False,np.isfinite(d[:-1])])
    ends=np.flatnonzero(np.isfinite(d) & ~np.r_[np.isfinite(d[1:]),False])
    for start,end in zip(starts,ends):
        for i in range(start,end+1):
            local=(t[start:end+1]>=t[i]-smooth_window_s/2)&(t[start:end+1]<=t[i]+smooth_window_s/2)
            smooth[i]=np.median(d[start:end+1][local])
    table['interpolated']=interpolated
    table['diameter_clean_px']=d; table['diameter_smooth_px']=smooth
    table['area_smooth_px2']=np.pi*smooth**2/4
    return table


def response_parameters(table, stimulus_s, kind, options, scale=None):
    """Exploratory threshold-based estimates; insufficient windows produce NaN."""
    if kind not in ('A','B'): raise ValueError("Record kind must be A or B")
    t=table.timestamp_s.to_numpy(); d=table.diameter_smooth_px.to_numpy()
    baseline=d[(t>=stimulus_s-options['baseline_window_s'])&(t<stimulus_s)]
    baseline=baseline[np.isfinite(baseline)]
    after=(t>=stimulus_s)&(t<=stimulus_s+options['response_window_s'])&np.isfinite(d)
    result={'record_type':kind,'stimulus_s':stimulus_s,'baseline_diameter_px':np.nan,
            'response_amplitude_px':np.nan,'response_amplitude_area_px2':np.nan,'latency_s':np.nan,
            'peak_constriction_speed_px_s':np.nan,'peak_redilation_speed_px_s':np.nan,
            'accepted_fraction':float(table.accepted.mean()),'status':'insufficient_data'}
    if len(baseline)<options['min_baseline_frames'] or after.sum()<3: return result
    basal=float(np.median(baseline)); noise=float(1.4826*np.median(abs(baseline-basal)))
    extreme=float(np.min(d[after]) if kind=='A' else np.max(d[after]))
    amplitude=basal-extreme if kind=='A' else extreme-basal
    result.update(baseline_diameter_px=basal,response_amplitude_px=amplitude,
        response_amplitude_area_px2=abs(np.pi*(basal**2-extreme**2)/4),status='no_sustained_response')
    threshold=max(options['relative_onset_threshold']*basal,options['noise_multiplier']*noise)
    changed=(basal-d if kind=='A' else d-basal)>=threshold
    run_start=None
    for i in range(len(t)):
        if not after[i] or not changed[i] or (i and t[i]-t[i-1]>options['max_gap_s']): run_start=None
        if after[i] and changed[i]:
            if run_start is None: run_start=i
            if t[i]-t[run_start]>=options['onset_hold_s']:
                result.update(latency_s=float(t[run_start]-stimulus_s),status='estimated_unvalidated'); break
    dt=np.diff(t); speed=np.diff(d)/dt
    use=after[:-1]&after[1:]&(dt<=options['max_gap_s'])&np.isfinite(speed)
    if use.any():
        result['peak_constriction_speed_px_s']=float(max(0,-speed[use].min()))
        result['peak_redilation_speed_px_s']=float(max(0,speed[use].max()))
    if scale is not None:
        for name in ['baseline_diameter','response_amplitude','peak_constriction_speed','peak_redilation_speed']:
            suffix='_px_s' if 'speed' in name else '_px'
            result[name+('_mm_s' if 'speed' in name else '_mm')]=10*result[name+suffix]/scale
        result['response_amplitude_area_mm2']=100*result['response_amplitude_area_px2']/scale**2
    return result
