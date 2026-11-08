# -*- coding: utf-8 -*-
"""CI 安裝合約守門（r1262, 2026-11-08）。

背景：GitHub auto CI（auto-ci.yml）自 2026-11-07 首跑起 **26 次全紅**，全部敗在
「pytest — ReqLoop」步。根因（f03d1177 乾淨 venv 複現）：
``test_reqloop_repair.py::test_pin_survives_venv_symlink`` 在實際啟動的直譯器裡斷言
``import scipy, numpy`` —— scipy/numpy **不在安裝合約**（vacant-network 依賴 + [dev]
extras 都沒有），只是開發機 venv 恰好有。乾淨 CI venv（``pip install -e ".[dev]"``）
沒有 → 必紅。3db4a7f3 已改用合約必有的 pytest。

本檔把「這類缺陷」變成機器紅燈：掃描 reqloop 測試中**實際經 subprocess.run 啟動**
的 ``-c`` 片段，要求其中每個 import 的 top-level 包都在安裝合約內（或為 stdlib）。
提示詞/資料字串（如 ``_loop_observation`` 的 pandas 例子）不掃——它們不會被执行。

安裝合約＝ ``importlib.metadata`` 中 vacant-network 的 requires：無 marker 的運行依賴
＋ ``extra == "dev"`` 的開發依賴（CI 正是 ``pip install -e ".[dev]"``）。
"""
from __future__ import annotations

import importlib.metadata
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
TESTS = REPO / "tests"


def _contract_packages() -> set[str]:
    """vacant-network 的安裝合約包名（運行依賴 + dev extras），含 import 名變體。"""
    allowed: set[str] = set()
    found = False
    for dist in importlib.metadata.distributions():
        name = (dist.metadata["Name"] or "").strip().lower()
        if name.replace("_", "-") != "vacant-network":
            continue
        found = True
        for req in dist.requires or []:
            marker = req.split(";", 1)[1] if ";" in req else ""
            if marker and 'extra == "dev"' not in marker and "extra == 'dev'" not in marker:
                continue  # 其它 extra，不在 CI 的 "[dev]" 安裝範圍
            top = re.split(r"[><=~!\[]", req, 1)[0].strip()
            if top:
                allowed.add(top.lower())
                allowed.add(top.lower().replace("-", "_"))
    if not found:
        raise AssertionError("vacant-network 未安裝；無法建立安裝合約（CI 會先 pip install -e .[dev]）")
    return allowed


def _subprocess_run_blocks(source: str) -> list[str]:
    """取出所有 subprocess.run(...) 呼叫的完整文字（括號配對，含字串）。"""
    blocks: list[str] = []
    for m in re.finditer(r"subprocess\.run\(", source):
        i = m.end() - 1  # 左括號
        depth = 0
        j = i
        while j < len(source):
            c = source[j]
            if c == "(":
                depth += 1
            elif c == ")":
                depth -= 1
                if depth == 0:
                    break
            j += 1
        blocks.append(source[i:j + 1])
    return blocks


def _c_snippets(block: str) -> list[str]:
    """subprocess 區塊裡 `-c '<snippet>'` / `-c "<snippet>"` 的片段（實際會执行者）。"""
    return [m.group(2) for m in re.finditer(r"-c\s+(['\"])(.*?)\1", block, re.S)]


def _imported_packages(snippet: str) -> set[str]:
    pkgs: set[str] = set()
    for m in re.finditer(r"^\s*import\s+([\w.,\s]+)", snippet, re.M):
        for part in m.group(1).split(","):
            name = part.strip().split(".")[0].split(" as ")[0].strip()
            if name and name != "__main__":
                pkgs.add(name)
    for m in re.finditer(r"^\s*from\s+([\w.]+)\s+import", snippet, re.M):
        pkgs.add(m.group(1).split(".")[0])
    return pkgs


def _violations(contract: set[str]) -> list[str]:
    stdlib = set(sys.stdlib_module_names)
    bad: list[str] = []
    for f in sorted(TESTS.glob("test_reqloop_*.py")):
        src = f.read_text(encoding="utf-8")
        for block in _subprocess_run_blocks(src):
            for snip in _c_snippets(block):
                for pkg in _imported_packages(snip):
                    if pkg.lower() not in contract and pkg not in stdlib:
                        bad.append(f"{f.name}: 實際啟動的 python -c 片段 import 了安裝合約外的包 {pkg!r} <- {snip!r}")
    return bad


def test_reqloop_tests_never_execute_non_contract_imports():
    """reqloop 測試實際啟動的直譯器，只准 import 安裝合約（vacant-network deps + [dev]）
    或 stdlib 的包。違反＝乾淨 CI venv 必紅（r1262：26 次紅燈的根因類別）。"""
    contract = _contract_packages()
    assert "pytest" in contract, "安裝合約應含 [dev] 的 pytest；若這裡紅，先查 pyproject [dev] extra"
    bad = _violations(contract)
    assert not bad, "\n".join(bad)


def test_guard_negative_control_scipy_numpy_flagged():
    """負向控制：掃描器＋合約判定必須抓到 scipy/numpy（f03d1177 CI 紅燈的原始缺陷）。
    若此測試綠而上面那條紅了，說明守門本身壞了（H-0 式：綠燈來自忘了掃）。"""
    contract = _contract_packages()
    assert "scipy" not in contract and "numpy" not in contract, \
        "前提錯誤：scipy/numpy 若進了安裝合約，本守門與負向控制都要重寫"
    src = (
        "def test_x():\n"
        "    import subprocess\n"
        "    r = subprocess.run(\n"
        '        ["bash", "-c", "python3 -c \'import scipy, numpy; print(scipy.__version__)\'"],\n'
        "        capture_output=True, text=True)\n"
    )
    stdlib = set(sys.stdlib_module_names)
    flagged: set[str] = set()
    for block in _subprocess_run_blocks(src):
        for snip in _c_snippets(block):
            flagged |= {
                p for p in _imported_packages(snip)
                if p.lower() not in contract and p not in stdlib
            }
    assert {"scipy", "numpy"} <= flagged, f"守門未抓到 scipy/numpy，只抓到 {sorted(flagged)}"
