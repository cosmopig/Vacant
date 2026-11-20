"""零設定的重開模式——`vacant do <agent>` 在沒有任務契約時的預設行為（T05／S3，2026-11-17；W1 擴充多驗收種類）。

這支在架構裡承重什麼：把 `ops/redo/redo.py` 的 R3 政策做成使用者打得到的一個指令。
R3 是這個 repo 裡第一個在**原生 agent**上量到交付變好的設定（redo1：pi＋gemma-4-12b、34 題×5，
進行中數字見 `ops/redo/`；結論以該批的 `REPORT.md` 為準，這裡不引用數字）。

政策（與 `redo.py` 的 `_policy_stop`／`_policy_deliver` 逐條相同，`tests/test_adapters_restart.py` 對照）：
1. 驗收訊號（依序選擇）：
   a. 明確指定 `--check "<shell command>"`：在快照副本中執行該指令，退出碼 0 即通過；
      若專案裡有 `find_tests` 找到的測試檔，跑驗收前仍會還原為開始時的位元組並保護不寫回。
   b. 自動偵測（未給 `--check` 時）：
      - Python 測試檔（`*_test.py`／`test_*.py`）：若皆為 `unittest.TestCase`，沿用既有 `unittest`
        執行器與計數（不改動）；若含 pytest 風格測試（模組層 `def test_*` 或非 `TestCase` 測試類別），
        則在測試直譯器可匯入 `pytest` 時跑 `pytest`（輸出於工作區外的 junitxml 解析通過／失敗數），
        否則退回極簡標準庫執行器（執行 `unittest.TestCase` 與裸 `def test_*` 函式／簡易 `Test*` 類別）。
      - `package.json`（含 `scripts.test` 且 `PATH` 有 `npm`）⇒ `npm test`；
        `Cargo.toml`（`PATH` 有 `cargo`）⇒ `cargo test`；
        `go.mod`（`PATH` 有 `go`）⇒ `go test ./...`。這幾種以退出碼 0 判通過（`passed`／`run` 為 `None`）。
      - 都沒有 ⇒ 跑一次、照實交回、明講「沒有可執行的驗收」，不假裝檢查過。
   c. 保護測試檔與驗收定義（開始時鎖定）：跨生態系測試檔（`*_test.py`、`test_*.py`、`*.test.*`、`*.spec.*`、
      `*_test.go`、`__tests__/**`、`tests/**`、`test/**`）、決定驗收指令的 manifest（`package.json`／`Cargo.toml`／
      `go.mod`）以及 `--protect PATH/GLOB` 指定檔案，在跑驗收前還原成原位元組；被改過的記在 `tests_tampered`，
      也**不寫回專案**。若沒有任何受保護檔案，交付訊息明講 agent 可能改動驗收所執行的內容。
   d. 基線預檢（BASELINE）：在第一次嘗試前先對未動過的專案副本跑一次驗收並記錄；若因環境問題無法執行
      （`load_error`／收集期 `ImportError`、缺 `pytest`／`npm`、指令不存在退出碼 126／127 等），立即停住
      （0 次 agent 嘗試、專案不動、非零退出碼），明講原因、指令與直譯器。若能執行但收到 0 個測試
      （`no_tests_collected`），仍照舊跑一次並明講未檢查。
2. Python 驗收優先使用專案直譯器（`$VIRTUAL_ENV/bin/python` ＞ `<project>/.venv` ＞ `<project>/venv` ＞ `PATH`
   ＞ `sys.executable`），保留 `-B`、捨 `-I` 改以工作區外私密腳本＋匯入前清 `sys.path` 維持 C3 防護，並把實際直譯器
   記在結果、簽章收據與訊息中。`node_modules` 不複製也不暴露給 agent 工作區，僅於外部驗收當下以 acceptance-only
   symlink＋`NODE_PATH` 提供並在驗收結束立刻移除。
3. 每一次嘗試：全新的暫存副本＋全新的 agent 行程。嘗試之間不留東西、不給失敗原文。
4. 驗收通過就停、交那一次；最多 `max_attempts` 次、每次 `attempt_timeout_s`、合計 `budget_s`。
   都沒過就交原件測試過最多的那一次（同分取後面那次；僅看退出碼的種類 `passed` 為 `None`，
   故依同分規則交最後一次），給人的訊息明講沒有通過，並列出實際使用的驗收種類／指令、直譯器與受保護檔案。

交回：被選中那一次的工作區同步回專案（新增／修改／刪除），**受保護的測試檔除外**——跟使用者直接在專案裡跑
agent 的結果同一種形狀，只是多了「選哪一次」。

誠實邊界（改碼請保留）：
- **未量測邊界**：`ops/redo/` 中量到的重開模式數字（redo1／confirm1 等）**只適用於既有的 `python_unittest` 路徑**；
  其餘新增的驗收種類（`check`、`python_pytest`、`python_bare`、`npm`、`cargo`、`go`）皆未經過對照實驗量測。
- 驗收＝「擋得住專案自己的測試會抓到的錯」，**不等於需求被滿足**。測試寫得弱，這一層就弱。
- 暫存副本**不是沙箱**：agent 與外部驗收指令（`--check`、`npm`、`cargo`、`go`）皆以使用者的帳號權限與環境變數執行，
  讀寫得到磁碟上你讀寫得到的一切；這層只保護「交回寫回」與「驗收流程」本身，擋不住執行期間直接讀寫專案外或其他路徑的檔案，
  也殺不到自己 `setsid()` 脫離行程群組的背景子行程。另 `COPY_SKIP` 名稱（如 `.git`、`node_modules`、`.venv`）
  不會複製進暫存工作區或快照副本。
- 等預算是牆鐘的；重開通常讓 agent 用掉更多模型呼叫（redo1 約兩倍），這一層不省算力。
- `budget_s` 是**整個指令**的牆鐘上限：agent、驗收（所有測試目錄與外部指令共用同一條期限，不設超額下限）、複製都算在內，
  每次嘗試前預留一次驗收的時間（2026-11-19：只算 agent 時間時，confirm1／confirm1c 各有 1 格第三次嘗試跑到
  外層時限被砍、什麼都沒交回）。
  ⚠ 這點和 `redo.py` 的 R3 不同（R3 只算 agent 牆鐘）：產品比量到的政策略保守，同樣預算下最後一次嘗試可能短一點。
- 快照與驗收一致性：每次 agent 結束並殺完其行程群組後，先拍一次只含一般檔案的私密快照（跳過符號連結、FIFO／socket／
  裝置檔、`COPY_SKIP` 名稱與無法讀取的項目），驗收與寫回皆以**同一份快照**為準（驗收測試的正是實際會寫回的檔案集合），
  避免殘留背景行程在驗收與寫回之間偷改工作區（TOCTOU），也避免 symlink 只在驗收生效卻不寫回。
- 驗收執行隔離邊界：Python 驗收路徑（`python_unittest`、`python_pytest`、`python_bare`）皆以專案直譯器＋`-B`
  （保留不寫 `.pyc`，捨 `-I` 以支援 `pip install --user` 與 `PYTHONPATH`）在工作區外的私密空目錄獨立腳本檔執行，
  於匯入標準庫／`pytest` 之前先從 `sys.path` 剔除 `""`、`.`、腳本目錄與工作區，再把工作區附在 `sys.path` 尾端，
  依原測試檔精確路徑載入（防止套件目錄或標準庫遮蔽），並透過獨立 session（結束或逾時皆 `killpg` 整組清除）、
  獨立管線（FD）與單次隨機 nonce 回傳結果（不依賴 stdout 固定標記；`pytest` 的 junitxml 寫在工作區外私密目錄）。
  外部指令（`--check`、`npm`、`cargo`、`go`）同樣於快照副本中以獨立 session（結束或逾時皆 `killpg`）與共用期限執行；
  若原專案有 `node_modules`，僅於外部驗收當下以 acceptance-only symlink（＋`NODE_PATH`）掛進驗收副本並於結束後立即移除
  （不放進 agent 的 `ws` 也不寫回；但驗收期間執行的候選碼仍以使用者權限執行，理論上仍可透過 symlink 寫入 `node_modules`）。
  ⚠ 另 Python 路徑的**候選程式碼與測試框架仍在同一個 Python 行程內執行**，故無法防禦惡意候選碼在行程內 monkey-patch
  測試框架或執行期狀態（若需要雙行程隔離，請用 `vacant_network.checks.run_python_check`）；另除跨生態系測試檔、
  manifest（`package.json`／`Cargo.toml`／`go.mod`）與 `--protect` 指定檔外，未涵蓋之設定檔（如根目錄 `conftest.py`、
  `pyproject.toml`、`jest.config.*`）與 agent 新建檔案皆不受保護。
- 寫回安全邊界：寫回前先規劃與驗證所有增／改／刪操作再套用，先刪後增、透過同目錄暫存檔＋`os.replace` 原子置換
  （不原地覆寫硬連結 inode、不把檔案寫進既有目錄）；符號連結、無法讀取的目錄／檔案、或與非空／受保護目錄衝突的路徑
  一律跳過並記於 `changed["skipped"]`，不會寫到專案外面也不會誤刪原檔；若套用途中遇非預期錯誤會回滾，維持原專案不變。
- 容錯邊界：單次嘗試在快照或驗收時發生任何非預期錯誤，該次嘗試一律記為未通過（例如 `acceptance_error`），不中斷整個
  `run()`、也不遺失前面嘗試的成果。
- 僅看退出碼的種類（`--check`、`npm`、`cargo`、`go`）沒有逐測試計數（`passed`／`run` 皆為 `None`）；若所有嘗試皆未通過，
  交回政策依同分規則交最後一次嘗試。
- 這一層不讀 agent 說了什麼；它只看驗收結果。說「做完了」但驗收沒過＝沒過。
"""
from __future__ import annotations

import ast
import dataclasses
import fnmatch
import hashlib
import hmac
import json
import os
import pathlib
import re
import secrets
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET
from typing import Any, Callable, Sequence

from .run import COPY_SKIP, Launch, run_agent, work_root

PATTERNS = ("*_test.py", "test_*.py")
_UNIVERSAL_TEST_NAME_PATTERNS = ("*_test.py", "test_*.py", "*.test.*", "*.spec.*", "*_test.go")
_UNIVERSAL_TEST_DIRS = frozenset({"__tests__", "tests", "test"})
_MANIFEST_BY_KIND: dict[str, tuple[str, ...]] = {
    "npm": ("package.json",),
    "cargo": ("Cargo.toml",),
    "go": ("go.mod",),
}
ACC_TIMEOUT_S = 120.0
_CHUNK_SIZE = 65536
_RESULT_KEYS = ("run", "failures", "errors", "skipped", "unexpected_successes")
_UNCHECKABLE_STATUSES = frozenset({"no_tests", "no_tests_collected", "runner_unavailable"})
_EXIT_CODE_ONLY_KINDS = frozenset({"check", "npm", "cargo", "go"})
_NPM_DEFAULT_TEST_MARKER = "Error: no test specified"
RECEIPT_SCHEMA = "vacant-restart-receipt/1"
_RECEIPT_MAX_BYTES = 48 * 1024  # 留足餘量低於 Logbook.MAX_PAYLOAD_BYTES (64 KiB)，不進可被 gc 的 blob
_MAX_ARG_LEN = 512

_SECRET_KEY_RE = re.compile(
    r"(?i)(?:api[_-]?key|secret|token|password|passwd|auth|credential|cookie|"
    r"private[_-]?key|bearer|jwt|dsn|database[_-]?url|connection[_-]?string|"
    r"signature|client[_-]?secret|access[_-]?key|signing[_-]?key|passphrase|"
    r"(?:^|[_-])(?:key|pass|cert)(?:$|[_-]))"
)
_SECRET_FLAG_RE = re.compile(
    r"(?i)^--?(?:api[_-]?key|token|secret|password|passwd|auth|bearer|key|cookie|credential|passphrase)(?:=|$)"
)
_SECRET_VAL_RE = re.compile(
    r"(?:sk-(?:ant-|proj-)?[A-Za-z0-9_-]{8,}|gh[pousr]_[A-Za-z0-9]{10,}|"
    r"github_pat_[A-Za-z0-9_]{10,}|glpat-[A-Za-z0-9_-]{8,}|"
    r"xox[baprs]-[A-Za-z0-9-]{8,}|AKIA[0-9A-Z]{16}|"
    r"(?i:^(?:bearer|basic)\s+\S+)|"
    r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----|"
    r"://[^/\s:@]+:[^/\s@]+@)"
)

_UNITTEST_RUNNER = r"""
def _main():
    import os as _os
    import sys as _sys

    _here = _os.path.dirname(_os.path.abspath(__file__))
    _init_cwd = _os.path.abspath(_os.getcwd())
    _sys.path[:] = [p for p in _sys.path if p not in ("", ".", _here, _init_cwd)]

    import importlib.util
    import json
    import traceback
    import unittest

    _json = json
    _tb = traceback
    _Loader = unittest.TestLoader
    _Result = unittest.TestResult
    _spec_from_file = importlib.util.spec_from_file_location
    _mod_from_spec = importlib.util.module_from_spec

    raw_cfg = _sys.stdin.read()
    try:
        dn = _os.open(_os.devnull, _os.O_RDONLY)
        try:
            _os.dup2(dn, 0)
        finally:
            _os.close(dn)
    except OSError:
        pass

    cfg = _json.loads(raw_cfg)
    w_fd = int(cfg["w_fd"])
    nonce = str(cfg["nonce"])
    cwd = str(cfg["cwd"])
    work_root = cfg.get("work_root")
    project_root = cfg.get("project_root")
    tests = cfg["tests"]
    try:
        _os.set_inheritable(w_fd, False)
    except OSError:
        pass

    if project_root and work_root and project_root != work_root:
        _proj_src = _os.path.join(project_root, "src")
        _work_src = _os.path.join(work_root, "src")
        _new_path = []
        for _p in _sys.path:
            _ap = _os.path.abspath(_p) if _p else _p
            if _ap == project_root:
                _new_path.append(work_root)
            elif _ap == _proj_src and _os.path.isdir(_work_src):
                _new_path.append(_work_src)
            else:
                _new_path.append(_p)
        _sys.path[:] = _new_path

    if cwd not in _sys.path:
        _sys.path.append(cwd)

    out = {
        "run": 0,
        "failures": 0,
        "errors": 0,
        "skipped": 0,
        "unexpected_successes": 0,
        "load_error": None,
        "first_problem": None,
    }
    for idx, (mod_name, file_path) in enumerate(tests):
        try:
            load_name = mod_name if mod_name not in _sys.modules else f"__vacant_test_{idx}_{mod_name}"
            spec = _spec_from_file(load_name, file_path)
            if spec is None or spec.loader is None:
                raise ImportError(f"cannot load test file: {file_path}")
            mod = _mod_from_spec(spec)
            _sys.modules[load_name] = mod
            spec.loader.exec_module(mod)
            suite = _Loader().loadTestsFromModule(mod)
        except BaseException:
            out["load_error"] = _tb.format_exc(limit=3)[-800:]
            break
        res = _Result()
        suite.run(res)
        out["run"] += res.testsRun
        out["failures"] += len(res.failures)
        out["errors"] += len(res.errors)
        out["skipped"] += len(res.skipped)
        out["unexpected_successes"] += len(res.unexpectedSuccesses)
        probs = res.failures + res.errors
        if probs and out["first_problem"] is None:
            out["first_problem"] = (str(probs[0][0]) + "\n" + probs[0][1])[-800:]

    try:
        _sys.stdout.flush()
        _sys.stderr.flush()
    except BaseException:
        pass

    payload = (nonce + "\n" + _json.dumps(out) + "\n").encode("utf-8")
    view = memoryview(payload)
    written = 0
    while written < len(view):
        n = _os.write(w_fd, view[written:])
        if n <= 0:
            break
        written += n
    try:
        _os.close(w_fd)
    except OSError:
        pass
    _os._exit(0)


_main()
"""

