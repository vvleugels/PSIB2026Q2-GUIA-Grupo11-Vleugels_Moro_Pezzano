"""Open desktop folders without leaking OpenCV's bundled libraries."""
import os
from pathlib import Path
import shutil
import subprocess


def desktop_environment():
    env=os.environ.copy()
    for key in ('QT_QPA_PLATFORM_PLUGIN_PATH','QT_QPA_FONTDIR'):
        if 'cv2' in env.get(key,''):env.pop(key,None)
    libraries=env.get('LD_LIBRARY_PATH')
    if libraries is not None:
        remaining=[p for p in libraries.split(os.pathsep) if p and 'cv2' not in p]
        if remaining:env['LD_LIBRARY_PATH']=os.pathsep.join(remaining)
        else:env.pop('LD_LIBRARY_PATH',None)
    return env


def open_folder(path):
    folder=Path(path).resolve()
    if not folder.is_dir():raise FileNotFoundError(f'Results folder does not exist: {folder}')
    errors=[]
    for program,args in [('xdg-open',[str(folder)]),('gio',['open',str(folder)])]:
        executable=shutil.which(program)
        if not executable:continue
        try:
            result=subprocess.run([executable,*args],env=desktop_environment(),capture_output=True,text=True,timeout=10)
            if result.returncode==0:return folder
            errors.append(f'{program}: {(result.stderr or result.stdout or str(result.returncode)).strip()[:500]}')
        except (OSError,subprocess.TimeoutExpired) as exc:errors.append(f'{program}: {exc}')
    raise RuntimeError('\n'.join(errors) or 'No folder opener found (xdg-open or gio).')
