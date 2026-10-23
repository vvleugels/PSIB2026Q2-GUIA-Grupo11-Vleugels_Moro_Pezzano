"""Optional OpenCV OpenCL dispatch; availability is not proof of GPU execution.

OpenCV may transparently execute individual UMat operations on the CPU. Reports
count dispatch attempts, never claim to measure kernels or promise a speedup.
"""
import json
import os
from pathlib import Path
from threading import RLock
import cv2
import numpy as np

_lock = RLock()
_state = dict(requested=False, available=False, device=None, double_precision=False,
              message='GPU off — CPU processing.', umat_attempts={}, cpu_fallbacks={})
_report_path = None


def probe_gpu():
    """Probe an OpenCL GPU in the calling thread; restore its previous setting."""
    result = dict(available=False, device=None, double_precision=False,
                  message='GPU unavailable — OpenCL runtime/device not found; using CPU.')
    previous = False
    try:
        previous = cv2.ocl.useOpenCL()
        if not cv2.ocl.haveOpenCL():
            return result
        cv2.ocl.setUseOpenCL(True)
        if not cv2.ocl.useOpenCL():
            return result
        device = cv2.ocl.Device_getDefault()
        if not device.available() or not device.type() & cv2.ocl.Device_TYPE_GPU:
            result['message'] = 'No OpenCL GPU selected — using CPU (CPU OpenCL devices do not count).'
            return result
        result.update(available=True, device=device.name(), double_precision=bool(device.doubleFPConfig()),
                      message=f'OpenCL GPU available: {device.name()}. Supported operations may still use CPU.')
        return result
    except Exception as exc:
        result['message'] = f'GPU probe failed — using CPU: {exc}'
        return result
    finally:
        try: cv2.ocl.setUseOpenCL(previous)
        except Exception: pass


def _write_report():
    if _report_path is None:
        return
    # Diagnostics must never turn a successful image operation into a failed run.
    try:
        temp = _report_path.with_suffix('.tmp')
        temp.write_text(json.dumps(_state, indent=2))
        temp.replace(_report_path)
    except OSError:
        pass


def configure(request_gpu=False, report_dir=None):
    """Configure one process/run. CPU remains the default and fallback."""
    global _state, _report_path
    if type(request_gpu) is not bool:
        raise ValueError('acceleration.gpu must be true or false')
    with _lock:
        info = probe_gpu() if request_gpu else dict(available=False, device=None, double_precision=False,
                                                    message='GPU off — CPU processing.')
        _state = dict(requested=request_gpu, **info, umat_attempts={}, cpu_fallbacks={},
                      supported_steps=['mean_filter', 'median_filter', 'gaussian_filter', 'fft2', 'ifft2'],
                      interpretation='UMat attempts are not verified GPU kernel executions; OpenCV may use CPU.')
        _report_path = None
        if report_dir is not None:
            folder = Path(report_dir); folder.mkdir(parents=True, exist_ok=True)
            _report_path = folder/f'process_{os.getpid()}.json'
        cv2.ocl.setUseOpenCL(request_gpu and info['available'])
        _write_report()
        return dict(_state)


def status():
    with _lock:
        return json.loads(json.dumps(_state))


def _record(kind, operation, error=None):
    with _lock:
        counts = _state[kind]; counts[operation] = counts.get(operation, 0)+1
        if error is not None: _state['last_fallback_reason'] = str(error)
        _write_report()


def dispatch(operation, cpu, opencl, *, needs_double=False):
    """Attempt a UMat operation when a GPU is available; otherwise retain CPU math."""
    if not _state['requested']:
        return cpu()
    if not _state['available'] or (needs_double and not _state['double_precision']):
        _record('cpu_fallbacks', operation, 'No usable OpenCL GPU / required float64 support')
        return cpu()
    try:
        # OpenCV's OpenCL enablement is thread-local. Notebook operations normally
        # run in one thread, but setting it here also supports worker callers.
        cv2.ocl.setUseOpenCL(True)
        if not cv2.ocl.useOpenCL():
            _record('cpu_fallbacks', operation, 'OpenCL disabled in the operation thread')
            return cpu()
        result = opencl()
        _record('umat_attempts', operation)
        return result
    except (cv2.error, RuntimeError) as exc:
        _record('cpu_fallbacks', operation, exc)
        return cpu()


def fft2(image):
    image = np.asarray(image, dtype=np.float64)
    def accelerated():
        result = cv2.dft(cv2.UMat(image), flags=cv2.DFT_COMPLEX_OUTPUT).get()
        return result[..., 0]+1j*result[..., 1]
    return dispatch('fft2', lambda: np.fft.fft2(image), accelerated, needs_double=True)


def ifft2(spectrum):
    spectrum = np.asarray(spectrum, dtype=np.complex128)
    def accelerated():
        channels = np.stack([spectrum.real, spectrum.imag], axis=-1)
        # Keep both channels: arbitrary phase reconstructions need not be Hermitian.
        result = cv2.idft(cv2.UMat(channels), flags=cv2.DFT_SCALE).get()
        return result[..., 0]+1j*result[..., 1]
    return dispatch('ifft2', lambda: np.fft.ifft2(spectrum), accelerated, needs_double=True)
