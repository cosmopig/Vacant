"""R530：整條迴圈的三種結局 ＋ 發射器的擋門。

用替身後端（`ops/gain/r530/stubbrain.py`）跑真的 `run_cell`——
量的是 **harness 的路徑**不是模型能力。這些數字不准拿去當任何一格結果。
"""
from __future__ import annotations

import json
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ops.gain.r530 import openwork_arms as oa  # noqa: E402
from ops.gain.r530 import sandbox as sb, tasks as taskmod, wshash  # noqa: E402
from ops.gain.r530.run_r530 import main as run_main  # noqa: E402
from ops.gain.r530.stubbrain import StubBrain  # noqa: E402
from vacant.identity import Identity  # noqa: E402
from vacant.logbook import Logbook  # noqa: E402


class AlwaysBadBrain(StubBrain):
    """永遠寫過不了可見驗收的那一份——用來走 `A-CONF` 的拒交路徑。"""

    def _source(self, task_id, good):
        return super()._source(task_id, False)


def _paths(tmp_path, task) -> oa.CellPaths:
    return oa.CellPaths(
        template_dir=task["template_dir"],
        visible_dir=task["visible_dir"],
        hidden_dir=task["hidden_dir"],
        cell_dir=tmp_path / "cell",
        verify_root=tmp_path / "_verify",
        ws_archive_dir=tmp_path / "ws",
    )


def _run(tmp_path, arm, *, seed="smoke-t", brain_cls=StubBrain,
         task_id="ow_01_csvjson"):
    task = taskmod.load_task(task_id)
    paths = _paths(tmp_path, task)
    book, ident = Logbook(), Identity.generate()
    brain = brain_cls(log_path=tmp_path / "calls.jsonl")
    row = oa.run_cell(task, brain, arm=arm, seed=seed, paths=paths,
                      sandbox=sb.NoneSandbox(),
                      calls_path=tmp_path / "calls.jsonl",
                      book=book, ident=ident)
    return row, book, task


# ── A-SOLO ────────────────────────────────────────────────────────────────
def test_solo_ships_whatever_it_declared_and_never_refuses(tmp_path):
    row, book, _task = _run(tmp_path, "A-SOLO")
    assert row["accepted"] is True, "A-SOLO 沒有拒交語意"
    assert row["stop_reason"] == "declared_done"
    # §三-6 C3：`A-SOLO` 那格**也要跑**可見驗收——只記分、不當閘門、不回饋。
    assert row["visible_total"] == 3 and row["visible_passed"] is not None, \
        "A-SOLO 的可見驗收要落盤（P-W7／W7a／W7b 的對照那一半）"
    # 只記分的那一次驗收跑在**收尾**（不是閘門輪）⇒ `gate_rounds` 是空的。
    # 這一格與「有閘門的臂」的差別就在這裡：`A-SOLO` 從來沒有過閘門。
    assert row["attempts"][0]["gate_rounds"] == []
    assert row["attempts_n"] == 1
    assert row["hidden_total"] == 14
    types = [e.type for e in book.entries]
    assert types.count("ws_verdict") == 1
    assert types.count("ws_attempt") == 1, \
        "沒有閘門的臂也要簽一筆 attempt，否則對帳會把它讀成漏寫"
    att = next(e for e in book.entries if e.type == "ws_attempt")
    # `A-SOLO` 沒有閘門 ⇒ 它那一筆 attempt 的 `verdict_sha256` 是 None，
    # 而且帶著 `no_gate_reason`——「這一份沒有跑過閘門」要表達得出來，
    # 不是靠「欄位剛好是空的」。
    assert att.payload["verdict_sha256"] is None
    assert att.payload["no_gate_reason"] == "declared_done"


def test_solo_false_delivery_is_visible_in_the_row(tmp_path):
    """hasty persona ⇒ 第一稿是壞的 ⇒ 出貨了但隱藏沒全過（P-W5 的那一格）。"""
    row, _book, _task = _run(tmp_path, "A-SOLO", seed="smoke-hasty")
    assert row["accepted"] is True
    if row["hidden_passed"] < row["hidden_total"]:
        assert row["deliv"] is False, "出貨但沒全過 ⇒ deliv 必須是 False"


