"""展場機那一支伺服器的可執行判準（`ops/exhibit/twin/serve_twin.py`）。

守的是 `decisions/DECISION_20260919_TWIN_LIVE.md` 的接口契約與四條展場鐵律，
以及 2026-09-24「刪事後推導，留錄影重播」之後的新形狀：

- 資料來源只有 lifecycle：`--recording`（重播）與 `--live`（真跑）。
- 秒級：一次 POST /control ⇒ 那一格馬上開播（第一筆當場寫出），其餘照錄影的
  相對間隔、壓縮進 `dwell×REPLAY_FILL` 秒內播完；壓縮比落在 `/state.replay`。
- 每一筆事件都帶 `mode`，重播寫死 `"replay"`（畫面上要講明）。
- 有真跑就先播真跑、輪播暫停；真跑閒下來回到錄影（切換規則在模組 docstring）。
- 無人值守：沒人按就自己輪播；一圈播完截檔（去重集合不會無限長）。
- 一格沒收尾不准卡死整批（D2）：過不了契約自檢的格子跳過並記下原因。
- 收據頁只認得資料包那一批：鏈頭對不上就 404 並講明，不帶觀眾去看另一跑。

以及一條口徑紅線：**這一支不得宣告任何驗證結果**（面板不是信任來源）。
⚠ 零模型呼叫：用 `run_twin.py --fixture`（腳本化 agent）現錄一份小錄影。
"""
from __future__ import annotations

import json
import pathlib
import sys
import threading
import time
import urllib.error
import urllib.request

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ops.exhibit.twin import pack as packlib  # noqa: E402
from ops.exhibit.twin import run_twin  # noqa: E402
from ops.exhibit.twin import serve_twin as S  # noqa: E402
from ops.exhibit.twin import tv_contract as tv  # noqa: E402
from vacant_network.vrun import lifecycle  # noqa: E402

TWIN_PACK = ROOT / "ops" / "exhibit" / "twin" / "twin_pack.json"


@pytest.fixture(scope="module")
def batch(tmp_path_factory) -> pathlib.Path:
    """現錄一份小錄影：1 位居民 × 2 題 × 兩份題面＝4 格（2 對），ON 用 revise。"""
    out = tmp_path_factory.mktemp("serve_twin_batch")
    rc = run_twin.main(["--out", str(out), "--fixture", "--residents", "1",
                        "--tasks", "s1_01_addmul,s1_12_hms", "--sandbox", "none",
                        "--retry", "revise", "--max-attempts", "2",
                        "--events", str(out / "lifecycle.jsonl")])
    assert rc == 0
    return out


@pytest.fixture(scope="module")
def recs(batch) -> list[pathlib.Path]:
    return [batch / "lifecycle.jsonl"]


@pytest.fixture(scope="module")
def rpack(batch) -> dict:
    """**同一批**的收據資料包（收據頁的那一份）：鏈頭與錄影對得上。"""
    return packlib.build(batch)


def mk(recs, tmp_path, **kw):
    kw.setdefault("dwell", 10_000)
    kw.setdefault("quiet", True)
    return S.make_server(recs, bind="127.0.0.1", port=0,
                         out=tmp_path / "events.jsonl", **kw)


def read_events(stage) -> list[dict]:
    """讀事件檔之前先快轉：重播是照時間一筆一筆寫的，測試不等那一段。"""
    stage.flush()
    return [json.loads(x) for x in stage.out.read_text(encoding="utf-8").splitlines()
            if x.strip()]


class Client:
    def __init__(self, base: str):
        self.base = base

    def get(self, path: str):
        with urllib.request.urlopen(self.base + path) as r:
            return r.status, dict(r.headers), r.read()

    def get_json(self, path: str):
        return json.loads(self.get(path)[2])

    def post(self, obj: dict):
        req = urllib.request.Request(
            self.base + "/control", data=json.dumps(obj).encode("utf-8"),
            headers={"content-type": "application/json"})
        try:
            with urllib.request.urlopen(req) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())

    def location(self, path: str):
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, *a, **k):
                return None
        op = urllib.request.build_opener(NoRedirect)
        try:
            with op.open(self.base + path) as r:
                return r.status, r.headers.get("Location")
        except urllib.error.HTTPError as e:
            return e.code, e.headers.get("Location")


@pytest.fixture
def server(recs, rpack, tmp_path):
    # dwell 很大 ⇒ 測試期間不會有輪播插進來把斷言弄亂。輪播本身另外測。
    srv, stage = mk(recs, tmp_path, pack=rpack)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield Client(f"http://127.0.0.1:{srv.server_address[1]}"), stage, stage.out
    srv.shutdown()
    srv.server_close()


# ── 錄影 ────────────────────────────────────────────────────────
def test_recording_is_split_into_cells_by_caller(recs):
    cells, info = S.load_recordings(recs)
    assert info[0]["accepted"] and info[0]["problems"] == []
    assert len(cells) == 4
    for c in cells.values():
        # 一格＝ON 那一跑＋OFF 那一跑的區段
        starts = [e for e in c["segment"] if e["type"] == "run_started"]
        assert [e["arm"] for e in starts] == ["RUN-ON", "RUN-OFF"]
        assert c["segment"][-1]["type"] == "run_ended"
        assert c["evidence"] == "L-none"            # fixture：腳本寫的
        assert c["side"] == ("pc" if c["cell_id"].endswith("__pc") else "held")


def test_exit_code_follows_the_launcher_rule(batch, recs):
    """`/state.cells[*].exit_code` 由 `run_ended` 推，規則與 `launcher.exit_code` 同一條。"""
    from vacant_network.vrun import launcher
    assert (S.EXIT_ACCEPTED, S.EXIT_REFUSED, S.EXIT_VOID) == \
        (launcher.EXIT_ACCEPTED, launcher.EXIT_REFUSED, launcher.EXIT_VOID)
    cells, _ = S.load_recordings(recs)
    for cid, c in cells.items():
        meta = json.loads((batch / "runs" / cid / "twin_cell.json").read_text("utf-8"))
        assert c["exit_code"] == meta["exit_code"], cid
    assert S.exit_code_of(None) is None, "錄影斷在半路 ⇒ 不猜"
    assert S.exit_code_of({"infra_void": "x", "refused": False}) == S.EXIT_VOID


