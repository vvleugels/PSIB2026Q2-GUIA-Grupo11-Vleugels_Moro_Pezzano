# PSIB — Pupillary light reflex pipeline

Python project for the Biomedical Signal and Image Processing practical guide:
eye video → pupil segmentation → area/diameter curve → response estimates.
Processing functions live in `src/psib/`; notebooks provide comparisons, figures
and discussion prompts.

## Current status

| Module | Implemented work |
| --- | --- |
| 0 — Acquisition | Recording inventory, timestamp checks, brightness-based stimulus preview |
| 1 — Image fundamentals | Sampling, quantization, RGB/HSV, enhancement, noise, spatial filtering, edges, Fourier, PSNR/SSIM |
| 2 — Segmentation | Otsu, K-means, snakes, watershed, morphology, contour skeletonization, optional Dice/IoU |
| 3 — Features and dynamics | Shape, RGB statistics, masked GLCM, frame-by-frame tracking, artifact flags, temporal curves, exploratory response parameters, optional MAE/RMSE |
| 4 — Compression | Pending |

Modules 0–3 have executed on `A_1.mp4`. **Successful execution does not establish
segmentation accuracy.** Reflection and low contrast still cause incorrect
contours, including some that pass the heuristic quality checks. Manual reference
annotations and validation on further recordings are pending. The project still
requires per-video ROI and pupil initialization; fully automatic processing of
unseen videos is pending.

## Desktop GUI (recommended)

From the project directory, activate the environment and start the app:

```bash
source .venv/bin/activate
python gui.py
```

No Jupyter browser session is needed. Choose a video, set the two comparison
timestamps, then prepare selections on the large image canvas:

1. Enable **Select eye ROI** to draw an eye crop. With this off, measurements use
   the full video frame; an internal eye-motion region still follows the pupil.
2. Enable **Calibration** to select two ruler endpoints and specify their known
   separation in centimeters. With this off, output remains in pixels.
3. Select the pupil center and a boundary point on each comparison frame.
4. Confirm each selection, then click **Run all notebooks (0–3)**.

Use Zoom/Fit and scrollbars for small pupils. Space/reset clears the selection;
Backspace/right click undoes a point; Enter confirms. All coordinates are stored
in original pixels. The app remembers selections per video in the ignored
`.psib_gui/` folder; changed videos, timestamps or ROI require renewed selections.

The Run button executes all four notebooks in order without additional selection
windows. Progress, logs, cancellation, figure browsing and HTML notebook reports
are available in the app. Each run creates a new `results/gui/<video>_<run id>/`
folder containing its configuration and outputs. Source notebooks, `config.yaml`
and earlier results are preserved. GUI-selected settings override old video-path
environment variables. Failed/cancelled runs retain clearly labelled partial outputs.

Tkinter is available in the development environment. If `import tkinter` fails on
Debian/Ubuntu, install the operating system's `python3-tk` package; this cannot be
installed through pip. Run the app in a desktop session with a display. Install
`requirements.txt` if Pillow, notebook execution or HTML-export dependencies are missing.

The desktop workflow does not resolve remaining segmentation accuracy limitations.
Inspect the pupil overlays before interpreting physiological results. Full-frame
mode can include distracting image structures; a focused eye ROI is generally easier
for the current algorithms.

## Installation

Development and validation used Linux and Python 3.12. From the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
jupyter lab
```

Interactive ROI, ruler and polygon selection require a desktop session and
GUI-enabled OpenCV. Coordinate-based configuration supports noninteractive runs.
Dependency versions in `requirements.txt` are minimum requirements, not an exact
lock of the validated environment.

## Input and configuration

Videos are excluded from Git. Put your recording at `data/A_1.mp4`, edit the
portable example paths in `config.yaml`, or override them:

```bash
export PSIB_VIDEO_PATH=/path/to/A_1.mp4
export PSIB_VIDEO_DIR=/path/to/recordings
```

Relative input and output paths resolve from the configuration file's directory.
The acquisition inventory scans `video_dir`; setting `PSIB_VIDEO_PATH` alone does
not change that inventory folder. Recording names use `A_n.mp4` for dark → light
and `B_n.mp4` for light → dark; Module 3 also supports an explicit record type.

Before each recording, configure:

- `frames`: representative timestamps (defaults are 1 and 5 seconds).
- `roi`: eye crop in pixels of the full decoded upright frame, or interactive mode.
- `module2.initializations`: pupil centers/radii for each selected frame, in ROI-local coordinates.
- `module3`: tracking method, quality checks, gap limits and response thresholds.
- `module3.stimulus_time_s`: a visually confirmed stimulus time when available.
- `calibration`: the recording's ruler scale when physical measurements are needed.

The included seeds/ROI were chosen for A_1 and must be reviewed for other videos.
Video frames are selected by decoded timestamps; temporal calculations do not
assume constant FPS. Timestamp behavior was checked on A_1 with the local OpenCV
backend; other decoders/recordings still need validation.

## Execution

Run notebooks in order, from Jupyter launched in the repository root:

1. `notebooks/00_acquisition.ipynb`
2. `notebooks/01_fundamentals_enhancement.ipynb`
3. `notebooks/02_segmentation_morphology.ipynb`
4. `notebooks/03_features_temporal.ipynb`

For a noninteractive configuration, execute copies using the active Python
interpreter and retain the source notebooks:

```bash
python validate_notebooks.py
# Execute only one notebook:
python validate_notebooks.py 03_features_temporal.ipynb
```

Jupyter execution requires local kernel ports. Executed copies are saved to
`results/validation/`. Writing those copies does not indicate success if an
execution fails: inspect errors or require a successful command exit.

## Ruler calibration

For recordings with a ruler below the eye, set:

```yaml
calibration:
  enabled: true
  mode: interactive
  frame_time_s: 1.0
  distance_cm: 1.0
  points_xy: null
