from pathlib import Path
import runpy

def main():
    workspace = Path.cwd()
    root = next(p for p in workspace.parents if (p / "gates" / 'mwaskom__seaborn-3187' / "selection.json").is_file())
    suite = root / "gates" / 'mwaskom__seaborn-3187'
    runpy.run_path(str(suite / "gate_runtime.py"))["check"](workspace, suite, root / 'mwaskom__seaborn-3187')
