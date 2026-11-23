from pathlib import Path
import runpy

def main():
    workspace = Path.cwd()
    root = next(p for p in workspace.parents if (p / "gates" / 'sphinx-doc__sphinx-9461' / "selection.json").is_file())
    suite = root / "gates" / 'sphinx-doc__sphinx-9461'
    runpy.run_path(str(suite / "gate_runtime.py"))["check"](workspace, suite, root / 'sphinx-doc__sphinx-9461')
