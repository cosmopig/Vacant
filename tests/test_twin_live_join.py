"""分身真跑 → 電視那一段接線（2026-09-24，D 線）的可執行判準。

守四件事：

1. **`task_kind` 契約**：`run_twin.py` 的格子是 `code`、`twinagent.py` 的格子是
   `practical`，由 `caller` 帶進 lifecycle、`live_events.Folder` 原樣轉到 `task_opened`；
   caller 沒帶（舊錄影）就**不寫**這個欄位（不替舊資料猜）。
2. **`tv_contract` 規則 11**：分身的自主任務沒有 OFF 臂、沒有閘門、`accepted` 恆 `null`。
   每一條都配負控制（壞掉的事件流真的會被抓到）。
3. **`serve_twin --live` 吃得下只有 ON 一臂、ungated 的格子**：逐臂收尾、切換規則、
   `/state.now` 不套反事實那兩顆鍵的字、收據頁照實說為什麼沒有。
4. **`exhibit_boot.sh` 把 loop 寫的檔與 serve_twin tail 的檔指到同一個**。

⚠ 零模型呼叫：分身那一跑用 `test_twin_agent_run.py` 的假上游＋腳本化 agent。
**這裡的綠燈證明的是接線（中介、事件、契約、切換），不是分身的能力。**
"""
from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys
import time

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ops.exhibit.twin import live_events as le  # noqa: E402
from ops.exhibit.twin import run_twin  # noqa: E402
from ops.exhibit.twin import serve_twin as S  # noqa: E402
from ops.exhibit.twin import tv_contract as tv  # noqa: E402
from ops.exhibit.twin import twinagent, twinlink  # noqa: E402
from ops.exhibit.twin.twinstore import DEFAULT_DB  # noqa: E402
from vacant_network.vrun import lifecycle  # noqa: E402

# 假上游＋腳本化 agent＋store（同一套，不另寫一份）
from test_twin_agent_run import (  # noqa: E402,F401
    DECISION, LETTER, NEED, TRAITS_TEXT, _ingest, env, upstream,
)

BOOT = ROOT / "ops" / "exhibit" / "twin" / "exhibit_boot.sh"
LOOP = ROOT / "ops" / "exhibit" / "twin" / "twin_loop.sh"


def _events(stage) -> list[dict]:
    return [json.loads(x) for x in stage.out.read_text(encoding="utf-8").splitlines()
            if x.strip()]


# ---------------------------------------------------------------------------
# 一、分身真跑一次 → serve_twin --live
# ---------------------------------------------------------------------------

def test_a_twin_run_reaches_the_tv_as_a_one_armed_practical_cell(env, monkeypatch, tmp_path):
    st, cfg = env["store"], env["cfg"]
    sid = _ingest(st, monkeypatch)
    tid = twinagent.public_twin_id(sid)
    # 開機時 live 檔還不存在（Tail 從檔尾讀；之後長出來的才是「正在發生」）
    srv, stage = S.make_server(S.default_recordings(), bind="127.0.0.1", port=0,
                               out=tmp_path / "events.jsonl", dwell=10_000, quiet=True,
                               live=cfg.events_path, live_runs=tmp_path / "no_such_runs",
                               live_idle_s=0.3, live_stale_s=60)
    try:
        stage.tick()
        assert stage.mode() == tv.MODE_REPLAY
        r = twinlink.generate(st, env["upstream"], "m", agent=cfg)
        assert r["generated"] == 1 and r["degraded"] == 0, r
        stage.tick()
        assert stage.live_errors == [], stage.live_errors
        assert stage.mode() == tv.MODE_LIVE
        evs = [e for e in _events(stage) if e["mode"] == tv.MODE_LIVE]
        mine = [e for e in evs if e["task_id"] == tid]
        assert mine, "分身那一跑沒有轉到電視上"

        # ── task_kind 與 join 鍵 ──
        op = [e for e in mine if e["type"] == "task_opened"][0]
        assert op["task_kind"] == tv.KIND_PRACTICAL
        assert op["task_id"] == tid, "電視用 task_id 對 people[].twin_id"
        assert op["prompt"] == twinagent.CALLER_PROMPT
        rt = [e for e in mine if e["type"] == "routed"][0]
        assert rt["basis_note"] == tv.PRACTICAL_BASIS_NOTE

        # ── 只有一臂、沒有閘門、不判 ──
        assert not [e for e in mine if e.get("arm") == tv.ARM_OFF]
        assert not [e for e in mine if e["type"] in ("gate_ran", "revised")]
        v = [e for e in mine if e["type"] == "verdict"][0]
        assert v["accepted"] is None and v["stop_reason"] == "ungated"
        assert v["accepted_note"] == tv.PRACTICAL_ACCEPTED_NOTE
        assert v["blocked_by"] is None
        assert [e for e in mine if e["type"] == "receipt"], "收據拍照常：它有收據"
        assert [e for e in mine if e["type"] == "working"], "每一通經過中介的呼叫都要有 working"

        # ── 整段過電視契約（逐臂收尾：只開了 ON，ON 有 verdict ⇒ 收得了尾）──
        assert tv.validate(evs, require_task_kind=True) == []

        # ── 事件流不帶觀眾原文、不帶 sub_id（撤回刪不到 append-only 的檔）──
        blob = stage.out.read_text(encoding="utf-8")
        for secret in (TRAITS_TEXT, NEED, DECISION, LETTER, sid):
            assert secret not in blob, f"電視事件流裡有 {secret[:10]}"

        # ── /state.now：不套反事實那兩顆鍵的字 ──
        now = stage.state()["now"]
        assert now["cell_id"] == tid and now["task_kind"] == tv.KIND_PRACTICAL
        assert now["side"] is None and now["side_label"] == S.PRACTICAL_SIDE_LABEL
        assert "名字" not in now["side_text"]

        # ── 收據頁：照實說為什麼沒有（不是等 900 秒之後講「run_twin 沒寫完」）──
        assert stage.live_pending == {}, "分身那一格不在 --live-runs 底下，不該等它"
        url, why = stage.receipt_target(tid)
        assert url is None and why == S.PRACTICAL_NO_RECEIPT_PAGE

        # ── 切換規則：閒下來就回輪播 ──
        time.sleep(0.4)
        stage.tick()
        assert stage.mode() == tv.MODE_REPLAY
    finally:
        srv.server_close()


