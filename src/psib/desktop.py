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
from .gui_model import (Setup, ProfileStore, CanvasGeometry, prepare_views,
                        effective_config, saved_overlays)
from .video_io import scan_video, read_frames_at_times
from .system_open import open_folder

NOTEBOOKS = ['00_acquisition.ipynb', '01_fundamentals_enhancement.ipynb',
             '02_segmentation_morphology.ipynb', '03_features_temporal.ipynb',
             '04_compression.ipynb']
MODULE_NAMES = ['Acquisition', 'Fundamentals', 'Segmentation', 'Features & time', 'Compression']
TOOLS = [('1. Eye ROI', 'roi'), ('2. Ruler endpoints', 'ruler'),
         ('3. Primary pupil', 'pupil0'), ('4. Secondary pupil', 'pupil1')]

SAVED_COLOR = '#55c5ff'
DRAFT_COLOR = '#00ff70'
STEP_SYMBOL = {'done': '✔', 'todo': '○', 'skip': '–'}
STEP_COLOR = {'done': '#1a7f37', 'todo': '#444444', 'skip': '#999999', 'next': '#0b57d0'}
FONT = ('TkDefaultFont', 10)
FONT_BOLD = ('TkDefaultFont', 10, 'bold')


def filled(value):
    """True when a stored selection (list, array or dict) exists and is not empty."""
    return value is not None and len(value) > 0


def labeled_entry(parent, text, variable, width):
    ttk.Label(parent, text=text).pack(side='left', padx=(10, 0))
    entry = ttk.Entry(parent, textvariable=variable, width=width)
    entry.pack(side='left', padx=5)
    return entry


def module_label(notebook):
    index = int(notebook[:2])
    return f'module {index + 1}/{len(NOTEBOOKS)}: {MODULE_NAMES[index]}'


