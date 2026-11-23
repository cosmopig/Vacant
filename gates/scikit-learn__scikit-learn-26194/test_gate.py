from pathlib import Path
import runpy

def main():
    workspace = Path.cwd()
    root = next(p for p in workspace.parents if (p / "gates" / 'scikit-learn__scikit-learn-26194' / "selection.json").is_file())
    suite = root / "gates" / 'scikit-learn__scikit-learn-26194'
    runpy.run_path(str(suite / "gate_runtime.py"))["check"](workspace, suite, root / 'scikit-learn__scikit-learn-26194')
