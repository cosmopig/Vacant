"""W4（乾淨環境新手體驗）抓到的缺陷：agent 沒裝時 `vacant do` 要立刻講清楚，不要靜靜燒三次；`vacant --version` 要能用。"""
import subprocess
import sys

from vacant_network.adapters import agents as A
from vacant_network.adapters import cli as adapters_cli


def _proj(tmp_path):
    p = tmp_path / "proj"
    p.mkdir()
    (p / "calc.py").write_text("def add(a, b):\n    return a - b\n")
    (p / "test_calc.py").write_text(
        "import unittest\nfrom calc import add\n"
        "class T(unittest.TestCase):\n    def test_add(self):\n        self.assertEqual(add(2, 3), 5)\n")
    return p


def test_named_agent_missing_stops_before_any_attempt(tmp_path, monkeypatch, capsys):
    p = _proj(tmp_path)
    monkeypatch.setenv("VACANT_WORK", str(tmp_path / "work"))
    monkeypatch.setenv("VACANT_HOME", str(tmp_path / "home"))
    monkeypatch.setattr(A, "which", lambda names: None)
    monkeypatch.chdir(p)
    rc = adapters_cli.main(["do", "pi", "--prompt", "fix add"])
    err = capsys.readouterr().err
    assert rc == adapters_cli.EXIT["void"]
    assert "pi is not installed or not on PATH" in err
    assert not (tmp_path / "work").exists() or not any((tmp_path / "work").glob("restart-*"))
    assert (p / "calc.py").read_text() == "def add(a, b):\n    return a - b\n"


def test_cmd_missing_binary_stops(tmp_path, monkeypatch, capsys):
    p = _proj(tmp_path)
    monkeypatch.setenv("VACANT_WORK", str(tmp_path / "work"))
    monkeypatch.setenv("VACANT_HOME", str(tmp_path / "home"))
    monkeypatch.chdir(p)
    rc = adapters_cli.main(["do", "--cmd", "definitely-not-a-binary-w4 {prompt}", "--prompt", "x"])
    assert rc == adapters_cli.EXIT["void"]
    assert "command not found" in capsys.readouterr().err


def test_version_flag():
    from vacant_network import __version__
    r = subprocess.run([sys.executable, "-m", "vacant_network", "--version"], capture_output=True, text=True)
    assert r.returncode == 0
    assert __version__ in r.stdout
