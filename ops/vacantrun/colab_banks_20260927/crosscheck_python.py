#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""換一個 Python 直譯器，用**同一份 driver**（`acceptance.DRIVER_SRC`）重跑參考解 × 可見＋隱藏。

這支在架構裡承重什麼
--------------------
`gauge_banks.py` 走閘門那條路（`sandbox.run` → `bash -lc`）。在 macOS 上 `bash -l` 會讀
`/etc/profile` 的 `path_helper`，把 PATH 重排 ⇒ `VACANT_ACCEPT_PATH_PREPEND` **換不掉直譯器**
（2026-09-27 實測：PATH 前面明明是 .venv/bin，沙箱裡的 `python3` 仍是 `/usr/local/bin/python3` 3.13.1）。
所以量具主跑只量得到 3.13.1。Colab 的 `python3` 多半是 3.12——字面值（大整數、complex、
nan）在不同版本上會不會解析得一樣，要另外量。這支繞過 `bash -lc`，直接用指定的直譯器跑
driver，判準（driver 的 case 協定、`_parse_cases`）跟閘門是同一份。

它**不是**閘門路徑：沒有 rlimit、沒有逾時信封以外的東西。只回答「換版本，參考解還全過嗎」。

用法
----
    .venv/bin/python ops/vacantrun/colab_banks_20260927/crosscheck_python.py \\
        --python /path/to/python3.12 --private-root /path/to/.vacant-private
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import pathlib
import secrets
import shutil
import subprocess
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO))

from ops.vacantrun.colab_banks_20260927 import build_banks as BB  # noqa: E402
from vacant_network.vrun.acceptance import DRIVER_SRC, _parse_cases  # noqa: E402


def run_one(py: str, tpl: pathlib.Path, hid: pathlib.Path, code: str, timeout_s: float) -> bool:
    with tempfile.TemporaryDirectory() as t:
        t = pathlib.Path(t)
        ws = t / "ws"
        shutil.copytree(tpl, ws)
        (ws / "solution.py").write_text(code, encoding="utf-8")
        v = t / "v"
        v.mkdir()
        (v / "driver.py").write_text(DRIVER_SRC, encoding="utf-8")
        for f in (tpl / "tests_visible" / "test_visible.py", hid / "test_hidden.py"):
            shutil.copy2(f, v / f.name)
            nonce = "XCHK:" + secrets.token_hex(8) + ":"
            try:
                p = subprocess.run([py, str(v / "driver.py"), str(ws), str(v / f.name), nonce],
                                   cwd=ws, capture_output=True, text=True, timeout=timeout_s,
                                   env={"PATH": "/usr/bin:/bin", "HOME": str(ws), "LANG": "C.UTF-8",
                                        "PYTHONDONTWRITEBYTECODE": "1"})
            except subprocess.TimeoutExpired:
                return False
            cases = _parse_cases(p.stdout, nonce)
            if not cases or not all(c.get("ok") for c in cases):
                return False
        return True


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="換直譯器重跑參考解（同一份 driver）")
    ap.add_argument("--python", required=True)
    ap.add_argument("--bank", default="all")
    ap.add_argument("--private-root", default=None)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--timeout-s", type=float, default=30.0)
    a = ap.parse_args(argv)
    private_root = pathlib.Path(a.private_root) if a.private_root else BB.default_private_root()
    ver = subprocess.run([a.python, "-V"], capture_output=True, text=True).stdout.strip()
    rc = 0
    for bank in (list(BB.BANKS) if a.bank == "all" else a.bank.split(",")):
        root = BB.tree_root(bank, private_root)
        man = json.loads((root / "bank_manifest.json").read_text(encoding="utf-8"))
        if BB.BANKS[bank]["private"]:
            refs = {t: (root / "reference" / p["dir"] / "solution.py") for t, p in man["tasks"].items()}
            refs = {t: f.read_text(encoding="utf-8") for t, f in refs.items() if f.exists()}
        else:
            name = "lcb_v3_probe_solutions.json" if bank == "lcb_v3" else "lcb_probe_solutions.json"
            probes = json.loads((REPO / "ops" / "gain" / "data" / name).read_text(encoding="utf-8"))
            refs = {t: c for t, c in probes.items() if t in man["tasks"]}
        jobs = {t: (root / "templates" / man["tasks"][t]["dir"], root / "hidden" / man["tasks"][t]["dir"], c)
                for t, c in refs.items() if man["tasks"][t].get("usable")}
        if not jobs:
            print(f"{bank}: 沒有參考解可跑（私有組要先解開 reference 包）——量不到不是通過")
            rc = 1
            continue
        with cf.ThreadPoolExecutor(a.workers) as ex:
            res = dict(zip(jobs, ex.map(lambda j: run_one(a.python, *j, a.timeout_s), jobs.values())))
        bad = sorted(t for t, ok in res.items() if not ok)
        print(f"{bank}: {ver} 參考解 可見＋隱藏 全過 {len(res) - len(bad)}/{len(res)}  失敗 {bad[:10]}")
        rc |= 1 if bad else 0
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