def test_a_broken_recording_is_refused_whole(recs, tmp_path):
    """一行壞掉 ⇒ 整份不收（挑著用等於替它背書）。"""
    lines = recs[0].read_text(encoding="utf-8").splitlines(True)
    d = json.loads(lines[2])
    d["seq"] = 99
    lines[2] = json.dumps(d) + "\n"
    bad = tmp_path / "broken.jsonl"
    bad.write_text("".join(lines), encoding="utf-8")
    cells, info = S.load_recordings([bad])
    assert cells == {} and info[0]["accepted"] is False and info[0]["problems"]
    assert S.check_recording(bad)
    assert S.main(["--check", "--recording", str(bad)]) == 1
    assert S.main(["--check", "--recording", str(recs[0])]) == 0


def test_the_same_cell_in_two_recordings_is_not_merged(recs, tmp_path):
    cells, info = S.load_recordings([recs[0], recs[0]])
    assert len(cells) == 4
    assert info[1]["cells"] == 0 and info[1]["problems"], "第二份要講明為什麼一格都沒收"


def test_committed_recordings_load_whole(tmp_path):
    """進版控的備援錄影：開箱就能播，而且整批都是 L-none（腳本，不是 AI）。"""
    recs = S.default_recordings()
    if not recs:
        pytest.skip("recordings/ 裡沒有錄影")
    for p in recs:
        assert S.check_recording(p) == [], p.name
    srv, stage = mk(recs, tmp_path)
    try:
        assert all(r["accepted"] for r in stage.recordings)
        assert stage.flat and len(stage.pl.pairs) * 2 == len(stage.flat)
        assert set(stage.evidence_counts()) == {"L-none"}
    finally:
        srv.server_close()


# ── 接口契約 ────────────────────────────────────────────────────
def test_state_has_the_three_buttons(server):
    c, _stage, _out = server
    st = c.get_json("/state")
    actions = [b["action"] for b in st["buttons"]]
    assert actions == ["held", "pc", "tamper"]
    held, pc = st["buttons"][0]["cell_id"], st["buttons"][1]["cell_id"]
    assert held.endswith("__held") and pc.endswith("__pc")
    assert held[:-len("__held")] == pc[:-len("__pc")]


def test_control_appends_exactly_that_cell(server):
    c, stage, _out = server
    st = c.get_json("/state")
    held = st["buttons"][0]["cell_id"]
    code, res = c.post({"action": "held"})
    assert code == 200 and res["ok"] and res["now"]["cell_id"] == held
    # 秒級：第一筆**當場**就在檔案裡（不等錄影的相對間隔）
    first = [json.loads(x) for x in stage.out.read_text("utf-8").splitlines() if x.strip()]
    assert first and first[0]["type"] == "task_opened"
    evs = read_events(stage)
    assert {e["task_id"] for e in evs} == {held}
    assert any(e["type"] == "verdict" for e in evs)


def test_every_replayed_event_says_replay(server):
    c, stage, _out = server
    c.post({"action": "held"})
    c.post({"action": "pc"})
    evs = read_events(stage)
    assert evs and {e["mode"] for e in evs} == {tv.MODE_REPLAY}
    assert tv.validate(evs) == []
    assert c.get_json("/state")["mode"] == tv.MODE_REPLAY


def test_both_sides_of_one_pair_are_playable(server):
    c, stage, _out = server
    st = c.get_json("/state")
    held, pc = st["buttons"][0]["cell_id"], st["buttons"][1]["cell_id"]
    c.post({"action": "held"})
    c.post({"action": "pc"})
    evs = read_events(stage)
    ids = [e["task_id"] for e in evs if e["type"] == "task_opened"]
    assert ids == [held, pc]

    def on_verdict(tid):
        return next(e for e in evs if e["type"] == "verdict"
                    and e["task_id"] == tid and e.get("arm") == "ON")
    assert on_verdict(held)["accepted"] is False
    assert on_verdict(pc)["accepted"] is True
    for e in evs:
        if e["type"] == "verdict" and e.get("arm") == "OFF":
            assert e["accepted"] is None


def test_switching_cells_finishes_the_previous_one_first(server):
    """換格之前上一格要**寫完**：開了沒 verdict 的格子會讓電視的佇列卡死。"""
    c, stage, _out = server
    c.post({"action": "held"})
    assert stage.pending, "前提：上一格還有沒寫出去的事件"
    c.post({"action": "pc"})
    evs = read_events(stage)
    opened = [e["task_id"] for e in evs if e["type"] == "task_opened"]
    for tid in opened:
        assert any(e["type"] == "verdict" and e["task_id"] == tid for e in evs), tid
    assert tv.validate(evs) == []


def test_events_are_deduplicable_by_the_tv_key(server):
    c, stage, _out = server
    for _ in range(4):
        c.post({"action": "held"})
        c.post({"action": "pc"})
    evs = read_events(stage)
    keys = [tv.dedup_key(e) for e in evs]
    assert len(set(keys)) == len(keys)


def test_per_cell_receipt_redirect(server):
    """C4：每一格指到自己那一頁；收據頁認得那一格（鏈頭對得上）才轉過去。"""
    c, stage, _out = server
    cid = sorted(stage.pl.cells)[0]
    code, loc = c.location(f"/r/{cid}")
    assert code == 302 and loc == f"/viewer.html#cell={cid}"
    code, loc = c.location(f"/r/{cid}?tamper=1")
    assert loc == f"/viewer.html#cell={cid}&tamper=1"
    from urllib.parse import quote
    assert c.location("/r/" + quote("沒有這一格"))[0] == 404


