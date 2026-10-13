"""Plot helpers shared by the notebooks."""
from __future__ import annotations

import math
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

plt.rcParams.update({"figure.dpi": 100, "axes.grid": False, "image.interpolation": "nearest"})


def show_grid(images, titles=None, ncols: int = 3, cell=(4.0, 4.0), cmap="gray",
              suptitle: str | None = None, vmin=None, vmax=None):
    """Show a list of images in a grid. uint8 images use the full 0-255 range."""
    n = len(images)
    nrows = math.ceil(n / ncols)
    fig, axes = plt.subplots(nrows, ncols, figsize=(cell[0] * ncols, cell[1] * nrows), squeeze=False)
    for ax in axes.ravel():
        ax.axis("off")
    for i, img in enumerate(images):
        ax = axes.ravel()[i]
        lo, hi = (0, 255) if (img.dtype == np.uint8 and vmin is None) else (vmin, vmax)
        ax.imshow(img, cmap=cmap if img.ndim == 2 else None, vmin=lo, vmax=hi)
        if titles is not None:
            ax.set_title(titles[i], fontsize=10)
    if suptitle:
        fig.suptitle(suptitle, fontsize=12)
    fig.tight_layout(h_pad=2.0, rect=(0, 0, 1, 0.96 if suptitle else 1))
    return fig


def save_fig(fig, name: str, cfg: dict, dpi: int = 130) -> Path:
    """Save a figure under ``<output_dir>/figures/<name>.png``."""
    path = cfg["_output_dir"] / "figures" / f"{name}.png"
    fig.savefig(path, dpi=dpi, bbox_inches="tight")
    return path
