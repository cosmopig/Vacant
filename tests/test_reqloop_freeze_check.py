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
    broken = [k for k in MANDATED if "OK" not in lines[k]]
    assert not broken, f"有檢查項非 OK: {broken}\n{run.stdout}"
