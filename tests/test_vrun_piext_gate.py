"""pi 互動模式的閘門（`agent_before_settle`）——**行為**測試。證據等級：**L-fake**。

`piext.render()` 出來的 extension 當 ES module 載進 node，塞一個假的 `pi`（照 pi 0.87.0
`docs/extensions.md` 的事件名與 payload 形狀：`agent_before_settle` 的
`{type, entries, continue, context:{canContinue}, outcome}`、回傳 `{entries, continue}`），
其餘全部是真的：extension 真的 spawn `python -m vacant_network.vrun.piext gate …`、
真的凍結工作區、真的跑 `acceptance.run_suite`、真的簽收據，掛鉤走真的 `hookcli`。
「模型呼叫」＝ harness 燒一次 `before_provider_request` 掛鉤、再往常駐 proxyd 的 journal
（`<state>/proxyd/wire/index.jsonl`）寫一行——**沒有真 pi、沒有真 proxyd、沒有真模型**。

⚠ 這裡量不到的（要真 pi 才能驗，`piext` 誠實邊界 G7）：真 pi 會不會照文件在收手時
`await` 這個 handler、`custom_message` 在 TUI 長什麼樣、`continue:true` 是否恰好多一通
provider request、排隊的 follow-up 會不會燒 `before_agent_start`。

收據用**同一把尺**驗（`verify_receipts`），而且**先跑它的 selftest**——尺自己壞了的話，
下面每一個 OK 都不算數。沒有 node ⇒ skip 並印理由（量不到不是通過）。
"""
from __future__ import annotations

import json
import os
import pathlib
import shutil
import subprocess
import sys

import pytest

from vacant_network.logbook import Logbook
from vacant_network.vrun import piext, verify_receipts

REPO = pathlib.Path(__file__).resolve().parents[1]

#: 隱藏測資的 canary（形狀照抄 `tests/test_vacant_run_retry.py`）。互動路徑**根本沒有**
#: 隱藏驗收；這一組是用來證明「回饋只吃被解析到的那一份可見驗收」，並且量具有牙齒。
GT_CANARY = "CANARY_GT_7b1d44"
NUM_CANARY = "919191919191"

_VISIBLE_TEST = '''
def check_add():
    from solution import add
    assert add(2, 3) == 5
'''

_HIDDEN_TEST = f'''
def check_hidden():
    from solution import add
    # {GT_CANARY}
    assert add(1, 1) == {NUM_CANARY}, "hint {GT_CANARY}"
'''

_GOOD = "def add(a, b):\n    return a + b\n"
_BAD = "def add(a, b):\n    return a - b\n"

