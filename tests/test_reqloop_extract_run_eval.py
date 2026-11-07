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


def _reqset(task_id: str = "t") -> RequirementSet:
    item = RequirementItem(
        id="R1", quote="How many unique merchants", deliverable="answer.txt",
        verifier="plain_recomputed",
        params={"data_file": "data/t.csv",
                "recompute": {"type": "unique_count", "col": "merchant_id"}},
    )
    return RequirementSet(task_id, [item])


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


# ── phase3（vq-el4.5）：9 錯＋自動擷取需求＋localized 修復＋獨立 scorer ──────────

from run_eval import (  # noqa: E402
    Real14Cell,
    load_phase3_sources,
    phase3_cell,
    prepare_phase3_task,
    run_phase3,
)


def _mk_base(tmp_path: pathlib.Path) -> pathlib.Path:
    """最小 effects2 形 base：fake-001（bad、答案錯）＋ fake-002（good、答案對），
    快照 task/draft＋effect_manifest source。唯一商戶數＝3。"""
    base = tmp_path / "base"
    (base / "snapshot" / "ops" / "reqloop" / "g2").mkdir(parents=True)
    (base / "before_after.json").write_text(json.dumps({
        "cells": [
            {"draft": "fake-001-pi-C", "arm": "generic",
             "before_d38d2eb2": {"policy30_2r": {"fixed": ["x"], "unresolved": []}}},
            {"draft": "fake-002-pi-C", "arm": "generic",
             "before_d38d2eb2": {"policy30_2r": {"fixed": [], "unresolved": []}}},
        ]}))
    g2 = base / "snapshot" / "ops" / "reqloop" / "g2" / "smoke"
    for name, ans in (("fake-001", "@m[1]\n"), ("fake-002", "@m[3]\n")):
        cell = f"{name}-pi-C"
        task = g2 / cell / "task"
        (task / "data").mkdir(parents=True)
        (g2 / cell / "draft").mkdir(parents=True)
        (task / "request.md").write_text("How many unique merchants?", encoding="utf-8")
        (task / "contract.md").write_text("Write your final answer to `answer.txt`.", encoding="utf-8")
        (task / "data" / "t.csv").write_text("merchant_id\nM1\nM1\nM2\nM3\n", encoding="utf-8")
        (task / "requirements.json").write_text(
            json.dumps(_reqset().to_dict()), encoding="utf-8")  # 手寫版：phase3 不得帶入
        (g2 / cell / "draft" / "answer.txt").write_text(ans, encoding="utf-8")
    (g2.parent / "effect_manifest.json").write_text(json.dumps({
        "model": {"provider": "p", "model": "m"},
        "drafts": [
            {"name": "fake-001-pi-C", "source": {"run": "r1", "cell": "c1", "score": {"pass": False}}},
            {"name": "fake-002-pi-C", "source": {"run": "r1", "cell": "c2", "score": {"pass": True}}},
        ]}))
    return base


def _fake_build():
    from vacant_network.adapters.run import Launch
    def build(prompt: str, ws: pathlib.Path):
        return Launch(argv=["true"], note="phase3-test-fake")
    return build


def _fake_agent(ws_files: dict[str, str] | None):
    from vacant_network.adapters.run import Launch

    def run(launch: Launch, *, workspace: pathlib.Path, timeout_s: float,
            log_dir: pathlib.Path) -> dict:
        for name, text in (ws_files or {}).items():
            p = pathlib.Path(workspace) / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text, encoding="utf-8")
        log_dir.mkdir(parents=True, exist_ok=True)
        (log_dir / "agent_stdout.log").write_text("{}", encoding="utf-8")
        (log_dir / "agent_stderr.log").write_text("", encoding="utf-8")
        return {"rc": 0, "timed_out": False, "wall_ms": 100, "spawn_error": None,
                "stdout_log": str(log_dir / "agent_stdout.log"),
                "stderr_log": str(log_dir / "agent_stderr.log")}
    return run


