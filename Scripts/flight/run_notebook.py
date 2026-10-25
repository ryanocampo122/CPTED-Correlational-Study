"""
run_notebook.py
===============
ComputerVision_Sentinel | Run one notebook top to bottom and save the run copy with its outputs

The notebook runs in Notebooks/ (so `from _setup import *` works), in the Python that runs this
script (.venv). The notebook in Notebooks/ is not changed; the copy with outputs goes to <out>.
Exits 1 if any cell raises an error (the copy is still saved, with the error in it).

USAGE (repository root)
-----
  .venv/bin/python Scripts/flight/run_notebook.py Notebooks/01_reddit.ipynb <out.ipynb> [--timeout 600]
"""

# Command-line options, file paths, and the exit code
import argparse
import sys
from pathlib import Path

# Reading, running and writing notebooks
import nbformat
from nbclient import NotebookClient
from nbclient.exceptions import CellExecutionError


def main():
    """Run the notebook and save the copy with outputs.

    :return: exit code (0 = every cell ran, 1 = a cell failed)
    """
    # The notebook to run, where to save the run copy, and how long one cell may take
    parser = argparse.ArgumentParser(description="Run one notebook and save a copy with its outputs.")
    parser.add_argument("notebook", type=Path)
    parser.add_argument("out", type=Path)
    parser.add_argument("--timeout", type=int, default=600, help="seconds allowed per cell")
    # Read what was typed
    args = parser.parse_args()

    # Read the notebook
    nb = nbformat.read(args.notebook, as_version=4)
    # Run it in its own folder, with this Python's kernel
    client = NotebookClient(nb, timeout=args.timeout, kernel_name="python3",
                            resources={"metadata": {"path": str(args.notebook.resolve().parent)}})
    # Exit code: 0 unless a cell fails
    code = 0
    # Run every cell; stop at the first error
    try:
        client.execute()
    except CellExecutionError as err:
        print(f"{args.notebook.name}: a cell failed\n{err}")
        # Report the failure in the exit code
        code = 1
    # Save the copy with its outputs (also when a cell failed, so the error can be read)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    nbformat.write(nb, args.out)
    # Count the code cells that ran
    ran = sum(1 for cell in nb.cells if cell.cell_type == "code" and cell.get("execution_count"))
    print(f"{args.notebook.name}: {ran} code cells run -> {args.out}")
    return code


# Run main() only when this file is run directly, and pass its exit code on
if __name__ == "__main__":
    sys.exit(main())
