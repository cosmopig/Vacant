from pathlib import Path
import runpy

def main():
    workspace = Path.cwd()
    root = next(p for p in workspace.parents if (p / "gates" / 'sympy__sympy-13974' / "selection.json").is_file())
    suite = root / "gates" / 'sympy__sympy-13974'
    runpy.run_path(str(suite / "gate_runtime.py"))["check"](workspace, suite, root / 'sympy__sympy-13974')
