"""接電視的那一條線：**進版控的錄影**（`ops/exhibit/twin/recordings/*.jsonl`）的驗收。

2026-09-24 起電視事件只有一個產生者（`live_events.Folder`），離線備援＝重播錄影。
這一組拿**展場開箱就會播的那幾份錄影**，走展場用的同一條路轉出來，守的是
**生產端不准多說一句話**（契約在 `ops/exhibit/twin/tv_contract.py`，電視端的文件是
`vacant_hm/world3/docs/LIVE_INTERFACE.md`）：

  · 沒發生的層不發事件（`review_vote`／`audited`）
  · `basis` 不准寫成 `reputation`——`vacant run` 沒有路由層
  · `meets_demand` 要隱藏測資才答得出來 ⇒ 只能是 null
  · OFF 臂不發 `gate_ran`／`receipt`、`accepted` 恆為 null
  · 每一格一定走到 `verdict`；`task_id` 每格唯一；去重鍵不撞
  · 每一筆都帶 `mode="replay"`（畫面上要講明是重播）

舊版這一組測的是 `to_events.build(twin_pack)`（事後推導，已刪）。
"""
from __future__ import annotations

import pathlib
import sys

import pytest

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from ops.exhibit.twin import live_events as le  # noqa: E402
from ops.exhibit.twin import serve_twin as S  # noqa: E402
from ops.exhibit.twin import tv_contract as tv  # noqa: E402
from vacant_network.vrun import lifecycle  # noqa: E402

RECORDINGS = S.default_recordings()
pytestmark = pytest.mark.skipif(not RECORDINGS, reason="recordings/ 裡沒有錄影")


@pytest.fixture(scope="module", params=RECORDINGS, ids=lambda p: p.name)
def rec(request):
    return request.param


@pytest.fixture(scope="module")
def lc(rec):
    return lifecycle.read(rec)


@pytest.fixture(scope="module")
def events(lc):
    return le.fold(lc, verify_url="/r/{cell}", mode=tv.MODE_REPLAY)


def test_recording_passes_both_contracts(rec):
    """展場開機前跑的就是這一支（`serve_twin.py --check`）。"""
    assert S.check_recording(rec) == []


def test_every_event_says_it_is_a_replay(events):
    assert events and {e["mode"] for e in events} == {tv.MODE_REPLAY}


def test_events_satisfy_the_tv_contract(events):
    assert tv.validate(events) == []


def test_events_do_not_invent_layers_that_do_not_exist(events):
    """`vacant run` **沒有**評審層、**沒有**抽樣稽核層 ⇒ 永遠不發。"""
    kinds = {e["type"] for e in events}
    for never in tv.NEVER:
        assert never not in kinds, never
    # 只能從 run 目錄事後推的兩種，也不在這條路上
    assert "counters" not in kinds and "postaudit" not in kinds


def test_events_never_claim_reputation_routing(events):
    routed = [e for e in events if e["type"] == "routed"]
    assert routed and all(e["basis"] == "random" for e in routed)


def test_events_never_claim_meets_demand(events):
    """把「通過驗收」寫成「符合需求」是這條線上最容易犯、後果最大的一個錯。"""
    vs = [e for e in events if e["type"] == "verdict"]
    assert vs and all(e["meets_demand"] is None for e in vs)


def test_off_arm_has_no_gate_no_receipt_no_verdict(events):
    off = [e for e in events if e.get("arm") == tv.ARM_OFF]
    assert off, "錄影裡沒有 OFF 臂 ⇒ 反事實那一邊沒得播"
    assert not [e for e in off if e["type"] in ("gate_ran", "receipt")]
    assert all(e["accepted"] is None for e in off if e["type"] == "verdict")


def test_on_verdict_is_what_the_run_ended_with(lc, events):
    """ON 的裁決三值原樣過來，不做 `bool()`。"""
    cell_of = {e["run_id"]: e["caller"]["cell_id"]
               for e in lc if e["type"] == "run_started"}
    ended = {cell_of[e["run_id"]]: e for e in lc
             if e["type"] == "run_ended" and e["arm"] == "RUN-ON"}
    seen = 0
    for e in events:
        if e["type"] == "verdict" and e.get("arm") == tv.ARM_ON:
            assert e["accepted"] is ended[e["task_id"]]["accepted"], e["task_id"]
            seen += 1
    assert seen == len(ended)


def test_receipt_event_carries_the_chain_head(lc, events):
    cell_of = {e["run_id"]: e["caller"]["cell_id"]
               for e in lc if e["type"] == "run_started"}
    heads = {cell_of[e["run_id"]]: e["verdict_hash"] for e in lc
             if e["type"] == "run_ended" and e["arm"] == "RUN-ON"}
    recs = [e for e in events if e["type"] == "receipt"]
    assert recs
    for e in recs:
        assert e["chain_head"] == e["sha256"] == heads[e["task_id"]]
        assert e["verify_url"] == "/r/" + e["task_id"], "觀眾要有一個自己重驗的地方"


def test_event_task_ids_are_unique_per_cell(lc, events):
    opened = [e["task_id"] for e in events if e["type"] == "task_opened"]
    ons = [e for e in lc if e["type"] == "run_started" and e["arm"] == "RUN-ON"]
    assert len(set(opened)) == len(opened) == len(ons)


def test_every_cell_reaches_a_verdict(events):
    """電視的 liveAssemble 要等到 verdict 才組得出一筆；少一個就永遠卡著。"""
    opened = {e["task_id"] for e in events if e["type"] == "task_opened"}
    settled = {e["task_id"] for e in events if e["type"] == "verdict"}
    assert opened == settled


def test_dedup_keys_never_collide(events):
    keys = [tv.dedup_key(e) for e in events]
    assert len(set(keys)) == len(keys)


def test_fixture_recording_is_labelled_l_none(rec, events):
    """fixture 錄影的 agent 是腳本（requests_seen＝0）⇒ 每一格都只能是 L-none。

    把它標成別的等級，畫面就會把腳本講成 AI（展場版鐵律 5）。
    """
    if not rec.name.startswith("fixture_"):
        pytest.skip("不是 fixture 錄影")
    lv = {e["evidence"] for e in events if e["type"] == "verdict"}
    assert lv == {"L-none"}
    notes = {e.get("evidence_note") for e in events
             if e["type"] == "verdict" and e.get("arm") == tv.ARM_ON}
    assert all("腳本" in (n or "") for n in notes)


def test_fixture_recording_shows_the_retry_loop(rec, events):
    """備援錄影刻意用 `--retry revise`：閘門 → 回饋 → 再 spawn 一次要看得見。"""
    if not rec.name.startswith("fixture_"):
        pytest.skip("不是 fixture 錄影")
    revised = [e for e in events if e["type"] == "revised"]
    assert revised and all(e["arm"] == tv.ARM_ON for e in revised)
    assert all("VACANT_FEEDBACK" in e["transition"] for e in revised)


def test_validate_has_teeth(events):
    """負控制：契約自檢真的會咬人，不是永遠回空清單。"""
    broken = [dict(e) for e in events]
    broken[0].pop("ts")
    assert tv.validate(broken)
    dupe = [dict(e) for e in events[:2]] + [dict(events[0])]
    assert tv.validate(dupe)
    unknown = [dict(e) for e in events]
    unknown[0]["type"] = "not_a_real_type"
    assert tv.validate(unknown)
    no_mode = [dict(e) for e in events]
    no_mode[3].pop("mode")
    assert tv.validate(no_mode)
    unsettled = [e for e in events if e["type"] != "verdict"]
    assert tv.validate(unsettled)
    assert tv.validate(unsettled, require_settled=False) == []
