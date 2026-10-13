# Pupillary light reflex pipeline (PSIB)

Biomedical Signal and Image Processing - eye video -> pupil area/diameter curve -> physiological parameters.

Status: **Modules 0-3 implemented.** Module 4 and the final standard output (CSV) will be added to `src/psib/` and `notebooks/`.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
jupyter lab
```

## Run

1. Edit `config.yaml` (only the paths and, if needed, the ROI / frame times):
   * `video_path`: video processed by the pipeline (or set the env variable `PSIB_VIDEO_PATH`).
   * `video_dir`: folder with all the `A_n.mp4` / `B_n.mp4` records (or `PSIB_VIDEO_DIR`).
   * `roi`: `mode: manual` (x, y, w, h) or `mode: interactive` (draw the box with the mouse; the notebook prints the values to paste).
2. Open and run, in order:
   * `notebooks/00_acquisition.ipynb` - inventory and validation of the recordings.
   * `notebooks/01_fundamentals_enhancement.ipynb` - sampling, quantisation, colour spaces, enhancement, filtering, edges, DFT, PSNR/SSIM.

Tables and figures are written to `results/` (ignored by git).

## Layout

```
config.yaml                single configuration file (video path, ROI, parameters)
src/psib/                  processing code (the notebooks only call it)
  config.py  video_io.py  roi.py  color.py  sampling.py  intensity.py
  noise.py  filters.py  edges.py  frequency.py  metrics.py  stimulus.py  plotting.py
notebooks/                 one notebook per module
results/                   generated tables and figures
```

## Notes on the recordings

* Phone videos are **variable frame rate** and may carry a rotation flag. `video_io` applies the rotation and selects frames by
  real timestamp, so always build time axes from timestamps (not from `frame_index / fps`).
* The ROI is expressed in pixels of the decoded (upright) frame; if videos have different resolutions it has to be adjusted.

## Module 2 and ruler calibration

Run `notebooks/02_segmentation_morphology.ipynb` after Module 1. It compares Otsu,
K-means (2-5 clusters), snakes and watershed on both configured frames, and
exports binary masks, morphology comparisons and measurements under
`results/module2/`. The configured method is provisional until validated with
manual reference masks (Dice/IoU).

For each new video, adjust ROI-local pupil centers and initial radii in
`module2.initializations`. Set `module2.reference_masks` to optional `.npy`
manual binary masks matching the exact cropped frames. The notebook includes
an optional polygon annotation cell for generating them.

For videos with a ruler below the eye, enable `calibration.enabled` and choose
`calibration.mode: interactive`. Click two marks 1 cm apart on the full upright
frame and press Enter. R resets and Esc cancels. Copy the printed endpoints into
`calibration.points_xy` and switch to `mode: manual` for reproducible reruns.
The selection requires desktop OpenCV; coordinates can also be entered directly.
Each recording requires its own calibration. The ruler must be in the eye plane;
changes in camera distance invalidate the scale. A_1 has no calibration by default.

Lengths use pixels / pixels_per_cm and areas use pixels squared / pixels_per_cm
squared. CSV output includes area in cm2/mm2, perimeter in mm and equal-area
circular diameter in mm when calibration exists; otherwise only pixel measures
are emitted. Diameter is an equivalent diameter, not an anatomical circle fit.
`calibration.json` stores the scale, video path, selected endpoints and frame time.

To execute validation copies with your environment:

```bash
.venv/bin/python validate_notebooks.py
```

Results appear in `results/validation/`; the source notebooks remain unchanged.

## Module 3: texture and video dynamics

Run `notebooks/03_features_temporal.ipynb`. Outputs are per-video under
`results/module3/<video stem>/`: `frame_features.csv`, `pupil_curve.csv`,
`physiological_parameters.csv`, optional `manual_validation.csv` and calibration
metadata. Trial variability is aggregated from saved per-video parameter tables.
Configure the initial ROI/pupil center for each recording and review the tracking
overlays; the selected tracking method is independently initialized snakes, with watershed/K-means alternatives.
The iris texture sample is an approximate ring, requiring visual review.

Use `module3.stimulus_time_s` for a visually confirmed stimulus. Without it, the
notebook labels the estimate as brightness-derived. Raw rejected measurements and
artifact reasons remain in the CSV. Only short internal gaps are interpolated;
long gaps remain missing. Parameters are exploratory until manual validation.
Manual measurement CSVs use `frame_index`, `area_px2` and/or
`equivalent_diameter_px`; the notebook reports accepted-frame MAE/RMSE and counts.
Calibration settings from Module 2 are reused for physical lengths and areas.
One trial cannot establish between-trial variability; compare pixel amplitudes
only at matching image scales or use calibrated mm outputs.

Run the focused checks with:

```bash
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -v
```
# PSIB_Competencia
