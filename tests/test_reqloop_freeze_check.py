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
    "wt_clean",       # 審查指示 #3 工作樹衛生：規範三分支 worktree in-scope 無殘留（r1309）
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
    # 條目邊界約定（r1279 起守衛要求）：條目行＝「（YYYY-MM-DD…」（live 24/24 實證）；
    # r1292 起錨點行（section 首個非空行）同為日期條目行——非條目行＝簿記違反約定。
    canonical = "# t\n\n## Current State\n（2026-11-08 r999: state）\n（2026-11-07 r998: log）\n"
    (repo / "STATE.md").write_text(canonical, encoding="utf-8")
    (repo / "ops" / "STATE.md").write_text("# t\n\n## Current State\n（2026-11-08 r999: state）\n", encoding="utf-8")
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
    # 但鏡像實際少了當前狀態條目的尾部字元——與 r1271/r1272 同型假綠燈
    # （H-0：漏掉一項得到的綠燈就是漏洞成因；I-4：未測量≠通過）。
    (repo / "ops" / "STATE.md").write_text(
        "# t\n\n## Current State\n（2026-11-08 r999: sta", encoding="utf-8"
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


def test_bookkeeping_header_only_mirror_negative_control(tmp_path: Path) -> None:
    """鏡像零條目假綠燈負控制（r1282，vq-el4.34）：舊守衛只驗「鏡像後的餘部以
    日期條目起始」——鏡像本身零條目行（只有標題＋'## Current State'）時，餘部
    恰為最新條目、自然日期起始，舊碼判「同步」（r1282 實測：
    ('bk_state', True, 'mirror 22B…同步')）。鏡像約定＝標題＋'## Current State'＋
    最新條目（單行，r1278 約定），故鏡像末行必須是 canonical 的最新條目行；
    零條目鏡像不是「同步」（I-4：未測量不是通過；H-0 同構：漏掉一項得到的綠燈
    就是漏洞成因）。正控制：正確鏡像（＝標題＋表頭＋最新條目單行）仍 OK。"""
    mod = _load_freeze_check()

    repo = tmp_path / "repo"
    (repo / "ops").mkdir(parents=True)
    (repo / "STATE.md").write_text(
        "# t\n\n## Current State\n（2026-11-08 r999: 當前條目）\n（2026-11-07 r998: 舊條目）\n",
        encoding="utf-8",
    )
    # (i) 鏡像只有標題＋表頭、零條目行 → 必須 BROKEN，不得假綠
    (repo / "ops" / "STATE.md").write_text("# t\n\n## Current State\n", encoding="utf-8")
    mod.results.clear()
    mod.check_bookkeeping_state(repo)  # type: ignore[attr-defined]
    name, ok, detail = mod.results[-1]
    assert name == "bk_state" and ok is False and "NO_ENTRY" in detail, mod.results

    # (ii) 正控制：正確鏡像（＝標題＋表頭＋最新條目單行）→ 仍 OK
    (repo / "ops" / "STATE.md").write_text(
        "# t\n\n## Current State\n（2026-11-08 r999: 當前條目）\n", encoding="utf-8"
    )
    mod.results.clear()
    mod.check_bookkeeping_state(repo)  # type: ignore[attr-defined]
    assert mod.results[-1][:2] == ("bk_state", True), mod.results


def test_bookkeeping_nonentry_anchor_zero_entry_mirror_negative_control(
    tmp_path: Path,
) -> None:
    """非條目錨點零條目鏡像假綠燈負控制（r1292, vq-el4.37）：r1282 守衛的錨點
    ＝「## Current State」後首個非空行，但從未被要求是日期條目行——若 section 首個
    非空行是非日期行（如 NOTE），鏡像＝標題＋表頭＋該非日期行（零條目行）時，既有
    全部守衛仍判「同步」（r1292 實測：('bk_state', True, 'mirror 27B…同步')，與
    r1271–r1282 同型假綠燈、H-0 同構：漏掉一項得到的綠燈就是漏洞成因；I-4：未測量
    不是通過）。錨點行須匹配 ENTRY_START_RE「（YYYY-MM-DD…」，否則 BROKEN。"""
    mod = _load_freeze_check()

    repo = tmp_path / "repo"
    (repo / "ops").mkdir(parents=True)
    (repo / "STATE.md").write_text(
        "# t\n\n## Current State\nNOTE\n（2026-11-08 r999: entry）\n",
        encoding="utf-8",
    )
    # 鏡像＝標題＋表頭＋非日期行（零條目行）→ 必須 BROKEN，不得假綠
    (repo / "ops" / "STATE.md").write_text(
        "# t\n\n## Current State\nNOTE\n", encoding="utf-8"
    )
    mod.results.clear()
    mod.check_bookkeeping_state(repo)  # type: ignore[attr-defined]
    name, ok, detail = mod.results[-1]
    assert name == "bk_state" and ok is False and "NO_ENTRY" in detail, mod.results


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

    # (b) 足額 5 測（期望測試名、身份齊）全綠 → OK
    (tests_dir / "test_reqloop_frozen_anchors.py").write_text(
        "\n".join(
            f"def {n}():\n    assert True\n"
            for n in (
                "test_repair_py_is_frozen",
                "test_extract_py_boundary_is_frozen",
                "test_guard_detects_tampered_copy",
                "test_g25_filing_code_hashes_match_repo",
                "test_filing_guard_detects_drift",
            )
        ),
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

    # (d) 足額 2 測（期望測試名、身份齊）全綠 → OK
    (tests_dir / "test_reqloop_ci_contract.py").write_text(
        "def test_reqloop_tests_never_execute_non_contract_imports():\n    assert True\n\n"
        "def test_guard_negative_control_scipy_numpy_flagged():\n    assert True\n",
        encoding="utf-8",
    )
    mod.results.clear()
    mod.check_ci_contract(cwd=repo)  # type: ignore[attr-defined]
    assert mod.results[-1][:2] == ("ci_contract", True), mod.results

    # (e) r1285：5 passed + 1 skipped（守衛測試被 @pytest.mark.skip 禁用、藏 assert False）
    #     → pytest 匯總「5 passed, 1 skipped」→ 舊計數守衛只抽 "5 passed" 仍判 OK＝假綠燈
    #     （r1271–r1282 同型、I-4 未測量不是通過）；必須 BROKEN 且 detail 點出 skipped。
    #     r1314 起 5 個守衛用期望真名（身份層滿足、結果類別層單獨抓 skipped）。
    (tests_dir / "test_reqloop_frozen_anchors.py").write_text(
        "\n".join(
            f"def {n}():\n    assert True\n"
            for n in (
                "test_repair_py_is_frozen",
                "test_extract_py_boundary_is_frozen",
                "test_guard_detects_tampered_copy",
                "test_g25_filing_code_hashes_match_repo",
                "test_filing_guard_detects_drift",
            )
        )
        + "\nimport pytest\n\n"
        + "@pytest.mark.skip(reason=\"guard disabled\")\n"
        + "def test_disabled_guard():\n    assert False\n",
        encoding="utf-8"
    )
    mod.results.clear()
    mod.check_anchors(cwd=repo)  # type: ignore[attr-defined]
    name, ok, detail = mod.results[-1]
    assert name == "anchors" and ok is False, mod.results
    assert "skipped" in detail, mod.results


def test_guard_suite_identity_negative_controls(tmp_path: Path) -> None:
    """守衛測試「身份」假綠燈負控制（r1314，vq-el4.49）：計數守衛必要但不充分（r1296 同型）。
    anchors 5 測（repair/extract 錨、篡改副本偵測、filing 哈希比對、漂移偵測）被換成 5 個
    assert True dummy（全綠、rc=0、計數=5、無 skipped）時，舊計數守衛仍判 OK＝假綠燈——
    本檔案既有 (b) fixture 曾字面編碼此期望；ci_contract 2 測同型。H-0：漏掉一項得到的
    綠燈就是漏洞成因；I-4：未測量不是通過。必須證明抓得到：身份缺失→BROKEN 且點名，
    身份齊→OK。全部對臨時 repo 操作，不碰真檔。"""
    mod = _load_freeze_check()

    repo = tmp_path / "repo"
    tests_dir = repo / "tests"
    tests_dir.mkdir(parents=True)

    # (a) anchors：5 dummy（非期望名）全綠 → 必須 BROKEN，且 detail 點名缺失守衛測試
    (tests_dir / "test_reqloop_frozen_anchors.py").write_text(
        "\n".join(f"def test_t{i}():\n    assert True\n" for i in range(5)),
        encoding="utf-8",
    )
    mod.results.clear()
    mod.check_anchors(cwd=repo)  # type: ignore[attr-defined]
    name, ok, detail = mod.results[-1]
    assert name == "anchors" and ok is False, mod.results
    assert "test_repair_py_is_frozen" in detail, mod.results

    # (b) anchors：期望 5 測試名齊（身份足）→ OK
    (tests_dir / "test_reqloop_frozen_anchors.py").write_text(
        "\n".join(
            f"def {n}():\n    assert True\n"
            for n in (
                "test_repair_py_is_frozen",
                "test_extract_py_boundary_is_frozen",
                "test_guard_detects_tampered_copy",
                "test_g25_filing_code_hashes_match_repo",
                "test_filing_guard_detects_drift",
            )
        ),
        encoding="utf-8",
    )
    mod.results.clear()
    mod.check_anchors(cwd=repo)  # type: ignore[attr-defined]
    assert mod.results[-1][:2] == ("anchors", True), mod.results

    # (c) ci_contract：2 dummy（非期望名）全綠 → 必須 BROKEN，且 detail 點名缺失
    (tests_dir / "test_reqloop_ci_contract.py").write_text(
        "def test_t0():\n    assert True\n\ndef test_t1():\n    assert True\n",
        encoding="utf-8",
    )
    mod.results.clear()
    mod.check_ci_contract(cwd=repo)  # type: ignore[attr-defined]
    name, ok, detail = mod.results[-1]
    assert name == "ci_contract" and ok is False, mod.results
    assert "test_reqloop_tests_never_execute_non_contract_imports" in detail, mod.results

    # (d) ci_contract：期望 2 測試名齊 → OK
    (tests_dir / "test_reqloop_ci_contract.py").write_text(
        "def test_reqloop_tests_never_execute_non_contract_imports():\n    assert True\n\n"
        "def test_guard_negative_control_scipy_numpy_flagged():\n    assert True\n",
        encoding="utf-8",
    )
    mod.results.clear()
    mod.check_ci_contract(cwd=repo)  # type: ignore[attr-defined]
    assert mod.results[-1][:2] == ("ci_contract", True), mod.results


def test_filing_null_sha_negative_control(tmp_path: Path) -> None:
    """filing null-sha 假綠燈負控制（r1288，vq-el4.36）：備案 code/sources 的
    sha256 若為 null（未 pin）且對應檔不存在，舊碼 `match = mine == meta["sha256"]`
    變成 None == None → True——什麼都没 pin、什麼都没量到的削弱備案仍被判
    「3/3 MATCH」＝假綠燈（r1288 實測：六 sha 全 null 備案 filing_sources 判
    OK，與 r1273 削弱但照綠同型；I-4：未測量不是通過；H-0：漏掉一項得到的綠燈
    就是漏洞成因）。null pin＝「sha 未 pin」＝未測量，必須 BROKEN。
    正控制：真 sha＋真檔仍 3/3 MATCH OK（修復不得破壞正常路徑）。"""
    import hashlib
    import json

    mod = _load_freeze_check()

    repo = tmp_path / "repo"
    fdir = repo / "ops" / "audits"
    fdir.mkdir(parents=True)
    filing = fdir / "g25_all_gates_filing.json"
    # 削弱備案：code 三檔＋sources 三檔全不存在，且六個 sha256 全為 null（未 pin）
    # ——舊碼對「檔不存在（_sha256→None）＋pin 為 null」判 MATCH。
    # r1296（vq-el4.38）：key 須為 canonical 3 份凍結檔（新 key-identity 守衛
    # 先過），才進得到 null-sha 路徑。
    filing.write_text(json.dumps({
        "code": {
            "vacant_network/reqloop/extract.py": {"sha256": None},
            "vacant_network/reqloop/checks.py": {"sha256": None},
            "ops/reqloop/extract/run_eval.py": {"sha256": None},
        },
        "sources": {
            f"phase{i}": {"path": f"/x/ops/reqloop/extract/out/all/phase{i}.json",
                          "sha256": None}
            for i in (1, 2, 3)
        },
    }), encoding="utf-8")
    mod.REPO = repo   # type: ignore[attr-defined]
    mod.FILING = filing  # type: ignore[attr-defined]
    mod.results.clear()
    mod.check_filing_code()  # type: ignore[attr-defined]
    name, ok, detail = mod.results[-1]
    assert name == "filing_code" and ok is False, mod.results
    assert "MISMATCH" in detail, mod.results
    mod.results.clear()
    mod.check_filing_sources()  # type: ignore[attr-defined]
    name, ok, detail = mod.results[-1]
    assert name == "filing_sources" and ok is False, mod.results
    assert "MISMATCH" in detail, mod.results

    # 正控制：同一 repo，真 sha＋真檔（canonical 3 份凍結檔＋3 份 phase 檔）
    # → 3/3 MATCH OK（修復不得破壞正常路徑；r1296 key＝canonical 身份）
    for rel in ("vacant_network/reqloop/extract.py",
                "vacant_network/reqloop/checks.py",
                "ops/reqloop/extract/run_eval.py"):
        p = repo / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("hello\n", encoding="utf-8")
    sdir = repo / "ops" / "reqloop" / "extract" / "out" / "all"
    sdir.mkdir(parents=True)
    for i in (1, 2, 3):
        (sdir / f"phase{i}.json").write_text("{}\n", encoding="utf-8")
    realsha = hashlib.sha256(b"hello\n").hexdigest()
    realjson = hashlib.sha256(b"{}\n").hexdigest()
    filing2 = fdir / "g25_all_gates_filing.json"
    filing2.write_text(json.dumps({
        "code": {
            "vacant_network/reqloop/extract.py": {"sha256": realsha},
            "vacant_network/reqloop/checks.py": {"sha256": realsha},
            "ops/reqloop/extract/run_eval.py": {"sha256": realsha},
        },
        "sources": {
            f"phase{i}": {"path": f"/x/ops/reqloop/extract/out/all/phase{i}.json",
                          "sha256": realjson}
            for i in (1, 2, 3)
        },
    }), encoding="utf-8")
    mod.FILING = filing2  # type: ignore[attr-defined]
    mod.results.clear()
    mod.check_filing_code()  # type: ignore[attr-defined]
    assert mod.results[-1][:2] == ("filing_code", True), mod.results
    mod.results.clear()
    mod.check_filing_sources()  # type: ignore[attr-defined]
    assert mod.results[-1][:2] == ("filing_sources", True), mod.results


def test_filing_key_substitution_negative_control(tmp_path: Path) -> None:
    """filing 覆蓋集身份假綠燈負控制（r1296，vq-el4.38）：count==3 必要但不
    充分（r1273 同型：計數守住但身份未守）——code 段 key 被換成另一檔（檔存在、
    sha 真）後 3 份凍結檔之一失去覆蓋，舊碼仍判「3/3 MATCH」OK（r1296 實證：
    run_eval.py key→decoy.py，舊碼判 OK＝假綠燈；H-0：漏掉一項得到的綠燈就是
    漏洞成因；I-4：未測量不是通過）。sources 段同（phase3 key→phaseX、
    phase3 路徑重指 phase1 檔）。新守衛：code key 集＝恰 3 份凍結檔；
    sources key 集＝phase1/2/3、派生 tail 集＝3 份 phase 檔且互異；
    正控制：canonical key 集＋真 sha 仍 OK。"""
    import hashlib
    import json

    mod = _load_freeze_check()
    repo = tmp_path / "repo"
    fdir = repo / "ops" / "audits"
    fdir.mkdir(parents=True)

    def sha(b: bytes) -> str:
        return hashlib.sha256(b).hexdigest()

    hs, hj = sha(b"hello\n"), sha(b"{}\n")
    CODE3 = (
        "vacant_network/reqloop/extract.py",
        "vacant_network/reqloop/checks.py",
        "ops/reqloop/extract/run_eval.py",
    )
    for rel in (*CODE3, "ops/reqloop/decoy.py"):
        p = repo / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"hello\n")
    sdir = repo / "ops" / "reqloop" / "extract" / "out" / "all"
    sdir.mkdir(parents=True)
    for i in (1, 2, 3):
        (sdir / f"phase{i}.json").write_bytes(b"{}\n")

    def sp(i: int) -> str:
        return f"/x/ops/reqloop/extract/out/all/phase{i}.json"

    filing = fdir / "g25_all_gates_filing.json"
    mod.REPO = repo  # type: ignore[attr-defined]
    mod.FILING = filing  # type: ignore[attr-defined]

    # (a) code 段 key 替換：run_eval.py → decoy.py（檔存在、sha 真）＝削弱但照綠
    filing.write_text(json.dumps({
        "code": {
            "vacant_network/reqloop/extract.py": {"sha256": hs},
            "vacant_network/reqloop/checks.py": {"sha256": hs},
            "ops/reqloop/decoy.py": {"sha256": hs},
        },
        "sources": {f"phase{i}": {"path": sp(i), "sha256": hj} for i in (1, 2, 3)},
    }), encoding="utf-8")
    mod.results.clear()
    mod.check_filing_code()  # type: ignore[attr-defined]
    name, ok, detail = mod.results[-1]
    assert name == "filing_code" and ok is False, mod.results
    assert "run_eval.py" in detail and "decoy.py" in detail, mod.results

    # (b) sources 段 key 改名：phase3 → phaseX（路徑/sha 真）＝削弱但照綠
    filing.write_text(json.dumps({
        "code": {k: {"sha256": hs} for k in CODE3},
        "sources": {
            "phase1": {"path": sp(1), "sha256": hj},
            "phase2": {"path": sp(2), "sha256": hj},
            "phaseX": {"path": sp(3), "sha256": hj},
        },
    }), encoding="utf-8")
    mod.results.clear()
    mod.check_filing_sources()  # type: ignore[attr-defined]
    name, ok, detail = mod.results[-1]
    assert name == "filing_sources" and ok is False, mod.results
    assert "phase3" in detail and "phaseX" in detail, mod.results

    # (c) sources 段路徑重指：key 集 canonical 但 phase3 指 phase1 檔（兩條量同一
    # 檔、phase3.json 失覆蓋）——tail 集守衛（互異性）
    filing.write_text(json.dumps({
        "code": {k: {"sha256": hs} for k in CODE3},
        "sources": {
            "phase1": {"path": sp(1), "sha256": hj},
            "phase2": {"path": sp(2), "sha256": hj},
            "phase3": {"path": sp(1), "sha256": hj},
        },
    }), encoding="utf-8")
    mod.results.clear()
    mod.check_filing_sources()  # type: ignore[attr-defined]
    name, ok, detail = mod.results[-1]
    assert name == "filing_sources" and ok is False, mod.results
    assert "phase3" in detail, mod.results

    # 正控制：canonical key 集＋真 sha → 全 MATCH OK（修復不得破壞正常路徑）
    filing.write_text(json.dumps({
        "code": {k: {"sha256": hs} for k in CODE3},
        "sources": {f"phase{i}": {"path": sp(i), "sha256": hj} for i in (1, 2, 3)},
    }), encoding="utf-8")
    mod.results.clear()
    mod.check_filing_code()  # type: ignore[attr-defined]
    assert mod.results[-1][:2] == ("filing_code", True), mod.results
    mod.results.clear()
    mod.check_filing_sources()  # type: ignore[attr-defined]
    assert mod.results[-1][:2] == ("filing_sources", True), mod.results


def test_check_crash_named_broken_verdict_negative_control(tmp_path: Path) -> None:
    """單項檢查崩潰失裁負控制（r1297，vq-el4.39）：任一檢查執行中拋異常時
    （FILING JSON 損毀＝本守衛要 pin 的備案本身壞掉；FILING 缺失；filing 條目
    非 dict；git 缺席；子程超時），舊 main() 直接 traceback——r1297 實證：
    stdout 全空（前 5 項檢查的結果也丟）、無裁決行、detail 未點名、且其後 4 項
    （filing_sources/g3gate_plan/bk_state/bk_now）根本未跑——freeze_check.py
    docstring 自載契約「單一指令、單一裁決行」「任一項 BROKEN，detail 點名」
    失守；I-4：未測量不是通過（4 項未跑＝4 項未測量，且操作者連「未跑」都
    看不到；H-0 同構：該有裁決處的空白本身就是漏洞成因）。
    修復：main() 每項檢查以 run_check 包層——異常被點名記 BROKEN
    （CRASH: <ExcType>: <msg>），9 項全在輸出、裁決行必現、rc=1。
    (a) FILING JSON 損毀 → filing_code BROKEN CRASH（舊碼：JSONDecodeError 逃逸、
        results 空）
    (b) FILING 整檔缺失 → BROKEN CRASH（舊碼：FileNotFoundError 逃逸）
    (c) filing code 條目非 dict（key 集 canonical）→ BROKEN CRASH
        （舊碼：TypeError 逃逸）
    (d) 沙盒 main() 全跑：rc=1、VERDICT: FROZEN_STATE_BROKEN、9 項全在、
        filing 兩項 CRASH 點名（舊碼：無裁決行、stdout 全空、後 4 項未跑）
    正控制：真 sha＋真檔（canonical key）filing 兩項仍 OK（包層不得打紅正常路徑）。"""
    import hashlib
    import json

    mod = _load_freeze_check()

    repo = tmp_path / "repo"
    fdir = repo / "ops" / "audits"
    fdir.mkdir(parents=True)
    filing = fdir / "g25_all_gates_filing.json"
    mod.REPO = repo  # type: ignore[attr-defined]
    mod.FILING = filing  # type: ignore[attr-defined]

    # (a) JSON 損毀 → 舊碼：JSONDecodeError 逃逸（r1297 實證：results=[]、無記錄）
    filing.write_text("{not json", encoding="utf-8")
    mod.results.clear()
    mod.run_check("filing_code", mod.check_filing_code)  # type: ignore[attr-defined]
    name, ok, detail = mod.results[-1]
    assert name == "filing_code" and ok is False, mod.results
    assert "CRASH" in detail, mod.results

    # (b) FILING 整檔缺失 → 舊碼：FileNotFoundError 逃逸
    filing.unlink()
    mod.results.clear()
    mod.run_check("filing_code", mod.check_filing_code)  # type: ignore[attr-defined]
    name, ok, detail = mod.results[-1]
    assert name == "filing_code" and ok is False, mod.results
    assert "CRASH" in detail, mod.results

    # (c) filing code 條目非 dict（key 集 canonical、覆集守衛先過）→ 舊碼：
    # TypeError: string indices must be integers 逃逸。
    # 須先建檔使 mine 非 None——mine=None 時 `mine is not None and meta["sha256"]`
    # 短路求值、根本到不了 meta["sha256"]（此為另一條 BROKEN 路徑，不是本負控制目標）。
    CODE3 = (
        "vacant_network/reqloop/extract.py",
        "vacant_network/reqloop/checks.py",
        "ops/reqloop/extract/run_eval.py",
    )
    for rel in CODE3:
        p3 = repo / rel
        p3.parent.mkdir(parents=True, exist_ok=True)
        p3.write_bytes(b"hello\n")
    filing.write_text(json.dumps({
        "code": {k: "garbage" for k in CODE3},
        "sources": {f"phase{i}": {"path": f"/x/phase{i}.json", "sha256": "0" * 64}
                    for i in (1, 2, 3)},
    }), encoding="utf-8")
    mod.results.clear()
    mod.run_check("filing_code", mod.check_filing_code)  # type: ignore[attr-defined]
    name, ok, detail = mod.results[-1]
    assert name == "filing_code" and ok is False, mod.results
    assert "CRASH" in detail, mod.results

    # (d) 沙盒 main() 全跑：單一裁決行契約（舊碼：traceback、無裁決行、
    # stdout 全空、filing_sources/g3gate_plan/bk_state/bk_now 未跑）
    sandbox = tmp_path / "sandbox"
    (sandbox / "ops" / "reqloop").mkdir(parents=True)
    (sandbox / "ops" / "audits").mkdir(parents=True)
    (sandbox / "ops" / "reqloop" / "freeze_check.py").write_text(
        SCRIPT.read_text(encoding="utf-8"), encoding="utf-8"
    )
    (sandbox / "ops" / "audits" / "g25_all_gates_filing.json").write_text(
        "{broken", encoding="utf-8"
    )
    p = subprocess.run(
        [sys.executable, str(sandbox / "ops" / "reqloop" / "freeze_check.py")],
        cwd=sandbox, capture_output=True, text=True, timeout=300,
    )
    assert p.returncode == 1, p.stdout + p.stderr
    assert "VERDICT: FROZEN_STATE_BROKEN" in p.stdout, p.stdout + p.stderr
    heads = {l.split()[0] for l in p.stdout.splitlines() if l.strip()}
    missing = [k for k in MANDATED if k not in heads]
    assert not missing, f"沙盒裁決輸出缺項 {missing}\n{p.stdout}"
    for k in ("filing_code", "filing_sources"):
        line = next(l for l in p.stdout.splitlines() if l.split() and l.split()[0] == k)
        assert "CRASH" in line, p.stdout

    # 正控制：真 sha＋真檔（canonical key）→ filing 兩項仍 OK
    for rel in CODE3:
        p2 = repo / rel
        p2.parent.mkdir(parents=True, exist_ok=True)
        p2.write_bytes(b"hello\n")
    sdir = repo / "ops" / "reqloop" / "extract" / "out" / "all"
    sdir.mkdir(parents=True)
    for i in (1, 2, 3):
        (sdir / f"phase{i}.json").write_bytes(b"{}\n")
    hs = hashlib.sha256(b"hello\n").hexdigest()
    hj = hashlib.sha256(b"{}\n").hexdigest()
    filing.write_text(json.dumps({
        "code": {k: {"sha256": hs} for k in CODE3},
        "sources": {f"phase{i}": {"path": f"/x/ops/reqloop/extract/out/all/phase{i}.json",
                                  "sha256": hj} for i in (1, 2, 3)},
    }), encoding="utf-8")
    mod.results.clear()
    mod.run_check("filing_code", mod.check_filing_code)  # type: ignore[attr-defined]
    assert mod.results[-1][:2] == ("filing_code", True), mod.results
    mod.results.clear()
    mod.run_check("filing_sources", mod.check_filing_sources)  # type: ignore[attr-defined]
    assert mod.results[-1][:2] == ("filing_sources", True), mod.results


def test_guard_suite_printed_summary_spoof_negative_control(tmp_path: Path) -> None:
    """r1324（vq-el4.50）：身份守衛的通過測試名只認 -rA short test summary 段。

    r1314 身份守衛從全量輸出收集「PASSED <nodeid>」行核對測試名——但測試體本身可
    print 以「PASSED 」開頭的行進 stdout，舊碼會把那些行加進 passed_names：削弱
    守衛檔（3 個真名 dummy＋2 個假名 dummy、print 偽造剩下 2 個期望名的 summary
    行）計數足（5 passed）、無其它結果類、「身份齊」→ OK＝假綠燈（r1324 RED 實
    證：('anchors', True, 'pytest rc=0（身份齊；expected 5 passed, got 5；…）')；
    r1296/r1314 同族：計數守住身份未守；H-0：漏掉一項得到的綠燈就是漏洞成因）。
    修：只認「short test summary info」標頭行以來的段（真 -rA summary）、nodeid
    須含測試檔名（defense in depth）；段不存在＝未測量→空集→missing→BROKEN
    （I-4：未測量不是通過）。

    (a) anchors：3 真名＋2 假名 dummy、print 偽造 2 期望名 summary 行→舊碼 OK
        （假綠燈，r1324 RED 實證）；新碼須 BROKEN 且 detail 點名 2 個真缺名。
    (b) ci_contract 同形：1 真名＋1 假名 print 偽造另一期望名→新碼 BROKEN 點名。
    (c) 正控制：真名齊全綠→仍 OK（summary 段是正常路徑，收緊不得假紅燈）。
    (d) fail-closed 單元：輸出無 summary 段→不收集任何名（I-4）；段內行認、段外
        print 行與異路徑行不收。
    """
    mod = _load_freeze_check()

    (tmp_path / "tests").mkdir()
    # (a) 削弱 anchors：3 真名＋2 假名（print 偽造剩下 2 期望名）
    (tmp_path / "tests" / "test_reqloop_frozen_anchors.py").write_text(
        "def test_repair_py_is_frozen():\n    assert True\n"
        "def test_extract_py_boundary_is_frozen():\n    assert True\n"
        "def test_guard_detects_tampered_copy():\n"
        "    print('PASSED tests/test_reqloop_frozen_anchors.py::test_g25_filing_code_hashes_match_repo')\n"
        "    print('PASSED tests/test_reqloop_frozen_anchors.py::test_filing_guard_detects_drift')\n"
        "def test_s0():\n"
        "    print('PASSED tests/test_reqloop_frozen_anchors.py::test_filing_guard_detects_drift')\n"
        "def test_s1():\n    pass\n"
    )
    mod.results.clear()  # type: ignore[attr-defined]
    mod.check_anchors(cwd=tmp_path)  # type: ignore[attr-defined]
    name, ok, detail = mod.results[0]  # type: ignore[attr-defined]
    assert name == "anchors"
    assert not ok, (
        f"print 偽造 summary 行應被拒（r1324 RED：舊碼判 OK＝假綠燈）: {mod.results}"
    )
    assert "test_g25_filing_code_hashes_match_repo" in detail
    assert "test_filing_guard_detects_drift" in detail

    # (b) ci_contract 同形：1 真名＋1 假名 print 偽造另一期望名
    (tmp_path / "tests" / "test_reqloop_ci_contract.py").write_text(
        "def test_reqloop_tests_never_execute_non_contract_imports():\n    assert True\n"
        "def test_s0():\n"
        "    print('PASSED tests/test_reqloop_ci_contract.py::test_guard_negative_control_scipy_numpy_flagged')\n"
    )
    mod.results.clear()  # type: ignore[attr-defined]
    mod.check_ci_contract(cwd=tmp_path)  # type: ignore[attr-defined]
    name, ok, detail = mod.results[0]  # type: ignore[attr-defined]
    assert name == "ci_contract"
    assert not ok, f"print 偽造 summary 行應被拒: {mod.results}"
    assert "test_guard_negative_control_scipy_numpy_flagged" in detail

    # (c) 正控制：真名齊全綠→OK
    (tmp_path / "tests" / "test_reqloop_frozen_anchors.py").write_text(
        "".join(
            f"def {n}():\n    assert True\n"
            for n in mod.EXPECTED_ANCHOR_TEST_NAMES  # type: ignore[attr-defined]
        )
    )
    mod.results.clear()  # type: ignore[attr-defined]
    mod.check_anchors(cwd=tmp_path)  # type: ignore[attr-defined]
    assert mod.results[0][1] is True, (  # type: ignore[attr-defined]
        f"真全綠守衛檔應仍 OK（正控制）: {mod.results}"
    )

    # (d) fail-closed 單元：無 summary 段→空集（I-4）；段外/異路徑行不收
    assert (
        mod._parse_passed_names(  # type: ignore[attr-defined]
            "PASSED tests/test_reqloop_frozen_anchors.py::test_repair_py_is_frozen\n",
            "tests/test_reqloop_frozen_anchors.py",
        )
        == set()
    )
    out = (
        "PASSED tests/test_reqloop_frozen_anchors.py::test_spoof\n"
        "=========================== short test summary info ============================\n"
        "PASSED tests/test_reqloop_frozen_anchors.py::test_repair_py_is_frozen\n"
        "PASSED other/file.py::test_repair_py_is_frozen\n"
    )
    assert (
        mod._parse_passed_names(  # type: ignore[attr-defined]
            out, "tests/test_reqloop_frozen_anchors.py"
        )
        == {"test_repair_py_is_frozen"}
    )


def test_guard_suite_fake_summary_header_negative_control(tmp_path: Path) -> None:
    """r1327 (vq-el4.51)：測試體可 print 偽「short test summary info」標頭＋偽 PASSED 行偽造身份集。

    r1324 只擋 plain print("PASSED <nodeid>")（偽行在標頭前、不進段），但
    _parse_passed_names 取輸出中「第一處」short test summary info 為段首——守衛檔的 dummy
    測試可 print 偽標頭＋偽 PASSED 行（-rA 下 PASSES 段顯示通過測試的 captured stdout；
    capfd.disabled() 更直接），偽頭必在真頭之前，舊碼以偽頭為段首→偽名進身份集＝假綠燈
    （r1327 RED 實證：3 真名＋2 偽名 dummy 檔被舊碼判
    ('anchors', True, 'pytest rc=0（身份齊；expected 5 passed, got 5；…）')）。
    期望行為：check_anchors/check_ci_contract 判 BROKEN、detail 點名缺的真實守衛測試名；
    正控制（全真名 dummy 檔、無偽 print）仍 OK（守衛不過緊）；單元級：段首＝最後一處
    標頭行；段內行數與 passed 對帳（_passed_lines）。
    殘留（誠實記錄）：真 summary 之後才 print（conftest.py pytest_terminal_summary hook／
    晚到 thread）超出本守衛的單檔威脅模型（既有負控制皆只改守衛檔），與 bk_state 已知
    殘留邊界同類；段內行數對帳（段內 PASSED 行數 == passed）是偽行落在最後段內的二道防線。
    """
    mod = _load_freeze_check()
    anchor_names = list(mod.EXPECTED_ANCHOR_TEST_NAMES)  # type: ignore[attr-defined]
    ci_names = list(mod.EXPECTED_CI_CONTRACT_TEST_NAMES)  # type: ignore[attr-defined]
    assert len(anchor_names) >= 4 and len(ci_names) >= 2

    # (a) anchors：3 真名＋2 偽名；一 dummy print 偽標頭＋2 偽 PASSED 行（＝期望真名）
    af = tmp_path / "tests" / "test_reqloop_frozen_anchors.py"
    af.parent.mkdir(parents=True, exist_ok=True)
    af.write_text(
        "\n\n".join(
            [f"def {n}():\n    assert True" for n in anchor_names[:3]]
            + [
                "def test_s0():\n"
                '    print("short test summary info")\n'
                + "\n".join(
                    f'    print("PASSED tests/test_reqloop_frozen_anchors.py::{n}")'
                    for n in anchor_names[3:]
                )
                + "\n\ndef test_s1():\n    assert True"
            ]
        ),
        encoding="utf-8",
    )
    mod.results.clear()  # type: ignore[attr-defined]
    mod.check_anchors(cwd=tmp_path)  # type: ignore[attr-defined]
    name, ok, detail = mod.results[0]  # type: ignore[attr-defined]
    assert name == "anchors"
    assert not ok, (
        f"偽 summary 標頭＋偽 PASSED 行偽造身份集、判 OK＝假綠燈（r1327 RED）: {detail}"
    )
    assert any(n in detail for n in anchor_names[3:]), (
        f"detail 須點名缺的真實守衛測試名: {detail}"
    )

    # (b) ci_contract 同型：1 真名＋1 偽名；偽 print 覆蓋兩個期望名
    (tmp_path / "tests" / "test_reqloop_ci_contract.py").write_text(
        f"def {ci_names[0]}():\n    assert True\n\n"
        "def test_s0():\n"
        '    print("short test summary info")\n'
        + "\n".join(
            f'    print("PASSED tests/test_reqloop_ci_contract.py::{n}")'
            for n in ci_names
        )
        + "\n",
        encoding="utf-8",
    )
    mod.results.clear()  # type: ignore[attr-defined]
    mod.check_ci_contract(cwd=tmp_path)  # type: ignore[attr-defined]
    name, ok, detail = mod.results[0]  # type: ignore[attr-defined]
    assert name == "ci_contract"
    assert not ok, f"偽 summary 標頭偽造 ci_contract 身份集、判 OK＝假綠燈: {detail}"

    # (c) 正控制：全真名 dummy 檔、無偽 print→仍 OK（守衛不過緊）
    (tmp_path / "tests" / "test_reqloop_frozen_anchors.py").write_text(
        "\n\n".join(f"def {n}():\n    assert True" for n in anchor_names),
        encoding="utf-8",
    )
    mod.results.clear()  # type: ignore[attr-defined]
    mod.check_anchors(cwd=tmp_path)  # type: ignore[attr-defined]
    assert mod.results[0][1] is True, (  # type: ignore[attr-defined]
        f"全真名守衛檔應仍 OK（守衛不過緊）: {mod.results}"
    )

    # (d) 單元：偽標頭在前、真標頭在後→段首＝最後一處標頭行（只收真段）
    out = (
        "short test summary info\n"
        "PASSED tests/test_reqloop_frozen_anchors.py::test_foo_spoof\n"
        "=========================== short test summary info ============================\n"
        "PASSED tests/test_reqloop_frozen_anchors.py::test_repair_py_is_frozen\n"
    )
    assert (
        mod._parse_passed_names(  # type: ignore[attr-defined]
            out, "tests/test_reqloop_frozen_anchors.py"
        )
        == {"test_repair_py_is_frozen"}
    )

    # (e) 單元：段內行數與 passed 對帳——段內 6 行 vs passed 5→對帳破→caller 判 BROKEN
    out = (
        "=========================== short test summary info ============================\n"
        + "".join(
            f"PASSED tests/test_reqloop_frozen_anchors.py::{n}\n"
            for n in [*anchor_names, "test_spoofed_extra"]
        )
        + "======================= 5 passed in 0.01s ========================\n"
    )
    assert (
        len(
            mod._passed_lines(  # type: ignore[attr-defined]
                out, "tests/test_reqloop_frozen_anchors.py"
            )
        )
        == 6
    )


def test_diff_anchor_negative_control(tmp_path: Path) -> None:
    """r1300：check_diff 的 base 必须錨定被測 commit（CI 是 detached checkout）。

    CI（ci.sh）detached checkout 被測 commit，repo 內分支 ref 指向執行時點的 live
    分支 HEAD：worktree 已同步到新 tip 時，舊 commit 自己的 in-scope 檔與 worktree
    不同，舊碼 ref 基 diff 判 0 file differ、OK＝假綠燈（r1300 實證：被測 commit
    ops/STATE.md=v1、兩 ref 皆指 v2 tip → ref 基 0 files OK／HEAD 基 1 file
    BROKEN；H-0 同構：量錯對象得到的綠燈就是漏洞成因；I-4：未測量不是通過）。
    期望行為（r1303 語義更新）：HEAD detached 時 base 錨定 HEAD（被測 commit）；
    另一分支錨定被測 commit 的「同步對應 commit」（同簿記身份）——示例舊 commit
    sha1 在 auto/worker 歷史中存在且內容相同（同步過）→ OK（r1303：量 live tip 判
    BROKEN＝假紅燈，已修；「未同步輪必 BROKEN」的負控制見
    test_diff_sync_counterpart_anchor）；HEAD attached 分支（本地 dev/worktree）
    口徑不變（base=auto/qwen27b）。
    """
    import os
    import subprocess

    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@t",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@t",
    }
    repo = tmp_path / "repo"
    repo.mkdir()

    def git(*args: str) -> None:
        subprocess.run(
            ["git", *args],
            cwd=repo,
            check=True,
            capture_output=True,
            text=True,
            env=env,
        )

    git("init", "-q", "-b", "main")
    (repo / "ops").mkdir()
    (repo / "ops" / "STATE.md").write_text("v1\n", encoding="utf-8")
    git("add", "-A")
    git("commit", "-qm", "c1")
    sha1 = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, check=True,
        capture_output=True, text=True,
    ).stdout.strip()
    (repo / "ops" / "STATE.md").write_text("v2\n", encoding="utf-8")
    git("commit", "-qam", "c2")
    sha2 = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, check=True,
        capture_output=True, text=True,
    ).stdout.strip()
    git("branch", "auto/qwen27b", sha2)
    git("branch", "auto/worker", sha2)
    git("checkout", "-q", "--detach", sha1)  # CI 沙盒：被測 commit＝舊 commit

    mod = _load_freeze_check()
    mod.REPO = repo

    # r1303 語義：被測 commit sha1 的輪次在 auto/worker 歷史中存在且內容相同
    # （sha1 ∈ auto/worker 祖先，簿記身份相同）＝已同步→OK。r1300 口徑（量 live
    # tip）在此判 BROKEN＝假紅燈（r1301 CI 實證）；「該輪從未同步」的負控制另見
    # test_diff_sync_counterpart_anchor（b）。
    mod.results.clear()
    mod.check_diff(branch="auto/worker", name="diff_worker")
    ok, detail = mod.results[-1][1], mod.results[-1][2]
    assert ok, (
        f"被測 commit 的輪次已同步、分支已前進，仍判 BROKEN＝假紅燈"
        f"（量 live tip 而非同步對應 commit）: {detail}"
    )

    # 正控制：被測 commit 與 worktree 同步 → OK（守衛未過緊）。
    mod.results.clear()
    git("checkout", "-q", "--detach", sha2)
    mod.check_diff(branch="auto/worker", name="diff_worker")
    ok, detail = mod.results[-1][1], mod.results[-1][2]
    assert ok, f"被測 commit 與 worktree 同步卻判 BROKEN（過緊）: {detail}"

    # attached-HEAD 控制（本地 dev/worktree 口徑不變）：base=auto/qwen27b、判旧同。
    mod.results.clear()
    git("checkout", "-q", "auto/qwen27b")
    mod.check_diff(branch="auto/worker", name="diff_worker")
    ok, detail = mod.results[-1][1], mod.results[-1][2]
    assert ok, f"attached-HEAD 口徑改變（期望 base=auto/qwen27b）: {detail}"


