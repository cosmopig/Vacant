"""freeze_check（r1268, vq-el4.27）：每輪凍結狀態複核已整合為單一指令。

背景：r1236–r1267 共 31 輪的「複核＋記錄」靠 ~6 條分散手動指令（anchors 測試、
ci-contract 測試、兩條 in-scope diff、filing 六個 sha、g3gate --plan），任一項漏跑
即無裁決可引（H-0 同型風險：漏掉一個旗標的綠燈就是漏洞成因）。
ops/reqloop/freeze_check.py 把審查指示 #1（anchors 守衛）與 #3（三分支實質檔案
比對）＋ filing sha ＋ g3gate --plan 收斂成一條指令、一個裁決行。

本測試即驗收：跑一次指令，要求 rc=0、裁決行存在、七項檢查全在輸出中且全 OK。
全唯讀：不呼叫模型、不寫檔、不改分支。
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "ops" / "reqloop" / "freeze_check.py"

MANDATED = (
    "anchors",        # 審查指示 #1：凍結錨點守衛（5 測）
    "ci_contract",    # 審查指示 #1：安裝合約（2 測）
    "diff_worker",    # 審查指示 #3：auto/worker  in-scope diff == 0
    "diff_argon",     # 審查指示 #3：auto/argon   in-scope diff == 0
    "filing_code",    # 審查指示 #1：filing code 三 sha 100% 吻合
    "filing_sources", # filing sources 三 sha
    "g3gate_plan",    # G3 前置（NOT FIRED、0 model calls）
    "bk_state",       # 審查指示 #3 工作樹衛生：STATE.md 簿記鏡像同步（r1271 起）
    "bk_now",         # 審查指示 #3 工作樹衛生：NOW.md 簿記鏡像同步（r1271 起）
)


@pytest.fixture(scope="module")
def run() -> subprocess.CompletedProcess[str]:
    assert SCRIPT.is_file(), f"缺少 {SCRIPT}（vq-el4.27 未落地）"
    return subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=REPO,
        capture_output=True,
        text=True,
        timeout=600,
    )


def test_freeze_check_verdict_ok(run: subprocess.CompletedProcess[str]) -> None:
    assert run.returncode == 0, f"rc={run.returncode}\n{run.stdout}\n{run.stderr}"
    assert "VERDICT: FROZEN_STATE_OK" in run.stdout, run.stdout


def test_freeze_check_covers_all_mandated_checks(
    run: subprocess.CompletedProcess[str],
) -> None:
    lines = {
        l.split()[0]: l
        for l in run.stdout.splitlines()
        if l.strip() and not l.startswith("VERDICT")
    }
    missing = [k for k in MANDATED if k not in lines]
    assert not missing, f"缺少檢查項 {missing}\n{run.stdout}"
    # 注意：必須比對狀態欄位（第 2 欄）而非子串——"OK" ⊂ "BROKEN"，
    # 用 `"OK" not in line` 永遠抓不到 BROKEN（r1271 實測發現的測試自身假綠燈）。
    broken = [k for k in MANDATED if lines[k].split()[1] != "OK"]
    assert not broken, f"有檢查項非 OK: {broken}\n{run.stdout}"


def _load_freeze_check() -> object:
    """以模組方式載入 freeze_check.py（非 subprocess、無 python -c 片段，
    不觸及 test_reqloop_ci_contract.py 的安裝合約掃描範圍）。"""
    import importlib.util

    spec = importlib.util.spec_from_file_location("freeze_check_mod", SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_bookkeeping_negative_controls(tmp_path: Path) -> None:
    """漂移負控制（r1271）：H-0 教訓——漏掉一項檢查得到的綠燈就是漏洞成因。
    必須證明檢查真的抓得到：鏡像漂移→BROKEN、缺表頭→BROKEN、NOW 不同→BROKEN，
    同步→OK。全部對臨時 repo 操作，不碰真檔。"""
    mod = _load_freeze_check()

    repo = tmp_path / "repo"
    (repo / "ops" / "loop").mkdir(parents=True)
    canonical = "# t\n\n## Current State\nCANONICAL\n（log line）\n"
    (repo / "STATE.md").write_text(canonical, encoding="utf-8")
    (repo / "ops" / "STATE.md").write_text("# t\n\n## Current State\nCANONICAL\n", encoding="utf-8")
    (repo / "NOW.md").write_text("NOW\n", encoding="utf-8")
    (repo / "ops" / "loop" / "NOW.md").write_text("NOW\n", encoding="utf-8")

    # (a) 同步 → OK
    mod.results.clear()
    mod.check_bookkeeping_state(repo)  # type: ignore[attr-defined]
    assert mod.results[-1][:2] == ("bk_state", True), mod.results
    mod.results.clear()
    mod.check_bookkeeping_now(repo)  # type: ignore[attr-defined]
    assert mod.results[-1][:2] == ("bk_now", True), mod.results

    # (b) 鏡像停滯（漂移）→ 必須 BROKEN，不得假綠
    (repo / "ops" / "STATE.md").write_text("# t\n\n## Current State\nSTALE\n", encoding="utf-8")
    mod.results.clear()
    mod.check_bookkeeping_state(repo)  # type: ignore[attr-defined]
    name, ok, detail = mod.results[-1]
    assert name == "bk_state" and ok is False and "DRIFT" in detail, mod.results

    # (c) 鏡像缺 '## Current State' 表頭 → BROKEN
    (repo / "ops" / "STATE.md").write_text("# t\n\nno header\n", encoding="utf-8")
    mod.results.clear()
    mod.check_bookkeeping_state(repo)  # type: ignore[attr-defined]
    assert mod.results[-1][1] is False, mod.results

    # (d) NOW 鏡像不同 → BROKEN
    (repo / "ops" / "loop" / "NOW.md").write_text("STALE\n", encoding="utf-8")
    mod.results.clear()
    mod.check_bookkeeping_now(repo)  # type: ignore[attr-defined]
    assert mod.results[-1][1] is False, mod.results

    # (e) 兩份 NOW.md 皆 0 字元 → 必須 BROKEN，不得假綠（r1272）：
    # byte-identical 對空檔成立是空集測量——I-4「未測量不是通過」，
    # NOW.md 的約定是承載「現在在哪、下一步」，0B 是簿記壞掉，不是「同步」。
    (repo / "NOW.md").write_bytes(b"")
    (repo / "ops" / "loop" / "NOW.md").write_bytes(b"")
    mod.results.clear()
    mod.check_bookkeeping_now(repo)  # type: ignore[attr-defined]
    name, ok, detail = mod.results[-1]
    assert name == "bk_now" and ok is False and "vacuous" in detail.lower(), mod.results
