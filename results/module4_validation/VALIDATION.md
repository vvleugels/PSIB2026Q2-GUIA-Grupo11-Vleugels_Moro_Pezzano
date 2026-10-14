# Module 4 validation — 2026-10-14

All five notebooks ran on A_2 in all four combinations of moving ROI/full frame
and calibration on/off. Each run exported five executed notebooks and HTML reports
without interactive prompts. Each baseline and JPEG Q=50/10 pass decoded all 238
frames. Every Module 4 uncompressed baseline exactly matched Module 3, including
physical columns when calibrated; calibration-off curves contained no mm columns.

For each configuration, all 56 selected-frame encoded files were checked against
reported byte sizes. Huffman and both RLE variants reconstructed exactly, with
PSNR=inf and SSIM=1. Ratios include complete file metadata.

The additional save-all run retained 476 JPEG files (238 at each temporal quality),
with verified byte sizes and frame-index/timestamp mappings. Compact runs retained
no temporal JPEGs. Completed experiment manifests were checked.

Real-kernel failure testing stopped at setup cell 1 and prevented subsequent
notebooks, returning exit 1. SIGTERM during temporal cell 5 returned exit 130,
preserved partial notebook/HTML reports, and closed the recorded kernel child.
Actual Tk widgets were instantiated on the desktop: the button reads Modules 0–4,
Module 4 progress mapped correctly to 85% at its first completed cell, and a
comparison figure loaded in the results viewer. Visual comparisons were inspected.

40 automated tests passed, including existing segmentation/tracking tests and new
codec, malformed-file, pairing, transform/observer, retention and timeout tests.
Dependency consistency and Git whitespace checks passed. The final notebook's
added pupil-edge display expressions were exercised against the generated figures.

## Interpretation

For moving ROI, Q=50 yielded paired diameter MAE about 0.96 px (214 paired frames).
Q=10 yielded about 6.70 px (78 paired frames), with only 87/238 frames accepted
versus 219/238 in the baseline. Inspect `diameter_summary.csv` for all configurations.
These are differences from an existing, anatomically unvalidated algorithm.
Successful execution and higher acceptance do not establish anatomical accuracy.

## Evidence and retention

This folder retains summary/selected-frame metrics, physiological comparisons,
input/configuration provenance, runner failure/cancellation statuses, and three
representative figures. Complete temporary runs (executed notebooks, all figures,
compressed selected-frame files, framewise curves and save-all JPEGs) remain in
`/tmp/psib-module4-validation/`; those temporary files are not repository content.
Their lifetime depends on system temporary-directory cleanup. No example video
was selected or bundled, and no existing project results were removed.
