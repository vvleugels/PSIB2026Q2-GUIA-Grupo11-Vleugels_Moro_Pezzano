"""Track eye translation using surrounding features, independently of pupil size."""
from dataclasses import dataclass
import cv2
import numpy as np


@dataclass
class EyeLocation:
    roi: tuple
    shift_xy: tuple
    valid: bool
    method: str
    inliers: int
    confidence: float
    reason: str = ''


def expanded_roi(roi, shape, margin):
    """Add context once; crop dimensions remain constant during tracking."""
    x,y,w,h=map(int,roi); H,W=shape[:2]
    if w <= 0 or h <= 0 or x < 0 or y < 0 or x+w > W or y+h > H:
        raise ValueError('Initial eye ROI must fit inside the reference frame')
    left,top=max(0,x-margin),max(0,y-margin)
    right,bottom=min(W,x+w+margin),min(H,y+h+margin)
    return left,top,right-left,bottom-top


class EyeTracker:
    """Translation-only LK tracking with fixed-reference template recovery.

    Fits a robust affine transform to feature correspondences to check rotation
    and scale, but only translates the measurement crop. It never resizes frames.
    Failed locations do not update the tracking reference.
    """
    def __init__(self, reference_rgb, roi, options=None):
        self.options = options or {}
        self.shape=reference_rgb.shape[:2]
        self.anchor_roi=expanded_roi(roi,self.shape,int(self.options.get('margin_px',10)))
        self.gray=self._normalized(cv2.cvtColor(reference_rgb,cv2.COLOR_RGB2GRAY))
        self.shift=np.zeros(2,dtype=float)
        self.relative_scale=1.0
        self.rotation_deg=0.0
        self.points=self._features(self.gray,self.shift)
        x,y,w,h=self.anchor_roi
        self.template=self.gray[y:y+h,x:x+w]

    @staticmethod
    def _normalized(gray):
        return cv2.createCLAHE(clipLimit=2,tileGridSize=(8,8)).apply(gray)

    def _features(self,gray,shift):
        x,y,w,h=self.anchor_roi
        x,y=int(round(x+shift[0])),int(round(y+shift[1]))
        mask=np.zeros(self.shape,np.uint8)
        # Suppress the central eye region: track eyelids/corners/skin, not pupil.
        cv2.rectangle(mask,(x,y),(x+w-1,y+h-1),255,-1)
        cv2.ellipse(mask,(x+w//2,y+h//2),(int(w*.3),int(h*.3)),0,0,360,0,-1)
        return cv2.goodFeaturesToTrack(gray,maxCorners=150,qualityLevel=.01,minDistance=5,mask=mask)

    def _location(self,shift,valid,method,inliers,confidence,reason=''):
        x,y,w,h=self.anchor_roi; H,W=self.shape
        px,py=int(round(x+shift[0])),int(round(y+shift[1]))
        if px < 0 or py < 0 or px+w > W or py+h > H:
            valid=False; reason='eye_roi_out_of_frame'
        # Keep full crop size even on rejected edge frames; record the actual origin.
        px,py=max(0,min(px,W-w)),max(0,min(py,H-h))
        return EyeLocation((px,py,w,h),tuple(shift),valid,method,inliers,confidence,reason)

    def update(self,frame_rgb):
        if frame_rgb.shape[:2] != self.shape:
            raise ValueError('Frame resolution changed; fixed calibration cannot be preserved')
        gray=self._normalized(cv2.cvtColor(frame_rgb,cv2.COLOR_RGB2GRAY))
        minimum=int(self.options.get('min_inliers',8))
        points=self.points
        candidate=None; scale_candidate=self.relative_scale; angle_candidate=self.rotation_deg
        inliers=0; confidence=0; reason='insufficient_eye_features'
        if points is not None and len(points)>=minimum:
            nxt,status,_=cv2.calcOpticalFlowPyrLK(self.gray,gray,points,None,winSize=(21,21),maxLevel=3)
            if nxt is not None:
                back,back_status,_=cv2.calcOpticalFlowPyrLK(gray,self.gray,nxt,None,winSize=(21,21),maxLevel=3)
                if back is not None:
                    keep=(status.ravel()>0)&(back_status.ravel()>0)&(np.linalg.norm(back-points,axis=2).ravel()<self.options.get('forward_backward_error_px',1.5))
                    a,b=points[keep].reshape(-1,2),nxt[keep].reshape(-1,2)
                    if len(a)>=minimum:
                        matrix,good=cv2.estimateAffinePartial2D(a,b,method=cv2.RANSAC,ransacReprojThreshold=2)
                        if matrix is not None and good is not None:
                            good=good.ravel().astype(bool);inliers=int(good.sum());confidence=inliers/len(a)
                            scale=float(np.hypot(matrix[0,0],matrix[1,0]))
                            signed_angle=float(np.degrees(np.arctan2(matrix[1,0],matrix[0,0])))
                            angle_candidate=signed_angle
                            scale_candidate=scale
                            angle=abs(angle_candidate)
                            delta=np.median(b[good]-a[good],axis=0) if inliers else np.zeros(2)
                            reason='unreliable_eye_motion'
                            if (inliers>=minimum and confidence>=self.options.get('min_inlier_fraction',.6)
                                and abs(scale_candidate-1)<=self.options.get('max_scale_change',.05)
                                and angle<=self.options.get('max_rotation_deg',5)
                                and np.linalg.norm(delta)<=self.options.get('max_step_px',60)):
                                candidate=self.shift+delta
                            elif inliers>=minimum and confidence>=self.options.get('min_inlier_fraction',.6) and (abs(scale_candidate-1)>self.options.get('max_scale_change',.05) or angle>self.options.get('max_rotation_deg',5)):
                                reason='eye_scale_or_rotation_change'
        method='optical_flow'
        location=self._location(candidate if candidate is not None else self.shift,candidate is not None,method,inliers,confidence,reason if candidate is None else '')
        if not location.valid and reason != 'eye_scale_or_rotation_change':
            # Recover against the ORIGINAL template; never learn a rejected pupil/blink.
            x,y,w,h=self.anchor_roi; H,W=self.shape
            radius=int(self.options.get('recovery_search_px',100))
            cx,cy=int(round(x+self.shift[0])),int(round(y+self.shift[1]))
            left,top=max(0,cx-radius),max(0,cy-radius)
            right,bottom=min(W,cx+w+radius),min(H,cy+h+radius)
            search=gray[top:bottom,left:right]
            if search.shape[0]>=h and search.shape[1]>=w and self.template.std()>1 and search.std()>1:
                scores=cv2.matchTemplate(search,self.template,cv2.TM_CCOEFF_NORMED)
                _,score,_,pos=cv2.minMaxLoc(scores)
                if np.isfinite(score) and score>=self.options.get('recovery_min_correlation',.75):
                    shift=np.array([left+pos[0]-x,top+pos[1]-y],float)
                    location=self._location(shift,True,'template_recovery',0,float(score))
        if location.valid:
            self.shift=np.array(location.shift_xy)
            if location.method == 'optical_flow':
                self.relative_scale=scale_candidate
                self.rotation_deg=angle_candidate
            self.gray=gray
            self.points=self._features(gray,self.shift)
        return location
