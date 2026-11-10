"""r1399（2026-11-10）：CI tip 收口機械檢查（vq-el4.87）。

NOW.md 下一步 #1「下輪開頭一次讀取三分支現 tip 之 per-sha CI json 並收口
（綠＝收口最終證據、紅＝查因；不 poll）」此前每輪靠散文推斷：LATEST 綠即口頭
「已覆蓋」。本輪實證其假綠燈洞（H-0 同構：綠燈來自沒量該量的；I-4：未測量
不是通過）：worker/argon 的 per-sha CI 跑在舊祖先（bb6de7a4/062cd433）上，
該祖先..tip 的 diff 含非簿記檔（tests/test_reqloop_freeze_check.py）——「LATEST
綠→收口」對這兩支不成立；真正成立的是「tip 與 qwen27b tip 之 root tree 恆等
（內容定址＝位元組恆等）＋qwen27b tip 之綠 CI 祖先僅差 4 簿記檔」。此區分
（自體綠／簿記延展／peer tree 恆等／未測量）此前無任何機械檢查。

本檔以偽 git（monkeypatch run_git，無真 git、無 subprocess、無 python -c 片段，
不觸及 test_reqloop_ci_contract.py 的安裝合約掃描範圍）對
ops/reqloop/ci_tip_check.py 的收口判定做負控制：

  綠燈：本輪真實狀態同構——qwen27b COVERED（綠祖先＋diff 純簿記）、
        worker PEER_COVERED（自體 diff 含碼、peer tree 恆等）、argon TIP_GREEN。
  負控 (a)：peer tree 不恆等＋自體 diff 含碼 → NO_COVERAGE → CI_TIP_BROKEN
            （「LATEST 綠→收口」必須不成立——本輪實證洞）。
  負控 (b)：ci 目錄全空 → 三分支皆 UNKNOWN → CI_TIP_UNKNOWN（空目錄≠OK，I-4）。
  負控 (c)：tip per-sha 紅（failed>0）→ RED → BROKEN。
  負控 (d)：json green=true 但 failed>0 → 不得判 TIP_GREEN（is_green fail-closed）。
  負控 (h)：json green=true 但 passed=0（零通過＝未測量任何測試）→ 不得判 TIP_GREEN；
            json bool 計數（failed:false／errors:false，False==0 型混淆）亦不得讀成 0
            （r1405 補；I-4「a suite that reported zero tests fails」，r1272 空檔 vacuous
            同族——舊碼判 TIP_GREEN→CI_TIP_OK＝假綠燈）。
  負控 (e)：兩綠祖先（commit 時間 100/200），新者 diff 純簿記、舊者含碼
            → 必選新者判 COVERED（按 commit 時間選最新，非 json mtime／任意序）。
  負控 (f)：損毀 json 不得崩潰、不得計入證據（I-4）。
  負控 (g)：state.json running 只加註記、不改判定（一次讀取、不 poll 的紀律）。
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "ops" / "reqloop" / "ci_tip_check.py"

A = "auto/qwen27b"
B = "auto/worker"
C = "auto/argon"

# 40-hex 偽 sha（固定字面量，非隨機——可複核）
TIP_A = "a1" * 20
TIP_B = "b1" * 20
TIP_C = "c1" * 20
ANC_A = "f3" * 20
ANC_B = "bb" * 20
ANC_OLD = "d1" * 20
ANC_NEW = "d2" * 20
TREE_X = "e5" * 20
TREE_Y = "f9" * 20
TREE_Z = "a9" * 20  # 唯一 tree（與 X、Y 皆不同）——用於斷開 peer 路徑

BOOKKEEPING = ["STATE.md", "NOW.md", "ops/STATE.md", "ops/loop/NOW.md"]
CODE_FILE = "tests/test_reqloop_freeze_check.py"


def _load() -> object:
    spec = importlib.util.spec_from_file_location("ci_tip_check_mod", SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _ci_record(branch: str, sha: str, *, green: bool = True,
               passed: int = 5134, failed: int = 0, errors: int = 0,
               skipped: int = 74) -> dict:
    return {
        "branch": branch, "sha": sha, "ts": 1794000000,
        "pytest_rc": 0 if green else 1, "collected": passed + skipped,
        "passed": passed, "failed": failed, "errors": errors, "skipped": skipped,
        "failures": [] if green else [f"tests/whatever.py::t (FAILED)"],
        "green": green,
    }


def _write_ci(ci_dir: Path, rec: dict) -> None:
    (ci_dir / f"{rec['sha']}.json").write_text(
        json.dumps(rec), encoding="utf-8")


class FakeGit:
    """偽 git：以場景字典回覆 run_git 的六種只讀命令。"""

    def __init__(self, tips: dict, ancestors: set, cts: dict,
                 diffs: dict, trees: dict) -> None:
        self.tips = tips            # {branch: tip_sha}
        self.ancestors = ancestors  # {(branch, sha)}：sha 是 branch tip 之祖先
        self.cts = cts              # {sha: commit_ts}
        self.diffs = diffs          # {(a, b): [files]}（缺＝rc!=0）
        self.trees = trees          # {ref: tree_hash}

    def run_git(self, wt, *args) -> tuple:
        a = list(args)
        if a[0] == "rev-parse" and a[1] == "--verify":
            br = a[2]
            if br in self.tips:
                return 0, self.tips[br] + "\n"
            return 1, "unknown revision\n"
        if a[0] == "rev-parse" and a[1].endswith("^{tree}"):
            ref = a[1][: -len("^{tree}")]
            if ref in self.trees:
                return 0, self.trees[ref] + "\n"
            return 1, "unknown revision\n"
        if a[0] == "cat-file" and a[1] == "-e":
            sha = a[2][: -len("^{commit}")] if a[2].endswith("^{commit}") else a[2]
            return (0, "") if sha in self.cts else (1, "missing\n")
        if a[0] == "merge-base" and a[1] == "--is-ancestor":
            return (0, "") if (a[3], a[2]) in self.ancestors else (1, "")
        if a[0] == "log" and a[2] == "--format=%ct":
            sha = a[3]
            if sha in self.cts:
                return 0, str(self.cts[sha]) + "\n"
            return 1, "bad sha\n"
        if a[0] == "diff" and a[1] == "--name-only":
            key = (a[2], a[3])
            if key in self.diffs:
                return 0, "\n".join(self.diffs[key]) + "\n"
            return 1, "bad revision\n"
        raise AssertionError(f"偽 git 未建模的命令: {a!r}")


def _eval(mod, ci_dir: Path, fg: FakeGit, monkeypatch) -> dict:
    monkeypatch.setattr(mod, "run_git", fg.run_git)
    return mod.evaluate(ci_dir, {A: Path("wtA"), B: Path("wtB"), C: Path("wtC")})


def _scenario_base() -> tuple[FakeGit, list]:
    """本輪真實狀態同構：A 綠祖先＋純簿記 diff；B 綠祖先＋含碼 diff；C tip 綠。"""
    fg = FakeGit(
        tips={A: TIP_A, B: TIP_B, C: TIP_C},
        ancestors={(A, ANC_A), (B, ANC_B)},
        cts={ANC_A: 100, ANC_B: 100, TIP_C: 200},
        diffs={(ANC_A, TIP_A): list(BOOKKEEPING), (ANC_B, TIP_B): BOOKKEEPING + [CODE_FILE]},
        trees={TIP_A: TREE_X, TIP_B: TREE_X, TIP_C: TREE_Y},
    )
    return fg, [_ci_record(A, ANC_A), _ci_record(B, ANC_B, passed=5133),
                _ci_record(C, TIP_C)]


# ── 綠燈（本輪真實狀態同構）─────────────────────────────────────────────────


def test_live_shape_covered_peercovered_tipgreen(tmp_path: Path, monkeypatch) -> None:
    """綠燈：qwen27b COVERED（綠祖先＋diff 純簿記 4 檔）、worker PEER_COVERED
    （自體 diff 含碼但 tip tree 與已收口 peer 恆等）、argon TIP_GREEN（tip per-sha 綠）
    → VERDICT: CI_TIP_OK rc=0。判定全由只讀輸入決定、可重放。"""
    mod = _load()
    fg, recs = _scenario_base()
    for r in recs:
        _write_ci(tmp_path, r)
    res = _eval(mod, tmp_path, fg, monkeypatch)
    va, vb, vc = res["branches"][A]["verdict"], res["branches"][B]["verdict"], res["branches"][C]["verdict"]
    assert va == "COVERED", res
    assert vb == "PEER_COVERED", res
    assert vc == "TIP_GREEN", res
    assert res["verdict"] == "CI_TIP_OK" and res["rc"] == 0, res
    # 證據必須點名依據（可複核，非裸判定；引用慣例 12 字元縮寫）
    assert any(ANC_A[:12] in e for e in res["branches"][A]["evidence"]), res
    assert any("peer=" in e and TREE_X[:12] in e for e in res["branches"][B]["evidence"]), res


# ── 負控制（證明綠燈不是空轉）──────────────────────────────────────────────


def test_peer_not_identical_code_diff_is_no_coverage(tmp_path: Path, monkeypatch) -> None:
    """負控 (a)：B 自體 diff 含碼＋peer tree 不恆等（TREE_Y≠TREE_X）→ NO_COVERAGE
    → 整體 CI_TIP_BROKEN rc=1。此為本輪實證洞：「LATEST 綠→收口」必須不成立
    （H-0 同構；I-4：未測量不是通過）。"""
    mod = _load()
    fg, recs = _scenario_base()
    fg.trees[TIP_B] = TREE_Z  # 與 X、Y 皆不同 → 無 peer 恆等
    for r in recs:
        _write_ci(tmp_path, r)
    res = _eval(mod, tmp_path, fg, monkeypatch)
    assert res["branches"][B]["verdict"] == "NO_COVERAGE", res
    assert res["verdict"] == "CI_TIP_BROKEN" and res["rc"] == 1, res


def test_empty_ci_dir_is_unknown_not_ok(tmp_path: Path, monkeypatch) -> None:
    """負控 (b)：ci 目錄全空（無 per-sha json、無綠祖先）→ 三分支皆 UNKNOWN
    → CI_TIP_UNKNOWN rc=2。空目錄＝未測量，不得判 OK（I-4）。"""
    mod = _load()
    fg, _ = _scenario_base()
    fg.ancestors = set()  # 無任何綠祖先
    res = _eval(mod, tmp_path, fg, monkeypatch)
    for br in (A, B, C):
        assert res["branches"][br]["verdict"] == "UNKNOWN", res
    assert res["verdict"] == "CI_TIP_UNKNOWN" and res["rc"] == 2, res


def test_red_tip_json_is_red(tmp_path: Path, monkeypatch) -> None:
    """負控 (c)：C tip 有 per-sha json 但紅（failed=2、green=false）→ RED
    → 整體 BROKEN rc=1（紅＝查因，不得被 peer 恆等洗白——peer 救不了自體紅）。"""
    mod = _load()
    fg, recs = _scenario_base()
    recs[-1] = _ci_record(C, TIP_C, green=False, passed=5132, failed=2)
    for r in recs:
        _write_ci(tmp_path, r)
    res = _eval(mod, tmp_path, fg, monkeypatch)
    assert res["branches"][C]["verdict"] == "RED", res
    assert res["verdict"] == "CI_TIP_BROKEN" and res["rc"] == 1, res


def test_green_true_but_failed_nonzero_is_not_green(tmp_path: Path, monkeypatch) -> None:
    """負控 (d)：json 自稱 green=true 但 failed=1 → is_green 必須 fail-closed
    判非綠 → C 不得 TIP_GREEN（自稱綠＋計數紅＝矛盾記錄，I-4 未測量不是通過）。"""
    mod = _load()
    fg, recs = _scenario_base()
    recs[-1] = _ci_record(C, TIP_C, green=True, passed=5133, failed=1)
    for r in recs:
        _write_ci(tmp_path, r)
    res = _eval(mod, tmp_path, fg, monkeypatch)
    assert res["branches"][C]["verdict"] != "TIP_GREEN", res
    assert res["verdict"] != "CI_TIP_OK", res


def test_vacuous_or_bool_counter_record_is_red_not_green(tmp_path: Path, monkeypatch) -> None:
    """負控 (h)（r1405）：C tip per-sha 記錄存在但不可用 → 必須判 RED（有記錄、非綠
    → 查因），整體 CI_TIP_BROKEN rc=1。舊碼（r1399 初版 is_green 只驗
    green is True＋failed==0＋errors==0、不驗 passed、計數不驗型）對兩場景皆判
    TIP_GREEN→CI_TIP_OK＝假綠燈（H-0 同構：綠燈來自沒量該量的）：
    (h1) green=true、passed=0、failed=0、errors=0——零通過＝未測量任何測試，
        I-4「a suite that reported zero tests fails」（本 ruler 自身 docstring 即引 I-4
        跳損毀 json；零計數記錄同為不可用證據，r1272 空檔 vacuous 同族）；
    (h2) green=true、passed=5134、failed=false、errors=false——json bool 非整數計數，
        舊碼因 False==0 被讀成「零失敗」（r1296 null-sha 同族：型未守）。
    修後 is_green 收緊為嚴格 int（非 bool）：passed>0、failed==0、errors==0。"""
    mod = _load()
    # (h1) 零通過空記錄
    fg, recs = _scenario_base()
    recs[-1] = _ci_record(C, TIP_C, green=True, passed=0, failed=0, errors=0, skipped=0)
    for r in recs:
        _write_ci(tmp_path, r)
    res = _eval(mod, tmp_path, fg, monkeypatch)
    assert res["branches"][C]["verdict"] == "RED", res
    assert res["verdict"] == "CI_TIP_BROKEN" and res["rc"] == 1, res
    # (h2) bool 計數型混淆（新 tmp 子目錄，避免與 (h1) 之 ci 檔混用）
    fg2, recs2 = _scenario_base()
    rec2 = _ci_record(C, TIP_C, green=True, passed=5134, failed=0, errors=0)
    rec2["failed"] = False  # json 序列化為 false——非整數
    rec2["errors"] = False
    recs2[-1] = rec2
    d2 = tmp_path / "h2"
    d2.mkdir()
    for r in recs2:
        _write_ci(d2, r)
    res2 = _eval(mod, d2, fg2, monkeypatch)
    assert res2["branches"][C]["verdict"] == "RED", res2
    assert res2["verdict"] == "CI_TIP_BROKEN" and res2["rc"] == 1, res2


def test_latest_green_ancestor_by_commit_time(tmp_path: Path, monkeypatch) -> None:
    """負控 (e)：A 有兩綠祖先——舊（ct=100，diff 含碼）與新（ct=200，diff 純簿記）。
    必按 commit 時間選最新（ANC_NEW）→ COVERED；若誤選舊者會得 NO_COVERAGE。
    （json 的 mtime／遍歷序不得決定選擇——可重放性。）"""
    mod = _load()
    fg, _ = _scenario_base()
    fg.ancestors = {(A, ANC_OLD), (A, ANC_NEW), (B, ANC_B)}
    fg.cts.update({ANC_OLD: 100, ANC_NEW: 200})
    fg.diffs[(ANC_OLD, TIP_A)] = BOOKKEEPING + [CODE_FILE]
    fg.diffs[(ANC_NEW, TIP_A)] = list(BOOKKEEPING)
    recs = [_ci_record(A, ANC_OLD, passed=5130), _ci_record(A, ANC_NEW, passed=5134),
            _ci_record(B, ANC_B, passed=5133), _ci_record(C, TIP_C)]
    for r in recs:
        _write_ci(tmp_path, r)
    res = _eval(mod, tmp_path, fg, monkeypatch)
    assert res["branches"][A]["verdict"] == "COVERED", res
    assert any(ANC_NEW[:12] in e for e in res["branches"][A]["evidence"]), res


def test_corrupt_ci_json_skipped_not_crash(tmp_path: Path, monkeypatch) -> None:
    """負控 (f)：ci 目錄含損毀 json（非 JSON）→ 必須跳過、不崩潰、不計入證據
    （I-4：未測量不是通過；解析失敗不得偽造成綠祖先）。"""
    mod = _load()
    fg, recs = _scenario_base()
    for r in recs:
        _write_ci(tmp_path, r)
    (tmp_path / (("e7" * 20) + ".json")).write_text("{not json", encoding="utf-8")
    res = _eval(mod, tmp_path, fg, monkeypatch)
    # A 仍只能靠 ANC_A（損毀檔不在祖先集）→ COVERED 不變；整體仍 OK
    assert res["branches"][A]["verdict"] == "COVERED", res
    assert res["verdict"] == "CI_TIP_OK", res


def test_state_json_running_is_note_only(tmp_path: Path, monkeypatch) -> None:
    """負控 (g)：state.json running=auto/worker@tip → B 的證據行須含「在跑」註記
    （一次讀取、不 poll 的紀律），但判定不變（PEER_COVERED）、整體仍 OK——
    註記不得升格為收口證據（在跑≠已綠）。"""
    mod = _load()
    fg, recs = _scenario_base()
    for r in recs:
        _write_ci(tmp_path, r)
    (tmp_path / "state.json").write_text(
        json.dumps({"running": B, "sha": TIP_B, "ts": 1794000001}), encoding="utf-8")
    res = _eval(mod, tmp_path, fg, monkeypatch)
    assert res["branches"][B]["verdict"] == "PEER_COVERED", res
    assert any("在跑" in e for e in res["branches"][B]["evidence"]), res
    assert res["verdict"] == "CI_TIP_OK" and res["rc"] == 0, res


def test_bookkeeping_only_diff_vs_one_code_file(tmp_path: Path, monkeypatch) -> None:
    """判界：diff 純簿記 4 檔 → COVERED；diff 多 1 個非簿記檔 → 不得 COVERED。
    （簿記集即契約：STATE.md／NOW.md／ops/STATE.md／ops/loop/NOW.md；
    任何產品碼或測試碼檔案皆非簿記。）"""
    mod = _load()
    fg, _ = _scenario_base()
    fg.diffs[(ANC_B, TIP_B)] = BOOKKEEPING + [CODE_FILE]
    fg.trees[TIP_B] = TREE_Z  # 斷開 peer 路徑（與 X、Y 皆不同），隔離自體判定
    fg.ancestors = {(A, ANC_A), (B, ANC_B)}
    recs = [_ci_record(A, ANC_A), _ci_record(B, ANC_B, passed=5133),
            _ci_record(C, TIP_C)]
    for r in recs:
        _write_ci(tmp_path, r)
    res = _eval(mod, tmp_path, fg, monkeypatch)
    assert res["branches"][A]["verdict"] == "COVERED", res
    assert res["branches"][B]["verdict"] == "NO_COVERAGE", res


def test_verdict_aggregation_priority(tmp_path: Path, monkeypatch) -> None:
    """聚合口徑：任一 RED／NO_COVERAGE → BROKEN（rc=1）優先於 UNKNOWN（rc=2）；
    全收口才 OK（rc=0）。三口徑互斥、可被下游自動化直接分支（同 run_eval 0/20/22 慣例）。"""
    mod = _load()
    # BROKEN 優先於 UNKNOWN：C 無任何 CI 數據（UNKNOWN）、B 未覆蓋（NO_COVERAGE）
    fg, _ = _scenario_base()
    fg.ancestors = {(A, ANC_A), (B, ANC_B)}
    fg.trees[TIP_B] = TREE_Z
    fg.tips = {k: v for k, v in fg.tips.items() if k != C}  # C tip 不可解析 → UNKNOWN
    recs = [_ci_record(A, ANC_A), _ci_record(B, ANC_B, passed=5133)]
    for r in recs:
        _write_ci(tmp_path, r)
    res = _eval(mod, tmp_path, fg, monkeypatch)
    assert res["branches"][C]["verdict"] == "UNKNOWN", res
    assert res["verdict"] == "CI_TIP_BROKEN" and res["rc"] == 1, res


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
