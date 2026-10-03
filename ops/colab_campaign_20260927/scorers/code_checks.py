#!/usr/bin/env python3
"""程式題計分（在計分使用者的圍牆裡跑）：`scorer.py <hidden 目錄> <最後的工作區>`，stdout 一行 JSON。

判準同 ops/vacantrun/bcb_hard_ab_20260924 的 bcb_score.py（＝閘門 acceptance.py 的判準）：每個 `check_*` 另開行程、
各自逾時 120 秒、RLIMIT_AS 2 GB，正常回傳＝過。可見測試用**題目原本那一份**（hidden/tests_visible，不是工作區裡的——
agent 可能改過工作區的測試），隱藏用 hidden/test_hidden.py（可見 ∪ 隱藏）。
`pass`＝隱藏全過（且至少 1 條）；`visible_pass`＝原本的可見全過；`false_done`＝可見全過但隱藏沒全過。
沒有 solution.py ⇒ 全部 0，`note` 記原因。"""
import json, os, pathlib, resource, shutil, subprocess, sys, tempfile

hid, app = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
ENTRY = os.environ.get("SOLUTION_FILE", "solution.py")
MEM = 2048 * 1024 * 1024
LIST = r'''
import importlib.util, json, os, sys
sys.path.insert(0, os.getcwd())
spec = importlib.util.spec_from_file_location("t", sys.argv[1]); mod = importlib.util.module_from_spec(spec)
try:
    spec.loader.exec_module(mod)
except BaseException as e:
    print(json.dumps({"import_error": "%s: %s" % (type(e).__name__, str(e)[:200])})); sys.exit(0)
print(json.dumps({"checks": [n for n, v in vars(mod).items() if n.startswith("check_") and callable(v)]}))
'''
ONE = r'''
import importlib.util, os, sys
sys.path.insert(0, os.getcwd())
spec = importlib.util.spec_from_file_location("t", sys.argv[1]); mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod); getattr(mod, sys.argv[2])()
'''


def _lim():
    resource.setrlimit(resource.RLIMIT_AS, (MEM, MEM))


def run_suite(test_file: pathlib.Path, sol: pathlib.Path) -> dict:
    out = {"passed": 0, "total": 0, "failures": []}
    with tempfile.TemporaryDirectory() as d:
        w = pathlib.Path(d)
        shutil.copy2(sol, w / ENTRY)
        shutil.copy2(test_file, w / "_suite.py")
        env = dict(os.environ, MPLBACKEND="Agg", PYTHONDONTWRITEBYTECODE="1")
        try:
            r = subprocess.run([sys.executable, "-c", LIST, "_suite.py"], cwd=w, capture_output=True, text=True,
                               timeout=120, env=env, preexec_fn=_lim)
            info = json.loads((r.stdout or "{}").strip().splitlines()[-1])
        except Exception as e:  # noqa: BLE001
            info = {"import_error": f"{type(e).__name__}: {e}"}
        if "import_error" in info:
            out.update(total=None, import_error=info["import_error"])
            return out
        for name in info["checks"]:
            out["total"] += 1
            try:
                r = subprocess.run([sys.executable, "-c", ONE, "_suite.py", name], cwd=w, capture_output=True,
                                   text=True, timeout=120, env=env, preexec_fn=_lim)
                ok = r.returncode == 0
                err = (r.stderr or "").strip().splitlines()
                msg = "" if ok else (err[-1][:160] if err else f"rc={r.returncode}")
            except subprocess.TimeoutExpired:
                ok, msg = False, "timeout 120s"
            if ok:
                out["passed"] += 1
            else:
                out["failures"].append(f"{name}: {msg}")
    return out


def all_pass(r: dict) -> bool:
    return bool(r.get("total")) and r["passed"] == r["total"]


sol = app / ENTRY
if not sol.is_file():
    print(json.dumps({"pass": False, "visible_pass": False, "false_done": False, "note": f"no {ENTRY}",
                      "hidden": None, "visible": None}))
    sys.exit(0)
vis_files = sorted((hid / "tests_visible").glob("test_*.py"))
visible = run_suite(vis_files[0], sol) if vis_files else {"passed": 0, "total": None, "note": "no visible suite"}
hidden = run_suite(hid / "test_hidden.py", sol)
res = {"pass": all_pass(hidden), "visible_pass": all_pass(visible), "hidden": hidden, "visible": visible}
res["false_done"] = res["visible_pass"] and not res["pass"]
print(json.dumps(res, ensure_ascii=False))