def _mk_repo(tmp_path: Path, name: str) -> tuple:
    """凍結沙盒 git repo，回傳 (repo, git, sha)（同 test_diff_anchor_negative_control 口徑）。"""
    import os
    import subprocess

    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@t",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@t",
    }
    repo = tmp_path / name
    repo.mkdir()

    def git(*args: str) -> None:
        subprocess.run(
            ["git", *args],
            cwd=repo,
            check=True,
            capture_output=True,
            text=True,
            env=env,
        )

    def sha() -> str:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=repo, check=True,
            capture_output=True, text=True,
        ).stdout.strip()

    git("init", "-q", "-b", "main")
    (repo / "ops").mkdir()
    return repo, git, sha


def test_diff_sync_counterpart_anchor(tmp_path: Path) -> None:
    """r1303（vq-el4.46）：check_diff 必須把另一分支錨定「被測 commit 的同步對應 commit」。

    r1300 把 base 錨定被測 commit，但仍對另一分支的 live tip diff；分支 tip 每輪前進——
    已正確同步的舊 commit 一旦分支前進必 diff≠0→假紅燈（r1301 CI 實證：被測
    r1301@bd93d42e2、worker tip 已進 r1301 redo→2 in-scope file differ BROKEN、2 failed；
    該輪實際同步乾淨：三分支 4 簿記檔 blob 全同、in-scope diff=0；H-0 同構：量錯對象
    得到的紅燈同样是壞裁決）。期望行為：
      (a) 被測 commit 的輪次已同步到另一分支（存在對應 commit）＋ tip 已前進→OK（不假紅燈）；
      (b) 被測 commit 的輪次從未同步到該分支（無對應 commit）→BROKEN、detail 點名該分支
          （fail-closed；r1296/r1297「同步殘留」缺陷類仍紅燈＝守衛未弱化）；
      (c) 同一被測 commit 對已同步的分支→OK。
    """
    import subprocess

    repo, git, sha = _mk_repo(tmp_path, "synced")
    (repo / "STATE.md").write_text("round1\n", encoding="utf-8")
    (repo / "ops" / "code.py").write_text("v1\n", encoding="utf-8")
    git("add", "-A")
    git("commit", "-qm", "c1")
    (repo / "STATE.md").write_text("round1\nround2\n", encoding="utf-8")
    (repo / "ops" / "code.py").write_text("v2\n", encoding="utf-8")
    git("add", "-A")
    git("commit", "-qm", "c2")  # 被測輪次（round2）
    c2 = sha()
    git("branch", "auto/qwen27b", c2)
    git("branch", "auto/argon", c2)   # round2 已同步
    # round2 同步後，worker 前進到新輪次（tip 不再＝被測 commit）：
    git("checkout", "-qb", "auto/worker", c2)
    (repo / "STATE.md").write_text("round1\nround2\nround3\n", encoding="utf-8")
    (repo / "ops" / "code.py").write_text("v3\n", encoding="utf-8")
    git("add", "-A")
    git("commit", "-qm", "c3-worker")
    # CI 沙盒：被測 commit＝round2（detached）；auto/worker tip＝round3。
    git("checkout", "-q", "--detach", c2)

    mod = _load_freeze_check()
    mod.REPO = repo

    # (a) 假紅燈重現：舊碼（對 live tip diff）在此判 BROKEN（1 file differ: ops/code.py）；
    #     新碼錨定同步對應 commit（c2）→0 differ→OK。
    mod.results.clear()
    mod.check_diff(branch="auto/worker", name="diff_worker")
    ok, detail = mod.results[-1][1], mod.results[-1][2]
    assert ok, (
        f"被測 commit 的輪次已正確同步、另一分支已前進，仍判 BROKEN＝假紅燈"
        f"（量 live tip 而非同步對應 commit）: {detail}"
    )

    mod.results.clear()
    mod.check_diff(branch="auto/argon", name="diff_argon")
    ok, detail = mod.results[-1][1], mod.results[-1][2]
    assert ok, f"已同步分支卻判 BROKEN（過緊）: {detail}"

    # (b) 負控制：該輪從未同步到該分支（無同步對應 commit）→必 BROKEN、點名分支。
    repo2, git2, sha2 = _mk_repo(tmp_path, "unsynced")
    (repo2 / "STATE.md").write_text("round1\n", encoding="utf-8")
    (repo2 / "ops" / "code.py").write_text("v1\n", encoding="utf-8")
    git2("add", "-A")
    git2("commit", "-qm", "d1")
    (repo2 / "STATE.md").write_text("round1\nround2\n", encoding="utf-8")
    (repo2 / "ops" / "code.py").write_text("v2\n", encoding="utf-8")
    git2("add", "-A")
    git2("commit", "-qm", "d2")  # 被測輪次（round2）只在 qwen27b
    d2 = sha2()
    git2("branch", "auto/qwen27b", d2)
    git2("branch", "auto/argon", d2)   # 已同步
    git2("branch", "auto/worker", "HEAD~1")  # 停在 round1＝從未同步 round2（r1296/r1297 缺陷類）
    git2("checkout", "-q", "--detach", d2)

    mod.REPO = repo2
    mod.results.clear()
    mod.check_diff(branch="auto/worker", name="diff_worker")
    ok, detail = mod.results[-1][1], mod.results[-1][2]
    assert not ok, (
        "被測輪次從未同步到 auto/worker 卻判 OK＝假綠燈（守衛弱化）"
    )
    assert "auto/worker" in detail, f"detail 應點名分支: {detail}"

    # (c) 同一被測 commit、已同步分支→OK。
    mod.results.clear()
    mod.check_diff(branch="auto/argon", name="diff_argon")
    ok, detail = mod.results[-1][1], mod.results[-1][2]
    assert ok, f"已同步分支卻判 BROKEN（過緊）: {detail}"

    # 恢復 git helper 的 cwd（module REPO 已被測試覆寫，無需還原；僅清理 detached HEAD）。
    subprocess.run(
        ["git", "checkout", "-q", "auto/qwen27b"],
        cwd=repo2, check=True, capture_output=True, text=True,
    )