# ── A-GATE ────────────────────────────────────────────────────────────────
def test_gate_feeds_the_failure_text_back_and_then_passes(tmp_path):
    row, book, _task = _run(tmp_path, "A-GATE", seed="smoke-hasty")
    rounds = row["attempts"][0]["gate_rounds"]
    assert rounds, "A-GATE 至少跑過一個閘門輪"
    if len(rounds) > 1:
        assert rounds[0]["all_pass"] is False and rounds[-1]["all_pass"] is True
        assert row["stop_reason"] == "visible_pass"
    assert row["attempts_n"] == 1, "A-GATE 全程一個工作區、一段對話"
    assert [e.type for e in book.entries].count("ws_verdict") == 1
    assert [e.type for e in book.entries].count("ws_attempt") == len(rounds)


def test_gate_workspace_accumulates_it_never_resets(tmp_path):
    task = taskmod.load_task("ow_01_csvjson")
    paths = _paths(tmp_path, task)
    row, _book, _t = _run(tmp_path, "A-GATE", seed="smoke-hasty")
    assert row["ws_start_sha256"] == wshash.tree_hash(task["template_dir"])
    assert row["ws_end_sha256"] != row["ws_start_sha256"], \
        "宣告完成時工作區必須真的被動過（nudge 擋的就是這件事）"
    del paths


def test_gate_refuses_when_the_rounds_run_out(tmp_path):
    row, _book, _task = _run(tmp_path, "A-GATE", brain_cls=AlwaysBadBrain,
                             seed="smoke-hasty")
    assert row["accepted"] is False
    assert row["stop_reason"] == "gate_exhausted"
    assert len(row["attempts"][0]["gate_rounds"]) == \
        oa.OPENWORK_BUDGET["max_gate_rounds"]
    assert row["deliv"] is False
    assert row["hidden_frac_delivered"] == 0.0
    assert row["hidden_frac"] is not None, \
        "拒交的格子仍然要量最終工作區——兩個數字都落盤，由 analyzer 挑"


# ── A-CONF ────────────────────────────────────────────────────────────────
def test_conf_resets_the_workspace_and_changes_persona(tmp_path):
    row, _book, task = _run(tmp_path, "A-CONF", brain_cls=AlwaysBadBrain,
                            seed="smoke-hasty")
    assert row["accepted"] is False
    assert row["stop_reason"] == "attempts_exhausted"
    assert row["attempts_n"] == oa.OPENWORK_BUDGET["max_conf_attempts"]
    assert row["attempts_used"] == row["attempts_n"]
    personas = [a["persona"] for a in row["attempts"]]
    assert len(set(personas)) == len(personas), "每次嘗試換一位 persona"
    # 每一次嘗試都從**同一個**樣板起點開始。
    assert row["ws_start_sha256"] == wshash.tree_hash(task["template_dir"])
    for a in row["attempts"]:
        assert len(a["gate_rounds"]) == 1, \
            "A-CONF 不回饋：一次嘗試只跑一次可見驗收就重抽"


class NeverWritesBrain(StubBrain):
    """宣告完成但一個檔案都不寫——走 nudge 那條路。"""

    def propose(self, messages, *, system, meta=None, role="r530"):
        return {"text": "I have finished the task.", "tool_calls": [],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5,
                          "total_tokens": 15},
                "finish_reason": "stop", "raw": {}}


def test_solo_accepted_is_true_even_when_it_wrote_nothing(tmp_path):
    """**`A-SOLO` 的 accepted 恆為 True——這是定義不是發現**（§六-0、§八-4）。

    連「宣告完成但什麼都沒寫」都是一份交付（一份空的）。記成拒交會讓
    `A-SOLO` 憑空長出拒交語意，而 P-W3 的「SOLO 拒交件數 ＝ 0」
    就從結構性必然變成一個會跳動的數字。
    """
    row, _book, _task = _run(tmp_path, "A-SOLO", brain_cls=NeverWritesBrain)
    assert row["stop_reason"] == "nudge_exhausted"
    assert row["accepted"] is True
    assert row["refusal"] is False
    assert row["deliv"] is False, "交了一份空的 ⇒ accepted 但不是 deliv"


def test_only_the_two_gated_arms_can_refuse(tmp_path):
    solo, _b, _t = _run(tmp_path, "A-SOLO", brain_cls=AlwaysBadBrain,
                        seed="smoke-hasty")
    gate, _b2, _t2 = _run(tmp_path, "A-GATE", brain_cls=AlwaysBadBrain,
                          seed="smoke-hasty")
    assert solo["refusal"] is False and solo["accepted"] is True
    assert gate["refusal"] is True and gate["accepted"] is False


