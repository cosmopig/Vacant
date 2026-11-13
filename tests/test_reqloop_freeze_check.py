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
    "queue_empty",    # 審查指示 #5：人類核准前 /srv/vlab/queue/ 必須為空（r1339）
    "bk_state",       # 審查指示 #3 工作樹衛生：STATE.md 簿記鏡像同步（r1271 起）
    "bk_now",         # 審查指示 #3 工作樹衛生：NOW.md 簿記鏡像同步（r1271 起）
    "wt_clean",       # 審查指示 #3 工作樹衛生：規範三分支 worktree in-scope 無殘留（r1309）
    "now_redline",    # r1393（vq-el4.81）：NOW.md 紅線契約行 vs 磁碟，進一鍵 ruler（11→12 項）
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
# 本節把守衛檔（ ruler freeze_check.py ＋ 它 invoke 的兩份守衛；r1347 起再加第二收口
# 標準 verify_effects_summary.py＋其測試檔）的內容 sha256 固化成錨點；解冻（含合法修改）
# 必須顯式更新 GUARD_CONTENT_PIN 並留記錄——與
# test_reqloop_frozen_anchors.py 的紀律一致（「解冻須顯式改本測試並留記錄」）。
# r1347（vq-el4.56）擴覆蓋記錄：審查指示 #3 點名的第二收口指令 verify_effects_summary.py
# （r1333 vq-el4.53）與其測試檔（r1344）建於 r1319 之後、從未釘住——同名 dummy＋stub
# 場景＝r1319 同型假綠燈（本輪 RED 實證：v==[]）。兩檔不含 pin 本身（無自釘循環），
# 故補釘。此後任何對兩檔的合法修改均須顯式更新錨並留記錄。
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
    # r1339 解冻記錄：freeze_check.py 新增 check_queue_empty（/srv/vlab/queue/ 人類
    # 核准前必須為空，審查指示 #5 機械化；r1309/r1321 同型：把人工紅線機械化）——
    # g3gate_plan 只驗「未發射」、不驗「queue 是否有任務」，本輪補上該缺口；queue
    # 路徑可注入（CI/沙盒用 tmp_path）。新增一項 mandated 檢查（10→11 項），其餘
    # 十項守衛逐位不變——顯式更新錨並留記錄。
    # r1343 解凍記錄（vq-el4.56）：freeze_check.py check_queue_empty 收緊——r1339 首版以
    # `startswith(".")` 跳過隱藏條目，非空 queue（僅隱藏檔）被計成「0 任務檔」判 OK＝
    # 假綠燈（r1272 空檔 vacuous、r1288 null-sha 同族；I-4：未測量不是通過；RED 證據
    # 見 test_queue_empty_hidden_entry_negative_control）；本輪改為計數所有條目（含隱藏）
    # 並點名。其餘十項守衛逐位不變——顯式更新錨並留記錄。
    # r1387 解凍記錄（補 r1386 遺漏）：r1386（50b7023c1）合法修改 freeze_check.py——
    # bk_state 訊息單位由 str 字元數改為 UTF-8 位元組數（len(s.encode('utf-8'))），使綠燈
    # 訊息可被 wc -c 複核（CJK 多字位元組下字元數≠位元組數，舊訊息鏡像實 1868B 卻報
    # 1372B＝H-0 同構假綠燈）；檢查邏輯（startswith／行邊界／條目錨點）逐位不變。r1386
    # 改 ruler 後遺漏更新本錨（pin 仍 r1343 之 4f8f669b），致本檔三 GUARD_CONTENT_PIN 測試
    # 轉紅（守衛照設計抓到未記錄的 ruler 改動）；r1386 只跑「5 檔 66 passed」（不含本檔）
    # 故未見紅。本輪按「合法修改須顯式更新錨並留記錄」紀律補錨（不改 ruler、不削守衛）：
    # (1) ops/reqloop/freeze_check.py
    #     4f8f669b2fdb5405172880cf2f8813fe58f000ef9f7c27a96ee07d136172e1fd
    #     → cfbfba31c224756b81e6fdf38d15331e8cd104ad7189399764162f9e274e2f9e
    # r1394 解凍記錄（補 r1393 遺漏，vq-el4.81）：r1393（790368a5e）合法修改
    # freeze_check.py——新增第 12 項 mandated 檢查 now_redline（r1392 紅線轉抄守衛接進
    # 一鍵 ruler、重用 tests/test_reqloop_now_redline.py 之 redline_violations() 為唯一
    # 實現）＋本檔 test_now_redline_green_light／test_now_redline_negative_controls
    # （綠燈 1＋負控 3 路徑）；但 commit 時未更新本 pin（其 docstring「pin 已更新」未
    # 兌現——r1386 同型遺漏，守衛照設計抓到：本檔 3 GUARD_CONTENT_PIN 測試紅）。r1394
    # 依「合法修改須顯式更新錨並留記錄」紀律補 pin（不改 ruler 邏輯、不削守衛；
    # r1393 docstring 虛記同步更正為如實記載）：
    # (1) ops/reqloop/freeze_check.py
    #     42ab72d217d429638125a3bcccb1b9318dca7d4c8b3d75baef6da4e0120c39d5
    #     → a83cb2df864e93a84673f41271cb4f43fc8a4f6130d12c51845cf44c39a57218
    "ops/reqloop/freeze_check.py":
        "a83cb2df864e93a84673f41271cb4f43fc8a4f6130d12c51845cf44c39a57218",
    # r1546/r1550 解凍記錄（P20261113_0300-3 D3 / 0344-1 D3b、11-13 定案第 3 條：extract.py/checks.py
    # 受控解凍；r1544-r1550 重錨 EXTRACT/CHECKS 凍結點；sha256sum 磁碟實算、非轉抄）：
    #   tests/test_reqloop_frozen_anchors.py
    #     90d686e3ec2de1c868e3e475d8abb96f63f8a22a7bc747d9898dd1a3ecdf780b
    #     → 27c0c1245fc76ef5053363067c436a6e9a2c38c885b1d95219b1c6407ce63156
    "tests/test_reqloop_frozen_anchors.py":
        "27c0c1245fc76ef5053363067c436a6e9a2c38c885b1d95219b1c6407ce63156",
    "tests/test_reqloop_ci_contract.py":
        "eafe829013f15de0e0933aad879ea40381f6239873ce885926951ea699b69d58",
    # r1347（vq-el4.56）擴覆蓋：第二收口標準（審查指示 #3 點名）兩檔——r1319 之後建立、
    # 此前從未釘住；補釘後「腳本 stub＋測試檔同名 dummy」假綠燈場景被本 pin 抓住
    # （RED 證據見 test_guard_content_pin_effects_summary_pair_negative_controls）。
    # r1354 解凍記錄（vq-el4.60）：_phase_internal_check 新增 movement_total 覆核
    # （＝逐格重算 w2r+r2w；OK detail 點名 movement；此前 13→12 仍 7/7 OK rc=0
    # 假綠燈，實測 RED）＋ test 新增 movement_drift 負控制＋REFERENCE 人審錨 13/11
    # （套件 17→18 測）。兩檔合法改動後顯式更新錨：
    # (1) ops/reqloop/verify_effects_summary.py sha256=e6cd3933db60be3e653ec62bbce607e4bf2925e39bf8a4086cfb99b2b2e88c55 → 5b44c3bba4c04767d372ca733967cf29932925370079af1a130e18db63f90583
    # (2) tests/test_reqloop_verify_effects_summary.py sha256=f72e692710c6669f01892bcd4dab4a78c6f9753ef45a2ca45b81100f8e068fb0 → 1dc3713eb9d8da8f20a81eeb56ba6bb8d82825867482fe9e5cf71ebeeb740ebf
    # r1361 解凍記錄（vq-el4.61）：_phase_internal_check 的 mismatch 列表覆核由
    # 「只比長度（n_list==n_false）」收緊為「長度＋內容（cell 名集合）」——
    # 舊碼對「右長度（3）錯內容（3 個 flag=True 格）」仍判 7/7 OK rc=0 假綠燈
    # （本輪 RED 實證：mismatch_content_drift）；同族 r1296/r1314/r1324/r1327/r1350
    # （計數守住、身份未守）。新覆核：mismatch 列表的 cell 名集合 ＝
    # cells_detail 中 flag=False 的格之 cell 名集合（cell=draft-"-"-arm）；
    # 長度檢查保留（重複／懸空名場景的清晰診斷）。＋ test 新增
    # mismatch_content_drift 負控制（套件 18→19 測）。live 檔仍 7/7 OK rc=0。
    # 兩檔合法改動後顯式更新錨：
    # (1) ops/reqloop/verify_effects_summary.py sha256=5b44c3bba4c04767d372ca733967cf29932925370079af1a130e18db63f90583 → 7a49b66c0b69784ec20401280f474450ca9b6866364e355ec933a18e92d8f9a7
    # (2) tests/test_reqloop_verify_effects_summary.py sha256=1dc3713eb9d8da8f20a81eeb56ba6bb8d82825867482fe9e5cf71ebeeb740ebf → 578f73bc5b4f262d2fb935315a460cf4b57b1412eb3f6cef107a79329f729fc2
    "ops/reqloop/verify_effects_summary.py":
        "7a49b66c0b69784ec20401280f474450ca9b6866364e355ec933a18e92d8f9a7",
    "tests/test_reqloop_verify_effects_summary.py":
        "578f73bc5b4f262d2fb935315a460cf4b57b1412eb3f6cef107a79329f729fc2",
    # r1365 解凍記錄（vq-el4.63）：G3 發射前置門對（freeze_check g3gate_plan 所 invoke 的
    # 門模組＋其 22 測測試檔）——r1257（vq-1zf.3）建立、r1319/r1347 建錨時點在後、
    # 從未釘住。攻擊場景（r1319/r1347 同型）：模組換「直接印 NOT FIRED＋G3GATE
    # PLAN OK、exit 0」stub＋測試檔換同名 dummy（22 真名、assert True、CI 計數不變）
    # → 舊 guard_content_violations 回空清單＋freeze_check g3gate_plan 照判 OK（本輪
    # RED 雙實證）＝完整假綠燈（H-0 同構：綠燈來自沒量該量的）。兩檔不含 pin 本身
    # （無自釘循環），故可釘、且必須釘——顯式更新錨並留記錄：
    # (1) vacant_network/reqloop/g3gate.py sha256=a0dd46f20138ff578153b8f5ab42f0d0d1f60e98f016bfd01253ff0a8c669b9b
    # (2) tests/test_reqloop_g3gate.py sha256=87e76f3dec89ff987dc06385c0e1e334c0190edf1e169866df707879c2bad60d
    # r1408 解凍記錄（vq-1zf.7）：check_budget 收緊——manifest 三個數值上限（max_cells/
    # timeout_s_per_round/daily_token_cap）原只要求 >0：manifest 寫 max_cells=999／
    # timeout=3000／cap=2e9 皆被接受（本輪 RED 實證；--plan 對之印 G3GATE PLAN OK
    # 假綠燈），而 boolean/enum 硬欄位（quota_fail_closed 等）早已 fail-closed——
    # 與函式自身 docstring「任何一項缺失/放寬即拒」及 DEFAULT_BUDGET 註解「manifest
    # 可加嚴、不可放寬」矛盾（同族 r1376 UNKNOWN fail-open、r1405 bool 當 int：門
    # 不得信被驗方的自我聲明）。本輪補 MAX_TIMEOUT_S_PER_ROUND=300／
    # MAX_DAILY_TOKEN_CAP=2_000_000 兩常數（MAX_CELLS=12 已有）、check_budget 對
    # 三上限一律「放寬即拒」（與硬欄位同口徑；等於上限不是放寬：live manifest
    # 12/300/2M 仍 PLAN OK rc=0 實測）。＋ test 檔新增 5 測（3 放寬欄位負控＋
    # 1 恰好上限正控＋1 CLI 負控 test_cli_plan_loosened_budget_rc1_not_ok：放寬
    # manifest→RC 1＋G3GATE PLAN FAIL 點名 max_cells；套件 22→27 測）。兩檔合法
    # 改動後顯式更新錨並留記錄：
    # (1) vacant_network/reqloop/g3gate.py sha256=a0dd46f20138ff578153b8f5ab42f0d0d1f60e98f016bfd01253ff0a8c669b9b → f1bd86be6698702ecf3f22fa7c263015f0b2d2c7905146e13e6a9e1a2318ebf2
    # (2) tests/test_reqloop_g3gate.py sha256=87e76f3dec89ff987dc06385c0e1e334c0190edf1e169866df707879c2bad60d → 86bac89dc0c4595140831b5e8b5e1c0744c20e3a9377bf66670ca18fbf3b8134
    # r1429 解凍記錄（票 P20261111_0645-1，G3 首發後檢＋重發＋AMEND-2）：
    # 首發 12 格 1 ok/11 error：8× glm 臂「Stopped: token_limit」（answer prompt
    # input 32609–39266 tok 全部 > glm CLI 預設 --max-tokens 30000＝prompt+
    # completion 總預算——vibe help 原文；擷取 call ~5.7K tok 在內故全成）＋
    # 3× native_pi「pi timed out after 300s」（唯一成功 pi 格用 278s 貼線）。本輪：
    # (1) g3gate.py：新增 MAX_TIMEOUT_S_PER_ROUND_PI=600（AMEND-2：pi 臂每格牆時
    #     cap；600 為新預註冊上限，可加嚴不可放寬）＋DEFAULT_BUDGET 加
    #     timeout_s_per_round_pi＋check_budget fail-closed 驗收（pi 臂在場必須在案、
    #     bool 拒、非 int 拒、放寬拒——r1405/r1408 同口徑）；
    # (2) g3.py：新增 GLM_MAX_TOKENS_TOTAL=60000，GlmChannel 顯式傳 --max-tokens
    #     （選項 a：提升 glm 上限；上限是 CLI 級參數非每帳號設定）＋fire()
    #     per-channel 牆時（pi 臂 600s／glm 臂與擷取 300s）；
    # (3) test_reqloop_g3gate.py：4 新測（600 正控／601 放寬拒／缺失拒／非 int 拒）；
    # (4) test_reqloop_g3.py：2 新測（pi 600s＋glm 300s per-channel 分流；
    #     --max-tokens 顯式傳＋>首發最大 prompt）；
    # (5) test_reqloop_g3_conformance.py：BUDGET_GLM_PI 加 timeout_s_per_round_pi
    #     （與 manifest 同 budget 形）。manifest.json（AMEND-2 條目＋budget 字段）
    #     不在 pin 清單；四凍結檔（freeze_check／anchors／ci_contract／
    #     effects_summary）與 g25 呈報未動：
    # (1) vacant_network/reqloop/g3gate.py sha256=a1b10e2e6e1aee46413d7da914f4e7197f4c3ef18c4d97b37989f9d977573229 → 367d88fef75aed9d8cd968e9b0f99e4443bee5765731ac12f7873e02ed7ba5ab
    # (2) tests/test_reqloop_g3gate.py sha256=86bac89dc0c4595140831b5e8b5e1c0744c20e3a9377bf66670ca18fbf3b8134 → b3ea217739530292642ab7eb6980e6e87aadb9540a259d17f65f4918d0238ab9
    # (3) vacant_network/reqloop/g3.py sha256=2ba95fe5fc49334f2fbe1a6088aa34bc77faf097b0b3d39bb1d0e5b71b762b75 → 189f4e732cf03b0fddbe8fe82dd7b66f60a041d64cf63e29daf97732eb3351f3
    # (4) tests/test_reqloop_g3.py sha256=b07ce47e21f44659066e3c3774c1ca2f9d7082aea57728ce8893749dcd5b6441 → 17c69ec886fc77deabd561e0a131f080a248e268b3b4080553ea43c861b49410
    # (5) tests/test_reqloop_g3_conformance.py sha256=a7507f6a17ea40f1823008589a42e4bf8c38a382b333c99fc90d4494acab346b → e6a6d6d41a1c3b5447fb23abd5e1a71de493556f8e2b9e7d82ab0ff5dab4830b
    "vacant_network/reqloop/g3gate.py":
        "367d88fef75aed9d8cd968e9b0f99e4443bee5765731ac12f7873e02ed7ba5ab",
    "tests/test_reqloop_g3gate.py":
        "b3ea217739530292642ab7eb6980e6e87aadb9540a259d17f65f4918d0238ab9",
    # r1397 擴覆蓋記錄（vq-el4.85）：GUARD_CONTENT_PIN 擴覆蓋——NOW.md 紅線轉抄守衛檔
    # （freeze_check 第 12 項 mandated 檢查 now_redline invoke 其 redline_violations()
    # 為唯一實現）。缺口（本輪 RED 雙實證）：該檔 r1392（vq-el4.80）建立、晚於
    # r1319/r1347/r1365 建錨各輪、從未釘住——vq-el4.63 同型。攻擊場景：同名 stub 換檔
    # （5 真名 assert True＋redline_violations→[]）→ 套件 5 例仍全綠、95 計數不變；
    # 下游實證：真 freeze_check.check_now_redline 對該 stub 判 OK（真 NOW.md 與「紅線
    # 契約行被整行掏空」的 NOW.md 皆判 ('now_redline', True, …)＝完整假綠燈、H-0 同構）。
    # 既有行為級信號（test_now_redline_negative_controls）住在自排除（自釘循環）的
    # test_reqloop_freeze_check.py 內，被 shortcut 同削即 swap 完成；位元組錨不依賴
    # 任何行為輸出、抓一切位元組改動。該檔不含 pin 本身（無自釘循環），故可釘、且
    # 必須釘（r1347 先例明文）：
    # (1) tests/test_reqloop_now_redline.py
    #     新增 pin 6ce235db5165ac82debda8656e870381dd3b5dae52eb17cd59f4f928b3c07f2f
    "tests/test_reqloop_now_redline.py":
        "6ce235db5165ac82debda8656e870381dd3b5dae52eb17cd59f4f928b3c07f2f",
    # r1398 擴覆蓋記錄（vq-el4.86）：GUARD_CONTENT_PIN 擴覆蓋——G3 發射管線對
    # （模組＋其實體紅線守衛檔，審查指示 #1 點名 7 檔之一）。缺口（本輪 RED 雙
    # 實證）：該對 r1373（vq-1zf.6）建檔、晚於 r1319/r1347/r1365 建錨各輪、從未
    # 釘住——vq-el4.63／vq-el4.85 同型。攻擊場景：模組換「直接印 fire 成功」
    # stub＋測試檔換同名 dummy（18 真名 assert True、守衛套件 96 計數不變）→
    # 舊 guard_content_violations 回空清單＝完整假綠燈（H-0 同構）；下游紅線
    # （無核准 RC 2 fail-closed／prompt 無 hidden·scorer／成本缺值 UNKNOWN／
    # 撞額度停）全被掏空。既有行為級信號（18 測）住在被 swap 的檔內、被削即
    # swap 完成；位元組錨不依賴任何行為輸出。該對不含 pin 本身（無自釘循環），
    # 故可釘、且必須釘（r1347/r1365 先例明文）：
    # (1) vacant_network/reqloop/g3.py
    #     新增 pin 220189d274bc4fa236b4638ecfadb5f946d40779d9dbce2acef8c0a411ac22f7
    # (2) tests/test_reqloop_g3.py
    #     新增 pin fbf58421608ef7762ab1a3077bc5f8a854f19821040520ef7a02af59c50dbdcd
    # r1419 解凍記錄（vq-el4.94）：g3.py GlmChannel.call raw usage 計數收緊——舊碼
    # `int(rec.get("total_tokens"))` 把 JSON bool 當 int（false→0＝實際耗 token 的
    # 呼叫記成本 0、true→1）、負數（-100 → QuotaGuard known_tokens 被扣減、日額度
    # 更遲才觸發）、float（截斷）／string（自我聲明文字）全靜默接受＝quota
    # fail-open（本輪 RED 實證：false→0／-100→-100／123.5→123／"123"→123；
    # r1376 同族「工作量的界不得依賴用量恰好被測到」、r1405 strict-int／r1408 預算
    # 同族；門不得信被驗方的自我聲明）。修法：只認嚴格 int≥0，否則 UNKNOWN
    # （None，不填 0）；vibe_calls.jsonl 由外部 glm CLI 寫（實測真形狀即嚴格 int，
    # 如 "total_tokens": 10164），正控制不受影響。test 檔新增 6 測（負控 4：
    # bool／負數／float+string／混合行；正控 2：int 計數／多行加總），g3 檔 18→24。
    # 兩檔合法改動後顯式更新錨：
    # (1) vacant_network/reqloop/g3.py
    #     220189d274bc4fa236b4638ecfadb5f946d40779d9dbce2acef8c0a411ac22f7
    #     → ecac78790351d2ca249f06106eef95da1b8fb6cffa517f013be03743b439dba2
    # (2) tests/test_reqloop_g3.py（新增 r1419 6 測）
    #     fbf58421608ef7762ab1a3077bc5f8a854f19821040520ef7a02af59c50dbdcd
    #     → c036e3cd767e929d691c39674890dfcdba69ebcc05b366ba05a2d3cff72f6f72
    # r1419 解凍記錄（分支 fix/g3-arms-actually-do-what-they-say；G3 三臂名實相符
    # P0 修復，2026-11-11 日報揭示）：舊 G3 管線與預註冊有重大落差——
    # native_pi 只是 ARM_SPECS 名稱＋提示文字（三臂全走 GlmChannel 單回合無工具，
    # 沒有 pi）；full_rloop 的 localized_repair=True 只由「必要答案項 @name[...]
    # 是否出現」的正規表示式實現（格式完整但數字錯誤的草稿完全抓不到）。
    # 本輪合法修改（不改凍結 manifest、不加寬任何預算）：
    # (1) g3.py：加 ARM_WIRED/ARM_REQUIRED＋arm_conformance 門（臂與預註冊定義
    #     不符→RC 3、0 模型呼叫；核准過了也不發）；full_rloop 真正接上
    #     checks.run_requirement_checks 程式重算（每輪重驗、reverify_all）、
    #     build_repair_feedback（FAIL-only localized 反饋，不含重算期望值）、
    #     repair.diff_results 差異；required_answer_names 修掉契約範本
    #     placeholder `@name[value]` 被誤算必要項的恆真假缺口；--fire 門序＝
    #     完整性→核准→臂 conformance。
    # (2) test_reqloop_g3.py：既有 6 測改至新語義（凍結三臂計畫拒發；兩臂
    #     皆接線的計畫 8 格跑通；成本/額度數字隨之更新）。
    # (3) tests/test_reqloop_g3_conformance.py（新增 pin）：抓假守衛檔——
    #     「格式完整但數字錯誤」的草稿必須被抓到（舊管線會放行的缺口，本檔
    #     使其 RED），reqlist_only 不得免費獲得重驗能力；conformance 負控制
    #     （native_pi 拒發、ARM_REQUIRED 不可清空）。新檔與 G3_PAIR 同型
    #     （r1347/r1365/r1398 先例：可釘、且必須釘）。
    # 顯式更新錨並留記錄：
    # (1) vacant_network/reqloop/g3.py
    #     220189d274bc4fa236b4638ecfadb5f946d40779d9dbce2acef8c0a411ac22f7
    #     → 8c91f709fdf840a341bf6d5bcdeac322aa6c4a61e5fe91e6104b0c92794b9214
    # (2) tests/test_reqloop_g3.py
    #     fbf58421608ef7762ab1a3077bc5f8a854f19821040520ef7a02af59c50dbdcd
    #     → 7cd9987e1b2495ae8e038da5fa47bc785a1c0067eccab3dc21c6ba56c587dd5e
    # (3) tests/test_reqloop_g3_conformance.py 新增 pin
    #     390443348660119eae2e2cf932e904ae25a4f9e857f141f7671945e1b19be6ea
    # r1420 解凍記錄（分支 fix/g3-arms-actually-do-what-they-say；AMEND-1
    # 2026-11-11 人類裁決：native_pi 接真 pi、模型用本地的 lms1003qwen）。
    # 在 r1419（G3 三臂名實相符 P0 修復）之上繼續：
    # (1) g3.py：新增 PiChannel（復用 repair.prepare_workspace／
    #     parse_usage_from_log／pin_agent_python 與 adapters pi_build／run_agent；
    #     provider/model＝manifest budget 宣告的本地模型 lms1003qwen/
    #     qwen3.8-27b）＋_ArmChannelRouter（pi 臂→PiChannel、其餘→glm；
    #     同一 QuotaGuard 日額度界）＋build_pi_cell_prompt（pi 用工作區真檔，
    #     不內嵌資料預覽；凍結 instruction 逐字）＋run_g3 pi_channel 注入
    #     檢查（缺注入→G3ArmsNotConformant、0 模型呼叫）；--fire 門序＝
    #     完整性→核准→臂 conformance→pi 通道注入。
    # (2) g3gate.py：check_budget 的 model_entry 改如實宣告白名單
    #     （'glm'｜'glm+local_pi'；native_pi 臂必須宣告 local_pi 入口、
    #     pi_provider/pi_model 必須非空——AMEND-1 fail-closed）；DEFAULT_BUDGET
    #     更新為 ARM_ORDER（含 native_pi）的如實形（glm+local_pi＋pi 欄位）。
    # (3) ops/reqloop/g3_gate/manifest.json：AMEND-1 區塊＋budget 三欄位
    #     （model_entry='glm+local_pi'、pi_provider、pi_model）；arm_defs／
    #     任務清單與逐檔 sha256 全部不變；舊核准作廢、發射前須重新核准。
    # (4) tests/test_reqloop_g3.py：12 格三臂發射回歸（native_pi 走假 pi
    #     通道）＋缺 pi_channel 注入拒發負控。
    # (5) tests/test_reqloop_g3_conformance.py：PiChannel 機制測試（workspace
    #     複本不動原檔、answer.txt 讀回、raw usage 缺值 UNKNOWN、agent 失敗
    #     →G3CallError）＋預算門 AMEND-1 負控（原生 pi 未宣告入口即拒）。
    # 顯式更新錨並留記錄：
    # (1) vacant_network/reqloop/g3.py
    #     8c91f709fdf840a341bf6d5bcdeac322aa6c4a61e5fe91e6104b0c92794b9214
    #     → ced948f47d470e1858d6870e2eb80b30a56fb8d6e32527744ebd360d017cf020
    # (2) tests/test_reqloop_g3.py
    #     7cd9987e1b2495ae8e038da5fa47bc785a1c0067eccab3dc21c6ba56c587dd5e
    #     → f628575570ca887646d1d97c7b15ea968232301e20b9afec1fcada82ae89c00b
    # (3) tests/test_reqloop_g3_conformance.py
    #     390443348660119eae2e2cf932e904ae25a4f9e857f141f7671945e1b19be6ea
    #     → a7507f6a17ea40f1823008589a42e4bf8c38a382b333c99fc90d4494acab346b
    # (4) vacant_network/reqloop/g3gate.py
    #     f1bd86be6698702ecf3f22fa7c263015f0b2d2c7905146e13e6a9e1a2318ebf2
    #     → a1b10e2e6e1aee46413d7da914f4e7197f4c3ef18c4d97b37989f9d977573229
    # r1421 合併記錄（工單 P20261111_0315-1-g3-merge-arm-conformance-amend1）：
    # merge origin/fix/g3-arms-actually-do-what-they-say（d13bac4be P0 修復＋
    # 9327dffb5 AMEND-1，基於 r1418/506ab8545）入 auto/qwen27b。工單衝突準則
    # 「兩邊的解凍記錄都保留」：上方本輪 r1419（vq-el4.94）記錄與分支 r1419/
    # r1420 記錄全數逐字保留。分支基於 r1418、不含本地 r1419 GlmChannel
    # strict-int 修復，故 g3.py 為兩邊 auto-merge（分支 AMEND-1 管線＋本地修復）；
    # test_reqloop_g3.py 同為兩邊 auto-merge（分支新語義＋本地 r1419 6 測）。
    # 工單準則「pin 值＝合併後各檔磁碟實算 sha」——本輪 sha256sum 自磁碟實算、
    # 非轉抄任一分支 pin：
    # (1) vacant_network/reqloop/g3.py
    #     ced948f47d470e1858d6870e2eb80b30a56fb8d6e32527744ebd360d017cf020
    #     （分支 r1420 記錄之末值）→ 2ba95fe5fc49334f2fbe1a6088aa34bc77faf097b0b3d39bb1d0e5b71b762b75
    # (2) tests/test_reqloop_g3.py
    #     f628575570ca887646d1d97c7b15ea968232301e20b9afec1fcada82ae89c00b
    #     （分支 r1420 記錄之末值）→ b07ce47e21f44659066e3c3774c1ca2f9d7082aea57728ce8893749dcd5b6441
    # (3) tests/test_reqloop_g3_conformance.py／g3gate.py／test_reqloop_g3gate.py
    #     未受本地改動影響，磁碟實算與分支記錄值吻合（a7507f6a…/a1b10e2e…/
    #     86bac89d…）。
    # r1435 解凍記錄（工單 P20261111_0840-1 項 1；AMEND-3
    # ops/approvals/g3_vq-1zf_fire_20261111_AMEND3.json 人類核准；分支
    # auto/qwen27b）：g3.py build_cell_prompt（round 1 與 round>=2 修復輪共用）
    # 頂部加顯式無工具覆寫 NO_TOOL_OVERRIDE（工單指定文句：「此任務文本原為
    # 工具使用者所寫；你沒有任何工具。不要讀檔、不要寫檔，僅依下文給出的任務與
    # 資料，在第一則訊息直接輸出全部 @name[值] 答案行」）——修 fire a/b 之 glm 臂
    # 8/8 turn_limit（agent 式任務文本撞 --max-turns 1 --enabled-tools none）；
    # 臂段指令／manifest／預算逐位不變；不改 ~/.local/bin/glm。
    # test_reqloop_g3.py 加 2 測（負控制 1：現版 prompt 無覆寫＝紅、修法後綠；
    # 正控制 1：覆寫存在且在任務文本之前、round 1 與 2 都在頂部），g3 檔 24→26。
    # sha256 本輪 sha256sum 自磁碟實算、非轉抄：
    # (1) vacant_network/reqloop/g3.py
    #     189f4e732cf03b0fddbe8fe82dd7b66f60a041d64cf63e29daf97732eb3351f3
    #     → c875ca69d221d92ad4a1753f2ccf3a926a59e662d4c86a5eb70b0cbe1186a581
    # (2) tests/test_reqloop_g3.py（新增 2 測）
    #     17c69ec886fc77deabd561e0a131f080a248e268b3b4080553ea43c861b49410
    #     → f462ac61704637ff33c0e6f9142080b630ec0c8ba9fb1afe3a187b886b3d8c74
    # r1436 解凍記錄（工單 P20261111_0840-1 項 2；AMEND-3
    # ops/approvals/g3_vq-1zf_fire_20261111_AMEND3.json 人類核准；分支
    # auto/qwen27b）：QuotaGuard max_calls 後備上限重測——舊公式
    # n_tasks + arms×n_tasks×max_rounds 把「一次 pi session」當 1 call，但
    # PiChannel.call 的 RoundUsage.calls＝session 內部實際 API 呼叫數
    # （工具迴圈：讀任務檔、寫 answer.txt），QuotaGuard 累計的就是它；
    # 4 題×3 臂舊式＝28 < fire b 實際 31（raw totals.model_calls：pi 4 格
    # 7+8+7+5＝27＋extract 4；ops/g3_fire_20261111b/g3_result.json）→
    # guard 中途假停（2 格 not_run/quota、非 token 額度）。修法：新常數
    # PI_SESSION_CALL_CAP＝8（實測 pi 單 session max，fire b dab_144；fire a
    # dab_129＝7）＋max_calls_bound()＝n_tasks＋Σ臂 n_tasks×max_rounds×
    # （pi 8｜非 pi 1）——c 計畫 4 題×3 臂＝4+32+4+8＝48≥31；仍為嚴上界、
    # fail-closed 語義不變（撞上界＝停、不重試）；無 pi 臂計畫每輪＝1 call
    # （既有形狀）。理由＋算式寫回票面與 commit 訊息（AMEND-3：不得靜默
    # 放寬）。test_reqloop_g3.py 加 3 測（負控制 1：pi 臂在場上界須≥8——對
    # 舊式必紅；正控制 2：≥fire b 實際 31／算式精確值 48 與無 pi 16），
    # g3 檔 26→29。sha256 本輪 sha256sum 自磁碟實算、非轉抄：
    # (1) vacant_network/reqloop/g3.py
    #     c875ca69d221d92ad4a1753f2ccf3a926a59e662d4c86a5eb70b0cbe1186a581
    #     → 5a94c1676958e7203bc41ec75a9f2c42cfd1b38812ba70d4e4274fc864dc358e
    # (2) tests/test_reqloop_g3.py（新增 3 測）
    #     f462ac61704637ff33c0e6f9142080b630ec0c8ba9fb1afe3a187b886b3d8c74
    #     → 3ed315e37f4fe05f705352f34a6911b6b9e20db95586670fe9744145bfbc8259
    # r1443 解凍記錄（票 P20261111_1152-1；分支 auto/qwen27b）：g3.py
    # unverified 原因持久化——G3 fire c 26/26 required claims 全 UNKNOWN、
    # evidence 只有 {"unverified": true}，extract.py 的逐條原因（如
    # unknown_verifier:missing）被 g3.py 丟棄、收案無法歸因。修法：run_g3
    # 擷取段把 report.unverified 存進 trec["unverified_reasons"]（base dict
    # 初始化 {}，quota 停止路徑亦在）；_claim_records 加可選參數
    # unverified_reasons，evidence.unverified=true 且 claim_id 在映射內時
    # 注入 evidence["reason"]（另建 dict、原 ClaimResult 不改動；無映射
    # 時行為逐位不變＝負控制）。凍結四檔未動、0 model calls。test_reqloop_g3.py
    # 加 1 測（test_unverified_reasons_persisted：負控制舊呼叫形狀無 reason
    # ＋正控制 reason 逐條一致＋end-to-end 假通道 trec/claims 皆有原因），
    # g3 檔 29→30。sha256 本輪 sha256sum 自磁碟實算、非轉抄：
    # (1) vacant_network/reqloop/g3.py
    #     5a94c1676958e7203bc41ec75a9f2c42cfd1b38812ba70d4e4274fc864dc358e
    #     → f5fc822e1ec43d34e1ed3864f366501dc15c5d1b6ca5a80a34210baaf7c7e731
    # (2) tests/test_reqloop_g3.py（新增 1 測）
    #     3ed315e37f4fe05f705352f34a6911b6b9e20db95586670fe9744145bfbc8259
    #     → 2168556a5775e68138e636cade988a08f2bd1e1d4740b4b098a48713c82742ca
    # r1459 解凍記錄（票 P20261111_1516-1-g3-input-contract-wiring，審查指示 #2；
    # 分支 auto/qwen27b）：r1450（c79af8cf6）修「擷取使用者原文漏附公開
    # contract.md→deliverable_not_in_request 假陽性」——compose_extract_user_text 改組
    # f"{goal}\n\n{contract}"（合法修改、已核准），但該輪未依紀律更新本 pin（r1393
    # 同型：改 ruler／被釘檔而 pin 未更新；本輪 6 支 guard_content_pin 測試紅＝
    # 守衛照設計抓到，r1394 先例依紀律補齊）。4 凍結題實測 old→new 全轉 None；
    # 凍結四檔未動、0 model calls。sha256 本輪 sha256sum 自磁碟實算、非轉抄：
    # (1) vacant_network/reqloop/g3.py
    #     f5fc822e1ec43d34e1ed3864f366501dc15c5d1b6ca5a80a34210baaf7c7e731
    #     → 24beb4b32a7e3beb7d4f400fc6334629216239a18caa3eeca5773c63183786ba
    # (2) tests/test_reqloop_g3.py
    #     2168556a5775e68138e636cade988a08f2bd1e1d4740b4b098a48713c82742ca
    #     → 7efb8398e73f84f57723d625ca079c014a9d860b58f295ea0ef4ddc488b321bc
    # r1544 解凍記錄（P20261113_0300-2 D2、11-13 定案第 2 條：trusted_deliverable
    # 抽取；r1544-r1547 落盤；sha256sum 磁碟實算、非轉抄）：
    #   vacant_network/reqloop/g3.py
    #     24beb4b32a7e3beb7d4f400fc6334629216239a18caa3eeca5773c63183786ba
    #     → 532a1f89dbb29fd125ac2ea10f3b20e27512364bd5dc64a1fdd23c965b7ae553
    "vacant_network/reqloop/g3.py":
        "532a1f89dbb29fd125ac2ea10f3b20e27512364bd5dc64a1fdd23c965b7ae553",
    "tests/test_reqloop_g3.py":
        "7efb8398e73f84f57723d625ca079c014a9d860b58f295ea0ef4ddc488b321bc",
    "tests/test_reqloop_g3_conformance.py":
        "e6a6d6d41a1c3b5447fb23abd5e1a71de493556f8e2b9e7d82ab0ff5dab4830b",
    # r1401 擴覆蓋記錄（vq-el4.87）：GUARD_CONTENT_PIN 擴覆蓋——CI tip 收口對（工具＋
    # 其 10 測測試檔）r1399 輪（rc=124 殘留）建於 r1319/r1347/r1365/r1397 建錨各輪
    # 之後、從未釘住（r1347 同型：verify_effects_summary 對建於 r1333/r1344、r1347
    # 補釘）。RED 實證（本輪新跑）：工具換「直接印 CI_TIP_OK」stub＋測試檔換同名
    # dummy（10 真名、assert True、CI passed 計數不變）→ 舊 10 檔 pin 回 []（兩檔
    # 不在 pin → 零違規＝假綠燈；H-0 同構：綠燈來自沒量該量的）。兩檔不含 pin 本身
    # （無自釘循環；r1347 先例明文「可釘、且必須釘」）。sha256 皆本輪 sha256sum 自
    # 磁碟實算、非轉抄。
    # r1405 解凍記錄（vq-el4.90）：ci_tip_check.py is_green 收緊——r1399 初版只驗
    # green is True＋failed==0＋errors==0、不驗 passed、計數不驗型：記錄
    # {green:true, passed:0, failed:0, errors:0}（零通過＝未測量任何測試）被判
    # TIP_GREEN→CI_TIP_OK＝假綠燈（本輪 RED 實證：舊碼證據行
    # 「per-sha … green（passed=0 failed=0 skipped=0）」→ CI_TIP_OK rc=0）；
    # {failed:false, errors:false}（json bool，False==0）亦被讀成零失敗＝型混淆同族
    # （I-4「a suite that reported zero tests fails」、r1272 空檔 vacuous、
    # r1296 null-sha 同族；該 ruler 自身 docstring 即引 I-4 跳損毀 json，零計數
    # 記錄同為不可用證據）。修法：is_green 收緊為嚴格 int（排除 bool）——
    # green is True 且 passed int>0 且 failed int==0 且 errors int==0；缺欄位／
    # 錯型／零通過＝非綠（fail-closed）。live 記錄 passed≈5145（int）不受影響
    # （live 判定仍 CI_TIP_OK）。兩檔合法改動後顯式更新錨：
    # (1) ops/reqloop/ci_tip_check.py
    #     9c1aee8e0fa8300c55c7d65316e84fb5f5b4aa2dac7803c49e408713aa61a202
    #     → 18700ff7f4632a56c16619fb8e4eda3b650bdca233b659e6c1e430edfa290089
    # (2) tests/test_reqloop_ci_tip_check.py（新增負控 (h) 雙場景）
    #     3ca4dd545ed9e077e156d5c20e1e83a8a60fdfe148bdd0be049c9665d3f42761
    #     → fb5939bd3da044b7de5af94e0c2fbd5b7b4ca6f47e96deb2952ae705af5a4ab4
    # r1413 解凍記錄（vq-el4.92；佔位 .9x 於 r1414 解析為實際 issue id）：
    # ci_tip_check.py evaluate 收緊——零分支輸入（檢查
    # 量零分支）被舊碼判 CI_TIP_OK rc=0（all([]) 恆真）＝空集綠燈（本輪 RED 實證：
    # `--branches '{}'` → VERDICT: CI_TIP_OK rc=0；I-4 未測量不是通過，r1272 空檔
    # vacuous／r1334 零格同族；移除全部測量對象把判定從 UNKNOWN 升成 OK＝H-0「綠燈
    # 來自沒量該量的」）。修法：evaluate 首守空 branch_wts → BROKEN（vacuous）rc=1
    # fail-closed＋證據點名 vacuous；main 補頂層證據輸出。其餘判定（TIP_GREEN/
    # COVERED/PEER_COVERED/RED/UNKNOWN 與聚合口徑）逐位不變；live 三分支判定仍
    # CI_TIP_OK（正控制實測）。兩檔合法改動後顯式更新錨：
    # (1) ops/reqloop/ci_tip_check.py
    #     18700ff7f4632a56c16619fb8e4eda3b650bdca233b659e6c1e430edfa290089
    #     → c0d41a915a255d128238b36374b5121a09fd2e69606bd245038425f3cf4b027a
    # (2) tests/test_reqloop_ci_tip_check.py（新增負控 (i)）
    #     fb5939bd3da044b7de5af94e0c2fbd5b7b4ca6f47e96deb2952ae705af5a4ab4
    #     → b1b1a9555e38fb0424899db45ca3f61ba794ed2616913eb32d36a594086f6944
    # r1414 解凍記錄（vq-el4.92）：r1413 遺留的佔位「vq-el4.9x」解析為實際 issue id
    # vq-el4.92（ci_tip_check.py 3 處：2 docstring＋1 evidence 字串；純文字、零邏輯改動；
    # evidence 子串 'vacuous' 不變，負控 (i) 仍成立；test_reqloop_ci_tip_check.py 未動，
    # 其錨不變）。顯式更新錨：
    # (1) ops/reqloop/ci_tip_check.py
    #     c0d41a915a255d128238b36374b5121a09fd2e69606bd245038425f3cf4b027a
    #     → 90f3a0ab6506d9399f47c92260318e231e2db29f00a2eda78610e2428bb2267f
    "ops/reqloop/ci_tip_check.py":
        "90f3a0ab6506d9399f47c92260318e231e2db29f00a2eda78610e2428bb2267f",
    "tests/test_reqloop_ci_tip_check.py":
        "b1b1a9555e38fb0424899db45ca3f61ba794ed2616913eb32d36a594086f6944",
}


