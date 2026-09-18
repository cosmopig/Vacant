"""`ops/gain/r530/judge_r530.py` 的紅線（R530 質化盲評管線）。

這支在架構裡承重什麼：盲評管線改壞了**不會噴錯**——它會照樣吐出一份四維分數，
而「評審其實看到了臂名」與「評審沒看到」在那份 JSON 裡長得一模一樣。
所以每一種壞法都要有一條跑得到的紅線：

  1. `--selftest` 的手算對照全過（三個係數都不是拿實作驗自己）；
  2. `--mutation-check` 的九種突變**全部**要被抓到；
  3. **去識別化是負控驗過的**：刻意帶 `A-GATE`／`seed`／`receipt` 字樣的工作區
     必須整包退出，而且**送出去的 prompt 裡一個字都不准有**；
  4. `infra_void`／`parse_void` 不准塌成分數（那會讓「沒量到」變成「量到低分」）；
  5. 預註冊指名的仲裁欄位每一個都要存在（`.get()` 會安靜地回 None，
     然後被讀成「量到 0」）。
"""

from __future__ import annotations

import json
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ops.gain.r530.judge_r530 import (  # noqa: E402
    DEFAULT_RUBRIC, DIMS, FROZEN_LEAK_TOKENS, JUDGE_PROMPT_FOOTER,
    JUDGE_PROMPT_HEADER, JUDGE_SYSTEM, NEVER_EXCUSABLE, Cell, Grader, _leak_hits,
    build_argparser, deidentify, krippendorff_alpha_ordinal,
    load_bank, load_cells, main, make_fake_run, median_quartiles, mutation_check,
    parse_scores, quadratic_weighted_kappa, resolve_graders, run_controls,
    run_judging, sample_id_for, score_one, selftest, spearman,
)
from ops.gain.brain_cline import InfraVoid  # noqa: E402
from vacant.memory import KS1Violation, assert_ks1_clean  # noqa: E402

PREREG = ROOT / "decisions/DECISION_20260913_R530_OPEN_GOAL_WITH_WITHOUT_VACANT_PREREG.md"

#: 送出去的 prompt 裡**一個字都不准**出現的字樣（Fable 2026-09-13 指名的那五個
#: ＋題目識別）。這一條是本檔最重要的紅線：它擋的不是當機，是「盲評其實沒有盲」。
FORBIDDEN_IN_PROMPT = ("A-SOLO", "A-CONF", "A-GATE", "seed", "receipt",
                       ".vacant", "logbook", "attempt", "fw_01", "fw_02", "fw_03",
                       "fake-s1", "fake-s2")


@pytest.fixture(scope="module")
def fake(tmp_path_factory):
    root = tmp_path_factory.mktemp("r530fake")
    bank_dir, run_dir = make_fake_run(root)
    return {"root": root, "bank_dir": bank_dir, "run_dir": run_dir,
            "bank": load_bank(bank_dir)}


def _args(**kw):
    ap = build_argparser()
    ns = ap.parse_args([])
    for k, v in kw.items():
        setattr(ns, k, v)
    return ns


# ── 1. 手算對照與突變 ───────────────────────────────────────────────────
def test_selftest_passes():
    assert selftest(verbose=False) == 0


def test_every_mutation_is_caught():
    """抓不到的突變＝那條紅線其實不存在，而它會安靜地改掉這一份質化結論。"""
    assert mutation_check(verbose=False) == 0


def test_kappa_and_alpha_are_undefined_not_zero_when_graders_are_constant():
    """P-W12 事前預測評審近乎常數函數 ⇒ 這條路是預期會走到的，不是例外。

    回 0.0 會被讀成「一致性等於零」；那與「沒有定義」是兩件事。
    """
    assert quadratic_weighted_kappa([4] * 8, [4] * 8)["kappa"] is None
    assert krippendorff_alpha_ordinal([(4, 4)] * 8)["alpha"] is None
    assert spearman([4] * 8, [1, 2, 3, 4, 5, 1, 2, 3])["rho"] is None