_HARNESS = r"""
import cp from "node:child_process";
import { syncBuiltinESMExports } from "node:module";
import fs from "node:fs";
import path from "node:path";
const [, , extPath, scriptJson] = process.argv;
const script = JSON.parse(scriptJson);
const WS = script.ws, STATE = script.state;

// fire() 的每一次呼叫：記事件名＋payload，然後照常跑真的 hookcli（hookcli 只落雜湊）
const fired = [];
const realSpawnSync = cp.spawnSync;
cp.spawnSync = function (cmd, args, o) {
  try { fired.push({ event: args[args.length - 1], payload: JSON.parse((o && o.input) || "{}") }); }
  catch (e) { fired.push({ event: args[args.length - 1], payload: null }); }
  return realSpawnSync.apply(this, arguments);
};
syncBuiltinESMExports();
globalThis.fetch = async () => { throw new Error("no network in test"); };

const providers = {}, commands = {}, handlers = {}, notes = [];
let current = { provider: "openai", id: "gpt-x" };
const registry = {
  models: [{ provider: "openai", id: "gpt-x" }],
  find(p, id) { return this.models.find((m) => m.provider === p && m.id === id) || null; },
  getAll() { return this.models; },
};
async function emitSelect(m, source) {
  const prev = current; current = m;
  for (const fn of handlers["model_select"] || []) await fn({ model: m, previousModel: prev, source });
}
const pi = {
  registerProvider(id, cfg) {
    providers[id] = cfg;
    for (const m of cfg.models) registry.models.push({ provider: id, id: m.id });
  },
  registerCommand(name, cfg) { commands[name] = cfg; },
  on(ev, fn) { (handlers[ev] = handlers[ev] || []).push(fn); },
  async setModel(m) { await emitSelect(m, "set"); return true; },
};
const hasUI = script.hasUI !== false;
const ctx = () => ({ hasUI, ui: { notify: (text, level) => notes.push({ text, level }) },
                     modelRegistry: registry, model: current, cwd: WS, signal: undefined });
async function emit(ev, event) {
  const out = [];
  for (const fn of handlers[ev] || []) out.push(await fn(event, ctx()));
  return out;
}
// 常駐 proxyd journal 的一行（欄位照 wireproxy 的索引）
const journal = path.join(STATE, "proxyd", "wire", "index.jsonl");
let calls = 0;
function journalCall(status, p) {
  fs.mkdirSync(path.dirname(journal), { recursive: true });
  calls += 1;
  fs.appendFileSync(journal, JSON.stringify({
    call_id: "c" + calls, ts: Date.now() / 1000, mode: "tee", wire: "openai", method: "POST",
    path: p || "/v1/chat/completions", upstream: "http://up.test/v1/chat/completions",
    request_sha256: String(calls).padStart(64, "a"), request_bytes: 10, body_rewritten: false,
    status: status || 200, error: null, response_sha256: String(calls).padStart(64, "b"),
    response_bytes: 10 }) + "\n");
}

const mod = await import(extPath);
mod.default(pi);

const settles = [];
for (const st of script.steps) {
  if (st.do === "session_start") await emit("session_start", { reason: "startup" });
  else if (st.do === "command") await commands.vacant.handler(st.args, ctx());
  else if (st.do === "prompt") await emit("before_agent_start", { prompt: "do the task" });
  else if (st.do === "model_call") {
    await emit("before_provider_request", { payload: {} });
    if (st.journal !== false) journalCall(st.status);
  } else if (st.do === "tool") {
    await emit("tool_call", { toolName: "write", input: { path: "solution.py" } });
    await emit("tool_result", { toolName: "write" });
  } else if (st.do === "probe_call") journalCall(200, "/v1/models?vacant_canary=refresh-x");
  else if (st.do === "write") {
    const p = st.abs ? st.path : path.join(WS, st.path);
    fs.mkdirSync(path.dirname(p), { recursive: true });
    fs.writeFileSync(p, st.text);
  } else if (st.do === "tamper_snapshot") {
    const root = path.join(process.env.HOME, ".vacant-run");
    const d = fs.readdirSync(root).find((x) => x.startsWith("pi_"));
    fs.appendFileSync(path.join(root, d, "suite", st.file), st.text);
  } else if (st.do === "agent_end") await emit("agent_end", { messages: [] });
  else if (st.do === "settle") {
    const res = await emit("agent_before_settle", {
      type: "agent_before_settle", entries: [], continue: false,
      context: { canContinue: st.canContinue !== false }, outcome: st.outcome || "completed" });
    settles.push(res.length ? (res[0] === undefined ? null : res[0]) : "NO_HANDLER");
  } else throw new Error("harness：不認得的步驟 " + st.do);   // 量具寫錯要死在這裡，不是安靜略過
}
console.log(JSON.stringify({ settles, notes, fired, current: current.provider + "/" + current.id }));
"""

#: 一整輪的標準動作：使用者送 prompt → agent 叫一次模型、用一次工具、寫檔 → 收手。
def _round(write: str | None = None, *, calls: int = 1, outcome: str = "completed",
           journal: bool = True) -> list[dict]:
    steps: list[dict] = [{"do": "prompt"}]
    for _ in range(calls):
        steps.append({"do": "model_call", "journal": journal})
    steps.append({"do": "tool"})
    if write is not None:
        steps.append({"do": "write", "path": "solution.py", "text": write})
    steps += [{"do": "model_call", "journal": journal}, {"do": "agent_end"},
              {"do": "settle", "outcome": outcome}]
    return steps


def _setup(tmp_path: pathlib.Path, suite: str | None = "outside",
           suite_src: str = _VISIBLE_TEST) -> dict:
    ws = tmp_path / "ws"
    ws.mkdir()
    (ws / ".git").mkdir()                    # resolve_suite 走到 git 根就停（不往 tmp 上面爬）
    home = tmp_path / "home"
    home.mkdir()
    env: dict[str, str] = {}
    if suite == "outside":
        d = tmp_path / "suite_visible"
        d.mkdir()
        (d / "test_visible.py").write_text(suite_src, encoding="utf-8")
        env["VACANT_SUITE"] = str(d)
    elif suite == "inside":
        d = ws / ".vacant" / "suite"
        d.mkdir(parents=True)
        (d / "test_visible.py").write_text(suite_src, encoding="utf-8")
    elif suite == "empty":
        d = tmp_path / "suite_empty"
        d.mkdir()
        (d / "README.txt").write_text("no tests here", encoding="utf-8")
        env["VACANT_SUITE"] = str(d)
    hidden = tmp_path / "hidden"
    hidden.mkdir()
    (hidden / "test_hidden.py").write_text(_HIDDEN_TEST, encoding="utf-8")
    return {"ws": ws, "home": home, "state": tmp_path / "state", "env": env,
            "hidden": hidden}


