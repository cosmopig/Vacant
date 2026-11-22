import json, os, pathlib, subprocess

def main():
    root = next(p for p in pathlib.Path(os.getcwd()).parents
                if (p / ".venv/bin/python").is_file() and (p / "gates").is_dir())
    suite = root / "gates" / 'sympy__sympy-14248'
    config = json.loads((suite / "selection.json").read_text())
    interpreter = root / config["interpreter"]
    assert interpreter.is_file(), "Install the instance environment: " + str(interpreter)
    proc = subprocess.run([str(interpreter), "-I", str(suite / "runner.py"),
                           os.getcwd(), str(suite / "selection.json")],
                          capture_output=True, text=True, timeout=config["timeout_s"] - 10,
                          env={**os.environ, "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1"})
    assert proc.returncode == 0, proc.stderr + proc.stdout
