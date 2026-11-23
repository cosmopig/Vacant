from pathlib import Path
import runpy

def main():
    workspace = Path.cwd()
    root = next(p for p in workspace.parents if (p / "gates" / 'matplotlib__matplotlib-25479' / "selection.json").is_file())
    suite = root / "gates" / 'matplotlib__matplotlib-25479'
    runpy.run_path(str(suite / "gate_runtime.py"))["check"](workspace, suite, root / 'matplotlib__matplotlib-25479')
