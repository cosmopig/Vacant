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
import pathlib

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
