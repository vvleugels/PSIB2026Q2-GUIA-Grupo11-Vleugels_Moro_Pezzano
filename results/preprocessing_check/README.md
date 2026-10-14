# Preprocessing comparison on A_2

Compared original grayscale, global histogram equalization, CLAHE (clip=2,
8x8 tiles), and a 3x3 median filter followed by CLAHE. Each variant was passed to
local multi-level Otsu and snakes with identical per-frame initialization and
morphological cleanup. Outlines are displayed on the original RGB image.

Video timestamps: 1 and 5 seconds. ROI: (172,357,154,109) at the primary frame,
tracked to the secondary frame. Pupil seeds/radii reproduced the user's latest
Module 2 selections: (76,55), radius 23.3452; (74,50), radius 8.9443.

The new local method retained nonempty cleaned masks (1669 and 216 pixels²)
without equalization. Its low-light boundary remains imperfect. Equalization
increased the low-light mask area and visually included additional iris regions.
CLAHE and median+CLAHE did not show a clear improvement on that frame.

Snakes collapsed on the dark frame with every preprocessing option tested.
Global equalization also caused snakes to collapse on the contracted-pupil frame,
where the unprocessed snake result was nonempty and visually plausible.

These results show that preprocessing is not automatically beneficial. There
are no annotated reference masks, so the comparison supplies visual evidence and
areas, not quantitative anatomical accuracy. No production preprocessing setting
was changed based on this experiment. See comparison.csv and the two PNG figures.
