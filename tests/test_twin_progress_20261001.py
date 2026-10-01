"""手機即時進度（2026-10-01，PROC4 線 A）的判準。

為什麼有這個檔：人類實測「下個就是你……明明已經在處理了」——雲端 status 在整段生成期間
一直是 `queued`（沒有人 claim，迴圈只在跑完才 publish）。`twinprogress` 讓迴圈在跑的當下把
進度推上去；這裡守 Vacant 這一側：

  1. 階段只講檔案上已經成立的事（沒有驗收套件的 run 永遠不會是 reviewing）；
  2. 審查結果轉成 `{id, ok, label, attempt}`（含重改的第二次嘗試）；
  3. 呈報者：每人每 5 秒最多一次、內容沒變不送（心跳例外）、失敗不往外丟、撤回後退場；
  4. `generate`／`loop` 真的把在跑的人登記進呈報者（旗標存在不等於產品路徑接上了）；
  5. 端到端：真的雲端（node，若在本機找得到）收得下我們送的形狀，status 回得出來。

⚠ 零模型呼叫。⚠ 每個綠燈配負控制。
"""
from __future__ import annotations

import json
import os
import pathlib
import shutil
import socket
import subprocess
import sys
import threading
import time

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ops.exhibit.twin import twinagent, twinlink, twinprogress  # noqa: E402

sys.path.insert(0, str(ROOT / "tests"))
from test_twin_agent_run import env, upstream  # noqa: E402,F401


SID = "0f0e0d0c-0b0a-4908-8706-050403020100"


def _say_log(path: pathlib.Path, items: list[tuple[str, int]]) -> None:
    rows = [{"type": "turn_start"}]
    for k, (text, ntools) in enumerate(items):
        content = ([{"type": "text", "text": text}] if text else []) \
            + [{"type": "toolCall", "arguments": {"path": "x.md"}}] * ntools
        rows.append({"type": "message_end", "message": {"role": "assistant", "content": content,
                                                         "timestamp": 1790000000000 + k}})
        rows.append({"type": "turn_start"})
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows),
                    encoding="utf-8")


def _steps(path: pathlib.Path, rows: list[tuple[str, str | None, int | None]]) -> None:
    out = []
    for i, (tool, p, b) in enumerate(rows, 1):
        out.append({"seq": i, "tool": tool, "path": p, "bytes": b, "ok": True, "ts_ms": 1})
    path.write_text("".join(json.dumps(r) + "\n" for r in out), encoding="utf-8")


def _visible(rd: pathlib.Path, name: str, cases: list[tuple[str, bool, str]]) -> None:
    res = {"all_pass": all(c[1] for c in cases), "passed": sum(c[1] for c in cases),
           "total": len(cases),
           "files": [{"file": "test_review.py", "cases": [
               {"case": c, "ok": ok, "kind": "assert", "message": m} for c, ok, m in cases]}]}
    (rd / name).write_text(json.dumps(res, ensure_ascii=False), encoding="utf-8")


@pytest.fixture()
def run(tmp_path):
    wr = tmp_path / "agentruns"
    ws, rd = twinagent.paths_for(wr, SID)
    return wr, ws, rd


def _set_mtime(p: pathlib.Path, t: float) -> None:
    os.utime(p, (t, t))


# ---------------------------------------------------------------------------
# 1. 階段
# ---------------------------------------------------------------------------

def test_stage_walks_claimed_forming_working_reviewing_done(run) -> None:
    wr, ws, rd = run
    assert twinprogress.infer_stage(rd) == "claimed"        # run 目錄還沒有
    rd.mkdir(parents=True)
    assert twinprogress.infer_stage(rd) == "forming"        # 起來了、pi 還沒說話
    _say_log(rd / twinagent.AGENT_STDOUT_NAME, [("我想先看看房間。", 1)])
    assert twinprogress.infer_stage(rd) == "working"
    (rd / twinprogress.SUITE_DIRNAME).mkdir()
    fz = rd / "_frozen_x"
    fz.mkdir()
    now = time.time()
    _set_mtime(rd / twinagent.AGENT_STDOUT_NAME, now - 10)
    _set_mtime(fz, now)
    assert twinprogress.infer_stage(rd) == "reviewing"
    # 重改：agent 又動手了（stdout 比凍結新）⇒ 回到 working
    _set_mtime(rd / twinagent.AGENT_STDOUT_NAME, now + 5)
    assert twinprogress.infer_stage(rd) == "working"
    (rd / "run_x.json").write_text("{}", encoding="utf-8")
    assert twinprogress.infer_stage(rd) == "done"


