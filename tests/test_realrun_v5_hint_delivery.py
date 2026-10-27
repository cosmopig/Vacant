"""v5 fresh_hint 投遞稽核的釘死（`ops/realrun/audit_v5_hint_delivery.py`）。

v5 的 UNRESOLVED 判定（`ops/realrun/analyze_v5.json`：n=102 pairs, b=6, c=8,
p=0.7905, scorer=false）建立在預註冊的治療描述上：兩臂唯一差異＝treatment 在
attempt 1 失敗後、重抽前，工作區放一份 ≤380B 真實失敗提示檔，agent 自讀進
prompt。本測試把「治療真的被投遞」這個邊界條件釘死，三層證據：

1. wire 層（最硬）：每個 attempt k>=2 的請求體（JSON 解析後）逐字包含該次
   該看到的提示全文；attempt 1 不含；control 全格不含。
2. 檔案層：treatment attempts_used>=2 的格 VACANT_FEEDBACK.md 存在且文字==
   最後一次寫入的提示；attempts_used==1 的格沒有該檔；control 204 格全無。
3. 摘要層：run 摘要 JSON 的 per-attempt feedback 元數據與 wire/檔案一致；
   兩臂 attempt-1 的 argv_sha256 相同（launcher prompt 逐位元組一致，差異只
   可能來自 agent 端追加的提示）。

另有兩個誠實性釘死：
- 描述性子集（treatment 真正用到提示的 49 pairs）明確標註 out_of_prereg、
  decision_state=null、無 p——它是 UNRESOLVED 判定的「暴露度」，不是新判定，
  不可引用為效應（v5 的判定仍是 102 pairs 的 pooled McNemar）。
- 稽核腳本自身可偽反證：--selftest 造 8 個合成 cell（好格要過、6 種 anomaly
  形狀要被抓、D5 配對要工作）。

落盤數據（~/dev/ops/realrun/runs_v5_r*）不在 repo；若在本機存在則重跑稽核
並與 repo 鏡像逐欄位比對，不在則 skip（鏡像本身的釘死不受影響）。
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
HERE = REPO / "ops" / "realrun"
AUDIT = HERE / "audit_v5_hint_delivery.py"
AUDIT_JSON = HERE / "audit_v5_hint_delivery.json"
ANALYZE = HERE / "analyze_v5.json"
PREREG = HERE / "prereg_v5.json"


def _load(p: Path) -> dict:
    assert p.exists(), f"missing {p}（引用前必須在 repo 裡）"
    return json.loads(p.read_text(encoding="utf-8"))


def test_files_present() -> None:
    for p in (AUDIT, AUDIT_JSON, ANALYZE, PREREG):
        assert p.exists(), f"missing {p}"


def test_audit_selftest_catches_all_anomaly_shapes() -> None:
    r = subprocess.run(
        [sys.executable, str(AUDIT), "--selftest"],
        capture_output=True, text=True, cwd=REPO, timeout=120)
    assert r.returncode == 0, f"selftest failed:\n{r.stdout}\n{r.stderr}"
    assert "selftest OK" in r.stdout


def test_audit_passes_all_cells() -> None:
    d = _load(AUDIT_JSON)
    assert d["schema"] == "vacant.audit/v5_hint_delivery/1"
    assert d["prereg_id"] == _load(PREREG)["id"]
    assert d["n_cells"] == 204  # 34 tasks x 2 arms x 3 reps
    assert d["all_checks_passed"] is True
    # 每個 cell 都過（anomalies 全空）
    for root_s, arms in d["per_root"].items():
        for arm, a in arms.items():
            assert a["n_cells"] == 34
            assert a["anomalies"] == [], f"{root_s} {arm}: {a['anomalies']}"
    # 負對照：control 204 格裡沒有非空提示檔
    assert d["control_nonempty_hint_files"] == 0
    # D5：兩臂 launcher prompt 逐位元組一致
    assert d["D5_prompt_identical_across_arms"]["pass"] is True
    assert d["D5_prompt_identical_across_arms"]["mismatches"] == []
    # wire 層：抽查一個 att>=2 的 treatment cell，每個 attempt k>=2 都有
    # marker 且逐字提示都在
    found = 0
    for root_s, arms in d["per_root"].items():
        for t, cell in arms["C_fresh_hint3"]["cells"].items():
            for pa in cell["checks"]["D4_wire_content"]["per_attempt"]:
                assert pa["marker"] is True and pa["exact_hint"] is True
                found += 1
    assert found >= 49  # 至少覆蓋 49 個「提示被用到」的格


def test_audit_consistent_with_analyze_v5() -> None:
    """稽核的逐格 accepted 必須與主分析 (b=6, c=8, n=102) 自洽。"""
    d = _load(AUDIT_JSON)
    a = _load(ANALYZE)
    assert d["arms"]["control"] == a["arm_a"] == "B_resample3"
    assert d["arms"]["treatment"] == a["arm_b"] == "C_fresh_hint3"
    ctrl = sum(r["B_resample3"]["n_accepted"] for r in d["per_root"].values())
    treat = sum(r["C_fresh_hint3"]["n_accepted"] for r in d["per_root"].values())
    b, c = a["pooled"]["b"], a["pooled"]["c"]
    assert a["n_pairs"] == 102 and (b, c) == (6, 8)
    # both = ctrl - b = treat - c（兩臂的「雙接受」格數必須一致）
    assert ctrl - b == treat - c
    assert (ctrl, treat) == (65, 67)


def test_descriptive_subset_labeled_not_a_decision() -> None:
    d = _load(AUDIT_JSON)["descriptive_hint_used_subset"]
    # 誠實性：這是描述性暴露度，不是判定
    assert d["out_of_prereg"] is True
    assert d["decision_state"] is None
    assert "p" not in d  # 明確沒有 p-value
    # 數值釘死（重跑必須同樣）
    assert (d["n_pairs"], d["control_accepted"], d["treatment_accepted"]) == (49, 17, 14)
    assert (d["b_control_only"], d["c_treatment_only"]) == (6, 3)
    # 方向守衛的措辭：note 裡不得出現「有害/harmful」式結論
    note = d["note"].lower()
    assert "harm" not in note and "有害" not in d["note"]


def test_rerun_audit_on_real_data_matches_mirror() -> None:
    """落盤數據在本機時：重跑稽核，結果（除生成時間）必須與鏡像一致。"""
    d = _load(AUDIT_JSON)
    roots = [Path(p) for p in d["roots"]]
    if not all(p.exists() for p in roots):
        pytest.skip("v5 落盤數據不在此機（runs_v5_r* 不在）；鏡像釘死仍有效")
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "rerun.json"
        r = subprocess.run(
            [sys.executable, str(AUDIT), "--prereg", str(PREREG),
             "--roots", *[str(p) for p in roots], "--json", str(out)],
            capture_output=True, text=True, cwd=REPO, timeout=600)
        assert r.returncode == 0, f"audit rerun failed:\n{r.stdout}\n{r.stderr}"
        fresh = json.loads(out.read_text(encoding="utf-8"))
    for k in ("generated",):
        fresh.pop(k, None)
        d.pop(k, None)
    assert fresh == d, "rerun 與鏡像不一致（落盤數據或被鏡像被改動）"
