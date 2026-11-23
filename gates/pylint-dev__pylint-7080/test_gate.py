from pathlib import Path
import runpy

def main():
    workspace = Path.cwd()
    root = next(p for p in workspace.parents if (p / "gates" / 'pylint-dev__pylint-7080' / "selection.json").is_file())
    suite = root / "gates" / 'pylint-dev__pylint-7080'
    runpy.run_path(str(suite / "gate_runtime.py"))["check"](workspace, suite, root / 'pylint-dev__pylint-7080')
