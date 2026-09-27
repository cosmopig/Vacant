#!/usr/bin/env python3
"""把一格的**凍結工作區**拿去跑隱藏尺（GT），回 passed/total。

⚠ 紅線（R534）：`ops/gain/r534/hidden/` 那棵樹**永遠不進工作區**，失敗訊息也
  **不回饋給模型**。本檔在 run 結束之後才跑，只為了計分，跑完不留任何東西在工作區。
⚠ 判準與 `run_tests.sh` 同一套：每個 `check_*()` 一條 case，正常回傳＝過。
⚠ 這把尺是**單邊**的（`suitegauge` 的誠實邊界）：過了只代表「題庫寫下來的那幾條過了」。
"""
import importlib.util
import json
import pathlib
import shutil
import subprocess
import sys
import tempfile

REPO = pathlib.Path("/home/user/Vacant")
HIDDEN = REPO / "ops/gain/r534/hidden"

DRIVER = r'''
import importlib.util, os, sys, json, traceback
sys.path.insert(0, os.getcwd())
spec = importlib.util.spec_from_file_location("hid", sys.argv[1])
mod = importlib.util.module_from_spec(spec)
out = {"passed": 0, "total": 0, "failures": []}
try:
    spec.loader.exec_module(mod)
except Exception as e:
    out["import_error"] = f"{type(e).__name__}: {e}"
    print(json.dumps(out)); sys.exit(0)
checks = [(n, v) for n, v in vars(mod).items() if n.startswith("check_") and callable(v)]
for name, fn in checks:
    out["total"] += 1
    try:
        fn()
    except Exception as e:
        out["failures"].append(f"{name}: {type(e).__name__}: {str(e)[:120]}")
    else:
        out["passed"] += 1
print(json.dumps(out))
'''


def score(task_id: str, frozen_dir: pathlib.Path, timeout_s: float = 120.0) -> dict:
    hid = HIDDEN / task_id / "test_hidden.py"
    if not hid.is_file():
        return {"error": f"沒有隱藏尺：{hid}"}
    sol = frozen_dir / "solution.py"
    if not sol.is_file():
        return {"passed": 0, "total": None, "note": "凍結工作區裡沒有 solution.py"}
    with tempfile.TemporaryDirectory() as d:
        w = pathlib.Path(d)
        shutil.copy2(sol, w / "solution.py")
        (w / "_driver.py").write_text(DRIVER, encoding="utf-8")
        try:
            r = subprocess.run([sys.executable, "_driver.py", str(hid)], cwd=w,
                               capture_output=True, text=True, timeout=timeout_s)
        except subprocess.TimeoutExpired:
            return {"passed": None, "total": None, "note": f"逾時 {timeout_s}s（不終止解）"}
    try:
        return json.loads((r.stdout or "").strip().splitlines()[-1])
    except Exception:
        return {"error": f"driver 沒吐 JSON：rc={r.returncode} {(r.stderr or '')[:200]}"}


if __name__ == "__main__":
    print(json.dumps(score(sys.argv[1], pathlib.Path(sys.argv[2])),
                     ensure_ascii=False, indent=2))