def _run(tmp_path: pathlib.Path, s: dict, steps: list[dict], *,
         env: dict | None = None, has_ui: bool = True,
         pi_agent_dir: pathlib.Path | None = None, upstream: str = "") -> dict:
    node = shutil.which("node")
    if not node:
        pytest.skip("這台沒有 node ⇒ 互動閘門的行為沒量到（不是通過）")
    body = piext.render(port=1, state_dir=str(s["state"]), python=sys.executable,
                        package_path=str(REPO), models=["m1"], upstream=upstream,
                        pi_agent_dir=str(pi_agent_dir) if pi_agent_dir else "")
    ext = tmp_path / "vacant.mjs"
    ext.write_text(body, encoding="utf-8")
    harness = tmp_path / "harness.mjs"
    harness.write_text(_HARNESS, encoding="utf-8")
    # 這台機器自己的設定不可以漏進測試
    drop = ("PI_CODING_AGENT_DIR", "VACANT_AGENT_MODEL", "VACANT_SUITE", "VACANT_ATTEST",
            "VACANT_PI_GATE", "VACANT_PI_GATE_FEEDBACK", "VACANT_PI_GATE_MAX_ROUNDS",
            "VACANT_PI_GATE_KEEP_FROZEN")
    run_env = {k: v for k, v in os.environ.items() if k not in drop}
    run_env.update({"HOME": str(s["home"]), "VACANT_PI_GATE_WIRE_WAIT_S": "0.3",
                    "VACANT_TEST_TIMEOUT": "20"})
    run_env.update(s["env"])
    run_env.update(env or {})
    script = {"ws": str(s["ws"]), "state": str(s["state"]), "hasUI": has_ui,
              "steps": steps}
    r = subprocess.run([node, str(harness), ext.as_uri(), json.dumps(script)],
                       capture_output=True, text=True, timeout=300, env=run_env,
                       cwd=str(s["ws"]))
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout.strip().splitlines()[-1])
    out["stderr"] = r.stderr
    out["run_dirs"] = sorted(p for p in s["home"].glob(".vacant-run/pi_*_s*/p*_r*")
                             if p.is_dir())
    hooks: list[dict] = []
    hd = s["state"] / "hooks"
    for p in sorted(hd.glob("pi_*.jsonl")) if hd.exists() else []:
        hooks += [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines()
                  if x.strip()]
    out["hooks"] = hooks
    return out


def _payload(run_dir: pathlib.Path, etype: str = "ws_verdict") -> dict:
    book = Logbook.load(run_dir / "receipts_RUN-ON.ndjson")
    got = [e.payload for e in book.entries if e.type == etype]
    assert len(got) == 1, (etype, [e.type for e in book.entries])
    return got[0]


@pytest.fixture(scope="module", autouse=True)
def _verifier_selftest_first():
    """尺先過自檢：驗章器抓不到竄改的話，下面每一個 OK 都只是「沒人檢查」。"""
    assert verify_receipts.selftest() == 0


def _gate_notes(out: dict) -> list[dict]:
    return [n for n in out["notes"] if n["text"].startswith("Vacant 閘門")]


# ══ 1) 沒交件 ⇒ 拒交裁決 ═════════════════════════════════════════════════════
def test_no_deliverable_is_refused_with_a_verifiable_receipt(tmp_path):
    """活體標本（2026-09-24 R534 `lcb_3584`／`lcb_3789`）：agent 退出碼 0、沒寫 solution.py、
    常駐 extension 那條路**沒有任何東西擋**。現在收手那一刻要有拒交裁決＋收據。"""
    s = _setup(tmp_path)
    out = _run(tmp_path, s, [{"do": "session_start"}] + _round(write=None))
    assert out["settles"] == [None]                    # 回饋預設關 ⇒ 不要求續跑
    assert len(out["run_dirs"]) == 1
    rd = out["run_dirs"][0]
    v = _payload(rd)
    assert v["accepted"] is False and v["accepted_is_null"] is False
    assert v["stop_reason"] == "visible_fail"
    assert v["settle_verdict"] == "fail"
    assert v["run"] == piext.GATE_RUN_TAG and v["trigger"] == "agent_before_settle"
    assert v["blocks_delivery"] is False               # 標記不是攔截（G2）
    assert v["requests_seen"] == 2                     # 兩通模型呼叫；canary 不算
    assert v["prompt_seq"] == 1 and v["gate_round"] == 1 and v["session_seq"] == 1
    assert v["final_for_prompt"] is True and v["continuation_requested"] is False
    # 級別由探針決定，**不由我們假設**：這台測試機跑出來的圍牆探針說不在圍牆裡 ⇒ B′
    # （canary 有燒）。只有 loopback 的極簡容器會讀成 A——那也是探針說的，不是我們說的。
    from vacant_network.vrun import attest as attestmod
    want = "A" if attestmod.probe_enclosure()["applied"] is True else "B'"
    assert v["tier"] == want and v["attested"] is (want == "A")
    assert v["canary_fired"] is True
    assert v["unexplained"] == 0                       # 每一通都對得上一個回合開端
    # 同一把尺驗：鏈完整、有中介、條數對得上
    g = verify_receipts.run_glob(str(rd))
    assert g["verdict"] == "OK", json.dumps(g["chains"], ensure_ascii=False)[:600]
    assert g["mediated_chains_n"] == 1 and verify_receipts.exit_code(g) == 0
    # 與 shim 同形的 possess.json：沒有退出碼、互動裁決在另一欄
    pj = json.loads((rd / "possess.json").read_text("utf-8"))
    assert pj["shim_exit"] is None and pj["settle_verdict"] == "fail"
    assert pj["gate"] == "ran" and pj["suite_source"] == "env:VACANT_SUITE"
    # 使用者在 TUI 看得到
    gn = [n for n in _gate_notes(out) if "拒交" in n["text"]]
    assert gn and gn[0]["level"] == "warning" and "check_add" in gn[0]["text"]
    assert "標記不是攔截" in gn[0]["text"]
    # 凍結副本預設收掉（樹雜湊已經綁進收據）
    assert not (rd / "_frozen_RUN-ON").exists() and v["ws_end_sha256"]


