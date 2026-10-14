"""Execute source notebooks; save executed copies without modifying sources."""
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'src'))

if __name__=='__main__':
    from psib.notebook_runner import main
    raise SystemExit(main(ROOT))