_PYTEST_RUNNER = r"""
def _main():
    import os as _os
    import sys as _sys

    _here = _os.path.dirname(_os.path.abspath(__file__))
    _init_cwd = _os.path.abspath(_os.getcwd())
    _sys.path[:] = [p for p in _sys.path if p not in ("", ".", _here, _init_cwd)]

    import json

    _json = json

    raw_cfg = _sys.stdin.read()
    try:
        dn = _os.open(_os.devnull, _os.O_RDONLY)
        try:
            _os.dup2(dn, 0)
        finally:
            _os.close(dn)
    except OSError:
        pass

    cfg = _json.loads(raw_cfg)
    w_fd = int(cfg["w_fd"])
    nonce = str(cfg["nonce"])
    extra_paths = cfg["extra_paths"]
    work_root = cfg.get("work_root")
    project_root = cfg.get("project_root")
    junit_xml = str(cfg["junit_xml"])
    tests = cfg["tests"]
    try:
        _os.set_inheritable(w_fd, False)
    except OSError:
        pass

    def _emit(obj):
        try:
            _sys.stdout.flush()
            _sys.stderr.flush()
        except BaseException:
            pass
        payload = (nonce + "\n" + _json.dumps(obj) + "\n").encode("utf-8")
        view = memoryview(payload)
        written = 0
        while written < len(view):
            n = _os.write(w_fd, view[written:])
            if n <= 0:
                break
            written += n
        try:
            _os.close(w_fd)
        except OSError:
            pass
        _os._exit(0)

    try:
        import pytest
    except BaseException as exc:
        _emit({"pytest_rc": None, "unavailable_reason": f"cannot import pytest: {exc}"})

    if project_root and work_root and project_root != work_root:
        _proj_src = _os.path.join(project_root, "src")
        _work_src = _os.path.join(work_root, "src")
        _new_path = []
        for _p in _sys.path:
            _ap = _os.path.abspath(_p) if _p else _p
            if _ap == project_root:
                _new_path.append(work_root)
            elif _ap == _proj_src and _os.path.isdir(_work_src):
                _new_path.append(_work_src)
            else:
                _new_path.append(_p)
        _sys.path[:] = _new_path

    for p in extra_paths:
        if p not in _sys.path:
            _sys.path.append(p)

    argv = [
        "-q",
        "-rN",
        "-p", "no:cacheprovider",
        "--import-mode=importlib",
        "-o", "addopts=",
        f"--junitxml={junit_xml}",
        *tests,
    ]
    try:
        rc = int(pytest.main(argv))
    except SystemExit as se:
        code = se.code
        rc = int(code) if isinstance(code, int) else 1
    _emit({"pytest_rc": rc, "unavailable_reason": None})


_main()
"""

_BARE_RUNNER = r"""
def _main():
    import os as _os
    import sys as _sys

    _here = _os.path.dirname(_os.path.abspath(__file__))
    _init_cwd = _os.path.abspath(_os.getcwd())
    _sys.path[:] = [p for p in _sys.path if p not in ("", ".", _here, _init_cwd)]

    import asyncio
    import importlib.util
    import inspect
    import json
    import traceback
    import unittest

    _json = json
    _tb = traceback
    _inspect = inspect
    _asyncio = asyncio
    _Loader = unittest.TestLoader
    _Result = unittest.TestResult
    _TestCase = unittest.TestCase
    _SkipTest = unittest.SkipTest
    _spec_from_file = importlib.util.spec_from_file_location
    _mod_from_spec = importlib.util.module_from_spec

    raw_cfg = _sys.stdin.read()
    try:
        dn = _os.open(_os.devnull, _os.O_RDONLY)
        try:
            _os.dup2(dn, 0)
        finally:
            _os.close(dn)
    except OSError:
        pass

    cfg = _json.loads(raw_cfg)
    w_fd = int(cfg["w_fd"])
    nonce = str(cfg["nonce"])
    extra_paths = cfg["extra_paths"]
    work_root = cfg.get("work_root")
    project_root = cfg.get("project_root")
    tests = cfg["tests"]
    try:
        _os.set_inheritable(w_fd, False)
    except OSError:
        pass

    if project_root and work_root and project_root != work_root:
        _proj_src = _os.path.join(project_root, "src")
        _work_src = _os.path.join(work_root, "src")
        _new_path = []
        for _p in _sys.path:
            _ap = _os.path.abspath(_p) if _p else _p
            if _ap == project_root:
                _new_path.append(work_root)
            elif _ap == _proj_src and _os.path.isdir(_work_src):
                _new_path.append(_work_src)
            else:
                _new_path.append(_p)
        _sys.path[:] = _new_path

    for p in extra_paths:
        if p not in _sys.path:
            _sys.path.append(p)

    def _needs_required_args(fn):
        try:
            sig = _inspect.signature(fn)
        except (ValueError, TypeError):
            return False
        for param in sig.parameters.values():
            if param.kind in (
                _inspect.Parameter.POSITIONAL_ONLY,
                _inspect.Parameter.POSITIONAL_OR_KEYWORD,
                _inspect.Parameter.KEYWORD_ONLY,
            ) and param.default is _inspect.Parameter.empty:
                return True
        return False

    def _run_callable(label, fn, out):
        out["run"] += 1
        try:
            if _inspect.iscoroutinefunction(fn):
                _asyncio.run(fn())
            else:
                fn()
        except _SkipTest:
            out["skipped"] += 1
        except AssertionError:
            out["failures"] += 1
            if out["first_problem"] is None:
                out["first_problem"] = (label + "\n" + _tb.format_exc(limit=5))[-800:]
        except BaseException:
            out["errors"] += 1
            if out["first_problem"] is None:
                out["first_problem"] = (label + "\n" + _tb.format_exc(limit=5))[-800:]

    out = {
        "run": 0,
        "failures": 0,
        "errors": 0,
        "skipped": 0,
        "unexpected_successes": 0,
        "load_error": None,
        "unavailable_reason": None,
        "first_problem": None,
    }

    for idx, (mod_name, file_path) in enumerate(tests):
        try:
            load_name = mod_name if mod_name not in _sys.modules else f"__vacant_test_{idx}_{mod_name}"
            spec = _spec_from_file(load_name, file_path)
            if spec is None or spec.loader is None:
                raise ImportError(f"cannot load test file: {file_path}")
            mod = _mod_from_spec(spec)
            _sys.modules[load_name] = mod
            spec.loader.exec_module(mod)
        except BaseException as exc:
            if isinstance(exc, ModuleNotFoundError) and getattr(exc, "name", None) in ("pytest", "_pytest"):
                out["unavailable_reason"] = f"test file requires pytest ({exc}), which is not installed"
                break
            if isinstance(exc, SyntaxError) and getattr(exc, "filename", None) == file_path:
                out["unavailable_reason"] = f"syntax error in original test file: {file_path}"
                break
            out["load_error"] = _tb.format_exc(limit=3)[-800:]
            break

        try:
            suite = _Loader().loadTestsFromModule(mod)
        except BaseException:
            out["load_error"] = _tb.format_exc(limit=3)[-800:]
            break
        res = _Result()
        suite.run(res)
        out["run"] += res.testsRun
        out["failures"] += len(res.failures)
        out["errors"] += len(res.errors)
        out["skipped"] += len(res.skipped)
        out["unexpected_successes"] += len(res.unexpectedSuccesses)
        probs = res.failures + res.errors
        if probs and out["first_problem"] is None:
            out["first_problem"] = (str(probs[0][0]) + "\n" + probs[0][1])[-800:]

        abort_unavail = False
        for name, obj in list(mod.__dict__.items()):
            if not name.startswith("test_"):
                continue
            if not _inspect.isfunction(obj):
                continue
            if getattr(obj, "__module__", None) != mod.__name__:
                continue
            if _needs_required_args(obj):
                out["unavailable_reason"] = f"test {mod_name}.{name} requires fixtures (pytest is not installed)"
                abort_unavail = True
                break
            _run_callable(f"{mod_name}.{name}", obj, out)
        if abort_unavail:
            break

        for cname, cobj in list(mod.__dict__.items()):
            if not cname.startswith("Test"):
                continue
            if not _inspect.isclass(cobj):
                continue
            if getattr(cobj, "__module__", None) != mod.__name__:
                continue
            if issubclass(cobj, _TestCase):
                continue
            method_names = [
                mname for mname, mval in cobj.__dict__.items()
                if mname.startswith("test_") and callable(mval)
            ]
            if not method_names:
                continue
            if _needs_required_args(cobj):
                out["unavailable_reason"] = f"test class {mod_name}.{cname} requires constructor args (pytest is not installed)"
                abort_unavail = True
                break
            for mname in method_names:
                try:
                    inst = cobj()
                except BaseException:
                    out["run"] += 1
                    out["errors"] += 1
                    if out["first_problem"] is None:
                        out["first_problem"] = (f"{mod_name}.{cname}.{mname}\n" + _tb.format_exc(limit=5))[-800:]
                    continue
                meth = getattr(inst, mname)
                if _needs_required_args(meth):
                    out["unavailable_reason"] = f"test {mod_name}.{cname}.{mname} requires fixtures (pytest is not installed)"
                    abort_unavail = True
                    break
                _run_callable(f"{mod_name}.{cname}.{mname}", meth, out)
            if abort_unavail:
                break
        if abort_unavail:
            break

    try:
        _sys.stdout.flush()
        _sys.stderr.flush()
    except BaseException:
        pass

    payload = (nonce + "\n" + _json.dumps(out) + "\n").encode("utf-8")
    view = memoryview(payload)
    written = 0
    while written < len(view):
        n = _os.write(w_fd, view[written:])
        if n <= 0:
            break
        written += n
    try:
        _os.close(w_fd)
    except OSError:
        pass
    _os._exit(0)


_main()
"""


def _has_copy_skip(rel: str) -> bool:
    return any(part in COPY_SKIP for part in pathlib.PurePosixPath(rel).parts)


def _matches_prefix(rel: str, prefixes: set[str]) -> bool:
    if not prefixes:
        return False
    if "." in prefixes or rel in prefixes:
        return True
    parts = pathlib.PurePosixPath(rel).parts
    cur = ""
    for part in parts[:-1]:
        cur = f"{cur}/{part}" if cur else part
        if cur in prefixes:
            return True
    return False


def _scan_files(root: pathlib.Path) -> tuple[list[str], set[str]]:
    """掃描 root 底下的所有一般檔案（跳過 COPY_SKIP 的目錄與檔案、symlink 與特殊檔）。
    同時回傳無法列出內容的目錄相對路徑集合。"""
    out: list[str] = []
    unreadable_dirs: set[str] = set()

    def _walk(cur: pathlib.Path, rel_prefix: str) -> None:
        try:
            entries = sorted(os.scandir(cur), key=lambda e: e.name)
        except OSError:
            unreadable_dirs.add(rel_prefix or ".")
            return
        for entry in entries:
            name = entry.name
            if name in COPY_SKIP:
                continue
            rel = f"{rel_prefix}/{name}" if rel_prefix else name
            try:
                st = entry.stat(follow_symlinks=False)
            except OSError:
                continue
            mode = st.st_mode
            if stat.S_ISLNK(mode):
                continue
            if stat.S_ISDIR(mode):
                _walk(cur / name, rel)
            elif stat.S_ISREG(mode):
                out.append(rel)

    _walk(root, "")
    return sorted(out), unreadable_dirs


def _files(root: pathlib.Path) -> list[str]:
    return _scan_files(root)[0]


def _through_symlink(root: pathlib.Path, rel: str) -> bool:
    """root/rel 的路徑上（含最後一段）有沒有 symlink。root 本身不算。"""
    p = root
    for part in pathlib.PurePosixPath(rel).parts:
        p = p / part
        try:
            if p.is_symlink():
                return True
        except OSError:
            return True
    return False


def _open_reg_readonly(path: pathlib.Path) -> tuple[int, os.stat_result] | None:
    """以 O_NOFOLLOW | O_NONBLOCK 開啟一般檔案，確認不是 symlink／FIFO／目錄。"""
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    try:
        fd = os.open(str(path), flags)
    except OSError:
        return None
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode):
            os.close(fd)
            return None
        return fd, st
    except OSError:
        os.close(fd)
        return None


def _sha256_file(path: pathlib.Path) -> str | None:
    opened = _open_reg_readonly(path)
    if opened is None:
        return None
    fd, _ = opened
    h = hashlib.sha256()
    try:
        with os.fdopen(fd, "rb") as f:
            while True:
                chunk = f.read(_CHUNK_SIZE)
                if not chunk:
                    break
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return None


def _copy_reg_file(src: pathlib.Path, dst: pathlib.Path, mode: int = 0o600, *,
                   preserve_exec: bool = False) -> bool:
    opened = _open_reg_readonly(src)
    if opened is None:
        return False
    fd, st = opened
    try:
        dst.parent.mkdir(parents=True, exist_ok=True)
        with os.fdopen(fd, "rb") as src_f:
            fd = -1
            with dst.open("wb") as dst_f:
                while True:
                    chunk = src_f.read(_CHUNK_SIZE)
                    if not chunk:
                        break
                    dst_f.write(chunk)
        final_mode = (mode | 0o100) if (preserve_exec and (st.st_mode & 0o100)) else mode
        os.chmod(dst, final_mode)
        return True
    except OSError:
        if fd >= 0:
            try:
                os.close(fd)
            except OSError:
                pass
        try:
            dst.unlink(missing_ok=True)
        except OSError:
            pass
        return False