# ══ 2) 交了而且過 ⇒ 通過 ═════════════════════════════════════════════════════
def test_delivered_and_passing_is_accepted(tmp_path):
    s = _setup(tmp_path)
    out = _run(tmp_path, s, [{"do": "session_start"}] + _round(write=_GOOD))
    rd = out["run_dirs"][0]
    v = _payload(rd)
    assert v["accepted"] is True and v["stop_reason"] == "visible_pass"
    assert v["settle_verdict"] == "pass"
    assert v["ws_start_sha256"] != v["ws_end_sha256"]  # 起點與終點是兩棵不同的樹
    a = _payload(rd, "ws_attempt")
    assert a["ws_sha256"] == v["ws_end_sha256"] and a["verdict_sha256"] == v["verdict_sha256"]
    g = verify_receipts.run_glob(str(rd))
    assert g["verdict"] == "OK" and g["broken_chains_n"] == 0
    assert any(n["level"] == "info" and "✓" in n["text"] for n in _gate_notes(out))


# ══ 3) 沒有驗收 ⇒ accepted=null（不是通過）═══════════════════════════════════
def test_no_suite_is_ungated_null_not_pass(tmp_path):
    s = _setup(tmp_path, suite=None)
    steps = [{"do": "session_start"}] + _round(write=_GOOD) + _round(write=_GOOD)
    out = _run(tmp_path, s, steps)
    assert len(out["run_dirs"]) == 2                   # 每一輪照樣落收據
    for rd in out["run_dirs"]:
        v = _payload(rd)
        assert v["accepted_is_null"] is True and v["accepted"] is False   # bool() 壓扁＋另一欄說「沒量」
        assert v["stop_reason"] == "ungated" and v["settle_verdict"] == "ungated"
        assert v["verdict_sha256"] is None and v["ws_end_sha256"] is None
        g = verify_receipts.run_glob(str(rd))
        assert g["verdict"] == "OK"                    # 有流量的 ungated 不是 VOID（selftest I 那一格）
        assert g["chains"][0]["ungated_task_ids"] == [v["task_id"]]
        rows = [json.loads(x) for x in (rd / "rows.jsonl").read_text("utf-8").splitlines()]
        assert rows[0]["accepted"] is None and rows[0]["refused"] is False
        assert json.loads((rd / "possess.json").read_text("utf-8"))["gate"] == "skipped"
    # 「沒有驗收可跑」講一次（session 開頭一次＋第一輪一次），不是每一輪都講
    said = [n for n in _gate_notes(out) if "沒有驗收可跑" in n["text"]]
    assert len(said) == 2, said
    assert all("不是通過" in n["text"] for n in said)


def test_empty_suite_dir_is_no_suite_refusal_fail_closed(tmp_path):
    """找到驗收目錄但沒有 test_*.py ⇒ `no_suite` 拒交（launcher 的 fail-closed，不是 ungated）。"""
    s = _setup(tmp_path, suite="empty")
    out = _run(tmp_path, s, [{"do": "session_start"}] + _round(write=_GOOD))
    v = _payload(out["run_dirs"][0])
    assert v["stop_reason"] == "no_suite" and v["accepted"] is False
    assert v["accepted_is_null"] is False and v["settle_verdict"] == "fail"


# ══ 4) 回饋：可選、只含可見驗收、有上限 ══════════════════════════════════════
def _scan(texts: list[str]) -> list[str]:
    return [c for c in (GT_CANARY, NUM_CANARY) if any(c in (t or "") for t in texts)]


def _all_text_under(*roots: pathlib.Path) -> list[str]:
    out: list[str] = []
    for root in roots:
        for p in root.rglob("*"):
            if p.is_file():
                try:
                    out.append(p.read_text("utf-8", errors="replace"))
                except OSError:
                    pass
    return out