def test_negative_control_no_suite_never_reviewing(run) -> None:
    """沒有驗收套件 ⇒ 就算凍結了也不准講「Vacant 在檢查」。"""
    wr, ws, rd = run
    rd.mkdir(parents=True)
    _say_log(rd / twinagent.AGENT_STDOUT_NAME, [("我想先看看房間。", 1)])
    fz = rd / "_frozen_x"
    fz.mkdir()
    now = time.time()
    _set_mtime(rd / twinagent.AGENT_STDOUT_NAME, now - 10)
    _set_mtime(fz, now)
    assert twinprogress.infer_stage(rd) == "working"


# ---------------------------------------------------------------------------
# 2. 審查結果
# ---------------------------------------------------------------------------

def test_read_review_two_attempts_with_attempt_index(run) -> None:
    wr, ws, rd = run
    rd.mkdir(parents=True)
    _visible(rd, "visible_on.json", [("test_r1_plan", True, ""),
                                      ("test_r4_artifact_matches", False, "成品跟決定對不上\n細節")])
    _visible(rd, "visible_on_a2.json", [("test_r1_plan", True, ""),
                                         ("test_r4_artifact_matches", True, "")])
    rv = twinprogress.read_review(rd)
    assert [(r["id"], r["ok"], r["attempt"]) for r in rv] == [
        ("R1", True, 0), ("R4", False, 0), ("R1", True, 1), ("R4", True, 1)]
    assert rv[1]["label"] == "成品跟決定對不上"           # 失敗時取訊息第一行
    # 形狀＝雲端 reviewProblem 要的
    for r in rv:
        assert set(r) == {"id", "ok", "label", "attempt"}
        assert isinstance(r["label"], str) and r["label"]


def test_read_review_uses_review_suite_describe_when_present(run, monkeypatch) -> None:
    import types
    import ops.exhibit.twin as pkg
    wr, ws, rd = run
    rd.mkdir(parents=True)
    _visible(rd, "visible_on.json", [("test_r2", True, "")])
    fake = types.ModuleType("ops.exhibit.twin.review_suite")
    fake.describe = lambda case, ok, msg: ("R2", "理由有根據" if ok else "理由沒有根據")
    monkeypatch.setitem(sys.modules, "ops.exhibit.twin.review_suite", fake)
    monkeypatch.setattr(pkg, "review_suite", fake, raising=False)
    assert twinprogress.read_review(rd)[0]["label"] == "理由有根據"
    # 負控制：describe 炸了 ⇒ 退通用寫法，不丟例外
    fake.describe = lambda *a: (_ for _ in ()).throw(RuntimeError("壞了"))
    assert twinprogress.read_review(rd)[0]["id"] == "R2"


def test_read_review_survives_garbage(run) -> None:
    wr, ws, rd = run
    rd.mkdir(parents=True)
    (rd / "visible_on.json").write_text("{not json", encoding="utf-8")
    assert twinprogress.read_review(rd) == []


def test_snapshot_shape_matches_cloud_contract(run) -> None:
    wr, ws, rd = run
    rd.mkdir(parents=True)
    _say_log(rd / twinagent.AGENT_STDOUT_NAME, [("我想替你排雜事。", 2)])
    _steps(rd / twinagent.STEP_LOG_NAME, [("ws_list", None, None), ("ws_list", None, None)])
    snap = twinprogress.snapshot(wr, SID, [])
    assert snap["stage"] == "working"
    assert snap["says"][0]["text"] == "我想替你排雜事。"
    assert len(snap["steps"]) == 2
    assert "review" not in snap
    # 負控制：forming 階段不帶內容欄位
    shutil.rmtree(rd)
    rd.mkdir(parents=True)
    assert twinprogress.snapshot(wr, SID, []) == {"stage": "forming"}


