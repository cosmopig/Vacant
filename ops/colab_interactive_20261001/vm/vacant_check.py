"""C 組有沒有真的裝上、有沒有作用（逐字取自 redesign 分支 ops/eval/harbor_vacant.py@11f91f87 的 `_CHECK`，
sha256 222fc559…）。在那一格使用者的圍牆裡、用 pipx 裝的 vacant 的 python 跑；讀 ~/.vacant，印一行 JSON。"""
import json, pathlib
h = pathlib.Path.home() / ".vacant"
out = {"install_json": None, "pi_installed": False, "chains": 0, "steps": 0, "reviews": 0,
       "review_actions": [], "nudges": 0, "nudge_turns": [], "ended_notes": 0}
p = h / "adapters" / "install.json"
if p.is_file():
    d = json.loads(p.read_text())
    out["install_json"] = {"mode": d.get("mode"), "agents": sorted((d.get("agents") or {}))}
    out["pi_installed"] = "pi" in (d.get("agents") or {})
for c in h.glob("trace/projects/*/chain.ndjson"):
    out["chains"] += 1
    for ln in c.read_text().split("\n"):
        if not ln.strip():
            continue
        e = json.loads(ln)
        if e.get("type") == "step":
            out["steps"] += 1
        elif e.get("type") == "review":
            out["reviews"] += 1
            out["review_actions"].append((e.get("payload") or {}).get("action"))
        elif e.get("type") == "nudge":            # 零設定 v3：回合預算提醒
            out["nudges"] += 1
            out["nudge_turns"].append((e.get("payload") or {}).get("turn"))
        elif e.get("type") == "ended":            # 零設定 v3：還沒說做完就結束的交件說明
            out["ended_notes"] += 1
# 裝上了、病歷有步驟＝C 組有作用；有沒有走到交件前檢查另外記（回合用完被中止的跑，pi 不會進 Stop）
out["c_arm_ok"] = out["pi_installed"] and out["steps"] > 0
out["stop_reached"] = out["reviews"] > 0
print(json.dumps(out))
