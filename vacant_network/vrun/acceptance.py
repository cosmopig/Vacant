#!/usr/bin/env python3
"""目錄級驗收 runner——R530 的量具。**標準庫，不依賴 pytest。**

這支在架構裡承重什麼（`DECISION_20260913_R530_…_PREREG.md` §五-1）：
既有的 `vacant_network/checks.py::run_python_check` 判的是**一個函式字串**，
R530 的交付是**一個目錄**（`solution.py` 或 `solution/` 套件、可能還有 CLI）。
兩者的驗收不可能共用同一支。而 vacant-dev 上**沒有 pip、沒有 venv、沒有 pytest**
（預註冊 §三-2 實測），所以這一支只能用標準庫寫。

## 測試檔是什麼形狀（`TASK_FORMAT.md` 是規格，這裡是執行語意）

一個測試檔 ＝ 一個 `.py`，三種寫法擇一，**檔案層級只准有一種**
（靜態分類器 `classify_dialect` 決定路由；同一檔宣告兩套語義＝`mixed`，
兩半都不跑、直接記一筆顯式 `protocol` 失敗）：

  1. 一組零引數的 `check_*()` 函式 ⇒ **每個函式一條 case**，
     依**定義順序**執行（Python 的 module `__dict__` 保序，所以順序是確定的）。
  2. 一個 `main()` ⇒ 整個檔案算**一條** case（名字就叫 `main`）。
  3. `unittest.TestCase` 子類（頂層）⇒ **每個 `test*()` 方法一條 case**
     （`ClassName.method`），依 `dir()` 字典序執行（機器間確定，I-6）。
     `async def test_*` 與 `skipTest` 都記**顯式失敗**（kind=protocol）——
     前者 unittest 根本不等候、方法體一行不跑，後者什麼都沒驗。

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
   `def check_*`（或 `def main`；unittest 方言則是 `TestCase` 子類的
   `test*()` 方法，`declared_unittest_cases()`），得到**預期的 case id**
   （`declared_cases()`）。check driver 只跑這份清單上的名字。
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
# P0-2: 套件目錄（vdir＝套件檔的副本）排在工作區**前面**——套件自己的
# helper（`test_utils.py` 之類）永遠先被解析；候選碼把工作區塞一個同檔名
# 檔也劫不走套件的 helper（helper 注入攻擊）。
_SUITE_DIR = os.path.dirname(os.path.abspath(TESTFILE))
if _SUITE_DIR:
    sys.path.insert(0, _SUITE_DIR)
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


def _is_test_name(name: str) -> bool:
    """測試檔命名的**唯一來源**（P0-2，round 131）。

    收 `test_*.py` **加** `*_test.py`（polyglot_py 34 題的真實形狀是後半部）；
    光板的 `test.py` 不收（stem 要 `test_` 前綴或 `_test` 後綴）。
    `test_files()`、launcher 的 `has_suite`、gateshim 的套件目錄發現都用這一個，
    兩處不會再漂移（漂移＝「launcher 以為有套件、門上什麼都看不到」的 0/34 形狀）。
    """
    if not name.endswith(".py"):
        return False
    stem = name[:-3]
    return stem.startswith("test_") or stem.endswith("_test")


def _static_import_roots(source: bytes) -> frozenset[str]:
    """這個檔案靜態 import 的頂層模組名（純語法樹、不執行）。

    供 helper 判定用：`from test_utils import …` ⇒ `test_utils`；
    `import test_utils` ⇒ `test_utils`。只認 level-0（絕對）import——
    相對 import 指的是同一包、不該被算成對兄弟檔的引用。
    語法錯誤 ⇒ 空集合（沒有 import 來源 ⇒ 不能當 helper ⇒ 照舊執行、
    落到顯式失敗）。
    """
    try:
        tree = ast.parse(source.decode("utf-8"))
    except (SyntaxError, ValueError, UnicodeDecodeError):
        return frozenset()
    roots: set[str] = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            roots.update(a.name.split(".")[0] for a in n.names)
        elif isinstance(n, ast.ImportFrom):
            if n.level == 0 and n.module:
                roots.add(n.module.split(".")[0])
    return frozenset(roots)


def test_files(suite_dir: str | pathlib.Path) -> list[pathlib.Path]:
    """一個驗收目錄裡的測試檔，**排序固定**（檔名字典序）。

    收 `test_*.py` 與 `*_test.py`（P0-2，`_is_test_name`）：目錄裡允許放
    helper（`test_utils.py`、`_support.py`）給測試 import，而 helper 不是
    一個測試檔（`run_suite` 的 helper 判定決定它執不執行）。認不出來的
    東西一律不當測試——「多跑了一個不是測試的東西」與「漏跑了一個測試」
    都會讓分數說謊。
    """
    d = pathlib.Path(suite_dir)
    if not d.is_dir():
        return []
    return sorted(p for p in d.glob("*.py")
                  if p.is_file() and _is_test_name(p.name))


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


# ── L2 方言偵測（DECISION_20261025_VISIBLE_SUITE_DIALECTS §4.2）───────────
# 純函數、只讀語法樹、不執行。分類發生在任何候選碼跑起來之前，所以候選碼
# 改不到分類結果。四個值：check / unittest / mixed / none。設計是 fail-closed：
# 認不出來的（none）與兩套語義混在一起的（mixed）都不該被當成「能照現行
# driver 跑」的檔案——那是 driver 分支的事，這裡只負責誠實地說它是哪一類。

DIALECT_CHECK = "check"
DIALECT_UNTEST = "unittest"
DIALECT_MIXED = "mixed"
DIALECT_NONE = "none"

# unittest 方言 driver（設計 §4.3）：同一套 nonce 協定、同一套檔案層級 id
# （<module>/<file>）、同一套結束標記——父程序的 `_parse_records`／`_reconcile`
# 對兩種 driver 的輸出完全同形，對帳邏輯不改一行。
#
# 與 `DRIVER_SRC` 的差異只有「案例怎麼跑」：
#  - 案例＝`TestLoader().loadTestsFromModule(mod)` 的葉子（設計 §4.3：順序＝
#    dir() 字典序，機器間確定 ⇒ I-6）；case id 記 `ClassName.method`，與
#    `declared_unittest_cases` 的宣告清單同形（對帳分母）。
#  - `async def test_*` 顯式失敗（kind=protocol）：unittest 跑 async 方法時
#    只調用、不等候，**方法體一行都不執行卻回報 pass**——實測確認的洞，
#    寧可顯式紅也不靜默綠（I-4）。
#  - `self.skipTest`／`@skip` 顯式失敗（kind=protocol）：被跳過的案例什麼都
#    沒驗，算過等於把分母藏掉。
#  - 零案例檔案：一筆 <file> driver_error（與 check 方言「無 check_*/main」
#    同形），不是「空＝過」。
UNTEST_DRIVER_SRC = '''
import contextlib, importlib.util, inspect, io, json, os, sys, traceback, unittest

NONCE = sys.argv[3]
WS = sys.argv[1]
TESTFILE = sys.argv[2]
REAL_STDOUT = sys.stdout

def emit(rec):
    line = json.dumps(rec, ensure_ascii=False, sort_keys=True)
    REAL_STDOUT.write(NONCE + line + "\\n")
    REAL_STDOUT.flush()

def clip(s, n):
    if s is None:
        return ""
    if len(s) <= n:
        return s
    return s[: n - 20] + "\\n...[clipped...]"

def last_line(info):
    lines = [l for l in (info or "").splitlines() if l.strip()]
    return lines[-1].strip() if lines else ""

def where_of(info, testfile):
    """從 traceback 字串（unittest 的 TestResult 只存字串形）取測試檔的
    `file:line: text`——與 check 方言 driver 的 where 同形。"""
    base = os.path.basename(testfile).lower()
    lines = (info or "").splitlines()
    hit = None
    for i, ln in enumerate(lines):
        s = ln.strip()
        if not s.startswith('File "'):
            continue
        q = s.find('"', 6)
        if q < 0:
            continue
        if os.path.basename(s[6:q]).lower() != base:
            continue
        j = s.find("line ", q)
        if j < 0:
            continue
        num = s[j + 5:].split(",")[0].strip()
        nxt = lines[i + 1].strip() if i + 1 < len(lines) else ""
        hit = f"{num}: {nxt}"
    if hit is None:
        return None
    return f"{os.path.basename(testfile)}:{hit}"

sys.path.insert(0, WS)
# P0-2: 同 check driver——套件目錄（vdir）排在工作區前面，helper 解析
# 永遠以套件自己的那份為準。
_SUITE_DIR = os.path.dirname(os.path.abspath(TESTFILE))
if _SUITE_DIR:
    sys.path.insert(0, _SUITE_DIR)
spec = importlib.util.spec_from_file_location("r530_testmod", TESTFILE)
mod = importlib.util.module_from_spec(spec)
# unittest.TestSuite._handleModuleSetUp／_handleTearDownModule 從
# `sys.modules[test.__class__.__module__]` 找測試模組——執行前不註冊，
# 查不到（KeyError）會靜默跳過 setUpModule／tearDownModule
# （GPT 審查 2026-10-28 P0-1(A)，與 setUpClass 同根因）。
sys.modules[spec.name] = mod
buf = io.StringIO()
try:
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        spec.loader.exec_module(mod)
except BaseException as e:
    info = "".join(traceback.format_exception(type(e), e, e.__traceback__))
    emit({"case": "<module>", "ok": False, "kind": "import",
          "message": clip(last_line(info) or type(e).__name__, 400),
          "where": where_of(info, TESTFILE), "output": clip(buf.getvalue(), 1200)})
    emit({"end": True, "ran": 0})
    raise SystemExit(0)

loader = unittest.TestLoader()
try:
    suite = loader.loadTestsFromModule(mod)
except BaseException as e:
    info = "".join(traceback.format_exception(type(e), e, e.__traceback__))
    emit({"case": "<file>", "ok": False, "kind": "driver_error",
          "message": clip("loading the unittest suite failed: " + (last_line(info) or type(e).__name__), 400),
          "where": where_of(info, TESTFILE), "output": ""})
    emit({"end": True, "ran": 0})
    raise SystemExit(0)

leaves = []
def _walk(s):
    for t in s:
        if isinstance(t, unittest.TestSuite):
            _walk(t)
        else:
            leaves.append(t)
_walk(suite)

if not leaves:
    emit({"case": "<file>", "ok": False, "kind": "driver_error",
          "message": ("no unittest.TestCase.test*() case found in this file "
                      "(a TestCase subclass without test methods verifies nothing)"),
          "where": None, "output": ""})
    emit({"end": True, "ran": 0})
    raise SystemExit(0)

# ── 執行：走標準 TestSuite，不是逐葉 test.run() ────────────────────────
# round-51 的寫法對每個葉子呼叫 `test.run(res)`。但 `setUpClass`／
# `setUpModule`／`tearDownClass`／`tearDownModule` 只由 `TestSuite.run`
# 觸發（unittest.TestSuite._handleClassSetUp／_handleModuleSetUp）——
# 逐葉呼叫**從不執行** class/module 層級的 setup hook：
# 依賴 setUpClass 的合法 TestCase 被誤判成 AttributeError（GPT 審查
# 2026-10-28 P0-1(A)）；同時 `@expectedFailure` 案例落進
# `res.expectedFailure`（failures／errors 都是空的）掉進 else 分支 →
# 假通過（P0-1(B)）。正確做法（即審查指定）：用 `suite.run(result)`
# 跑，以自訂 TestResult 收集逐 case 結果。

class Capture(unittest.TestResult):
    """收集逐 case 結果：`(test, status, detail, output)`，執行順序。
    status ∈ pass／assert／exception／skip／expected_failure／unexpected_success。"""

    def __init__(self):
        super().__init__()
        self.results = []
        self.fixtures = []
        self._buf = None
        self._prev = None
        self._fbuf = io.StringIO()

    def startTest(self, test):
        super().startTest(test)
        self._fbuf.seek(0)
        self._fbuf.truncate(0)
        self._buf = io.StringIO()
        self._prev = (sys.stdout, sys.stderr)
        sys.stdout = self._buf
        sys.stderr = self._buf

    def stopTest(self, test):
        if self._prev is not None:
            sys.stdout, sys.stderr = self._prev
        self._buf = None
        super().stopTest(test)

    def _record(self, test, status, detail):
        out = self._buf.getvalue() if self._buf is not None else ""
        if getattr(test, "_testMethodName", None) is None:
            # CPython 把 setUpClass／tearDownClass／setUpModule／
            # tearDownModule（以及 addCleanup）的失敗報告成一個合成物件
            # （unittest._ErrorHolder，沒有 `_testMethodName`）。若混進
            # case 清單，輸出迴圈用 `test._testMethodName` 拼 id 會
            # AttributeError 崩潰（rc=1、無 end marker——「碰巧」fail-closed，
            # 但記錄變成 driver_error 而不是「哪個 fixture 失敗」）。
            # 單列為檔案層 fixture 結果；輸出迴圈只從真 case 拼 id。
            # （GPT 審查 2026-10-28 P0-1 好/壞對照；round-149 釘住。）
            fout = self._fbuf.getvalue() + out
            self._fbuf.seek(0)
            self._fbuf.truncate(0)
            self.fixtures.append((test, status, detail, fout))
            return
        self.results.append((test, status, detail, out))

    def addSuccess(self, test):
        self._record(test, "pass", None)

    def addFailure(self, test, err):
        self._record(test, "assert", err)

    def addError(self, test, err):
        self._record(test, "exception", err)

    def addSkip(self, test, reason):
        self._record(test, "skip", reason)

    def addExpectedFailure(self, test, err):
        self._record(test, "expected_failure", err)

    def addUnexpectedSuccess(self, test):
        self._record(test, "unexpected_success", None)

async_leaves = []
sync_leaves = []
for test in leaves:
    meth = getattr(type(test), test._testMethodName)
    if inspect.iscoroutinefunction(meth):
        async_leaves.append(test)
    else:
        sync_leaves.append(test)
for test in async_leaves:
    # unittest 對 async 方法只調用不等候：方法體不執行、回報 pass。
    # 寧可顯式失敗，不可靜默通過（round-51 的守衛保留）。
    emit({"case": f"{test.__class__.__qualname__}.{test._testMethodName}",
          "ok": False, "kind": "protocol",
          "message": ("async test methods are not awaited by the unittest "
                      "runner, so their body never executes; write the case "
                      "synchronously (or drop the async keyword)"),
          "where": None, "output": ""})

def _emit_fixtures(cap):
    """把 fixture 層結果（setUp*/tearDown* 失敗）發成 `<file>` 記錄：
    與 case 記錄同形、顯式紅、指名 fixture，driver 正常收尾（end marker、
    rc=0）——不靠 driver 崩潰來「碰巧紅」。"""
    for test, status, detail, _out in cap.fixtures:
        desc = (getattr(test, "description", None) or "fixture")
        # 模組名是 driver 的內部 spec 名，換回測試檔名讓記錄可讀。
        desc = desc.replace("r530_testmod", os.path.basename(TESTFILE))
        if status in ("assert", "exception"):
            info = "".join(traceback.format_exception(*detail))
            emit({"case": "<file>", "ok": False, "kind": status,
                  "message": clip(f"{desc} failed: " +
                                  (last_line(info) or "fixture failure"), 400),
                  "where": where_of(info, TESTFILE), "output": clip(_out, 1200)})
        else:
            # fixture 自己 raise SkipTest（addSkip）或其他異常結果——
            # 對驗收門而言，fixture 不跑案例＝什麼都沒驗證，顯式紅。
            emit({"case": "<file>", "ok": False, "kind": "protocol",
                  "message": (f"{desc} reported {status} ({detail}); a fixture "
                              f"that skips the cases verifies nothing about "
                              f"the candidate"),
                  "where": None, "output": clip(_out, 1200)})

cap = Capture()
try:
    with contextlib.redirect_stdout(cap._fbuf), contextlib.redirect_stderr(cap._fbuf):
        unittest.TestSuite(sync_leaves).run(cap)
except BaseException as e:
    # 逐 case 的例外 unittest 會吞進 Capture；走到這裡是套件機件本身炸了。
    _emit_fixtures(cap)
    info = "".join(traceback.format_exception(type(e), e, e.__traceback__))
    emit({"case": "<file>", "ok": False, "kind": "exception",
          "message": clip("running the unittest suite failed: " +
                          (last_line(info) or type(e).__name__), 400),
          "where": where_of(info, TESTFILE), "output": ""})
    emit({"end": True, "ran": len(async_leaves) + len(cap.results)})
    raise SystemExit(0)

for test, status, detail, out in cap.results:
    case = f"{test.__class__.__qualname__}.{test._testMethodName}"
    if status == "pass":
        emit({"case": case, "ok": True, "kind": "pass",
              "message": "", "where": None, "output": clip(out, 1200)})
    elif status == "assert":
        # addFailure 的 err 是 (type, value, tb) 三元組。
        info = "".join(traceback.format_exception(*detail))
        emit({"case": case, "ok": False, "kind": "assert",
              "message": clip(last_line(info) or "assertion failed", 400),
              "where": where_of(info, TESTFILE), "output": clip(out, 1200)})
    elif status == "exception":
        info = "".join(traceback.format_exception(*detail))
        emit({"case": case, "ok": False, "kind": "exception",
              "message": clip(last_line(info) or "exception", 400),
              "where": where_of(info, TESTFILE), "output": clip(out, 1200)})
    elif status == "skip":
        emit({"case": case, "ok": False, "kind": "protocol",
              "message": (f"the case skipped itself ({detail}); "
                          f"a skipped case verifies nothing and counts as a failure"),
              "where": None, "output": clip(out, 1200)})
    elif status == "expected_failure":
        # @expectedFailure：unittest 算「既非 pass 也非 fail」。對驗收門而言，
        # 一個「預期候選是壞的」案例驗證不了候選任何事——當 pass 是假通過
        # （GPT 審查 P0-1(B)）。fail-closed：顯式紅。
        emit({"case": case, "ok": False, "kind": "expected_failure",
              "message": ("the case is marked @expectedFailure and failed as expected; "
                          "an acceptance suite that expects a failure verifies nothing "
                          "about the candidate, so it cannot count as a pass"),
              "where": None, "output": clip(out, 1200)})
    else:  # unexpected_success
        # 標記了 @expectedFailure 但實際成功：測試確實跑過並成功——
        # 要顯式記錄 kind，不靜默寫成普通 "pass"（GPT 審查 P0-1(B)）。
        emit({"case": case, "ok": True, "kind": "unexpected_success",
              "message": "the case was marked @expectedFailure but actually succeeded",
              "where": None, "output": clip(out, 1200)})

_emit_fixtures(cap)

emit({"end": True, "ran": len(async_leaves) + len(cap.results)})
'''


def _ast_of(source: bytes):
    try:
        return ast.parse(source.decode("utf-8"))
    except (SyntaxError, ValueError, UnicodeDecodeError):
        return None


def _top_level_functions(tree) -> list:
    return [n for n in tree.body
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]


def _has_check_signal(tree) -> bool:
    """頂層有 `def check_*`（含 async）或 `def main` ＝ check 方言的形狀。

    與現行 `_declared_from_source` 的判據對齊：先 check_*，沒有才看 main。
    """
    fns = _top_level_functions(tree)
    if any(n.name.startswith("check_") for n in fns):
        return True
    return any(n.name == "main" for n in fns)


def _base_is_unittest_case(base) -> bool:
    """一個 base 是否指向 `unittest.TestCase`。

    兩種合法寫法都認：`class X(unittest.TestCase)`（Attribute）與
    `from unittest import TestCase` 後的 `class X(TestCase)`（Name）。
    設計 §4.2 的判據是「`class … (unittest.TestCase)` 子類」；`from-import`
    那一支是它明確涵蓋的「含 `from unittest import …`」的執行形態。
    """
    if isinstance(base, ast.Attribute):
        return base.attr == "TestCase"
    if isinstance(base, ast.Name):
        return base.id == "TestCase"
    return False


def _has_unittest_class(tree) -> bool:
    """頂層有 `class …(unittest.TestCase)` 子類（只認頂層，與 check 方言對齊）。"""
    return any(
        isinstance(n, ast.ClassDef)
        and any(_base_is_unittest_case(b) for b in n.bases)
        for n in tree.body)


def _has_unittest_import(tree) -> bool:
    """頂層有 `import unittest`（含 `import unittest as x`）或 `from unittest import …`。"""
    for n in tree.body:
        if isinstance(n, ast.Import):
            if any(a.name == "unittest" for a in n.names):
                return True
        elif isinstance(n, ast.ImportFrom):
            if n.module == "unittest":
                return True
    return False


def classify_dialect(source: bytes) -> str:
    """L2 方言偵測：靜態、只讀語法樹、四值（`check`/`unittest`/`mixed`/`none`）。

    判據（頂層，與現行 check 方言「只認頂層」對齊）：
      - `check`    頂層有 `def check_*` 或 `def main`
      - `unittest` 有 `import unittest`（含 `from unittest import …`）**且**
                   頂層有 `class …(unittest.TestCase)` 子類
      - `mixed`    兩套語義都在——**顯式失敗**的候選（driver 不猜、不拆半跑）
      - `none`     都沒有（含 `test_utils.py` 這種工具檔）
    語法錯誤 ⇒ `none`（不猜；driver import 時會自己報 `import` 失敗）。

    純函數、不執行：分類與宣告都發生在任何候選碼跑起來之前。
    """
    tree = _ast_of(source)
    if tree is None:
        return DIALECT_NONE
    has_check = _has_check_signal(tree)
    has_unittest = _has_unittest_import(tree) and _has_unittest_class(tree)
    if has_check and has_unittest:
        return DIALECT_MIXED
    if has_check:
        return DIALECT_CHECK
    if has_unittest:
        return DIALECT_UNTEST
    return DIALECT_NONE


def _is_static_testcase_class(node, top) -> bool:
    """頂層類別是否為 `TestCase` 子類：直接繼承 `unittest.TestCase`／`TestCase`，
    或透過**本模組頂層**類別的繼承鏈（`Sub(Base)`、`Base(unittest.TestCase)`）。

    與 loader 的 `issubclass` 判據同形；其他模組定義的 base 靜態不可判定
    （執行時若該 case 被跑出來，對帳會給顯式失敗，fail-closed，不假過）。
    """
    def walk(cls, seen):
        for b in cls.bases:
            if _base_is_unittest_case(b):
                return True
            if isinstance(b, ast.Name) and b.id in top and b.id not in seen \
                    and walk(top[b.id], seen | {b.id}):
                return True
        return False
    return walk(node, {node.name})


def _static_test_names(node, top) -> list[str]:
    """該類別上**可見**的 `test*` 方法名：自己的＋繼承自本模組頂層 base 的，
    去重、依定義順序。

    與 `unittest.TestLoader.loadTestsFromTestCase` 的收集判據同形：它從
    `dir(cls)` 收集（含繼承方法），所以 `Sub(Base)` 也會執行 `Base` 的 `test*`
    （case id 為 `Sub.<方法名>`）。跨模組 base 的 `test*` 靜態不可見——
    執行時被跑出來即對帳為「未宣告」，顯式失敗（fail-closed，不假過）。
    """
    names: list[str] = []
    def add(nm: str) -> None:
        if nm not in names:
            names.append(nm)
    def walk(cls, seen) -> None:
        for m in cls.body:
            if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef)) \
                    and m.name.startswith("test"):
                add(m.name)
        for b in cls.bases:
            if isinstance(b, ast.Name) and b.id in top and b.id not in seen:
                walk(top[b.id], seen | {b.id})
    walk(node, {node.name})
    return names


def declared_unittest_cases(source: bytes) -> list[str]:
    """unittest 方言的**宣告清單**：每個頂層 `TestCase` 子類（含本模組繼承鏈，
    如 `Sub(Base)`）上可見的 `test*` 方法（自己的＋繼承自本模組 base 的），
    記 `ClassName.method`（與 `_declared_from_source` 同形：只讀語法樹、不執行、
    依定義順序、去重）。

    這是對帳（`_reconcile`）的分母來源：宣告了沒跑、跑了沒宣告、重複——任一
    即該檔失敗；零案例的檔案＝失敗，不是「空＝過」（I-4）。設計 §4.3 的
    宣告清單就是這份。`setUp`/`tearDown`/非 `test*` 方法不列入（不是 case）。
    語法錯誤 ⇒ 空清單。

    繼承與 `TestLoader` 同形（round-143，GPT 審查 P0-1「inherited tests」）：
    loader 從 `dir(cls)` 收集，`Sub(Base)` 會執行 `Base` 的 `test*` 方法；
    宣告若只數直接定義，每個繼承 case 都會變成「未宣告的 id」，把正確套件
    誤判成 protocol 失敗。跨模組 base 的 `test*` 靜態不可枚舉：執行時若被跑
    出來，對帳給顯式 protocol 失敗（fail-closed，永不假過）。
    """
    tree = _ast_of(source)
    if tree is None:
        return []
    top = {n.name: n for n in tree.body if isinstance(n, ast.ClassDef)}
    out: list[str] = []
    for n in tree.body:
        if not isinstance(n, ast.ClassDef) or not _is_static_testcase_class(n, top):
            continue
        for m in _static_test_names(n, top):
            name = f"{n.name}.{m}"
            if name not in out:
                out.append(name)
    return out


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
    # P0-2 (round 131)：命名＝`test_*.py` **或** `*_test.py`（`_is_test_name`
    # 是命名規則的唯一來源，`test_files()` 與 launcher 的 `has_suite` 共用）。
    names = sorted(n for n in blobs if _is_test_name(n))
    if not names:
        return _empty_result(suite, task_id,
                             reason=f"驗收目錄沒有 test_*.py 或 *_test.py 測試檔：{src}")
    suite_sha = suite_digest(blobs)
    # 方言路由（設計 §4.2）：每個被發現的檔先由靜態分類器決定走哪支 driver。
    #   check / none → 舊 driver（與 adapter 前逐位相同，`none` 照舊給
    #                  顯式 driver_error，不靜默跳過）；
    #   unittest     → UNTEST_DRIVER_SRC，宣告清單換成 declared_unittest_cases；
    #   mixed        → 兩半都不跑、不拆半——直接合成一筆顯式 protocol 失敗。
    # 分類在任何候選碼執行前完成（純語法樹），候選碼改不到路由結果。
    dialects = {n: classify_dialect(blobs[n]) for n in names}
    # P0-2: helper 判定——**符合命名**的檔、靜態 dialect 為 `none`、且被同套件
    # 另一個**符合命名**的檔靜態 import ⇒ helper（如 polyglot_py pg_paasio 的
    # `test_utils.py`），**不執行**。單獨一個 `none` 檔照舊執行、落到顯式
    # `driver_error`（round 51/126 的 pin，`tests/test_visible_suite_dialect.py` §C）。
    # 判定是純語法樹（不執行）：候選碼改不到 helper 判定，helper 鏈可以有多層
    # （test→test_mid(none)→test_utils(none)，兩層都因被上游引用而成為 helper）。
    import_roots = {n: _static_import_roots(blobs[n]) for n in names}
    helpers = {n for n in names
               if dialects[n] == DIALECT_NONE
               and any(n[:-3] in import_roots[o] for o in names if o != n)}
    names = [n for n in names if n not in helpers]
    if not names:
        # 所有符合命名的檔都是 helper ⇒ 沒有可執行的測試 ⇒ 不是通過（fail-closed）。
        return _empty_result(suite, task_id,
                             reason=(f"驗收目錄只有 helper（被其他測試檔 import 的"
                                     f"工具檔 {sorted(helpers)}）、沒有可執行的測試檔：{src}"))
    for rel in names:
        dialect = dialects[rel]
        if dialect == DIALECT_MIXED:
            files_rec.append(_mixed_failure_record(rel, blobs[rel]))
            continue
        if dialect == DIALECT_UNTEST:
            declared = declared_unittest_cases(blobs[rel])
            driver_name = "driver_untest.py"
        else:
            declared = _declared_from_source(blobs[rel])
            driver_name = "driver.py"
        vdir = vroot / f"_v_{suite}_{secrets.token_hex(8)}"
        try:
            vdir.mkdir(parents=True)
            (vdir / "driver.py").write_text(DRIVER_SRC, encoding="utf-8")
            if driver_name == "driver_untest.py":
                (vdir / driver_name).write_text(UNTEST_DRIVER_SRC,
                                                encoding="utf-8")
            for n, b in blobs.items():
                (vdir / n).write_bytes(b)
            tf = vdir / rel
            mf = vdir / f"_declared_{tf.stem}.json"
            mf.write_text(json.dumps(declared), encoding="utf-8")
            cmd = (f"python3 {_q(vdir / driver_name)} {_q(ws)} {_q(tf)} "
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
    # P0-2: discovery 稽核紀錄——驗收目錄裡**每個 .py** 一筆（不管執不執行），
    # 供逐題回答「看到了什麼、執行了什麼、為什麼」。純增量欄位：**不進**
    # `result_digest`（動簽進收據的欄位集合＝全世界既有收據的雜湊形狀都變）。
    out["discovery"] = [_discovery_record(n, blobs, dialects, import_roots, helpers)
                        for n in sorted(blobs)]
    return out


def _discovery_record(name: str, blobs: dict[str, bytes],
                      dialects: dict[str, str],
                      import_roots: dict[str, frozenset[str]],
                      helpers: set[str]) -> dict:
    """P0-2 discovery 稽核筆（欄位語意見 `run_suite` 末段的註解）。"""
    rec = {"name": name,
           "sha256": hashlib.sha256(blobs[name]).hexdigest()}
    if name not in dialects:
        # 不合測試檔命名（`test_*.py`／`*_test.py`）：永遠不執行。
        rec.update({"role": "helper", "dialect": None, "executed": False,
                    "reason": "not_test_name"})
    elif name in helpers:
        # 符合命名但被另一個測試檔靜態 import ⇒ helper，不執行。
        importers = sorted(o for o in dialects
                           if o != name and name[:-3] in import_roots[o])
        rec.update({"role": "helper", "dialect": DIALECT_NONE,
                    "executed": False, "imported_by": importers,
                    "reason": (f"helper: statically imported by "
                              f"{', '.join(importers)}")})
    else:
        rec.update({"role": "test", "dialect": dialects[name], "executed": True})
    return rec


def _mixed_failure_record(rel: str, blob: bytes) -> dict:
    """`mixed` 檔（同一檔既宣告 `check_*` 又宣告 `unittest.TestCase` 子類）的
    檔案層級失敗紀錄——兩半**都不執行**（設計 §4.2：「不猜、不拆半跑」）。

    形狀與真實跑過一支 driver 的檔案紀錄同形（`_finish`/`render_failures`/
    收據雜湊不需特判）：`complete=False`、`rc=None`（driver 沒跑過）、
    `end_marker=False`、唯一 case 是這筆 protocol 失敗 ⇒ `all_pass` 必為
    False，且失敗原因會原樣進回饋（**不標 `synthesized`**——這是要讓寫測試
    的人看到並改的動作項，不是重複貼的雜訊）。
    """
    check_names = _declared_from_source(blob)
    untest_names = declared_unittest_cases(blob)
    cases = [{"case": "<file>", "ok": False, "kind": "protocol",
              "message": (f"this file declares two dialects at once "
                          f"(check_*: {check_names or 'none'}; unittest: "
                          f"{untest_names or 'none'}); neither half was run — "
                          f"split it into one file per dialect"),
              "where": None, "output": ""}]
    return {"file": rel,
            "sha256": hashlib.sha256(blob).hexdigest(),
            "rc": None, "timed_out": False, "wall_ms": 0,
            "declared": [],
            "end_marker": False,
            "complete": False,
            "cases": cases,
            "passed": 0, "total": len(cases),
            "stderr_tail": ""}


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