def test_feedback_loop_contains_only_visible_results_and_fixes(tmp_path):
    """開回饋：第一輪沒過 ⇒ 回 `{entries:[custom_message], continue:true}`；內容只有
    **可見驗收**的失敗原文（隱藏側的 canary 零命中）；agent 修好 ⇒ 第二輪通過；
    兩輪的收據用 `prev_receipt_head` 串起來。"""
    s = _setup(tmp_path)
    steps = ([{"do": "session_start"}] + _round(write=_BAD)
             # 續跑（沒有 before_agent_start）：agent 讀到回饋、改檔、再收手
             + [{"do": "model_call"}, {"do": "tool"},
                {"do": "write", "path": "solution.py", "text": _GOOD},
                {"do": "model_call"}, {"do": "agent_end"}, {"do": "settle"}])
    out = _run(tmp_path, s, steps, env={"VACANT_PI_GATE_FEEDBACK": "revise"})
    first, second = out["settles"]
    assert second is None
    assert first["continue"] is True
    (entry,) = first["entries"]
    assert entry["type"] == "custom_message" and entry["customType"] == "vacant-gate-feedback"
    assert entry["display"] is True                    # 使用者看得到我們替他送了什麼
    fb = entry["content"]
    # ⚠ 量具先證明接上了：回饋真的有內容、真的提到可見的那一條
    assert "check_add" in fb and "machine output, not a person" in fb
    assert "round 1 of 3" in fb
    # 紅線：隱藏測資零命中——回饋、通知、掛鉤日誌、收據目錄、state 全掃
    texts = [fb] + [n["text"] for n in out["notes"]]
    texts += _all_text_under(s["home"] / ".vacant-run", s["state"])
    assert _scan(texts) == []
    r1, r2 = out["run_dirs"]
    v1, v2 = _payload(r1), _payload(r2)
    assert (v1["stop_reason"], v1["continuation_requested"], v1["final_for_prompt"]) == \
        ("visible_fail", True, False)
    assert (v2["stop_reason"], v2["gate_round"], v2["prompt_seq"]) == ("visible_pass", 2, 1)
    assert v1["feedback_sha256"] and v2["feedback_sha256"] is None
    # 輪與輪串起來：第二張收據簽著第一張的鏈頭
    head1 = Logbook.load(r1 / "receipts_RUN-ON.ndjson").entries[-1].hash()
    assert v2["prev_receipt_head"] == head1 and v1["prev_receipt_head"] is None
    # 續跑那一通有自己的回合開端（extension 寫的 user_prompt_submit）⇒ 對帳 0 通對不上
    assert v1["unexplained"] == 0 and v2["unexplained"] == 0
    srcs = [f["payload"].get("source") for f in out["fired"]
            if f["event"] == "user_prompt_submit"]
    assert srcs == ["pi-extension", "vacant-gate"]
    for rd in (r1, r2):
        assert verify_receipts.run_glob(str(rd))["verdict"] == "OK"


def test_feedback_canary_scan_has_teeth(tmp_path):
    """負向控制：把**隱藏**那一份當成驗收餵進去，同一支掃描必須翻紅——不然上面的
    「零命中」跟把掃描關掉在輸出上同形。"""
    s = _setup(tmp_path)
    out = _run(tmp_path, s, [{"do": "session_start"}] + _round(write=_BAD),
               env={"VACANT_PI_GATE_FEEDBACK": "revise", "VACANT_SUITE": str(s["hidden"])})
    fb = out["settles"][0]["entries"][0]["content"]
    assert _scan([fb]) == [GT_CANARY, NUM_CANARY], fb


def test_feedback_rounds_are_capped(tmp_path):
    """文件：無條件 `continue:true` 會無限迴圈 ⇒ 上限到了就停，最後一輪 `attempts_exhausted`。"""
    s = _setup(tmp_path)
    again = [{"do": "model_call"}, {"do": "agent_end"}, {"do": "settle"}]
    out = _run(tmp_path, s, [{"do": "session_start"}] + _round(write=_BAD) + again,
               env={"VACANT_PI_GATE_FEEDBACK": "revise", "VACANT_PI_GATE_MAX_ROUNDS": "2"})
    assert out["settles"][0]["continue"] is True and out["settles"][1] is None
    v2 = _payload(out["run_dirs"][1])
    assert v2["stop_reason"] == "attempts_exhausted" and v2["max_attempts"] == 2
    assert v2["continuation_requested"] is False and v2["final_for_prompt"] is True


@pytest.mark.parametrize("outcome,can_continue", [("error", True), ("completed", False)])
def test_no_continuation_on_hard_exit_or_when_pi_says_cannot(tmp_path, outcome, can_continue):
    """文件：error／aborted 是 hard exit；`canContinue=false` 時要求續跑會被 pi 回報為錯。"""
    s = _setup(tmp_path)
    steps = [{"do": "session_start"}] + _round(write=_BAD)
    steps[-1] = {"do": "settle", "outcome": outcome, "canContinue": can_continue}
    out = _run(tmp_path, s, steps, env={"VACANT_PI_GATE_FEEDBACK": "revise"})
    assert out["settles"] == [None]
    v = _payload(out["run_dirs"][0])
    assert v["continuation_requested"] is False and v["settle_outcome"] == outcome
    assert v["settle_verdict"] == "fail"               # 照判，只是不續跑