def test_after_withdrawal_the_roster_no_longer_carries_what_the_tv_would_show(env, monkeypatch):
    """電視的 join 靠的是名冊：撤回之後同一個 twin_id 在 people[] 裡 tier＝withdrawn、
    決定與卡全是 null（`never_play_tier`）——事件流拿不掉，名冊這一側一定要拿得掉。"""
    st, cfg = env["store"], env["cfg"]
    sid = _ingest(st, monkeypatch)
    tid = twinagent.public_twin_id(sid)
    twinlink.generate(st, env["upstream"], "m", agent=cfg)
    before = [p for p in twinlink.build_view(st)["people"] if p["twin_id"] == tid]
    # 正控制：撤回前名冊上有他、有決定（不然下面的「沒有」沒意義）
    assert before and before[0]["decision"] == DECISION and before[0]["tier"] != "withdrawn"
    twinlink.withdraw(st, sid)
    view = twinlink.build_view(st)
    after = [p for p in view["people"] if p["twin_id"] == tid]
    assert all(p["tier"] == "withdrawn" and p["decision"] is None and p["card"] is None
               for p in after)
    assert "withdrawn" in view["screen_contract"]["never_play_tier"]
    assert view["screen_contract"]["join_live_events_on"] == "twin_id"
    # 事件流那一側：撤回刪不到（append-only），但裡面本來就沒有他的東西
    text = cfg.events_path.read_text(encoding="utf-8")
    assert tid in text and DECISION not in text and sid not in text


# ---------------------------------------------------------------------------
# 二、task_kind：兩個呼叫端各寫各的，舊錄影不猜
# ---------------------------------------------------------------------------

def test_run_twin_tags_its_cells_as_code(tmp_path):
    out = tmp_path / "b"
    rc = run_twin.main(["--out", str(out), "--fixture", "--residents", "1",
                        "--tasks", "s1_01_addmul", "--sandbox", "none",
                        "--events", str(tmp_path / "lc.jsonl")])
    assert rc == 0
    evs = lifecycle.read(tmp_path / "lc.jsonl")
    kinds = {e["caller"].get("task_kind") for e in evs if e["type"] == "run_started"}
    assert kinds == {"code"}
    tvevs = le.fold(evs, verify_url="/r/{cell}")
    assert {e["task_kind"] for e in tvevs if e["type"] == "task_opened"} == {"code"}
    assert tv.validate(tvevs, require_task_kind=True) == []


