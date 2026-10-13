"""Execute the existing notebooks and keep validation copies in results/."""
from pathlib import Path
import os
import sys

import nbformat
from nbclient import NotebookClient
from jupyter_client import KernelManager
from jupyter_client.kernelspec import KernelSpec

root = Path(__file__).resolve().parent
os.chdir(root)
os.environ["MPLBACKEND"] = "module://matplotlib_inline.backend_inline"
out = root / "results" / "validation"
out.mkdir(parents=True, exist_ok=True)
paths = [root / "notebooks" / name for name in sys.argv[1:]] if len(sys.argv) > 1 else sorted((root / "notebooks").glob("*.ipynb"))
for path in paths:
    nb = nbformat.read(path, as_version=4)
    km = KernelManager(kernel_name="python3")
    km._kernel_spec = KernelSpec(argv=[sys.executable, "-m", "ipykernel_launcher", "-f", "{connection_file}"], display_name="Validation Python", language="python")
    client = NotebookClient(nb, km=km, timeout=300, resources={"metadata": {"path": str(root)}})
    try:
        client.execute()
    finally:
        nbformat.write(nb, out / path.name)
        if km.has_kernel:
            km.shutdown_kernel(now=True)
    print("EXECUTED", path.name, flush=True)
    for i, cell in enumerate(nb.cells):
        for output in cell.get("outputs", []):
            if output.output_type == "stream":
                print(i, output.text[:2000], flush=True)
