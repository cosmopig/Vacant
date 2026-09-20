#!/usr/bin/env python3
"""把 `pi_tty_cell.sh` 的格子收成一張表。**衍生物，零模型呼叫。**

三類欄位分開放，不准混：

  A. **閘門的判決**   `accepted`／`refused`／`stop_reason`（launcher 落的原文）
  B. **中介的證據**   `requests_seen`、wire index 逐條 path、canary
  C. **事後計分**     `postaudit_hidden_*`（隱藏測資，衍生物）
                      🔴 不准填進 `accepted`。

## 模式證據（這一批的核心宣稱靠它）

`mode_evidence` 不看我們下了什麼旗標，看**轉錄裡有沒有只有互動模式才會出現
的東西**：

  · `To resume this session:`  —— `interactive-mode.js::shutdown()` 才印
  · TUI 狀態列（`(vacantproxy)`／`Working` spinner）
  · alt-screen／Kitty keyboard protocol 的 escape sequence

`PTP` 臂（同一張 pty、但 wrapper 仍是 `pi -p`）**必須一個都沒有**——
那是這張表自己帶的負控制。有的話整批的模式宣稱作廢。

## 隱藏測資的三態

`postaudit_hidden_status` ∈ `all_pass` / `fail` / **`timeout`** / `no_solution`
/ `error`。**`timeout` 不是 `fail`**：2026-09-20 已知 `lcb_3649` 有交付出來的
解在隱藏測資上 600 秒不終止，而同一個隱藏檔對退化樁秒回 ⇒ 那是**解本身不終止**。
把它併進 `fail` 會讓「跑不完」這個現象從資料裡消失。
"""
from __future__ import annotations

import argparse
import collections
import json
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

#: 只有互動模式才會出現的字串（`interactive-mode.js`）。
INTERACTIVE_MARKERS = ("To resume this session:",)
#: TUI 才會畫的東西。
TUI_MARKERS = ("(vacantproxy)", "Working", "ctrl+c/ctrl+d")

_DRIVER = r'''
import importlib.util, os, sys, traceback
sys.path.insert(0, os.getcwd())
spec = importlib.util.spec_from_file_location("hid", sys.argv[1])
mod = importlib.util.module_from_spec(spec)
try:
    spec.loader.exec_module(mod)
except Exception:
    print("IMPORT_FAIL"); traceback.print_exc(); sys.exit(2)
checks = sorted((n, v) for n, v in vars(mod).items()
                if n.startswith("check_") and callable(v))
p = f = 0
for n, fn in checks:
    try:
        fn(); p += 1
    except Exception:
        f += 1
print("PASSED=%d FAILED=%d TOTAL=%d" % (p, f, len(checks)))
sys.exit(0 if f == 0 else 1)
'''


def score_hidden(hidden_py: pathlib.Path, solution: pathlib.Path | None,
                 timeout_s: float) -> dict:
    """在一個**工作區外面**的 temp dir 裡跑隱藏測資。V/GT 分離靠這個。"""
    if solution is None or not solution.exists():
        return {"status": "no_solution", "passed": None, "total": None,
                "wall_s": None}
    with tempfile.TemporaryDirectory(prefix="ttyscore_") as td:
        d = pathlib.Path(td)
        shutil.copy(solution, d / "solution.py")
        shutil.copy(hidden_py, d / "_hidden.py")
        (d / "_driver.py").write_text(_DRIVER, encoding="utf-8")
        try:
            r = subprocess.run([sys.executable, str(d / "_driver.py"),
                                str(d / "_hidden.py")],
                               cwd=str(d), capture_output=True, text=True,
                               timeout=timeout_s, check=False)
        except subprocess.TimeoutExpired:
            # ⚠ **`timeout` 不是 `fail`**：交出來的解在這組輸入上不終止。
            return {"status": "timeout", "passed": None, "total": None,
                    "wall_s": timeout_s}
        m = re.search(r"PASSED=(\d+) FAILED=(\d+) TOTAL=(\d+)", r.stdout)
        if not m:
            return {"status": "error", "passed": None, "total": None,
                    "stderr_tail": r.stderr[-400:]}
        p, f, t = (int(x) for x in m.groups())
        return {"status": "all_pass" if f == 0 else "fail",
                "passed": p, "total": t}


