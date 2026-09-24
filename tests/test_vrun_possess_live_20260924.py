"""2026-09-24 在 vacant-dev 上實測 pi 整合抓到的兩個洞——`possess.py` 的可執行防呆。

1. **本機上游被丟進 sink。** 舊判準 `"127.0.0.1" in url or "localhost" in url` 本意是
   「不要把我們自己的 proxy 當上游」，但它把使用者真的在用的本機模型服務也丟掉了：
   pi provider `http://127.0.0.1:1234/v1`（LM Studio）⇒ `discover_install_upstreams` 回 sink、
   `pi_key_carrier` 回 None。**展場機器（1003，離線）跑的正是 127.0.0.1:1234 的 LM Studio。**
   新判準：迴路主機 **且** 埠落在我們會用的範圍（`DEFAULT_PORT` 起 40 個、這次要裝的埠起
   40 個）才跳過；用 `urllib.parse` 解析，不比子字串。
2. **常駐 extension 那條路永遠點不亮 `proven`。** `mark_proven` 只有 gateshim（shim 路）會叫；
   實測 133 通經過常駐 proxyd 而 `vacant possess status` 仍印「未證實」。
   現在 `status()` 從落盤證據推（`possess.extension_proof`），**而且永遠標路**：
   extension 路只證通道、不證閘門，不准冒充 shim 路。

⚠ 全部在 tmp_path 底下、`skip_service=True`：不碰網路、不裝服務、不動真的 `$HOME`。
  掛鉤日誌與 journal 是照 `hookcli.emit`／`wireproxy._finish` 的欄位**合成**的——
  這一組守的是判準的邏輯，**不是**「常駐 extension 在真 pi 上會燒」的證據（那是 L-real 的事）。
"""
from __future__ import annotations

import inspect
import json
import pathlib

import pytest

from vacant_network.vrun import envmap, possess

PORT = 18790                     # 跟 tests/test_vrun_possess.py 的 `_install` 同一個
RID = "0f4b8a36-1111-4222-8333-444455556666"
T0 = 1_790_000_000.0


def _clear_env(monkeypatch):
    for _w, names in envmap.UPSTREAM_VARS:
        for n in names:
            monkeypatch.delenv(n, raising=False)
    monkeypatch.delenv("PI_CODING_AGENT_DIR", raising=False)
    monkeypatch.delenv("VACANT_POSSESS_HOME", raising=False)


def _seed_pi(h: pathlib.Path, providers: dict, default: str | None = None) -> None:
    d = h / ".pi" / "agent"
    d.mkdir(parents=True, exist_ok=True)
    (d / "models.json").write_text(json.dumps({"providers": providers}), "utf-8")
    if default:
        (d / "settings.json").write_text(json.dumps({"defaultProvider": default}),
                                         "utf-8")


def _install(h: pathlib.Path, **kw) -> dict:
    kw.setdefault("startable_probe", False)
    kw.setdefault("gate_reach_probe", False)
    return possess.install(home=h, port=PORT, probe_shell=False,
                           skip_service=True, **kw)


# ══ 洞 1：本機上游不可以被當成「我們自己」 ═══════════════════════════════

LOCAL_SERVERS = ["http://127.0.0.1:1234/v1",      # LM Studio（展場 1003 就是這個）
                 "http://localhost:11434/v1",      # Ollama
                 "http://[::1]:8080/v1"]           # llama.cpp（IPv6 迴路）


@pytest.mark.parametrize("url", LOCAL_SERVERS)
def test_local_model_server_is_pi_upstream_and_key_carrier(tmp_path, monkeypatch, url):
    _clear_env(monkeypatch)
    h = tmp_path / "home"
    _seed_pi(h, {"lm": {"baseUrl": url, "api": "openai-completions",
                        "apiKey": "lm-studio"}})
    ups = possess.discover_install_upstreams(h, prefer=["pi"],
                                             proxy_port=possess.DEFAULT_PORT)
    assert ups["openai"] == {"url": url, "source": "pi:providers.lm"}
    assert not envmap.is_sink(ups["openai"]["url"])
    assert possess.pi_key_carrier(h, url, proxy_port=possess.DEFAULT_PORT) == "lm"