def _mk_3wt_repo(tmp_path: Path, name: str) -> tuple:
    """三分支 worktree 沙盒 repo（r1309、審查指示 #3）：主 worktree（auto/qwen27b）＋
    auto/worker、auto/argon 兩 linked worktree，全 clean。
    回傳 (repo, git, wt_worker, wt_argon)。"""
    import os
    import subprocess

    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@t",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@t",
    }
    repo = tmp_path / name
    (repo / "ops" / "reqloop").mkdir(parents=True)
    (repo / "ops" / "reqloop" / "x.py").write_text("x = 1\n", encoding="utf-8")

    def git(*args: str) -> None:
        subprocess.run(
            ["git", *args], cwd=repo, check=True,
            capture_output=True, text=True, env=env,
        )

    git("init", "-q", "-b", "auto/qwen27b")
    git("add", "ops")
    git("commit", "-qm", "c1")
    wt_w = tmp_path / f"{name}-worker"
    wt_a = tmp_path / f"{name}-argon"
    git("worktree", "add", "-q", "-b", "auto/worker", str(wt_w))
    git("worktree", "add", "-q", "-b", "auto/argon", str(wt_a))
    return repo, git, wt_w, wt_a


def test_worktree_clean_negative_controls(tmp_path: Path) -> None:
    """r1309（審查指示 #3 機械化）：規範三分支 worktree in-scope 無殘留。

    本輪實證洞（舊碼、主 repo live）：in-scope 殘留
    `?? ops/reqloop/zz_scratch_r1309.txt` 存在時，舊 freeze_check（9 項）仍輸出
    VERDICT: FROZEN_STATE_OK rc=0＝假綠燈（審查指示 #3：「嚴禁 staged 未 commit
    殘留引發 in-scope diff 導致 CI live 測試紅燈」；H-0 同構：漏檢查項得到的綠燈
    就是洞的成因；I-4：未測量不是通過）。期望行為：
      (a) 三 worktree 全 clean→OK、detail 點名三分支；
      (b) 主 worktree in-scope staged 未 commit→BROKEN 且點名該檔；
      (c) worker worktree 未追蹤 in-scope 檔→BROKEN 且點名該檔；
      (d) 規範 worktree 缺（argon）→BROKEN 未測量（fail-closed，I-4）；
      (e) detached（CI 沙盒口徑）clean checkout→OK、scope 收斂到 checkout 本身
          （r1300：CI 量被測 commit；local worktrees 不可達、不冒充已量）；
      (f) detached＋in-scope 殘留→BROKEN（CI 沙盒自身殘留也抓）。
    """
    mod = _load_freeze_check()
    repo, git, wt_w, wt_a = _mk_3wt_repo(tmp_path, "wtc")

    # (a) 三 worktree 全 clean→OK、點名三分支
    mod.results.clear()
    mod.check_worktree_clean(repo)  # type: ignore[attr-defined]
    name, ok, detail = mod.results[-1]
    assert (name, ok) == ("wt_clean", True), mod.results
    assert "auto/qwen27b" in detail and "auto/worker" in detail and "auto/argon" in detail, detail

    # (b) staged 未 commit（modified＋staged）→BROKEN、點名該檔
    (repo / "ops" / "reqloop" / "x.py").write_text("x = 2\n", encoding="utf-8")
    git("add", "ops")
    mod.results.clear()
    mod.check_worktree_clean(repo)  # type: ignore[attr-defined]
    name, ok, detail = mod.results[-1]
    assert (name, ok) == ("wt_clean", False), mod.results
    assert "x.py" in detail, detail
    git("reset", "-q", "--hard")  # 恢復 clean、讓 (c) 獨立

    # (c) worker worktree 未追蹤 in-scope 檔→BROKEN、點名該檔
    (wt_w / "ops" / "scratch.txt").write_text("scratch\n", encoding="utf-8")
    mod.results.clear()
    mod.check_worktree_clean(repo)  # type: ignore[attr-defined]
    name, ok, detail = mod.results[-1]
    assert (name, ok) == ("wt_clean", False), mod.results
    assert "scratch.txt" in detail, detail
    (wt_w / "ops" / "scratch.txt").unlink()

    # (d) 規範 worktree 缺（argon）→BROKEN 未測量（I-4）
    git("worktree", "remove", "--force", str(wt_a))
    mod.results.clear()
    mod.check_worktree_clean(repo)  # type: ignore[attr-defined]
    name, ok, detail = mod.results[-1]
    assert (name, ok) == ("wt_clean", False), mod.results
    assert "auto/argon" in detail, detail

    # (e)(f) detached（CI 沙盒口徑）
    import os
    import subprocess

    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
        "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t",
    }
    repo2 = tmp_path / "wtc-detached"
    (repo2 / "ops").mkdir(parents=True)
    (repo2 / "ops" / "y.py").write_text("y = 1\n", encoding="utf-8")

    def git2(*args: str) -> None:
        subprocess.run(
            ["git", *args], cwd=repo2, check=True,
            capture_output=True, text=True, env=env,
        )

    git2("init", "-q", "-b", "master")
    git2("add", "ops")
    git2("commit", "-qm", "c1")
    git2("checkout", "-q", "--detach")
    mod.results.clear()
    mod.check_worktree_clean(repo2)  # type: ignore[attr-defined]
    name, ok, detail = mod.results[-1]
    assert (name, ok) == ("wt_clean", True), mod.results
    assert "checkout" in detail, f"detached detail 必須點名 scope: {detail}"
    (repo2 / "ops" / "z.txt").write_text("z\n", encoding="utf-8")
    mod.results.clear()
    mod.check_worktree_clean(repo2)  # type: ignore[attr-defined]
    name, ok, detail = mod.results[-1]
    assert (name, ok) == ("wt_clean", False), mod.results
    assert "z.txt" in detail, detail


