# PSIB — Pupillary light reflex analysis

Eye video → pupil segmentation → area/diameter curve → exploratory response
estimates, following the Biomedical Signal and Image Processing practical guide.

**[Read the project documentation](documentation.md)** for architecture,
configuration precedence, algorithms, output formats and maintenance notes.

## Current status

| Module | Status |
| --- | --- |
| 0 — Acquisition | Inventory, timestamp/lighting checks and selected-video image preview implemented |
| 1 — Image fundamentals | Sampling, color, enhancement, filters, edges, Fourier and quality comparisons implemented |
| 2 — Segmentation | Multiple methods, morphology and optional reference-mask comparison implemented |
| 3 — Features and dynamics | Shape/texture, moving eye ROI, temporal curves and exploratory response estimates implemented |
| 4 — Compression | Pending |

Modules 0–3 run on the available examples. **Execution success is not measurement
accuracy.** Some pupil boundaries remain incorrect; manual annotations and further
recordings are needed to validate them. Written discussion answers and fully
automatic handling of unseen recordings are also pending.

## Install and open the desktop app

Use Linux and the tested Python 3.12 environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python gui.py
```

Tkinter comes from the operating system (`python3-tk` on Debian/Ubuntu), not pip.
Use a desktop session. Folder opening needs the system's `xdg-open` or `gio`.

## Run an analysis

1. Choose a video and apply the primary/secondary timestamps.
2. Enable **Select eye ROI** to draw a crop; disable it for full-frame measurements.
3. Enable **Calibration** to select two ruler marks a known distance apart,
   normally 1 cm. Disable it for pixel-only measurements.
4. Select the pupil center and a boundary point in each comparison frame.
5. Confirm each selection, then click **Run all notebooks (0–3)**.
6. Inspect the plots and executed notebook reports in **Results & log**.

Use Zoom/Fit and scrollbars. Space resets a draft selection; Backspace/right click
undoes a point; Enter confirms. **Show saved presets** displays previous selections
as blue dashed overlays. Presets are remembered per video in the ignored
`.psib_gui/` folder. Changing video/timestamps/ROI requires new dependent selections.

The app runs notebooks without additional selection windows. Progress and Cancel
are available. Each run gets its own `results/gui/<video>_<run id>/` directory,
including configuration, CSVs, figures, notebooks, HTML reports and execution status.
Failed/cancelled runs retain labelled partial outputs. Source notebooks and prior
results are preserved.

## Configuration and other entry points

- `config.yaml`: portable example settings.
- `config.local.yaml`: optional ignored machine-specific settings, preferred by
  ordinary notebook runs and the GUI.
- GUI-generated run configurations override old video-path environment variables.
- Videos in `data/` are ignored. Inputs may also live outside the repository.

To use notebooks manually, install the optional interface first:

```bash
python -m pip install -r requirements-notebooks.txt
python -m jupyterlab
```

Open it from the repository root and run
`notebooks/00_acquisition.ipynb` through `03_features_temporal.ipynb` in order.
Restart the kernel after code changes. For terminal execution:

```bash
python validate_notebooks.py
python validate_notebooks.py 02_segmentation_morphology.ipynb
python validate_notebooks.py --config /absolute/path/run_config.yaml --json-events
```

Prepared configurations must include manual selections. Kernel execution needs
local ports. See [documentation.md](documentation.md) for exact configuration,
coordinate and calibration conventions.

## Verify changes

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
python -m pip check
```

Synthetic tests check processing and workflow behavior, not anatomical accuracy.
Inspect overlays and compare with manually annotated frames before interpreting
latency, amplitude or speed. Equivalent diameter comes from mask area, not an
anatomical circle fit. Ruler calibration assumes a suitable plane and stable
camera distance.

## Repository contents

`src/psib/` contains reusable processing and GUI code; `notebooks/` contains the
experiments; `tests/` contains focused checks; `results/` contains saved outputs and
validation evidence. Some committed results include eye images and original local
execution paths. Videos, environments, presets, local settings and caches are ignored.

The source code is small compared with generated reports. See the documentation's
maintenance section for the debloat audit and approved cleanup decisions.
