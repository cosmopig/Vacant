"""Aggregate metrics.json files into a markdown summary (+ within-task consistency).

Usage: python analyze.py RUNS_DIR [--out summary.md]
Within-task consistency = mean pairwise edit similarity between repeats of the
same task and condition: a process the agent itself can't reproduce can't be
expected to match a user's.
"""
from __future__ import annotations

import argparse
import itertools
import json
from collections import defaultdict
from pathlib import Path

import metrics


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("runs")
    ap.add_argument("--out")
    a = ap.parse_args()
    rows = [json.loads(p.read_text()) for p in sorted(Path(a.runs).glob("*/metrics.json"))]
    lines = ["| run | sequence | steps | asks | read<edit | test<edit | test>edit | diff +/- | errors | calls | tok in/out | wall s | sim cautious (seq/feat) | sim fast (seq/feat) |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    by_task = defaultdict(list)
    for r in rows:
        f = r["features"]
        ps = r.get("persona_similarity", {})
        def sim(n):
            p = ps.get(n, {})
            return f"{p.get('edit_sim_collapsed','-')}/{p.get('feature_agreement','-')}"
        lines.append(f"| {r['run_id']} | `{r['sequence']}` | {f['n_steps']} | {f['counts']['A']} | {f['read_before_first_edit']} | "
                     f"{f['test_before_first_edit']} | {f['test_after_last_edit']} | +{f['diff_added']}/-{f['diff_removed']} | "
                     f"{f['n_tool_errors']} | {r['llm_calls']} | {r['tokens_in']}/{r['tokens_out']} | {r['wall_s']} | {sim('example_cautious')} | {sim('example_fast')} |")
        by_task[(r["task_id"], r["condition"])].append(r["sequence"])
    lines += ["", "Within-task self-consistency (mean pairwise collapsed edit similarity across repeats):", ""]
    for (t, c), seqs in sorted(by_task.items()):
        pairs = list(itertools.combinations(seqs, 2))
        if pairs:
            v = sum(metrics.edit_similarity(metrics.collapse(x), metrics.collapse(y)) for x, y in pairs) / len(pairs)
            lines.append(f"- {t} [{c}]: {v:.3f} over {len(seqs)} runs ({', '.join('`'+s+'`' for s in seqs)})")
    txt = "\n".join(lines) + "\n\nPersona columns compare against SYNTHETIC example personas (personas/examples.json), not a real user.\n"
    if a.out:
        Path(a.out).write_text(txt)
    print(txt)


if __name__ == "__main__":
    main()
