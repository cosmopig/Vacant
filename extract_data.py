#!/usr/bin/env python3
import json
from pathlib import Path

EXP = "e011_l001_dabench_smoke"
RUNS_DIR = Path("/srv/vlab/runs") / EXP
TASKS = ["dab_378", "dab_426", "dab_039", "dab_725", "dab_218", "dab_517"]

data = []
for t in TASKS:
    for arm in ("A", "C"):
        name = f"dabench-{t}-pi-{arm}-r1"
        path = RUNS_DIR / name
        if path.exists():
            score_f = path / "score.json"
            cell_f = path / "cell.json"
            s = {}
            c = {}
            if score_f.exists():
                with open(score_f) as f: s = json.load(f)
            if cell_f.exists():
                with open(cell_f) as f: c = json.load(f)
            
            # The metrics are nested inside a "metrics" key in some files, 
            # but the previous grep showed them at top level or maybe I misread.
            # Let's check the head output again: "metrics":{...} was there.
            m = c.get("metrics", {})
            data.append({
                "task": t,
                "arm": arm,
                "pass": s.get("pass"),
                "wall_s": c.get("wall_s"),
                "model_calls": m.get("model_calls"),
                "input_tokens": m.get("input_tokens")
            })

print(json.dumps(data, indent=2))