def test_kappa_uses_the_fixed_1_to_5_category_set():
    """類別集合隨資料浮動 ⇒ 不同維度的 kappa 不能並排看。"""
    r = quadratic_weighted_kappa([3, 4, 3, 4], [4, 3, 4, 3])
    assert r["observed_disagreement"] == pytest.approx(1 / 16)


def test_median_quartiles_carries_both_median_and_mean():
    """四分位是 Fable 要的形狀，`mean` 是預註冊 P-W11 指名的仲裁欄位——都要在。"""
    r = median_quartiles([1, 2, 3, 4, 5])
    assert (r["median"], r["q1"], r["q3"], r["mean"]) == (3.0, 2.0, 4.0, 3.0)


# ── 2. 去識別化：負控必須抓到 ────────────────────────────────────────────
def test_leaky_workspace_is_dropped_whole(fake):
    """帶臂名／收據字樣那一格**整包**退出質化（§五-6-1：不是遮掉）。"""
    cells, _ = load_cells(_args(run_dir=str(fake["run_dir"])))
    dropped = {}
    for c in cells:
        d = deidentify(c, fake["bank"][c.task_id], "salt")
        if not d.ok:
            dropped[c.cell_id] = d.reason
    assert len(dropped) == 2, dropped
    for cid, reason in dropped.items():
        assert cid.startswith("fw_03_leak|A-GATE|")
        assert "a-gate" in reason and "receipt" in reason and ".vacant" in reason


def test_no_emitted_prompt_contains_any_identifying_string(fake, tmp_path):
    """Fable 指名的那一條：含 A-SOLO／A-CONF／A-GATE／seed／receipt 的檔案
    **不得出現在送出的 prompt 裡**。"""
    cells, run_id = load_cells(_args(run_dir=str(fake["run_dir"])))
    out = tmp_path / "dry"
    run_judging(cells, fake["bank"], resolve_graders(_args(stub_graders=True)),
                run_id=run_id, salt="salt", out_dir=out, dry_run=True)
    lines = (out / "judge_prompts.jsonl").read_text("utf-8").splitlines()
    assert lines, "一筆 prompt 都沒產出來"
    for line in lines:
        rec = json.loads(line)
        blob = (rec["prompt"] + rec["system"]).lower()
        for bad in FORBIDDEN_IN_PROMPT:
            assert bad.lower() not in blob, f"{rec['sample_id']} 洩漏 {bad}"


def test_scaffolding_is_removed_but_modified_scaffolding_is_kept(fake, tmp_path):
    """`.git/`／`TASK.md`／`examples/` 無條件刪；`run_examples.sh` 只有與樣板
    逐位元相同時才刪——刪掉 worker 改過的檔案＝改變被評的東西。"""
    cells, _ = load_cells(_args(run_dir=str(fake["run_dir"])))
    c = next(c for c in cells if c.task_id == "fw_01_records")
    d = deidentify(c, fake["bank"][c.task_id], "salt")
    names = [p for p, _ in d.files]
    assert names == ["solution.py"], names
    assert any("TASK.md" in x for x in d.dropped_files)
    assert any(".git" in x for x in d.dropped_files)
    assert any("examples/" in x for x in d.dropped_files)
    assert any("run_examples.sh [drop_scaffold_unchanged]" in x
               for x in d.dropped_files)

    # 改過的鷹架要留著（而且照樣過洩漏掃描）
    ws = tmp_path / "ws"
    ws.mkdir()
    (ws / "solution.py").write_text("def normalise(rows):\n    return []\n")
    (ws / "run_examples.sh").write_text("#!/bin/sh\n# worker changed this\n")
    c2 = Cell("t|A-SOLO|s", "fw_01_records", "A-SOLO", "s", ws)
    d2 = deidentify(c2, fake["bank"]["fw_01_records"], "salt")
    assert sorted(p for p, _ in d2.files) == ["run_examples.sh", "solution.py"]


