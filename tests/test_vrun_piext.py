"""piext 渲染出來的 extension **行為**測試（不只是語法）。

`test_vrun_possess.py` 用 `node --check` 驗語法；這裡把渲染結果當 ES module 載進 node，
塞一個假的 `pi` 物件＋假的 `fetch`，真的去跑 `refreshModels` 與 `/vacant off`。
掛鉤走**真的** `hookcli`（python＝本測試的直譯器、PYTHONPATH＝repo 根），
所以「日誌裡有幾筆 vacant_off」數的是實際落盤的 JSONL，不是 stub 的計數器。
hookcli 只落雜湊（邊界 6），看不到 payload 的 `source`——所以 harness 另外把
`node:child_process.spawnSync` 包一層（`syncBuiltinESMExports`），記下每一次 fire 的
事件名與 payload，**再照常呼叫真的 spawnSync**。兩邊的筆數要對得上。

假 pi 照 2026-09-24 在 vacant-dev 對真 pi 0.87.0 量到的行為做：extension 的
`await pi.setModel(m)` 會在 await 之內觸發 `model_select`；事件是
`{model, previousModel, source}`，Ctrl+P 的 source 是 "cycle"。

沒有 node ⇒ **skip 並印理由**（量不到不是通過）。
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from vacant_network.vrun import piext

REPO = Path(__file__).resolve().parents[1]

_HARNESS = r"""
import cp from "node:child_process";
import { syncBuiltinESMExports } from "node:module";
const [, , extPath, scenario, optsJson] = process.argv;
const opts = JSON.parse(optsJson || "{}");

// fire() 的每一次呼叫：記事件名＋payload，然後照常跑真的 hookcli
const fired = [];
const realSpawnSync = cp.spawnSync;
cp.spawnSync = function (cmd, args, o) {
  try { fired.push({ event: args[args.length - 1], payload: JSON.parse((o && o.input) || "{}") }); }
  catch (e) { fired.push({ event: args[args.length - 1], payload: null }); }
  return realSpawnSync.apply(this, arguments);
};
syncBuiltinESMExports();

let fetchCalls = 0;
const withCount = (f) => async (...a) => { fetchCalls += 1; return f(...a); };
globalThis.fetch = withCount(async () => { throw new Error("no network in test"); });

const providers = {}, commands = {}, handlers = {}, notes = [];
let current = opts.current || { provider: "openai", id: "gpt-x" };
const registry = {
  models: [Object.assign({}, current)],
  find(p, id) { return this.models.find((m) => m.provider === p && m.id === id) || null; },
  getAll() { return this.models; },
};
if (!registry.find("openai", "gpt-x")) registry.models.push({ provider: "openai", id: "gpt-x" });
async function emitSelect(m, source, withPrev) {
  const prev = current;
  current = m;
  const ev = { model: m, source };
  if (withPrev !== false) ev.previousModel = prev;
  for (const fn of handlers["model_select"] || []) await fn(ev);
}
const pi = {
  registerProvider(id, cfg) {
    providers[id] = cfg;
    for (const m of cfg.models) registry.models.push({ provider: id, id: m.id });
  },
  registerCommand(name, cfg) { commands[name] = cfg; },
  on(ev, fn) { (handlers[ev] = handlers[ev] || []).push(fn); },
  // 真 pi：extension 的 await pi.setModel 會在 await 之內同步觸發 model_select（source "set"）
  async setModel(m) { await emitSelect(m, "set", true); return true; },
};
const ctx = () => ({ hasUI: true, ui: { notify: (text, level) => notes.push({ text, level }) },
                     modelRegistry: registry, model: current });
// 使用者在 TUI 裡 Ctrl+P／`/model`：pi 自己換模型，不經過 extension 的 setModel
const userSelect = (provider, id, source, withPrev) =>
  emitSelect(registry.find(provider, id) || { provider, id }, source, withPrev);
const cur = () => current.provider + "/" + current.id;

const mod = await import(extPath);
mod.default(pi);

