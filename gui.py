"""Launch the local PSIB desktop app using the active Python environment."""
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'src'))
if __name__=='__main__':
    try:
        from psib.desktop import main
    except ModuleNotFoundError as exc:
        raise SystemExit(f'Missing dependency: {exc.name}. Install requirements.txt; on Linux, Tkinter may require python3-tk.')
    main(ROOT)