# ── r1319（2026-11-09）：守衛內容 hash 錨（同名 dummy 守衛假綠燈，r1314 之後一步）──
# 缺陷實測（本輪 RED）：tests/test_reqloop_frozen_anchors.py 被換成 5 個「期望真名」的
# assert True dummy（全綠、rc=0、計數=5、身份齊）時，freeze_check 仍判
# ('anchors', True, …)=假綠燈；ci_contract 2 測同型。本檔案既有 fixture
# （test_guard_suite_count_negative_controls (b)、test_guard_suite_identity_negative_controls
# (b)/(d)）曾字面編碼「同名 dummy → OK」的期望——那正是缺口：r1314 身份守衛防「改名」，
# 防不了「同名換內容」。且四份守衛檔（freeze_check.py／anchors／ci-contract／本檔）的
# 內容此前無任何 hash 錨點（filing 只釘 extract/checks/run_eval 三份、anchor 只釘
# repair/extract 兩份）——H-0 同型（綠燈來自沒量該量的）、I-4（未測量不是通過）。
# 本節把三份守衛檔（ ruler freeze_check.py ＋ 它 invoke 的兩份守衛）的內容 sha256 固化成
# 錨點；解冻（含合法修改）必須顯式更新 GUARD_CONTENT_PIN 並留記錄——與
# test_reqloop_frozen_anchors.py 的紀律一致（「解冻須顯式改本測試並留記錄」）。
# 殘留（誠實記錄）：本檔自身不釘（自釘是循環：驗自己的檔可連期望值一起改）；該層的
# 獨立信號＝CI 套件 passed 計數（落 ~/dev/ops/ci/*.json，本檔被刪/被削即計數可見地掉）
# ＋ 三分支 in-scope diff（跨分支不同步的篡改被凍結狀態複核抓住）。

