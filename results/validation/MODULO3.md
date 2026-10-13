# Module 3 implementation and validation — 2026-10-13

The notebook processes the selected video from beginning to end using decoded
presentation timestamps. Frame descriptors include area, perimeter, centroid,
circularity, eccentricity, independent RGB statistics and masked symmetric GLCM
features. Iris texture uses an approximate ring, not a manually delineated iris.

The temporal tracker supports snakes, watershed and K-means. The configured
snakes reacquire a dark component independently and initialize a fresh circle
rather than propagating a shrinking or drifting contour. Area, border, diameter and center-motion checks flag suspect
masks. Raw measurements and rejection reasons remain available. Short internal
gaps are interpolated with actual timestamps; long gaps and endpoints stay missing.
Smoothing operates separately on each finite segment. Review sampled overlays.

A_1 has 207 frames and no ruler calibration. It is a difficult validation example:
reflection and low pupil/iris contrast affect segmentation. Passing heuristic
checks does not prove anatomical accuracy. Physiological CSV values are explicitly
unvalidated; the stimulus is brightness-derived unless manually specified.
Latency requires sustained baseline-relative change; missing baseline yields NaN.
A and B response directions are supported. Physical lengths/areas reuse the
per-video calibration. No unseen videos were available for external testing.

Manual measurement CSV input enables MAE/RMSE on accepted annotated frames,
with matched/evaluated/rejected counts. No manual measurements were supplied.
Between-trial tables aggregate existing per-video outputs; with one A trial,
sample standard deviations are undefined. Millimeter amplitude columns are
included when calibrated trials exist; pixel comparisons require equal scales.

Four synthetic tests pass: masked GLCM excludes outside-mask background;
short-gap interpolation preserves long gaps/endpoints; known A/B response
latency/amplitude and physical conversion; missing-baseline handling.
Notebook schema and all Python cells were checked. The executed notebook is
saved under results/validation, and per-frame/per-video CSV outputs under
results/module3/A_1. Manual anatomical accuracy remains pending.

Final full execution: 207 rows; 90 frames passed heuristic checks (43.5%),
34 rejected frames were filled as short internal gaps. Visual inspection still
shows inaccurate contours on A_1, including some accepted masks. Therefore the
physiological CSV is an exploratory algorithm output and must not be used as a
validated measurement. Manual annotations and clean recordings are needed before
assessing physiological accuracy; all other videos remain unavailable.