class DesktopApp:
    def __init__(self, window, root):
        self.window = window
        self.root = Path(root)
        base_path = self.root / 'config.local.yaml'
        if not base_path.is_file():
            base_path = self.root / 'config.yaml'
        self.base = yaml.safe_load(base_path.read_text(encoding='utf-8'))
        self.store = ProfileStore(self.root / '.psib_gui')

        # Analysis state
        self.setup = None
        self.frames = None
        self.crops = None
        self.busy = False
        self.process = None
        self.cancel_requested = False
        self.last_run = None
        self.events = queue.Queue()

        # Canvas / draft state
        self.mode = None
        self.view_mode = None
        self.points = []
        self.rect = None
        self.drag_start = None
        self.image = None
        self.photo = None
        self.geometry = None
        self.scale = 1

        # Results state
        self.figures = []
        self.figure_index = 0

        # Tk variables
        self.video_var = tk.StringVar()
        self.t1 = tk.StringVar(value='1.0')
        self.t2 = tk.StringVar(value='5.0')
        self.cal = tk.BooleanVar(value=False)
        self.roi = tk.BooleanVar(value=True)
        self.distance = tk.StringVar(value='1.0')
        self.show_saved = tk.BooleanVar(value=True)
        self.manual_pupils = tk.BooleanVar(value=True)
        self.gpu = tk.BooleanVar(value=False)
        self.gpu_details = tk.StringVar(value='GPU off — CPU processing.')
        self.status = tk.StringVar(value='Choose a video to begin.')
        self.details = tk.StringVar(value='No video loaded')
        self.selection_info = tk.StringVar()
        self.report_names = tk.StringVar()

        window.title('PSIB — Pupil analysis')
        if sys.platform == 'win32': 
            window.state('zoomed')
        else: 
            window.attributes('-zoomed', True)
        window.minsize(1000, 700)
        window.protocol('WM_DELETE_WINDOW', self.close)

        self.build_header()
        bottom = ttk.Frame(window, padding=10)
        bottom.pack(side='bottom', fill='x')
        middle = ttk.Frame(window, padding=(10, 0))
        middle.pack(fill='both', expand=True)
        self.build_steps_panel(middle)
        self.tabs = ttk.Notebook(middle)
        self.tabs.pack(side='left', fill='both', expand=True)
        setup_tab = ttk.Frame(self.tabs)
        results_tab = ttk.Frame(self.tabs)
        self.tabs.add(setup_tab, text='Setup')
        self.tabs.add(results_tab, text='Results & log')
        self.build_setup_tab(setup_tab)
        self.build_results_tab(results_tab)
        self.build_bottom(bottom)

        # Clicking a checklist row presses the matching button (no-op if disabled).
        self.step_buttons = [self.browse_button, self.apply_button,
                             *self.select_buttons, self.run_button]
        for label, button in zip(self.step_labels, self.step_buttons):
            label.bind('<Button-1>', lambda event, b=button: b.invoke())
        for variable in (self.t1, self.t2, self.distance):
            variable.trace_add('write', lambda *args: self.refresh())
        self.refresh()
        window.after(100, self.poll)

    # ------------------------------------------------------------------ layout
    def build_header(self):
        header = ttk.Frame(self.window, padding=10)
        header.pack(fill='x')
        ttk.Label(header, text='PSIB pupil analysis', font=('TkDefaultFont', 16, 'bold')).pack(anchor='w')

        row = ttk.Frame(header)
        row.pack(fill='x', pady=5)
        ttk.Entry(row, textvariable=self.video_var, state='readonly').pack(side='left', fill='x', expand=True)
        self.browse_button = ttk.Button(row, text='Choose video…', command=self.browse)
        self.browse_button.pack(side='left', padx=5)
        ttk.Label(header, textvariable=self.details).pack(anchor='w')

        controls = ttk.Frame(header)
        controls.pack(fill='x', pady=6)
        ttk.Label(controls, text='Primary (s)').pack(side='left')
        self.time1 = ttk.Entry(controls, textvariable=self.t1, width=7)
        self.time1.pack(side='left', padx=5)
        self.time2 = labeled_entry(controls, 'Secondary (s)', self.t2, 7)
        self.apply_button = ttk.Button(controls, text='Apply / load frames', command=self.apply)
        self.apply_button.pack(side='left', padx=5)
        self.cal_toggle = ttk.Checkbutton(controls, text='Calibration', variable=self.cal, command=self.toggle)
        self.cal_toggle.pack(side='left', padx=10)
        self.roi_toggle = ttk.Checkbutton(controls, text='Select eye ROI', variable=self.roi, command=self.toggle)
        self.roi_toggle.pack(side='left')
        self.distance_entry = labeled_entry(controls, 'Ruler distance (cm)', self.distance, 5)

        pupil_controls = ttk.Frame(header)
        pupil_controls.pack(fill='x')
        self.pupil_toggle = ttk.Checkbutton(pupil_controls, text='Select pupils manually',
                                            variable=self.manual_pupils, command=self.toggle)
        self.pupil_toggle.pack(side='left')
        ttk.Label(pupil_controls, text='Off: estimate both pupils automatically; '
                                       'review the blue dashed overlays.').pack(side='left', padx=8)

        gpu_controls = ttk.Frame(header)
        gpu_controls.pack(fill='x')
        self.gpu_toggle = ttk.Checkbutton(gpu_controls, text='Request GPU (OpenCL)',
                                          variable=self.gpu, command=self.toggle_gpu)
        self.gpu_toggle.pack(side='left')
        ttk.Label(gpu_controls, textvariable=self.gpu_details, wraplength=950).pack(side='left', padx=8)

    def build_steps_panel(self, parent):
        panel = ttk.LabelFrame(parent, text='Checklist', padding=8)
        panel.pack(side='left', fill='y', padx=(0, 8))
        self.step_labels = []
        for _ in range(7):
            label = ttk.Label(panel, cursor='hand2')
            label.pack(anchor='w', pady=2)
            self.step_labels.append(label)
        ttk.Label(panel, text='✔ done  ▶ next  ○ pending  – not needed',
                  foreground=STEP_COLOR['skip']).pack(anchor='w', pady=(8, 0))
        self.hint = ttk.Label(panel, wraplength=230, justify='left')
        self.hint.pack(anchor='w', pady=10)
        self.next_button = ttk.Button(panel, text='Go to next step ▶', command=self.next_step)
        self.next_button.pack(fill='x')

    def build_setup_tab(self, tab):
        bar = ttk.Frame(tab)
        bar.pack(fill='x', pady=5)
        self.select_buttons = []
        for text, mode in TOOLS:
            button = ttk.Button(bar, text=text, command=lambda m=mode: self.select(m))
            button.pack(side='left', padx=3)
            self.select_buttons.append(button)
        ttk.Checkbutton(bar, text='Show saved presets', variable=self.show_saved,
                        command=self.render).pack(side='left', padx=8)
        ttk.Button(bar, text='Fit', command=self.fit).pack(side='right')
        ttk.Button(bar, text='Zoom −', command=lambda: self.zoom(.8)).pack(side='right')
        ttk.Button(bar, text='Zoom +', command=lambda: self.zoom(1.25)).pack(side='right')

        area = ttk.Frame(tab)
        area.pack(fill='both', expand=True)
        self.canvas = tk.Canvas(area, background='#20252b', highlightthickness=0, takefocus=True)
        vscroll = ttk.Scrollbar(area, orient='vertical', command=self.canvas.yview)
        hscroll = ttk.Scrollbar(area, orient='horizontal', command=self.canvas.xview)
        self.canvas.configure(xscrollcommand=hscroll.set, yscrollcommand=vscroll.set)
        vscroll.pack(side='right', fill='y')
        hscroll.pack(side='bottom', fill='x')
        self.canvas.pack(fill='both', expand=True)
        self.canvas.bind('<ButtonPress-1>', self.press)
        self.canvas.bind('<B1-Motion>', self.drag)
        self.canvas.bind('<ButtonRelease-1>', self.release)
        self.canvas.bind('<space>', lambda e: self.reset())
        self.canvas.bind('<BackSpace>', lambda e: self.undo())
        self.canvas.bind('<Button-3>', lambda e: self.undo())
        self.canvas.bind('<Return>', lambda e: self.confirm())

        ttk.Label(tab, textvariable=self.selection_info).pack(anchor='w', pady=3)
        action = ttk.Frame(tab)
        action.pack(fill='x')
        ttk.Label(action, text='Drag ROI / click points • Space: reset • '
                               'Backspace/right click: undo • Enter: confirm').pack(side='left')
        self.confirm_button = ttk.Button(action, text='Confirm selection', command=self.confirm)
        self.confirm_button.pack(side='right')
        self.reset_button = ttk.Button(action, text='Reset', command=self.reset)
        self.reset_button.pack(side='right', padx=5)

    def build_results_tab(self, tab):
        bar = ttk.Frame(tab)
        bar.pack(fill='x', pady=5)
        ttk.Button(bar, text='Open results folder', command=self.open_results).pack(side='left')
        self.report_menu = ttk.Combobox(bar, textvariable=self.report_names, state='readonly', width=40)
        self.report_menu.pack(side='left', padx=6)
        ttk.Button(bar, text='Open notebook report', command=self.open_report).pack(side='left')
        self.log_button = ttk.Button(bar, text='Show log ▲', command=self.toggle_log)
        self.log_button.pack(side='left', padx=6)
        ttk.Button(bar, text='Previous figure', command=lambda: self.figure(-1)).pack(side='right')
        ttk.Button(bar, text='Next figure', command=lambda: self.figure(1)).pack(side='right')
        self.result_image = ttk.Label(tab, anchor='center')
        self.result_image.pack(fill='both', expand=True)
        self.log = tk.Text(tab, height=9, wrap='word', state='disabled')

    def build_bottom(self, bottom):
        ttk.Label(bottom, textvariable=self.status, wraplength=940).pack(anchor='w')
        self.progress = ttk.Progressbar(bottom, maximum=100)
        self.progress.pack(side='left', fill='x', expand=True, pady=6)
        self.cancel_button = ttk.Button(bottom, text='Cancel run', command=self.cancel)
        self.cancel_button.pack(side='right')
        self.run_button = ttk.Button(bottom, text='Run all notebooks (0–4)', command=self.run)
        self.run_button.pack(side='right', padx=8)

    # --------------------------------------------------------- background tasks
    def task(self, function, callback):
        """Run `function` in a thread; `callback(result)` runs later on the Tk thread."""
        if self.busy:
            return
        self.busy = True
        self.refresh()

        def worker():
            try:
                self.events.put(('task_done', callback, function(), None))
            except Exception as exc:
                self.events.put(('task_done', callback, None, str(exc)))

        threading.Thread(target=worker, daemon=True).start()

    def browse(self):
        path = filedialog.askopenfilename(
            title='Choose eye recording',
            filetypes=[('Videos', '*.mp4 *.mov *.avi *.mkv'), ('All files', '*')])
        if not path:
            return
        self.status.set('Reading video metadata…')

        def load():
            scan = scan_video(path)
            restored = self.store.load(path)
            setup = restored or Setup(str(Path(path).resolve()), scan['width'], scan['height'],
                                      scan['duration_s'], self.store.fingerprint(path))
            if not restored:
                setup.times = [float(self.base['frames']['primary_time_s']),
                               float(self.base['frames']['secondary_time_s'])]
            return setup

        def loaded(setup):
            self.setup = setup
            self.frames = None
            self.crops = None
            self.mode = None
            self.image = None
            self.video_var.set(setup.video)
            self.t1.set(str(setup.times[0]))
            self.t2.set(str(setup.times[1]))
            self.manual_pupils.set(setup.manual_pupils)
            self.gpu.set(setup.use_gpu)
            self.gpu_details.set('Checking GPU…' if setup.use_gpu else 'GPU off — CPU processing.')
            self.cal.set(setup.calibration_enabled)
            self.roi.set(setup.roi_enabled)
            self.distance.set(str(setup.distance_cm))
            self.details.set(f'{Path(setup.video).name}  |  {setup.width} × {setup.height}'
                             f'  |  last frame: {setup.duration:.3f} s')
            self.apply()

        self.task(load, loaded)

    def apply(self):
        if not self.setup or self.busy:
            return
        try:
            self.setup.change_geometry(times=[float(self.t1.get()), float(self.t2.get())])
            self.setup.distance_cm = float(self.distance.get())
        except ValueError:
            messagebox.showerror('Invalid settings', 'Enter numerical timestamps and ruler distance.')
            return
        self.frames = None
        self.crops = None
        self.mode = None
        self.status.set('Preparing comparison frames and tracking the eye…')

        def prepare():
            # Keep a usable reference frame when tracking the second crop fails,
            # so the user can redraw the ROI without accepting a false crop.
            frames = read_frames_at_times(self.setup.video, self.setup.times)
            try:
                _, crops = prepare_views(self.setup, self.base)
            except RuntimeError as exc:
                return frames, None, str(exc), [None, None]
            automatic = [None, None]
            roi_ok = not self.setup.roi_enabled or self.setup.roi is not None
            if not self.setup.manual_pupils and roi_ok:
                try:
                    automatic = estimate_comparison_pupils(
                        frames, crops, self.setup.video,
                        self.base['module3'].get('eye_tracking', {}),
                        self.base['module2'].get('min_component_size', 30))
                except (ValueError, RuntimeError) as exc:
                    return frames, crops, f'Automatic pupil estimation: {exc}', [None, None]
            return frames, crops, None, automatic

        def prepared(result):
            self.frames, self.crops, error, automatic = result
            self.setup.automatic_pupils = automatic
            self.store.save(self.setup)
            self.view_mode = None
            self.show_image(self.frames[0][0])
            self.refresh()
            if error:
                messagebox.showerror('Preparation needs attention', error)
            if self.gpu.get():
                self.toggle_gpu()

        self.task(prepare, prepared)

    def toggle_gpu(self):
        if self.busy:
            return
        if self.setup:
            self.setup.use_gpu = self.gpu.get()
            self.store.save(self.setup)
        if not self.gpu.get():
            self.gpu_details.set('GPU off — CPU processing.')
            return
        self.gpu_details.set('Checking OpenCL GPU…')
        self.task(probe_gpu, lambda info: self.gpu_details.set(info['message']))

    def toggle(self):
        if not self.setup:
            return
        self.setup.calibration_enabled = self.cal.get()
        self.setup.manual_pupils = self.manual_pupils.get()
        self.setup.change_geometry(roi_enabled=self.roi.get())
        self.apply()

    # ------------------------------------------------------ checklist and state
    def unapplied(self):
        """True when the time fields differ from the times already applied."""
        if self.setup is None:
            return False
        try:
            return [float(self.t1.get()), float(self.t2.get())] != self.setup.times
        except ValueError:
            return True

    def distance_ok(self):
        try:
            value = float(self.distance.get())
        except ValueError:
            return False
        return bool(np.isfinite(value) and value > 0)

    def missing_inputs(self):
        """Everything still blocking Run, as readable messages."""
        missing = list(self.setup.missing()) if self.setup else ['Choose a video']
        if self.cal.get() and not self.distance_ok():
            missing.append('Enter a positive ruler distance')
        if not missing and self.frames is not None and self.crops is None:
            missing.append('Eye crops unavailable — adjust the ROI or the times')
        return missing

    def ready_to_run(self):
        return (self.setup is not None and self.frames is not None and not self.busy
                and not self.unapplied() and not self.missing_inputs())

    def steps(self):
        """Checklist rows as (title, how-to hint, state); state is done, todo or skip."""
        s = self.setup
        loaded = s is not None
        auto = not self.manual_pupils.get()
        pupils = s.active_pupils if loaded else [None, None]

        def row(title, hint, done, needed=True):
            return title, hint, 'skip' if not needed else 'done' if done else 'todo'

        def pupil_row(index):
            name = 'Primary' if index == 0 else 'Secondary'
            if auto:
                hint = (f'Click "{index + 3}. {name} estimate" and check the blue circle. '
                        'If it is wrong, tighten the eye ROI or select pupils manually.')
            else:
                hint = (f'Click "{index + 3}. {name} pupil", click the pupil center, then one '
                        'point on its edge, and press Confirm.')
            return row(f'{name} pupil' + (' (auto)' if auto else ''), hint,
                       loaded and filled(pupils[index]))

        missing = self.missing_inputs()
        run_hint = 'Click "Run all notebooks (0–4)".' if not missing else 'Still missing: ' + '; '.join(missing)
        return [
            row('Choose video', 'Click "Choose video…" and pick the eye recording.', loaded),
            row('Apply times',
                'Set the Primary and Secondary times (seconds), then click "Apply / load frames".',
                loaded and self.frames is not None and not self.unapplied()),
            row('Eye ROI', 'Click "1. Eye ROI", drag a rectangle around the whole eye and press Confirm.',
                loaded and s.roi is not None, self.roi.get()),
            row('Ruler calibration',
                'Click "2. Ruler endpoints", mark two points at the distance entered (cm) and '
                'press Confirm. Turn Calibration off if there is no ruler.',
                loaded and filled(s.ruler_points) and self.distance_ok(), self.cal.get()),
            pupil_row(0),
            pupil_row(1),
            row('Run notebooks', run_hint, False),
        ]

    def update_checklist(self):
        """Redraw the checklist; returns (steps, index of the next pending step)."""
        steps = self.steps()
        nxt = next((i for i, step in enumerate(steps) if step[2] == 'todo'), None)
        for i, (label, (title, hint, state)) in enumerate(zip(self.step_labels, steps)):
            is_next = i == nxt
            label.configure(text=f"{'▶' if is_next else STEP_SYMBOL[state]} {i + 1}. {title}",
                            foreground=STEP_COLOR['next' if is_next else state],
                            font=FONT_BOLD if is_next else FONT)
        self.hint.configure(text=steps[nxt][1] if nxt is not None else 'Everything is set.')
        can_go = nxt is not None and nxt < len(steps) - 1 and not self.busy
        self.next_button.configure(state='normal' if can_go else 'disabled')
        return steps, nxt

    def next_step(self):
        """Press the button of the first pending step (never starts a run)."""
        steps = self.steps()
        for index, step in enumerate(steps[:-1]):
            if step[2] == 'todo':
                self.step_buttons[index].invoke()
                return

    def refresh(self):
        settings = [self.browse_button, self.apply_button, self.time1, self.time2, self.cal_toggle,
                    self.roi_toggle, self.pupil_toggle, self.gpu_toggle, self.distance_entry]
        for widget in settings:
            widget.configure(state='disabled' if self.busy else 'normal')
        ready = self.setup is not None and self.frames is not None and not self.busy
        crops_ready = ready and self.crops is not None

        for i, button in enumerate(self.select_buttons):
            if i == 0:
                enabled = ready and self.roi.get()
            elif i == 1:
                enabled = ready and self.cal.get()
            else:
                enabled = crops_ready and (not self.roi.get() or self.setup.roi is not None)
                prefix = 'Primary' if i == 2 else 'Secondary'
                kind = 'pupil' if self.manual_pupils.get() else 'estimate'
                button.configure(text=f'{i + 1}. {prefix} {kind}')
            button.configure(state='normal' if enabled else 'disabled')

        can_run = self.ready_to_run()
        process_alive = self.process is not None and self.process.poll() is None
        self.run_button.configure(state='normal' if can_run else 'disabled')
        self.distance_entry.configure(state='disabled' if self.busy or not self.cal.get() else 'normal')
        self.cancel_button.configure(state='normal' if process_alive and not self.cancel_requested else 'disabled')
        self.confirm_button.configure(state='normal' if ready and self.mode else 'disabled')
        self.reset_button.configure(state='normal' if ready and self.mode else 'disabled')

        steps, nxt = self.update_checklist()
        if self.busy:
            return
        if can_run:
            self.status.set('Ready: run all notebooks.')
        elif nxt is not None and nxt < len(steps) - 1:
            self.status.set(f'Next step: {steps[nxt][0]}')
        else:
            self.status.set('Setup needed: ' + '; '.join(self.missing_inputs()))

    # ------------------------------------------------------- selection / canvas
    def select(self, mode):
        if not self.frames or self.busy:
            return
        is_pupil = mode.startswith('pupil')
        self.mode = None if is_pupil and not self.manual_pupils.get() else mode
        self.view_mode = mode
        self.points = []
        self.rect = None
        self.drag_start = None
        if is_pupil:
            self.show_image(self.crops[int(mode[-1])][0])
        else:
            self.show_image(self.frames[0][0])
        self.canvas.focus_set()
        self.refresh()

    def show_image(self, image):
        self.image = image
        self.points = []
        self.rect = None
        self.fit()

    def fit(self):
        if self.image is None:
            return
        self.window.update_idletasks()
        h, w = self.image.shape[:2]
        self.scale = min(max(self.canvas.winfo_width() - 20, 100) / w,
                         max(self.canvas.winfo_height() - 20, 100) / h)
        self.canvas.xview_moveto(0)
        self.canvas.yview_moveto(0)
        self.render()

    def zoom(self, factor):
        if self.image is None:
            return
        self.scale = max(.1, min(self.scale * factor, 16))
        self.render()

    def render(self):
        if self.image is None:
            return
        h, w = self.image.shape[:2]
        dw, dh = max(1, round(w * self.scale)), max(1, round(h * self.scale))
        self.geometry = CanvasGeometry(w, h, self.scale)
        resized = Image.fromarray(self.image).resize((dw, dh), Image.Resampling.BILINEAR)
        self.photo = ImageTk.PhotoImage(resized)
        self.canvas.delete('all')
        self.canvas.create_image(0, 0, image=self.photo, anchor='nw')
        self.canvas.configure(scrollregion=(0, 0, max(dw, self.canvas.winfo_width()),
                                            max(dh, self.canvas.winfo_height())))
        if self.show_saved.get() and self.setup:
            self.draw_saved()
        self.draw_draft()

    def draw_saved(self):
        s = self.scale
        for kind, data, label in saved_overlays(self.setup, self.view_mode):
            if kind == 'rectangle':
                x, y, rw, rh = data
                self.canvas.create_rectangle(x * s, y * s, (x + rw) * s, (y + rh) * s,
                                             outline=SAVED_COLOR, width=2, dash=(5, 3), tags='saved')
            elif kind == 'line':
                self.canvas.create_line(*(np.asarray(data) * s).ravel(),
                                        fill=SAVED_COLOR, width=2, dash=(5, 3), tags='saved')
            else:
                (x, y), radius = data
                self.canvas.create_oval((x - radius) * s, (y - radius) * s, (x + radius) * s, (y + radius) * s,
                                        outline=SAVED_COLOR, width=2, dash=(5, 3), tags='saved')
                self.canvas.create_line((x - 3) * s, y * s, (x + 3) * s, y * s, fill=SAVED_COLOR, tags='saved')
                self.canvas.create_text(x * s, (y - radius) * s - 10, text=label,
                                        fill=SAVED_COLOR, anchor='s', tags='saved')

    def draw_draft(self):
        """Draw the unsaved selection and update the description line."""
        s = self.scale
        if self.rect:
            x, y, rw, rh = self.rect
            self.canvas.create_rectangle(x * s, y * s, (x + rw) * s, (y + rh) * s,
                                         outline=DRAFT_COLOR, width=2)
        for i, (x, y) in enumerate(self.points):
            x, y = x * s, y * s
            self.canvas.create_line(x - 9, y, x + 9, y, fill=DRAFT_COLOR, width=2)
            self.canvas.create_line(x, y - 9, x, y + 9, fill=DRAFT_COLOR, width=2)
            self.canvas.create_text(x + 12, y - 12, text=str(i + 1), fill=DRAFT_COLOR)

        info = self.mode or ('Automatic pupil estimates — review before running'
                             if self.setup and not self.setup.manual_pupils else 'Preview')
        if self.show_saved.get():
            info += ' | Blue dashed: saved preset; green/yellow: new selection'
        if self.mode and self.mode.startswith('pupil') and len(self.points) == 2:
            cx, cy = self.points[0]
            r = float(np.linalg.norm(np.array(self.points[1]) - self.points[0]))
            self.canvas.create_oval((cx - r) * s, (cy - r) * s, (cx + r) * s, (cy + r) * s,
                                    outline='yellow', width=2)
            info += f' | center ({cx:.1f}, {cy:.1f}), radius {r:.1f} original pixels'
        elif self.mode == 'ruler' and len(self.points) == 2:
            line = np.array(self.points) * s
            self.canvas.create_line(*line.ravel(), fill='yellow', width=2)
            length = np.linalg.norm(np.array(self.points[1]) - self.points[0])
            info += f' | {length:.2f} original pixels'
        elif self.rect:
            info += f' | {self.rect}'
        self.selection_info.set(info)

    def mapped(self, event):
        if not self.geometry:
            return None
        return self.geometry.point(self.canvas.canvasx(event.x), self.canvas.canvasy(event.y))

    def press(self, event):
        if self.busy or not self.mode:
            return
        point = self.mapped(event)
        if point is None:
            return
        self.canvas.focus_set()
        if self.mode == 'roi':
            self.drag_start = point
            self.rect = None
        elif len(self.points) < 2:
            self.points.append(point)
        self.render()

    def drag(self, event):
        if self.mode == 'roi' and self.drag_start is not None and not self.busy:
            point = self.mapped(event)
            if point:
                self.rect = self.geometry.rectangle(self.drag_start, point)
                self.render()

    def release(self, event):
        self.drag(event)
        self.drag_start = None

    def reset(self):
        if self.busy:
            return
        self.points = []
        self.rect = None
        self.drag_start = None
        self.render()
        return 'break'

    def undo(self):
        if self.busy:
            return
        if self.points:
            self.points.pop()
        else:
            self.rect = None
        self.render()
        return 'break'

    def confirm(self):
        if not self.mode or self.busy:
            return
        if self.mode.startswith('pupil') and not self.setup.manual_pupils:
            return
        if self.mode == 'roi':
            if not self.rect or min(self.rect[2:]) <= 0:
                messagebox.showinfo('Selection needed', 'Drag a rectangle around the entire eye.')
                return
            self.setup.change_geometry(roi=self.rect)
            self.store.save(self.setup)
            self.apply()
            return
        if len(self.points) != 2:
            messagebox.showinfo('Selection needed', 'Click two points, then confirm.')
            return
        radius = float(np.linalg.norm(np.array(self.points[1]) - self.points[0]))
        if radius <= 0:
            messagebox.showerror('Invalid selection', 'The points must be different.')
            return
        if self.mode == 'ruler':
            self.setup.ruler_points = [p.copy() for p in self.points]
        else:
            self.setup.pupils[int(self.mode[-1])] = {'center_xy': self.points[0].copy(),
                                                     'radius_px': radius}
        self.store.save(self.setup)
        self.mode = None
        self.render()
        self.refresh()
        self.selection_info.set('Selection saved. Use the selection buttons to redo it.')

    # --------------------------------------------------------------- notebooks
    def append_log(self, text):
        self.log.configure(state='normal')
        self.log.insert('end', text + '\n')
        self.log.see('end')
        self.log.configure(state='disabled')
        
    def toggle_log(self):
        if  self.log.winfo_manager():
            self.log.pack_forget()
            self.log_button.configure(text='Show log ▲')
        else:
            self.log.pack(fill='x')
            self.log_button.configure(text='Hide log ▼')

    def run(self):
        if not self.setup or self.busy:
            return
        # Parse settings again so edits cannot launch using stale distance/times.
        try:
            if [float(self.t1.get()), float(self.t2.get())] != self.setup.times:
                raise ValueError('Apply changed timestamps before running.')
            self.setup.distance_cm = float(self.distance.get())
            stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            name = f'{Path(self.setup.video).stem}_{stamp}_{uuid.uuid4().hex[:6]}'
            folder = self.root / 'results' / 'gui' / name
            cfg = effective_config(self.setup, self.base, folder, self.root)
            folder.mkdir(parents=True)
            config = folder / 'run_config.yaml'
            config.write_text(yaml.safe_dump(cfg, sort_keys=False))
        except Exception as exc:
            messagebox.showerror('Cannot run', str(exc))
            return

        self.store.save(self.setup)
        self.last_run = folder
        self.figures = []
        self.report_menu.configure(values=[])
        self.busy = True
        self.cancel_requested = False
        self.progress['value'] = 0
        self.tabs.select(1)
        self.report_names.set('')
        self.result_image.configure(image='', text='Running… results will appear here.')
        self.append_log('New run: ' + str(folder))
        self.status.set('Starting notebooks…')

        command = [sys.executable, str(self.root / 'validate_notebooks.py'),
                   '--config', str(config), '--json-events', *NOTEBOOKS]
        env = os.environ.copy()
        for key in ('PSIB_VIDEO_PATH', 'PSIB_VIDEO_DIR', 'PSIB_RUN_CONFIG'):
            env.pop(key, None)
        try:
            self.process = subprocess.Popen(command, cwd=self.root, env=env, stdout=subprocess.PIPE,
                                            stderr=subprocess.STDOUT, text=True, bufsize=1)
        except OSError as exc:
            self.busy = False
            self.status.set(str(exc))
            self.refresh()
            return
        self.refresh()
        process = self.process

        def monitor():
            for line in process.stdout:
                try:
                    self.events.put(('run_event', json.loads(line)))
                except ValueError:
                    self.events.put(('run_event', {'event': 'log', 'text': line.rstrip()}))
            self.events.put(('run_done', process.wait()))

        threading.Thread(target=monitor, daemon=True).start()

    def cancel(self):
        if self.process and self.process.poll() is None and not self.cancel_requested:
            self.cancel_requested = True
            self.status.set('Cancelling; shutting down notebook kernel…')
            if sys.platform == 'win32':
                # /T mata también los procesos hijos (los kernels de los notebooks)
                subprocess.run(['taskkill', '/PID', str(self.process.pid), '/T', '/F'], capture_output=True)
            else:
                self.process.terminate()
            self.refresh()

    # ----------------------------------------------------------- event handling
    def poll(self):
        """Consume worker events on the Tk thread (runs every 100 ms)."""
        try:
            while True:
                item = self.events.get_nowait()
                kind = item[0]
                if kind == 'task_done':
                    self.on_task_done(*item[1:])
                elif kind == 'folder_opened':
                    self.on_folder_opened(*item[1:])
                elif kind == 'run_event':
                    self.on_run_event(item[1])
                elif kind == 'run_done':
                    self.on_run_done()
        except queue.Empty:
            pass
        finally:
            self.window.after(100, self.poll)

    def on_task_done(self, callback, value, error):
        self.busy = False
        if error:
            self.frames = None
            self.crops = None
            self.refresh()
            self.status.set('Preparation failed: ' + error)
            messagebox.showerror('Preparation failed', error)
            return
        callback(value)
        if not self.busy:
            self.refresh()

    def on_folder_opened(self, folder, error):
        if error:
            self.append_log('Cannot open folder: ' + error)
            messagebox.showerror('Cannot open results folder', f'{folder}\n\n{error}')
        else:
            self.append_log('Opened results folder: ' + folder)

    def on_run_event(self, event):
        name = event.get('event')
        if name == 'module_started':
            label = module_label(event['notebook'])
            self.status.set('Running ' + label)
            self.append_log('Running ' + label)
        elif name == 'cell_completed':
            module = int(event['notebook'][:2])
            self.progress['value'] = 20 * (module + event['completed'] / max(event['total'], 1))
            self.status.set(f"{module_label(event['notebook'])} — "
                            f"{event['completed']}/{event['total']} cells done")
        elif name == 'log':
            self.append_log(event.get('text', ''))
        elif name in ('failed', 'cancelled', 'complete'):
            self.append_log(json.dumps(event))
            self.status.set(f"{name}: {event.get('notebook', '')} cell {event.get('cell', '')} "
                            f"{event.get('error', '')[:250]}")

    def on_run_done(self):
        self.busy = False
        self.process = None
        self.refresh()
        try:
            state = json.loads((self.last_run / 'validation/status.json').read_text())
        except (OSError, ValueError):
            state = {'status': 'cancelled' if self.cancel_requested else 'failed',
                     'error': 'Runner exited before saving status'}
        if state['status'] == 'running':
            state['status'] = 'cancelled' if self.cancel_requested else 'failed'
        if state['status'] == 'complete':
            self.status.set(f"Run complete. Results: {self.last_run}")
            self.progress['value'] = 100
        else:
            self.status.set(f"Run {state['status']}: {state.get('notebook', '')} "
                            f"cell {state.get('cell', '')} {state.get('error', '')[:180]}")
        self.figures = sorted((self.last_run / 'figures').glob('*.png'))
        self.figure_index = 0
        self.figure(0)
        reports = sorted(p.name for p in (self.last_run / 'validation').glob('*.html'))
        self.report_menu.configure(values=reports)
        if reports:
            self.report_names.set(reports[0])
        if state['status'] != 'complete' and not self.log.winfo_manager():
            self.toggle_log()

    # ----------------------------------------------------------------- results
    def figure(self, step):
        if not self.figures:
            return
        self.figure_index = (self.figure_index + step) % len(self.figures)
        path = self.figures[self.figure_index]
        with Image.open(path) as image:
            image.thumbnail((1000, 470))
            self.result_photo = ImageTk.PhotoImage(image.copy())
        self.result_image.configure(image=self.result_photo, text=path.name, compound='top')

    def open_results(self):
        folder = self.last_run or self.root / 'results'
        if not folder.is_dir():
            folder = self.root

        def worker():
            try:
                if sys.platform == 'win32':
                    os.startfile(folder)
                    opened = folder
                else:
                    opened = open_folder(folder)
                self.events.put(('folder_opened', str(opened), None))
            except Exception as exc:
                self.events.put(('folder_opened', str(folder), str(exc)))

        threading.Thread(target=worker, daemon=True).start()

    def open_report(self):
        if self.last_run and self.report_names.get():
            report = self.last_run / 'validation' / self.report_names.get()
            if report.is_file():
                webbrowser.open(report.as_uri())

    def close(self):
        if self.busy:
            messagebox.showinfo('Work in progress',
                                'Cancel the run and wait for cleanup before closing. '
                                'Frame preparation finishes automatically.')
            return
        self.window.destroy()


def main(root):
    try:
        window = tk.Tk()
    except tk.TclError as exc:
        raise SystemExit(f'Cannot open desktop GUI: {exc}. Run from a desktop session with a display.')
    DesktopApp(window, root)
    window.mainloop()
    if sys.platform == 'win32':
       # Mata este proceso y todos sus hijos (runner y kernels), para que no quede nada vivo.
       subprocess.run(['taskkill', '/PID', str(os.getpid()), '/T', '/F'], capture_output=True)
    os._exit(0)