def _rmtree_force(path: pathlib.Path) -> None:
    """清理暫存目錄：先恢復目錄權限（不跟隨 symlink），避免 0o555／0o000 目錄殘留。"""
    if not path.exists() and not path.is_symlink():
        return
    if path.is_symlink() or not path.is_dir():
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass
        return
    for dp, dns, fns in os.walk(path, topdown=True, followlinks=False):
        try:
            os.chmod(dp, 0o700)
        except OSError:
            pass
        for name in list(dns) + list(fns):
            p = pathlib.Path(dp) / name
            try:
                if not p.is_symlink():
                    os.chmod(p, 0o700 if p.is_dir() else 0o600)
            except OSError:
                pass
    shutil.rmtree(path, ignore_errors=True)


def _kill_group_and_wait(proc: subprocess.Popen) -> None:
    """殺掉整個獨立 session／行程群組，並短暫等待確認沒有殘留成員。"""
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError, OSError):
        pass
    try:
        proc.wait(timeout=2.0)
    except Exception:  # noqa: BLE001
        pass
    deadline = time.monotonic() + 0.5
    while time.monotonic() < deadline:
        try:
            os.killpg(proc.pid, 0)
        except OSError:
            break
        time.sleep(0.01)


def _read_all_fd(fd: int) -> bytes:
    chunks: list[bytes] = []
    try:
        while True:
            data = os.read(fd, _CHUNK_SIZE)
            if not data:
                break
            chunks.append(data)
    except OSError:
        pass
    finally:
        try:
            os.close(fd)
        except OSError:
            pass
    return b"".join(chunks)


def _is_python_test(rel: str) -> bool:
    name = rel.rsplit("/", 1)[-1]
    return any(fnmatch.fnmatchcase(name, p) for p in PATTERNS)


def _is_universal_test(rel: str) -> bool:
    parts = pathlib.PurePosixPath(rel).parts
    if any(d in _UNIVERSAL_TEST_DIRS for d in parts[:-1]):
        return True
    name = parts[-1]
    return any(fnmatch.fnmatchcase(name, p) for p in _UNIVERSAL_TEST_NAME_PATTERNS)


def find_tests(root: pathlib.Path) -> list[str]:
    return [r for r in _files(root) if _is_python_test(r)]


def _normalize_protect_pattern(pat: str, project: pathlib.Path) -> str:
    raw = str(pat).strip().replace("\\", "/")
    if not raw:
        raise ValueError("--protect pattern must not be empty")
    p = pathlib.Path(raw)
    if p.is_absolute():
        try:
            raw = p.resolve().relative_to(project.resolve()).as_posix()
        except ValueError as exc:
            raise ValueError(f"--protect pattern must stay inside project: {pat!r}") from exc
    while raw.startswith("./"):
        raw = raw[2:]
    raw = raw.rstrip("/")
    if not raw or raw == ".":
        raise ValueError(f"--protect pattern must name a path inside project: {pat!r}")
    parts = pathlib.PurePosixPath(raw).parts
    if ".." in parts:
        raise ValueError(f"--protect pattern must stay inside project: {pat!r}")
    return "/".join(parts)


def _glob_to_regex(pat: str) -> re.Pattern[str]:
    """將支援 `**` 的 POSIX glob 轉成完整比對正則。"""
    i = 0
    n = len(pat)
    out = ["^"]
    while i < n:
        c = pat[i]
        if c == "*":
            if i + 1 < n and pat[i + 1] == "*":
                if i + 2 < n and pat[i + 2] == "/":
                    out.append("(?:.+/)?")
                    i += 3
                else:
                    out.append(".*")
                    i += 2
            else:
                out.append("[^/]*")
                i += 1
        elif c == "?":
            out.append("[^/]")
            i += 1
        elif c == "[":
            j = i + 1
            if j < n and pat[j] in ("!", "^"):
                j += 1
            if j < n and pat[j] == "]":
                j += 1
            while j < n and pat[j] != "]":
                j += 1
            if j >= n:
                out.append(re.escape(c))
                i += 1
            else:
                stuff = pat[i + 1:j]
                if stuff.startswith("!"):
                    stuff = "^" + stuff[1:]
                out.append(f"[{stuff}]")
                i = j + 1
        else:
            out.append(re.escape(c))
            i += 1
    out.append("$")
    return re.compile("".join(out))


def _match_protect_pattern(rel: str, norm_pat: str) -> bool:
    has_glob = any(ch in norm_pat for ch in "*?[")
    if not has_glob:
        return rel == norm_pat or rel.startswith(norm_pat + "/")
    rx = _glob_to_regex(norm_pat)
    if "/" not in norm_pat:
        return bool(rx.match(rel) or rx.match(rel.rsplit("/", 1)[-1]))
    return bool(rx.match(rel))


def find_protected(root: pathlib.Path, *, kind: str = "none",
                   protect: Sequence[str] | None = None,
                   _all_files: list[str] | None = None) -> list[str]:
    """列出開始時應受保護（驗收前還原原位元組、不寫回 agent 改動）的相對路徑。"""
    root = root.resolve()
    files = _all_files if _all_files is not None else _files(root)
    files_set = set(files)
    out: set[str] = {r for r in files if _is_universal_test(r)}
    for mf in _MANIFEST_BY_KIND.get(kind, ()):
        if mf in files_set:
            out.add(mf)
    if protect:
        norm_pats = [_normalize_protect_pattern(p, root) for p in protect]
        for r in files:
            if any(_match_protect_pattern(r, np) for np in norm_pats):
                out.add(r)
    return sorted(out)


def _is_exec_file(p: pathlib.Path) -> bool:
    try:
        return p.is_file() and os.access(str(p), os.X_OK)
    except OSError:
        return False


def resolve_python(project: pathlib.Path | None = None) -> str:
    """依優先順序解析專案用的 Python 直譯器（不 dereference venv symlink，保留 pyvenv.cfg 生效）：
    1. `$VIRTUAL_ENV/bin/python`（或 `python3`）
    2. `<project>/.venv/bin/python`（或 `python3`）
    3. `<project>/venv/bin/python`（或 `python3`）
    4. `PATH` 上的 `python3`／`python`
    5. `sys.executable`（最後手段）
    """
    venv_env = (os.environ.get("VIRTUAL_ENV") or "").strip()
    if venv_env:
        base = pathlib.Path(os.path.abspath(venv_env))
        for name in ("python", "python3"):
            cand = base / "bin" / name
            if _is_exec_file(cand):
                return str(cand)

    if project is not None:
        proj = project.resolve()
        for vdir in (".venv", "venv"):
            for name in ("python", "python3"):
                cand = proj / vdir / "bin" / name
                if _is_exec_file(cand):
                    return str(cand)

    for name in ("python3", "python"):
        found = shutil.which(name)
        if found and _is_exec_file(pathlib.Path(found)):
            return found

    return sys.executable


def _venv_root_for(python_exe: str | None) -> str | None:
    if not python_exe:
        return None
    p = pathlib.Path(os.path.abspath(python_exe))
    if p.parent.name == "bin":
        root = p.parent.parent
        if (root / "pyvenv.cfg").is_file():
            return str(root)
        env_v = (os.environ.get("VIRTUAL_ENV") or "").strip()
        if env_v and os.path.abspath(env_v) == str(root):
            return str(root)
    return None


def _clean_env(home: pathlib.Path, *, python_exe: str | None = None,
               work_root: pathlib.Path | None = None) -> dict[str, str]:
    path_val = os.environ.get("PATH", "/usr/bin:/bin")
    if python_exe:
        py_bin = os.path.dirname(os.path.abspath(python_exe))
        parts = path_val.split(os.pathsep) if path_val else []
        if py_bin and (not parts or parts[0] != py_bin):
            path_val = os.pathsep.join([py_bin, *parts])
    env: dict[str, str] = {
        "PATH": path_val,
        "HOME": str(home),
        "LANG": "C.UTF-8",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONHASHSEED": "0",
    }
    vroot = _venv_root_for(python_exe)
    if vroot:
        env["VIRTUAL_ENV"] = vroot
    raw_pp = os.environ.get("PYTHONPATH")
    if raw_pp:
        work_abs = str(work_root.resolve()) if work_root is not None else None
        safe_pp: list[str] = []
        for entry in raw_pp.split(os.pathsep):
            if not entry or not os.path.isabs(entry):
                continue
            ep = os.path.abspath(entry)
            if work_abs and (ep == work_abs or ep.startswith(work_abs + os.sep)):
                continue
            safe_pp.append(ep)
        if safe_pp:
            env["PYTHONPATH"] = os.pathsep.join(safe_pp)
    return env


@dataclasses.dataclass
class _Snapshot:
    root: pathlib.Path
    files: dict[str, str]             # rel -> sha256 hex of bytes stored in root/rel
    modes: dict[str, int]             # rel -> original st_mode permission bits (0o777)
    symlinks: set[str]                # rel paths in ws that were symlinks
    unreadable_dirs: set[str]         # rel dirs in ws that could not be listed
    unreadable_files: set[str]        # rel files in ws that could not be read
    special_files: set[str]           # rel non-reg, non-dir, non-symlink paths (FIFO/socket/dev)


def _snapshot_workspace(ws: pathlib.Path, dest: pathlib.Path) -> _Snapshot:
    """將工作區拍成只含一般檔案的私密快照（不跟隨 symlink、跳過特殊檔與 COPY_SKIP）。"""
    dest.mkdir(parents=True, exist_ok=True)
    os.chmod(dest, 0o700)
    files: dict[str, str] = {}
    modes: dict[str, int] = {}
    symlinks: set[str] = set()
    unreadable_dirs: set[str] = set()
    unreadable_files: set[str] = set()
    special_files: set[str] = set()

    def _walk(cur: pathlib.Path, rel_prefix: str) -> None:
        try:
            entries = sorted(os.scandir(cur), key=lambda e: e.name)
        except OSError:
            unreadable_dirs.add(rel_prefix or ".")
            return
        for entry in entries:
            name = entry.name
            if name in COPY_SKIP:
                continue
            rel = f"{rel_prefix}/{name}" if rel_prefix else name
            try:
                st = entry.stat(follow_symlinks=False)
            except OSError:
                unreadable_files.add(rel)
                continue
            mode = st.st_mode
            if stat.S_ISLNK(mode):
                symlinks.add(rel)
                continue
            if stat.S_ISDIR(mode):
                _walk(cur / name, rel)
                continue
            if not stat.S_ISREG(mode):
                special_files.add(rel)
                continue
            opened = _open_reg_readonly(cur / name)
            if opened is None:
                unreadable_files.add(rel)
                continue
            fd, st2 = opened
            out_p = dest / rel
            h = hashlib.sha256()
            try:
                out_p.parent.mkdir(parents=True, exist_ok=True)
                with os.fdopen(fd, "rb") as src_f:
                    fd = -1
                    with out_p.open("wb") as dst_f:
                        while True:
                            chunk = src_f.read(_CHUNK_SIZE)
                            if not chunk:
                                break
                            h.update(chunk)
                            dst_f.write(chunk)
                os.chmod(out_p, 0o600)
                files[rel] = h.hexdigest()
                modes[rel] = stat.S_IMODE(st2.st_mode) & 0o777
            except OSError:
                if fd >= 0:
                    try:
                        os.close(fd)
                    except OSError:
                        pass
                try:
                    out_p.unlink(missing_ok=True)
                except OSError:
                    pass
                unreadable_files.add(rel)

    _walk(ws, "")
    return _Snapshot(
        root=dest,
        files=files,
        modes=modes,
        symlinks=symlinks,
        unreadable_dirs=unreadable_dirs,
        unreadable_files=unreadable_files,
        special_files=special_files,
    )


def _detect_tampered(snap: _Snapshot, originals: dict[str, bytes]) -> list[str]:
    tampered: list[str] = []
    for rel, want in sorted(originals.items()):
        if rel not in snap.files:
            tampered.append(rel)
            continue
        if snap.files[rel] != hashlib.sha256(want).hexdigest():
            tampered.append(rel)
    return tampered


@dataclasses.dataclass
class _WritePlan:
    added: list[str]
    modified: list[str]
    deleted: list[str]
    skipped: list[str]
    dirs_to_remove: list[str]         # deepest-first relative dir paths safe to rmdir
    before_files: set[str]


def _can_remove_dir(project: pathlib.Path, rel: str, deletes: set[str]) -> list[str] | None:
    """檢查 project/rel 目錄底下是否只包含即將刪除的一般檔案（無 symlink、COPY_SKIP、保護檔、特殊檔或不可讀目錄）。
    安全時回傳由深到淺的相對目錄清單（含 rel 本身），否則回傳 None。"""
    dirs_out: list[str] = []

    def _check(cur: pathlib.Path, cur_rel: str) -> bool:
        try:
            entries = sorted(os.scandir(cur), key=lambda e: e.name)
        except OSError:
            return False
        for entry in entries:
            name = entry.name
            if name in COPY_SKIP:
                return False
            child_rel = f"{cur_rel}/{name}"
            try:
                st = entry.stat(follow_symlinks=False)
            except OSError:
                return False
            mode = st.st_mode
            if stat.S_ISLNK(mode):
                return False
            if stat.S_ISDIR(mode):
                if not _check(cur / name, child_rel):
                    return False
            elif stat.S_ISREG(mode):
                if child_rel not in deletes:
                    return False
            else:
                return False
        dirs_out.append(cur_rel)
        return True

    if not _check(project / rel, rel):
        return None
    return dirs_out


