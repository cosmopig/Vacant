"""vq-el4.4 item 2（run_eval.py --phase2，14 份真實草稿）離線測試。

不呼叫模型：以自組 RequirementSet＋小型 CSV 確定性地驅動 run_requirement_checks；
cell 集合推導只讀 effects2_20261106 的 before_after.json（非本批的 host 會 skip）。
"""

import json
import pathlib
import re
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "ops" / "reqloop" / "extract"))

from run_eval import (  # noqa: E402
    MAX_FALSE_GOOD,
    MIN_CATCH_BAD,
    RECOMPUTE_TYPES,
    build_phase2_prompt,
    derive_real14_cells,
    gate_pass,
    load_cell_request_text,
    phase2_extract_cell,
    task_data_files,
)
from vacant_network.reqloop.requirements import RequirementItem, RequirementSet  # noqa: E402

EFFECTS2 = pathlib.Path("~/dev/ops/effects2_20261106").expanduser()


def test_gate_thresholds_match_rloop_plan():
    """RLOOP_PLAN 第 91 行：抓錯 ≥ 5/9、冤枉 ≤ 1/5。"""
    assert MIN_CATCH_BAD == 5
    assert MAX_FALSE_GOOD == 1


def test_gate_pass_logic():
    assert gate_pass(5, 9, 1, 5) is True      # 恰好達標
    assert gate_pass(9, 9, 0, 5) is True      # 全抓、零冤枉
    assert gate_pass(6, 9, 1, 5) is True
    assert gate_pass(4, 9, 0, 5) is False     # 抓錯不足
    assert gate_pass(9, 9, 2, 5) is False     # 冤枉過多
    assert gate_pass(0, 9, 5, 5) is False     # 全漏、全冤枉


@pytest.mark.skipif(
    not (EFFECTS2 / "before_after.json").is_file(),
    reason="effects2_20261106 不在此 host",
)
def test_real14_cellset_from_effects2():
    cells = derive_real14_cells(EFFECTS2)
    assert len(cells) == 14
    roles = {c.role for c in cells}
    assert sum(1 for c in cells if c.role == "bad") == 9
    assert sum(1 for c in cells if c.role == "good") == 5
    assert not any("1753" in c.cell for c in cells)   # 本批排除 1753
    for c in cells:
        assert c.task_dir.is_dir(), c.cell
        assert c.draft_dir.is_dir(), c.cell


def test_derive_missing_base_fails_closed(tmp_path):
    with pytest.raises(FileNotFoundError):
        derive_real14_cells(tmp_path / "no_such_base")


def test_derive_cells_missing_in_snapshot_fails_closed(tmp_path):
    """before_after.json 有 cell、snapshot 缺 task/draft → fail-closed，不准靜默少算。"""
    (tmp_path / "before_after.json").write_text(json.dumps({
        "cells": [{
            "draft": "fake-001-pi-C", "arm": "generic",
            "before_d38d2eb2": {"policy30_2r": {"fixed": ["x"], "unresolved": []}},
        }],
    }), encoding="utf-8")
    with pytest.raises(RuntimeError, match="fake-001-pi-C"):
        derive_real14_cells(tmp_path)


def _mk_task(tmp_path: pathlib.Path) -> pathlib.Path:
    """最小 G2 形任務：data/t.csv（M1,M1,M2,M3）；答案 = 去重商戶數。"""
    task = tmp_path / "task"
    (task / "data").mkdir(parents=True)
    (task / "data" / "t.csv").write_text("merchant_id\nM1\nM1\nM2\nM3\n", encoding="utf-8")
    return task


def _reqset() -> RequirementSet:
    item = RequirementItem(
        id="R1", quote="How many unique merchants", deliverable="answer.txt",
        verifier="plain_recomputed",
        params={"data_file": "data/t.csv",
                "recompute": {"type": "unique_count", "col": "merchant_id"}},
    )
    return RequirementSet("t", [item])


def test_phase2_verdict_bad_caught_good_clean(tmp_path):
    """壞草稿（值錯）→ 至少一個 FAIL；好草稿（值對）→ 無 FAIL。"""
    from vacant_network.reqloop.checks import run_requirement_checks
    task = _mk_task(tmp_path)
    good = tmp_path / "good"; good.mkdir()
    (good / "answer.txt").write_text("3\n", encoding="utf-8")
    bad = tmp_path / "bad"; bad.mkdir()
    (bad / "answer.txt").write_text("5\n", encoding="utf-8")
    req = _reqset()
    assert any(r.status == "FAIL" for r in run_requirement_checks(task, req, bad))
    assert not any(r.status == "FAIL" for r in run_requirement_checks(task, req, good))


