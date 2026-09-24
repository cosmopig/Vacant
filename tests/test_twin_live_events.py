"""數位分身的唯一一條路：`vacant.lifecycle/1` → `live_events.Folder` → 電視事件。

2026-09-24 人類裁決「刪事後推導，留錄影重播」之後，這一組的承重換了一把尺：
舊版拿**事後推導**（`to_events.py`，已刪）當第二把尺逐欄比；現在拿**收據**當第二把尺。

  · 真跑一批（`run_twin.py --fixture --events`，零模型）→ 錄下 lifecycle
  · `Folder` 轉出電視事件 → 過電視契約（`tv_contract.validate`）
  · 對帳 run 目錄裡**簽了章的那一份**：`receipt.chain_head`＝`run_ended.verdict_hash`
    ＝收據鏈的鏈頭（`verify_receipts.verify_run` 從創世驗到鏈頭）；
    `verdict.accepted`＝鏈上 `ws_verdict` 的 `accepted`（含 `accepted_is_null`）。

收據是簽章覆蓋的東西，事件流不是——所以對帳的方向是「事件要對得上收據」，
不是反過來。⚠ 零模型呼叫：fixture 的 agent 是腳本，`requests_seen`＝0。
"""
from __future__ import annotations

import json
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ops.exhibit.twin import live_events as le                       # noqa: E402
from ops.exhibit.twin import run_twin                                # noqa: E402
from ops.exhibit.twin import tv_contract as tv                       # noqa: E402
from vacant_network.vrun import lifecycle, verify_receipts           # noqa: E402

TASKS = "s1_01_addmul,s1_12_hms"


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


def _fold(batch, mode=tv.MODE_LIVE):
    return le.fold(lifecycle.read(batch / "lifecycle.jsonl"),
                   verify_url="/r/{cell}", mode=mode)


def reconcile(batch: pathlib.Path, events: list[dict]) -> list[str]:
    """電視事件 ↔ 收據，逐格對帳。回問題清單（空＝對得上）。

    ⚠ 第二把尺是**收據**（簽章覆蓋的那一份），不是任何一條事後推導。
    """
    bad: list[str] = []
    cells = sorted(p.name for p in (batch / "runs").iterdir() if p.is_dir())
    for cid in cells:
        run = batch / "runs" / cid
        evs = [e for e in events if e["task_id"] == cid]
        on = [e for e in evs if e.get("arm") == tv.ARM_ON]
        rec = [e for e in on if e["type"] == "receipt"]
        ver = [e for e in on if e["type"] == "verdict"]
        chain = run / "receipts_RUN-ON.ndjson"
        if not chain.exists():
            bad.append(f"{cid}：沒有 ON 的收據鏈")
            continue
        rows = {r["arm"]: r for r in verify_receipts.verify_run(run)}
        v = rows.get("RUN-ON") or {}
        if v.get("chain_ok") is not True:
            bad.append(f"{cid}：收據鏈從創世驗不過 {v.get('failures')}")
        if len(rec) != 1 or rec[0]["chain_head"] != v.get("head") \
                or rec[0]["sha256"] != v.get("head"):
            bad.append(f"{cid}：receipt 的鏈頭與收據鏈不同")
        signed = None
        for ln in chain.read_text(encoding="utf-8").splitlines():
            d = json.loads(ln)
            if d["type"] == "ws_verdict":
                p = d["payload"]
                signed = None if p.get("accepted_is_null") else p.get("accepted")
        # `is not`：True／False／None 都是單例，而「沒量」(None) 與「沒過」(False)
        # 用 `!=` 比也分得開——但 `0`／`1` 混進來時 `is` 才擋得住。
        if len(ver) != 1 or ver[0]["accepted"] is not signed:
            bad.append(f"{cid}：verdict.accepted 與簽章那一份的 ws_verdict 不同")
        # OFF 那一臂：沒有收據鏈、事件裡也不准有 receipt／gate_ran
        if (run / "receipts_RUN-OFF.ndjson").exists():
            bad.append(f"{cid}：OFF 臂竟然有收據鏈")
        off = [e for e in evs if e.get("arm") == tv.ARM_OFF]
        if any(e["type"] in ("receipt", "gate_ran") for e in off):
            bad.append(f"{cid}：OFF 臂的事件裡有 receipt／gate_ran")
        if [e["accepted"] for e in off if e["type"] == "verdict"] != [None]:
            bad.append(f"{cid}：OFF 臂的 verdict 不是恰好一筆 accepted=null")
    return bad