def test_solo_visible_result_never_reaches_the_model(tmp_path):
    """只記分的那一次驗收**不准**進對話——進了就不是 `A-SOLO` 了。"""
    _row, _book, _task = _run(tmp_path, "A-SOLO", seed="smoke-hasty")
    body = (tmp_path / "calls.jsonl").read_text(encoding="utf-8")
    head = oa.FEEDBACK_TEMPLATE.split("{block}")[0].strip()
    assert head not in body
    import json as _json
    for line in body.splitlines():
        rec = _json.loads(line)
        for m in rec.get("messages") or []:
            assert "::check_" not in (m.get("content") or ""), \
                "可見驗收的逐條結果不准出現在送給模型的訊息裡"


def test_conf_gives_no_feedback_text_at_all(tmp_path):
    """`A-CONF` 一個字都不給——`calls.jsonl` 裡不該出現回饋模板。"""
    _row, _book, _task = _run(tmp_path, "A-CONF", brain_cls=AlwaysBadBrain,
                              seed="smoke-hasty")
    body = (tmp_path / "calls.jsonl").read_text(encoding="utf-8")
    head = oa.FEEDBACK_TEMPLATE.split("{block}")[0].strip()
    assert head not in body


def test_conf_ships_the_first_attempt_that_passes(tmp_path):
    row, _book, _task = _run(tmp_path, "A-CONF", seed="smoke-careful")
    if row["accepted"]:
        assert row["stop_reason"] == "visible_pass"
        assert row["attempts"][-1]["gate_rounds"][-1]["all_pass"] is True


# ── 發射器的擋門 ──────────────────────────────────────────────────────────
def _base_argv(out, **kw):
    argv = ["--out", out, "--task-set", "ow_01_csvjson", "--seed", "smoke-x",
            "--backend", "none", "--brain", "stub", "--smoke"]
    for k, v in kw.items():
        argv += [f"--{k.replace('_', '-')}", str(v)]
    return argv


def test_smoke_requires_a_smoke_seed():
    with pytest.raises(SystemExit) as e:
        run_main(["--out", "runs/_smoke/x", "--seed", "g-r530-s1",
                  "--backend", "none", "--brain", "stub", "--smoke"])
    assert "smoke-" in str(e.value)


def test_smoke_requires_the_smoke_out_dir():
    with pytest.raises(SystemExit) as e:
        run_main(["--out", "runs/g_r530_real", "--seed", "smoke-x",
                  "--backend", "none", "--brain", "stub", "--smoke"])
    assert "runs/_smoke/" in str(e.value)


def test_real_run_requires_a_decision():
    with pytest.raises(SystemExit) as e:
        run_main(["--out", "runs/g_r530_real", "--seed", "g-r530-s1",
                  "--backend", "none"])
    assert "--decision" in str(e.value)


def test_real_run_refuses_the_stub_backend(tmp_path):
    dec = tmp_path / "DEC.md"
    from ops.gain.r530.run_r530 import registration_line
    from ops.gain.brain_cline import endpoint
    line = registration_line(out="runs/g_r530_real", task_set="ow_01_csvjson",
                             arms=",".join(oa.ARMS), seed="g-r530-s1",
                             endpoint_url=endpoint())
    dec.write_text(line + "\n", encoding="utf-8")
    with pytest.raises(SystemExit) as e:
        run_main(["--out", "runs/g_r530_real", "--decision", str(dec),
                  "--task-set", "ow_01_csvjson", "--seed", "g-r530-s1",
                  "--backend", "none", "--brain", "stub"])
    assert "stub" in str(e.value)


def test_unregistered_block_is_refused(tmp_path):
    dec = tmp_path / "DEC.md"
    dec.write_text("nothing registered here\n", encoding="utf-8")
    with pytest.raises(SystemExit) as e:
        run_main(["--out", "runs/g_r530_real", "--decision", str(dec),
                  "--task-set", "ow_01_csvjson", "--seed", "g-r530-s1",
                  "--backend", "none"])
    assert "abort_not_registered" in str(e.value)


def test_plan_mode_writes_nothing(capsys):
    out = "runs/_smoke/r530_plan_probe"
    rc = run_main(["--out", out, "--task-set", "ow_01_csvjson",
                   "--seed", "smoke-x", "--backend", "none", "--brain", "stub",
                   "--smoke", "--plan"])
    assert rc == 0
    assert not (ROOT / out).exists(), "--plan 不准寫 runs/"
    assert "R530_BLOCK:" in capsys.readouterr().out