def test_load_phase3_sources_from_manifest(tmp_path):
    base = _mk_base(tmp_path)
    src = load_phase3_sources(base)
    assert src["fake-001-pi-C"] == {"run": "r1", "cell": "c1", "before_pass": False}
    assert src["fake-002-pi-C"]["before_pass"] is True


def test_load_phase3_sources_missing_manifest_fails_closed(tmp_path):
    import pytest
    with pytest.raises(FileNotFoundError):
        load_phase3_sources(tmp_path)


def test_prepare_phase3_task_uses_extracted_not_handwritten(tmp_path):
    """phase3 任務目錄的 requirements.json＝自動擷取版；快照（task_dir）不被修改。"""
    cell = Real14Cell(cell="fake-001-pi-C", role="bad",
                      task_dir=tmp_path / "task", draft_dir=tmp_path / "draft")
    (cell.task_dir / "data").mkdir(parents=True)
    (cell.task_dir / "request.md").write_text("req", encoding="utf-8")
    (cell.task_dir / "contract.md").write_text("contract", encoding="utf-8")
    (cell.task_dir / "data" / "t.csv").write_text("merchant_id\nM1\n", encoding="utf-8")
    (cell.task_dir / "requirements.json").write_text("HANDWRITTEN-MARKER", encoding="utf-8")
    extracted = RequirementSet("fake-001-pi-C", [
        RequirementItem(id="X1", quote="unique", deliverable="answer.txt",
                        verifier="plain_recomputed",
                        params={"data_file": "data/t.csv",
                               "recompute": {"type": "unique_count", "col": "merchant_id"}}),
    ])
    dest = prepare_phase3_task(cell, extracted, tmp_path / "phase3" / "tasks" / "fake-001-pi-C")
    got = json.loads((dest / "requirements.json").read_text(encoding="utf-8"))
    assert got["items"][0]["id"] == "X1"
    assert "HANDWRITTEN-MARKER" not in (dest / "requirements.json").read_text(encoding="utf-8")
    assert (dest / "request.md").is_file() and (dest / "contract.md").is_file()
    assert (dest / "data" / "t.csv").is_file()
    # 快照未被修改
    assert (cell.task_dir / "requirements.json").read_text(encoding="utf-8") == "HANDWRITTEN-MARKER"


def test_phase3_cell_fixed_bad_draft(tmp_path):
    """bad 草稿＋fake 修復（寫對答案）＋scorer pass=True → fixed；成本透傳。"""
    base = _mk_base(tmp_path)
    cells = {c.cell: c for c in derive_real14_cells(base)}
    cell = cells["fake-001-pi-C"]
    reqs = _reqset("fake-001-pi-C")
    src = load_phase3_sources(base)["fake-001-pi-C"]
    scorer = lambda source, ws, deliv: {"pass": True, "status": "scored", "rc": 0}
    row = phase3_cell(cell, reqs, src, tmp_path / "out",
                      build=_fake_build(), run=_fake_agent({"answer.txt": "@m[3]\n"}),
                      scorer=scorer)
    assert row["verdict"] == "fixed"
    assert row["before"] is False and row["after"]["pass"] is True
    assert row["cost"]["repair_sessions"] is not None
    assert row["deliverables"] == ["answer.txt"]


def test_phase3_cell_tampered_rejected_even_if_scorer_passes(tmp_path):
    """修復若改來源（workspace 的 data/t.csv）→ source_tampered ⇒ rejected，不得翻 fixed。"""
    base = _mk_base(tmp_path)
    cells = {c.cell: c for c in derive_real14_cells(base)}
    cell = cells["fake-001-pi-C"]
    reqs = _reqset("fake-001-pi-C")
    src = load_phase3_sources(base)["fake-001-pi-C"]
    scorer = lambda source, ws, deliv: {"pass": True, "status": "scored", "rc": 0}
    row = phase3_cell(cell, reqs, src, tmp_path / "out",
                      build=_fake_build(),
                      run=_fake_agent({"answer.txt": "@m[3]\n",
                                       "data/t.csv": "merchant_id\nM1\nM1\nM2\n"}),
                      scorer=scorer)
    assert row["source_tampered"] is True
    assert row["verdict"] == "rejected"