def test_phase2_missing_answer_file_is_fail_for_bad_draft(tmp_path):
    """答案檔不存在（dab_039 形）→ FAIL（missing），不是 UNKNOWN。"""
    from vacant_network.reqloop.checks import run_requirement_checks
    task = _mk_task(tmp_path)
    empty = tmp_path / "empty"; empty.mkdir()
    req = RequirementSet("t", [RequirementItem(
        id="R0", quote="answer.txt", deliverable="answer.txt",
        verifier="plain_recomputed",
        params={"data_file": "data/t.csv",
                "recompute": {"type": "unique_count", "col": "merchant_id"}})])
    assert any(r.status == "FAIL" for r in run_requirement_checks(task, req, empty))


def test_phase2_prompt_carries_recompute_vocabulary():
    """prompt 必帶全部受支援的 recompute 型別（防語法悄悄漏失）。"""
    p = build_phase2_prompt(
        "question text", ["data/t.csv"], {"data/t.csv": "merchant_id\nM1\n"})
    for t in RECOMPUTE_TYPES:
        assert t in p, t
    assert "data/t.csv" in p
    # 資料檔名必須是相對任務目錄的真實檔名（checker 以 task_dir/data_rel 解析）
    assert "data/t.csv" in p


def test_phase2_prompt_recompute_types_exhaustive_vs_checks_dispatch():
    """RECOMPUTE_TYPES 必須與 checks.py 實際 dispatch 的型別一致（雙向）。"""
    import vacant_network.reqloop.checks as checks
    src = pathlib.Path(checks.__file__).read_text(encoding="utf-8")
    dispatched = set(re.findall(r'rtype == "(\w+)"', src))
    # kv_recomputed 與 plain_recomputed 合起來的受支援型別
    assert set(RECOMPUTE_TYPES) <= dispatched, set(RECOMPUTE_TYPES) - dispatched
    # dispatch 出來的型別都要在語法表裡（不讓模型自創、也不讓文檔漏型別）
    assert dispatched <= set(RECOMPUTE_TYPES), dispatched - set(RECOMPUTE_TYPES)


def test_task_data_files_prefers_data_subdir(tmp_path):
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "b.csv").write_text("a\n1\n", encoding="utf-8")
    (tmp_path / "data" / "a.csv").write_text("a\n1\n", encoding="utf-8")
    (tmp_path / "data" / "x.json").write_text("[]", encoding="utf-8")
    (tmp_path / "top.csv").write_text("a\n1\n", encoding="utf-8")
    files = task_data_files(tmp_path)
    names = [p.name for p in files]
    assert names[:2] == ["a.csv", "b.csv"]     # data/ 優先、字典序
    assert "x.json" in names
    assert "top.csv" not in names


def test_load_cell_request_text_prefers_request_md(tmp_path):
    task = tmp_path / "task"; task.mkdir()
    (task / "request.md").write_text("original request", encoding="utf-8")
    real14 = tmp_path / "real14"
    assert load_cell_request_text(task, "dabstep-10", real14) == "original request"


def test_load_cell_request_text_falls_back_to_real14(tmp_path):
    task = tmp_path / "task"; task.mkdir()
    real14 = tmp_path / "real14"
    real14.mkdir(parents=True, exist_ok=True)
    (real14 / "dabstep-10.request.md").write_text("reconstructed question", encoding="utf-8")
    assert load_cell_request_text(task, "dabstep-10", real14) == "reconstructed question"


def test_load_cell_request_text_missing_fails_closed(tmp_path):
    task = tmp_path / "task"; task.mkdir()
    with pytest.raises(FileNotFoundError):
        load_cell_request_text(task, "dabstep-99", tmp_path / "real14")


class _ExplodingClient:
    """若被呼叫即失敗——驗證既有 out 檔存在時不得再叫模型。"""

    def complete(self, prompt: str) -> str:
        raise AssertionError("既有 out 檔存在時不準再呼叫模型")


