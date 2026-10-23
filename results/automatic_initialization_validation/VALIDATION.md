# Optional automatic pupil initialization — 2026-10-23

47 automated tests passed, including synthetic pupil/reflection/distractor tests,
ambiguous and flat images, full-frame coordinate mapping, tracking failure,
manual/automatic state isolation, legacy profiles, invalidation and overlays.

The actual Tk GUI was exercised on A_2: turning off manual pupil selection enabled
Run without any pupil clicks; primary/secondary buttons showed read-only estimate
previews; hiding overlays worked; restoring manual mode retained old manual points.
A screenshot of the secondary estimate was visually inspected.

Modules 0–4 ran successfully with A_2 at 1 s / 5 s, calibration enabled, and ROI
both enabled and disabled. All five HTML reports were generated without pupil
selection prompts. Every temporal pass processed 238 frames. Module 4's baseline
matched Module 3 exactly. Full-frame measurement images remained 464 × 832 pixels.
The effective run configuration used fixed numeric values with
`initialization_source: automatic`, avoiding redetection or prompts in notebooks.

See `initializations.json` for seeds and accepted-frame counts. Moving-ROI tracking
accepted 227/238 frames; full-frame tracking accepted 97/238. These counts describe
algorithm quality flags, not anatomical accuracy. Automatic full-frame tracking is
more sensitive to the seed-dependent tracking support region. Prefer an eye ROI
and review overlays; manual mode remains available. No human ground-truth pupil
annotations were supplied.

Complete executed reports and figures remain in
`/tmp/psib-auto-pupil-validation/`; their lifetime depends on temporary-directory
cleanup. No existing profiles or project results were removed. The live GUI check
used a separate temporary profile directory.
