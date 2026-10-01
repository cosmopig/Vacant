#!/usr/bin/env python3
"""程式題計分（在計分使用者的圍牆裡跑）：`scorer.py <hidden 目錄> <最後的工作區>`，stdout 一行 JSON。

判準＝題庫量具用的那一份（`vacant_network/vrun/acceptance.py` 的 `run_suite`，commit fb7f4bfb）：
一個測試檔的所有 `check_*` 在**同一個行程**裡跑（下面的 DRIVER_SRC 逐字取自 acceptance.py），輸出行用隨機 nonce 認；
整個檔一個時限（`SUITE_TIMEOUT_S`，預設 60 秒＝量具 30 秒的 2 倍：VM 上 48 格同時跑，比量具那台忙），RLIMIT_AS 2 GB。
逾時 ⇒ 那個檔多記一條失敗（同 run_suite）。`pass`＝隱藏檔（可見 ∪ 隱藏）每一條都過且至少 1 條；
可見用題目**原本**那一份（hidden/tests_visible，不是工作區裡的——agent 可能改過）；`false_done`＝可見全過但隱藏沒全過。
沒有 solution.py ⇒ 全部 0，`note` 記原因。
（2026-09-27 從「每條另開行程」改成這個：HumanEval+ 每題約 1,000 條檢查，每條開行程會拖到逾時被判成 void。）"""
import json, os, pathlib, resource, secrets, shutil, subprocess, sys, tempfile

hid, app = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
ENTRY = os.environ.get("SOLUTION_FILE", "solution.py")
SUITE_TIMEOUT_S = float(os.environ.get("SUITE_TIMEOUT_S", "60"))
MEM = 2048 * 1024 * 1024
DRIVER_SRC = r'''
import contextlib, importlib.util, io, json, os, sys, traceback

NONCE = sys.argv[3]
WS = sys.argv[1]
TESTFILE = sys.argv[2]
REAL_STDOUT = sys.stdout

def emit(rec):
    REAL_STDOUT.write(NONCE + json.dumps(rec, ensure_ascii=False) + "\n")
    REAL_STDOUT.flush()

def clip(s, n):
    s = s or ""
    return s if len(s) <= n else s[: n // 2] + "…[cut]…" + s[-(n // 2):]

def where_of(exc, testfile):
    frames = traceback.extract_tb(exc.__traceback__)
    hit = [f for f in frames if os.path.abspath(f.filename) == os.path.abspath(testfile)]
    f = hit[-1] if hit else (frames[-1] if frames else None)
    if f is None:
        return None
    return "%s:%d: %s" % (os.path.basename(f.filename), f.lineno, (f.line or "").strip())

sys.path.insert(0, WS)
spec = importlib.util.spec_from_file_location("r530_testmod", TESTFILE)
mod = importlib.util.module_from_spec(spec)
buf = io.StringIO()
try:
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        spec.loader.exec_module(mod)
except BaseException as e:
    emit({"case": "<module>", "ok": False, "kind": "import",
          "message": "%s: %s" % (type(e).__name__, e),
          "where": where_of(e, TESTFILE), "output": clip(buf.getvalue(), 1200)})
    raise SystemExit(0)

checks = [(n, v) for n, v in vars(mod).items()
          if n.startswith("check_") and callable(v)]
if not checks:
    main = getattr(mod, "main", None)
    checks = [("main", main)] if callable(main) else []
if not checks:
    emit({"case": "<module>", "ok": False, "kind": "driver_error",
          "message": "test file defines neither check_*() nor main()",
          "where": None, "output": ""})
    raise SystemExit(0)

for name, fn in checks:
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            fn()
    except AssertionError as e:
        emit({"case": name, "ok": False, "kind": "assert",
              "message": clip(str(e) or "assertion failed", 800),
              "where": where_of(e, TESTFILE), "output": clip(buf.getvalue(), 1200)})
    except BaseException as e:
        emit({"case": name, "ok": False, "kind": "exception",
              "message": clip("%s: %s" % (type(e).__name__, e), 800),
              "where": where_of(e, TESTFILE), "output": clip(buf.getvalue(), 1200)})
    else:
        emit({"case": name, "ok": True, "kind": "pass", "message": "",
              "where": None, "output": clip(buf.getvalue(), 1200)})
'''


def _lim():
    resource.setrlimit(resource.RLIMIT_AS, (MEM, MEM))


def run_file(test_file: pathlib.Path, sol: pathlib.Path) -> dict:
    with tempfile.TemporaryDirectory() as d:
        ws, vd = pathlib.Path(d) / "ws", pathlib.Path(d) / "v"
        ws.mkdir(); vd.mkdir()
        shutil.copy2(sol, ws / ENTRY)
        shutil.copy2(test_file, vd / test_file.name)
        (vd / "driver.py").write_text(DRIVER_SRC)
        nonce = "R530CASE" + secrets.token_hex(8) + ":"
        env = dict(os.environ, MPLBACKEND="Agg", PYTHONDONTWRITEBYTECODE="1")
        timed_out = False
        try:
            r = subprocess.run([sys.executable, str(vd / "driver.py"), str(ws), str(vd / test_file.name), nonce], cwd=ws,
                               capture_output=True, text=True, timeout=SUITE_TIMEOUT_S, env=env, preexec_fn=_lim)
            out = r.stdout
        except subprocess.TimeoutExpired as e:
            timed_out, out = True, (e.stdout.decode(errors="replace") if isinstance(e.stdout, bytes) else (e.stdout or ""))
        cases = []
        for line in out.splitlines():
            if line.startswith(nonce):
                try:
                    cases.append(json.loads(line[len(nonce):]))
                except ValueError:
                    pass
        if timed_out:
            cases.append({"case": "<file>", "ok": False, "kind": "timeout"})
        elif not cases:
            cases.append({"case": "<file>", "ok": False, "kind": "driver_error"})
        fails = [f"{c.get('case')}: {c.get('kind')} {str(c.get('message', ''))[:120]}" for c in cases if not c.get("ok")]
        return {"passed": sum(1 for c in cases if c.get("ok")), "total": len(cases), "timed_out": timed_out, "failures": fails[:20],
                "n_failures": len(fails)}


def all_pass(r: dict | None) -> bool:
    return bool(r) and r["total"] > 0 and r["passed"] == r["total"]


sol = app / ENTRY
if not sol.is_file():
    print(json.dumps({"pass": False, "visible_pass": False, "false_done": False, "note": f"no {ENTRY}",
                      "hidden": None, "visible": None}))
    sys.exit(0)
vis = sorted((hid / "tests_visible").glob("test_*.py"))
visible = run_file(vis[0], sol) if len(vis) == 1 else None
hidden = run_file(hid / "test_hidden.py", sol)
res = {"pass": all_pass(hidden), "visible_pass": all_pass(visible), "hidden": hidden, "visible": visible,
       "suite_timeout_s": SUITE_TIMEOUT_S, "n_visible_files": len(vis)}
res["false_done"] = res["visible_pass"] and not res["pass"]
print(json.dumps(res, ensure_ascii=False))
