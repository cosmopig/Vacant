"""收據的對帳欄位與 fail-closed 分級（`DECISION_20260920_COMPLETE_MEDIATION` §二 P0）。

守的是四個欄位與一個級別，**每一條都配一個負控制**——沒有負控制的
「量到了」等於沒量（這個 repo 一個晚上累積了 19 個「量具說謊」的案例，
其中三個就在這條線上：啟動橫幅說謊、`[ -S socket ]` ≠ 門活著、
`grep -c` 沒命中印 0 又回 1）。

| 欄位 | 正控制 | 負控制 |
|---|---|---|
| `enclosure.applied` | 只有 `lo` ＋ netns 跟外面不同 ⇒ `True` | 這台 macOS 跑一次 ⇒ **`False`**（不是 `0`、不是缺欄位）；問不出來 ⇒ `None` |
| `framework_hook.canary_fired` | 掛鉤真的跑過 ⇒ `True` | 掛鉤拆掉 ⇒ `False` ＋**自動降級**；沒裝過 ⇒ `None` |
| `reconciled.unexplained` | 每通都對得上 ⇒ `0` | 多一通對不上 ⇒ `> 0` ＋降級；沒量到 ⇒ `None`（**不是 0**） |
| `tier` | 三者皆成立 ⇒ `A` | 缺任一 ⇒ B／B′／C；C ⇒ **拒發收據** |

⚠ 本檔零外部網路：上游是本機假 server。
⚠ 本檔的 enclosure 正控制是**注入的探針結果**（macOS 上沒有 netns）。
  真的在圍牆裡量到的那一格在 Linux 上跑，證據落在
  `ops/vacantrun/enclosure_20260920/evidence/`——**兩者不可混講成一組數字**。
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import socket
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from vacant_network.vrun import attest, hookcli, launcher                # noqa: E402
from vacant_network.vrun.wireproxy import WireProxy                      # noqa: E402


# ── 假上游 ─────────────────────────────────────────────────────────────
class _Upstream(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):          # noqa: D102
        return

    def _any(self):
        n = int(self.headers.get("Content-Length") or 0)
        if n:
            self.rfile.read(n)
        payload = b'{"ok":true}'
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    do_GET = do_POST = _any                                      # noqa: N815


@pytest.fixture()
def upstream():
    srv = ThreadingHTTPServer(("127.0.0.1", 0), _Upstream)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        yield f"http://127.0.0.1:{srv.server_address[1]}"
    finally:
        srv.shutdown()
        srv.server_close()


# ── 1. enclosure：三態 ＋ 負控制 ───────────────────────────────────────

def test_enclosure_negative_control_is_false_not_zero_not_missing():
    """**負控制**：這台機器沒有套 enclosure ⇒ `applied` 必須是 `False`。

    ⚠ 三件事都要驗，缺一不可：
      (1) 是 `False` 不是 `0`（`False == 0` 在 Python 是真的，所以用 `is`）；
      (2) 欄位**存在**（缺欄位跟 `null` 在 JSON 裡長得一樣，但意思不同）；
      (3) `ns_id`／`policy_sha256` 兩欄也在（沒量到就寫 `null`）。
    """
    enc = attest.probe_enclosure(policy_path="/nonexistent/policy.json")
    assert "applied" in enc and "ns_id" in enc and "policy_sha256" in enc
    assert enc["applied"] is False, enc["probe"]["reason"]
    assert enc["applied"] is not 0            # noqa: F632 - 這一條就是要驗身分
    assert enc["policy_sha256"] is None, "沒有政策檔 ⇒ null，不是空字串"
    assert enc["probe"]["interfaces"] and set(enc["probe"]["interfaces"]) - {"lo"}


def test_enclosure_positive_only_lo_and_ns_differs(tmp_path, monkeypatch):
    """正控制：只有 `lo` ＋ netns 跟圍牆外面不同 ⇒ `applied=True`（硬證據）。"""
    policy = tmp_path / "policy.json"
    policy.write_text(json.dumps({"version": 1,
                                  "outer_net_ns": "net:[4026531840]",
                                  "door_sock": str(tmp_path / "nope.sock")}),
                      encoding="utf-8")
    monkeypatch.setattr(socket, "if_nameindex", lambda: [(1, "lo")])
    monkeypatch.setattr(attest, "_net_ns_id", lambda: "net:[4026533226]")
    enc = attest.probe_enclosure(policy_path=policy)
    assert enc["applied"] is True
    assert enc["ns_id"] == "net:[4026533226]"
    assert enc["probe"]["ns_differs_from_outer"] is True
    # `policy_sha256` **對得上實際用的那一份政策**
    assert enc["policy_sha256"] == hashlib.sha256(
        policy.read_bytes()).hexdigest()
    # 門的路徑給了但沒有人在聽 ⇒ False（不是 None）
    assert enc["probe"]["door_reachable"] is False


def test_enclosure_same_ns_as_outer_is_false_even_with_only_lo(tmp_path,
                                                               monkeypatch):
    """**硬否證的負控制**：只有 `lo` 但 netns 跟外面同一個 ⇒ 還是 `False`。

    這一格擋的是「一台本來就只有 `lo` 的機器被讀成進了圍牆」。
    """
    policy = tmp_path / "policy.json"
    policy.write_text(json.dumps({"outer_net_ns": "net:[4026531840]"}),
                      encoding="utf-8")
    monkeypatch.setattr(socket, "if_nameindex", lambda: [(1, "lo")])
    monkeypatch.setattr(attest, "_net_ns_id", lambda: "net:[4026531840]")
    enc = attest.probe_enclosure(policy_path=policy)
    assert enc["applied"] is False
    assert enc["probe"]["ns_differs_from_outer"] is False


def test_enclosure_unmeasured_is_none_not_false(monkeypatch):
    """**問不出來 ⇒ `None`**，不是 `False`。鐵律 3 的核心那一格。"""
    def _boom():
        raise OSError("no such thing on this platform")
    monkeypatch.setattr(socket, "if_nameindex", _boom)
    monkeypatch.setattr(attest, "_net_ns_id", lambda: None)
    enc = attest.probe_enclosure(policy_path="/nonexistent")
    assert enc["applied"] is None
    assert enc["applied"] is not False


# ── 2. 掛鉤 canary：三態 ＋ 負控制 ─────────────────────────────────────

def test_hook_canary_unmeasured_vs_false(tmp_path):
    """**沒裝過 ⇒ `None`；裝過卻沒日誌 ⇒ `False`。** 這兩格不可以同形。

    右邊那一格就是 Linux 上 `install-status` 說「✓ 已寫入」而 codex 其實
    起不來的病——**不准用「我們裝過了」推論「它在」**。
    """
    log = tmp_path / "hooks.jsonl"
    never = attest.probe_framework_hook(agent="codex", hook_log=log,
                                        install_attempted=None)
    assert never["canary_fired"] is None

    claimed = attest.probe_framework_hook(agent="codex", hook_log=log,
                                          install_attempted=True)
    assert claimed["canary_fired"] is False, "宣稱裝過卻沒有日誌＝量到假的"


def test_hook_canary_fired_and_torn_down(tmp_path):
    """正控制（燒了）＋ 負控制（把那一行拆掉 ⇒ `False`）。"""
    log = tmp_path / "hooks.jsonl"
    log.write_text(
        json.dumps({"contract": attest.CONTRACT_VERSION, "event": "session_start",
                    "ts": 1.0}) + "\n"
        + json.dumps({"contract": attest.CONTRACT_VERSION, "event": "canary",
                      "ts": 1.1, "agent": "claude"}) + "\n", encoding="utf-8")
    fired = attest.probe_framework_hook(agent="claude", hook_log=log,
                                        install_attempted=True)
    assert fired["canary_fired"] is True
    assert fired["contract_version"] == attest.CONTRACT_VERSION
    assert fired["version_drift"] is False
    assert fired["events_n"] == 2

    # 負控制：掛鉤被拆掉 ⇒ 只剩別的事件、沒有 canary
    log.write_text(json.dumps({"event": "pre_tool_use", "ts": 2.0}) + "\n",
                   encoding="utf-8")
    torn = attest.probe_framework_hook(agent="claude", hook_log=log,
                                       install_attempted=True)
    assert torn["canary_fired"] is False
    assert torn["events_n"] == 1


def test_contract_version_comes_from_the_line_not_our_constant(tmp_path):
    """`contract_version` 讀的是**掛鉤自己寫的那個版本**，不是本檔的常數。

    不然它就變成「我們裝的是 v1 所以它是 v1」——同一種推論錯誤。
    """
    log = tmp_path / "hooks.jsonl"
    log.write_text(json.dumps({"contract": "vacant-hook/999",
                               "event": "canary", "ts": 1.0}) + "\n",
                   encoding="utf-8")
    hk = attest.probe_framework_hook(agent="pi", hook_log=log,
                                     install_attempted=True)
    assert hk["contract_version"] == "vacant-hook/999"
    assert hk["version_drift"] is True


# ── 3. 對帳：三態 ＋ 負控制 ────────────────────────────────────────────

def _call(ts, path="/v1/chat/completions", cid="c"):
    return {"call_id": cid, "ts": ts, "path": path, "status": 200}


def _ev(ts, event="post_tool_use"):
    return {"event": event, "ts": ts}


def test_reconcile_unmeasured_is_none_not_zero():
    """**兩邊任一邊沒量到 ⇒ `unexplained=None`**，而 `None` 達不到 A 級。"""
    r = attest.reconcile(relay_calls=None, hook_events=[_ev(1.0)])
    assert r["unexplained"] is None and r["relay_calls"] is None
    r2 = attest.reconcile(relay_calls=[_call(1.0)], hook_events=None)
    assert r2["unexplained"] is None and r2["hook_events"] is None
    assert r2["relay_calls"] == 1, "中繼那一邊量到了就要寫出來"
    # 沒量到不可以被當成 0：級別必須降下來
    enc = {"applied": True}
    assert attest.grade(enc, {"canary_fired": True}, r2)["tier"] == attest.TIER_B


def test_reconcile_zero_and_the_one_that_does_not_match():
    """正控制：每通都對得上 ⇒ `0`。負控制：多一通 ⇒ `> 0` ＋降級。"""
    hooks = [_ev(1.0, "user_prompt_submit"), _ev(2.0), _ev(3.0)]
    ok = attest.reconcile(relay_calls=[_call(1.5), _call(2.5), _call(3.5)],
                          hook_events=hooks)
    assert ok["unexplained"] == 0 and ok["relay_calls"] == 3
    assert attest.grade({"applied": True}, {"canary_fired": True},
                        ok)["tier"] == attest.TIER_A

    # 負控制：**同一份掛鉤事件**，中繼多一通（有人直接對門 curl 了一發）
    bad = attest.reconcile(
        relay_calls=[_call(1.5), _call(2.5), _call(3.5), _call(3.9, cid="rogue")],
        hook_events=hooks)
    assert bad["unexplained"] == 1
    assert bad["unexplained_detail"][0]["call_id"] == "rogue"
    g = attest.grade({"applied": True}, {"canary_fired": True}, bad)
    assert g["tier"] == attest.TIER_B, "對帳沒過就不准是 A 級"
    assert g["attested"] is False


def test_session_start_alone_does_not_explain_a_call():
    """**`session_start` 不是一個回合開端**——它不會自己引起一通模型呼叫。

    ⚠ 這一格是負控制抓出來的：2026-09-20 vacant-dev 的 `rogue` 那一格真的
      多打了一通，而對帳因為把 `session_start` 算成額度而回 `unexplained=0`。
      **假陰性比沒有這個欄位更糟。**
    """
    r = attest.reconcile(
        relay_calls=[_call(1.5), _call(2.5)],
        hook_events=[_ev(1.0, "session_start"), _ev(1.1, "canary")])
    assert r["unexplained"] == 1, "只有 canary 那一個額度，第二通對不上"


def test_a_call_before_any_hook_event_is_unexplained():
    """次序也算：掛鉤事件**之前**就發生的那一通對不上。"""
    r = attest.reconcile(relay_calls=[_call(0.5)], hook_events=[_ev(1.0)])
    assert r["unexplained"] == 1


# ── 4. 分級表 ＋ 三態防呆 ──────────────────────────────────────────────

@pytest.mark.parametrize("enc,hook,unexp,tier", [
    (True, True, 0, attest.TIER_A),
    (True, True, 1, attest.TIER_B),
    (True, False, None, attest.TIER_B),
    (True, None, None, attest.TIER_B),
    (False, True, 0, attest.TIER_B_PRIME),
    (False, False, None, attest.TIER_C),
    (None, None, None, attest.TIER_C),
])
def test_grade_table(enc, hook, unexp, tier):
    g = attest.grade({"applied": enc}, {"canary_fired": hook},
                     {"unexplained": unexp})
    assert g["tier"] == tier
    assert g["attested"] is (tier == attest.TIER_A)
    assert g["sentence"] == attest.TIER_SENTENCE[tier]


def test_exhibition_only_allows_A():
    """展場只允許 A 級（裁決 §三-3）：只有 A 的退出碼是「不覆蓋」。"""
    assert attest.TIER_EXIT[attest.TIER_A] is None
    assert attest.TIER_EXIT[attest.TIER_B] == 24
    assert attest.TIER_EXIT[attest.TIER_B_PRIME] == 25
    assert attest.TIER_EXIT[attest.TIER_C] == 26
    assert len({24, 25, 26} & {0, 20, 21, 22, 23}) == 0, \
        "新碼不可以跟既有的五個碼撞"


def test_three_state_guards_are_executable():
    """鐵律 3 的防呆**要擋得住**，不是寫在文件裡。"""
    with pytest.raises(ValueError):
        attest.assert_three_state({"applied": 0}, ("applied",))
    with pytest.raises(ValueError):
        attest.assert_three_state({}, ("applied",))          # 缺欄位
    with pytest.raises(ValueError):
        attest.assert_count_three_state({"relay_calls": False}, ("relay_calls",))
    # 合法的三態一個都不准被誤擋
    attest.assert_three_state({"applied": None}, ("applied",))
    attest.assert_three_state({"applied": False}, ("applied",))
    attest.assert_count_three_state({"relay_calls": 0}, ("relay_calls",))
    attest.assert_count_three_state({"relay_calls": None}, ("relay_calls",))


# ── 5. canary 真的跑一遍：掛鉤 ⇒ 日誌 ＋ **中繼 journal** ──────────────

def test_canary_fires_both_probes_end_to_end(tmp_path, upstream, monkeypatch):
    """兩個探針一次驗完：掛鉤寫下那一行 **且** 中繼 journal 看得到那一通。

    ⚠ 第二個探針是被實測逼出來的：`network_proxy` 關著的時候 allowlist
      **設了、不報錯、也不執行** ⇒ **收據不可以只檢查設定檔寫了什麼**。
    """
    wire = tmp_path / "w"
    px = WireProxy(wire_dir=wire, upstreams={"openai": upstream,
                                             "anthropic": upstream},
                   keys={}, sentinel="", mode="tee", port=0)
    px.start()
    log = tmp_path / "hooks.jsonl"
    monkeypatch.setenv("VACANT_HOOK_LOG", str(log))
    monkeypatch.setenv("VACANT_RUN_ID", "runX")
    monkeypatch.setenv("VACANT_HOOK_AGENT", "claude")
    monkeypatch.setenv("VACANT_RUN_PROXY", px.url)
    try:
        assert hookcli.handle("session_start") == 0
        px.quiesce()
    finally:
        px.stop()

    hk = attest.probe_framework_hook(agent="claude", hook_log=log,
                                     run_id="runX", install_attempted=True)
    assert hk["canary_fired"] is True

    calls = attest.read_relay_calls(wire / "index.jsonl")
    assert calls is not None and len(calls) == 1
    assert attest.CANARY_QUERY_KEY in calls[0]["path"]
    assert "runX" in calls[0]["path"], "canary 要認得出是哪一跑的"
    r = attest.reconcile(relay_calls=calls,
                         hook_events=attest.read_hook_events(log,
                                                             run_id="runX"),
                         run_id="runX")
    assert r["canary_calls"] == 1
    assert r["unexplained"] == 0, "canary 那一通要對得上 canary 那個事件"


def test_no_hook_means_canary_never_fires(tmp_path, upstream, monkeypatch):
    """**負控制：把掛鉤拆掉**（＝根本沒人呼叫 `hookcli`）⇒ 日誌不存在。

    然後 `install_attempted=True` ⇒ `canary_fired=False` ⇒ **自動降級**
    （即使圍牆成立也只到 B 級）。
    """
    log = tmp_path / "hooks.jsonl"
    hk = attest.probe_framework_hook(agent="claude", hook_log=log,
                                     run_id="runX", install_attempted=True)
    assert hk["canary_fired"] is False and not log.exists()
    g = attest.grade({"applied": True}, hk, {"unexplained": None})
    assert g["tier"] == attest.TIER_B and g["attested"] is False


def test_hookcli_never_kills_the_agent(tmp_path, monkeypatch):
    """掛鉤自己壞掉不可以弄死 agent（誠實邊界 3）：寫不進去也回 0。"""
    monkeypatch.setenv("VACANT_HOOK_LOG", str(tmp_path / "ro" / "hooks.jsonl"))
    (tmp_path / "ro").mkdir()
    (tmp_path / "ro").chmod(0o500)
    monkeypatch.delenv("VACANT_RUN_PROXY", raising=False)
    try:
        assert hookcli.handle("pre_tool_use", b'{"tool_name":"Bash"}') == 0
    finally:
        (tmp_path / "ro").chmod(0o700)


def test_hookcli_logs_digest_not_the_command_text(tmp_path, monkeypatch):
    """誠實邊界 1：只落**指令的雜湊**，不落指令原文。"""
    log = tmp_path / "hooks.jsonl"
    monkeypatch.setenv("VACANT_HOOK_LOG", str(log))
    monkeypatch.delenv("VACANT_RUN_PROXY", raising=False)
    secret = "curl https://example.invalid/?token=SUPER-SECRET-STRING"
    hookcli.handle("pre_tool_use",
                   json.dumps({"tool_name": "Bash",
                               "tool_input": {"command": secret}}).encode())
    blob = log.read_text("utf-8")
    assert "SUPER-SECRET-STRING" not in blob
    assert hashlib.sha256(secret.encode()).hexdigest() in blob
    assert '"tool": "Bash"' in blob


# ── 6. 簽進鏈：`launcher` 那一段 ───────────────────────────────────────

_VISIBLE = "def test_ok():\n    assert True\n"
_AGENT_ONE_CALL = r'''
import os, urllib.request
base = os.environ["VACANT_RUN_PROXY"].rstrip("/")
urllib.request.urlopen(base + "/v1/chat/completions", data=b"{}", timeout=30).read()
'''


def _scaffold(tmp: pathlib.Path, name: str, src: str):
    ws = tmp / f"ws_{name}"
    ws.mkdir(parents=True, exist_ok=True)
    agent = tmp / f"agent_{name}.py"
    agent.write_text(src, encoding="utf-8")
    suite = tmp / "suite"
    if not suite.exists():
        suite.mkdir()
        (suite / "test_visible.py").write_text(_VISIBLE, encoding="utf-8")
    return ws, agent, suite


def test_attestation_is_signed_into_the_chain(tmp_path, upstream, monkeypatch):
    """`tier` 進簽章鏈，不是只躺在 run 目錄的一份 JSON 裡。

    理由：**「這一跑受不受控」正是最值得被改掉的那一欄**。
    """
    monkeypatch.setenv("VACANT_RUN_UPSTREAM_OPENAI", upstream)
    monkeypatch.setenv("VACANT_ATTEST", "warn")
    monkeypatch.delenv("VACANT_HOOK_LOG", raising=False)
    monkeypatch.delenv("VACANT_HOOK_AGENT", raising=False)
    ws, agent, suite = _scaffold(tmp_path, "signed", _AGENT_ONE_CALL)
    run_dir = tmp_path / "rd_signed"
    s = launcher.run([sys.executable, str(agent)], workspace=ws,
                     run_dir=run_dir, suite_dir=suite, vacant_on=True,
                     task_id="signed_cell", sandbox_name="none")
    att = s["attestation"]
    assert att is not None and att["tier"] in ("A", "B", "B'", "C")
    chain = json.loads((run_dir / f"receipts_{launcher.ARM_ON}.ndjson"
                        ).read_text("utf-8").splitlines()[-1])
    p = chain["payload"]
    assert p["tier"] == att["tier"]
    assert p["attested"] == att["attested"]
    assert p["enclosure_applied"] is att["enclosure"]["applied"]
    assert p["canary_fired"] is att["framework_hook"]["canary_fired"]
    assert p["attestation_sha256"] == hashlib.sha256(
        json.dumps(att, sort_keys=True, ensure_ascii=False,
                   separators=(",", ":")).encode("utf-8")).hexdigest()


def test_attest_off_writes_null_not_false(tmp_path, upstream, monkeypatch):
    """`VACANT_ATTEST=off` ⇒ 鏈上是 `null`＝**沒量到**，不是「量到沒有」。

    這一格也順便守住既有資料：舊鏈沒有這些欄位，讀出來一樣是「沒量到」。
    """
    monkeypatch.setenv("VACANT_RUN_UPSTREAM_OPENAI", upstream)
    monkeypatch.setenv("VACANT_ATTEST", "off")
    ws, agent, suite = _scaffold(tmp_path, "off", _AGENT_ONE_CALL)
    run_dir = tmp_path / "rd_off"
    s = launcher.run([sys.executable, str(agent)], workspace=ws,
                     run_dir=run_dir, suite_dir=suite, vacant_on=True,
                     task_id="off_cell", sandbox_name="none")
    assert s["attestation"] is None
    chain = json.loads((run_dir / f"receipts_{launcher.ARM_ON}.ndjson"
                        ).read_text("utf-8").splitlines()[-1])
    p = chain["payload"]
    for k in ("tier", "attested", "enclosure_applied", "canary_fired",
              "unexplained", "attestation_sha256"):
        assert k in p, f"{k} 欄位要在（缺欄位 ≠ null）"
        assert p[k] is None, f"{k} 應該是 null（沒量到）而不是 {p[k]!r}"


# ── 7. 級別蓋不蓋既有退出碼：**既有語意不准被動到** ────────────────────

@pytest.mark.parametrize("verdict,tier,mode,want", [
    # `off`／`warn` ⇒ 一個字都不動（本輪驗收第 6 項）
    (0, "C", "off", 0), (20, "C", "off", 20), (21, "C", "off", 21),
    (22, "C", "off", 22), (23, "C", "off", 23),
    (0, "C", "warn", 0), (20, "C", "warn", 20), (21, "C", "warn", 21),
    (22, "C", "warn", 22), (23, "C", "warn", 23),
    # `fail` ⇒ 蓋，但 A 級不蓋、22 不蓋
    (0, "A", "fail", 0), (20, "A", "fail", 20),
    (0, "B", "fail", 24), (20, "B'", "fail", 25), (0, "C", "fail", 26),
    (21, "C", "fail", 26), (23, "C", "fail", 26),
    (22, "C", "fail", 22),      # ⚠ infra_void 不准被級別蓋掉
    (0, None, "fail", 0),       # 沒量到級別 ⇒ 不蓋
])
def test_apply_tier_exit(verdict, tier, mode, want):
    from vacant_network.vrun import gateshim
    assert gateshim.apply_tier_exit(verdict, tier, mode) == want


# ── 8. 跟 `verify_receipts` 那一套對齊 ─────────────────────────────────

def test_verify_surfaces_tier_and_does_not_touch_verdict(tmp_path, upstream,
                                                         monkeypatch):
    """驗章器讀得到 `tier`／`attested`，而且**不因為級別低就改判**。

    紀律逐字沿用 `mediated`：級別低不代表鏈壞了，兩個維度混成一個
    就分不出「鏈被改過」與「這一跑沒受控」。
    """
    from vacant_network.vrun import verify_receipts as vrr
    monkeypatch.setenv("VACANT_RUN_UPSTREAM_OPENAI", upstream)
    monkeypatch.setenv("VACANT_ATTEST", "warn")
    ws, agent, suite = _scaffold(tmp_path, "vfy", _AGENT_ONE_CALL)
    run_dir = tmp_path / "rd_vfy"
    launcher.run([sys.executable, str(agent)], workspace=ws, run_dir=run_dir,
                 suite_dir=suite, vacant_on=True, task_id="vfy_cell",
                 sandbox_name="none")
    rec = vrr.verify_run(run_dir)[0]
    assert rec["tier"] == "C", "這台機器沒有圍牆也沒有掛鉤"
    assert rec["attested"] is False
    assert rec["unattested_task_ids"] == ["vfy_cell"]
    # ⚠ **verdict 沒有被級別動到**
    assert rec["verdict"] == "OK" and rec["chain_ok"] is True
    assert vrr.run_glob(str(run_dir))["verdict"] == "OK"
    assert vrr.exit_code(vrr.run_glob(str(run_dir))) == vrr.EXIT_OK
    # 明講要 A 級（展場那條線）才有牙齒
    out = vrr.run_glob(str(run_dir), require_tier="A")
    assert out["verdict"] == "BROKEN"
    assert out["chains"][0]["failures"][-1]["reason"] == "tier_below_required"
    assert out["tier_histogram"] == {"C": 1}
    assert out["unattested_chains_n"] == 1


def test_old_chains_without_tier_are_unmeasured_not_failed(tmp_path, upstream,
                                                           monkeypatch):
    """**舊鏈一個 byte 都不會改判**：沒有 `tier` 欄位 ⇒ `attested=null`。"""
    from vacant_network.vrun import verify_receipts as vrr
    monkeypatch.setenv("VACANT_RUN_UPSTREAM_OPENAI", upstream)
    monkeypatch.setenv("VACANT_ATTEST", "off")     # ＝舊鏈的形狀
    ws, agent, suite = _scaffold(tmp_path, "oldchain", _AGENT_ONE_CALL)
    run_dir = tmp_path / "rd_old"
    launcher.run([sys.executable, str(agent)], workspace=ws, run_dir=run_dir,
                 suite_dir=suite, vacant_on=True, task_id="old_cell",
                 sandbox_name="none")
    rec = vrr.verify_run(run_dir)[0]
    assert rec["attested"] is None and rec["tier"] is None
    assert rec["verdict"] == "OK"
    out = vrr.run_glob(str(run_dir))
    assert out["chains_without_tier_n"] == 1
    assert out["attested_chains_n"] == 0 and out["unattested_chains_n"] == 0
    assert out["verdict"] == "OK"
