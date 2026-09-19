#!/usr/bin/env python3
"""把 20 格的 run_RUN-ON.json 收成一份 matrix.json（機器讀）＋一張表（人讀）。

在 vacant-dev 上跑。不做任何判斷，只搬欄位——判斷留給人。
"""
import json
import pathlib
import collections
import hashlib
import sys

ROOT = pathlib.Path("/var/tmp/vacant_v1matrix")
AGENTS = ["pi", "opencode", "claude", "codex", "hermes"]
GRIDS = ["refuse", "deliver"]
REPS = [1, 2]

FIELDS = ("task_id", "accepted", "refused", "stop_reason", "requests_seen",
          "wire_by_protocol", "wire_errors", "agent_rc", "agent_wall_s",
          "run_wall_s", "visible_passed", "visible_total",
          "ws_start_sha256", "ws_end_sha256", "wire_digest",
          "verdict_sha256", "verdict_hash", "upstreams_defaulted",
          "attempts_used", "retry")

rows = []
for rep in REPS:
    for agent in AGENTS:
        for grid in GRIDS:
            name = f"{agent}_{grid}_r{rep}"
            rd = ROOT / f"rd_{name}"
            ws = ROOT / f"ws_{name}"
            rec = {"cell": name, "agent": agent, "grid": grid, "rep": rep}
            ec = rd / "_launcher_exit_code.txt"
            rec["exit_code"] = int(ec.read_text().strip()) if ec.exists() else None
            f = rd / "run_RUN-ON.json"
            if not f.exists():
                rec["_missing"] = True
                rows.append(rec)
                continue
            d = json.loads(f.read_text())
            for k in FIELDS:
                rec[k] = d.get(k)
            idx = rd / "wire_RUN-ON" / "index.jsonl"
            paths = collections.Counter()
            ups = set()
            if idx.exists():
                for line in idx.read_text().splitlines():
                    if not line.strip():
                        continue
                    r = json.loads(line)
                    key = (f"{r.get('method')} {r.get('path')} -> {r.get('status')} "
                           f"[{r.get('wire') or r.get('protocol')}]")
                    paths[key] += 1
                    if r.get("upstream"):
                        ups.add(r["upstream"])
            rec["proxy_paths"] = dict(paths)
            rec["upstreams_seen"] = sorted(ups)
            sol = ws / "solution.py"
            if sol.exists():
                b = sol.read_bytes()
                rec["solution_sha256"] = hashlib.sha256(b).hexdigest()
                rec["solution_text"] = b.decode("utf-8", "replace")
            else:
                rec["solution_sha256"] = None
                rec["solution_text"] = None
            rp = rd / f"receipts_RUN-ON.ndjson"
            rec["receipts_lines"] = (
                len([x for x in rp.read_text().splitlines() if x.strip()])
                if rp.exists() else None)
            rows.append(rec)

out = ROOT / "matrix.json"
out.write_text(json.dumps(rows, ensure_ascii=False, indent=2))
print(f"wrote {out} ({len(rows)} cells)")

hdr = ("cell", "exit", "accepted", "stop_reason", "rs", "wire_by_protocol",
       "agent_rc", "vis", "ws_end_sha256")
print("\t".join(hdr))
for r in rows:
    print("\t".join(str(x) for x in (
        r["cell"], r.get("exit_code"), r.get("accepted"), r.get("stop_reason"),
        r.get("requests_seen"), r.get("wire_by_protocol"), r.get("agent_rc"),
        f"{r.get('visible_passed')}/{r.get('visible_total')}",
        (r.get("ws_end_sha256") or "")[:12])))

# 一致性：rep1 vs rep2
print("\n#### rep1 vs rep2")
for agent in AGENTS:
    for grid in GRIDS:
        a = next(r for r in rows if r["cell"] == f"{agent}_{grid}_r1")
        b = next(r for r in rows if r["cell"] == f"{agent}_{grid}_r2")
        diffs = []
        for k in ("exit_code", "accepted", "stop_reason", "requests_seen",
                  "wire_by_protocol", "agent_rc", "visible_passed",
                  "ws_end_sha256", "proxy_paths"):
            if a.get(k) != b.get(k):
                diffs.append(f"{k}: {a.get(k)} vs {b.get(k)}")
        print(f"{agent}_{grid}: " + ("IDENTICAL" if not diffs else "; ".join(diffs)))
