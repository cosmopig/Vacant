import os, pathlib, subprocess, tempfile

def main():
    with tempfile.TemporaryDirectory() as temp:
        path = pathlib.Path(temp) / "test_public.py"
        path.write_text('import pytest\nfrom shipping import shipping_cost\n\ndef test_negative():\n    with pytest.raises(ValueError):\n        shipping_cost(-1)\n')
        driver = "import sys,pytest; sys.path.insert(0,sys.argv.pop(1)); raise SystemExit(pytest.main(sys.argv[1:]))"
        run = subprocess.run([next(str(p / ".venv/bin/python") for p in pathlib.Path(os.getcwd()).parents if (p / ".venv/bin/python").is_file()), "-I", "-c", driver, os.getcwd(), str(path), "-q", "-p", "no:cacheprovider", "--noconftest"], capture_output=True, text=True, timeout=10, env={**os.environ, "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1"})
        assert run.returncode == 0, run.stdout + run.stderr