@pytest.mark.parametrize("url", [
    "http://127.0.0.1:8787/v1",          # DEFAULT_PORT 本身（舊版 install 改寫的樣子）
    "http://localhost:8826/v1",          # pick_port 掃描範圍的最後一個
    "http://[::1]:8800/v1",
    "http://0.0.0.0:8787/v1",
    "http://127.0.0.2:8790/v1",          # 127.0.0.0/8 整段都是迴路
    "http://[::ffff:127.0.0.1]:8787/v1",  # IPv4-mapped
])
def test_own_default_proxy_range_is_skipped(tmp_path, monkeypatch, url):
    """proxyd 不可以把自己當上游（會轉回自己）⇒ 這些要跳過，落到 sink（fail-closed）。"""
    _clear_env(monkeypatch)
    h = tmp_path / "home"
    _seed_pi(h, {"old": {"baseUrl": url, "api": "openai-completions"}})
    ups = possess.discover_install_upstreams(h, prefer=["pi"])
    assert envmap.is_sink(ups["openai"]["url"]), ups
    assert possess.pi_key_carrier(h, url) is None


def test_install_port_range_is_skipped_only_when_that_port_is_being_installed(
        tmp_path, monkeypatch):
    """這次要裝的埠（及 `pick_port` 往上掃的 40 個）也是我們的；沒給 `proxy_port` 時它只是一般本機埠。"""
    _clear_env(monkeypatch)
    h = tmp_path / "home"
    url = f"http://127.0.0.1:{PORT + 5}/v1"
    _seed_pi(h, {"p": {"baseUrl": url, "api": "openai-completions"}})
    assert envmap.is_sink(possess.discover_install_upstreams(
        h, prefer=["pi"], proxy_port=PORT)["openai"]["url"])
    assert possess.discover_install_upstreams(
        h, prefer=["pi"], proxy_port=None)["openai"]["url"] == url
    # 範圍外一格
    assert not possess._is_own_proxy_url(
        f"http://127.0.0.1:{PORT + possess._PORT_SCAN_SPAN}/v1", PORT)


def test_port_is_parsed_not_substring_matched():
    own = possess._is_own_proxy_url
    assert not own("http://127.0.0.1:12345/v1", proxy_port=1234)   # 12345 ≠ 1234..1273
    assert not own("http://127.0.0.1:1234/v1", proxy_port=12345)
    assert own("http://127.0.0.1:1250/v1", proxy_port=1234)
    assert not own("http://127.0.0.1:18787/v1")                     # 含 "8787" 子字串，但不是 8787
    assert not own("http://127.0.0.1.example.com:8787/v1")          # 主機名不是迴路
    assert not own("http://localhost.evil.example:8787/v1")
    assert not own("http://8787.example/v1")
    assert not own("http://localhost/v1")                           # 預設埠 80
    assert own("localhost:8787/v1")                                 # 沒寫 scheme 也認得
    assert own("http://sub.localhost:8790/v1")                      # *.localhost 是迴路
    # pick_port 與判準共用同一個寬度（各寫一個 40 會漂）
    assert "_PORT_SCAN_SPAN" in inspect.getsource(possess.pick_port)


@pytest.mark.parametrize("url", ["http://192.168.1.5:1234/v1",
                                 "http://100.64.0.7:8787/v1",      # Tailscale，埠剛好 8787 也不算
                                 "https://api.example.com/v1"])
def test_non_loopback_upstreams_unaffected(tmp_path, monkeypatch, url):
    _clear_env(monkeypatch)
    h = tmp_path / "home"
    _seed_pi(h, {"lan": {"baseUrl": url, "api": "openai-completions"}})
    assert possess.discover_install_upstreams(
        h, prefer=["pi"], proxy_port=PORT)["openai"]["url"] == url


