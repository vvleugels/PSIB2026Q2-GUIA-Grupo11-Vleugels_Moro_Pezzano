# Module 2 validation — 2026-10-13

Executed on A_1.mp4 with the existing virtual environment. Both configured frames
were processed by Otsu, K-means (K=2–5), active contours and watershed. Morphology
includes erosion, dilation, opening, closing, combined cleanup, hole filling and
contour skeletonization. Binary masks and measurements are saved in results/module2.

Visual inspection: Otsu and K=2 include substantial iris/shadow regions. Higher K
improves isolation but retains reflection-related defects. Snakes and watershed
produce more localized pupil masks; snakes are the configured provisional method.
The primary frame remains affected by the reflection and initialization sensitivity.
No manual references were supplied, so Dice/IoU accuracy and a final winning method
cannot be claimed. The notebook supports reference polygons and .npy masks.

Calibration arithmetic was checked with diagonal endpoints (30,40 pixels = 50
pixels/cm), area conversion (2500 pixels² = 1 cm²), and perimeter conversion
(200 pixels = 40 mm). Identity Dice and disjoint IoU were checked. A_1 has no ruler,
so physical measurements are deliberately absent from its CSV. The interactive
ruler selection needs validation by the user on an actual ruler-containing video.
Other videos were not available and were assumed suitable as requested.

The ruler and eye should share the measurement plane. Use each video's calibration
and avoid changing resolution after calibration. Equivalent diameter is derived
from mask area; perimeter is a discrete pixel estimate. Module 3 temporal processing
remains pending. Pupil seeds and ROI selection are still manual/configurable.