def _plan_write_back(project: pathlib.Path, snap: _Snapshot, protected: set[str]) -> _WritePlan:
    """規劃寫回專案的所有操作（唯讀掃描 project，不做任何變更）。"""
    before_list, proj_unreadable = _scan_files(project)
    before = set(before_list)
    after = set(snap.files)
    ws_unsafe = snap.symlinks | snap.unreadable_dirs | snap.unreadable_files | snap.special_files

    deletes: list[str] = []
    delete_skips: set[str] = set()
    for rel in sorted(before - after - protected):
        if _has_copy_skip(rel):
            continue
        if (_matches_prefix(rel, ws_unsafe)
                or _matches_prefix(rel, proj_unreadable)
                or _through_symlink(project, rel)):
            delete_skips.add(rel)
            continue
        deletes.append(rel)
    delete_set = set(deletes)

    added: list[str] = []
    modified: list[str] = []
    write_skips: set[str] = set()
    dirs_to_remove: list[str] = []
    dirs_seen: set[str] = set()

    for rel in sorted(after - protected):
        if _has_copy_skip(rel):
            continue
        if _through_symlink(project, rel) or _matches_prefix(rel, proj_unreadable):
            write_skips.add(rel)
            continue
        # 檢查每一層父路徑：不能是無法移除的非目錄（例如受保護檔案、特殊檔、或沒被排進刪除的既有檔案）
        parts = pathlib.PurePosixPath(rel).parts
        parent_conflict = False
        cur_p = project
        cur_rel = ""
        for part in parts[:-1]:
            cur_p = cur_p / part
            cur_rel = f"{cur_rel}/{part}" if cur_rel else part
            try:
                st_p = cur_p.lstat()
            except FileNotFoundError:
                break
            except OSError:
                parent_conflict = True
                break
            if stat.S_ISLNK(st_p.st_mode):
                parent_conflict = True
                break
            if not stat.S_ISDIR(st_p.st_mode):
                if not (stat.S_ISREG(st_p.st_mode) and cur_rel in delete_set):
                    parent_conflict = True
                    break
        if parent_conflict:
            write_skips.add(rel)
            continue

        dst = project / rel
        try:
            st_dst = dst.lstat()
        except FileNotFoundError:
            st_dst = None
        except OSError:
            write_skips.add(rel)
            continue

        if st_dst is not None:
            if stat.S_ISLNK(st_dst.st_mode):
                write_skips.add(rel)
                continue
            if stat.S_ISDIR(st_dst.st_mode):
                removable = _can_remove_dir(project, rel, delete_set)
                if removable is None:
                    write_skips.add(rel)
                    continue
                for d_rel in removable:
                    if d_rel not in dirs_seen:
                        dirs_seen.add(d_rel)
                        dirs_to_remove.append(d_rel)
                added.append(rel)
                continue
            if not stat.S_ISREG(st_dst.st_mode):
                write_skips.add(rel)
                continue
            dst_sha = _sha256_file(dst)
            if dst_sha is None:
                write_skips.add(rel)
                continue
            if dst_sha == snap.files[rel]:
                continue
            modified.append(rel)
        else:
            added.append(rel)

    dirs_to_remove.sort(key=lambda r: (-len(pathlib.PurePosixPath(r).parts), r))
    return _WritePlan(
        added=added,
        modified=modified,
        deleted=deletes,
        skipped=sorted(delete_skips | write_skips),
        dirs_to_remove=dirs_to_remove,
        before_files=before,
    )


def _atomic_write_from_file(src: pathlib.Path, dst: pathlib.Path, mode: int | None) -> None:
    """經由同目錄私密暫存檔＋os.replace 原子寫入 dst（不覆寫硬連結 inode，也不寫進既有目錄）。"""
    fd, tmp_name = tempfile.mkstemp(prefix=".vacant-tmp-", dir=str(dst.parent))
    tmp_path = pathlib.Path(tmp_name)
    try:
        with os.fdopen(fd, "wb") as dst_f:
            fd = -1
            with src.open("rb") as src_f:
                while True:
                    chunk = src_f.read(_CHUNK_SIZE)
                    if not chunk:
                        break
                    dst_f.write(chunk)
        if mode is not None:
            os.chmod(tmp_path, mode & 0o777)
        if dst.is_symlink():
            raise OSError(f"refusing to replace symlink: {dst}")
        os.replace(tmp_path, dst)
    except BaseException:
        if fd >= 0:
            try:
                os.close(fd)
            except OSError:
                pass
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise


def _apply_write_plan(project: pathlib.Path, snap: _Snapshot, plan: _WritePlan,
                      backup_dir: pathlib.Path) -> dict[str, list[str]]:
    """套用已驗證的寫回計畫；任何非預期錯誤都會回滾，維持專案不變。"""
    # 套用前驗證所有待寫檔案的快照雜湊仍完整無誤
    for rel in plan.added + plan.modified:
        if _sha256_file(snap.root / rel) != snap.files.get(rel):
            all_planned = sorted(set(plan.skipped) | set(plan.added) | set(plan.modified) | set(plan.deleted))
            return {"added": [], "modified": [], "deleted": [], "skipped": all_planned}

    backup_dir.mkdir(parents=True, exist_ok=True)
    os.chmod(backup_dir, 0o700)
    undo: list[Callable[[], None]] = []
    bkp_seq = 0

    def _backup_existing(target: pathlib.Path) -> tuple[pathlib.Path, int]:
        nonlocal bkp_seq
        bkp_seq += 1
        st = target.lstat()
        old_mode = stat.S_IMODE(st.st_mode) & 0o777
        bkp = backup_dir / f"bkp_{bkp_seq}"
        if not _copy_reg_file(target, bkp, mode=0o600):
            raise OSError(f"cannot back up {target}")
        return bkp, old_mode

    try:
        # 1. 先刪除（避免檔案變目錄時的 FileExistsError，也先清空可移除的目錄）
        for rel in plan.deleted:
            target = project / rel
            bkp, old_mode = _backup_existing(target)
            target.unlink()
            undo.append(lambda t=target, b=bkp, m=old_mode: _atomic_write_from_file(b, t, m))

        # 2. 移除即將改為一般檔案的空目錄（由深到淺）
        for rel_dir in plan.dirs_to_remove:
            d = project / rel_dir
            old_mode = stat.S_IMODE(d.lstat().st_mode) & 0o777
            d.rmdir()

            def _restore_dir(p: pathlib.Path = d, m: int = old_mode) -> None:
                p.mkdir(exist_ok=True)
                os.chmod(p, m)

            undo.append(_restore_dir)

        # 3. 寫入新增與修改的檔案（先補齊缺的父目錄並記下回滾動作）
        modified_set = set(plan.modified)
        for rel in sorted(plan.added + plan.modified):
            dst = project / rel
            src = snap.root / rel
            missing_dirs: list[pathlib.Path] = []
            cur = dst.parent
            while cur != project:
                if cur.is_symlink():
                    raise OSError(f"unexpected symlink ancestor: {cur}")
                if cur.exists():
                    break
                missing_dirs.append(cur)
                cur = cur.parent
            for md in reversed(missing_dirs):
                md.mkdir()
                undo.append(lambda p=md: p.rmdir())

            if rel in modified_set:
                bkp, old_mode = _backup_existing(dst)
                _atomic_write_from_file(src, dst, snap.modes.get(rel))
                undo.append(lambda t=dst, b=bkp, m=old_mode: _atomic_write_from_file(b, t, m))
            else:
                _atomic_write_from_file(src, dst, snap.modes.get(rel))
                undo.append(lambda t=dst: t.unlink(missing_ok=True))

        return {
            "added": list(plan.added),
            "modified": list(plan.modified),
            "deleted": list(plan.deleted),
            "skipped": list(plan.skipped),
        }
    except Exception:  # noqa: BLE001
        for fn in reversed(undo):
            try:
                fn()
            except Exception:  # noqa: BLE001
                pass
        all_planned = sorted(set(plan.skipped) | set(plan.added) | set(plan.modified) | set(plan.deleted))
        return {"added": [], "modified": [], "deleted": [], "skipped": all_planned}
    finally:
        _rmtree_force(backup_dir)


def _write_back(project: pathlib.Path, ws: pathlib.Path | _Snapshot, protected: set[str], *,
                _plan: _WritePlan | None = None,
                _backup_root: pathlib.Path | None = None) -> dict[str, list[str]]:
    tmp_dir: pathlib.Path | None = None
    try:
        if isinstance(ws, _Snapshot):
            snap = ws
        else:
            tmp_dir = pathlib.Path(tempfile.mkdtemp(prefix="vsnap-"))
            snap = _snapshot_workspace(ws, tmp_dir / "s")
        plan = _plan if _plan is not None else _plan_write_back(project, snap, protected)
        bkp_base = _backup_root if _backup_root is not None else pathlib.Path(tempfile.mkdtemp(prefix="vbkp-"))
        try:
            return _apply_write_plan(project, snap, plan, bkp_base / f"bkp-{secrets.token_hex(6)}")
        finally:
            if _backup_root is None:
                _rmtree_force(bkp_base)
    except Exception:  # noqa: BLE001
        return {"added": [], "modified": [], "deleted": [], "skipped": []}
    finally:
        if tmp_dir is not None:
            _rmtree_force(tmp_dir)


def _restore_test_file(work: pathlib.Path, rel: str, want: bytes) -> None:
    """在驗收副本 work 裡強制還原單一原測試檔（處理路徑上被換成檔案、目錄、symlink 或唯讀權限的情況）。"""
    p = work
    for part in pathlib.PurePosixPath(rel).parts[:-1]:
        p = p / part
        try:
            st = p.lstat()
        except FileNotFoundError:
            p.mkdir(mode=0o700)
            continue
        if stat.S_ISLNK(st.st_mode) or not stat.S_ISDIR(st.st_mode):
            p.unlink()
            p.mkdir(mode=0o700)
        else:
            try:
                os.chmod(p, 0o700)
            except OSError:
                pass
    f = work / rel
    try:
        st_f = f.lstat()
    except FileNotFoundError:
        st_f = None
    if st_f is not None:
        if stat.S_ISDIR(st_f.st_mode) and not stat.S_ISLNK(st_f.st_mode):
            _rmtree_force(f)
        else:
            f.unlink()
    f.write_bytes(want)
    os.chmod(f, 0o600)


def _populate_acceptance_work(work: pathlib.Path, originals: dict[str, bytes], snap: _Snapshot,
                              project: pathlib.Path | None, plan: _WritePlan | None) -> None:
    """組裝驗收目錄 work：完全不含 symlink，且與實際會寫回專案的檔案集合一致，最後覆寫原測試檔。"""
    work.mkdir(parents=True, exist_ok=True)
    os.chmod(work, 0o700)
    protected = set(originals)
    if project is not None and plan is not None:
        deleted_set = set(plan.deleted)
        written_set = set(plan.added) | set(plan.modified)
        # 1. 保留專案中未被刪除、未被改寫、且非測試檔的一般檔案（包含因安全原因跳過刪除者）
        for rel in sorted(plan.before_files - deleted_set - written_set - protected):
            _copy_reg_file(project / rel, work / rel, mode=0o600, preserve_exec=True)
        # 2. 放入計畫中真正會寫回的新增／修改檔案（跳過不安全而不會寫回的檔案）
        for rel in sorted(written_set):
            m = 0o700 if (snap.modes.get(rel, 0) & 0o100) else 0o600
            _copy_reg_file(snap.root / rel, work / rel, mode=m)
    else:
        for rel in sorted(snap.files):
            if rel not in protected:
                m = 0o700 if (snap.modes.get(rel, 0) & 0o100) else 0o600
                _copy_reg_file(snap.root / rel, work / rel, mode=m)
    # 3. 最後以開始時的原始測試檔覆寫
    for rel, want in sorted(originals.items()):
        _restore_test_file(work, rel, want)


@dataclasses.dataclass(frozen=True)
class AcceptanceSpec:
    kind: str                          # check | python_unittest | python_pytest | python_bare | npm | cargo | go | none
    command: str | None
    argv: tuple[str, ...] | None = None
    protected: tuple[str, ...] = ()
    reason: str | None = None
    interpreter: str | None = None
    pinned_script: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "kind": self.kind,
            "command": self.command,
            "protected": list(self.protected),
            "reason": self.reason,
        }
        if self.interpreter is not None:
            d["interpreter"] = self.interpreter
        if self.pinned_script is not None:
            d["pinned_script"] = self.pinned_script
        return d


@dataclasses.dataclass(frozen=True)
class _PyTestInspection:
    has_pytest_style: bool
    has_unittest: bool
    syntax_error: str | None = None


def _iter_module_stmts(stmts: list[ast.stmt]) -> list[ast.stmt]:
    """展開模組層（不含函式與類別內部）的 if／try 區塊，以偵測條件定義的測試。"""
    out: list[ast.stmt] = []
    for st in stmts:
        out.append(st)
        if isinstance(st, ast.If):
            out.extend(_iter_module_stmts(st.body))
            out.extend(_iter_module_stmts(st.orelse))
        elif isinstance(st, ast.Try):
            out.extend(_iter_module_stmts(st.body))
            out.extend(_iter_module_stmts(st.orelse))
            out.extend(_iter_module_stmts(st.finalbody))
            for h in st.handlers:
                out.extend(_iter_module_stmts(h.body))
    return out


def _inspect_python_tests(originals: dict[str, bytes]) -> _PyTestInspection:
    """以靜態 AST 檢查原測試檔是純 unittest 還是含 pytest 風格（裸 def test_* 或非 TestCase 測試類別）。"""
    has_pytest_style = False
    has_unittest = False

    for rel, raw in sorted(originals.items()):
        try:
            tree = ast.parse(raw, filename=rel)
        except SyntaxError as e:
            return _PyTestInspection(
                has_pytest_style=False,
                has_unittest=False,
                syntax_error=f"{rel}:{e.lineno or 0}: {e.msg}",
            )

        stmts = _iter_module_stmts(tree.body)
        testcase_names: set[str] = {"TestCase", "IsolatedAsyncioTestCase", "FunctionTestCase"}
        for st in stmts:
            if isinstance(st, ast.ImportFrom) and st.module in (
                "unittest", "unittest.case", "unittest.async_case"
            ):
                for alias in st.names:
                    if alias.name in testcase_names or alias.name.endswith("TestCase"):
                        testcase_names.add(alias.asname or alias.name)

        def _base_is_testcase(expr: ast.expr, local_tc: set[str]) -> bool:
            if isinstance(expr, ast.Name):
                return expr.id in testcase_names or expr.id in local_tc or expr.id.endswith("TestCase")
            if isinstance(expr, ast.Attribute):
                return expr.attr in testcase_names or expr.attr.endswith("TestCase")
            if isinstance(expr, ast.Subscript):
                return _base_is_testcase(expr.value, local_tc)
            return False

        classes = [st for st in stmts if isinstance(st, ast.ClassDef)]
        local_tc: set[str] = set()
        changed = True
        while changed:
            changed = False
            for cls in classes:
                if cls.name in local_tc:
                    continue
                if any(_base_is_testcase(b, local_tc) for b in cls.bases):
                    local_tc.add(cls.name)
                    changed = True

        for st in stmts:
            if isinstance(st, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if st.name.startswith("test_"):
                    has_pytest_style = True
                elif st.name == "load_tests":
                    has_unittest = True
            elif isinstance(st, ast.ClassDef):
                has_test_methods = any(
                    isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef)) and m.name.startswith("test_")
                    for m in st.body
                )
                if st.name in local_tc:
                    has_unittest = True
                elif st.name.startswith("Test") and has_test_methods:
                    has_pytest_style = True

    return _PyTestInspection(has_pytest_style=has_pytest_style, has_unittest=has_unittest)


