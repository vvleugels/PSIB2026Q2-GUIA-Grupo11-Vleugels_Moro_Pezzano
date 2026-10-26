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
from tkinter import font as tkfont

import numpy as np
from PIL import Image, ImageTk
import yaml

from .initialization import estimate_comparison_pupils
from .acceleration import probe_gpu
from .gui_model import (Setup, ProfileStore, CanvasGeometry, prepare_views,
                        effective_config, saved_overlays)
from .video_io import scan_video, read_frames_at_times
from .system_open import open_folder
from .theme import (INK, INK_MUTED, INK_SOFT, IRIS, IRIS_DARK, IRIS_LIGHT, AMBER, AMBER_LIGHT, BG,
                    TEXT, CANVAS_BG, Stepper, apply_theme, card, mark_image)

NOTEBOOKS = ['00_acquisition.ipynb', '01_fundamentals_enhancement.ipynb',
             '02_segmentation_morphology.ipynb', '03_features_temporal.ipynb',
             '04_compression.ipynb']
MODULE_NAMES = ['Acquisition', 'Fundamentals', 'Segmentation', 'Features & time', 'Compression']
TOOLS = [('1. Eye ROI', 'roi'), ('2. Ruler endpoints', 'ruler'),
         ('3. Primary pupil', 'pupil0'), ('4. Secondary pupil', 'pupil1')]
INSTRUCTIONS = {
    'roi': 'Drag a rectangle around the whole eye (with a little skin around it), then press Confirm.',
    'ruler': 'Click the two ruler marks that are exactly the entered distance apart, then press Confirm.',
    'pupil': 'Click the pupil center first, then one point on its edge, then press Confirm.',
}

SAVED_COLOR = '#55c5ff'
DRAFT_COLOR = '#00ff70'


def filled(value):
    """True when a stored selection (list, array or dict) exists and is not empty."""
    return value is not None and len(value) > 0


def field_row(parent, row, text, variable):
    """Label + entry on one grid row (the entry stretches); returns the entry."""
    parent.columnconfigure(1, weight=1)
    ttk.Label(parent, text=text, style='Card.TLabel').grid(row=row, column=0, sticky='w', pady=2)
    entry = ttk.Entry(parent, textvariable=variable, width=8)
    entry.grid(row=row, column=1, sticky='ew', padx=(10, 0), pady=2)
    return entry


def autowrap(label):
    """Wrap a label's text to the width it is given."""
    label.bind('<Configure>', lambda event: label.configure(wraplength=max(event.width - 4, 100)))


def flatten(image):
    """RGB copy of an image, with transparency shown over white."""
    rgba = image.convert('RGBA')
    return Image.alpha_composite(Image.new('RGBA', rgba.size, 'white'), rgba).convert('RGB')


def module_label(notebook):
    index = int(notebook[:2])
    return f'module {index + 1}/{len(NOTEBOOKS)}: {MODULE_NAMES[index]}'


