import json, os, pathlib, subprocess

def main():
    root = next(p for p in pathlib.Path(os.getcwd()).parents
                if (p / ".venv/bin/python").is_file() and (p / "gates").is_dir())
    suite = root / "gates" / 'scikit-learn__scikit-learn-25747'
    proc = subprocess.run([str(root / ".venv/bin/python"), "-I", str(suite / "runner.py"),
                           os.getcwd(), str(suite / "selection.json")],
                          capture_output=True, text=True, timeout=1800,
                          env={**os.environ, "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1"})
    assert proc.returncode == 0, proc.stdout + proc.stderr
