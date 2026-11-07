"""dab_055-pi-C 下一切片選題的常設守衛（11-07 資深審查 P3：選題事實由 raw 釘住）。

審查 P3：下一最小切片必須選 effects2_20261106 中 generic 實際未修好、且可見內容
檢查能給出具體結構化反例的真實失敗草稿。本測試把 dab_055-pi-C 的對照事實（選題
六要素票 P20261107_0210-1 的「預期可展示改善」已在 raw 中成立的部分）由
~/dev/ops/effects2_20261106 獨立釘住，與 test_reqloop_effects2_analysis.py 互補：
該檔釘 bad9 聚合（9/9 vs 7/9），本檔釘逐題結構——同草稿 hash、baseline 雙臂
FAIL、generic 的 req_mean_cases_recomputed 未解（具體反例，非 crash/tamper）、
localized gap_closed 兩 claim PASS、獨立裁決與成本常數。防「下一切片前提與 raw
漂移」與空洞斷言。

裁決紀律（與 r1162 守衛同口徑）：裁決以 before_after.json after_this_rep 為準
（逐格 hidden_after 為 UNKNOWN，本地無權重跑，不計成功）；tamper 不計成功；
成本取 raw usage 實值、缺值不填 0；1753 不在此題集合（本批排除）。
raw 在 repo 外（1004 主機）；缺目錄 skip（不在本機的 CI 不得偽綠）。
"""
import json
import pathlib

import pytest

RAW = pathlib.Path("/home/user1/dev/ops/effects2_20261106")
CONTRAST = RAW / "contrast"
DRAFT = "dab_055-pi-C"


def _cell(arm: str):
    d = json.loads((CONTRAST / f"g2_result_{DRAFT}_{arm}.json").read_text())
    return d, [c for c in d["cells"] if c["draft"] == DRAFT][0]


def _ba_after(arm: str) -> dict:
    ba = json.loads((RAW / "before_after.json").read_text())
    return [e for e in ba["cells"] if e["draft"] == DRAFT and e["arm"] == arm][0][
        "after_this_rep"
    ]


def test_dab055_slice_contrast_pinned_from_raw():
    if not CONTRAST.is_dir():
        pytest.skip("raw effects2_20261106 not present on this host")

    dg, cg = _cell("generic")
    dl, cl = _cell("localized")

    # 公平性（11-06 #2：兩臂實際起始檔 hash 必須一致；同一凍結 manifest）
    assert cg["draft_sha256"] == cl["draft_sha256"]
    assert dg["manifest"]["sha256"] == dl["manifest"]["sha256"]
    assert cg["role"] == cl["role"] == "bad"

    # baseline：草稿是真實失敗（雙臂 before_hidden 皆 false、0/1）
    assert cg["before_hidden"]["pass"] is False
    assert cl["before_hidden"]["pass"] is False
    assert cg["before_hidden"]["n_correct"] == cl["before_hidden"]["n_correct"] == "0/1"

    # generic 實際未修好：內容檢查給具體結構化反例（非 crash、非 tamper）
    assert cg["source_tampered"] is False
    assert cg["after_readable_status"] == {
        "req_answer_kv": "PASS",
        "req_mean_cases_recomputed": "FAIL",
    }
    assert cg["fixed"] == ["req_answer_kv"]  # 只修回格式；重算值仍不符
    assert cg["unresolved"] == ["req_mean_cases_recomputed"]
    assert cg["regressed"] == []
    assert cg["stopped"] == "max_rounds"

    # localized 修好：兩 claim PASS、gap 閉合、無退步
    assert cl["source_tampered"] is False
    assert cl["final_readable_status"] == {
        "req_answer_kv": "PASS",
        "req_mean_cases_recomputed": "PASS",
    }
    assert sorted(cl["fixed"]) == ["req_answer_kv", "req_mean_cases_recomputed"]
    assert cl["unresolved"] == []
    assert cl["regressed"] == []
    assert cl["stopped"] == "gap_closed"

    # 獨立裁決（before_after.json 同口徑；逐格 hidden_after UNKNOWN 不計成功）
    bg, bl = _ba_after("generic"), _ba_after("localized")
    assert bg["independent_pass"] is False and bg["independent_status"] == "scored"
    assert bl["independent_pass"] is True and bl["independent_status"] == "scored"
    assert bg["source_tampered"] is False and bl["source_tampered"] is False

    # 成本常數（raw usage 實值；缺值不填 0）
    assert cg["cost"]["model_calls"] == 25
    assert cg["cost"]["tokens"] == 1451938
    assert cg["cost"]["wall_ms_total"] == 149433
    assert cl["cost"]["model_calls"] == 21
    assert cl["cost"]["tokens"] == 372043
    assert cl["cost"]["wall_ms_total"] == 67646
