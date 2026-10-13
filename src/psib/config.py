"""Configuration loading. The whole pipeline is driven by ``config.yaml``."""
from __future__ import annotations

import os
from pathlib import Path

import yaml


def find_project_root(start: str | Path | None = None) -> Path:
    """Walk up from ``start`` (default: cwd) until a ``config.yaml`` is found."""
    here = Path(start or Path.cwd()).resolve()
    for folder in [here, *here.parents]:
        if (folder / "config.yaml").exists():
            return folder
    raise FileNotFoundError("config.yaml not found in the current folder or any parent folder")


def load_config(path: str | Path | None = None) -> dict:
    """Load the YAML configuration.

    Environment overrides (handy for running the pipeline on a new video
    without editing any file):
        PSIB_VIDEO_PATH -> video_path
        PSIB_VIDEO_DIR  -> video_dir
    The returned dict gets two extra keys: ``_root`` (project root) and
    ``_output_dir`` (absolute output folder, already created).
    """
    cfg_path = Path(path) if path else find_project_root() / "config.yaml"
    with open(cfg_path, "r", encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh)

    if os.environ.get("PSIB_VIDEO_PATH"):
        cfg["video_path"] = os.environ["PSIB_VIDEO_PATH"]
    if os.environ.get("PSIB_VIDEO_DIR"):
        cfg["video_dir"] = os.environ["PSIB_VIDEO_DIR"]

    root = cfg_path.resolve().parent
    for key in ("video_path", "video_dir"):
        value = Path(cfg[key]).expanduser()
        cfg[key] = str(value if value.is_absolute() else root / value)

    out = Path(cfg.get("output_dir", "results"))
    out = out if out.is_absolute() else root / out
    (out / "figures").mkdir(parents=True, exist_ok=True)
    cfg["_root"] = root
    cfg["_output_dir"] = out
    return cfg
