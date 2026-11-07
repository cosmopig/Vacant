"""effects2_20261106 審計摘要守衛（11-06 #1/#2 必答數字的常設針）。

r1135 的 ops/audits/effects2_20261106_analysis.json（0fa90edd）是本批 28 格的
正規審計記錄。本測試是它的常設守衛：由 raw（~/dev/ops/effects2_20261106）獨立
重算裁決數字，與摘要逐項對照；並釘住事實常數（bad9 7/9、good5 5/5、
昨日 6/9→9/9、成本 235/5,576,588 vs 347/9,691,033），防「摘要與 raw 同漂移」
與空洞斷言。raw 在 repo 外（1004 主機）；缺目錄 skip（不在本機的 CI 不得偽綠）。

裁決紀律（與摘要一致）：tamper/UNKNOWN 不計成功；兩臂同起始草稿 hash；
與昨日比較標明 dabstep-1753 排除、僅同 9 題集合；成本缺值＝null 不填 0。
"""
import json
import pathlib

import pytest

REPO = pathlib.Path(__file__).resolve().parent.parent
ANALYSIS = REPO / "ops" / "audits" / "effects2_20261106_analysis.json"
RAW = pathlib.Path("/home/user1/dev/ops/effects2_20261106")
CONTRAST = RAW / "contrast"
ARMS = ("generic", "localized")


def _raw_cells():
    out = {}
    for f in sorted(CONTRAST.glob("g2_result_*.json")):
        d = json.loads(f.read_text())
        for c in d["cells"]:
            out[(c["draft"], c["arm"])] = (d, c)
    return out


def _recompute():
    cells = _raw_cells()
    ba = json.loads((RAW / "before_after.json").read_text())
    ba_by = {(e["draft"], e["arm"]): e for e in ba["cells"]}
    drafts = sorted({k[0] for k in cells})
    assert len(cells) == 28 and len(drafts) == 14

    same_start = all(
        cells[(d, "generic")][1]["draft_sha256"] == cells[(d, "localized")][1]["draft_sha256"]
        for d in drafts
    )
    mans = {cells[(d, a)][0]["manifest"]["sha256"] for d in drafts for a in ARMS}
    assert len(mans) == 1
    bad = sorted(d for d in drafts if cells[(d, "generic")][1]["role"] == "bad")
    good = sorted(d for d in drafts if cells[(d, "generic")][1]["role"] == "good")
    assert len(bad) == 9 and len(good) == 5
    assert "dabstep-1753" not in drafts  # 本批排除
    for d in bad:  # baseline sanity：bad 原始全錯
        for arm in ARMS:
            assert cells[(d, arm)][1]["before_hidden"]["pass"] is False
    for d in good:  # good 原始全對
        for arm in ARMS:
            assert cells[(d, arm)][1]["before_hidden"]["pass"] is True

    def after_ok(draft: str, arm: str) -> bool:
        return ba_by[(draft, arm)]["after_this_rep"]["independent_pass"] is True

    def fixed_of(draft: str, arm: str) -> bool:  # 原始錯（before_hidden False）→ 修好，tamper 不計
        c = cells[(draft, arm)][1]
        assert c["before_hidden"]["pass"] is False
        return after_ok(draft, arm) and not c["source_tampered"]

    def yest(draft: str, arm: str) -> bool:  # 昨日 d38d2eb2 policy30 2r 修復結果
        return ba_by[(draft, arm)]["before_d38d2eb2"]["policy30_2r"]["independent_pass"] is True

    def tot(arm: str, field: str, ds):
        vals = [cells[(d, arm)][1]["cost"].get(field) for d in ds]
        return sum(v for v in vals if v is not None)

    return {
        "same_start": same_start,
        "bad_generic": sum(fixed_of(d, "generic") for d in bad),
        "bad_localized": sum(fixed_of(d, "localized") for d in bad),
        "good_generic": sum(after_ok(d, "generic") for d in good),
        "good_localized": sum(after_ok(d, "localized") for d in good),
        "yest_generic": sum(yest(d, "generic") for d in bad),
        "yest_localized": sum(yest(d, "localized") for d in bad),
        "tampered": sum(cells[(d, a)][1]["source_tampered"] for d in drafts for a in ARMS),
        "gen_bad_calls": tot("generic", "model_calls", bad),
        "gen_bad_tokens": tot("generic", "tokens", bad),
        "loc_bad_calls": tot("localized", "model_calls", bad),
        "loc_bad_tokens": tot("localized", "tokens", bad),
        "drafts": drafts,
    }


def test_effects2_analysis_summary_matches_raw_recompute():
    if not CONTRAST.is_dir():
        pytest.skip("raw effects2_20261106 not present on this host")
    a = json.loads(ANALYSIS.read_text())
    r = _recompute()

    # 公平性（11-06 #2：兩臂實際起始檔 hash 必須一致）
    sd = a["checks"]["same_draft"]
    assert sd["all_same_draft"] is r["same_start"] is True
    assert sd["n_tasks"] == 14
    for t in sd["tasks"]:
        assert len(set(t["draft_sha256"])) == 1  # 每題兩臂同一 hash
    assert {t["draft"] for t in sd["tasks"]} == set(r["drafts"])

    # Q1：同草稿同預算，localized 多修好（tamper 不計成功）
    b = a["this_batch_bad9"]
    assert b["generic"]["pass_after"] == r["bad_generic"] == 7
    assert b["localized"]["pass_after"] == r["bad_localized"] == 9
    assert a["answers_1106_2"]["Q1_localized_fixes_more"]  # 必答在案
    assert r["tampered"] == 0

    # Q2：正確成果退步
    g = a["this_batch_good5"]
    assert g["generic"]["pass_after"] == r["good_generic"] == 5
    assert g["localized"]["pass_after"] == r["good_localized"] == 5
    assert g["generic"]["regressed_effective"] == []
    assert g["localized"]["regressed_effective"] == []

    # Q3：成本（raw usage、缺值不填 0）
    cb = b["generic"]["cost"]
    assert cb["api_model_calls"]["total"] == r["gen_bad_calls"] == 235
    assert cb["tokens"]["total"] == r["gen_bad_tokens"] == 5576588
    cl = b["localized"]["cost"]
    assert cl["api_model_calls"]["total"] == r["loc_bad_calls"] == 347
    assert cl["tokens"]["total"] == r["loc_bad_tokens"] == 9691033

    # 對昨日 d38d2eb2（11-06 #6：1753 排除、僅同 9 題集合可比）
    pa = a["cross_batch_same9set"]["per_arm"]
    assert pa["generic"]["before_pass_d38d2eb2"] == r["yest_generic"] == 7
    assert pa["generic"]["after_pass_this_batch"] == 7
    assert pa["localized"]["before_pass_d38d2eb2"] == r["yest_localized"] == 6
    assert pa["localized"]["after_pass_this_batch"] == 9
    assert "dabstep-1753" in a["cross_batch_same9set"]["note"]

    # 28 格逐格：source_tampered 全 false（raw 重算）
    assert all(c["source_tampered"] is False for c in a["cells"])
    assert len(a["cells"]) == 28
