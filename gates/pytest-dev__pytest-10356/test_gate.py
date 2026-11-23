from pathlib import Path
import runpy
import json
import os

def main():
    workspace = Path.cwd()
    root = next(p for p in workspace.parents if (p / "gates" / 'pytest-dev__pytest-10356' / "selection.json").is_file())
    suite = root / "gates" / 'pytest-dev__pytest-10356'
    os.environ.update(json.loads((suite / "selection.json").read_text()).get("runner_environment", {}))
    runpy.run_path(str(suite / "gate_runtime.py"))["check"](workspace, suite, root / 'pytest-dev__pytest-10356')