def _pytest_available(python_exe: str | None = None) -> bool:
    """檢查測試用直譯器在 `-B` 模式下（排除 cwd／"" 以防專案內假 pytest.py 遮蔽）能否匯入 pytest。"""
    exe = python_exe or sys.executable
    probe = (
        "import importlib.util, os, sys; "
        "cwd = os.path.abspath(os.getcwd()); "
        "sys.path[:] = [p for p in sys.path if p not in ('', '.', cwd)]; "
        "sys.exit(0 if importlib.util.find_spec('pytest') else 1)"
    )
    try:
        cp = subprocess.run(
            [exe, "-B", "-c", probe],
            cwd=tempfile.gettempdir(),
            env=_clean_env(pathlib.Path(tempfile.gettempdir()), python_exe=exe),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=10.0,
        )
        return cp.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def _has_reg_file(path: pathlib.Path) -> bool:
    opened = _open_reg_readonly(path)
    if opened is None:
        return False
    fd, _ = opened
    try:
        os.close(fd)
    except OSError:
        pass
    return True


def _npm_test_script(project: pathlib.Path) -> str | None:
    opened = _open_reg_readonly(project / "package.json")
    if opened is None:
        return None
    fd, _ = opened
    try:
        with os.fdopen(fd, "rb") as f:
            raw = f.read(1 << 20)
        data = json.loads(raw.decode("utf-8"))
    except (OSError, ValueError, UnicodeDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    scripts = data.get("scripts")
    if not isinstance(scripts, dict):
        return None
    test_cmd = scripts.get("test")
    if not isinstance(test_cmd, str) or not test_cmd.strip():
        return None
    if _NPM_DEFAULT_TEST_MARKER in test_cmd:
        return None
    return test_cmd.strip()


def _has_npm_test_script(project: pathlib.Path) -> bool:
    return _npm_test_script(project) is not None


def detect_acceptance(project: pathlib.Path, *, check: str | None = None,
                      originals: dict[str, bytes] | None = None,
                      protect: Sequence[str] | None = None) -> AcceptanceSpec:
    """依固定優先順序選擇驗收種類：--check ＞ Python 測試檔 ＞ package.json ＞ Cargo.toml ＞ go.mod ＞ none。
    同時於任務開始時鎖定驗收定義與受保護檔案清單（跨生態系測試檔、manifest 與使用者 `--protect`）。"""
    project = project.resolve()
    all_files = _files(project)
    extra_orig = set(originals) if originals is not None else set()
    py_orig: dict[str, bytes]
    if originals is not None:
        py_orig = {rel: raw for rel, raw in originals.items() if _is_python_test(rel)}
    else:
        py_orig = {rel: (project / rel).read_bytes() for rel in all_files if _is_python_test(rel)}

    def _prot(kind: str) -> tuple[str, ...]:
        base = set(find_protected(project, kind=kind, protect=protect, _all_files=all_files))
        base |= extra_orig
        return tuple(sorted(base))

    if check is not None:
        cmd = check.strip()
        if not cmd:
            raise ValueError("--check command must not be empty")
        return AcceptanceSpec(kind="check", command=cmd, argv=None, protected=_prot("check"))

    if py_orig:
        py_exe = resolve_python(project)
        insp = _inspect_python_tests(py_orig)
        if insp.syntax_error is not None:
            return AcceptanceSpec(
                kind="python_unittest",
                command=f"{py_exe} -B (unittest)",
                protected=_prot("python_unittest"),
                reason=f"syntax error in original test file: {insp.syntax_error}",
                interpreter=py_exe,
            )
        if insp.has_pytest_style:
            if _pytest_available(py_exe):
                return AcceptanceSpec(
                    kind="python_pytest",
                    command=f"{py_exe} -B -m pytest -q -rN",
                    protected=_prot("python_pytest"),
                    interpreter=py_exe,
                )
            return AcceptanceSpec(
                kind="python_bare",
                command=f"{py_exe} -B (stdlib test runner)",
                protected=_prot("python_bare"),
                interpreter=py_exe,
            )
        return AcceptanceSpec(
            kind="python_unittest",
            command=f"{py_exe} -B (unittest)",
            protected=_prot("python_unittest"),
            interpreter=py_exe,
        )

    missing: list[str] = []
    npm_script = _npm_test_script(project)
    if npm_script is not None:
        if shutil.which("npm"):
            return AcceptanceSpec(
                kind="npm",
                command="npm test",
                argv=("npm", "test"),
                protected=_prot("npm"),
                pinned_script=npm_script,
            )
        missing.append("package.json has a \"test\" script, but 'npm' was not found on PATH")

    if _has_reg_file(project / "Cargo.toml"):
        if shutil.which("cargo"):
            return AcceptanceSpec(kind="cargo", command="cargo test", argv=("cargo", "test"), protected=_prot("cargo"))
        missing.append("Cargo.toml found, but 'cargo' was not found on PATH")

    if _has_reg_file(project / "go.mod"):
        if shutil.which("go"):
            return AcceptanceSpec(kind="go", command="go test ./...", argv=("go", "test", "./..."), protected=_prot("go"))
        missing.append("go.mod found, but 'go' was not found on PATH")

    return AcceptanceSpec(
        kind="none",
        command=None,
        argv=None,
        protected=_prot("none"),
        reason="; ".join(missing) if missing else None,
    )


def _parse_runner_output(raw: bytes, nonce: str, *,
                         allow_unavailable: bool = False) -> tuple[dict[str, Any] | None, str | None]:
    """嚴格驗證並解析 runner 經獨立管線送回的結果；任何格式異常皆回失敗。"""
    if not raw:
        return None, "runner_no_output"
    try:
        text = raw.decode("utf-8", "strict")
    except UnicodeDecodeError:
        return None, "runner_bad_output"
    lines = [ln for ln in text.splitlines() if ln]
    if len(lines) != 2 or not hmac.compare_digest(lines[0], nonce):
        return None, "runner_bad_output"
    try:
        data = json.loads(lines[1])
    except (ValueError, TypeError):
        return None, "runner_bad_output"
    if not isinstance(data, dict):
        return None, "runner_bad_output"
    for k in _RESULT_KEYS:
        v = data.get(k)
        if not isinstance(v, int) or isinstance(v, bool) or v < 0:
            return None, "runner_bad_output"
    le = data.get("load_error")
    fp = data.get("first_problem")
    if le is not None and not isinstance(le, str):
        return None, "runner_bad_output"
    if fp is not None and not isinstance(fp, str):
        return None, "runner_bad_output"
    if allow_unavailable:
        ur = data.get("unavailable_reason")
        if ur is not None and not isinstance(ur, str):
            return None, "runner_bad_output"
    return data, None


def _parse_pytest_pipe(raw: bytes, nonce: str) -> tuple[dict[str, Any] | None, str | None]:
    """嚴格驗證並解析 _PYTEST_RUNNER 經獨立管線送回的退出碼與狀態。"""
    if not raw:
        return None, "runner_no_output"
    try:
        text = raw.decode("utf-8", "strict")
    except UnicodeDecodeError:
        return None, "runner_bad_output"
    lines = [ln for ln in text.splitlines() if ln]
    if len(lines) != 2 or not hmac.compare_digest(lines[0], nonce):
        return None, "runner_bad_output"
    try:
        data = json.loads(lines[1])
    except (ValueError, TypeError):
        return None, "runner_bad_output"
    if not isinstance(data, dict):
        return None, "runner_bad_output"
    prc = data.get("pytest_rc")
    ur = data.get("unavailable_reason")
    if prc is not None and (not isinstance(prc, int) or isinstance(prc, bool)):
        return None, "runner_bad_output"
    if ur is not None and not isinstance(ur, str):
        return None, "runner_bad_output"
    return data, None


def _parse_junit_xml(xml_path: pathlib.Path) -> tuple[dict[str, Any] | None, str | None]:
    """解析工作區外由 pytest 產生的 junitxml，彙總測試數、失敗數、錯誤數、跳過數與第一個問題。"""
    if not xml_path.is_file():
        return None, "runner_bad_output"
    try:
        tree = ET.parse(xml_path)
    except (OSError, ET.ParseError):
        return None, "runner_bad_output"
    root = tree.getroot()
    suites = [root] if root.tag == "testsuite" else list(root.findall(".//testsuite"))
    if not suites:
        return None, "runner_bad_output"
    tests_n = 0
    failures = 0
    errors = 0
    skipped = 0
    first: str | None = None
    for ts in suites:
        try:
            tests_n += int(ts.attrib.get("tests", "0"))
            failures += int(ts.attrib.get("failures", "0"))
            errors += int(ts.attrib.get("errors", "0"))
            skipped += int(ts.attrib.get("skipped", "0"))
        except ValueError:
            return None, "runner_bad_output"
        if first is None:
            for tc in ts.findall("testcase"):
                prob = tc.find("failure")
                if prob is None:
                    prob = tc.find("error")
                if prob is not None:
                    name = tc.attrib.get("name", "")
                    msg = prob.attrib.get("message", "")
                    body = (prob.text or "").strip()
                    detail = body or msg
                    first = (f"{name}\n{detail}" if name and detail else (detail or name))[-800:]
                    break
    if tests_n < 0 or failures < 0 or errors < 0 or skipped < 0:
        return None, "runner_bad_output"
    return {"tests": tests_n, "failures": failures, "errors": errors, "skipped": skipped, "first_problem": first}, None


def _run_isolated_python_script(runner_script: pathlib.Path, cfg_obj: dict[str, Any],
                                run_cwd: pathlib.Path, home: pathlib.Path,
                                runner_dir: pathlib.Path, tag: str,
                                deadline: float, *,
                                python_exe: str | None = None,
                                work_root: pathlib.Path | None = None
                                ) -> tuple[bool, int | None, bytes, pathlib.Path, pathlib.Path, str | None]:
    """以 `<python_exe> -B`、工作區外獨立腳本、獨立 session、共用期限與單次隨機 nonce 管線執行隔離腳本。"""
    exe = python_exe or sys.executable
    r_fd, w_fd = os.pipe()
    out_log = runner_dir / f"out_{tag}.log"
    err_log = runner_dir / f"err_{tag}.log"
    cfg_file = runner_dir / f"cfg_{tag}.json"
    cfg_data = json.dumps({**cfg_obj, "w_fd": w_fd}).encode("utf-8")
    cfg_file.write_bytes(cfg_data)
    os.chmod(cfg_file, 0o600)

    proc: subprocess.Popen | None = None
    timed_out = False
    raw_res = b""
    rc: int | None = None
    spawn_err: str | None = None
    try:
        with cfg_file.open("rb") as cfg_in, out_log.open("wb") as out_f, err_log.open("wb") as err_f:
            try:
                cfg_file.unlink(missing_ok=True)
            except OSError:
                pass
            try:
                proc = subprocess.Popen(
                    [exe, "-B", str(runner_script)],
                    cwd=str(run_cwd),
                    env=_clean_env(home, python_exe=exe, work_root=work_root),
                    stdin=cfg_in,
                    stdout=out_f,
                    stderr=err_f,
                    pass_fds=(w_fd,),
                    start_new_session=True,
                )
            except OSError as e:
                spawn_err = f"{type(e).__name__}: {e}"[-800:]
        os.close(w_fd)
        w_fd = -1
        if proc is not None:
            wait_left = deadline - time.monotonic()
            if wait_left <= 0:
                timed_out = True
            else:
                try:
                    rc = proc.wait(timeout=wait_left)
                except subprocess.TimeoutExpired:
                    timed_out = True
    finally:
        if w_fd >= 0:
            try:
                os.close(w_fd)
            except OSError:
                pass
        if proc is not None:
            _kill_group_and_wait(proc)
        raw_res = _read_all_fd(r_fd)
    return timed_out, rc, raw_res, out_log, err_log, spawn_err


def _tail_logs(out_log: pathlib.Path, err_log: pathlib.Path) -> str | None:
    try:
        parts = []
        if out_log.is_file():
            parts.append(out_log.read_bytes())
        if err_log.is_file():
            parts.append(err_log.read_bytes())
        text = b"\n".join(p for p in parts if p).decode("utf-8", "replace").strip()
        return text[-800:] if text else None
    except OSError:
        return None


def _run_python_unittest(base: dict[str, Any], tests: list[str], work: pathlib.Path,
                         home: pathlib.Path, runner_dir: pathlib.Path, deadline: float, *,
                         python_exe: str | None = None,
                         project_root: pathlib.Path | None = None) -> dict[str, Any]:
    """既有 unittest 驗收路徑（與 confirm1 相同執行器與計數；僅 0 個測試改記 no_tests_collected）。"""
    runner_script = runner_dir / "runner.py"
    runner_script.write_text(_UNITTEST_RUNNER, encoding="utf-8")
    os.chmod(runner_script, 0o600)

    by_dir: dict[str, list[tuple[str, pathlib.Path]]] = {}
    for rel in tests:
        d, _, name = rel.rpartition("/")
        by_dir.setdefault(d, []).append((name[:-3], (work / rel).resolve()))

    work_res = work.resolve()
    proj_str = str(project_root.resolve()) if project_root is not None else None
    agg = {k: 0 for k in _RESULT_KEYS}
    first: str | None = None
    for idx, (d, mod_entries) in enumerate(sorted(by_dir.items())):
        if deadline - time.monotonic() <= 0:
            return {**base, "status": "timeout"}
        run_cwd = (work / d if d else work).resolve()
        nonce = secrets.token_hex(16)
        timed_out, rc, raw_res, out_log, err_log, spawn_err = _run_isolated_python_script(
            runner_script,
            {
                "nonce": nonce,
                "cwd": str(run_cwd),
                "work_root": str(work_res),
                "project_root": proj_str,
                "tests": [[m, str(p)] for m, p in mod_entries],
            },
            run_cwd, home, runner_dir, f"u_{idx}", deadline,
            python_exe=python_exe,
            work_root=work_res,
        )
        if spawn_err is not None:
            return {**base, "status": "runner_unavailable", "accept": None, "first_problem": spawn_err}
        if timed_out:
            return {**base, "status": "timeout"}
        if rc != 0:
            return {**base, "status": "runner_no_output" if not raw_res else "runner_bad_output",
                    "first_problem": _tail_logs(out_log, err_log)}
        r, err_status = _parse_runner_output(raw_res, nonce)
        if err_status is not None or r is None:
            out_tail = None
            try:
                out_tail = out_log.read_bytes().decode("utf-8", "replace")[-800:] or None
            except OSError:
                pass
            return {**base, "status": err_status or "runner_bad_output", "first_problem": out_tail}
        if r["load_error"]:
            return {**base, "status": "load_error", "first_problem": r["load_error"], "run": agg["run"]}
        for k in _RESULT_KEYS:
            agg[k] += r[k]
        first = first or r["first_problem"]

    bad = agg["failures"] + agg["errors"] + agg["unexpected_successes"]
    if agg["run"] == 0 and bad == 0:
        return {**base, "status": "no_tests_collected", "run": 0, "passed": 0,
                "accept": None, "first_problem": first}
    return {**base, "status": "ok", "run": agg["run"], "passed": agg["run"] - bad - agg["skipped"],
            "accept": agg["run"] > 0 and bad == 0 and agg["skipped"] == 0, "first_problem": first}


def _run_python_pytest(base: dict[str, Any], tests: list[str], work: pathlib.Path,
                       home: pathlib.Path, runner_dir: pathlib.Path, deadline: float, *,
                       python_exe: str | None = None,
                       project_root: pathlib.Path | None = None) -> dict[str, Any]:
    """pytest 驗收路徑：隔離腳本載入 pytest、依原測試檔精確路徑執行、junitxml 寫於工作區外。"""
    if deadline - time.monotonic() <= 0:
        return {**base, "status": "timeout"}
    runner_script = runner_dir / "runner_pytest.py"
    runner_script.write_text(_PYTEST_RUNNER, encoding="utf-8")
    os.chmod(runner_script, 0o600)

    work_res = work.resolve()
    proj_str = str(project_root.resolve()) if project_root is not None else None
    extra_paths: list[str] = [str(work_res)]
    for rel in tests:
        parent = str((work / rel).resolve().parent)
        if parent not in extra_paths:
            extra_paths.append(parent)
    test_paths = [str((work / rel).resolve()) for rel in tests]
    junit_xml = runner_dir / f"junit-{secrets.token_hex(8)}.xml"
    nonce = secrets.token_hex(16)

    timed_out, rc, raw_res, out_log, err_log, spawn_err = _run_isolated_python_script(
        runner_script,
        {
            "nonce": nonce,
            "extra_paths": extra_paths,
            "work_root": str(work_res),
            "project_root": proj_str,
            "junit_xml": str(junit_xml),
            "tests": test_paths,
        },
        work_res, home, runner_dir, "pytest", deadline,
        python_exe=python_exe,
        work_root=work_res,
    )
    if spawn_err is not None:
        return {**base, "status": "runner_unavailable", "accept": None, "first_problem": spawn_err}
    if timed_out:
        return {**base, "status": "timeout"}
    if rc != 0:
        return {**base, "status": "runner_no_output" if not raw_res else "runner_bad_output",
                "first_problem": _tail_logs(out_log, err_log)}
    pipe_data, err_status = _parse_pytest_pipe(raw_res, nonce)
    if err_status is not None or pipe_data is None:
        return {**base, "status": err_status or "runner_bad_output", "first_problem": _tail_logs(out_log, err_log)}
    if pipe_data["unavailable_reason"]:
        return {**base, "status": "runner_unavailable", "accept": None,
                "first_problem": pipe_data["unavailable_reason"]}

    prc = pipe_data["pytest_rc"]
    if prc == 5:
        return {**base, "status": "no_tests_collected", "run": 0, "passed": 0, "accept": None}
    if prc in (3, 4):
        return {**base, "status": "runner_unavailable", "accept": None,
                "first_problem": _tail_logs(out_log, err_log)}

    parsed, xml_err = _parse_junit_xml(junit_xml)
    if xml_err is not None or parsed is None:
        if prc == 2:
            return {**base, "status": "load_error", "run": 0, "passed": 0, "accept": False,
                    "first_problem": _tail_logs(out_log, err_log)}
        return {**base, "status": xml_err or "runner_bad_output", "first_problem": _tail_logs(out_log, err_log)}

    tests_n = parsed["tests"]
    failures = parsed["failures"]
    errors = parsed["errors"]
    skipped = parsed["skipped"]
    first = parsed["first_problem"] or _tail_logs(out_log, err_log)

    if prc == 2:
        passed = max(0, tests_n - failures - errors - skipped)
        return {**base, "status": "load_error", "run": 0 if errors == tests_n else tests_n,
                "passed": passed, "accept": False, "first_problem": first}
    if tests_n == 0 and failures == 0 and errors == 0:
        return {**base, "status": "no_tests_collected", "run": 0, "passed": 0, "accept": None}

    bad = failures + errors
    passed = max(0, tests_n - bad - skipped)
    accept = (prc == 0 and passed > 0 and bad == 0)
    return {**base, "status": "ok", "run": tests_n, "passed": passed,
            "accept": accept, "first_problem": first if not accept else None}


def _run_python_bare(base: dict[str, Any], tests: list[str], work: pathlib.Path,
                     home: pathlib.Path, runner_dir: pathlib.Path, deadline: float, *,
                     python_exe: str | None = None,
                     project_root: pathlib.Path | None = None) -> dict[str, Any]:
    """pytest 缺席時的極簡標準庫執行器：同時跑 unittest.TestCase、裸 def test_* 與簡易非 TestCase 測試類別。"""
    runner_script = runner_dir / "runner_bare.py"
    runner_script.write_text(_BARE_RUNNER, encoding="utf-8")
    os.chmod(runner_script, 0o600)

    by_dir: dict[str, list[tuple[str, pathlib.Path]]] = {}
    for rel in tests:
        d, _, name = rel.rpartition("/")
        by_dir.setdefault(d, []).append((name[:-3], (work / rel).resolve()))

    work_res = work.resolve()
    proj_str = str(project_root.resolve()) if project_root is not None else None
    agg = {k: 0 for k in _RESULT_KEYS}
    first: str | None = None
    for idx, (d, mod_entries) in enumerate(sorted(by_dir.items())):
        if deadline - time.monotonic() <= 0:
            return {**base, "status": "timeout"}
        run_cwd = (work / d if d else work).resolve()
        extra_paths = [str(run_cwd)]
        if str(work_res) not in extra_paths:
            extra_paths.append(str(work_res))
        nonce = secrets.token_hex(16)
        timed_out, rc, raw_res, out_log, err_log, spawn_err = _run_isolated_python_script(
            runner_script,
            {
                "nonce": nonce,
                "extra_paths": extra_paths,
                "work_root": str(work_res),
                "project_root": proj_str,
                "tests": [[m, str(p)] for m, p in mod_entries],
            },
            run_cwd, home, runner_dir, f"b_{idx}", deadline,
            python_exe=python_exe,
            work_root=work_res,
        )
        if spawn_err is not None:
            return {**base, "status": "runner_unavailable", "accept": None, "first_problem": spawn_err}
        if timed_out:
            return {**base, "status": "timeout"}
        if rc != 0:
            return {**base, "status": "runner_no_output" if not raw_res else "runner_bad_output",
                    "first_problem": _tail_logs(out_log, err_log)}
        r, err_status = _parse_runner_output(raw_res, nonce, allow_unavailable=True)
        if err_status is not None or r is None:
            return {**base, "status": err_status or "runner_bad_output", "first_problem": _tail_logs(out_log, err_log)}
        if r.get("unavailable_reason"):
            return {**base, "status": "runner_unavailable", "accept": None,
                    "first_problem": r["unavailable_reason"]}
        if r["load_error"]:
            return {**base, "status": "load_error", "first_problem": r["load_error"], "run": agg["run"]}
        for k in _RESULT_KEYS:
            agg[k] += r[k]
        first = first or r["first_problem"]

    bad = agg["failures"] + agg["errors"] + agg["unexpected_successes"]
    if agg["run"] == 0 and bad == 0:
        return {**base, "status": "no_tests_collected", "run": 0, "passed": 0,
                "accept": None, "first_problem": first}
    return {**base, "status": "ok", "run": agg["run"], "passed": agg["run"] - bad - agg["skipped"],
            "accept": agg["run"] > 0 and bad == 0 and agg["skipped"] == 0, "first_problem": first}


def _run_external_command(base: dict[str, Any], spec: AcceptanceSpec, work: pathlib.Path,
                          runner_dir: pathlib.Path, deadline: float, *,
                          node_modules_dir: pathlib.Path | None = None) -> dict[str, Any]:
    """在快照副本 work 裡執行外部驗收指令（--check／npm／cargo／go），獨立 session、共用期限、沿用使用者環境。"""
    if deadline - time.monotonic() <= 0:
        return {**base, "status": "timeout"}
    work_res = work.resolve()
    if spec.kind == "npm" and spec.pinned_script is not None:
        # 雙重防線：確認驗收副本中的 package.json scripts.test 與開始時鎖定的一致
        if _npm_test_script(work_res) != spec.pinned_script:
            return {
                **base,
                "status": "acceptance_error",
                "accept": False,
                "first_problem": "package.json scripts.test does not match the pinned start definition",
            }
    env = dict(os.environ)
    env["PWD"] = str(work_res)
    if node_modules_dir is not None and node_modules_dir.is_dir():
        nm_str = str(node_modules_dir)
        old_np = env.get("NODE_PATH", "")
        env["NODE_PATH"] = f"{nm_str}{os.pathsep}{old_np}" if old_np else nm_str
        nm_bin = node_modules_dir / ".bin"
        if nm_bin.is_dir():
            old_path = env.get("PATH", "")
            env["PATH"] = f"{nm_bin}{os.pathsep}{old_path}" if old_path else str(nm_bin)
    out_log = runner_dir / "ext_out.log"
    err_log = runner_dir / "ext_err.log"

    proc: subprocess.Popen | None = None
    timed_out = False
    rc: int | None = None
    try:
        with out_log.open("wb") as out_f, err_log.open("wb") as err_f:
            try:
                if spec.kind == "check":
                    proc = subprocess.Popen(
                        str(spec.command),
                        shell=True,
                        cwd=str(work_res),
                        env=env,
                        stdin=subprocess.DEVNULL,
                        stdout=out_f,
                        stderr=err_f,
                        start_new_session=True,
                    )
                else:
                    proc = subprocess.Popen(
                        list(spec.argv or ()),
                        cwd=str(work_res),
                        env=env,
                        stdin=subprocess.DEVNULL,
                        stdout=out_f,
                        stderr=err_f,
                        start_new_session=True,
                    )
            except OSError as e:
                return {**base, "status": "runner_unavailable", "accept": None,
                        "first_problem": f"{type(e).__name__}: {e}"[-800:]}
        wait_left = deadline - time.monotonic()
        if wait_left <= 0:
            timed_out = True
        else:
            try:
                rc = proc.wait(timeout=wait_left)
            except subprocess.TimeoutExpired:
                timed_out = True
    finally:
        if proc is not None:
            _kill_group_and_wait(proc)

    if timed_out:
        return {**base, "status": "timeout"}
    if rc == 0:
        return {**base, "status": "ok", "accept": True, "returncode": 0}
    tail = _tail_logs(out_log, err_log)
    return {**base, "status": "failed", "accept": False, "returncode": rc,
            "first_problem": tail or f"exit code {rc}"}


def acceptance(originals: dict[str, bytes], ws: pathlib.Path, timeout_s: float = ACC_TIMEOUT_S, *,
               spec: AcceptanceSpec | None = None,
               check: str | None = None,
               protect: Sequence[str] | None = None,
               _snapshot: _Snapshot | None = None,
               _project: pathlib.Path | None = None,
               _plan: _WritePlan | None = None) -> dict:
    """在工作區快照的**潔淨副本**裡、把開始時的受保護檔案還原之後跑驗收。驗收自己壞掉＝沒過（不是通過）。"""
    all_protected = sorted(originals)
    py_tests = [rel for rel in all_protected if _is_python_test(rel)]
    src_root = (_project if _project is not None else ws).resolve()
    if spec is None:
        spec = detect_acceptance(
            src_root,
            check=check,
            originals=originals,
            protect=protect,
        )
    py_exe = spec.interpreter or (resolve_python(src_root) if spec.kind.startswith("python_") else None)
    base: dict[str, Any] = {
        "accept": False,
        "tests": py_tests if spec.kind.startswith("python_") else all_protected,
        "passed": None,
        "run": None,
        "tests_tampered": [],
        "status": None,
        "first_problem": None,
        "kind": spec.kind,
        "command": spec.command,
        "interpreter": py_exe,
    }
    if spec.kind == "none":
        return {
            **base,
            "accept": None,
            "status": "runner_unavailable" if spec.reason else "no_tests",
            "first_problem": spec.reason,
        }
    if spec.reason is not None:
        return {**base, "accept": None, "status": "runner_unavailable", "first_problem": spec.reason}

    deadline = time.monotonic() + max(0.0, timeout_s)
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="vrun-"))
    os.chmod(tmp, 0o700)
    try:
        snap = _snapshot if _snapshot is not None else _snapshot_workspace(ws, tmp / "snap")
        base["tests_tampered"] = _detect_tampered(snap, originals)
        if deadline - time.monotonic() <= 0:
            return {**base, "status": "timeout"}
        work = tmp / "w"
        _populate_acceptance_work(work, originals, snap, _project, _plan)
        home = tmp / "h"
        home.mkdir(mode=0o700)
        runner_dir = tmp / "r"
        runner_dir.mkdir(mode=0o700)

        if spec.kind == "python_unittest":
            return _run_python_unittest(
                base, py_tests, work, home, runner_dir, deadline,
                python_exe=py_exe, project_root=_project,
            )
        if spec.kind == "python_pytest":
            return _run_python_pytest(
                base, py_tests, work, home, runner_dir, deadline,
                python_exe=py_exe, project_root=_project,
            )
        if spec.kind == "python_bare":
            return _run_python_bare(
                base, py_tests, work, home, runner_dir, deadline,
                python_exe=py_exe, project_root=_project,
            )
        if spec.kind in _EXIT_CODE_ONLY_KINDS:
            # 僅於驗收階段將原專案的 node_modules 以 symlink（＋NODE_PATH）提供給驗收副本，
            # 絕不放進 agent 的 ws 也不會寫回原專案；結束立即 unlink。
            orig_nm = src_root / "node_modules"
            nm_target: pathlib.Path | None = None
            nm_link: pathlib.Path | None = None
            if orig_nm.is_dir():
                nm_target = orig_nm.resolve()
                cand_link = work / "node_modules"
                if not cand_link.exists() and not cand_link.is_symlink():
                    try:
                        os.symlink(nm_target, cand_link)
                        nm_link = cand_link
                    except OSError:
                        nm_link = None
            try:
                return _run_external_command(
                    base, spec, work, runner_dir, deadline,
                    node_modules_dir=nm_target,
                )
            finally:
                if nm_link is not None and nm_link.is_symlink():
                    try:
                        nm_link.unlink(missing_ok=True)
                    except OSError:
                        pass
        return {**base, "accept": None, "status": "runner_unavailable",
                "first_problem": f"unsupported acceptance kind: {spec.kind}"}
    except Exception as e:  # noqa: BLE001 — 單次驗收任何非預期錯誤皆安全判為未通過
        return {**base, "status": "acceptance_error", "first_problem": f"{type(e).__name__}: {e}"[-800:]}
    finally:
        _rmtree_force(tmp)


