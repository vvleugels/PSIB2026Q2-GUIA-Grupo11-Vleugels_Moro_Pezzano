"""Visual identity of the PSIB desktop app: palette, fonts, ttk styles, logo mark and stepper."""
import tkinter as tk
from tkinter import ttk
from tkinter import font as tkfont
from types import SimpleNamespace

from PIL import Image, ImageDraw

# Iris teal gives the structure; amber (light) is reserved for "what to do now".
INK = '#0f2e36'
INK_MUTED = '#9db8be'
INK_SOFT = '#1c4752'
IRIS = '#0e7c86'
IRIS_DARK = '#0a5f67'
IRIS_LIGHT = '#d7eef0'
AMBER = '#f5a524'
AMBER_DARK = '#dd9013'
AMBER_LIGHT = '#fff4dc'
BG = '#f2f5f5'
CARD = '#ffffff'
BORDER = '#d9e1e2'
TEXT = '#17262b'
MUTED = '#62767c'
CANVAS_BG = '#10242a'


def make_mark(size):
    """Draw the PSIB mark (a pupil inside an iris, ringed by light) as an RGBA image."""
    s = size * 4
    image = Image.new('RGBA', (s, s), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    c = s / 2

    def circle(radius, **kwargs):
        draw.ellipse([c - radius, c - radius, c + radius, c + radius], **kwargs)

    circle(s * 0.48, fill=IRIS)
    circle(s * 0.48, outline=AMBER, width=max(2, int(s * 0.04)))
    circle(s * 0.34, fill=IRIS_DARK)
    circle(s * 0.20, fill=INK)
    gx, gy, gr = c + s * 0.07, c - s * 0.09, s * 0.055
    draw.ellipse([gx - gr, gy - gr, gx + gr, gy + gr], fill='white')
    return image.resize((size, size), Image.Resampling.LANCZOS)


def mark_image(root, size, *names):
    """Use assets/<name>.png when the project has one, otherwise draw the default mark."""
    for name in names:
        path = root / 'assets' / f'{name}.png'
        if path.is_file():
            try:
                with Image.open(path) as image:
                    return image.convert('RGBA').resize((size, size), Image.Resampling.LANCZOS)
            except OSError:
                continue
    return make_mark(size)


def apply_theme(window):
    """Configure fonts and ttk styles for the light theme; returns the fonts the app uses."""
    families = set(tkfont.families(window))
    family = next((f for f in ('Inter', 'Segoe UI', 'Ubuntu', 'Noto Sans', 'Cantarell')
                   if f in families), None)
    for name in ('TkDefaultFont', 'TkTextFont', 'TkMenuFont', 'TkHeadingFont'):
        font = tkfont.nametofont(name)
        font.configure(size=10)
        if family:
            font.configure(family=family)
    tkfont.nametofont('TkFixedFont').configure(size=10)

    base = tkfont.nametofont('TkDefaultFont')
    fonts = SimpleNamespace(base=base, bold=base.copy(), title=base.copy(), small=base.copy())
    fonts.bold.configure(weight='bold')
    fonts.title.configure(size=16, weight='bold')
    fonts.small.configure(size=9, weight='bold')

    style = ttk.Style()
    style.theme_use('clam')
    window.configure(background=BG)
    style.configure('.', background=BG, foreground=TEXT, bordercolor=BORDER, focuscolor=BG)
    style.configure('TLabel', background=BG)
    style.configure('Muted.TLabel', foreground=MUTED)

    # Cards: white surfaces with their own label / checkbutton variants.
    style.configure('Card.TFrame', background=CARD)
    style.configure('Card.TLabel', background=CARD)
    style.configure('CardMuted.TLabel', background=CARD, foreground=MUTED)
    style.configure('CardTitle.TLabel', background=CARD, foreground=MUTED, font=fonts.small)
    style.configure('Info.TFrame', background=IRIS_LIGHT)
    style.configure('Info.TLabel', background=IRIS_LIGHT, foreground=INK)
    style.configure('InfoTitle.TLabel', background=IRIS_LIGHT, foreground=IRIS_DARK, font=fonts.bold)
    style.configure('Callout.TLabel', background=AMBER_LIGHT, foreground=INK, padding=(12, 8))
    style.configure('Card.TCheckbutton', background=CARD)
    style.map('Card.TCheckbutton', background=[('active', CARD)],
              indicatorbackground=[('selected', IRIS), ('!selected', 'white')],
              indicatorforeground=[('selected', 'white')])

    style.configure('TEntry', padding=5, fieldbackground='white')
    style.map('TEntry', fieldbackground=[('readonly', '#eef2f3'), ('disabled', '#eef2f3')],
              bordercolor=[('focus', IRIS)])
    style.configure('TCombobox', fieldbackground='white', arrowcolor=MUTED)
    style.map('TCombobox', fieldbackground=[('readonly', 'white')])

    style.configure('TButton', padding=(12, 6), background='#e6edee', borderwidth=1)
    style.map('TButton', background=[('disabled', '#f0f4f4'), ('active', '#d5e0e2')],
              foreground=[('disabled', '#a2b0b3')])
    style.configure('Tool.TButton', padding=(8, 5))
    style.configure('Accent.TButton', padding=(18, 8), background=IRIS, foreground='white',
                    font=fonts.bold, bordercolor=IRIS)
    style.map('Accent.TButton', background=[('disabled', '#a9cfd3'), ('active', IRIS_DARK)],
              foreground=[('disabled', 'white')])
    style.configure('Next.TButton', background=AMBER, foreground=INK, font=fonts.bold,
                    bordercolor=AMBER)
    style.map('Next.TButton', background=[('disabled', '#f1e3c4'), ('active', AMBER_DARK)],
              foreground=[('disabled', '#9a8c6a')])
    style.configure('Link.TButton', background=BG, foreground=IRIS, borderwidth=0, padding=(2, 4))
    style.map('Link.TButton', background=[('active', BG)], foreground=[('active', IRIS_DARK)])

    style.configure('TNotebook', background=BG, borderwidth=0)
    style.configure('TNotebook.Tab', padding=(18, 8), background='#e3eaeb', foreground=MUTED)
    style.map('TNotebook.Tab', background=[('selected', CARD)],
              foreground=[('selected', IRIS_DARK)])
    style.configure('Horizontal.TProgressbar', troughcolor='#dfe8e9', background=IRIS,
                    bordercolor='#dfe8e9', thickness=12)
    for orient in ('Vertical', 'Horizontal'):
        style.configure(f'{orient}.TScrollbar', background='#c3d0d2', troughcolor=BG,
                        bordercolor=BG, arrowcolor=MUTED)
    return fonts


def card(parent, title):
    """White bordered panel with a small caption; returns (outer frame to pack, inner frame to fill)."""
    outer = tk.Frame(parent, background=CARD, highlightbackground=BORDER,
                     highlightcolor=BORDER, highlightthickness=1)
    inner = ttk.Frame(outer, style='Card.TFrame', padding=(10, 6, 10, 8))
    inner.pack(fill='both', expand=True)
    ttk.Label(inner, text=title.upper(), style='CardTitle.TLabel').pack(anchor='w')
    return outer, inner


class Stepper(tk.Canvas):
    """Vertical list of numbered steps. Done = teal check, next = amber, pending = outline.

    Rows shrink when the window is short, so every step stays visible."""

    ROW = 33
    RADIUS = 11

    def __init__(self, parent, fonts, count, on_click, width=236):
        super().__init__(parent, width=width, height=count * self.ROW, background=CARD,
                         highlightthickness=0, cursor='hand2')
        self.fonts = fonts
        self.count = count
        self.on_click = on_click
        self.steps = []
        self.nxt = None
        self.bind('<Button-1>', self.click)
        self.bind('<Configure>', lambda event: self.draw())

    @property
    def row(self):
        return max(24, min(self.ROW, self.winfo_height() / self.count))

    def click(self, event):
        index = int(event.y // self.row)
        if 0 <= index < self.count:
            self.on_click(index)

    def update_steps(self, steps, nxt):
        """steps: list of (title, state) with state done / todo / skip; nxt: highlighted index."""
        self.steps = steps
        self.nxt = nxt
        self.draw()

    def draw(self):
        self.delete('all')
        row, nxt = self.row, self.nxt
        width = self.winfo_width()
        x, r = 20, min(self.RADIUS, row / 2 - 3)
        for i, (title, state) in enumerate(self.steps):
            y = i * row + row / 2
            if i == nxt:
                self.create_rectangle(0, i * row + 2, width, (i + 1) * row - 2,
                                      fill=AMBER_LIGHT, outline='')
            if i < len(self.steps) - 1:
                self.create_line(x, y + r, x, y + row - r, width=2,
                                 fill=IRIS if state == 'done' else BORDER)
        for i, (title, state) in enumerate(self.steps):
            y = i * row + row / 2
            box = (x - r, y - r, x + r, y + r)
            if state == 'done':
                self.create_oval(*box, fill=IRIS, outline=IRIS)
                glyph, glyph_color = '✔', 'white'
            elif i == nxt:
                self.create_oval(*box, fill=AMBER, outline=AMBER)
                glyph, glyph_color = str(i + 1), INK
            elif state == 'skip':
                self.create_oval(*box, fill='#eef2f3', outline='#d5dcdd')
                glyph, glyph_color = '–', MUTED
            else:
                self.create_oval(*box, fill=CARD, outline='#b4c3c6', width=2)
                glyph, glyph_color = str(i + 1), MUTED
            self.create_text(x, y, text=glyph, fill=glyph_color, font=self.fonts.small)
            weight = self.fonts.bold if i == nxt else self.fonts.base
            color = TEXT if state == 'done' or i == nxt else MUTED
            self.create_text(x + r + 12, y, text=title, anchor='w', fill=color, font=weight)