def test_receipt_page_is_not_offered_for_a_different_run(recs, tmp_path):
    """**誠實邊界 2**：錄影與收據頁共用 cell_id、但鏈不同 ⇒ 404 並講明。

    真實情境：fixture 錄影與 54 格 L-real 資料包的 cell_id 一模一樣。
    沒有這一條，觀眾掃了收據會看到**另一跑**的鏈，而且驗得過。
    """
    if not TWIN_PACK.exists():
        pytest.skip("沒有 twin_pack.json")
    other = json.loads(TWIN_PACK.read_text(encoding="utf-8"))
    srv, stage = mk(recs, tmp_path, pack=other)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        c = Client(f"http://127.0.0.1:{srv.server_address[1]}")
        cid = sorted(stage.pl.cells)[0]
        assert cid in stage.receipts, "前提：兩邊的 cell_id 真的撞在一起"
        code, _loc = c.location(f"/r/{cid}")
        assert code == 404
        why = stage.receipt_why_not(cid)
        assert why and "另一跑" in why
        stage.advance()
        assert stage.press("tamper")["ok"] is False, "沒有對得上的收據就沒有東西可以翻"
        assert stage.state()["now"]["receipt_available"] is False
    finally:
        srv.shutdown(); srv.server_close()


def test_receipt_url_in_events_is_per_cell(server):
    c, stage, _out = server
    c.post({"action": "held"})
    c.post({"action": "pc"})
    rec = [e for e in read_events(stage) if e["type"] == "receipt"]
    assert len(rec) == 2
    assert len({e["verify_url"] for e in rec}) == 2
    for e in rec:
        assert e["verify_url"].endswith("/r/" + e["task_id"])


def test_cors_header_is_present(server):
    """電視在另一個埠（run.sh 的 8420）；沒有這個標頭就一個字都拿不到。"""
    c, _stage, _out = server
    for path in ("/state", "/live/events.jsonl"):
        _code, headers, _body = c.get(path)
        assert headers.get("Access-Control-Allow-Origin") == "*"


def test_viewer_and_phone_are_served(server):
    c, _stage, _out = server
    for path, needle in (("/viewer.html", b"twin-pack"),
                         ("/phone.html", b"charset=\"utf-8\"")):
        code, headers, body = c.get(path)
        assert code == 200
        assert "text/html" in headers["Content-Type"]
        assert needle in body


# ── 重播的節奏 ──────────────────────────────────────────────────
def _stretched(recs, tmp_path, factor=1000) -> pathlib.Path:
    """把錄影裡**每一格內部**的間隔拉長 factor 倍（模擬真模型一題一兩分鐘）。"""
    evs = lifecycle.read(recs[0])
    cell_of, t0 = {}, {}
    for e in evs:
        if e["type"] == "run_started":
            cell_of[e["run_id"]] = e["caller"]["cell_id"]
        cid = cell_of[e["run_id"]]
        t0.setdefault(cid, e["ts_ms"])
        e["ts_ms"] = t0[cid] + (e["ts_ms"] - t0[cid]) * factor
    p = tmp_path / "stretched.jsonl"
    p.write_text("".join(json.dumps(e) + "\n" for e in evs), encoding="utf-8")
    assert lifecycle.validate_stream(lifecycle.read(p)) == []
    return p


def test_replay_keeps_relative_timing_but_fits_in_the_dwell(recs, tmp_path):
    """一格錄影跨度 ~1000 秒 ⇒ 壓進 dwell×REPLAY_FILL；壓縮比落在 /state。"""
    dwell = 1.0
    srv, stage = mk([_stretched(recs, tmp_path)], tmp_path, dwell=dwell)
    try:
        t_start_ms = S.now_ms()
        res = stage.advance()
        assert res["ok"]
        rp = stage.state()["replay"]
        assert rp["span_s"] > 100, "前提：錄影真的很長"
        assert rp["compress"] < 0.01 and rp["speedup"] > 100
        assert rp["played_span_s"] <= rp["budget_s"] + 1e-6
        assert rp["budget_s"] == pytest.approx(dwell * S.REPLAY_FILL)
        # 一開始只寫出一部分（照相對時間，不是一次倒完）
        n0 = len(stage.out.read_text("utf-8").splitlines())
        assert 0 < n0 < rp["events"]
        deadline = time.monotonic() + dwell * S.REPLAY_FILL + 1.0
        while stage.pending and time.monotonic() < deadline:
            stage.pump()
            time.sleep(0.02)
        assert not stage.pending, "播出跨度超過了 dwell"
        evs = [json.loads(x) for x in stage.out.read_text("utf-8").splitlines()]
        assert len(evs) == rp["events"]
        # ts 是**重播當下的牆鐘**，不是錄影當時的
        assert evs[0]["ts"] >= tv.iso(t_start_ms)
        assert tv.validate(evs) == []
    finally:
        srv.server_close()


def test_a_short_recording_is_never_stretched(recs, tmp_path):
    """只壓不拉：錄影本來就比 dwell 短 ⇒ 原速（ratio＝1）。"""
    srv, stage = mk(recs, tmp_path, dwell=60)
    try:
        stage.advance()
        assert stage.replay["compress"] == 1.0
        assert stage.replay["played_span_s"] == stage.replay["span_s"]
    finally:
        srv.server_close()


# ── 真跑優先 ────────────────────────────────────────────────────
def _one_cell_lines(recs) -> list[str]:
    lines = recs[0].read_text(encoding="utf-8").splitlines(True)
    evs = [json.loads(x) for x in lines]
    cid = evs[0]["caller"]["cell_id"]
    runs = {e["run_id"] for e in evs if e["type"] == "run_started"
            and e["caller"]["cell_id"] == cid}
    return [ln for ln, e in zip(lines, evs) if e["run_id"] in runs]