def test_phase3_cell_unresolved_when_scorer_unknown(tmp_path):
    """scorer UNKNOWN（pass=None）→ unresolved；FAIL→UNKNOWN 不算修好。"""
    base = _mk_base(tmp_path)
    cells = {c.cell: c for c in derive_real14_cells(base)}
    cell = cells["fake-001-pi-C"]
    reqs = _reqset("fake-001-pi-C")
    src = load_phase3_sources(base)["fake-001-pi-C"]
    scorer = lambda source, ws, deliv: {"pass": None, "status": "UNKNOWN", "rc": 1}
    row = phase3_cell(cell, reqs, src, tmp_path / "out",
                      build=_fake_build(), run=_fake_agent({"answer.txt": "@m[3]\n"}),
                      scorer=scorer)
    assert row["verdict"] == "unresolved"
    assert row["after"]["pass"] is None


def test_phase3_cell_scorer_exception_is_unknown(tmp_path):
    """scorer 例外 → UNKNOWN（fail-closed），不得冒稱 pass、不拖垮全批。"""
    base = _mk_base(tmp_path)
    cells = {c.cell: c for c in derive_real14_cells(base)}
    cell = cells["fake-001-pi-C"]
    reqs = _reqset("fake-001-pi-C")
    src = load_phase3_sources(base)["fake-001-pi-C"]

    def boom(source, ws, deliv):
        raise RuntimeError("lab scorer down")
    row = phase3_cell(cell, reqs, src, tmp_path / "out",
                      build=_fake_build(), run=_fake_agent(None), scorer=boom)
    assert row["verdict"] == "unresolved"
    assert "SCORER_ERROR" in row["after"]["status"]


def test_run_phase3_bad_and_good_verdicts_freeze_and_progress(tmp_path):
    """run_phase3：9 錯（這裡 1 錯＋1 好）→ fixed／held 兩行；freeze.json＋progress.json 完整。"""
    base = _mk_base(tmp_path)
    req_dir = tmp_path / "req"
    req_dir.mkdir()
    for cell in ("fake-001-pi-C", "fake-002-pi-C"):
        (req_dir / f"{cell}.glm53.json").write_text(
            json.dumps(_reqset(task_id=cell).to_dict()), encoding="utf-8")

    def scorer(source, ws, deliv):
        # fake-001（bad、答案被修對）→ pass；fake-002（good）→ pass
        return {"pass": True, "status": "scored", "rc": 0}

    rc = run_phase3(base=base, include_good=True,
                    build=_fake_build(), run=_fake_agent({"answer.txt": "@m[3]\n"}),
                    scorer=scorer, req_dir=req_dir, out_root=tmp_path / "out",
                    json_out=tmp_path / "phase3.json")
    doc = json.loads((tmp_path / "phase3.json").read_text(encoding="utf-8"))
    assert rc == 0
    by_cell = {r["cell"]: r for r in doc["rows"]}
    assert by_cell["fake-001-pi-C"]["verdict"] == "fixed"
    assert by_cell["fake-002-pi-C"]["verdict"] == "held"
    freeze = json.loads((tmp_path / "out" / "freeze.json").read_text(encoding="utf-8"))
    assert len(freeze["cells"]) == 2
    assert all(c["req_sha256"] for c in freeze["cells"])
    assert all(c["source"]["run"] == "r1" for c in freeze["cells"])
    prog = json.loads((tmp_path / "out" / "progress.json").read_text(encoding="utf-8"))
    assert prog["complete"] is True and len(prog["rows"]) == 2
    # 成本缺值＝UNKNOWN（None）：允許 None，絕不填 0（None 與 0 必須可區分）
    for v in doc["cost"].values():
        assert v is None or (isinstance(v, (int, float)) and v >= 0)


