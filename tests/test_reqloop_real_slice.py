"""P20261107_0237-1（資深審查 2026-11-06 #3＋11-06 指示 #4）：CSV/JSON 真實任務
最小對照規格——dab_378（e008 真實 CSV 任務、真實失敗草稿 9 PASS/2 FAIL）六要素
（原始需求、真實失敗產物、目前行為、預期可展示改善、成本上限 60/4M/300s、獨立
驗收方法）＋三離線門（verify_frozen / dry-run / 無洩漏）。

本檔只驗離線規格與凍結；零模型呼叫。發射是另一步授權（點名＋成本另報），
不在本檔範圍。紅線沿用：tamper/UNKNOWN 不算成功；缺值＝UNKNOWN 不填 0；
開發選樣不宣稱 localized 較好。
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import re

import vacant_network.reqloop.g2 as g2
import vacant_network.reqloop.repair as repair
from vacant_network.reqloop.checks import run_requirement_checks
from vacant_network.reqloop.requirements import RequirementSet


def _sha(p: pathlib.Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()

REAL_SLICE_MANIFEST = (
    pathlib.Path(__file__).resolve().parent.parent
    / "ops" / "reqloop" / "g2" / "real_slice" / "manifest.json"
)
# r1157（P20261107_0210-1）：dab_055 content closed loop slice 的產品管線凍結規格
DAB055_MANIFEST = (
    pathlib.Path(__file__).resolve().parent.parent
    / "ops" / "reqloop" / "g2" / "real_slice_dab055" / "manifest.json"
)
SIX_ELEMENTS = (
    "original_user_requirement",
    "existing_real_failed_artifact",
    "current_behavior",
    "expected_demonstrable_improvement",
    "cost_cap",
    "independent_acceptance",
)


def _loaded():
    assert REAL_SLICE_MANIFEST.is_file(), "real_slice manifest 未凍結"
    return g2.G2Manifest.load(REAL_SLICE_MANIFEST)


def test_real_slice_manifest_frozen_four_cells():
    """真實 CSV 任務最小對照＝1 失敗＋1 正確真草稿 × 2 臂＝4 格；凍結副本存在、hash 對得上。
    失敗草稿保持在 drafts[0]（其它測試與針守衛以 drafts[0] 為反例基準）。"""
    man = _loaded()
    man.verify_frozen(REAL_SLICE_MANIFEST.parent)
    assert set(man.arms) == {"generic", "localized"}
    assert len(man.drafts) == 2, "4 格最小對照＝2 真草稿 × 2 臂（11-06 指示 2：正確成果須有真實基線）"
    assert {d["role"] for d in man.drafts} == {"bad", "good"}
    assert man.drafts[0]["role"] == "bad", "失敗草稿須為 drafts[0]（反例基準，針守衛依賴）"
    base = REAL_SLICE_MANIFEST.parent
    for d in man.drafts:
        assert d["task_id"] == "dab_378"
        assert d["source"]["score"] is not None, "真實草稿須有已記錄分數（不得 null）"
        assert d["source"]["score"].get("task_id") == "dab_378"
        for rel, h in d["draft"]["files"].items():
            f = base / d["draft"]["dir"] / rel
            assert f.is_file()
            assert _sha(f) == h
        assert d["task"]["requirements"]["sha256"]
        # r1011 口徑：凍結資料檔（CSV）必須釘 hash 且可解析
        assert d["task"].get("data_files", {}).get("data/2014_q4.csv"), \
            "真實 CSV 任務必須釘資料檔 hash（漏驗即放過洞）"
        df = base / d["task"]["dir"] / "data/2014_q4.csv"
        assert df.is_file()
    # 兩臂公平比較客觀基線：兩草稿共用同一 task 目錄（同一 request/requirements/CSV）
    assert len({d["task"]["dir"] for d in man.drafts}) == 1, \
        "兩草稿必須共用同一 task 目錄（同起點），實得不同"
    cells = g2.plan_cells(man)
    assert len(cells) == 4
    assert {(n, a) for n, a in cells} == {
        ("dab_378-pi-A", "generic"), ("dab_378-pi-A", "localized"),
        ("dab_378-pi-C", "generic"), ("dab_378-pi-C", "localized"),
    }


def test_real_slice_six_elements_and_cost_cap():
    """六要素齊備；成本上限＝審查指定 max_tool_calls=60 / max_tokens=4000000 /
    timeout=300s，且 budget 欄位同值（dry-run 文字行不得缺席）。"""
    man = _loaded()
    el = man.raw.get("six_elements", {})
    missing = [k for k in SIX_ELEMENTS if k not in el]
    assert not missing, f"六要素缺：{missing}"
    cc = el["cost_cap"]
    assert cc["max_tool_calls"] == 60
    assert cc["max_tokens"] == 4000000
    assert cc["timeout_s_per_round"] == 300
    b = man.budget
    assert b["max_tool_calls"] == 60
    assert b["max_tokens"] == 4000000
    assert b["timeout_s_per_round"] == 300
    assert b["max_rounds_per_cell"] == 1, "最小對照＝單輪（multideliv 同口徑）"


def test_real_slice_real_failed_artifact_two_kurtosis_fail():
    """現有真實失敗產物＝9 PASS/2 FAIL（pre/post_kurtosis，可見重算反例可重現）；
    保留意圖＝9 滿足行須逐位元組保留、只改 2 未滿足行。"""
    man = _loaded()
    base = REAL_SLICE_MANIFEST.parent
    d = man.drafts[0]
    task_dir = base / d["task"]["dir"]
    draft_dir = base / d["draft"]["dir"]
    req_set = RequirementSet.load(task_dir / "requirements.json")
    results = run_requirement_checks(task_dir, req_set, draft_dir)
    st = {r.claim_id: r.status for r in results}
    assert st["pre_kurtosis"] == "FAIL", "測試空洞：pre_kurtosis 非 FAIL"
    assert st["post_kurtosis"] == "FAIL", "測試空洞：post_kurtosis 非 FAIL"
    assert sum(1 for v in st.values() if v == "PASS") == 9, \
        f"真實失敗產物應為 9 PASS/2 FAIL，實得 {st}"
    p = d["preservation"]
    assert set(p["unsatisfied_items"]) == {"pre_kurtosis", "post_kurtosis"}
    assert len(p["satisfied_items"]) == 9
    assert p["note"]


def test_real_slice_baseline_good_and_bad():
    """4 格 baseline（0 模型呼叫）：真實正確草稿 11/11 PASS、真實失敗草稿 9 PASS/2 FAIL——
    「正確成果是否退步（right_to_wrong=0）」的客觀真實基線（11-06 指示 2）。"""
    man = _loaded()
    base = REAL_SLICE_MANIFEST.parent
    by_role = {d["role"]: d for d in man.drafts}
    assert set(by_role) == {"bad", "good"}
    for role in ("good", "bad"):
        d = by_role[role]
        task_dir = base / d["task"]["dir"]
        draft_dir = base / d["draft"]["dir"]
        req_set = RequirementSet.load(task_dir / "requirements.json")
        results = run_requirement_checks(task_dir, req_set, draft_dir)
        st = {r.claim_id: r.status for r in results}
        n_pass = sum(1 for v in st.values() if v == "PASS")
        if role == "good":
            assert n_pass == 11 and all(v == "PASS" for v in st.values()), \
                f"dab_378-pi-A 應 11/11 PASS，實得 {st}"
        else:
            assert n_pass == 9, f"dab_378-pi-C 應 9 PASS/2 FAIL，實得 {st}"
            assert {k for k, v in st.items() if v == "FAIL"} == {"pre_kurtosis", "post_kurtosis"}, st


def test_real_slice_localized_prompt_leak_free():
    """無洩漏門：localized 提示點名 2 條 FAIL（修復目標仍在），但重算峰度值
    -1.13 絕不進提示；FAIL 證據標記 expected_in_evidence=False。零模型呼叫。"""
    man = _loaded()
    base = REAL_SLICE_MANIFEST.parent
    d = man.drafts[0]
    task_dir = base / d["task"]["dir"]
    draft_dir = base / d["draft"]["dir"]
    req_set = RequirementSet.load(task_dir / "requirements.json")
    before = run_requirement_checks(task_dir, req_set, draft_dir)
    failing = [c for c in before if c.status != "PASS"]
    assert {c.claim_id for c in failing} == {"pre_kurtosis", "post_kurtosis"}
    for c in failing:
        assert c.evidence.get("expected_in_evidence") is False, \
            f"{c.claim_id}：FAIL 證據須標記 expected_in_evidence=False"
    prompt = repair.build_repair_prompt(
        task_dir, req_set, draft_dir, before, feedback_mode="localized")
    assert "pre_kurtosis" in prompt, "失敗條目未進 localized 提示（修復目標丟失）"
    assert "post_kurtosis" in prompt
    assert "-1.13" not in prompt, "localized 提示洩重算峰度值 -1.13"


def test_real_slice_dry_run_lists_four_cells_and_caps():
    """--dry-run 文字行：2 drafts · 4 cells、成本上限顯式（漏掉的 flag 正是長尾要防的形狀）。"""
    man = _loaded()
    txt = g2.dry_run_text(man)
    assert "2 drafts · 4 cells" in txt
    assert "1 drafts" not in txt
    assert "dab_378-pi-A × generic" in txt
    assert "dab_378-pi-A × localized" in txt
    assert "dab_378-pi-C × generic" in txt
    assert "dab_378-pi-C × localized" in txt
    assert "max_tool_calls=60" in txt
    assert "max_tokens=4000000" in txt
    assert "timeout_s_per_round=1" not in txt
    assert "timeout_s_per_round=300" in txt


def test_real_slice_needle_is_true_recomputed_value():
    """資深審查 2026-11-06 #2 驗收判準：無洩漏針必須是對應題目的真實重算值——
    由 checker 自己的 col_stats 代碼路徑對凍結 task/data/ 實算得出，不是手寫數字。
    （錯誤針＝空洞斷言：切片 A 的 1628／0.020500 即此形狀、已收斂移除；r1140 4990.0→4811.76 同訓。）
    零模型呼叫。"""
    import csv
    from vacant_network.reqloop.checks import _col_stats
    man = _loaded()
    base = REAL_SLICE_MANIFEST.parent
    d = man.drafts[0]
    needle = "-1.13"
    assert needle in man.raw.get("leak_guard", ""), "manifest leak_guard 須點名針（防針漂移）"
    req_set = RequirementSet.load(base / d["task"]["dir"] / "requirements.json")
    hit = 0
    for it in req_set.items:
        if it.id not in ("pre_kurtosis", "post_kurtosis"):
            continue
        hit += 1
        rc = it.params["recompute"]
        assert rc["type"] == "col_stats"
        data_path = base / d["task"]["dir"] / it.params["data_file"]
        with open(data_path, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        expected = round(_col_stats(rows, rc), int(rc.get("round", 0)))
        assert str(expected) == needle, \
            f"{it.id}: 針 {needle!r} 非 task/data 實算真值 {expected!r}（空洞斷言）"
    assert hit == 2, "測試空洞：pre/post_kurtosis 未皆驗到"


def test_real_slice_status_pending_naming():
    """發射需點名＋成本另報（11-06 #7）：規格凍結但狀態不得是 FIRED。"""
    man = _loaded()
    status = man.raw.get("status", "")
    assert status == "FROZEN_PENDING_NAMING", f"status={status!r}（發射未授權）"