def test_hidden_json_in_the_workspace_is_a_structural_drop(fake, tmp_path):
    """`hidden.json` 依設計從不進工作區（§五-3-1）。它一旦出現在那裡，
    就算題目正文剛好有 "hidden" 這個字，也**不接受豁免**。"""
    ws = tmp_path / "ws_hidden"
    ws.mkdir()
    (ws / "solution.py").write_text("def normalise(rows):\n    return []\n")
    (ws / "hidden.json").write_text("[]")
    entry = dict(fake["bank"]["fw_01_records"])
    entry["vocab"] = entry["vocab"] + "\nthe client has hidden columns"
    d = deidentify(Cell("t|A-SOLO|s", "fw_01_records", "A-SOLO", "s", ws),
                   entry, "salt")
    assert d.ok is False
    assert d.reason.startswith("forbidden_path")


def test_excuse_is_recorded_not_silent():
    """題目正文本來就有的字（`ow_07_retrypolicy` 的 retry）⇒ 豁免，但要落盤。"""
    vocab = "the client wants a retry policy with exponential backoff"
    hits, excused = _leak_hits("we retry three times here", vocab)
    assert hits == []
    assert [e["token"] for e in excused] == ["retry"]
    assert "task's own frozen text" in excused[0]["excuse"]


def test_arm_names_are_never_excusable():
    """就算題目正文寫了 `A-GATE` 三個字，那一格照樣要被擋。"""
    hits, excused = _leak_hits("# A-GATE", "this task is about an A-GATE device")
    assert any(h["token"] == "a-gate" for h in hits)
    assert not any(e["token"] == "a-gate" for e in excused)
    for tok in ("a-solo", "a-conf", "a-gate", ".vacant", "vacant", "r530"):
        assert tok in NEVER_EXCUSABLE


def test_frozen_leak_list_matches_the_prereg():
    """§五-6-1 逐字凍結的清單不准在程式裡悄悄縮水。"""
    for token in ("acceptance", "gate", "attempt", "retry", "round 2",
                  "the tests said"):
        assert token in FROZEN_LEAK_TOKENS
    for token in ("seed", "receipt"):          # Fable 2026-09-13 補的
        assert token in FROZEN_LEAK_TOKENS


def test_sample_id_is_deterministic_and_leaks_nothing():
    a = sample_id_for("salt", "ow_01_csvjson|A-GATE|g-r530-s1")
    assert a == sample_id_for("salt", "ow_01_csvjson|A-GATE|g-r530-s1")
    assert a != sample_id_for("other-salt", "ow_01_csvjson|A-GATE|g-r530-s1")
    assert a.startswith("sample_") and len(a) == len("sample_") + 8
    for bad in ("ow_01", "A-GATE", "r530", "s1"):
        assert bad.lower() not in a.lower()


# ── 3. 盲：順序與獨立呼叫 ────────────────────────────────────────────────
def test_each_grader_gets_its_own_order_over_the_same_set(fake, tmp_path):
    cells, run_id = load_cells(_args(run_dir=str(fake["run_dir"])))
    out = tmp_path / "dry2"
    run_judging(cells, fake["bank"], resolve_graders(_args(stub_graders=True)),
                run_id=run_id, salt="salt", out_dir=out, dry_run=True)
    seen: dict[str, list[str]] = {}
    for line in (out / "judge_prompts.jsonl").read_text("utf-8").splitlines():
        rec = json.loads(line)
        seen.setdefault(rec["grader_id"], []).append(rec["sample_id"])
    assert len(seen) == 2
    (o1, o2) = list(seen.values())
    assert o1 != o2, "兩位評審的順序一樣＝順序隨機沒生效"
    assert sorted(o1) == sorted(o2), "兩位評審看到的集合必須相同"


def test_one_call_per_cell_no_side_by_side_comparison(fake, tmp_path):
    """同一題的三臂**各自獨立呼叫**——一個 prompt 裡只能有一份提交。"""
    cells, run_id = load_cells(_args(run_dir=str(fake["run_dir"])))
    out = tmp_path / "dry3"
    run_judging(cells, fake["bank"], resolve_graders(_args(stub_graders=True)),
                run_id=run_id, salt="salt", out_dir=out, dry_run=True)
    for line in (out / "judge_prompts.jsonl").read_text("utf-8").splitlines():
        rec = json.loads(line)
        assert rec["prompt"].count("## Submission") == 1


# ── 4. 沒量到 ≠ 量到低分 ─────────────────────────────────────────────────
class _VoidBrain:
    def chat(self, *a, **kw):
        raise InfraVoid("四次都失敗")