def test_legacy_opencode_codex_claude_use_the_same_rule(tmp_path, monkeypatch):
    """opencode／codex／claude 那一段：讀的檔、順序、`source` 字串不變，只換判準。"""
    _clear_env(monkeypatch)
    h = tmp_path / "home"
    oc = h / ".config" / "opencode"
    oc.mkdir(parents=True)
    (oc / "opencode.json").write_text(json.dumps({"provider": {
        "vacant": {"options": {"baseURL": "http://127.0.0.1:8787/v1"}},   # 我們的 ⇒ 跳過
        "lm": {"options": {"baseURL": "http://127.0.0.1:1234/v1"}},       # 使用者的 ⇒ 採用
    }}), "utf-8")
    ups = possess.discover_install_upstreams(h, proxy_port=PORT)
    assert ups["openai"] == {"url": "http://127.0.0.1:1234/v1",
                             "source": "opencode:provider.lm"}

    (oc / "opencode.json").unlink()
    cx = h / ".codex"
    cx.mkdir()
    (cx / "config.toml").write_text(
        '[model_providers.vacant]\nbase_url = "http://127.0.0.1:18791/v1"\n\n'
        '[model_providers.ollama]\nbase_url = "http://localhost:11434/v1"\n', "utf-8")
    ups = possess.discover_install_upstreams(h, proxy_port=PORT)
    assert ups["openai"] == {"url": "http://localhost:11434/v1",
                             "source": "codex:model_providers.ollama"}

    cl = h / ".claude"
    cl.mkdir()
    sj = cl / "settings.json"
    sj.write_text(json.dumps({"env": {"ANTHROPIC_BASE_URL": "http://localhost:8787"}}),
                  "utf-8")
    # 舊判準對 claude 只看 "127.0.0.1" ⇒ localhost:8787（我們自己）會被採用；現在跳過
    assert envmap.is_sink(possess.discover_install_upstreams(
        h, proxy_port=PORT)["anthropic"]["url"])
    sj.write_text(json.dumps({"env": {"ANTHROPIC_BASE_URL": "http://127.0.0.1:4000"}}),
                  "utf-8")
    assert possess.discover_install_upstreams(h, proxy_port=PORT)["anthropic"] == {
        "url": "http://127.0.0.1:4000", "source": "claude:env.ANTHROPIC_BASE_URL"}


def test_pi_install_with_lm_studio_upstream_is_not_a_sink(tmp_path, monkeypatch):
    """端到端（不起服務）：展場的形狀——pi 指到本機 LM Studio ⇒ 上游是它、金鑰向它借、
    **沒有** sink 警告，extension 裡烤的也是它。"""
    _clear_env(monkeypatch)
    h = tmp_path / "home"
    url = "http://127.0.0.1:1234/v1"
    _seed_pi(h, {"lmstudio": {"baseUrl": url, "api": "openai-completions",
                              "apiKey": "lm-studio"}}, default="lmstudio")
    st = _install(h, agents=["pi"])
    assert st["upstreams"]["openai"] == {"url": url, "source": "pi:providers.lmstudio"}
    assert not any(w.startswith(possess.SINK_WARNING_HEAD) for w in st["warnings"])
    assert not any("借不到金鑰" in w for w in st["warnings"])
    body = (h / possess.AGENTS["pi"].config_file).read_text("utf-8")
    assert f'const UPSTREAM = "{url}";' in body
    assert 'const KEY_FROM = "lmstudio";' in body
    assert "const UPSTREAM_IS_SINK = false;" in body


# ══ 洞 5：extension 路點得亮 proven，而且永遠標路 ══════════════════════════

def _set_installed_at(h: pathlib.Path, ts: float) -> None:
    sp = possess.state_home(h) / "state.json"
    st = json.loads(sp.read_text("utf-8"))
    st["installed_at"] = ts
    sp.write_text(json.dumps(st), "utf-8")


def _installed_pi(tmp_path, monkeypatch) -> pathlib.Path:
    """裝好 pi，並把 `installed_at` 釘在合成事件（`T0` 起）**之前**——判準 0 只看這次安裝之後的證據。"""
    _clear_env(monkeypatch)
    h = tmp_path / "home"
    _seed_pi(h, {"lm": {"baseUrl": "http://127.0.0.1:1234/v1",
                        "api": "openai-completions"}})
    st = _install(h, agents=["pi"])
    assert st["channel"]["pi"]["ok"] is True
    _set_installed_at(h, T0 - 100)
    return h


def _hooks(h: pathlib.Path, events: list[tuple[str, float]], rid: str = RID,
           name: str | None = None) -> pathlib.Path:
    """照 `hookcli.emit` 的欄位合成一份常駐 extension 的掛鉤日誌。"""
    d = possess.state_home(h) / "hooks"
    d.mkdir(parents=True, exist_ok=True)
    p = d / (name or f"pi_{rid}.jsonl")
    with p.open("w", encoding="utf-8") as f:
        for ev, ts in events:
            f.write(json.dumps({"contract": "vacant-hook/1", "run_id": rid,
                                "agent": "pi", "event": ev, "ts": ts, "pid": 4242,
                                "payload_sha256": "0" * 64}) + "\n")
    return p


