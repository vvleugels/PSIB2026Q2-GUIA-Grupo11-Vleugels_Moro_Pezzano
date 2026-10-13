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

Click two ruler marks **1 cm apart**, then Enter. R resets and Esc cancels. Copy
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

Module 3 supports snakes, watershed and K-means. Snakes independently reacquire a
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

Four focused synthetic tests cover masked texture, short/long gap behavior, known
A/B response timing and physical conversion, and missing baseline handling.
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
