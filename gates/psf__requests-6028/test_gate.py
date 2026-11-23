from pathlib import Path
import runpy

def main():
    workspace = Path.cwd()
    root = next(p for p in workspace.parents if (p / "gates" / 'psf__requests-6028' / "selection.json").is_file())
    suite = root / "gates" / 'psf__requests-6028'
    runpy.run_path(str(suite / "gate_runtime.py"))["check"](workspace, suite, root / 'psf__requests-6028')