def test_real_slice_smoke_preservation_and_exit_codes(tmp_path):
    """P20261107_0041-2：真實 CSV 切片端到端修復保留／拒收管線（假代理、零模型呼叫）。
    C×generic 正確修復 kurtosis、其餘 8 鍵保留 → gap_closed／exit 0／8 鍵 preserved；
    C×localized 修復但竄改初始 PASS 的 pre_mean → satisfied_mutated、exit 20 拒收；
    A（正確草稿）兩臂 exit 0、right_to_wrong（regressed）== 0。"""
    from vacant_network.adapters.agents import Launch
    man = g2.G2Manifest.load(REAL_SLICE_MANIFEST)
    base = REAL_SLICE_MANIFEST.parent
    before_txt = (base / "dab_378-pi-C" / "draft" / "answer.txt").read_text(encoding="utf-8")
    assert "-1.17" in before_txt, "測試空洞：草稿 C 應有 kurtosis 錯值"
    fixed = before_txt.replace("-1.17", "-1.13")                     # 只改 2 未滿足行
    tampered = fixed.replace("@pre_mean[21144.08]", "@pre_mean[999.0]")  # 修復＋竄改已滿足鍵
    PRESERVED_8 = {"pre_mean", "pre_median", "pre_sd", "pre_skewness",
                   "post_mean", "post_median", "post_sd", "post_skewness"}

    def build(prompt: str, ws: pathlib.Path) -> Launch:
        return Launch(argv=["true"], note="fake")

    def run(launch: Launch, *, workspace: pathlib.Path, timeout_s: float,
            log_dir: pathlib.Path, **kw) -> dict:
        ws_s = str(workspace)
        if "dab_378-pi-C" in ws_s:   # A（正確草稿）：no-op、不得被改
            text = tampered if "localized" in ws_s else fixed
            (pathlib.Path(workspace) / "answer.txt").write_text(text, encoding="utf-8")
        log_dir.mkdir(parents=True, exist_ok=True)
        (log_dir / "agent_stdout.log").write_text("{}", encoding="utf-8")
        (log_dir / "agent_stderr.log").write_text("", encoding="utf-8")
        return {"rc": 0, "timed_out": False, "wall_ms": 700, "spawn_error": None,
                "stdout_log": str(log_dir / "agent_stdout.log"),
                "stderr_log": str(log_dir / "agent_stderr.log")}

    res = g2.run_g2_smoke(man, base, tmp_path / "out", build, run, include_dirs=("data",))
    by = {(c["draft"], c["arm"]): c for c in res.cells}
    assert len(res.cells) == 4, "4 格＝2 真草稿 × 2 臂"
    c_fix = by[("dab_378-pi-C", "generic")]   # (1) 正確修復：缺口關閉＋其餘保留＋exit 0
    assert c_fix["stopped"] == "gap_closed"
    assert c_fix["exit_code"] == 0
    assert set(c_fix["satisfied_preserved"]) == PRESERVED_8
    assert c_fix["satisfied_mutated"] == []
    assert c_fix["fixed"] == ["post_kurtosis", "pre_kurtosis"]
    c_tamp = by[("dab_378-pi-C", "localized")]  # (2) 修復但竄改已滿足項：精確偵測＋exit 20
    assert "pre_mean" in c_tamp["satisfied_mutated"]
    assert c_tamp["exit_code"] == 20
    assert c_tamp["stopped"] != "gap_closed"
    for arm in ("generic", "localized"):       # (3) 正確草稿：兩臂 exit 0、right_to_wrong == 0
        a = by[("dab_378-pi-A", arm)]
        assert a["exit_code"] == 0
        assert a["regressed"] == []