GUARD_CONTENT_PIN = {
    # r1321 解冻記錄：freeze_check.py check_g3gate 加 cmd 注入參數（預設＝真命令，
    # 行為逐位不變）以補上 10 項中唯一缺失的紅路負控制——顯式更新錨並留記錄。
    # r1324 解冻記錄：freeze_check.py anchors/ci_contract 身份守衛的通過名收集改為
    # _parse_passed_names（只認「short test summary info」段＋nodeid 須含測試檔名）——
    # 堵 r1324 RED 實證的 print 偽造 summary 行假綠燈（3 真名＋2 print 偽造 dummy
    # 檔，舊碼判 ('anchors', True, '身份齊；expected 5 passed, got 5')；r1296/r1314
    # 同族：計數守住身份未守）。真守衛檔（全綠）仍 OK（測試檔正控制 (c)）；計數/
    # 其它結果類守衛不變，只收緊身份集來源——顯式更新錨並留記錄。
    # r1327 解冻記錄：freeze_check.py 身份集段首改為「最後一處」short test summary
    # info 標頭行（_passed_lines）＋計數錨（段內 PASSED 行數 == passed，_check_guard_suite）
    # ——堵 r1327 RED 實證的「dummy print 偽標頭＋偽 PASSED 行」假綠燈（3 真名＋2 偽名
    # dummy 檔，舊碼判 ('anchors', True, '身份齊；expected 5 passed, got 5；…')；
    # r1296/r1314/r1324 同族）。真守衛檔（全綠）仍 OK（測試檔正控制 (c)）；計數/其它
    # 結果類守衛不變，只收緊段首＋加計數錨——顯式更新錨並留記錄。
    "ops/reqloop/freeze_check.py":
        "1d7841ad8749ec30b59ff637a2fbb8b11d8bbfc087fe95660183c9ee7558a1e9",
    "tests/test_reqloop_frozen_anchors.py":
        "90d686e3ec2de1c868e3e475d8abb96f63f8a22a7bc747d9898dd1a3ecdf780b",
    "tests/test_reqloop_ci_contract.py":
        "eafe829013f15de0e0933aad879ea40381f6239873ce885926951ea699b69d58",
}


