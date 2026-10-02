"""2026-10-02 展場第一跑的回歸：現場 tail 是一段一段餵 Folder 的，後段看不到
`task_opened`；契約若因此把帶 `checks` 的 `gate_ran` 當成題庫格而丟掉，
整格就斷在「它說做完了」。這裡用真跑錄下的事件流**一筆一筆**餵，要一路演到 verdict。
"""
from __future__ import annotations

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ops.exhibit.twin import live_events as le  # noqa: E402
from ops.exhibit.twin import sidecar as sc  # noqa: E402
from ops.exhibit.twin import tv_contract as tv  # noqa: E402

EV = ROOT / "ops/exhibit/twin/evidence_gate_20261002"


def _load(p):
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]


def test_gate_ran_with_checks_alone_in_a_batch_is_not_rejected() -> None:
    ev = {"type": "gate_ran", "ts": "2026-10-02T00:00:00Z", "task_id": "tw-x", "mode": "live",
          "arm": "ON", "attempt": 1, "passed": False,
          "checks": [{"id": "G1", "ok": False, "label": "x", "file": "plan", "line": 3}]}
    assert not [b for b in tv.validate([ev], require_settled=False) if "才帶 checks" in b]


def test_negative_control_code_cell_with_checks_still_rejected() -> None:
    opened = {"type": "task_opened", "task_id": "c1", "task_kind": tv.KIND_CODE}
    ev = {"type": "gate_ran", "task_id": "c1", "checks": [{"id": "G1", "ok": True, "label": "x"}]}
    assert [b for b in tv.validate([opened, ev], require_settled=False) if "才帶 checks" in b]


def test_real_run_fed_one_event_per_batch_reaches_verdict() -> None:
    for name in ("f02", "f04"):
        lc = _load(EV / f"{name}.lifecycle.jsonl")
        side = _load(EV / f"{name}.lifecycle.sidecar.jsonl")
        f = le.Folder(verify_url="/r/{cell}", mode=tv.MODE_LIVE)
        out = []
        for ev in sc.merge(lc, side):
            out += f.feed(ev)          # 一筆一筆餵＝現場 tail 的最壞情況
        types = [e["type"] for e in out]
        assert "verdict" in types and types.count("gate_ran") >= 1, (name, types[-6:])
        assert any(e.get("checks") for e in out if e["type"] == "gate_ran"), name
