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
| 4 — Compression | Huffman, horizontal/vertical RLE, JPEG quality comparisons and whole-video diameter effects implemented |

Modules 0–4 run on the available examples. **Execution success is not measurement
accuracy.** Some pupil boundaries remain incorrect; manual annotations and further
recordings are needed to validate them. Written discussion answers and fully
automatic handling of unseen recordings are also pending.

## Install and open the desktop app

Python 3.12 is the tested version. Tkinter comes from the operating system or the
Python installer, not pip.

### Linux

Run commands from the repository root.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python gui.py
```

Tkinter is provided by `python3-tk` on Debian/Ubuntu. Use a desktop session.
Folder opening needs the system's `xdg-open` or `gio`.

### Windows

**Quick start (recommended)**

1. Install **64-bit Python 3.12** with pip, the Python launcher (`py`), and
   **Tcl/Tk and IDLE** enabled. See the [Python Windows installation guide](https://docs.python.org/3.12/using/windows.html).
2. Download the repository: on its GitHub page, click **Code → Download ZIP**.
   Right-click the downloaded ZIP and choose **Extract All**. Open the extracted
   folder until you can see `gui.py`, `requirements.txt` and `PSIB.bat`.
3. **Double-click `PSIB.bat`.**

The first launch installs the program automatically: it creates the `.venv`
environment and installs `requirements.txt`. This needs an internet connection
and can take a few minutes; a console window shows the progress. Later launches
skip the installation and open the app directly.

Choose your video with **Choose video…**; recordings are not bundled with the
repository.

What `PSIB.bat` does, in order:

1. Moves to its own folder, so it works from any location, including a shortcut.
2. If `.venv` does not exist, creates it with `py -3.12` and installs the
   requirements. If either step fails, it prints the reason and waits for a key.
   A partly installed `.venv` is removed so the next launch retries cleanly.
3. Starts `gui.py` with the environment's Python. The console closes by itself
   when you close the app.

**Optional: desktop shortcut.** Right-click `PSIB.bat` → **Show more options** →
**Send to** → **Desktop (create shortcut)**. In the shortcut's **Properties** you
can set **Run: Minimized** and change its icon.

**If something goes wrong**

| Message or symptom | What to do |
| --- | --- |
| "Could not create the environment" | Python 3.12 or the `py` launcher is missing. Reinstall Python with the options in step 1 |
| "Dependency installation failed" | Check your internet connection and double-click `PSIB.bat` again |
| The console shows "Press any key to continue" after the app closes | The app exited with an error. Read the message above it |
| A Tkinter / `_tkinter` error | Modify the Python installation to include **Tcl/Tk and IDLE**; do not install it through pip |
| You changed `requirements.txt` or the environment is broken | Delete the `.venv` folder and double-click `PSIB.bat` again |

**Manual setup (alternative)**

Use this if you prefer to run the commands yourself, for example during
development. Use **Command Prompt (CMD)**, run one command at a time and press
**Enter** after each. Open CMD in the folder containing `gui.py`: click the
**address bar** in File Explorer, type `cmd` and press Enter.

```cmd
py -3.12 --version
py -3.12 -m venv .venv
.venv\Scripts\activate.bat
python -m pip install -r requirements.txt
python gui.py
```

`py -3.12 --version` should print `Python 3.12.x`. Creating `.venv` and installing
packages are one-time steps. In a new CMD window, run only
`.venv\Scripts\activate.bat` and `python gui.py`; you should see **`(.venv)`** at
the start of the command line. Type `deactivate` to leave the environment.

**Optional: open the notebooks in JupyterLab**

With `(.venv)` visible in CMD, install the optional notebook interface once:

```cmd
python -m pip install -r requirements-notebooks.txt
```

Then start it with:

```cmd
python -m jupyterlab
```

The regular GUI does not require JupyterLab. Advanced terminal execution, also
from the activated environment, uses a prepared configuration with numeric pupil
initializations:

```cmd
python validate_notebooks.py --config "C:/path/to/run_config.yaml"
```

Replace `C:/path/to/run_config.yaml` with the actual path to your configuration.
For manual YAML configuration, use forward slashes in Windows paths, for example
`video_path: "C:/Users/YourName/Videos/A_2.mp4"`. Keep machine-specific settings in
`config.local.yaml`. Create a new Windows environment rather than copying a Linux
`.venv` folder. See Python's [virtual environment documentation](https://docs.python.org/3.12/library/venv.html).

**Windows notes**

- **Open results folder** opens the run's directory in File Explorer. HTML reports
  open in your browser.
- **Cancel run** ends the notebook runner and its kernels with `taskkill`. This has
  not been systematically validated on Windows (Linux is the tested platform). If a
  `python.exe` process stays alive after cancelling, end it from Task Manager.
- Closing the window is blocked while a run or frame preparation is active. Cancel
  the run first and wait for it to finish.

## Run an analysis

New to the app? Follow the [step-by-step GUI walkthrough](documentation.md#3-desktop-workflow-a-guided-walkthrough).
The documentation also maps [each button to its Python functions](documentation.md#51-functions-behind-the-buttons).
See the [frontend guide](documentation.md#55-frontend-structure-and-layout) for widgets, layout, events and image rendering.

The **Checklist** panel on the left shows what is done (✔), what to do next (▶)
and what is pending (○). Steps that do not apply, such as the ruler when
Calibration is off, are marked with –. A short hint under the list explains the
current step, **Go to next step ▶** opens its tool, and clicking a step in the list
does the same. The status line above the progress bar always says what is missing.

1. Choose a video and apply the primary/secondary timestamps.
2. Enable **Select eye ROI** to draw a crop; disable it for full-frame measurements.
3. Enable **Calibration** to select two ruler marks a known distance apart,
   normally 1 cm. Disable it for pixel-only measurements.
4. Leave **Select pupils manually** on to select a center and boundary point in
   each comparison frame. Turn it off to estimate both pupils automatically. Use
   **Primary estimate** / **Secondary estimate** to review the blue dashed circles.
5. Confirm any manual selections, then click **Run all notebooks (0–4)**.
6. Inspect the plots and executed notebook reports in **Results & log**. The
   execution log is hidden by default; use **Show log** to display it.

Use Zoom/Fit and scrollbars. Space resets a draft selection; Backspace/right click
undoes a point; Enter confirms. **Show saved presets** displays previous selections
as blue dashed overlays. Presets are remembered per video in the ignored
`.psib_gui/` folder. Changing video/timestamps/ROI requires new dependent selections.

The app runs notebooks without additional selection windows. Progress and Cancel
are available; the status line names the current module and completed cells. Each
run gets its own `results/gui/<video>_<run id>/` directory,
including configuration, CSVs, figures, notebooks, HTML reports and execution status.
Failed/cancelled runs retain labelled partial outputs. Source notebooks and prior
results are preserved.

An eye ROI is recommended for automatic mode. Automatic initialization is a
heuristic, not a validated pupil boundary. If it
cannot find an unambiguous candidate, Run stays disabled: select a tighter eye ROI
or turn manual selection back on. Full-frame mode follows a local eye region to
estimate the second pupil, while keeping measurement frames full-size. Manual
points and automatic estimates are stored separately in the per-video profile.

## Optional GPU processing

1. Start the app (`PSIB.bat` on Windows, or `python gui.py` from the activated
   virtual environment).
2. Tick **Request GPU (OpenCL)**, below the pupil-selection toggle.
3. Read the message beside it. **OpenCL GPU available** means supported steps
   can request the GPU. **GPU unavailable … using CPU** means the run will still
   work, using the CPU instead.
4. Choose the video, finish your selections, and run the notebooks normally.
   Leave the checkbox off to use the original CPU paths.

This option applies to mean/median/Gaussian filters and Fourier transforms in
Module 1. Pupil segmentation, eye tracking, JPEG compression and the remaining
steps stay on the CPU. Fourier operations require GPU float64 support; otherwise
those operations also use CPU. OpenCV may silently run individual supported
operations on the CPU, and small images can be slower with GPU transfers.

The option is remembered per video. No extra pip packages are needed, but a
working **OpenCL GPU runtime and driver** must be installed on the computer.
The app does not install or change drivers. If the unavailable message appears,
leave the checkbox off to continue normally. AMD GPUs use OpenCL here, not CUDA.

Each run records availability, device, UMat dispatch attempts and explicit CPU
fallbacks in `acceleration/process_*.json` under the run's results folder. These
reports do not prove that individual GPU kernels ran. See the
[OpenCV OpenCL notes](https://github.com/opencv/opencv/wiki/OpenCL-optimizations)
for its automatic per-operation fallback behavior.

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
`notebooks/00_acquisition.ipynb` through `04_compression.ipynb` in order.
Restart the kernel after code changes. For terminal execution:

```bash
python validate_notebooks.py
python validate_notebooks.py 02_segmentation_morphology.ipynb
python validate_notebooks.py --config /absolute/path/run_config.yaml --json-events
```

Prepared configurations must include numeric pupil initializations (manual or
GUI-estimated). Kernel execution needs local ports. See [documentation.md](documentation.md) for exact configuration,
coordinate and calibration conventions.

## Verify changes

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
python -m pip check
```