def test_snapshot_drops_verbatim_copy_of_the_audience_text(run) -> None:
    wr, ws, rd = run
    rd.mkdir(parents=True)
    orig = "我最近很喜歡整理書架而且說話慢條斯理"
    _say_log(rd / twinagent.AGENT_STDOUT_NAME, [(orig + "所以我想寫東西", 1), ("我開始了。", 0)])
    snap = twinprogress.snapshot(wr, SID, [orig])
    assert [s["text"] for s in snap["says"]] == ["我開始了。"]


# ---------------------------------------------------------------------------
# 3. 呈報者
# ---------------------------------------------------------------------------

class _Clock:
    def __init__(self) -> None:
        self.t = 1000.0

    def __call__(self) -> float:
        return self.t


def _reporter(wr, posts, *, status=200, body=None, clock=None, **kw):
    def post(url, payload, timeout=0):
        posts.append((url, payload))
        if isinstance(status, Exception):
            raise status
        return status, (body if body is not None else {"ok": True})
    return twinprogress.ProgressReporter("http://cloud.test/", "TOK", wr, post=post,
                                         clock=clock or _Clock(), **kw)


def test_reporter_sends_claimed_immediately_then_throttles_to_5s(run) -> None:
    wr, ws, rd = run
    posts: list = []
    clk = _Clock()
    rep = _reporter(wr, posts, clock=clk)
    rep.track(SID, [])
    assert rep.tick_once() == [SID]
    url, pl = posts[0]
    assert url == "http://cloud.test/api/progress"
    assert pl["id"] == SID and pl["token"] == "TOK" and pl["stage"] == "claimed"
    # 5 秒內不再送（就算內容變了）
    rd.mkdir(parents=True)
    clk.t += 2
    assert rep.tick_once() == []
    assert len(posts) == 1
    # 超過 5 秒、內容（階段）變了 ⇒ 送
    clk.t += 4
    assert rep.tick_once() == [SID]
    assert posts[1][1]["stage"] == "forming"


def test_reporter_skips_unchanged_content_but_sends_keepalive(run) -> None:
    wr, ws, rd = run
    rd.mkdir(parents=True)
    posts: list = []
    clk = _Clock()
    rep = _reporter(wr, posts, clock=clk)
    rep.track(SID, [])
    rep.tick_once()
    for _ in range(5):
        clk.t += 6
        rep.tick_once()
    assert len(posts) == 1, "內容沒變就不該一直送"
    clk.t += twinprogress.KEEPALIVE_S
    rep.tick_once()
    assert len(posts) == 2, "超過心跳間隔要送一次"


def test_reporter_failure_never_raises_and_counts(run) -> None:
    wr, ws, rd = run
    posts: list = []
    rep = _reporter(wr, posts, status=OSError("斷網"))
    rep.track(SID, [])
    assert rep.tick_once() == []
    assert rep.stats["failed"] == 1 and rep.stats["sent"] == 0
    rep2 = _reporter(wr, [], status=500)
    rep2.track(SID, [])
    assert rep2.tick_once() == []
    assert rep2.stats["failed"] == 1


def test_reporter_untracked_person_is_never_sent(run) -> None:
    wr, ws, rd = run
    posts: list = []
    rep = _reporter(wr, posts)
    rep.track(SID, [])
    rep.untrack(SID)
    assert rep.tick_once() == [] and posts == []
    rep.track(SID, [])
    rep.sync(set())
    assert rep.tick_once() == [] and posts == []


def test_reporter_thread_start_stop(run) -> None:
    wr, ws, rd = run
    posts: list = []
    rep = _reporter(wr, posts, tick_s=0.02, clock=time.monotonic, min_interval_s=0.0)
    rep.track(SID, [])
    rep.start()
    t0 = time.time()
    while not posts and time.time() - t0 < 3:
        time.sleep(0.02)
    rep.stop()
    assert posts, "背景執行緒沒有送出任何進度"
    n = len(posts)
    time.sleep(0.1)
    assert len(posts) == n, "stop 之後不准再送"


