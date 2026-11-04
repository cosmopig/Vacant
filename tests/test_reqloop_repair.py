"""
G2 局部修復切片測試（工單 P000-20261104-01-repair-slice，2026-11-04）。

全部使用 G1 自造案例（expense_category），fake agent 離線接線——**synthetic**，
只驗管線（修復請求帶什麼、重驗、前後差異、停因、成本），不宣稱任何真實修復效果。

規則（RD_FOCUS_20261104）：
- 保留原候選：原草稿目錄永遠不被改動。
- FAIL→UNKNOWN 不算修好；缺項/UNKNOWN/CONFLICT 不宣告完成。
- 任何原有 PASS 退步（PASS→FAIL/UNKNOWN）都要記錄。
- 連續兩次修復沒有消除已確認缺口 ⇒ 停止，回傳停因及未解決項。
- 成本缺值＝UNKNOWN（None），絕不填 0。
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import shutil

import pytest

from vacant_network.adapters.agents import Launch
from vacant_network.reqloop import repair
from vacant_network.reqloop.checks import check_tag_format, run_requirement_checks
from vacant_network.reqloop.requirements import RequirementItem, RequirementSet

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
G1_TASK = REPO_ROOT / "ops" / "reqloop" / "g1" / "tasks" / "expense_category"

#: G1 bad 草稿：3 條需求，2 PASS + 1 FAIL（req_summary_numbers）
BAD_DRAFT = "bad_grand_total_wrong"
FAIL_CLAIM = "req_summary_numbers"
PASS_CLAIMS = ("req_csv_structure", "req_group_recompute")


@pytest.fixture()
def task_dir(tmp_path: pathlib.Path) -> pathlib.Path:
    """G1 任務目錄拷貝到 tmp（測試對它只讀；工作區一律寫 tmp）。標 synthetic。"""
    d = tmp_path / "task"
    shutil.copytree(G1_TASK, d)
    return d


def load_req_set(task_dir: pathlib.Path) -> RequirementSet:
    return RequirementSet.load(task_dir / "requirements.json")


def _fake_build(log: list[dict]):
    def build(prompt: str, ws: pathlib.Path) -> Launch:
        log.append({"prompt": prompt, "ws": str(ws)})
        return Launch(argv=["true"], note="fake")
    return build


def _fake_agent(ws_files: dict[str, str] | None, *, wall_ms: int = 1200,
                stdout_json: str | None = None):
    """fake run：把 ws_files 寫進 workspace（模擬修復模型改交付物），回 run_agent 同款 dict。"""
    def run(launch: Launch, *, workspace: pathlib.Path, timeout_s: float,
            log_dir: pathlib.Path) -> dict:
        for name, text in (ws_files or {}).items():
            p = pathlib.Path(workspace) / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text, encoding="utf-8")
        log_dir.mkdir(parents=True, exist_ok=True)
        (log_dir / "agent_stdout.log").write_text(stdout_json or "{}", encoding="utf-8")
        (log_dir / "agent_stderr.log").write_text("", encoding="utf-8")
        return {"rc": 0, "timed_out": False, "wall_ms": wall_ms,
                "spawn_error": None, "stdout_log": str(log_dir / "agent_stdout.log"),
                "stderr_log": str(log_dir / "agent_stderr.log")}
    return run


def _good_summary(task_dir: pathlib.Path) -> str:
    return (task_dir / "good" / "summary.md").read_text(encoding="utf-8")


def _good_csv(task_dir: pathlib.Path) -> str:
    return (task_dir / "good" / "expense_summary.csv").read_text(encoding="utf-8")


def test_module_documented_rules():
    """切片必須把 11/04 的規則寫進模組文件（防骨架化：只交抽象接口不算完成）。"""
    doc = repair.__doc__ or ""
    for needle in ("FAIL→UNKNOWN", "PASS", "停", "原草稿", "UNKNOWN"):
        assert needle in doc, f"模組文件缺規則說明：{needle}"


# ── 前後差異（FAIL/UNKNOWN/PASS）──────────────────────────────────────

def test_diff_fail_to_pass_is_fixed(task_dir):
    rs = load_req_set(task_dir)
    before = run_requirement_checks(task_dir, rs, task_dir / BAD_DRAFT)
    after = run_requirement_checks(task_dir, rs, task_dir / "good")
    d = repair.diff_results(before, after)
    assert FAIL_CLAIM in d.fixed
    assert FAIL_CLAIM not in d.not_fixed
    assert d.regressed == ()
    assert d.required_fail_before == 1
    assert d.required_fail_after == 0
    assert d.closed_any_gap is True
    assert d.transitions[FAIL_CLAIM] == ("FAIL", "PASS")


def test_diff_fail_to_unknown_not_fixed(task_dir):
    """FAIL→UNKNOWN 不算修好（規則明列）。"""
    rs = load_req_set(task_dir)
    before = [
        _cr("a", "FAIL"), _cr("b", "PASS"),
    ]
    after = [
        _cr("a", "UNKNOWN"), _cr("b", "PASS"),
    ]
    d = repair.diff_results(before, after)
    assert d.fixed == ()
    assert "a" in d.not_fixed
    assert d.closed_any_gap is False


def test_diff_pass_to_fail_regressed(task_dir):
    """原有 PASS 退步必須被記錄，不能被淨改善掩蓋。"""
    before = [_cr("a", "PASS"), _cr("b", "FAIL")]
    after = [_cr("a", "FAIL"), _cr("b", "PASS")]
    d = repair.diff_results(before, after)
    assert d.fixed == ("b",)
    assert d.regressed == ("a",)
    assert d.transitions["a"] == ("PASS", "FAIL")


def test_diff_missing_claim_not_completion(task_dir):
    """重驗後缺項＝沒完成，不算 PASS、也不算修好。"""
    before = [_cr("a", "FAIL")]
    after = []  # 該條目在重驗中消失了
    d = repair.diff_results(before, after)
    assert d.fixed == ()
    assert d.not_fixed == ("a",)
    assert d.transitions["a"][1] == "MISSING"


def _cr(cid: str, status: str):
    from vacant_network.intake.verifiers import ClaimResult
    return ClaimResult(claim_id=cid, status=status, detail="", evidence={},
                       verifier="t", verifier_version="t", required=True,
                       authority="client")


# ── 修復請求內容（原生 pi 會收到的提示）─────────────────────────────

def test_localized_prompt_has_requirement_counterexample_and_scope(task_dir):
    rs = load_req_set(task_dir)
    before = run_requirement_checks(task_dir, rs, task_dir / BAD_DRAFT)
    prompt = repair.build_repair_prompt(task_dir, rs, task_dir / BAD_DRAFT, before,
                                        feedback_mode="localized")
    assert "報銷總金額" in prompt                      # 原始需求原文（request.md）
    assert "10674.83" in prompt                        # 可見反例（重算的正確值）
    assert FAIL_CLAIM in prompt                        # 哪一條沒過
    assert "expense_summary.csv" in prompt             # 可改的交付物檔
    assert "summary.md" in prompt
    assert "expenses.csv" in prompt                    # 源資料檔（不可改）
    assert "req_csv_structure" in prompt               # 已 PASS、必須保持
    # 兩臂對照（generic/localized）的差異必須真實存在：generic 不得帶失敗證據
    generic = repair.build_repair_prompt(task_dir, rs, task_dir / BAD_DRAFT, before,
                                         feedback_mode="generic")
    assert "10674.83" not in generic
    assert FAIL_CLAIM not in generic
    assert "報銷總金額" in generic                     # 原始需求兩臂都有


def test_prompt_tells_env_has_sciplib_and_verify_by_import(task_dir):
    """dab_039 真實停因：草稿 solution.py 舊註解聲稱 scipy 缺失，模型誤信後
    手刻 Royston 演算法＋搜尋工作區外部目錄，300s 預算耗盡（r976 複跑 549k tok 仍 stalled）。
    修復請求（兩臂一致）必須明示：環境已裝 scipy/numpy，直接調用產出交付物；
    是否可用以實際 import 為準，不得因草稿內過時註解而手刻替代演算法。"""
    rs = load_req_set(task_dir)
    before = run_requirement_checks(task_dir, rs, task_dir / BAD_DRAFT)
    for mode in ("generic", "localized"):
        p = repair.build_repair_prompt(task_dir, rs, task_dir / BAD_DRAFT, before,
                                       feedback_mode=mode)
        assert "scipy" in p and "numpy" in p, mode
        assert "import" in p, mode                    # 以實際 import 為準
        assert "手刻" in p or "替代演算法" in p, mode   # 禁止假設缺失而手刻


def test_prompt_never_names_hidden_sources(task_dir):
    """修復請求不得出現 hidden／scorer 等隱藏來源字眼。"""
    rs = load_req_set(task_dir)
    before = run_requirement_checks(task_dir, rs, task_dir / BAD_DRAFT)
    for mode in ("generic", "localized"):
        p = repair.build_repair_prompt(task_dir, rs, task_dir / BAD_DRAFT, before,
                                       feedback_mode=mode)
        for bad in ("hidden/", "scorer.py", "/srv/eval"):
            assert bad not in p, (mode, bad)


def test_plain_recomputed_fail_prompt_leak_guard(tmp_path: pathlib.Path):
    """G2 依賴核對（repair.py × checks.cond_rate，r985 審查 redo）：
    build_repair_prompt 是 cond_rate FAIL 輸出進入修復提示的唯一路徑——
    localized 只帶「值不符重算」的事實＋公開規則＋交付物自身的值；
    重算值（本例 2/4＝0.5）絕不進提示（leak guard，manifest 口徑，同 e013）；
    generic 臂不帶失敗證據；兩臂皆不點名 hidden 來源。"""
    task_dir = tmp_path / "task"
    draft = tmp_path / "draft"
    task_dir.mkdir(parents=True)
    draft.mkdir(parents=True)
    (task_dir / "request.md").write_text(
        "What is the fraud rate for in-person transactions for the year 2023?\n"
        "（Answer must be just a number）\n", encoding="utf-8")
    (task_dir / "payments.csv").write_text(
        "year,shopper_interaction,has_fraudulent_dispute\n"
        "2023,POS,True\n2023,POS,True\n2023,POS,False\n2023,POS,False\n"
        "2023,Ecommerce,True\n2022,POS,True\n", encoding="utf-8")   # 重算值＝2/4＝0.5
    (draft / "answer.txt").write_text("0.4\n", encoding="utf-8")
    rs = RequirementSet(task_id="t", items=[RequirementItem(
        id="req_main", quote="fraud_rate_2023_inperson", deliverable="answer.txt",
        verifier="plain_recomputed",
        params={"data_file": "payments.csv", "recompute": {
            "type": "cond_rate",
            "where": [{"col": "year", "op": "eq", "value": "2023"},
                      {"col": "shopper_interaction", "op": "eq", "value": "POS"}],
            "num_where": [{"col": "has_fraudulent_dispute", "op": "eq", "value": "True"}]}})])
    before = run_requirement_checks(task_dir, rs, draft)
    assert {c.claim_id: c.status for c in before}["req_main"] == "FAIL"

    loc = repair.build_repair_prompt(task_dir, rs, draft, before, feedback_mode="localized")
    assert "req_main" in loc                                # 哪一條沒過
    assert "fraud_rate_2023_inperson" in loc                # 條目原文
    assert "不符" in loc                                     # 失敗事實（detail 原文）
    assert "0.4" in loc                                      # 交付物自身的值（可見反例）
    assert "0.5" not in loc                                  # 重算值不得進提示（leak guard）

    gen = repair.build_repair_prompt(task_dir, rs, draft, before, feedback_mode="generic")
    assert "fraud rate" in gen                               # 原始需求兩臂都有
    assert "req_main" not in gen                              # generic 不帶失敗證據
    assert "0.5" not in gen
    assert "0.4" not in gen
    for p in (loc, gen):
        for bad in ("hidden/", "scorer.py", "/srv/eval"):
            assert bad not in p, bad


# ── 完整切片（fake agent，synthetic 離線接線）──────────────────────

def test_repair_fail_to_pass_and_original_preserved(task_dir, tmp_path):
    rs = load_req_set(task_dir)
    draft = task_dir / BAD_DRAFT
    draft_hashes = _dir_hashes(draft)
    log: list[dict] = []
    run = _fake_agent({"summary.md": _good_summary(task_dir)})
    out = repair.repair_slice(
        task_dir, rs, draft,
        out_root=tmp_path / "out", build=_fake_build(log), run=run,
        feedback_mode="localized", max_rounds=2, synthetic=True,
    )
    # 修好：FAIL→PASS，缺口關閉
    assert out.stopped == "gap_closed"
    assert FAIL_CLAIM in out.fixed
    assert out.final_status[FAIL_CLAIM] == "PASS"
    assert out.unresolved == ()
    # 原草稿逐位元組未動（保留原候選）
    assert _dir_hashes(draft) == draft_hashes
    # 成本：1 次呼叫、wall_ms 來自執行器實際攔截
    assert out.cost["calls"] == 1
    assert out.cost["wall_ms_total"] == 1200
    assert out.cost["tokens"] is None                  # 缺值＝UNKNOWN，不填 0
    # 標 synthetic
    assert out.synthetic is True
    # 提示是 localized（帶反例）
    assert "10674.83" in log[0]["prompt"]


def test_repair_fail_to_unknown_counts_as_not_fixed(task_dir, tmp_path):
    """fake agent 把源資料弄壞 ⇒ 重算變 UNKNOWN：不算修好、缺口仍在。"""
    rs = load_req_set(task_dir)
    draft = task_dir / BAD_DRAFT
    run = _fake_agent({"expenses.csv": "corrupted,not,a,valid\ngarbage"})
    out = repair.repair_slice(
        task_dir, rs, draft,
        out_root=tmp_path / "out", build=_fake_build([]), run=run,
        feedback_mode="localized", max_rounds=1, synthetic=True,
    )
    assert out.stopped != "gap_closed"
    assert FAIL_CLAIM not in out.fixed
    assert out.final_status[FAIL_CLAIM] == "UNKNOWN"
    assert FAIL_CLAIM in out.unresolved                # UNKNOWN 不得宣告完成
    assert out.cost["calls"] == 1


def test_repair_records_pass_to_fail_regression(task_dir, tmp_path):
    """fake agent 修了摘要但弄壞 CSV 結構 ⇒ 退步必須被記錄。"""
    rs = load_req_set(task_dir)
    draft = task_dir / BAD_DRAFT
    broken_csv = "category,total_amount\nit,3380.25\n"  # 缺 subcategory 欄位
    run = _fake_agent({"summary.md": _good_summary(task_dir),
                       "expense_summary.csv": broken_csv})
    out = repair.repair_slice(
        task_dir, rs, draft,
        out_root=tmp_path / "out", build=_fake_build([]), run=run,
        feedback_mode="localized", max_rounds=1, synthetic=True,
    )
    assert "req_csv_structure" in out.regressed
    assert out.final_status["req_csv_structure"] == "FAIL"
    assert out.stopped != "gap_closed"                 # 新出現的 FAIL ⇒ 缺口未閉


def test_kv_json_repair_slice_fail_to_pass_and_leak_guard(tmp_path: pathlib.Path):
    """G2 依賴核對（repair.py × checks.kv_recomputed .json，r992 redo）：.json 資料檔走完整切片——
    before 重算（FAIL，非垃圾 CSV 假 PASS）→ localized 提示 leak guard → fake agent 修正→
    工作區重驗（PASS，資料檔由 prepare_workspace 帶入）→ 原草稿未動。重算值（真計數 7）
    絕不進任何一臂提示。synthetic 離線接線，只驗管線。"""
    task_dir = tmp_path / "task"
    draft = tmp_path / "draft"
    task_dir.mkdir(parents=True)
    draft.mkdir(parents=True)
    (task_dir / "request.md").write_text(
        "How many tickets were late?\n（Answer must be just a number）\n", encoding="utf-8")
    rows = [{"day": str(i + 1), "late": 1} for i in range(7)] \
        + [{"day": "8", "late": 0}, {"day": "9", "late": 0}]
    (task_dir / "tickets.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")  # 真計數＝7
    (draft / "answer.txt").write_text("@late_count[0]\n", encoding="utf-8")
    rs = RequirementSet(task_id="t", items=[RequirementItem(
        id="req_main", quote="late_ticket_count", deliverable="answer.txt",
        verifier="kv_recomputed",
        params={"key": "late_count", "data_file": "tickets.json",
                "recompute": {"type": "count_if", "col": "late", "eq": 1}})])

    before = run_requirement_checks(task_dir, rs, draft)
    assert {c.claim_id: c.status for c in before}["req_main"] == "FAIL"   # .json 真重算（舊行為＝假 PASS）

    loc = repair.build_repair_prompt(task_dir, rs, draft, before, feedback_mode="localized")
    assert "req_main" in loc
    assert "late_ticket_count" in loc
    assert "0" in loc                # 交付物自身的值（可見反例）
    assert "7" not in loc            # 重算值不得進提示（leak guard）

    gen = repair.build_repair_prompt(task_dir, rs, draft, before, feedback_mode="generic")
    assert "late" in gen             # 原始需求兩臂都有
    assert "req_main" not in gen     # generic 不帶失敗證據
    assert "7" not in gen
    for p in (loc, gen):
        for bad in ("hidden/", "scorer.py", "/srv/eval"):
            assert bad not in p, bad

    # 完整切片：fake agent 寫對值→工作區重驗 PASS；原草稿逐位元組未動
    draft_hashes = _dir_hashes(draft)
    log: list[dict] = []
    run = _fake_agent({"answer.txt": "@late_count[7]\n"})
    out = repair.repair_slice(
        task_dir, rs, draft,
        out_root=tmp_path / "out", build=_fake_build(log), run=run,
        feedback_mode="localized", max_rounds=1, synthetic=True,
    )
    assert out.stopped == "gap_closed"
    assert "req_main" in out.fixed
    assert out.final_status["req_main"] == "PASS"   # 重驗從工作區的 .json 算出
    assert out.unresolved == ()
    assert (tmp_path / "out" / "round_1" / "tickets.json").is_file()  # 資料檔已帶入工作區
    assert _dir_hashes(draft) == draft_hashes       # 保留原候選
    assert out.cost["calls"] == 1
    assert out.cost["tokens"] is None               # 缺值＝UNKNOWN，不填 0
    assert out.synthetic is True
    assert "late_ticket_count" in log[0]["prompt"]  # 提示是 localized（帶條目）


def test_kv_json_corrupted_in_workspace_is_unknown_not_fixed(tmp_path: pathlib.Path):
    """fake agent 弄壞 .json 源資料⇒重驗 UNKNOWN（壞 JSON 分支）：不算修好、不得宣告完成。"""
    task_dir = tmp_path / "task"
    draft = tmp_path / "draft"
    task_dir.mkdir(parents=True)
    draft.mkdir(parents=True)
    (task_dir / "request.md").write_text("How many tickets were late?\n", encoding="utf-8")
    (task_dir / "tickets.json").write_text(
        json.dumps([{"day": "1", "late": 1}, {"day": "2", "late": 1}, {"day": "3", "late": 0}]),
        encoding="utf-8")
    (draft / "answer.txt").write_text("@late_count[0]\n", encoding="utf-8")
    rs = RequirementSet(task_id="t", items=[RequirementItem(
        id="req_main", quote="late_ticket_count", deliverable="answer.txt",
        verifier="kv_recomputed",
        params={"key": "late_count", "data_file": "tickets.json",
                "recompute": {"type": "count_if", "col": "late", "eq": 1}})])
    run = _fake_agent({"tickets.json": "{not json"})
    out = repair.repair_slice(
        task_dir, rs, draft,
        out_root=tmp_path / "out", build=_fake_build([]), run=run,
        feedback_mode="localized", max_rounds=1, synthetic=True,
    )
    assert out.stopped != "gap_closed"
    assert "req_main" not in out.fixed
    assert out.final_status["req_main"] == "UNKNOWN"
    assert "req_main" in out.unresolved              # UNKNOWN 不得宣告完成
    assert out.cost["calls"] == 1


def test_repair_outcome_fixed_must_be_pass_in_final_status_and_disjoint_from_unresolved(task_dir, tmp_path):
    """若某輪修好某條目但後續輪次未維持（或改壞），最終 outcome.fixed 嚴禁包含最終仍為 FAIL 的條目。
    outcome.fixed 與 outcome.unresolved 必須嚴格互斥。"""
    rs = load_req_set(task_dir)
    draft = task_dir / BAD_DRAFT
    calls = {"n": 0}

    def run(launch: Launch, *, workspace: pathlib.Path, timeout_s: float, log_dir: pathlib.Path) -> dict:
        calls["n"] += 1
        log_dir.mkdir(parents=True, exist_ok=True)
        (log_dir / "agent_stdout.log").write_text("{}", encoding="utf-8")
        (log_dir / "agent_stderr.log").write_text("", encoding="utf-8")
        if calls["n"] == 1:
            # 第 1 輪修好 summary.md，但弄壞 expense_summary.csv
            (workspace / "summary.md").write_text(_good_summary(task_dir), encoding="utf-8")
            (workspace / "expense_summary.csv").write_text("corrupted", encoding="utf-8")
        elif calls["n"] == 2:
            pass
        return {"rc": 0, "timed_out": False, "wall_ms": 100, "spawn_error": None,
                "stdout_log": str(log_dir / "agent_stdout.log"),
                "stderr_log": str(log_dir / "agent_stderr.log")}

    out = repair.repair_slice(
        task_dir, rs, draft,
        out_root=tmp_path / "out", build=_fake_build([]), run=run,
        feedback_mode="localized", max_rounds=2, synthetic=True,
    )
    # fixed 與 unresolved 必須互斥，嚴禁虛假宣告 fixed
    assert not (set(out.fixed) & set(out.unresolved)), (
        f"fixed {out.fixed} and unresolved {out.unresolved} must be disjoint!"
    )
    for cid in out.fixed:
        assert out.final_status.get(cid) == "PASS", (
            f"fixed claim {cid} must have final status PASS, got {out.final_status.get(cid)}"
        )



def test_repair_stops_after_two_no_progress_rounds(task_dir, tmp_path):
    """連續兩次修復沒有消除已確認缺口 ⇒ 停止，回傳停因及未解決項（不花第 3 次）。"""
    rs = load_req_set(task_dir)
    draft = task_dir / BAD_DRAFT
    run = _fake_agent(None)  # no-op：什麼都沒改
    out = repair.repair_slice(
        task_dir, rs, draft,
        out_root=tmp_path / "out", build=_fake_build([]), run=run,
        feedback_mode="generic", max_rounds=4, synthetic=True,
    )
    assert out.stopped == "stalled"
    assert len(out.rounds) == 2                        # 不是 4：兩次無進展即停
    assert out.cost["calls"] == 2
    assert out.cost["wall_ms_total"] == 2400
    assert FAIL_CLAIM in out.unresolved                # 停因＋未解決項都回傳
    assert out.final_status[FAIL_CLAIM] == "FAIL"


def test_repair_no_gap_makes_no_agent_call(task_dir, tmp_path):
    """草稿全部必需條目 PASS ⇒ 不呼叫模型（零成本、零呼叫）。"""
    rs = load_req_set(task_dir)
    run = _fake_agent(None)
    out = repair.repair_slice(
        task_dir, rs, task_dir / "good",
        out_root=tmp_path / "out", build=_fake_build([]), run=run,
        feedback_mode="localized", max_rounds=2, synthetic=True,
    )
    assert out.stopped == "no_gap"
    assert out.rounds == []
    assert out.cost["calls"] == 0
    assert out.cost["wall_ms_total"] is None           # 沒有呼叫＝沒有 wall time，不填 0


def test_repair_agent_crash_is_no_progress_and_reported(task_dir, tmp_path):
    """agent 執行失敗（spawn_error）＝該輪無進展、如實記錄，不假裝修好。"""
    rs = load_req_set(task_dir)
    draft = task_dir / BAD_DRAFT

    def run(launch, *, workspace, timeout_s, log_dir):
        return {"rc": None, "timed_out": False, "wall_ms": None,
                "spawn_error": "FileNotFoundError: no-such-agent"}

    out = repair.repair_slice(
        task_dir, rs, draft,
        out_root=tmp_path / "out", build=_fake_build([]), run=run,
        feedback_mode="localized", max_rounds=2, synthetic=True,
    )
    assert out.stopped == "stalled"
    assert out.rounds[0].agent["spawn_error"]
    assert FAIL_CLAIM in out.unresolved


def test_usage_parsed_from_agent_stdout(tmp_path):
    """成本從 agent 原始 usage 讀；有值才記錄，沒有就是 None。"""
    log = tmp_path / "agent_stdout.log"
    log.write_text(json.dumps({"message": "done",
                               "usage": {"inputTokens": 100, "outputTokens": 50}}),
                   encoding="utf-8")
    u = repair.parse_usage_from_log(log)
    assert u == {"input": 100, "output": 50, "total": 150}
    # 沒有 usage 的輸出 ⇒ None（UNKNOWN），不是 0
    log2 = tmp_path / "plain.log"
    log2.write_text("just text output\n", encoding="utf-8")
    assert repair.parse_usage_from_log(log2) is None
    assert repair.parse_usage_from_log(tmp_path / "missing.log") is None


def test_usage_parsed_from_pi_jsonl_stream(tmp_path):
    """pi --mode json 的 JSONL 事件流：逐事件 usage 加總；全零事件＝UNKNOWN。"""
    log = tmp_path / "agent_stdout.log"
    lines = [
        json.dumps({"type": "session", "id": "x"}),
        json.dumps({"type": "message_update",
                    "usage": {"input": 7479, "output": 419, "cacheRead": 0,
                              "totalTokens": 7898}}),
        json.dumps({"type": "message_update",
                    "usage": {"input": 10, "output": 5}}),
        json.dumps({"type": "agent_settled"}),
    ]
    log.write_text("\n".join(lines) + "\n", encoding="utf-8")
    u = repair.parse_usage_from_log(log)
    assert u == {"input": 7489, "output": 424, "total": 7913}
    # 只有全零 usage 事件 ⇒ 沒有真實 token 數 ⇒ None（不填 0）
    log2 = tmp_path / "zeros.log"
    log2.write_text(json.dumps({"type": "message_update",
                                "usage": {"input": 0, "output": 0, "totalTokens": 0}})
                    + "\n", encoding="utf-8")
    assert repair.parse_usage_from_log(log2) is None


def test_usage_counts_into_cost(task_dir, tmp_path):
    rs = load_req_set(task_dir)
    draft = task_dir / BAD_DRAFT
    run = _fake_agent({"summary.md": _good_summary(task_dir)},
                      stdout_json=json.dumps({"usage": {"inputTokens": 10, "outputTokens": 5}}))
    out = repair.repair_slice(
        task_dir, rs, draft,
        out_root=tmp_path / "out", build=_fake_build([]), run=run,
        feedback_mode="localized", max_rounds=1, synthetic=True,
    )
    assert out.cost["tokens"] == 15
    assert out.cost["token_source"] == "agent_stdout"


def _dir_hashes(d: pathlib.Path) -> dict[str, str]:
    return {str(p.relative_to(d)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(d.rglob("*")) if p.is_file()}


# ── CLI（可重跑的原生 pi 命令的離線對照）────────────────────────────

def test_main_exit_codes_and_json(task_dir, tmp_path, capsys):
    rs = load_req_set(task_dir)  # noqa: F841  (main 自己載)
    draft = task_dir / BAD_DRAFT
    # 修好 ⇒ exit 0
    run = _fake_agent({"summary.md": _good_summary(task_dir)})
    rc = repair.main(["--task", str(task_dir), "--draft", str(draft),
                      "--out", str(tmp_path / "out0"), "--rounds", "1",
                      "--synthetic", "--json"],
                     build=_fake_build([]), run=run)
    assert rc == 0
    body = json.loads(capsys.readouterr().out)
    assert body["stopped"] == "gap_closed"
    assert body["synthetic"] is True
    # 修不好 ⇒ exit 20
    tmp2 = tmp_path / "t2"
    shutil.copytree(G1_TASK, tmp2)
    rc2 = repair.main(["--task", str(tmp2), "--draft", str(tmp2 / BAD_DRAFT),
                       "--out", str(tmp_path / "out2"), "--rounds", "1",
                       "--synthetic", "--json"],
                      build=_fake_build([]), run=_fake_agent(None))
    assert rc2 == 20
    # agent 根本沒跑起來 ⇒ exit 22（infra）
    def dead(launch, *, workspace, timeout_s, log_dir):
        return {"rc": None, "timed_out": False, "wall_ms": None,
                "spawn_error": "FileNotFoundError: no-such-agent"}
    tmp3 = tmp_path / "t3"
    shutil.copytree(G1_TASK, tmp3)
    rc3 = repair.main(["--task", str(tmp3), "--draft", str(tmp3 / BAD_DRAFT),
                       "--out", str(tmp_path / "out3"), "--rounds", "1",
                       "--synthetic", "--json"],
                      build=_fake_build([]), run=dead)
    assert rc3 == 22


def test_selftest_command_all_green(capsys):
    """一條指令離線 selftest（r1008）：`--selftest` 用 synthetic G1 案例跑完整管線。
    全過 ⇒ rc=0、輸出每條一行＋成本缺值顯示 UNKNOWN（不填 0）；任一不過 ⇒ rc=1。"""
    rc = repair.main(["--selftest"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "SELFTEST: 7/7 PASS" in out
    assert "[7/7] ok" in out            # 退出碼 0/20＋成本缺值 UNKNOWN（check 7 內斷言）


def test_main_cli_supports_min_rounds_and_defaults_generic_to_one(task_dir, tmp_path):
    """CLI 支援 --min-rounds：
    - generic 臂預設 min_rounds=1（好草稿也至少跑 1 輪以重驗有無退步）
    - 顯式傳入 --min-rounds 0 則不呼叫 agent
    """
    good_draft = task_dir / "good"
    calls: list[int] = []

    def counting_agent(launch, *, workspace, timeout_s, log_dir):
        calls.append(1)
        log_dir.mkdir(parents=True, exist_ok=True)
        (log_dir / "agent_stdout.log").write_text("{}")
        return {"rc": 0, "timed_out": False, "wall_ms": 50, "spawn_error": None}

    # 1. generic 臂未顯式給 --min-rounds：預設 1 輪（不能 0 呼叫逃逸）
    rc = repair.main(
        ["--task", str(task_dir), "--draft", str(good_draft),
         "--out", str(tmp_path / "out_gen"), "--feedback-mode", "generic",
         "--synthetic", "--json"],
        build=_fake_build([]), run=counting_agent,
    )
    assert rc == 0
    assert len(calls) == 1, "generic 臂預設 min_rounds 應為 1，至少重驗 1 輪"

    # 2. 顯式給予 --min-rounds 0：好草稿直接 0 呼叫放行
    calls.clear()
    rc2 = repair.main(
        ["--task", str(task_dir), "--draft", str(good_draft),
         "--out", str(tmp_path / "out_zero"), "--feedback-mode", "generic",
         "--min-rounds", "0", "--synthetic", "--json"],
        build=_fake_build([]), run=counting_agent,
    )
    assert rc2 == 0
    assert len(calls) == 0, "顯式 --min-rounds 0 應為 0 呼叫"



# --- check_tag_format（自 auto/argon 198e5043 移植；r974 merge 保留 qwen 實作）---

# ── 直譯器 pin（dab_039 停因，r975；2026-11-04）────────────────────
# 根因：agent 的裸 python3 走 PATH 解析；冒煙時 venv 在 PATH 前但缺 scipy/numpy，
# 模型誤判科學堆疊不可用、兩輪均未產出交付物。pin＝env 層保證，不靠提示詞。

def test_pin_agent_python_puts_executable_bin_first():
    import os, sys
    l = Launch(argv=["pi"], env={"PATH": "/usr/bin:/bin"})
    repair.pin_agent_python(l)
    # 啟動路徑（venv 身份靠它），不 resolve symlink
    bindir = str(pathlib.Path(sys.executable).parent)
    assert l.env["PATH"].split(":")[0] == bindir
    assert l.env["VACANT_REPAIR_PYTHON"] == os.path.abspath(sys.executable)
    assert "/usr/bin" in l.env["PATH"].split(":")          # 原 PATH 條目保留


def test_pin_agent_python_dedupes_and_keeps_other_entries():
    import sys
    bindir = str(pathlib.Path(sys.executable).parent)
    l = Launch(argv=["pi"], env={"PATH": f"{bindir}:/usr/bin"})
    repair.pin_agent_python(l)
    entries = l.env["PATH"].split(":")
    assert entries.count(bindir) == 1                        # 不重複
    assert "/usr/bin" in entries


def test_pin_agent_python_failopen_when_interpreter_missing():
    l = Launch(argv=["pi"], env={"PATH": "/usr/bin"})
    before = dict(l.env)
    repair.pin_agent_python(l, python="/nonexistent/python3.9")
    assert l.env == before                                   # 找不到直譯器＝不動 env


def test_default_build_pins_python_into_launch_env():
    import sys
    build = repair._default_build(None, None, hooks=False)
    l = build("prompt", pathlib.Path("/tmp"))
    bindir = str(pathlib.Path(sys.executable).parent)
    assert l.env["PATH"].split(":")[0] == bindir


def test_pin_survives_venv_symlink():
    """venv 的 bin/python 是指向基礎直譯器的 symlink；pin 到的是啟動路徑（venv），
    agent 端 import 到 venv 的 site-packages，不是基礎直譯器的。"""
    import subprocess, sys
    build = repair._default_build(None, None, hooks=False)
    l = build("prompt", pathlib.Path("/tmp"))
    r = subprocess.run(
        ["bash", "-c", "command -v python3; python3 -c 'import scipy, numpy; print(scipy.__version__)'"],
        env=dict(l.env), capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    first = r.stdout.splitlines()[0]
    assert pathlib.Path(first).parent == pathlib.Path(sys.executable).parent, first
    # 若 venv 與基礎直譯器的 scipy 版本不同，這裡就抓得到 pin 失效
    import scipy as venv_scipy
    assert venv_scipy.__version__ in r.stdout, r.stdout


def test_g2_default_build_pins_python_too():
    """g2 曾有一份未 pin 的 _default_build 副本（drift 來源）——兩處必須同一行為。"""
    import sys
    from vacant_network.reqloop import g2
    build = g2._default_build(None, None, hooks=False)
    l = build("prompt", pathlib.Path("/tmp"))
    bindir = str(pathlib.Path(sys.executable).parent)
    assert l.env["PATH"].split(":")[0] == bindir


def test_tag_format_verifier(tmp_path: pathlib.Path):
    item = RequirementItem(
        id="c1",
        quote="quote",
        deliverable="answer.txt",
        verifier="tag_format",
        kind="explicit",
        params={"file": "answer.txt", "tag": "mean_val", "value_type": "integer"},
    )

    # 1. missing file
    res = check_tag_format(tmp_path, item)
    assert res.status == "FAIL"
    assert "缺少指定檔案" in res.detail

    # 2. missing brackets: @mean_val1234
    (tmp_path / "answer.txt").write_text("@mean_val1234\n", encoding="utf-8")
    res = check_tag_format(tmp_path, item)
    assert res.status == "FAIL"
    assert "缺少方括號" in res.detail

    # 3. float with decimal when integer required: @mean_val[1234.56]
    (tmp_path / "answer.txt").write_text("@mean_val[1234.56]\n", encoding="utf-8")
    res = check_tag_format(tmp_path, item)
    assert res.status == "FAIL"
    assert "包含小數點" in res.detail

    # 4. correct positive integer: @mean_val[1234]
    (tmp_path / "answer.txt").write_text("@mean_val[1234]\n", encoding="utf-8")
    res = check_tag_format(tmp_path, item)
    assert res.status == "PASS"


# ── r996 兩個缺口（TDD 先紅）────────────────────────────────────────

def test_stall_budget_not_reset_by_nonrequired_fix(task_dir, tmp_path):
    """停滯決策只看已確認缺口（必需 FAIL）：非必需項 FAIL→PASS 不算進度。

    若把它算進度（缺陷）：每輪 diff 都對照原草稿，一次非必需修復會**每一輪**都重置
    停滯預算，迴圈燒盡 max_rounds。規則原文：「連續兩次修復沒有消除已確認缺口⇒停止」
    ——已確認缺口（req_group_recompute）從未消除，第 2 次無進展就必須停（2 呼叫，不是 4）。
    """
    import dataclasses
    rs = load_req_set(task_dir)
    items = [dataclasses.replace(it, id="req_optional_total", required=False)
             if it.id == FAIL_CLAIM else it for it in rs.items]
    rs2 = RequirementSet(task_id=rs.task_id, items=items)

    draft = task_dir / "bad_round_each_row"   # 必需 group FAIL ＋ 非必需 summary FAIL
    before = run_requirement_checks(task_dir, rs2, draft)
    st = {c.claim_id: c.status for c in before}
    assert st["req_group_recompute"] == "FAIL"
    assert st["req_optional_total"] == "FAIL"

    # agent 每輪只修非必需的 summary（CSV 不碰）
    run = _fake_agent({"summary.md": _good_summary(task_dir)})
    out = repair.repair_slice(
        task_dir, rs2, draft,
        out_root=tmp_path / "out", build=_fake_build([]), run=run,
        feedback_mode="localized", max_rounds=4, synthetic=True,
    )
    assert out.stopped == "stalled"            # 不是 max_rounds：已確認缺口從未消除
    assert out.cost["calls"] == 2              # 兩次無進展即停，不燒 4 次
    assert "req_group_recompute" in out.unresolved
    assert "req_optional_total" in out.fixed   # 非必需的修復如實記錄（fixed 不受影響）


def test_main_no_gap_but_unverified_is_rejected_not_infra(task_dir, tmp_path, capsys):
    """無必需 FAIL（0 呼叫）但有必需項 UNKNOWN（源資料缺失）：退出碼＝20（未驗證、拒收），
    不是 22（infra）。22 保留給「agent 應該跑但沒跑起來」；把『未驗證』誤報成 infra
    會誤導呼叫方去重試/查基建——裁決是『未驗證』，不是『基建壞了』。
    """
    d = tmp_path / "t"
    shutil.copytree(task_dir, d)
    (d / "expenses.csv").unlink()              # 重算檢查 → UNKNOWN（不自評）
    log: list[dict] = []
    rc = repair.main(["--task", str(d), "--draft", str(d / "good"),
                      "--out", str(tmp_path / "o"), "--rounds", "2",
                      "--feedback-mode", "localized", "--synthetic", "--json"],
                     build=_fake_build(log), run=_fake_agent(None))
    body = json.loads(capsys.readouterr().out)
    assert rc == 20                            # 現行為 22（誤標 infra）
    assert body["stopped"] == "no_gap"
    assert log == []                           # 零呼叫是設計（缺口驅動），不是基建故障
    assert "req_group_recompute" in body["unresolved"]
    assert "req_summary_numbers" in body["unresolved"]


# ── argon 0f0a6a0d：預設 include_dirs=('data',)（TDD）──────────────────

def test_repair_slice_and_cli_default_include_dirs_data(tmp_path: pathlib.Path):
    """修復切片與 CLI 必須預設帶入 data/ 目錄：
    真實任務（DABench/DABStep）的資料檔普遍置於 data/ 子目錄。
    若 repair_slice 與 CLI 未預設 include_dirs=('data',)，
    工作區缺少 data/ 目錄，會導致：
    1. agent 在無資料環境下執行；
    2. 重驗因資料檔缺失誤判 UNKNOWN，好草稿被冤枉成 PASS→UNKNOWN 退步。
    本測試驗證：
    - repair_slice 預設帶入 data/
    - repair.main CLI 預設帶入 data/，且支援 --include-dirs 參數
    """
    task_dir = tmp_path / "task"
    draft_dir = tmp_path / "draft"
    data_dir = task_dir / "data"
    data_dir.mkdir(parents=True)
    draft_dir.mkdir(parents=True)

    (task_dir / "request.md").write_text("Report total amount\n", encoding="utf-8")
    (data_dir / "records.json").write_text(json.dumps([{"val": 10}, {"val": 20}]), encoding="utf-8")
    (draft_dir / "answer.txt").write_text("@total[1]\n", encoding="utf-8")

    rs = RequirementSet(task_id="t", items=[RequirementItem(
        id="req_total", quote="total", deliverable="answer.txt",
        verifier="kv_recomputed",
        params={"key": "total", "data_file": "data/records.json",
                "recompute": {"type": "count_if", "col": "val", "eq": 10}}
    )])

    # 1. 測試 repair_slice 預設 include_dirs
    out1 = tmp_path / "out1"
    res1 = repair.repair_slice(
        task_dir, rs, draft_dir, out1,
        build=_fake_build([]),
        run=_fake_agent(None),
        feedback_mode="generic",
        min_rounds=1,
    )
    assert (out1 / "round_1" / "data" / "records.json").is_file(), "工作區必須預設包含 data/records.json"
    assert res1.final_status["req_total"] == "PASS", "資料檔不應缺失，應成功判定為 PASS"

    # 2. 測試 CLI 預設帶入 data/
    out2 = tmp_path / "out2"
    (task_dir / "requirements.json").write_text(json.dumps(rs.to_dict()), encoding="utf-8")
    rc = repair.main(
        ["--task", str(task_dir), "--draft", str(draft_dir),
         "--out", str(out2), "--feedback-mode", "generic",
         "--synthetic", "--json"],
        build=_fake_build([]),
        run=_fake_agent(None),
    )
    assert rc == 0
    assert (out2 / "round_1" / "data" / "records.json").is_file(), "CLI 工作區必須預設包含 data/records.json"

    # 3. 測試 CLI 支援 --include-dirs 自訂目錄
    custom_dir = task_dir / "custom"
    custom_dir.mkdir(parents=True)
    (custom_dir / "extra.txt").write_text("extra", encoding="utf-8")
    out3 = tmp_path / "out3"
    rc_custom = repair.main(
        ["--task", str(task_dir), "--draft", str(draft_dir),
         "--out", str(out3), "--feedback-mode", "generic",
         "--include-dirs", "data", "custom",
         "--synthetic", "--json"],
        build=_fake_build([]),
        run=_fake_agent(None),
    )
    assert rc_custom == 0
    assert (out3 / "round_1" / "custom" / "extra.txt").is_file(), "--include-dirs 自訂目錄必須進工作區"
