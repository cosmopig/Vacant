#!/usr/bin/env python3
"""隱藏尺：拿 LiveCodeBench v6 的 **private ＋ public 全部測資**驗一個 `solution.py`。

一題一個布林（全過才算過）＝ LCB 的標準計分方式，所以跟外界公布的 pass@1 是同一把尺。

⚠ **逾時算不過**：每條 case 10 秒、整題 180 秒。那是競賽語意——正確但太慢就是沒解出來，
  不是量具壞掉。隱藏測資含很大的輸入，naive 演算法會死在這裡，**那正是這批要量的東西**。
⚠ 只在 run 結束之後跑，失敗訊息不回饋給模型，隱藏測資不進工作區。
"""
from __future__ import annotations

import json
import pathlib
import shutil
import subprocess
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
PER_CASE_S = 10.0
TOTAL_S = 180.0

DRIVER = r'''
import json, os, sys, signal
sys.path.insert(0, os.getcwd())
sys.setrecursionlimit(100000)
out = {"ok": False, "passed": 0, "total": 0, "why": None}
spec = json.load(open("_cases.json"))
entry = spec["entry_point"]
try:
    import solution
except Exception as e:
    out["why"] = "import solution: %s: %s" % (type(e).__name__, str(e)[:160])
    print(json.dumps(out)); sys.exit(0)
fn = getattr(solution, entry, None)
if not callable(fn):
    out["why"] = "solution.%s 不存在或不可呼叫" % entry
    print(json.dumps(out)); sys.exit(0)

def _aeq(a, b):
    try:
        if a == b: return True
    except (TypeError, ValueError): pass
    if isinstance(a, bool) != isinstance(b, bool): return False
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(a - b) <= 1e-6
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        return len(a) == len(b) and all(_aeq(x, y) for x, y in zip(a, b))
    return a == b

class TLE(Exception): pass
def _alarm(sig, frm): raise TLE()
signal.signal(signal.SIGALRM, _alarm)

cases = spec["cases"]
out["total"] = len(cases)
for i, c in enumerate(cases):
    signal.setitimer(signal.ITIMER_REAL, PER_CASE)
    try:
        got = fn(*c["args"])
        signal.setitimer(signal.ITIMER_REAL, 0)
    except TLE:
        out["why"] = "case %d 逾時 %.0fs" % (i, PER_CASE); break
    except Exception as e:
        signal.setitimer(signal.ITIMER_REAL, 0)
        out["why"] = "case %d %s: %s" % (i, type(e).__name__, str(e)[:120]); break
    if not _aeq(got, c["want"]):
        out["why"] = "case %d 答錯" % i; break
    out["passed"] += 1
out["ok"] = out["passed"] == out["total"] and out["total"] > 0
print(json.dumps(out))
'''


def score(task_id: str, solution_path: pathlib.Path) -> dict:
    h = HERE / "hidden" / task_id / "cases.json"
    if not h.is_file():
        return {"ok": False, "why": f"沒有隱藏尺：{h}"}
    if not solution_path.is_file():
        return {"ok": False, "why": "沒有 solution.py（agent 沒有交付）"}
    with tempfile.TemporaryDirectory() as d:
        w = pathlib.Path(d)
        shutil.copy2(solution_path, w / "solution.py")
        shutil.copy2(h, w / "_cases.json")
        (w / "_driver.py").write_text(
            f"PER_CASE = {PER_CASE_S}\n" + DRIVER, encoding="utf-8")
        try:
            r = subprocess.run([sys.executable, "_driver.py"], cwd=w,
                               capture_output=True, text=True, timeout=TOTAL_S)
        except subprocess.TimeoutExpired:
            return {"ok": False, "why": f"整題逾時 {TOTAL_S}s"}
    try:
        return json.loads((r.stdout or "").strip().splitlines()[-1])
    except Exception:
        return {"ok": False, "why": f"driver 沒吐 JSON: rc={r.returncode} "
                                    f"{(r.stderr or '')[:160]}"}


if __name__ == "__main__":
    print(json.dumps(score(sys.argv[1], pathlib.Path(sys.argv[2])),
                     ensure_ascii=False))