def test_feedback_is_off_by_default(tmp_path):
    s = _setup(tmp_path)
    out = _run(tmp_path, s, [{"do": "session_start"}] + _round(write=_BAD))
    assert out["settles"] == [None]
    run = json.loads((out["run_dirs"][0] / "run_RUN-ON.json").read_text("utf-8"))
    assert run["continuation"]["why_not"][0] == "feedback_off"
    assert "回饋：關" in [n for n in _gate_notes(out)][0]["text"]


# ══ 5) 驗收是 session 開頭的快照：agent 改來源不影響裁決、改快照 ⇒ infra_void ═══
def test_agent_editing_the_suite_mid_session_does_not_change_the_verdict(tmp_path):
    s = _setup(tmp_path, suite="inside")
    cheat = "def check_add():\n    pass\n"            # agent 把驗收改成永遠過
    steps = [{"do": "session_start"}, {"do": "prompt"}, {"do": "model_call"},
             {"do": "write", "path": ".vacant/suite/test_visible.py", "text": cheat},
             {"do": "model_call"}, {"do": "agent_end"}, {"do": "settle"}]
    out = _run(tmp_path, s, steps)
    v = _payload(out["run_dirs"][0])
    assert v["settle_verdict"] == "fail" and v["stop_reason"] == "visible_fail"
    assert v["suite_drift"] is True and v["suite_source"] == "dir:.vacant/suite"
    assert any("suite_drift=true" in n["text"] for n in _gate_notes(out))


def test_tampered_snapshot_is_infra_void_without_a_receipt(tmp_path):
    """快照在 `~/.vacant-run` 裡、agent 寫得到（G3）——寫了就要看得見：雜湊對不上 session
    開頭釘在 pi 記憶體裡的那一個 ⇒ infra_void，**不簽收據**（不判拒交也不判通過）。"""
    s = _setup(tmp_path)
    steps = [{"do": "session_start"}, {"do": "prompt"}, {"do": "model_call"},
             {"do": "tamper_snapshot", "file": "test_visible.py", "text": "\ncheck_add = None\n"},
             {"do": "agent_end"}, {"do": "settle"}]
    out = _run(tmp_path, s, steps)
    rd = out["run_dirs"][0]
    assert not (rd / "receipts_RUN-ON.ndjson").exists()
    run = json.loads((rd / "run_RUN-ON.json").read_text("utf-8"))
    assert run["stop_reason"] == "suite_snapshot_changed" and run["settle_verdict"] == "infra_void"
    assert run["accepted"] is None and run["refused"] is None
    assert json.loads((rd / "possess.json").read_text("utf-8"))["settle_verdict"] == "infra_void"
    assert any(n["level"] == "error" and "infra_void" in n["text"] for n in _gate_notes(out))


# ══ 6) wire 0 通 ⇒ no_mediation（shim 的 23），收據照簽、驗章器判 VOID ════════════
def test_zero_requests_is_no_mediation_and_verifier_says_void(tmp_path):
    """模型呼叫沒經過常駐 proxyd（例如 Ctrl+P 切到自己的 provider）：掛鉤說叫了兩通、
    journal 一通都沒有 ⇒ 裁決不可歸因。驗收照跑、收據照簽（`requests_seen=0` 簽進去）。"""
    s = _setup(tmp_path)
    out = _run(tmp_path, s, [{"do": "session_start"}] + _round(write=_BAD, journal=False),
               env={"VACANT_PI_GATE_FEEDBACK": "revise"})
    assert out["settles"] == [None]                    # 不可歸因的裁決不拿來驅動 agent
    rd = out["run_dirs"][0]
    v = _payload(rd)
    assert v["requests_seen"] == 0 and v["settle_verdict"] == "no_mediation"
    assert v["stop_reason"] == "visible_fail"          # 驗收本身沒過——但不可歸因，也不續跑
    assert v["continuation_requested"] is False
    run = json.loads((rd / "run_RUN-ON.json").read_text("utf-8"))
    assert "requests_seen=0" in run["continuation"]["why_not"]
    assert v["wire_count_semantics"] == "lower_bound" and v["wire_quiesced"] is False
    g = verify_receipts.run_glob(str(rd))
    assert g["verdict"] == "VOID" and verify_receipts.exit_code(g) == verify_receipts.EXIT_VOID


def test_canary_and_probe_calls_are_not_model_calls(tmp_path):
    """refresh／status／hookcli 的 canary 都帶 `vacant_canary` ⇒ 一通都不算進 requests_seen。"""
    s = _setup(tmp_path)
    steps = ([{"do": "session_start"}, {"do": "prompt"}, {"do": "probe_call"},
              {"do": "probe_call"}, {"do": "agent_end"}, {"do": "settle"}])
    out = _run(tmp_path, s, steps)
    v = _payload(out["run_dirs"][0])
    assert v["requests_seen"] == 0 and v["settle_verdict"] == "no_mediation"


