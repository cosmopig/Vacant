import os, pathlib, subprocess, tempfile

def main():
    with tempfile.TemporaryDirectory() as temp:
        path = pathlib.Path(temp) / "tests"
        path.mkdir()
        for name, content in {'test_visible.py': b'from service import Catalog\n\ndef test_catalog_lookup():\n    catalog = Catalog()\n    catalog.add("Tea", 250)\n    assert catalog.lookup("tea")["price"] == 250\n'}.items():
            target = path / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
        driver = "import sys,pytest; sys.path.insert(0,sys.argv.pop(1)); raise SystemExit(pytest.main(sys.argv[1:]))"
        run = subprocess.run([next(str(p / ".venv/bin/python") for p in pathlib.Path(os.getcwd()).parents if (p / ".venv/bin/python").is_file()), "-I", "-c", driver, os.getcwd(), str(path), "-q", "-p", "no:cacheprovider", "--noconftest", "--import-mode=importlib"], capture_output=True, text=True, timeout=10, env={**os.environ, "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1"})
        assert run.returncode == 0, run.stdout + run.stderr