def deliver_index(accs: list[dict]) -> int:
    """交哪一次：第一個驗收通過的；都沒過就交原件測試過最多的（同分取最後一次）。
    僅看退出碼的驗收種類（check／npm／cargo／go）的 `passed` 為 `None`，故都沒過時依同分規則交最後一次。
    ＝redo.py `_policy_deliver`。"""
    for i, a in enumerate(accs):
        if a["accept"]:
            return i
    return max(range(len(accs)), key=lambda i: (accs[i]["passed"] or 0, i))


def _truncate_str(s: str, limit: int = _MAX_ARG_LEN) -> str:
    if len(s) <= limit:
        return s
    h = hashlib.sha256(s.encode("utf-8", "replace")).hexdigest()[:12]
    return f"{s[:limit // 2]}...[truncated:{len(s)}ch,sha256={h}]"


def _is_secret_key(key: str) -> bool:
    return bool(_SECRET_KEY_RE.search(key))


def _is_secret_value(val: str) -> bool:
    return bool(_SECRET_VAL_RE.search(val))


def _redact_env(env: dict[str, str]) -> dict[str, str]:
    """對收據記錄的 Launch.env 遮罩機密值（只讀複本，絕不修改交給 agent 的 env）。"""
    out: dict[str, str] = {}
    for k in sorted(env):
        ks = str(k)
        vs = str(env[k])
        if _is_secret_key(ks) or _is_secret_value(vs):
            out[ks] = "[REDACTED]"
        else:
            out[ks] = _truncate_str(vs)
    return out


