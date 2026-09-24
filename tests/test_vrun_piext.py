"""piext 渲染出來的 extension **行為**測試（不只是語法）。

`test_vrun_possess.py` 用 `node --check` 驗語法；這裡把渲染結果當 ES module 載進 node，
塞一個假的 `pi` 物件＋假的 `fetch`，真的去跑 `refreshModels` 與 `/vacant off`。
掛鉤走**真的** `hookcli`（python＝本測試的直譯器、PYTHONPATH＝repo 根），
所以「日誌裡有幾筆 vacant_off」數的是實際落盤的 JSONL，不是 stub 的計數器。

沒有 node ⇒ **skip 並印理由**（量不到不是通過）。
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from vacant_network.vrun import piext

REPO = Path(__file__).resolve().parents[1]

_HARNESS = r"""
const [, , extPath, scenario] = process.argv;
const providers = {}, commands = {}, handlers = {};
const registry = {
  models: [{ provider: "openai", id: "gpt-x" }],
  find(p, id) { return this.models.find((m) => m.provider === p && m.id === id) || null; },
  getAll() { return this.models; },
};
let current = { provider: "openai", id: "gpt-x" };
const pi = {
  registerProvider(id, cfg) {
    providers[id] = cfg;
    for (const m of cfg.models) registry.models.push({ provider: id, id: m.id });
  },
  registerCommand(name, cfg) { commands[name] = cfg; },
  on(ev, fn) { (handlers[ev] = handlers[ev] || []).push(fn); },
  async setModel(m) {
    current = m;
    // 模擬 pi：切模型會觸發 model_select（真 pi 的 /model 也走這條）
    for (const fn of handlers["model_select"] || []) await fn({ model: m, source: "set" });
    return true;
  },
};
const ctx = () => ({ hasUI: false, modelRegistry: registry, model: current });

const mod = await import(extPath);
mod.default(pi);

const out = {};
if (scenario === "refresh_502_text") {
  globalThis.fetch = async () => new Response("<html>502 Bad Gateway</html>",
    { status: 502, headers: { "content-type": "text/html" } });
  out.models = await providers.vacant.refreshModels({ signal: undefined });
} else if (scenario === "refresh_json_error") {
  globalThis.fetch = async () => new Response(JSON.stringify({ error: { message: "upstream down" } }),
    { status: 502, headers: { "content-type": "application/json" } });
  out.models = await providers.vacant.refreshModels({ signal: undefined });
} else if (scenario === "refresh_200_empty") {
  globalThis.fetch = async () => new Response(JSON.stringify({ data: [] }), { status: 200 });
  out.models = await providers.vacant.refreshModels({ signal: undefined });
} else if (scenario === "refresh_throws") {
  globalThis.fetch = async () => { throw new Error("ECONNREFUSED"); };
  out.models = await providers.vacant.refreshModels({ signal: undefined });
} else if (scenario === "refresh_ok") {
  globalThis.fetch = async () => new Response(JSON.stringify({ data: [{ id: "up-a" }, { id: "up-b" }] }), { status: 200 });
  out.models = await providers.vacant.refreshModels({ signal: undefined });
} else if (scenario === "off_via_command" || scenario === "off_via_model") {
  globalThis.fetch = async () => { throw new Error("no network in test"); };
  await commands.vacant.handler("on", ctx());
  out.after_on = current.provider + "/" + current.id;
  if (scenario === "off_via_command") {
    await commands.vacant.handler("off", ctx());
  } else {
    await pi.setModel({ provider: "openai", id: "gpt-x" });   // 使用者自己 /model 切走
  }
  out.after_off = current.provider + "/" + current.id;
}
out.models = out.models && out.models.map((m) => m.id);
console.log(JSON.stringify(out));
"""


def _run(tmp_path: Path, scenario: str, models: list[str]) -> tuple[dict, list[dict]]:
    node = shutil.which("node")
    if not node:
        pytest.skip("這台沒有 node ⇒ extension 行為沒量到（不是通過）")
    state = tmp_path / "state"
    body = piext.render(port=1, state_dir=str(state), python=sys.executable,
                        package_path=str(REPO), models=models,
                        default_model="dflt-model")
    ext = tmp_path / "vacant.mjs"          # 內容是純 JS；.mjs 讓 node 以 ESM 載入
    ext.write_text(body, encoding="utf-8")
    harness = tmp_path / "harness.mjs"
    harness.write_text(_HARNESS, encoding="utf-8")
    r = subprocess.run([node, str(harness), ext.as_uri(), scenario],
                       capture_output=True, text=True, timeout=120)
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
