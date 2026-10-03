#!/usr/bin/env python3
"""目錄級驗收 runner——R530 的量具。**標準庫，不依賴 pytest。**

這支在架構裡承重什麼（`DECISION_20260913_R530_…_PREREG.md` §五-1）：
既有的 `vacant_network/checks.py::run_python_check` 判的是**一個函式字串**，
R530 的交付是**一個目錄**（`solution.py` 或 `solution/` 套件、可能還有 CLI）。
兩者的驗收不可能共用同一支。而 vacant-dev 上**沒有 pip、沒有 venv、沒有 pytest**
（預註冊 §三-2 實測），所以這一支只能用標準庫寫。

## 測試檔是什麼形狀（`TASK_FORMAT.md` 是規格，這裡是執行語意）

一個測試檔 ＝ 一個 `.py`，兩種寫法擇一，**檔案層級只准有一種**：

  1. 一組零引數的 `check_*()` 函式 ⇒ **每個函式一條 case**，
     依**定義順序**執行（Python 的 module `__dict__` 保序，所以順序是確定的）。
  2. 一個 `main()` ⇒ 整個檔案算**一條** case（名字就叫 `main`）。

判準：函式**回傳 `None`（或 `True`）** ＝ 過；丟任何例外 ＝ 不過。
`AssertionError` 與其他例外分開記（`kind`），因為回饋要說得出是「答錯了」
還是「爆掉了」——零資訊的「你的程式壞了」是 R460 §3.2 已經量過的壞回饋。

⚠ **2026-09-24 改：回傳值不再一律當「過」**（外部質疑報告 §03 ＋附錄 B 第五列）。
`return False` 在任何人讀起來都是「沒過」，舊版卻記成 `pass`；`async def check_*`
回傳一個沒被執行的 coroutine，舊版也記成 `pass`。現在：`None`／`True` ＝過、
`False` ＝不過（`kind="assert"`）、其他任何值（含 coroutine）＝不過（`kind="protocol"`）。
全 repo 289 個驗收檔、1803 條 check 掃過（AST，排除巢狀函式）：只有一個凍結的
候選檔 `return True`，**沒有任何一條會因此翻面**。

## 完整性：分母由可信的父行程決定，不由回報決定（2026-09-24，報告 §03 P0）

舊版的 `total` 是「收到幾筆結果」而不是「原本該跑幾條」⇒ 第一條過、第二條還沒跑
行程就死了（退出碼 7 或甚至 0），彙總只看到一筆 PASS，判 `all_pass=True`。
報告附錄 B 的 T1 重現了這件事；`tests/test_acceptance_completeness.py` 把那五列
搬進 repo 並走真的 `run_suite`。

修法是**對帳**，不是只加一個 `rc != 0`（退出碼 0 的提早結束一樣會漏）：

1. **宣告清單**：父行程在跑任何候選碼之前，用 `ast` 讀測試檔頂層的
   `def check_*`（或 `def main`），得到**預期的 case id 與順序**
   （`declared_cases()`）。driver 只跑這份清單上的名字。
2. **結束標記**：driver 跑完清單才印一行 `{"end": true}`。
3. **對帳**（`_reconcile()`）：每個宣告的 id 恰好一筆結果；缺的補一筆
   `kind="incomplete"`、重複或清單外的記 `kind="protocol"`；
   沒有結束標記或 `rc != 0` ⇒ 檔案層級再加一筆 `incomplete`。
   `all_pass` 另外要求**每個檔案都 `complete`**——雙重保險，不靠計數巧合。

⚠ **這一層防的是「意外」，不是「惡意候選碼」**（兩種安全層級不准混成一個修補）：
nonce 經由 argv 傳給 driver，而候選碼跟 driver 在**同一個直譯器**裡，
讀得到 `sys.argv`、也能自己印一行偽造的結果再 `os._exit(0)`。
對帳能抓到「偽造一行 PASS 之後真的結果又來了」（重複 ⇒ `protocol`），
抓不到「偽造全部結果＋結束標記」。對惡意候選碼要把**執行候選的行程**與
**決定評分的行程**分開（判準不在候選碼能碰到的地方），那是另一層，
見 `vacant_network/suitespec.py`（資料化規約）與 `sandbox.py` 的威脅模型。

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

## 誠實邊界（`vacant_network/suitegauge.py` 的單邊保證，逐字適用）

「參考解全過 ＋ 每個已知壞樁都被擋」是**單邊**保證：擋得住已知壞解
**不等於**涵蓋真需求。這支算出來的 `passed/total` 是「過了我們自己寫的幾條」，
不是「做對了幾成」。不准讀成「驗收套件固定點已解」。
"""
from __future__ import annotations