def test_payload_never_carries_what_the_cloud_would_refuse(run) -> None:
    """形狀自檢：送出的欄位只有雲端 /api/progress 收的那幾個。"""
    wr, ws, rd = run
    rd.mkdir(parents=True)
    _say_log(rd / twinagent.AGENT_STDOUT_NAME, [("我開始了。", 1)])
    _steps(rd / twinagent.STEP_LOG_NAME, [("ws_read", "TRAITS.md", 300)])
    posts: list = []
    rep = _reporter(wr, posts)
    rep.track(SID, [])
    rep.tick_once()
    assert set(posts[0][1]) <= {"token", "id", "ts", "stage", "says", "steps", "review"}


# ---------------------------------------------------------------------------
# 4. 接線：generate 真的登記呈報者（旗標存在不等於產品路徑接上了）
# ---------------------------------------------------------------------------

def test_loop_cli_wires_a_reporter_and_has_a_kill_switch() -> None:
    src = (ROOT / "ops/exhibit/twin/twinlink.py").read_text(encoding="utf-8")
    assert "twinprogress.ProgressReporter(a.cloud, a.token, acfg.work_root)" in src
    assert "progress=reporter" in src
    assert "--no-progress" in src
    # 負控制：舊的呼叫點（不給 progress）簽名仍相容
    import inspect
    assert inspect.signature(twinlink.generate).parameters["progress"].default is None


def test_generate_agent_tracks_submitted_people_and_untracks_when_harvested(env, monkeypatch) -> None:
    from test_twin_agent_run import _ingest
    st, cfg = env["store"], env["cfg"]
    monkeypatch.setenv("TWIN_FIXTURE_MODE", "slow")
    sid = _ingest(st, monkeypatch)
    posts: list = []
    rep = twinprogress.ProgressReporter("http://cloud.invalid", "t", cfg.work_root,
                                        post=lambda u, p, timeout=0: (posts.append(p) or (200, {})))
    pool = twinagent.AgentPool(cfg.parallel)
    try:
        r1 = twinlink.generate(st, env["upstream"], "m", agent=cfg, pool=pool, progress=rep)
        assert r1["submitted"] == 1
        assert rep.tracked() == {sid}, "提交的人要登記進呈報者"
        # 登記的原文清單要含卡上的字（says 才擋得住逐字抄）
        assert any("念舊" in x or len(x) > 0 for x in rep._tracked[sid])
        pool.wait_idle()
        twinlink.generate(st, env["upstream"], "m", agent=cfg, pool=pool, progress=rep)
        assert rep.tracked() == set(), "收成之後要退場"
    finally:
        pool.shutdown()


def test_withdrawn_person_is_untracked_before_the_next_generate(env, monkeypatch) -> None:
    from test_twin_agent_run import _ingest
    st, cfg = env["store"], env["cfg"]
    monkeypatch.setenv("TWIN_FIXTURE_MODE", "slow")
    sid = _ingest(st, monkeypatch)
    rep = twinprogress.ProgressReporter("http://cloud.invalid", "t", cfg.work_root,
                                        post=lambda u, p, timeout=0: (200, {}))
    pool = twinagent.AgentPool(cfg.parallel)
    try:
        twinlink.generate(st, env["upstream"], "m", agent=cfg, pool=pool, progress=rep)
        assert rep.tracked() == {sid}
        twinlink.withdraw(st, sid)
        twinlink.generate(st, env["upstream"], "m", agent=cfg, pool=pool, progress=rep)
        assert rep.tracked() == set()
        pool.wait_idle()
    finally:
        pool.shutdown()


# ---------------------------------------------------------------------------
# 5. 端到端：真的雲端收得下
# ---------------------------------------------------------------------------