def collect_cell(root: pathlib.Path, name: str, hidden_root: pathlib.Path,
                 hidden_timeout: float) -> dict:
    task, arm, rep = name.rsplit("_", 2)
    rd = root / "cells" / name
    ws = root / f"ws_{name}"
    out: dict = {"name": name, "task": task, "arm": arm, "rep": rep}

    # ── A. 閘門 ＋ B. 中介（launcher 落的原文）──────────────────────
    f = rd / "run_RUN-ON.json"
    if f.exists():
        d = json.loads(f.read_text(encoding="utf-8"))
        for k in ("accepted", "refused", "stop_reason", "requests_seen",
                  "wire_errors", "agent_rc", "agent_timed_out",
                  "agent_wall_s", "run_wall_s", "visible_passed",
                  "visible_total", "wire_quiesced", "orphans_killed"):
            out[k] = d.get(k)
        att = d.get("attestation") or {}
        out["tier"] = att.get("tier")
        fh = att.get("framework_hook") or {}
        out["canary_fired"] = fh.get("canary_fired")
        out["hook_events_n"] = fh.get("events_n")
    else:
        out["run_json_missing"] = True

    idx = rd / "wire_RUN-ON" / "index.jsonl"
    if idx.exists():
        c: collections.Counter = collections.Counter()
        canary = 0
        for line in idx.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            r = json.loads(line)
            path = r.get("path") or ""
            if "vacant_canary=" in path:
                canary += 1
            c[f"{r.get('method')} {path.split('?')[0]} -> {r.get('status')}"] += 1
        out["wire_paths"] = dict(c)
        out["wire_canary"] = canary
        seen = out.get("requests_seen")
        out["wire_model_calls"] = (seen - canary) if isinstance(seen, int) else None
    else:
        out["wire_paths"] = None
        out["wire_canary"] = None
        out["wire_model_calls"] = None

    # ── 模式證據 ────────────────────────────────────────────────────
    pty = root / "pty" / f"{name}.pty.plain.txt"
    if pty.exists():
        txt = pty.read_text(encoding="utf-8", errors="replace")
        out["mode_evidence"] = {
            "interactive_only": [m for m in INTERACTIVE_MARKERS if m in txt],
            "tui": [m for m in TUI_MARKERS if m in txt],
            "bytes": len(txt),
        }
        out["pi_mode_inferred"] = ("interactive"
                                   if any(m in txt for m in INTERACTIVE_MARKERS)
                                   else "print_or_unknown")
    else:
        # `PRT` 沒有 pty ⇒ **沒量到就是沒量到**，不寫 False
        out["mode_evidence"] = None
        out["pi_mode_inferred"] = None

    drv = root / "pty" / f"{name}.drive.json"
    if drv.exists():
        d = json.loads(drv.read_text(encoding="utf-8"))
        out["drive"] = {k: d.get(k) for k in
                        ("done_signal", "ended_by", "exit_code", "exit_signal",
                         "wall_s", "turns_typed", "stops_seen", "child_is_tty")}
    else:
        out["drive"] = None

    hl = root / "hooks" / f"{name}.jsonl"
    if hl.exists():
        ec: collections.Counter = collections.Counter()
        tools: collections.Counter = collections.Counter()
        for line in hl.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                r = json.loads(line)
            except ValueError:
                continue
            ec[r.get("event")] += 1
            if r.get("tool"):
                tools[r["tool"]] += 1
        out["hook_events"] = dict(ec)
        out["hook_tools"] = dict(tools)
        out["agent_end_n"] = ec.get("stop", 0)
    else:
        out["hook_events"] = None
        out["agent_end_n"] = None

    # ── C. 事後計分（衍生物）────────────────────────────────────────
    sol = ws / "solution.py"
    out["solution_bytes"] = sol.stat().st_size if sol.exists() else None
    hid = hidden_root / task / "test_hidden.py"
    if hid.exists():
        s = score_hidden(hid, sol if sol.exists() else None, hidden_timeout)
        out["postaudit_hidden_status"] = s["status"]
        out["postaudit_hidden_passed"] = s.get("passed")
        out["postaudit_hidden_total"] = s.get("total")
    else:
        out["postaudit_hidden_status"] = None
    return out


def negative_control(hidden_root: pathlib.Path, tasks: list[str],
                     timeout_s: float) -> dict:
    """**沒有負控制的綠燈不算數**：每一題的隱藏尺都要擋得住退化樁。

    退化樁＝整支 `solution.py` 只有 `def <entry>(*a, **k): return None`
    （同 abpi §三-E 那一把）。任何一題沒被擋，這張表的 `postaudit_hidden_*`
    整欄不可引用。
    """
    out: dict = {"stub": "def <entry>(*a, **k): return None", "per_task": {},
                 "blocks_all": None}
    ok = True
    with tempfile.TemporaryDirectory(prefix="ttyneg_") as td:
        for t in tasks:
            hid = hidden_root / t / "test_hidden.py"
            if not hid.exists():
                out["per_task"][t] = "no_hidden_file"
                ok = False
                continue
            m = re.search(r"solution\.([A-Za-z_]\w*)\(",
                          hid.read_text(encoding="utf-8"))
            if not m:
                out["per_task"][t] = "entry_point_not_found"
                ok = False
                continue
            stub = pathlib.Path(td) / f"{t}_stub.py"
            stub.write_text(f"def {m.group(1)}(*a, **k):\n    return None\n",
                            encoding="utf-8")
            r = score_hidden(hid, stub, timeout_s)
            out["per_task"][t] = {"entry": m.group(1), **r}
            if r["status"] != "fail":       # 擋住＝fail（不是 all_pass）
                ok = False
    out["blocks_all"] = ok
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default="/var/tmp/vacant_tty_20260920")
    ap.add_argument("--hidden-timeout", type=float, default=60.0)
    ap.add_argument("--out", default=None)
    ap.add_argument("--negative-control", default=None,
                    help="逗號分隔的題號；只跑退化樁負控制，不收表")
    a = ap.parse_args(argv)
    if a.negative_control:
        hr = pathlib.Path(a.root) / "repo" / "ops" / "gain" / "r534" / "hidden"
        nc = negative_control(hr, a.negative_control.split(","),
                              a.hidden_timeout)
        print(json.dumps(nc, ensure_ascii=False, indent=2))
        return 0 if nc["blocks_all"] else 1
    root = pathlib.Path(a.root)
    hidden_root = root / "repo" / "ops" / "gain" / "r534" / "hidden"
    rows = [collect_cell(root, p.name, hidden_root, a.hidden_timeout)
            for p in sorted((root / "cells").iterdir()) if p.is_dir()]
    blob = json.dumps({"root": str(root), "hidden_timeout_s": a.hidden_timeout,
                       "n": len(rows), "rows": rows},
                      ensure_ascii=False, indent=2)
    if a.out:
        pathlib.Path(a.out).write_text(blob, encoding="utf-8")
    print(blob)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