```

Click two ruler marks **1 cm apart**, then Enter. Space/R resets all points,
right click/Backspace undoes the last point, and Esc cancels. Copy
the printed full-frame endpoints into `points_xy` and switch to `mode: manual`
for reproducible runs. Both modules 2 and 3 read this configuration; save manual
coordinates to avoid selecting them again in each notebook.

Scale is the Euclidean distance between the endpoints divided by `distance_cm`.
Lengths use pixels / pixels_per_cm; areas use pixels² / pixels_per_cm². Physical
outputs include area in mm², perimeter and equivalent diameter in mm. Equivalent
diameter describes a circle with the same mask area; it is not a fitted anatomical
diameter. Centroids remain pixel coordinates.

Use a separate calibration for each recording, before resizing. The ruler should
be approximately in the eye plane; perspective or changing camera distance affects
the scale. A_1 is uncalibrated and produces pixel measurements only. Conversion
arithmetic was tested; interactive selection on an actual ruler video is pending.

## Segmentation and manual validation

Module 2 compares methods and morphology on both configured frames. Its selected
method is provisional. Optional manual reference `.npy` masks must match the video,
timestamp, orientation and crop; their paths go in `module2.reference_masks`.
The notebook provides a polygon annotation cell. Dice/IoU are emitted only when
references exist. Filling holes cannot repair an incorrect outer boundary.

Module 3 supports local multi-level Otsu, snakes, watershed and K-means. Snakes independently reacquire a
dark region before initializing a fresh contour to reduce accumulated drift.
Area, boundary, motion, diameter and contrast checks reject suspect samples;
these checks are not anatomical ground truth. Raw rejected measurements and
reasons remain in the output. Only short internal gaps are interpolated using
actual timestamps; long gaps and endpoints stay missing. Smoothing operates on
separate finite segments.

Texture statistics are computed independently for RGB channels. GLCM counts only
pairs whose two endpoints are inside the region. The iris sample is an approximate
ring, requiring visual review for sclera, eyelids and reflections.

For Module 3 manual comparison, set `manual_measurements_csv` to a CSV with unique
`frame_index` values and `area_px2` and/or `equivalent_diameter_px`. The notebook
reports MAE/RMSE on accepted matched frames, with evaluation/rejection counts.

Response parameters are threshold-based **unvalidated estimates**. Without an
explicit stimulus time, the source is labelled `brightness_estimate`. Insufficient
windows produce missing values. Peak speeds are particularly sensitive to
segmentation and smoothing. Between-trial variability needs multiple recordings;
compare pixel amplitudes only at matching image scales, or use calibrated mm.

## Outputs and included evidence

| Location | Contents |
| --- | --- |
| `results/module0_*.csv` | Inventory and stimulus preview |
| `results/module1_metrics.csv` | PSNR/SSIM comparisons |
| `results/module2/` | Binary masks, calibration record and frame measurements; reference scores when supplied |
| `results/module3/<video stem>/` | `frame_features.csv`, `pupil_curve.csv`, `physiological_parameters.csv`; optional calibration and manual validation |
| `results/module3/trial_variability.csv` | Summary of saved per-video parameters |
| `results/figures/` | Comparison plots and sampled tracking overlays |
| `results/validation/` | Executed notebooks and validation notes |

This repository intentionally includes the executed notebooks and generated
results from A_1 for review. They may contain images of the recorded eye and
original local execution paths. Input videos are not included. Results are
regenerated/overwritten on execution; figure names outside the per-video CSV
folders are shared across recordings. Use a distinct `output_dir` to preserve
separate result sets. Do not treat existing example outputs as a new successful run.

## Checks

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

Focused synthetic tests cover masked texture, short/long gap behavior, known
A/B response timing and physical conversion, missing baseline handling, eye translation/recovery, pupil-size independence and calibration preservation under a moving crop.
See `results/validation/MODULO2.md` and `MODULO3.md` for limitations and evidence.

## Repository layout

```text
config.yaml              portable example configuration
requirements.txt         processing and notebook dependencies
src/psib/                reusable processing functions
notebooks/               source notebooks for modules 0–3
validate_notebooks.py    notebook execution helper
tests/                   focused synthetic checks
data/                    local videos and annotations (ignored)
results/                 included example outputs and executed notebooks
```

Remaining work: Module 4, manual accuracy validation, further recordings, reliable
tracking under artifacts, and an automatic entry point for unseen-video evaluation.

## Moving eye ROI

Eye tracking is separate from pupil segmentation. Modules 1 and 2 follow the
intervening video frames to move the comparison crop. Module 3 tracks the eye
through the full recording using features around the eye, excluding the central
region containing the pupil. A robust motion fit and forward/backward optical-flow
checks validate translation; an original-reference template can recover after loss.
Large scale/rotation changes are rejected rather than resizing the eye.

Choose an initial ROI containing the complete eye with a little skin/eyelid margin,
excluding the ruler and unrelated objects. The ROI belongs to the primary selected
frame (usually 1 s); it is not assumed to belong to the first video frame. Tracking
translates a fixed-size crop at original resolution, preserving the ruler's pixel
scale. Module 3 adds the configured context margin once, not repeatedly per frame.

`module3.eye_tracking` controls enablement, margin and quality thresholds.
`module2.initialization_mode: interactive` lets you click the pupil center and then
its boundary for each comparison frame. Save the printed ROI-local initialization
and use `manual` mode for reproducible runs. Modules use the same selected
reference-frame convention; previous A_1 seeds do not automatically fit A_2.

New Module 3 outputs include `eye_tracking.csv`, moving-ROI rectangles in the full
frame and pupil overlays in the crop. `pupil_curve.csv` records actual ROI origins,
eye translations, tracking validity/confidence and both full-frame and anchor-frame
pupil coordinates. Pupil-motion checks use anchor-frame coordinates so head motion
alone is not mistaken for a pupil-center jump. Failed eye tracking rejects the
corresponding pupil measurement; only short gaps may be interpolated.

Restart the notebook kernel after changing the tracking code, then run all cells.
Frames with a blink may retain a valid eye location while pupil segmentation fails;
tracking validity is not a pupil-accuracy guarantee. Camera depth movement changes
physical scale, and exceeding supported rotation/scale is flagged. Visual and manual
anatomical validation remain necessary.

For the default `local_otsu` pupil method, `pupil_threshold_classes` splits a local
pupil/iris neighborhood into intensity groups; the darkest group is retained.
`pupil_search_radius_factor` controls that neighborhood relative to the selected
initial radius. Cleanup retains one component nearest the predicted pupil center.
`pupil_confirmation_frames` requires consistent consecutive candidates before
accepting a new size/position after a jump; those events are recorded as
`pupil_reacquired`. These heuristics still require manual accuracy validation.

Module 2 also compares `local_otsu` and uses it as its provisional cleanup method.
It shares the local threshold implementation with Module 3. A snake can collapse
on low-contrast frames even with a reasonable initial contour; opening may then
remove the entire tiny mask. The notebook warns about collapsed candidates and
empty cleanup results rather than treating them as a measured constriction.

Pupil/ruler/polygon point-selection windows enlarge the displayed image to fit
within a 1000 × 650 pixel image area. Pupil selection previews the selected center
and radius. Space or R clears the selection for unlimited retries before Enter;
right click or Backspace removes the last point. Coordinates are converted back
to the original image pixels, so display enlargement does not change calibration
or measurements. Clicks in the instruction area are ignored. Restart the kernel
to load these updated interaction controls.

The GUI's **Show saved presets** toggle displays saved ROI, ruler and pupil
selections as blue dashed overlays in their corresponding setup views. New
selections use green/yellow overlays; hiding saved overlays does not erase them.
Preset JSON files live under `.psib_gui/`, which is excluded by `.gitignore`.
Module 0's contact-sheet images show only the selected video; folder-wide
recording inventory checks remain available.

For machine-specific settings, create `config.local.yaml` beside `config.yaml`.
The GUI and ordinary notebook runs prefer this local file when present. It is
ignored by Git; the published `config.yaml` remains a portable example. Explicit
GUI/runner run configurations still take precedence over the local file.
