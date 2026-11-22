import os, pathlib, subprocess, sys, tempfile

def main():
    with tempfile.TemporaryDirectory() as temp:
        path = pathlib.Path(temp) / "test_public.py"
        path.write_text('from counts import merge_counts\n\ndef test_empty():\n    assert merge_counts() == {}\n')
        driver = "import sys,pytest; sys.path.insert(0,sys.argv.pop(1)); raise SystemExit(pytest.main(sys.argv[1:]))"
        run = subprocess.run([sys.executable, "-I", "-c", driver, os.getcwd(), str(path), "-q", "-p", "no:cacheprovider", "--noconftest"], capture_output=True, text=True, timeout=10, env={**os.environ, "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1"})
        assert run.returncode == 0, run.stdout + run.stderr