def test_an_old_recording_without_task_kind_is_not_given_one():
    """舊錄影（2026-09-24 之前）caller 沒有 task_kind ⇒ task_opened **不寫**這個欄位。"""
    recs = S.default_recordings()
    assert recs, "前提：repo 裡有錄影"
    evs = lifecycle.read(recs[0])
    assert all("task_kind" not in (e.get("caller") or {})
               for e in evs if e["type"] == "run_started"), "前提：那一份是舊錄影"
    tvevs = le.fold(evs, verify_url="/r/{cell}", mode=tv.MODE_REPLAY)
    assert all("task_kind" not in e for e in tvevs if e["type"] == "task_opened")
    # 缺席＝code：舊錄影照舊過契約；但當成「新的東西」驗就要被擋（新錄影必須有）
    assert tv.validate(tvevs) == []
    assert any("沒有 task_kind" in b for b in tv.validate(tvevs, require_task_kind=True))
    assert S.check_recording(recs[0]) == []
    assert S.check_recording(recs[0], require_task_kind=True), \
        "`--check --new` 必須擋下沒有 task_kind 的錄影"


# ---------------------------------------------------------------------------
# 三、tv_contract 規則 11（每一條配負控制）
# ---------------------------------------------------------------------------

def _practical_cell(tid: str = "tw-abc") -> list[dict]:
    """一格合格的分身事件（Folder 轉出來的形狀）。"""
    base = {"task_id": tid, "mode": tv.MODE_LIVE}
    ts = iter(tv.iso(1_790_000_000_000 + i) for i in range(100))
    return [
        {**base, "type": "task_opened", "ts": next(ts), "prompt": "p", "prompt_sha256": "x",
         "evidence": None, "stratum": "twin", "task_kind": tv.KIND_PRACTICAL},
        {**base, "type": "routed", "ts": next(ts), "worker": "MOR-31", "basis": "random"},
        {**base, "type": "working", "ts": next(ts), "arm": "ON", "worker": "MOR-31",
         "attempt": 1, "calls_so_far": 1},
        {**base, "type": "draft_done", "ts": next(ts), "arm": "ON", "worker": "MOR-31",
         "calls_used": 1, "attempt": 1},
        {**base, "type": "verdict", "ts": next(ts), "arm": "ON", "accepted": None,
         "meets_demand": None, "blocked_by": None, "stop_reason": "ungated"},
        {**base, "type": "receipt", "ts": next(ts), "arm": "ON", "sha256": "h",
         "chain_head": "h", "verify_url": "/r/tw-abc"},
    ]


def test_a_well_formed_practical_cell_passes():
    assert tv.validate(_practical_cell(), require_task_kind=True) == []


@pytest.mark.parametrize("mutate,needle", [
    (lambda evs: evs[:4] + [{**evs[3], "type": "gate_ran", "ts": evs[3]["ts"] + "z",
                              "passed": False}] + evs[4:], "gate_ran"),
    (lambda evs: evs + [{**evs[4], "arm": "OFF", "ts": evs[5]["ts"] + "z"}], "OFF 臂"),
    (lambda evs: [dict(e, accepted=False, stop_reason="visible_fail") if e["type"] == "verdict"
                  else e for e in evs], "accepted 不是 null"),
    (lambda evs: [dict(e, stop_reason="visible_pass") if e["type"] == "verdict" else e
                  for e in evs], "stop_reason"),
    (lambda evs: [dict(e, task_kind="PRACTICAL") if e["type"] == "task_opened" else e
                  for e in evs], "task_kind 是"),
])
def test_rule_9_bites(mutate, needle):
    bad = tv.validate(mutate(_practical_cell()), require_task_kind=True)
    assert any(needle in b for b in bad), bad


def test_rule_9_is_driven_by_task_kind_negative_control():
    """負控制：同一串有 gate_ran 的事件，**拿掉 task_kind**（當 code）就不觸發規則 11
    ——證明是 task_kind 在決定，不是規則 11 對每一格都亂咬。"""
    evs = _practical_cell()
    evs = evs[:4] + [{**evs[3], "type": "gate_ran", "ts": evs[3]["ts"] + "z",
                      "passed": True, "n_tests": 1, "failed_case": None}] + evs[4:]
    coded = [{k: v for k, v in e.items() if k != "task_kind"} for e in evs]
    assert not [b for b in tv.validate(coded) if "分身的自主任務" in b]
    assert [b for b in tv.validate(evs) if "分身的自主任務" in b]