def _cloud_dir() -> pathlib.Path | None:
    env = os.environ.get("VACANT_WORLD_CLOUD_DIR")
    cands = [pathlib.Path(env)] if env else []
    cands += [ROOT.parent / "vacant-world-cloud-wt-p4a", ROOT.parent / "vacant-world-cloud"]
    for c in cands:
        if (c / "server.js").is_file() and (c / "node_modules").exists():
            return c
    return None


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


@pytest.fixture()
def real_cloud(tmp_path):
    cd = _cloud_dir()
    node = shutil.which("node")
    if cd is None or node is None:
        pytest.skip("本機沒有雲端 repo 或 node")
    # 只在這個雲端有 /api/progress 時才測（舊版雲端沒有這條）
    if "/api/progress" not in (cd / "server.js").read_text(encoding="utf-8"):
        pytest.skip("這份雲端還沒有 /api/progress")
    port = _free_port()
    token = "e2e-token"
    proc = subprocess.Popen([node, "server.js"], cwd=str(cd), stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                            env={**os.environ, "PORT": str(port), "VENUE_TOKEN": token,
                                 "DATA_DIR": str(tmp_path / "clouddata"),
                                 "RATE_WINDOW_MS": "5"})
    base = f"http://127.0.0.1:{port}"
    for _ in range(100):
        try:
            twinlink._http_json(base + "/api/status/nope", timeout=1)
        except Exception as e:  # noqa: BLE001
            if getattr(e, "code", None) == 404:
                break
            time.sleep(0.1)
        else:
            break
    yield base, token
    proc.terminate()
    proc.wait(timeout=5)


def test_end_to_end_real_cloud_status_follows_the_run(real_cloud, run) -> None:
    base, token = real_cloud
    wr, ws, rd = run
    status, sub = twinlink._http_json(base + "/api/submit", {
        "card_text": "需求：測試即時進度", "self_attested": True, "age_gate": True})
    assert status == 200, sub
    sid = sub["id"]
    st = twinlink._http_json(f"{base}/api/status/{sid}")[1]
    assert st["status"] == "queued" and st["queue"]["position"] == 1   # 卡住的原樣

    rep = twinprogress.ProgressReporter(base, token, wr, min_interval_s=0.0)
    # 借用真人的 sid：把本機 run 目錄放在 slug_for(sid) 底下
    ws, rd = twinagent.paths_for(wr, sid)
    rep.track(sid, [])
    assert rep.tick_once() == [sid]
    st = twinlink._http_json(f"{base}/api/status/{sid}")[1]
    assert st["status"] == "claimed" and st["stage"] == "claimed"
    assert st["queue"]["position"] is None            # 不再是「下一個就是你」

    rd.mkdir(parents=True)
    _say_log(rd / twinagent.AGENT_STDOUT_NAME, [("我想替你把這週的雜事排個順序", 1)])
    _steps(rd / twinagent.STEP_LOG_NAME, [("ws_list", None, None), ("ws_list", None, None)])
    assert rep.tick_once() == [sid]
    st = twinlink._http_json(f"{base}/api/status/{sid}")[1]
    assert st["stage"] == "working"
    assert st["says"][0]["text"].startswith("我想替你")
    assert len(st["steps"]) == 2

    (rd / twinprogress.SUITE_DIRNAME).mkdir()
    fz = rd / "_frozen_on"
    fz.mkdir()
    now = time.time()
    os.utime(rd / twinagent.AGENT_STDOUT_NAME, (now - 9, now - 9))
    os.utime(rd / twinagent.STEP_LOG_NAME, (now - 9, now - 9))
    os.utime(fz, (now, now))
    _visible(rd, "visible_on.json", [("test_r1_plan", True, ""),
                                      ("test_r4_artifact", False, "成品跟決定對不上")])
    assert rep.tick_once() == [sid]
    st = twinlink._http_json(f"{base}/api/status/{sid}")[1]
    assert st["stage"] == "reviewing"
    assert [(r["id"], r["ok"]) for r in st["review"]] == [("R1", True), ("R4", False)]
    assert rep.stats["failed"] == 0
