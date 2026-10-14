# Desktop GUI validation — 2026-10-14

## Implemented workflow

Launch `python gui.py` in the project's Python environment. Tkinter provides video
browsing, comparison timestamps, ROI/calibration toggles, a zoomable image canvas,
selection confirmation/reset/undo, readiness checks, per-video profiles and one
button to execute Modules 0–3. Results include figures, HTML notebook reports,
CSV tables, effective run configuration, execution events and status.

ROI disabled means full-frame measurement, with an internal motion-tracking region
derived from the pupil initialization. Calibration disabled omits physical units.
All selections are prepared before execution; explicit run configurations disable
interactive OpenCV selection calls and override stale video environment variables.
GUI profiles are kept in the ignored .psib_gui folder. Normal GUI runs use distinct
results/gui directories. Source notebooks/configuration and previous outputs are
preserved. Changed video metadata, timestamps or ROI invalidate relevant selections.

## Checks performed

- 27 automated tests pass, including canvas coordinate geometry, selection controls,
  profile restoration/invalidation, calibration and full-frame modes, old environment
  overrides, runner progress/failure/cancellation, and existing image-processing tests.
- A real-display Tk smoke check exercised canvas clicks/reset/undo, Run readiness,
  and figure viewing. The app layout was inspected in desktop_preview.png.
- All four notebooks executed on A_2 in each combination of ROI enabled/disabled and
  calibration enabled/disabled. Each run produced 238 temporal rows. The full-frame
  runs retain 464 × 832 measurement images. Millimeter output columns exist only
  when calibration is enabled. Runs completed without interactive selection windows.
- A final complete run passed with the asynchronous kernel manager used by the app.
- Real-kernel cancellation stopped a temporary 30-second cell promptly, returned
  exit code 130 and saved a cancelled status plus partial notebook/report output.
  This exposed and fixed an upstream signal/blocking-channel conflict in earlier
  runner iterations; mocked cancellation tests alone were insufficient.
- Python syntax checks and Git whitespace checks pass.

Actual-video test selections used the primary frame at 1 s and secondary at 5 s,
ROI (172,357,154,109), ruler endpoints (239,484)/(304,485), and the pupil selections
from the user's prior run. Full-frame pupil coordinates were mapped from those
same original-pixel selections. No human ground-truth annotation was supplied.

## Remaining limitations

The GUI simplifies operation; it does not establish anatomical segmentation
accuracy, validate physiological measurements, or implement Module 4. Full-frame
processing can admit distracting regions. Calibration assumes a suitable ruler
plane and stable camera distance. Inspect overlays and compare with manual
references before interpreting results. Validation files are separate test evidence,
not a saved profile to be automatically applied to another video.
