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

Run commands from the repository root. Python 3.12 is the tested version.

### Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python gui.py
```

Tkinter comes from the operating system (`python3-tk` on Debian/Ubuntu), not pip.
Use a desktop session. Folder opening needs the system's `xdg-open` or `gio`.

### Windows (Command Prompt / CMD)

Use **Command Prompt (CMD)** for the steps below. Run one command at a time and
press **Enter** after each command. Wait for it to finish before entering the next.

**First-time setup**

1. Install **64-bit Python 3.12** with pip, the Python launcher (`py`), and
   **Tcl/Tk and IDLE** enabled. See the [Python Windows installation guide](https://docs.python.org/3.12/using/windows.html).
2. Download the repository: on its GitHub page, click **Code → Download ZIP**.
   Right-click the downloaded ZIP and choose **Extract All**. Open the extracted
   folder until you can see `gui.py` and `requirements.txt`.
3. In that folder's File Explorer window, click the **address bar** at the top,
   type `cmd`, and press Enter. This opens CMD in the correct folder.
4. Check that Python 3.12 is available:

   ```cmd
   py -3.12 --version
   ```

   It should print `Python 3.12.x`. If the command is not recognized, check the
   Python installation before continuing.
5. Create the virtual environment. This creates a `.venv` folder for the project's
   Python packages. You only need to create it once:

   ```cmd
   py -3.12 -m venv .venv
   ```

6. **Activate the virtual environment** before installing packages or running the
   project:

   ```cmd
   .venv\Scripts\activate.bat
   ```

   You should now see **`(.venv)`** at the beginning of the command line. Activate
   it again whenever you open a new CMD window.
7. Install the required packages inside the activated environment:

   ```cmd
   python -m pip install -r requirements.txt
   ```

   This may take a few minutes. Wait until the command line returns. If it reports
   an error, resolve it before continuing.
8. Start the desktop app:

   ```cmd
   python gui.py
   ```

   Keep CMD open while using the app. Choose your video with **Choose video…**;
   recordings are not bundled with the repository.

**Opening the app next time**

Open the folder containing `gui.py`, type `cmd` in File Explorer's address bar,
then run these two commands in order:

```cmd
.venv\Scripts\activate.bat
python gui.py
```

You do not need to recreate `.venv` or reinstall packages each time. To leave the
virtual environment after closing the app, type `deactivate` or close CMD.

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

**Windows limitations:** end-to-end execution and cancellation/kernel cleanup have
only been validated on Linux. The **Open results folder** button currently uses
Linux helpers (`xdg-open`/`gio`); on Windows, open the displayed run path in File
Explorer. HTML reports can be opened directly in a browser. If Tkinter is missing,
modify the Python installation to include Tcl/Tk; do not install it through pip.

## Run an analysis

New to the app? Follow the [step-by-step GUI walkthrough](documentation.md#3-desktop-workflow-a-guided-walkthrough).
The documentation also maps [each button to its Python functions](documentation.md#51-functions-behind-the-buttons).
See the [frontend guide](documentation.md#55-frontend-structure-and-layout) for widgets, layout, events and image rendering.

1. Choose a video and apply the primary/secondary timestamps.
2. Enable **Select eye ROI** to draw a crop; disable it for full-frame measurements.
3. Enable **Calibration** to select two ruler marks a known distance apart,
   normally 1 cm. Disable it for pixel-only measurements.
4. Leave **Select pupils manually** on to select a center and boundary point in
   each comparison frame. Turn it off to estimate both pupils automatically. Use
   **Primary estimate** / **Secondary estimate** to review the blue dashed circles.
5. Confirm any manual selections, then click **Run all notebooks (0–4)**.
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

An eye ROI is recommended for automatic mode. Automatic initialization is a
heuristic, not a validated pupil boundary. If it
cannot find an unambiguous candidate, Run stays disabled: select a tighter eye ROI
or turn manual selection back on. Full-frame mode follows a local eye region to
estimate the second pupil, while keeping measurement frames full-size. Manual
points and automatic estimates are stored separately in the per-video profile.

## Optional GPU processing

1. Start the app from your activated virtual environment with `python gui.py`.
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
experiments; `tests/` contains focused checks; `results/` contains saved outputs and
validation evidence. Some committed results include eye images and original local
execution paths. Videos, environments, presets, local settings and caches are ignored.

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