def test_lifecycle_stream_from_a_real_batch_is_valid(batch):
    evs = lifecycle.read(batch / "lifecycle.jsonl")
    assert lifecycle.validate_stream(evs) == []
    # 4 格 × 兩臂 ＝ 8 跑，每一跑都有頭有尾
    assert [e["type"] for e in evs].count("run_started") == 8
    assert [e["type"] for e in evs].count("run_ended") == 8


def test_folded_events_pass_the_tv_contract(batch):
    live = _fold(batch)
    assert tv.validate(live) == []
    assert {e["mode"] for e in live} == {tv.MODE_LIVE}


def test_folded_events_reconcile_with_the_signed_receipts(batch):
    """**承重的那一條**：電視上講的，要對得上簽了章的收據。"""
    live = _fold(batch)
    assert reconcile(batch, live) == []
    # 這一批真的有兩種格（不然「對得上」只驗了一半）
    ons = [e["accepted"] for e in live
           if e["type"] == "verdict" and e.get("arm") == tv.ARM_ON]
    assert True in ons and False in ons


def test_reconcile_has_teeth(batch):
    """負控制：把一格的裁決翻過來、把鏈頭改一個字，對帳一定要紅。"""
    live = _fold(batch)
    flipped = [dict(e) for e in live]
    v = next(e for e in flipped if e["type"] == "verdict" and e.get("arm") == tv.ARM_ON)
    v["accepted"] = not v["accepted"]
    assert reconcile(batch, flipped)
    forged = [dict(e) for e in live]
    r = next(e for e in forged if e["type"] == "receipt")
    r["chain_head"] = "0" * len(r["chain_head"])
    assert reconcile(batch, forged)


def test_replay_differs_from_live_only_in_mode(batch):
    """同一份錄影，重播與現場走同一個 Folder：差別**只有** `mode` 那一欄。"""
    a, b = _fold(batch, tv.MODE_LIVE), _fold(batch, tv.MODE_REPLAY)
    assert len(a) == len(b)
    for x, y in zip(a, b):
        assert x["mode"] == tv.MODE_LIVE and y["mode"] == tv.MODE_REPLAY
        assert {k: v for k, v in x.items() if k != "mode"} == \
               {k: v for k, v in y.items() if k != "mode"}


def test_revise_batch_really_has_the_loop(batch):
    live = _fold(batch)
    types = [e["type"] for e in live]
    evs = lifecycle.read(batch / "lifecycle.jsonl")
    if any(e.get("retry") == "revise" for e in evs if e["type"] == "run_started"):
        assert "revised" in types
        assert any(e["type"] == "feedback_ready" for e in evs)
        # 用了幾次嘗試，ON 就要有幾個 gate_ran、少一個 revised（以 run_ended 為準）
        for end in (e for e in evs if e["type"] == "run_ended" and e["arm"] == "RUN-ON"):
            start = next(e for e in evs if e["type"] == "run_started"
                         and e["run_id"] == end["run_id"])
            cid = start["caller"]["cell_id"]
            mine = [e for e in live if e["task_id"] == cid and e.get("arm") == tv.ARM_ON]
            n = end["attempts_used"]
            assert sum(e["type"] == "gate_ran" for e in mine) == n, cid
            assert sum(e["type"] == "revised" for e in mine) == n - 1, cid
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


def test_zero_model_calls_means_zero_working_events(batch):
    """fixture 一通模型都沒打 ⇒ 一筆 `working` 都不准有（沒發生就不發）。"""
    assert not [e for e in _fold(batch) if e["type"] == "working"]


def test_schema_mismatch_is_loud():
    with pytest.raises(le.SchemaMismatch):
        le.fold([{"schema": "vacant.lifecycle/2", "type": "run_started",
                  "run_id": "r", "ts_ms": 0, "task_id": "t", "arm": "RUN-ON"}],
                verify_url="")


def test_folder_refuses_an_unknown_mode():
    with pytest.raises(ValueError):
        le.Folder(verify_url="", mode="simulated")


def _no_ts(e: dict) -> dict:
    return {k: v for k, v in e.items() if k != "ts"}


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
    want = _fold(batch)
    assert [_no_ts(e) for e in got] == [_no_ts(e) for e in want]


def test_tail_from_end_ignores_what_was_already_there(batch, tmp_path):
    """`--live` 從檔尾開始：檔案裡**已經有的**不是「正在發生」。"""
    src = tmp_path / "lc.jsonl"
    text = (batch / "lifecycle.jsonl").read_text(encoding="utf-8")
    src.write_text(text, encoding="utf-8")
    t = le.Tail(src, start_at_end=True)
    assert t.poll() == []
    with src.open("a", encoding="utf-8") as fh:
        fh.write(text.splitlines(True)[0])
    got = t.poll()
    assert len(got) == 1 and got[0]["type"] == "run_started"
    assert t.open_runs == {got[0]["run_id"]}