def _journal(h: pathlib.Path, recs: list[dict]) -> None:
    """照 `wireproxy._finish` 的欄位合成常駐 proxyd 的 `index.jsonl`。"""
    d = possess.state_home(h) / "proxyd" / "wire"
    d.mkdir(parents=True, exist_ok=True)
    with (d / "index.jsonl").open("w", encoding="utf-8") as f:
        for r in recs:
            f.write(json.dumps(r) + "\n")


def _call(ts: float, *, method="POST", path="/v1/chat/completions", status=200,
          call_id="c-model") -> dict:
    return {"call_id": call_id, "ts": ts, "mode": "tee", "wire": "openai",
            "method": method, "path": path, "status": status,
            "upstream": "http://127.0.0.1:1234" + path.split("?")[0]}


def _canary(ts: float = T0 + 0.15, rid: str = RID) -> dict:
    return _call(ts, method="GET", path=f"/v1/models?vacant_canary={rid}",
                 call_id="c-canary")


def _session(*, on: bool = True, off_at: float | None = None) -> list[tuple[str, float]]:
    ev = [("session_start", T0), ("canary", T0 + 0.1), ("canary_result", T0 + 0.2)]
    if on:
        ev.append(("vacant_on", T0 + 1))
    if off_at is not None:
        ev.append(("vacant_off", off_at))
    ev += [("user_prompt_submit", T0 + 2), ("before_provider_request", T0 + 3),
           ("stop", T0 + 10), ("session_end", T0 + 20)]
    return sorted(ev, key=lambda t: t[1])


def _pi_line(h: pathlib.Path) -> str:
    out = possess._fmt_status(possess.status(home=h))
    return next(ln for ln in out.splitlines() if ln.strip().startswith("pi "))


def test_extension_route_lights_proven_and_says_which_route(tmp_path, monkeypatch):
    h = _installed_pi(tmp_path, monkeypatch)
    assert possess.status(home=h)["channel"]["pi"]["proven"] is False
    hp = _hooks(h, _session())
    _journal(h, [_canary(), _call(T0 + 3.2, call_id="c-good")])
    s = possess.status(home=h)
    pi = s["channel"]["pi"]
    assert pi["proven"] is True
    assert pi["proven_via"] == "extension"
    assert list(pi["proven_routes"]) == ["extension"]
    assert "c-good" in pi["proven_routes"]["extension"]
    assert hp.name in pi["proven_routes"]["extension"]
    assert pi["extension_proof"]["call_id"] == "c-good"
    assert pi["extension_proof"]["run_id"] == RID
    # 🔴 狀態列：**標路**，而且講明只證通道
    line = _pi_line(h)
    assert "中介 ✓（extension 路）" in line
    assert "shim 路" not in line
    out = possess._fmt_status(s)
    assert "只證通道" in out and "沒有閘門" in out
    # 記進 state ⇒ 證據檔被清掉之後仍讀得出是哪一條路、哪一個 call_id
    st = json.loads((possess.state_home(h) / "state.json").read_text("utf-8"))
    assert st["channel"]["pi"]["proven_via"] == "extension"
    hp.unlink()
    again = possess.status(home=h)["channel"]["pi"]
    assert again["proven_via"] == "extension" and "c-good" in again["note"]
    # 🔴 不因此填 repo 級的實測紀錄
    assert possess.CHANNEL_MEASURED["pi"] == ""


def test_extension_route_negative_evidence_from_a_previous_install(tmp_path, monkeypatch):
    """`uninstall` 刻意留下 journal、掛鉤日誌也在 state 目錄 ⇒ 重裝之後上一輪的證據不准點亮這一輪。"""
    h = _installed_pi(tmp_path, monkeypatch)
    _hooks(h, _session())
    _journal(h, [_canary(), _call(T0 + 3.2)])
    _set_installed_at(h, T0 + 30)            # 這次安裝在那一輪之後
    pi = possess.status(home=h)["channel"]["pi"]
    assert pi["proven"] is False
    assert "這次安裝" in pi["extension_proof"]["reason"]
    _set_installed_at(h, T0 - 100)           # 對照：同一份證據，安裝在前 ⇒ 點得亮
    assert possess.status(home=h)["channel"]["pi"]["proven"] is True


