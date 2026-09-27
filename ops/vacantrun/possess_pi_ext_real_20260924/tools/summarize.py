#!/usr/bin/env python3
"""五格收斂成一張表。只讀已落盤的切片，不重算任何東西；隱藏尺在這裡跑（run 結束之後）。"""
import collections, json, pathlib, subprocess, sys
R = pathlib.Path("/var/tmp/vacant_piext_20260924")
SCORER = R / "repo/ops/vacantrun/possess_pi_real_20260922/tools/score_hidden.py"
rows = []
for t in ["lcb_3522", "lcb_3584", "lcb_3649", "lcb_3715", "lcb_3789"]:
    L = R / "cells" / f"task_{t}_r1"
    relay = [json.loads(x) for x in open(L / "relay_slice.jsonl") if x.strip()]
    prox = [json.loads(x) for x in open(L / "proxyd_slice.jsonl") if x.strip()]
    rp = [r for r in relay if r["method"] == "POST"]
    pp = [r for r in prox if r["method"] == "POST"]
    hooks = []
    hfs = (L / "hook_files_new.txt").read_text().split()
    for hf in hfs:
        hooks += [json.loads(x) for x in open(L / hf) if x.strip()]
    ev = collections.Counter(h["event"] for h in hooks)
    out = subprocess.run([sys.executable, str(SCORER), t, str(R / "ws" / f"{t}_r1")],
                         capture_output=True, text=True)
    try:
        hs = json.loads(out.stdout)
    except Exception:
        hs = {"error": (out.stdout + out.stderr)[-300:]}
    hidden = (f"{hs['passed']}/{hs['total']}" if hs.get("total") is not None
              else hs.get("note") or hs.get("error") or hs)
    rows.append(dict(
        task=t, rc=int((L / "rc").read_text()), wall_s=float((L / "wall_s").read_text()),
        visible_rc=int((L / "visible.rc").read_text()),
        delivered=(L / "delivered_solution.py").exists(),
        relay_post=len(rp), relay_post_auth_ok=sum(r["auth"] == "ok" for r in rp),
        relay_post_200=sum(r.get("status") == 200 for r in rp),
        proxyd_post=len(pp), proxyd_post_200=sum(r.get("status") == 200 for r in pp),
        proxyd_all=len(prox), hook_files=len(hfs), hook_events=dict(ev), hidden=hidden))
json.dump(rows, open(R / "cells/tasks_summary.json", "w"), ensure_ascii=False, indent=1)
for r in rows:
    print(json.dumps(r, ensure_ascii=False))