import ast
import hashlib
import json
import pathlib
import shutil
import secrets

from .sandbox import DEFAULT_TEST_TIMEOUT_S, Sandbox, SandboxInfraError

SUITES = ("visible", "hidden")

#: case 的封閉結果集合。多一個就是規格變更——不准在別處臨時造字串。
#: 2026-09-24 加兩個（報告 §03）：
#:   `incomplete` ＝ 宣告了但沒回報（行程提早結束／沒有結束標記／rc≠0）；
#:   `protocol`   ＝ 回報了不該有的東西（重複 id、清單外 id、非 None/True/False 的回傳值）。
CASE_KINDS = frozenset({"pass", "assert", "exception", "import", "timeout",
                        "nofile", "driver_error", "incomplete", "protocol"})

#: 檔案層級（不屬於任何宣告 case）的紀錄用的 id。
FILE_LEVEL_IDS = frozenset({"<module>", "<file>"})

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
import contextlib, importlib.util, inspect, io, json, os, sys, traceback

NONCE = sys.argv[3]
WS = sys.argv[1]
TESTFILE = sys.argv[2]
# 第四個引數＝父行程用 AST 算好的宣告清單（JSON 檔）。沒給 ⇒ 舊行為（相容）。
DECLARED = None
if len(sys.argv) > 4:
    with open(sys.argv[4], encoding="utf-8") as _f:
        DECLARED = json.load(_f)
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
    emit({"end": True, "ran": 0})
    raise SystemExit(0)

found = [(n, v) for n, v in vars(mod).items()
         if n.startswith("check_") and callable(v)]
if DECLARED is None:
    checks = found
    if not checks:
        main = getattr(mod, "main", None)
        checks = [("main", main)] if callable(main) else []
else:
    checks = [(n, vars(mod).get(n)) for n in DECLARED]
    for n, _v in found:
        if n not in DECLARED:
            emit({"case": n, "ok": False, "kind": "protocol",
                  "message": ("%s is callable in the test module but is not a top-level "
                              "'def check_*' in this file (imported or generated); it was "
                              "not run. Declare every check with def." % n),
                  "where": None, "output": ""})
if not checks:
    emit({"case": "<module>", "ok": False, "kind": "driver_error",
          "message": "test file defines neither check_*() nor main()",
          "where": None, "output": ""})
    emit({"end": True, "ran": 0})
    raise SystemExit(0)

for name, fn in checks:
    buf = io.StringIO()
    if not callable(fn):
        emit({"case": name, "ok": False, "kind": "driver_error",
              "message": "declared check %s is not callable after import" % name,
              "where": None, "output": ""})
        continue
    try:
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            ret = fn()
    except AssertionError as e:
        emit({"case": name, "ok": False, "kind": "assert",
              "message": clip(str(e) or "assertion failed", 800),
              "where": where_of(e, TESTFILE), "output": clip(buf.getvalue(), 1200)})
    except BaseException as e:
        emit({"case": name, "ok": False, "kind": "exception",
              "message": clip("%s: %s" % (type(e).__name__, e), 800),
              "where": where_of(e, TESTFILE), "output": clip(buf.getvalue(), 1200)})
    else:
        if ret is None or ret is True:
            emit({"case": name, "ok": True, "kind": "pass", "message": "",
                  "where": None, "output": clip(buf.getvalue(), 1200)})
        elif ret is False:
            emit({"case": name, "ok": False, "kind": "assert",
                  "message": "check returned False (a check fails by raising; "
                             "returning False is treated as a failure)",
                  "where": None, "output": clip(buf.getvalue(), 1200)})
        else:
            if inspect.iscoroutine(ret):
                ret.close()
            emit({"case": name, "ok": False, "kind": "protocol",
                  "message": ("check returned %s; a check passes by returning None "
                              "(or True) and fails by raising" % type(ret).__name__),
                  "where": None, "output": clip(buf.getvalue(), 1200)})

emit({"end": True, "ran": len(checks)})
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


def declared_cases(test_file: str | pathlib.Path) -> list[str]:
    """父行程在跑任何候選碼**之前**決定「這個檔案該有幾條 case」。

    只讀語法樹，不 import、不執行：頂層的 `def check_*`（依定義順序）；
    一個都沒有才看頂層 `def main`。`async def check_*` 也列入——它會被執行、
    回傳 coroutine、被判 `protocol`，而不是被安靜略過。
    語法錯誤 ⇒ 回空清單（driver import 時會自己報 `import`）。

    ⚠ 動態產生的 check（`globals()["check_x"] = …`、`from h import check_y`）
    **不在清單上**，driver 會把它們報成 `protocol` 失敗而不是偷偷跑或偷偷漏。
    """
    return _declared_from_source(pathlib.Path(test_file).read_bytes())