def test_folder_writes_practical_notes_only_for_practical():
    lc = [{"schema": lifecycle.SCHEMA, "type": "run_started", "run_id": "r", "seq": 1,
           "ts_ms": 1, "task_id": "t", "arm": "RUN-ON", "retry": "none",
           "caller": {"cell_id": "tw-1", "resident": "X", "task_kind": "practical"}},
          {"schema": lifecycle.SCHEMA, "type": "run_ended", "run_id": "r", "seq": 2,
           "ts_ms": 2, "task_id": "t", "arm": "RUN-ON", "stop_reason": "ungated",
           "accepted": None, "requests_seen": 1, "has_receipt": False}]
    out = le.fold(lc, verify_url="/r/{cell}")
    v = [e for e in out if e["type"] == "verdict"][0]
    assert v["accepted_note"] == tv.PRACTICAL_ACCEPTED_NOTE
    lc[0]["caller"]["task_kind"] = "code"
    out = le.fold(lc, verify_url="/r/{cell}")
    v = [e for e in out if e["type"] == "verdict"][0]
    assert "accepted_note" not in v, "題庫格的 ungated 不是「沒有客觀標準」"
    # 口徑：不講信任、不講驗證了它做得好
    for s in (tv.PRACTICAL_ACCEPTED_NOTE, tv.PRACTICAL_BASIS_NOTE):
        assert "信任" not in s and "驗證了" not in s and "沒有閘門" not in s


# ---------------------------------------------------------------------------
# 四、開機腳本：loop 寫的檔 ＝ serve_twin tail 的檔
# ---------------------------------------------------------------------------

def _boot_events(*args, env_extra=None) -> subprocess.CompletedProcess:
    e = {k: v for k, v in os.environ.items()
         if k not in ("VACANT_EVENTS", "VACANT_TWIN_DB")}
    e.update(env_extra or {})
    return subprocess.run(["bash", str(BOOT), *args, "--print-events"],
                          capture_output=True, text=True, env=e, timeout=30)


def test_boot_points_the_loop_and_the_tv_at_the_same_lifecycle_file(monkeypatch):
    r = _boot_events()
    assert r.returncode == 0, r.stderr
    monkeypatch.delenv("VACANT_EVENTS", raising=False)
    # 跟 twinagent.default_events_path 同一個算法（loop 自己不給 --events 時寫的那一個）
    assert pathlib.Path(r.stdout.strip()) == twinagent.default_events_path(
        ROOT / "ops" / "exhibit" / "twin" / "store" / "twinstore.sqlite3")
    r2 = _boot_events(env_extra={"VACANT_EVENTS": "/x/y.jsonl"})
    assert r2.stdout.strip() == "/x/y.jsonl"
    r3 = _boot_events("--live", "runs/a.jsonl")
    assert r3.stdout.strip() == "runs/a.jsonl", "給了 --live ⇒ loop 也寫進那一個"
    r4 = _boot_events("--twin-db", "/d/t.sqlite3")
    assert r4.stdout.strip() == "/d/twin_lifecycle.jsonl"
    r5 = _boot_events("--no-twin")
    assert r5.returncode == 2 and r5.stdout == ""


def test_boot_really_hands_that_path_to_both_sides():
    """`--print-events` 印的那一個，要真的同時交給 serve_twin（--live）與 loop（VACANT_EVENTS）。"""
    s = BOOT.read_text(encoding="utf-8")
    assert 'LIVE_SRC="$TWIN_EVENTS"' in s
    assert '[ -n "$LIVE_SRC" ] && TWIN_ARGS+=(--live "$LIVE_SRC")' in s
    assert 'VACANT_EVENTS="$TWIN_EVENTS"' in s
    # 「一份錄影都沒有」那一道門看的是**人有沒有給 --live**，不是預設補上來的分身檔
    assert '[ -z "$LIVE_GIVEN" ]' in s


def test_twin_loop_honours_vacant_events():
    """loop 那一側：`VACANT_EVENTS` 真的變成 `twinlink loop --events`（正控制：不給就沒有）。"""
    e = {k: v for k, v in os.environ.items() if k != "VACANT_EVENTS"}
    r = subprocess.run(["bash", str(LOOP), "--print-cmd"], capture_output=True, text=True,
                       env=e, timeout=30)
    assert r.returncode == 0 and "--events" not in r.stdout
    e["VACANT_EVENTS"] = "/x/twin_lifecycle.jsonl"
    r = subprocess.run(["bash", str(LOOP), "--print-cmd"], capture_output=True, text=True,
                       env=e, timeout=30)
    assert "--events /x/twin_lifecycle.jsonl" in r.stdout


def test_default_db_matches_the_boot_default():
    """開機腳本寫死的預設庫路徑 ＝ twinstore.DEFAULT_DB（沒設 VACANT_TWIN_DB 時）。"""
    if os.environ.get("VACANT_TWIN_DB"):
        pytest.skip("這台設了 VACANT_TWIN_DB")
    assert DEFAULT_DB == ROOT / "ops" / "exhibit" / "twin" / "store" / "twinstore.sqlite3"