def test_run_phase3_missing_extraction_fails_closed(tmp_path):
    """缺擷取結果 → ERROR 行、rc=2（不拿缺的當通過）。"""
    base = _mk_base(tmp_path)
    req_dir = tmp_path / "req"
    req_dir.mkdir()
    (req_dir / "fake-001-pi-C.glm53.json").write_text(
        json.dumps(_reqset(task_id="fake-001-pi-C").to_dict()), encoding="utf-8")
    rc = run_phase3(base=base, include_good=True,
                    build=_fake_build(), run=_fake_agent(None),
                    scorer=lambda s, w, d: {"pass": True, "status": "scored", "rc": 0},
                    req_dir=req_dir, out_root=tmp_path / "out")
    assert rc == 2
    prog = json.loads((tmp_path / "out" / "progress.json").read_text(encoding="utf-8"))
    by_cell = {r["cell"]: r for r in prog["rows"]}
    assert by_cell["fake-002-pi-C"]["status"] == "ERROR"


def test_run_phase3_resumes_from_existing_progress(tmp_path):
    """progress.json 已有裁決 → 第二輪不重複呼叫 build/run，結果保留（斷點接續）。"""
    base = _mk_base(tmp_path)
    req_dir = tmp_path / "req"
    req_dir.mkdir()
    for cell in ("fake-001-pi-C", "fake-002-pi-C"):
        (req_dir / f"{cell}.glm53.json").write_text(
            json.dumps(_reqset(task_id=cell).to_dict()), encoding="utf-8")
    scorer = lambda s, w, d: {"pass": True, "status": "scored", "rc": 0}
    out_root = tmp_path / "out"
    calls = {"build": 0, "run": 0}

    def counting_build(prompt: str, ws: pathlib.Path):
        calls["build"] += 1
        return _fake_build()(prompt, ws)

    def counting_run(launch, *, workspace: pathlib.Path, timeout_s: float,
                     log_dir: pathlib.Path) -> dict:
        calls["run"] += 1
        return _fake_agent({"answer.txt": "@m[3]\n"})(
            launch, workspace=workspace, timeout_s=timeout_s, log_dir=log_dir)

    rc1 = run_phase3(base=base, include_good=True, build=counting_build,
                     run=counting_run, scorer=scorer, req_dir=req_dir, out_root=out_root)
    assert rc1 == 0 and calls["build"] >= 1 and calls["run"] >= 1
    prog1 = json.loads((out_root / "progress.json").read_text(encoding="utf-8"))
    first_verdicts = {r["cell"]: r["verdict"] for r in prog1["rows"]}
    assert first_verdicts == {"fake-001-pi-C": "fixed", "fake-002-pi-C": "held"}

    def boom(*a, **k):
        raise AssertionError("接續時不準再呼叫 build/run")

    calls["build"] = calls["run"] = 0
    rc2 = run_phase3(base=base, include_good=True, build=boom, run=boom,
                     scorer=scorer, req_dir=req_dir, out_root=out_root,
                     json_out=tmp_path / "phase3.json")
    assert rc2 == 0
    assert calls["build"] == 0 and calls["run"] == 0     # 沒有重複執行
    doc = json.loads((tmp_path / "phase3.json").read_text(encoding="utf-8"))
    second_verdicts = {r["cell"]: r["verdict"] for r in doc["rows"]}
    assert second_verdicts == first_verdicts             # 結果保留
    assert {r["cell"]: r for r in doc["rows"]} == {r["cell"]: r for r in prog1["rows"]}
    assert doc["fixed"] == 1 and doc["held"] == 1 and doc["errors"] == 0


# ── 多模型對照（vq-el4.6）：--models 表格＋JSON ─────────────────────────────

