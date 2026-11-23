from pathlib import Path
import runpy
import json
import os

def main():
    workspace = Path.cwd()
    root = next(p for p in workspace.parents if (p / "gates" / 'sphinx-doc__sphinx-7462' / "selection.json").is_file())
    suite = root / "gates" / 'sphinx-doc__sphinx-7462'
    os.environ.update(json.loads((suite / "selection.json").read_text()).get("runner_environment", {}))
    runpy.run_path(str(suite / "gate_runtime.py"))["check"](workspace, suite, root / 'sphinx-doc__sphinx-7462')
