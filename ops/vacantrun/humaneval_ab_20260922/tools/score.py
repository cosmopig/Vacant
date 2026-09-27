#!/usr/bin/env python3
"""隱藏尺：拿官方 HumanEval 的完整 `check(candidate)` 去驗一個 `solution.py`。

一題一個布林（過／不過）＝ HumanEval 的標準計分方式（pass@1，n=1 樣本），
所以這裡算出來的比率跟外界公布的 pass@1 是同一把尺。

⚠ 只在 run 結束之後跑，**失敗訊息不回饋給模型**，官方測資不進工作區。
⚠ 在子行程裡跑並設逾時：不終止解不可以把整批拖死。
"""
from __future__ import annotations

import json
import pathlib
import shutil
import subprocess
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent

DRIVER = r'''
import json, os, sys, traceback
sys.path.insert(0, os.getcwd())
out = {"ok": False, "why": None}
try:
    import solution
except Exception as e:
    out["why"] = "import solution: %s: %s" % (type(e).__name__, str(e)[:200])
    print(json.dumps(out)); sys.exit(0)
meta = json.load(open("_meta.json"))
entry = meta["entry_point"]
cand = getattr(solution, entry, None)
if not callable(cand):
    out["why"] = "solution.%s 不存在或不可呼叫" % entry
    print(json.dumps(out)); sys.exit(0)
ns = {}
try:
    exec(open("_official_test.py").read(), ns)
except Exception as e:
    out["why"] = "官方測資載入失敗: %s: %s" % (type(e).__name__, str(e)[:200])
    print(json.dumps(out)); sys.exit(0)
check = ns.get("check")
if not callable(check):
    out["why"] = "官方測資沒有 check()"
    print(json.dumps(out)); sys.exit(0)
try:
    check(cand)
except Exception as e:
    out["why"] = "%s: %s" % (type(e).__name__, str(e)[:200])
    print(json.dumps(out)); sys.exit(0)
out["ok"] = True
print(json.dumps(out))
'''


def score(task_dir_name: str, solution_path: pathlib.Path,
          timeout_s: float = 60.0) -> dict:
    h = HERE / "hidden" / task_dir_name
    if not h.is_dir():
        return {"ok": False, "why": f"沒有隱藏尺：{h}"}
    if not solution_path.is_file():
        return {"ok": False, "why": "沒有 solution.py（agent 沒有交付）"}
    with tempfile.TemporaryDirectory() as d:
        w = pathlib.Path(d)
        shutil.copy2(solution_path, w / "solution.py")
        shutil.copy2(h / "official_test.py", w / "_official_test.py")
        shutil.copy2(h / "meta.json", w / "_meta.json")
        (w / "_driver.py").write_text(DRIVER, encoding="utf-8")
        try:
            r = subprocess.run([sys.executable, "_driver.py"], cwd=w,
                               capture_output=True, text=True, timeout=timeout_s)
        except subprocess.TimeoutExpired:
            return {"ok": False, "why": f"逾時 {timeout_s}s（不終止解）"}
    try:
        return json.loads((r.stdout or "").strip().splitlines()[-1])
    except Exception:
        return {"ok": False, "why": f"driver 沒吐 JSON: rc={r.returncode} "
                                    f"{(r.stderr or '')[:200]}"}


if __name__ == "__main__":
    print(json.dumps(score(sys.argv[1], pathlib.Path(sys.argv[2])),
                     ensure_ascii=False))
