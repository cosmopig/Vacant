#!/usr/bin/env python3
"""目錄級驗收 runner——R530 的量具。**標準庫，不依賴 pytest。**

這支在架構裡承重什麼（`DECISION_20260913_R530_…_PREREG.md` §五-1）：
既有的 `vacant/checks.py::run_python_check` 判的是**一個函式字串**，
R530 的交付是**一個目錄**（`solution.py` 或 `solution/` 套件、可能還有 CLI）。
兩者的驗收不可能共用同一支。而 vacant-dev 上**沒有 pip、沒有 venv、沒有 pytest**
（預註冊 §三-2 實測），所以這一支只能用標準庫寫。

## 測試檔是什麼形狀（`TASK_FORMAT.md` 是規格，這裡是執行語意）

一個測試檔 ＝ 一個 `.py`，兩種寫法擇一，**檔案層級只准有一種**：

  1. 一組零引數的 `check_*()` 函式 ⇒ **每個函式一條 case**，
     依**定義順序**執行（Python 的 module `__dict__` 保序，所以順序是確定的）。
  2. 一個 `main()` ⇒ 整個檔案算**一條** case（名字就叫 `main`）。

判準：函式**正常回傳** ＝ 過；丟任何例外 ＝ 不過。
`AssertionError` 與其他例外分開記（`kind`），因為回饋要說得出是「答錯了」
還是「爆掉了」——零資訊的「你的程式壞了」是 R460 §3.2 已經量過的壞回饋。

## 為什麼一個測試檔一個子行程

Fable 裁決「逾時 10 秒／每測試檔」。**逾時的單位就是隔離的單位**：
一個檔案裡的某條 case 進無窮迴圈，整個檔案被 `killpg` 收掉，
其餘檔案照跑。同行程跑全部的話，一條死迴圈會讓整格驗收變成一個 timeout，
而那會讓「一條壞」與「全部壞」在資料上同形。

## 隱藏驗收永遠不進工作區（V/GT 紅線，§五-3 第 1 條）

`hidden/<task_id>/` 只在**驗收的那一瞬間**被複製到 run 目錄底下的一個暫存目錄，
以 `ro_binds` 明示地掛進沙箱，跑完**立刻刪掉**。工作區在整個過程中沒有被寫入
任何一個位元組（樹雜湊在驗收前後不變，`tests/test_r530_acceptance.py` 有對這一條）。
`bwrap` 後端之下 repo 根本不在沙箱的檔案系統裡 ⇒ 這是結構性保證不是擋門。

## 誠實邊界（`vacant/suitegauge.py` 的單邊保證，逐字適用）

「參考解全過 ＋ 每個已知壞樁都被擋」是**單邊**保證：擋得住已知壞解
**不等於**涵蓋真需求。這支算出來的 `passed/total` 是「過了我們自己寫的幾條」，
不是「做對了幾成」。不准讀成「驗收套件固定點已解」。
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import shutil
import secrets

from .sandbox import DEFAULT_TEST_TIMEOUT_S, Sandbox, SandboxInfraError

SUITES = ("visible", "hidden")

#: case 的封閉結果集合。多一個就是規格變更——不准在別處臨時造字串。
CASE_KINDS = frozenset({"pass", "assert", "exception", "import", "timeout",
                        "nofile", "driver_error"})

#: 回饋與落盤的截斷長度（完整原文另外以 sha256 落盤，形狀沿用
#: `harness_arms.truncate_message` 的「頭尾都留」而不是純 tail）。
MAX_CASE_OUTPUT_CHARS = 1200
MAX_CASE_MESSAGE_CHARS = 800

#: 一條失敗 case 貼回去的那一行（`A-GATE` 的回饋骨架）。**逐字凍結。**
#: 四個欄位逐字對應 Fable 裁決的「哪個測試、輸出、期望」：
#:   {file}::{case} ＝ 哪個測試；{kind} ＋ {message} ＝ 期望與實際的差；
#:   {output} ＝ 那條 case 自己印出來的東西。
CASE_LINE = "{file}::{case} — {kind}: {message}"
CASE_OUTPUT_LINE = "    output: {output}"
NO_FAILURE_LINE = "(no failing case was recorded)"

#: driver 用來把結果帶出沙箱的前綴。每次執行換一個 nonce，
#: 免得被測程式印出一行長得像結果的東西把判準騙過去。
_NONCE_PREFIX = "R530CASE:"

#: driver 的原始碼。寫進 run 目錄的暫存驗收目錄，以唯讀綁進沙箱。
#: **它不讀工作區以外的東西，也不寫任何檔案**——它只 import 測試檔、
#: 呼叫 `check_*`、把結果印在 stdout。
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


def test_files(suite_dir: str | pathlib.Path) -> list[pathlib.Path]:
    """一個驗收目錄裡的測試檔，**排序固定**（檔名字典序）。

    只收 `test_*.py`：目錄裡允許放 helper（`_support.py`）給測試 import，
    而 helper 不是一個測試檔。認不出來的東西一律不當測試——
    「多跑了一個不是測試的東西」與「漏跑了一個測試」都會讓分數說謊。
    """
    d = pathlib.Path(suite_dir)
    if not d.is_dir():
        return []
    return sorted(p for p in d.glob("test_*.py") if p.is_file())


def _parse_cases(stdout: str, nonce: str) -> list[dict]:
    """只認**這一次執行**的 nonce 開頭的行。

    為什麼不用固定前綴：被測程式可以自己印一行 `R530CASE:{"ok":true…}`
    把判準騙過去。nonce 每次隨機 ⇒ 那條偽造路徑要先猜中 16 個十六進位字元。
    （這不是密碼學保證，是把「不小心」與「故意」分開——本 run 的威脅模型
    是前者，見 `sandbox.py` 的誠實邊界。）
    """
    out: list[dict] = []
    for line in (stdout or "").splitlines():
        if not line.startswith(nonce):
            continue
        try:
            out.append(json.loads(line[len(nonce):]))
        except ValueError:
            continue
    return out


def run_suite(sandbox: Sandbox, workspace: str | pathlib.Path,
              suite_dir: str | pathlib.Path, *, suite: str, task_id: str,
              verify_root: str | pathlib.Path,
              timeout_s: float = DEFAULT_TEST_TIMEOUT_S,
              keep_verify_dir: bool = False) -> dict:
    """跑一整組驗收，回一份可落盤的結果。

    `suite="hidden"` 時 `suite_dir` 會被**複製**到 `verify_root` 底下的一個
    隨機暫存目錄，跑完刪掉（`keep_verify_dir=True` 只給偵錯用，
    正式 run 一律是 False——留著就等於把隱藏驗收落在 run 目錄裡）。
    """
    if suite not in SUITES:
        raise ValueError(f"unknown suite {suite!r}（可用 {SUITES}）")
    ws = pathlib.Path(workspace).resolve()
    src = pathlib.Path(suite_dir)
    vroot = pathlib.Path(verify_root).resolve()
    vroot.mkdir(parents=True, exist_ok=True)
    vdir = vroot / f"_v_{suite}_{secrets.token_hex(8)}"
    files_rec: list[dict] = []
    nonce = f"{_NONCE_PREFIX}{secrets.token_hex(8)}:"
    try:
        vdir.mkdir(parents=True)
        (vdir / "driver.py").write_text(DRIVER_SRC, encoding="utf-8")
        if src.is_dir():
            for p in sorted(src.iterdir()):
                if p.is_file() and p.suffix == ".py":
                    shutil.copy2(p, vdir / p.name)
        tfs = test_files(vdir)
        if not tfs:
            return _empty_result(suite, task_id,
                                 reason=f"驗收目錄沒有 test_*.py：{src}")
        for tf in tfs:
            rel = tf.name
            cmd = (f"python3 {_q(vdir / 'driver.py')} {_q(ws)} {_q(tf)} "
                   f"{_q(nonce)}")
            try:
                res = sandbox.run(cmd, workspace=ws, timeout_s=timeout_s,
                                  ro_binds=(vdir,))
            except SandboxInfraError:
                raise
            cases = _parse_cases(res.stdout, nonce)
            if res.timed_out:
                cases.append({"case": "<file>", "ok": False, "kind": "timeout",
                              "message": (f"the checks in this file did not finish "
                                          f"within {int(timeout_s)} seconds."),
                              "where": None, "output": ""})
            elif not cases:
                cases.append({"case": "<file>", "ok": False, "kind": "driver_error",
                              "message": _driver_error_message(res),
                              "where": None,
                              "output": (res.stderr or "")[-MAX_CASE_OUTPUT_CHARS:]})
            files_rec.append({
                "file": rel,
                "rc": res.rc,
                "timed_out": res.timed_out,
                "wall_ms": res.wall_ms,
                "cases": cases,
                "passed": sum(1 for c in cases if c.get("ok")),
                "total": len(cases),
                "stderr_tail": (res.stderr or "")[-400:],
            })
    finally:
        if vdir.exists() and not keep_verify_dir:
            shutil.rmtree(vdir, ignore_errors=True)
    return _finish(suite, task_id, files_rec)


def _driver_error_message(res) -> str:
    """driver 一行結果都沒吐 ⇒ 說出來是為什麼，不要只寫「沒有結果」。"""
    tail = (res.stderr or "").strip().splitlines()
    last = tail[-1] if tail else ""
    if "No such file" in (res.stderr or "") or res.rc == 127:
        return f"the acceptance driver could not start (rc={res.rc}): {last[:300]}"
    return f"the acceptance driver produced no result (rc={res.rc}): {last[:300]}"


def _empty_result(suite: str, task_id: str, *, reason: str) -> dict:
    rec = {"suite": suite, "task_id": task_id, "files": [],
           "passed": 0, "total": 0, "all_pass": False,
           "empty_reason": reason}
    rec["result_sha256"] = result_digest(rec)
    return rec


def _finish(suite: str, task_id: str, files_rec: list[dict]) -> dict:
    passed = sum(f["passed"] for f in files_rec)
    total = sum(f["total"] for f in files_rec)
    rec = {
        "suite": suite, "task_id": task_id, "files": files_rec,
        "passed": passed, "total": total,
        # `total == 0` ⇒ **不是通過**。量不到不是通過（`suitegauge` 的同一條）。
        "all_pass": bool(total > 0 and passed == total),
        "empty_reason": None,
    }
    rec["result_sha256"] = result_digest(rec)
    return rec


def result_digest(result: dict) -> str:
    """驗收結果的雜湊——**只取判準相關的欄位**，不取時間與 rc。

    為什麼要挑欄位：這個雜湊要簽進收據鏈（`ws_verdict.verdict_sha256`），
    而收據的用途是「同一份工作區跑同一組驗收，結果不會被事後改掉」。
    `wall_ms` 每次都不同，把它算進去等於讓收據永遠對不上自己。
    """
    reduced = [
        {"file": f["file"],
         "cases": [{"case": c.get("case"), "ok": bool(c.get("ok")),
                    "kind": c.get("kind")} for c in f.get("cases", [])]}
        for f in result.get("files", [])
    ]
    payload = {"suite": result.get("suite"), "task_id": result.get("task_id"),
               "files": reduced, "passed": result.get("passed"),
               "total": result.get("total")}
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"),
                   ensure_ascii=False).encode("utf-8")).hexdigest()


def failing_cases(result: dict) -> list[dict]:
    out: list[dict] = []
    for f in result.get("files", []):
        for c in f.get("cases", []):
            if not c.get("ok"):
                out.append({**c, "file": f["file"]})
    return out


def render_failures(result: dict, *, max_cases: int = 6) -> str:
    """把失敗原文渲染成 `A-GATE` 貼回去的那一段。**逐字模板凍結。**

    只給**可見**驗收的結果（呼叫端負責，見 `openwork_arms.ARM_GATE`）。
    隱藏驗收的存在、條數、內容一律不進回饋（§二-5）。
    """
    bad = failing_cases(result)
    if not bad:
        return NO_FAILURE_LINE
    lines: list[str] = []
    for c in bad[:max_cases]:
        msg = c.get("message") or ""
        if c.get("where"):
            msg = f"{msg} [{c['where']}]"
        lines.append(CASE_LINE.format(file=c["file"], case=c.get("case"),
                                      kind=c.get("kind"), message=msg))
        out = (c.get("output") or "").strip()
        if out:
            lines.append(CASE_OUTPUT_LINE.format(
                output=out.replace("\n", "\n    ")[:MAX_CASE_OUTPUT_CHARS]))
    if len(bad) > max_cases:
        lines.append(f"…[{len(bad) - max_cases} more failing checks omitted]…")
    return "\n".join(lines)


def main() -> int:
    import argparse

    from .sandbox import make_sandbox

    ap = argparse.ArgumentParser(
        description="R530 目錄級驗收 runner（零模型呼叫）")
    ap.add_argument("--workspace", required=True)
    ap.add_argument("--suite-dir", required=True)
    ap.add_argument("--suite", default="visible", choices=list(SUITES))
    ap.add_argument("--task-id", required=True)
    ap.add_argument("--verify-root", default=None,
                    help="暫存驗收目錄的位置（預設＝工作區的同層 _verify）")
    ap.add_argument("--backend", default="auto")
    ap.add_argument("--timeout-s", type=float, default=DEFAULT_TEST_TIMEOUT_S)
    ap.add_argument("--json", default=None)
    args = ap.parse_args()

    ws = pathlib.Path(args.workspace).resolve()
    vroot = pathlib.Path(args.verify_root or (ws.parent / "_verify"))
    sb, meta = make_sandbox(args.backend, workdir=str(vroot))
    res = run_suite(sb, ws, args.suite_dir, suite=args.suite,
                    task_id=args.task_id, verify_root=vroot,
                    timeout_s=args.timeout_s)
    res["backend_meta"] = meta
    text = json.dumps(res, ensure_ascii=False, indent=2)
    print(text)
    if args.json:
        p = pathlib.Path(args.json)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text + "\n", encoding="utf-8")
    return 0 if res["all_pass"] else 1


def _q(p) -> str:
    import shlex
    return shlex.quote(str(p))


if __name__ == "__main__":
    raise SystemExit(main())