def test_real_slice_dab055_baseline_reproduces_content_counterexample():
    """P20261107_0210-1（r1157）：dab_055 content closed loop slice 進產品管線。

    此前該 slice 的內容反例只存在於 ad-hoc 審計腳本
    （ops/audits/dab055_slice_precheck_20261107.py）；本測試把它變成產品自己的
    離線命令輸出（g2 --manifest … --baseline），且：
    - 凍結副本存在、hash 對得上（verify_frozen，同 r1011 口徑：每條 pin 都驗）
    - baseline 對 bad 草稿（2081990.36 點估計 float）必為 FAIL/FAIL——可重現內容反例；
      I-4 形狀：required 為空集不許冒稱全過
    - 重算期望整數 2081990 永不進 detail/evidence；草稿自己的值 2081990.36 是
      合法內容、允許出現（以「2081990 後不接小數點」區分兩者）
    - 工單成本上限（25 calls / 1,451,938 tokens，cell 總預算）在 budget 欄位同值
    - 本檔零模型呼叫；發射＝另一步授權（點名＋成本另報），不在本檔範圍
    """
    man = g2.G2Manifest.load(DAB055_MANIFEST)
    base = DAB055_MANIFEST.parent
    man.verify_frozen(base)

    # 2 格＝1 bad 真草稿 × 2 臂；同草稿同預算（2 輪×300s、min_rounds 語義同 effects2 口徑）
    assert set(man.arms) == {"generic", "localized"}
    assert [d["name"] for d in man.drafts] == ["dab_055-pi-C"]
    assert man.drafts[0]["role"] == "content_counterexample"
    assert man.drafts[0]["synthetic"] is False, "真草稿，不是 synthetic"
    assert len(g2.plan_cells(man)) == 2
    b = man.budget
    assert b["max_rounds_per_cell"] == 2 and b["timeout_s_per_round"] == 300
    assert b["min_rounds"] == {"generic": 1, "localized": 0}
    cc = b["cell_cost_cap"]
    assert cc["model_calls"] == 25 and cc["tokens_total"] == 1451938, "工單成本上限同值"
    assert man.drafts[0]["source"]["score"]["pass"] is False, "已記錄獨立 scorer：draft fail"

    # baseline：FAIL/FAIL 內容反例（產品自己的離線命令，不是 ad-hoc 腳本）
    j = g2.baseline_json(man, base)
    d = j["drafts"][0]
    assert d["name"] == "dab_055-pi-C"
    assert d["required_total"] == 2
    assert d["required_pass"] == 0, "bad 草稿 baseline 必為 FAIL/FAIL（反例）"
    assert d["all_required_pass"] is False
    by_id = {i["id"]: i for i in d["items"]}
    assert by_id["req_answer_kv"]["status"] == "FAIL"
    assert by_id["req_mean_cases_recomputed"]["status"] == "FAIL"

    # 無洩漏：期望整數 2081990（重算值）不得進 detail/evidence；
    # 2081990.36（草稿自己的 float 值）是合法內容、須允許出現
    blob = json.dumps({k: by_id[k] for k in ("req_answer_kv", "req_mean_cases_recomputed")},
                      ensure_ascii=False)
    assert not re.search(r"2081990(?!\.)", blob), f"重算期望值進證據：{blob}"
    assert "2081990.36" in blob, "草稿自己的值（合法內容）應可見"

    # dry-run 同 manifest 可列格（發射前最後一道離線門，本檔不真跑）
    dj = g2.dry_run_json(man)
    assert [c["draft"] for c in dj["cells"]] == ["dab_055-pi-C", "dab_055-pi-C"]
    assert dj["hidden_after"] == "UNKNOWN"