def _redact_argv(argv: list[str]) -> list[str]:
    """對收據記錄的 argv 遮罩機密參數並截短過長引數（不改原 argv）。"""
    out: list[str] = []
    redact_next = False
    for raw in argv:
        s = str(raw)
        if redact_next:
            out.append("[REDACTED]")
            redact_next = False
            continue
        if _SECRET_FLAG_RE.match(s):
            if "=" in s:
                flag, _ = s.split("=", 1)
                out.append(f"{flag}=[REDACTED]")
            else:
                out.append(s)
                redact_next = True
            continue
        if "=" in s and not s.startswith("-"):
            k, _, v = s.partition("=")
            if k and (k.replace("_", "").isalnum()) and (_is_secret_key(k) or _is_secret_value(v)):
                out.append(f"{k}=[REDACTED]")
                continue
        if _is_secret_value(s):
            out.append("[REDACTED]")
        else:
            out.append(_truncate_str(s))
    return out


def _snapshot_tree_sha256(snap: _Snapshot | None) -> str | None:
    """對快照檔案樹算確定性 SHA-256（按排序相對路徑與檔案 SHA-256 逐筆串接）。"""
    if snap is None:
        return None
    h = hashlib.sha256()
    for rel in sorted(snap.files):
        h.update(rel.encode("utf-8"))
        h.update(b"\x00")
        h.update(snap.files[rel].encode("ascii"))
        h.update(b"\n")
    return h.hexdigest()


def _written_back_entries(project: pathlib.Path, snap: _Snapshot | None,
                          changed: dict[str, list[str]]) -> list[dict[str, Any]]:
    """收集實際寫回專案的檔案清單及其 SHA-256（按相對路徑排序）。"""
    ops: list[tuple[str, str]] = (
        [(rel, "added") for rel in changed.get("added") or ()]
        + [(rel, "modified") for rel in changed.get("modified") or ()]
    )
    ops.sort(key=lambda t: t[0])
    out: list[dict[str, Any]] = []
    for rel, op in ops:
        sha = _sha256_file(project / rel)
        if sha is None and snap is not None:
            sha = snap.files.get(rel)
        out.append({"path": rel, "op": op, "sha256": sha})
    return out


def _list_sha256(items: Any) -> str:
    from ..canonical import canonical_bytes
    return hashlib.sha256(canonical_bytes(items)).hexdigest()


def _bound_receipt_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """確保收據 payload 永遠低於 Logbook.MAX_PAYLOAD_BYTES（不依賴可被 gc 的外部 blob）。"""
    from ..canonical import canonical_bytes
    if len(canonical_bytes(payload)) <= _RECEIPT_MAX_BYTES:
        return payload
    out = dict(payload)
    for key in ("written_back", "deleted", "skipped"):
        items = out.get(key)
        if isinstance(items, list) and len(items) > 64:
            out[f"{key}_count"] = len(items)
            out[f"{key}_sha256"] = _list_sha256(items)
            out[f"{key}_truncated"] = True
            out[key] = items[:64]
            if len(canonical_bytes(out)) <= _RECEIPT_MAX_BYTES:
                return out
    acc = dict(out.get("acceptance") or {})
    prot = acc.get("protected")
    if isinstance(prot, list) and len(prot) > 64:
        acc["protected_count"] = len(prot)
        acc["protected_sha256"] = _list_sha256(prot)
        acc["protected_truncated"] = True
        acc["protected"] = prot[:64]
        out["acceptance"] = acc
    return out


def _record_receipt(*, project: pathlib.Path, prompt: str, agent: str | None,
                    launch_meta: list[tuple[list[str], dict[str, str]]],
                    spec: AcceptanceSpec, protected: set[str],
                    attempts: list[dict[str, Any]], snaps: list[_Snapshot | None],
                    delivered_idx: int, changed: dict[str, list[str]],
                    res: dict[str, Any], run_dir: pathlib.Path) -> dict[str, Any]:
    """把這次 restart-mode 執行簽進專案既有的 trace 簽章鏈（`$VACANT_HOME/trace/projects/<proj>/chain.ndjson`）。
    完全事後記錄、fail-open（簽章失敗只記在回傳與 result.json，不影響已完成的交回）。"""
    try:
        from ..trace.recorder import Recorder, project_key
        first_argv, first_env = launch_meta[0] if launch_meta else ([], {})
        agent_name = agent or (pathlib.Path(first_argv[0]).name if first_argv else "unknown")
        proj_str = str(project)
        proj_sha = hashlib.sha256(proj_str.encode("utf-8")).hexdigest()
        pkey = project_key(project)
        attempt_recs: list[dict[str, Any]] = []
        for idx, a in enumerate(attempts):
            snap = snaps[idx] if idx < len(snaps) else None
            attempt_recs.append({
                "attempt": a["attempt"],
                "wall_s": a["wall_s"],
                "rc": a["rc"],
                "timed_out": a["timed_out"],
                "accept": a["accept"],
                "passed": a["passed"],
                "run": a["run"],
                "status": a["status"],
                "tests_tampered": list(a["tests_tampered"]),
                "snapshot_tree_sha256": _snapshot_tree_sha256(snap),
            })
        delivered_snap = snaps[delivered_idx] if 0 <= delivered_idx < len(snaps) else None
        payload: dict[str, Any] = {
            "receipt_schema": RECEIPT_SCHEMA,
            "run_id": run_dir.name,
            "request_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
            "agent": agent_name,
            "argv": _redact_argv(first_argv),
            "env": _redact_env(first_env),
            "project_path_sha256": proj_sha,
            "project_key": pkey,
            "acceptance": {
                "kind": spec.kind,
                "command": spec.command,
                "interpreter": spec.interpreter,
                "protected": sorted(protected),
                "reason": spec.reason,
            },
            "baseline": res.get("baseline"),
            "baseline_error": res.get("baseline_error"),
            "max_attempts": res["max_attempts"],
            "attempts": attempt_recs,
            "delivered_attempt": res["delivered_attempt"],
            "accepted": res["accepted"],
            "written_back": _written_back_entries(project, delivered_snap, changed),
            "deleted": list(changed.get("deleted") or ()),
            "skipped": list(changed.get("skipped") or ()),
            "agent_wall_s": res["agent_wall_s"],
            "total_wall_s": res["total_wall_s"],
        }
        payload = _bound_receipt_payload(payload)
        rec = Recorder(project)
        ref = rec.append("restart_receipt", payload)
        return {
            "recorded": True,
            "schema": RECEIPT_SCHEMA,
            "project_key": rec.dir.name,
            "chain_path": str(rec.chain_path),
            "seq": ref["seq"],
            "hash": ref["hash"],
        }
    except Exception as e:  # noqa: BLE001 — fail-open：記錄失敗不影響已交回結果
        return {
            "recorded": False,
            "schema": RECEIPT_SCHEMA,
            "error": f"{type(e).__name__}: {e}"[:300],
        }


def verify_receipts(project: pathlib.Path, *, state_root: pathlib.Path | None = None,
                    trust: Any = None,
                    expected_head: dict[str, Any] | None = None
                    ) -> tuple[bool, str, list[dict[str, Any]]]:
    """離線驗證專案簽章鏈（`vacant trace verify` 同源機制）並回傳所有 `restart_receipt` 紀錄。

    除了 `Recorder.verify()`（驗 Ed25519 簽章、seq 連續、prev_hash 連結、stream_id、
    `trace_genesis`、`head.json`、`trust.json` verifier 清單與選用 `expected_head` 錨點），
    另對鏈檔做嚴格逐行完整性檢查（拒收損壞 JSON 行或截斷半行，防無 head.json 時的半行省略）。
    """
    from ..intake import keys as _keys
    from ..logbook import LogEntry
    from ..trace.recorder import Recorder, _volume_bytes

    troot = (pathlib.Path(state_root) / "trace") if state_root is not None else None
    rec = Recorder(project, root=troot)
    if trust is None and state_root is not None:
        trust = _keys.Trust.load(pathlib.Path(state_root) / "intake" / "trust.json")

    vols = rec._sealed_volume_paths()
    all_files = list(vols) + ([rec.chain_path] if rec.chain_path.is_file() else [])
    if not all_files:
        return False, "no trace chain", []

    for fp in all_files:
        try:
            raw = _volume_bytes(fp)
        except Exception as e:  # noqa: BLE001
            return False, f"unreadable chain file {fp.name}: {type(e).__name__}", []
        if raw and not raw.endswith(b"\n"):
            return False, f"truncated trailing line in {fp.name}", []
        for idx, line in enumerate(raw.split(b"\n"), start=1):
            if not line:
                continue
            try:
                LogEntry.from_json(json.loads(line))
            except Exception:  # noqa: BLE001
                return False, f"malformed entry at {fp.name}:{idx}", []

    ok, why = rec.verify(trust=trust, anchor=expected_head)
    if not ok:
        return False, why, []
    receipts = [e for e in rec.events() if e.get("type") == "restart_receipt"]
    return True, why, receipts


_MISSING_MOD_RE = re.compile(r"No module named '([A-Za-z0-9_.]+)'")


def _missing_module_name(text: str | None) -> str | None:
    """從載入錯誤的 traceback 取出 ModuleNotFoundError 的模組名；沒有就 None。"""
    if not text:
        return None
    found = _MISSING_MOD_RE.findall(text)
    return found[-1] if found else None


def _norm_dist(name: str) -> str:
    return re.sub(r"[-_.]+", "_", name).lower()


def _declared_dependency(project: pathlib.Path, module: str) -> bool:
    """`module` 是否出現在專案宣告的相依裡（以名稱正規化比對；只認頂層名＝發行名的常見情形）。"""
    want = _norm_dist(module)
    names: set[str] = set()
    req_line = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)")
    try:
        for req in sorted(project.glob("requirements*.txt")):
            for line in req.read_text(errors="replace").splitlines():
                line = line.split("#", 1)[0].strip()
                if not line or line.startswith("-"):
                    continue
                m = req_line.match(line)
                if m:
                    names.add(_norm_dist(m.group(1)))
        for meta in ("pyproject.toml", "setup.cfg", "setup.py"):
            f = project / meta
            if f.is_file():
                txt = f.read_text(errors="replace")
                for m in re.finditer(r"[\"']\s*([A-Za-z0-9][A-Za-z0-9._-]*)\s*(?:[<>=!~;\[ ][^\"']*)?[\"']", txt):
                    names.add(_norm_dist(m.group(1)))
                if meta == "setup.cfg":
                    for line in txt.splitlines():
                        m = req_line.match(line)
                        if m and line[:1].isspace():
                            names.add(_norm_dist(m.group(1)))
    except OSError:
        return False
    return want in names


def _baseline_env_reason(spec: AcceptanceSpec, base_acc: dict[str, Any] | None,
                         project: pathlib.Path | None = None) -> str | None:
    """判斷基線驗收是否因環境問題無法執行；是則回傳人讀原因，否則 None。"""
    if spec.kind == "none":
        return spec.reason  # None＝專案本來就沒測試；非 None＝偵測到專案標記但工具缺席（例如 npm）
    if spec.reason is not None:
        return spec.reason
    if base_acc is None:
        return None
    st = base_acc.get("status")
    fp = base_acc.get("first_problem")
    if st == "runner_unavailable":
        return fp or "test runner is unavailable"
    if st == "load_error":
        # 收集期載入錯誤多半是「agent 要寫的模組還不存在」（例如測試 import 了待實作的 m.py），那是正常起點，
        # 不是環境問題。只有兩種算環境跑不起來：測試工具本身匯入不了（pytest／_pytest），或缺的是專案
        # 在 requirements*.txt／pyproject.toml／setup.cfg／setup.py 宣告過的相依（宣告了卻沒裝在這個直譯器）。
        missing = _missing_module_name(fp)
        if missing is None:
            return None
        top = missing.split(".")[0]
        if top in ("pytest", "_pytest"):
            return fp or f"test runner module {top!r} is not importable"
        if project is not None and _declared_dependency(project, top):
            return (f"module {top!r} is declared as a project dependency but is not installed for "
                    f"{spec.interpreter or 'the resolved interpreter'}")
        return None
    if st in ("runner_no_output", "runner_bad_output", "acceptance_error"):
        return fp or f"acceptance runner failed ({st})"
    if spec.kind in _EXIT_CODE_ONLY_KINDS and base_acc.get("returncode") in (126, 127):
        return fp or f"command not found or not executable (exit code {base_acc.get('returncode')})"
    return None


