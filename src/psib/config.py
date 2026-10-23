"""Configuration loading. The whole pipeline is driven by ``config.yaml``."""
from __future__ import annotations

import os
import warnings
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
    explicit_run = os.environ.get("PSIB_RUN_CONFIG")
    cfg_path = Path(explicit_run) if explicit_run else (Path(path) if path else find_project_root() / "config.yaml")
    local_path = cfg_path.with_name("config.local.yaml")
    if not explicit_run and cfg_path.name == "config.yaml" and local_path.is_file():
        cfg_path = local_path
    with open(cfg_path, "r", encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh)

    if not explicit_run and os.environ.get("PSIB_VIDEO_PATH"):
        if os.environ["PSIB_VIDEO_PATH"] != cfg["video_path"]:
            warnings.warn(
                f"PSIB_VIDEO_PATH overrides config.yaml: using {os.environ['PSIB_VIDEO_PATH']} "
                f"instead of {cfg['video_path']}. Unset it to use the YAML setting.",
                stacklevel=2,
            )
        cfg["video_path"] = os.environ["PSIB_VIDEO_PATH"]
    if not explicit_run and os.environ.get("PSIB_VIDEO_DIR"):
        cfg["video_dir"] = os.environ["PSIB_VIDEO_DIR"]

    defaults = dict(jpeg_qualities=[90, 50, 10, 5], temporal_qualities=[50, 10], save_all_frames=False)
    cfg['module4'] = {**defaults, **cfg.get('module4', {})}

    root = Path(cfg.get("project_root", cfg_path.resolve().parent)).resolve()
    for key in ("video_path", "video_dir"):
        value = Path(cfg[key]).expanduser()
        cfg[key] = str(value if value.is_absolute() else root / value)

    out = Path(cfg.get("output_dir", "results"))
    out = out if out.is_absolute() else root / out
    (out / "figures").mkdir(parents=True, exist_ok=True)
    acceleration = cfg.get('acceleration', {})
    if not isinstance(acceleration, dict):
        raise ValueError('acceleration must be a mapping with gpu: true or false')
    cfg['acceleration'] = {**acceleration, 'gpu': acceleration.get('gpu', False)}
    from .acceleration import configure
    info = configure(cfg['acceleration']['gpu'], out/'acceleration')
    print(info['message'])
    cfg["_root"] = root
    cfg["_output_dir"] = out
    return cfg