def guard_content_violations(root: Path) -> list[str]:
    """三份守衛檔內容 vs GUARD_CONTENT_PIN 的違規清單；空列表＝逐位吻合。

    只讀受測檔，不寫任何共享狀態；root 為 repo 根（真 repo 或臨時 repo）。
    """
    import hashlib

    out: list[str] = []
    for rel, want in GUARD_CONTENT_PIN.items():
        p = root / rel
        if not p.is_file():
            out.append(f"守衛檔不存在: {rel}")
            continue
        got = hashlib.sha256(p.read_bytes()).hexdigest()
        if got != want:
            out.append(
                f"守衛內容漂移 {rel}: 期望 {want[:8]}, 實際 {got[:8]}"
                "（同名 dummy／stub 換檔？合法修改須顯式更新 GUARD_CONTENT_PIN 並留記錄）"
            )
    return out


def test_guard_content_pin_green_and_negative_controls(tmp_path: Path) -> None:
    """守衛內容錨（r1319）：
    (a) 綠燈：真 repo 三份守衛檔與 GUARD_CONTENT_PIN 逐位吻合；
    (b) anchors 守衛檔被換成同名 dummy（5×assert True，恰為 freeze_check 期望真名）
        → 必須判內容漂移（r1314 之前的假綠燈，本輪起必須紅），且未改檔不得誤判；
    (c) ruler freeze_check.py 被換成直接印 FROZEN_STATE_OK 的 stub → 必須判漂移；
    (d) ci_contract 同名 dummy（2×assert True）→ 必須判漂移。
    全部對臨時 repo 操作，不碰真檔；無 subprocess 片段（不觸及安裝合約掃描範圍）。"""
    import hashlib

    # (a) 真 repo 綠燈
    v = guard_content_violations(REPO)
    assert v == [], f"三份守衛檔內容須與 GUARD_CONTENT_PIN 吻合（解冻須顯式更新錨並留記錄）: {v}"

    def fake_repo() -> Path:
        root = tmp_path / "repo"
        for rel in tuple(GUARD_CONTENT_PIN):
            dst = root / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes((REPO / rel).read_bytes())
        return root

    expected_anchors_names = (
        "test_repair_py_is_frozen",
        "test_extract_py_boundary_is_frozen",
        "test_guard_detects_tampered_copy",
        "test_g25_filing_code_hashes_match_repo",
        "test_filing_guard_detects_drift",
    )
    expected_ci_names = (
        "test_reqloop_tests_never_execute_non_contract_imports",
        "test_guard_negative_control_scipy_numpy_flagged",
    )

    # (b) anchors 同名 dummy → 必須判漂移；ruler／ci_contract 未改不得誤判
    root_b = fake_repo()
    (root_b / "tests" / "test_reqloop_frozen_anchors.py").write_text(
        "\n".join(f"def {n}():\n    assert True\n" for n in expected_anchors_names),
        encoding="utf-8",
    )
    v = guard_content_violations(root_b)
    assert any("test_reqloop_frozen_anchors.py" in s and "內容漂移" in s for s in v), \
        f"同名 dummy 守衛檔未被抓到（r1314 假綠燈缺口）: {v}"
    assert not any("freeze_check.py" in s for s in v), f"未改檔被誤判: {v}"
    assert not any("test_reqloop_ci_contract.py" in s for s in v), f"未改檔被誤判: {v}"

    # (c) ruler 被換成 stub（直接印 FROZEN_STATE_OK、10 項全 OK 的假裁決）→ 必須判漂移
    root_c = fake_repo()
    (root_c / "ops" / "reqloop" / "freeze_check.py").write_text(
        "def main():\n    print('VERDICT: FROZEN_STATE_OK')\n\nmain()\n", encoding="utf-8"
    )
    v = guard_content_violations(root_c)
    assert any("freeze_check.py" in s and "內容漂移" in s for s in v), \
        f"stub ruler 未被抓到: {v}"
    assert not any("test_reqloop_frozen_anchors.py" in s for s in v), f"未改檔被誤判: {v}"

    # (d) ci_contract 同名 dummy → 必須判漂移
    root_d = fake_repo()
    (root_d / "tests" / "test_reqloop_ci_contract.py").write_text(
        "\n\n".join(f"def {n}():\n    assert True\n" for n in expected_ci_names),
        encoding="utf-8",
    )
    v = guard_content_violations(root_d)
    assert any("test_reqloop_ci_contract.py" in s and "內容漂移" in s for s in v), \
        f"同名 dummy ci_contract 守衛未被抓到: {v}"
    assert not any("freeze_check.py" in s for s in v), f"未改檔被誤判: {v}"


