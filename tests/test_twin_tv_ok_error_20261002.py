"""P8：電視要演「想放進地上被擋」與「每一通都打不到模型」，所以
`twin_step.ok` 與 `model_call.error` 這兩個布林要原樣帶進電視事件（2026-10-02）。

兩者都不含內容；契約只收布林。每一條配負控制。
"""
from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ops.exhibit.twin import live_events as le  # noqa: E402
from ops.exhibit.twin import sidecar as sc  # noqa: E402
from ops.exhibit.twin import tv_contract as tv  # noqa: E402
from vacant_network.vrun import lifecycle  # noqa: E402

LC = {"schema": lifecycle.SCHEMA, "type": "run_started", "run_id": "r1", "ts_ms": 1000,
      "arm": "RUN-ON", "task_id": "twin:tw-x", "retry": "none",
      "caller": {"cell_id": "tw-x", "resident": "R1", "prompt": "p", "stratum": "twin",
                 "task_kind": tv.KIND_PRACTICAL}}


def _step(ok):
    return sc.twin_step_row({"ts_ms": 1500, "seq": 1, "tool": "ws_write",
                             "path": "地上/紙卡地/x.md", "bytes": 9, "ok": ok},
                            cell_id="tw-x", run_id="r1")


def _fold(*evs):
    f = le.Folder(verify_url="/r/{cell}", mode=tv.MODE_LIVE)
    out = []
    for e in evs:
        out += f.feed(e)
    return out


def test_twin_step_ok_false_reaches_tv_and_validates() -> None:
    out = _fold(LC, _step(False))
    step = [e for e in out if e["type"] == "twin_step"]
    assert len(step) == 1 and step[0]["ok"] is False
    assert tv.validate(out, require_settled=False) == []


def test_twin_step_ok_true_also_carried() -> None:
    out = _fold(LC, _step(True))
    assert [e["ok"] for e in out if e["type"] == "twin_step"] == [True]


def test_negative_control_non_bool_ok_rejected_by_contract() -> None:
    out = _fold(LC, _step(True))
    for e in out:
        if e["type"] == "twin_step":
            e["ok"] = "false"
    assert any("twin_step.ok 要是布林" in b for b in tv.validate(out, require_settled=False))


def _mc(error):
    ev = {"schema": lifecycle.SCHEMA, "type": "model_call", "run_id": "r1", "ts_ms": 1200,
          "attempt": 1}
    if error is not None:
        ev["error"] = error
    return ev


def test_model_call_error_reaches_working() -> None:
    out = _fold(LC, _mc(True), _mc(False))
    w = [e for e in out if e["type"] == "working"]
    assert [e["error"] for e in w] == [True, False]
    assert tv.validate(out, require_settled=False) == []


def test_model_call_without_error_field_adds_nothing() -> None:
    out = _fold(LC, _mc(None))
    w = [e for e in out if e["type"] == "working"]
    assert len(w) == 1 and "error" not in w[0]


def test_negative_control_non_bool_error_rejected_by_contract() -> None:
    out = _fold(LC, _mc(True))
    for e in out:
        if e["type"] == "working":
            e["error"] = 1
    assert any("working.error 要是布林" in b for b in tv.validate(out, require_settled=False))
