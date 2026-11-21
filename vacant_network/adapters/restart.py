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
   記在結果、簽章收據與訊息中。`node_modules` 給 agent 獨立副本（優先 `cp --reflink=auto -a`，失敗退回一般複製，
   絕不給 agent 指向原專案 `node_modules` 的可寫路徑，且絕不寫回）；外部驗收對未動過的原專案 `node_modules`
   以唯讀＋symlink／`NODE_PATH` 執行並在結束後立刻移除，且於開始、每次驗收前／後與結束時以內容清單（sha256＋mode＋
   型別＋symlink 目標）重驗原專案 `node_modules`。
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
  讀寫得到磁碟上你讀寫得到的一切；這層只保護「交回寫回」與「驗收流程」本身，擋不住執行期間直接讀寫專案外或其他路徑的檔案。
  Linux 上於執行期間啟用 `prctl(PR_SET_CHILD_SUBREAPER, 1)`，於每次 agent 嘗試後（驗收前）、每次驗收／基線後與結束前，
  透過 `/proc/*/stat`（`ppid == vacant_pid`）與 `VACANT_RUN_ID` 雙訊號抓出並 `SIGKILL` 脫離子孫行程（即使 `setsid`＋`env -i`），
  記於 `detached_processes`；**非 Linux 平台沒有此防護層**（記 `null` 並在交付訊息明講）。**A write by a detached process after delivery is not recorded.**
  另開始與結束時會對原專案做純 `lstat` 清單比對（含整棵 `.git`——包括 `.git/objects/info/**` 與 `.git/objects/pack/**` 的完整 `lstat`，
  以及 `.git/objects/??/` 鬆散物件的純檔名集合比對（不讀物件內容、不對鬆散物件逐檔 `lstat`）——以及任意深度的 `node_modules`／`.venv`／
  `__pycache__`／`.pytest_cache` 與任意處 symlink，並排除 Vacant 自己的 `VACANT_HOME`／`VACANT_WORK`），偵測並回報計畫寫回以外的異動。
  `COPY_SKIP` 名稱（如 `.git`、`node_modules`、`.venv`、`__pycache__`、`.pytest_cache`）不會寫回原專案（agent 在其下新建的檔案會列在 `not_delivered`）。
- 驗收追蹤狀態（`acceptance_integrity: "traced" | "untraced"`）：指令分析器採保守二分法——唯有完全追蹤每個執行的簡單指令、
  其直接執行的專案檔案、npm/yarn/pnpm 腳本與設定、make 目標（含 `.PHONY` 與 `.DEFAULT_GOAL`）、`unittest discover` 匹配檔、
  與 runner 設定（`package.json`／`jest.config.*`／`vitest.config.*`／`.mocharc.*`），且**固定不變清單非空**時才記為 `traced`；
  只要有任何無法追蹤到底的語法／指令／腳本逃逸（Python `os.system`/`subprocess`/`ctypes`/動態匯入/非固定 `open`/`pathlib`、
  Node `fs`/`child_process`/`vm`/動態 `require`/`import`/`eval`/`process.binding`、或直接執行腳本匯入專案模組），一律標為 `untraced`。
  多數實務上的檢查腳本會是 `untraced`；`traced` 只代表分析器追蹤了每個執行的檔案並將它們固定為開始時內容，**不代表檢查本身正確，也不代表沒有其他檔案影響結果**。
  交付訊息只陳述事實（`kept fixed (restored to their start content before each check):`、變更檔列表、`untraced` 短標籤），
  僅當具體偵測到交件嘗試改動了檢查會讀取或執行且未固定的檔案時，才印出 `NOTE:` 提醒。
- **同帳號簽署金鑰結構邊界（0.9.2 未修正）**：簽章私鑰（`$VACANT_HOME/intake/keys/verifier/identity.key`）是同帳號所有行程都讀得到的檔案，
  包含 agent 本身。兩面如實陳述：
  - 收據**能防事後竄改**（改動或刪除任一筆紀錄，其後所有雜湊與簽章都會驗證失敗）；
  - 收據**不能防同一 OS 使用者底下的行程偽造**，因為同使用者行程（包括 agent 自己）讀得到私鑰並能簽出可通過驗證的紀錄。
- 驗收依賴標記（`acceptance_dependencies_changed`）涵蓋測試檔字串常值、Python／JS 最深 2 層遞移匯入（含 `jest.mock`）與
  `fixtures/`／`testdata/`／`test_data/`／`__fixtures__/`／`__mocks__/`／`mocks/`／`golden/`／`data/`／測試目錄，且排除受測模組本身（單一直接匯入）。
  **Dynamic imports and paths computed at runtime are not traced.**
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
  於匯入標準庫／`pytest` 之前先從 `sys.path` 剔除 `""`、`.`、腳本目錄與工作區，匯入執行器自身相依後再把工作區插在 `sys.path` 前端（與使用者直接跑 `python -m unittest`／`pytest` 一致；開始時不存在且會遮蔽已解析模組的新檔仍由 rc5e 排除於驗收副本外），
  依原測試檔精確路徑載入（防止套件目錄或標準庫遮蔽），並透過獨立 session（結束或逾時皆 `killpg` 整組清除）、
  獨立管線（FD）與單次隨機 nonce 回傳結果（不依賴 stdout 固定標記；`pytest` 的 junitxml 寫在工作區外私密目錄）。
  外部指令（`--check`、`npm`、`cargo`、`go`）同樣於快照副本中以獨立 session（結束或逾時皆 `killpg`）與共用期限執行；
  若原專案有 `node_modules`，僅於外部驗收當下以 acceptance-only symlink（＋`NODE_PATH`）掛進驗收副本並於結束後立即移除
  （不放進 agent 的 `ws` 也不寫回；但驗收期間執行的候選碼仍以使用者權限執行，理論上仍可透過 symlink 寫入 `node_modules`）。
  ⚠ 另 Python 路徑的**候選程式碼與測試框架仍在同一個 Python 行程內執行**，故無法防禦惡意候選碼在行程內 monkey-patch
  測試框架或執行期狀態（若需要雙行程隔離，請用 `vacant_network.checks.run_python_check`）；跨生態系測試檔、測試設定檔
  （含 `conftest.py`、`pytest.ini`、`pyproject.toml`、`jest.config.*`、`playwright.config.*`、`cypress.config.*`、
  `wdio.conf.*`、`ava.config.*`、`.nycrc*`、`noxfile.py` 等）、manifest（`package.json`／`Cargo.toml`／`go.mod`／
  `Makefile`）、`--check` 指令列點名的專案既有檔案與 `--protect` 指定檔受保護；測試所匯入的輔助模組與 `fixtures/`／
  `testdata/`／`test_data/`／`__fixtures__/` 下被改動的檔案不阻擋，改以 `acceptance_dependencies_changed` 標記提醒審閱。
- 寫回安全邊界：寫回前先相對「開始時的原專案快照」規劃與驗證所有增／改／刪操作再套用——只刪除開始時存在且交件嘗試刪除的檔，
  執行期間新出現在原專案的檔絕不刪除（記於 `appeared_during_run`），開始後在原專案已被改動且交件嘗試亦欲改／刪的檔標為 `conflict`
  並保留原專案版本；先刪後增、透過同目錄暫存檔＋`os.replace` 原子置換（不原地覆寫硬連結 inode、不把檔案寫進既有目錄）；
  符號連結、無法讀取的目錄／檔案、或與非空／受保護目錄衝突的路徑一律跳過並記於 `changed["skipped"]`，不會寫到專案外面也不會誤刪原檔；
  若套用途中遇非預期錯誤會回滾，維持原專案不變。
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
import shlex
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
_FIXTURE_DIRS = frozenset({
    "fixtures", "testdata", "test_data", "__fixtures__",
    "__mocks__", "mocks", "golden", "data",
})
_DETACHED_MARKER_ENV = "VACANT_RUN_ID"
_JS_EXTS = (".js", ".cjs", ".mjs", ".ts", ".cts", ".mts", ".jsx", ".tsx")
_JS_REL_IMPORT_RES = (
    re.compile(r"""\brequire\s*\(\s*['"`](\.\.?/[^'"`$]+)['"`]\s*\)"""),
    re.compile(r"""\bimport\s+(?:[^'"]+?\s+from\s+)?['"](\.\.?/[^'"]+)['"]"""),
    re.compile(r"""\bexport\s+[^'"]+?\s+from\s+['"](\.\.?/[^'"]+)['"]"""),
    re.compile(r"""\bimport\s*\(\s*['"`](\.\.?/[^'"`$]+)['"`]\s*\)"""),
    re.compile(r"""\b(?:jest|vi)\.(?:do)?[Mm]ock\s*\(\s*['"`](\.\.?/[^'"`$]+)['"`]"""),
)
_QUOTED_LIT_RE = re.compile(r"""'([^'\n\\]{2,240})'|"([^"\n\\]{2,240})"|`([^`\n\\$]{2,240})`""")
#: 測試設定檔：能改變「測試怎麼跑、算不算過」的檔（pytest 的 conftest 掛鉤、ini 選項；jest／vitest／mocha／babel 設定）。
#: 開始時就有的：和測試檔一樣受保護（驗收前還原、不寫回）。agent 新增的：驗收副本裡不放、不寫回、交件訊息列出。
_TEST_CONFIG_NAMES = frozenset({
    "conftest.py", "pytest.ini", ".pytest.ini", "tox.ini", "setup.cfg", "pyproject.toml",
    "cypress.json", ".nycrc", "noxfile.py",
    ".npmrc", ".yarnrc", ".yarnrc.yml", ".pnpmrc", "pnpm-workspace.yaml",
    ".babelrc", ".swcrc", "tsconfig.json",
})
_TEST_CONFIG_PATTERNS = (
    "jest.config.*", "jest.setup.*", "vitest.config.*", "vitest.workspace.*", "vite.config.*",
    ".mocharc*", ".mocharc.*", "babel.config.*", ".babelrc*", ".babelrc.*", "karma.conf.*",
    "playwright.config.*", "cypress.config.*", "wdio.conf.*", "ava.config.*", ".nycrc.*",
    "tsconfig*.json",
)
_TEST_CONFIG_REL_SUFFIXES = (".cargo/config.toml", ".cargo/config")
_MANIFEST_BY_KIND: dict[str, tuple[str, ...]] = {
    "npm": ("package.json",),
    "cargo": ("Cargo.toml",),
    "go": ("go.mod",),
}
_NPM_LIKE_CMDS = frozenset({"npm", "npx", "yarn", "pnpm"})
_CHECK_MANIFEST_BY_CMD: dict[str, tuple[str, ...]] = {
    "npm": ("package.json",),
    "npx": ("package.json",),
    "yarn": ("package.json",),
    "pnpm": ("package.json",),
    "cargo": ("Cargo.toml",),
    "go": ("go.mod",),
    "make": ("Makefile", "makefile", "GNUmakefile"),
    "gmake": ("Makefile", "makefile", "GNUmakefile"),
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

    while cwd in _sys.path:
        _sys.path.remove(cwd)
    _sys.path.insert(0, cwd)

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

    for p in reversed(extra_paths):
        while p in _sys.path:
            _sys.path.remove(p)
        _sys.path.insert(0, p)

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

    for p in reversed(extra_paths):
        while p in _sys.path:
            _sys.path.remove(p)
        _sys.path.insert(0, p)

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


def _vacant_skip_dirs() -> set[pathlib.Path]:
    """Vacant 自己的狀態與工作區根目錄：若落在專案裡面，不可複製進 agent 工作區，
    也不可列入掃描、快照、B1 清單或寫回計畫（同契約路徑 `_skip_dirs`）。"""
    from ..intake.statepaths import state_dir
    out: set[pathlib.Path] = set()
    for p in (state_dir(), work_root()):
        try:
            out.add(p.resolve())
        except OSError:
            out.add(pathlib.Path(os.path.abspath(str(p))))
    return out


def _skip_rels_for(root: pathlib.Path, skip_abs: set[pathlib.Path] | None = None) -> set[str]:
    """計算 `skip_abs` 中嚴格位於 `root` 底下的相對 POSIX 路徑集合。"""
    sabs = _vacant_skip_dirs() if skip_abs is None else skip_abs
    if not sabs:
        return set()
    try:
        root_res = root.resolve()
    except OSError:
        root_res = pathlib.Path(os.path.abspath(str(root)))
    rels: set[str] = set()
    for sd in sabs:
        if sd == root_res:
            continue
        try:
            rel = sd.relative_to(root_res).as_posix()
        except ValueError:
            continue
        if rel and rel != ".":
            rels.add(rel)
    return rels


def _copytree_ignore(skip_abs: set[pathlib.Path]) -> Callable[[str, list[str]], set[str]]:
    def _ignore(d: str, names: list[str]) -> set[str]:
        ignored = {n for n in names if n in COPY_SKIP}
        try:
            d_res = pathlib.Path(d).resolve()
        except OSError:
            d_res = pathlib.Path(os.path.abspath(d))
        for n in names:
            if n in ignored:
                continue
            cand = d_res / n
            if cand in skip_abs:
                ignored.add(n)
                continue
            try:
                if (pathlib.Path(d) / n).resolve() in skip_abs:
                    ignored.add(n)
            except OSError:
                pass
        return ignored
    return _ignore


def _scan_files(root: pathlib.Path, *, skip_abs: set[pathlib.Path] | None = None) -> tuple[list[str], set[str]]:
    """掃描 root 底下的所有一般檔案（跳過 COPY_SKIP 的目錄與檔案、Vacant 狀態/工作區根目錄、symlink 與特殊檔）。
    同時回傳無法列出內容的目錄相對路徑集合。"""
    out: list[str] = []
    unreadable_dirs: set[str] = set()
    skip_rels = _skip_rels_for(root, skip_abs)

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
            if rel in skip_rels:
                continue
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


def _find_unreadable_paths(root: pathlib.Path, *, skip_abs: set[pathlib.Path] | None = None) -> list[str]:
    """掃描專案內（跳過 COPY_SKIP、Vacant 狀態/工作區根目錄與 symlink）任何不可讀的檔案或目錄。"""
    unreadable: set[str] = set()
    skip_rels = _skip_rels_for(root, skip_abs)
    open_flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)

    def _walk(cur: pathlib.Path, rel_prefix: str) -> None:
        try:
            entries = sorted(os.scandir(cur), key=lambda e: e.name)
        except PermissionError:
            unreadable.add(rel_prefix or ".")
            return
        except OSError:
            return
        if rel_prefix and not os.access(str(cur), os.X_OK):
            unreadable.add(rel_prefix)
            return
        for entry in entries:
            name = entry.name
            if name in COPY_SKIP:
                continue
            rel = f"{rel_prefix}/{name}" if rel_prefix else name
            if rel in skip_rels:
                continue
            try:
                st = entry.stat(follow_symlinks=False)
            except PermissionError:
                if rel_prefix:
                    unreadable.add(rel_prefix)
                    return
                unreadable.add(rel)
                continue
            except OSError:
                continue
            mode = st.st_mode
            if stat.S_ISLNK(mode):
                continue
            if stat.S_ISDIR(mode):
                _walk(cur / name, rel)
            elif stat.S_ISREG(mode):
                try:
                    fd = os.open(str(cur / name), open_flags)
                except PermissionError:
                    unreadable.add(rel)
                except OSError:
                    pass
                else:
                    try:
                        os.close(fd)
                    except OSError:
                        pass

    _walk(root, "")
    return sorted(unreadable)


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


def _make_tree_writable(root: pathlib.Path) -> None:
    """讓 agent 的工作區副本可寫（對所有非 symlink 目錄與檔案加上 u+w，不跟隨 symlink）。"""
    if root.is_symlink() or not root.exists():
        return
    try:
        st = root.lstat()
        os.chmod(root, stat.S_IMODE(st.st_mode) | stat.S_IWUSR)
    except OSError:
        pass
    for dp, dns, fns in os.walk(root, topdown=True, followlinks=False):
        try:
            st = os.lstat(dp)
            if not stat.S_ISLNK(st.st_mode):
                os.chmod(dp, stat.S_IMODE(st.st_mode) | stat.S_IWUSR)
        except OSError:
            pass
        for name in list(dns) + list(fns):
            p = os.path.join(dp, name)
            try:
                st = os.lstat(p)
                if not stat.S_ISLNK(st.st_mode):
                    os.chmod(p, stat.S_IMODE(st.st_mode) | stat.S_IWUSR)
            except OSError:
                pass


_PR_SET_CHILD_SUBREAPER = 36
_PR_GET_CHILD_SUBREAPER = 37


def _linux_proc_available() -> bool:
    return sys.platform.startswith("linux") and os.path.isdir("/proc")


def _set_child_subreaper(enable: bool) -> int | None:
    """在 Linux 上透過 ctypes 呼叫 prctl(PR_SET_CHILD_SUBREAPER, 1/0)，回傳原值；非 Linux 或失敗回傳 None。"""
    if not sys.platform.startswith("linux"):
        return None
    try:
        import ctypes
        libc = ctypes.CDLL(None, use_errno=True)
        prev = ctypes.c_int(0)
        if libc.prctl(_PR_GET_CHILD_SUBREAPER, ctypes.byref(prev), 0, 0, 0) != 0:
            prev_val = 0
        else:
            prev_val = int(prev.value)
        if libc.prctl(_PR_SET_CHILD_SUBREAPER, 1 if enable else 0, 0, 0, 0) != 0:
            return None
        return prev_val
    except Exception:  # noqa: BLE001
        return None


def _read_proc_stat(pid: int) -> tuple[str, str, int, int] | None:
    """讀取 /proc/<pid>/stat，回傳 `(comm, state, ppid, pgrp)`；讀不到回傳 None。"""
    try:
        raw = pathlib.Path("/proc", str(pid), "stat").read_bytes()
    except OSError:
        return None
    txt = raw.decode("utf-8", errors="backslashreplace")
    lp = txt.find("(")
    rp = txt.rfind(")")
    if lp < 0 or rp <= lp:
        return None
    comm = txt[lp + 1:rp]
    fields = txt[rp + 2:].split()
    if len(fields) < 3:
        return None
    try:
        return comm, fields[0], int(fields[1]), int(fields[2])
    except ValueError:
        return None


def _read_proc_cmdline(pid: int, fallback_comm: str = "") -> str:
    """讀取 /proc/<pid>/cmdline 並轉為 byte-safe UTF-8 字串（空時退回 comm）。"""
    try:
        raw = pathlib.Path("/proc", str(pid), "cmdline").read_bytes()
    except OSError:
        raw = b""
    parts = [p for p in raw.split(b"\x00") if p]
    if parts:
        txt = " ".join(p.decode("utf-8", errors="backslashreplace") for p in parts)
    else:
        txt = fallback_comm
    return _safe_str(txt)[0][:512]


def _direct_children_pids() -> set[int]:
    """列出目前 /proc 中 ppid == os.getpid() 且非僵屍的子行程 PID 集合。"""
    if not _linux_proc_available():
        return set()
    me = os.getpid()
    out: set[int] = set()
    try:
        entries = list(os.scandir("/proc"))
    except OSError:
        return out
    for entry in entries:
        if not entry.name.isdigit():
            continue
        pid = int(entry.name)
        if pid == me:
            continue
        info = _read_proc_stat(pid)
        if info is None:
            continue
        _, state, ppid, _ = info
        if ppid == me and state != "Z":
            out.add(pid)
    return out


def _find_detached_processes(marker_val: str, *, known_pids: set[int] | None = None) -> list[int] | None:
    """在 Linux 上以 child subreaper（/proc/*/stat ppid==self）＋環境變數標記（/proc/*/environ）
    找出仍存活的脫離子孫行程（排除自身、既知子行程與僵屍）。非 Linux 或無 /proc 回傳 None。"""
    if not _linux_proc_available():
        return None
    needle = f"{_DETACHED_MARKER_ENV}={marker_val}".encode("utf-8")
    me = os.getpid()
    known = known_pids or set()
    found: set[int] = set()
    try:
        entries = list(os.scandir("/proc"))
    except OSError:
        return None
    for entry in entries:
        if not entry.name.isdigit():
            continue
        pid = int(entry.name)
        if pid == me or pid in known:
            continue
        info = _read_proc_stat(pid)
        if info is None:
            continue
        _, state, ppid, _ = info
        if state == "Z":
            continue
        if ppid == me:
            found.add(pid)
            continue
        try:
            raw = pathlib.Path(entry.path, "environ").read_bytes()
        except OSError:
            continue
        if needle in raw.split(b"\x00"):
            found.add(pid)
    return sorted(found)