def test_bank_sha_mismatch_aborts(tmp_path):
    ts = taskmod.load_tasks("ow_01_csvjson")
    man = taskmod.bank_manifest(ts)
    man["ow_01_csvjson"]["files"]["templates/ow_01_csvjson/goal.md"] = "0" * 64
    p = tmp_path / "pinned.json"
    p.write_text(json.dumps(man), encoding="utf-8")
    with pytest.raises(SystemExit) as e:
        taskmod.assert_bank_matches(ts, p)
    assert "abort_bank_sha_mismatch" in str(e.value)


def test_bank_manifest_round_trips(tmp_path):
    ts = taskmod.load_tasks("all")
    man = taskmod.bank_manifest(ts)
    p = tmp_path / "pinned.json"
    p.write_text(json.dumps(man), encoding="utf-8")
    assert taskmod.assert_bank_matches(ts, p)["_root_sha256"] == man["_root_sha256"]


# ── 收尾記帳不准只走 happy path（§三-6 C3／C6 抓到的那兩個 bug）──────────
class BusyForeverBrain(StubBrain):
    """永遠要工具、永遠不宣告完成——逼出「撞預算」那條路徑。"""

    def propose(self, messages, *, system, meta=None, role="r530"):
        return {"text": "",
                "tool_calls": [{"id": "x", "name": "run_bash",
                                "command": "echo still working >> notes.txt",
                                "timeout_s": None}],
                "usage": {"prompt_tokens": 100, "completion_tokens": 10,
                          "total_tokens": 110},
                "finish_reason": "stop", "raw": {}}


def test_a_cell_that_never_declares_done_still_has_a_visible_result(tmp_path):
    """C3：可見驗收**每一格都要有**，撞預算的也要。

    原本只在「宣告完成」那條路上跑 ⇒ 撞 `budget_calls` 的格子 `visible` 是
    None ⇒ P-W7／W7a／W7b 的對照那一半整個不見。
    """
    row, _book, _task = _run(tmp_path, "A-SOLO", brain_cls=BusyForeverBrain)
    assert row["stop_reason"].startswith("budget")
    # 條數不是 3 也沒關係——工作區裡沒有 `solution.py`，可見驗收會在
    # import 那一步就整檔失敗（1 條 `<module>`）。要的是「**跑過了**」，
    # 不是「跑出漂亮的數字」。
    assert row["visible_total"] >= 1, "撞預算的格子也要有可見驗收結果"
    assert row["visible_passed"] == 0
    assert row["visible_result_sha256"]


def test_a_cell_that_never_declares_done_still_signs_an_attempt(tmp_path):
    """C6：`attempt 數 ≥ verdict 數` 的對帳在**所有**結局上都要成立。

    收尾記帳只走 happy path 是一種很安靜的壞法：鏈本身沒壞，
    壞的是「鏈說得出這一格發生過什麼」這件事。
    """
    row, book, _task = _run(tmp_path, "A-GATE", brain_cls=BusyForeverBrain)
    types = [e.type for e in book.entries]
    assert types.count("ws_verdict") == 1
    assert types.count("ws_attempt") >= 1, "撞預算的格子也要簽一筆 attempt"
    assert types.count("ws_attempt") >= types.count("ws_verdict")
    att = next(e for e in book.entries if e.type == "ws_attempt")
    assert att.payload["no_gate_reason"].startswith("budget")
    assert row["receipt_attempt_hashes"]


def test_conf_gets_a_second_attempt_when_the_first_runs_out_of_its_quota(tmp_path):
    """Fable 2026-09-14：`A-CONF` 每份 24 通、最多 3 份、整格 72 通。

    前一版三臂共用 24 通 ⇒ 第一份用完就整格結束，「重抽」永遠不會發生，
    而 §八-4 把 `A-GATE` vs `A-CONF` 指定為等預算的那一刀。
    """
    row, _book, _task = _run(tmp_path, "A-CONF", brain_cls=BusyForeverBrain)
    b = oa.OPENWORK_BUDGET
    assert row["attempts_used"] == b["max_conf_attempts"], \
        "每一份用完自己的配額要換下一份，不是整格停"
    assert row["calls_used"] == b["max_model_calls"]
    for a in row["attempts"]:
        assert a["calls"] == b["max_calls_per_attempt"]
        assert a["attempt_calls_exhausted"] is True
    personas = [a["persona"] for a in row["attempts"]]
    assert len(set(personas)) == len(personas), "每一份換一位 persona"
    assert row["stop_reason"] == "attempts_exhausted"
    assert row["refusal"] is True
