"""
G2 真草稿冒煙測試（工單 P000-20261104-02-real-draft-smoke，2026-11-04）。

範圍（工單紅線）：
- 6 格（3 真草稿 × generic/localized）只驗管線，不宣稱任何提升。
- 兩臂同模型、同總預算；成本缺值＝UNKNOWN（None），絕不填 0。
- hidden 分只引用既有受權量表的已記錄結果（score.json），不餵給模型、不在本地重跑。
- 阻塞就列最小接線工單，不等待。

本檔用 fake agent 離線接線（synthetic 假裝真跑），只驗：
1. answer_kv 驗證器（@key[value] 答案檔格式）的判定與證據；
2. repair_slice 的 min_rounds：無缺口時 generic 臂仍做 1 次重驗、localized 臂 0 呼叫；
3. g2 入口：凍結 manifest、6 格計畫、--dry-run 輸出、真跑結果結構（含 hidden-after=UNKNOWN）。
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import shutil

import pytest

from vacant_network.adapters.agents import Launch
from vacant_network.reqloop import g2, repair
from vacant_network.reqloop.checks import run_requirement_checks
from vacant_network.reqloop.requirements import RequirementSet

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
SMOKE = REPO_ROOT / "ops" / "reqloop" / "g2" / "smoke"
MANIFEST = SMOKE / "manifest.json"
MULTIDELIV_MANIFEST = REPO_ROOT / "ops" / "reqloop" / "g2" / "multideliv" / "manifest.json"
REALTASK_MANIFEST = REPO_ROOT / "ops" / "reqloop" / "g2" / "realtask_manifest.json"


# ── 工具 ─────────────────────────────────────────────────────────────

def _sha(p: pathlib.Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _dir_hashes(d: pathlib.Path) -> dict[str, str]:
    return {str(p.relative_to(d)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(d.rglob("*")) if p.is_file()}


def _fake_build(log: list[dict]):
    def build(prompt: str, ws: pathlib.Path) -> Launch:
        log.append({"prompt": prompt, "ws": str(ws)})
        return Launch(argv=["true"], note="fake")
    return build


def _fake_run(ws_files: dict[str, str] | None = None, *, fail: bool = False):
    def run(launch: Launch, *, workspace: pathlib.Path, timeout_s: float,
            log_dir: pathlib.Path) -> dict:
        for name, text in (ws_files or {}).items():
            p = pathlib.Path(workspace) / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text, encoding="utf-8")
        log_dir.mkdir(parents=True, exist_ok=True)
        (log_dir / "agent_stdout.log").write_text("{}", encoding="utf-8")
        (log_dir / "agent_stderr.log").write_text("", encoding="utf-8")
        return {"rc": 0 if not fail else 127, "timed_out": False, "wall_ms": 900,
                "spawn_error": "NoModuleNamed" if fail else None,
                "stdout_log": str(log_dir / "agent_stdout.log"),
                "stderr_log": str(log_dir / "agent_stderr.log")}
    return run


def _item(verifier: str, deliverable: str, params: dict, quote: str = "q",
          required: bool = True, authority: str = "user_request"):
    from vacant_network.reqloop.requirements import RequirementItem
    return RequirementItem(id="req_x", quote=quote, deliverable=deliverable,
                           verifier=verifier, kind="explicit", params=params,
                           description="d", required=required, authority=authority)


# ── 凍結資料存在（工單：先凍結清單再跑）────────────────────────────

def test_smoke_fixtures_frozen():
    assert MANIFEST.is_file(), "G2 smoke manifest 未凍結"
    man = g2.G2Manifest.load(MANIFEST)
    assert len(man.drafts) == 3
    roles = {d["role"] for d in man.drafts}
    assert roles == {"bad", "good"}
    cells = g2.plan_cells(man)
    assert len(cells) == 6
    assert {c[1] for c in cells} == set(man.arms)
    # 每個 draft 都有來源、hash、已記錄 hidden 分
    for d in man.drafts:
        assert d["source"]["cell"] and d["source"]["score"] is not None
        assert d["draft"]["files"] and all(_is64(v) for v in d["draft"]["files"].values())
        assert d["task"]["requirements"]["sha256"]
        # 凍結副本真的在 repo 裡，且 hash 對得上
        base = MANIFEST.parent
        for rel, h in d["draft"]["files"].items():
            assert (base / d["draft"]["dir"] / rel).is_file()
            assert _sha(base / d["draft"]["dir"] / rel) == h
        assert _sha(base / d["task"]["dir"] / "requirements.json") == d["task"]["requirements"]["sha256"]


def _is64(s: str) -> bool:
    return isinstance(s, str) and len(s) == 64 and all(c in "0123456789abcdef" for c in s)


def test_multideliv_manifest_frozen():
    """P20261106_0834-2：多交付物局部修復最小對照＝orders_monthly 2 份真失敗草稿
    × 2 臂（generic/localized）＝4 格；凍結結構、凍結副本存在性、預算釘住
    （max_rounds_per_cell=1、max_tool_calls=60、max_tokens=4000000）。
    本批只驗管線與保留指標，不宣稱任何真模型效果；零模型呼叫。"""
    assert MULTIDELIV_MANIFEST.is_file(), "多交付物最小對照 manifest 未凍結"
    man = g2.G2Manifest.load(MULTIDELIV_MANIFEST)
    assert set(man.arms) == {"generic", "localized"}
    assert len(man.drafts) == 2
    names = {d["name"] for d in man.drafts}
    assert names == {"orders_monthly_bad_missing_top_products",
                     "orders_monthly_bad_summary_number_mismatch"}
    cells = g2.plan_cells(man)
    assert len(cells) == 4 and {c[1] for c in cells} == {"generic", "localized"}
    for d in man.drafts:
        assert d["task_id"] == "orders_monthly" and d["role"] == "bad"
        # 保留意圖：恰一份已滿足＋一份未滿足交付物（本切片的存在理由）
        p = d["preservation"]
        assert set(p["satisfied"]) | set(p["unsatisfied"]) == {"summary.md", "monthly_sales.csv"}
        assert len(p["satisfied"]) == 1 and len(p["unsatisfied"]) == 1
        if d["name"] == "orders_monthly_bad_missing_top_products":
            assert p["satisfied"] == ["summary.md"]
            assert p["unsatisfied"] == ["monthly_sales.csv"]
        else:
            assert p["satisfied"] == ["monthly_sales.csv"]
            assert p["unsatisfied"] == ["summary.md"]
        # 凍結副本真的在 repo 裡，且 hash 對得上（同 smoke 口徑）
        base = MULTIDELIV_MANIFEST.parent
        for rel, h in d["draft"]["files"].items():
            f = base / d["draft"]["dir"] / rel
            assert f.is_file(), f"凍結交付檔缺失：{f}"
            assert _sha(f) == h, f"凍結交付檔 hash 不符：{f}"
        assert _sha(base / d["task"]["dir"] / "requirements.json") == d["task"]["requirements"]["sha256"]
        assert d["source"]["score"] is not None   # 來源分數如實記錄（synthetic 亦不得 null）
    # 預算釘住（工單：單輪、硬上限齊備；未發射＝0 模型呼叫）
    b = man.budget
    assert b["max_rounds_per_cell"] == 1
    assert b["max_tool_calls"] == 60
    assert b["max_tokens"] == 4000000


def test_multideliv_localized_prompt_leak_free():
    """R20261106_1121-1（資深審查 2026-11-06 #3）：multideliv 的 localized 修復提示詞
    不得攜帶重算答案（UltraWide Monitor / Ergonomic Mouse / 88000）。

    兩份草稿：localized 提示詞仍點名未滿足交付物＋失敗條目（非空洞、修復目標仍在），
    但任何重算答案都不出現。verify_frozen 在改動 requirements.json 後仍須通過
    （requirements.sha256 更新、request.sha256 補釘）。零模型呼叫。"""
    base = MULTIDELIV_MANIFEST.parent
    man = g2.G2Manifest.load(MULTIDELIV_MANIFEST)
    man.verify_frozen(base)   # 改動 requirements.json 後凍結仍須驗過
    req_set = RequirementSet.load(base / "task" / "requirements.json")
    # 本任務用到的重算類 verifier 必須全部 opt-out 洩漏（期望值不進 detail/evidence）
    recomputing = {"monthly_sales_metrics", "monthly_top_products", "summary_metrics_consistency"}
    assert recomputing & {it.verifier for it in req_set.items}, "測試空洞：multideliv 無重算類 verifier"
    for it in req_set.items:
        if it.verifier in recomputing:
            assert it.params.get("expected_in_evidence") is False, \
                f"{it.id}（{it.verifier}）須設 expected_in_evidence=false"
    NEEDLES = ("UltraWide Monitor", "Ergonomic Mouse", "Mechanical Keyboard", "88000")
    for d in man.drafts:
        assert "request" in d["task"] and _is64(d["task"]["request"].get("sha256", "")), \
            f"{d['name']}: manifest 須補釘 task.request.sha256"
        task_dir = base / d["task"]["dir"]
        draft_dir = base / d["draft"]["dir"]
        before = run_requirement_checks(task_dir, req_set, draft_dir)
        failing = [c for c in before if c.status != "PASS"]
        assert failing, f"{d['name']}: 無 FAIL 條目（測試空洞）"
        prompt = repair.build_repair_prompt(task_dir, req_set, draft_dir, before, feedback_mode="localized")
        assert any(c.claim_id in prompt for c in failing), \
            f"{d['name']}: 失敗條目未進 localized 提示（修復目標丟失）"
        for n in NEEDLES:
            assert n not in prompt, f"{d['name']}: localized 提示洩重算答案 {n!r}"


def test_realtask_manifest_frozen_and_leakfree():
    """P20261106_1840-2：真實 CSV/JSON 任務切片 4 格最小對照＝e013 dab_055-pi-C
    （CSV estimated_numbers.csv 均值）＋e014 dabstep-1273-pi-C（JSON fees.json 費率）
    兩份真實歷史失敗草稿（synthetic=false、lab 記錄 pass=False）× generic/localized＝4 格；
    單輪硬上限釘住（300s/60 calls/4M tok）；NOT_fired（0 模型呼叫）。
    localized 提示詞點名未滿足條目事實，但絕不洩漏重算答案（1628／0.020500）。"""
    assert REALTASK_MANIFEST.is_file(), "真實任務切片 manifest 未凍結"
    man = g2.G2Manifest.load(REALTASK_MANIFEST)
    base = REALTASK_MANIFEST.parent
    man.verify_frozen(base)   # 凍結副本（smoke_e013/smoke_e014 既有凍結目錄）hash 須全部對上
    assert man.raw.get("status") == "NOT_fired", "本批只凍結計畫、不發射"
    assert set(man.arms) == {"generic", "localized"}
    names = {d["name"] for d in man.drafts}
    assert names == {"dab_055-pi-C", "dabstep-1273-pi-C"}
    cells = g2.plan_cells(man)
    assert len(cells) == 4 and {c[1] for c in cells} == {"generic", "localized"}
    b = man.budget
    assert b["max_rounds_per_cell"] == 1
    assert b["timeout_s_per_round"] == 300
    assert b["max_tool_calls"] == 60
    assert b["max_tokens"] == 4000000
    assert b["hard_token_cap"] is False
    NEEDLES = ("1628", "0.020500")   # 兩題重算答案（驗收針；絕不得進 localized 提示）
    for d in man.drafts:
        assert d["synthetic"] is False, f"{d['name']}: 真實任務切片須 synthetic=false"
        assert d["source"]["score"] is not None and d["source"]["score"].get("pass") is False, \
            f"{d['name']}: 來源須為已記錄 pass=False 的真實失敗草稿"
        task_dir = base / d["task"]["dir"]
        draft_dir = base / d["draft"]["dir"]
        req_set = RequirementSet.load(task_dir / "requirements.json")
        before = run_requirement_checks(task_dir, req_set, draft_dir)
        failing = [c for c in before if c.status != "PASS"]
        assert failing, f"{d['name']}: 初始驗無 FAIL 條目（測試空洞）"
        prompt = repair.build_repair_prompt(task_dir, req_set, draft_dir, before,
                                            feedback_mode="localized")
        assert any(c.claim_id in prompt for c in failing), \
            f"{d['name']}: 未滿足條目未進 localized 提示（修復目標丟失）"
        for n in NEEDLES:
            assert n not in prompt, f"{d['name']}: localized 提示洩重算答案 {n!r}"


# ── answer_kv 驗證器 ────────────────────────────────────────────────

@pytest.fixture()
def kv_task(tmp_path: pathlib.Path) -> pathlib.Path:
    d = tmp_path / "task"
    (d / "data").mkdir(parents=True)
    (d / "request.md").write_text("Answer format: @removed_outliers_count[count]", encoding="utf-8")
    rs = RequirementSet(task_id="kvtest", items=[
        _item("answer_kv", "answer.txt",
              {"keys": [{"key": "removed_outliers_count", "type": "nonneg_int"},
                        {"key": "p", "type": "number_in_01"}]})
    ])
    (d / "requirements.json").write_text(json.dumps(rs.to_dict()), encoding="utf-8")
    return d


def test_answer_kv_missing_file_fails(kv_task):
    out = kv_task / "draft"
    out.mkdir()
    res = run_requirement_checks(kv_task, RequirementSet.load(kv_task / "requirements.json"), out)
    assert res[0].status == "FAIL"
    assert res[0].evidence.get("missing_file") == "answer.txt"


def test_answer_kv_missing_key_fails_with_counterexample(kv_task):
    out = kv_task / "draft"
    out.mkdir()
    (out / "answer.txt").write_text("@removed_outliers_count[3]\n", encoding="utf-8")
    res = run_requirement_checks(kv_task, RequirementSet.load(kv_task / "requirements.json"), out)
    assert res[0].status == "FAIL"
    ce = res[0].evidence["counterexamples"]
    assert any(c.get("key") == "p" and c.get("problem") == "missing" for c in ce)


def test_answer_kv_bad_value_fails(kv_task):
    out = kv_task / "draft"
    out.mkdir()
    (out / "answer.txt").write_text("@removed_outliers_count[-2]\n@p[0.41]\n", encoding="utf-8")
    res = run_requirement_checks(kv_task, RequirementSet.load(kv_task / "requirements.json"), out)
    assert res[0].status == "FAIL"
    ce = {c["key"]: c["problem"] for c in res[0].evidence["counterexamples"]}
    assert ce["removed_outliers_count"] == "not_nonneg_int"


def test_answer_kv_range_violation_fails(kv_task):
    out = kv_task / "draft"
    out.mkdir()
    (out / "answer.txt").write_text("@removed_outliers_count[0]\n@p[1.41]\n", encoding="utf-8")
    res = run_requirement_checks(kv_task, RequirementSet.load(kv_task / "requirements.json"), out)
    assert res[0].status == "FAIL"
    ce = {c["key"]: c["problem"] for c in res[0].evidence["counterexamples"]}
    assert ce["p"] == "out_of_01"


def test_answer_kv_pass_and_evidence(kv_task):
    out = kv_task / "draft"
    out.mkdir()
    (out / "answer.txt").write_text("@removed_outliers_count[2]\n@p[0.042]\n", encoding="utf-8")
    res = run_requirement_checks(kv_task, RequirementSet.load(kv_task / "requirements.json"), out)
    assert res[0].status == "PASS"
    assert res[0].evidence["checked_keys"] == ["removed_outliers_count", "p"]


def test_answer_kv_duplicate_key_fails(kv_task):
    out = kv_task / "draft"
    out.mkdir()
    (out / "answer.txt").write_text("@removed_outliers_count[2]\n@removed_outliers_count[5]\n@p[0.5]\n",
                                   encoding="utf-8")
    res = run_requirement_checks(kv_task, RequirementSet.load(kv_task / "requirements.json"), out)
    assert res[0].status == "FAIL"
    ce = {c["key"]: c["problem"] for c in res[0].evidence["counterexamples"]}
    assert ce["removed_outliers_count"] == "ambiguous"


# ── min_rounds：無缺口時 generic 重驗、localized 0 呼叫 ─────────────

@pytest.fixture()
def g1_task(tmp_path: pathlib.Path) -> pathlib.Path:
    src = REPO_ROOT / "ops" / "reqloop" / "g1" / "tasks" / "expense_category"
    d = tmp_path / "task"
    shutil.copytree(src, d)
    return d


def test_min_rounds_zero_no_gap_zero_calls(g1_task, tmp_path: pathlib.Path):
    """localized 語義（min_rounds=0）：無缺口 ⇒ 0 模型呼叫。"""
    rs = RequirementSet.load(g1_task / "requirements.json")
    good = g1_task / "good"
    log: list[dict] = []
    out = repair.repair_slice(g1_task, rs, good, tmp_path / "o1",
                              _fake_build(log), _fake_run(), "localized",
                              max_rounds=2, timeout_s=30, synthetic=True, min_rounds=0)
    assert out.stopped == repair.STOP_NO_GAP
    assert log == []
    assert out.cost["calls"] == 0
    assert out.cost["model_calls"] == 0   # 零模型活動：0 次 API 呼叫是完整事實（agent 未啟動）


def test_min_rounds_one_no_gap_runs_one_recheck(g1_task, tmp_path: pathlib.Path):
    """generic 語義（min_rounds=1）：無缺口也要重驗 1 次，重驗後仍全 PASS ⇒ 停 GAP_CLOSED。"""
    rs = RequirementSet.load(g1_task / "requirements.json")
    good = g1_task / "good"
    log: list[dict] = []
    out = repair.repair_slice(g1_task, rs, good, tmp_path / "o2",
                              _fake_build(log), _fake_run(), "generic",
                              max_rounds=2, timeout_s=30, synthetic=True, min_rounds=1)
    assert len(log) == 1
    assert out.stopped == repair.STOP_GAP_CLOSED
    assert out.cost["calls"] == 1                     # 修復 session（agent 啟動）數
    assert out.cost["model_calls"] is None            # fake 無原始 usage ⇒ UNKNOWN（不拿 session 數頂替）


def test_min_rounds_one_recheck_breaks_regression_recorded(g1_task, tmp_path: pathlib.Path):
    """generic 重驗把對的改壞 ⇒ 退步必須記錄；且第 2 輪承接第 1 輪候選（累積修復，
    P000-20261105-01）：第 1 輪改壞（PASS→FAIL 被記錄）；第 2 輪承接壞狀態、修回 ⇒
    停 GAP_CLOSED。退步仍留在 regressed 與第 1 輪 diff（不被最終修回隱藏）。
    原草稿逐位元組未動（保留原候選）。"""
    rs = RequirementSet.load(g1_task / "requirements.json")
    good = g1_task / "good"
    good_md = (good / "summary.md").read_text(encoding="utf-8")
    bad_md = (g1_task / "bad_grand_total_wrong" / "summary.md").read_text(encoding="utf-8")
    good_hashes = _dir_hashes(good)

    def run(launch: Launch, *, workspace: pathlib.Path, timeout_s: float,
            log_dir: pathlib.Path) -> dict:
        ws = pathlib.Path(workspace)
        if ws.name == "round_1":
            # 第 1 輪（好草稿起）：把對的改壞 ⇒ PASS→FAIL 必須被記錄
            (ws / "summary.md").write_text(bad_md, encoding="utf-8")
        else:
            # 第 2 輪承接第 1 輪的壞狀態（累積修復）：修回
            (ws / "summary.md").write_text(good_md, encoding="utf-8")
        log_dir = pathlib.Path(log_dir)
        log_dir.mkdir(parents=True, exist_ok=True)
        (log_dir / "agent_stdout.log").write_text("{}", encoding="utf-8")
        (log_dir / "agent_stderr.log").write_text("", encoding="utf-8")
        return {"rc": 0, "timed_out": False, "wall_ms": 500, "spawn_error": None,
                "stdout_log": str(log_dir / "agent_stdout.log"),
                "stderr_log": str(log_dir / "agent_stderr.log")}

    out = repair.repair_slice(g1_task, rs, good, tmp_path / "o3",
                              _fake_build([]), run, "generic",
                              max_rounds=2, timeout_s=30, synthetic=True, min_rounds=1)
    # 第 1 輪退步（PASS→FAIL）被記錄，不被最終修回隱藏
    assert "req_summary_numbers" in out.regressed
    assert "req_summary_numbers" in out.rounds[0].diff.regressed
    # 第 2 輪承接第 1 輪的壞狀態並修回（相鄰輪差異＝修復）⇒ 全 PASS ⇒ 停 GAP_CLOSED
    assert out.rounds[1].diff.fixed == ("req_summary_numbers",)
    assert out.stopped == repair.STOP_GAP_CLOSED
    assert out.final_status["req_summary_numbers"] == "PASS"
    # 原草稿保留（第 1 輪的改壞只發生在 round_1/ 工作區）
    assert (tmp_path / "o3" / "round_1" / "summary.md").read_text(encoding="utf-8") == bad_md
    assert _dir_hashes(good) == good_hashes


def test_include_dirs_copies_data_but_not_reference_dirs(g1_task, tmp_path):
    """include_dirs 只把白名單子目錄（data/）帶進工作區；good/bad 參考目錄永不入場。"""
    (g1_task / "data").mkdir()
    (g1_task / "data" / "x.csv").write_text("a\n1\n", encoding="utf-8")
    ws = repair.prepare_workspace(g1_task, g1_task / "good", tmp_path / "ws",
                                  include_dirs=("data",))
    assert (ws / "data" / "x.csv").is_file()
    assert not (ws / "good").exists()
    assert not (ws / "bad_grand_total_wrong").exists()


# ── g2 入口：dry-run 與真跑（fake agent）────────────────────────────

def test_dry_run_lists_3_drafts_6_cells_and_budget():
    man = g2.G2Manifest.load(MANIFEST)
    txt = g2.dry_run_text(man)
    assert "3 drafts" in txt and "6 cells" in txt
    for d in man.drafts:
        assert d["name"] in txt
        assert d["source"]["cell"] in txt
    assert "max_rounds_per_cell=2" in txt
    assert "timeout_s_per_round=300" in txt
    assert "hard_token_cap=false" in txt
    assert "qwen/qwen3.8-27b" in txt


def test_dry_run_json_is_machine_readable():
    man = g2.G2Manifest.load(MANIFEST)
    j = g2.dry_run_json(man)
    assert j["schema"] == g2.RESULT_SCHEMA
    assert len(j["drafts"]) == 3 and len(j["cells"]) == 6
    assert j["budget"]["hard_token_cap"] is False


def test_dry_run_text_shows_hard_caps_explicitly():
    """r1095：dry-run 是發射前唯一的驗看，但人看文字 budget 行不顯示
    max_tool_calls/max_tokens（6a360204 引入）——dry_run_json 有（整包 dump
    budget）、文字行沒有，兩份出口不一致。dabstep-10 長尾（148 calls / 5.87M tok）
    之後，控本靠發射前看得到上限；H-0 教訓：綠燈來自漏掉的 flag 正是要防的洞。
    未設＝顯式 none（不量不殺、舊路徑），不是隱藏、也不是 UNKNOWN（值缺失）；
    設了＝顯示數值，與 dry_run_json 同值。離線，零模型呼叫。
    """
    man = g2.G2Manifest.load(MANIFEST)
    txt = g2.dry_run_text(man)
    # 原始 manifest 無 cap 欄⇒顯式 none（不得缺席、不得填 0/UNKNOWN）
    assert "max_tool_calls=none" in txt
    assert "max_tokens=none" in txt
    # manifest budget 設了⇒顯示數值，且與 dry_run_json 的 budget 同值
    man.budget["max_tool_calls"] = 40
    man.budget["max_tokens"] = 8_000_000
    txt2 = g2.dry_run_text(man)
    assert "max_tool_calls=40" in txt2
    assert "max_tokens=8000000" in txt2
    j2 = g2.dry_run_json(man)
    assert j2["budget"]["max_tool_calls"] == 40
    assert j2["budget"]["max_tokens"] == 8_000_000


def test_run_g2_smoke_fake_six_cells(tmp_path):
    """6 格全出結果；localized 無缺口格＝0 呼叫；hidden-after 一律 UNKNOWN。"""
    man = g2.G2Manifest.load(MANIFEST)
    base = MANIFEST.parent
    rs_by_task = {
        d["task_id"]: RequirementSet.load(base / d["task"]["dir"] / "requirements.json")
        for d in man.drafts
    }

    def build(prompt: str, ws: pathlib.Path) -> Launch:
        return Launch(argv=["true"], note="fake")

    def run(launch: Launch, *, workspace: pathlib.Path, timeout_s: float,
            log_dir: pathlib.Path) -> dict:
        # 模擬修復模型：把 answer.txt 補成合法格式（值不保證正確＝hidden 領域）
        if "dab_039" in str(workspace):
            (workspace / "answer.txt").write_text(
                "@is_normal[0.31]\n@transformed_importance_score_mean[4.2]\n"
                "@transformed_importance_score_std[1.1]\n", encoding="utf-8")
        log_dir.mkdir(parents=True, exist_ok=True)
        (log_dir / "agent_stdout.log").write_text("{}", encoding="utf-8")
        (log_dir / "agent_stderr.log").write_text("", encoding="utf-8")
        return {"rc": 0, "timed_out": False, "wall_ms": 700, "spawn_error": None,
                "stdout_log": str(log_dir / "agent_stdout.log"),
                "stderr_log": str(log_dir / "agent_stderr.log")}

    res = g2.run_g2_smoke(man, base, tmp_path / "out", build, run,
                          include_dirs=("data",))
    assert len(res.cells) == 6
    for c in res.cells:
        assert c["after_hidden"] == g2.AFTER_HIDDEN_UNKNOWN
        assert c["before_hidden"] is not None          # 已記錄 hidden 分有引用來源
        assert c["cost"] is not None
    # localized 好草稿格：0 修復 session（缺口驅動）
    good_loc = [c for c in res.cells if c["arm"] == "localized"
                and c["draft"].startswith("dab_035")][0]
    assert good_loc["cost"]["calls"] == 0
    assert good_loc["cost"]["model_calls"] == 0   # 零模型活動：0 次 API 呼叫是完整事實
    assert good_loc["stopped"] == repair.STOP_NO_GAP
    # bad 草稿格（answer 缺失）：修復後 readable 判定 PASS（值正確性＝hidden，不在此斷言）
    bad = [c for c in res.cells if c["draft"].startswith("dab_039")]
    assert len(bad) == 2
    assert all(c["final_readable_status"]["req_answer_kv"] == "PASS" for c in bad)
    # 結果可 machine-read
    j = res.to_dict()
    assert j["hidden_after"] == g2.AFTER_HIDDEN_UNKNOWN


def test_cell_records_repair_exit_code(tmp_path):
    """R20261106_1121-1 重跑審計需要每格 _exit_code：g2 結果必須直接記錄
    repair._exit_code(outcome) 的值（單一真相源），審計方不得從結果欄位重推。
    覆蓋三枝：0（no_gap／gap_closed 無 unresolved）、20（agent 跑過但缺口未消）、
    22（agent 未跑＝基建故障）。"""
    man = g2.G2Manifest.load(MANIFEST)
    base = MANIFEST.parent

    def build(prompt: str, ws: pathlib.Path) -> Launch:
        return Launch(argv=["true"], note="fake")

    # 場景 A：fake 只修 dab_039；dab_507 缺口保留
    def run_fix_039(launch, *, workspace, timeout_s, log_dir):
        if "dab_039" in str(workspace):
            (workspace / "answer.txt").write_text(
                "@is_normal[0.31]\n@transformed_importance_score_mean[4.2]\n"
                "@transformed_importance_score_std[1.1]\n", encoding="utf-8")
        log_dir.mkdir(parents=True, exist_ok=True)
        (log_dir / "agent_stdout.log").write_text("{}", encoding="utf-8")
        (log_dir / "agent_stderr.log").write_text("", encoding="utf-8")
        return {"rc": 0, "timed_out": False, "wall_ms": 700, "spawn_error": None,
                "stdout_log": str(log_dir / "agent_stdout.log"),
                "stderr_log": str(log_dir / "agent_stderr.log")}

    res = g2.run_g2_smoke(man, base, tmp_path / "a", build, run_fix_039,
                          include_dirs=("data",))
    assert len(res.cells) == 6
    for c in res.cells:
        assert "exit_code" in c, "g2 cell 必須記錄 repair 退出碼（審計直接引用，不重推）"
        assert c["exit_code"] in (0, 20, 22)
    # no_gap 好草稿（雙臂）＝0
    assert all(c["exit_code"] == 0 for c in res.cells if c["draft"].startswith("dab_035"))
    # gap_closed（fake 修回 039）＝0
    c039 = [c for c in res.cells if c["draft"].startswith("dab_039")]
    assert c039 and all(c["final_readable_status"]["req_answer_kv"] == "PASS" for c in c039)
    assert all(c["exit_code"] == 0 for c in c039)
    # 507：agent 跑過但缺口未消（unresolved）＝20（拒收、非基建故障）
    c507 = [c for c in res.cells if c["draft"].startswith("dab_507")]
    assert c507 and all(c["unresolved"] for c in c507)
    assert all(c["exit_code"] == 20 for c in c507)

    # 場景 B：agent 未跑（spawn 失敗）＝22（基建故障保留碼）
    res2 = g2.run_g2_smoke(man, base, tmp_path / "b", build, _fake_run(fail=True),
                           include_dirs=("data",))
    active = [c for c in res2.cells if c["draft"].startswith(("dab_039", "dab_507"))]
    assert active and all(c["exit_code"] == 22 for c in active)
    # no_gap localized（0 呼叫）不受 spawn 失敗影響＝0
    assert all(c["exit_code"] == 0 for c in res2.cells
               if c["draft"].startswith("dab_035") and c["arm"] == "localized")


def test_g2_totals_and_cli_include_exit_codes(tmp_path, capsys):
    """P20261106_1237-1：審計要直接讀全批收錄率、終端使用者不需傾印 JSON。
    1. `G2Result.to_dict()["totals"]` 含 exit_0_total/exit_20_total/exit_22_total；
    2. `main()` 文字行：逐格印 exit=...（0/20/22 皆見），totals: 行印 exit_0=... exit_20=...。
    fake 場景（與 test_cell_records_repair_exit_code 同構）：035 雙臂 no_gap=0、
    039 雙臂 gap_closed=0、507 雙臂 unresolved=20 ⇒ 4×0、2×20、0×22。零模型呼叫。"""
    man = g2.G2Manifest.load(MANIFEST)
    base = MANIFEST.parent

    def build(prompt: str, ws: pathlib.Path) -> Launch:
        return Launch(argv=["true"], note="fake")

    def run_fix_039(launch, *, workspace, timeout_s, log_dir):
        if "dab_039" in str(workspace):
            (workspace / "answer.txt").write_text(
                "@is_normal[0.31]\n@transformed_importance_score_mean[4.2]\n"
                "@transformed_importance_score_std[1.1]\n", encoding="utf-8")
        log_dir.mkdir(parents=True, exist_ok=True)
        (log_dir / "agent_stdout.log").write_text("{}", encoding="utf-8")
        (log_dir / "agent_stderr.log").write_text("", encoding="utf-8")
        return {"rc": 0, "timed_out": False, "wall_ms": 700, "spawn_error": None,
                "stdout_log": str(log_dir / "agent_stdout.log"),
                "stderr_log": str(log_dir / "agent_stderr.log")}

    res = g2.run_g2_smoke(man, base, tmp_path / "out", build, run_fix_039,
                          include_dirs=("data",))
    t = res.to_dict()["totals"]
    assert t["exit_0_total"] == 4     # 035×2 臂 + 039×2 臂
    assert t["exit_20_total"] == 2    # 507×2 臂（agent 跑過、缺口未消＝拒收）
    assert t["exit_22_total"] == 0

    # main() 文字行：逐格 exit=... 與 totals: 行 exit_0=.../exit_20=...（改前必紅）
    rc = g2.main(["--manifest", str(MANIFEST), "--out", str(tmp_path / "mout")],
                 build=build, run=run_fix_039)
    assert rc == 0
    out = capsys.readouterr().out
    assert out.count("exit=0") == 4
    assert out.count("exit=20") == 2
    assert "exit_0=4" in out and "exit_20=2" in out
    # P20261106_1638-2：totals 行三態完整（基建失敗一眼可見）
    assert "exit_22=0" in out


def test_result_written_machine_readable(tmp_path):
    man = g2.G2Manifest.load(MANIFEST)
    base = MANIFEST.parent

    def build(prompt: str, ws: pathlib.Path) -> Launch:
        return Launch(argv=["true"], note="fake")

    def run(launch: Launch, *, workspace: pathlib.Path, timeout_s: float,
            log_dir: pathlib.Path) -> dict:
        log_dir.mkdir(parents=True, exist_ok=True)
        (log_dir / "agent_stdout.log").write_text("{}", encoding="utf-8")
        (log_dir / "agent_stderr.log").write_text("", encoding="utf-8")
        return {"rc": 0, "timed_out": False, "wall_ms": 100, "spawn_error": None,
                "stdout_log": str(log_dir / "agent_stdout.log"),
                "stderr_log": str(log_dir / "agent_stderr.log")}

    out = tmp_path / "out"
    res = g2.run_g2_smoke(man, base, out, build, run, include_dirs=("data",))
    p = g2.write_result(res, out)
    data = json.loads(p.read_text(encoding="utf-8"))
    assert data["schema"] == g2.RESULT_SCHEMA
    assert data["manifest"]["sha256"] == _sha(MANIFEST)
    assert len(data["cells"]) == 6
    assert data["totals"]["cells"] == 6
    # R20261105_0346-1：dab_035-pi-C（good）的 localized 格 no_gap（0 呼叫，cost 全 None）
    # 不得拖垮總計。smoke manifest max_rounds=2：4 個 bad 格各 2 輪（stall 止）＋good generic
    # 1 輪（min_rounds=1，重驗後缺口關閉）＝9 個 session，wall 各 100 ⇒ 900。
    # fake 不寫原始 usage ⇒ 任一 active 格缺 ⇒ model_calls/tokens 仍 UNKNOWN（P001-20261105-03）。
    active = [c for c in data["cells"] if c["cost"]["calls"] > 0]
    assert len(active) == 5
    assert data["totals"]["repair_sessions"] == sum(c["cost"]["calls"] for c in data["cells"]) == 9
    assert data["totals"]["model_calls"] is None
    assert data["totals"]["tokens"] is None
    assert data["totals"]["wall_ms_total"] == sum(c["cost"]["wall_ms_total"] for c in active) == 900


def test_totals_active_cells_only_usage_complete(tmp_path):
    """R20261105_0346-1(a)：所有 calls>0 格都有完整 usage 時，即使存在 no_gap（calls==0）格，
    totals.tokens／model_calls 仍是完整精確總和（不再恆 None）。"""
    man = g2.G2Manifest.load(MANIFEST)
    base = MANIFEST.parent

    def build(prompt: str, ws: pathlib.Path) -> Launch:
        return Launch(argv=["true"], note="fake")

    def run(launch: Launch, *, workspace: pathlib.Path, timeout_s: float,
            log_dir: pathlib.Path) -> dict:
        log_dir.mkdir(parents=True, exist_ok=True)
        # 每輪 1 次 API 呼叫（message_end＝1 次真實呼叫）、100+15 tokens
        (log_dir / "agent_stdout.log").write_text(
            json.dumps({"type": "message_end",
                        "message": {"role": "assistant",
                                    "usage": {"input": 100, "output": 15}}}) + "\n",
            encoding="utf-8")
        (log_dir / "agent_stderr.log").write_text("", encoding="utf-8")
        return {"rc": 0, "timed_out": False, "wall_ms": 100, "spawn_error": None,
                "stdout_log": str(log_dir / "agent_stdout.log"),
                "stderr_log": str(log_dir / "agent_stderr.log")}

    out = tmp_path / "out"
    res = g2.run_g2_smoke(man, base, out, build, run, include_dirs=("data",))
    data = res.to_dict()
    active = [c for c in data["cells"] if c["cost"]["calls"] > 0]
    assert len(active) == 5   # good 草稿的 localized 格 no_gap（0 呼叫）
    # 9 個 session（4 bad×2 輪 + good generic 1 輪），每輪 1 次 API 呼叫、115 tokens
    assert data["totals"]["repair_sessions"] == 9
    assert data["totals"]["model_calls"] == 9      # 9 輪 × 1 次 API 呼叫
    assert data["totals"]["tokens"] == 9 * 115     # 完整精確總和，不被 no_gap 格拖成 None
    assert data["totals"]["wall_ms_total"] == 900


def test_totals_any_active_cell_missing_usage_is_none(tmp_path):
    """R20261105_0346-1(b)：任一 calls>0 格缺 usage ⇒ totals.tokens／model_calls 必須 None
    （P001-20261105-03：不得把已知部分當完整總和）。"""
    man = g2.G2Manifest.load(MANIFEST)
    base = MANIFEST.parent
    state = {"n": 0}

    def build(prompt: str, ws: pathlib.Path) -> Launch:
        return Launch(argv=["true"], note="fake")

    def run(launch: Launch, *, workspace: pathlib.Path, timeout_s: float,
            log_dir: pathlib.Path) -> dict:
        log_dir.mkdir(parents=True, exist_ok=True)
        state["n"] += 1
        if state["n"] == 1:
            # 第一個 active 格不寫 usage（缺值）
            (log_dir / "agent_stdout.log").write_text("{}", encoding="utf-8")
        else:
            (log_dir / "agent_stdout.log").write_text(
                json.dumps({"type": "message_end",
                            "message": {"role": "assistant",
                                        "usage": {"input": 100, "output": 15}}}) + "\n",
                encoding="utf-8")
        (log_dir / "agent_stderr.log").write_text("", encoding="utf-8")
        return {"rc": 0, "timed_out": False, "wall_ms": 100, "spawn_error": None,
                "stdout_log": str(log_dir / "agent_stdout.log"),
                "stderr_log": str(log_dir / "agent_stderr.log")}

    out = tmp_path / "out"
    res = g2.run_g2_smoke(man, base, out, build, run, include_dirs=("data",))
    data = res.to_dict()
    assert data["totals"]["repair_sessions"] == 9
    assert data["totals"]["model_calls"] is None   # 任一 active 格缺 ⇒ UNKNOWN
    assert data["totals"]["tokens"] is None
    assert data["totals"]["wall_ms_total"] == 900  # wall 各格齊全，不受 usage 缺值影響


def test_result_manifest_sha_is_the_loaded_manifest(tmp_path):
    """結果的 manifest.sha256 必須是**實際載入**的 manifest（r976 修：
    用過濾 manifest（manifest_alt.json）跑時，舊碼固定記 base/manifest.json，
    把 1 草稿的複跑誤記成 3 草稿的原冒煙清單）。"""
    base = tmp_path / "smoke"
    for sub in ("dab_039/draft", "dab_039/task"):
        shutil.copytree(SMOKE / sub, base / sub)
    full = json.loads(MANIFEST.read_text(encoding="utf-8"))
    alt = dict(full)
    alt["drafts"] = [d for d in alt["drafts"] if d["task_id"] == "dab_039"]
    alt_p = base / "manifest_alt.json"
    alt_p.write_text(json.dumps(alt, ensure_ascii=False), encoding="utf-8")
    (base / "manifest.json").write_text(json.dumps(full, ensure_ascii=False),
                                        encoding="utf-8")

    man = g2.G2Manifest.load(alt_p)

    def build(prompt: str, ws: pathlib.Path) -> Launch:
        return Launch(argv=["true"], note="fake")

    def run(launch: Launch, *, workspace: pathlib.Path, timeout_s: float,
            log_dir: pathlib.Path) -> dict:
        (workspace / "answer.txt").write_text(
            "@is_normal[0.31]\n@transformed_importance_score_mean[4.2]\n"
            "@transformed_importance_score_std[1.1]\n", encoding="utf-8")
        log_dir.mkdir(parents=True, exist_ok=True)
        (log_dir / "agent_stdout.log").write_text("{}", encoding="utf-8")
        (log_dir / "agent_stderr.log").write_text("", encoding="utf-8")
        return {"rc": 0, "timed_out": False, "wall_ms": 100, "spawn_error": None,
                "stdout_log": str(log_dir / "agent_stdout.log"),
                "stderr_log": str(log_dir / "agent_stderr.log")}

    res = g2.run_g2_smoke(man, base, tmp_path / "out", build, run,
                          include_dirs=("data",))
    assert res.manifest_sha256 == _sha(alt_p)
    assert res.manifest_sha256 != _sha(base / "manifest.json")


def test_manifest_budget_reaches_executor(tmp_path):
    """G3 預註冊預算契約（r995 回歸鎖，vq-5nz.6）：manifest 的 budget 必須逐字傳到
    執行器 run()——fire 命令（python -m vacant_network.reqloop.g2）走的就是
    run_g2_smoke→repair_slice 這條路。若回归把單輪 timeout 掉回硬編碼 300s、
    或丟棄 manifest 的 min_rounds/max_rounds，本測試必須紅。
    用 600s（G3 預註冊值 300s→600s）而非 300s：若實作只讀預設值，兩者無差別、
    測試無牙。
    """
    base = tmp_path / "smoke"
    shutil.copytree(SMOKE, base)
    full = json.loads(MANIFEST.read_text(encoding="utf-8"))
    full["budget"]["timeout_s_per_round"] = 600
    (base / "manifest.json").write_text(json.dumps(full, ensure_ascii=False),
                                        encoding="utf-8")

    man = g2.G2Manifest.load(base / "manifest.json")
    seen_timeouts: list[float] = []

    def build(prompt: str, ws: pathlib.Path) -> Launch:
        return Launch(argv=["true"], note="fake")

    def run(launch: Launch, *, workspace: pathlib.Path, timeout_s: float,
            log_dir: pathlib.Path) -> dict:
        seen_timeouts.append(timeout_s)
        log_dir.mkdir(parents=True, exist_ok=True)
        (log_dir / "agent_stdout.log").write_text("{}", encoding="utf-8")
        (log_dir / "agent_stderr.log").write_text("", encoding="utf-8")
        return {"rc": 0, "timed_out": False, "wall_ms": 50, "spawn_error": None,
                "stdout_log": str(log_dir / "agent_stdout.log"),
                "stderr_log": str(log_dir / "agent_stderr.log")}

    res = g2.run_g2_smoke(man, base, tmp_path / "out", build, run,
                          include_dirs=("data",))

    # 600s 預算真的傳到執行器（不是 300s 預設值）
    assert seen_timeouts, "無模型呼叫，無法驗證預算傳遞"
    assert all(t == 600 for t in seen_timeouts), seen_timeouts

    by = {(c["draft"], c["arm"]): c for c in res.cells}
    # min_rounds：generic 臂對的草稿也重驗 1 次；localized 缺口驅動 0 session（calls＝修復 session 數）
    assert by[("dab_035-pi-C", "generic")]["cost"]["calls"] == 1
    assert by[("dab_035-pi-C", "localized")]["cost"]["calls"] == 0
    # fake 不寫原始 usage ⇒ model_calls 一律 UNKNOWN（不拿 session 數頂替）
    assert by[("dab_035-pi-C", "generic")]["cost"]["model_calls"] is None
    assert by[("dab_035-pi-C", "localized")]["cost"]["model_calls"] == 0
    # bad 草稿：兩輪預算用盡（max_rounds=2＝_STALL_LIMIT＝2），缺口仍在
    assert by[("dab_507-pi-A", "generic")]["cost"]["calls"] == 2
    assert by[("dab_507-pi-A", "localized")]["cost"]["calls"] == 2
    assert by[("dab_507-pi-A", "generic")]["cost"]["model_calls"] is None
    assert by[("dab_507-pi-A", "localized")]["cost"]["model_calls"] is None
    assert by[("dab_039-pi-C", "generic")]["stopped"] in (
        repair.STOP_MAX_ROUNDS, repair.STOP_STALLED)
    assert by[("dab_039-pi-C", "generic")]["final_readable_status"]["req_answer_kv"] != "PASS"


def test_budget_caps_reach_executor_at_g2_level(tmp_path):
    """r1094（審查指示 4/5「硬上限控本確立」）：硬上限鏈路的 g2 層此前無測試。
    adapter 層（test_adapters_budget.py 殺程語義）與 repair 層（test_reqloop_repair.py
    轉發＋cost.budget 記錄）已覆蓋；run_g2_smoke→repair_slice 這跳（CLI 發射走的路徑）
    若回歸丟掉 max_tool_calls/max_tokens 或調換優先序，無測試會紅。
    三語義：(1) 顯式引數到執行器且優於 manifest；(2) 顯式 None⇒回退 manifest
    budget.max_tool_calls/max_tokens；(3) 皆 None＝不量不殺、呼叫不帶新 kwarg
    （舊簽名 RunFn 照跑＝逐位元組不變量）。
    離線 fake agent，零模型呼叫。
    """
    base = tmp_path / "smoke"
    shutil.copytree(SMOKE, base)
    full = json.loads(MANIFEST.read_text(encoding="utf-8"))
    # manifest budget 上限（與顯式值不同⇒優先序可驗）
    full["budget"]["max_tool_calls"] = 21
    full["budget"]["max_tokens"] = 2_100_000
    (base / "manifest.json").write_text(json.dumps(full, ensure_ascii=False),
                                        encoding="utf-8")
    man = g2.G2Manifest.load(base / "manifest.json")

    def build(prompt: str, ws: pathlib.Path) -> Launch:
        return Launch(argv=["true"], note="fake")

    def _mkrun(seen: list):
        def run(launch: Launch, *, workspace: pathlib.Path, timeout_s: float,
                log_dir: pathlib.Path, **kw) -> dict:
            seen.append((kw.get("max_tool_calls"), kw.get("max_tokens")))
            log_dir.mkdir(parents=True, exist_ok=True)
            (log_dir / "agent_stdout.log").write_text("{}", encoding="utf-8")
            (log_dir / "agent_stderr.log").write_text("", encoding="utf-8")
            return {"rc": 0, "timed_out": False, "wall_ms": 50, "spawn_error": None,
                    "stdout_log": str(log_dir / "agent_stdout.log"),
                    "stderr_log": str(log_dir / "agent_stderr.log")}
        return run

    # (1) 顯式引數到執行器，且優於 manifest budget（21/2_100_000 不得出現）
    seen: list = []
    g2.run_g2_smoke(man, base, tmp_path / "out1", build, _mkrun(seen),
                    include_dirs=("data",),
                    max_tool_calls=5, max_tokens=100_000)
    assert seen, "無模型呼叫，無法驗證上限傳遞"
    assert all(c == (5, 100_000) for c in seen), seen

    # (2) 顯式 None⇒回退 manifest budget 上限
    seen = []
    g2.run_g2_smoke(man, base, tmp_path / "out2", build, _mkrun(seen),
                    include_dirs=("data",))
    assert seen and all(c == (21, 2_100_000) for c in seen), seen

    # (3) 皆 None（原始 manifest 無 cap 欄）＝不量不殺：舊簽名 RunFn（無 **kwargs）照跑
    base3 = tmp_path / "smoke3"
    shutil.copytree(SMOKE, base3)
    man3 = g2.G2Manifest.load(base3 / "manifest.json")
    legacy_calls: list = []

    def legacy_run(launch: Launch, *, workspace: pathlib.Path, timeout_s: float,
                   log_dir: pathlib.Path) -> dict:  # 無 **kwargs＝舊簽名
        legacy_calls.append(True)
        log_dir.mkdir(parents=True, exist_ok=True)
        (log_dir / "agent_stdout.log").write_text("{}", encoding="utf-8")
        (log_dir / "agent_stderr.log").write_text("", encoding="utf-8")
        return {"rc": 0, "timed_out": False, "wall_ms": 50, "spawn_error": None,
                "stdout_log": str(log_dir / "agent_stdout.log"),
                "stderr_log": str(log_dir / "agent_stderr.log")}

    g2.run_g2_smoke(man3, base3, tmp_path / "out3", build, legacy_run,
                    include_dirs=("data",))
    assert legacy_calls, "無模型呼叫，無法驗證不帶新 kwarg 的路徑"


# ── G2 正式效果比較預註冊（vq-5nz.15）────────────────────────────

EFFECT_MANIFEST = REPO_ROOT / "ops" / "reqloop" / "g2" / "effect_manifest.json"


def test_effect_manifest_preregistration():
    """G2 正式效果比較預註冊鎖（vq-5nz.15 預註冊，vq-5nz.16 全凍結，RLOOP_PLAN G2：10–20 錯＋5 對）：
    15 份 ready（10 錯＋5 對）＝已凍結真草稿原地引用，hash 必須與盤一致（verify_frozen）；
    pending 空（原 6 份 4 錯＋2 對已於 vq-5nz.16 凍結，每份都有已記錄分＋before-check 一致性）；
    達規格下界 10 錯＋5 對。兩臂同模型（1004 gemma）、同總預算（2×300s）。
    未點名＝未發射：本測試只驗凍結完整性，不發射、不呼叫模型。
    """
    man = g2.G2Manifest.load(EFFECT_MANIFEST)
    raw = man.raw

    # 15 份 ready：10 錯＋5 對，全部為真草稿（e008/e013/e014 來源）
    assert len(man.drafts) == 15
    assert sum(1 for d in man.drafts if d["role"] == "bad") == 10
    assert sum(1 for d in man.drafts if d["role"] == "good") == 5
    srcs = {d["source"]["run"] for d in man.drafts}
    assert srcs == {"e008_dabench_pi_AC", "e013_dabench_pi_AC_full", "e014_dabstep_block"}

    # 凍結完整性：hash 與盤一致（base＝manifest 所在目錄，原地引用）
    man.verify_frozen(EFFECT_MANIFEST.parent)
    base = EFFECT_MANIFEST.parent
    for d in man.drafts:
        assert (base / d["draft"]["dir"]).is_dir(), d["draft"]["dir"]
        assert d["task"]["dir"].startswith(("smoke/", "smoke_e013/", "smoke_e014/"))

    # pending 已清空：原 6 份（4 錯＋2 對）已凍結進 drafts，且每份都有已記錄分（引用、不重跑）
    assert raw["pending"] == []
    for d in man.drafts:
        assert d["source"]["score"] is not None and d["source"]["score"].get("pass") is not None

    # 新凍結的 6 份（vq-5nz.16）每份都有 before-check 結果且與已記錄分一致（缺值不填 0）
    new_names = {n for n in ("dab_378-pi-C", "dab_427-pi-A", "dab_057-pi-A",
                             "dabstep-10-pi-C", "dabstep-1273-pi-C", "dabstep-11-pi-A")}
    by_name = {d["name"]: d for d in man.drafts}
    assert new_names <= set(by_name)
    for n in new_names:
        bc = by_name[n].get("before_check")
        assert bc is not None, f"{n} 缺 before_check 結果"
        assert bc["consistent_with_recorded"] is True, n
        for k in ("pass", "fail", "unknown", "consistent_with_recorded"):
            assert k in bc, (n, k)

    # 達 RLOOP_PLAN 規格下界（10–20 錯＋5 對）
    spec = raw["spec_gap"]
    assert spec["ready"] == {"bad": 10, "good": 5}
    assert spec["pending"] == {"bad": 0, "good": 0}
    assert spec["total_if_all_frozen"] == {"bad": 10, "good": 5}

    # 兩臂同模型（1004 gemma）、同總預算（2 輪×300s）；無硬 token 上限（缺值 UNKNOWN 不填 0）
    assert man.arms == ("generic", "localized")
    assert man.model["provider"] == "lms1004nothink"
    assert man.model["model"] == "gemma-4-12b-it-qat"
    assert man.budget["max_rounds_per_cell"] == 2
    assert man.budget["timeout_s_per_round"] == 300
    assert man.budget["min_rounds"] == {"generic": 1, "localized": 0}
    assert man.budget["hard_token_cap"] is False

    # scoring 與 repair.py 實際語義對齊（2026-11-04 對照代碼核實）：裁決看管線輸出，
    # 不看批跑退出碼（g2 批跑管線跑通即回 0；0/20/22 屬 repair 單格 CLI）
    sc = raw["scoring"]
    assert "repair.py" in sc["source"] and "g2.py" in sc["source"]
    assert "22" in sc["source"]  # infra 退出碼明確歸屬 repair CLI
    assert "_required_all_pass" in sc["gap_closed"] and "必需條目" in sc["gap_closed"]
    assert "末輪重驗" in sc["fixed"] and "FAIL→UNKNOWN 不算修好" in sc["fixed"]
    assert "after＝before" in sc["after"]  # 零呼叫⇒after＝before
    assert all(k in sc["stopped"] for k in ("no_gap", "gap_closed", "stalled", "max_rounds"))

    # 未點名＝未發射；15 份全凍結仍不得呈現為 G2 正式效果比較（點名＋發射才是）
    assert raw["status"] == "FROZEN_PENDING_NAMING"
    assert "15" in raw["naming_required"]  # 完整清單＝15 ready（vq-5nz.16 全凍結後）
    assert "10–20" in raw["naming_required"] or "5 對" in raw["naming_required"]


def test_verify_frozen_covers_data_files(tmp_path):
    """回歸鎖（r1011，審計票 R20261104_2123-1）：verify_frozen 必須也驗 data_files。
    舊門只驗交付檔＋requirements.json；data_files 的 hash 被凍結進 manifest 卻從不驗
    路徑——effect_manifest 5 份 e013 條目 key 缺 data/ 前綴，檔案在、hash 對，官方門
    卻發現不了（靠漏驗拿到的綠燈就是放過這個洞的條件；H-0 同型）。
    凍結清單裡每一條 pin 都必須指向可解析、hash 相符的檔案，否則該 pin 只是裝飾。
    """
    base = tmp_path / "g2"
    task_dir = base / "smoke" / "t1" / "task"
    draft_dir = base / "smoke" / "t1" / "draft"
    (task_dir / "data").mkdir(parents=True)
    draft_dir.mkdir(parents=True)
    (task_dir / "requirements.json").write_text("{}", encoding="utf-8")
    (task_dir / "data" / "in.csv").write_text("a,b\n1,2\n", encoding="utf-8")
    (draft_dir / "answer.txt").write_text("42\n", encoding="utf-8")

    def manifest(data_files: dict) -> pathlib.Path:
        raw = {
            "schema": "vacant.reqloop.g2.manifest/1",
            "frozen_at": "t", "ticket": "t", "purpose": "t",
            "arms": ["generic", "localized"],
            "model": {}, "budget": {}, "scoring": {}, "leak_guard": "t",
            "drafts": [{
                "name": "t1-pi-A", "role": "bad", "task_id": "t1",
                "source": {"run": "r", "cell": "c",
                           "score": {"pass": False, "n_correct": "0/1"}},
                "draft": {"dir": "smoke/t1/draft",
                          "files": {"answer.txt": _sha(draft_dir / "answer.txt")}},
                "task": {"dir": "smoke/t1/task",
                         "requirements": {"sha256": _sha(task_dir / "requirements.json")},
                         "data_files": data_files},
            }],
            "pending": [],
        }
        p = base / "manifest.json"
        p.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
        return p

    in_hash = _sha(task_dir / "data" / "in.csv")

    # 路徑與 hash 都對 → 過
    g2.G2Manifest.load(manifest({"data/in.csv": in_hash})).verify_frozen(base)

    # key 缺 data/ 前綴（effect_manifest 5 份 e013 條目的實況）→ 必須拒
    with pytest.raises((FileNotFoundError, ValueError, KeyError)):
        g2.G2Manifest.load(manifest({"in.csv": in_hash})).verify_frozen(base)

    # hash 不符 → 必須拒
    with pytest.raises((ValueError, KeyError)):
        g2.G2Manifest.load(manifest({"data/in.csv": "0" * 64})).verify_frozen(base)


def test_all_repo_reqloop_manifests_resolve_frozen():
    """全庫掃鎖（r1017）：repo 內每一份 g2 manifest schema 的凍結清單都必須過得自己的門。
    r1011 補了 effect_manifest 5 份 e013 條目（key 缺 data/ 前綴），但同型缺陷還在
    smoke_e013/manifest.json（dab_105/055/426 三份 pin 指向不存在的路徑，verify_frozen
    直接「凍結資料檔缺失」）——一份過不了自己門的凍結記錄，pin 只是裝飾（H-0 同型：
    靠漏驗拿到的綠燈就是放過洞的條件）。本測試不發射、不呼叫模型，只驗 pin 可解析。
    """
    reqloop = REPO_ROOT / "ops" / "reqloop"
    mans = []
    for p in sorted(reqloop.rglob("*.json")):
        if not p.is_file():
            continue
        try:
            raw = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(raw, dict) and raw.get("schema") == "vacant.reqloop.g2.manifest/1":
            mans.append(p)

    # 掃到的是真的那幾份（防 rglob 路徑漂移讓掃鎖空轉）
    names = {str(p.relative_to(reqloop)) for p in mans}
    assert {
        "g2/effect_manifest.json",
        "g2/smoke/manifest.json",
        "g2/smoke/manifest_dab039_repin.json",
        "g2/smoke_e013/manifest.json",
        "g2/smoke_e014/manifest.json",
        "g3/manifest.json",
    } <= names

    # 每份都要過 verify_frozen（交付檔＋requirements＋data_files 全部可解析、hash 相符）
    for p in mans:
        g2.G2Manifest.load(p).verify_frozen(p.parent)


# ── vq-5nz.16：新凍結 6 份的 before-check 與已記錄分一致 ──────────────────

# name → (role, task 目錄, draft 目錄, 期望 FAIL 的必需條目 id；None＝只要有必需 FAIL 即可；
#        frozenset()＝好草稿，全部必需條目必須 PASS)
NEW_DRAFTS: dict[str, tuple[str, str, str, set[str] | None]] = {
    # 記錄 6/8（pass=False）：8 PASS＋2 FAIL（兩項 kurtosis），恰為 2 個錯項
    "dab_378-pi-C": ("bad", "smoke/dab_378/task", "smoke/dab_378/draft",
                     {"pre_kurtosis", "post_kurtosis"}),
    # 記錄 no_items 0/1（pass=False）：@null_entries_count101 缺方括號→格式 FAIL
    "dab_427-pi-A": ("bad", "smoke_e013/dab_427-pi-A/task", "smoke_e013/dab_427-pi-A/draft", None),
    # 記錄 1/1（pass=True）：0.97＝Int64 點估計（median 列）口徑重算一致
    "dab_057-pi-A": ("good", "smoke_e013/dab_057-pi-A/task", "smoke_e013/dab_057-pi-A/draft", frozenset()),
    # 記錄 reward 0：答案 30 ≠ payments.csv（readme 明言即 dataset）unique merchant 5
    "dabstep-10-pi-C": ("bad", "smoke_e014/dabstep-10-pi-C/task", "smoke_e014/dabstep-10-pi-C/draft", None),
    # 記錄 reward 0：prose 答案不可解析為單一數字（且 0.120132≠按 manual.md 公式重算）
    "dabstep-1273-pi-C": ("bad", "smoke_e014/dabstep-1273-pi-C/task", "smoke_e014/dabstep-1273-pi-C/draft", None),
    # 記錄 reward 1：4811.76＝payments.csv eur_amount 最大值重算一致
    "dabstep-11-pi-A": ("good", "smoke_e014/dabstep-11-pi-A/task", "smoke_e014/dabstep-11-pi-A/draft", frozenset()),
}


def test_vq5nz16_before_check_matches_recorded_score():
    """before-check 一致性（紅線）：bad 草稿必須有必需 FAIL（pass=False 與記錄 pass=False 同向）；
    good 草稿全部必需條目 PASS（無 UNKNOWN 頂包）；FAIL→UNKNOWN 不算修好；缺值標 UNKNOWN 不填 0。
    本測試只跑本地重算檢查器，不呼叫模型、不讀 hidden。
    """
    base = EFFECT_MANIFEST.parent
    for name, (role, task_rel, draft_rel, expected_fail_ids) in NEW_DRAFTS.items():
        task_dir = base / task_rel
        draft_dir = base / draft_rel
        assert task_dir.is_dir(), f"{name}: task 目錄缺失 {task_dir}"
        assert draft_dir.is_dir(), f"{name}: draft 目錄缺失 {draft_dir}"
        rs = RequirementSet.load(task_dir / "requirements.json")
        res = run_requirement_checks(task_dir, rs, draft_dir)
        assert res, f"{name}: 無任何檢查結果"
        statuses = {r.claim_id: r.status for r in res}
        # 狀態只準三種；UNKNOWN 是「不能判定」，絕不用 0 頂包
        assert set(statuses.values()) <= {"PASS", "FAIL", "UNKNOWN"}, (name, statuses)
        required = {r.claim_id for r in res if r.required}
        assert required, f"{name}: 無必需條目"
        if role == "bad":
            fails = {k for k in required if statuses.get(k) == "FAIL"}
            assert fails, f"{name}: bad 草稿無必需 FAIL（與記錄 pass=False 不一致）"
            if expected_fail_ids is not None:
                assert fails == expected_fail_ids, (name, fails, expected_fail_ids)
        else:
            bad = {k: statuses[k] for k in required if statuses.get(k) != "PASS"}
            assert not bad, f"{name}: good 草稿有必需條目未 PASS：{bad}"


def test_vq5nz16_recorded_scores_are_cited_not_rerun():
    """6 份的 lab 分只引用（score.json 既有記錄），不本地重跑 hidden scorer。"""
    man = g2.G2Manifest.load(EFFECT_MANIFEST)
    by_name = {d["name"]: d for d in man.drafts}
    expect = {
        # e008/e013 用 n_correct（pass=False/True）；e014 用 reward（"0"/"1"）
        "dab_378-pi-C": (False, {"note_contains": "6/8"}),
        "dab_427-pi-A": (False, {"note_contains": "no_items"}),
        "dab_057-pi-A": (True, {}),
        "dabstep-10-pi-C": (False, {"reward": "0"}),
        "dabstep-1273-pi-C": (False, {"reward": "0"}),
        "dabstep-11-pi-A": (True, {"reward": "1"}),
    }
    for n, (passed, chk) in expect.items():
        sc = by_name[n]["source"]["score"]
        assert sc["pass"] is passed, (n, sc)
        if "reward" in chk:
            assert str(sc.get("reward")) == chk["reward"], (n, sc)
        if "note_contains" in chk:
            assert chk["note_contains"] in str(sc.get("note") or ""), (n, sc)
        assert by_name[n]["source"]["fetched_from"].startswith("/srv/vlab/runs"), n


# ── R20261105_0346-2：effects_20261105 50 格誠實審計摘要 ────────────────────
# 摘要檔是凍結審計工件（snapshot d38d2eb2）：本測試鎖住其完整性、無佔位、
# 以及與 ~/dev/ops/effects_20261105/ 源檔的逐數一致（源檔在本地時）。

EFFECTS_20261105 = pathlib.Path("/home/user1/dev/ops/effects_20261105")
SUMMARY_JSON = (pathlib.Path(__file__).resolve().parents[1]
                / "ops" / "audits" / "effects_20261105_summary.json")


def _load_summary() -> dict:
    assert SUMMARY_JSON.exists(), (
        "ops/audits/effects_20261105_summary.json 缺——應與產生器 "
        "ops/audits/effects_20261105_summary.py 同庫提交")
    return json.loads(SUMMARY_JSON.read_text(encoding="utf-8"))


def test_effects_20261105_summary_complete_no_placeholders():
    """R20261105_0346-2 驗收：結構完整、無 placeholder、30+20 格、口徑字段齊全。"""
    raw = SUMMARY_JSON.read_text(encoding="utf-8")
    for bad in ("TODO", "FIXME", "placeholder", "占位", "待補", "TBD"):
        assert bad not in raw, f"摘要含佔位文字 {bad!r}"
    s = _load_summary()
    assert s["snapshot_sha"] == "d38d2eb21d7ffbb927eb263e657d907dc112bc7d"
    assert s["total_cells"] == 50
    assert set(s["phases"]) == {"policy30", "feedback_once20"}
    required_cell_keys = {
        "draft", "arm", "role", "before_pass_independent", "after_independent",
        "local_stopped_d38d2eb2", "local_all_pass_d38d2eb2", "current_code_all_pass",
        "local_matches_independent", "current_code_matches_independent",
        "repair_sessions", "api_model_calls_true", "api_model_calls_recorded_d38d2eb2",
        "tokens_true", "tokens_recorded_d38d2eb2", "wall_ms_total", "rounds",
    }
    for ph, exp_n in (("policy30", 30), ("feedback_once20", 20)):
        v = s["phases"][ph]
        assert v["cells"] == exp_n == len(v["cells_detail"]), ph
        for c in v["cells_detail"]:
            missing = required_cell_keys - set(c)
            assert not missing, (ph, c["draft"], c["arm"], missing)
        for metric in ("wrong_to_right", "right_to_wrong", "preserved_good",
                       "still_wrong"):
            assert (sum(v["per_arm"][a][metric] for a in ("generic", "localized"))
                    == v[metric]), (ph, metric)
        assert (sum(v["per_arm"][a]["repair_sessions"] for a in ("generic", "localized"))
                == v["repair_sessions_total"]), ph
        # 動量守恆：bad 格非 W→R 即 still_wrong；good 格非 preserved 即 R→W
        n_bad = sum(1 for c in v["cells_detail"] if c["before_pass_independent"] is False)
        n_good = sum(1 for c in v["cells_detail"] if c["before_pass_independent"] is True)
        assert v["wrong_to_right"] + v["still_wrong"] == n_bad, ph
        assert v["preserved_good"] + v["right_to_wrong"] == n_good, ph
    # r1029 驗收口徑：當前 checks 碼重驗與獨立 scorer 50/50 一致
    assert s["current_code_matches_total"] == 50


def test_effects_20261105_summary_matches_source_files():
    """R20261105_0346-2 驗收：摘要數字與 effects 源檔（manifest／g2_result／independent）一致。"""
    if not EFFECTS_20261105.is_dir():
        pytest.skip("~/dev/ops/effects_20261105 不在本機（CI 環境）——逐數交叉核對需源檔")
    s = _load_summary()
    for ph, man_name in (("policy30", "effect_manifest.json"),
                         ("feedback_once20", "feedback_once_manifest.json")):
        snap = EFFECTS_20261105 / "snapshot/ops/reqloop/g2"
        man = json.loads((snap / man_name).read_text(encoding="utf-8"))
        g2 = json.loads((EFFECTS_20261105 / ph / "g2_result.json").read_text(encoding="utf-8"))
        ind = json.loads((EFFECTS_20261105 / ph / "independent.json").read_text(encoding="utf-8"))
        before_of = {d["name"]: d["source"]["score"].get("pass") for d in man["drafts"]}
        after_of = {f"{c['draft']}-{c['arm']}": c["independent_after"]["pass"]
                    for c in ind["cells"]}
        sessions_of = {f"{c['draft']}-{c['arm']}": int(c["cost"].get("calls") or 0)
                       for c in g2["cells"]}
        v = s["phases"][ph]
        cells = v["cells_detail"]
        assert len(cells) == len(ind["cells"]) == len(g2["cells"]), ph
        for c in cells:
            key = f"{c['draft']}-{c['arm']}"
            assert c["before_pass_independent"] == before_of[c["draft"]], (ph, key)
            assert c["after_independent"] == after_of[key], (ph, key)
            assert c["repair_sessions"] == sessions_of[key], (ph, key)
        # 階段總數＝源檔重算
        assert v["wrong_to_right"] == sum(
            1 for c in cells if before_of[c["draft"]] is False and after_of[f"{c['draft']}-{c['arm']}"] is True)
        assert v["right_to_wrong"] == sum(
            1 for c in cells if before_of[c["draft"]] is True and after_of[f"{c['draft']}-{c['arm']}"] is False)
        assert v["repair_sessions_total"] == sum(sessions_of.values()), ph


def test_effects_20261105_summary_wall_ms_and_active_cost_totals():
    """argon 20261105_0715 回歸：
    policy30 含 5 份 good 草稿（no_gap，0 輪修復，單格 wall_ms_total=None），但另外 25 格有實際執行
    （每格皆有真實 wall_ms_total）。階段級與 per_arm 的 wall_ms_total 必須加總所有實際執行格
    （repair_sessions > 0），不得因 no_gap 格的 None 把整個 policy30 階段的 wall_ms_total 抹成 null。
    同時 api_model_calls_recorded_d38d2eb2 必須反映舊 parser 的記錄值（或與 repair_sessions 區分），
    no_gap 格不得把 tokens_true=0 與 wall_ms_total=None 混用導致階段加總邏輯不一致。
    """
    s = _load_summary()
    p30 = s["phases"]["policy30"]
    fb20 = s["phases"]["feedback_once20"]
    assert p30["wall_ms_total"] == 4398675
    assert p30["per_arm"]["generic"]["wall_ms_total"] == 2192195
    assert p30["per_arm"]["localized"]["wall_ms_total"] == 2206480
    assert fb20["wall_ms_total"] == 2482095
    assert fb20["per_arm"]["generic"]["wall_ms_total"] == 867644
    assert fb20["per_arm"]["localized"]["wall_ms_total"] == 1614451
    # no_gap 格（repair_sessions == 0，無任何 agent 啟動、無 usage 來源）的 tokens_true 必須為 None（UNKNOWN，絕不填 0），
    # 與 repair.py:1252-1256 及 tokens_recorded_d38d2eb2=None 一致
    no_gap_cells = [c for c in p30["cells_detail"] if c["repair_sessions"] == 0]
    assert len(no_gap_cells) == 5
    for c in no_gap_cells:
        assert c["api_model_calls_true"] == 0, c["draft"]
        assert c["tokens_true"] is None, f"{c['draft']}-{c['arm']} no_gap cell must have tokens_true=None, got {c['tokens_true']}"
        assert c["wall_ms_total"] is None, c["draft"]


def test_g2_result_totals_keeps_repair_sessions_and_model_calls_distinct():
    """R20261105_1047-1：`G2Result.to_dict()["totals"]` 的 `repair_sessions`（agent 啟動數）
    與 `model_calls`（真實 API 請求數）是兩個獨立鍵，絕不互相覆寫。
    回歸形狀：contrast3_20261105/run_contrast.py 曾以
    `payload['totals']['repair_sessions'] = payload['totals'].pop('model_calls')`
    把 172 次 API 請求冒稱為 172 個 repair_sessions。單個 session 內可含多次
    API 呼叫（如 1 session 3 個 message_end usage 事件），兩鍵數值必須不同。
    """
    def _cell(draft: str, calls: int, model_calls: int, tokens: int) -> dict:
        return {
            "draft": draft, "arm": "localized", "stopped": "STOP_GAP_CLOSED",
            "cost": {"calls": calls, "model_calls": model_calls,
                     "tokens": tokens, "wall_ms_total": 1000},
        }

    cells = [_cell("d1", 1, 3, 1000), _cell("d2", 2, 10, 5000)]
    res = g2.G2Result(
        manifest_sha256="0" * 64,
        generated_at="2026-11-05T00:00:00Z",
        model={"provider": "p", "model": "m"},
        budget={"max_rounds_per_cell": 2, "timeout_s_per_round": 300.0},
        scoring={"independent": "UNKNOWN"},
        cells=cells,
    )
    totals = res.to_dict()["totals"]
    assert "repair_sessions" in totals and "model_calls" in totals
    assert totals["repair_sessions"] == sum(c["cost"]["calls"] for c in cells) == 3
    assert totals["model_calls"] == sum(c["cost"]["model_calls"] for c in cells) == 13
    assert totals["repair_sessions"] != totals["model_calls"]


def test_g2_totals_and_cli_include_satisfied_deliverable_preservation(tmp_path, capsys):
    """P20261106_1035-2：已滿足交付物位元組保留狀態必須顯式可見：
    1. `G2Result.to_dict()["totals"]` 含 `satisfied_preserved_total`／`satisfied_mutated_total`；
    2. CLI 文字輸出：每格 `satisfied_mutated` 非空 ⇒ 印 `SATISFIED_MUTATED: <files>`；
       `source_tampered` ⇒ 印 `SOURCE_TAMPERED: <files>`；totals 行顯示 `preserved=... mutated=...`。
    回歸形狀：multideliv_20261106 的 generic 臂 top_products 格 `satisfied_mutated=["summary.md"]`，
    但舊 CLI 文字行只印 REGRESSED、`totals` 完全沒有保留／竄改總計，人看輸出誤以為全數合格。
    synthetic 離線接線（G1 自造案例＋fake agent），只驗管線，不宣稱任何效果。"""
    # (1) to_dict totals
    def _cell(draft: str, arm: str, preserved: list, mutated: list,
              tampered_files: tuple = ()) -> dict:
        return {
            "draft": draft, "arm": arm, "stopped": "gap_closed",
            "cost": {"calls": 1, "model_calls": 2, "tokens": 100, "wall_ms_total": 50},
            "satisfied_preserved": preserved,
            "satisfied_mutated": mutated,
            "source_tampered": bool(tampered_files),
            "source_tampered_files": list(tampered_files),
        }

    cells = [
        _cell("d1", "localized", ["a.csv"], []),
        _cell("d2", "generic", [], ["summary.md"]),
        _cell("d3", "localized", [], ["b.md"], tampered_files=("data/in.csv",)),
    ]
    res = g2.G2Result(
        manifest_sha256="0" * 64, generated_at="2026-11-06T00:00:00Z",
        model={"provider": "p", "model": "m"},
        budget={"max_rounds_per_cell": 1, "timeout_s_per_round": 30},
        scoring={"independent": "UNKNOWN"}, cells=cells,
    )
    totals = res.to_dict()["totals"]
    assert totals["satisfied_preserved_total"] == 1
    assert totals["satisfied_mutated_total"] == 2

    # (2) CLI 文字輸出（G1 自造案例、fake agent 兩臂不同行為）
    g1 = REPO_ROOT / "ops" / "reqloop" / "g1" / "tasks" / "expense_category"
    base = tmp_path / "g2base"
    shutil.copytree(g1, base / "task")   # 任務目錄（requirements/request/expenses.csv＋good/bad 草稿）
    draft_src = g1 / "bad_grand_total_wrong"
    shutil.copytree(draft_src, base / "draft")
    good_md = (g1 / "good" / "summary.md").read_text(encoding="utf-8")
    csv_text = (base / "draft" / "expense_summary.csv").read_text(encoding="utf-8")

    def run(launch, *, workspace, timeout_s, log_dir):
        ws = pathlib.Path(workspace)
        (ws / "summary.md").write_text(good_md, encoding="utf-8")
        if "generic" in ws.parts:
            # generic 臂：竄改已滿足交付物（CSV 尾加空行：位元組變、內容不變）
            (ws / "expense_summary.csv").write_text(csv_text + "\n", encoding="utf-8")
        else:
            # localized 臂：改寫來源資料 ⇒ source_tampered
            (ws / "expenses.csv").write_text("category,amount\nx,1\n", encoding="utf-8")
        log_dir.mkdir(parents=True, exist_ok=True)
        (log_dir / "agent_stdout.log").write_text("{}", encoding="utf-8")
        (log_dir / "agent_stderr.log").write_text("", encoding="utf-8")
        return {"rc": 0, "timed_out": False, "wall_ms": 100, "spawn_error": None,
                "stdout_log": str(log_dir / "agent_stdout.log"),
                "stderr_log": str(log_dir / "agent_stderr.log")}

    man = {
        "schema": "vacant.reqloop.g2.manifest/1",
        "frozen_at": "2026-11-06T00:00:00Z",
        "ticket": "P20261106_1035-2", "purpose": "synthetic 管線測試",
        "arms": ["generic", "localized"],
        "model": {"provider": "fake", "model": "fake"},
        "budget": {"max_rounds_per_cell": 1, "timeout_s_per_round": 30},
        "scoring": {"independent": "UNKNOWN"},
        "leak_guard": "synthetic",
        "drafts": [{
            "name": "g1_expense_bad", "role": "bad", "task_id": "expense_category",
            "source": {"cell": "synthetic", "score": {"pass": False,
                                                      "n_correct": "2/3", "status": "ok"}},
            "draft": {"dir": "draft", "files": {
                "summary.md": _sha(base / "draft" / "summary.md"),
                "expense_summary.csv": _sha(base / "draft" / "expense_summary.csv")}},
            "task": {"dir": "task",
                     "requirements": {"sha256": _sha(base / "task" / "requirements.json")},
                     "request": {"sha256": _sha(base / "task" / "request.md")}},
        }],
    }
    man_path = base / "manifest.json"
    man_path.write_text(json.dumps(man, ensure_ascii=False), encoding="utf-8")

    out_root = tmp_path / "out"
    rc = g2.main(["--manifest", str(man_path), "--out", str(out_root)],
                 build=_fake_build([]), run=run)
    assert rc == 0   # 冒煙口徑：管線跑通即 0（拒收裁決在 repair._exit_code 層，由另票測試鎖）
    text = capsys.readouterr().out
    # 每格顯式暴露保留／突變／來源狀態（舊碼只印 REGRESSED，此三行必紅）
    assert "SATISFIED_MUTATED" in text and "expense_summary.csv" in text
    assert "SOURCE_TAMPERED" in text and "expenses.csv" in text
    assert "preserved=1" in text and "mutated=1" in text
    # g2_result.json 的 totals 同含兩欄（經真實管線派生，非手抄）
    payload = json.loads((out_root / "g2_result.json").read_text(encoding="utf-8"))
    t = payload["totals"]
    assert t["satisfied_preserved_total"] == 1
    assert t["satisfied_mutated_total"] == 1


def test_run_g2_smoke_records_spawn_errors_and_auto_binds_default_build_factory(tmp_path):
    """argon 20261106_0800 回歸（effects2cap_20261106 實況）：
    1. `g2_result.json` 的每格必須記錄 `spawn_errors`（逐輪 `r.agent.get("spawn_error")`），
       不得靜默吞掉執行器啟動錯誤（否則 `spawn_error` 格在 `g2_result.json` 中看起來像正常跑完 2 輪卻
       `tokens: null, stopped: stalled`）。
    2. 若呼叫端把 `g2._default_build` 或 `repair._default_build`（未呼叫的工廠函式）直接作為 `build`
       傳給 `run_g2_smoke`，`run_g2_smoke` 應自動以 `man.model` 綁定 `(provider, model)` 取得真正的
       `BuildFn`，避免因簽名同為 2 個位置參數而把 `(prompt, ws)` 誤綁成 `(provider, model)`。
    """
    base = tmp_path / "smoke"
    for sub in ("dab_035/draft", "dab_035/task"):
        shutil.copytree(SMOKE / sub, base / sub)
    full = json.loads(MANIFEST.read_text(encoding="utf-8"))
    full["drafts"] = [d for d in full["drafts"] if d["task_id"] == "dab_035"]
    (base / "manifest.json").write_text(json.dumps(full, ensure_ascii=False), encoding="utf-8")
    man = g2.G2Manifest.load(base / "manifest.json")

    seen_launches: list[Launch] = []

    def run_ok(launch: Launch, *, workspace: pathlib.Path, timeout_s: float,
               log_dir: pathlib.Path) -> dict:
        assert isinstance(launch, Launch), f"expected Launch, got {type(launch)}"
        seen_launches.append(launch)
        log_dir.mkdir(parents=True, exist_ok=True)
        (log_dir / "agent_stdout.log").write_text("{}", encoding="utf-8")
        (log_dir / "agent_stderr.log").write_text("", encoding="utf-8")
        return {"rc": 0, "timed_out": False, "wall_ms": 10, "spawn_error": None,
                "stdout_log": str(log_dir / "agent_stdout.log"),
                "stderr_log": str(log_dir / "agent_stderr.log")}

    # 直接傳入未呼叫的 g2._default_build 工廠，應自動綁定 man.model 並成功產生 Launch
    res = g2.run_g2_smoke(man, base, tmp_path / "out_factory", g2._default_build, run_ok,
                          include_dirs=("data",))
    assert len(seen_launches) == 1
    assert "--provider" in seen_launches[0].argv
    by = {(c["draft"], c["arm"]): c for c in res.cells}
    assert by[("dab_035-pi-C", "generic")]["spawn_errors"] == [None]

    # 當執行器回傳 spawn_error 時，g2_result.json 的 cell["spawn_errors"] 必須如實暴露
    def run_err(launch: Launch, *, workspace: pathlib.Path, timeout_s: float,
                log_dir: pathlib.Path) -> dict:
        return {"rc": None, "timed_out": False, "wall_ms": 1,
                "spawn_error": "RuntimeError: simulated launch crash"}

    res_err = g2.run_g2_smoke(man, base, tmp_path / "out_err", g2._default_build, run_err,
                              include_dirs=("data",))
    by_err = {(c["draft"], c["arm"]): c for c in res_err.cells}
    assert by_err[("dab_035-pi-C", "generic")]["spawn_errors"] == ["RuntimeError: simulated launch crash"]


def test_g2_propagates_manifest_synthetic_flag_and_verifies_request_sha256(tmp_path):
    """argon 20261106_1121 回歸（3b3f8f46 缺陷）：
    1. 當 manifest 的 draft 明確標記 `"synthetic": true`（如 `ops/reqloop/g2/multideliv/manifest.json`）時，
       `run_g2_smoke` 不得寫死 `synthetic=False`，必須把 `bool(d.get("synthetic", False))` 傳給
       `repair.repair_slice`，並在 `g2_result.json` 的每格記錄 `"synthetic": True/False`，
       遵守 2026-11-04 紅線「自造 G1 案例只能用於離線修復單元測試，標 synthetic」。
    2. 當 manifest 的 `d["task"]["request"]["sha256"]` 釘住 `request.md` 指紋時，
       `G2Manifest.verify_frozen` 必須實際核對 `request.md` 的存在與 sha256，不得漏驗。
    """
    multideliv_dir = REPO_ROOT / "ops" / "reqloop" / "g2" / "multideliv"
    base = tmp_path / "md"
    shutil.copytree(multideliv_dir, base)
    man_data = json.loads((base / "manifest.json").read_text(encoding="utf-8"))
    man_data["drafts"] = man_data["drafts"][:1]
    req_md = base / man_data["drafts"][0]["task"]["dir"] / "request.md"
    req_sha = hashlib.sha256(req_md.read_bytes()).hexdigest()
    man_data["drafts"][0]["task"]["request"] = {"sha256": req_sha}
    (base / "manifest.json").write_text(json.dumps(man_data, ensure_ascii=False), encoding="utf-8")

    man = g2.G2Manifest.load(base / "manifest.json")
    man.verify_frozen(base)

    def run_noop(launch, *, workspace, timeout_s, log_dir):
        log_dir.mkdir(parents=True, exist_ok=True)
        (log_dir / "agent_stdout.log").write_text("{}", encoding="utf-8")
        (log_dir / "agent_stderr.log").write_text("", encoding="utf-8")
        return {"rc": 0, "timed_out": False, "wall_ms": 10, "spawn_error": None,
                "stdout_log": str(log_dir / "agent_stdout.log"),
                "stderr_log": str(log_dir / "agent_stderr.log")}

    res = g2.run_g2_smoke(man, base, tmp_path / "out_syn", _fake_build([]), run_noop)
    assert all(c["synthetic"] is True for c in res.cells)

    # 竄改 request.md ⇒ verify_frozen 必須拒絕（ValueError）
    req_md.write_text("tampered request\n", encoding="utf-8")
    with pytest.raises(ValueError, match="request"):
        man.verify_frozen(base)

    # 刪除 request.md ⇒ verify_frozen 必須拒絕（FileNotFoundError）
    req_md.unlink()
    with pytest.raises(FileNotFoundError, match="request"):
        man.verify_frozen(base)


def test_g2_dry_run_verifies_frozen_files(tmp_path):
    """argon 20261106_1447 回歸：
    `g2.main(["--manifest", ..., "--dry-run"])` 在列印計畫並回傳 0 之前，
    必須先執行 `man.verify_frozen(base)`；若凍結檔案缺失或 sha256 不符，
    `--dry-run` 必須當場拋錯拒絕，不得在凍結毀損時仍回傳 rc=0。
    """
    multideliv_dir = REPO_ROOT / "ops" / "reqloop" / "g2" / "multideliv"
    base = tmp_path / "md"
    shutil.copytree(multideliv_dir, base)
    man_path = base / "manifest.json"

    # 正常凍結狀態：--dry-run 回傳 0
    assert g2.main(["--manifest", str(man_path), "--dry-run"]) == 0

    # 竄改 requirements.json：--dry-run 必須拋 ValueError 拒絕
    (base / "task" / "requirements.json").write_text('{"corrupted": true}\n', encoding="utf-8")
    with pytest.raises(ValueError, match="requirements"):
        g2.main(["--manifest", str(man_path), "--dry-run"])




