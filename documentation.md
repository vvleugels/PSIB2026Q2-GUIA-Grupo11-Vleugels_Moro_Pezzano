# PSIB project documentation

This document describes the current implementation, how its parts connect, and
how to run and maintain it. Start with [README.md](README.md) for quick setup.

## 1. Purpose and current state

The project measures an eye's pupil response to a light change. It follows the
PSIB practical guide and keeps image-processing experiments in notebooks while
reusable algorithms live in Python modules.

| Module | Implemented responsibilities | Important qualification |
| --- | --- | --- |
| 0: acquisition | Inventory recordings, inspect timestamps and brightness; preview images from the selected video | Inventory and brightness checks can include the input folder, while the contact sheet shows only the selected video |
| 1: image fundamentals | Sampling, quantization, color spaces, intensity transforms, noise/filtering, edges, Fourier and image-quality metrics | These experiments illustrate methods; a higher image-similarity score does not establish better pupil detection |
| 2: segmentation | Global/local Otsu, K-means, snakes, watershed, morphology, contour skeletonization and optional reference comparison | Local Otsu is provisional; weak contrast and reflections still affect boundaries |
| 3: features and time | Shape, RGB texture, eye tracking, pupil size curves, artifact handling and response estimates | Physiological measurements remain unvalidated until compared with human references |
| 4: compression | Explicit Huffman and horizontal/vertical RLE, JPEG image comparisons and full-video Q=50/10 measurements | Pipeline differences are not anatomical accuracy; source videos are already compressed |

The desktop app runs Modules 0–4. It simplifies configuration but does not make the
pipeline fully automatic for unseen videos: initial eye/pupil selections are still
required. Written notebook discussion answers and broader validation remain work
for the practical assignment.

## 2. Installation and entry points

Development uses Linux and Python 3.12. The annotations and GUI code require a
modern Python version; use the tested 3.12 environment rather than assuming the
assignment's older minimum is sufficient.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python gui.py
```

Tkinter is provided by the operating system, not pip. On Debian/Ubuntu its package
is `python3-tk`. Folder opening uses the system's `xdg-open` or `gio`. A desktop
display is needed for the app and standalone OpenCV selection windows.

| Entry point | Purpose |
| --- | --- |
| `gui.py` | Start the desktop application |
| `validate_notebooks.py` | Execute notebooks and preserve executed copies |
| `notebooks/00_…04_*.ipynb` | Run experiments manually in Jupyter |
| `tests/` | Focused automated checks; no real-video anatomical ground truth |

JupyterLab is optional and is not required by the desktop app or terminal runner.
To install the browser-based editor and launch it from the repository root:

```bash
python -m pip install -r requirements-notebooks.txt
python -m jupyterlab
```

The optional file includes the base requirements. Existing environments retain
already-installed packages; this change makes new desktop installations lighter
without uninstalling anything from the current environment. Terminal examples:

```bash
python validate_notebooks.py
python validate_notebooks.py 02_segmentation_morphology.ipynb
python validate_notebooks.py --config /absolute/path/run_config.yaml --json-events
```

The last command executes all notebooks using prepared configuration. Such runs
must contain manual/full-frame ROI settings and manual pupil/ruler selections;
interactive selection calls are blocked rather than opening unexpected windows.
Jupyter kernels need local communication ports even when no browser is involved.

`--output-dir` changes the destination for executed notebook/report copies. The
configuration's `output_dir` controls processing figures and tables; they are
separate concepts. An explicit configuration outside the project should contain
absolute input/output paths and a `project_root` when project-relative paths are used.

## 3. Desktop workflow

1. Choose a video. The app decodes it to obtain dimensions, timing and a profile
   fingerprint based on resolved path, file size and modification time.
2. Set primary and secondary timestamps and apply them. They must be ordered,
   within the last-frame timestamp, and decode to different frames.
3. Enable ROI selection to draw an eye crop. With ROI off, measurements use the
   entire frame. Full-frame mode still uses an internal eye-motion support region.
4. Enable calibration if the video has a ruler. Select two marks and enter their
   known distance in centimeters. Calibration off means pixel-only results.
5. Select the pupil center and one boundary point on each comparison frame.
6. Confirm selections and click **Run all notebooks (0–4)**.
7. Inspect the figures and executed HTML reports in **Results & log**.

Zoom/Fit and scrollbars affect only the display. Coordinates map back to original
pixels. Space/reset clears the draft selection; Backspace/right click undoes it;
Enter confirms it. Saved presets appear as blue dashed overlays when **Show saved
presets** is enabled. Green/yellow marks represent the new draft selection. Hiding
saved overlays does not delete the preset.

Profiles live in `.psib_gui/` and are ignored by Git. Reopening the same unchanged
video restores its settings. Changed file metadata invalidates the saved profile;
changing timestamps or the ROI invalidates dependent pupil selections. Changing
timestamps also clears ruler points because their reference frame changed.

Preparation/tracking errors require a corrected ROI or timestamp. The app does not
silently substitute another crop. A selected crop should contain the eye with
some surrounding context while avoiding the ruler and unrelated dark structures.

## 4. Configuration and precedence

The published `config.yaml` is a portable example. `config.local.yaml`, when
present beside it, contains machine-specific settings and is ignored by Git.

Ordinary notebook configuration resolves in this order:

1. `PSIB_RUN_CONFIG`: an explicit prepared run file; video environment overrides
   and local-file substitution do not override it.
2. Otherwise, the requested `config.yaml`, preferring its sibling
   `config.local.yaml` if that exists.
3. For ordinary runs only, `PSIB_VIDEO_PATH` and `PSIB_VIDEO_DIR` override the video
   and inventory-folder settings. A conflicting video override produces a warning.

Relative inputs/outputs resolve from the configuration directory, or from its
explicit `project_root`. The desktop app reads the local configuration when
available, then creates a separate effective configuration for each run. It does
not edit the published or local configuration.

| Group | Key settings |
| --- | --- |
| Inputs/outputs | `video_path`, `video_dir`, patterns, `output_dir` |
| Representative frames | `frames.primary_time_s`, `secondary_time_s` |
| ROI | `manual` with `(x,y,w,h)`, `interactive`, or `full_frame` |
| Calibration | Enabled flag, mode, reference time, distance in cm, full-frame endpoints |
| Module 1 | Noise seed, sampling/quantization, intensity/filter/edge/frequency settings |
| Module 2 | Method, manual/interactive initialization, per-frame centers/radii, morphology, optional reference-mask paths |
| Module 3 | Pupil method, local threshold settings, quality limits, eye tracking, interpolation/smoothing, stimulus and response settings |
| Module 4 | `jpeg_qualities: [90, 50, 10, 5]`, `temporal_qualities: [50, 10]`, `save_all_frames: false`; absent section uses these defaults |

GUI runs force manual selections, set the video inventory directory to the selected
video's parent, and clear optional reference-mask/manual-measurement paths to avoid
accidentally reusing annotations from a different video. To use those validation
inputs, prepare an appropriate configuration and run the notebook/runner directly.

## 5. Architecture and data flow

```text
GUI setup → decoded comparison frames → confirmed original-pixel selections
    → isolated run configuration → notebook worker → kernels for Modules 0–4
    → tables + masks + figures + executed notebooks + HTML + execution status
