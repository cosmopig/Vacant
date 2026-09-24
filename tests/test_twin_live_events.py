"""數位分身的活模式：`vacant.lifecycle/1` → 電視事件（`ops/exhibit/twin/live_events.py`）。

承重的是第一條：**同一批真跑，「當下轉的」與「事後推的」講同一件事。**
Vacant 之後怎麼迭代，只要這一條還綠，分身畫面就不會安靜地演錯；
它一紅，就是兩條線在某個欄位上分家了——要嘛修 launcher 的事件，要嘛換契約版號。

刻意不比的欄位寫死在 `LIVE_ONLY_DIFFS`，理由在 `live_events.py` 的模組 docstring。
⚠ 零模型呼叫：`run_twin.py --fixture`（腳本化 agent，requests_seen＝0）。
"""
from __future__ import annotations

import json
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ops.exhibit.twin import live_events as le                       # noqa: E402
from ops.exhibit.twin import pack, run_twin                          # noqa: E402
from ops.exhibit.twin import to_events as te                         # noqa: E402
from vacant_network.vrun import lifecycle                            # noqa: E402

#: 事後那條有、當下那條刻意沒有（或值不同）的東西。**加一格要寫理由。**
LIVE_ONLY_DIFFS = {
    "*": ("ts", "of"),                          # 真牆鐘；跑到一半不知道總數
    "task_opened": ("evidence", "evidence_note"),   # 開題那一刻還推不出來
    "verdict": ("evidence", "evidence_note"),       # 當下那條多帶（推出來的值）
}
SKIP_TYPES = ("counters", "postaudit")          # 批次累計／事後稽核不是 Vacant 當場的事

TASKS = "s1_01_addmul,s1_12_hms"


def _norm(e: dict) -> dict:
    drop = set(LIVE_ONLY_DIFFS["*"]) | set(LIVE_ONLY_DIFFS.get(e["type"], ()))
    return {k: v for k, v in e.items() if k not in drop}


@pytest.fixture(scope="module", params=[
    [],                                         # 單發
    ["--retry", "revise", "--max-attempts", "2"],   # 迴圈：revised 那一拍
], ids=["single", "revise"])
def batch(request, tmp_path_factory):
    out = tmp_path_factory.mktemp("twin_live")
    rc = run_twin.main(["--out", str(out), "--fixture", "--residents", "1",
                        "--tasks", TASKS, "--sandbox", "none",
                        "--events", str(out / "lifecycle.jsonl"), *request.param])
    assert rc == 0
    return out


def test_lifecycle_stream_from_a_real_batch_is_valid(batch):
    evs = lifecycle.read(batch / "lifecycle.jsonl")
    assert lifecycle.validate_stream(evs) == []
    # 4 格 × 兩臂 ＝ 8 跑，每一跑都有頭有尾
    assert [e["type"] for e in evs].count("run_started") == 8
    assert [e["type"] for e in evs].count("run_ended") == 8


def test_live_matches_posthoc_for_the_same_runs(batch):
    post = [e for e in te.build(pack.build(batch), verify_url="/r/{cell}", t0_ms=0)
            if e["type"] not in SKIP_TYPES]
    live = le.fold(lifecycle.read(batch / "lifecycle.jsonl"), verify_url="/r/{cell}")
    assert te.validate(live) == []
    assert [e["type"] for e in live] == [e["type"] for e in post]
    for i, (a, b) in enumerate(zip(post, live)):
        assert _norm(a) == _norm(b), f"第 {i} 筆（{a['type']}／{a.get('arm')}）兩條線分家了"


def test_revise_batch_really_has_the_loop(batch):
    live = le.fold(lifecycle.read(batch / "lifecycle.jsonl"), verify_url="/r/{cell}")
    types = [e["type"] for e in live]
    evs = lifecycle.read(batch / "lifecycle.jsonl")
    if any(e.get("retry") == "revise" for e in evs if e["type"] == "run_started"):
        assert "revised" in types
        assert any(e["type"] == "feedback_ready" for e in evs)
    else:
        assert "revised" not in types


def test_evidence_is_derived_not_declared(batch):
    """fixture 的 requests_seen＝0 ⇒ 不管宣告什麼都是 L-none（宣告蓋不過資料）。"""
    evs = lifecycle.read(batch / "lifecycle.jsonl")
    for e in evs:
        if e["type"] == "run_started":
            e["caller"]["declared_evidence"] = "L-real"
    live = le.fold(evs, verify_url="/r/{cell}")
    assert {e["evidence"] for e in live if e["type"] == "verdict"} == {"L-none"}
    assert all(e["evidence"] is None for e in live if e["type"] == "task_opened")


def test_schema_mismatch_is_loud():
    with pytest.raises(le.SchemaMismatch):
        le.fold([{"schema": "vacant.lifecycle/2", "type": "run_started",
                  "run_id": "r", "ts_ms": 0, "task_id": "t", "arm": "RUN-ON"}],
                verify_url="")


def test_follow_waits_for_the_rest_of_a_half_written_line(batch, tmp_path):
    lines = (batch / "lifecycle.jsonl").read_text(encoding="utf-8").splitlines(True)
    src, out = tmp_path / "lc.jsonl", tmp_path / "ev.jsonl"
    first_run_end = next(i for i, ln in enumerate(lines)
                         if json.loads(ln)["type"] == "run_ended")
    head, tail = lines[:first_run_end + 1], lines[first_run_end + 1:]
    half = tail[0][:len(tail[0]) // 2]
    src.write_text("".join(head) + half, encoding="utf-8")
    calls = {"n": 0}

    def sleep(_):
        # 第一次睡醒時把那半行補完，並補上剩下的
        calls["n"] += 1
        if calls["n"] == 1:
            with src.open("a", encoding="utf-8") as fh:
                fh.write(tail[0][len(half):] + "".join(tail[1:]))

    le.follow(src, out, verify_url="/r/{cell}", interval=0.01,
              idle_exit_s=0.05, sleep=sleep)
    got = [json.loads(l) for l in out.read_text(encoding="utf-8").splitlines()]
    want = le.fold(lifecycle.read(batch / "lifecycle.jsonl"), verify_url="/r/{cell}")
    assert [_norm(e) for e in got] == [_norm(e) for e in want]