def _mk_g1_multi(tmp_path: pathlib.Path) -> tuple[pathlib.Path, pathlib.Path]:
    """2 題 G1 形（各 1 good＋1 bad）；答案＝去重商戶數 3。

    m1 擷取＝有效重算需求（bad 抓出、good VERIFIED）；
    m2 擷取＝unverified 條目（全 UNKNOWN、抓不出、不冤枉）；m3 無擷取結果（fail-closed）。
    """
    good_req = _reqset("t")
    weak_req = RequirementSet("t", [RequirementItem(
        id="R2", quote="How many unique merchants", deliverable="answer.txt",
        verifier="plain_recomputed", params={}, unverified=True)])
    g1 = tmp_path / "g1"
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    for tname in ("ta", "tb"):
        t = g1 / tname
        (t / "data").mkdir(parents=True)
        (t / "data" / "t.csv").write_text("merchant_id\nM1\nM1\nM2\nM3\n", encoding="utf-8")
        (t / "requirements.json").write_text(json.dumps(good_req.to_dict()), encoding="utf-8")
        (t / "good").mkdir()
        (t / "good" / "answer.txt").write_text("3\n", encoding="utf-8")
        (t / "bad_wrong").mkdir()
        (t / "bad_wrong" / "answer.txt").write_text("5\n", encoding="utf-8")
        (out_dir / f"{tname}.m1.json").write_text(json.dumps(good_req.to_dict()), encoding="utf-8")
        (out_dir / f"{tname}.m2.json").write_text(json.dumps(weak_req.to_dict()), encoding="utf-8")
    return g1, out_dir


def test_run_eval_multi_model_comparison(tmp_path, capsys):
    """--models m1,m2：對照表（Model/Bad Caught/Caught %/Good FP/Total Good/Calls/Tokens）
    ＋JSON 的 models 字典；一 PASS 一 FAIL → rc 20；單模型全 PASS → rc 0；缺擷取 → rc 2。"""
    from run_eval import main
    g1, out_dir = _mk_g1_multi(tmp_path)
    vc = tmp_path / "vibe_calls.jsonl"
    vc.write_text("\n".join(
        json.dumps({"model": "m1", "rc": 0, "purpose": f"g1 {t}", "total_tokens": tok})
        for t, tok in (("ta", 100), ("tb", 200))) + "\n", encoding="utf-8")
    jout = tmp_path / "compare.json"

    rc = main(["--models", "m1,m2", "--g1", str(g1), "--out-dir", str(out_dir),
               "--vibe-calls", str(vc), "--json", str(jout)])
    out = capsys.readouterr().out
    assert rc == 20                                   # m1 PASS、m2 FAIL → 非全過
    row1 = next(l for l in out.splitlines() if l.startswith("m1"))
    row2 = next(l for l in out.splitlines() if l.startswith("m2"))
    for col in ("Model", "Bad Caught", "Caught %", "Good FP", "Total Good", "Calls", "Tokens"):
        assert col in out, col
    assert "2/2" in row1 and "100.0%" in row1 and "300" in row1    # m1：全抓、有成本
    assert "0/2" in row2 and "UNKNOWN" in row2                      # m2：0 抓、成本缺值
    doc = json.loads(jout.read_text(encoding="utf-8"))
    assert set(doc["models"]) == {"m1", "m2"}
    m1, m2 = doc["models"]["m1"], doc["models"]["m2"]
    assert (m1["bad_caught"], m1["total_bad"], m1["good_fp"], m1["total_good"]) == (2, 2, 0, 2)
    assert m1["calls"] == 2 and m1["tokens"] == 300 and m1["gate"] == "PASS"
    assert m2["bad_caught"] == 0 and m2["good_fp"] == 0
    assert m2["calls"] is None and m2["tokens"] is None             # 缺值＝UNKNOWN，不填 0
    assert m2["gate"] == "FAIL"

    assert main(["--models", "m1", "--g1", str(g1), "--out-dir", str(out_dir),
                 "--vibe-calls", str(vc)]) == 0                     # 單模型全 PASS → 0
    assert main(["--models", "m3", "--g1", str(g1), "--out-dir", str(out_dir),
                 "--vibe-calls", str(vc)]) == 2                     # 缺擷取 → fail-closed