class Tooltip:
    """Small hint shown when the mouse rests on a widget."""

    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.window = None
        self.job = None
        widget.bind('<Enter>', self.schedule, add='+')
        widget.bind('<Leave>', self.hide, add='+')
        widget.bind('<ButtonPress>', self.hide, add='+')

    def schedule(self, event=None):
        self.job = self.widget.after(500, self.show)

    def show(self):
        x = self.widget.winfo_rootx() + 12
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 4
        self.window = tk.Toplevel(self.widget)
        self.window.wm_overrideredirect(True)
        self.window.wm_geometry(f'+{x}+{y}')
        tk.Label(self.window, text=self.text, justify='left', wraplength=320,
                 background='#fffbe6', foreground=TEXT, relief='solid',
                 borderwidth=1, padx=8, pady=5).pack()

    def hide(self, event=None):
        if self.job:
            self.widget.after_cancel(self.job)
            self.job = None
        if self.window:
            self.window.destroy()
            self.window = None


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
        self.auto_fit = True

        # Results state
        self.figures = []
        self.figure_index = 0
        self.result_photo = None
        self.result_pil = None
        self.result_size = None
        self.result_scale = 1.0
        self.result_fit = True
        self.result_message = ''
        self.sidebar_visible = True
        self.sidebar_width = 344

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
        self.instruction = tk.StringVar()
        self.advanced_summary = tk.StringVar()
        self.report_names = tk.StringVar()
        self.progress_text = tk.StringVar(value='0%')
        self.note_title = tk.StringVar()
        self.note_body = tk.StringVar()
        self.figure_counter = tk.StringVar()

        window.title('PSIB — Pupil analysis')
        window.minsize(900, 600)
        window.protocol('WM_DELETE_WINDOW', self.close)
        self.maximize()
        self.fonts = apply_theme(window)
        self.set_icon()

        self.build_appbar()
        bottom = ttk.Frame(window, padding=(14, 6, 14, 12))
        bottom.pack(side='bottom', fill='x')
        self.paned = tk.PanedWindow(window, orient='horizontal', sashwidth=12, sashrelief='flat',
                                    background=BG, borderwidth=0)
        self.paned.pack(fill='both', expand=True, padx=14, pady=(8, 0))
        self.build_sidebar()
        self.main = ttk.Frame(self.paned)
        self.paned.add(self.sidebar, minsize=270, stretch='never')
        self.paned.add(self.main, minsize=480, stretch='always')
        self.tabs = ttk.Notebook(self.main)
        self.tabs.pack(fill='both', expand=True)
        setup_tab = ttk.Frame(self.tabs, style='Card.TFrame', padding=10)
        results_tab = ttk.Frame(self.tabs, style='Card.TFrame', padding=10)
        self.tabs.add(setup_tab, text='Setup')
        self.tabs.add(results_tab, text='Results & log')
        self.build_setup_tab(setup_tab)
        self.build_results_tab(results_tab)
        self.build_bottom(bottom)
        self.add_tooltips()

        # Stepper rows press the matching button (no-op if it is disabled).
        self.step_buttons = [self.browse_button, self.apply_button,
                             *self.select_buttons, self.run_button]
        for variable in (self.t1, self.t2, self.distance):
            variable.trace_add('write', lambda *args: self.refresh())
        for sequence in ('<MouseWheel>', '<Button-4>', '<Button-5>'):
            window.bind_all(sequence, self.on_wheel)
        self.show_result_message('Run the notebooks to see the figures here.')
        self.refresh()
        window.after(100, self.poll)

    # ------------------------------------------------------------------- look
    def maximize(self):
        """Open maximized so the Run button is always visible."""
        try:
            if sys.platform == 'win32':
                self.window.state('zoomed')
            else:
                self.window.attributes('-zoomed', True)
        except tk.TclError:
            self.window.geometry('1280x800')

    def set_icon(self):
        """Use the PSIB mark (or assets/icon.png) as the window and taskbar icon."""
        try:
            self.icon = ImageTk.PhotoImage(mark_image(self.root, 64, 'icon', 'logo'))
            self.window.iconphoto(True, self.icon)
        except tk.TclError:
            pass   # a missing or invalid icon should never stop the app

    # ------------------------------------------------------------------ layout
    def build_appbar(self):
        bar = tk.Frame(self.window, background=INK)
        bar.pack(fill='x')
        self.logo = ImageTk.PhotoImage(mark_image(self.root, 34, 'logo', 'icon'))
        tk.Label(bar, image=self.logo, background=INK).pack(side='left', padx=(16, 10), pady=8)
        tk.Label(bar, text='PSIB', font=self.fonts.title, foreground='white',
                 background=INK).pack(side='left')
        tk.Label(bar, text='Pupil light-reflex analysis', font=self.fonts.base,
                 foreground=INK_MUTED, background=INK).pack(side='left', padx=14, pady=(5, 0))
        self.sidebar_button = tk.Button(bar, text='◀ Hide panel', command=self.toggle_sidebar,
                                        font=self.fonts.base, relief='flat', borderwidth=0,
                                        padx=12, pady=5, cursor='hand2', background=INK_SOFT,
                                        foreground='white', activebackground=IRIS,
                                        activeforeground='white')
        self.sidebar_button.pack(side='right', padx=16)
        tk.Frame(self.window, background=AMBER, height=3).pack(fill='x')

    def build_sidebar(self):
        """Left panel with every setting, scrollable so it fits any screen height."""
        self.sidebar = tk.Frame(self.paned, background=BG)
        self.side_canvas = tk.Canvas(self.sidebar, background=BG, highlightthickness=0, width=330)
        scroll = ttk.Scrollbar(self.sidebar, orient='vertical', command=self.side_canvas.yview)
        self.side_canvas.configure(yscrollcommand=scroll.set)
        scroll.pack(side='right', fill='y')
        self.side_canvas.pack(side='left', fill='both', expand=True)
        body = ttk.Frame(self.side_canvas, padding=(0, 0, 8, 8))
        body_id = self.side_canvas.create_window(0, 0, window=body, anchor='nw')
        self.side_canvas.bind('<Configure>',
                              lambda e: self.side_canvas.itemconfigure(body_id, width=e.width))
        body.bind('<Configure>',
                  lambda e: self.side_canvas.configure(scrollregion=self.side_canvas.bbox('all')))

        outer, video = card(body, 'Video')
        outer.pack(fill='x', pady=(0, 8))
        ttk.Entry(video, textvariable=self.video_var, state='readonly').pack(fill='x', pady=(4, 0))
        details = ttk.Label(video, textvariable=self.details, style='CardMuted.TLabel')
        details.pack(fill='x', pady=4)
        autowrap(details)
        self.browse_button = ttk.Button(video, text='Choose video…', command=self.browse)
        self.browse_button.pack(fill='x')

        outer, frames = card(body, 'Frames to compare')
        outer.pack(fill='x', pady=(0, 8))
        grid = ttk.Frame(frames, style='Card.TFrame')
        grid.pack(fill='x', pady=(4, 0))
        self.time1 = field_row(grid, 0, 'Primary (s)', self.t1)
        self.time2 = field_row(grid, 1, 'Secondary (s)', self.t2)
        self.apply_button = ttk.Button(frames, text='Apply / load frames', command=self.apply)
        self.apply_button.pack(fill='x', pady=(6, 0))

        outer, measure = card(body, 'Measurement')
        outer.pack(fill='x', pady=(0, 8))
        self.roi_toggle = ttk.Checkbutton(measure, text='Select eye ROI', variable=self.roi,
                                          style='Card.TCheckbutton', command=self.toggle)
        self.roi_toggle.pack(anchor='w', pady=(4, 2))
        self.cal_toggle = ttk.Checkbutton(measure, text='Calibration', variable=self.cal,
                                          style='Card.TCheckbutton', command=self.toggle)
        self.cal_toggle.pack(anchor='w', pady=2)
        grid = ttk.Frame(measure, style='Card.TFrame')
        grid.pack(fill='x')
        self.distance_entry = field_row(grid, 0, 'Ruler (cm)', self.distance)

        # Advanced options stay folded away until the user asks for them.
        self.advanced_row = ttk.Frame(body)
        self.advanced_row.pack(fill='x', pady=(0, 8))
        self.advanced_button = ttk.Button(self.advanced_row, text='Advanced options ▸',
                                          style='Link.TButton', command=self.toggle_advanced)
        self.advanced_button.pack(side='left')
        ttk.Label(self.advanced_row, textvariable=self.advanced_summary,
                  style='Muted.TLabel').pack(side='right')

        self.advanced, advanced = card(body, 'Advanced')   # packed by toggle_advanced
        self.pupil_toggle = ttk.Checkbutton(advanced, text='Select pupils manually',
                                            variable=self.manual_pupils, style='Card.TCheckbutton',
                                            command=self.toggle)
        self.pupil_toggle.pack(anchor='w', pady=(4, 0))
        explanation = ttk.Label(advanced, style='CardMuted.TLabel',
                                text='Off: estimate both pupils automatically and review the blue dashed circles.')
        explanation.pack(fill='x', pady=(0, 8))
        autowrap(explanation)
        self.gpu_toggle = ttk.Checkbutton(advanced, text='Request GPU (OpenCL)', variable=self.gpu,
                                          style='Card.TCheckbutton', command=self.toggle_gpu)
        self.gpu_toggle.pack(anchor='w')
        gpu_message = ttk.Label(advanced, textvariable=self.gpu_details, style='CardMuted.TLabel')
        gpu_message.pack(fill='x')
        autowrap(gpu_message)

        outer, steps = card(body, 'Steps')
        outer.pack(fill='x')
        self.stepper = Stepper(steps, self.fonts, 7, lambda index: self.step_buttons[index].invoke())
        self.stepper.pack(fill='x', pady=(4, 0))
        self.hint = ttk.Label(steps, justify='left', style='Card.TLabel')
        self.hint.pack(fill='x', pady=8)
        autowrap(self.hint)
        self.next_button = ttk.Button(steps, text='Go to next step ▶', style='Next.TButton',
                                      command=self.next_step)
        self.next_button.pack(fill='x')

    def toggle_advanced(self):
        if self.advanced.winfo_manager():
            self.advanced.pack_forget()
            self.advanced_button.configure(text='Advanced options ▸')
        else:
            self.advanced.pack(fill='x', pady=(0, 8), after=self.advanced_row)
            self.advanced_button.configure(text='Advanced options ▾')

    def toggle_sidebar(self):
        if self.sidebar_visible:
            self.sidebar_width = self.sidebar.winfo_width()
            self.paned.forget(self.sidebar)
            self.sidebar_button.configure(text='▶ Show panel')
        else:
            self.paned.add(self.sidebar, before=self.main, minsize=270,
                           width=self.sidebar_width, stretch='never')
            self.sidebar_button.configure(text='◀ Hide panel')
        self.sidebar_visible = not self.sidebar_visible

    def build_setup_tab(self, tab):
        bar = ttk.Frame(tab, style='Card.TFrame')
        bar.pack(fill='x', pady=(0, 8))
        # Zoom controls are packed first so they are never squeezed out.
        zoom_controls = [('Fit', None, 'Fit the image to the window.'),
                         ('−', .8, 'Zoom out.'), ('+', 1.25, 'Zoom in.')]
        for text, factor, tip in zoom_controls:
            command = self.fit if factor is None else (lambda f=factor: self.zoom(f))
            button = ttk.Button(bar, text=text, style='Tool.TButton', width=4 if factor else 5,
                                command=command)
            button.pack(side='right', padx=(4, 0))
            Tooltip(button, tip)
        self.select_buttons = []
        for text, mode in TOOLS:
            button = ttk.Button(bar, text=text, style='Tool.TButton',
                                command=lambda m=mode: self.select(m))
            button.pack(side='left', padx=(0, 4))
            self.select_buttons.append(button)

        # Amber callout: what to do on the image right now.
        callout = tk.Frame(tab, background=AMBER_LIGHT)
        callout.pack(fill='x', pady=(0, 8))
        tk.Frame(callout, background=AMBER, width=4).pack(side='left', fill='y')
        message = ttk.Label(callout, textvariable=self.instruction, style='Callout.TLabel', anchor='w')
        message.pack(side='left', fill='x', expand=True)
        message.bind('<Configure>', lambda e: message.configure(wraplength=max(e.width - 30, 200)))

        # The rows below the image are packed before it, so the image shrinks first
        # and Confirm / Reset stay visible on short windows.
        action = ttk.Frame(tab, style='Card.TFrame')
        action.pack(side='bottom', fill='x')
        self.confirm_button = ttk.Button(action, text='Confirm selection', style='Accent.TButton',
                                         command=self.confirm)
        self.confirm_button.pack(side='right')
        self.reset_button = ttk.Button(action, text='Reset', command=self.reset)
        self.reset_button.pack(side='right', padx=6)
        ttk.Label(action, text='Space: reset • Backspace / right click: undo • Enter: confirm',
                  style='CardMuted.TLabel').pack(side='left')
        info_row = ttk.Frame(tab, style='Card.TFrame')
        info_row.pack(side='bottom', fill='x', pady=4)
        self.saved_toggle = ttk.Checkbutton(info_row, text='Show saved presets', variable=self.show_saved,
                                            style='Card.TCheckbutton', command=self.render)
        self.saved_toggle.pack(side='right')
        ttk.Label(info_row, textvariable=self.selection_info, style='Card.TLabel').pack(side='left')

        area = ttk.Frame(tab, style='Card.TFrame')
        area.pack(fill='both', expand=True)
        self.canvas = tk.Canvas(area, background=CANVAS_BG, highlightthickness=0, takefocus=True)
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
        self.canvas.bind('<Configure>', self.on_canvas_resize)

    def build_results_tab(self, tab):
        bar = ttk.Frame(tab, style='Card.TFrame')
        bar.pack(fill='x', pady=(0, 8))
        self.log_button = ttk.Button(bar, text='Show log ▲', command=self.toggle_log)
        self.log_button.pack(side='right', padx=(4, 0))
        for text, step, tip in (('Next ▶', 1, 'Next figure.'), ('◀ Prev', -1, 'Previous figure.')):
            button = ttk.Button(bar, text=text, style='Tool.TButton', command=lambda s=step: self.figure(s))
            button.pack(side='right', padx=(4, 0))
            Tooltip(button, tip)
        ttk.Button(bar, text='Results folder', command=self.open_results).pack(side='left')
        self.report_menu = ttk.Combobox(bar, textvariable=self.report_names, state='readonly', width=16)
        self.report_menu.pack(side='left', padx=6)
        ttk.Button(bar, text='Open report', command=self.open_report).pack(side='left')

        # What the figure on display shows (texts live in figure_notes.yaml).
        note = tk.Frame(tab, background=IRIS_LIGHT)
        note.pack(fill='x', pady=(0, 8))
        tk.Frame(note, background=IRIS, width=4).pack(side='left', fill='y')
        text = ttk.Frame(note, style='Info.TFrame', padding=(12, 8))
        text.pack(side='left', fill='x', expand=True)
        ttk.Label(text, textvariable=self.note_title, style='InfoTitle.TLabel').pack(anchor='w')
        body = ttk.Label(text, textvariable=self.note_body, style='Info.TLabel', justify='left')
        body.pack(fill='x', anchor='w')
        autowrap(body)

        tools = ttk.Frame(tab, style='Card.TFrame')
        tools.pack(fill='x', pady=(0, 6))
        for text, factor, tip in (('Fit', None, 'Fit the figure to the window.'),
                                  ('−', .8, 'Zoom out.'), ('+', 1.25, 'Zoom in.')):
            command = self.fit_result if factor is None else (lambda f=factor: self.zoom_result(f))
            button = ttk.Button(tools, text=text, style='Tool.TButton', width=4 if factor else 5,
                                command=command)
            button.pack(side='right', padx=(4, 0))
            Tooltip(button, tip)
        ttk.Label(tools, textvariable=self.figure_counter, style='Card.TLabel',
                  font=self.fonts.bold).pack(side='left')
        ttk.Label(tools, text='Drag to move  •  Ctrl + wheel to zoom',
                  style='CardMuted.TLabel').pack(side='left', padx=12)

        self.log = tk.Text(tab, height=9, wrap='word', state='disabled', relief='flat', borderwidth=0,
                           background=BG, foreground=TEXT, padx=10, pady=8)   # shown on demand
        self.viewer = ttk.Frame(tab, style='Card.TFrame')
        self.viewer.pack(fill='both', expand=True)
        self.result_canvas = tk.Canvas(self.viewer, background=CANVAS_BG, highlightthickness=0,
                                       width=100, height=100, cursor='fleur')
        vscroll = ttk.Scrollbar(self.viewer, orient='vertical', command=self.result_canvas.yview)
        hscroll = ttk.Scrollbar(self.viewer, orient='horizontal', command=self.result_canvas.xview)
        self.result_canvas.configure(xscrollcommand=hscroll.set, yscrollcommand=vscroll.set)
        vscroll.pack(side='right', fill='y')
        hscroll.pack(side='bottom', fill='x')
        self.result_canvas.pack(fill='both', expand=True)
        self.result_canvas.bind('<ButtonPress-1>', lambda e: self.result_canvas.scan_mark(e.x, e.y))
        self.result_canvas.bind('<B1-Motion>', lambda e: self.result_canvas.scan_dragto(e.x, e.y, gain=1))
        self.result_canvas.bind('<Configure>', lambda e: self.draw_result())

    def build_bottom(self, bottom):
        ttk.Label(bottom, textvariable=self.status, wraplength=940, font=self.fonts.bold).pack(anchor='w')
        row = ttk.Frame(bottom)
        row.pack(fill='x', pady=(6, 0))
        self.run_button = ttk.Button(row, text='Run all notebooks (0–4)', style='Accent.TButton',
                                     command=self.run)
        self.run_button.pack(side='right')
        self.cancel_button = ttk.Button(row, text='Cancel run', command=self.cancel)
        self.cancel_button.pack(side='right', padx=8)
        ttk.Label(row, textvariable=self.progress_text, width=5, anchor='e',
                  style='Muted.TLabel').pack(side='right')
        self.progress = ttk.Progressbar(row, maximum=100)
        self.progress.pack(side='left', fill='x', expand=True)

    def add_tooltips(self):
        tips = [
            (self.browse_button, 'Pick the eye recording to analyze (mp4, mov, avi or mkv).'),
            (self.time1, 'Time in the recording (seconds) of the first comparison frame, '
                         'usually before the light change.'),
            (self.time2, 'Time of the second comparison frame, after the light change. It must be '
                         'later than the primary time and not beyond the last frame.'),
            (self.apply_button, 'Loads the two frames and follows the eye between them. '
                                'Click it after changing the times.'),
            (self.roi_toggle, 'Recommended. You draw a rectangle around the eye and the program '
                              'follows it through the video. Off: the full frame is measured.'),
            (self.cal_toggle, 'Turn on if the video shows a ruler: sizes are then reported in cm/mm. '
                              'Off: results are in pixels.'),
            (self.distance_entry, 'Real distance between the two ruler marks you will click '
                                  '(normally 1 cm).'),
            (self.pupil_toggle, 'On: you click the center and edge of each pupil. Off: the program '
                                'estimates both pupils and you only review them.'),
            (self.gpu_toggle, 'Optional speed-up of some Module 1 filters on an OpenCL GPU. '
                              'If no GPU is found, the CPU is used.'),
            (self.saved_toggle, 'Blue dashed shapes are saved selections or automatic estimates. '
                                'Green/yellow shapes are the selection you are drawing now.'),
            (self.next_button, 'Opens the tool for the first pending step.'),
            (self.log_button, 'Shows the raw messages printed by the notebooks. '
                              'Useful when something fails.'),
            (self.run_button, 'Runs notebooks 0 to 4 with the current setup. '
                              'Enabled when the checklist is complete.'),
            (self.cancel_button, 'Stops the current run. Partial results are kept.'),
        ]
        tools = ['Draw a rectangle around the eye. The program follows it through the video.',
                 'Mark two ruler points a known distance apart to convert pixels to cm.',
                 'Mark the pupil center and one edge point on the primary frame, '
                 'or review the automatic estimate.',
                 'Same as the primary pupil, on the secondary frame.']
        tips += list(zip(self.select_buttons, tools))
        for widget, text in tips:
            Tooltip(widget, text)

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
            self.view_mode = None
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
            self.refresh()
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
                hint = (f'Click "{index + 3}. {name} estimate" and check the blue circle. If it is '
                        'wrong, tighten the eye ROI or select pupils manually (Advanced options).')
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
        """Redraw the stepper; returns (steps, index of the next pending step)."""
        steps = self.steps()
        nxt = next((i for i, step in enumerate(steps) if step[2] == 'todo'), None)
        self.stepper.update_steps([(title, state) for title, hint, state in steps], nxt)
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

    def instruction_text(self):
        """One sentence telling the user what to do on the image right now."""
        if self.setup is None:
            return 'Start by choosing an eye recording with the "Choose video…" button.'
        if self.frames is None:
            return 'Preparing the comparison frames…'
        if self.mode:
            return INSTRUCTIONS['pupil' if self.mode.startswith('pupil') else self.mode]
        if self.view_mode and self.view_mode.startswith('pupil') and not self.manual_pupils.get():
            return ('Blue circle = automatic estimate. Check that it matches the pupil; if not, '
                    'tighten the eye ROI or select pupils manually (Advanced options).')
        if self.view_mode:
            return 'Selection saved. Use the checklist to redo it or continue with the next step.'
        return 'Frames ready. Follow the checklist on the left: the ▶ step is what to do next.'

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

        self.advanced_summary.set(f"{'Manual' if self.manual_pupils.get() else 'Auto'} pupils"
                                  f"  ·  GPU {'on' if self.gpu.get() else 'off'}")
        self.instruction.set(self.instruction_text())
        if self.image is None:
            self.draw_placeholder()

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

    def fit(self, update=True):
        if self.image is None:
            return
        if update:
            self.window.update_idletasks()
        self.auto_fit = True
        h, w = self.image.shape[:2]
        self.scale = min(max(self.canvas.winfo_width() - 20, 100) / w,
                         max(self.canvas.winfo_height() - 20, 100) / h)
        self.canvas.xview_moveto(0)
        self.canvas.yview_moveto(0)
        self.render()

    def zoom(self, factor):
        if self.image is None:
            return
        self.auto_fit = False
        self.scale = max(.1, min(self.scale * factor, 16))
        self.render()

    def on_canvas_resize(self, event):
        if self.image is None:
            self.draw_placeholder()
        elif self.auto_fit:
            self.fit(update=False)   # keep the image fitted while the window is resized

    def draw_placeholder(self):
        """Empty state: what PSIB measures and how to start."""
        self.canvas.delete('all')
        w, h = self.canvas.winfo_width(), self.canvas.winfo_height()
        cx, cy = w / 2, h / 2
        if self.setup is not None:
            self.canvas.create_text(cx, cy, text='Preparing frames…', fill='#e5e7eb', font=self.fonts.bold)
            return
        steps = ('How it works\n1. Choose an eye recording\n2. Pick two frames to compare and click Apply\n'
                 '3. Mark the eye, the ruler and the pupils\n4. Run all notebooks and read the results\n\n'
                 'Your next step is always highlighted in amber.')
        if h < 290:
            self.canvas.create_text(cx, cy, text=steps, fill='#e5e7eb', font=self.fonts.base, justify='center')
            return
        # Two eyes: the pupil contracts under bright light, which is what PSIB measures.
        r = 38
        top = cy - 125
        for dx, pupil, caption in ((-120, 24, 'Dim light: wide pupil'), (120, 10, 'Bright light: small pupil')):
            x, y = cx + dx, top + r + 2
            self.canvas.create_oval(x - r, y - r, x + r, y + r, fill=IRIS, outline=AMBER, width=3)
            self.canvas.create_oval(x - 27, y - 27, x + 27, y + 27, fill=IRIS_DARK, outline='')
            self.canvas.create_oval(x - pupil, y - pupil, x + pupil, y + pupil, fill=INK, outline='')
            self.canvas.create_oval(x + 5, y - 17, x + 13, y - 9, fill='white', outline='')
            self.canvas.create_text(x, y + r + 16, text=caption, fill=INK_MUTED, font=self.fonts.base)
        self.canvas.create_text(cx, top + 2 * r + 46, text=steps, fill='#e5e7eb', font=self.fonts.base,
                                justify='center', anchor='n')

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
        """Draw the unsaved selection and show its measurements."""
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

        info = ''
        if self.mode and self.mode.startswith('pupil') and len(self.points) == 2:
            cx, cy = self.points[0]
            r = float(np.linalg.norm(np.array(self.points[1]) - self.points[0]))
            self.canvas.create_oval((cx - r) * s, (cy - r) * s, (cx + r) * s, (cy + r) * s,
                                    outline='yellow', width=2)
            info = f'Pupil center ({cx:.1f}, {cy:.1f}), radius {r:.1f} px'
        elif self.mode == 'ruler' and len(self.points) == 2:
            line = np.array(self.points) * s
            self.canvas.create_line(*line.ravel(), fill='yellow', width=2)
            length = float(np.linalg.norm(np.array(self.points[1]) - self.points[0]))
            info = f'Ruler length: {length:.1f} px'
            if self.distance_ok():
                info += f'  →  {length / float(self.distance.get()):.1f} px/cm'
        elif self.rect:
            info = f'ROI (x, y, width, height): {self.rect}'
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

    # --------------------------------------------------------------- notebooks
    def append_log(self, text):
        self.log.configure(state='normal')
        self.log.insert('end', text + '\n')
        self.log.see('end')
        self.log.configure(state='disabled')

    def toggle_log(self):
        if self.log.winfo_manager():
            self.log.pack_forget()
            self.log_button.configure(text='Show log ▲')
        else:
            self.log.pack(side='bottom', fill='x', before=self.viewer)
            self.log_button.configure(text='Hide log ▼')

    def set_progress(self, value):
        self.progress['value'] = value
        self.progress_text.set(f'{value:.0f}%')

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
        self.set_progress(0)
        self.tabs.select(1)
        self.report_names.set('')
        self.show_result_message('Running… results will appear here.')
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
                # /T also ends the child processes (the notebook kernels)
                subprocess.run(['taskkill', '/PID', str(self.process.pid), '/T', '/F'],
                               capture_output=True)
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
            self.set_progress(20 * (module + event['completed'] / max(event['total'], 1)))
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
            self.set_progress(100)
        else:
            self.status.set(f"Run {state['status']}: {state.get('notebook', '')} "
                            f"cell {state.get('cell', '')} {state.get('error', '')[:180]}")
            if not self.log.winfo_manager():
                self.toggle_log()   # show the details when something went wrong
        self.figures = sorted((self.last_run / 'figures').glob('*.png'))
        self.figure_index = 0
        if self.figures:
            self.figure(0)
        else:
            self.show_result_message('No figures were saved for this run.')
        reports = sorted(p.name for p in (self.last_run / 'validation').glob('*.html'))
        self.report_menu.configure(values=reports)
        if reports:
            self.report_names.set(reports[0])

    # ----------------------------------------------------------------- results
    def figure(self, step):
        """Show the figure `step` positions away from the current one, with its explanation."""
        if not self.figures:
            return
        self.figure_index = (self.figure_index + step) % len(self.figures)
        path = self.figures[self.figure_index]
        try:
            with Image.open(path) as image:
                self.result_pil = flatten(image)
        except OSError as exc:
            self.show_result_message(f'Cannot open {path.name}: {exc}')
            return
        self.result_size = None
        self.result_fit = True
        title, text = self.figure_note(path)
        self.note_title.set(title)
        self.note_body.set(text)
        self.figure_counter.set(f'Figure {self.figure_index + 1} of {len(self.figures)}')
        self.draw_result()
        self.result_canvas.xview_moveto(0)
        self.result_canvas.yview_moveto(0)

    def figure_note(self, path):
        """(title, explanation) of a figure, read from figure_notes.yaml in the project folder."""
        try:
            notes = yaml.safe_load((self.root / 'figure_notes.yaml').read_text(encoding='utf-8'))
        except (OSError, yaml.YAMLError):
            notes = None
        notes = notes if isinstance(notes, dict) else {}
        stem = path.stem
        text = notes.get(stem)
        if text is None:   # patterns such as "m4_*"; the longest match wins
            patterns = [str(key) for key in notes if str(key).endswith('*') and stem.startswith(str(key)[:-1])]
            if patterns:
                text = notes[max(patterns, key=len)]
        if not text:
            text = f'No explanation yet. Add a "{stem}:" entry with its text to figure_notes.yaml.'
        return stem, str(text).strip()

    def show_result_message(self, text):
        """Replace the figure with a short message (nothing to show yet, running, ...)."""
        self.result_pil = None
        self.result_message = text
        self.note_title.set('Results')
        self.note_body.set('After a run, each figure appears here with a short explanation of what it shows.')
        self.figure_counter.set('')
        self.draw_result()

    def draw_result(self):
        canvas = self.result_canvas
        canvas.delete('all')
        cw, ch = max(canvas.winfo_width(), 1), max(canvas.winfo_height(), 1)
        if self.result_pil is None:
            canvas.configure(scrollregion=(0, 0, cw, ch))
            canvas.create_text(cw / 2, ch / 2, text=self.result_message, fill='#e5e7eb',
                               font=self.fonts.base, justify='center')
            return
        w, h = self.result_pil.size
        if self.result_fit:
            self.result_scale = min(max(cw - 4, 50) / w, max(ch - 4, 50) / h, 1.0)
        dw, dh = max(1, round(w * self.result_scale)), max(1, round(h * self.result_scale))
        if (dw, dh) != self.result_size:   # resize only when the displayed size changes
            method = Image.Resampling.LANCZOS if self.result_scale < 1 else Image.Resampling.BILINEAR
            self.result_photo = ImageTk.PhotoImage(self.result_pil.resize((dw, dh), method))
            self.result_size = (dw, dh)
        sw, sh = max(dw, cw), max(dh, ch)
        canvas.configure(scrollregion=(0, 0, sw, sh))
        canvas.create_image(sw / 2, sh / 2, image=self.result_photo, anchor='center')

    def fit_result(self):
        if self.result_pil is None:
            return
        self.result_fit = True
        self.draw_result()
        self.result_canvas.xview_moveto(0)
        self.result_canvas.yview_moveto(0)

    def zoom_result(self, factor):
        if self.result_pil is None:
            return
        w, h = self.result_pil.size
        limit = min(8.0, (40e6 / (w * h)) ** .5)   # keep the zoomed image a manageable size
        self.result_fit = False
        self.result_scale = max(.05, min(self.result_scale * factor, limit))
        self.draw_result()

    def on_wheel(self, event):
        """Mouse wheel scrolls the area under the pointer; Ctrl + wheel zooms images."""
        try:
            widget = self.window.winfo_containing(event.x_root, event.y_root)
        except (KeyError, tk.TclError):
            return   # pointer is over a popup menu
        zoomers = {self.canvas: self.zoom, self.result_canvas: self.zoom_result, self.side_canvas: None}
        while widget is not None and widget not in zoomers:
            widget = widget.master
        if widget is None:
            return
        steps = -1 if event.num == 4 or (event.num != 5 and event.delta > 0) else 1
        if event.state & 0x4 and zoomers[widget]:
            zoomers[widget](1.25 if steps < 0 else .8)
        elif event.state & 0x1:
            widget.xview_scroll(steps * 3, 'units')
        else:
            widget.yview_scroll(steps * 3, 'units')

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
    if sys.platform == 'win32':
        import ctypes   # own taskbar identity, not grouped with python.exe
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('psib.pupil.analysis')
    try:
        window = tk.Tk()
    except tk.TclError as exc:
        raise SystemExit(f'Cannot open desktop GUI: {exc}. Run from a desktop session with a display.')
    DesktopApp(window, root)
    window.mainloop()
    os._exit(0)