def test_real_slice_dab055_needle_is_true_recomputed_value():
    """P20261107_0243-2 針守衛（資深審查 2026-11-07 #3）：req_mean_cases_recomputed 的
    重算真值必須是對凍結資料 data/estimated_numbers.csv 實算的點估計均值
    （dab_055 規則：純整數／點估計前導整數，Null/空/非數值忽略），round 後恰為 2081990、
    與 manifest purpose 點名之針一致——手寫數字不算（空洞斷言，同 r1140 訓）。
    直接呼叫產品 checks._mean_int_col(rows, rc)，禁止在測試內複製解析迴圈。零模型呼叫。"""
    import csv
    from vacant_network.reqloop.checks import _mean_int_col
    man = g2.G2Manifest.load(DAB055_MANIFEST)
    base = DAB055_MANIFEST.parent
    d = man.drafts[0]
    needle = "2081990"
    assert needle in man.raw.get("purpose", ""), "manifest purpose 須點名針（防針漂移）"
    req_set = RequirementSet.load(base / d["task"]["dir"] / "requirements.json")
    item = next(it for it in req_set.items if it.id == "req_mean_cases_recomputed")
    rc = item.params["recompute"]
    assert rc["type"] == "mean_int_col"
    data_path = base / d["task"]["dir"] / item.params["data_file"]
    with open(data_path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    expected, unrounded = _mean_int_col(rows, rc)
    assert f"{int(expected)}" == needle, (
        f"真值漂移：_mean_int_col={expected!r} (unrounded={unrounded!r}) ≠ 針 {needle}"
    )


def test_real_slice_dab055_precheck_single_source_of_truth():
    """P20261107_0539-1（r1166）：dab_055 審計預檢腳本的值計算＝產品 checks._mean_int_col
    （單一事實來源）——防「審計腳本內嵌解析迴圈、產品改口徑後靜默漂移」。

    本輪改善：ops/audits/dab055_slice_precheck_20261107.py 不再複製 _mean_int_col 的
    解析迴圈，改直接呼叫產品 _mean_int_col 取值，並輸出 single_source_of_truth 欄位。
    本測試斷言：審計預檢輸出的 single_source_of_truth.expected/unrounded == 產品對同一
    凍結資料（repo 凍結 slice，sha bc485997…，與預檢讀的 effects2 快照逐位元組同）實算值。
    預檢輸出在 ~/dev/ops（本機審計證據）；若缺席（CI 他主機）則 skip，不視為失敗。
    若有人把預檢回復成內嵌迴圈的舊版（無 single_source_of_truth 欄位），本測試即紅。
    零模型呼叫。
    """
    import csv
    import pytest
    from vacant_network.reqloop.checks import _mean_int_col
    precheck_json = (
        pathlib.Path.home() / "dev" / "ops" / "audits" / "dab055_slice_precheck_20261107.json"
    )
    if not precheck_json.is_file():
        pytest.skip("dab055 預檢輸出不在本機（~/dev/ops/audits），無法交叉驗證")
    man = g2.G2Manifest.load(DAB055_MANIFEST)
    base = DAB055_MANIFEST.parent
    d = man.drafts[0]
    req_set = RequirementSet.load(base / d["task"]["dir"] / "requirements.json")
    item = next(it for it in req_set.items if it.id == "req_mean_cases_recomputed")
    rc = item.params["recompute"]
    assert rc["type"] == "mean_int_col"
    data_path = base / d["task"]["dir"] / item.params["data_file"]
    with open(data_path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    expected, unrounded = _mean_int_col(rows, rc)
    audit = json.loads(precheck_json.read_text(encoding="utf-8"))
    sst = audit.get("single_source_of_truth")
    assert sst is not None, (
        "審計預檢缺 single_source_of_truth 欄位——疑似回復「內嵌解析迴圈」複製，"
        "會與產品 _mean_int_col 口徑漂移"
    )
    assert "checks._mean_int_col" in sst.get("expected_from", ""), (
        f"single_source_of_truth.expected_from 須點名產品函數，實得 {sst.get('expected_from')!r}"
    )
    assert sst["expected"] == expected, (
        f"審計腳本值 {sst['expected']!r} ≠ 產品 _mean_int_col {expected!r}（口徑漂移）"
    )
    assert sst["unrounded"] == unrounded, (
        f"審計腳本 unrounded {sst['unrounded']!r} ≠ 產品 {unrounded!r}"
    )


def test_real_slice_dab055_smoke_pipeline_and_exit_codes(tmp_path):
    """P20261107_0243-2：dab_055 內容閉環端到端修復／拒收管線（假代理、零模型呼叫）。

    同草稿（2081990.36 點估計 float）、同預算（manifest 凍結 2 輪×300s）、2 臂：
    - localized：修復非整數格式錯誤並保留點估計數值 → @mean_cases[2081990]
      → req_answer_kv＋req_mean_cases_recomputed 兩缺口全閉、gap_closed、exit 0；
    - generic：落入 note 嚴整數解讀陷阱（2200，獨立 scorer 已記錄的 note-trap 形狀、
      非隱藏分數反推）→ req_answer_kv PASS（值合法整數）但 req_mean_cases_recomputed
      FAIL、不提前放行，max_rounds 用盡以 exit 20 拒收、unresolved 精確點名未滿足條目。
    （11-06 指示 4：先證明可修回一種內容錯誤才擴量。）"""
    from vacant_network.adapters.agents import Launch
    man = g2.G2Manifest.load(DAB055_MANIFEST)
    base = DAB055_MANIFEST.parent
    # 測試空洞門：bad 草稿 baseline 必 FAIL/FAIL（可重現反例），否則「修好」無意義
    j = g2.baseline_json(man, base)
    st = {i["id"]: i["status"] for i in j["drafts"][0]["items"]}
    assert st == {"req_answer_kv": "FAIL", "req_mean_cases_recomputed": "FAIL"}, st

    def build(prompt: str, ws: pathlib.Path) -> Launch:
        return Launch(argv=["true"], note="fake")

    def run(launch: Launch, *, workspace: pathlib.Path, timeout_s: float,
            log_dir: pathlib.Path, **kw) -> dict:
        ws_s = str(workspace)
        if "localized" in ws_s:
            text = "@mean_cases[2081990]"    # 格式修復、保留點估計數值
        else:
            text = "@mean_cases[2200]"       # 模擬 note 嚴整數解讀陷阱
        (pathlib.Path(workspace) / "answer.txt").write_text(text, encoding="utf-8")
        log_dir.mkdir(parents=True, exist_ok=True)
        (log_dir / "agent_stdout.log").write_text("{}", encoding="utf-8")
        (log_dir / "agent_stderr.log").write_text("", encoding="utf-8")
        return {"rc": 0, "timed_out": False, "wall_ms": 700, "spawn_error": None,
                "stdout_log": str(log_dir / "agent_stdout.log"),
                "stderr_log": str(log_dir / "agent_stderr.log")}

    res = g2.run_g2_smoke(man, base, tmp_path / "out", build, run, include_dirs=("data",))
    by = {(c["draft"], c["arm"]): c for c in res.cells}
    assert len(res.cells) == 2, "2 格＝1 bad 真草稿 × 2 臂"
    c_loc = by[("dab_055-pi-C", "localized")]
    assert c_loc["stopped"] == "gap_closed"
    assert c_loc["exit_code"] == 0
    assert set(c_loc["fixed"]) == {"req_answer_kv", "req_mean_cases_recomputed"}
    assert c_loc["unresolved"] == []
    assert c_loc["regressed"] == [], "無初始已滿足項，退步必為空"
    c_gen = by[("dab_055-pi-C", "generic")]
    assert c_gen["exit_code"] == 20
    assert c_gen["stopped"] == "max_rounds"
    assert c_gen["unresolved"] == ["req_mean_cases_recomputed"]
    assert c_gen["after_readable_status"]["req_answer_kv"] == "PASS", \
        "2200 是合法整數格式：req_answer_kv 應 PASS（未滿足的是值、非格式）"
