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

    # (e) r1285：5 passed + 1 skipped（守衛測試被 @pytest.mark.skip 禁用、藏 assert False，
    #     另補一個足量測試保持 passed 計數＝5）→ pytest 匯總「5 passed, 1 skipped」→
    #     舊計數守衛只抽 "5 passed" 仍判 OK＝假綠燈（r1271–r1282 同型、I-4 未測量不是通過）；
    #     必須 BROKEN 且 detail 點出 skipped。
    (tests_dir / "test_reqloop_frozen_anchors.py").write_text(
        "\n".join(f"def test_t{i}():\n    assert True\n" for i in range(5))
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


def test_diff_anchor_negative_control(tmp_path: Path) -> None:
    """r1300：check_diff 的 base 必须錨定被測 commit（CI 是 detached checkout）。

    CI（ci.sh）detached checkout 被測 commit，repo 內分支 ref 指向執行時點的 live
    分支 HEAD：worktree 已同步到新 tip 時，舊 commit 自己的 in-scope 檔與 worktree
    不同，舊碼 ref 基 diff 判 0 file differ、OK＝假綠燈（r1300 實證：被測 commit
    ops/STATE.md=v1、兩 ref 皆指 v2 tip → ref 基 0 files OK／HEAD 基 1 file
    BROKEN；H-0 同構：量錯對象得到的綠燈就是漏洞成因；I-4：未測量不是通過）。
    期望行為：HEAD detached 時 base 錨定 HEAD（被測 commit）→ 示例舊 commit 判
    BROKEN、detail 點名差異檔；HEAD attached 分支（本地 dev/worktree）時口徑不變
    （base=auto/qwen27b，判旧同）。
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

    # 負控制：被測 commit 的 in-scope 檔與 worktree 不同 → 必 BROKEN。
    # 舊碼（ref 基，量 tip 狀態）在此判 OK＝假綠燈（已實證）。
    mod.results.clear()
    mod.check_diff(branch="auto/worker", name="diff_worker")
    ok, detail = mod.results[-1][1], mod.results[-1][2]
    assert not ok, (
        f"被測 commit 的 in-scope 檔與 worktree 不同卻判 OK＝假綠燈"
        f"（ref 基量 tip 狀態而非被測 commit）: {detail}"
    )
    assert "ops/STATE.md" in detail, f"detail 應點名差異檔: {detail}"

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
