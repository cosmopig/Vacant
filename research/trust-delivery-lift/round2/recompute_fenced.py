#!/usr/bin/env python3
"""Post-fence recomputes: primary untouched IDs, secondary, mechanism honesty."""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parents[1]))
from vacant_network.research import mcnemar_exact

from recompute_r2 import load_rows, summarize_primary, mcnemar_pair

MANIFEST = ROOT / "data/holdout_05b_confirmatory/FENCE_MANIFEST.json"
ROWS = ROOT / "data/holdout_05b_confirmatory/rows.jsonl"


def filter_rows(rows: list[dict], ids: set[str]) -> list[dict]:
    return [r for r in rows if r["task_id"] in ids]


def mechanism_vacant(rows: list[dict]) -> dict:
    vac = [r for r in rows if r["arm"] == "VACANT"]
    n = len(vac)
    n_calls = [r["n_calls"] for r in vac]
    repair_fired = [r for r in vac if r.get("n_calls", 0) > 1]
    gains = []
    for r in vac:
        d0 = bool(r.get("draft_oracle_success"))
        fin = bool(r.get("oracle_whole_success"))
        if r.get("n_calls", 0) > 1:
            gains.append(int(fin) - int(d0))
    draft_rate = sum(bool(r.get("draft_oracle_success")) for r in vac) / n if n else 0
    return {
        "n": n,
        "repair_trigger_rate": len(repair_fired) / n if n else 0,
        "n_calls_histogram": dict(sorted({c: n_calls.count(c) for c in set(n_calls)}.items())),
        "mean_cpu_s": sum(r["cpu_seconds"] for r in vac) / n if n else 0,
        "draft_oracle_rate": draft_rate,
        "conditional_repair_gain": {
            "n_repair_fired": len(repair_fired),
            "mean_oracle_delta_final_minus_draft": sum(gains) / len(gains) if gains else None,
            "net_tasks_improved": sum(1 for g in gains if g > 0),
        },
        "note": "Greedy draft often passes visible → n_calls=1 → compares 1-shot vs Maj3×3, not repair loop.",
    }


def main() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    primary_ids = set(manifest["primary_confirmatory"])
    secondary_ids = set(manifest["secondary_sensitivity"])
    rows = load_rows(ROWS)
    primary_rows = filter_rows(rows, primary_ids)
    secondary_rows = filter_rows(rows, secondary_ids)

    out = {
        "label_primary": "primary_confirmatory_untouched_tail",
        "n_tasks_primary": len(primary_ids),
        "primary": summarize_primary(primary_rows),
        "mcnemar_primary_vacant_vs_maj3": mcnemar_pair(primary_rows, "VACANT", "MAJ3"),
        "label_secondary": "secondary_sensitivity_contaminated",
        "secondary_mcnemar_vacant_vs_maj3": mcnemar_pair(secondary_rows, "VACANT", "MAJ3"),
        "secondary_mcnemar_vacant_vs_blind": mcnemar_pair(secondary_rows, "VACANT", "BLIND"),
        "mechanism_honesty_vacant": {
            "primary_tail": mechanism_vacant(primary_rows),
            "secondary_all": mechanism_vacant(secondary_rows),
        },
        "cpu_taint_warning": "confirmatory rows may reflect dual-harness CPU contention through hold_K",
        "manifest_sha256_file": "FENCE_ADDENDUM_SHA256.json",
    }
    out_path = ROOT / "data/holdout_05b_confirmatory/summary_fenced.json"
    out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps({"primary_mcnemar": out["mcnemar_primary_vacant_vs_maj3"], "n_primary_tasks": len(primary_ids)}, indent=2))


if __name__ == "__main__":
    main()