On Windows CMD, open the project folder and activate the environment first.
These checks are for development; they are not needed to launch the app:

```cmd
.venv\Scripts\activate.bat
set "PYTHONPATH=src"
python -m unittest discover -s tests -v
python -m pip check
set "PYTHONPATH="
```

Synthetic tests check processing and workflow behavior, not anatomical accuracy.
Inspect overlays and compare with manually annotated frames before interpreting
latency, amplitude or speed. Equivalent diameter comes from mask area, not an
anatomical circle fit. Ruler calibration assumes a suitable plane and stable
camera distance.

## Repository contents

`src/psib/` contains reusable processing and GUI code; `notebooks/` contains the
experiments; `tests/` contains focused checks. `gui.py` starts the desktop app and
`PSIB.bat` is its Windows launcher and installer. The application creates `results/`
locally for generated figures, measurements, executed notebooks and reports. This
entire directory is ignored and is not part of the repository. Source notebooks
are committed without saved cell outputs or execution counts. Clear those outputs
before committing notebooks that you ran manually; GUI runs already write executed
copies under the ignored results directory.

Videos, environments, presets, local settings and caches are also ignored. Older
Git commits may still contain previously published results; removing them from the
current tree does not rewrite repository history.

The source code is small compared with generated reports. See the documentation's
maintenance section for the debloat audit and approved cleanup decisions.

## Compression study

Module 4 compares Huffman, horizontal/vertical RLE and JPEG Q=90/50/10/5 on the
selected frames and segmented regions. It also reruns the whole video at JPEG
Q=50/10 to compare diameter curves, rejection rates and exploratory response
parameters against uncompressed processing. This adds two JPEG passes and an
independent baseline to execution time. These are differences from the existing
pipeline, not anatomical accuracy scores.

Selected-frame compressed files, CSVs and figures are retained. Temporal JPEGs
are processed in memory by default. Set `module4.save_all_frames: true` in your
configuration to save every temporal JPEG for a future example recording; these
bulk files are ignored by Git. The example video and publication set will be
chosen separately. No additional packages are required.