"""數位分身真跑（2026-09-24）的判準：假上游下一位分身完整跑一次、撤回真的刪、退化看得出來。

裁決：`decisions/DECISION_20260924_TWIN_AGENT_RUN.md`。

⚠ 本檔零模型呼叫：上游是本機假 server（照 `tests/test_vacant_run.py::_Upstream`），
agent 是一支 fixture（照 `run_twin.py` 的 FIXTURE_AGENT 精神：腳本化、會真的打一通
proxy，讓 wire log 裡真的有 TRAITS.md 原文——撤回要刪的正是那一份）。
**所以這裡的綠燈證明的是機制（中介、收據、事件、撤回），不是分身的能力。**

⚠ 每一個綠燈配一個負控制（「那個量法量得到東西」才算量到）。
"""
from __future__ import annotations

import json
import os
import pathlib
import shutil
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ops.exhibit.twin import twinagent, twinlink  # noqa: E402
from ops.exhibit.twin.twinstore import (  # noqa: E402
    KIND_ERASED, KIND_GENERATED, KIND_NOTE, TwinStore, canonical_json,
)
from vacant_network.vrun import lifecycle  # noqa: E402
from vacant_network.vrun import verify_receipts as vrr  # noqa: E402

#: 觀眾的特質。中文、夠長 ⇒ 在任何落點都搜得到（負控制用）。
TRAITS_TEXT = "我是一個很怕麻煩、但對老朋友很念舊的人，最近一直想寫信給國小導師"
NEED = "想跟國小導師說聲謝謝"
#: fixture 分身「決定」的事（衍生物，撤回也要刪）。
DECISION = "寫一封謝卡給國小導師"
LETTER = "老師您好：謝謝您當年每天放學陪我寫功課。"

_FIXTURE = r'''
import json, os, pathlib, sys, urllib.request
mode = os.environ.get("TWIN_FIXTURE_MODE", "good")
traits = pathlib.Path("TRAITS.md").read_text(encoding="utf-8")
# argv 尾端是 launcher 接上的 <run_dir> <system_prompt> <first_message>
run_dir, sysp, msg = sys.argv[-3], sys.argv[-2], sys.argv[-1]
pathlib.Path(run_dir, "fixture_argv.json").write_text(
    json.dumps({"n": len(sys.argv), "sys_len": len(sysp), "msg": msg},
               ensure_ascii=False), encoding="utf-8")
if mode != "silent":
    base = os.environ["OPENAI_BASE_URL"].rstrip("/")
    body = json.dumps({"model": "m", "messages": [
        {"role": "system", "content": sysp},
        {"role": "user", "content": traits + "\n" + msg}]},
        ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(base + "/chat/completions", data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=30) as r:
        r.read()
if mode == "slow":
    import time; time.sleep(float(os.environ.get("TWIN_FIXTURE_SLEEP", "1.5")))
if mode != "noplan":
    pathlib.Path("PLAN.md").write_text(
        "__DECISION__\n我很念舊，所以想先謝謝老師。這件事寫一張卡就做得完。\n",
        encoding="utf-8")
pathlib.Path("letter.md").write_text("__LETTER__\n", encoding="utf-8")
print("交出了 letter.md")
'''.replace("__DECISION__", DECISION).replace("__LETTER__", LETTER)