```

The Tk main thread handles widgets only. Frame preparation runs in a background
thread; notebook execution runs in a subprocess using the current Python
interpreter. A queue delivers progress/errors to the GUI without blocking its
main event loop.

| Components under `src/psib/` | Responsibility |
| --- | --- |
| `desktop`, `gui_model` | Widgets, selection geometry, setup validation and per-video profiles |
| `notebook_runner` | Kernel lifecycle, progress events, failure/cancellation and report export |
| `config`, `video_io` | Configuration resolution, upright decoding and real presentation timestamps |
| `roi`, `calibration`, `gui` | Crops, comparison-frame tracking, selection windows, ruler conversion and font fallback |
| `eye_tracking`, `temporal` | Eye translation, independent pupil extraction, quality flags and temporal estimates |
| `segmentation`, `features` | Candidate masks, morphology, reference overlap, shape and masked texture |
| `color`, `sampling`, `intensity`, `noise`, `filters` | Module 1 image transformations |
| `edges`, `frequency`, `metrics` | Edge/frequency analysis and image-quality statistics |
| `compression`, `compression_study` | Self-contained lossless codecs, RGB-safe JPEG and image/temporal experiments |
| `plotting`, `utils`, `system_open` | Figure output, array conversion and desktop folder opening |

Important interfaces:

- `load_config(path=None)` returns a dictionary with resolved paths plus `_root`
  and `_output_dir`. It creates the output/figures directory.
- `Setup` stores the selected video, geometry, timestamps, toggles and selections.
  `missing()` reports setup errors; `effective_config(...)` builds a prepared run.
- `EyeTracker.update(frame_rgb)` returns `EyeLocation`: crop, translation, validity,
  method, feature inliers, confidence and failure reason.
- `track_video(path, roi, center_xy, radius_px, options, scale=None, *, frame_transform=None, frame_observer=None)` returns a
  per-frame DataFrame and sampled previews. Coordinates are ROI-local on input.
- `clean_curve(...)` returns the raw table plus cleaned/smoothed size columns and
  interpolation flags. `response_parameters(...)` returns a parameter dictionary.
- `execute_notebooks(project_root, paths, config_path=None, output_dir=None,
  emit=None)` returns a state dictionary and optionally emits progress dictionaries.

The runner emits module/cell start/completion, log, complete, failed and cancelled
events. Failure records the notebook and cell index and prevents subsequent
modules from running. Cancel terminates the active kernel and leaves a labelled
partial notebook/report. CLI exit codes are 0 (complete), 1 (failed) and 130
(cancelled). Source notebooks remain unchanged by runner execution. The runner uses a
300-second per-cell timeout unless positive integer notebook metadata
`execution_timeout_s` overrides it. Module 4 uses 1800 seconds because its
whole-video multi-pass cell is substantially longer; cancellation remains available.

## 6. Tracking, segmentation and measurement

The ROI is defined on the primary comparison frame, not necessarily video frame
zero. Comparison crops follow intervening frames. Full-video tracking initializes
from that reference and then processes the recording from its first frame.

Eye tracking uses features around the eye while excluding the central pupil area.
Contrast normalization, forward/backward optical-flow checks and a robust motion
fit assess translation. A fixed-reference template supports recovery. Crops move
at constant dimensions without resizing; large per-frame rotation/scale changes
are rejected. Gradual camera-depth changes can still invalidate calibration.

Pupil segmentation is independent of eye tracking. The current provisional default
is local multi-level Otsu: threshold the pupil/iris neighborhood and retain the
nearby dark component. Snakes, watershed and K-means remain comparison options.
Snakes can collapse in low contrast even with a reasonable initialization.
Equalization/CLAHE do not automatically improve segmentation; the A_2 experiment
showed additional iris leakage and did not rescue the dark-frame snake.

Morphological opening/closing, small-component removal and hole filling clean the
selected mask. They cannot repair a fundamentally incorrect boundary. Module 2
warns about collapsed masks and empty cleanup results.

Quality checks include area, ROI boundaries, diameter jumps, eye-compensated
centroid movement and pupil/background contrast. A consistently changed candidate
can be reacquired after the configured confirmation count. Passing these checks
is not proof that a mask is anatomically correct.

Rejected raw measurements remain available with reasons. Only short internal gaps
are interpolated using actual timestamps. Long gaps and endpoints remain missing;
a time-window median smooths separate finite segments. Values derived from filled
gaps should not be confused with directly observed measurements.

Calibration uses `pixels_per_cm = endpoint_distance_px / known_distance_cm`.
Lengths divide by that scale; areas divide by its square. mm lengths multiply cm
by 10; mm² areas multiply cm² by 100. Equivalent diameter is `sqrt(4*area/pi)`, not
a fitted anatomical diameter. Calibration requires a suitable ruler plane and
stable camera distance.

RGB texture statistics are computed independently. GLCM counts only pairs whose
both endpoints belong to the mask, using pooled directions/distances. The iris
sample is an approximate ring and may include unwanted structures. Constant
regions can have undefined skewness/correlation.

Physiological estimates use the configured stimulus time or a labelled global-
brightness estimate. A records describe constriction; B records describe redilation.
Latency requires sustained change exceeding baseline-relative and robust-noise
thresholds. Amplitude uses baseline and a post-stimulus extremum; peak speeds use
adjacent smoothed samples. Missing windows produce NaN. These estimates remain
exploratory until segmentation and timing are independently validated.

## 7. Outputs and provenance

GUI runs use `results/gui/<video>_<timestamp>_<unique id>/`. Standalone notebooks
write to the configuration's output directory and may overwrite earlier files.

| Output | Meaning |
| --- | --- |
| `run_config.yaml` | Exact prepared settings for that GUI run |
| `module0_*.csv` | Folder inventory and stimulus preview |
| `module1_metrics.csv` | Image comparison PSNR/SSIM |
| `module2/*.npy`, `measurements.csv` | Masks and raw/morphology measurements |
| `module2/reference_scores.csv` | Dice/IoU when actual manual masks are provided |
| `module3/<video>/frame_features.csv` | Shape and RGB texture of comparison regions |
| `module3/<video>/pupil_curve.csv` | One row per frame: time, raw/clean sizes, flags and coordinates |
| `module3/<video>/eye_tracking.csv` | Per-frame crop origins, motion and tracking quality |
| `physiological_parameters.csv` | Estimated response values, status and stimulus source |
| `manual_validation.csv` | MAE/RMSE on accepted annotated frames when supplied |
| `trial_variability.csv` | Summary of saved per-video response tables; one trial cannot estimate sample variability |
| `figures/` | Comparisons, moving rectangles and pupil overlays |
| `validation/` | Executed notebooks, HTML reports, JSON-lines event log and status |

Useful curve columns include `frame_index`, `timestamp_s`, `accepted`,
`artifact_reason`, `interpolated`, `pupil_reacquired`, `eye_tracking_valid`, ROI
origin/dimensions, raw `area_px2` and `equivalent_diameter_px`, and cleaned/smoothed
size columns. Physical columns are emitted only with calibration. Centroids are
available in crop-local, full-frame and eye-motion-compensated reference coordinates.

Run configurations can contain local paths, and reports can contain eye images.
Review what is included before publishing results. Existing checked-in results
are evidence from particular runs, not proof that the current setup just ran.

## 8. Testing and troubleshooting

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
python -m pip check
```

Tests cover geometry, profiles, configuration precedence, tracking/loss/recovery,
full-frame coordinates and scale preservation, local segmentation on synthetic
images, masked texture, temporal gap handling, response estimates, selection
controls, runner events/cancellation and folder-opening behavior. They do not
replace manual contours or physiological ground truth.

Real-video validation has exercised A_2 with all ROI/calibration toggle combinations.
A real-display Tk smoke check and actual-kernel cancellation were also performed.
Historical validation notes live under the results folders.

| Symptom | Check |
| --- | --- |
| Wrong video | Inspect `video_path`; ordinary notebook runs may inherit `PSIB_VIDEO_PATH`; GUI run configurations override it |
| Run disabled | Complete/confirm required selections; apply changed timestamps; inspect the setup-status message |
| Empty or incorrect mask | Inspect segmentation comparisons and initialization; change method/parameters rather than trusting a cleaned empty mask |
| Eye leaves the crop | Choose context around the eye and review tracking flags; a bigger crop alone does not establish reliable tracking |
| Old Python code in Jupyter | Restart its kernel before rerunning; restart the desktop app after GUI code changes |
| Missing fonts in OpenCV | Selection helpers fall back to installed fonts; desktop Tk selectors do not use OpenCV windows |
| Results folder will not open | The app strips OpenCV-specific library settings and tries xdg-open/gio; errors show the path and reason |
| No desktop display/Tkinter | Use a desktop session and install the OS Tk package |

## 9. Maintenance and debloat policy

Keep the notebooks required by the assignment and their reusable algorithms even
when a method is not selected as the current default. Comparison methods are used
for academic evaluation and are not dead code.

The dominant disk costs are the installed virtual environment and generated
results, not Python source. `.venv/`, caches, videos, profiles and local settings
are ignored. Deleting an installed environment prevents execution until rebuilt.
Removing already committed artifacts does not erase their old Git objects; history
rewriting would be a separate, explicitly approved operation.

A static source/notebook/test reference audit identified a small unused intensity
helper and unused tracking buffers/contour construction. These can be removed
without removing a supported workflow. Broader changes to stored results or
optional notebook dependencies require the user's decision. The cleanup record
is kept below as decisions are applied.

### Cleanup applied on 2026-10-14

- Removed the unused `clipped_fraction` helper after auditing live Python,
  notebook and test references. Existing metrics retain their clipping statistics.
- Removed an unused tracking-image copy and unused temporal variables/contour
  construction. Supported tracking/segmentation methods are retained.
- Consolidated the README into a starting guide; detailed explanations are kept
  in this document rather than repeated across appended README sections.
- With user approval, removed 274 repeated GUI-validation figures,
  masks and executed notebook/HTML reports, reclaiming 117.1 MiB in the
  working tree. Preserved configurations, CSV measurements, status/event logs,
  the validation summary and the unique desktop preview.
- Added ignore rules for regenerated heavyweight GUI-validation artifacts.
  Other results folders and actual GUI run outputs were not removed.
- With user approval, moved JupyterLab to `requirements-notebooks.txt`. The base
  requirements retain all desktop, processing, kernel and HTML-export packages.
- Git history and the existing virtual environment were not altered. Previous
  commits still contain old artifacts, so clone-history size has not been reduced.

## 10. Module 4: compression and downstream measurements

The notebook `04_compression.ipynb` prepares the current video's confirmed settings,
compares compression on two selected frames, then runs a whole-video baseline and
JPEG Q=50/10 comparisons. Both ROI modes and calibration on/off are supported.
An older configuration without `module4` uses defaults; required assignment
qualities must remain present, although more qualities may be added.

### Inputs and codecs

At each timestamp, compare the full RGB frame, tracked eye RGB image, RGB image
with the algorithm's pupil mask zeroing the background, and the binary mask as
uint8 0/255. With ROI off, the eye image is full-frame. The selected segmentation
method and morphology match Module 2. Masks are algorithm-generated references.

`encode_lossless(image, codec)` and `decode_lossless(data)` accept nonempty uint8
grayscale/RGB images and produce/consume complete PSIC v1 files. The format starts
with `PSIC` and version byte 1, a four-byte big-endian JSON-header length, JSON
metadata, and binary payload. Metadata includes shape, dtype and codec. Huffman
uses a serialized prefix-code table, valid bit count and zero-padded packed bits.
RLE uses five-byte big-endian (uint32 length, uint8 value) records, with runs
reset at scanline boundaries and separate channel planes. Traversal direction
is recorded in the codec name. Decoding validates payload lengths and structure;
every experiment requires exact round-trip reconstruction.

`jpeg_roundtrip(image, quality)` returns encoded JPEG bytes and decoded pixels,
with explicit RGB/BGR conversion and unchanged dimensions. Binary-mask JPEG
reconstructions are compared as intensity images; they are not thresholded and
used as anatomical segmentations.

Compression ratio is `image.nbytes / complete_encoded_file_bytes`, including
headers and decoding metadata. Values below 1 mean expansion. It does not compare
with the source MP4 size, nor with bit-packed binary masks. Lossless PSNR is
infinite and SSIM is 1. Quality plots keep infinite PSNR out of numeric axes and
label the lossless case. Error images use a shared 0–255 scale (mean RGB error).
Pupil-edge enlargements support visual discussion of blocking and ringing;
zeroing the background creates additional artificial edges.

### Temporal comparison

The optional `frame_transform(rgb)` hook applies to the original-resolution
reference frame and all sequential frames before tracking/segmentation. It must
preserve uint8 dtype and shape. `frame_observer(index, timestamp, original_rgb,
transformed_rgb)` observes sequential frames only; callback exceptions terminate
the pass and release the capture. Ordinary Module 3 calls do not use these hooks.

Each pass has independent tracking state but identical settings, pixel scale,
manual initialization and stimulus time. The original video's brightness is used
once for stimulus estimation when no manual time is configured. Clean curves and
physiological estimates reuse Module 3's logic. Paired diameter error uses only
finite raw measurements accepted in both passes. Reports include paired counts,
acceptance/rejection counts and unavailable statuses when no pairs exist. Missing
physiological windows remain unavailable; interpolation does not validate masks.

These results measure **additional still-image JPEG compression of decoded video
frames**. They do not measure video-codec bitrate, a lossless camera reference, or
anatomical accuracy. Inspect curves and overlays before drawing conclusions.

### Files and retention

Outputs live under the current run's `module4/<video>/` directory:

- `manifest.json`: input metadata, effective algorithm/codec settings, frame
  indices/timestamps, ROI, ruler scale, shared stimulus and completion state.
- `selected_frames/`: complete compressed Huffman/RLE/JPEG files for both frames;
  `compression_metrics.csv` records sizes, ratios, PSNR/SSIM and SHA-256 checksums.
- `baseline_pupil_curve.csv`, `jpeg_q50_pupil_curve.csv`, `jpeg_q10_pupil_curve.csv`:
  raw flags/measurements and cleaned curves; physical columns only with calibration.
- `diameter_comparison.csv`: paired bias, MAE/RMSE and sample/rejection counts.
- `physiological_parameters.csv`, `physiological_differences.csv`: exploratory
  parameters and numeric differences from the baseline, with status columns.
- `temporal_compression_metrics.csv`: per-frame JPEG sizes, ratios and quality;
  when retained, paths map JPEG filenames to original frame indices/timestamps.

Comparison figures use the current run's `figures/m4_*.png` paths. Executed notebook
copies and HTML reports use the existing runner output directory. Completed passes
are saved progressively. A manifest with status other than `complete` is partial;
consult the runner's status/error and failed cell before using it.

By default, whole-video JPEG bytes are discarded after measurement, while the
selected-frame examples, figures and CSVs remain. `save_all_frames: true` saves all
temporal JPEGs under `temporal_jpeg/<variant>/`; the source video supplies the
original sequence. Bulk temporal JPEG directories are ignored by Git. Selection
and bundling of a publishable example video remain a separate future task.