def test_live_takes_over_and_hands_back(recs, tmp_path):
    live = tmp_path / "live_lifecycle.jsonl"
    live.write_text(recs[0].read_text(encoding="utf-8"), encoding="utf-8")  # 舊的東西
    srv, stage = mk(recs, tmp_path, live=live, live_idle_s=0.3, live_stale_s=60)
    try:
        # 開機時檔案裡已經有的不是「正在發生」
        stage.tick()
        assert stage.mode() == tv.MODE_REPLAY
        stage.advance()
        replay_cell = stage.now["cell_id"]
        assert stage.pending, "前提：重播那一格還沒播完"
        # ── 真跑來了 ──
        with live.open("a", encoding="utf-8") as fh:
            fh.writelines(_one_cell_lines(recs))
        stage.tick()
        assert stage.mode() == tv.MODE_LIVE
        st = stage.state()
        assert st["mode"] == tv.MODE_LIVE and st["live"]["active"] is True
        assert st["now"]["why"] == "live" and st["now"]["mode"] == tv.MODE_LIVE
        evs = [json.loads(x) for x in stage.out.read_text("utf-8").splitlines()]
        modes = [e["mode"] for e in evs]
        first_live = modes.index(tv.MODE_LIVE)
        # 規則 1：重播那一格先快轉寫完（有 verdict），真跑才接上去
        before = evs[:first_live]
        assert any(e["type"] == "verdict" and e["task_id"] == replay_cell
                   for e in before)
        assert all(m == tv.MODE_LIVE for m in modes[first_live:])
        assert tv.validate(evs) == []
        # 規則 3：真跑期間輪播暫停、導播鍵講明
        res = stage.press("held")
        assert res["ok"] is False and "真跑" in res["error"]
        n = stage.n_emitted
        stage.deadline = 0
        stage.tick()
        assert stage.n_emitted == n, "真跑期間輪播不准往前走"
        # 規則 4：閒下來 ⇒ 回到錄影輪播
        time.sleep(0.4)
        stage.tick()
        assert stage.mode() == tv.MODE_REPLAY
        assert stage.n_emitted == n + 1 and stage.now["mode"] == tv.MODE_REPLAY
        assert stage.press("pc")["ok"] is True
    finally:
        srv.server_close()


def test_an_open_live_run_holds_until_it_goes_stale(recs, tmp_path):
    live = tmp_path / "live.jsonl"
    live.write_text("", encoding="utf-8")
    srv, stage = mk(recs, tmp_path, live=live, live_idle_s=0.1, live_stale_s=0.6)
    try:
        with live.open("a", encoding="utf-8") as fh:
            fh.write(_one_cell_lines(recs)[0])      # 只有 run_started
        stage.tick()
        time.sleep(0.3)                             # 過了 idle，但那一跑還開著
        assert stage.live_active() is True
        time.sleep(0.4)                             # 過了 stale ⇒ 當它死了
        assert stage.live_active() is False
    finally:
        srv.server_close()


# ── 無人值守 ────────────────────────────────────────────────────
def test_autoplay_walks_pairs_and_truncates_each_lap(recs, tmp_path):
    """沒人按就自己播；一圈播完截檔（D3：檔案不會一整天無限長）。"""
    srv, stage = mk(recs, tmp_path)
    try:
        seen = []
        for _ in range(len(stage.flat)):
            res = stage.advance()
            seen.append(res["now"]["cell_id"])
        assert len(set(seen)) == len(stage.pl.cells)      # 一圈把每一格都播到
        assert stage.laps == 0
        stage.flush()      # 展場上 dwell > 播出跨度，換圈時上一格早就寫完了
        n_before = len(stage.out.read_text("utf-8").splitlines())
        assert n_before > 0
        before_ts = stage.last_ts_ms
        first_of_lap2 = stage.advance()["now"]["cell_id"]
        assert stage.laps == 1
        evs = read_events(stage)
        assert 0 < len(evs) < n_before
        assert {e["task_id"] for e in evs} == {first_of_lap2}
        assert stage.last_ts_ms > before_ts             # 截檔不會讓電視重播舊的
    finally:
        srv.server_close()


def test_truncation_waits_if_the_last_cell_is_still_playing(recs, tmp_path):
    """上一格還沒寫完就換圈 ⇒ 先快轉寫完、這一圈**不截**（截了電視那一格等不到收尾）。"""
    srv, stage = mk(recs, tmp_path)
    try:
        for _ in range(len(stage.flat)):
            stage.advance()
        assert stage.pending
        last = stage.now["cell_id"]
        stage.advance()
        assert stage.laps == 1
        evs = read_events(stage)
        assert any(e["type"] == "verdict" and e["task_id"] == last for e in evs)
    finally:
        srv.server_close()


def _drop_on_verdict(recs, tmp_path) -> tuple[pathlib.Path, str]:
    """錄影斷在半路：第一格 ON 那一跑沒有 `run_ended`（lifecycle 契約照樣合格）。"""
    evs = lifecycle.read(recs[0])
    cid = evs[0]["caller"]["cell_id"]
    on_run = evs[0]["run_id"]
    kept = [e for e in evs if not (e["run_id"] == on_run and e["type"] == "run_ended")]
    p = tmp_path / "cut.jsonl"
    p.write_text("".join(json.dumps(e) + "\n" for e in kept), encoding="utf-8")
    assert lifecycle.validate_stream(kept) == []
    return p, cid