def test_phase2_extract_cell_reuses_existing_out(tmp_path):
    from run_eval import Real14Cell
    c = Real14Cell(cell="fake-001-pi-C", role="bad",
                   task_dir=tmp_path / "t", draft_dir=tmp_path / "d")
    (tmp_path / "t").mkdir(); (tmp_path / "d").mkdir()
    out_path = tmp_path / "out" / "real14" / "fake-001-pi-C.glm53.json"
    req = _reqset()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(req.to_dict()), encoding="utf-8")
    got = phase2_extract_cell(c, "user text", [], {}, "glm53",
                              _ExplodingClient(), out_path)
    assert got.items[0].id == "R1"


def test_load_cell_request_text_appends_public_contract_md(tmp_path):
    """argon 20261107_1242：real14 首跑 prompt 漏了 contract.md（公開交付規格：寫到
    answer.txt、@name[value] 格式），擷取模型只好猜交付檔名（answer、@x[y]、
    /app/answer.txt），草稿明明有 answer.txt 卻每條都判「答案檔不存在」FAIL——
    9/9 抓錯與 4/5 冤枉都是這個假象。contract.md 是 agent 拿到的公開任務文字，必須進原文。"""
    task = tmp_path / "task"; task.mkdir()
    (task / "request.md").write_text("original request", encoding="utf-8")
    (task / "contract.md").write_text("Write your final answer to `answer.txt`.", encoding="utf-8")
    got = load_cell_request_text(task, "dab_001", tmp_path / "real14")
    assert got.startswith("original request")
    assert "Write your final answer to `answer.txt`." in got


def test_load_cell_request_text_real14_fallback_also_gets_contract(tmp_path):
    task = tmp_path / "task"; task.mkdir()
    (task / "contract.md").write_text("Write ONLY the final answer to answer.txt", encoding="utf-8")
    real14 = tmp_path / "real14"; real14.mkdir()
    (real14 / "dabstep-10.request.md").write_text("reconstructed question", encoding="utf-8")
    got = load_cell_request_text(task, "dabstep-10", real14)
    assert got.startswith("reconstructed question") and "answer.txt" in got


class _CountingClient:
    def __init__(self, response: str) -> None:
        self.response = response
        self.calls = 0

    def complete(self, prompt: str) -> str:
        self.calls += 1
        return self.response


_RAW_ONE = json.dumps([{
    "id": "R1", "quote": "How many unique merchants", "deliverable": "answer",
    "verifier": "plain_recomputed",
    "params": {"data_file": "data/t.csv",
               "recompute": {"type": "unique_count", "col": "merchant_id"}}}])


def test_phase2_extract_cell_pins_prompt_and_reextracts_when_prompt_changes(tmp_path):
    """argon 20261107_1248：out 檔記 prompt_sha256；原文改了（補 contract.md）不得
    靜默沿用舊 prompt 的擷取結果；同 prompt 重跑 0 呼叫，且從 raw_output 以目前規則重建。"""
    from run_eval import Real14Cell
    c = Real14Cell(cell="fake-002-pi-C", role="bad",
                   task_dir=tmp_path / "t", draft_dir=tmp_path / "d")
    out_path = tmp_path / "out" / "fake-002-pi-C.glm53.json"
    cl = _CountingClient(_RAW_ONE)
    t1 = "How many unique merchants are there?"
    r1 = phase2_extract_cell(c, t1, [], {}, "glm53", cl, out_path)
    doc = json.loads(out_path.read_text(encoding="utf-8"))
    assert cl.calls == 1 and doc["raw_output"] == _RAW_ONE
    assert len(doc["provenance"]["prompt_sha256"]) == 64
    # 原文沒點名 "answer" 這個檔 → 猜名 → unverified（不是 FAIL 來源）
    assert r1.items[0].unverified

    # 同 prompt：0 呼叫
    r1b = phase2_extract_cell(c, t1, [], {}, "glm53", _ExplodingClient(), out_path)
    assert [i.id for i in r1b.items] == ["R1"]

    # 原文補上公開交付規格 → prompt 變了 → 重新擷取
    t2 = t1 + "\n\nWrite your final answer to `answer.txt`."
    phase2_extract_cell(c, t2, [], {}, "glm53", cl, out_path)
    assert cl.calls == 2