def guard_content_violations(root: Path) -> list[str]:
    """七份守衛檔內容（r1347 起五份；r1365 擴至七份）vs GUARD_CONTENT_PIN 的違規清單；空列表＝逐位吻合。

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
    """守衛內容錨（r1319；r1347 擴至五份；r1365 擴至七份）：
    (a) 綠燈：真 repo 七份守衛檔與 GUARD_CONTENT_PIN 逐位吻合；
    (b) anchors 守衛檔被換成同名 dummy（5×assert True，恰為 freeze_check 期望真名）
        → 必須判內容漂移（r1314 之前的假綠燈，本輪起必須紅），且未改檔不得誤判；
    (c) ruler freeze_check.py 被換成直接印 FROZEN_STATE_OK 的 stub → 必須判漂移；
    (d) ci_contract 同名 dummy（2×assert True）→ 必須判漂移。
    全部對臨時 repo 操作，不碰真檔；無 subprocess 片段（不觸及安裝合約掃描範圍）。"""
    import hashlib

    # (a) 真 repo 綠燈
    v = guard_content_violations(REPO)
    assert v == [], f"七份守衛檔內容須與 GUARD_CONTENT_PIN 吻合（解冻須顯式更新錨並留記錄）: {v}"

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


# ---------------------------------------------------------------------------
# queue_empty（r1339）：人類核准前 /srv/vlab/queue/ 必須為空（審查指示 #5：
# 核准前嚴禁向 queue 放入新任務）。g3gate_plan 只驗「未發射」，不驗「queue
# 是否有任務」——本檢查把該人工紅線機械化（r1309/r1321 同型；I-4：未測量
# 不是通過）。queue 路徑可注入（CI/沙盒用 tmp_path，不碰真 /srv/vlab/queue/）。
# ---------------------------------------------------------------------------
def test_check_queue_empty_green_and_negative_controls(tmp_path: Path) -> None:
    mod = _load_freeze_check()

    # (a) 正控制：queue 為空目錄 → ok=True。
    empty_q = tmp_path / "qempty"
    empty_q.mkdir()
    mod.results.clear()  # type: ignore[attr-defined]
    mod.check_queue_empty(queue=empty_q)  # type: ignore[attr-defined]
    got = mod.results[-1]  # type: ignore[attr-defined]
    assert got[0] == "queue_empty", mod.results
    assert got[1] is True, f"空 queue 應 ok=True，實際 {got}"

    # (b) 負控制：queue 有一個任務檔 → ok=False（detail 點名該檔）。
    nonempty_q = tmp_path / "qnonempty"
    nonempty_q.mkdir()
    (nonempty_q / "00_smoke.json").write_text("{}", encoding="utf-8")
    mod.results.clear()  # type: ignore[attr-defined]
    mod.check_queue_empty(queue=nonempty_q)  # type: ignore[attr-defined]
    got = mod.results[-1]  # type: ignore[attr-defined]
    assert got[0] == "queue_empty", mod.results
    assert got[1] is False, f"非空 queue 應 ok=False，實際 {got}"
    assert "00_smoke.json" in got[2], f"detail 未點名任務檔 —— {got}"

    # (c) 負控制：queue 不存在 → ok=True（無 queue 即無任務；detail 點名 absent）。
    mod.results.clear()  # type: ignore[attr-defined]
    mod.check_queue_empty(queue=tmp_path / "no_such_queue_dir")  # type: ignore[attr-defined]
    got = mod.results[-1]  # type: ignore[attr-defined]
    assert got[0] == "queue_empty", mod.results
    assert got[1] is True, f"queue 不存在應 ok=True（無任務），實際 {got}"
    assert "absent" in got[2], f"detail 未點名 queue absent scope —— {got}"


def test_queue_empty_hidden_entry_negative_control(tmp_path: Path) -> None:
    """r1343（vq-el4.56）：r1339 的 queue_empty 守衛跳過隱藏項
    （`if not p.name.startswith(".")`）——非空 queue（僅隱藏檔）被計成「0 任務檔」
    判 OK＝假綠燈（r1272 空檔 vacuous、r1288 null-sha 同族；I-4：未測量不是通過）。
    審查指示 #5 紅線是「嚴禁向 /srv/vlab/queue/ 放入新任務」——隱藏任務檔也是任務檔；
    fail-closed：queue 內任何條目（含隱藏）都必須點名 BROKEN。RED 證據（本輪、舊碼）：
    dotfile-only queue → ('queue_empty', True, '…(0 任務檔…')。
    正控制：空目錄仍 OK（守衛未過度收緊）。"""
    mod = _load_freeze_check()

    # 負控制：queue 僅有隱藏條目 → ok=False（detail 點名該隱藏檔）。
    hidden_q = tmp_path / "qhidden"
    hidden_q.mkdir()
    (hidden_q / ".00_smoke_hidden.json").write_text("{}", encoding="utf-8")
    mod.results.clear()  # type: ignore[attr-defined]
    mod.check_queue_empty(queue=hidden_q)  # type: ignore[attr-defined]
    got = mod.results[-1]  # type: ignore[attr-defined]
    assert got[0] == "queue_empty", mod.results
    assert got[1] is False, (
        f"僅隱藏條目的非空 queue 應 ok=False（r1339 跳過隱藏檔＝假綠燈缺口），實際 {got}"
    )
    assert ".00_smoke_hidden.json" in got[2], f"detail 未點名隱藏任務檔 —— {got}"

    # 正控制：空目錄仍 OK（收緊後不得誤判空 queue）。
    empty_q = tmp_path / "qempty2"
    empty_q.mkdir()
    mod.results.clear()  # type: ignore[attr-defined]
    mod.check_queue_empty(queue=empty_q)  # type: ignore[attr-defined]
    got2 = mod.results[-1]  # type: ignore[attr-defined]
    assert got2[0] == "queue_empty", mod.results
    assert got2[1] is True, f"空 queue 應仍 ok=True，實際 {got2}"


# ── r1347（vq-el4.56）：GUARD_CONTENT_PIN 擴覆蓋——第二收口標準（verify_effects_summary 對）──
# 缺口（本輪 RED 實證）：審查指示 #3 點名 verify_effects_summary.py 與 freeze_check.py 為收口
# 兩指令，但 GUARD_CONTENT_PIN（r1319）只釘三份（freeze_check.py＋anchors＋ci_contract）；
# ops/reqloop/verify_effects_summary.py（r1333 vq-el4.53）與
# tests/test_reqloop_verify_effects_summary.py（r1344）建於 r1319 之後、從未釘住。
# 攻擊場景（r1319 同名 dummy 同型）：測試檔換同名 dummy（assert True 全綠）＋腳本換直接印
# VERDICT: EFFECTS_SUMMARY_OK 的 stub → 舊 guard_content_violations 回空清單、收口指令照綠
# ＝假綠燈（H-0 同構：綠燈來自沒量該量的）。此兩檔不含 pin 本身（無自釘循環，與本檔殘留
# 不同），故可釘、且必須釘。

EFFECTS_PAIR = (
    "ops/reqloop/verify_effects_summary.py",
    "tests/test_reqloop_verify_effects_summary.py",
)


def test_guard_content_pin_effects_summary_pair_negative_controls(tmp_path: Path) -> None:
    """r1347（vq-el4.56）：第二收口標準對（腳本＋其測試檔）必須在 GUARD_CONTENT_PIN 內。
    (a) 負控制：腳本換「直接印 VERDICT: EFFECTS_SUMMARY_OK」stub＋測試檔換同名 dummy
        （真名 assert True）→ guard_content_violations 必對兩檔各判內容漂移；
    (b) 正控制：五份守衛檔皆真內容 → 零違規（擴錨後不得誤判未改檔）。
    全部對臨時 repo 操作，不碰真檔；無 subprocess 片段（不觸及安裝合約掃描範圍）。
    RED 證據（本輪、舊錨）：(a) 的 v == []（兩檔不在 pin → 零違規＝假綠燈）。"""

    def fake_repo() -> Path:
        root = tmp_path / "repo"
        for rel in tuple(GUARD_CONTENT_PIN):
            dst = root / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes((REPO / rel).read_bytes())
        return root

    def place(root: Path, content: str) -> None:
        for rel in EFFECTS_PAIR:
            (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / "ops/reqloop/verify_effects_summary.py").write_text(
            "def main():\n    print('VERDICT: EFFECTS_SUMMARY_OK')\n\nmain()\n",
            encoding="utf-8",
        )
        (root / "tests/test_reqloop_verify_effects_summary.py").write_text(content, encoding="utf-8")

    # (a) 腳本 stub＋測試檔同名 dummy（真名、assert True）→ 兩檔都必須被判漂移
    real_names = (
        "test_script_exists",
        "test_live_verdict_ok",
        "test_live_covers_all_mandated",
        "test_live_file_sha_pinned",
    )
    root_a = fake_repo()
    place(root_a, "\n".join(f"def {n}():\n    assert True\n" for n in real_names))
    v = guard_content_violations(root_a)
    assert any("ops/reqloop/verify_effects_summary.py" in s and "內容漂移" in s for s in v), (
        f"verify_effects_summary.py stub 未被抓到（r1319 同型缺口：r1319 後建檔、從未釘住）: {v}"
    )
    assert any("tests/test_reqloop_verify_effects_summary.py" in s and "內容漂移" in s for s in v), (
        f"同名 dummy 測試檔未被抓到: {v}"
    )
    # 未改的既有三份守衛檔不得誤判
    for rel in tuple(GUARD_CONTENT_PIN):
        if rel not in EFFECTS_PAIR:
            assert not any(rel in s for s in v), f"未改檔被誤判: {rel}: {v}"

    # (b) 正控制：五份守衛檔皆真內容 → 零違規
    root_b = fake_repo()
    for rel in EFFECTS_PAIR:
        (root_b / rel).parent.mkdir(parents=True, exist_ok=True)
        (root_b / rel).write_bytes((REPO / rel).read_bytes())
    v_ok = guard_content_violations(root_b)
    assert v_ok == [], f"真內容守衛檔被誤判漂移: {v_ok}"


# ── r1365（vq-el4.63）：GUARD_CONTENT_PIN 擴覆蓋——G3 發射前置門對（g3gate 模組＋其測試檔）──
# 缺口（本輪 RED 實證）：freeze_check 的 g3gate_plan 只驗子程 rc 0＋stdout 含「NOT FIRED」
# ＋「G3GATE PLAN OK」——ruler 所 invoke 的 G3 發射前置門模組 vacant_network/reqloop/g3gate.py
# （r1257 vq-1zf.3）可被換成「直接印該兩行、exit 0」的 stub 而 freeze_check 照判 OK；其測試檔
# tests/test_reqloop_g3gate.py（22 測）可被換同名 dummy（22 真名、assert True）而 CI 套件
# passed 計數不變（5106）——完整假綠燈（H-0 同構：綠燈來自沒量該量的；r1319/r1347 同族：
# 計數守住、身份未守／檔案未守）。GUARD_CONTENT_PIN（r1319；r1347 擴至五份）未覆蓋此兩檔；
# r1347 先例明文：「兩檔不含 pin 本身（無自釘循環），故可釘、且必須釘」——本對同形。
# 獨立信號缺失實證：同名 dummy 保持 CI 計數；loop 每輪自動同步三分支 worktree→跨分支
# diff 信號亦被規避——pin 是唯一能抓此 swap 的守衛。
G3GATE_PAIR = (
    "vacant_network/reqloop/g3gate.py",
    "tests/test_reqloop_g3gate.py",
)


def test_guard_content_pin_g3gate_pair_negative_controls(tmp_path: Path) -> None:
    """r1365（vq-el4.63）：G3 發射前置門對（模組＋其測試檔）必須在 GUARD_CONTENT_PIN 內。
    (a) 負控制：模組換「直接印 NOT FIRED＋G3GATE PLAN OK、exit 0」stub＋測試檔換同名
        dummy（22 真名、assert True、CI 計數不變）→ guard_content_violations 必對兩檔
        各判內容漂移；
    (b) 正控制：七份守衛檔皆真內容 → 零違規（擴錨後不得誤判未改檔）。
    全部對臨時 repo 操作，不碰真檔；無 subprocess 片段（不觸及安裝合約掃描範圍）。
    RED 證據（本輪、舊錨）：(a) 的 v == []（兩檔不在 pin → 零違規＝假綠燈）；
    下游實證：真 freeze_check.check_g3gate 對該 stub 判 OK（rc=0 NOT_FIRED=True
    PLAN_OK=True）——守衛套 v==[]＋ruler 照綠＝完整假綠燈。"""

    def fake_repo() -> Path:
        root = tmp_path / "repo"
        for rel in tuple(GUARD_CONTENT_PIN):
            dst = root / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes((REPO / rel).read_bytes())
        return root

    def place(root: Path, dummy_names: tuple[str, ...]) -> None:
        for rel in G3GATE_PAIR:
            (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / "vacant_network/reqloop/g3gate.py").write_text(
            "print('NOT FIRED（無核准信號；0 model calls）')\n"
            "print('G3GATE PLAN OK')\n",
            encoding="utf-8",
        )
        (root / "tests/test_reqloop_g3gate.py").write_text(
            "\n".join(f"def {n}():\n    assert True\n" for n in dummy_names),
            encoding="utf-8",
        )

    # (a) g3gate 模組 stub＋測試檔同名 dummy → 兩檔都必須被判漂移
    real_names = (
        "test_unseen_selection_matches_preregistration",
        "test_unseen_selection_is_computation_not_hardcode",
        "test_unseen_selection_insufficient_raises",
        "test_plan_load_and_verify_frozen",
        "test_verify_frozen_detects_tampered_sha",
        "test_verify_frozen_detects_missing_file",
        "test_check_budget_accepts_frozen_plan",
        "test_check_budget_rejects_over_cell_cap",
        "test_check_budget_rejects_missing_daily_cap",
        "test_check_budget_rejects_wrong_entry",
        "test_no_leftover_temp_directories_in_tmp",
        "test_approval_gate_rejects_absent_or_invalid",
        "test_approval_gate_accepts_valid",
        "test_cli_plan_rc0_and_not_fired",
        "test_cli_fire_without_approval_rc2_zero_calls",
        "test_cli_fire_with_invalid_approval_rc2",
        "test_build_manifest_selection_hashes_and_roundtrip",
        "test_build_manifest_fail_closed",
        "test_plan_report_machine_readable",
        "test_cli_fire_valid_approval_rc3_approved_not_wired",
        "test_cli_plan_tampered_manifest_rc1_not_ok",
        "test_cli_fire_tampered_manifest_rejected_before_approval",
    )
    root_a = fake_repo()
    place(root_a, real_names)
    v = guard_content_violations(root_a)
    assert any("vacant_network/reqloop/g3gate.py" in s and "內容漂移" in s for s in v), (
        f"g3gate 前置門 stub 未被抓到（r1319/r1347 同型缺口：ruler 所 invoke 的門模組"
        f"從未釘住；freeze_check g3gate_plan 對 stub 照判 OK）: {v}"
    )
    assert any("tests/test_reqloop_g3gate.py" in s and "內容漂移" in s for s in v), (
        f"同名 dummy 測試檔未被抓到: {v}"
    )
    # 未改的既有五份守衛檔不得誤判
    for rel in tuple(GUARD_CONTENT_PIN):
        if rel not in G3GATE_PAIR:
            assert not any(rel in s for s in v), f"未改檔被誤判: {rel}: {v}"

    # (b) 正控制：七份守衛檔皆真內容 → 零違規
    root_b = fake_repo()
    for rel in G3GATE_PAIR:
        (root_b / rel).parent.mkdir(parents=True, exist_ok=True)
        (root_b / rel).write_bytes((REPO / rel).read_bytes())
    v_ok = guard_content_violations(root_b)
    assert v_ok == [], f"真內容守衛檔被誤判漂移: {v_ok}"


# ─────────────────────────────────────────────────────────────────────────────
# r1398（vq-el4.86）：GUARD_CONTENT_PIN 擴覆蓋——G3 發射管線對（g3.py＋其測試檔）
# 缺口（本輪 RED 實證）：G3 發射管線模組 vacant_network/reqloop/g3.py（r1373
# vq-1zf.6）與其實體紅線守衛檔 tests/test_reqloop_g3.py（18 測；無核准→RC 2、
# 0 模型呼叫 fail-closed；prompt 無 hidden/scorer；成本缺值→UNKNOWN 絕不填 0；
# 撞日額度→停、不得重試）皆建於 r1319/r1347/r1365 建錨各輪之後、從未釘住。
# 攻擊場景（r1365 同型）：模組換「直接印 fire 成功」stub＋測試檔換同名 dummy
# （18 真名、assert True）→ 守衛套件 96 計數不變、全綠；真發射時的紅線
# （fail-closed／無 hidden／額度停）被整層掏空＝完整假綠燈（H-0 同構：綠燈
# 來自沒量該量的）。兩檔不含 pin 本身（無自釘循環；r1347/r1365 先例明文：
# 「可釘、且必須釘」）。
# 獨立信號缺失同 r1365：同名 dummy 保持 CI passed 計數；loop 每輪三分支
# 同步→跨分支 diff 信號被規避——pin 是唯一能抓此 swap 的守衛。
G3_PAIR = (
    "vacant_network/reqloop/g3.py",
    "tests/test_reqloop_g3.py",
)


def test_guard_content_pin_g3_pair_negative_controls(tmp_path: Path) -> None:
    """r1398（vq-el4.86）：G3 發射管線對（模組＋其 18 測紅線守衛檔）必須在 GUARD_CONTENT_PIN 內。
    (a) 負控制：模組換「直接印 fire 成功」stub＋測試檔換同名 dummy
        （18 真名、assert True、守衛套件 96 計數不變）→ guard_content_violations
        必對兩檔各判內容漂移；
    (b) 正控制：守衛檔皆真內容 → 零違規（擴錨後不得誤判未改檔）。
    全部對臨時 repo 操作，不碰真檔；無 subprocess 片段（不觸及安裝合約掃描範圍）。
    RED 證據（本輪、舊錨）：(a) 的 v == []（兩檔不在 pin → 零違規＝假綠燈）。"""

    def fake_repo() -> Path:
        root = tmp_path / "repo"
        for rel in tuple(GUARD_CONTENT_PIN):
            dst = root / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes((REPO / rel).read_bytes())
        return root

    def place(root: Path, dummy_names: tuple[str, ...]) -> None:
        for rel in G3_PAIR:
            (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / "vacant_network/reqloop/g3.py").write_text(
            "def fire(*args, **kwargs):\n"
            "    print('G3 FIRED OK（12/12 cells、0 model calls、hidden_after UNKNOWN）')\n",
            encoding="utf-8",
        )
        (root / "tests/test_reqloop_g3.py").write_text(
            "\n".join(f"def {n}():\n    assert True\n" for n in dummy_names),
            encoding="utf-8",
        )

    # (a) g3 模組 stub＋測試檔同名 dummy → 兩檔都必須被判漂移
    real_names = (
        "test_channel_is_abstract_contract",
        "test_arm_specs_match_preregistration",
        "test_arm_order_matches_gate",
        "test_dry_run_rc0_zero_calls",
        "test_fire_no_approval_rc2_zero_calls",
        "test_fire_invalid_approval_rc2_zero_calls",
        "test_fire_tampered_manifest_rc1_before_approval",
        "test_fire_valid_approval_fake_channel_rc0_12cells",
        "test_three_arms_same_task_input_and_list_only_for_two_arms",
        "test_prompts_contain_no_hidden_or_scorer",
        "test_missing_usage_totals_unknown_not_zero",
        "test_quota_exceeded_stops_no_retry",
        "test_quota_guard_blocks_before_call",
        "test_quota_guard_unknown_usage_bounded_by_call_cap",
        "test_quota_guard_no_backstop_preserves_legacy_behavior",
        "test_full_rloop_second_round_only_when_missing",
        "test_glm_channel_uses_cli_only",
        "test_rc_codes_match_gate",
    )
    root_a = fake_repo()
    place(root_a, real_names)
    v = guard_content_violations(root_a)
    assert any("vacant_network/reqloop/g3.py" in s and "內容漂移" in s for s in v), (
        f"g3 發射管線 stub 未被抓到（r1365 同型缺口：發射管線模組建於建錨輪後、"
        f"從未釘住；換 fire 成功 stub 後紅線整層掏空仍綠）: {v}"
    )
    assert any("tests/test_reqloop_g3.py" in s and "內容漂移" in s for s in v), (
        f"同名 dummy 測試檔未被抓到（18 真名 assert True、套件 96 計數不變）: {v}"
    )
    # 未改的既有守衛檔不得誤判
    for rel in tuple(GUARD_CONTENT_PIN):
        if rel not in G3_PAIR:
            assert not any(rel in s for s in v), f"未改檔被誤判: {rel}: {v}"

    # (b) 正控制：守衛檔皆真內容 → 零違規
    root_b = fake_repo()
    for rel in G3_PAIR:
        (root_b / rel).parent.mkdir(parents=True, exist_ok=True)
        (root_b / rel).write_bytes((REPO / rel).read_bytes())
    v_ok = guard_content_violations(root_b)
    assert v_ok == [], f"真內容守衛檔被誤判漂移: {v_ok}"


# ─────────────────────────────────────────────────────────────────────────────
# r1401（vq-el4.87）：GUARD_CONTENT_PIN 擴覆蓋——CI tip 收口對（ci_tip_check.py＋
# 其 10 測測試檔）
#
# 缺口（本輪 RED 實證、全數新跑）：r1399 輪（rc=124 殘留）建 CI tip 收口機械
# 檢查 ops/reqloop/ci_tip_check.py（NOW.md 下一步 #1 機械化：綠＝收口最終證據、
# 紅＝查因、未測量≠通過、state.json 一次讀取不 poll）＋tests/test_reqloop_ci_
# tip_check.py（10 測、含 7 負控制）——與 verify_effects_summary 對（r1333/r1344，
# r1347 補釘）同型——建於各建錨輪之後、從未釘住。攻擊場景（r1347 同型）：工具
# 換「直接印 CI_TIP_OK」stub＋測試檔換同名 dummy（10 真名、assert True、CI
# passed 計數不變）→ 收口判定整層掏空仍綠＝假綠燈（H-0 同構：綠燈來自沒量該
# 量的）。pin 是唯一能抓此 swap 的守衛。兩檔不含 pin 本身（無自釘循環；r1347
# 先例明文「可釘、且必須釘」）。
CI_TIP_PAIR = (
    "ops/reqloop/ci_tip_check.py",
    "tests/test_reqloop_ci_tip_check.py",
)


def test_guard_content_pin_ci_tip_pair_negative_controls(tmp_path: Path) -> None:
    """r1401（vq-el4.87）：CI tip 收口對（工具＋其 10 測測試檔）必須在 GUARD_CONTENT_PIN 內。
    (a) 負控制：工具換「直接印 CI_TIP_OK」stub＋測試檔換同名 dummy
        （10 真名、assert True、CI passed 計數不變）→ guard_content_violations
        必對兩檔各判內容漂移；
    (b) 正控制：守衛檔皆真內容 → 零違規（擴錨後不得誤判未改檔）。
    全部對臨時 repo 操作，不碰真檔；無 subprocess 片段（不觸及安裝合約掃描範圍）。
    RED 證據（本輪、舊錨）：(a) 的 v == []（兩檔不在 pin → 零違規＝假綠燈）。"""

    def fake_repo() -> Path:
        root = tmp_path / "repo"
        for rel in tuple(GUARD_CONTENT_PIN):
            dst = root / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes((REPO / rel).read_bytes())
        return root

    def place(root: Path, dummy_names: tuple[str, ...]) -> None:
        for rel in CI_TIP_PAIR:
            (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / "ops/reqloop/ci_tip_check.py").write_text(
            "def main(*args, **kwargs):\n"
            "    print('VERDICT: CI_TIP_OK')\n    return 0\n",
            encoding="utf-8",
        )
        (root / "tests/test_reqloop_ci_tip_check.py").write_text(
            "\n".join(f"def {n}():\n    assert True\n" for n in dummy_names),
            encoding="utf-8",
        )

    # (a) ci_tip_check 工具 stub＋測試檔同名 dummy → 兩檔都必須被判漂移
    real_names = (
        "test_live_shape_covered_peercovered_tipgreen",
        "test_peer_not_identical_code_diff_is_no_coverage",
        "test_empty_ci_dir_is_unknown_not_ok",
        "test_red_tip_json_is_red",
        "test_green_true_but_failed_nonzero_is_not_green",
        "test_latest_green_ancestor_by_commit_time",
        "test_corrupt_ci_json_skipped_not_crash",
        "test_state_json_running_is_note_only",
        "test_bookkeeping_only_diff_vs_one_code_file",
        "test_verdict_aggregation_priority",
    )
    root_a = fake_repo()
    place(root_a, real_names)
    v = guard_content_violations(root_a)
    assert any("ops/reqloop/ci_tip_check.py" in s and "內容漂移" in s for s in v), (
        f"ci_tip_check 收口 stub 未被抓到（r1347 同型缺口：收口工具建於建錨輪後、"
        f"從未釘住；換直接印 OK 的 stub 後收口證據整層掏空仍綠）: {v}"
    )
    assert any("tests/test_reqloop_ci_tip_check.py" in s and "內容漂移" in s for s in v), (
        f"同名 dummy 測試檔未被抓到（10 真名 assert True、CI passed 計數不變）: {v}"
    )
    # 未改的既有守衛檔不得誤判
    for rel in tuple(GUARD_CONTENT_PIN):
        if rel not in CI_TIP_PAIR:
            assert not any(rel in s for s in v), f"未改檔被誤判: {rel}: {v}"

    # (b) 正控制：守衛檔皆真內容 → 零違規
    root_b = fake_repo()
    for rel in CI_TIP_PAIR:
        (root_b / rel).parent.mkdir(parents=True, exist_ok=True)
        (root_b / rel).write_bytes((REPO / rel).read_bytes())
    v_ok = guard_content_violations(root_b)
    assert v_ok == [], f"真內容守衛檔被誤判漂移: {v_ok}"


# ─────────────────────────────────────────────────────────────────────────────
# r1393（vq-el4.81）：NOW.md 紅線守衛接進 freeze_check 一鍵 ruler（11→12 項）
#
# 背景：r1392 落地的紅線轉抄守衛（tests/test_reqloop_now_redline.py）只在 pytest
# 套件內跑——旁路 pytest、只看 freeze_check 的 FROZEN_STATE_OK 時，紅線轉抄漂移
# 仍不被一鍵 ruler 測量（H-0 同型：忘了把該測的測進 ruler 得到的綠燈）。
# 本輪以第 12 項 mandated 檢查 now_redline 補上：重用紅線守衛檔的
# redline_violations() 為唯一實現（同一把尺、無第二份 ruler、vrun 同原則）；
# 守衛檔缺／NOW.md 缺 → BROKEN（I-4：未測量不是通過）。
# 紀律（r1387/r1388 同型）：改 ruler 須同步顯式更新 GUARD_CONTENT_PIN 中
# ops/reqloop/freeze_check.py 之 pin 並留解凍記錄（見該 pin 條目 r1394 記錄）；
# r1393 改 ruler 但 pin 未更新（守衛抓到、三測試紅），r1394 依紀律補齊。
# ─────────────────────────────────────────────────────────────────────────────


def _now_redline_guard():
    """載入紅線守衛唯一實現（tests/test_reqloop_now_redline.py）。"""
    import importlib.util as _ilu

    guard = REPO / "tests" / "test_reqloop_now_redline.py"
    spec = _ilu.spec_from_file_location("reqloop_now_redline_guard", guard)
    assert spec is not None and spec.loader is not None, f"守衛檔不可載入: {guard}"
    mod = _ilu.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_now_redline_green_light() -> None:
    """（綠）真 repo：NOW.md 紅線契約行與磁碟逐條相符 → now_redline OK。
    本輪目標輸出：freeze_check 12/12 OK（上一輪 11/11）。"""
    mod = _load_freeze_check()
    g = _now_redline_guard()
    v = g.redline_violations(REPO / "NOW.md")
    assert v == [], f"前置：紅線守衛本身紅（NOW.md 與磁碟漂移）: {v}"
    mod.results.clear()
    mod.run_check("now_redline", mod.check_now_redline)
    assert len(mod.results) == 1, f"run_check 應記 1 筆: {mod.results}"
    name, ok, detail = mod.results[0]
    assert name == "now_redline", f"檢查名錯: {mod.results[0]}"
    assert ok is True, f"真 repo 應 OK: {mod.results[0]}"
    assert "now_redline" not in detail, "OK 訊息不應混入 BROKEN 字樣: " + detail


def test_now_redline_negative_controls(tmp_path: Path) -> None:
    """（負控制×3）RED 路徑證明，防空轉假綠燈（I-4）。
    (a) NOW.md 紅線轉抄漂移（blob hash 前綴差一位，r1392 守衛同型負控）→ BROKEN；
    (b) NOW.md 不存在 → BROKEN（fail-closed，不是 OK）；
    (c) 守衛模組不存在 → BROKEN（fail-closed；沙盒裡 ruler 被拷走時即此路徑）。
    """
    mod = _load_freeze_check()
    g = _now_redline_guard()

    # (a) 轉抄漂移：只在紅線契約行內改一個 blob 前綴（重用守衛自己的 _mutate_redline，
    #     同一把尺；注意：NOW.md 其它行可能含同前綴，全檔 sub 會打錯行；前綴取紅線行
    #     現值 extract.py blob b502741b…，11-13 受控解凍後重錨）
    mutated = g._mutate_redline(REPO / "NOW.md", tmp_path, "b502741b", "0502741b")
    v = g.redline_violations(mutated)
    assert any("extract.py" in s and "blob 前綴漂移" in s for s in v), (
        f"前置：守衛應抓到該漂移: {v}"
    )
    mod.results.clear()
    mod.run_check("now_redline", lambda: mod.check_now_redline(now=mutated))
    name, ok, detail = mod.results[0]
    assert name == "now_redline"
    assert ok is False, f"篡改 NOW.md 應 BROKEN: {mod.results[0]}"
    assert "漂移" in detail, f"BROKEN 訊息應點名漂移: {mod.results[0]}"

    # (b) NOW.md 不存在 → BROKEN（fail-closed）
    missing_now = tmp_path / "no_such_NOW.md"
    assert not missing_now.exists()
    mod.results.clear()
    mod.run_check("now_redline", lambda: mod.check_now_redline(now=missing_now))
    name, ok, detail = mod.results[0]
    assert name == "now_redline"
    assert ok is False, f"NOW.md 缺應 BROKEN（fail-closed）: {mod.results[0]}"
    assert "未測量" in detail or "不存在" in detail, f"detail 應點名未測量: {mod.results[0]}"

    # (c) 守衛模組不存在 → BROKEN（fail-closed；沙盒裡 freeze_check 被拷走時即此路徑）
    missing_guard = tmp_path / "no_such_guard.py"
    assert not missing_guard.exists()
    mod.results.clear()
    mod.run_check("now_redline", lambda: mod.check_now_redline(guard=missing_guard))
    name, ok, detail = mod.results[0]
    assert name == "now_redline"
    assert ok is False, f"守衛模組缺應 BROKEN（fail-closed）: {mod.results[0]}"
    assert "守衛" in detail, f"detail 應點名守衛缺: {mod.results[0]}"


# ── r1397（vq-el4.85）：GUARD_CONTENT_PIN 擴覆蓋——NOW.md 紅線轉抄守衛檔 ──
# 缺口（本輪 RED 實證）：freeze_check 第 12 項 mandated 檢查 now_redline 所 invoke 之
# redline_violations() 唯一實現在 tests/test_reqloop_now_redline.py（r1392 vq-el4.80 建立，
# 晚於 r1319/r1347/r1365 建錨各輪、從未釘住——vq-el4.63 同型：ruler 所 invoke 的守衛檔
# 建於建錨之後）。攻擊場景（r1365 同型）：該檔換同名 stub（5 真名 assert True＋
# redline_violations→[]）→ 套件 5 例仍全綠、95 計數不變；check_now_redline 調 stub 得 []
# → ruler 照判 OK；NOW.md 紅線契約行可整行掏空而 FROZEN_STATE_OK 仍成立（H-0 同構：
# 綠燈來自沒量該量的；r1319/r1347/r1365 同族：計數守住、檔案未守）。既有行為級信號
# （test_now_redline_negative_controls）住在自排除（自釘循環）的 test_reqloop_freeze_check.py
# 內——被 shortcut 同削即 swap 完成；位元組錨不依賴任何行為輸出、抓一切位元組改動。
# 該檔不含 pin 本身（無自釘循環），故可釘、且必須釘（r1347 先例明文）。
NOW_REDLINE_GUARD = "tests/test_reqloop_now_redline.py"


def test_guard_content_pin_now_redline_guard_negative_controls(tmp_path: Path) -> None:
    """r1397（vq-el4.85）：ruler（freeze_check 第 12 項 now_redline）所 invoke 之紅線
    守衛檔必須在 GUARD_CONTENT_PIN 內。
    (a) 負控制：檔換同名 stub（5 真名 assert True＋redline_violations→[]）→
        guard_content_violations 必判內容漂移；
    (b) 正控制：八份守衛檔皆真內容 → 零違規（擴錨後不得誤判未改檔）。
    全部對臨時 repo 操作，不碰真檔；無 subprocess 片段（不觸及安裝合約掃描範圍）。
    RED 證據（本輪、舊錨）：(a) 的 v == []（檔不在 pin → 零違規＝假綠燈；r1365 同形：
    guard_content_violations 只掃 pin 內檔，未釘檔的 stub swap 對它是隱形的）。"""

    def fake_repo() -> Path:
        root = tmp_path / "repo"
        for rel in tuple(GUARD_CONTENT_PIN):
            dst = root / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes((REPO / rel).read_bytes())
        return root

    # (a) 同名 stub（5 真名 assert True＋redline_violations→[]）→ 必須被判漂移
    real_names = (
        "test_now_redline_claims_match_disk",
        "test_guard_detects_transcribed_hash_drift",
        "test_guard_detects_transcribed_line_count_drift",
        "test_guard_detects_filing_count_drift",
        "test_guard_detects_missing_redline_line",
    )
    stub = (
        "def redline_violations(now_path=None):\n    return []\n\n"
        + "\n".join(f"def {n}():\n    assert True\n" for n in real_names)
    )
    root_a = fake_repo()
    dst = root_a / NOW_REDLINE_GUARD
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(stub, encoding="utf-8")
    v = guard_content_violations(root_a)
    assert any(NOW_REDLINE_GUARD in s and "內容漂移" in s for s in v), (
        f"紅線守衛 stub swap 未被抓到（vq-el4.63 同型缺口：ruler 所 invoke 的守衛檔"
        f"從未釘住；check_now_redline 調 stub 之 redline_violations 得 [] → ruler 照判 OK，"
        f"NOW.md 紅線契約行可整行掏空而 FROZEN_STATE_OK 仍成立）: {v}"
    )
    # 未改的既有守衛檔不得誤判
    for rel in tuple(GUARD_CONTENT_PIN):
        if rel != NOW_REDLINE_GUARD:
            assert not any(rel in s for s in v), f"未改檔被誤判: {rel}: {v}"

    # (b) 正控制：八份守衛檔皆真內容 → 零違規
    root_b = fake_repo()
    dst = root_b / NOW_REDLINE_GUARD
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes((REPO / NOW_REDLINE_GUARD).read_bytes())
    v_ok = guard_content_violations(root_b)
    assert v_ok == [], f"真內容守衛檔被誤判漂移: {v_ok}"