def _kill_and_reap_detached(pid: int, pgrp: int, my_pgrp: int) -> bool:
    """以 SIGKILL 結束脫離子孫（安全時殺其行程群組）並短暫等待／reap，回傳是否成功結束。"""
    if pgrp > 1 and pgrp != my_pgrp:
        try:
            os.killpg(pgrp, signal.SIGKILL)
        except (ProcessLookupError, PermissionError, OSError):
            pass
    try:
        os.kill(pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    except (PermissionError, OSError):
        pass

    deadline = time.monotonic() + 0.4
    while time.monotonic() < deadline:
        try:
            wpid, _ = os.waitpid(pid, os.WNOHANG)
            if wpid == pid:
                return True
        except ChildProcessError:
            pass
        except OSError:
            pass
        info = _read_proc_stat(pid)
        if info is None or info[1] == "Z":
            try:
                os.waitpid(pid, os.WNOHANG)
            except OSError:
                pass
            return True
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return True
        except OSError:
            pass
        time.sleep(0.015)

    info = _read_proc_stat(pid)
    return info is None or info[1] == "Z"


def _reap_detached_processes(phase: str, marker_val: str, *,
                             known_pids: set[int]) -> list[dict[str, Any]] | None:
    """在 Linux 上掃描並 SIGKILL 脫離子孫（subreaper ppid 為主、VACANT_RUN_ID 環境變數為輔），
    回傳 `[{"phase", "pid", "cmdline", "killed"}, ...]`；非 Linux 回傳 None。"""
    if not _linux_proc_available():
        return None
    me = os.getpid()
    my_pgrp = os.getpgrp()
    needle = f"{_DETACHED_MARKER_ENV}={marker_val}".encode("utf-8")
    recorded: dict[int, dict[str, Any]] = {}

    for _pass in range(5):
        targets: list[tuple[int, str, int]] = []
        try:
            entries = list(os.scandir("/proc"))
        except OSError:
            return None
        for entry in entries:
            if not entry.name.isdigit():
                continue
            pid = int(entry.name)
            if pid == me or pid in known_pids or pid in recorded:
                continue
            info = _read_proc_stat(pid)
            if info is None:
                continue
            comm, state, ppid, pgrp = info
            if state == "Z":
                if ppid == me:
                    try:
                        os.waitpid(pid, os.WNOHANG)
                    except OSError:
                        pass
                continue
            matched = (ppid == me)
            if not matched:
                try:
                    raw = pathlib.Path(entry.path, "environ").read_bytes()
                    matched = needle in raw.split(b"\x00")
                except OSError:
                    matched = False
            if matched:
                targets.append((pid, comm, pgrp))
        if not targets:
            break
        for pid, comm, pgrp in sorted(targets):
            cmdline = _read_proc_cmdline(pid, comm)
            killed = _kill_and_reap_detached(pid, pgrp, my_pgrp)
            recorded[pid] = {
                "phase": phase,
                "pid": pid,
                "cmdline": cmdline,
                "killed": killed,
            }
        # 短暫讓新被 reparent 到 subreaper 的孫行程浮現
        time.sleep(0.03)

    return [recorded[pid] for pid in sorted(recorded)]


def _dir_has_detectable_tests(d: pathlib.Path) -> bool:
    """快速淺層檢查目錄 d 是否有會被偵測到的測試檔、測試設定檔或測試目錄（不遞迴整棵樹）。"""
    skip_abs = _vacant_skip_dirs()
    try:
        entries = list(os.scandir(d))
    except OSError:
        return False
    for e in entries:
        name = e.name
        if name in COPY_SKIP:
            continue
        try:
            if pathlib.Path(e.path).resolve() in skip_abs:
                continue
        except OSError:
            pass
        try:
            st = e.stat(follow_symlinks=False)
        except OSError:
            continue
        if stat.S_ISLNK(st.st_mode):
            continue
        if stat.S_ISREG(st.st_mode):
            if (_is_python_test(name) or _is_universal_test(name) or _is_test_config(name)
                    or name in ("Cargo.toml", "go.mod")):
                return True
            if name == "package.json" and _npm_test_script(d) is not None:
                return True
        elif stat.S_ISDIR(st.st_mode) and name in _UNIVERSAL_TEST_DIRS:
            # 確認測試目錄內至少有檔案（淺層、上限 200 項）
            seen = 0
            stack = [pathlib.Path(e.path)]
            while stack and seen < 200:
                cur = stack.pop()
                try:
                    sub_entries = list(os.scandir(cur))
                except OSError:
                    continue
                for se in sub_entries:
                    seen += 1
                    if se.name in COPY_SKIP:
                        continue
                    try:
                        sst = se.stat(follow_symlinks=False)
                    except OSError:
                        continue
                    if stat.S_ISREG(sst.st_mode):
                        return True
                    if stat.S_ISDIR(sst.st_mode) and not stat.S_ISLNK(sst.st_mode):
                        stack.append(pathlib.Path(se.path))
    return False


def _find_parent_with_tests(project: pathlib.Path, max_levels: int = 5) -> pathlib.Path | None:
    """向上檢查父目錄（最多 max_levels 層、遇 git 根即止，且不掃 $HOME 與 /）是否含有可偵測的測試。"""
    cur = project.resolve()
    try:
        home = pathlib.Path.home().resolve()
    except (RuntimeError, OSError):
        home = None
    for _ in range(max_levels):
        parent = cur.parent
        if parent == cur or parent == pathlib.Path("/") or (home is not None and parent == home):
            break
        is_git_root = (parent / ".git").exists()
        if _dir_has_detectable_tests(parent):
            return parent
        if is_git_root:
            break
        cur = parent
    return None


def _norm_posix_join(base_parts: tuple[str, ...], rel_spec: str) -> str | None:
    parts = list(base_parts)
    for seg in rel_spec.replace("\\", "/").split("/"):
        if not seg or seg == ".":
            continue
        if seg == "..":
            if not parts:
                return None
            parts.pop()
        else:
            parts.append(seg)
    return "/".join(parts) if parts else None


def _extract_py_imports_and_inits(raw: bytes, rel_path: str, known_files: set[str], *,
                                  start_files: set[str] | frozenset[str] | None = None) -> tuple[set[str], set[str]]:
    """Extract Python imports from `raw` and package `__init__.py` chains.
    Returns `(direct_modules, package_inits)`:
    - `direct_modules`: resolved target `.py` / `/__init__.py` files.
    - `package_inits`: parent package `__init__.py` files along dotted import chains `a.b.c`
      (`a/__init__.py`, `a/b/__init__.py`, plus `src/`-layout and relative equivalents), and
      pre-existing directly imported package `__init__.py` files (never exempted as MUT)."""
    try:
        tree = ast.parse(raw, filename=rel_path)
    except SyntaxError:
        return set(), set()
    parent = pathlib.PurePosixPath(rel_path).parent
    parent_parts = () if parent == pathlib.PurePosixPath(".") else parent.parts
    search_prefixes: list[tuple[str, ...]] = [()]
    if parent_parts and parent_parts not in search_prefixes:
        search_prefixes.append(parent_parts)
    if ("src",) not in search_prefixes:
        search_prefixes.append(("src",))

    out: set[str] = set()
    pkg_inits: set[str] = set()

    def _add_parent_inits(base_prefixes: list[tuple[str, ...]], mod_parts: list[str]) -> None:
        if len(mod_parts) < 2:
            return
        for k in range(1, len(mod_parts)):
            for pref in base_prefixes:
                cand = "/".join((*pref, *mod_parts[:k], "__init__.py"))
                if cand in known_files:
                    pkg_inits.add(cand)

    def _resolve(base_prefixes: list[tuple[str, ...]], mod_parts: list[str], *,
                 is_dotted: bool = False) -> bool:
        if not mod_parts:
            return False
        found = False
        for pref in base_prefixes:
            cand_base = "/".join((*pref, *mod_parts))
            cand_py = cand_base + ".py"
            cand_init = cand_base + "/__init__.py"
            if cand_py in known_files:
                out.add(cand_py)
                found = True
            if cand_init in known_files:
                out.add(cand_init)
                found = True
                if (is_dotted or start_files is None
                        or cand_init in start_files
                        or any(f.startswith(cand_base + "/") for f in start_files)):
                    pkg_inits.add(cand_init)
        return found

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                mod_parts = [p for p in alias.name.split(".") if p]
                _add_parent_inits(search_prefixes, mod_parts)
                _resolve(search_prefixes, mod_parts, is_dotted=(len(mod_parts) >= 2))
        elif isinstance(node, ast.ImportFrom):
            if node.level and node.level > 0:
                up = node.level - 1
                if up <= len(parent_parts):
                    rel_pref = [parent_parts[:len(parent_parts) - up]]
                else:
                    rel_pref = []
            else:
                rel_pref = search_prefixes
            mod_parts = [p for p in (node.module or "").split(".") if p]
            submod_resolved = False
            for alias in node.names:
                if alias.name == "*":
                    continue
                sub_parts = [*mod_parts, alias.name]
                if _resolve(rel_pref, sub_parts, is_dotted=(len(sub_parts) >= 2)):
                    submod_resolved = True
                    _add_parent_inits(rel_pref, sub_parts)
            if mod_parts:
                _add_parent_inits(rel_pref, mod_parts)
                _resolve(rel_pref, mod_parts, is_dotted=(len(mod_parts) >= 2 or submod_resolved))
    out.discard(rel_path)
    pkg_inits.discard(rel_path)
    return out, pkg_inits


def _extract_py_imports(raw: bytes, rel_path: str, known_files: set[str]) -> set[str]:
    direct, _ = _extract_py_imports_and_inits(raw, rel_path, known_files)
    return direct


def _extract_js_imports(raw: bytes, rel_path: str, known_files: set[str]) -> set[str]:
    parent = pathlib.PurePosixPath(rel_path).parent
    parent_parts = () if parent == pathlib.PurePosixPath(".") else parent.parts
    txt = raw.decode("utf-8", errors="replace")
    specs: set[str] = set()
    for rx in _JS_REL_IMPORT_RES:
        for m in rx.finditer(txt):
            specs.add(m.group(1))
    out: set[str] = set()
    for sp in specs:
        norm = _norm_posix_join(parent_parts, sp)
        if not norm:
            continue
        if norm in known_files:
            out.add(norm)
            continue
        for ext in (*_JS_EXTS, ".json"):
            if norm + ext in known_files:
                out.add(norm + ext)
            if f"{norm}/index{ext}" in known_files:
                out.add(f"{norm}/index{ext}")
    out.discard(rel_path)
    return out


def _extract_string_literals(raw: bytes, rel_path: str) -> set[str]:
    lits: set[str] = set()
    if rel_path.endswith(".py"):
        try:
            tree = ast.parse(raw, filename=rel_path)
            for node in ast.walk(tree):
                if isinstance(node, ast.Constant) and isinstance(node.value, str):
                    val = node.value.strip().replace("\\", "/")
                    while val.startswith("./"):
                        val = val[2:]
                    if 2 <= len(val) <= 240:
                        lits.add(val)
            return lits
        except SyntaxError:
            pass
    txt = raw.decode("utf-8", errors="replace")
    for m in _QUOTED_LIT_RE.finditer(txt):
        raw_s = m.group(1) or m.group(2) or m.group(3) or ""
        val = raw_s.strip().replace("\\", "/")
        while val.startswith("./"):
            val = val[2:]
        if 2 <= len(val) <= 240:
            lits.add(val)
    return lits


def _read_source_bytes(rel: str, source_root: pathlib.Path | None, originals: dict[str, bytes]) -> bytes | None:
    if source_root is not None:
        p = source_root / rel
        try:
            if p.is_file() and not p.is_symlink():
                return p.read_bytes()
        except OSError:
            pass
    return originals.get(rel)


def _find_acceptance_dependencies(originals: dict[str, bytes], known_files: set[str],
                                  delivered_changed: set[str], *,
                                  source_root: pathlib.Path | None = None,
                                  extra_unfixed: dict[str, tuple[str, ...]] | None = None,
                                  start_files: set[str] | frozenset[str] | None = None) -> list[dict[str, Any]]:
    """找出交件嘗試所改動、且驗收依賴的檔案（僅標記提醒人審閱，不阻擋交件）：
    (a) 受保護測試檔中以字串常值出現其檔名或相對路徑的已變更檔（reason: literal）；
    (b) 受保護 Python 測試檔與固定腳本遞移匯入（最深 2 層 AST）的專案模組（reason: import），
        以及點狀匯入鏈與既有套件的 `__init__.py`（reason: package-init，不適用單一受測模組豁免）；
    (c) 受保護 JS/TS 測試檔遞移 require/import/jest.mock（最深 2 層）的專案模組（reason: import）；
    (d) 位於 fixtures/、testdata/、test_data/、__fixtures__/、__mocks__/、mocks/、golden/、data/
        或測試目錄下的檔案（reason: dir）。
    若某非測試模組是單一測試檔唯一直接匯入的非測試原始碼（即受測模組本身），不因該直接匯入將其標記。
    註：動態匯入（importlib/__import__）與執行期組合之路徑不追蹤。"""
    if not delivered_changed:
        return []
    protected_set = set(originals)
    dir_roots = _FIXTURE_DIRS | _UNIVERSAL_TEST_DIRS
    reasons: dict[str, set[str]] = {}

    def _add_reason(rel: str, why: str) -> None:
        if rel in delivered_changed:
            reasons.setdefault(rel, set()).add(why)

    def _in_special_dir(rel: str) -> bool:
        parts = pathlib.PurePosixPath(rel).parts
        return any(d in dir_roots for d in parts[:-1])

    # (d) fixture / mock / golden / data / test 目錄
    for rel in delivered_changed:
        if _in_special_dir(rel):
            _add_reason(rel, "dir")

    # 收集每個測試檔的字串常值與深度 1/2 匯入
    all_literals: set[str] = set()
    for test_rel, raw in originals.items():
        if not (_is_universal_test(test_rel) or _is_python_test(test_rel) or test_rel.endswith((".sh", ".bash"))):
            # 仍對非純設定檔（排除 package.json/Cargo.toml/go.mod）抽出字面路徑
            bn = pathlib.PurePosixPath(test_rel).name
            if bn in ("package.json", "Cargo.toml", "go.mod") or _is_test_config(test_rel):
                continue
        all_literals |= _extract_string_literals(raw, test_rel)

        if test_rel.endswith(".py"):
            d1, d1_inits = _extract_py_imports_and_inits(raw, test_rel, known_files, start_files=start_files)
            for init_rel in d1_inits:
                if init_rel not in protected_set:
                    _add_reason(init_rel, "package-init")
            non_test_d1 = {
                m for m in d1
                if m not in protected_set and not _in_special_dir(m) and m not in d1_inits
            }
            # 單一直接匯入非測試源檔（受測模組）不以直接匯入標記
            if len(non_test_d1) > 1:
                for m in non_test_d1:
                    _add_reason(m, "import")
            # 深度 2（遞移匯入，包含從受測模組出發的第 2 層）
            for m1 in d1:
                if not m1.endswith(".py"):
                    continue
                m1_raw = _read_source_bytes(m1, source_root, originals)
                if m1_raw is None:
                    continue
                is_brand_new_sole_mut = (
                    start_files is not None
                    and len(non_test_d1) == 1
                    and m1 in non_test_d1
                    and m1 not in start_files
                )
                m2_direct, m2_inits = _extract_py_imports_and_inits(
                    m1_raw, m1, known_files, start_files=start_files
                )
                for m2 in m2_direct:
                    if m2 in protected_set or m2 in m2_inits:
                        continue
                    if is_brand_new_sole_mut and m2 not in start_files:
                        continue
                    _add_reason(m2, "import")
                for m2_init in m2_inits:
                    if m2_init in protected_set:
                        continue
                    if is_brand_new_sole_mut and m2_init not in start_files:
                        continue
                    _add_reason(m2_init, "package-init")
        elif test_rel.endswith(_JS_EXTS):
            d1 = _extract_js_imports(raw, test_rel, known_files)
            non_test_d1 = {m for m in d1 if m not in protected_set and not _in_special_dir(m)}
            if len(non_test_d1) > 1:
                for m in non_test_d1:
                    _add_reason(m, "import")
            for m1 in d1:
                if not m1.endswith(_JS_EXTS):
                    continue
                m1_raw = _read_source_bytes(m1, source_root, originals)
                if m1_raw is None:
                    continue
                for m2 in _extract_js_imports(m1_raw, m1, known_files):
                    if m2 not in protected_set:
                        _add_reason(m2, "import")

    # (a) 受保護測試檔中的字串常值比對已變更檔的相對路徑或檔名
    if all_literals:
        for rel in delivered_changed:
            if rel in protected_set:
                continue
            bn = pathlib.PurePosixPath(rel).name
            if len(bn) < 2:
                continue
            for lit in all_literals:
                if lit == rel or lit == bn or lit.endswith("/" + rel) or lit.endswith("/" + bn):
                    _add_reason(rel, "literal")
                    break

    # (e) files found by the acceptance command analyzer that could not be kept fixed
    if extra_unfixed:
        for rel, rs in extra_unfixed.items():
            if rel not in protected_set and rel in delivered_changed:
                for why in rs:
                    _add_reason(rel, why)

    # 排序：先列 literal/dir/analyzer（直接驗收資料/常值/未固定腳本目標），再列 import（匯入輔助模組），同層按路徑字母排序
    def _sort_key(item: tuple[str, set[str]]) -> tuple[int, str]:
        rel, rs = item
        prio = 0 if (rs - {"import"}) else 1
        return (prio, rel)

    return [
        {"path": rel, "reasons": sorted(rs)}
        for rel, rs in sorted(reasons.items(), key=_sort_key)
    ]


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


def _is_test_config(rel: str) -> bool:
    norm = rel.replace("\\", "/")
    if norm in _TEST_CONFIG_REL_SUFFIXES or any(norm.endswith("/" + s) for s in _TEST_CONFIG_REL_SUFFIXES):
        return True
    name = pathlib.PurePosixPath(norm).name
    return name in _TEST_CONFIG_NAMES or any(fnmatch.fnmatchcase(name, p) for p in _TEST_CONFIG_PATTERNS)


def _is_universal_test(rel: str) -> bool:
    parts = pathlib.PurePosixPath(rel).parts
    if any(d in _UNIVERSAL_TEST_DIRS for d in parts[:-1]):
        return True
    name = parts[-1]
    return any(fnmatch.fnmatchcase(name, p) for p in _UNIVERSAL_TEST_NAME_PATTERNS)


def _is_protected_by_default(rel: str) -> bool:
    return _is_universal_test(rel) or _is_test_config(rel)


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


_SHELL_OPS = frozenset({";", "&&", "||", "|", "&", "|&", "\n"})
_SHELL_WRAPPER_CMDS = frozenset({"sh", "bash", "dash", "zsh", "ash", "ksh"})


def _has_shell_expansion(cmd: str) -> bool:
    """偵測命令字串是否含單引號外的 $VAR / ${...} / $(...) 或反引號展開。"""
    in_single = False
    escaped = False
    i = 0
    n = len(cmd)
    while i < n:
        ch = cmd[i]
        if escaped:
            escaped = False
            i += 1
            continue
        if in_single:
            if ch == "'":
                in_single = False
            i += 1
            continue
        if ch == "\\":
            escaped = True
            i += 1
            continue
        if ch == "'":
            in_single = True
            i += 1
            continue
        if ch == "`":
            return True
        if ch == "$" and i + 1 < n:
            nxt = cmd[i + 1]
            if nxt.isalpha() or nxt in ("_", "{", "(", "*", "@", "?", "#", "$", "!") or nxt.isdigit():
                return True
        i += 1
    return False


def _split_shell_segments(cmd: str) -> list[list[str]]:
    """將 shell 指令字串依 `;`, `&&`, `||`, `|` 等運算子拆成多個指令段（保留引號語義）。"""
    try:
        lex = shlex.shlex(cmd, posix=True, punctuation_chars=";&|")
        lex.whitespace_split = True
        raw_tokens = list(lex)
    except ValueError:
        raw_tokens = []
        for part in re.split(r"(?:&&|\|\||[;|])", cmd):
            toks = part.split()
            if toks:
                raw_tokens.extend(toks)
                raw_tokens.append(";")
    segments: list[list[str]] = []
    cur: list[str] = []
    for tok in raw_tokens:
        if tok in _SHELL_OPS:
            if cur:
                segments.append(cur)
                cur = []
        else:
            cur.append(tok)
    if cur:
        segments.append(cur)
    return segments


def _is_env_assign(tok: str) -> bool:
    return "=" in tok and not tok.startswith("=") and tok.split("=", 1)[0].replace("_", "").isalnum()


def _parse_check_shell_cmd(cmd: str, *, _cur_dir: tuple[str, ...] = (),
                           _depth: int = 0) -> tuple[set[str], list[tuple[str, tuple[str, ...]]], bool]:
    """遞迴解析 `--check` 指令：拆開 `;`/`&&`/`||`/`|`，遞迴展開 `sh -c`/`bash -c`/`env`/`timeout`/`nice`/`cd`，
    回傳 `(cmd_words, [(token, cur_dir_parts), ...], uses_shell_expansion)`。"""
    if _depth > 8:
        return set(), [], False
    uses_exp = _has_shell_expansion(cmd)
    cmd_words: set[str] = set()
    all_tokens: list[tuple[str, tuple[str, ...]]] = []
    cur_dir = _cur_dir

    def _consume_segment(tokens: list[str], seg_dir: tuple[str, ...], depth: int) -> tuple[str, ...]:
        nonlocal uses_exp
        if not tokens or depth > 8:
            return seg_dir
        for t in tokens:
            all_tokens.append((t, seg_dir))
        i = 0
        n = len(tokens)
        while i < n and _is_env_assign(tokens[i]):
            i += 1
        if i >= n:
            return seg_dir
        base = pathlib.PurePosixPath(tokens[i]).name
        cmd_words.add(base)
        rest = tokens[i + 1:]

        if base == "cd":
            for t in rest:
                if t == "--" or t.startswith("-"):
                    continue
                if t.startswith("/"):
                    return ()
                joined = _norm_posix_join(seg_dir, t)
                return tuple(joined.split("/")) if joined else ()
            return seg_dir

        if base == "env":
            j = 0
            new_dir = seg_dir
            while j < len(rest):
                t = rest[j]
                if t == "--":
                    j += 1
                    break
                if t == "-C" and j + 1 < len(rest):
                    d_arg = rest[j + 1]
                    joined = _norm_posix_join(new_dir, d_arg) if not d_arg.startswith("/") else None
                    new_dir = tuple(joined.split("/")) if joined else ()
                    j += 2
                    continue
                if t == "-S" and j + 1 < len(rest):
                    cw, at, ex = _parse_check_shell_cmd(rest[j + 1], _cur_dir=new_dir, _depth=depth + 1)
                    cmd_words.update(cw)
                    all_tokens.extend(at)
                    uses_exp = uses_exp or ex
                    j += 2
                    continue
                if t in ("-u", "-P") and j + 1 < len(rest):
                    j += 2
                    continue
                if t.startswith("-") or _is_env_assign(t):
                    j += 1
                    continue
                break
            if j < len(rest):
                return _consume_segment(rest[j:], new_dir, depth + 1)
            return new_dir

        if base == "timeout":
            j = 0
            while j < len(rest):
                t = rest[j]
                if t == "--":
                    j += 1
                    break
                if t in ("-k", "-s", "--kill-after", "--signal") and j + 1 < len(rest):
                    j += 2
                    continue
                if t.startswith("-"):
                    j += 1
                    continue
                break
            if j < len(rest):
                j += 1  # skip DURATION
            if j < len(rest):
                return _consume_segment(rest[j:], seg_dir, depth + 1)
            return seg_dir

        if base == "nice":
            j = 0
            while j < len(rest):
                t = rest[j]
                if t == "--":
                    j += 1
                    break
                if t == "-n" and j + 1 < len(rest):
                    j += 2
                    continue
                if t.startswith("-"):
                    j += 1
                    continue
                break
            if j < len(rest):
                return _consume_segment(rest[j:], seg_dir, depth + 1)
            return seg_dir

        if base in ("sudo", "nohup", "time", "exec", "command", "setsid"):
            j = 0
            while j < len(rest):
                t = rest[j]
                if t == "--":
                    j += 1
                    break
                if base == "sudo" and t in ("-u", "-g", "-C", "-D", "-p", "-r", "-t") and j + 1 < len(rest):
                    j += 2
                    continue
                if t.startswith("-"):
                    j += 1
                    continue
                break
            if j < len(rest):
                return _consume_segment(rest[j:], seg_dir, depth + 1)
            return seg_dir

        if base in _SHELL_WRAPPER_CMDS:
            j = 0
            while j < len(rest):
                t = rest[j]
                if t == "--":
                    break
                if t == "-c" or (t.startswith("-") and not t.startswith("--") and "c" in t[1:]):
                    if j + 1 < len(rest):
                        cw, at, ex = _parse_check_shell_cmd(rest[j + 1], _cur_dir=seg_dir, _depth=depth + 1)
                        cmd_words.update(cw)
                        all_tokens.extend(at)
                        uses_exp = uses_exp or ex
                    break
                if t in ("-o", "+o") and j + 1 < len(rest):
                    j += 2
                    continue
                if t.startswith("-") or t.startswith("+"):
                    j += 1
                    continue
                break
            return seg_dir

        if base == "eval" and rest:
            cw, at, ex = _parse_check_shell_cmd(" ".join(rest), _cur_dir=seg_dir, _depth=depth + 1)
            cmd_words.update(cw)
            all_tokens.extend(at)
            uses_exp = uses_exp or ex
            return seg_dir

        return seg_dir

    for seg in _split_shell_segments(cmd):
        cur_dir = _consume_segment(seg, cur_dir, _depth)
    return cmd_words, all_tokens, uses_exp


def _npm_script_at(pkg_json: pathlib.Path, script_name: str = "test") -> str | None:
    opened = _open_reg_readonly(pkg_json)
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
    sc = scripts.get(script_name)
    if not isinstance(sc, str) or not sc.strip():
        return None
    if script_name == "test" and _NPM_DEFAULT_TEST_MARKER in sc:
        return None
    return sc.strip()


def _npm_test_script_at(pkg_json: pathlib.Path) -> str | None:
    return _npm_script_at(pkg_json, "test")


_SHELL_RESERVED_WORDS = frozenset({
    "if", "then", "else", "elif", "fi", "for", "while", "until", "do", "done",
    "case", "esac", "select", "function", "{", "}", "[[", "]]", "!", "coproc",
})
_UNSAFE_ENV_ASSIGN_KEYS = frozenset({
    "PATH", "PYTHONPATH", "NODE_PATH", "NODE_OPTIONS", "PYTHONSTARTUP",
    "LD_PRELOAD", "LD_LIBRARY_PATH", "BASH_ENV", "ENV", "PERL5LIB",
    "RUBYLIB", "PYTHONHOME", "PYTHONUSERBASE",
})
_KNOWN_JS_RUNNERS = frozenset({"jest", "vitest", "mocha", "ava"})
_PKG_RUNNER_CONFIG_KEYS = ("jest", "mocha", "ava", "vitest", "nyc", "c8", "babel", "eslintConfig")
_JS_RUNNER_DEFAULT_CONFIG_PATTERNS: dict[str, tuple[str, ...]] = {
    "jest": ("jest.config.*",),
    "vitest": ("vitest.config.*",),
    "mocha": (".mocharc", ".mocharc.*"),
    "ava": ("ava.config.*",),
}
_CONFIG_PATH_EXTS = (
    ".js", ".cjs", ".mjs", ".ts", ".cts", ".mts", ".jsx", ".tsx",
    ".json", ".jsonc", ".yaml", ".yml", ".toml", ".py", ".sh", ".bash", ".txt",
)
_PY_TOOL_RE = re.compile(r"^python(?:3(?:\.\d+)?)?$")
_JS_ANY_REL_IMPORT_RES = (
    re.compile(r"""\brequire\s*\(\s*['"`](\.\.?/[^'"`]*)['"`]\s*\)"""),
    re.compile(r"""\bimport\s+(?:[^'"]+?\s+from\s+)?['"](\.\.?/[^'"]*)['"]"""),
    re.compile(r"""\bexport\s+[^'"]+?\s+from\s+['"](\.\.?/[^'"]*)['"]"""),
    re.compile(r"""\bimport\s*\(\s*['"`](\.\.?/[^'"`]*)['"`]\s*\)"""),
)
_JS_FORBIDDEN_MOD_RES = (
    re.compile(r"""\brequire\s*\(\s*['"`](?:node:)?(fs(?:/promises)?|child_process|worker_threads|vm)['"`]\s*\)"""),
    re.compile(r"""\b(?:import|export)\s+(?:[^'"]+?\s+from\s+)?['"](?:node:)?(fs(?:/promises)?|child_process|worker_threads|vm)['"]"""),
    re.compile(r"""\bimport\s*\(\s*['"`](?:node:)?(fs(?:/promises)?|child_process|worker_threads|vm)['"`]\s*\)"""),
)
_JS_REQUIRE_CALL_RE = re.compile(r"""\brequire\s*\(""")
_JS_IMPORT_CALL_RE = re.compile(r"""\bimport\s*\(""")
_JS_PROCESS_BINDING_RE = re.compile(r"""\bprocess\s*\.\s*binding\b""")
_JS_EVAL_RE = re.compile(r"""\beval\s*\(""")
_JS_NEW_FUNC_RE = re.compile(r"""\bnew\s+Function\b""")
_PY_DYN_CALL_NAMES = frozenset({"__import__", "eval", "exec", "compile"})
_PY_DYN_MODULES = frozenset({"importlib", "runpy"})
_PY_DYN_IMPORT_HITS = frozenset({
    "importlib", "import_module", "spec_from_file_location",
    "runpy", "run_path", "run_module", "__import__", "eval", "exec",
})
_PY_PROC_MODULES = frozenset({"subprocess", "pty", "ctypes"})
_PY_PROC_OS_FUNCS = frozenset({
    "system", "popen",
    "execl", "execle", "execlp", "execlpe", "execv", "execve", "execvp", "execvpe",
    "spawnl", "spawnle", "spawnlp", "spawnlpe", "spawnv", "spawnve", "spawnvp", "spawnvpe",
    "posix_spawn", "posix_spawnp",
})
_MAKE_COMPLEX_DIRECTIVES = frozenset({
    "include", "-include", "sinclude", "define", "endef",
    "ifeq", "ifneq", "ifdef", "ifndef", "else", "endif", "override", "export",
})
@dataclasses.dataclass
class _AcceptanceAnalysis:
    integrity: str                                  # "traced" | "untraced"
    reasons: list[str]
    protected: set[str]
    pinned_scripts: dict[str, str]                  # pkg_rel -> scripts.test
    pinned_named_scripts: dict[str, dict[str, str]] # pkg_rel -> {script_name: cmd}
    shell_expansion: bool = False
    ignored_new_paths: set[str] = dataclasses.field(default_factory=set)
    ignored_new_globs: list[tuple[str, str]] = dataclasses.field(default_factory=list)
    unfixed_deps: dict[str, set[str]] = dataclasses.field(default_factory=dict)
    runs_project_code: bool = False
    py_sys_path_dirs: set[str] = dataclasses.field(default_factory=set)
    py_interpreters: list[str] = dataclasses.field(default_factory=list)
    uses_python: bool = False
    unittest_start_dirs: set[str] = dataclasses.field(default_factory=set)


def _tokenize_simple_shell(cmd: str) -> tuple[list[list[str]], list[str], bool]:
    """Conservative POSIX shell lexer for acceptance integrity analysis.
    Accepts ONLY simple commands separated by `;`, `&&`, `||`, `|`.
    Any expansion, redirection, here-doc, subshell, brace grouping, background `&`,
    unquoted glob (`*`, `?`, `[`), or unclosed quote records a reason."""
    reasons: list[str] = []
    uses_exp = False
    segments: list[list[str]] = []
    cur_seg: list[str] = []
    buf: list[str] = []
    has_tok = False
    in_single = False
    in_double = False
    escaped = False
    i = 0
    n = len(cmd)

    def _add_reason(msg: str) -> None:
        if msg not in reasons:
            reasons.append(msg)

    def _flush_tok() -> None:
        nonlocal has_tok
        if has_tok:
            cur_seg.append("".join(buf))
            buf.clear()
            has_tok = False

    def _flush_seg() -> None:
        _flush_tok()
        if cur_seg:
            segments.append(list(cur_seg))
            cur_seg.clear()

    while i < n:
        ch = cmd[i]
        if escaped:
            buf.append(ch)
            has_tok = True
            escaped = False
            i += 1
            continue
        if in_single:
            if ch == "'":
                in_single = False
            else:
                buf.append(ch)
            i += 1
            continue
        if in_double:
            if ch == "\\":
                if i + 1 < n and cmd[i + 1] in ('"', "\\", "$", "`", "\n"):
                    if cmd[i + 1] != "\n":
                        buf.append(cmd[i + 1])
                    i += 2
                    continue
                buf.append(ch)
                i += 1
                continue
            if ch == '"':
                in_double = False
                i += 1
                continue
            if ch == "`":
                uses_exp = True
                _add_reason("uses shell expansion (backticks)")
                buf.append(ch)
                i += 1
                continue
            if ch == "$" and i + 1 < n:
                nxt = cmd[i + 1]
                if nxt.isalpha() or nxt in ("_", "{", "(", "*", "@", "?", "#", "$", "!") or nxt.isdigit():
                    uses_exp = True
                    _add_reason("uses shell expansion ($VAR or $(...))")
            buf.append(ch)
            i += 1
            continue

        # Unquoted context
        if ch in (" ", "\t", "\r"):
            _flush_tok()
            i += 1
            continue
        if ch == "\n":
            _flush_seg()
            i += 1
            continue
        if ch == "#" and not has_tok:
            # Comment to end of line
            while i < n and cmd[i] != "\n":
                i += 1
            continue
        if ch == "\\":
            if i + 1 < n and cmd[i + 1] == "\n":
                i += 2
                continue
            escaped = True
            has_tok = True
            i += 1
            continue
        if ch == "'":
            in_single = True
            has_tok = True
            i += 1
            continue
        if ch == '"':
            in_double = True
            has_tok = True
            i += 1
            continue
        if ch == "`":
            uses_exp = True
            _add_reason("uses shell expansion (backticks)")
            buf.append(ch)
            has_tok = True
            i += 1
            continue
        if ch == "$" and i + 1 < n:
            nxt = cmd[i + 1]
            if nxt.isalpha() or nxt in ("_", "{", "(", "*", "@", "?", "#", "$", "!") or nxt.isdigit():
                uses_exp = True
                _add_reason("uses shell expansion ($VAR or $(...))")
            buf.append(ch)
            has_tok = True
            i += 1
            continue
        if ch == ";":
            if i + 1 < n and cmd[i + 1] == ";":
                _add_reason("shell case syntax (;;)")
                i += 2
                continue
            _flush_seg()
            i += 1
            continue
        if ch == "&":
            if i + 1 < n and cmd[i + 1] == "&":
                _flush_seg()
                i += 2
                continue
            _add_reason("background or fd operator (&)")
            _flush_seg()
            i += 1
            continue
        if ch == "|":
            if i + 1 < n and cmd[i + 1] == "|":
                _flush_seg()
                i += 2
                continue
            if i + 1 < n and cmd[i + 1] == "&":
                _add_reason("shell stderr pipe operator (|&)")
                _flush_seg()
                i += 2
                continue
            _flush_seg()
            i += 1
            continue
        if ch in ("(", ")"):
            _add_reason("subshell or function syntax")
            _flush_seg()
            i += 1
            continue
        if ch == "<":
            if i + 1 < n and cmd[i + 1] == "<":
                _add_reason("here-doc or here-string redirection")
                i += 3 if (i + 2 < n and cmd[i + 2] == "<") else 2
                _flush_seg()
                continue
            if i + 1 < n and cmd[i + 1] == "(":
                _add_reason("process substitution")
                i += 2
                _flush_seg()
                continue
            _add_reason("shell input redirection")
            _flush_seg()
            i += 1
            continue
        if ch == ">":
            if i + 1 < n and cmd[i + 1] == "(":
                _add_reason("process substitution")
                i += 2
                _flush_seg()
                continue
            _add_reason("shell output redirection")
            _flush_seg()
            i += 2 if (i + 1 < n and cmd[i + 1] in (">", "&")) else 1
            continue
        if ch in ("*", "?", "["):
            _add_reason("unquoted shell globbing")
            buf.append(ch)
            has_tok = True
            i += 1
            continue
        buf.append(ch)
        has_tok = True
        i += 1

    if in_single or in_double or escaped:
        _add_reason("unclosed quote or trailing escape")
    _flush_seg()
    return segments, reasons, uses_exp


def _resolve_project_file(project: pathlib.Path, proj_res: pathlib.Path, files_set: set[str],
                          tok: str, cur_dir: tuple[str, ...]) -> str | None:
    raw = tok.strip().replace("\\", "/")
    if not raw or raw in (".", ".."):
        return None
    p = pathlib.Path(raw)
    if p.is_absolute():
        try:
            rel = p.resolve().relative_to(proj_res).as_posix()
        except (ValueError, OSError):
            return None
        return rel if rel in files_set else None
    joined = _norm_posix_join(cur_dir, raw)
    if joined and joined in files_set:
        return joined
    return None


def _resolve_project_subdir(project: pathlib.Path, proj_res: pathlib.Path,
                            tok: str, cur_dir: tuple[str, ...]) -> tuple[str, ...] | None:
    raw = tok.strip().replace("\\", "/")
    if not raw:
        return None
    if raw == ".":
        return cur_dir
    p = pathlib.Path(raw)
    if p.is_absolute():
        try:
            rel = p.resolve().relative_to(proj_res).as_posix()
        except (ValueError, OSError):
            return None
        if rel == ".":
            return ()
        return tuple(rel.split("/"))
    joined = _norm_posix_join(cur_dir, raw)
    if joined is None:
        return None
    cand = project / joined
    try:
        if not cand.is_dir() or _through_symlink(project, joined):
            return None
    except OSError:
        return None
    return tuple(joined.split("/"))


def _strip_js_comments(src: str) -> str:
    """Strip // and /* */ comments from JS/JSONC while preserving string literals and newlines."""
    out: list[str] = []
    i = 0
    n = len(src)
    while i < n:
        ch = src[i]
        if ch in ("'", '"', "`"):
            quote = ch
            out.append(ch)
            i += 1
            while i < n:
                c = src[i]
                out.append(c)
                if c == "\\" and i + 1 < n:
                    out.append(src[i + 1])
                    i += 2
                    continue
                if c == quote:
                    i += 1
                    break
                i += 1
            continue
        if ch == "/" and i + 1 < n and src[i + 1] == "/":
            i += 2
            while i < n and src[i] != "\n":
                i += 1
            continue
        if ch == "/" and i + 1 < n and src[i + 1] == "*":
            i += 2
            while i + 1 < n and not (src[i] == "*" and src[i + 1] == "/"):
                if src[i] == "\n":
                    out.append("\n")
                i += 1
            i = min(n, i + 2)
            out.append(" ")
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def _is_pure_js_literal_arg(text: str, pos: int, *, allow_second_obj: bool = False) -> bool:
    """Return True iff text[pos:] (immediately after '(') begins with a pure string literal
    (no concatenation, no template ${...}) followed directly by ')' (or ', {' if allow_second_obj)."""
    n = len(text)
    i = pos
    while i < n and text[i] in (" ", "\t", "\r", "\n"):
        i += 1
    if i >= n or text[i] not in ("'", '"', "`"):
        return False
    quote = text[i]
    i += 1
    while i < n:
        c = text[i]
        if c == "\\" and i + 1 < n:
            i += 2
            continue
        if quote == "`" and c == "$" and i + 1 < n and text[i + 1] == "{":
            return False
        if c == quote:
            i += 1
            break
        i += 1
    else:
        return False
    while i < n and text[i] in (" ", "\t", "\r", "\n"):
        i += 1
    if i < n and text[i] == ")":
        return True
    if i < n and text[i] == ",":
        i += 1
        while i < n and text[i] in (" ", "\t", "\r", "\n"):
            i += 1
        if i < n and text[i] == ")":
            return True
        if allow_second_obj and i < n and text[i] == "{":
            return True
    return False


def _extract_cmd_file_refs(node: ast.Call, project: pathlib.Path | None, proj_res: pathlib.Path | None,
                           files_set: set[str], cur_dir: tuple[str, ...]) -> set[str]:
    """Best-effort extraction of existing project files named in constant string/list args of os.system/subprocess."""
    refs: set[str] = set()
    if project is None or proj_res is None:
        return refs
    tokens: list[str] = []
    if node.args:
        a0 = node.args[0]
        if isinstance(a0, ast.Constant) and isinstance(a0.value, str):
            try:
                tokens.extend(shlex.split(a0.value))
            except ValueError:
                tokens.extend(a0.value.split())
        elif isinstance(a0, (ast.List, ast.Tuple)):
            for el in a0.elts:
                if isinstance(el, ast.Constant) and isinstance(el.value, str):
                    tokens.append(el.value)
    for tok in tokens:
        rel = _resolve_project_file(project, proj_res, files_set, tok, cur_dir)
        if rel is not None:
            refs.add(rel)
    return refs


def _py_analyze_code_ast(raw: bytes, label: str, files_set: set[str], *,
                         inline: bool = False,
                         project: pathlib.Path | None = None,
                         proj_res: pathlib.Path | None = None,
                         cur_dir: tuple[str, ...] = ()) -> tuple[list[str], set[str], dict[str, set[str]]]:
    """Unified AST check for both Python FILE scripts and `python -c` inline code.
    Flags:
    - project-local imports;
    - process execution: os.system, os.popen, os.exec*/os.spawn*, subprocess.*, pty.*, ctypes;
    - dynamic code: importlib, runpy, __import__, eval, exec, compile;
    - file reads: open() with non-constant path, open() of unprotected relative path,
      pathlib read_text/read_bytes/open.
    A constant open() path resolving to an existing project file is added to extra_protected instead."""
    extra_protected: set[str] = set()
    unfixed_deps: dict[str, set[str]] = {}
    try:
        tree = ast.parse(raw, filename=label)
    except SyntaxError:
        return [f"could not parse python code: {label}"], extra_protected, unfixed_deps

    reasons: list[str] = []
    kind_s = "python -c" if inline else f"script {label}"
    rel_for_imports = label if not inline else "__inline__.py"
    _local_direct, _local_inits = _extract_py_imports_and_inits(raw, rel_for_imports, files_set)
    local_mods = _local_direct | _local_inits
    rel_imports: set[str] = set()
    proc_hits: set[str] = set()
    dyn_hits: set[str] = set()
    io_reasons: list[str] = []

    os_aliases: set[str] = {"os"}
    from_os_proc: dict[str, str] = {}
    open_aliases: set[str] = {"open"}
    io_mod_aliases: set[str] = {"io", "builtins", "codecs"}

    def _add_io(msg: str) -> None:
        if msg not in io_reasons:
            io_reasons.append(msg)

    # First pass: track imports & aliases
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                top = alias.name.split(".", 1)[0]
                as_name = alias.asname or top
                if top == "os" and alias.name == "os":
                    os_aliases.add(as_name)
                if top in ("io", "builtins", "codecs") and alias.name == top:
                    io_mod_aliases.add(as_name)
                if top in _PY_PROC_MODULES:
                    proc_hits.add(top)
                elif top in _PY_DYN_MODULES:
                    dyn_hits.add(top)
        elif isinstance(node, ast.ImportFrom):
            if node.level and node.level > 0:
                rel_imports.add("." * node.level + (node.module or ""))
            mod = node.module or ""
            top = mod.split(".", 1)[0]
            if top in _PY_PROC_MODULES:
                proc_hits.add(top)
            elif top in _PY_DYN_MODULES:
                dyn_hits.add(top)
            elif mod == "os":
                for alias in node.names:
                    if alias.name in _PY_PROC_OS_FUNCS:
                        full = f"os.{alias.name}"
                        proc_hits.add(full)
                        from_os_proc[alias.asname or alias.name] = full
            elif mod in ("io", "builtins", "codecs"):
                for alias in node.names:
                    if alias.name == "open":
                        open_aliases.add(alias.asname or "open")
                    elif mod == "builtins" and alias.name in _PY_DYN_CALL_NAMES:
                        dyn_hits.add(alias.name)

    # Second pass: inspect calls
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        # 1. Process execution calls
        if isinstance(fn, ast.Attribute) and fn.attr in _PY_PROC_OS_FUNCS:
            is_os = isinstance(fn.value, ast.Name) and fn.value.id in os_aliases
            proc_hits.add(f"os.{fn.attr}" if is_os else fn.attr)
            for ref in _extract_cmd_file_refs(node, project, proj_res, files_set, cur_dir):
                unfixed_deps.setdefault(ref, set()).add("script-exec")
            continue
        if isinstance(fn, ast.Attribute) and isinstance(fn.value, ast.Name) and fn.value.id == "subprocess":
            proc_hits.add(f"subprocess.{fn.attr}")
            for ref in _extract_cmd_file_refs(node, project, proj_res, files_set, cur_dir):
                unfixed_deps.setdefault(ref, set()).add("script-exec")
            continue
        if isinstance(fn, ast.Name) and fn.id in from_os_proc:
            proc_hits.add(from_os_proc[fn.id])
            for ref in _extract_cmd_file_refs(node, project, proj_res, files_set, cur_dir):
                unfixed_deps.setdefault(ref, set()).add("script-exec")
            continue

        # 2. Dynamic code calls
        if isinstance(fn, ast.Name) and fn.id in _PY_DYN_CALL_NAMES:
            dyn_hits.add(fn.id)
            continue
        if isinstance(fn, ast.Attribute) and fn.attr in ("import_module", "spec_from_file_location", "run_path", "run_module"):
            dyn_hits.add(fn.attr)
            continue

        # 3. File reading: open(...)
        is_builtin_open = (
            (isinstance(fn, ast.Name) and fn.id in open_aliases)
            or (isinstance(fn, ast.Attribute) and fn.attr == "open"
                and isinstance(fn.value, ast.Name) and fn.value.id in io_mod_aliases)
        )
        if is_builtin_open:
            path_arg: ast.expr | None = node.args[0] if node.args else None
            if path_arg is None:
                for kw in node.keywords:
                    if kw.arg in ("file", "filename"):
                        path_arg = kw.value
                        break
            if isinstance(path_arg, ast.Constant) and isinstance(path_arg.value, str):
                s = path_arg.value
                rel: str | None = None
                if project is not None and proj_res is not None:
                    rel = _resolve_project_file(project, proj_res, files_set, s, cur_dir)
                elif s in files_set:
                    rel = s
                if rel is not None:
                    extra_protected.add(rel)
                elif not os.path.isabs(s):
                    _add_io(f"{kind_s} uses open() of unprotected path {s!r}")
                    cand = _norm_posix_join(cur_dir, s)
                    if cand:
                        unfixed_deps.setdefault(cand, set()).add("script-open")
                elif s != "/dev/null":
                    _add_io(f"{kind_s} uses open() of outside path {s!r}")
            else:
                _add_io(f"{kind_s} uses open() with non-constant path")
            continue

        # 4. pathlib read_text / read_bytes / open
        if isinstance(fn, ast.Attribute) and fn.attr in ("read_text", "read_bytes", "open"):
            _add_io(f"{kind_s} uses pathlib.{fn.attr}()")
            # Best-effort: extract constant Path("foo.txt") target for concrete NOTE reporting
            if isinstance(fn.value, ast.Call) and fn.value.args:
                p0 = fn.value.args[0]
                if isinstance(p0, ast.Constant) and isinstance(p0.value, str) and not os.path.isabs(p0.value):
                    cand = _norm_posix_join(cur_dir, p0.value)
                    if cand:
                        unfixed_deps.setdefault(cand, set()).add("script-read")

    all_local = sorted(local_mods | rel_imports)
    if all_local:
        if inline:
            reasons.append(f"python -c imports project modules: {', '.join(all_local[:8])}")
        else:
            reasons.append(f"script imports project modules: {label} -> {', '.join(all_local[:8])}")
    if proc_hits:
        reasons.append(f"{kind_s} uses process execution: {', '.join(sorted(proc_hits)[:8])}")
    if dyn_hits:
        if dyn_hits & _PY_DYN_IMPORT_HITS:
            reasons.append(f"dynamic-import: {kind_s} uses {', '.join(sorted(dyn_hits)[:8])}")
        else:
            reasons.append(f"{kind_s} uses dynamic code: {', '.join(sorted(dyn_hits)[:8])}")
    reasons.extend(io_reasons)
    return reasons, extra_protected, unfixed_deps


def _py_find_dynamic_imports(raw: bytes, label: str) -> list[str]:
    """Detect dynamic import/execution constructs in Python source:
    importlib.import_module, importlib.util.spec_from_file_location, __import__, exec, eval, runpy."""
    try:
        tree = ast.parse(raw, filename=label)
    except SyntaxError:
        return []
    hits: set[str] = set()
    builtins_aliases: set[str] = {"builtins"}
    dyn_name_map: dict[str, str] = {
        "__import__": "__import__",
        "exec": "exec",
        "eval": "eval",
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                top = alias.name.split(".", 1)[0]
                as_name = alias.asname or top
                if top == "runpy":
                    hits.add("runpy")
                elif top == "builtins" and alias.name == "builtins":
                    builtins_aliases.add(as_name)
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            top = mod.split(".", 1)[0]
            if top == "runpy":
                hits.add("runpy")
            elif mod == "importlib":
                for alias in node.names:
                    if alias.name in ("import_module", "*"):
                        hits.add("importlib.import_module")
                        if alias.name == "import_module":
                            dyn_name_map[alias.asname or "import_module"] = "importlib.import_module"
            elif mod == "importlib.util":
                for alias in node.names:
                    if alias.name in ("spec_from_file_location", "*"):
                        hits.add("importlib.util.spec_from_file_location")
                        if alias.name == "spec_from_file_location":
                            dyn_name_map[alias.asname or "spec_from_file_location"] = "importlib.util.spec_from_file_location"
            elif mod == "builtins":
                for alias in node.names:
                    if alias.name in ("__import__", "exec", "eval"):
                        hits.add(alias.name)
                        dyn_name_map[alias.asname or alias.name] = alias.name
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            if node.attr == "import_module":
                hits.add("importlib.import_module")
            elif node.attr == "spec_from_file_location":
                hits.add("importlib.util.spec_from_file_location")
            elif node.attr in ("run_path", "run_module"):
                hits.add("runpy")
            elif (node.attr in ("__import__", "exec", "eval")
                  and isinstance(node.value, ast.Name)
                  and node.value.id in builtins_aliases):
                hits.add(node.attr)
        elif isinstance(node, ast.Call):
            fn = node.func
            if isinstance(fn, ast.Name) and fn.id in dyn_name_map:
                hits.add(dyn_name_map[fn.id])
    return sorted(hits)


def _scan_protected_dynamic_imports(
    project: pathlib.Path,
    protected: Sequence[str],
    *,
    originals: dict[str, bytes] | None = None,
    existing_reasons: Sequence[str] = (),
) -> list[str]:
    """Scan protected Python test files / kept-fixed scripts for dynamic imports/exec."""
    out: list[str] = []
    orig_map = originals or {}
    for rel in sorted(protected):
        is_py = rel.endswith(".py")
        raw = orig_map.get(rel)
        if raw is None:
            raw = _read_source_bytes(rel, project, {})
        if raw is None:
            continue
        if not is_py:
            first_line = raw.splitlines()[0].decode("utf-8", errors="replace").strip() if raw else ""
            if not (first_line.startswith("#!") and "python" in first_line.lower()):
                continue
        if any(r.startswith("dynamic-import:") and rel in r for r in existing_reasons):
            continue
        hits = _py_find_dynamic_imports(raw, rel)
        if hits:
            out.append(f"dynamic-import: {rel} uses {', '.join(hits)}")
    return out


def _js_analyze_file(raw: bytes, rel_path: str, files_set: set[str]) -> list[str]:
    """Check whether JS/TS script imports project-local modules or uses fs/process/vm/dynamic require/eval."""
    reasons: list[str] = []

    def _add(msg: str) -> None:
        if msg not in reasons:
            reasons.append(msg)

    resolved_local = _extract_js_imports(raw, rel_path, files_set)
    txt = _strip_js_comments(raw.decode("utf-8", errors="replace"))
    raw_rel_specs: set[str] = set()
    for rx in _JS_ANY_REL_IMPORT_RES:
        for m in rx.finditer(txt):
            raw_rel_specs.add(m.group(1))
    local_labels = sorted(resolved_local) if resolved_local else sorted(raw_rel_specs)
    if local_labels:
        _add(f"script imports project modules: {rel_path} -> {', '.join(local_labels[:8])}")

    # Forbidden Node built-ins: fs, fs/promises, child_process, worker_threads, vm
    forbidden_mods: list[str] = []
    for rx in _JS_FORBIDDEN_MOD_RES:
        for m in rx.finditer(txt):
            mod = m.group(1)
            if mod not in forbidden_mods:
                forbidden_mods.append(mod)
    if forbidden_mods:
        _add(f"script {rel_path} requires/imports {', '.join(forbidden_mods[:6])}")

    # Non-literal require(...)
    for m in _JS_REQUIRE_CALL_RE.finditer(txt):
        if not _is_pure_js_literal_arg(txt, m.end()):
            _add(f"script {rel_path} uses non-literal require()")
            break

    # Dynamic import(...) with non-literal argument
    for m in _JS_IMPORT_CALL_RE.finditer(txt):
        if not _is_pure_js_literal_arg(txt, m.end(), allow_second_obj=True):
            _add(f"script {rel_path} uses dynamic import()")
            break

    if _JS_PROCESS_BINDING_RE.search(txt):
        _add(f"script {rel_path} uses process.binding")
    if _JS_EVAL_RE.search(txt):
        _add(f"script {rel_path} uses eval()")
    if _JS_NEW_FUNC_RE.search(txt):
        _add(f"script {rel_path} uses new Function")
    return reasons


def _looks_like_config_path(s: str) -> bool:
    """Return True if a runner-config string value looks like a filesystem path (vs env/package name)."""
    t = s.strip()
    if not t:
        return False
    if "<rootDir>" in t:
        return True
    if t.startswith(("./", "../", "/", "~/")):
        return True
    if t.startswith(("http://", "https://")):
        return False
    if any(t.lower().endswith(ext) for ext in _CONFIG_PATH_EXTS):
        return True
    if "/" in t:
        # Exclude scoped npm package names like @babel/preset-env or @jest/globals
        if re.match(r"^@[A-Za-z0-9._-]+/[A-Za-z0-9._-]+$", t):
            return False
        # Exclude obvious regexes without path prefix
        if t.startswith("^") or "\\" in t:
            return False
        return True
    return False


def _resolve_js_config_file(project: pathlib.Path, proj_res: pathlib.Path, files_set: set[str],
                            spec_s: str, base_dir: tuple[str, ...]) -> str | None:
    """Resolve a path-like string in a JS runner config to an existing project file (supporting JS/TS ext fallback)."""
    raw = spec_s.strip().replace("\\", "/")
    if not raw or raw in (".", ".."):
        return None
    direct = _resolve_project_file(project, proj_res, files_set, raw, base_dir)
    if direct is not None:
        return direct
    for ext in (*_JS_EXTS, ".json"):
        cand = _resolve_project_file(project, proj_res, files_set, raw + ext, base_dir)
        if cand is not None:
            return cand
    for ext in _JS_EXTS:
        cand = _resolve_project_file(project, proj_res, files_set, raw.rstrip("/") + "/index" + ext, base_dir)
        if cand is not None:
            return cand
    return None


def _parse_simple_yaml(text: str) -> tuple[Any, bool]:
    """Parse YAML runner config (uses PyYAML if available, else a conservative stdlib parser).
    Returns (parsed_obj, ok)."""
    try:
        import yaml  # type: ignore[import-not-found]
        return yaml.safe_load(text), True
    except ImportError:
        pass
    except Exception:  # noqa: BLE001
        return None, False

    def _unquote(v: str) -> str:
        s = v.strip()
        if len(s) >= 2 and s[0] == s[-1] and s[0] in ("'", '"'):
            return s[1:-1]
        return s

    out: list[Any] = []
    for raw_ln in text.splitlines():
        ln = raw_ln.strip()
        if not ln or ln.startswith("#"):
            continue
        # Strip inline comment outside quotes
        if "#" in ln and not (ln.startswith(("'", '"'))):
            ln = re.split(r"\s+#", ln, maxsplit=1)[0].strip()
        if not ln:
            continue
        if re.search(r"(?:^|\s)[&*!]\S", ln):
            return None, False
        if ln.startswith("- "):
            item = ln[2:].strip()
            if item.startswith("[") and item.endswith("]"):
                out.extend(_unquote(x) for x in item[1:-1].split(",") if x.strip())
            else:
                out.append(_unquote(item))
            continue
        if ":" in ln:
            _, _, rhs = ln.partition(":")
            rhs = rhs.strip()
            if not rhs:
                continue
            if rhs.startswith("[") and rhs.endswith("]"):
                out.extend(_unquote(x) for x in rhs[1:-1].split(",") if x.strip())
            elif rhs.startswith("{") and rhs.endswith("}"):
                try:
                    out.append(json.loads(rhs))
                except ValueError:
                    return None, False
            else:
                out.append(_unquote(rhs))
            continue
        return None, False
    return out, True


_JS_CFG_NONLITERAL_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bpath\s*\.\s*(?:resolve|join)\s*\("), "path.resolve/join"),
    (re.compile(r"\b__dirname\b|\b__filename\b"), "__dirname/__filename"),
    (re.compile(r"\bprocess\s*\.\s*cwd\s*\("), "process.cwd()"),
    (re.compile(r"`[^`]*\$\{"), "template interpolation"),
    (re.compile(r"""['"`]\s*\+|\+\s*['"`]"""), "string concatenation"),
    (_JS_EVAL_RE, "eval()"),
    (_JS_NEW_FUNC_RE, "new Function"),
    (_JS_PROCESS_BINDING_RE, "process.binding"),
)
_JS_CFG_PATH_KEYS_RE = re.compile(
    r"""\b(?:setupFiles|setupFilesAfterEnv|globalSetup|globalTeardown|require|spec|"""
    r"""resolver|runner|transform|moduleNameMapper|preset|roots|testMatch|testRegex|"""
    r"""file|files|include|exclude|config)\s*:\s*([^,}\]\n]+)"""
)
_JS_STR_LIT_RE = re.compile(
    r"""'((?:[^'\\\n]|\\.)*)'|"((?:[^"\\\n]|\\.)*)"|`((?:[^`\\\n$]|\\.)*)`"""
)


def _analyze_js_runner_config_text(raw: bytes, rel_path: str) -> tuple[list[str], list[str]]:
    """Scan a JS/TS runner config file (e.g. jest.config.js, vitest.config.ts, .mocharc.js).
    Returns (string_literals, unverified_reasons)."""
    reasons: list[str] = []

    def _add(msg: str) -> None:
        if msg not in reasons:
            reasons.append(msg)

    txt = _strip_js_comments(raw.decode("utf-8", errors="replace"))
    for rx, label in _JS_CFG_NONLITERAL_PATTERNS:
        if rx.search(txt):
            _add(f"{rel_path}: non-literal path expression ({label})")
    for rx in _JS_FORBIDDEN_MOD_RES:
        m = rx.search(txt)
        if m:
            _add(f"{rel_path}: requires/imports {m.group(1)}")
    for m in _JS_REQUIRE_CALL_RE.finditer(txt):
        if not _is_pure_js_literal_arg(txt, m.end()):
            _add(f"{rel_path}: non-literal require()")
            break
    for m in _JS_IMPORT_CALL_RE.finditer(txt):
        if not _is_pure_js_literal_arg(txt, m.end(), allow_second_obj=True):
            _add(f"{rel_path}: dynamic import()")
            break
    # Check path-bearing config keys for non-literal values (e.g. setupFiles: [getSetup()] or setupFiles: arr)
    for m in _JS_CFG_PATH_KEYS_RE.finditer(txt):
        val = m.group(1).strip()
        if not val:
            continue
        if val[0] in ("'", '"', "`", "{"):
            continue
        if val.startswith("["):
            # Inspect items inside the array up to matching ']'
            start_b = m.start(1) + 1
            end_b = txt.find("]", start_b)
            inner = txt[start_b:end_b] if end_b >= 0 else val[1:]
            # Remove all string literals from inner; only commas/whitespace should remain
            rem = _JS_STR_LIT_RE.sub("", inner)
            if re.sub(r"[\s,]+", "", rem):
                _add(f"{rel_path}: non-literal path in runner config array")
        elif val not in ("true", "false", "null", "undefined") and not re.match(r"^\d+$", val):
            _add(f"{rel_path}: non-literal path value in runner config")

    lits: list[str] = []
    for m in _JS_STR_LIT_RE.finditer(txt):
        s = m.group(1) if m.group(1) is not None else (m.group(2) if m.group(2) is not None else m.group(3))
        if s is not None:
            lits.append(s)
    return lits, reasons


def _parse_makefile_targets(raw: bytes, rel_path: str) -> tuple[dict[str, tuple[list[str], list[str]]], str | None, set[str], list[str]]:
    """Conservative Makefile parser. Returns (targets_map, default_target, phony_targets, reasons).
    targets_map: target_name -> (prerequisites, recipe_lines)."""
    reasons: list[str] = []
    if b"\x00" in raw:
        return {}, None, set(), [f"binary Makefile: {rel_path}"]
    text = raw.decode("utf-8", errors="replace")
    raw_lines = text.splitlines()
    # Join backslash-continued lines
    lines: list[tuple[bool, str]] = []
    i = 0
    while i < len(raw_lines):
        ln = raw_lines[i]
        is_tab = ln.startswith("\t")
        while ln.endswith("\\") and i + 1 < len(raw_lines):
            i += 1
            ln = ln[:-1] + " " + raw_lines[i].lstrip()
        lines.append((is_tab, ln))
        i += 1

    targets: dict[str, tuple[list[str], list[str]]] = {}
    phony_targets: set[str] = set()
    first_target: str | None = None
    default_goal_set = False
    default_goal_val: str | None = None
    default_goal_unresolvable = False
    cur_targets: list[str] = []

    for is_tab, ln in lines:
        if is_tab:
            if cur_targets:
                recipe = ln.lstrip("\t").strip()
                if recipe and not recipe.startswith("#"):
                    for t in cur_targets:
                        targets[t][1].append(recipe)
            continue
        stripped = ln.strip()
        if not stripped or stripped.startswith("#"):
            cur_targets = []
            continue
        first_word = stripped.split(None, 1)[0]
        if first_word in _MAKE_COMPLEX_DIRECTIVES:
            reasons.append(f"Makefile uses untraceable directive ({first_word}): {rel_path}")
            cur_targets = []
            continue
        if "$(shell" in stripped or "${shell" in stripped:
            reasons.append(f"Makefile uses $(shell ...): {rel_path}")
            cur_targets = []
            continue
        # Variable assignment (outside rule), including names starting with '.' (e.g. .DEFAULT_GOAL)
        m_assign = re.match(r"^([A-Za-z_.][A-Za-z0-9_.-]*)\s*(::=|:=|\?=|\+=|!=|=)(.*)$", stripped)
        if m_assign:
            var_name, op, rhs_val = m_assign.group(1), m_assign.group(2), m_assign.group(3)
            if op == "!=":
                reasons.append(f"Makefile uses != shell assignment: {rel_path}")
            elif var_name == ".DEFAULT_GOAL":
                val = rhs_val.split("#", 1)[0].strip()
                if op == "+=":
                    default_goal_unresolvable = True
                elif op == "?=":
                    if not default_goal_set:
                        if "$" in val or "%" in val:
                            default_goal_unresolvable = True
                        elif val:
                            toks = val.split()
                            if len(toks) == 1:
                                default_goal_val = toks[0]
                                default_goal_set = True
                            else:
                                default_goal_unresolvable = True
                else:  # "=", ":=", "::="
                    if "$" in val or "%" in val:
                        default_goal_unresolvable = True
                    elif not val:
                        default_goal_val = None
                        default_goal_set = False
                    else:
                        toks = val.split()
                        if len(toks) == 1:
                            default_goal_val = toks[0]
                            default_goal_set = True
                        else:
                            default_goal_unresolvable = True
            cur_targets = []
            continue
        # Rule header: target(s): prereqs
        if "::" in stripped:
            reasons.append(f"Makefile uses double-colon rule: {rel_path}")
            cur_targets = []
            continue
        if ":" in stripped:
            lhs, _, rhs = stripped.partition(":")
            lhs_s = lhs.strip()
            if "%" in lhs_s or "$" in lhs_s:
                reasons.append(f"Makefile uses pattern/variable target: {rel_path}")
                cur_targets = []
                continue
            rhs_clean = rhs.split("#", 1)[0].strip()
            inline_recipe: str | None = None
            if ";" in rhs_clean:
                rhs_clean, _, inline_recipe = rhs_clean.partition(";")
                inline_recipe = inline_recipe.strip()
            t_names = lhs_s.split()
            prereqs = rhs_clean.split()
            if ".PHONY" in t_names:
                for pr in prereqs:
                    if "$" not in pr and "%" not in pr:
                        phony_targets.add(pr)
                cur_targets = []
                continue
            cur_targets = []
            for t in t_names:
                if t.startswith("."):
                    continue
                if first_target is None:
                    first_target = t
                if t not in targets:
                    targets[t] = (list(prereqs), [])
                else:
                    targets[t][0].extend(prereqs)
                if inline_recipe:
                    targets[t][1].append(inline_recipe)
                cur_targets.append(t)
            continue
        reasons.append(f"unrecognized Makefile line in {rel_path}: {stripped[:60]}")
        cur_targets = []

    if default_goal_unresolvable:
        reasons.append(f"Makefile defines .DEFAULT_GOAL unresolvably: {rel_path}")
        default_target = first_target
    elif default_goal_set and default_goal_val:
        default_target = default_goal_val
    else:
        default_target = first_target

    return targets, default_target, phony_targets, reasons


def _analyze_acceptance_command(project: pathlib.Path, cmd: str,
                                files_set: set[str]) -> _AcceptanceAnalysis:
    """Binary acceptance integrity analyzer: either FULLY UNDERSTOOD ('verified') or 'unverified'.
    Conservative by design: when unsure -> unverified."""
    proj_res = project.resolve()
    reasons: list[str] = []
    protected: set[str] = set()
    pinned_scripts: dict[str, str] = {}
    pinned_named_scripts: dict[str, dict[str, str]] = {}
    ignored_new_paths: set[str] = set()
    ignored_new_globs: list[tuple[str, str]] = []
    unfixed_deps: dict[str, set[str]] = {}
    py_sys_path_dirs: set[str] = set()
    py_interpreters: list[str] = []
    unittest_start_dirs: set[str] = set()
    uses_exp = False
    runs_project_code = False
    uses_python = False
    visited: set[tuple[str, str, str]] = set()
    max_depth = 12

    def _note_py_interp(tok: str) -> None:
        nonlocal uses_python
        uses_python = True
        resolved = tok if os.path.isabs(tok) else shutil.which(tok)
        if resolved and resolved not in py_interpreters:
            py_interpreters.append(resolved)

    def _note_py_file_dir(rel: str) -> None:
        p = pathlib.PurePosixPath(rel).parent
        py_sys_path_dirs.add("" if p == pathlib.PurePosixPath(".") else p.as_posix())

    def _fail(msg: str) -> None:
        if msg not in reasons:
            reasons.append(msg)

    def _add_unfixed(rel: str, why: str) -> None:
        if rel:
            unfixed_deps.setdefault(rel, set()).add(why)

    def _analyze_py_file(rel: str, cur_dir: tuple[str, ...] = ()) -> None:
        nonlocal uses_python
        uses_python = True
        py_sys_path_dirs.add("/".join(cur_dir))
        _note_py_file_dir(rel)
        protected.add(rel)
        raw = _read_source_bytes(rel, project, {})
        if raw is None:
            _fail(f"could not read python script: {rel}")
            return
        py_reasons, extra_prot, py_unfixed = _py_analyze_code_ast(
            raw, rel, files_set, inline=False, project=project, proj_res=proj_res, cur_dir=cur_dir
        )
        protected.update(extra_prot)
        for u_rel, u_rs in py_unfixed.items():
            for ur in u_rs:
                _add_unfixed(u_rel, ur)
        for r in py_reasons:
            _fail(r)

    def _analyze_js_file(rel: str) -> None:
        protected.add(rel)
        raw = _read_source_bytes(rel, project, {})
        if raw is None:
            _fail(f"could not read js script: {rel}")
            return
        for r in _js_analyze_file(raw, rel, files_set):
            _fail(r)

    def _scan_config_string(s: str, source_rel: str, base_dir: tuple[str, ...]) -> None:
        t = s.strip()
        if not t:
            return
        if "<rootDir>" in t:
            if t.startswith("<rootDir>/"):
                sub = t[len("<rootDir>/"):]
                if any(c in "$*?[](){}<>" for c in sub):
                    _fail(f"{source_rel}: unresolvable <rootDir> expansion {t!r}")
                    return
                rel = _resolve_js_config_file(project, proj_res, files_set, sub, base_dir)
                if rel is not None:
                    protected.add(rel)
                    return
                _fail(f"{source_rel}: unresolvable <rootDir> path {t!r}")
                cand = _norm_posix_join(base_dir, sub)
                if cand:
                    _add_unfixed(cand, "runner-config")
                return
            _fail(f"{source_rel}: unresolvable <rootDir> reference {t!r}")
            return
        if _looks_like_config_path(t):
            rel = _resolve_js_config_file(project, proj_res, files_set, t, base_dir)
            if rel is not None:
                protected.add(rel)
                return
            _fail(f"{source_rel}: unresolvable config path {t!r}")
            if not os.path.isabs(t) and not any(c in "*?[]" for c in t):
                cand = _norm_posix_join(base_dir, t)
                if cand:
                    _add_unfixed(cand, "runner-config")

    def _scan_runner_config_obj(obj: Any, source_rel: str, base_dir: tuple[str, ...]) -> None:
        if isinstance(obj, str):
            _scan_config_string(obj, source_rel, base_dir)
        elif isinstance(obj, list):
            for item in obj:
                _scan_runner_config_obj(item, source_rel, base_dir)
        elif isinstance(obj, dict):
            for v in obj.values():
                _scan_runner_config_obj(v, source_rel, base_dir)

    def _scan_runner_config_file(cfg_rel: str) -> None:
        protected.add(cfg_rel)
        vkey = ("rcfg", cfg_rel, "")
        if vkey in visited:
            return
        visited.add(vkey)
        raw = _read_source_bytes(cfg_rel, project, {})
        if raw is None:
            _fail(f"could not read runner config: {cfg_rel}")
            return
        cfg_parts = pathlib.PurePosixPath(cfg_rel).parts[:-1]
        base_dir = tuple(cfg_parts)
        bn = pathlib.PurePosixPath(cfg_rel).name.lower()
        if bn.endswith((".json", ".jsonc")) or (bn == ".mocharc" and raw.lstrip().startswith(b"{")):
            txt = raw.decode("utf-8", errors="replace")
            if bn.endswith(".jsonc"):
                txt = _strip_js_comments(txt)
            try:
                data = json.loads(txt)
            except ValueError:
                _fail(f"could not parse runner config JSON: {cfg_rel}")
                return
            _scan_runner_config_obj(data, cfg_rel, base_dir)
            return
        if bn.endswith((".yml", ".yaml")):
            data, ok = _parse_simple_yaml(raw.decode("utf-8", errors="replace"))
            if not ok:
                _fail(f"could not parse runner config YAML: {cfg_rel}")
                return
            _scan_runner_config_obj(data, cfg_rel, base_dir)
            return
        if bn.endswith(_JS_EXTS):
            lits, js_reasons = _analyze_js_runner_config_text(raw, cfg_rel)
            for jr in js_reasons:
                _fail(jr)
            for lit in lits:
                _scan_config_string(lit, cfg_rel, base_dir)
            return
        _fail(f"unsupported runner config format: {cfg_rel}")

    def _scan_pkg_runner_configs(pkg_rel: str, pkg_dir: tuple[str, ...]) -> None:
        vkey = ("pkgcfg", pkg_rel, "")
        if vkey in visited:
            return
        visited.add(vkey)
        raw = _read_source_bytes(pkg_rel, project, {})
        if raw is None:
            return
        try:
            data = json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return
        if not isinstance(data, dict):
            return
        for key in _PKG_RUNNER_CONFIG_KEYS:
            if key in data and data[key] is not None:
                _scan_runner_config_obj(data[key], f"{pkg_rel}[{key}]", pkg_dir)

    def _analyze_js_runner(runner: str, args: list[str], cur_dir: tuple[str, ...], *, prefix: str = "") -> None:
        label = f"{prefix}{runner}"
        pkg_rel = "/".join((*cur_dir, "package.json")) if cur_dir else "package.json"
        if pkg_rel in files_set:
            protected.add(pkg_rel)
            _scan_pkg_runner_configs(pkg_rel, cur_dir)
        # Scan any existing default runner config files in cur_dir
        dir_pref = "/".join(cur_dir)
        pats = _JS_RUNNER_DEFAULT_CONFIG_PATTERNS.get(runner, ())
        if pats:
            for rel in sorted(files_set):
                parent_rel = "/".join(pathlib.PurePosixPath(rel).parts[:-1])
                if parent_rel != dir_pref:
                    continue
                bn = pathlib.PurePosixPath(rel).name
                if any(fnmatch.fnmatchcase(bn, p) for p in pats):
                    _scan_runner_config_file(rel)
        # Parse runner CLI args (--config, --require, --setupFiles*, positional files)
        ai = 0
        while ai < len(args):
            arg = args[ai]
            if arg in ("-r", "--require") and ai + 1 < len(args):
                req_tok = args[ai + 1]
                _fail(f"{label} uses --require")
                r_rel = _resolve_js_config_file(project, proj_res, files_set, req_tok, cur_dir)
                if r_rel is not None:
                    _add_unfixed(r_rel, "runner-require")
                ai += 2
                continue
            if arg.startswith("--require="):
                req_tok = arg.split("=", 1)[1]
                _fail(f"{label} uses --require")
                r_rel = _resolve_js_config_file(project, proj_res, files_set, req_tok, cur_dir)
                if r_rel is not None:
                    _add_unfixed(r_rel, "runner-require")
                ai += 1
                continue
            if arg in ("-r", "--require"):
                _fail(f"{label} uses --require")
                ai += 1
                continue
            cfg_tok: str | None = None
            if arg in ("--config", "-c") and ai + 1 < len(args):
                cfg_tok = args[ai + 1]
                ai += 2
            elif arg.startswith("--config="):
                cfg_tok = arg.split("=", 1)[1]
                ai += 1
            elif arg.startswith("-c="):
                cfg_tok = arg.split("=", 1)[1]
                ai += 1
            if cfg_tok is not None:
                if cfg_tok.lstrip().startswith("{"):
                    try:
                        inline_cfg = json.loads(cfg_tok)
                    except ValueError:
                        _fail(f"{label} --config JSON could not be parsed")
                    else:
                        _scan_runner_config_obj(inline_cfg, f"{label} --config", cur_dir)
                else:
                    c_rel = _resolve_js_config_file(project, proj_res, files_set, cfg_tok, cur_dir)
                    if c_rel is None:
                        _fail(f"{label} --config file not found in project: {cfg_tok}")
                    else:
                        _scan_runner_config_file(c_rel)
                continue
            if arg in ("--setupFiles", "--setupFilesAfterEnv", "--globalSetup", "--globalTeardown") and ai + 1 < len(args):
                _scan_config_string(args[ai + 1], f"{label} {arg}", cur_dir)
                ai += 2
                continue
            if arg.startswith(("--setupFiles=", "--setupFilesAfterEnv=", "--globalSetup=", "--globalTeardown=")):
                flag_k, _, flag_v = arg.partition("=")
                _scan_config_string(flag_v, f"{label} {flag_k}", cur_dir)
                ai += 1
                continue
            f_rel = _resolve_project_file(project, proj_res, files_set, arg, cur_dir)
            if f_rel is not None:
                protected.add(f_rel)
            ai += 1

    def _analyze_shell_file(rel: str, cur_dir: tuple[str, ...], depth: int) -> None:
        protected.add(rel)
        vkey = ("sh", rel, "/".join(cur_dir))
        if vkey in visited:
            return
        if depth > max_depth:
            _fail(f"recursion limit reached tracing {rel}")
            return
        visited.add(vkey)
        raw = _read_source_bytes(rel, project, {})
        if raw is None:
            _fail(f"could not read shell script: {rel}")
            return
        if b"\x00" in raw:
            _fail(f"binary shell script: {rel}")
            return
        text = raw.decode("utf-8", errors="replace")
        # Join backslash-continued lines
        raw_lines = text.splitlines()
        joined_lines: list[str] = []
        i = 0
        while i < len(raw_lines):
            ln = raw_lines[i]
            while ln.endswith("\\") and i + 1 < len(raw_lines):
                i += 1
                ln = ln[:-1] + raw_lines[i]
            joined_lines.append(ln)
            i += 1
        # Check the whole script for multi-line constructs like here-docs before line splitting
        _, whole_reasons, whole_exp = _tokenize_simple_shell(text)
        nonlocal uses_exp
        uses_exp = uses_exp or whole_exp
        if whole_reasons:
            for wr in whole_reasons:
                _fail(f"{rel}: {wr}")
            return
        script_dir = cur_dir
        for ln in joined_lines:
            stripped = ln.strip()
            if not stripped or stripped.startswith("#"):
                continue
            script_dir = _analyze_cmd_str(stripped, script_dir, depth + 1, in_script=rel)

    def _analyze_executable_file(rel: str, cur_dir: tuple[str, ...], depth: int) -> None:
        protected.add(rel)
        raw = _read_source_bytes(rel, project, {})
        if raw is None:
            _fail(f"could not read executable script: {rel}")
            return
        first_line = raw.splitlines()[0].decode("utf-8", errors="replace").strip() if raw else ""
        if first_line.startswith("#!"):
            shebang = first_line[2:].strip().split()
            interp = pathlib.PurePosixPath(shebang[0]).name if shebang else ""
            if interp == "env" and len(shebang) >= 2:
                interp = pathlib.PurePosixPath(shebang[1]).name
            if interp in ("sh", "bash", "dash"):
                _analyze_shell_file(rel, cur_dir, depth)
                return
            if _PY_TOOL_RE.match(interp):
                _analyze_py_file(rel, cur_dir)
                return
            if interp == "node":
                _analyze_js_file(rel)
                return
            _fail(f"executable script has unsupported shebang ({interp or 'empty'}): {rel}")
            return
        if rel.endswith((".sh", ".bash")):
            _analyze_shell_file(rel, cur_dir, depth)
        elif rel.endswith(".py"):
            _analyze_py_file(rel, cur_dir)
        elif rel.endswith(_JS_EXTS):
            _analyze_js_file(rel)
        else:
            _fail(f"executable file of untraceable type: {rel}")

    def _follow_npm_script(target_dir: tuple[str, ...], script_name: str, depth: int) -> None:
        pkg_rel = "/".join((*target_dir, "package.json")) if target_dir else "package.json"
        if pkg_rel not in files_set:
            _fail(f"package.json not found: {pkg_rel}")
            return
        protected.add(pkg_rel)
        _scan_pkg_runner_configs(pkg_rel, target_dir)
        vkey = ("npm", pkg_rel, script_name)
        if vkey in visited:
            return
        if depth > max_depth:
            _fail(f"recursion limit reached tracing {pkg_rel}:{script_name}")
            return
        visited.add(vkey)
        sc = _npm_script_at(project / pkg_rel, script_name)
        if sc is None:
            _fail(f"{pkg_rel} has no resolvable scripts.{script_name}")
            return
        pinned_named_scripts.setdefault(pkg_rel, {})[script_name] = sc
        if script_name == "test":
            pinned_scripts[pkg_rel] = sc
        # Follow pre<script> and post<script> lifecycle hooks if defined
        for hook in (f"pre{script_name}", f"post{script_name}"):
            hsc = _npm_script_at(project / pkg_rel, hook)
            if hsc is not None:
                pinned_named_scripts.setdefault(pkg_rel, {})[hook] = hsc
                _analyze_cmd_str(hsc, target_dir, depth + 1)
        _analyze_cmd_str(sc, target_dir, depth + 1)

    def _analyze_make(rest: list[str], cur_dir: tuple[str, ...], depth: int) -> None:
        target_dir = cur_dir
        explicit_mf: str | None = None
        req_targets: list[str] = []
        j = 0
        while j < len(rest):
            t = rest[j]
            if t in ("-C", "--directory") and j + 1 < len(rest):
                nd = _resolve_project_subdir(project, proj_res, rest[j + 1], target_dir)
                if nd is None:
                    _fail(f"make -C directory cannot be resolved inside project: {rest[j + 1]}")
                    return
                target_dir = nd
                j += 2
                continue
            if t.startswith("--directory="):
                nd = _resolve_project_subdir(project, proj_res, t.split("=", 1)[1], target_dir)
                if nd is None:
                    _fail(f"make --directory cannot be resolved inside project: {t}")
                    return
                target_dir = nd
                j += 1
                continue
            if t in ("-f", "--file", "--makefile") and j + 1 < len(rest):
                explicit_mf = rest[j + 1]
                j += 2
                continue
            if t.startswith(("--file=", "--makefile=")):
                explicit_mf = t.split("=", 1)[1]
                j += 1
                continue
            if t in ("-s", "--silent", "--quiet", "-i", "-k", "-B", "--no-print-directory", "-j") or re.match(r"^-j\d+$", t):
                j += 1
                continue
            if t.startswith("-"):
                _fail(f"unsupported make option: {t}")
                return
            if "=" in t:
                _fail(f"make variable override cannot be traced: {t}")
                return
            req_targets.append(t)
            j += 1

        mk_rel: str | None = None
        if explicit_mf is not None:
            mk_rel = _resolve_project_file(project, proj_res, files_set, explicit_mf, target_dir)
        else:
            for cand_name in ("GNUmakefile", "makefile", "Makefile"):
                cand = "/".join((*target_dir, cand_name)) if target_dir else cand_name
                if cand in files_set:
                    mk_rel = cand
                    break
        if mk_rel is None:
            _fail("Makefile not found in project")
            return
        protected.add(mk_rel)
        raw = _read_source_bytes(mk_rel, project, {})
        if raw is None:
            _fail(f"could not read Makefile: {mk_rel}")
            return
        targets_map, default_target, phony_targets, mk_reasons = _parse_makefile_targets(raw, mk_rel)
        for mr in mk_reasons:
            _fail(mr)
        if not req_targets:
            if default_target is None:
                _fail(f"no default target found in {mk_rel}")
                return
            req_targets = [default_target]

        def _follow_target(tname: str, d: int) -> None:
            vkey = ("make", mk_rel, tname)
            if vkey in visited:
                return
            if d > max_depth:
                _fail(f"recursion limit reached tracing make target {mk_rel}:{tname}")
                return
            visited.add(vkey)
            if tname not in targets_map:
                _fail(f"make target not found in {mk_rel}: {tname}")
                return
            if tname not in phony_targets:
                t_rel = _norm_posix_join(target_dir, tname)
                if t_rel is not None:
                    exists_in_proj = (
                        t_rel in files_set
                        or any(f.startswith(t_rel + "/") for f in files_set)
                        or os.path.lexists(project / t_rel)
                    )
                    if exists_in_proj:
                        _fail(f"make target '{tname}' is not .PHONY and a file named {tname} exists")
                        if t_rel in files_set:
                            _add_unfixed(t_rel, "make-target")
                    ignored_new_paths.add(t_rel)
                else:
                    _fail(f"make target '{tname}' is not .PHONY and cannot be resolved inside project")
            prereqs, recipes = targets_map[tname]
            for pr in prereqs:
                if pr in targets_map:
                    _follow_target(pr, d + 1)
                else:
                    _fail(f"make target {tname} has untraceable prerequisite: {pr}")
                    pr_rel = _resolve_project_file(project, proj_res, files_set, pr, target_dir)
                    if pr_rel is not None:
                        _add_unfixed(pr_rel, "make-prereq")
            for rec_line in recipes:
                cleaned = rec_line.lstrip("@-+ \t")
                if not cleaned:
                    continue
                if "$" in cleaned:
                    _fail(f"make recipe in {mk_rel}:{tname} uses variable/shell expansion")
                    continue
                _analyze_cmd_str(cleaned, target_dir, d + 1)

        for tn in req_targets:
            _follow_target(tn, depth + 1)

    def _analyze_simple_segment(tokens: list[str], cur_dir: tuple[str, ...], depth: int, *,
                                in_script: str | None = None) -> tuple[str, ...]:
        nonlocal runs_project_code
        if not tokens:
            return cur_dir
        if depth > max_depth:
            _fail("check command recursion limit exceeded")
            return cur_dir
        i = 0
        while i < len(tokens) and _is_env_assign(tokens[i]):
            k = tokens[i].split("=", 1)[0]
            if k in _UNSAFE_ENV_ASSIGN_KEYS:
                _fail(f"env assignment alters runtime resolution: {k}")
            i += 1
        if i >= len(tokens):
            _fail("shell variable assignment without known command")
            return cur_dir
        cmd_tok = tokens[i]
        rest = tokens[i + 1:]

        if cmd_tok in _SHELL_RESERVED_WORDS:
            _fail(f"shell control-flow construct: {cmd_tok}")
            return cur_dir

        # Trivial no-op/control builtins safe in scripts or commands
        if cmd_tok in ("true", "false"):
            return cur_dir
        if cmd_tok == "exit":
            if not rest or (len(rest) == 1 and rest[0].isdigit()):
                return cur_dir
            _fail(f"unsupported exit argument: {' '.join(rest)}")
            return cur_dir
        if cmd_tok == "set" and in_script is not None:
            ok_set = True
            j = 0
            while j < len(rest):
                t = rest[j]
                if t == "-o" and j + 1 < len(rest) and rest[j + 1] in ("pipefail", "errexit", "nounset", "noglob", "xtrace"):
                    j += 2
                    continue
                if t.startswith("-") and len(t) > 1 and all(c in "euxf" for c in t[1:]):
                    j += 1
                    continue
                ok_set = False
                break
            if ok_set:
                return cur_dir
            _fail(f"{in_script}: unsupported set command")
            return cur_dir

        if cmd_tok == "cd":
            if len(rest) == 1 and not rest[0].startswith("-"):
                nd = _resolve_project_subdir(project, proj_res, rest[0], cur_dir)
                if nd is not None:
                    return nd
            _fail(f"cd target cannot be resolved inside project: {' '.join(rest)}")
            return cur_dir

        # Anything past trivial shell builtins executes external/project code
        runs_project_code = True

        # Project-local executable (contains "/" and resolves inside project, or relative path)
        if "/" in cmd_tok:
            local_exec = _resolve_project_file(project, proj_res, files_set, cmd_tok, cur_dir)
            if local_exec is not None:
                _analyze_executable_file(local_exec, cur_dir, depth + 1)
                return cur_dir
            if not os.path.isabs(cmd_tok):
                _fail(f"project executable not found: {cmd_tok}")
                return cur_dir
            # Absolute path outside project (e.g. /usr/bin/python3, /path/to/.venv/bin/python)
            tool = pathlib.PurePosixPath(cmd_tok).name
        else:
            tool = cmd_tok

        # 1. npm
        if tool == "npm":
            target_dir = cur_dir
            j = 0
            while j < len(rest):
                t = rest[j]
                if t in ("--prefix", "-C") and j + 1 < len(rest):
                    nd = _resolve_project_subdir(project, proj_res, rest[j + 1], target_dir)
                    if nd is None:
                        _fail(f"npm --prefix directory not inside project: {rest[j + 1]}")
                        return cur_dir
                    target_dir = nd
                    j += 2
                    continue
                if t.startswith("--prefix="):
                    nd = _resolve_project_subdir(project, proj_res, t.split("=", 1)[1], target_dir)
                    if nd is None:
                        _fail(f"npm --prefix directory not inside project: {t}")
                        return cur_dir
                    target_dir = nd
                    j += 1
                    continue
                if t in ("-s", "--silent", "--no-audit", "--no-fund") or t.startswith("--loglevel="):
                    j += 1
                    continue
                if t.startswith("-"):
                    _fail(f"unsupported npm flag: {t}")
                    return cur_dir
                break
            if j >= len(rest):
                _fail("npm missing subcommand")
                return cur_dir
            sub = rest[j]
            if sub in ("test", "t"):
                _follow_npm_script(target_dir, "test", depth + 1)
                return cur_dir
            if sub in ("run", "run-script") and j + 1 < len(rest):
                _follow_npm_script(target_dir, rest[j + 1], depth + 1)
                return cur_dir
            _fail(f"unsupported npm subcommand: {sub}")
            return cur_dir

        # 2. yarn / pnpm
        if tool in ("yarn", "pnpm"):
            target_dir = cur_dir
            j = 0
            while j < len(rest):
                t = rest[j]
                if t in ("--cwd", "--dir", "-C") and j + 1 < len(rest):
                    nd = _resolve_project_subdir(project, proj_res, rest[j + 1], target_dir)
                    if nd is None:
                        _fail(f"{tool} directory option not inside project: {rest[j + 1]}")
                        return cur_dir
                    target_dir = nd
                    j += 2
                    continue
                if t in ("-s", "--silent"):
                    j += 1
                    continue
                if t.startswith("-"):
                    _fail(f"unsupported {tool} flag: {t}")
                    return cur_dir
                break
            if j >= len(rest):
                _fail(f"{tool} missing subcommand")
                return cur_dir
            sub = rest[j]
            if sub == "test":
                _follow_npm_script(target_dir, "test", depth + 1)
                return cur_dir
            if sub == "run" and j + 1 < len(rest):
                _follow_npm_script(target_dir, rest[j + 1], depth + 1)
                return cur_dir
            _fail(f"unsupported {tool} subcommand: {sub}")
            return cur_dir

        # 3. npx jest|vitest|mocha|ava
        if tool == "npx":
            j = 0
            while j < len(rest) and rest[j] in ("--no-install", "-y", "--yes", "-q", "--quiet"):
                j += 1
            if j >= len(rest):
                _fail("npx missing command")
                return cur_dir
            runner = rest[j]
            if runner in _KNOWN_JS_RUNNERS:
                _analyze_js_runner(runner, rest[j + 1:], cur_dir, prefix="npx ")
                return cur_dir
            _fail(f"npx runs unknown command: {runner}")
            return cur_dir

        # 4. Known direct test runners: pytest, jest, vitest, mocha, ava, cargo test, go test
        if tool == "pytest":
            nonlocal uses_python
            uses_python = True
            py_sys_path_dirs.add("/".join(cur_dir))
            pytest_bin = cmd_tok if os.path.isabs(cmd_tok) else shutil.which(cmd_tok)
            if pytest_bin:
                try:
                    with open(pytest_bin, "rb") as _pf:
                        _she = _pf.readline(256).decode("utf-8", errors="replace").strip()
                    if _she.startswith("#!"):
                        _sh_parts = _she[2:].strip().split()
                        if _sh_parts:
                            _pi = _sh_parts[1] if (pathlib.PurePosixPath(_sh_parts[0]).name == "env" and len(_sh_parts) >= 2) else _sh_parts[0]
                            _note_py_interp(_pi)
                except OSError:
                    pass
            j = 0
            while j < len(rest):
                arg = rest[j]
                if arg == "-p" and j + 1 < len(rest):
                    pmod = rest[j + 1]
                    if not pmod.startswith("no:") and (pmod.replace(".", "/") + ".py") in files_set:
                        _fail(f"pytest loads local plugin: {pmod}")
                        _add_unfixed(pmod.replace(".", "/") + ".py", "runner-plugin")
                        return cur_dir
                    j += 2
                    continue
                f_rel = _resolve_project_file(project, proj_res, files_set, arg, cur_dir)
                if f_rel is not None:
                    protected.add(f_rel)
                    if f_rel.endswith(".py"):
                        _note_py_file_dir(f_rel)
                j += 1
            return cur_dir

        if tool in _KNOWN_JS_RUNNERS:
            _analyze_js_runner(tool, rest, cur_dir)
            return cur_dir

        if tool == "cargo":
            if rest and rest[0] == "test":
                ct = "/".join((*cur_dir, "Cargo.toml")) if cur_dir else "Cargo.toml"
                if ct in files_set:
                    protected.add(ct)
                return cur_dir
            _fail(f"unsupported cargo subcommand: {rest[0] if rest else '(none)'}")
            return cur_dir

        if tool == "go":
            if rest and rest[0] == "test":
                gm = "/".join((*cur_dir, "go.mod")) if cur_dir else "go.mod"
                if gm in files_set:
                    protected.add(gm)
                return cur_dir
            _fail(f"unsupported go subcommand: {rest[0] if rest else '(none)'}")
            return cur_dir

        # 5. python / python3
        if _PY_TOOL_RE.match(tool):
            _note_py_interp(cmd_tok)
            py_sys_path_dirs.add("/".join(cur_dir))
            j = 0
            while j < len(rest):
                t = rest[j]
                if t in ("-B", "-E", "-I", "-O", "-OO", "-S", "-s", "-u", "-v", "-q", "-P", "-bb", "-b", "-d", "-x"):
                    j += 1
                    continue
                if t in ("-W", "-X") and j + 1 < len(rest):
                    j += 2
                    continue
                if (t.startswith("-W") or t.startswith("-X")) and len(t) > 2:
                    j += 1
                    continue
                break
            if j >= len(rest):
                _fail("python invoked without script or module")
                return cur_dir
            mode_tok = rest[j]
            if mode_tok == "-m" and j + 1 < len(rest):
                mod_name = rest[j + 1]
                mod_args = rest[j + 2:]
                if mod_name == "pytest":
                    k_idx = 0
                    while k_idx < len(mod_args):
                        ma = mod_args[k_idx]
                        if ma == "-p" and k_idx + 1 < len(mod_args):
                            pmod = mod_args[k_idx + 1]
                            if not pmod.startswith("no:") and (pmod.replace(".", "/") + ".py") in files_set:
                                _fail(f"pytest loads local plugin: {pmod}")
                                _add_unfixed(pmod.replace(".", "/") + ".py", "runner-plugin")
                                return cur_dir
                            k_idx += 2
                            continue
                        if not ma.startswith("-"):
                            f_rel = _resolve_project_file(project, proj_res, files_set, ma, cur_dir)
                            if f_rel is not None:
                                protected.add(f_rel)
                        k_idx += 1
                    return cur_dir
                if mod_name == "unittest" or mod_name.startswith("unittest."):
                    # Strip leading unittest flags before checking for `discover`
                    u_idx = 0
                    u_bool_long = frozenset({"--verbose", "--quiet", "--failfast", "--catch", "--buffer", "--locals"})
                    while u_idx < len(mod_args):
                        tok = mod_args[u_idx]
                        if tok in ("-k",) and u_idx + 1 < len(mod_args):
                            u_idx += 2
                            continue
                        if tok.startswith("-k") and len(tok) > 2:
                            u_idx += 1
                            continue
                        if tok in u_bool_long or (tok.startswith("-") and not tok.startswith("--") and len(tok) > 1 and all(c in "vqfcb" for c in tok[1:])):
                            u_idx += 1
                            continue
                        break
                    rem = mod_args[u_idx:]
                    if not rem or rem[0] == "discover":
                        d_args = rem[1:] if (rem and rem[0] == "discover") else []
                        start_tok = "."
                        pat_tok = "test*.py"
                        top_tok: str | None = None
                        pos_args: list[str] = []
                        di = 0
                        while di < len(d_args):
                            dt = d_args[di]
                            if dt in ("-s", "--start-directory") and di + 1 < len(d_args):
                                start_tok = d_args[di + 1]
                                di += 2
                                continue
                            if dt.startswith("--start-directory="):
                                start_tok = dt.split("=", 1)[1]
                                di += 1
                                continue
                            if dt.startswith("-s") and len(dt) > 2:
                                start_tok = dt[2:]
                                di += 1
                                continue
                            if dt in ("-p", "--pattern") and di + 1 < len(d_args):
                                pat_tok = d_args[di + 1]
                                di += 2
                                continue
                            if dt.startswith("--pattern="):
                                pat_tok = dt.split("=", 1)[1]
                                di += 1
                                continue
                            if dt.startswith("-p") and len(dt) > 2:
                                pat_tok = dt[2:]
                                di += 1
                                continue
                            if dt in ("-t", "--top-level-directory") and di + 1 < len(d_args):
                                top_tok = d_args[di + 1]
                                di += 2
                                continue
                            if dt.startswith("--top-level-directory="):
                                top_tok = dt.split("=", 1)[1]
                                di += 1
                                continue
                            if dt.startswith("-t") and len(dt) > 2:
                                top_tok = dt[2:]
                                di += 1
                                continue
                            if dt == "-k" and di + 1 < len(d_args):
                                di += 2
                                continue
                            if dt.startswith("-k") and len(dt) > 2:
                                di += 1
                                continue
                            if dt in u_bool_long or (dt.startswith("-") and not dt.startswith("--") and len(dt) > 1 and all(c in "vqfcb" for c in dt[1:])):
                                di += 1
                                continue
                            if dt.startswith("-"):
                                _fail(f"unsupported unittest discover option: {dt}")
                                return cur_dir
                            pos_args.append(dt)
                            di += 1
                        if len(pos_args) >= 1:
                            start_tok = pos_args[0]
                        if len(pos_args) >= 2:
                            pat_tok = pos_args[1]
                        if len(pos_args) >= 3:
                            top_tok = pos_args[2]
                        if len(pos_args) > 3:
                            _fail("unsupported extra unittest discover arguments")
                            return cur_dir
                        sd = _resolve_project_subdir(project, proj_res, start_tok, cur_dir)
                        if sd is None:
                            _fail(f"unittest discover start directory not inside project: {start_tok}")
                            return cur_dir
                        if top_tok is not None:
                            td = _resolve_project_subdir(project, proj_res, top_tok, cur_dir)
                            if td is None:
                                _fail(f"unittest discover top-level directory not inside project: {top_tok}")
                                return cur_dir
                            py_sys_path_dirs.add("/".join(td))
                        start_pref = "/".join(sd)
                        py_sys_path_dirs.add(start_pref)
                        unittest_start_dirs.add(start_pref)
                        for rel in files_set:
                            if start_pref == "" or rel.startswith(start_pref + "/"):
                                bn = pathlib.PurePosixPath(rel).name
                                if fnmatch.fnmatchcase(bn, pat_tok):
                                    protected.add(rel)
                        ignored_new_globs.append((start_pref, pat_tok))
                        return cur_dir
                    # Explicit unittest target(s): files or dotted module/class/method specs
                    for ma in rem:
                        if ma.startswith("-"):
                            continue
                        f_rel = _resolve_project_file(project, proj_res, files_set, ma, cur_dir)
                        if f_rel is not None:
                            protected.add(f_rel)
                            continue
                        parts_m = [p for p in ma.split(".") if p]
                        found_m = False
                        for end_i in range(len(parts_m), 0, -1):
                            sub_m = "/".join(parts_m[:end_i])
                            f_mod = _resolve_project_file(project, proj_res, files_set, sub_m + ".py", cur_dir)
                            if f_mod is not None:
                                protected.add(f_mod)
                                found_m = True
                                break
                        if not found_m:
                            _fail(f"unittest target cannot be resolved in project: {ma}")
                    return cur_dir
                # Look up MOD.py / MOD/__main__.py in project
                mod_parts = [p for p in mod_name.split(".") if p]
                mod_sub = "/".join(mod_parts)
                found_files: list[str] = []
                search_bases: list[tuple[str, ...]] = [cur_dir]
                if () not in search_bases:
                    search_bases.append(())
                if ("src",) not in search_bases:
                    search_bases.append(("src",))
                for base_p in search_bases:
                    pref = "/".join(base_p)
                    cand_py = f"{pref}/{mod_sub}.py" if pref else f"{mod_sub}.py"
                    cand_main = f"{pref}/{mod_sub}/__main__.py" if pref else f"{mod_sub}/__main__.py"
                    cand_init = f"{pref}/{mod_sub}/__init__.py" if pref else f"{mod_sub}/__init__.py"
                    if cand_py in files_set:
                        found_files.append(cand_py)
                        break
                    if cand_main in files_set:
                        found_files.append(cand_main)
                        if cand_init in files_set:
                            found_files.append(cand_init)
                        break
                if found_files:
                    for fp in found_files:
                        _analyze_py_file(fp, cur_dir)
                    return cur_dir
                _fail(f"python -m module cannot be resolved in project: {mod_name}")
                return cur_dir
            if mode_tok == "-c" and j + 1 < len(rest):
                code_str = rest[j + 1]
                py_reasons, extra_prot, py_unfixed = _py_analyze_code_ast(
                    code_str.encode("utf-8", "replace"), "<python -c>", files_set,
                    inline=True, project=project, proj_res=proj_res, cur_dir=cur_dir,
                )
                protected.update(extra_prot)
                for u_rel, u_rs in py_unfixed.items():
                    for ur in u_rs:
                        _add_unfixed(u_rel, ur)
                for r in py_reasons:
                    _fail(r)
                return cur_dir
            if mode_tok.startswith("-"):
                _fail(f"unsupported python option: {mode_tok}")
                return cur_dir
            f_rel = _resolve_project_file(project, proj_res, files_set, mode_tok, cur_dir)
            if f_rel is None:
                _fail(f"python script not found in project: {mode_tok}")
                return cur_dir
            _analyze_py_file(f_rel, cur_dir)
            return cur_dir

        # 6. node
        if tool == "node":
            j = 0
            while j < len(rest):
                t = rest[j]
                if t in ("-e", "--eval", "-p", "--print"):
                    _fail(f"node inline code ({t}) cannot be resolved")
                    return cur_dir
                if t in ("-r", "--require", "--import", "--loader"):
                    _fail(f"node preload option ({t}) cannot be resolved")
                    return cur_dir
                if t in ("--no-warnings", "--enable-source-maps", "--experimental-vm-modules"):
                    j += 1
                    continue
                if t.startswith("-"):
                    _fail(f"unsupported node option: {t}")
                    return cur_dir
                break
            if j >= len(rest):
                _fail("node invoked without script file")
                return cur_dir
            f_rel = _resolve_project_file(project, proj_res, files_set, rest[j], cur_dir)
            if f_rel is None:
                _fail(f"node script not found in project: {rest[j]}")
                return cur_dir
            _analyze_js_file(f_rel)
            return cur_dir

        # 7. bash / sh / dash FILE
        if tool in ("bash", "sh", "dash"):
            j = 0
            while j < len(rest):
                t = rest[j]
                if t.startswith("-") and not t.startswith("--") and len(t) > 1 and all(c in "eux" for c in t[1:]):
                    j += 1
                    continue
                break
            if j >= len(rest):
                _fail(f"{tool} invoked without script file")
                return cur_dir
            if rest[j].startswith("-"):
                _fail(f"unsupported {tool} option: {rest[j]}")
                return cur_dir
            f_rel = _resolve_project_file(project, proj_res, files_set, rest[j], cur_dir)
            if f_rel is None:
                _fail(f"shell script not found in project: {rest[j]}")
                return cur_dir
            _analyze_shell_file(f_rel, cur_dir, depth + 1)
            return cur_dir

        # 8. make / gmake
        if tool in ("make", "gmake"):
            _analyze_make(rest, cur_dir, depth + 1)
            return cur_dir

        # Everything else -> untraced; record any existing project file args as unfixed deps
        _fail(f"unknown command: {tool}")
        dep_why = "script-source" if tool in ("source", ".") else "script-ref"
        for tok in rest:
            f_rel = _resolve_project_file(project, proj_res, files_set, tok, cur_dir)
            if f_rel is not None:
                _add_unfixed(f_rel, dep_why)
        return cur_dir

    def _analyze_cmd_str(cmd_str: str, cur_dir: tuple[str, ...], depth: int, *,
                         in_script: str | None = None) -> tuple[str, ...]:
        nonlocal uses_exp
        segs, tok_reasons, exp = _tokenize_simple_shell(cmd_str)
        uses_exp = uses_exp or exp
        for tr in tok_reasons:
            _fail(f"{in_script}: {tr}" if in_script else tr)
        if not segs and not tok_reasons:
            _fail("empty acceptance command")
            return cur_dir
        d = cur_dir
        for seg in segs:
            d = _analyze_simple_segment(seg, d, depth, in_script=in_script)
        return d

    _analyze_cmd_str(cmd, (), 0)
    integrity = "traced" if not reasons else "untraced"
    return _AcceptanceAnalysis(
        integrity=integrity,
        reasons=reasons,
        protected=protected,
        pinned_scripts=pinned_scripts,
        pinned_named_scripts=pinned_named_scripts,
        shell_expansion=uses_exp,
        ignored_new_paths=ignored_new_paths,
        ignored_new_globs=ignored_new_globs,
        unfixed_deps=unfixed_deps,
        runs_project_code=runs_project_code,
        py_sys_path_dirs=py_sys_path_dirs,
        py_interpreters=py_interpreters,
        uses_python=uses_python,
        unittest_start_dirs=unittest_start_dirs,
    )


def _check_command_protections(project: pathlib.Path, cmd: str,
                               files_set: set[str]) -> tuple[set[str], str | None, dict[str, str], bool]:
    """解析 `--check "<cmd>"` 自動應受保護的專案檔案、鎖定的 scripts.test 與是否含 shell 展開：
    1. 拆開 `;`/`&&`/`||`/`|` 並遞迴展開 `sh -c`/`bash -c`/`env`/`timeout`/`nice`/`cd`，收集所有指令詞。
    2. 若含 npm/npx/yarn/pnpm ⇒ 保護專案內所有 `package.json`（不含 node_modules）並鎖定各自的 `scripts.test`；
       make/gmake ⇒ 所有 Makefile/makefile/GNUmakefile 與 `*.mk`；
       cargo ⇒ 所有 `Cargo.toml`；go ⇒ 所有 `go.mod`。
    3. 任一深度的 token 若對應專案內既有一般檔案（相對、`./x` 或專案內絕對路徑），納入保護。"""
    cmd_words, all_tokens, uses_expansion = _parse_check_shell_cmd(cmd)
    out: set[str] = set()
    pinned_scripts: dict[str, str] = {}

    if cmd_words & _NPM_LIKE_CMDS:
        for rel in sorted(files_set):
            if pathlib.PurePosixPath(rel).name == "package.json":
                out.add(rel)
                sc = _npm_test_script_at(project / rel)
                if sc is not None:
                    pinned_scripts[rel] = sc
    if cmd_words & {"make", "gmake"}:
        for rel in files_set:
            bn = pathlib.PurePosixPath(rel).name
            if bn in ("Makefile", "makefile", "GNUmakefile") or bn.endswith(".mk"):
                out.add(rel)
    if "cargo" in cmd_words:
        for rel in files_set:
            if pathlib.PurePosixPath(rel).name == "Cargo.toml":
                out.add(rel)
    if "go" in cmd_words:
        for rel in files_set:
            if pathlib.PurePosixPath(rel).name == "go.mod":
                out.add(rel)

    pinned_script = pinned_scripts.get("package.json")
    proj_res = project.resolve()
    for tok, tok_dir in all_tokens:
        candidates = [tok]
        if "=" in tok and not tok.startswith("="):
            candidates.append(tok.split("=", 1)[1])
        for cand in candidates:
            raw = cand.strip().replace("\\", "/")
            if not raw or raw in (".", ".."):
                continue
            while raw.startswith("./"):
                raw = raw[2:]
            if not raw:
                continue
            p = pathlib.Path(raw)
            if p.is_absolute():
                try:
                    rel = p.resolve().relative_to(proj_res).as_posix()
                except (ValueError, OSError):
                    continue
                if rel in files_set:
                    out.add(rel)
            else:
                parts = pathlib.PurePosixPath(raw).parts
                if ".." not in parts:
                    rel = "/".join(parts)
                    if rel in files_set:
                        out.add(rel)
                if tok_dir:
                    joined = _norm_posix_join(tok_dir, raw)
                    if joined and joined in files_set:
                        out.add(joined)
    return out, pinned_script, pinned_scripts, uses_expansion


def find_protected(root: pathlib.Path, *, kind: str = "none",
                   protect: Sequence[str] | None = None,
                   check: str | None = None,
                   _all_files: list[str] | None = None) -> list[str]:
    """列出開始時應受保護（驗收前還原原位元組、不寫回 agent 改動）的相對路徑。"""
    root = root.resolve()
    files = _all_files if _all_files is not None else _files(root)
    files_set = set(files)
    out: set[str] = {r for r in files if _is_protected_by_default(r)}
    for mf in _MANIFEST_BY_KIND.get(kind, ()):
        if mf in files_set:
            out.add(mf)
    if check:
        extra_check, _, _, _ = _check_command_protections(root, check, files_set)
        out |= extra_check
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
               work_root: pathlib.Path | None = None,
               run_id: str | None = None) -> dict[str, str]:
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
    if run_id:
        env[_DETACHED_MARKER_ENV] = run_id
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
    copy_skip_created: list[dict[str, str]] = dataclasses.field(default_factory=list)


_COPY_SKIP_RECORD_LIMIT = 500


def _collect_copy_skip_files(cur_dir: pathlib.Path, rel_prefix: str, skip_name: str,
                             out: list[dict[str, str]]) -> None:
    """收集 agent 在 COPY_SKIP 同名目錄下建立的檔案，供 not_delivered 回報（不跟隨 symlink，設上限）。"""
    stack = [(cur_dir, rel_prefix)]
    reason = f"under skipped directory ({skip_name})"
    while stack and len(out) < _COPY_SKIP_RECORD_LIMIT:
        d, pref = stack.pop()
        try:
            entries = sorted(os.scandir(d), key=lambda e: e.name)
        except OSError:
            continue
        for e in entries:
            if len(out) >= _COPY_SKIP_RECORD_LIMIT:
                break
            rel = f"{pref}/{e.name}" if pref else e.name
            try:
                st = e.stat(follow_symlinks=False)
            except OSError:
                continue
            if stat.S_ISDIR(st.st_mode) and not stat.S_ISLNK(st.st_mode):
                stack.append((pathlib.Path(e.path), rel))
            else:
                out.append({"path": rel, "reason": reason})


def _snapshot_workspace(ws: pathlib.Path, dest: pathlib.Path, *,
                        skip_abs: set[pathlib.Path] | None = None,
                        record_copy_skip: bool = False,
                        had_root_nm: bool = False) -> _Snapshot:
    """將工作區拍成只含一般檔案的私密快照（不跟隨 symlink、跳過特殊檔、Vacant 狀態/工作區根與 COPY_SKIP）。"""
    dest.mkdir(parents=True, exist_ok=True)
    os.chmod(dest, 0o700)
    files: dict[str, str] = {}
    modes: dict[str, int] = {}
    symlinks: set[str] = set()
    unreadable_dirs: set[str] = set()
    unreadable_files: set[str] = set()
    special_files: set[str] = set()
    copy_skip_created: list[dict[str, str]] = []
    skip_rels = _skip_rels_for(ws, skip_abs)

    def _walk(cur: pathlib.Path, rel_prefix: str) -> None:
        try:
            entries = sorted(os.scandir(cur), key=lambda e: e.name)
        except OSError:
            unreadable_dirs.add(rel_prefix or ".")
            return
        for entry in entries:
            name = entry.name
            rel = f"{rel_prefix}/{name}" if rel_prefix else name
            if name in COPY_SKIP:
                if record_copy_skip and not (rel_prefix == "" and name == "node_modules" and had_root_nm):
                    try:
                        st_cs = entry.stat(follow_symlinks=False)
                    except OSError:
                        st_cs = None
                    if st_cs is not None and stat.S_ISDIR(st_cs.st_mode) and not stat.S_ISLNK(st_cs.st_mode):
                        _collect_copy_skip_files(cur / name, rel, name, copy_skip_created)
                    elif st_cs is not None:
                        copy_skip_created.append({"path": rel, "reason": f"skipped name ({name})"})
                continue
            if rel in skip_rels:
                continue
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
    copy_skip_created.sort(key=lambda d: d["path"])
    return _Snapshot(
        root=dest,
        files=files,
        modes=modes,
        symlinks=symlinks,
        unreadable_dirs=unreadable_dirs,
        unreadable_files=unreadable_files,
        special_files=special_files,
        copy_skip_created=copy_skip_created,
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
    config_ignored: list[str] = dataclasses.field(default_factory=list)  # agent 新增的測試設定檔：不驗、不寫回
    config_ignored_reasons: dict[str, str] = dataclasses.field(default_factory=dict)  # rel -> reason (e.g. shadows module)
    appeared: list[str] = dataclasses.field(default_factory=list)        # 執行期間出現在原專案的檔案：絕不刪除
    conflicts: list[str] = dataclasses.field(default_factory=list)       # 開始後原專案與交件嘗試皆改動：保留原專案版本


def _scan_file_hashes(root: pathlib.Path) -> dict[str, str | None]:
    """掃描 root 下所有一般檔案並計算 SHA-256（供 D3 寫回比對開始狀態）。"""
    files, _ = _scan_files(root)
    return {rel: _sha256_file(root / rel) for rel in files}


def _project_lstat_listing(project: pathlib.Path, *,
                           skip_abs: set[pathlib.Path] | None = None,
                           skip_root_nm: bool = False) -> dict[str, tuple]:
    """對原專案做純 lstat 清單（不讀檔內容、不跟隨 symlink）：
    涵蓋整棵 `.git`（含 `.git/objects/info/**` 與 `.git/objects/pack/**` 的完整 lstat，以及
    `.git/objects/??/` 下鬆散物件的純檔名集合 scandir 不做每檔 lstat、不讀內容）、以及任意深度的
    `node_modules`、`.venv`、`__pycache__`、`.pytest_cache` 與任意處的 symlink。
    若根目錄 `node_modules` 已由 B3 清單追蹤（`skip_root_nm=True`），則僅跳過根層 `node_modules` 避免重複走訪。
    永遠排除 Vacant 狀態與工作區根目錄。"""
    out: dict[str, tuple] = {}
    skip_rels = _skip_rels_for(project, skip_abs)

    def _walk_git_full(cur: pathlib.Path, rel_prefix: str) -> None:
        try:
            entries = sorted(os.scandir(cur), key=lambda e: e.name)
        except OSError:
            out[rel_prefix + "/"] = ("unreadable",)
            return
        for entry in entries:
            name = entry.name
            rel = f"{rel_prefix}/{name}"
            if rel in skip_rels:
                continue
            full = cur / name
            try:
                st = entry.stat(follow_symlinks=False)
            except OSError:
                continue
            if stat.S_ISDIR(st.st_mode) and not stat.S_ISLNK(st.st_mode):
                _walk_git_full(full, rel)
            else:
                out[rel] = _lstat_tuple(full, st)

    def _walk_git_objects(cur: pathlib.Path, rel_prefix: str) -> None:
        try:
            entries = sorted(os.scandir(cur), key=lambda e: e.name)
        except OSError:
            out[rel_prefix + "/"] = ("unreadable",)
            return
        for entry in entries:
            name = entry.name
            rel = f"{rel_prefix}/{name}"
            if rel in skip_rels:
                continue
            full = cur / name
            # Fanout loose-object dirs (.git/objects/??/): scandir names only, no per-file lstat, no content reads
            if len(name) == 2 and all(c in "0123456789abcdefABCDEF" for c in name):
                try:
                    if entry.is_dir(follow_symlinks=False):
                        try:
                            for sub in os.scandir(full):
                                sub_rel = f"{rel}/{sub.name}"
                                if sub_rel not in skip_rels:
                                    out[sub_rel] = ("git_loose",)
                        except OSError:
                            out[rel + "/"] = ("unreadable",)
                        continue
                except OSError:
                    continue
            try:
                st = entry.stat(follow_symlinks=False)
            except OSError:
                continue
            if stat.S_ISDIR(st.st_mode) and not stat.S_ISLNK(st.st_mode):
                # info/**, pack/**, or any unexpected subdir under .git/objects/ -> full lstat
                _walk_git_full(full, rel)
            else:
                out[rel] = _lstat_tuple(full, st)

    def _walk_git(cur: pathlib.Path, rel_prefix: str) -> None:
        try:
            entries = sorted(os.scandir(cur), key=lambda e: e.name)
        except OSError:
            out[rel_prefix + "/"] = ("unreadable",)
            return
        for entry in entries:
            name = entry.name
            rel = f"{rel_prefix}/{name}"
            if rel in skip_rels:
                continue
            full = cur / name
            try:
                st = entry.stat(follow_symlinks=False)
            except OSError:
                continue
            if name == "objects" and stat.S_ISDIR(st.st_mode) and not stat.S_ISLNK(st.st_mode):
                _walk_git_objects(full, rel)
                continue
            if stat.S_ISDIR(st.st_mode) and not stat.S_ISLNK(st.st_mode):
                _walk_git(full, rel)
            else:
                out[rel] = _lstat_tuple(full, st)

    def _walk(cur: pathlib.Path, rel_prefix: str) -> None:
        try:
            entries = sorted(os.scandir(cur), key=lambda e: e.name)
        except OSError:
            out[(rel_prefix or ".") + "/"] = ("unreadable",)
            return
        for entry in entries:
            name = entry.name
            rel = f"{rel_prefix}/{name}" if rel_prefix else name
            if rel in skip_rels:
                continue
            full = cur / name
            try:
                st = entry.stat(follow_symlinks=False)
            except OSError:
                continue
            is_real_dir = stat.S_ISDIR(st.st_mode) and not stat.S_ISLNK(st.st_mode)
            if skip_root_nm and rel == "node_modules" and is_real_dir:
                continue
            if name == ".git" and is_real_dir:
                _walk_git(full, rel)
                continue
            if is_real_dir:
                _walk(full, rel)
            else:
                out[rel] = _lstat_tuple(full, st)

    _walk(project, "")
    return out


def _can_remove_dir(project: pathlib.Path, rel: str, deletes: set[str], *,
                    skip_rels: set[str] | None = None) -> list[str] | None:
    """檢查 project/rel 目錄底下是否只包含即將刪除的一般檔案（無 symlink、COPY_SKIP、Vacant 狀態根、保護檔、特殊檔或不可讀目錄）。
    安全時回傳由深到淺的相對目錄清單（含 rel 本身），否則回傳 None。"""
    dirs_out: list[str] = []
    srels = _skip_rels_for(project) if skip_rels is None else skip_rels

    def _check(cur: pathlib.Path, cur_rel: str) -> bool:
        if cur_rel in srels:
            return False
        try:
            entries = sorted(os.scandir(cur), key=lambda e: e.name)
        except OSError:
            return False
        for entry in entries:
            name = entry.name
            if name in COPY_SKIP:
                return False
            child_rel = f"{cur_rel}/{name}"
            if child_rel in srels:
                return False
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


def _plan_write_back(project: pathlib.Path, snap: _Snapshot, protected: set[str], *,
                     start_hashes: dict[str, str | None] | None = None,
                     ignore_new: Callable[[str], bool] | None = None,
                     ignore_new_reason: Callable[[str, set[str] | None, set[str] | frozenset[str] | None], str | None] | None = None) -> _WritePlan:
    """規劃寫回專案的所有操作（唯讀掃描 project，不做任何變更）。
    當提供 `start_hashes`（任務開始時的原專案快照）時：
    - 僅刪除「開始時存在且交件嘗試刪掉」的檔案；執行期間新出現在原專案的檔案絕不刪除，改記 `appeared`。
    - 交件嘗試欲修改或刪除的路徑若在開始後已被原專案改動（雜湊異於開始時或已刪），保留原專案版本並記 `conflicts`。"""
    before_list, proj_unreadable = _scan_files(project)
    before = set(before_list)
    after = set(snap.files)
    ws_unsafe = snap.symlinks | snap.unreadable_dirs | snap.unreadable_files | snap.special_files
    proj_skip_rels = _skip_rels_for(project)

    start_set = set(start_hashes) if start_hashes is not None else before
    appeared = (
        sorted(
            rel for rel in (before - start_set - protected)
            if not _has_copy_skip(rel) and not _matches_prefix(rel, proj_skip_rels)
        )
        if start_hashes is not None
        else []
    )
    conflicts: set[str] = set()

    deletes: list[str] = []
    delete_skips: set[str] = set()
    for rel in sorted(start_set - after - protected):
        if _has_copy_skip(rel) or _matches_prefix(rel, proj_skip_rels):
            continue
        if start_hashes is not None and rel not in before:
            continue  # 原專案自己已經刪掉，不需再刪
        if (_matches_prefix(rel, ws_unsafe)
                or _matches_prefix(rel, proj_unreadable)
                or _through_symlink(project, rel)):
            delete_skips.add(rel)
            continue
        if start_hashes is not None:
            live_sha = _sha256_file(project / rel)
            if live_sha is None:
                delete_skips.add(rel)
                continue
            start_sha = start_hashes.get(rel)
            if start_sha is not None and live_sha != start_sha:
                conflicts.add(rel)
                continue
        deletes.append(rel)
    delete_set = set(deletes)

    added: list[str] = []
    modified: list[str] = []
    write_skips: set[str] = set()
    dirs_to_remove: list[str] = []
    dirs_seen: set[str] = set()

    config_ignored: list[str] = []
    config_ignored_reasons: dict[str, str] = {}
    for rel in sorted(after - protected):
        if _has_copy_skip(rel) or _matches_prefix(rel, proj_skip_rels):
            continue
        if rel not in start_set:
            if _is_test_config(rel):
                config_ignored.append(rel)
                continue
            if ignore_new_reason is not None:
                ig_why = ignore_new_reason(rel, after, start_set)
                if ig_why is not None:
                    config_ignored.append(rel)
                    if ig_why:
                        config_ignored_reasons[rel] = ig_why
                    continue
            elif ignore_new is not None and ignore_new(rel):
                config_ignored.append(rel)
                continue
        # 交件嘗試相對於開始時並未改動此檔 ⇒ 絕不覆寫原專案（即使原專案有並發編輯）
        if start_hashes is not None and rel in start_set:
            start_sha = start_hashes.get(rel)
            if start_sha is not None and snap.files[rel] == start_sha:
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
            if start_hashes is not None:
                if rel not in start_set:
                    if dst_sha == snap.files[rel]:
                        continue
                    conflicts.add(rel)
                    continue
                start_sha = start_hashes.get(rel)
                if start_sha is not None and dst_sha != start_sha:
                    conflicts.add(rel)
                    continue
            if dst_sha == snap.files[rel]:
                continue
            modified.append(rel)
        else:
            if start_hashes is not None and rel in start_set:
                # 開始時存在、執行期間被使用者刪掉、而 agent 改動過 ⇒ conflict，保留使用者版本
                conflicts.add(rel)
                continue
            added.append(rel)

    dirs_to_remove.sort(key=lambda r: (-len(pathlib.PurePosixPath(r).parts), r))
    return _WritePlan(
        added=added,
        modified=modified,
        deleted=deletes,
        skipped=sorted(delete_skips | write_skips),
        dirs_to_remove=dirs_to_remove,
        before_files=before,
        config_ignored=config_ignored,
        config_ignored_reasons=config_ignored_reasons,
        appeared=appeared,
        conflicts=sorted(conflicts),
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
                      backup_dir: pathlib.Path, *,
                      start_hashes: dict[str, str | None] | None = None) -> dict[str, list[str]]:
    """套用已驗證的寫回計畫；任何非預期錯誤都會回滾，維持專案不變。
    若提供 `start_hashes`，在每個 unlink／os.replace 之前再次確認原專案檔案仍符合開始快照，
    不符時跳過該檔並標記為 conflict（防 plan→apply TOCTOU）。"""
    # 套用前驗證所有待寫檔案的快照雜湊仍完整無誤
    for rel in plan.added + plan.modified:
        if _sha256_file(snap.root / rel) != snap.files.get(rel):
            all_planned = sorted(set(plan.skipped) | set(plan.added) | set(plan.modified) | set(plan.deleted))
            return {"added": [], "modified": [], "deleted": [], "skipped": all_planned, "conflict": list(plan.conflicts)}

    backup_dir.mkdir(parents=True, exist_ok=True)
    os.chmod(backup_dir, 0o700)
    undo: list[Callable[[], None]] = []
    bkp_seq = 0
    applied_deleted: list[str] = []
    applied_added: list[str] = []
    applied_modified: list[str] = []
    runtime_conflicts: set[str] = set()
    removed_dirs: set[str] = set()

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
            if start_hashes is not None:
                try:
                    st_live = target.lstat()
                except OSError:
                    runtime_conflicts.add(rel)
                    continue
                if stat.S_ISLNK(st_live.st_mode) or not stat.S_ISREG(st_live.st_mode):
                    runtime_conflicts.add(rel)
                    continue
                live_sha = _sha256_file(target)
                start_sha = start_hashes.get(rel)
                if live_sha is None or (start_sha is not None and live_sha != start_sha):
                    runtime_conflicts.add(rel)
                    continue
            bkp, old_mode = _backup_existing(target)
            target.unlink()
            applied_deleted.append(rel)
            undo.append(lambda t=target, b=bkp, m=old_mode: _atomic_write_from_file(b, t, m))

        # 2. 移除即將改為一般檔案的空目錄（由深到淺）
        for rel_dir in plan.dirs_to_remove:
            d = project / rel_dir
            try:
                old_mode = stat.S_IMODE(d.lstat().st_mode) & 0o777
                d.rmdir()
            except OSError:
                runtime_conflicts.add(rel_dir)
                continue
            removed_dirs.add(rel_dir)

            def _restore_dir(p: pathlib.Path = d, m: int = old_mode) -> None:
                p.mkdir(exist_ok=True)
                os.chmod(p, m)

            undo.append(_restore_dir)

        # 3. 寫入新增與修改的檔案（先補齊缺的父目錄並記下回滾動作）
        modified_set = set(plan.modified)
        for rel in sorted(plan.added + plan.modified):
            dst = project / rel
            src = snap.root / rel
            if start_hashes is not None:
                if rel in modified_set:
                    try:
                        st_live = dst.lstat()
                    except OSError:
                        runtime_conflicts.add(rel)
                        continue
                    if stat.S_ISLNK(st_live.st_mode) or not stat.S_ISREG(st_live.st_mode):
                        runtime_conflicts.add(rel)
                        continue
                    live_sha = _sha256_file(dst)
                    start_sha = start_hashes.get(rel)
                    if live_sha is None or (start_sha is not None and live_sha != start_sha):
                        runtime_conflicts.add(rel)
                        continue
                else:
                    if rel not in removed_dirs:
                        try:
                            dst.lstat()
                            # 開始時不存在、現在卻冒出來了 ⇒ TOCTOU conflict，跳過不覆寫
                            runtime_conflicts.add(rel)
                            continue
                        except FileNotFoundError:
                            pass
                        except OSError:
                            runtime_conflicts.add(rel)
                            continue
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
                applied_modified.append(rel)
                undo.append(lambda t=dst, b=bkp, m=old_mode: _atomic_write_from_file(b, t, m))
            else:
                _atomic_write_from_file(src, dst, snap.modes.get(rel))
                applied_added.append(rel)
                undo.append(lambda t=dst: t.unlink(missing_ok=True))

        return {
            "added": applied_added,
            "modified": applied_modified,
            "deleted": applied_deleted,
            "skipped": list(plan.skipped),
            "conflict": sorted(set(plan.conflicts) | runtime_conflicts),
        }
    except Exception:  # noqa: BLE001
        for fn in reversed(undo):
            try:
                fn()
            except Exception:  # noqa: BLE001
                pass
        all_planned = sorted(set(plan.skipped) | set(plan.added) | set(plan.modified) | set(plan.deleted))
        return {"added": [], "modified": [], "deleted": [], "skipped": all_planned, "conflict": list(plan.conflicts)}
    finally:
        _rmtree_force(backup_dir)


def _write_back(project: pathlib.Path, ws: pathlib.Path | _Snapshot, protected: set[str], *,
                _plan: _WritePlan | None = None,
                _backup_root: pathlib.Path | None = None,
                start_hashes: dict[str, str | None] | None = None) -> dict[str, list[str]]:
    tmp_dir: pathlib.Path | None = None
    try:
        if isinstance(ws, _Snapshot):
            snap = ws
        else:
            tmp_dir = pathlib.Path(tempfile.mkdtemp(prefix="vsnap-"))
            snap = _snapshot_workspace(ws, tmp_dir / "s")
        plan = _plan if _plan is not None else _plan_write_back(project, snap, protected, start_hashes=start_hashes)
        bkp_base = _backup_root if _backup_root is not None else pathlib.Path(tempfile.mkdtemp(prefix="vbkp-"))
        try:
            return _apply_write_plan(
                project, snap, plan, bkp_base / f"bkp-{secrets.token_hex(6)}",
                start_hashes=start_hashes,
            )
        finally:
            if _backup_root is None:
                _rmtree_force(bkp_base)
    except Exception:  # noqa: BLE001
        return {"added": [], "modified": [], "deleted": [], "skipped": [], "conflict": []}
    finally:
        if tmp_dir is not None:
            _rmtree_force(tmp_dir)


def _restore_test_file(work: pathlib.Path, rel: str, want: bytes, *, mode: int | None = None) -> None:
    """在驗收副本 work 裡強制還原單一原測試檔（處理路徑上被換成檔案、目錄、symlink 或唯讀權限的情況；
    保留原檔案的權限位元含執行權限）。"""
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
    final_mode = (mode & 0o777) if mode is not None else 0o600
    os.chmod(f, final_mode)


def _populate_acceptance_work(work: pathlib.Path, originals: dict[str, bytes], snap: _Snapshot,
                              project: pathlib.Path | None, plan: _WritePlan | None, *,
                              orig_modes: dict[str, int] | None = None,
                              start_snap: _Snapshot | None = None,
                              ignore_new: Callable[[str], bool] | None = None,
                              ignore_new_reason: Callable[[str, set[str] | None, set[str] | frozenset[str] | None], str | None] | None = None,
                              start_files: set[str] | frozenset[str] | None = None) -> None:
    """組裝驗收目錄 work：完全不含 symlink，以「開始快照＋本輪嘗試改動」組裝（絕不讀 live 專案的未改動檔），
    最後覆寫原測試檔（保留原始 mode 位元）。"""
    work.mkdir(parents=True, exist_ok=True)
    os.chmod(work, 0o700)
    protected = set(originals)
    if start_snap is not None and plan is not None:
        deleted_set = set(plan.deleted)
        written_set = set(plan.added) | set(plan.modified)
        # 1. 未被本輪刪除、未被本輪改寫的非受保護檔案一律取自 START 快照（不讀 live 專案）
        for rel in sorted(set(start_snap.files) - deleted_set - written_set - protected):
            m = 0o700 if (start_snap.modes.get(rel, 0) & 0o100) else 0o600
            _copy_reg_file(start_snap.root / rel, work / rel, mode=m)
        # 2. 放入本輪嘗試真正要寫回的新增／修改檔案
        for rel in sorted(written_set):
            m = 0o700 if (snap.modes.get(rel, 0) & 0o100) else 0o600
            _copy_reg_file(snap.root / rel, work / rel, mode=m)
    elif project is not None and plan is not None:
        deleted_set = set(plan.deleted)
        written_set = set(plan.added) | set(plan.modified)
        # 1. 保留專案中未被刪除、未被改寫、且非測試檔的一般檔案（包含因安全原因跳過刪除者；跳過執行期間新出現的並發檔）
        for rel in sorted(plan.before_files - deleted_set - written_set - protected - set(plan.appeared)):
            _copy_reg_file(project / rel, work / rel, mode=0o600, preserve_exec=True)
        # 2. 放入計畫中真正會寫回的新增／修改檔案（跳過不安全而不會寫回的檔案）
        for rel in sorted(written_set):
            m = 0o700 if (snap.modes.get(rel, 0) & 0o100) else 0o600
            _copy_reg_file(snap.root / rel, work / rel, mode=m)
    else:
        after_set = set(snap.files)
        for rel in sorted(snap.files):
            if rel in protected:
                continue
            is_new = start_files is None or rel not in start_files
            if is_new:
                if _is_test_config(rel):
                    continue
                if ignore_new_reason is not None:
                    if ignore_new_reason(rel, after_set, start_files) is not None:
                        continue
                elif ignore_new is not None and ignore_new(rel):
                    continue
            m = 0o700 if (snap.modes.get(rel, 0) & 0o100) else 0o600
            _copy_reg_file(snap.root / rel, work / rel, mode=m)
    # 3. 最後以開始時的原始測試檔覆寫（保留原始 mode 位元含執行權限）
    modes_map = orig_modes or {}
    for rel, want in sorted(originals.items()):
        _restore_test_file(work, rel, want, mode=modes_map.get(rel))


_SHADOW_PROBE = (
    "import importlib.metadata, importlib.util, json, os, sys\n"
    "proj_roots = [os.path.realpath(p) for p in json.loads(sys.argv[1])]\n"
    "drop = {os.path.abspath(p) for p in json.loads(sys.argv[1])} | {'', '.', os.path.abspath(os.getcwd())}\n"
    "drop_real = {os.path.realpath(p) for p in drop} | set(proj_roots)\n"
    "sys.path[:] = [\n"
    "    p for p in sys.path\n"
    "    if p not in ('', '.') and os.path.abspath(p) not in drop and os.path.realpath(p) not in drop_real\n"
    "]\n"
    "name = sys.argv[2]\n"
    "if name in getattr(sys, 'stdlib_module_names', ()):\n"
    "    sys.exit(0)\n"
    "try:\n"
    "    dists = importlib.metadata.packages_distributions()\n"
    "    if name in dists:\n"
    "        sys.exit(0)\n"
    "except Exception:\n"
    "    pass\n"
    "try:\n"
    "    spec = importlib.util.find_spec(name)\n"
    "    if spec is not None:\n"
    "        orig = getattr(spec, 'origin', None)\n"
    "        locs = list(getattr(spec, 'submodule_search_locations', None) or ())\n"
    "        def _in_proj(path):\n"
    "            if not path or path in ('built-in', 'frozen'):\n"
    "                return False\n"
    "            rp = os.path.realpath(path)\n"
    "            return any(rp == r or rp.startswith(r + os.sep) for r in proj_roots)\n"
    "        if (orig and _in_proj(orig)) or (locs and all(_in_proj(l) for l in locs)):\n"
    "            sys.exit(1)\n"
    "        sys.exit(0)\n"
    "except Exception:\n"
    "    pass\n"
    "sys.exit(1)\n"
)


def _python_module_resolves_in_interpreter(
    python_exe: str,
    mod_name: str,
    project_dirs: Sequence[str],
    *,
    clean_env: bool = False,
    cache: dict[str, bool] | None = None,
) -> bool:
    """Check whether top-level module `mod_name` already resolves in `python_exe`
    (stdlib, installed distribution, or find_spec) with project directories removed from sys.path."""
    if not mod_name or mod_name == "__pycache__" or not mod_name.isidentifier():
        return False
    if cache is not None and mod_name in cache:
        return cache[mod_name]
    try:
        same_interp = os.path.realpath(python_exe) == os.path.realpath(sys.executable)
    except OSError:
        same_interp = False
    if same_interp and mod_name in sys.stdlib_module_names:
        if cache is not None:
            cache[mod_name] = True
        return True
    drop_dirs = sorted({os.path.abspath(d) for d in project_dirs if d})
    if clean_env:
        env = _clean_env(pathlib.Path(tempfile.gettempdir()), python_exe=python_exe)
    else:
        env = dict(os.environ)
        # Strip PYTHONPATH entries pointing inside project directories
        if "PYTHONPATH" in env:
            drop_reals = {os.path.realpath(d) for d in drop_dirs}
            kept: list[str] = []
            for entry in env["PYTHONPATH"].split(os.pathsep):
                if not entry or entry == ".":
                    continue
                re_p = os.path.realpath(entry)
                if any(re_p == dr or re_p.startswith(dr + os.sep) for dr in drop_reals):
                    continue
                kept.append(entry)
            if kept:
                env["PYTHONPATH"] = os.pathsep.join(kept)
            else:
                env.pop("PYTHONPATH", None)
    try:
        cp = subprocess.run(
            [python_exe, "-B", "-c", _SHADOW_PROBE, json.dumps(drop_dirs), mod_name],
            cwd=tempfile.gettempdir(),
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=10.0,
        )
        res = cp.returncode == 0
    except (OSError, subprocess.SubprocessError):
        res = mod_name in sys.stdlib_module_names
    if cache is not None:
        cache[mod_name] = res
    return res


def _collect_start_project_modules(all_files: Sequence[str], py_dirs: set[str]) -> dict[str, tuple[str, ...]]:
    """Map top-level Python module names existing at start in `py_dirs` -> their start rel paths."""
    if not py_dirs:
        return {}
    mods: dict[str, set[str]] = {}
    for rel in all_files:
        if not rel.endswith(".py"):
            continue
        for d in py_dirs:
            if d == "":
                sub = rel
            elif rel.startswith(d + "/"):
                sub = rel[len(d) + 1:]
            else:
                continue
            parts = sub.split("/")
            if len(parts) == 1 and parts[0].endswith(".py"):
                stem = parts[0][:-3]
                if stem and stem != "__init__" and stem != "__pycache__" and stem.isidentifier():
                    mods.setdefault(stem, set()).add(rel)
            elif len(parts) == 2 and parts[1] == "__init__.py":
                pkg = parts[0]
                if pkg and pkg != "__pycache__" and pkg.isidentifier():
                    mods.setdefault(pkg, set()).add(rel)
    return {k: tuple(sorted(v)) for k, v in mods.items()}


@dataclasses.dataclass(frozen=True)
class AcceptanceSpec:
    kind: str                          # check | python_unittest | python_pytest | python_bare | npm | cargo | go | none
    command: str | None
    argv: tuple[str, ...] | None = None
    protected: tuple[str, ...] = ()
    reason: str | None = None
    interpreter: str | None = None
    pinned_script: str | None = None
    pinned_scripts: dict[str, str] = dataclasses.field(default_factory=dict)
    pinned_named_scripts: dict[str, dict[str, str]] = dataclasses.field(default_factory=dict)
    shell_expansion: bool = False
    integrity: str | None = None       # "traced" | "untraced" | None (for kind == "none")
    integrity_reasons: tuple[str, ...] = ()
    ignored_new_paths: tuple[str, ...] = ()
    ignored_new_globs: tuple[tuple[str, str], ...] = ()
    unfixed_deps: dict[str, tuple[str, ...]] = dataclasses.field(default_factory=dict)
    py_sys_path_dirs: tuple[str, ...] = ()
    protected_test_dirs: tuple[str, ...] = ()
    start_files: frozenset[str] = dataclasses.field(default_factory=frozenset)
    start_project_modules: dict[str, tuple[str, ...]] = dataclasses.field(default_factory=dict)
    shadow_check_python: str | None = None
    shadow_check_clean_env: bool = False
    project_root: str | None = None
    _shadow_cache: dict[str, bool] = dataclasses.field(default_factory=dict, repr=False, compare=False)

    def ignored_new_file_reason(
        self,
        rel: str,
        all_files: set[str] | None = None,
        start_files: set[str] | frozenset[str] | None = None,
    ) -> str | None:
        """Return None if `rel` is a normal new file; return '' if it is ignored as
        test-config / make-target / unittest-discover-glob / test-dir __init__.py;
        return `\"shadows module 'X'\"` if it shadows a module that already resolved at start."""
        for p in self.ignored_new_paths:
            if rel == p or rel.startswith(p + "/"):
                return ""
        if self.ignored_new_globs:
            bn = pathlib.PurePosixPath(rel).name
            for pref, pat in self.ignored_new_globs:
                if (pref == "" or rel.startswith(pref + "/")) and fnmatch.fnmatchcase(bn, pat):
                    return ""
        # New __init__.py under a test directory (tests/, test/, __tests__) or next to a protected test file
        parts = pathlib.PurePosixPath(rel).parts
        if parts and parts[-1] == "__init__.py":
            parent_parts = parts[:-1]
            parent_dir = "/".join(parent_parts)
            if any(d in _UNIVERSAL_TEST_DIRS for d in parent_parts) or parent_dir in self.protected_test_dirs:
                return ""
        # Python module shadowing: new X.py or new dir X/ containing __init__.py on check's sys.path
        if self.py_sys_path_dirs:
            eff_start = start_files if start_files is not None else self.start_files
            for d in self.py_sys_path_dirs:
                if d == "":
                    sub = rel
                elif rel.startswith(d + "/"):
                    sub = rel[len(d) + 1:]
                else:
                    continue
                sub_parts = sub.split("/")
                cand_mod: str | None = None
                if len(sub_parts) == 1 and sub_parts[0].endswith(".py"):
                    stem = sub_parts[0][:-3]
                    if stem and stem != "__init__" and stem != "__pycache__" and stem.isidentifier():
                        cand_mod = stem
                elif len(sub_parts) == 2 and sub_parts[1] == "__init__.py":
                    pkg = sub_parts[0]
                    if pkg and pkg != "__pycache__" and pkg.isidentifier():
                        cand_mod = pkg
                elif len(sub_parts) >= 2 and all_files is not None:
                    pkg = sub_parts[0]
                    pkg_prefix = f"{d}/{pkg}" if d else pkg
                    pkg_init = f"{pkg_prefix}/__init__.py"
                    if (pkg and pkg != "__pycache__" and pkg.isidentifier()
                            and pkg_init in all_files
                            and pkg_init not in eff_start
                            and not any(f.startswith(pkg_prefix + "/") for f in eff_start)):
                        cand_mod = pkg
                if cand_mod is None:
                    continue
                resolved_at_start = False
                if cand_mod in self.start_project_modules:
                    resolved_at_start = True
                elif self.shadow_check_python:
                    drop_dirs: list[str] = []
                    if self.project_root:
                        drop_dirs.append(self.project_root)
                        for pd in self.py_sys_path_dirs:
                            drop_dirs.append(os.path.join(self.project_root, pd) if pd else self.project_root)
                    resolved_at_start = _python_module_resolves_in_interpreter(
                        self.shadow_check_python,
                        cand_mod,
                        drop_dirs,
                        clean_env=self.shadow_check_clean_env,
                        cache=self._shadow_cache,
                    )
                else:
                    resolved_at_start = cand_mod in sys.stdlib_module_names
                if resolved_at_start:
                    return f"shadows module '{cand_mod}'"
        return None

    def should_ignore_new_file(self, rel: str) -> bool:
        return self.ignored_new_file_reason(rel) is not None

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
        if self.pinned_scripts:
            d["pinned_scripts"] = dict(self.pinned_scripts)
        if self.pinned_named_scripts:
            d["pinned_named_scripts"] = {k: dict(v) for k, v in self.pinned_named_scripts.items()}
        if self.shell_expansion:
            d["shell_expansion"] = True
        if self.integrity is not None:
            d["integrity"] = self.integrity
            d["integrity_reasons"] = list(self.integrity_reasons)
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

    start_files_fs = frozenset(all_files)
    has_src_dir = (project / "src").is_dir() or any(f.startswith("src/") for f in all_files)

    def _py_guard_kwargs(
        prot: Sequence[str],
        *,
        is_python: bool,
        extra_py_dirs: set[str] | None = None,
        extra_test_dirs: set[str] | None = None,
        shadow_python: str | None = None,
        clean_env: bool = False,
    ) -> dict[str, Any]:
        prot_test_dirs: set[str] = set(extra_test_dirs or ())
        for rel in prot:
            if _is_python_test(rel) or _is_universal_test(rel) or (is_python and rel.endswith(".py")):
                p = pathlib.PurePosixPath(rel).parent
                prot_test_dirs.add("" if p == pathlib.PurePosixPath(".") else p.as_posix())
        py_dirs: set[str] = set()
        if is_python:
            py_dirs.add("")
            if has_src_dir:
                py_dirs.add("src")
            if extra_py_dirs:
                py_dirs |= extra_py_dirs
            py_dirs |= prot_test_dirs
        start_mods = _collect_start_project_modules(all_files, py_dirs) if py_dirs else {}
        return {
            "py_sys_path_dirs": tuple(sorted(py_dirs)),
            "protected_test_dirs": tuple(sorted(prot_test_dirs)),
            "start_files": start_files_fs,
            "start_project_modules": start_mods,
            "shadow_check_python": shadow_python if is_python else None,
            "shadow_check_clean_env": clean_env,
            "project_root": str(project),
        }

    if check is not None:
        cmd = check.strip()
        if not cmd:
            raise ValueError("--check command must not be empty")
        files_set = set(all_files)
        extra_check, pinned_script_r2, pinned_scripts_r2, uses_exp = _check_command_protections(
            project, cmd, files_set
        )
        analysis = _analyze_acceptance_command(project, cmd, files_set)
        merged_pinned = {**pinned_scripts_r2, **analysis.pinned_scripts}
        pinned_script = merged_pinned.get("package.json") or pinned_script_r2
        prot = tuple(sorted(set(_prot("check")) | extra_check | analysis.protected))
        integ = analysis.integrity
        integ_reasons = list(analysis.reasons)
        if not prot and analysis.runs_project_code:
            integ = "untraced"
            if "no project files kept fixed" not in integ_reasons:
                integ_reasons.append("no project files kept fixed")
        dyn_reasons = _scan_protected_dynamic_imports(
            project, prot, originals=originals, existing_reasons=integ_reasons
        )
        if dyn_reasons:
            integ = "untraced"
            for dr in dyn_reasons:
                if dr not in integ_reasons:
                    integ_reasons.append(dr)
        is_py_check = analysis.uses_python or any(r.endswith(".py") for r in extra_check)
        if not is_py_check:
            cw, _, _ = _parse_check_shell_cmd(cmd)
            is_py_check = any(_PY_TOOL_RE.match(w) or w == "pytest" for w in cw)
        shadow_py = (
            analysis.py_interpreters[0]
            if analysis.py_interpreters
            else (resolve_python(project) if is_py_check else None)
        )
        return AcceptanceSpec(
            kind="check",
            command=cmd,
            argv=None,
            protected=prot,
            pinned_script=pinned_script,
            pinned_scripts=merged_pinned,
            pinned_named_scripts=analysis.pinned_named_scripts,
            shell_expansion=bool(uses_exp or analysis.shell_expansion),
            integrity=integ,
            integrity_reasons=tuple(integ_reasons),
            ignored_new_paths=tuple(sorted(analysis.ignored_new_paths)),
            ignored_new_globs=tuple(analysis.ignored_new_globs),
            unfixed_deps={k: tuple(sorted(v)) for k, v in analysis.unfixed_deps.items()},
            **_py_guard_kwargs(
                prot,
                is_python=is_py_check,
                extra_py_dirs=analysis.py_sys_path_dirs,
                extra_test_dirs=analysis.unittest_start_dirs,
                shadow_python=shadow_py,
                clean_env=False,
            ),
        )

    if py_orig:
        py_exe = resolve_python(project)
        insp = _inspect_python_tests(py_orig)

        def _auto_py_integrity(prot_files: Sequence[str]) -> tuple[str, tuple[str, ...]]:
            if not prot_files:
                return "untraced", ("no project files kept fixed",)
            dyn = _scan_protected_dynamic_imports(project, prot_files, originals=py_orig)
            if dyn:
                return "untraced", tuple(dyn)
            return "traced", ()

        if insp.syntax_error is not None:
            prot_u = _prot("python_unittest")
            integ_u, reasons_u = _auto_py_integrity(prot_u)
            return AcceptanceSpec(
                kind="python_unittest",
                command=f"{py_exe} -B (unittest)",
                protected=prot_u,
                reason=f"syntax error in original test file: {insp.syntax_error}",
                interpreter=py_exe,
                integrity=integ_u,
                integrity_reasons=reasons_u,
                **_py_guard_kwargs(prot_u, is_python=True, shadow_python=py_exe, clean_env=True),
            )
        if insp.has_pytest_style:
            if _pytest_available(py_exe):
                prot_p = _prot("python_pytest")
                integ_p, reasons_p = _auto_py_integrity(prot_p)
                return AcceptanceSpec(
                    kind="python_pytest",
                    command=f"{py_exe} -B -m pytest -q -rN",
                    protected=prot_p,
                    interpreter=py_exe,
                    integrity=integ_p,
                    integrity_reasons=reasons_p,
                    **_py_guard_kwargs(prot_p, is_python=True, shadow_python=py_exe, clean_env=True),
                )
            prot_b = _prot("python_bare")
            integ_b, reasons_b = _auto_py_integrity(prot_b)
            return AcceptanceSpec(
                kind="python_bare",
                command=f"{py_exe} -B (stdlib test runner)",
                protected=prot_b,
                interpreter=py_exe,
                integrity=integ_b,
                integrity_reasons=reasons_b,
                **_py_guard_kwargs(prot_b, is_python=True, shadow_python=py_exe, clean_env=True),
            )
        prot_u = _prot("python_unittest")
        integ_u, reasons_u = _auto_py_integrity(prot_u)
        return AcceptanceSpec(
            kind="python_unittest",
            command=f"{py_exe} -B (unittest)",
            protected=prot_u,
            interpreter=py_exe,
            integrity=integ_u,
            integrity_reasons=reasons_u,
            **_py_guard_kwargs(prot_u, is_python=True, shadow_python=py_exe, clean_env=True),
        )

    missing: list[str] = []
    npm_script = _npm_test_script(project)
    if npm_script is not None:
        if shutil.which("npm"):
            analysis = _analyze_acceptance_command(project, "npm test", set(all_files))
            merged_pinned = {"package.json": npm_script, **analysis.pinned_scripts}
            prot = tuple(sorted(set(_prot("npm")) | analysis.protected))
            integ = analysis.integrity
            integ_reasons = list(analysis.reasons)
            if not prot:
                integ = "untraced"
                if "no project files kept fixed" not in integ_reasons:
                    integ_reasons.append("no project files kept fixed")
            npm_dyn = _scan_protected_dynamic_imports(
                project, prot, originals=originals, existing_reasons=integ_reasons
            )
            if npm_dyn:
                integ = "untraced"
                for dr in npm_dyn:
                    if dr not in integ_reasons:
                        integ_reasons.append(dr)
            npm_py = analysis.uses_python
            npm_shadow_py = (
                analysis.py_interpreters[0]
                if analysis.py_interpreters
                else (resolve_python(project) if npm_py else None)
            )
            return AcceptanceSpec(
                kind="npm",
                command="npm test",
                argv=("npm", "test"),
                protected=prot,
                pinned_script=npm_script,
                pinned_scripts=merged_pinned,
                pinned_named_scripts=analysis.pinned_named_scripts,
                shell_expansion=analysis.shell_expansion,
                integrity=integ,
                integrity_reasons=tuple(integ_reasons),
                ignored_new_paths=tuple(sorted(analysis.ignored_new_paths)),
                ignored_new_globs=tuple(analysis.ignored_new_globs),
                unfixed_deps={k: tuple(sorted(v)) for k, v in analysis.unfixed_deps.items()},
                **_py_guard_kwargs(
                    prot,
                    is_python=npm_py,
                    extra_py_dirs=analysis.py_sys_path_dirs,
                    extra_test_dirs=analysis.unittest_start_dirs,
                    shadow_python=npm_shadow_py,
                    clean_env=False,
                ),
            )
        missing.append("package.json has a \"test\" script, but 'npm' was not found on PATH")

    if _has_reg_file(project / "Cargo.toml"):
        if shutil.which("cargo"):
            prot_c = _prot("cargo")
            return AcceptanceSpec(
                kind="cargo", command="cargo test", argv=("cargo", "test"),
                protected=prot_c,
                integrity="traced" if prot_c else "untraced",
                integrity_reasons=() if prot_c else ("no project files kept fixed",),
                **_py_guard_kwargs(prot_c, is_python=False),
            )
        missing.append("Cargo.toml found, but 'cargo' was not found on PATH")

    if _has_reg_file(project / "go.mod"):
        if shutil.which("go"):
            prot_g = _prot("go")
            return AcceptanceSpec(
                kind="go", command="go test ./...", argv=("go", "test", "./..."),
                protected=prot_g,
                integrity="traced" if prot_g else "untraced",
                integrity_reasons=() if prot_g else ("no project files kept fixed",),
                **_py_guard_kwargs(prot_g, is_python=False),
            )
        missing.append("go.mod found, but 'go' was not found on PATH")

    prot_n = _prot("none")
    return AcceptanceSpec(
        kind="none",
        command=None,
        argv=None,
        protected=prot_n,
        reason="; ".join(missing) if missing else None,
        integrity=None,
        **_py_guard_kwargs(prot_n, is_python=False),
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
                                work_root: pathlib.Path | None = None,
                                run_id: str | None = None
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
                    env=_clean_env(home, python_exe=exe, work_root=work_root, run_id=run_id),
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
                         project_root: pathlib.Path | None = None,
                         run_id: str | None = None) -> dict[str, Any]:
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
            run_id=run_id,
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
                       project_root: pathlib.Path | None = None,
                       run_id: str | None = None) -> dict[str, Any]:
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
        run_id=run_id,
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
                     project_root: pathlib.Path | None = None,
                     run_id: str | None = None) -> dict[str, Any]:
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
            run_id=run_id,
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
                          node_modules_dir: pathlib.Path | None = None,
                          run_id: str | None = None) -> dict[str, Any]:
    """在快照副本 work 裡執行外部驗收指令（--check／npm／cargo／go），獨立 session、共用期限、沿用使用者環境。"""
    if deadline - time.monotonic() <= 0:
        return {**base, "status": "timeout"}
    work_res = work.resolve()
    if spec.kind in ("npm", "check"):
        pinned_map = dict(spec.pinned_scripts)
        if spec.pinned_script is not None and "package.json" not in pinned_map:
            pinned_map["package.json"] = spec.pinned_script
        for pkg_rel, want_script in sorted(pinned_map.items()):
            if _npm_test_script_at(work_res / pkg_rel) != want_script:
                return {
                    **base,
                    "status": "acceptance_error",
                    "accept": False,
                    "first_problem": f"{pkg_rel} scripts.test does not match the pinned start definition",
                }
        for pkg_rel, named_map in sorted(spec.pinned_named_scripts.items()):
            for sc_name, want_script in sorted(named_map.items()):
                if _npm_script_at(work_res / pkg_rel, sc_name) != want_script:
                    return {
                        **base,
                        "status": "acceptance_error",
                        "accept": False,
                        "first_problem": f"{pkg_rel} scripts.{sc_name} does not match the pinned start definition",
                    }
    env = dict(os.environ)
    env["PWD"] = str(work_res)
    if run_id:
        env[_DETACHED_MARKER_ENV] = run_id
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
               _plan: _WritePlan | None = None,
               _orig_modes: dict[str, int] | None = None,
               _start_snap: _Snapshot | None = None,
               _run_id: str | None = None) -> dict:
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
        eff_orig_modes = dict(_orig_modes) if _orig_modes is not None else {}
        if _orig_modes is None and _project is not None:
            for rel in originals:
                try:
                    eff_orig_modes[rel] = stat.S_IMODE((_project / rel).lstat().st_mode) & 0o777
                except OSError:
                    pass
        _populate_acceptance_work(
            work, originals, snap, _project, _plan, orig_modes=eff_orig_modes, start_snap=_start_snap,
            ignore_new=(spec.should_ignore_new_file if spec is not None else None),
            ignore_new_reason=(spec.ignored_new_file_reason if spec is not None else None),
            start_files=(spec.start_files if (spec is not None and spec.start_files) else None),
        )
        home = tmp / "h"
        home.mkdir(mode=0o700)
        runner_dir = tmp / "r"
        runner_dir.mkdir(mode=0o700)

        if spec.kind == "python_unittest":
            return _run_python_unittest(
                base, py_tests, work, home, runner_dir, deadline,
                python_exe=py_exe, project_root=_project, run_id=_run_id,
            )
        if spec.kind == "python_pytest":
            return _run_python_pytest(
                base, py_tests, work, home, runner_dir, deadline,
                python_exe=py_exe, project_root=_project, run_id=_run_id,
            )
        if spec.kind == "python_bare":
            return _run_python_bare(
                base, py_tests, work, home, runner_dir, deadline,
                python_exe=py_exe, project_root=_project, run_id=_run_id,
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
                    node_modules_dir=nm_target, run_id=_run_id,
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
    s, _ = _safe_str(s)
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


def _has_surrogates(s: str) -> bool:
    return any(0xD800 <= ord(ch) <= 0xDFFF for ch in s)


def _to_raw_bytes(s: str) -> bytes:
    """還原字串的原始位元組：對 surrogateescape 字串用 os.fsencode，其餘孤立 surrogate 退回 surrogatepass。"""
    try:
        return os.fsencode(s)
    except UnicodeEncodeError:
        return s.encode("utf-8", errors="surrogatepass")


def _safe_str(val: str | os.PathLike[str]) -> tuple[str, bool]:
    """將可能含 surrogateescape（非 UTF-8 位元組）的任意字串或路徑轉為確定性 UTF-8 安全字串。
    合法 UTF-8 字串原樣回傳 `(s, False)`；含 surrogate 時經 `os.fsencode(s)` 還原原始位元組，
    再以 UTF-8 `backslashreplace` 解碼（如 0xff → `\\xff`），回傳 `(safe, True)`。"""
    s = os.fspath(val)
    if not _has_surrogates(s):
        return s, False
    return _to_raw_bytes(s).decode("utf-8", errors="backslashreplace"), True


_safe_path_str = _safe_str


def _sanitize_json_obj(obj: Any) -> tuple[Any, bool]:
    """遞迴將結構內所有含 surrogate 的字串轉為 byte-safe UTF-8 字串，回傳 `(new_obj, had_non_utf8)`。"""
    if isinstance(obj, str):
        return _safe_str(obj)
    if isinstance(obj, list):
        had = False
        out = []
        for item in obj:
            v, f = _sanitize_json_obj(item)
            had = had or f
            out.append(v)
        return out, had
    if isinstance(obj, tuple):
        had = False
        out = []
        for item in obj:
            v, f = _sanitize_json_obj(item)
            had = had or f
            out.append(v)
        return out, had
    if isinstance(obj, dict):
        had = False
        out_d: dict[Any, Any] = {}
        for k, v in obj.items():
            nk, fk = _sanitize_json_obj(k) if isinstance(k, str) else (k, False)
            nv, fv = _sanitize_json_obj(v)
            had = had or fk or fv
            out_d[nk] = nv
        return out_d, had
    return obj, False


def _snapshot_tree_sha256(snap: _Snapshot | None) -> str | None:
    """對快照檔案樹算確定性 SHA-256（按排序相對路徑原始位元組與檔案 SHA-256 逐筆串接）。"""
    if snap is None:
        return None
    h = hashlib.sha256()
    for rel in sorted(snap.files):
        h.update(os.fsencode(rel))
        h.update(b"\x00")
        h.update(snap.files[rel].encode("ascii"))
        h.update(b"\n")
    return h.hexdigest()


def _written_back_entries(project: pathlib.Path, snap: _Snapshot | None,
                          changed: dict[str, list[str]]) -> tuple[list[dict[str, Any]], bool]:
    """收集實際寫回專案的檔案清單及其 SHA-256（按相對路徑排序；非 UTF-8 檔名採一致 backslashreplace）。"""
    ops: list[tuple[str, str]] = (
        [(rel, "added") for rel in changed.get("added") or ()]
        + [(rel, "modified") for rel in changed.get("modified") or ()]
    )
    ops.sort(key=lambda t: t[0])
    out: list[dict[str, Any]] = []
    had_non_utf8 = False
    for rel, op in ops:
        sha = _sha256_file(project / rel)
        if sha is None and snap is not None:
            sha = snap.files.get(rel)
        safe_rel, flag = _safe_path_str(rel)
        had_non_utf8 = had_non_utf8 or flag
        out.append({"path": safe_rel, "op": op, "sha256": sha})
    return out, had_non_utf8


def _list_sha256(items: Any) -> str:
    from ..canonical import canonical_bytes
    return hashlib.sha256(canonical_bytes(items)).hexdigest()


def _bound_receipt_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """確保收據 payload 永遠低於 Logbook.MAX_PAYLOAD_BYTES（不依賴可被 gc 的外部 blob）。"""
    from ..canonical import canonical_bytes
    if len(canonical_bytes(payload)) <= _RECEIPT_MAX_BYTES:
        return payload
    out = dict(payload)
    for key in ("written_back", "deleted", "skipped", "appeared_during_run", "conflicts",
                "write_back_conflicts", "outside_changes", "acceptance_dependencies_changed",
                "acceptance_integrity_reasons", "not_delivered", "detached_processes",
                "unreadable_paths"):
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


def _repair_vacant_state_permissions(project: pathlib.Path) -> None:
    """Repair user permissions on Vacant's own state paths (u+rwx dirs, u+rw files; never follows symlinks)
    from $VACANT_HOME down to the trace chain path, key paths, trust.json, and head.json."""
    from ..intake.statepaths import state_dir
    from ..trace.recorder import project_key

    def _fix_dir(p: pathlib.Path) -> None:
        try:
            st = p.lstat()
        except OSError:
            return
        if stat.S_ISLNK(st.st_mode) or not stat.S_ISDIR(st.st_mode):
            return
        try:
            os.chmod(p, stat.S_IMODE(st.st_mode) | stat.S_IRWXU)
        except OSError:
            pass

    def _fix_file(p: pathlib.Path) -> None:
        try:
            st = p.lstat()
        except OSError:
            return
        if stat.S_ISLNK(st.st_mode) or not stat.S_ISREG(st.st_mode):
            return
        try:
            os.chmod(p, stat.S_IMODE(st.st_mode) | stat.S_IRUSR | stat.S_IWUSR)
        except OSError:
            pass

    vh = state_dir()
    pkey = project_key(project)
    trace_root = vh / "trace"
    trace_projects = trace_root / "projects"
    trace_proj = trace_projects / pkey
    trace_objs = trace_root / "objects"
    intake_root = vh / "intake"
    keys_root = intake_root / "keys"

    # Top-down directory repair so parent dirs are traversable/writable before touching children
    for d in (vh, trace_root, trace_projects, trace_proj, trace_objs, intake_root, keys_root):
        _fix_dir(d)
    for role in ("verifier", "approver", "reviewer", "owner"):
        rdir = keys_root / role
        _fix_dir(rdir)
        for fname in ("identity.key", "identity.pub", "identity.json"):
            _fix_file(rdir / fname)
        try:
            for e in os.scandir(rdir):
                _fix_file(pathlib.Path(e.path))
        except OSError:
            pass

    for f in (
        intake_root / "trust.json",
        intake_root / "keys.lock",
        trace_proj / "chain.ndjson",
        trace_proj / "head.json",
        trace_proj / "state.json",
        trace_proj / "lock",
        trace_proj / ".lock",
    ):
        _fix_file(f)
    try:
        for e in os.scandir(trace_proj):
            ep = pathlib.Path(e.path)
            _fix_file(ep)
    except OSError:
        pass


def _record_receipt(*, project: pathlib.Path, prompt: str, agent: str | None,
                    launch_meta: list[tuple[list[str], dict[str, str]]],
                    spec: AcceptanceSpec, protected: set[str],
                    attempts: list[dict[str, Any]], snaps: list[_Snapshot | None],
                    delivered_idx: int, changed: dict[str, list[str]],
                    res: dict[str, Any], run_dir: pathlib.Path) -> dict[str, Any]:
    """把這次 restart-mode 執行簽進專案既有的 trace 簽章鏈（`$VACANT_HOME/trace/projects/<proj>/chain.ndjson`）。
    寫入前先修復 `$VACANT_HOME` 至簽章鏈／金鑰／`trust.json`／`head.json` 的使用者權限並於失敗時重試一次；
    仍失敗則 fail-open（不改結束碼、記 `receipt_error` 並於摘要最前一行明講警告）。"""
    try:
        from ..trace.recorder import Recorder, project_key
        first_argv, first_env = launch_meta[0] if launch_meta else ([], {})
        agent_name = agent or (pathlib.Path(first_argv[0]).name if first_argv else "unknown")
        proj_safe, proj_non_utf8 = _safe_path_str(project)
        proj_sha = hashlib.sha256(proj_safe.encode("utf-8")).hexdigest()
        pkey = project_key(project)
        attempt_recs: list[dict[str, Any]] = []
        for idx, a in enumerate(attempts):
            snap = snaps[idx] if idx < len(snaps) else None
            attempt_recs.append({
                "attempt": a["attempt"],
                "wall_s": a["wall_s"],
                "rc": a["rc"],
                "timed_out": a["timed_out"],
                "time_limit_s": a.get("time_limit_s"),
                "accept": a["accept"],
                "passed": a["passed"],
                "run": a["run"],
                "status": a["status"],
                "tests_tampered": list(a["tests_tampered"]),
                "snapshot_tree_sha256": _snapshot_tree_sha256(snap),
            })
        delivered_snap = snaps[delivered_idx] if 0 <= delivered_idx < len(snaps) else None
        wb_entries, wb_non_utf8 = _written_back_entries(project, delivered_snap, changed)
        payload: dict[str, Any] = {
            "receipt_schema": RECEIPT_SCHEMA,
            "run_id": run_dir.name,
            "request_sha256": hashlib.sha256(_to_raw_bytes(prompt)).hexdigest(),
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
                "integrity": spec.integrity,
                "integrity_reasons": list(spec.integrity_reasons),
            },
            "acceptance_integrity": spec.integrity,
            "acceptance_integrity_reasons": list(spec.integrity_reasons),
            "baseline": res.get("baseline"),
            "baseline_error": res.get("baseline_error"),
            "node_modules_changed": res.get("node_modules_changed") or [],
            "max_attempts": res["max_attempts"],
            "attempts": attempt_recs,
            "delivered_attempt": res["delivered_attempt"],
            "accepted": res["accepted"],
            "written_back": wb_entries,
            "deleted": list(changed.get("deleted") or ()),
            "skipped": list(changed.get("skipped") or ()),
            "appeared_during_run": list(res.get("appeared_during_run") or ()),
            "conflicts": list(res.get("conflicts") or ()),
            "write_back_conflicts": list(res.get("write_back_conflicts") or ()),
            "outside_changes": list(res.get("outside_changes") or ()),
            "protected_outside_changes": list(res.get("protected_outside_changes") or ()),
            "lstat_listing_s": res.get("lstat_listing_s"),
            "detached_processes": res.get("detached_processes"),
            "acceptance_dependencies_changed": list(res.get("acceptance_dependencies_changed") or ()),
            "not_delivered": list(res.get("not_delivered") or ()),
            "agent_wall_s": res["agent_wall_s"],
            "total_wall_s": res["total_wall_s"],
        }
        if res.get("unreadable_paths"):
            payload["unreadable_paths"] = list(res["unreadable_paths"])
        payload, payload_non_utf8 = _sanitize_json_obj(payload)
        any_non_utf8 = bool(
            proj_non_utf8 or wb_non_utf8 or payload_non_utf8
            or res.get("non_utf8_paths") or _has_surrogates(prompt)
        )
        payload["non_utf8_paths"] = any_non_utf8
        if any_non_utf8:
            payload["path_encoding"] = "utf-8-backslashreplace"
        payload = _bound_receipt_payload(payload)
        last_exc: Exception | None = None
        for _attempt in range(2):
            _repair_vacant_state_permissions(project)
            try:
                rec = Recorder(project)
                ref = rec.append("restart_receipt", payload)
                return {
                    "recorded": True,
                    "schema": RECEIPT_SCHEMA,
                    "project_key": rec.dir.name,
                    "chain_path": _safe_str(rec.chain_path)[0],
                    "seq": ref["seq"],
                    "hash": ref["hash"],
                }
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
        assert last_exc is not None
        raise last_exc
    except Exception as e:  # noqa: BLE001 — fail-open：記錄失敗不影響已交回結果
        err_safe = _safe_str(f"{type(e).__name__}: {e}")[0]
        return {
            "recorded": False,
            "schema": RECEIPT_SCHEMA,
            "error": err_safe[:300],
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


AGENT_QUICK_FAIL_MS = 30_000


def _nm_root(project: pathlib.Path) -> pathlib.Path | None:
    nm = project / "node_modules"
    try:
        return nm.resolve() if nm.is_dir() else None
    except OSError:
        return None


_NM_CHEAP_SHA_MAX_FILES = 500
_NM_CHEAP_SHA_MAX_BYTES = 5 * 1024 * 1024


def _is_within_dir(path: pathlib.Path, parent: pathlib.Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _lstat_tuple(full: str | os.PathLike[str], st: os.stat_result) -> tuple:
    """lstat 摘要：(type, size, mtime_ns, ctime_ns, ino, mode, symlink_target)。
    一般使用者無法偽造 ctime_ns，故同長度覆寫並還原 mtime 仍會改變 ctime_ns。"""
    mode = stat.S_IMODE(st.st_mode)
    if stat.S_ISLNK(st.st_mode):
        try:
            tgt = os.readlink(full)
        except OSError:
            tgt = None
        return ("l", st.st_size, st.st_mtime_ns, st.st_ctime_ns, st.st_ino, mode, tgt)
    if stat.S_ISDIR(st.st_mode):
        return ("d", st.st_size, st.st_mtime_ns, st.st_ctime_ns, st.st_ino, mode, None)
    if stat.S_ISREG(st.st_mode):
        return ("f", st.st_size, st.st_mtime_ns, st.st_ctime_ns, st.st_ino, mode, None)
    return ("o", st.st_size, st.st_mtime_ns, st.st_ctime_ns, st.st_ino, mode, None)


def _nm_manifest(root: pathlib.Path) -> dict[str, tuple]:
    """node_modules 的 lstat 清單：相對路徑 → (type, size, mtime_ns, ctime_ns, ino, mode, symlink_target)。
    對於指向 node_modules 外部的 symlink，追蹤並納入其目標檔案（含循環保護），
    使直接寫入 symlink 目標的逃逸會被偵測為 node_modules_modified。"""
    out: dict[str, tuple] = {}
    root_res = root.resolve()
    visited_dirs: set[tuple[int, int]] = set()
    try:
        rst = os.stat(root_res)
        visited_dirs.add((rst.st_dev, rst.st_ino))
    except OSError:
        pass

    def _walk_dir(cur_dir: pathlib.Path, rel_prefix: str) -> None:
        try:
            it = list(os.scandir(cur_dir))
        except OSError:
            out[(rel_prefix + "/") if rel_prefix else "./"] = ("unreadable",)
            return
        for e in it:
            try:
                st = e.stat(follow_symlinks=False)
            except OSError:
                continue
            rel = f"{rel_prefix}/{e.name}" if rel_prefix else e.name
            if stat.S_ISLNK(st.st_mode):
                out[rel] = _lstat_tuple(e.path, st)
                try:
                    resolved = pathlib.Path(e.path).resolve()
                except OSError:
                    continue
                if not _is_within_dir(resolved, root_res):
                    try:
                        tst = resolved.stat()
                    except OSError:
                        continue
                    if stat.S_ISREG(tst.st_mode):
                        out[f"{rel} -> target"] = _lstat_tuple(resolved, tst)
                    elif stat.S_ISDIR(tst.st_mode):
                        dkey = (tst.st_dev, tst.st_ino)
                        if dkey not in visited_dirs:
                            visited_dirs.add(dkey)
                            out[rel + "/"] = _lstat_tuple(resolved, tst)
                            _walk_dir(resolved, rel)
            elif stat.S_ISDIR(st.st_mode):
                dkey = (st.st_dev, st.st_ino)
                out[rel + "/"] = _lstat_tuple(e.path, st)
                if dkey not in visited_dirs:
                    visited_dirs.add(dkey)
                    _walk_dir(pathlib.Path(e.path), rel)
            else:
                out[rel] = _lstat_tuple(e.path, st)

    _walk_dir(root_res, "")
    return out


def _nm_cheap_sha_manifest(root: pathlib.Path, lstat_manifest: dict[str, tuple]) -> dict[str, str | None] | None:
    """只有在 node_modules 很小（<=500 檔且 <=5MB）時做一次低成本 sha256 校驗，否則回傳 None 略過。"""
    reg_entries: list[tuple[str, int]] = []
    total_bytes = 0
    for rel, tup in lstat_manifest.items():
        if len(tup) >= 2 and tup[0] == "f" and " -> " not in rel:
            reg_entries.append((rel, tup[1]))
            total_bytes += tup[1]
            if len(reg_entries) > _NM_CHEAP_SHA_MAX_FILES or total_bytes > _NM_CHEAP_SHA_MAX_BYTES:
                return None
    root_res = root.resolve()
    out: dict[str, str | None] = {}
    for rel, _ in reg_entries:
        p = root_res / rel
        try:
            # 允許透過外部 symlink 走進目標檔
            if p.is_file():
                h = hashlib.sha256()
                with p.open("rb") as f:
                    while True:
                        chunk = f.read(_CHUNK_SIZE)
                        if not chunk:
                            break
                        h.update(chunk)
                out[rel] = h.hexdigest()
            else:
                out[rel] = None
        except OSError:
            out[rel] = None
    return out


def _nm_diff(a: dict[str, tuple], b: dict[str, tuple]) -> list[str]:
    keys = set(a) | set(b)
    return sorted(k for k in keys if a.get(k) != b.get(k))


def _nm_sha_diff(a: dict[str, str | None], b: dict[str, str | None]) -> list[str]:
    keys = set(a) | set(b)
    return sorted(k for k in keys if a.get(k) != b.get(k))


def _copy_deref_tree(src_dir: pathlib.Path, dst_dir: pathlib.Path, visited: set[tuple[int, int]]) -> None:
    """將外部 symlink 目標目錄複製為真實目錄（展開內部指到外部的 symlink，附循環保護）。"""
    dst_dir.mkdir(parents=True, exist_ok=True)
    try:
        entries = list(os.scandir(src_dir))
    except OSError:
        return
    for e in entries:
        src_p = pathlib.Path(e.path)
        dst_p = dst_dir / e.name
        try:
            lst = e.stat(follow_symlinks=False)
        except OSError:
            continue
        if stat.S_ISLNK(lst.st_mode):
            try:
                tgt = src_p.resolve()
                tst = tgt.stat()
            except OSError:
                continue
            if stat.S_ISDIR(tst.st_mode):
                dkey = (tst.st_dev, tst.st_ino)
                if dkey not in visited:
                    visited.add(dkey)
                    _copy_deref_tree(tgt, dst_p, visited)
            elif stat.S_ISREG(tst.st_mode):
                try:
                    shutil.copy2(tgt, dst_p)
                except OSError:
                    pass
        elif stat.S_ISDIR(lst.st_mode):
            dkey = (lst.st_dev, lst.st_ino)
            if dkey not in visited:
                visited.add(dkey)
                _copy_deref_tree(src_p, dst_p, visited)
        elif stat.S_ISREG(lst.st_mode):
            try:
                shutil.copy2(src_p, dst_p)
            except OSError:
                pass


def _dereference_external_symlinks(nm_dst: pathlib.Path, nm_orig: pathlib.Path) -> None:
    """在 agent 的 node_modules 副本中，把任何解析目標落在副本 node_modules 之外的 symlink
    換成目標的真實副本（或移除懸空外部 symlink），防止 agent 透過 symlink 寫回原專案。"""
    dst_res = nm_dst.resolve()
    orig_res = nm_orig.resolve()
    stack: list[pathlib.Path] = [dst_res]
    while stack:
        cur = stack.pop()
        try:
            entries = list(os.scandir(cur))
        except OSError:
            continue
        for e in entries:
            p = pathlib.Path(e.path)
            try:
                st = e.stat(follow_symlinks=False)
            except OSError:
                continue
            if stat.S_ISLNK(st.st_mode):
                try:
                    raw_tgt = os.readlink(p)
                except OSError:
                    continue
                if os.path.isabs(raw_tgt):
                    resolved = pathlib.Path(raw_tgt).resolve()
                else:
                    resolved = (p.parent / raw_tgt).resolve()
                if _is_within_dir(resolved, dst_res):
                    continue
                # 目標落在副本 node_modules 之外：優先從原專案對應 symlink 解析真實來源
                rel_from_dst = p.relative_to(dst_res)
                orig_cand = orig_res / rel_from_dst
                src_target: pathlib.Path | None = None
                try:
                    if orig_cand.is_symlink() or orig_cand.exists():
                        oc_res = orig_cand.resolve()
                        if oc_res.exists():
                            src_target = oc_res
                except OSError:
                    pass
                if src_target is None and resolved.exists():
                    src_target = resolved
                try:
                    p.unlink()
                except OSError:
                    continue
                if src_target is None:
                    continue
                try:
                    tst = src_target.stat()
                except OSError:
                    continue
                if stat.S_ISDIR(tst.st_mode):
                    visited = {(tst.st_dev, tst.st_ino)}
                    _copy_deref_tree(src_target, p, visited)
                    _make_tree_writable(p)
                elif stat.S_ISREG(tst.st_mode):
                    try:
                        shutil.copy2(src_target, p)
                        os.chmod(p, stat.S_IMODE(p.lstat().st_mode) | stat.S_IWUSR)
                    except OSError:
                        pass
            elif stat.S_ISDIR(st.st_mode):
                stack.append(p)


def _find_first_reg_file(root: pathlib.Path) -> pathlib.Path | None:
    stack = [root]
    while stack:
        cur = stack.pop()
        try:
            entries = list(os.scandir(cur))
        except OSError:
            continue
        for e in entries:
            try:
                st = e.stat(follow_symlinks=False)
            except OSError:
                continue
            if stat.S_ISREG(st.st_mode):
                return pathlib.Path(e.path)
            if stat.S_ISDIR(st.st_mode) and not stat.S_ISLNK(st.st_mode):
                stack.append(pathlib.Path(e.path))
    return None


def _copy_node_modules_for_agent(project: pathlib.Path, ws: pathlib.Path) -> tuple[float, bool]:
    """給 agent 工作區一份獨立的 node_modules 副本（絕不提供指向原專案 node_modules 的可寫路徑）。
    先以單檔探測 `cp --reflink=always` 是否支援 CoW reflink，不支援時退回一般複製並回傳 fallback=True。
    複製後將任何指向副本 node_modules 外部的 symlink 展開為真實副本。
    回傳 `(複製耗時秒數, reflink_fallback)`。"""
    orig = project / "node_modules"
    dst = ws / "node_modules"
    if not orig.is_dir() or dst.exists() or dst.is_symlink():
        return 0.0, False
    src = orig.resolve()
    t0 = time.monotonic()
    copied = False
    reflink_fallback = False
    cp_bin = shutil.which("cp")
    if cp_bin:
        probe_file = _find_first_reg_file(src)
        reflink_ok = False
        if probe_file is not None:
            probe_dst = ws / f".vacant-reflink-probe-{secrets.token_hex(4)}"
            try:
                pr = subprocess.run(
                    [cp_bin, "--reflink=always", str(probe_file), str(probe_dst)],
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=10.0,
                )
                reflink_ok = (pr.returncode == 0 and probe_dst.is_file())
            except (OSError, subprocess.SubprocessError):
                reflink_ok = False
            finally:
                try:
                    probe_dst.unlink(missing_ok=True)
                except OSError:
                    pass
        else:
            reflink_ok = True  # 無一般檔案，不需警示 fallback

        if not reflink_ok:
            reflink_fallback = True
        cp_args = [cp_bin, "--reflink=always", "-a", str(src), str(dst)] if reflink_ok else [cp_bin, "-a", str(src), str(dst)]
        try:
            cp = subprocess.run(
                cp_args,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=120.0,
            )
            if cp.returncode == 0 and dst.is_dir() and not dst.is_symlink():
                copied = True
            else:
                _rmtree_force(dst)
                if reflink_ok:
                    reflink_fallback = True
        except (OSError, subprocess.SubprocessError):
            _rmtree_force(dst)
            if reflink_ok:
                reflink_fallback = True
    else:
        reflink_fallback = True
    if not copied:
        shutil.copytree(src, dst, symlinks=True)
    _dereference_external_symlinks(dst, src)
    _make_tree_writable(dst)
    return time.monotonic() - t0, reflink_fallback


def _agent_error_tail(log_dir: pathlib.Path, r: dict[str, Any], max_lines: int = 8) -> str:
    """agent 啟動即失敗時，給人看的錯誤摘要：spawn 錯誤，或 stderr（沒有就 stdout）的最後幾行。"""
    if r.get("spawn_error"):
        return _safe_str(str(r["spawn_error"]))[0][-800:]
    for name in ("agent_stderr.log", "agent_stdout.log"):
        try:
            raw = (log_dir / name).read_bytes()
        except OSError:
            continue
        txt = raw.decode("utf-8", errors="backslashreplace").strip()
        if txt:
            lines = [ln for ln in txt.splitlines() if ln.strip()]
            return "\n".join(lines[-max_lines:])[-1200:]
    return f"exit code {r.get('rc')}, no output"


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
    _raw_say = log or (lambda m: None)
    say = lambda m: _raw_say(_safe_str(m)[0])  # noqa: E731
    skip_abs = _vacant_skip_dirs()
    run_dir = work_root() / f"restart-{time.strftime('%Y%m%dT%H%M%S')}-{os.getpid()}-{secrets.token_hex(3)}"
    run_dir.mkdir(parents=True, exist_ok=True)
    run_id = run_dir.name
    attempts: list[dict] = []
    snaps: list[_Snapshot | None] = []
    launch_meta: list[tuple[list[str], dict[str, str]]] = []
    spent = 0.0
    t0 = time.monotonic()

    # P5：專案內有不可讀的檔案或目錄（chmod 000／docker 留下的 root 檔）⇒ 複製工作區前先停下、明講並寫收據（exit 43）
    unreadable_paths = _find_unreadable_paths(project, skip_abs=skip_abs)
    if unreadable_paths:
        shown_up = ", ".join(unreadable_paths[:10]) + (
            f", … (+{len(unreadable_paths) - 10} more)" if len(unreadable_paths) > 10 else ""
        )
        say(f"cannot read {len(unreadable_paths)} path(s) in the project (permission denied): "
            f"{shown_up}; stopping before running the agent")
        empty_spec = AcceptanceSpec(kind="none", command=None)
        changed = {"added": [], "modified": [], "deleted": [], "skipped": [], "conflict": []}
        res = {
            "mode": "restart",
            "project": str(project),
            "tests": [],
            "protected": [],
            "acceptance": empty_spec.to_dict(),
            "acceptance_integrity": empty_spec.integrity,
            "acceptance_integrity_reasons": list(empty_spec.integrity_reasons),
            "interpreter": empty_spec.interpreter,
            "baseline": None,
            "baseline_error": None,
            "unreadable_paths": list(unreadable_paths),
            "parent_tests_dir": None,
            "detached_processes": None if (not sys.platform.startswith("linux") or not os.path.isdir("/proc")) else [],
            "appeared_during_run": [],
            "conflicts": [],
            "write_back_conflicts": [],
            "outside_changes": [],
            "protected_outside_changes": [],
            "acceptance_dependencies_changed": [],
            "not_delivered": [],
            "lstat_listing_s": 0.0,
            "node_modules_changed": [],
            "node_modules_manifest_s": 0.0,
            "copy_s": 0.0,
            "node_modules_copy_s": 0.0,
            "node_modules_hash_s": 0.0,
            "max_attempts": max_attempts,
            "accepted": None,
            "delivered_attempt": 0,
            "attempts": [],
            "changed": changed,
            "agent_wall_s": 0.0,
            "total_wall_s": round(time.monotonic() - t0, 1),
            "run_dir": str(run_dir),
        }
        res, res_non_utf8 = _sanitize_json_obj(res)
        res["non_utf8_paths"] = res_non_utf8
        if res_non_utf8:
            res["path_encoding"] = "utf-8-backslashreplace"
        res["receipt"] = _record_receipt(
            project=project,
            prompt=prompt,
            agent=agent,
            launch_meta=launch_meta,
            spec=empty_spec,
            protected=set(),
            attempts=attempts,
            snaps=snaps,
            delivered_idx=-1,
            changed=changed,
            res=res,
            run_dir=run_dir,
        )
        if not res["receipt"].get("recorded"):
            res["receipt_error"] = res["receipt"].get("error") or "unknown receipt error"
        (run_dir / "result.json").write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
        return res

    spec = detect_acceptance(project, check=check, protect=protect)
    originals = {rel: (project / rel).read_bytes() for rel in spec.protected}
    orig_modes: dict[str, int] = {}
    for rel in spec.protected:
        try:
            orig_modes[rel] = stat.S_IMODE((project / rel).lstat().st_mode) & 0o777
        except OSError:
            pass
    protected = set(originals)
    py_tests = [rel for rel in spec.protected if _is_python_test(rel)]
    has_acceptance = spec.kind != "none" and spec.reason is None
    if not has_acceptance:
        max_attempts = 1
        attempt_timeout_s = budget_s
    parent_tests_dir = _find_parent_with_tests(project) if spec.kind == "none" else None

    # D1：原專案根目錄不可寫 ⇒ 寫回一定會失敗，跑 agent 前先停下並明講（exit 43）
    if not os.access(str(project), os.W_OK):
        say(f"project directory is not writable ({project}); write-back would fail, stopping before running the agent")
        changed = {"added": [], "modified": [], "deleted": [], "skipped": [], "conflict": []}
        res = {
            "mode": "restart",
            "project": str(project),
            "tests": py_tests if spec.kind.startswith("python_") else sorted(originals),
            "protected": sorted(protected),
            "acceptance": spec.to_dict(),
            "acceptance_integrity": spec.integrity,
            "acceptance_integrity_reasons": list(spec.integrity_reasons),
            "interpreter": spec.interpreter,
            "baseline": None,
            "baseline_error": None,
            "project_not_writable": True,
            "parent_tests_dir": str(parent_tests_dir) if parent_tests_dir is not None else None,
            "detached_processes": None if (not sys.platform.startswith("linux") or not os.path.isdir("/proc")) else [],
            "appeared_during_run": [],
            "conflicts": [],
            "write_back_conflicts": [],
            "outside_changes": [],
            "protected_outside_changes": [],
            "acceptance_dependencies_changed": [],
            "not_delivered": [],
            "lstat_listing_s": 0.0,
            "node_modules_changed": [],
            "node_modules_manifest_s": 0.0,
            "copy_s": 0.0,
            "node_modules_copy_s": 0.0,
            "node_modules_hash_s": 0.0,
            "max_attempts": max_attempts,
            "accepted": None,
            "delivered_attempt": 0,
            "attempts": [],
            "changed": changed,
            "agent_wall_s": 0.0,
            "total_wall_s": round(time.monotonic() - t0, 1),
            "run_dir": str(run_dir),
        }
        res, res_non_utf8 = _sanitize_json_obj(res)
        res["non_utf8_paths"] = res_non_utf8
        if res_non_utf8:
            res["path_encoding"] = "utf-8-backslashreplace"
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
        if not res["receipt"].get("recorded"):
            res["receipt_error"] = res["receipt"].get("error") or "unknown receipt error"
        (run_dir / "result.json").write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
        return res

    # 基線驗收：在第一次跑 agent 之前先對未動過的專案副本跑一次，確認驗收在此環境能執行
    # R2/R3：在 Linux 上於整個 run() 期間啟用 PR_SET_CHILD_SUBREAPER，使 setsid/env -i 脫離子孫
    # 全部收歸本行程底下，可列出並 SIGKILL 清理；結束時在 finally 還原。
    prev_subreaper = _set_child_subreaper(True) if _linux_proc_available() else None
    known_child_pids = _direct_children_pids() if _linux_proc_available() else set()
    detached_records: list[dict[str, Any]] | None = [] if _linux_proc_available() else None
    start_snap: _Snapshot | None = None
    start_copy: pathlib.Path | None = None

    def _reap_phase(phase: str, label: str = "") -> list[dict[str, Any]] | None:
        nonlocal detached_records
        found = _reap_detached_processes(phase, run_id, known_pids=known_child_pids)
        if found is None:
            detached_records = None
            return None
        if detached_records is not None and found:
            detached_records.extend(found)
            n_k = sum(1 for x in found if x.get("killed"))
            prefix = f"{label}: " if label else ""
            say(
                f"{prefix}WARNING: {len(found)} detached descendant process(es) detected in {phase} phase "
                f"({n_k}/{len(found)} killed; PIDs: {', '.join(str(x['pid']) for x in found)})"
            )
        return found

    try:
        baseline_rec: dict[str, Any] | None = None
        nm_root = _nm_root(project)
        nm_start: dict[str, tuple] | None = None
        nm_sha_start: dict[str, str | None] | None = None
        nm_changed: list[str] = []
        nm_copy_s = 0.0
        copy_s = 0.0
        nm_manifest_s = 0.0
        nm_hash_s = 0.0
        nm_reflink_fallback = False
        nm_reflink_warned = False
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
            base_acc = acceptance(
                originals, project, base_t, spec=spec, _project=project,
                _orig_modes=orig_modes, _run_id=run_id,
            )
            _reap_phase("acceptance", "baseline")
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
            _reap_phase("end")
            say(f"baseline: acceptance cannot run in this environment: {baseline_error}")
            changed = {"added": [], "modified": [], "deleted": [], "skipped": [], "conflict": []}
            res = {
                "mode": "restart",
                "project": str(project),
                "tests": py_tests if spec.kind.startswith("python_") else sorted(originals),
                "protected": sorted(protected),
                "acceptance": spec.to_dict(),
                "acceptance_integrity": spec.integrity,
                "acceptance_integrity_reasons": list(spec.integrity_reasons),
                "interpreter": spec.interpreter,
                "baseline": baseline_rec,
                "baseline_error": baseline_error,
                "parent_tests_dir": str(parent_tests_dir) if parent_tests_dir is not None else None,
                "node_modules_changed": [],
                "node_modules_manifest_s": 0.0,
                "copy_s": 0.0,
                "node_modules_copy_s": 0.0,
                "node_modules_hash_s": 0.0,
                "appeared_during_run": [],
                "conflicts": [],
                "write_back_conflicts": [],
                "outside_changes": [],
                "protected_outside_changes": [],
                "detached_processes": detached_records,
                "acceptance_dependencies_changed": [],
                "not_delivered": [],
                "lstat_listing_s": 0.0,
                "max_attempts": max_attempts,
                "accepted": None,
                "delivered_attempt": 0,
                "attempts": [],
                "changed": changed,
                "agent_wall_s": 0.0,
                "total_wall_s": round(time.monotonic() - t0, 1),
                "run_dir": str(run_dir),
            }
            res, res_non_utf8 = _sanitize_json_obj(res)
            res["non_utf8_paths"] = res_non_utf8
            if res_non_utf8:
                res["path_encoding"] = "utf-8-backslashreplace"
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
            if not res["receipt"].get("recorded"):
                res["receipt_error"] = res["receipt"].get("error") or "unknown receipt error"
            (run_dir / "result.json").write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
            return res

        reserve = min(ACC_TIMEOUT_S, budget_s / 10) if has_acceptance else 0.0   # 每次嘗試後留給驗收的時間
        agent_error: str | None = None
        # 開始時的原專案快照（R11：驗收與各輪工作區皆從開始狀態出發，不讀 live 專案）與純 lstat 清單（B1）
        start_snap = _snapshot_workspace(project, run_dir / f"start-snap-{secrets.token_hex(6)}", skip_abs=skip_abs)
        start_copy = run_dir / f"start-copy-{secrets.token_hex(6)}"
        shutil.copytree(project, start_copy, symlinks=True, ignore=_copytree_ignore(skip_abs))
        start_hashes = start_snap.files
        start_unsafe = (
            start_snap.symlinks | start_snap.unreadable_dirs | start_snap.unreadable_files | start_snap.special_files
        )
        lstat_listing_s = 0.0
        t_ls = time.monotonic()
        orig_lstat_start = _project_lstat_listing(project, skip_abs=skip_abs, skip_root_nm=(nm_root is not None))
        lstat_listing_s += time.monotonic() - t_ls
        # 開始時的 node_modules lstat 清單（含外部 symlink 目標；很小時另做一次低成本 sha256 校驗）
        if nm_root is not None:
            t_nm = time.monotonic()
            nm_start = _nm_manifest(nm_root)
            nm_manifest_s += time.monotonic() - t_nm
            t_sh = time.monotonic()
            nm_sha_start = _nm_cheap_sha_manifest(nm_root, nm_start)
            nm_hash_s += time.monotonic() - t_sh
        while len(attempts) < max_attempts:
            remaining = budget_s - (time.monotonic() - t0) - reserve
            if attempts and remaining < min_attempt_s:
                break
            remaining = max(remaining, min(0.1, budget_s))
            k = len(attempts) + 1
            attempt_dir = run_dir / f"attempt_{k}"
            ws = attempt_dir / "w"
            t_cp = time.monotonic()
            shutil.copytree(start_copy, ws, symlinks=True)
            _make_tree_writable(ws)
            nm_c_s, fb = _copy_node_modules_for_agent(project, ws)
            nm_copy_s += nm_c_s
            copy_s += time.monotonic() - t_cp
            if fb:
                nm_reflink_fallback = True
                if not nm_reflink_warned:
                    nm_reflink_warned = True
                    say("warning: node_modules reflink copy is not supported on this filesystem; fell back to plain copy")
            launch = build(prompt, ws)
            launch_meta.append((list(launch.argv), dict(launch.env)))
            attempt_launch = dataclasses.replace(launch, env={**launch.env, _DETACHED_MARKER_ENV: run_id})
            attempt_limit_s = min(attempt_timeout_s, remaining)
            say(f"attempt {k} of {max_attempts} (up to {attempt_limit_s:.0f}s)")
            # 不再對原專案 node_modules 做 chmod（agent 拿到的是自己的副本，原專案完整性由清單比對保障）。
            try:
                r = run_agent(attempt_launch, workspace=ws, timeout_s=min(attempt_timeout_s, remaining),
                              log_dir=attempt_dir / "logs")
            finally:
                if launch.cleanup:
                    launch.cleanup()
            spent += r["wall_ms"] / 1000.0
            # R2：agent 結束後、快照與驗收開始前立刻掃描並 SIGKILL 脫離子孫，避免它們在驗收途中改工作區
            agent_detached = _reap_phase("agent", f"attempt {k}")
            stderr_tail = _agent_error_tail(attempt_dir / "logs", r, max_lines=5) if r["rc"] not in (0, None) else None
            if nm_start is not None:
                t_nm = time.monotonic()
                nm_cur = _nm_manifest(nm_root)
                nm_changed = _nm_diff(nm_start, nm_cur)
                nm_manifest_s += time.monotonic() - t_nm
                if not nm_changed and nm_sha_start is not None:
                    t_sh = time.monotonic()
                    nm_sha_cur = _nm_cheap_sha_manifest(nm_root, nm_cur)
                    if nm_sha_cur is not None:
                        nm_changed = _nm_sha_diff(nm_sha_start, nm_sha_cur)
                    nm_hash_s += time.monotonic() - t_sh
                if nm_changed:
                    say(f"attempt {k}: the agent changed the project's node_modules ({len(nm_changed)} path(s), e.g. "
                        f"{', '.join(nm_changed[:3])}); not accepted, stopping, nothing written back")
                    attempts.append({
                        "attempt": k, "accept": False, "passed": None, "run": None,
                        "status": "node_modules_modified", "acceptance_kind": spec.kind, "tests_tampered": [],
                        "config_ignored": [], "first_problem": "node_modules changed: " + ", ".join(nm_changed[:20]),
                        "rc": r["rc"], "timed_out": r["timed_out"], "wall_s": round(r["wall_ms"] / 1000.0, 1),
                        "spawn_error": r["spawn_error"], "workspace": str(ws), "node_modules_changed": nm_changed[:200],
                        "detached_processes": agent_detached,
                        **({"agent_stderr_tail": stderr_tail} if stderr_tail else {}),
                    })
                    snaps.append(None)
                    break

            snap: _Snapshot | None = None
            plan: _WritePlan | None = None
            acc_detached: list[dict[str, Any]] | None = [] if _linux_proc_available() else None
            try:
                snap_dir = attempt_dir / f"snap-{secrets.token_hex(8)}"
                snap = _snapshot_workspace(
                    ws, snap_dir, skip_abs=skip_abs, record_copy_skip=True, had_root_nm=(nm_root is not None)
                )
                # R11：驗收階段一律以開始快照為基準規劃本輪改動（排除開始時就不安全的路徑如 symlink），
                # 使驗收永遠只測試「開始狀態＋本輪嘗試改動」，不受 live 專案並發改動或逃逸寫入影響。
                plan = _plan_write_back(
                    start_snap.root, snap, protected, start_hashes=start_hashes,
                    ignore_new=spec.should_ignore_new_file,
                    ignore_new_reason=spec.ignored_new_file_reason,
                )
                if start_unsafe:
                    blocked_add = [r for r in plan.added if _matches_prefix(r, start_unsafe)]
                    blocked_mod = [r for r in plan.modified if _matches_prefix(r, start_unsafe)]
                    blocked_del = [r for r in plan.deleted if _matches_prefix(r, start_unsafe)]
                    if blocked_add or blocked_mod or blocked_del:
                        blk = set(blocked_add) | set(blocked_mod) | set(blocked_del)
                        plan.added = [r for r in plan.added if r not in blk]
                        plan.modified = [r for r in plan.modified if r not in blk]
                        plan.deleted = [r for r in plan.deleted if r not in blk]
                        plan.skipped = sorted(set(plan.skipped) | blk)
                if has_acceptance:
                    acc_t = max(0.0, min(ACC_TIMEOUT_S, budget_s - (time.monotonic() - t0)))
                    acc = acceptance(
                        originals, ws, acc_t, spec=spec, _snapshot=snap, _project=project,
                        _plan=plan, _orig_modes=orig_modes, _start_snap=start_snap, _run_id=run_id,
                    )
                    acc_detached = _reap_phase("acceptance", f"attempt {k} acceptance")
                    if nm_start is not None:
                        t_nm = time.monotonic()
                        nm_cur = _nm_manifest(nm_root)
                        nm_changed = _nm_diff(nm_start, nm_cur)
                        nm_manifest_s += time.monotonic() - t_nm
                        if not nm_changed and nm_sha_start is not None:
                            t_sh = time.monotonic()
                            nm_sha_cur = _nm_cheap_sha_manifest(nm_root, nm_cur)
                            if nm_sha_cur is not None:
                                nm_changed = _nm_sha_diff(nm_sha_start, nm_sha_cur)
                            nm_hash_s += time.monotonic() - t_sh
                        if nm_changed:
                            acc = {**acc, "accept": False, "status": "node_modules_modified",
                                   "first_problem": "node_modules changed during acceptance: " + ", ".join(nm_changed[:20])}
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
                acc_detached = _reap_phase("acceptance", f"attempt {k} acceptance")
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

            if agent_detached is None or acc_detached is None:
                att_detached: list[dict[str, Any]] | None = None
            else:
                att_detached = list(agent_detached) + list(acc_detached)

            attempts.append({
                "attempt": k,
                "accept": acc["accept"],
                "passed": acc["passed"],
                "run": acc["run"],
                "status": acc["status"],
                "acceptance_kind": spec.kind,
                "tests_tampered": acc["tests_tampered"],
                "config_ignored": list(plan.config_ignored) if plan is not None else [],
                **({"config_ignored_reasons": dict(plan.config_ignored_reasons)} if (plan is not None and plan.config_ignored_reasons) else {}),
                "first_problem": acc.get("first_problem"),
                "rc": r["rc"],
                "timed_out": r["timed_out"],
                "time_limit_s": round(attempt_limit_s, 1),
                "wall_s": round(r["wall_ms"] / 1000.0, 1),
                "spawn_error": r["spawn_error"],
                "workspace": str(ws),
                "detached_processes": att_detached,
                **({"agent_stderr_tail": stderr_tail} if stderr_tail else {}),
            })
            snaps.append(snap)

            if acc["accept"] is None:
                say(f"attempt {k}: not checked ({acc['status']})")
            elif acc["run"] is not None:
                say(f"attempt {k}: {spec.kind} {'PASS' if acc['accept'] else 'FAIL'} ({acc['passed']}/{acc['run']})")
            else:
                say(f"attempt {k}: {spec.kind} {'PASS' if acc['accept'] else 'FAIL'} (status={acc['status']})")

            if nm_changed:
                attempts[-1]["node_modules_changed"] = nm_changed[:200]
                say(f"attempt {k}: node_modules changed during the check; not accepted, stopping, nothing written back")
                break
            if acc["accept"] is None or acc["accept"] is True:
                break
            # agent 一啟動就失敗（找不到執行檔、版本不合當場崩潰、沒設定模型就退出）：重開也只會一樣，
            # 停下來把 agent 自己的錯誤講出來，而不是靜靜燒完剩下的嘗試。
            quick_fail = (r["spawn_error"] is not None
                          or (r["rc"] not in (0, None) and not r["timed_out"]
                              and r["wall_ms"] < AGENT_QUICK_FAIL_MS))
            untouched = plan is not None and not (plan.added or plan.modified or plan.deleted)
            if quick_fail and untouched:
                agent_error = _agent_error_tail(attempt_dir / "logs", r)
                attempts[-1]["agent_failed_to_start"] = True
                say(f"attempt {k}: the agent exited with an error after {r['wall_ms'] / 1000.0:.1f}s without "
                    f"changing anything; not restarting. agent said: {agent_error.splitlines()[-1] if agent_error else '(nothing)'}")
                break

        if nm_start is not None and not nm_changed:
            t_nm = time.monotonic()
            nm_cur = _nm_manifest(nm_root)
            nm_changed = _nm_diff(nm_start, nm_cur)
            nm_manifest_s += time.monotonic() - t_nm
            if not nm_changed and nm_sha_start is not None:
                t_sh = time.monotonic()
                nm_sha_cur = _nm_cheap_sha_manifest(nm_root, nm_cur)
                if nm_sha_cur is not None:
                    nm_changed = _nm_sha_diff(nm_sha_start, nm_sha_cur)
                nm_hash_s += time.monotonic() - t_sh
            if nm_changed and attempts:
                attempts[-1]["accept"] = False
                attempts[-1]["status"] = "node_modules_modified"
                attempts[-1]["node_modules_changed"] = nm_changed[:200]

        d = deliver_index([{"accept": bool(a["accept"]), "passed": a["passed"]} for a in attempts])
        if nm_changed:
            d = len(attempts) - 1
        appeared_during_run: list[str] = []
        conflicts: list[str] = []
        write_back_conflicts: list[str] = []
        outside_changes: list[str] = []
        if snaps[d] is not None and not nm_changed:
            t_ls = time.monotonic()
            orig_lstat_before_wb = _project_lstat_listing(project, skip_abs=skip_abs, skip_root_nm=(nm_root is not None))
            lstat_listing_s += time.monotonic() - t_ls
            final_plan = _plan_write_back(
                project, snaps[d], protected, start_hashes=start_hashes,
                ignore_new=spec.should_ignore_new_file,
                ignore_new_reason=spec.ignored_new_file_reason,
            )
            appeared_during_run = list(final_plan.appeared)
            attempt_writes = (
                set(final_plan.added) | set(final_plan.modified) | set(final_plan.deleted) | set(final_plan.conflicts)
            )
            lstat_live_diff = {
                k for k in (set(orig_lstat_start) | set(orig_lstat_before_wb))
                if orig_lstat_start.get(k) != orig_lstat_before_wb.get(k)
            }
            live_changed_paths = lstat_live_diff | set(final_plan.conflicts) | set(final_plan.appeared)
            overlap = sorted(set(final_plan.conflicts) | (attempt_writes & live_changed_paths))
            if overlap:
                # R11(b)：交件寫回路徑與執行期間原專案異動重疊 ⇒ 什麼都不寫回（無部分交件），exit 43
                write_back_conflicts = list(overlap)
                conflicts = list(overlap)
                changed = {"added": [], "modified": [], "deleted": [], "skipped": [], "conflict": list(overlap)}
                outside_changes = sorted(live_changed_paths)
            else:
                # R11(a)：無重疊 ⇒ 照常寫回（並於 _apply_write_plan 內做 TOCTOU 複檢）
                changed = _write_back(
                    project, snaps[d], protected, _plan=final_plan, _backup_root=run_dir, start_hashes=start_hashes
                )
                if changed.get("conflict"):
                    write_back_conflicts = list(changed["conflict"])
                    conflicts = list(changed["conflict"])
                t_ls = time.monotonic()
                orig_lstat_end = _project_lstat_listing(project, skip_abs=skip_abs, skip_root_nm=(nm_root is not None))
                lstat_listing_s += time.monotonic() - t_ls
                written_paths = set(changed["added"]) | set(changed["modified"]) | set(changed["deleted"])
                outside_changes = sorted(
                    k for k in (set(orig_lstat_start) | set(orig_lstat_end) | set(appeared_during_run))
                    if (orig_lstat_start.get(k) != orig_lstat_end.get(k) or k in appeared_during_run)
                    and k not in written_paths
                )
        else:
            changed = {"added": [], "modified": [], "deleted": [], "skipped": [], "conflict": []}
            # 仍檢查並發出現的檔案與 B1 異動（如 node_modules 異常中止時）
            live_now, _ = _scan_files(project, skip_abs=skip_abs)
            appeared_during_run = sorted(
                rel for rel in (set(live_now) - set(start_hashes) - protected) if not _has_copy_skip(rel)
            )
            t_ls = time.monotonic()
            orig_lstat_end = _project_lstat_listing(project, skip_abs=skip_abs, skip_root_nm=(nm_root is not None))
            lstat_listing_s += time.monotonic() - t_ls
            outside_changes = sorted(
                k for k in (set(orig_lstat_start) | set(orig_lstat_end) | set(appeared_during_run))
                if (orig_lstat_start.get(k) != orig_lstat_end.get(k) or k in appeared_during_run)
            )

        protected_outside_changes = sorted(p for p in outside_changes if p in protected)

        # R2/R3：結束前最後再清一次任何殘留脫離子孫
        _reap_phase("end")

        # A1/A2/R6：標記交件嘗試所改動、且驗收依賴的檔案（字串常值、2 層遞移匯入、fixture/mock/data 目錄）
        planned_paths = set(changed["added"]) | set(changed["modified"]) | set(changed["deleted"])
        known_files = set(start_hashes) | planned_paths
        dep_src_root = snaps[d].root if (0 <= d < len(snaps) and snaps[d] is not None) else project
        acc_deps_changed = _find_acceptance_dependencies(
            originals, known_files, planned_paths, source_root=dep_src_root,
            extra_unfixed=spec.unfixed_deps,
            start_files=set(start_hashes),
        )
        not_delivered = list(snaps[d].copy_skip_created) if (0 <= d < len(snaps) and snaps[d] is not None) else []

        only_uncheckable = len(attempts) == 1 and attempts[0]["accept"] is None
        res = {
            "mode": "restart",
            "project": str(project),
            "tests": py_tests if spec.kind.startswith("python_") else sorted(originals),
            "protected": sorted(protected),
            "acceptance": spec.to_dict(),
            "acceptance_integrity": spec.integrity,
            "acceptance_integrity_reasons": list(spec.integrity_reasons),
            "interpreter": spec.interpreter,
            "baseline": baseline_rec,
            "baseline_error": None,
            "agent_error": agent_error,
            "parent_tests_dir": str(parent_tests_dir) if parent_tests_dir is not None else None,
            "node_modules_changed": nm_changed[:200],
            "node_modules_manifest_s": round(nm_manifest_s, 3),
            "copy_s": round(copy_s, 3),
            "node_modules_copy_s": round(nm_copy_s, 3),
            "node_modules_hash_s": round(nm_hash_s, 3),
            "node_modules_reflink_fallback": nm_reflink_fallback,
            "appeared_during_run": appeared_during_run,
            "conflicts": conflicts,
            "write_back_conflicts": write_back_conflicts,
            "outside_changes": outside_changes,
            "protected_outside_changes": protected_outside_changes,
            "lstat_listing_s": round(lstat_listing_s, 3),
            "detached_processes": detached_records,
            "acceptance_dependencies_changed": acc_deps_changed,
            "not_delivered": not_delivered,
            "max_attempts": max_attempts,
            "accepted": None if only_uncheckable else bool(attempts[d]["accept"]),
            "delivered_attempt": d + 1,
            "attempts": attempts,
            "changed": changed,
            "agent_wall_s": round(spent, 1),
            "total_wall_s": round(time.monotonic() - t0, 1),
            "run_dir": str(run_dir),
        }
        raw_changed = changed
        res, res_non_utf8 = _sanitize_json_obj(res)
        res["non_utf8_paths"] = res_non_utf8
        if res_non_utf8:
            res["path_encoding"] = "utf-8-backslashreplace"
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
            changed=raw_changed,
            res=res,
            run_dir=run_dir,
        )
        if not res["receipt"].get("recorded"):
            res["receipt_error"] = res["receipt"].get("error") or "unknown receipt error"
        (run_dir / "result.json").write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
        return res
    finally:
        if start_snap is not None:
            _rmtree_force(start_snap.root)
        if start_copy is not None:
            _rmtree_force(start_copy)
        if prev_subreaper is not None:
            _set_child_subreaper(bool(prev_subreaper))


def _time_limit_notice(res: dict) -> str:
    """rc5：嘗試被單次時限切斷時講出來（只改訊息，不改政策）。

    推論慢的機器上，一次嘗試可能連一輪「改→測→改」都做不完；重開也一樣撞上限，這時重開沒有意義。
    使用者唯一看得到這件事的地方是交件訊息，所以每一次被切斷都列出來；全部被切斷時明講該調時限。
    """
    atts = [a for a in (res.get("attempts") or []) if isinstance(a, dict)]
    cut = [a for a in atts if a.get("timed_out")]
    if not cut:
        return ""
    lines = []
    for a in cut:
        lim = a.get("time_limit_s")
        lim_txt = f"{lim:.0f}s" if isinstance(lim, (int, float)) else "its"
        lines.append(f"\n  attempt {a.get('attempt')} was cut off at the {lim_txt} time limit "
                     f"(ran {a.get('wall_s')}s; its result is whatever the agent had written by then)")
    if len(cut) == len(atts) and res.get("accepted") is not True:
        lines.append("\n  every attempt hit the time limit: this looks like too little time rather than wrong work. "
                     "Restarting cannot help if one attempt cannot finish; raise --attempt-timeout (per attempt) "
                     "and --timeout (total), e.g. --attempt-timeout 1800 --timeout 1800 for a single long run.")
    return "".join(lines)


def _short_integrity_code(reason: str) -> str:
    """Convert a full acceptance_integrity_reasons string into a short, readable tag code."""
    s = reason.strip()
    if not s:
        return "untraced"
    if "imports project modules" in s:
        return "script-imports-project-modules"
    m = re.search(r"unknown command:\s*(\S+)", s)
    if m:
        return f"unknown-command:{m.group(1)}"
    if "shell output redirection" in s or "shell input redirection" in s:
        return "shell-redirection"
    if "here-doc" in s or "here-string" in s:
        return "shell-heredoc"
    if "process substitution" in s:
        return "process-substitution"
    if "shell expansion" in s:
        return "shell-expansion"
    if "unquoted shell globbing" in s:
        return "shell-glob"
    if "subshell or function syntax" in s:
        return "shell-subshell"
    m = re.search(r"shell control-flow construct:\s*(\S+)", s)
    if m:
        return f"shell-control-flow:{m.group(1)}"
    m = re.search(r"unsupported (\S+) option:\s*(\S+)", s)
    if m:
        return f"unsupported-option:{m.group(1)}:{m.group(2)}"
    m = re.match(r"make target '([^']+)' is not \.PHONY", s)
    if m:
        return f"make-non-phony:{m.group(1)}"
    if ".DEFAULT_GOAL" in s:
        return "make-default-goal"
    m = re.search(r"Makefile uses untraceable directive \(([^)]+)\)", s)
    if m:
        return f"make-directive:{m.group(1)}"
    if "$(shell" in s:
        return "make-shell-func"
    if "double-colon rule" in s:
        return "make-double-colon"
    if "pattern/variable target" in s:
        return "make-pattern-target"
    if "!= shell assignment" in s:
        return "make-shell-assign"
    if "untraceable prerequisite" in s:
        return "make-untraced-prereq"
    if "make variable override" in s:
        return "make-var-override"
    if "uses variable/shell expansion" in s:
        return "make-recipe-expansion"
    m = re.search(r"uses process execution:\s*([^,\s]+)", s)
    if m:
        return f"py-exec:{m.group(1)}"
    if s == "dynamic-import" or s.startswith("dynamic-import:"):
        return "dynamic-import"
    m = re.search(r"uses dynamic code:\s*([^,\s]+)", s)
    if m:
        return f"py-dynamic:{m.group(1)}"
    if "uses open() with non-constant path" in s:
        return "py-open-dynamic"
    if "uses open() of unprotected path" in s:
        return "py-open-unprotected"
    if "uses open() of outside path" in s:
        return "py-open-outside"
    m = re.search(r"uses pathlib\.(\w+)\(\)", s)
    if m:
        return f"py-pathlib:{m.group(1)}"
    m = re.search(r"requires/imports\s+([^,\s]+)", s)
    if m:
        return f"js-require:{m.group(1)}"
    if "uses non-literal require()" in s or "non-literal require()" in s:
        return "js-dynamic-require"
    if "uses dynamic import()" in s or "dynamic import()" in s:
        return "js-dynamic-import"
    if "uses process.binding" in s:
        return "js-process-binding"
    if "uses eval()" in s:
        return "js-eval"
    if "uses new Function" in s:
        return "js-new-function"
    if "<rootDir>" in s or "unresolvable config path" in s or "non-literal path" in s or "runner config" in s or "--config" in s:
        return "runner-config-untraced"
    if "uses --require" in s:
        return "runner-require"
    if "loads local plugin" in s:
        return "runner-plugin"
    if s == "no project files kept fixed":
        return "no-fixed-files"
    if "node inline code" in s:
        return "node-inline"
    if "node preload option" in s:
        return "node-preload"
    m = re.search(r"env assignment alters runtime resolution:\s*(\S+)", s)
    if m:
        return f"env-override:{m.group(1)}"
    if "python -m module cannot be resolved" in s:
        return "py-module-untraced"
    slug = re.sub(r"[^a-z0-9:._-]+", "-", s.lower()).strip("-")
    return slug[:36] or "untraced"


def summary(res: dict) -> str:
    res, _ = _sanitize_json_obj(res)
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

    if res.get("project_not_writable"):
        head = (
            f"[vacant] project directory is not writable ({res.get('project')}); "
            f"write-back would fail, so nothing was run and the project is unchanged."
        )
    elif res.get("unreadable_paths"):
        up = list(res["unreadable_paths"])
        shown_up = ", ".join(up[:10]) + (f", … (+{len(up) - 10} more)" if len(up) > 10 else "")
        head = (
            f"[vacant] cannot read {len(up)} path(s) in the project (permission denied): "
            f"{shown_up}; fix the permissions or move them out of the project. Nothing was run."
        )
    elif baseline_err:
        reason_txt = str(baseline_err).strip()
        head = (
            f"[vacant] acceptance cannot run in this environment: {reason_txt}\n"
            f"  stopped before running the agent (0 attempts); project unchanged."
        )
    elif res.get("node_modules_changed"):
        nmc = res["node_modules_changed"]
        head = (f"[vacant] the agent changed the project's node_modules during attempt {len(res['attempts'])} "
                f"({len(nmc)} path(s): {', '.join(nmc[:8])}{' …' if len(nmc) > 8 else ''}). That attempt was not "
                f"accepted, the run stopped, and nothing was written back. node_modules is NOT restored: "
                f"reinstall it (e.g. `npm ci`) before trusting it again.")
    elif res.get("write_back_conflicts"):
        wbc = list(res["write_back_conflicts"])
        shown_wbc = ", ".join(wbc[:10]) + (f" … (+{len(wbc) - 10} more)" if len(wbc) > 10 else "")
        d_idx = (res.get("delivered_attempt") or 1) - 1
        d_att = res["attempts"][d_idx] if (res.get("attempts") and 0 <= d_idx < len(res["attempts"])) else {}
        ws_dir = d_att.get("workspace") or res.get("run_dir")
        acc_tag = "accepted" if res.get("accepted") is True else ("not accepted" if res.get("accepted") is False else "unchecked")
        head = (
            f"[vacant] write-back stopped due to overlapping changes in your project during the run "
            f"({len(wbc)} path(s): {shown_wbc}); nothing was written back (no partial delivery).\n"
            f"  the delivered ({acc_tag}) attempt's files are kept at: {ws_dir} (merge by hand)."
        )
    elif res.get("agent_error"):
        a = res["attempts"][-1] if res.get("attempts") else {}
        tail = "\n".join("    " + ln for ln in str(res["agent_error"]).splitlines())
        head = (
            f"[vacant] the agent failed on attempt {a.get('attempt', n)} (exit code {a.get('rc')}, "
            f"{a.get('wall_s')}s) without changing anything, so it was not restarted. {files}.\n"
            f"  the agent's last output:\n{tail}"
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

    head += _time_limit_notice(res)
    acc_integrity = res.get("acceptance_integrity")
    if acc_integrity is None:
        acc_integrity = acc_info.get("integrity")
    acc_integrity_reasons = list(
        res.get("acceptance_integrity_reasons")
        or acc_info.get("integrity_reasons")
        or ()
    )
    cmd_part = f" ({acc_cmd})" if acc_cmd else ""
    if acc_integrity in ("untraced", "unverified"):
        codes: list[str] = []
        for r in acc_integrity_reasons:
            c = _short_integrity_code(str(r))
            if c not in codes:
                codes.append(c)
        if codes:
            shown_codes = ", ".join(codes[:3]) + (f", +{len(codes) - 3}" if len(codes) > 3 else "")
            head += f"\n  acceptance: {acc_kind}{cmd_part} — inputs not fully traced [{shown_codes}]"
        else:
            head += f"\n  acceptance: {acc_kind}{cmd_part} — inputs not fully traced"
    else:
        head += f"\n  acceptance: {acc_kind}{cmd_part}"
    if acc_info.get("shell_expansion"):
        head += "\n  warning: the check command uses shell expansion; Vacant could not see which files it runs"
    if res.get("project"):
        head += f"\n  scanned: {res['project']} (parent directories were not scanned)"
    if res.get("parent_tests_dir"):
        head += f"\n  tests found in {res['parent_tests_dir']}; run from there to check them"
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
        head += f"\n  kept fixed (restored to their start content before each check): {shown}"
    else:
        head += "\n  kept fixed (restored to their start content before each check): none"
    deliv_changed = (
        [f"+{p}" for p in (ch.get("added") or ())]
        + [f"~{p}" for p in (ch.get("modified") or ())]
        + [f"-{p}" for p in (ch.get("deleted") or ())]
    )
    if deliv_changed:
        shown_dc = ", ".join(deliv_changed[:10]) + (
            f" (+{len(deliv_changed) - 10} more)" if len(deliv_changed) > 10 else ""
        )
        head += f"\n  changed files: {shown_dc}"
    if ch.get("skipped"):
        head += (f"\n  not written back ({len(ch['skipped'])}): unsafe path (symlink, conflict, or unreadable) "
                 f"({', '.join(ch['skipped'][:5])}{' …' if len(ch['skipped']) > 5 else ''}); see the attempt workspace.")
    conflicts_list = list(res.get("write_back_conflicts") or res.get("conflicts") or ch.get("conflict") or ())
    if conflicts_list and not res.get("write_back_conflicts"):
        shown_c = ", ".join(conflicts_list[:10]) + (f" … (+{len(conflicts_list) - 10} more)" if len(conflicts_list) > 10 else "")
        head += f"\n  conflicting paths (skipped during write-back): {shown_c}"
    outside_list = list(res.get("outside_changes") or ())
    if outside_list:
        shown_o = ", ".join(outside_list[:10]) + (f" … (+{len(outside_list) - 10} more)" if len(outside_list) > 10 else "")
        head += f"\n  your project changed during the run, not by this delivery: {shown_o} — not checked and not touched"
        prot_set = set(protected)
        prot_outside = list(res.get("protected_outside_changes") or [p for p in outside_list if p in prot_set])
        if prot_outside:
            shown_po = ", ".join(prot_outside[:10]) + (f" … (+{len(prot_outside) - 10} more)" if len(prot_outside) > 10 else "")
            head += f"\n  a kept-fixed test/config file changed in your project during the run: {shown_po}"
        git_hooks = [
            p for p in outside_list
            if p == ".git/hooks" or p.startswith(".git/hooks/") or "/.git/hooks/" in p
        ]
        if git_hooks:
            shown_h = ", ".join(git_hooks[:10]) + (f" … (+{len(git_hooks) - 10} more)" if len(git_hooks) > 10 else "")
            head += (f"\n  WARNING: .git/hooks was added or changed outside the delivered attempt "
                     f"({shown_h}) — inspect before running git commands!")
        git_refs = [
            p for p in outside_list
            if (p == ".git/refs" or p.startswith(".git/refs/") or "/.git/refs/" in p
                or p == ".git/HEAD" or p.startswith(".git/HEAD") or "/.git/HEAD" in p
                or p == ".git/packed-refs" or p.endswith("/.git/packed-refs"))
        ]
        if git_refs:
            shown_r = ", ".join(git_refs[:10]) + (f" … (+{len(git_refs) - 10} more)" if len(git_refs) > 10 else "")
            head += (f"\n  WARNING: git refs/HEAD changed outside the delivered attempt "
                     f"({shown_r}) — inspect before running git commands!")
        git_objects = [
            p for p in outside_list
            if p == ".git/objects" or p.startswith(".git/objects/") or "/.git/objects/" in p
        ]
        if git_objects:
            shown_go = ", ".join(git_objects[:10]) + (f" … (+{len(git_objects) - 10} more)" if len(git_objects) > 10 else "")
            head += (f"\n  WARNING: .git/objects was added, changed, or deleted outside the delivered attempt "
                     f"({shown_go}) — inspect repository integrity (e.g. `git fsck`) before trusting git!")
        venv_pths = [
            p for p in outside_list
            if p.endswith(".pth") and ".venv" in pathlib.PurePosixPath(p).parts[:-1]
        ]
        if venv_pths:
            shown_v = ", ".join(venv_pths[:10]) + (f" … (+{len(venv_pths) - 10} more)" if len(venv_pths) > 10 else "")
            head += (f"\n  WARNING: .pth file under .venv was added or changed outside the delivered attempt "
                     f"({shown_v}) — executes code at Python startup!")
    not_deliv = list(res.get("not_delivered") or ())
    if not_deliv:
        def _fmt_nd(item: Any) -> str:
            if isinstance(item, dict):
                return f"{item.get('path')} ({item.get('reason')})"
            return str(item)
        shown_nd = ", ".join(_fmt_nd(x) for x in not_deliv[:10]) + (
            f" … (+{len(not_deliv) - 10} more)" if len(not_deliv) > 10 else ""
        )
        head += f"\n  not delivered ({len(not_deliv)}): {shown_nd}"
    cfg_new = sorted({t for a in res["attempts"] for t in (a.get("config_ignored") or [])})
    if cfg_new:
        cfg_reasons: dict[str, str] = {}
        for a in res["attempts"]:
            for k_p, v_r in (a.get("config_ignored_reasons") or {}).items():
                if k_p not in cfg_reasons and v_r:
                    cfg_reasons[k_p] = str(v_r)
        def _fmt_cfg(p: str) -> str:
            why = cfg_reasons.get(p)
            return f"{p} ({why})" if why else p
        d_att = res["attempts"][res["delivered_attempt"] - 1] if res.get("attempts") else {}
        where = next((a.get("workspace") for a in ([d_att] + list(res["attempts"]))
                      if a.get("config_ignored") and a.get("workspace")), None)
        head += (f"\n  the agent added test configuration ({', '.join(_fmt_cfg(p) for p in cfg_new[:10])}"
                 f"{' …' if len(cfg_new) > 10 else ''}); not used for the check and not written back"
                 + (f" — still in the attempt workspace: {where}" if where else "") + ".")
    tam = sorted({t for a in res["attempts"] for t in a["tests_tampered"]})
    if tam:
        if all(_is_universal_test(t) or _is_test_config(t) for t in tam):
            head += f"\n  the agent edited test files ({', '.join(tam)}); checked against the originals, not written back."
        else:
            head += f"\n  the agent edited kept-fixed files ({', '.join(tam)}); checked against the originals, not written back."
    if (not res.get("project_not_writable") and not res.get("unreadable_paths")
            and not baseline_err and not res.get("node_modules_changed")
            and not res.get("agent_error") and res.get("attempts") and res.get("delivered_attempt")):
        d_att = res["attempts"][res["delivered_attempt"] - 1]
        if d_att.get("rc") not in (0, None):
            head += (f"\n  warning: the agent exited with code {d_att.get('rc')} on delivered attempt "
                     f"{res['delivered_attempt']}")
            stail = d_att.get("agent_stderr_tail")
            if stail:
                tail_fmt = "\n".join("    " + ln for ln in str(stail).splitlines()[-5:])
                head += f"\n  the agent's last output:\n{tail_fmt}"
    dep_changed = list(res.get("acceptance_dependencies_changed") or ())
    if dep_changed:
        def _fmt_dep(item: Any) -> str:
            if isinstance(item, dict):
                rs = ", ".join(str(r) for r in (item.get("reasons") or ()))
                return f"{item.get('path')} ({rs})" if rs else str(item.get("path"))
            return str(item)
        shown_dep = ", ".join(_fmt_dep(x) for x in dep_changed[:20]) + (
            f" … (+{len(dep_changed) - 20} more)" if len(dep_changed) > 20 else ""
        )
        head += (
            f"\n  NOTE: the delivered attempt changed files the check reads or runs "
            f"that were not kept fixed: {shown_dep}"
        )
    det_items = res.get("detached_processes")
    if "detached_processes" in res and det_items is None:
        head += (
            "\n  note: detached-process detection and cleanup does not exist on this platform "
            "(Linux child subreaper and /proc required)."
        )
    elif isinstance(det_items, list) and det_items:
        n_det = len(det_items)
        n_killed = sum(1 for x in det_items if isinstance(x, dict) and x.get("killed"))
        parts = [
            f"pid={x['pid']}({x.get('phase')},{'killed' if x.get('killed') else 'alive'})"
            if isinstance(x, dict) else str(x)
            for x in det_items[:10]
        ]
        shown_p = ", ".join(parts) + (f" … (+{n_det - 10} more)" if n_det > 10 else "")
        head += (
            f"\n  WARNING: {n_det} detached descendant process(es) detected "
            f"({n_killed}/{n_det} killed: {shown_p}); writes after delivery are not recorded."
        )
    rcpt_err = res.get("receipt_error")
    if not rcpt_err:
        rcpt_obj = res.get("receipt")
        if isinstance(rcpt_obj, dict) and rcpt_obj.get("recorded") is False:
            rcpt_err = rcpt_obj.get("error") or "unknown error"
    out = head + f"\n  attempts and logs: {res['run_dir']}"
    if rcpt_err:
        out = (
            f"WARNING: the signed receipt for this run could NOT be written ({rcpt_err}); "
            f"this run has no verifiable record\n{out}"
        )
    return out
