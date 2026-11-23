from pathlib import Path
import runpy

def main():
    workspace = Path.cwd()
    root = next(p for p in workspace.parents if (p / "gates" / 'astropy__astropy-14182' / "selection.json").is_file())
    suite = root / "gates" / 'astropy__astropy-14182'
    runpy.run_path(str(suite / "gate_runtime.py"))["check"](workspace, suite, root / 'astropy__astropy-14182')