def test_a_cell_that_never_settles_is_skipped_not_stuck(recs, tmp_path):
    """D2：錄影斷在半路那一格收不了尾。一格收不了尾不准卡死整個佇列。"""
    p, bad = _drop_on_verdict(recs, tmp_path)
    srv, stage = mk([p], tmp_path)
    try:
        played = []
        for _ in range(len(stage.flat)):
            res = stage.advance()
            if res.get("ok"):
                played.append(res["now"]["cell_id"])
        assert bad not in played
        assert len(played) == len(stage.pl.cells) - 1           # 其餘照播
        assert [s["cell_id"] for s in stage.skipped] == [bad]   # 說得出是哪一格
        assert stage.skipped[0]["reason"]
        assert tv.validate(read_events(stage)) == []
        # 同一格再被跳過一次：不重複堆一筆，而是記次數
        for _ in range(len(stage.flat)):
            stage.advance()
        assert [s["cell_id"] for s in stage.skipped] == [bad]
        assert stage.skipped[0]["times"] == 2
        # 那一格的退出碼是「不知道」，不是猜一個
        assert stage.pl.cells[bad]["exit_code"] is None
    finally:
        srv.server_close()


def test_skipped_cells_show_up_in_state(recs, tmp_path):
    p, bad = _drop_on_verdict(recs, tmp_path)
    srv, stage = mk([p], tmp_path)
    try:
        stage._seek([i for i, pr in enumerate(stage.pl.pairs)
                     if bad in (pr["held"], pr["pc"])][0])
        while stage.flat[stage.cursor][1] != (
                "held" if bad.endswith("__held") else "pc"):
            stage.cursor += 1
        stage.advance()
        st = stage.state()
        assert st["skipped"] and st["skipped"][0]["reason"]
        assert st["now"] is None                      # 沒收尾的格子不准變成「正在演」
    finally:
        srv.server_close()


# ── 口徑紅線 ────────────────────────────────────────────────────
def test_tamper_does_not_claim_any_verification_result(server):
    """「翻一個位元」只交出網址。翻、重算、看簽章紅，都在觀眾自己的瀏覽器裡。"""
    c, _stage, _out = server
    c.post({"action": "held"})
    _code, res = c.post({"action": "tamper"})
    tam = res["tamper"]
    assert tam["url"].endswith("?tamper=1")
    joined = json.dumps(res, ensure_ascii=False)
    for banned in ("簽章對不上", "驗證通過", "驗過了", "已驗證"):
        assert banned not in joined
    assert "沒有驗" in tam["note"]


def test_state_never_says_trust(server):
    """展場口徑：用「可究責性 / 讓依賴有根據」，不要用「信任」。"""
    c, _stage, _out = server
    text = json.dumps(c.get_json("/state"), ensure_ascii=False)
    assert "信任" not in text
    phone = (ROOT / "ops" / "exhibit" / "twin" / "phone.html").read_text(encoding="utf-8")
    assert "信任" not in phone


def test_state_says_it_is_a_replay_in_words(server):
    """`mode` 是給電視的；`honesty` 是給人讀的——兩邊都要講是重播。"""
    c, _stage, _out = server
    st = c.get_json("/state")
    assert st["mode"] == "replay"
    assert "重播" in st["honesty"][0]
    assert "AI 真的動手過" not in json.dumps(st, ensure_ascii=False), \
        "fixture 錄影是腳本寫的，這句話對它是假的"


def test_no_model_call_anywhere_in_this_path(server):
    """展場鐵律：重播零模型呼叫。事件這條線上的三支連出網的能力都不該有。"""
    for name in ("serve_twin.py", "live_events.py", "tv_contract.py"):
        src = (ROOT / "ops" / "exhibit" / "twin" / name).read_text(encoding="utf-8")
        for banned in ("import requests", "urllib.request", "httpx",
                       "socket.create_connection", "openai", "anthropic"):
            assert banned not in src, (name, banned)


def test_the_posthoc_path_is_gone():
    """人類裁決（2026-09-24）：只剩 lifecycle 一條路。事後推導那一支不准回來。"""
    assert not (ROOT / "ops" / "exhibit" / "twin" / "to_events.py").exists()
    import re
    imp = re.compile(r"^\s*(from\s+\S+\s+)?import\s+.*\bto_events\b", re.M)
    for name in ("serve_twin.py", "live_events.py", "tv_contract.py"):
        src = (ROOT / "ops" / "exhibit" / "twin" / name).read_text(encoding="utf-8")
        assert not imp.search(src), name
        assert "events_for_cell(" not in src, name
    # 正控制：那條 regex 真的抓得到舊的 import 形狀（不然上面永遠是綠的）
    assert imp.search("from ops.exhibit.twin import to_events as tolib")
    assert imp.search("    from ops.exhibit.twin import pack, to_events")


def test_phone_page_has_no_external_resource():
    """離線：手機頁不准連任何外部資源（展場沒有網路）。"""
    import re
    html = (ROOT / "ops" / "exhibit" / "twin" / "phone.html").read_text(encoding="utf-8")
    assert '<meta charset="utf-8">' in html
    for m in re.finditer(r'(?:src|href)\s*=\s*"([^"]+)"', html):
        u = m.group(1)
        assert not u.startswith(("http://", "https://", "//")), u
    assert "fonts.googleapis" not in html


def test_phone_press_moves_the_autoplay_cursor(recs, tmp_path):
    """人放手之後接下去播的是下一格，不是又回到他剛剛看過的那一格。"""
    srv, stage = mk(recs, tmp_path)
    try:
        stage.press("pc")                       # 手機把第 0 對的「寫明」那邊叫上來
        nxt = stage.advance()["now"]["cell_id"]  # 放手之後輪播接下去
        assert nxt == stage.pl.pair(1)["held"]
    finally:
        srv.server_close()