def _declared_from_source(source: bytes) -> list[str]:
    try:
        tree = ast.parse(source.decode("utf-8"))
    except (SyntaxError, ValueError, UnicodeDecodeError):
        return []
    fns = [n for n in tree.body
           if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    names: list[str] = []
    for n in fns:
        if n.name.startswith("check_") and n.name not in names:
            names.append(n.name)
    if names:
        return names
    return ["main"] if any(n.name == "main" for n in fns) else []


def _parse_records(stdout: str, nonce: str) -> tuple[list[dict], dict | None]:
    """把 driver 的輸出分成 case 紀錄與結束標記。"""
    cases: list[dict] = []
    end: dict | None = None
    for rec in _parse_cases(stdout, nonce):
        if rec.get("end") is True and "case" not in rec:
            end = rec
        else:
            cases.append(rec)
    return cases, end


def _reconcile(declared: list[str], records: list[dict], end: dict | None,
               *, rc: int | None, timed_out: bool) -> tuple[list[dict], bool]:
    """宣告清單 × 實際回報的對帳。回 `(cases, complete)`。

    `complete` ＝ 每個宣告的 id 恰好一筆、有結束標記、rc 為 0、沒逾時、
    沒有重複或清單外的 id。任何一條不成立 ⇒ 這個檔案**不可能**全過。
    """
    declared_set = set(declared)
    out: list[dict] = []
    seen: set[str] = set()
    problems = False
    module_failed = False
    for r in records:
        cid = r.get("case")
        if cid in FILE_LEVEL_IDS:
            out.append({**r, "ok": False})
            module_failed = module_failed or r.get("kind") == "import"
            problems = True
            continue
        if cid not in declared_set:
            out.append({**r, "ok": False, "kind": "protocol",
                        "message": r.get("message") if r.get("kind") == "protocol"
                        else f"reported a result for {cid!r}, which is not a declared "
                             f"check in this file"})
            problems = True
            continue
        if cid in seen:
            out.append({**r, "ok": False, "kind": "protocol",
                        "message": f"{cid} reported more than one result"})
            problems = True
            continue
        seen.add(cid)
        out.append(r)
    missing = [n for n in declared if n not in seen]
    for n in missing:
        # import 失敗／逾時：已經有一筆檔案層級紀錄說明原因 ⇒ 補的這幾筆標
        # `synthesized`，`render_failures` 不重複貼（回饋文字維持舊形狀）。
        # 其餘（行程無聲地提早結束）是**新資訊**——舊版在這裡判全過——要貼出來。
        if module_failed:
            out.append({"case": n, "ok": False, "kind": "import",
                        "message": "not run: the test file failed to import",
                        "where": None, "output": "", "synthesized": True})
            continue
        why = ("the test process timed out first" if timed_out else
               f"the test process ended before reaching it (rc={rc})")
        out.append({"case": n, "ok": False, "kind": "incomplete",
                    "message": f"this check never reported a result: {why}",
                    "where": None, "output": "", "synthesized": bool(timed_out)})
    if missing:
        problems = True
    if not timed_out and (end is None or rc not in (0, None)):
        out.append({"case": "<file>", "ok": False, "kind": "incomplete",
                    "message": (f"the test process did not finish normally "
                                f"(rc={rc}, end marker "
                                f"{'missing' if end is None else 'present'})"),
                    "where": None, "output": ""})
        problems = True
    complete = (not problems and not timed_out and end is not None
                and rc in (0, None) and bool(declared))
    return out, complete


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
    files_rec: list[dict] = []
    nonce = f"{_NONCE_PREFIX}{secrets.token_hex(8)}:"
    # **先讀進記憶體、先算好每個檔案的宣告清單與雜湊，再跑任何候選碼。**
    # 每個測試檔各拿一份從記憶體重寫的新目錄 ⇒ 前一個檔案裡跑的候選碼
    # 改不到後一個檔案的測試碼（`none` 後端沒有唯讀掛載，這是實測過的洞）。
    blobs: dict[str, bytes] = {}
    if src.is_dir():
        for p in sorted(src.iterdir()):
            if p.is_file() and p.suffix == ".py":
                blobs[p.name] = p.read_bytes()
    names = sorted(n for n in blobs if n.startswith("test_"))
    if not names:
        return _empty_result(suite, task_id,
                             reason=f"驗收目錄沒有 test_*.py：{src}")
    suite_sha = suite_digest(blobs)
    plan = {n: _declared_from_source(blobs[n]) for n in names}
    for rel in names:
        declared = plan[rel]
        vdir = vroot / f"_v_{suite}_{secrets.token_hex(8)}"
        try:
            vdir.mkdir(parents=True)
            (vdir / "driver.py").write_text(DRIVER_SRC, encoding="utf-8")
            for n, b in blobs.items():
                (vdir / n).write_bytes(b)
            tf = vdir / rel
            mf = vdir / f"_declared_{tf.stem}.json"
            mf.write_text(json.dumps(declared), encoding="utf-8")
            cmd = (f"python3 {_q(vdir / 'driver.py')} {_q(ws)} {_q(tf)} "
                   f"{_q(nonce)} {_q(mf)}")
            res = sandbox.run(cmd, workspace=ws, timeout_s=timeout_s,
                              ro_binds=(vdir,))
        finally:
            if vdir.exists() and not keep_verify_dir:
                shutil.rmtree(vdir, ignore_errors=True)
        records, end = _parse_records(res.stdout, nonce)
        timeout_rec = []
        if res.timed_out:
            timeout_rec = [{"case": "<file>", "ok": False, "kind": "timeout",
                            "message": (f"the checks in this file did not finish "
                                        f"within {int(timeout_s)} seconds."),
                            "where": None, "output": ""}]
        elif not records:
            records = [{"case": "<file>", "ok": False, "kind": "driver_error",
                        "message": _driver_error_message(res),
                        "where": None,
                        "output": (res.stderr or "")[-MAX_CASE_OUTPUT_CHARS:]}]
        cases, complete = _reconcile(declared, records, end,
                                     rc=res.rc, timed_out=res.timed_out)
        cases = cases + timeout_rec
        files_rec.append({
            "file": rel,
            "sha256": hashlib.sha256(blobs[rel]).hexdigest(),
            "rc": res.rc,
            "timed_out": res.timed_out,
            "wall_ms": res.wall_ms,
            "declared": declared,
            "end_marker": end is not None,
            "complete": complete,
            "cases": cases,
            "passed": sum(1 for c in cases if c.get("ok")),
            "total": len(cases),
            "stderr_tail": (res.stderr or "")[-400:],
        })
    out = _finish(suite, task_id, files_rec, suite_sha256=suite_sha)
    return out


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


def suite_digest(blobs: dict[str, bytes]) -> str:
    """驗收目錄內容的雜湊（檔名＋每檔 sha256，排序固定）。

    收據要說得出「跑的是**哪一份**驗收」——舊版只簽結果不簽測試本身。
    """
    rows = [[n, hashlib.sha256(b).hexdigest()] for n, b in sorted(blobs.items())]
    return hashlib.sha256(json.dumps(rows, separators=(",", ":")).encode()).hexdigest()


def _finish(suite: str, task_id: str, files_rec: list[dict], *,
            suite_sha256: str | None = None) -> dict:
    passed = sum(f["passed"] for f in files_rec)
    total = sum(f["total"] for f in files_rec)
    # 每個檔案都要對帳完整。沒有 `complete` 欄位的紀錄（舊呼叫端手造的）
    # 視為不完整——fail-closed，不是預設為真。
    complete = bool(files_rec) and all(f.get("complete") is True for f in files_rec)
    rec = {
        "suite": suite, "task_id": task_id, "files": files_rec,
        "passed": passed, "total": total,
        # `total == 0` ⇒ **不是通過**。量不到不是通過（`suitegauge` 的同一條）。
        # `complete` ⇒ 分母是宣告清單，不是回報筆數（報告 §03 P0）。
        "all_pass": bool(total > 0 and passed == total and complete),
        "complete": complete,
        "suite_sha256": suite_sha256,
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
    reduced = []
    for f in result.get("files", []):
        r = {"file": f["file"],
             "cases": [{"case": c.get("case"), "ok": bool(c.get("ok")),
                        "kind": c.get("kind")} for c in f.get("cases", [])]}
        # 宣告清單是分母的來源 ⇒ 屬於判準欄位。舊紀錄沒有這一欄，雜湊形狀不變。
        if "declared" in f:
            r["declared"] = list(f["declared"])
        reduced.append(r)
    payload = {"suite": result.get("suite"), "task_id": result.get("task_id"),
               "files": reduced, "passed": result.get("passed"),
               "total": result.get("total")}
    if "complete" in result:
        payload["complete"] = bool(result["complete"])
    if result.get("suite_sha256"):
        payload["suite_sha256"] = result["suite_sha256"]
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
    bad = [c for c in failing_cases(result) if not c.get("synthesized")]
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