def test_extension_route_negative_post_before_vacant_on(tmp_path, monkeypatch):
    """那一通 POST 發生在切到 vacant **之前** ⇒ 不是 vacant provider 打的，不算。"""
    h = _installed_pi(tmp_path, monkeypatch)
    _hooks(h, _session())
    _journal(h, [_canary(), _call(T0 + 0.5)])
    pi = possess.status(home=h)["channel"]["pi"]
    assert pi["proven"] is False and pi["proven_via"] is None
    assert "2xx" in pi["extension_proof"]["reason"]
    assert "未證實" in _pi_line(h)


@pytest.mark.parametrize("status", [401, 502, 0])
def test_extension_route_negative_non_2xx(tmp_path, monkeypatch, status):
    """401（借不到金鑰）／502（sink）／0（上游掛了）經過了 proxyd，但**叫不到模型**
    ⇒ 不准印成 ✓（比 shim 路嚴格，理由在 `extension_proof` 誠實邊界 4）。"""
    h = _installed_pi(tmp_path, monkeypatch)
    _hooks(h, _session())
    _journal(h, [_canary(), _call(T0 + 3.2, status=status)])
    pi = possess.status(home=h)["channel"]["pi"]
    assert pi["proven"] is False
    assert "401" in pi["extension_proof"]["reason"]


def test_extension_route_negative_without_vacant_on(tmp_path, monkeypatch):
    h = _installed_pi(tmp_path, monkeypatch)
    _hooks(h, _session(on=False))
    _journal(h, [_canary(), _call(T0 + 3.2)])
    pi = possess.status(home=h)["channel"]["pi"]
    assert pi["proven"] is False
    assert "vacant_on" in pi["extension_proof"]["reason"]
    assert "extension 路還沒證實" in possess._fmt_status(possess.status(home=h))


def test_extension_route_negative_after_vacant_off(tmp_path, monkeypatch):
    """`/vacant off`（或 `/model` 切走）之後的 before_provider_request 不算。"""
    h = _installed_pi(tmp_path, monkeypatch)
    _hooks(h, _session(off_at=T0 + 1.5))
    _journal(h, [_canary(), _call(T0 + 3.2)])
    pi = possess.status(home=h)["channel"]["pi"]
    assert pi["proven"] is False
    assert "vacant_on 之後沒有 before_provider_request" in pi["extension_proof"]["reason"]


def test_extension_route_negative_without_this_runs_canary(tmp_path, monkeypatch):
    """journal 沒有 per-agent 標記：沒有**這一跑**的 canary，窗內那一通可能是別的 agent 打的。"""
    h = _installed_pi(tmp_path, monkeypatch)
    _hooks(h, _session())
    _journal(h, [_canary(rid="another-run-id"), _call(T0 + 3.2)])
    pi = possess.status(home=h)["channel"]["pi"]
    assert pi["proven"] is False
    assert "canary" in pi["extension_proof"]["reason"]


def test_extension_route_accepts_the_extensions_own_canary_forms(tmp_path, monkeypatch):
    """extension 自己的 `refresh-<run_id>`／`status-<run_id>` 也綁得到這一跑。"""
    h = _installed_pi(tmp_path, monkeypatch)
    _hooks(h, _session())
    _journal(h, [_call(T0 + 0.3, method="GET", call_id="c-r",
                       path=f"/v1/models?vacant_canary=refresh-{RID}"),
                 _call(T0 + 3.2)])
    assert possess.status(home=h)["channel"]["pi"]["proven"] is True


@pytest.mark.parametrize("call", [
    _call(T0 + 3 + possess.EXT_PROOF_WINDOW_S + 1),                 # 窗外
    _call(T0 + 3.2, method="GET", path="/v1/models"),              # 不是模型呼叫
    _call(T0 + 3.2, path="/v1/messages/count_tokens"),             # 不是生成
])
def test_extension_route_negative_wrong_call(tmp_path, monkeypatch, call):
    h = _installed_pi(tmp_path, monkeypatch)
    _hooks(h, _session())
    _journal(h, [_canary(), call])
    pi = possess.status(home=h)["channel"]["pi"]
    assert pi["proven"] is False
    assert "沒有 2xx 的模型呼叫" in pi["extension_proof"]["reason"]