class _JunkBrain:
    def __init__(self):
        self.n = 0

    def chat(self, *a, **kw):
        self.n += 1
        return "I think it is pretty good overall.", {"latency_ms": 1}


def test_infra_void_is_not_a_score():
    g = Grader("J1", "http://x", "m", "s")
    r = score_one(g, _VoidBrain(), "prompt")
    assert r["status"] == "infra_void" and r["scores"] is None


def test_unparsable_reply_is_not_a_score_and_is_retried():
    g = Grader("J1", "http://x", "m", "s")
    b = _JunkBrain()
    r = score_one(g, b, "prompt", parse_retries=2)
    assert r["status"] == "parse_void" and r["scores"] is None
    assert b.n == 3, "解析失敗要重問 parse_retries 次"


def test_parser_refuses_partial_or_out_of_range():
    assert parse_scores('{"readability":3,"structure":3,"error_handling":3}') is None
    assert parse_scores('{"readability":0,"structure":3,"error_handling":3,'
                        '"goal_fit":3}') is None
    assert parse_scores('{"readability":true,"structure":3,"error_handling":3,'
                        '"goal_fit":3}') is None
    ok = parse_scores('noise ```json\n{"readability":1,"structure":2,'
                      '"error_handling":3,"goal_fit":4,"reason":"r"}\n``` tail')
    assert ok[0] == {"readability": 1, "structure": 2, "error_handling": 3,
                     "goal_fit": 4}


# ── 5. 輸出：預註冊指名的欄位 ────────────────────────────────────────────
def test_summary_has_every_field_the_prereg_arbitrates_on(fake, tmp_path):
    cells, run_id = load_cells(_args(run_dir=str(fake["run_dir"])))
    out = tmp_path / "stub"
    s = run_judging(cells, fake["bank"], resolve_graders(_args(stub_graders=True)),
                    run_id=run_id, salt="salt", out_dir=out, dry_run=False)
    # §六-6 的擋門
    assert s["does_not_change_four_state"] is True
    # P-W11：rubric.<seed>.<dim>.<ARM>.mean
    for seed in ("fake-s1", "fake-s2"):
        for dim in DIMS:
            for arm in ("A-SOLO", "A-CONF", "A-GATE"):
                cell = s["rubric"][seed][dim].get(arm)
                assert cell is not None, f"缺 rubric.{seed}.{dim}.{arm}"
                for k in ("mean", "median", "q1", "q3", "n"):
                    assert k in cell
    # P-W12：rubric.irr.alpha_<dim>
    for dim in DIMS:
        assert f"alpha_{dim}" in s["rubric"]["irr"]
    assert "deident_dropped_n" in s["rubric"]
    assert s["rubric"]["deident_dropped_n"] == 2
    assert s["rubric"]["graders"] == ["J1", "J2"]
    assert s["contains_stub_grader"] is True, "替身評審必須自己承認"
    assert (out / "rubric_summary.json").exists()
    assert (out / "judge_calls.jsonl").exists()
    assert (out / "deident.jsonl").exists()


def test_seeds_are_never_pooled(fake, tmp_path):
    """「不平均跨 seed」是 Fable 指名的形狀：每顆 seed 自己一棵樹。"""
    cells, run_id = load_cells(_args(run_dir=str(fake["run_dir"])))
    s = run_judging(cells, fake["bank"], resolve_graders(_args(stub_graders=True)),
                    run_id=run_id, salt="salt", out_dir=tmp_path / "s", dry_run=False)
    seeds = [k for k in s["rubric"]
             if k not in ("irr", "deident_dropped_n", "graders")]
    assert sorted(seeds) == ["fake-s1", "fake-s2"]


