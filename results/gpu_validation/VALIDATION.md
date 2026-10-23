# Optional OpenCL GPU requests — 2026-10-23

53 automated tests passed. Added tests cover CPU parity, UMat numerical paths
executed on CPU, mocked GPU availability, missing/broken runtime, rejecting CPU
OpenCL devices, preserving float64 math, explicit runtime fallback, diagnostic
reports, configuration/profile persistence and reset to CPU defaults.

The local machine exposes AMD Radeon hardware but OpenCV reports no usable OpenCL
runtime, including outside the sandbox. **Actual GPU execution and speedup were
not verified.** No GPU drivers or system packages were installed or modified.
UMat attempt counters are dispatch evidence, not proof of GPU kernel execution.

All five notebooks completed on A_2 with `acceleration.gpu: true`. They exported
HTML reports without extra prompts. Five per-kernel reports showed GPU requested,
no OpenCL GPU available, and zero UMat dispatch attempts. Module 1 recorded explicit
CPU fallbacks for all five supported operation types (see `dispatch_report.json`).
Module 1 metrics, Module 2 measurements, Module 3 pupil curves and Module 4 diameter
comparison CSVs exactly matched the preceding CPU-only run.

The actual Tk GUI was exercised: background GPU probing showed the CPU fallback
message; the checkbox persisted per video; turning it on/off preserved pupil
selections and loaded frames; Run remained available after probing. The optional
automatic pupil workflow continued to work. A screenshot was visually inspected.

Full temporary reports are under `/tmp/psib-gpu-validation/`. GPU benchmarks and
numerical parity on actual hardware remain pending until a working OpenCL GPU
runtime is installed/configured. Default CPU processing requires no GPU setup.
