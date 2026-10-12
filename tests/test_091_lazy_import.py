"""0.9.1 熱路徑：套件 `__init__` 惰性匯入（PEP 562）。

承重：Claude 掛鉤每個工具呼叫跑兩次 `python -m vacant_network hook`，匯入 `vacant_network.adapters.hook`
不該連帶載入 brains（urllib.request）、controller、gateway、host 等無關子模組。
誠實邊界：這只量「沒被連帶載入」，不量秒數（秒數隨機器變）。
"""
from __future__ import annotations

import subprocess
import sys

import pytest

import vacant_network


def _run(code: str) -> str:
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    return r.stdout


def test_hook_import_does_not_pull_heavy_modules():
    out = _run("import sys, vacant_network.adapters.hook;"
               "print(' '.join(sorted(m for m in sys.modules if m.startswith('vacant_network'))))")
    loaded = set(out.split())
    for heavy in ("brains", "agent", "controller", "gateway", "host", "agent", "waker", "composer"):
        assert f"vacant_network.{heavy}" not in loaded, heavy


def test_every_all_name_resolves_in_fresh_process():
    out = _run("import vacant_network as v;"
               "missing=[n for n in v.__all__ if getattr(v, n, None) is None];"
               "print(len(v.__all__), missing)")
    assert out.strip() == f"{len(vacant_network.__all__)} []"


@pytest.mark.parametrize("name", vacant_network.__all__)
def test_every_exported_name_still_importable(name):
    ns: dict = {}
    exec(f"from vacant_network import {name} as x", ns)
    assert ns["x"] is not None


def test_unknown_attribute_raises_and_all_unchanged():
    with pytest.raises(AttributeError):
        vacant_network.no_such_name  # noqa: B018
    assert len(vacant_network.__all__) == 50
    assert set(vacant_network.__all__) <= set(dir(vacant_network))