const out = {};
async function refresh() {
  const r = await providers.vacant.refreshModels({ signal: undefined });
  out.defs = r;
  out.models = r.map((m) => m.id);
}
if (scenario === "registered") {
  out.defs = providers.vacant.models;
  out.models = out.defs.map((m) => m.id);
  out.apiKey = providers.vacant.apiKey;
  out.provider_compat = providers.vacant.compat === undefined ? null : providers.vacant.compat;
  out.model_compats = Object.fromEntries(providers.vacant.models.map((m) => [m.id, m.compat]));
  out.provider_keys = Object.keys(providers.vacant).sort();
} else if (scenario === "refresh_502_text") {
  globalThis.fetch = withCount(async () => new Response("<html>502 Bad Gateway</html>",
    { status: 502, headers: { "content-type": "text/html" } }));
  await refresh();
} else if (scenario === "refresh_json_error") {
  globalThis.fetch = withCount(async () => new Response(JSON.stringify({ error: { message: "upstream down" } }),
    { status: 502, headers: { "content-type": "application/json" } }));
  await refresh();
} else if (scenario === "refresh_401") {
  // 要金鑰的上游對不帶 Authorization 的 /v1/models（實測）
  globalThis.fetch = withCount(async () => new Response(JSON.stringify({ error: "unauthorized" }), { status: 401 }));
  await refresh();
} else if (scenario === "refresh_200_empty") {
  globalThis.fetch = withCount(async () => new Response(JSON.stringify({ data: [] }), { status: 200 }));
  await refresh();
} else if (scenario === "refresh_throws") {
  await refresh();
} else if (scenario === "refresh_ok") {
  globalThis.fetch = withCount(async () => new Response(JSON.stringify({ data: [{ id: "up-a" }, { id: "up-b" }] }), { status: 200 }));
  await refresh();
} else if (scenario === "refresh_ok_overlap") {
  globalThis.fetch = withCount(async () => new Response(JSON.stringify({ data: [{ id: "gpt-y" }, { id: "up-a" }, { id: "up-a" }] }), { status: 200 }));
  await refresh();
} else if (scenario === "on_only") {
  await commands.vacant.handler("on", ctx());
  out.after_on = cur();
} else if (scenario === "off_via_command" || scenario === "off_via_model") {
  await commands.vacant.handler("on", ctx());
  out.after_on = cur();
  if (scenario === "off_via_command") {
    await commands.vacant.handler("off", ctx());
  } else {
    await pi.setModel({ provider: "openai", id: "gpt-x" });   // 使用者自己 /model 切走
  }
  out.after_off = cur();
} else if (scenario === "cycle_away_and_back") {
  await commands.vacant.handler("on", ctx());
  out.after_on = cur();
  await userSelect("openai", "gpt-x", "cycle");                // Ctrl+P 切走
  out.after_away = cur();
  await userSelect("vacant", opts.back || "baked-a", "cycle");  // Ctrl+P 切回來
  out.after_back = cur();
  await commands.vacant.handler("off", ctx());                  // 再 /vacant off：回到切回來之前的那個
  out.after_off = cur();
} else if (scenario === "non_transitions") {
  for (const fn of handlers["session_start"] || []) await fn({ reason: "startup" }, ctx());
  out.after_start = cur();
  await userSelect("vacant", "baked-b", "cycle");   // vacant→vacant：不是轉換
  await userSelect("openai", "gpt-x", "set");       // vacant→別家：一筆 vacant_off
  await userSelect("other", "zzz", "set");          // 別家→別家：不是轉換
  out.after = cur();
} else if (scenario === "no_previous_model") {
  // previousModel 沒帶時退回 extension 自己記的狀態；一開始是「不知道」⇒ 當成轉換
  await userSelect("vacant", "baked-a", "restore", false);
  await userSelect("vacant", "baked-b", "cycle", false);
  await userSelect("openai", "gpt-x", "cycle", false);
  await userSelect("other", "zzz", "cycle", false);
  out.after = cur();
} else if (scenario === "command") {
  for (const a of opts.args) await commands.vacant.handler(a, ctx());
  out.after = cur();
}
out.fired = fired;
out.notes = notes;
out.fetch_calls = fetchCalls;
console.log(JSON.stringify(out));
"""


def _run(tmp_path: Path, scenario: str, models: list[str], *,
         default_model: str | None = "dflt-model", upstream: str = "",
         pi_agent_dir: Path | None = None, opts: dict | None = None,
         env: dict | None = None) -> tuple[dict, list[dict]]:
    node = shutil.which("node")
    if not node:
        pytest.skip("這台沒有 node ⇒ extension 行為沒量到（不是通過）")
    state = tmp_path / "state"
    body = piext.render(port=1, state_dir=str(state), python=sys.executable,
                        package_path=str(REPO), models=models,
                        default_model=default_model, upstream=upstream,
                        pi_agent_dir=str(pi_agent_dir) if pi_agent_dir else "")
    ext = tmp_path / "vacant.mjs"          # 內容是純 JS；.mjs 讓 node 以 ESM 載入
    ext.write_text(body, encoding="utf-8")
    harness = tmp_path / "harness.mjs"
    harness.write_text(_HARNESS, encoding="utf-8")
    # 這台機器自己的 pi 設定／模型偏好不可以漏進測試
    run_env = {k: v for k, v in os.environ.items()
               if k not in ("PI_CODING_AGENT_DIR", "VACANT_AGENT_MODEL")}
    run_env.update(env or {})
    r = subprocess.run([node, str(harness), ext.as_uri(), scenario, json.dumps(opts or {})],
                       capture_output=True, text=True, timeout=120, env=run_env)
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout.strip().splitlines()[-1])
    events: list[dict] = []
    for p in sorted((state / "hooks").glob("pi_*.jsonl")) if (state / "hooks").exists() else []:
        events += [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]
    return out, events


@pytest.mark.parametrize("scenario", ["refresh_502_text", "refresh_json_error",
                                      "refresh_200_empty", "refresh_throws"])
def test_refresh_models_falls_back_to_baked_list(tmp_path, scenario):
    """上游壞掉時 refreshModels 不可以回空清單（會讓 pickVacantModel 找不到 ⇒ 安靜不切過去）。"""
    out, _ = _run(tmp_path, scenario, models=["baked-a", "baked-b"])
    assert out["models"] == ["baked-a", "baked-b"]


def test_refresh_models_falls_back_to_default_when_nothing_baked(tmp_path):
    out, _ = _run(tmp_path, "refresh_502_text", models=[])
    assert out["models"] == ["dflt-model"]


def test_refresh_models_uses_upstream_when_ok(tmp_path):
    """正控制：上游正常時用上游清單——不然上面那組可能只是永遠回烤進去的。"""
    out, _ = _run(tmp_path, "refresh_ok", models=["baked-a"])
    assert out["models"] == ["up-a", "up-b"]


def test_vacant_off_command_logs_exactly_one_vacant_off(tmp_path):
    out, events = _run(tmp_path, "off_via_command", models=["baked-a"])
    assert out["after_on"] == "vacant/baked-a"
    assert out["after_off"] == "openai/gpt-x"
    offs = [e for e in events if e.get("event") == "vacant_off"]
    assert len(offs) == 1, events
    assert any(e.get("event") == "vacant_on" for e in events)   # 正控制：掛鉤真的有在寫


def test_model_select_away_logs_exactly_one_vacant_off(tmp_path):
    """/model 切走（不經 /vacant off）仍要留恰好一筆——去重不可以把這條也吃掉。"""
    out, events = _run(tmp_path, "off_via_model", models=["baked-a"])
    assert out["after_off"] == "openai/gpt-x"
    offs = [e for e in events if e.get("event") == "vacant_off"]
    assert len(offs) == 1, events


# ── Finding 2：要金鑰的上游 ⇒ 模型清單要借使用者自己的，不可以只剩 DEFAULT_MODEL ──────

UP = "https://up.example/v1"


def _agent_dir(tmp_path: Path, providers: dict) -> Path:
    d = tmp_path / "agent"
    d.mkdir(exist_ok=True)
    (d / "models.json").write_text(json.dumps({"providers": providers}), encoding="utf-8")
    return d


def _keyed_providers() -> dict:
    return {
        "elsewhere": {"baseUrl": "https://elsewhere.example/v1", "apiKey": "sk-WRONG",
                      "models": [{"id": "wrong-model"}]},
        "openai": {"baseUrl": UP + "/", "apiKey": "$OPENAI_API_KEY",
                   "headers": {"X-Secret": "h"}, "authHeader": True,
                   "models": [{"id": "gpt-x", "name": "GPT X", "contextWindow": 262144,
                               "maxTokens": 32768, "reasoning": True,
                               "input": ["text", "image"],
                               "cost": {"input": 5, "output": 15, "cacheRead": 1,
                                        "cacheWrite": 1}},
                              {"id": "gpt-y"}]},
    }


def _defs(out: dict) -> dict:
    return {m["id"]: m for m in out["defs"]}


def test_vacant_models_come_from_borrowed_provider_not_default(tmp_path):
    """活體標本（2026-09-24）：上游要金鑰 ⇒ 裝機探測 401 ⇒ BAKED_MODELS=[]。舊版就只註冊
    `gemma-4-12b-it-qat`，用 OpenAI 的人每一通 404。現在要借同一個 provider 的 `models`。"""
    agent = _agent_dir(tmp_path, _keyed_providers())
    out, _ = _run(tmp_path, "registered", models=[], default_model=None,
                  upstream=UP, pi_agent_dir=agent)
    assert out["models"] == ["gpt-x", "gpt-y"]
    assert piext.DEFAULT_MODEL not in out["models"] and "wrong-model" not in out["models"]
    d = _defs(out)
    # 抄 name／contextWindow／maxTokens／reasoning／input；缺的用預設
    assert d["gpt-x"]["name"] == "GPT X"
    assert d["gpt-x"]["contextWindow"] == 262144 and d["gpt-x"]["maxTokens"] == 32768
    assert d["gpt-x"]["reasoning"] is True and d["gpt-x"]["input"] == ["text", "image"]
    assert d["gpt-y"]["contextWindow"] == 131072 and d["gpt-y"]["input"] == ["text"]
    # cost 不抄；headers／authHeader 不抄（誠實邊界 7、9）
    assert d["gpt-x"]["cost"] == {"input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0}
    assert "headers" not in out["provider_keys"] and "authHeader" not in out["provider_keys"]
    assert out["apiKey"] == "$OPENAI_API_KEY"      # 金鑰仍只借設定字串


@pytest.mark.parametrize("providers,baked,want", [
    # 同 baseUrl 的 provider 沒有 models ⇒ 裝機時烤進來的
    ({"openai": {"baseUrl": UP, "apiKey": "k"}}, ["baked-a"], ["baked-a"]),
    # 沒有 models、也沒烤到 ⇒ DEFAULT_MODEL（猜的；session_start 會講）
    ({"openai": {"baseUrl": UP, "apiKey": "k"}}, [], ["dflt-model"]),
    # baseUrl 對不上 ⇒ 別家的清單不借
    ({"other": {"baseUrl": "https://elsewhere.example/v1", "apiKey": "k",
                "models": [{"id": "nope"}]}}, [], ["dflt-model"]),
    # 借金鑰的那一個沒有 models，但同一台主機的另一個 provider 有 ⇒ 借那一份（裸字串 id 也收、重複只留一個）
    ({"openai": {"baseUrl": UP, "apiKey": "k"},
      "mirror": {"baseUrl": UP, "models": ["m-1", {"id": "m-2"}, "m-1"]}}, ["baked-a"],
     ["m-1", "m-2"]),
    # 借來的清單優先於烤進來的
    ({"openai": {"baseUrl": UP, "apiKey": "k", "models": [{"id": "gpt-x"}]}}, ["baked-a"],
     ["gpt-x"]),
])
def test_model_list_fallback_chain(tmp_path, providers, baked, want):
    agent = _agent_dir(tmp_path, providers)
    out, _ = _run(tmp_path, "registered", models=baked, upstream=UP, pi_agent_dir=agent)
    assert out["models"] == want


def test_refresh_401_falls_back_to_borrowed_list(tmp_path):
    """refreshModels 不帶 Authorization ⇒ 要金鑰的上游 401 ⇒ 回的要是**借來的**那份，
    不是 DEFAULT_MODEL（否則 refresh 一跑就把對的清單蓋回錯的）。"""
    agent = _agent_dir(tmp_path, _keyed_providers())
    out, _ = _run(tmp_path, "refresh_401", models=[], default_model=None,
                  upstream=UP, pi_agent_dir=agent)
    assert out["fetch_calls"] == 1                 # 正控制：真的去抓了、而且失敗
    assert out["models"] == ["gpt-x", "gpt-y"]
    assert _defs(out)["gpt-x"]["contextWindow"] == 262144


def test_refresh_ok_merges_upstream_after_borrowed_keeping_user_metadata(tmp_path):
    """不要金鑰的上游 2xx：借來的在前、欄位原樣（contextWindow 不被重設）、上游多列的補在後、
    重複 id 只留一個；上游沒列的借來 id **不刪**。"""
    agent = _agent_dir(tmp_path, _keyed_providers())
    out, _ = _run(tmp_path, "refresh_ok_overlap", models=[], upstream=UP, pi_agent_dir=agent)
    assert out["models"] == ["gpt-x", "gpt-y", "up-a"]
    assert _defs(out)["gpt-x"]["contextWindow"] == 262144


def test_refresh_401_without_borrow_still_uses_baked(tmp_path):
    out, _ = _run(tmp_path, "refresh_401", models=["baked-a"])
    assert out["models"] == ["baked-a"]


@pytest.mark.parametrize("current,env,default,want", [
    # 使用者現在用 gpt-y ⇒ /vacant on ＝ 同一個模型經過 Vacant（勝過 VACANT_AGENT_MODEL）
    ({"provider": "openai", "id": "gpt-y"}, {"VACANT_AGENT_MODEL": "gpt-x"}, None, "vacant/gpt-y"),
    # 現在用的 id vacant 沒有 ⇒ VACANT_AGENT_MODEL
    ({"provider": "other", "id": "zzz"}, {"VACANT_AGENT_MODEL": "gpt-y"}, None, "vacant/gpt-y"),
    # 再來是 DEFAULT_MODEL
    ({"provider": "other", "id": "zzz"}, {}, "gpt-y", "vacant/gpt-y"),
    # 都沒有 ⇒ 第一個
    ({"provider": "other", "id": "zzz"}, {}, None, "vacant/gpt-x"),
])
def test_pick_vacant_model_prefers_current_model_id(tmp_path, current, env, default, want):
    agent = _agent_dir(tmp_path, _keyed_providers())
    out, events = _run(tmp_path, "on_only", models=[], default_model=default, upstream=UP,
                       pi_agent_dir=agent, opts={"current": current}, env=env)
    assert out["after_on"] == want
    assert [e["event"] for e in events].count("vacant_on") == 1


# ── Finding 3：Ctrl+P／/model 切回 vacant 也要留一筆 vacant_on ─────────────────────

def _transitions(out: dict) -> list[tuple[str, str | None]]:
    return [(f["event"], f["payload"].get("source")) for f in out["fired"]
            if f["event"] in ("vacant_on", "vacant_off")]


def _jsonl_counts(events: list[dict]) -> tuple[int, int]:
    names = [e.get("event") for e in events]
    return names.count("vacant_on"), names.count("vacant_off")


def test_cycle_back_to_vacant_logs_exactly_one_vacant_on(tmp_path):
    """活體標本（2026-09-24）：Ctrl+P 切走 ⇒ vacant_off(cycle)；Ctrl+P 切回 ⇒ **什麼都沒有**，
    日誌一路說 off。現在切回要有一筆 vacant_on(cycle)；switchOn 自己的 setModel 不重複。"""
    out, events = _run(tmp_path, "cycle_away_and_back", models=["baked-a", "baked-b"])
    assert out["after_on"] == "vacant/baked-a"
    assert out["after_away"] == "openai/gpt-x"
    assert out["after_back"] == "vacant/baked-a"
    assert out["after_off"] == "openai/gpt-x"      # /vacant off 回到切回來之前那個
    assert _transitions(out) == [("vacant_on", "command"), ("vacant_off", "cycle"),
                                 ("vacant_on", "cycle"), ("vacant_off", None)]
    # 真的落盤的 JSONL 筆數與 fire 次數對得上（不是只數 stub）
    assert _jsonl_counts(events) == (2, 2), events


def test_switch_on_own_set_model_does_not_double_log(tmp_path):
    """反事實：拿掉 onInProgress，switchOn 的 pi.setModel 觸發的 model_select（previousModel
    是別家）就會再寫一筆 vacant_on ⇒ 這裡會數到 2。"""
    out, events = _run(tmp_path, "on_only", models=["baked-a"])
    assert out["after_on"] == "vacant/baked-a"
    assert _transitions(out) == [("vacant_on", "command")]
    assert _jsonl_counts(events) == (1, 0)


def test_non_transitions_leave_no_trace(tmp_path):
    """vacant→vacant（換 vacant 底下的模型）、別家→別家 不是轉換 ⇒ 不寫。
    session_start 的自動切換走 switchOn ⇒ 恰好一筆 vacant_on。"""
    out, events = _run(tmp_path, "non_transitions", models=["baked-a", "baked-b"])
    assert out["after_start"] == "vacant/baked-a"
    assert out["after"] == "other/zzz"
    assert _transitions(out) == [("vacant_on", "session_start"), ("vacant_off", "set")]
    assert _jsonl_counts(events) == (1, 1)


def test_model_select_without_previous_model_uses_own_state(tmp_path):
    """previousModel 沒帶：一開始不知道 ⇒ 當成轉換；之後照 extension 自己記的狀態判斷。"""
    out, events = _run(tmp_path, "no_previous_model", models=["baked-a", "baked-b"])
    assert _transitions(out) == [("vacant_on", "restore"), ("vacant_off", "cycle")]
    assert _jsonl_counts(events) == (1, 1)


# ── Finding 4：`/vacant <打錯字>` 不可以默默跑 status ─────────────────────────────

@pytest.mark.parametrize("arg", ["bogus", "statusReply…", "ON"])
def test_unknown_subcommand_is_usage_warning_without_side_effects(tmp_path, arg):
    out, events = _run(tmp_path, "command", models=["baked-a"], opts={"args": [arg]})
    assert out["after"] == "openai/gpt-x"          # 沒切
    assert out["fired"] == [] and events == []     # 沒留痕
    assert out["fetch_calls"] == 0                 # 沒跑 status（status 會探 proxyd）
    assert len(out["notes"]) == 1
    note = out["notes"][0]
    assert note["level"] == "warning"
    assert note["text"].startswith("用法：/vacant on | off | status")


@pytest.mark.parametrize("arg", ["", "   ", "status", "status extra"])
def test_empty_or_status_still_runs_status(tmp_path, arg):
    """正控制：上面那組的「什麼都沒做」不是因為 handler 整個壞掉。"""
    out, _ = _run(tmp_path, "command", models=["baked-a"], opts={"args": [arg]})
    assert out["fetch_calls"] == 1
    assert len(out["notes"]) == 1 and out["notes"][0]["text"].startswith("Vacant status")
    assert "模型清單" in out["notes"][0]["text"]


def test_compat_is_borrowed_onto_every_model_not_the_provider(tmp_path):
    """2026-09-24 接 Gemini 實測兩件事：(1) 它回 400「Unknown name "store"」，使用者要寫
    `compat.supportsStore:false`，vacant provider 得跟著借；(2) pi 的 registerProvider **只認
    model 層的 compat**——寫在 provider 層會被靜靜忽略（那一次就是這樣照樣送出 store）。
    所以每個 model 都要帶：預設 ← 使用者 provider 層 ← 使用者 model 層；別家 provider 的不借。"""
    provs = _keyed_providers()
    provs["openai"]["compat"] = {"supportsStore": False, "supportsDeveloperRole": True}
    provs["openai"]["models"][1] = {"id": "gpt-y", "compat": {"maxTokensField": "max_tokens",
                                                              "supportsStore": True}}
    provs["elsewhere"]["compat"] = {"supportsStore": True, "thinkingFormat": "qwen"}
    out, _ = _run(tmp_path, "registered", models=[], upstream=UP,
                  pi_agent_dir=_agent_dir(tmp_path, provs))
    assert out["provider_compat"] is None, "provider 層寫 compat 會被 pi 忽略，不准再寫在那裡"
    assert out["model_compats"]["gpt-x"] == {"supportsDeveloperRole": True,
                                             "supportsReasoningEffort": False,
                                             "supportsStore": False}
    # model 層蓋過 provider 層
    assert out["model_compats"]["gpt-y"] == {"supportsDeveloperRole": True,
                                             "supportsReasoningEffort": False,
                                             "supportsStore": True,
                                             "maxTokensField": "max_tokens"}


def test_compat_defaults_when_user_provider_has_none(tmp_path):
    out, _ = _run(tmp_path, "registered", models=[], upstream=UP,
                  pi_agent_dir=_agent_dir(tmp_path, _keyed_providers()))
    assert out["provider_compat"] is None
    for c in out["model_compats"].values():
        assert c == {"supportsDeveloperRole": False, "supportsReasoningEffort": False}
