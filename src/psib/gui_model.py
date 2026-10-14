"""GUI setup validation, original-pixel geometry and per-video persistence."""
from dataclasses import dataclass, field, asdict
from pathlib import Path
from copy import deepcopy
import hashlib
import json
import math
import numpy as np
from .calibration import pixels_per_cm
from .video_io import read_frames_at_times
from .roi import tracked_frame_rois


@dataclass
class Setup:
    video: str
    width: int
    height: int
    duration: float
    fingerprint: str
    times: list = field(default_factory=lambda: [1.0, 5.0])
    calibration_enabled: bool = False
    roi_enabled: bool = True
    distance_cm: float = 1.0
    roi: list | None = None
    ruler_points: list | None = None
    pupils: list = field(default_factory=lambda: [None, None])

    def change_geometry(self, times=None, roi_enabled=None, roi=None):
        changed=False
        if times is not None and list(times)!=self.times:
            self.times=list(times); self.ruler_points=None; changed=True
        if roi_enabled is not None and roi_enabled!=self.roi_enabled:
            self.roi_enabled=roi_enabled; changed=True
        if roi is not None and list(roi)!=self.roi:
            self.roi=list(roi); changed=True
        if changed: self.pupils=[None,None]

    def missing(self):
        errors=[]
        if not Path(self.video).is_file(): errors.append('Choose an existing video')
        elif ProfileStore.fingerprint(self.video)!=self.fingerprint: errors.append('Video changed: reopen it and redo image selections')
        if not all(math.isfinite(float(t)) for t in self.times) or not 0<=self.times[0]<self.times[1]<=self.duration:
            errors.append('Set two timestamps: 0 <= primary < secondary <= duration')
        if self.roi_enabled:
            if self.roi is None: errors.append('Select the eye ROI')
            else:
                x,y,w,h=self.roi
                if w<=0 or h<=0 or x<0 or y<0 or x+w>self.width or y+h>self.height:
                    errors.append('ROI must fit inside the frame')
        if self.calibration_enabled:
            if not math.isfinite(self.distance_cm) or self.distance_cm<=0: errors.append('Ruler distance must be positive')
            try:
                pixels_per_cm(self.ruler_points,self.distance_cm)
                for x,y in self.ruler_points:
                    if not (0<=x<self.width and 0<=y<self.height): raise ValueError()
            except (ValueError,TypeError): errors.append('Select two valid ruler endpoints')
        w,h=self.roi[2:] if self.roi_enabled and self.roi else (self.width,self.height)
        for i,pupil in enumerate(self.pupils):
            if pupil is None: errors.append(f'Select pupil {i+1} center and boundary')
            elif not (np.isfinite(pupil['center_xy']).all() and np.isfinite(pupil['radius_px'])
                      and 0<=pupil['center_xy'][0]<w and 0<=pupil['center_xy'][1]<h and pupil['radius_px']>0):
                errors.append(f'Invalid pupil {i+1} selection')
        return errors


class CanvasGeometry:
    """Image/canvas mapping includes scroll coordinates and letterbox offsets."""
    def __init__(self,width,height,scale=1.0,offset=(0,0)):
        self.width,self.height,self.scale,self.offset=width,height,scale,offset

    def point(self,x,y):
        x=(x-self.offset[0])/self.scale; y=(y-self.offset[1])/self.scale
        if not (0<=x<self.width and 0<=y<self.height): return None
        return [float(x),float(y)]

    def rectangle(self,a,b):
        if a is None or b is None:return None
        x,y=np.floor(np.minimum(a,b)).astype(int)
        right,bottom=np.ceil(np.maximum(a,b)).astype(int)
        return [int(x),int(y),int(min(right,self.width)-x),int(min(bottom,self.height)-y)]


class ProfileStore:
    def __init__(self,root): self.root=Path(root)

    @staticmethod
    def fingerprint(path):
        p=Path(path).resolve();s=p.stat()
        return hashlib.sha256(f'{p}:{s.st_size}:{s.st_mtime_ns}'.encode()).hexdigest()

    def path(self,video):
        return self.root/(hashlib.sha256(str(Path(video).resolve()).encode()).hexdigest()+'.json')

    def save(self,setup):
        self.root.mkdir(parents=True,exist_ok=True)
        p=self.path(setup.video);temp=p.with_suffix('.tmp')
        temp.write_text(json.dumps(asdict(setup),indent=2));temp.replace(p)

    def load(self,video):
        p=self.path(video)
        if not p.exists():return None
        try:
            data=json.loads(p.read_text())
            if data['fingerprint']!=self.fingerprint(video):return None
            return Setup(**data)
        except (ValueError,TypeError,KeyError):return None


def prepare_views(setup,base):
    if not 0<=setup.times[0]<setup.times[1]<=setup.duration:
        raise ValueError('Choose valid timestamps within the video')
    frames=read_frames_at_times(setup.video,setup.times)
    if frames[0][2]==frames[1][2]:raise ValueError('Choose comparison timestamps that decode to different frames')
    if setup.roi_enabled and setup.roi is not None:
        crops=tracked_frame_rois(frames,tuple(setup.roi),base['module3'].get('eye_tracking',{}),setup.video)
    else:
        crops=[(frame,(0,0,setup.width,setup.height)) for frame,_,_ in frames]
    return frames,crops


def effective_config(setup,base,output_dir,project_root):
    errors=setup.missing()
    if errors:raise ValueError('; '.join(errors))
    cfg=deepcopy(base)
    cfg.update(video_path=str(Path(setup.video).resolve()),video_dir=str(Path(setup.video).resolve().parent),
               output_dir=str(Path(output_dir).resolve()),project_root=str(Path(project_root).resolve()))
    cfg['frames'].update(primary_time_s=setup.times[0],secondary_time_s=setup.times[1])
    cfg['roi']={'mode':'manual','x':setup.roi[0],'y':setup.roi[1],'w':setup.roi[2],'h':setup.roi[3]} if setup.roi_enabled else {'mode':'full_frame'}
    cfg['calibration'].update(enabled=setup.calibration_enabled,mode='manual',frame_time_s=setup.times[0],
        distance_cm=setup.distance_cm,points_xy=setup.ruler_points if setup.calibration_enabled else None)
    cfg['module2'].update(initialization_mode='manual',initializations=deepcopy(setup.pupils),reference_masks=[None,None])
    cfg['module3'].update(roi_reference_time_s=setup.times[0],manual_measurements_csv=None)
    return cfg


def saved_overlays(setup, view):
    """Describe saved selections in the coordinate system of the visible view."""
    shapes=[]
    if view in (None,'roi') and setup.roi_enabled and setup.roi:
        shapes.append(('rectangle',list(setup.roi),'Saved ROI'))
    if view in (None,'ruler') and setup.calibration_enabled and setup.ruler_points:
        shapes.append(('line',setup.ruler_points,'Saved ruler'))
    index=int(view[-1]) if view and view.startswith('pupil') else 0
    pupil=setup.pupils[index]
    if pupil and view in (None,'pupil0','pupil1'):
        center=list(pupil['center_xy'])
        if view is None and setup.roi_enabled and setup.roi:
            center=[center[0]+setup.roi[0],center[1]+setup.roi[1]]
        shapes.append(('circle',[center,pupil['radius_px']],f'Saved pupil {index+1}'))
    return shapes