def test_reconcile_window_is_per_round_not_whole_session(tmp_path):
    """一個 session 的第二輪多了一通沒有回合開端的呼叫 ⇒ `unexplained=1`。

    負向控制的理由：若對帳不切窗（`attest.attest(hook_since_ts=None)`），第一輪留下來的
    回合開端會把第二輪多出來的那一通「解釋掉」（貪婪配對只看時間在前）⇒ 讀成 0。
    這一格正是 `attest` 那個新參數存在的理由。"""
    s = _setup(tmp_path)
    steps = ([{"do": "session_start"}] + _round(write=_GOOD)
             + [{"do": "prompt"}, {"do": "model_call"}, {"do": "model_call"},
                {"do": "agent_end"}, {"do": "settle"}])
    out = _run(tmp_path, s, steps)
    v1, v2 = _payload(out["run_dirs"][0]), _payload(out["run_dirs"][1])
    assert (v1["prompt_seq"], v2["prompt_seq"]) == (1, 2)
    assert v1["unexplained"] == 0 and v2["unexplained"] == 1
    assert v2["requests_seen"] == 2                    # 只數這一輪的窗
    # 反事實：同一份掛鉤日誌與 journal，不切窗 ⇒ 被上一輪的開端吸收掉
    from vacant_network.vrun import attest as attestmod
    run2 = json.loads((out["run_dirs"][1] / "run_RUN-ON.json").read_text("utf-8"))
    rec = run2["attestation"]["reconciled"]
    hook_log = run2["attestation"]["framework_hook"]["log"]
    whole = attestmod.attest(agent="pi", run_id=run2["session"]["run_id"],
                             hook_log=hook_log, install_attempted=True,
                             relay_index=run2["model_wire"]["journal"],
                             relay_since=run2["model_wire"]["journal_offset_begin"])
    assert whole["reconciled"]["unexplained"] == 0 and "hook_since_ts" not in whole["reconciled"]
    assert rec["hook_since_ts"] is not None


def test_attest_since_ts_is_opt_in_and_filters_by_time(tmp_path):
    from vacant_network.vrun import attest as attestmod
    log = tmp_path / "h.jsonl"
    log.write_text("\n".join(json.dumps(r) for r in (
        {"event": "user_prompt_submit", "ts": 10.0, "run_id": "r"},
        {"event": "tool_result", "ts": 20.0, "run_id": "r"},
        {"event": "tool_result", "run_id": "r"},            # 沒有 ts
    )) + "\n", encoding="utf-8")
    assert len(attestmod.read_hook_events(log, run_id="r")) == 3      # 預設：行為不變
    got = attestmod.read_hook_events(log, run_id="r", since_ts=15.0)
    assert [e["ts"] for e in got] == [20.0]                          # 沒有 ts 的放不進窗 ⇒ 丟掉


# ══ 7) 既有不變式：/vacant off 恰好一筆、off 那一段沒有閘門、Esc 不判、關得掉 ════════
def test_vacant_off_skips_the_gate_and_keeps_exactly_one_trace(tmp_path):
    s = _setup(tmp_path)
    steps = ([{"do": "session_start"}, {"do": "command", "args": "off"}]
             + _round(write=_GOOD))
    out = _run(tmp_path, s, steps)
    assert out["run_dirs"] == []                       # off 的那一段沒有閘門（G1）
    names = [h["event"] for h in out["hooks"]]
    assert names.count("vacant_off") == 1 and names.count("vacant_on") == 1
    skips = [f["payload"] for f in out["fired"] if f["event"] == "gate_skipped"]
    assert skips == [{"reason": "vacant_off"}]


def test_aborted_round_has_no_verdict(tmp_path):
    s = _setup(tmp_path)
    out = _run(tmp_path, s, [{"do": "session_start"}] + _round(write=_GOOD, outcome="aborted"))
    assert out["run_dirs"] == [] and out["settles"] == [None]
    assert any("被中斷" in n["text"] and "沒有裁決" in n["text"] for n in _gate_notes(out))


def test_gate_can_be_turned_off(tmp_path):
    s = _setup(tmp_path)
    out = _run(tmp_path, s, [{"do": "session_start"}] + _round(write=_GOOD),
               env={"VACANT_PI_GATE": "off"})
    assert out["run_dirs"] == [] and out["settles"] == [None]
    assert not any(f["event"].startswith("gate_") for f in out["fired"])
    assert not (s["home"] / ".vacant-run").exists()


def test_print_mode_writes_the_verdict_to_stderr(tmp_path):
    """用完整路徑打 `pi -p`（不經 shim）也會載入常駐 extension ⇒ 沒有 UI ⇒ 裁決寫 stderr。"""
    s = _setup(tmp_path)
    out = _run(tmp_path, s, [{"do": "session_start"}] + _round(write=None), has_ui=False)
    assert out["notes"] == []
    assert "[vacant] Vacant 閘門：✗ 拒交裁決" in out["stderr"]