def test_run_eval_multi_model_extraction_failure_labeled(tmp_path, capsys):
    """擷取失敗格（report.extract_error／parse_error，r1197：glm53flash 4 題 deadline／
    token_limit、deepseek41 2 題 turn_limit）：
    - 計為未抓出（fail-closed），但對照表與 JSON 必須點名該題與原因——不得讀成「模型沒抓出」；
    - 任一題擷取失敗 → 門禁不得 PASS（擷取不完整），即使抓錯率仍達標。
    """
    from run_eval import main
    g1, out_dir = _mk_g1_multi(tmp_path)
    good = RequirementSet.load(out_dir / "ta.m1.json")
    err = "ExtractError: glm rc=4: deadline"
    failed_doc = {"task_id": "ta", "items": [],
                  "report": {"parse_error": None, "extract_error": err,
                             "kept": [], "discarded": [], "unverified": []}}
    (out_dir / "ta.m4.json").write_text(json.dumps(failed_doc, ensure_ascii=False), encoding="utf-8")
    (out_dir / "tb.m4.json").write_text(json.dumps(good.to_dict()), encoding="utf-8")
    vc = tmp_path / "vc_m4.jsonl"
    vc.write_text("", encoding="utf-8")
    jout = tmp_path / "c4.json"

    rc = main(["--models", "m4", "--g1", str(g1), "--out-dir", str(out_dir),
               "--vibe-calls", str(vc), "--json", str(jout)])
    out = capsys.readouterr().out
    assert rc == 20                                    # 擷取失敗 → 門禁 FAIL（非 PASS）
    assert "ta" in out and "deadline" in out            # 表格必須點名失敗題與原因
    doc = json.loads(jout.read_text(encoding="utf-8"))
    m4 = doc["models"]["m4"]
    assert m4["gate"] == "FAIL"
    assert m4["extract_failed"] == {"ta": err}
    assert (m4["bad_caught"], m4["total_bad"]) == (1, 2)   # 失敗題計未抓出（fail-closed）
    assert m4["good_fp"] == 0                            # 失敗題的 good＝UNKNOWN，不冤枉

    # 全部擷取成功時 extract_failed 為空（不影響既有 PASS 口徑）
    assert main(["--models", "m1", "--g1", str(g1), "--out-dir", str(out_dir),
                 "--vibe-calls", str(vc)]) == 0
    capsys.readouterr()
    main(["--models", "m1", "--g1", str(g1), "--out-dir", str(out_dir),
          "--vibe-calls", str(vc), "--json", str(jout)])
    doc1 = json.loads(jout.read_text(encoding="utf-8"))
    assert doc1["models"]["m1"]["extract_failed"] == {}


def test_eval_g1_compare_3m_baseline_contract():
    """vq-el4.6 結案基準（2026-11-07 裁決）：3 模型對照表已鎖定。

    官方證據 out/eval_g1_compare_3m.json：恰為 3 模型（gemma 為 1004 本地端點、
    不繞 glm 直呼 vibe、不入表）；glm53 達標（39/39 100% FP0 門禁 PASS）；另兩模型
    FAIL（G1 開發樣本單 rep，不宣稱模型較好）。缺值不填 0——缺成本即 None。
    """
    out = (pathlib.Path(__file__).resolve().parents[1] / "ops" / "reqloop" / "extract"
           / "out" / "eval_g1_compare_3m.json")
    assert out.is_file(), f"結案基準證據缺失: {out}"
    doc = json.loads(out.read_text(encoding="utf-8"))
    assert set(doc["models"]) == {"glm53", "glm53flash", "deepseek41"}
    m = doc["models"]["glm53"]
    assert m["bad_caught"] == 39
    assert m["caught_pct"] == 100.0
    assert m["good_fp"] == 0
    assert m["gate"] == "PASS"
    assert doc["models"]["glm53flash"]["gate"] == "FAIL"
    assert doc["models"]["deepseek41"]["gate"] == "FAIL"
