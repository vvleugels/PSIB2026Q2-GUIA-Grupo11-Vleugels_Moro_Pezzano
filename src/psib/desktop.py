"""Tkinter desktop workflow for PSIB setup and notebook execution."""
from pathlib import Path
from datetime import datetime
import json
import os
import queue
import subprocess
import sys
import threading
import uuid
import webbrowser
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import numpy as np
from PIL import Image, ImageTk
import yaml
from .initialization import estimate_comparison_pupils
from .acceleration import probe_gpu
from .gui_model import Setup,ProfileStore,CanvasGeometry,prepare_views,effective_config,saved_overlays
from .video_io import scan_video, read_frames_at_times
from .system_open import open_folder


class DesktopApp:
    def __init__(self,window,root):
        self.window=window;self.root=Path(root)
        base_path=self.root/'config.local.yaml'
        if not base_path.is_file():base_path=self.root/'config.yaml'
        self.base=yaml.safe_load(base_path.read_text())
        self.store=ProfileStore(self.root/'.psib_gui')
        self.setup=None;self.frames=None;self.crops=None;self.busy=False;self.process=None
        self.events=queue.Queue();self.mode=None;self.view_mode=None;self.points=[];self.rect=None;self.drag_start=None
        self.image=None;self.photo=None;self.geometry=None;self.scale=1;self.last_run=None
        self.cancel_requested=False;self.figures=[];self.figure_index=0
        self.video_var=tk.StringVar();self.t1=tk.StringVar(value='1.0');self.t2=tk.StringVar(value='5.0')
        self.cal=tk.BooleanVar(value=False);self.roi=tk.BooleanVar(value=True);self.distance=tk.StringVar(value='1.0')
        self.show_saved=tk.BooleanVar(value=True)
        self.manual_pupils=tk.BooleanVar(value=True)
        self.gpu=tk.BooleanVar(value=False)
        self.gpu_details=tk.StringVar(value='GPU off — CPU processing.')
        self.status=tk.StringVar(value='Choose a video to begin.')
        self.details=tk.StringVar(value='No video loaded');self.selection_info=tk.StringVar()
        window.title('PSIB — Pupil analysis');window.geometry('1280x850');window.minsize(1000,700)
        window.protocol('WM_DELETE_WINDOW',self.close)
        header=ttk.Frame(window,padding=10);header.pack(fill='x')
        ttk.Label(header,text='PSIB pupil analysis',font=('TkDefaultFont',16,'bold')).pack(anchor='w')
        row=ttk.Frame(header);row.pack(fill='x',pady=5)
        ttk.Entry(row,textvariable=self.video_var,state='readonly').pack(side='left',fill='x',expand=True)
        self.browse_button=ttk.Button(row,text='Choose video…',command=self.browse);self.browse_button.pack(side='left',padx=5)
        ttk.Label(header,textvariable=self.details).pack(anchor='w')
        controls=ttk.Frame(header);controls.pack(fill='x',pady=6)
        ttk.Label(controls,text='Primary (s)').pack(side='left');self.time1=ttk.Entry(controls,textvariable=self.t1,width=7);self.time1.pack(side='left',padx=5)
        ttk.Label(controls,text='Secondary (s)').pack(side='left');self.time2=ttk.Entry(controls,textvariable=self.t2,width=7);self.time2.pack(side='left',padx=5)
        self.apply_button=ttk.Button(controls,text='Apply / load frames',command=self.apply);self.apply_button.pack(side='left',padx=5)
        self.cal_toggle=ttk.Checkbutton(controls,text='Calibration',variable=self.cal,command=self.toggle);self.cal_toggle.pack(side='left',padx=10)
        self.roi_toggle=ttk.Checkbutton(controls,text='Select eye ROI',variable=self.roi,command=self.toggle);self.roi_toggle.pack(side='left')
        ttk.Label(controls,text='Ruler distance (cm)').pack(side='left',padx=5);self.distance_entry=ttk.Entry(controls,textvariable=self.distance,width=5);self.distance_entry.pack(side='left')
        pupil_controls=ttk.Frame(header);pupil_controls.pack(fill='x')
        self.pupil_toggle=ttk.Checkbutton(pupil_controls,text='Select pupils manually',variable=self.manual_pupils,command=self.toggle)
        self.pupil_toggle.pack(side='left')
        ttk.Label(pupil_controls,text='Off: estimate both pupils automatically; review the blue dashed overlays.').pack(side='left',padx=8)
        gpu_controls=ttk.Frame(header);gpu_controls.pack(fill='x')
        self.gpu_toggle=ttk.Checkbutton(gpu_controls,text='Request GPU (OpenCL)',variable=self.gpu,command=self.toggle_gpu)
        self.gpu_toggle.pack(side='left')
        ttk.Label(gpu_controls,textvariable=self.gpu_details,wraplength=950).pack(side='left',padx=8)
        self.tabs=ttk.Notebook(window);self.tabs.pack(fill='both',expand=True,padx=10)
        setup_tab=ttk.Frame(self.tabs);results_tab=ttk.Frame(self.tabs);self.tabs.add(setup_tab,text='Setup');self.tabs.add(results_tab,text='Results & log')
        bar=ttk.Frame(setup_tab);bar.pack(fill='x',pady=5)
        self.select_buttons=[]
        for text,mode in [('1. Eye ROI','roi'),('2. Ruler endpoints','ruler'),('3. Primary pupil','pupil0'),('4. Secondary pupil','pupil1')]:
            button=ttk.Button(bar,text=text,command=lambda m=mode:self.select(m));button.pack(side='left',padx=3);self.select_buttons.append(button)
        ttk.Checkbutton(bar,text='Show saved presets',variable=self.show_saved,command=self.render).pack(side='left',padx=8)
        ttk.Button(bar,text='Fit',command=self.fit).pack(side='right')
        ttk.Button(bar,text='Zoom −',command=lambda:self.zoom(.8)).pack(side='right')
        ttk.Button(bar,text='Zoom +',command=lambda:self.zoom(1.25)).pack(side='right')
        area=ttk.Frame(setup_tab);area.pack(fill='both',expand=True)
        self.canvas=tk.Canvas(area,background='#20252b',highlightthickness=0,takefocus=True)
        vs=ttk.Scrollbar(area,orient='vertical',command=self.canvas.yview);hs=ttk.Scrollbar(area,orient='horizontal',command=self.canvas.xview)
        self.canvas.configure(xscrollcommand=hs.set,yscrollcommand=vs.set)
        vs.pack(side='right',fill='y');hs.pack(side='bottom',fill='x');self.canvas.pack(fill='both',expand=True)
        self.canvas.bind('<ButtonPress-1>',self.press);self.canvas.bind('<B1-Motion>',self.drag);self.canvas.bind('<ButtonRelease-1>',self.release)
        self.canvas.bind('<space>',lambda e:self.reset());self.canvas.bind('<BackSpace>',lambda e:self.undo())
        self.canvas.bind('<Button-3>',lambda e:self.undo());self.canvas.bind('<Return>',lambda e:self.confirm())
        ttk.Label(setup_tab,textvariable=self.selection_info).pack(anchor='w',pady=3)
        action=ttk.Frame(setup_tab);action.pack(fill='x')
        ttk.Label(action,text='Drag ROI / click points • Space: reset • Backspace/right click: undo • Enter: confirm').pack(side='left')
        self.confirm_button=ttk.Button(action,text='Confirm selection',command=self.confirm);self.confirm_button.pack(side='right')
        self.reset_button=ttk.Button(action,text='Reset',command=self.reset);self.reset_button.pack(side='right',padx=5)
        result_bar=ttk.Frame(results_tab);result_bar.pack(fill='x',pady=5)
        ttk.Button(result_bar,text='Open results folder',command=self.open_results).pack(side='left')
        self.report_names=tk.StringVar();self.report_menu=ttk.Combobox(result_bar,textvariable=self.report_names,state='readonly',width=40);self.report_menu.pack(side='left',padx=6)
        ttk.Button(result_bar,text='Open notebook report',command=self.open_report).pack(side='left')
        ttk.Button(result_bar,text='Previous figure',command=lambda:self.figure(-1)).pack(side='right')
        ttk.Button(result_bar,text='Next figure',command=lambda:self.figure(1)).pack(side='right')
        self.result_image=ttk.Label(results_tab,anchor='center');self.result_image.pack(fill='both',expand=True)
        self.log=tk.Text(results_tab,height=9,wrap='word',state='disabled');self.log.pack(fill='x')
        bottom=ttk.Frame(window,padding=10);bottom.pack(fill='x')
        ttk.Label(bottom,textvariable=self.status,wraplength=940).pack(anchor='w')
        self.progress=ttk.Progressbar(bottom,maximum=100);self.progress.pack(side='left',fill='x',expand=True,pady=6)
        self.cancel_button=ttk.Button(bottom,text='Cancel run',command=self.cancel);self.cancel_button.pack(side='right')
        self.run_button=ttk.Button(bottom,text='Run all notebooks (0–4)',command=self.run);self.run_button.pack(side='right',padx=8)
        for variable in (self.t1,self.t2,self.distance):variable.trace_add('write',lambda *args:self.refresh())
        self.refresh();window.after(100,self.poll)

    def task(self,function,callback):
        if self.busy:return
        self.busy=True;self.refresh()
        def worker():
            try:self.events.put(('task_done',callback,function(),None))
            except Exception as exc:self.events.put(('task_done',callback,None,str(exc)))
        threading.Thread(target=worker,daemon=True).start()

    def browse(self):
        path=filedialog.askopenfilename(title='Choose eye recording',filetypes=[('Videos','*.mp4 *.mov *.avi *.mkv'),('All files','*')])
        if not path:return
        self.status.set('Reading video metadata…')
        def load():
            scan=scan_video(path)
            restored=self.store.load(path)
            s=restored or Setup(str(Path(path).resolve()),scan['width'],scan['height'],scan['duration_s'],self.store.fingerprint(path))
            if not restored:
                s.times=[float(self.base['frames']['primary_time_s']),float(self.base['frames']['secondary_time_s'])]
            return s
        def loaded(s):
            self.setup=s;self.frames=None;self.crops=None;self.mode=None;self.image=None
            self.video_var.set(s.video);self.t1.set(str(s.times[0]));self.t2.set(str(s.times[1]))
            self.manual_pupils.set(s.manual_pupils)
            self.gpu.set(s.use_gpu)
            self.gpu_details.set('Checking GPU…' if s.use_gpu else 'GPU off — CPU processing.')
            self.cal.set(s.calibration_enabled);self.roi.set(s.roi_enabled);self.distance.set(str(s.distance_cm))
            self.details.set(f'{Path(s.video).name}  |  {s.width} × {s.height}  |  last frame: {s.duration:.3f} s')
            self.apply()
        self.task(load,loaded)

    def apply(self):
        if not self.setup or self.busy:return
        try:
            self.setup.change_geometry(times=[float(self.t1.get()),float(self.t2.get())])
            self.setup.distance_cm=float(self.distance.get())
        except ValueError:
            messagebox.showerror('Invalid settings','Enter numerical timestamps and ruler distance.');return
        self.frames=None;self.crops=None;self.mode=None
        self.status.set('Preparing comparison frames and tracking the eye…')
        def prepare():
            # Keep a usable reference frame when tracking the second crop fails,
            # so the user can redraw the ROI without accepting a false crop.
            frames=read_frames_at_times(self.setup.video,self.setup.times)
            try:
                _,crops=prepare_views(self.setup,self.base)
            except RuntimeError as exc:return frames,None,str(exc),[None,None]
            automatic=[None,None]
            if not self.setup.manual_pupils and (not self.setup.roi_enabled or self.setup.roi is not None):
                try:
                    automatic=estimate_comparison_pupils(frames,crops,self.setup.video,
                        self.base['module3'].get('eye_tracking',{}),self.base['module2'].get('min_component_size',30))
                except (ValueError,RuntimeError) as exc:
                    return frames,crops,f'Automatic pupil estimation: {exc}',[None,None]
            return frames,crops,None,automatic
        def prepared(result):
            self.frames,self.crops,error,automatic=result
            self.setup.automatic_pupils=automatic
            self.store.save(self.setup)
            self.view_mode=None;self.show_image(self.frames[0][0]);self.refresh()
            if error:
                messagebox.showerror('Preparation needs attention',error)
            if self.gpu.get():self.toggle_gpu()
        self.task(prepare,prepared)

    def toggle_gpu(self):
        if self.busy:return
        if self.setup:
            self.setup.use_gpu=self.gpu.get()
            self.store.save(self.setup)
        if not self.gpu.get():
            self.gpu_details.set('GPU off — CPU processing.');return
        self.gpu_details.set('Checking OpenCL GPU…')
        self.task(probe_gpu,lambda info:self.gpu_details.set(info['message']))

    def toggle(self):
        if not self.setup:return
        self.setup.calibration_enabled=self.cal.get()
        self.setup.manual_pupils=self.manual_pupils.get()
        self.setup.change_geometry(roi_enabled=self.roi.get())
        self.apply()

    def refresh(self):
        settings=[self.browse_button,self.apply_button,self.time1,self.time2,self.cal_toggle,self.roi_toggle,self.pupil_toggle,self.gpu_toggle,self.distance_entry]
        for widget in settings:widget.configure(state='disabled' if self.busy else 'normal')
        ready=self.setup is not None and self.frames is not None and not self.busy
        crops_ready=ready and self.crops is not None
        for i,button in enumerate(self.select_buttons):
            enabled=ready and (i!=0 or self.roi.get()) and (i!=1 or self.cal.get()) and (i<2 or (crops_ready and (not self.roi.get() or self.setup.roi is not None)))
            button.configure(state='normal' if enabled else 'disabled')
            if i>=2:
                prefix='Primary' if i==2 else 'Secondary'
                button.configure(text=f'{i+1}. {prefix} '+('pupil' if self.manual_pupils.get() else 'estimate'))
        missing=self.setup.missing() if self.setup else ['Choose a video']
        try:unapplied=self.setup and [float(self.t1.get()),float(self.t2.get())]!=self.setup.times
        except ValueError:unapplied=True
        try:bad_distance=self.cal.get() and (not np.isfinite(float(self.distance.get())) or float(self.distance.get())<=0)
        except ValueError:bad_distance=self.cal.get()
        if bad_distance:missing.append('Enter a positive ruler distance')
        self.run_button.configure(state='normal' if crops_ready and not missing and not unapplied else 'disabled')
        self.distance_entry.configure(state='disabled' if self.busy or not self.cal.get() else 'normal')
        self.cancel_button.configure(state='normal' if self.process is not None and self.process.poll() is None and not self.cancel_requested else 'disabled')
        self.confirm_button.configure(state='normal' if ready and self.mode else 'disabled')
        self.reset_button.configure(state='normal' if ready and self.mode else 'disabled')
        if not self.busy:
            self.status.set('Ready: run all notebooks.' if crops_ready and not missing and not unapplied else 'Setup needed: '+('; '.join(missing) if missing else 'Apply timestamps'))

    def select(self,mode):
        if not self.frames or self.busy:return
        self.mode=None if mode.startswith('pupil') and not self.manual_pupils.get() else mode
        self.view_mode=mode;self.points=[];self.rect=None;self.drag_start=None
        if mode=='roi':self.show_image(self.frames[0][0])
        elif mode=='ruler':self.show_image(self.frames[0][0])
        else:self.show_image(self.crops[int(mode[-1])][0])
        self.canvas.focus_set();self.refresh()

    def show_image(self,image):
        self.image=image;self.points=[];self.rect=None
        self.fit()

    def fit(self):
        if self.image is None:return
        self.window.update_idletasks()
        h,w=self.image.shape[:2]
        self.scale=min(max(self.canvas.winfo_width()-20,100)/w,max(self.canvas.winfo_height()-20,100)/h)
        self.canvas.xview_moveto(0);self.canvas.yview_moveto(0);self.render()

    def zoom(self,factor):
        if self.image is None:return
        self.scale=max(.1,min(self.scale*factor,16));self.render()

    def render(self):
        if self.image is None:return
        h,w=self.image.shape[:2]
        dw,dh=max(1,round(w*self.scale)),max(1,round(h*self.scale))
        self.geometry=CanvasGeometry(w,h,self.scale)
        self.photo=ImageTk.PhotoImage(Image.fromarray(self.image).resize((dw,dh),Image.Resampling.BILINEAR))
        self.canvas.delete('all');self.canvas.create_image(0,0,image=self.photo,anchor='nw')
        self.canvas.configure(scrollregion=(0,0,max(dw,self.canvas.winfo_width()),max(dh,self.canvas.winfo_height())))
        if self.show_saved.get() and self.setup:
            for kind,data,label in saved_overlays(self.setup,self.view_mode):
                color='#55c5ff'
                if kind=='rectangle':
                    x,y,rw,rh=data
                    self.canvas.create_rectangle(x*self.scale,y*self.scale,(x+rw)*self.scale,(y+rh)*self.scale,outline=color,width=2,dash=(5,3),tags='saved')
                elif kind=='line':
                    self.canvas.create_line(*(np.asarray(data)*self.scale).ravel(),fill=color,width=2,dash=(5,3),tags='saved')
                else:
                    (x,y),radius=data
                    self.canvas.create_oval((x-radius)*self.scale,(y-radius)*self.scale,(x+radius)*self.scale,(y+radius)*self.scale,outline=color,width=2,dash=(5,3),tags='saved')
                    self.canvas.create_line((x-3)*self.scale,y*self.scale,(x+3)*self.scale,y*self.scale,fill=color,tags='saved')
                    self.canvas.create_text(x*self.scale,(y-radius)*self.scale-10,text=label,fill=color,anchor='s',tags='saved')
        if self.rect:
            x,y,rw,rh=self.rect;self.canvas.create_rectangle(x*self.scale,y*self.scale,(x+rw)*self.scale,(y+rh)*self.scale,outline='#00ff70',width=2)
        for i,(x,y) in enumerate(self.points):
            x,y=x*self.scale,y*self.scale
            self.canvas.create_line(x-9,y,x+9,y,fill='#00ff70',width=2)
            self.canvas.create_line(x,y-9,x,y+9,fill='#00ff70',width=2)
            self.canvas.create_text(x+12,y-12,text=str(i+1),fill='#00ff70')
        info=self.mode or ('Automatic pupil estimates — review before running' if self.setup and not self.setup.manual_pupils else 'Preview')
        if self.show_saved.get():info+=' | Blue dashed: saved preset; green/yellow: new selection'
        if self.mode and self.mode.startswith('pupil') and len(self.points)==2:
            cx,cy=self.points[0];r=float(np.linalg.norm(np.array(self.points[1])-self.points[0]))
            self.canvas.create_oval((cx-r)*self.scale,(cy-r)*self.scale,(cx+r)*self.scale,(cy+r)*self.scale,outline='yellow',width=2)
            info+=f' | center ({cx:.1f}, {cy:.1f}), radius {r:.1f} original pixels'
        elif self.mode=='ruler' and len(self.points)==2:
            p=np.array(self.points)*self.scale;self.canvas.create_line(*p.ravel(),fill='yellow',width=2)
            info+=f' | {np.linalg.norm(np.array(self.points[1])-self.points[0]):.2f} original pixels'
        elif self.rect:info+=f' | {self.rect}'
        self.selection_info.set(info)

    def mapped(self,event):
        return self.geometry.point(self.canvas.canvasx(event.x),self.canvas.canvasy(event.y)) if self.geometry else None

    def press(self,event):
        if self.busy or not self.mode:return
        p=self.mapped(event)
        if p is None:return
        self.canvas.focus_set()
        if self.mode=='roi':self.drag_start=p;self.rect=None
        elif len(self.points)<2:self.points.append(p)
        self.render()

    def drag(self,event):
        if self.mode=='roi' and self.drag_start is not None and not self.busy:
            p=self.mapped(event)
            if p:self.rect=self.geometry.rectangle(self.drag_start,p);self.render()

    def release(self,event):
        self.drag(event);self.drag_start=None

    def reset(self):
        if self.busy:return
        self.points=[];self.rect=None;self.drag_start=None;self.render()
        return 'break'

    def undo(self):
        if self.busy:return
        if self.points:self.points.pop()
        else:self.rect=None
        self.render();return 'break'

    def confirm(self):
        if not self.mode or self.busy:return
        if self.mode.startswith('pupil') and not self.setup.manual_pupils:return
        if self.mode=='roi':
            if not self.rect or min(self.rect[2:])<=0:
                messagebox.showinfo('Selection needed','Drag a rectangle around the entire eye.');return
            self.setup.change_geometry(roi=self.rect)
            self.store.save(self.setup);self.apply();return
        if len(self.points)!=2:
            messagebox.showinfo('Selection needed','Click two points, then confirm.');return
        if np.linalg.norm(np.array(self.points[1])-self.points[0])<=0:
            messagebox.showerror('Invalid selection','The points must be different.');return
        if self.mode=='ruler':self.setup.ruler_points=[p.copy() for p in self.points]
        else:
            self.setup.pupils[int(self.mode[-1])]={'center_xy':self.points[0].copy(),'radius_px':float(np.linalg.norm(np.array(self.points[1])-self.points[0]))}
        self.store.save(self.setup);self.mode=None;self.render();self.refresh();self.selection_info.set('Selection saved. Use the selection buttons to redo it.')

    def append_log(self,text):
        self.log.configure(state='normal');self.log.insert('end',text+'\n');self.log.see('end');self.log.configure(state='disabled')

    def run(self):
        if not self.setup or self.busy:return
        # Parse settings again so edits cannot launch using stale distance/times.
        try:
            if [float(self.t1.get()),float(self.t2.get())]!=self.setup.times:
                raise ValueError('Apply changed timestamps before running.')
            self.setup.distance_cm=float(self.distance.get())
            folder=self.root/'results'/'gui'/(Path(self.setup.video).stem+'_'+datetime.now().strftime('%Y%m%d_%H%M%S')+'_'+uuid.uuid4().hex[:6])
            cfg=effective_config(self.setup,self.base,folder,self.root)
            folder.mkdir(parents=True);config=folder/'run_config.yaml';config.write_text(yaml.safe_dump(cfg,sort_keys=False))
        except Exception as exc:messagebox.showerror('Cannot run',str(exc));return
        self.store.save(self.setup);self.last_run=folder;self.figures=[];self.report_menu.configure(values=[])
        self.busy=True;self.cancel_requested=False;self.progress['value']=0;self.tabs.select(1)
        self.report_names.set('');self.result_image.configure(image='',text='Running… results will appear here.')
        self.append_log('New run: '+str(folder))
        self.status.set('Starting notebooks…')
        command=[sys.executable,str(self.root/'validate_notebooks.py'),'--config',str(config),'--json-events',
                 '00_acquisition.ipynb','01_fundamentals_enhancement.ipynb','02_segmentation_morphology.ipynb','03_features_temporal.ipynb','04_compression.ipynb']
        env=os.environ.copy()
        for key in ('PSIB_VIDEO_PATH','PSIB_VIDEO_DIR','PSIB_RUN_CONFIG'):env.pop(key,None)
        try:self.process=subprocess.Popen(command,cwd=self.root,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,bufsize=1)
        except OSError as exc:
            self.busy=False;self.status.set(str(exc));self.refresh();return
        self.refresh()
        process=self.process
        def monitor():
            for line in process.stdout:
                try:self.events.put(('run_event',json.loads(line)))
                except ValueError:self.events.put(('run_event',{'event':'log','text':line.rstrip()}))
            code=process.wait();self.events.put(('run_done',code))
        threading.Thread(target=monitor,daemon=True).start()

    def cancel(self):
        if self.process and self.process.poll() is None and not self.cancel_requested:
            self.cancel_requested=True;self.status.set('Cancelling; shutting down notebook kernel…');self.process.terminate();self.refresh()

    def poll(self):
        try:
            while True:
                item=self.events.get_nowait();kind=item[0]
                if kind=='task_done':
                    _,callback,value,error=item;self.busy=False
                    if error:
                        self.frames=None;self.crops=None;self.refresh();self.status.set('Preparation failed: '+error);messagebox.showerror('Preparation failed',error)
                    else:
                        callback(value)
                        if not self.busy:self.refresh()
                elif kind=='folder_opened':
                    _,folder,error=item
                    if error:
                        self.append_log('Cannot open folder: '+error)
                        messagebox.showerror('Cannot open results folder',f'{folder}\n\n{error}')
                    else:self.append_log('Opened results folder: '+folder)
                elif kind=='run_event':
                    event=item[1];name=event.get('event')
                    if name=='module_started':self.status.set('Running '+event['notebook']);self.append_log('Running '+event['notebook'])
                    elif name=='cell_completed':
                        module=int(event['notebook'][:2]);self.progress['value']=20*(module+event['completed']/max(event['total'],1))
                        self.status.set(f"{event['notebook']} — {event['completed']}/{event['total']} cells")
                    elif name=='log':self.append_log(event.get('text',''))
                    elif name in ('failed','cancelled','complete'):
                        self.append_log(json.dumps(event));self.status.set(f"{name}: {event.get('notebook','')} cell {event.get('cell','')} {event.get('error','')[:250]}")
                elif kind=='run_done':
                    self.busy=False;self.process=None;self.refresh()
                    try:state=json.loads((self.last_run/'validation/status.json').read_text())
                    except (OSError,ValueError):state={'status':'cancelled' if self.cancel_requested else 'failed','error':'Runner exited before saving status'}
                    if state['status']=='running':state['status']='cancelled' if self.cancel_requested else 'failed'
                    self.status.set(f"Run {state['status']}. Results: {self.last_run}" if state['status']=='complete' else f"Run {state['status']}: {state.get('notebook','')} cell {state.get('cell','')} {state.get('error','')[:180]}")
                    if state['status']=='complete':self.progress['value']=100
                    self.figures=sorted((self.last_run/'figures').glob('*.png'));self.figure_index=0;self.figure(0)
                    reports=sorted(p.name for p in (self.last_run/'validation').glob('*.html'));self.report_menu.configure(values=reports)
                    if reports:self.report_names.set(reports[0])
        except queue.Empty:pass
        self.window.after(100,self.poll)

    def figure(self,step):
        if not self.figures:return
        self.figure_index=(self.figure_index+step)%len(self.figures)
        with Image.open(self.figures[self.figure_index]) as im:
            im.thumbnail((1000,470));self.result_photo=ImageTk.PhotoImage(im.copy())
        self.result_image.configure(image=self.result_photo,text=self.figures[self.figure_index].name,compound='top')

    def open_results(self):
        folder=self.last_run or self.root/'results'
        def worker():
            try:
                opened=open_folder(folder)
                self.events.put(('folder_opened',str(opened),None))
            except Exception as exc:self.events.put(('folder_opened',str(folder),str(exc)))
        threading.Thread(target=worker,daemon=True).start()

    def open_report(self):
        if self.last_run and self.report_names.get():
            report=self.last_run/'validation'/self.report_names.get()
            if report.is_file():webbrowser.open(report.as_uri())

    def close(self):
        if self.busy:
            messagebox.showinfo('Work in progress','Cancel the run and wait for cleanup before closing. Frame preparation finishes automatically.');return
        self.window.destroy()


def main(root):
    try:window=tk.Tk()
    except tk.TclError as exc:
        raise SystemExit(f'Cannot open desktop GUI: {exc}. Run from a desktop session with a display.')
    DesktopApp(window,root);window.mainloop()

#prueba