from pathlib import Path
import runpy

def main():
    workspace = Path.cwd()
    root = next(p for p in workspace.parents if (p / "gates" / 'django__django-14034' / "selection.json").is_file())
    suite = root / "gates" / 'django__django-14034'
    runpy.run_path(str(suite / "gate_runtime.py"))["check"](workspace, suite, root / 'django__django-14034')