def test_phone_node_check_is_runnable_offline():
    """手機頁那一段判準有自己的 node check，而且離線也跑得過。"""
    import shutil
    import subprocess
    if not shutil.which("node"):
        pytest.skip("沒有 node")
    r = subprocess.run(
        ["node", str(ROOT / "ops" / "exhibit" / "twin" / "phone_node_check.mjs")],
        capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "全部通過" in r.stdout


# ── 翻位元的狀態會自己過期 ──────────────────────────────────────
def test_tamper_clears_when_the_tv_moves_on(recs, rpack, tmp_path):
    """實測抓到的謊：**舊狀態不會清**（第一個觀眾按完走掉，那行字留 4 分半）。"""
    srv, stage = mk(recs, tmp_path, pack=rpack)
    try:
        stage.advance()
        first = stage.now["cell_id"]
        assert stage.press("tamper")["ok"]
        assert stage.tamper["cell_id"] == first
        assert stage.state()["tamper"]["cell_id"] == first
        stage.advance()
        assert stage.now["cell_id"] != first
        assert stage.tamper is None
        assert stage.state()["tamper"] is None
    finally:
        srv.server_close()


def test_tamper_expires_on_its_own(recs, rpack, tmp_path):
    srv, stage = mk(recs, tmp_path, pack=rpack)
    try:
        stage.advance()
        stage.press("tamper")
        assert stage.state()["tamper"] is not None
        stage.tamper_mono -= S.TAMPER_TTL_S + 1
        assert stage.state()["tamper"] is None
    finally:
        srv.server_close()


def test_tamper_state_always_matches_the_cell_on_screen(recs, rpack, tmp_path):
    """`/state` 給出去的 tamper，`cell_id` 必定等於 `now.cell_id`（或為 None）。"""
    srv, stage = mk(recs, tmp_path, pack=rpack)
    try:
        for k in range(len(stage.flat)):
            stage.advance()
            if k % 3 == 0:
                stage.press("tamper")
            st = stage.state()
            if st["tamper"]:
                assert st["tamper"]["cell_id"] == st["now"]["cell_id"], k
    finally:
        srv.server_close()


def test_now_carries_why_so_the_tv_can_tell_a_press_from_autoplay(recs, tmp_path):
    srv, stage = mk(recs, tmp_path)
    try:
        assert stage.advance()["now"]["why"] == "autoplay"
        assert stage.press("held")["now"]["why"] == "phone"
        assert stage.press("next")["now"]["why"] == "autoplay"   # next ⇒ 走排程
        assert stage.state()["now"]["why"] in ("autoplay", "phone")
    finally:
        srv.server_close()


# ── QR 一定要指到手機連得到的地方 ───────────────────────────────
def test_qr_encodes_the_runtime_phone_url(recs, tmp_path):
    """**展場當天最會壞的一格。**

    舊的 `world3/qr.png` 是 2026-08-30 的靜態佔位圖（比 `phone.html` 早三個星期），
    而 `--bind 0.0.0.0` 之後手機要連的是展場那台機器的區網 IP、每次開機可能不同。
    ⇒ QR 的內容必須是**執行期** `base_url` 算出來的那一個網址。
    """
    import sys as _sys
    _sys.path.insert(0, str(ROOT))
    from ops.exhibit.twin import qr as qrlib
    out = tmp_path / "ev.jsonl"
    srv, stage = S.make_server(recs, bind="127.0.0.1", port=0, out=out, dwell=10_000,
                               quiet=True, base_url="http://192.168.1.23:8899")
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        c = Client(f"http://127.0.0.1:{srv.server_address[1]}")
        st = c.get_json("/state")
        assert st["phone_url"] == "http://192.168.1.23:8899/phone.html"
        assert "127.0.0.1" not in st["phone_url"]
        code, headers, body = c.get("/qr.png")
        assert code == 200 and headers["Content-Type"] == "image/png"
        assert body[:8] == b"\x89PNG\r\n\x1a\n"
        # ⚠ **這裡不是 `phone_url`。** `make_server` 的 `visitor_url` 有預設值
        # （`DEFAULT_VISITOR_URL`），而 `qr_target()` 一旦設了 visitor_url 就回它——
        # 觀眾掃的是**公網那一頁**，不是這台機器的導播頁，而且**刻意不附 token**
        # （附上去等於把展場的控制 token 印在一張誰都能拍的圖上）。
        # 2026-09-22：舊斷言寫 `phone_url`，在 visitor_url 有預設值之後就一直紅，
        # 而它是這個檔案裡唯一的紅 ⇒ 很容易被當成「本來就紅」略過。
        # 產品是對的、斷言過期了。
        assert body == qrlib.to_png(stage.qr_target(with_token=False), scale=8)
        assert stage.qr_target(with_token=False) == stage.visitor_url
        # token 不准出現在誰都能拍的那張圖裡（負控制的另一半在下一條）
        assert "t=" not in stage.qr_target(with_token=True)
        code, headers, body = c.get("/qr.svg")
        assert code == 200 and "image/svg+xml" in headers["Content-Type"]
        assert b"<svg" in body
    finally:
        srv.shutdown()
        srv.server_close()


def test_沒有_visitor_url_時_QR_必須是執行期算的(recs, tmp_path):
    """**展場當天最會壞的一格**（原本那條測試守的東西，不能因為預設值改了就丟掉）。

    `vacant_hm/world3/qr.png` 是 2026-08-30 的靜態佔位圖，比 `phone.html` 早三個星期。
    `--bind 0.0.0.0` 之後手機要連的是展場那台機器的**區網 IP、每次開機可能不同**。
    烤死的 QR 必然指到錯的地方，而畫面正在叫觀眾「掃一下」。

    ⇒ 明確把 `visitor_url` 關掉（展場沒有公網、或刻意要走區網那一頁）時，
      QR 的內容必須是**執行期** `base_url` 算出來的那一個。
    """
    import sys as _sys
    _sys.path.insert(0, str(ROOT))
    from ops.exhibit.twin import qr as qrlib
    out = tmp_path / "ev2.jsonl"
    srv, stage = S.make_server(recs, bind="127.0.0.1", port=0, out=out, dwell=10_000,
                               quiet=True, base_url="http://192.168.1.23:8899",
                               visitor_url="")          # ← 明確關掉
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        c = Client(f"http://127.0.0.1:{srv.server_address[1]}")
        _code, _h, body = c.get("/qr.png")
        assert body == qrlib.to_png("http://192.168.1.23:8899/phone.html", scale=8)
        assert b"\x89PNG" in body[:8]
        # 負控制：**證明這條測得動**——換一個 base_url 就該畫出不一樣的圖，
        # 否則上面那個相等只是「兩邊都算錯成同一個」。
        assert body != qrlib.to_png("http://10.9.9.9:8899/phone.html", scale=8)
    finally:
        srv.shutdown()
        srv.server_close()


def test_receipt_urls_use_the_same_base_as_the_qr(recs, tmp_path):
    """收據網址與 QR 要指到同一台。兩邊各自組字串遲早會分岔。"""
    out = tmp_path / "ev.jsonl"
    _srv, stage = S.make_server(recs, bind="127.0.0.1", port=0, out=out, dwell=10_000,
                                quiet=True, base_url="http://10.0.0.7:8899")
    res = stage.advance()
    assert res["now"]["receipt_url"].startswith("http://10.0.0.7:8899/r/")
    assert stage.phone_url().startswith("http://10.0.0.7:8899/")


# ── `--token` 預設開啟（DECISION_20260919_EXHIBIT_UNATTENDED.md §一）──────────
#
# 展場的 `exhibit_boot.sh --lan` 把 serve_twin 綁到 0.0.0.0。舊的預設是
# 「`--token` 可選、預設空＝不驗」⇒ 同一個區網（展場 hotspot）上任何人都按得動
# 那台電視。這一組把新的預設釘死。
#
# ⚠ 口徑：token **不是身分驗證**。看得到電視的人都拿得到它（它就印在 QR 裡）。
#   它擋的是「連上同一個 hotspot、但沒站在展件前面」的人。測試只測這件事。

def test_lan_bind_gets_a_token_without_anybody_asking():
    """展場的那一種綁法，沒給 token 也**一定**會有一把。"""
    tok, why = S.resolve_token("0.0.0.0", "", False)
    assert why == "auto"
    assert len(tok) >= 10          # secrets.token_urlsafe(9)
    # 每一次都不一樣（不是寫死的一把）
    assert tok != S.resolve_token("0.0.0.0", "", False)[0]


def test_loopback_bind_stays_tokenless_so_local_dev_is_not_annoying():
    for bind in ("127.0.0.1", "::1", "localhost"):
        assert S.resolve_token(bind, "", False) == ("", "off-loopback")


def test_an_explicit_token_wins_and_no_token_must_be_explicit():
    assert S.resolve_token("0.0.0.0", "abc", False) == ("abc", "given")
    assert S.resolve_token("0.0.0.0", "", True) == ("", "off-explicit")
    # `--token` 與 `--no-token` 同時給：明確給的那把贏（不要靜靜關掉門檻）
    assert S.resolve_token("0.0.0.0", "abc", True) == ("abc", "given")


def _tokened(recs, tmp_path, token="s3cr3t", base="http://192.168.1.23:8899"):
    out = tmp_path / "ev.jsonl"
    srv, stage = S.make_server(recs, bind="127.0.0.1", port=0, out=out,
                               dwell=10_000, quiet=True, token=token,
                               base_url=base)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, stage, Client(f"http://127.0.0.1:{srv.server_address[1]}")


def test_control_is_403_without_the_token_and_200_with_it(recs, tmp_path):
    srv, _stage, c = _tokened(recs, tmp_path)
    try:
        code, res = c.post({"action": "next"})
        assert code == 403 and res["ok"] is False
        code, res = c.post({"action": "next", "token": "wrong"})
        assert code == 403
        code, res = c.post({"action": "next", "token": "s3cr3t"})
        assert code == 200 and res["ok"] is True
    finally:
        srv.shutdown(); srv.server_close()


def test_the_qr_carries_the_token_or_the_phone_cannot_press_anything(recs, tmp_path):
    """QR 是觀眾唯一的入口。token 沒編進去＝掃了進來一顆鍵都按不動。"""
    srv, stage, c = _tokened(recs, tmp_path)
    try:
        assert stage.phone_url() == "http://192.168.1.23:8899/phone.html?t=s3cr3t"
        st = c.get_json("/state")                     # 從 loopback 打（＝電視）
        assert st["phone_url"].endswith("?t=s3cr3t")
        assert st["control_token_required"] is True
    finally:
        srv.shutdown(); srv.server_close()


def test_state_does_not_hand_the_token_to_the_rest_of_the_lan(recs, tmp_path):
    """否則 token 只是**一個 GET 的距離**，等於沒有。

    這裡直接測那個純函數的分流（`with_token=False`）：整合層的判準是
    `venue_check.sh` 第七節，它從這台機器的區網位址真的打一次 `/state`。
    """
    _srv, stage, _c = _tokened(recs, tmp_path)
    try:
        assert "t=" not in stage.phone_url(with_token=False)
        assert "t=" not in stage.state(with_token=False)["phone_url"]
        # 但「有沒有門檻」這件事可以講（不講手機不知道要帶什麼）
        assert stage.state(with_token=False)["control_token_required"] is True
    finally:
        _srv.shutdown(); _srv.server_close()


def test_token_also_accepted_from_query_and_header(recs, tmp_path):
    """少一條，展場當天就是「怎麼按都沒反應」。"""
    srv, _stage, c = _tokened(recs, tmp_path)
    try:
        req = urllib.request.Request(
            c.base + "/control?t=s3cr3t",
            data=json.dumps({"action": "next"}).encode(),
            headers={"content-type": "application/json"})
        with urllib.request.urlopen(req) as r:
            assert r.status == 200
        req = urllib.request.Request(
            c.base + "/control", data=json.dumps({"action": "next"}).encode(),
            headers={"content-type": "application/json",
                     "X-Twin-Token": "s3cr3t"})
        with urllib.request.urlopen(req) as r:
            assert r.status == 200
    finally:
        srv.shutdown(); srv.server_close()


def test_read_only_endpoints_stay_open_because_the_tv_has_no_token(recs, tmp_path):
    """電視、收據頁、事件流都不帶 token。把讀也擋住＝電視自己黑掉。"""
    srv, _stage, c = _tokened(recs, tmp_path)
    try:
        for p in ("/state", "/live/events.jsonl", "/phone.html", "/viewer.html",
                  "/qr.png"):
            assert c.get(p)[0] == 200, p
    finally:
        srv.shutdown(); srv.server_close()


def test_phone_page_sends_the_token_it_was_scanned_with():
    """`phone.html` 一定要從自己的網址讀 `t=` 並帶進 POST。

    漏掉這一行＝伺服器有門檻、手機沒有鑰匙，展場現象是「三顆鍵全部按不動」，
    而畫面上不會說是為什麼。
    """
    html = (ROOT / "ops" / "exhibit" / "twin" / "phone.html").read_text("utf-8")
    assert 'URLSearchParams(location.search).get("t")' in html
    assert "JSON.stringify({ action, token: TOKEN })" in html
    # 403 要講人話（那一定是「上一次開機留下來的分頁」）
    assert "重新掃電視上的 QR" in html


# ── 區網 IP 偵測（DECISION_20260919_EXHIBIT_UNATTENDED.md §五-1）────────────
#
# 這一組守的是一個**真的發生過**的事故形狀：`exhibit_boot.sh` 裡算區網 IP 的
# 那一段在 2026-09-19 之前**從來沒有被執行過**（它只有加 `--lan` 才會跑），
# 只被「讀碼讀出來」寫進紀錄。真的跑下去是 `set -euo pipefail` 底下當場斷掉
# ——**exit 1、一個字都不印**，在 systemd 底下就是無限重啟而 journal 什麼都沒有。
#
# 所以這裡釘的不是「它抓到哪個位址」（那跟跑測試的機器有關，釘不得），
# 而是**離開碼的契約**：0＝抓到並印出來、2＝抓不到但說了為什麼。
# **1 永遠是 bug**：那代表又有一條路徑安靜地斷掉了。

BOOT_SH = ROOT / "ops" / "exhibit" / "twin" / "exhibit_boot.sh"


def _print_host(*args):
    import subprocess
    return subprocess.run(
        ["bash", str(BOOT_SH), "--print-host", *args],
        capture_output=True, text=True, timeout=60)


@pytest.mark.skipif(not BOOT_SH.exists(), reason="沒有 exhibit_boot.sh")
def test_lan_detection_never_dies_silently():
    """**這一條就是那個 bug 的形狀。**

    `exit 1` ＋ 空輸出 ＝ 腳本在某處被 `set -e` 砍掉而沒有人知道。
    fail-closed 的意思是「拒絕啟動**並說明**」，不是「安靜地不見」。
    """
    r = _print_host("--lan")
    assert r.returncode in (0, 2), (
        f"--lan --print-host 回 {r.returncode}（只准 0 或 2）\n"
        f"stdout={r.stdout!r} stderr={r.stderr!r}")
    if r.returncode == 2:
        assert r.stderr.strip(), "抓不到區網 IP 的時候**一定要說為什麼**"
    else:
        assert r.stdout.strip(), "回 0 就一定要把位址印在 stdout"


@pytest.mark.skipif(not BOOT_SH.exists(), reason="沒有 exhibit_boot.sh")
def test_loopback_mode_prints_loopback():
    """不帶 `--lan` 就不該去碰那一整段（那是展場才用的路徑）。"""
    r = _print_host()
    assert r.returncode == 0
    assert r.stdout.strip() == "127.0.0.1"


@pytest.mark.skipif(not BOOT_SH.exists(), reason="沒有 exhibit_boot.sh")
def test_unusable_address_is_refused_with_a_reason_not_a_silent_death():
    """指定一個**不能用**的位址 ⇒ 2 ＋ 講理由，不是 1 ＋ 沉默。

    169.254.0.0/16 ＝ link-local。展場手機連不到 ⇒ QR 掃不開 ⇒ 寧可不啟動。
    """
    import os
    env = dict(os.environ, VACANT_LAN_IP="169.254.7.7")
    import subprocess
    r = subprocess.run(["bash", str(BOOT_SH), "--lan", "--print-host"],
                       capture_output=True, text=True, timeout=60, env=env)
    assert r.returncode == 2, f"回了 {r.returncode}"
    assert "抓不到可用的區網 IP" in r.stderr


@pytest.mark.skipif(not BOOT_SH.exists(), reason="沒有 exhibit_boot.sh")
def test_interface_names_are_not_hardcoded_on_linux():
    """不准再靠猜介面名字。

    舊版寫死 `en0 en1 eth0 wlan0`，而 vacant-dev 的介面叫 `ens33`
    ——名單全部落空。展場機的網卡叫什麼**沒有人保證得了**。
    """
    src = BOOT_SH.read_text(encoding="utf-8")
    assert "addr show scope global" in src, "Linux 那一段要列真的存在的位址"
    # ⚠ 只看**程式碼**，不看註解：解釋那個 bug 的註解裡本來就會寫 `eth0 wlan0`，
    #   那段字**應該留著**（它是為什麼要這樣寫的理由）。把註解一起掃進來，
    #   這一條就會逼人把歷史刪掉才會綠——那是拿判準去換紀錄。
    code = "\n".join(ln for ln in src.splitlines()
                     if not ln.lstrip().startswith("#"))
    assert "eth0" not in code and "wlan0" not in code, "不要再寫死介面名字"
    # 而且那條管線一定要有退路（沒有 `|| true` ＝ pipefail 之下當場斷掉）
    assert "| cut -d/ -f1 | head -1 || true)" in src, (
        "`ip …` 那條管線少了 `|| true`：`ip` 對不存在的介面回 1，"
        "在 `set -o pipefail` 底下會讓整支腳本 exit 1 而且一個字都不印")