def test_disagreement_list_is_produced(tmp_path):
    """兩評審差 ≥2 分的清單是給人抽讀的，不能只存在於註解裡。"""
    from ops.gain.r530.judge_r530 import aggregate
    recs = []
    for gid, v in (("J1", 5), ("J2", 2)):
        recs.append({"status": "ok", "grader_id": gid, "sample_id": "sample_x",
                     "reason": f"{gid} reason",
                     "scores": {d: v for d in DIMS},
                     "cell": {"cell_id": "t|A-GATE|s1", "task_id": "t",
                              "arm": "A-GATE", "seed": "s1"}})
    s = aggregate(recs, [], [Grader("J1", "x", "m", "a"), Grader("J2", "x", "m", "b")],
                  run_id="r", salt="s")
    assert len(s["disagreements"]) == len(DIMS)
    assert s["disagreements"][0]["diff"] == 3


# ── 6. 正控／負控 ───────────────────────────────────────────────────────
def test_controls_direction_and_leak_negative_control(tmp_path):
    res = run_controls(resolve_graders(_args(stub_graders=True)), tmp_path / "ctrl")
    assert res["negative_control_leaky_dropped"] is True
    assert res["direction_ok"] is True
    for gid in ("J1", "J2"):
        d = res["by_grader"][gid]
        assert d["total_delta"] > 0
        assert d["deltas"]["structure"] >= 0
        assert d["deltas"]["error_handling"] >= 0


# ── 7. KS-1 與 prompt 紀律 ──────────────────────────────────────────────
def test_prompt_constants_are_ks1_clean():
    for txt in (JUDGE_SYSTEM, JUDGE_PROMPT_HEADER, JUDGE_PROMPT_FOOTER):
        assert assert_ks1_clean(txt) == txt
    for dim in DEFAULT_RUBRIC.values():
        for lvl in dim.values():
            assert_ks1_clean(lvl)
    with pytest.raises(KS1Violation):
        assert_ks1_clean(JUDGE_PROMPT_HEADER + "\nYou are responsible for this.")


def test_prompt_never_mentions_the_experiment():
    """評審不該從 prompt 本身知道有幾條臂、有沒有閘門、測試過了沒有。"""
    blob = (JUDGE_SYSTEM + JUDGE_PROMPT_HEADER + JUDGE_PROMPT_FOOTER).lower()
    for word in ("arm", "attempt", "retry", "gate", "hidden test", "passed",
                 "experiment", "vacant"):
        assert word not in blob, f"prompt 模板提到了 {word}"


def test_rubric_dims_match_the_prereg_table():
    """§一-4 的四維：可讀性／結構／錯誤處理／與目標的貼合度。"""
    assert DIMS == ("readability", "structure", "error_handling", "goal_fit")
    assert set(DEFAULT_RUBRIC) == set(DIMS)
    for dim in DIMS:
        assert set(DEFAULT_RUBRIC[dim]) == {"1", "3", "5"}


def test_bank_is_fail_closed_on_a_missing_dimension(tmp_path):
    """少一個維度而靜靜地補預設值＝評分表在題目之間偷偷不一樣。"""
    d = tmp_path / "bank" / "t1"
    d.mkdir(parents=True)
    (d / "task.md").write_text("goal")
    broken = {k: v for k, v in DEFAULT_RUBRIC.items() if k != "goal_fit"}
    (d / "rubric.json").write_text(json.dumps(broken))
    with pytest.raises(SystemExit):
        load_bank(tmp_path / "bank")


def test_prereg_still_says_quality_does_not_move_the_verdict():
    """§六-6 在預註冊裡改掉的話，本檔寫死的 `does_not_change_four_state` 要跟著檢討。"""
    if not PREREG.exists():          # worktree 裡可能還沒 merge 到預註冊
        pytest.skip("預註冊不在這個工作樹裡")
    text = PREREG.read_text("utf-8")
    assert "質化不改裁決" in text
    assert "沒有一條讀 `rubric.*`" in text


# ── 8. CLI ─────────────────────────────────────────────────────────────
def test_cli_dry_run_end_to_end(fake, tmp_path, capsys):
    rc = main(["--run-dir", str(fake["run_dir"]), "--bank", str(fake["bank_dir"]),
               "--out-dir", str(tmp_path / "cli"), "--dry-run", "--stub-graders"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "does_not_change_four_state=True" in out
    assert (tmp_path / "cli" / "judge_prompts.jsonl").exists()


def test_cli_selftest_and_mutation_check():
    assert main(["--selftest"]) == 0
    assert main(["--mutation-check"]) == 0