# r1321（2026-11-09）：g3gate_plan 是 10 項 mandated 檢查中唯一沒有負控制的一項。
# repo 自身紀律（r1261 起各守衛輪、verify_run_receipts.py「先跑負控制」）：必須先
# 證明守衛會紅，綠燈才算數。check_g3gate 的綠燈＝rc==0 且 "NOT FIRED" 且
# "G3GATE PLAN OK"——三者缺一必須 BROKEN（I-4：未測量不是通過；r1288 null-sha
# 同型：綠燈須來自全部條件，不是子集）。舊簽名無注入點（命令硬編碼），本測試
# 先紅（TypeError: unexpected keyword argument 'cmd'）→ 最小修改＝check_g3gate
# 加 cmd 參數（預設＝真命令，main() 行為逐位不變）。fake g3gate＝純 print 腳本：
# 0 模型呼叫、無網路、不觸真 g3gate 模組（紅線：G3 未 --fire）。

def test_g3gate_red_path_negative_controls(tmp_path: Path) -> None:
    """g3gate_plan 紅路負控制（r1321）：
    (a) rc=0 但只印 NOT FIRED（缺 G3GATE PLAN OK）→ 必須 BROKEN；
    (b) rc=0 但只印 G3GATE PLAN OK（缺 NOT FIRED）→ 必須 BROKEN；
    (c) 兩個 marker 都在但 rc=1 → 必須 BROKEN；
    (d) 正控制：rc=0＋兩 marker 齊 → OK（修復不得破壞正常路徑）。
    全對臨時 repo 操作，不碰真檔；detail 須點名三條件各自真偽。"""
    mod = _load_freeze_check()
    repo = tmp_path / "repo"
    repo.mkdir()
    mod.REPO = repo  # type: ignore[attr-defined]

    def fake(name: str, body: str) -> Path:
        p = tmp_path / name
        p.write_text(body, encoding="utf-8")
        return p

    cases = (
        ("only_not_fired.py", "print('NOT FIRED')\n",
         False, "NOT_FIRED=True PLAN_OK=False"),
        ("only_plan_ok.py", "print('G3GATE PLAN OK')\n",
         False, "NOT_FIRED=False PLAN_OK=True"),
        ("both_rc1.py",
         "import sys\nprint('NOT FIRED')\nprint('G3GATE PLAN OK')\nsys.exit(1)\n",
         False, "NOT_FIRED=True PLAN_OK=True"),
        ("both_rc0.py", "print('NOT FIRED')\nprint('G3GATE PLAN OK')\n",
         True, "NOT_FIRED=True PLAN_OK=True"),
    )
    for name, body, expect_ok, expect_flags in cases:
        script = fake(name, body)
        mod.results.clear()  # type: ignore[attr-defined]
        mod.check_g3gate(cmd=[sys.executable, str(script)])  # type: ignore[attr-defined]
        got = mod.results[-1]  # type: ignore[attr-defined]
        assert got[0] == "g3gate_plan", (name, mod.results)
        assert got[1] is expect_ok, \
            f"{name}: 期望 ok={expect_ok}，實際 ok={got[1]} —— {mod.results}"
        assert "rc=" in got[2] and expect_flags in got[2], \
            f"{name}: detail 未點名三條件各自真偽 —— {mod.results}"
