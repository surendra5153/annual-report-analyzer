"""
Build .ipynb notebooks from percent-format sources (`# %%` code cells,
`# %% [markdown]` markdown cells) and execute them so outputs are embedded.

Sources stay as plain .py (easy to diff/review); the executed .ipynb is what
gets submitted / opened in Jupyter.

Usage (from repo root):
    python -m ml.notebooks.nbbuild                 # build + execute all
    python -m ml.notebooks.nbbuild 01_preprocessing --no-exec
"""
import argparse
import re
from pathlib import Path

import nbformat
from nbconvert.preprocessors import ExecutePreprocessor

NB_DIR = Path(__file__).resolve().parent
REPO_DIR = NB_DIR.parents[1]
_CELL_RE = re.compile(r"^# %%(?: \[(markdown)\])?.*$", re.MULTILINE)


def parse_cells(source: str):
    marks = list(_CELL_RE.finditer(source))
    for i, m in enumerate(marks):
        body = source[m.end(): marks[i + 1].start() if i + 1 < len(marks) else len(source)].strip("\n")
        if m.group(1) == "markdown":
            text = "\n".join(l[2:] if l.startswith("# ") else l.lstrip("#") for l in body.splitlines())
            yield nbformat.v4.new_markdown_cell(text.strip())
        elif body.strip():
            yield nbformat.v4.new_code_cell(body)


def build(name: str, execute: bool) -> Path:
    src = NB_DIR / f"{name}.py"
    nb = nbformat.v4.new_notebook()
    nb.cells = list(parse_cells(src.read_text(encoding="utf-8")))
    nb.metadata["kernelspec"] = {"name": "python3", "display_name": "Python 3", "language": "python"}
    if execute:
        ExecutePreprocessor(timeout=1800, kernel_name="python3").preprocess(
            nb, {"metadata": {"path": str(REPO_DIR)}}  # run from repo root so `import ml...` works
        )
    out = NB_DIR / f"{name}.ipynb"
    nbformat.write(nb, out)
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("names", nargs="*")
    ap.add_argument("--no-exec", action="store_true")
    args = ap.parse_args()
    names = args.names or sorted(p.stem for p in NB_DIR.glob("[0-9][0-9]_*.py"))
    for n in names:
        print("built", build(n, execute=not args.no_exec))
