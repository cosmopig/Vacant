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
    # P001-20261105-03：fake 不寫原始 usage ⇒ 任一格缺 ⇒ 總計 UNKNOWN，
    # 不得把已知部分（部分格的 wall_ms）當完整總和
    assert data["totals"]["model_calls"] is None
    assert data["totals"]["tokens"] is None
    assert data["totals"]["wall_ms_total"] is None


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
