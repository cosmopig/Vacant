"""`vacant dashboard`（`vacant_network/statusboard.py`）：裝完 Vacant 就看得到每一個狀態。

紀錄是經過真的 `hook.handle` 產生的（同 `test_zero_stop.py` 的假 agent），不是手寫的假檔；
儀表板只讀——讀完之後 `$VACANT_HOME` 底下逐位元不變。"""
import hashlib
import http.client
import json
import threading

import pytest

from vacant_network import cli as top_cli
from vacant_network import statusboard as SB
from vacant_network.adapters import hook
from vacant_network.adapters import install as INS
from vacant_network.trace import zerostop
from vacant_network.trace.recorder import Recorder, project_key

SALES = "date,region,amount\n2026-07-01,north,1200\n2026-07-02,south,845\n" \
        "2026-07-03,north,310\n2026-07-04,east,1990\n2026-07-05,south,467\n"
ASK = "Using data/sales.csv, write the total amount to report.md."


@pytest.fixture
def env(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("VACANT_HOME", str(tmp_path / "vh"))
    for k in ("VACANT_TRACE", "VACANT_MODE", "VACANT_HOOK_NO_STOP", "VACANT_FEEDBACK_MODE",
              "CLAUDE_CONFIG_DIR", "CODEX_HOME", "XDG_CONFIG_HOME", "PI_CODING_AGENT_DIR"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setattr(zerostop, "_run_child", zerostop.check)
    SB._EVENTS._c.clear()
    return tmp_path


def _install(mode="evidence"):
    p = INS.state_root() / "install.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"agents": {}, "mode": mode}))


class Agent:
    def __init__(self, proj, session="S"):
        self.p, self.s, self.n = proj, session, 0

    def ask(self, text):
        hook.handle("claude", "UserPromptSubmit", {"session_id": self.s, "cwd": str(self.p),
                                                   "prompt": text})

    def step(self, tool, inp, output=None, *, write=None):
        self.n += 1
        pre = {"session_id": self.s, "cwd": str(self.p), "tool_name": tool,
               "tool_use_id": f"t{self.n}", "tool_input": inp}
        hook.handle("claude", "PreToolUse", pre)
        for rel, content in (write or {}).items():
            (self.p / rel).parent.mkdir(parents=True, exist_ok=True)
            (self.p / rel).write_text(content)
        hook.handle("claude", "PostToolUse", {**pre, "tool_response": output or {}})

    def read(self, rel):
        self.step("Read", {"file_path": str(self.p / rel)},
                  {"file": {"content": (self.p / rel).read_text()}})

    def write(self, rel, content):
        self.step("Write", {"file_path": str(self.p / rel), "content": content}, {},
                  write={rel: content})

    def stop(self, final="Done."):
        out, _err, _code = hook.handle("claude", "Stop", {
            "session_id": self.s, "cwd": str(self.p), "hook_event_name": "Stop",
            "stop_hook_active": False, "last_assistant_message": final})
        return json.loads(out) if out else {}


def _proj(env, name="proj"):
    p = env / "work" / name
    (p / "data").mkdir(parents=True)
    (p / "data" / "sales.csv").write_text(SALES)
    (p / ".git").mkdir()
    return p


def _sent_back_then_fixed(env):
    _install()
    p = _proj(env)
    a = Agent(p)
    a.ask(ASK)
    a.write("report.md", "# Sales\n\nTotal amount: 5,200\n")
    assert a.stop().get("decision") == "block"
    a.read("data/sales.csv")
    a.write("report.md", "# Sales\n\nTotal amount: 4,812\n")
    assert "decision" not in a.stop("The total is 4,812.")
    return p


def _tree(root):
    return {str(p.relative_to(root)): (hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else "dir")
            for p in sorted(root.rglob("*"))}


# ── 沒裝 ────────────────────────────────────────────────────────────────
def test_before_install_it_says_so_and_creates_nothing(env):
    o = SB.overview()
    assert o["install"]["manifest_found"] is False
    assert o["install"]["mode"] == "off"
    assert {a["name"] for a in o["install"]["agents"]} == {"claude", "codex", "opencode", "pi"}
    assert all(a["health"] == "not_installed" for a in o["install"]["agents"])
    assert o["projects"] == [] and o["tasks"]["n_tasks"] == 0 and o["hooks"]["events"] == []
    assert not (env / "vh").exists()          # 只讀：連 $VACANT_HOME 都不建


# ── 裝了、照常用 ─────────────────────────────────────────────────────────
def test_a_sent_back_then_fixed_task_shows_up_with_its_checks(env):
    p = _sent_back_then_fixed(env)
    o = SB.overview()
    assert o["install"]["mode"] == "evidence" and o["install"]["manifest_found"]
    [proj] = o["projects"]
    assert proj["key"] == project_key(p) and proj["workspace"] == str(p.resolve())
    assert proj["n_checks"] == 2 and proj["n_sent_back"] == 1
    assert proj["n_steps"] >= 3 and proj["n_sessions"] == 1
    d = proj["delivery"]
    assert d and d["in_progress"] is False and d["n_fixed"] >= 1 and d["session"] == "claude:S"
    stops = [e for e in o["hooks"]["events"] if e.get("kind") == "stop"]
    assert [e["action"] for e in stops] == ["continue", "allow"]
    assert stops[0]["zero"]["round"] == 1


def test_project_detail_has_the_history_the_note_and_a_verified_chain(env):
    p = _sent_back_then_fixed(env)
    det = SB.project_detail(project_key(p))
    assert det["chain_ok"] is True, det["chain_note"]
    assert [c["action"] for c in det["checks"] if c["type"] == "review"] == ["continue", "allow"]
    first = det["checks"][0]
    assert first["round"] == 1 and any('"5,200"' in f for f in first["findings"])
    assert det["delivery_md"] == (Recorder(p).dir / "delivery.md").read_text()
    assert any("report.md" in w for s in det["steps"] for w in s["writes"])
    assert det["sessions"][0]["session"] == "claude:S" and det["sessions"][0]["n_steps"] >= 3


def test_reading_everything_leaves_vacant_home_byte_identical(env):
    p = _sent_back_then_fixed(env)
    before = _tree(env / "vh")
    SB.overview()
    SB.project_detail(project_key(p))
    SB.main(["--json"])
    assert _tree(env / "vh") == before


def test_a_removed_hook_is_shown_as_drift(env):
    _install()
    m = INS.Manifest()
    cfg = env / "home" / ".claude" / "settings.json"
    cfg.parent.mkdir(parents=True)
    cfg.write_text("{}")                      # 有人把 Vacant 的掛鉤拿掉了
    m.data.setdefault("agents", {})["claude"] = {"installed_at": "2026-10-11T00:00:00+00:00", "ops": [
        {"op": "json_hooks", "path": str(cfg), "events": ["Stop"], "root_key": "hooks",
         "created": False, "backup": None}]}
    m.save()
    [claude] = [a for a in SB.install_status()["agents"] if a["name"] == "claude"]
    assert claude["installed"] and claude["health"] == "drift"
    assert claude["config"][0]["state"] == "missing"


def test_a_torn_chain_does_not_take_the_page_down(env):
    p = _sent_back_then_fixed(env)
    rec = Recorder(p)
    rec.chain_path.write_bytes(rec.chain_path.read_bytes()[:-40])
    SB._EVENTS._c.clear()
    assert SB.overview()["projects"][0]["key"] == project_key(p)
    assert SB.project_detail(project_key(p))["chain_ok"] is False


def test_project_keys_are_not_paths(env):
    _sent_back_then_fixed(env)
    for bad in ("../../etc", "..", "abc", "0123456789abcdeg", "/etc/passwd"):
        assert SB.project_detail(bad) is None


# ── HTTP ────────────────────────────────────────────────────────────────
@pytest.fixture
def server(env):
    srv = SB.make_server(0)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield srv.server_address[1]
    srv.shutdown()
    srv.server_close()


def _get(port, path, host=None, method="GET"):
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    c.request(method, path, headers={"Host": host or f"127.0.0.1:{port}"})
    r = c.getresponse()
    body = r.read()
    c.close()
    return r.status, r.getheader("Content-Type"), body


def test_http_serves_the_page_and_the_api(env, server):
    p = _sent_back_then_fixed(env)
    st, ct, body = _get(server, "/")
    assert st == 200 and ct.startswith("text/html") and "Vacant 儀表板".encode() in body
    for forbidden in (b"LM Studio", b"lmstudio", b"Hermes", b"hermes"):
        assert forbidden not in body
    st, _, body = _get(server, "/api/overview", host=f"localhost:{server}")
    assert st == 200 and json.loads(body)["projects"][0]["n_sent_back"] == 1
    st, _, body = _get(server, f"/api/project/{project_key(p)}")
    assert st == 200 and json.loads(body)["chain_ok"] is True
    assert _get(server, "/api/project/0000000000000000")[0] == 404
    assert _get(server, "/nope")[0] == 404


def test_api_index_lists_only_real_endpoints(env, server):
    # dogfood（2026-10-24 round 17）：`GET /api` 以前回裸 {"error":"not found"}，
    # 舊 backlog 指的 `/api/snapshot` 是舊 dashboard.py 的端點、本面板沒有——不指向不存在的端點。
    st, ct, body = _get(server, "/api")
    assert st == 200 and ct.startswith("application/json")
    eps = json.loads(body)["endpoints"]
    assert set(eps) == {"/", "/api/overview", "/api/project/<key>"}
    st, _, body = _get(server, "/api/")
    assert st == 200  # 尾斜線同一索引
    assert set(json.loads(body)["endpoints"]) == set(eps)
    # 未知 /api/*：仍是 404，但指出哪些端點真的存在
    st, _, body = _get(server, "/api/snapshot")
    assert st == 404 and json.loads(body)["endpoints"] == eps
    # 非 /api 路徑維持裸 404
    st, _, body = _get(server, "/nope")
    assert st == 404 and json.loads(body) == {"error": "not found"}


def test_page_states_numbers_are_read_time_snapshot(env, server):
    # round 17 #5：HTML 頁應說明「數字是讀取時刻的快照」（/api 索引已有、HTML 頁沒有）。
    st, ct, body = _get(server, "/")
    assert st == 200 and ct.startswith("text/html")
    assert "數字是讀取時刻的快照".encode() in body


def test_http_is_read_only_and_local_only(env, server):
    assert _get(server, "/api/overview", method="POST")[0] == 405
    assert _get(server, "/api/overview", method="DELETE")[0] == 405
    assert _get(server, "/api/overview", host="evil.example")[0] == 403      # DNS rebinding
    assert _get(server, "/", host=f"evil.example:{server}")[0] == 403


def test_the_server_only_listens_on_loopback(env):
    srv = SB.make_server(0)
    try:
        assert srv.server_address[0] == "127.0.0.1"
    finally:
        srv.server_close()


# ── 指令 ────────────────────────────────────────────────────────────────
def test_vacant_dashboard_json_goes_through_the_top_level_cli(env, capsys):
    _sent_back_then_fixed(env)
    assert top_cli.main(["dashboard", "--json"]) == 0
    o = json.loads(capsys.readouterr().out)
    assert o["install"]["mode"] == "evidence" and len(o["projects"]) == 1


def test_install_points_at_the_dashboard(env, capsys, monkeypatch):
    from vacant_network.adapters import agents as A
    from vacant_network.adapters import cli as acli
    monkeypatch.setattr(A, "detect", lambda: {n: None for n in A.AGENTS})
    acli.main(["install", "--agents", "claude", "--force"])
    assert "vacant dashboard" in capsys.readouterr().out