# ══ 8) 掛鉤只落雜湊、金鑰借不存、run 目錄在工作區裡就停用 ═══════════════════════════
def test_hook_log_has_hashes_only_and_no_key_is_written(tmp_path):
    s = _setup(tmp_path)
    agent = tmp_path / "agent"
    agent.mkdir()
    secret = "sk-SECRET-do-not-write-0d9f"
    (agent / "models.json").write_text(json.dumps({"providers": {"mine": {
        "baseUrl": "https://up.example/v1", "apiKey": secret,
        "models": [{"id": "m1"}]}}}), encoding="utf-8")
    out = _run(tmp_path, s, [{"do": "session_start"}] + _round(write=_BAD),
               env={"VACANT_PI_GATE_FEEDBACK": "revise"}, pi_agent_dir=agent,
               upstream="https://up.example/v1")
    fb = out["settles"][0]["entries"][0]["content"]
    hook_text = "\n".join(json.dumps(h, ensure_ascii=False) for h in out["hooks"])
    assert "check_add" not in hook_text and fb[:40] not in hook_text
    assert {"gate_snapshot", "gate_verdict"} <= {h["event"] for h in out["hooks"]}
    assert all(secret not in t for t in _all_text_under(s["home"], s["state"]))


def test_workspace_that_contains_the_receipt_dir_disables_the_gate(tmp_path):
    """在 $HOME 開 pi：收據目錄落在工作區裡 ⇒ 凍結會把收據自己複製進去 ⇒ 整個 session 停用並講出來。"""
    s = _setup(tmp_path)
    s["ws"] = s["home"]
    (s["home"] / ".git").mkdir()
    out = _run(tmp_path, s, [{"do": "session_start"}] + _round(write=_GOOD))
    assert out["run_dirs"] == []
    errs = [n for n in _gate_notes(out) if n["level"] == "error"]
    assert errs and "停用" in errs[0]["text"]


def test_status_shows_the_gate_and_the_last_verdict(tmp_path):
    s = _setup(tmp_path)
    out = _run(tmp_path, s, [{"do": "session_start"}] + _round(write=_GOOD)
               + [{"do": "command", "args": "status"}])
    st = [n["text"] for n in out["notes"] if n["text"].startswith("Vacant status")][-1]
    assert "閘門      驗收來源 env:VACANT_SUITE" in st
    assert "最後裁決  pass（visible_pass）" in st and "不擋檔案" in st


# ══ 9) python 端的純函式 ═════════════════════════════════════════════════════
def test_settle_feedback_template_is_ks1_clean_and_r534_verbatim():
    t = piext.render_settle_feedback("x::y — assert: ", gate_round=1, max_rounds=3)
    assert "responsible" not in t.lower()
    # 正文逐字沿用 R534 piarms.FEEDBACK_TEMPLATE（那一段在真 pi 上跑過）
    src = (REPO / "ops" / "gain" / "r534" / "piarms.py").read_text("utf-8")
    assert piext.SETTLE_FEEDBACK_BODY in src


def test_ks1_dirty_test_message_voids_the_round(tmp_path):
    """責任修辭從客戶測試的訊息帶進來 ⇒ 鐵律 1：那一輪作廢（infra_void、不續跑、不簽收據）。"""
    s = _setup(tmp_path, suite_src='''
def check_add():
    from solution import add
    assert add(2, 3) == 5, "you will be punished for this"
''')
    out = _run(tmp_path, s, [{"do": "session_start"}] + _round(write=_BAD),
               env={"VACANT_PI_GATE_FEEDBACK": "revise"})
    assert out["settles"] == [None]
    rd = out["run_dirs"][0]
    run = json.loads((rd / "run_RUN-ON.json").read_text("utf-8"))
    assert run["stop_reason"] == "ks1_violation" and run["settle_verdict"] == "infra_void"
    assert not (rd / "receipts_RUN-ON.ndjson").exists()


def test_gate_main_always_prints_one_json_line_even_when_broken(tmp_path, capsys, monkeypatch):
    import io
    monkeypatch.setattr(sys, "stdin", io.StringIO("not json"))
    assert piext.main(["gate", "nope"]) == 0
    line = capsys.readouterr().out.strip().splitlines()[-1]
    got = json.loads(line)
    assert got["ok"] is False and "nope" in got["error"]


def test_rendered_extension_is_valid_javascript(tmp_path):
    node = shutil.which("node")
    if not node:
        pytest.skip("這台沒有 node ⇒ extension 語法沒量到（不是通過）")
    f = tmp_path / "vacant.mjs"
    f.write_text(piext.render(port=18790, state_dir="/x", python="/py", package_path="/pkg"),
                 "utf-8")
    r = subprocess.run([node, "--check", str(f)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    body = f.read_text("utf-8")
    assert 'pi.on("agent_before_settle"' in body and '"vacant_network.vrun.piext"' in body
