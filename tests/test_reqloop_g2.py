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


# ── 工具 ─────────────────────────────────────────────────────────────

def _sha(p: pathlib.Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


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
    assert out.cost["model_calls"] == 0


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
    assert out.cost["model_calls"] == 1


def test_min_rounds_one_recheck_breaks_regression_recorded(g1_task, tmp_path: pathlib.Path):
    """generic 重驗把對的改壞 ⇒ 退步必須記錄；每輪從原草稿起新工作區（保留原候選），
    第 2 輪不改 ⇒ 回到全 PASS ⇒ 停 GAP_CLOSED（第 1 輪的退步仍被記錄）。"""
    rs = RequirementSet.load(g1_task / "requirements.json")
    good = g1_task / "good"
    bad_md = (g1_task / "bad_grand_total_wrong" / "summary.md").read_text(encoding="utf-8")

    calls = {"n": 0}

    def run(launch: Launch, *, workspace: pathlib.Path, timeout_s: float,
            log_dir: pathlib.Path) -> dict:
        calls["n"] += 1
        if calls["n"] == 1:
            (pathlib.Path(workspace) / "summary.md").write_text(bad_md, encoding="utf-8")
            # 重驗把它改壞（報銷總金額錯值）
        # 第 2 輪：新工作區＝原草稿（好值），不改
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
    # 第 1 輪退步（PASS→FAIL）被記錄
    assert "req_summary_numbers" in out.regressed
    assert "req_summary_numbers" in out.rounds[0].diff.regressed
    # 第 2 輪新工作區（原草稿好值）⇒ 全 PASS ⇒ 停 GAP_CLOSED
    assert out.stopped == repair.STOP_GAP_CLOSED
    assert out.final_status["req_summary_numbers"] == "PASS"


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
    # localized 好草稿格：0 模型呼叫（缺口驅動）
    good_loc = [c for c in res.cells if c["arm"] == "localized"
                and c["draft"].startswith("dab_035")][0]
    assert good_loc["cost"]["model_calls"] == 0
    assert good_loc["stopped"] == repair.STOP_NO_GAP
    # bad 草稿格（answer 缺失）：修復後 readable 判定 PASS（值正確性＝hidden，不在此斷言）
    bad = [c for c in res.cells if c["draft"].startswith("dab_039")]
    assert len(bad) == 2
    assert all(c["final_readable_status"]["req_answer_kv"] == "PASS" for c in bad)
    # 結果可 machine-read
    j = res.to_dict()
    assert j["hidden_after"] == g2.AFTER_HIDDEN_UNKNOWN


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
    # min_rounds：generic 臂對的草稿也重驗 1 次；localized 缺口驅動 0 呼叫
    assert by[("dab_035-pi-C", "generic")]["cost"]["model_calls"] == 1
    assert by[("dab_035-pi-C", "localized")]["cost"]["model_calls"] == 0
    # bad 草稿：兩輪預算用盡（max_rounds=2＝_STALL_LIMIT＝2），缺口仍在
    assert by[("dab_507-pi-A", "generic")]["cost"]["model_calls"] == 2
    assert by[("dab_507-pi-A", "localized")]["cost"]["model_calls"] == 2
    assert by[("dab_039-pi-C", "generic")]["stopped"] in (
        repair.STOP_MAX_ROUNDS, repair.STOP_STALLED)
    assert by[("dab_039-pi-C", "generic")]["final_readable_status"]["req_answer_kv"] != "PASS"