class _Upstream(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    seen: list[bytes] = []

    def log_message(self, *a):
        return

    def do_GET(self):                                     # noqa: N802
        payload = b'{"data":[{"id":"m"}]}'
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_POST(self):                                    # noqa: N802
        n = int(self.headers.get("Content-Length") or 0)
        type(self).seen.append(self.rfile.read(n))
        payload = json.dumps({"choices": [{"message": {"content": "好"}}]}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


@pytest.fixture()
def upstream():
    _Upstream.seen = []
    srv = ThreadingHTTPServer(("127.0.0.1", 0), _Upstream)
    srv.daemon_threads = True
    threading.Thread(target=srv.serve_forever, kwargs={"poll_interval": 0.1},
                     daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}/v1"
    srv.shutdown()
    srv.server_close()


@pytest.fixture()
def env(tmp_path, upstream, monkeypatch):
    """store ＋ 假上游 ＋ fixture agent 的 AgentConfig。

    ⚠ 上游與模型是**行程層級**的環境變數（`_generate_agent` 會寫 os.environ）。
      這裡先用 monkeypatch 設好，測試結束時它會把**原本的狀態**（不存在）還回去，
      不會漏到別的測試（`VACANT_RUN_UPSTREAM_OPENAI` 的優先序高於 `OPENAI_BASE_URL`）。
    """
    monkeypatch.setenv("VACANT_RUN_UPSTREAM_OPENAI", upstream)
    monkeypatch.setenv("VACANT_AGENT_MODEL", "m")
    monkeypatch.delenv("VACANT_TWIN_AGENTRUNS", raising=False)
    monkeypatch.delenv(lifecycle.ENV_EVENTS, raising=False)
    monkeypatch.setenv("TWIN_FIXTURE_MODE", "good")
    fx = tmp_path / "fixture_agent.py"
    fx.write_text(_FIXTURE, encoding="utf-8")
    st = TwinStore(tmp_path / "t.sqlite3")
    cfg = twinagent.AgentConfig(
        work_root=twinagent.default_work_root(st.path),
        events_path=tmp_path / "live.jsonl", model="m", endpoint=upstream,
        parallel=2, timeout_s=60.0,
        argv_prefix=[sys.executable, str(fx)], requires=[])
    yield {"store": st, "cfg": cfg, "upstream": upstream, "tmp": tmp_path}
    st.close()


def _ingest(st: TwinStore, monkeypatch, sid: str = "sub-秘密-001") -> str:
    def fake(url, payload=None, timeout=30.0, headers=None):  # noqa: ANN001
        return 200, {"items": [{"id": sid, "card": {"need": NEED, "vibe": "念舊"},
                                "card_text": TRAITS_TEXT, "ts": 1_900_000_000_000}]}
    monkeypatch.setattr(twinlink, "_http_json", fake)
    twinlink.ingest(st, "http://cloud.invalid", "t")
    return sid


def _all_bytes_under(root: pathlib.Path) -> bytes:
    return b"".join(p.read_bytes() for p in root.rglob("*") if p.is_file())


def _chain_blob(st: TwinStore) -> str:
    return "\n".join(canonical_json(e["payload"]) for e in st.events())


# ---------------------------------------------------------------------------
# 一、一位分身完整跑一次
# ---------------------------------------------------------------------------

def test_one_twin_runs_under_vacant_run_end_to_end(env, monkeypatch) -> None:
    st, cfg = env["store"], env["cfg"]
    sid = _ingest(st, monkeypatch)
    r = twinlink.generate(st, env["upstream"], "m", agent=cfg)
    assert r["mode"] == "agent" and r["generated"] == 1 and r["degraded"] == 0, r

    cur = st.current(sid)
    tw = cur["twin"]
    assert tw["engine"] == "vacant_run:pi:m"
    assert tw["decision"] == DECISION, "分身自己決定的那件事要讀得回來"
    assert tw["artifacts"][0]["name"] == "letter.md"
    assert LETTER in tw["artifacts"][0]["text"]
    assert tw["lines_from"] == "agent_workspace"
    assert tw["arrival"] == DECISION
    # 🔴 三值：沒有客觀標準 ⇒ None，**不是 False**
    assert tw["accepted"] is None and tw["stop_reason"] == "ungated"
    assert tw["requests_seen"] == 1

    # ── lifecycle：過契約、run_ended 的語意對 ──
    evs = lifecycle.read(cfg.events_path)
    assert lifecycle.validate_stream(evs) == []
    started = [e for e in evs if e["type"] == "run_started"][0]
    ended = [e for e in evs if e["type"] == "run_ended"][0]
    assert ended["accepted"] is None
    assert ended["stop_reason"] == "ungated"
    assert ended["has_receipt"] is True and ended["verdict_hash"] == tw["verdict_hash"]
    assert not [e for e in evs if e["type"] == "gate_ran"], "沒有套件就不會有 gate_ran"
    tid = twinagent.public_twin_id(sid)
    assert started["caller"]["cell_id"] == tid
    assert started["caller"]["resident"] == twinagent.resident_code(sid)
    assert started["caller"]["prompt"] == twinagent.CALLER_PROMPT
    assert ended["task_id"] == f"twin:{tid}"
    assert tw["run_id"] == started["run_id"]

    # ── 收據：既有的那把尺驗得過 ──
    ws, rd = twinagent.paths_for(cfg.work_root, sid)
    out = vrr.verify_run(rd)
    assert [x["verdict"] for x in out] == ["OK"], json.dumps(out, ensure_ascii=False)[:600]

    # ── 鏈上那一列指到那一跑，而且沒有原文 ──
    gen = list(st.events(sub_id=sid, kind=KIND_GENERATED))[-1]["payload"]
    assert gen["run_id"] == started["run_id"] and gen["verdict_hash"] == tw["verdict_hash"]
    blob = _chain_blob(st)
    for secret in (TRAITS_TEXT, NEED, DECISION, LETTER):
        assert secret not in blob, f"原文上鏈了：{secret[:10]}"

    # ── 畫面 ──
    view = twinlink.build_view(st)
    p = view["people"][0]
    assert p["twin_id"] == tid and p["decision"] == DECISION
    assert p["run"]["accepted"] is None and p["run"]["verdict_hash"] == tw["verdict_hash"]


def test_public_records_never_carry_viewer_text_or_sub_id(env, monkeypatch) -> None:
    """事件流（會被錄影、接到公開螢幕）與 argv **不帶觀眾原文，也不帶 sub_id**。"""
    st, cfg = env["store"], env["cfg"]
    sid = _ingest(st, monkeypatch)
    twinlink.generate(st, env["upstream"], "m", agent=cfg)
    text = cfg.events_path.read_text(encoding="utf-8")
    for bad in (TRAITS_TEXT, NEED, DECISION, LETTER, sid):
        assert bad not in text, f"事件流裡有 {bad[:10]}"
    ws, rd = twinagent.paths_for(cfg.work_root, sid)
    run_json = (rd / "run_RUN-ON.json").read_text(encoding="utf-8")
    argv = json.dumps(json.loads(run_json)["argv"], ensure_ascii=False)
    assert TRAITS_TEXT not in argv and NEED not in argv
    receipts = (rd / "receipts_RUN-ON.ndjson").read_text(encoding="utf-8")
    for bad in (TRAITS_TEXT, NEED, DECISION, sid):
        assert bad not in receipts
    # 負控制：wire log 裡**真的有**特質原文（鐵律 3 逐字落盤）——下面撤回要刪的就是它
    assert TRAITS_TEXT.encode("utf-8") in _all_bytes_under(rd / "wire_RUN-ON")


# ---------------------------------------------------------------------------
# 二、撤回要真的刪
# ---------------------------------------------------------------------------

def test_withdraw_erases_wire_log_workspace_and_logs(env, monkeypatch) -> None:
    st, cfg = env["store"], env["cfg"]
    sid = _ingest(st, monkeypatch)
    twinlink.generate(st, env["upstream"], "m", agent=cfg)
    ws, rd = twinagent.paths_for(cfg.work_root, sid)
    # 負控制：撤回前，特質原文在 run 那一側**找得到**（不然下面的「找不到」沒意義）
    assert TRAITS_TEXT.encode("utf-8") in _all_bytes_under(cfg.work_root)
    assert (rd / "agent_stdout.log").exists() and (rd / "_frozen_RUN-ON").is_dir()

    out = twinlink.withdraw(st, sid)
    assert out["ok"] is True
    assert not ws.exists(), "工作區沒刪"
    left = sorted(c.name for c in rd.iterdir())
    assert left == sorted(twinagent.KEEP_ON_ERASE), left
    blob = _all_bytes_under(cfg.work_root)
    for secret in (TRAITS_TEXT, NEED, DECISION, LETTER):
        assert secret.encode("utf-8") not in blob, f"撤回後還找得到 {secret[:10]}"
    what = {e["what"] for e in out["run_artifacts_erased"]}
    assert {"workspace", "wire_RUN-ON", "_frozen_RUN-ON", "agent_stdout.log"} <= what
    assert out["run_artifacts_kept_hash_only"] == sorted(twinagent.KEEP_ON_ERASE)
    assert out["run_artifacts_problems"] == []
    assert out["fully_erased"] is True
    # 留下來的收據**仍然驗得過**（留了卻驗不了等於沒留）
    assert [x["verdict"] for x in vrr.verify_run(rd)] == ["OK"]
    # 抹除證明本身也不帶原文
    er = list(st.events(sub_id=sid, kind=KIND_ERASED))[-1]["payload"]
    assert TRAITS_TEXT not in canonical_json(er)
    # 畫面上什麼都不留
    p = twinlink.build_view(st)["people"][0]
    assert p["decision"] is None and p["artifacts"] is None


def test_fully_erased_is_false_when_run_artifacts_survive(env, monkeypatch) -> None:
    """負控制：run 產物刪不掉 ⇒ **不准**回報 fully_erased。"""
    st, cfg = env["store"], env["cfg"]
    sid = _ingest(st, monkeypatch)
    twinlink.generate(st, env["upstream"], "m", agent=cfg)
    monkeypatch.setattr(twinagent, "erase_run_artifacts", lambda root, s: {
        "erased": [], "kept_hash_only": [], "problems": ["wire_RUN-ON: PermissionError"]})
    out = twinlink.withdraw(st, sid)
    assert out["fully_erased"] is False
    assert out["run_artifacts_problems"]


def test_withdrawn_mid_run_is_discarded_not_sealed(env, monkeypatch) -> None:
    """跑到一半被撤回：收成時**不封印**、再刪一次、記一列只有計數的 note。"""
    st, cfg = env["store"], env["cfg"]
    monkeypatch.setenv("TWIN_FIXTURE_MODE", "slow")
    sid = _ingest(st, monkeypatch)
    pool = twinagent.AgentPool(cfg.parallel)
    try:
        r1 = twinlink.generate(st, env["upstream"], "m", agent=cfg, pool=pool)
        assert r1["submitted"] == 1 and r1["in_flight"] == 1
        twinlink.withdraw(st, sid)
        pool.wait_idle()
        r2 = twinlink.generate(st, env["upstream"], "m", agent=cfg, pool=pool)
    finally:
        pool.shutdown()
    assert r2["discarded"] == 1 and r2["generated"] == 0
    assert not list(st.events(sub_id=sid, kind=KIND_GENERATED)), "撤回的人被封印了"
    assert st.vault.open_twin(sid) is None
    assert not twinagent.run_artifacts_present(cfg.work_root, sid)
    note = [e for e in st.events(sub_id=sid, kind=KIND_NOTE)
            if e["payload"].get("twinlink_event") == "late_run_discarded"]
    assert note and TRAITS_TEXT not in canonical_json(note[0]["payload"])


# ---------------------------------------------------------------------------
# 三、退化要看得出來
# ---------------------------------------------------------------------------

def test_no_model_call_is_not_labelled_as_a_real_run(env, monkeypatch) -> None:
    st, cfg = env["store"], env["cfg"]
    monkeypatch.setenv("TWIN_FIXTURE_MODE", "silent")    # 寫了 PLAN.md，但一通都沒打
    sid = _ingest(st, monkeypatch)
    r = twinlink.generate(st, env["upstream"], "m", agent=cfg)
    tw = st.current(sid)["twin"]
    assert tw["engine"] == "fallback_deterministic", "沒打到模型卻標成真跑"
    assert tw["degrade_kind"] == "no_model_call"
    assert tw["degraded_from"] == "vacant_run:pi:m"
    assert tw["run_id"], "有跑就有紀錄：run_id 照樣上鏈"
    assert r["degraded"] == 1


def test_no_plan_is_degraded(env, monkeypatch) -> None:
    st, cfg = env["store"], env["cfg"]
    monkeypatch.setenv("TWIN_FIXTURE_MODE", "noplan")
    sid = _ingest(st, monkeypatch)
    twinlink.generate(st, env["upstream"], "m", agent=cfg)
    tw = st.current(sid)["twin"]
    assert tw["engine"] == "fallback_deterministic"
    assert tw["degrade_kind"] == "agent_no_plan"


def test_agent_unavailable_falls_back_and_says_so(env, monkeypatch) -> None:
    st, cfg = env["store"], env["cfg"]
    cfg.requires = ["definitely-not-an-installed-binary-7f3a"]
    sid = _ingest(st, monkeypatch)
    r = twinlink.generate(st, env["upstream"], "m", agent=cfg)
    assert r["agent_available"] is False and r["agent_unavailable_reason"]
    tw = st.current(sid)["twin"]
    assert tw["degrade_kind"] == "agent_unavailable"
    assert tw["degraded_from"] == "vacant_run:pi:m"
    assert not str(tw["engine"]).startswith("vacant_run"), "沒跑 pi 卻標成 vacant_run"
    assert not cfg.work_root.exists(), "跑不起 pi 就不該長出 run 目錄"


def test_upstream_unreachable_does_not_start_pi(env, monkeypatch) -> None:
    st, cfg = env["store"], env["cfg"]
    sid = _ingest(st, monkeypatch)
    r = twinlink.generate(st, "http://127.0.0.1:1/v1", "m", agent=cfg)
    assert r["upstream_reachable"] is False
    tw = st.current(sid)["twin"]
    assert tw["engine"] == "fallback_deterministic"
    assert tw["degrade_kind"] == "upstream_unreachable"
    assert not cfg.work_root.exists()


def test_negative_control_withdrawn_people_are_never_run(env, monkeypatch) -> None:
    """負控制：撤回過的人**不會**被排進佇列（再拿他的特質去跑就是沒在聽）。"""
    st, cfg = env["store"], env["cfg"]
    sid = _ingest(st, monkeypatch)
    twinlink.withdraw(st, sid)
    r = twinlink.generate(st, env["upstream"], "m", agent=cfg)
    assert r["submitted"] == 0 and r["generated"] == 0
    assert not cfg.work_root.exists()
    assert _Upstream.seen == []


# ---------------------------------------------------------------------------
# 四、佇列、固定文字
# ---------------------------------------------------------------------------

def test_pool_never_exceeds_parallel(monkeypatch) -> None:
    live, peak, lock = [0], [0], threading.Lock()

    def fake_run_one(job):
        with lock:
            live[0] += 1
            peak[0] = max(peak[0], live[0])
        time.sleep(0.15)
        with lock:
            live[0] -= 1
        return {"sub_id": job.sub_id}

    monkeypatch.setattr(twinagent, "run_one", fake_run_one)
    pool = twinagent.AgentPool(2)
    cfg = twinagent.AgentConfig(work_root=pathlib.Path("/nonexistent"),
                                events_path=None, model="m", endpoint="x")
    for i in range(6):
        assert pool.submit(twinagent.Job(sub_id=f"s{i}", traits="t", cfg=cfg))
    assert not pool.submit(twinagent.Job(sub_id="s0", traits="t", cfg=cfg)), \
        "同一個人不准同時排兩次"
    got = pool.harvest(block=True)
    pool.shutdown()
    assert len(got) == 6
    assert peak[0] == 2, f"並行上限沒守住（峰值 {peak[0]}）"


def test_fixed_texts_are_ks1_clean_and_the_guard_bites() -> None:
    from vacant_network.memory import KS1Violation, assert_ks1_clean
    for t in (twinagent.SYSTEM_PROMPT, twinagent.FIRST_MESSAGE, twinagent.CALLER_PROMPT):
        assert_ks1_clean(t)
        twinlink.assert_ks1_clean(t)
    with pytest.raises(KS1Violation):                       # 負控制：尺是有牙齒的
        assert_ks1_clean(twinagent.SYSTEM_PROMPT + "你有責任把它做完")
    assert "不要寫程式" in twinagent.SYSTEM_PROMPT, "人類定義：實務任務，不是寫程式"


def test_twin_id_is_not_the_sub_id() -> None:
    sid = "abc-123"
    tid = twinagent.public_twin_id(sid)
    assert sid not in tid and tid.startswith("tw-")
    assert tid == twinagent.public_twin_id(sid), "要確定性，事件流才接得起來"
    assert tid != twinagent.public_twin_id("abc-124")


# ---------------------------------------------------------------------------
# 五、pi 權限 probe（本機要有 pi 0.85.x 才跑）
# ---------------------------------------------------------------------------

def _pi_version() -> str | None:
    exe = os.environ.get("VACANT_TWIN_PI") or shutil.which("pi")
    if not exe:
        return None
    try:
        return subprocess.run([exe, "--version"], capture_output=True, text=True,
                              timeout=30).stdout.strip() or None
    except Exception:                                     # noqa: BLE001
        return None


@pytest.mark.skipif(_pi_version() is None,
                    reason=("本機沒有 pi：pi 0.85.1 只裝在 vacant-dev（1003 上的 VM）。"
                            "這條 probe 在那台實跑過，證據落在 "
                            "ops/exhibit/twin/evidence_agentrun_20260924/probe_pi_tools.json"))
def test_pi_cannot_run_shell_or_leave_its_room(tmp_path) -> None:
    from ops.exhibit.twin import probe_pi_tools
    rep = probe_pi_tools.run_probe(tmp_path)
    assert rep["negative_control"]["bash_executed"] is True, "負控制失效：量不到 bash"
    t = rep["twin"]
    assert t["bash_executed"] is False
    assert t["escape_written"] is False
    assert t["outside_read"] is False
    assert t["plan_written"] is True, "正控制：房間裡要寫得進去"
    assert set(t["tools_offered"]) == {"ws_list", "ws_read", "ws_write"}


def test_probe_evidence_is_on_disk_and_says_what_it_says() -> None:
    """probe 在 vacant-dev 實跑的證據要落盤，而且結論跟上面那條測試同一套判準。"""
    p = ROOT / "ops/exhibit/twin/evidence_agentrun_20260924/probe_pi_tools.json"
    rep = json.loads(p.read_text(encoding="utf-8"))
    assert rep["pi_version"].startswith("0.85")
    assert rep["negative_control"]["bash_executed"] is True
    t = rep["twin"]
    assert (t["bash_executed"], t["escape_written"], t["outside_read"]) == (False, False, False)
    assert t["plan_written"] is True
    assert set(t["tools_offered"]) == {"ws_list", "ws_read", "ws_write"}