def run(project: pathlib.Path, build: Callable[[str, pathlib.Path], Launch], prompt: str, *,
        max_attempts: int = 3, attempt_timeout_s: float = 600.0, budget_s: float = 1800.0,
        min_attempt_s: float = 60.0, check: str | None = None,
        protect: Sequence[str] | None = None,
        agent: str | None = None,
        log: Callable[[str], None] | None = None) -> dict:
    project = project.resolve()
    say = log or (lambda m: None)
    spec = detect_acceptance(project, check=check, protect=protect)
    originals = {rel: (project / rel).read_bytes() for rel in spec.protected}
    protected = set(originals)
    py_tests = [rel for rel in spec.protected if _is_python_test(rel)]
    has_acceptance = spec.kind != "none" and spec.reason is None
    if not has_acceptance:
        max_attempts = 1
        attempt_timeout_s = budget_s
    run_dir = work_root() / f"restart-{time.strftime('%Y%m%dT%H%M%S')}-{os.getpid()}-{secrets.token_hex(3)}"
    run_dir.mkdir(parents=True, exist_ok=True)
    attempts: list[dict] = []
    snaps: list[_Snapshot | None] = []
    launch_meta: list[tuple[list[str], dict[str, str]]] = []
    spent = 0.0
    t0 = time.monotonic()

    # 基線驗收：在第一次跑 agent 之前先對未動過的專案副本跑一次，確認驗收在此環境能執行
    baseline_rec: dict[str, Any] | None = None
    baseline_error: str | None = None
    if spec.reason is not None:
        baseline_rec = {
            "accept": None,
            "passed": None,
            "run": None,
            "status": "runner_unavailable",
            "first_problem": spec.reason,
            "returncode": None,
        }
        baseline_error = _baseline_env_reason(spec, baseline_rec, project)
    elif has_acceptance:
        base_t = max(0.0, min(ACC_TIMEOUT_S, budget_s / 2 if budget_s < 10.0 else budget_s))
        base_acc = acceptance(originals, project, base_t, spec=spec, _project=project)
        baseline_rec = {
            "accept": base_acc.get("accept"),
            "passed": base_acc.get("passed"),
            "run": base_acc.get("run"),
            "status": base_acc.get("status"),
            "first_problem": base_acc.get("first_problem"),
            "returncode": base_acc.get("returncode"),
        }
        baseline_error = _baseline_env_reason(spec, base_acc, project)
        if baseline_error is None:
            if baseline_rec["accept"] is None:
                say(f"baseline: not checked ({baseline_rec['status']})")
            elif baseline_rec["run"] is not None:
                say(f"baseline: {spec.kind} {'PASS' if baseline_rec['accept'] else 'FAIL'} "
                    f"({baseline_rec['passed']}/{baseline_rec['run']})")
            else:
                say(f"baseline: {spec.kind} {'PASS' if baseline_rec['accept'] else 'FAIL'} "
                    f"(status={baseline_rec['status']})")

    if baseline_error is not None:
        say(f"baseline: acceptance cannot run in this environment: {baseline_error}")
        changed = {"added": [], "modified": [], "deleted": [], "skipped": []}
        res = {
            "mode": "restart",
            "project": str(project),
            "tests": py_tests if spec.kind.startswith("python_") else sorted(originals),
            "protected": sorted(protected),
            "acceptance": spec.to_dict(),
            "interpreter": spec.interpreter,
            "baseline": baseline_rec,
            "baseline_error": baseline_error,
            "max_attempts": max_attempts,
            "accepted": None,
            "delivered_attempt": 0,
            "attempts": [],
            "changed": changed,
            "agent_wall_s": 0.0,
            "total_wall_s": round(time.monotonic() - t0, 1),
            "run_dir": str(run_dir),
        }
        res["receipt"] = _record_receipt(
            project=project,
            prompt=prompt,
            agent=agent,
            launch_meta=launch_meta,
            spec=spec,
            protected=protected,
            attempts=attempts,
            snaps=snaps,
            delivered_idx=-1,
            changed=changed,
            res=res,
            run_dir=run_dir,
        )
        (run_dir / "result.json").write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
        return res

    reserve = min(ACC_TIMEOUT_S, budget_s / 10) if has_acceptance else 0.0   # 每次嘗試後留給驗收的時間
    while len(attempts) < max_attempts:
        remaining = budget_s - (time.monotonic() - t0) - reserve
        if attempts and remaining < min_attempt_s:
            break
        remaining = max(remaining, min(0.1, budget_s))
        k = len(attempts) + 1
        attempt_dir = run_dir / f"attempt_{k}"
        ws = attempt_dir / "w"
        shutil.copytree(project, ws, symlinks=True, ignore=shutil.ignore_patterns(*COPY_SKIP))
        launch = build(prompt, ws)
        launch_meta.append((list(launch.argv), dict(launch.env)))
        say(f"attempt {k} of {max_attempts} (up to {min(attempt_timeout_s, remaining):.0f}s)")
        try:
            r = run_agent(launch, workspace=ws, timeout_s=min(attempt_timeout_s, remaining),
                          log_dir=attempt_dir / "logs")
        finally:
            if launch.cleanup:
                launch.cleanup()
        spent += r["wall_ms"] / 1000.0

        snap: _Snapshot | None = None
        plan: _WritePlan | None = None
        try:
            snap_dir = attempt_dir / f"snap-{secrets.token_hex(8)}"
            snap = _snapshot_workspace(ws, snap_dir)
            plan = _plan_write_back(project, snap, protected)
            if has_acceptance:
                acc_t = max(0.0, min(ACC_TIMEOUT_S, budget_s - (time.monotonic() - t0)))
                acc = acceptance(originals, ws, acc_t, spec=spec, _snapshot=snap, _project=project, _plan=plan)
            else:
                tam = _detect_tampered(snap, originals) if originals else []
                acc = {
                    "accept": None,
                    "passed": None,
                    "run": None,
                    "status": "runner_unavailable" if spec.reason else "no_tests",
                    "tests_tampered": tam,
                    "first_problem": spec.reason,
                }
        except Exception as e:  # noqa: BLE001 — 單次評估失敗安全判為未通過，不影響其他嘗試
            acc = {
                "accept": False if has_acceptance else None,
                "passed": None,
                "run": None,
                "status": "acceptance_error",
                "tests_tampered": [],
                "first_problem": f"{type(e).__name__}: {e}"[-800:],
            }

        uncheckable = acc["status"] in _UNCHECKABLE_STATUSES
        if uncheckable and not attempts:
            acc["accept"] = None
        elif uncheckable and attempts:
            # 前一次已有可執行的驗收；後續嘗試若突然收集不到測試或壞掉，仍視為該次未通過而非放棄先前的驗收結果
            acc["accept"] = False

        attempts.append({
            "attempt": k,
            "accept": acc["accept"],
            "passed": acc["passed"],
            "run": acc["run"],
            "status": acc["status"],
            "acceptance_kind": spec.kind,
            "tests_tampered": acc["tests_tampered"],
            "first_problem": acc.get("first_problem"),
            "rc": r["rc"],
            "timed_out": r["timed_out"],
            "wall_s": round(r["wall_ms"] / 1000.0, 1),
            "spawn_error": r["spawn_error"],
            "workspace": str(ws),
        })
        snaps.append(snap)

        if acc["accept"] is None:
            say(f"attempt {k}: not checked ({acc['status']})")
        elif acc["run"] is not None:
            say(f"attempt {k}: {spec.kind} {'PASS' if acc['accept'] else 'FAIL'} ({acc['passed']}/{acc['run']})")
        else:
            say(f"attempt {k}: {spec.kind} {'PASS' if acc['accept'] else 'FAIL'} (status={acc['status']})")

        if acc["accept"] is None or acc["accept"] is True:
            break

    d = deliver_index([{"accept": bool(a["accept"]), "passed": a["passed"]} for a in attempts])
    if snaps[d] is not None:
        changed = _write_back(project, snaps[d], protected, _backup_root=run_dir)
    else:
        changed = {"added": [], "modified": [], "deleted": [], "skipped": []}

    only_uncheckable = len(attempts) == 1 and attempts[0]["accept"] is None
    res = {
        "mode": "restart",
        "project": str(project),
        "tests": py_tests if spec.kind.startswith("python_") else sorted(originals),
        "protected": sorted(protected),
        "acceptance": spec.to_dict(),
        "interpreter": spec.interpreter,
        "baseline": baseline_rec,
        "baseline_error": None,
        "max_attempts": max_attempts,
        "accepted": None if only_uncheckable else bool(attempts[d]["accept"]),
        "delivered_attempt": d + 1,
        "attempts": attempts,
        "changed": changed,
        "agent_wall_s": round(spent, 1),
        "total_wall_s": round(time.monotonic() - t0, 1),
        "run_dir": str(run_dir),
    }
    res["receipt"] = _record_receipt(
        project=project,
        prompt=prompt,
        agent=agent,
        launch_meta=launch_meta,
        spec=spec,
        protected=protected,
        attempts=attempts,
        snaps=snaps,
        delivered_idx=d,
        changed=changed,
        res=res,
        run_dir=run_dir,
    )
    (run_dir / "result.json").write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    return res


def summary(res: dict) -> str:
    n = len(res["attempts"])
    ch = res["changed"]
    files = f"{len(ch['added'])} added, {len(ch['modified'])} modified, {len(ch['deleted'])} deleted"
    acc_info = res.get("acceptance") or {}
    acc_kind = acc_info.get("kind") or ("python_unittest" if res.get("tests") else "none")
    acc_cmd = acc_info.get("command")
    acc_reason = acc_info.get("reason")
    acc_interp = acc_info.get("interpreter") or res.get("interpreter")
    protected = list(res.get("protected") if "protected" in res else (res.get("tests") or []))
    baseline = res.get("baseline") if isinstance(res.get("baseline"), dict) else None
    baseline_err = res.get("baseline_error")

    if baseline_err:
        reason_txt = str(baseline_err).strip()
        head = (
            f"[vacant] acceptance cannot run in this environment: {reason_txt}\n"
            f"  stopped before running the agent (0 attempts); project unchanged."
        )
    elif res["accepted"] is None:
        a0 = res["attempts"][0] if res.get("attempts") else {}
        st = a0.get("status")
        why = acc_reason or a0.get("first_problem")
        if st == "no_tests_collected":
            head = (f"[vacant] ran once; 0 tests were collected by {acc_kind}, "
                    f"so nothing could be checked. {files}.")
        elif st == "runner_unavailable":
            detail = why or "runner could not start"
            head = (f"[vacant] ran once; no executable acceptance ({detail}), "
                    f"so nothing could be checked. {files}.")
        else:
            head = (f"[vacant] ran once; no executable acceptance (no tests or supported test runner detected), "
                    f"so nothing was checked. {files}.")
    elif res["accepted"]:
        a = res["attempts"][res["delivered_attempt"] - 1]
        if a.get("run") is not None:
            detail = f"{a['passed']}/{a['run']} tests"
        else:
            detail = "exit 0"
        head = (f"[vacant] acceptance passed on attempt {res['delivered_attempt']} "
                f"(up to {res.get('max_attempts', n)} allowed; {detail}); delivered that attempt. {files}.")
    else:
        a = res["attempts"][res["delivered_attempt"] - 1]
        if a.get("run") is not None:
            head = (f"[vacant] not all tests pass after {n} attempt(s); delivered attempt "
                    f"{res['delivered_attempt']} ({a['passed'] or 0}/{a['run'] or 0} tests). {files}.")
        elif acc_kind in _EXIT_CODE_ONLY_KINDS:
            head = (f"[vacant] acceptance did not pass after {n} attempt(s); delivered latest attempt "
                    f"{res['delivered_attempt']} (status: {a.get('status')}). {files}.")
        else:
            head = (f"[vacant] not all tests pass after {n} attempt(s); delivered attempt "
                    f"{res['delivered_attempt']} (status: {a.get('status')}). {files}.")

    cmd_part = f" ({acc_cmd})" if acc_cmd else ""
    head += f"\n  acceptance: {acc_kind}{cmd_part}"
    if acc_interp:
        head += f"\n  interpreter: {acc_interp}"
    if baseline is not None and not baseline_err:
        if baseline.get("accept") is True:
            if baseline.get("run") is not None:
                head += (f"\n  baseline (before agent): PASS ({baseline['passed']}/{baseline['run']} tests; "
                         f"already passing before the agent ran)")
            else:
                head += "\n  baseline (before agent): PASS (exit 0; already passing before the agent ran)"
        elif baseline.get("accept") is False:
            if baseline.get("run") is not None:
                head += (f"\n  baseline (before agent): FAIL ({baseline['passed'] or 0}/{baseline['run']} tests, "
                         f"status={baseline.get('status')})")
            else:
                head += f"\n  baseline (before agent): FAIL (status={baseline.get('status')})"
    if protected:
        shown = ", ".join(protected[:20]) + (f" … (+{len(protected) - 20} more)" if len(protected) > 20 else "")
        head += f"\n  protected (restored before check): {shown}"
    elif acc_kind != "none":
        head += "\n  protected (restored before check): none — the agent could have edited what this check runs"
    else:
        head += "\n  protected (restored before check): none"
    if ch.get("skipped"):
        head += (f"\n  not written back ({len(ch['skipped'])}): unsafe path (symlink, conflict, or unreadable) "
                 f"({', '.join(ch['skipped'][:5])}{' …' if len(ch['skipped']) > 5 else ''}); see the attempt workspace.")
    tam = sorted({t for a in res["attempts"] for t in a["tests_tampered"]})
    if tam:
        if all(_is_universal_test(t) for t in tam):
            head += f"\n  the agent edited test files ({', '.join(tam)}); checked against the originals, not written back."
        else:
            head += f"\n  the agent edited protected files ({', '.join(tam)}); checked against the originals, not written back."
    return head + f"\n  attempts and logs: {res['run_dir']}"