def test_shim_style_hook_log_cannot_impersonate_extension_route(tmp_path, monkeypatch):
    """shim 那條的掛鉤日誌在 per-run 目錄的 `hooks.jsonl`——長得再像也不在 extension 路的讀取範圍。"""
    h = _installed_pi(tmp_path, monkeypatch)
    run = possess.state_home(h) / "runs" / "r1"
    run.mkdir(parents=True)
    src = _hooks(h, _session())
    (run / "hooks.jsonl").write_bytes(src.read_bytes())
    src.unlink()
    _journal(h, [_canary(), _call(T0 + 3.2)])
    pi = possess.status(home=h)["channel"]["pi"]
    assert pi["proven"] is False
    # 檔名與行內 run_id 對不上的也不收
    _hooks(h, _session(), name="pi_some-other-id.jsonl")
    assert possess.status(home=h)["channel"]["pi"]["proven"] is False


def test_shim_proven_stays_via_shim(tmp_path, monkeypatch):
    """gateshim 那條（`mark_proven` 預設 `via="shim"`，呼叫方式不變）點亮的格子，
    之後 extension 路也有證據時：`proven_via` **仍是 shim**，兩條各自列出。"""
    h = _installed_pi(tmp_path, monkeypatch)
    assert inspect.signature(possess.mark_proven).parameters["via"].default == "shim"
    possess.mark_proven("pi", 7, home=h)                  # gateshim 的叫法，一字不改
    pi = possess.status(home=h)["channel"]["pi"]
    assert pi["proven"] is True and pi["proven_via"] == "shim"
    assert list(pi["proven_routes"]) == ["shim"]
    assert "requests_seen=7" in pi["proven_routes"]["shim"]
    line = _pi_line(h)
    assert "中介 ✓（shim 路）" in line and "extension" not in line

    _hooks(h, _session())
    _journal(h, [_canary(), _call(T0 + 3.2)])
    pi = possess.status(home=h)["channel"]["pi"]
    assert pi["proven_via"] == "shim"
    assert list(pi["proven_routes"]) == ["shim", "extension"]
    assert "中介 ✓（shim 路＋extension 路）" in _pi_line(h)
    st = json.loads((possess.state_home(h) / "state.json").read_text("utf-8"))
    assert st["channel"]["pi"]["proven_via"] == "shim"
    assert "requests_seen=7" in st["channel"]["pi"]["proven_note"]
    # 之後 shim 再跑一次：proven_note 照舊更新成 shim 最新那一筆
    possess.mark_proven("pi", 3, home=h)
    st = json.loads((possess.state_home(h) / "state.json").read_text("utf-8"))
    assert st["channel"]["pi"]["proven_via"] == "shim"
    assert "requests_seen=3" in st["channel"]["pi"]["proven_note"]
    assert "c-model" in st["channel"]["pi"]["proven_routes"]["extension"]


def test_legacy_state_without_proven_via_reads_as_shim(tmp_path, monkeypatch):
    """2026-09-24 之前的 state 只有 `proven`＋`proven_note`：那時候唯一的呼叫者是 gateshim。"""
    h = _installed_pi(tmp_path, monkeypatch)
    sp = possess.state_home(h) / "state.json"
    st = json.loads(sp.read_text("utf-8"))
    st["channel"]["pi"].update(proven=True,
                               proven_note="requests_seen=2 @ 2026-09-22T05:28:41+0000")
    sp.write_text(json.dumps(st), "utf-8")
    pi = possess.status(home=h)["channel"]["pi"]
    assert pi["proven_via"] == "shim"
    assert pi["proven_routes"] == {"shim": "requests_seen=2 @ 2026-09-22T05:28:41+0000"}


def test_mark_proven_rejects_unknown_route_and_zero(tmp_path, monkeypatch):
    h = _installed_pi(tmp_path, monkeypatch)
    with pytest.raises(ValueError):
        possess.mark_proven("pi", 5, home=h, via="gate")
    possess.mark_proven("pi", 0, home=h, via="extension")
    assert possess.status(home=h)["channel"]["pi"]["proven"] is False


def test_extension_route_only_applies_to_agents_with_a_resident_extension(tmp_path):
    r = possess.extension_proof(tmp_path, agent="codex")
    assert r["proven"] is False and "沒有常駐 extension" in r["reason"]
