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
    # 條目邊界約定（r1279 起守衛要求）：條目行＝「（YYYY-MM-DD…」（live 24/24 實證）。
    canonical = "# t\n\n## Current State\nCANONICAL\n（2026-11-08 r999: log）\n"
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

    # (f) 鏡像截斷：最新條目尾部被砍 → 必須 BROKEN，不得假綠（r1278）：
    # 截斷後的鏡像仍是 canonical 的 byte 前綴（startswith 成立），舊檢查判 OK，
    # 但鏡像實際少了當前狀態條目的 9 個字元——與 r1271/r1272 同型假綠燈
    # （H-0：漏掉一項得到的綠燈就是漏洞成因；I-4：未測量≠通過）。
    (repo / "ops" / "STATE.md").write_text(
        "# t\n\n## Current State\nCANONICA", encoding="utf-8"
    )
    mod.results.clear()
    mod.check_bookkeeping_state(repo)  # type: ignore[attr-defined]
    name, ok, detail = mod.results[-1]
    assert name == "bk_state" and ok is False and "TRUNCATED" in detail, mod.results

    # (g) 多行條目在行邊界截斷（鏡像以完整行結尾、但 canonical 餘部不是新條目）
    # → 必須 BROKEN：只守「以換行結尾」不夠，條目邊界（'（'）守衛才能抓住。
    (repo / "STATE.md").write_text(
        "# t\n\n## Current State\nE1 part1\nE1 part2\n（log line）\n", encoding="utf-8"
    )
    (repo / "ops" / "STATE.md").write_text(
        "# t\n\n## Current State\nE1 part1\n", encoding="utf-8"
    )
    mod.results.clear()
    mod.check_bookkeeping_state(repo)  # type: ignore[attr-defined]
    name, ok, detail = mod.results[-1]
    assert name == "bk_state" and ok is False and "TRUNCATED" in detail, mod.results


def test_bookkeeping_multiline_paren_continuation_negative_control(
    tmp_path: Path,
) -> None:
    """多行條目截斷假綠燈負控制（r1279）：r1278 守衛只要求餘部以「（」起始——
    多行條目的續行本身以「（」開頭時（如「（續行…）」），條目中途被砍的鏡像仍被
    判「同步」＝假綠燈（r1279 實測：('bk_state', True, 'mirror 31B…同步')，與
    r1271/r1272/r1278 同型、H-0 同構）。條目邊界約定須按 live 檔實證的
    「（YYYY-MM-DD…」起始（24/24 條目行逐條核實），不得只守「（」前綴：
    非條目邊界的行邊界截斷一律 BROKEN。"""
    mod = _load_freeze_check()

    repo = tmp_path / "repo"
    (repo / "ops").mkdir(parents=True)
    # canonical：條目 E1 跨兩行，續行以「（」開頭（形如新條目，實為條目本體）。
    (repo / "STATE.md").write_text(
        "# t\n\n## Current State\n（2026-11-08 r999: part1\n（續行以（開頭）\n",
        encoding="utf-8",
    )
    # 鏡像在行邊界截斷：E1 只留第一行——舊守衛判「同步」（假綠），必須 BROKEN。
    (repo / "ops" / "STATE.md").write_text(
        "# t\n\n## Current State\n（2026-11-08 r999: part1\n", encoding="utf-8"
    )
    mod.results.clear()
    mod.check_bookkeeping_state(repo)  # type: ignore[attr-defined]
    name, ok, detail = mod.results[-1]
    assert name == "bk_state" and ok is False and "TRUNCATED" in detail, mod.results


def test_guard_suite_count_negative_controls(tmp_path: Path) -> None:
    """守衛測試「計數弱化」負控制（r1273）：審查指示 #1 點名「5 passed 守衛」與
    「tests/test_reqloop_ci_contract.py（2 passed）嚴禁弱化」——rc=0 不等於「足額通過」：
    守衛檔被削掉測試、剩下全綠時，freeze_check 若仍判 OK 即假綠燈（與 r1271/r1272
    空對/空檔假綠同型，H-0：漏掉一項得到的綠燈就是漏洞成因）。必須證明抓得到。"""
    mod = _load_freeze_check()

    repo = tmp_path / "repo"
    tests_dir = repo / "tests"
    tests_dir.mkdir(parents=True)

    # (a) anchors 守衛檔 5 測被削成 1 測（剩餘全綠、rc=0）→ 必須 BROKEN
    (tests_dir / "test_reqloop_frozen_anchors.py").write_text(
        "def test_weakened():\n    assert True\n", encoding="utf-8"
    )
    mod.results.clear()
    mod.check_anchors(cwd=repo)  # type: ignore[attr-defined]
    name, ok, detail = mod.results[-1]
    assert name == "anchors" and ok is False, mod.results

    # (b) 足額 5 測全綠 → OK
    (tests_dir / "test_reqloop_frozen_anchors.py").write_text(
        "\n".join(f"def test_t{i}():\n    assert True\n" for i in range(5)),
        encoding="utf-8",
    )
    mod.results.clear()
    mod.check_anchors(cwd=repo)  # type: ignore[attr-defined]
    assert mod.results[-1][:2] == ("anchors", True), mod.results

    # (c) ci_contract 守衛檔 2 測被削成 1 測（剩餘全綠、rc=0）→ 必須 BROKEN
    (tests_dir / "test_reqloop_ci_contract.py").write_text(
        "def test_weakened():\n    assert True\n", encoding="utf-8"
    )
    mod.results.clear()
    mod.check_ci_contract(cwd=repo)  # type: ignore[attr-defined]
    name, ok, detail = mod.results[-1]
    assert name == "ci_contract" and ok is False, mod.results

    # (d) 足額 2 測全綠 → OK
    (tests_dir / "test_reqloop_ci_contract.py").write_text(
        "def test_t0():\n    assert True\n\n"
        "def test_t1():\n    assert True\n",
        encoding="utf-8",
    )
    mod.results.clear()
    mod.check_ci_contract(cwd=repo)  # type: ignore[attr-defined]
    assert mod.results[-1][:2] == ("ci_contract", True), mod.results
