# Moving ROI validation — 2026-10-13

## Implemented behavior

Eye translation is tracked independently of pupil segmentation. Sparse optical
flow uses eyelids/corners/context features, excludes the central eye region,
normalizes local contrast for lighting changes, checks forward/backward error and
fits robust motion. A fixed-reference template supports recovery. The crop is
translated at constant pixel dimensions without resizing. Unsupported per-frame
rotation/scale, insufficient features and out-of-frame positions are rejected.
Gradual camera-depth movement can still invalidate physical calibration.

The ROI belongs to the selected primary reference frame, not necessarily frame 0.
Comparison notebooks follow intervening video frames before extracting their
second crop. Full-video processing tracks back from the reference to the first
frame, then forward. Pupil centers are mapped between crop/full/reference-frame
coordinates; pupil-motion rejection compensates for the eye translation.

Interactive pupil initialization now accepts a center and boundary point. The
new default local multi-level Otsu pupil method evaluates the darkest group in a
pupil/iris neighborhood and retains one component after cleanup. Consecutive
consistent candidates permit pupil reacquisition after size/position jumps.
Quality checks are heuristic, not anatomical ground truth.

## Actual-video run

Input: /home/zenith/Videos/PSIB/A_2.mp4.
Reference timestamp: 1 s; comparison: 5 s.
Manual test ROI: (135, 350, 220, 115); support margin: 10 px.
Initial test pupil center: (115, 68), radius: 25 px, ROI-local.
Interactive ruler calibration was disabled for this automated test, not changed
in the user's configuration. No physical accuracy claim is made for this run.

Modules 1, 2 and 3 executed without errors using temporary noninteractive settings.
Outputs were kept in this separate tracking_validation folder; earlier user outputs
were preserved. 238 frames were decoded. Eye tracking passed checks on all 238;
pupil segmentation passed on 215 (90.3%). There were 8 confirmed pupil reacquisition
events. The expanded crop stayed 240 × 135 pixels throughout the video.

Full-frame crop overlays show the eye remains inside the moving crop. Pupil
overlays still show imperfect boundaries, especially in low contrast and near
reflections/eyelashes. Passing checks does not establish accuracy. No manual
reference masks or manual size measurements were supplied; Dice/IoU and MAE/RMSE
remain pending. Physiological outputs remain exploratory.

## Automated checks

12 tests pass: the existing four temporal/texture tests, plus eye translation,
backward initialization, loss/recovery, fixed-template recovery, blank rejection,
pupil-size independence, unsupported rotation rejection, and a temporal integration
check for full/reference coordinates and unchanged physical scale during translation.
The integration check uses a controlled contour to isolate motion/coordinate logic;
it does not validate anatomical segmentation. Notebook schemas and cell syntax pass.
