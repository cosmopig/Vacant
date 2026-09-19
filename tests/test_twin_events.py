"""接電視的那一條線：`ops/exhibit/twin/to_events.py` 的驗收。

契約在 `vacant_hm/world3/docs/LIVE_INTERFACE.md` §一（那是另一個 repo，
電視端已經實作完畢：`world3/index.html` 的 `?live=` 活模式）。這組測試守的是
**生產端不准多說一句話**：

  · 沒發生的步驟不發事件（這一批沒有評審、沒有修訂、沒有抽樣稽核）
  · `basis` 不准寫成 `reputation`——`vacant run` 沒有路由層
  · `meets_demand` 要隱藏測資才答得出來 ⇒ 只能是 null
  · 裁決讀**簽章覆蓋的那一份**，不讀 run 摘要
  · `task_id` 每格唯一，否則會被電視的去重鍵靜靜吃掉一格
"""
import json
import pathlib
import sys

import pytest

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from ops.exhibit.twin import build_viewer, to_events  # noqa: E402

VIEWER = REPO / "examples" / "twin_viewer.html"


@pytest.fixture(scope="module")
def pack():
    html = VIEWER.read_text(encoding="utf-8")
    return json.loads(build_viewer.extract_block(html, "twin-pack"))


@pytest.fixture(scope="module")
def events(pack):
    return to_events.build(pack, verify_url="twin_viewer.html",
                           t0_ms=1_789_000_000_000)


def test_events_satisfy_the_tv_contract(events):
    assert to_events.validate(events) == []


def test_events_do_not_invent_steps_that_did_not_happen(events):
    kinds = {e["type"] for e in events}
    for never in ("review_vote", "revised", "audited"):
        assert never not in kinds, never


def test_events_never_claim_reputation_routing(events):
    for e in events:
        if e["type"] == "routed":
            assert e["basis"] == "random", e


def test_events_never_claim_meets_demand(events):
    """把「通過驗收」寫成「符合需求」是這條線上最容易犯、後果最大的一個錯。"""
    for e in events:
        if e["type"] == "verdict":
            assert e["meets_demand"] is None, e


def test_event_verdict_comes_from_the_signed_entry(pack, events):
    signed = {}
    for c in pack["cells"]:
        for ln in c["chain"]:
            d = json.loads(ln)
            if d["type"] == "ws_verdict":
                signed[c["cell_id"]] = bool(d["payload"]["accepted"])
    seen = 0
    for e in events:
        if e["type"] == "verdict":
            assert e["accepted"] == signed[e["task_id"]], e["task_id"]
            seen += 1
    assert seen == len(pack["cells"])


def test_event_task_ids_are_unique_per_cell(pack, events):
    opened = [e["task_id"] for e in events if e["type"] == "task_opened"]
    assert len(set(opened)) == len(opened) == len(pack["cells"])


def test_every_cell_reaches_a_verdict(events):
    """電視的 liveAssemble 要等到 verdict 才組得出一筆；少一個就永遠卡著。"""
    opened = {e["task_id"] for e in events if e["type"] == "task_opened"}
    settled = {e["task_id"] for e in events if e["type"] == "verdict"}
    assert opened == settled


def test_validate_has_teeth(events):
    """負控制：契約自檢真的會咬人，不是永遠回空清單。"""
    broken = [dict(e) for e in events]
    broken[0].pop("ts")
    assert to_events.validate(broken)
    dupe = [dict(e) for e in events[:2]] + [dict(events[0])]
    assert to_events.validate(dupe)
    unknown = [dict(e) for e in events]
    unknown[0]["type"] = "not_a_real_type"
    assert to_events.validate(unknown)


def test_receipt_event_carries_the_chain_head(pack, events):
    from vacant.logbook import LogEntry
    heads = {c["cell_id"]: LogEntry.from_json(json.loads(c["chain"][-1])).hash()
             for c in pack["cells"]}
    for e in events:
        if e["type"] == "receipt":
            assert e["chain_head"] == heads[e["task_id"]]
            assert e["verify_url"], "觀眾要有一個自己重驗的地方"
