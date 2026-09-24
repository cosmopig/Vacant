#!/usr/bin/env python3
"""隱藏測試計分：把 solution.py 與 test_hidden.py 放進乾淨暫存目錄，逐個 check_* 跑（每個另開行程、各自逾時）。
判準與 acceptance.py 相同：check_* 正常回傳＝過。沒有 solution.py ⇒ passed=0、total=None。"""
import json, os, pathlib, shutil, subprocess, sys, tempfile
hid, sol = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
if not sol.is_file():
    print(json.dumps({"passed": 0, "total": None, "note": "沒有 solution.py"})); sys.exit(0)
LIST = r'''
import importlib.util, json, os, sys
sys.path.insert(0, os.getcwd())
spec = importlib.util.spec_from_file_location("hid", sys.argv[1]); mod = importlib.util.module_from_spec(spec)
try:
    spec.loader.exec_module(mod)
except BaseException as e:
    print(json.dumps({"import_error": "%s: %s" % (type(e).__name__, str(e)[:200])})); sys.exit(0)
print(json.dumps({"checks": [n for n, v in vars(mod).items() if n.startswith("check_") and callable(v)]}))
'''
ONE = r'''
import importlib.util, os, sys
sys.path.insert(0, os.getcwd())
spec = importlib.util.spec_from_file_location("hid", sys.argv[1]); mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod); getattr(mod, sys.argv[2])()
'''
out = {"passed": 0, "total": 0, "failures": []}
with tempfile.TemporaryDirectory() as d:
    w = pathlib.Path(d); shutil.copy2(sol, w / "solution.py"); shutil.copy2(hid, w / "test_hidden.py")
    env = dict(os.environ, MPLBACKEND="Agg")
    try:
        r = subprocess.run([sys.executable, "-c", LIST, "test_hidden.py"], cwd=w, capture_output=True,
                           text=True, timeout=120, env=env)
        info = json.loads((r.stdout or "{}").strip().splitlines()[-1])
    except Exception as e:
        info = {"import_error": f"{type(e).__name__}: {e}"}
    if "import_error" in info:
        out.update(total=None, import_error=info["import_error"]); print(json.dumps(out, ensure_ascii=False)); sys.exit(0)
    for name in info["checks"]:
        out["total"] += 1
        try:
            r = subprocess.run([sys.executable, "-c", ONE, "test_hidden.py", name], cwd=w, capture_output=True,
                               text=True, timeout=120, env=env)
            ok = r.returncode == 0
            msg = "" if ok else (r.stderr or "").strip().splitlines()[-1:][0][:160] if (r.stderr or "").strip() else f"rc={r.returncode}"
        except subprocess.TimeoutExpired:
            ok, msg = False, "逾時 120s"
        if ok:
            out["passed"] += 1
        else:
            out["failures"].append(f"{name}: {msg}")
print(json.dumps(out, ensure_ascii=False))
