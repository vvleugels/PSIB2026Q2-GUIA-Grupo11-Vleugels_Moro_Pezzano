"""Video reading utilities.

Phone recordings are usually *variable frame rate* and carry a rotation flag.
OpenCV applies the rotation automatically, so width/height reported here are
the ones of the decoded (upright) frames. Frames are selected by their real
presentation timestamp, never by ``frame_index / nominal_fps``, and always by
sequential decoding (seeking with ``CAP_PROP_POS_MSEC`` snaps to keyframes and
can land >100 ms away from the requested time).
"""
from __future__ import annotations

import fnmatch
from pathlib import Path

import cv2
import numpy as np


def _open(path) -> cv2.VideoCapture:
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise FileNotFoundError(f"Cannot open video: {path}")
    if hasattr(cv2, "CAP_PROP_ORIENTATION_AUTO"):
        cap.set(cv2.CAP_PROP_ORIENTATION_AUTO, 1)  # honour the phone rotation flag
    return cap


def list_videos(video_dir, patterns=("A_*.mp4", "B_*.mp4")) -> list[Path]:
    """Videos in ``video_dir`` matching any glob pattern, sorted by name (A first, then B)."""
    folder = Path(video_dir)
    if not folder.is_dir():
        raise FileNotFoundError(f"Video folder not found: {folder}")
    found = [p for p in folder.iterdir() if any(fnmatch.fnmatch(p.name, pat) for pat in patterns)]
    return sorted(found, key=lambda p: p.name.lower())


def record_type(path) -> str:
    """'A' (dark->light) or 'B' (light->dark) from the file name, '?' otherwise."""
    name = Path(path).name.upper()
    return name[0] if name[:1] in ("A", "B") else "?"


def scan_video(path, downscale: float = 0.25) -> dict:
    """Decode the whole video once and return timestamps and mean gray level per frame.

    Returns a dict with: width, height, fps_nominal, n_frames, timestamps_s (array),
    brightness (array, mean gray level of each downscaled frame), duration_s.
    """
    cap = _open(path)
    fps_nominal = cap.get(cv2.CAP_PROP_FPS)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    ts, bright = [], []
    while True:
        ok, bgr = cap.read()
        if not ok:
            break
        ts.append(cap.get(cv2.CAP_PROP_POS_MSEC) / 1000.0)
        small = cv2.resize(bgr, None, fx=downscale, fy=downscale, interpolation=cv2.INTER_AREA)
        bright.append(float(cv2.cvtColor(small, cv2.COLOR_BGR2GRAY).mean()))
    cap.release()
    if not ts:
        raise ValueError(f"No frames decoded from {path}")
    ts = np.asarray(ts)
    return {
        "width": width,
        "height": height,
        "fps_nominal": float(fps_nominal),
        "n_frames": len(ts),
        "timestamps_s": ts,
        "brightness": np.asarray(bright),
        "duration_s": float(ts[-1]),
    }


def read_frames_at_times(path, times_s):
    """Single decoding pass returning, for every requested time, the closest frame.

    Returns a list (same order as ``times_s``) of ``(frame_rgb, actual_time_s, frame_index)``.
    """
    targets = [float(t) for t in times_s]
    order = sorted(range(len(targets)), key=lambda i: targets[i])
    results: list = [None] * len(targets)
    cap = _open(path)
    prev = None  # (timestamp, bgr, index)
    idx = 0
    ptr = 0
    try:
        while ptr < len(order):
            ok, bgr = cap.read()
            if not ok:
                break
            ts = cap.get(cv2.CAP_PROP_POS_MSEC) / 1000.0
            while ptr < len(order) and ts >= targets[order[ptr]]:
                t = targets[order[ptr]]
                if prev is not None and (t - prev[0]) < (ts - t):
                    p_ts, p_bgr, p_idx = prev
                    results[order[ptr]] = (cv2.cvtColor(p_bgr, cv2.COLOR_BGR2RGB), p_ts, p_idx)
                else:
                    results[order[ptr]] = (cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB), ts, idx)
                ptr += 1
            prev = (ts, bgr, idx)
            idx += 1
    finally:
        cap.release()
    for k in range(ptr, len(order)):  # targets beyond the last frame
        t = targets[order[k]]
        if prev is not None and t - prev[0] < 0.5:
            results[order[k]] = (cv2.cvtColor(prev[1], cv2.COLOR_BGR2RGB), prev[0], prev[2])
        else:
            raise ValueError(f"t = {t:.2f} s is beyond the end of the video ({path})")
    return results


def read_frame_at_time(path, t_s: float):
    """Return ``(frame_rgb, actual_time_s, frame_index)`` of the frame closest to ``t_s``."""
    return read_frames_at_times(path, [t_s])[0]
