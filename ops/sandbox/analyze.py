"""配對量尺與成本表；基礎設施作廢保留在分母，缺資料不偽裝成零。"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from vacant_network.research import boot_ci, mcnemar_exact

UNKNOWN = 'UNKNOWN'


def paired(a, b, seed=0):
    pairs = [(a[k], b[k]) for k in sorted(a.keys() & b.keys())]
    if not pairs:
        return dict(n=0, delta=None, p=None, ci95=None)
    improved = sum(not x and y for x, y in pairs)
    regressed = sum(x and not y for x, y in pairs)
    delta = sum(int(y) - int(x) for x, y in pairs) / len(pairs)
    ci = boot_ci(pairs, lambda ps: sum(int(y) - int(x) for x, y in ps) / len(ps), n_boot=10000, seed=seed)
    return dict(n=len(pairs), delta=delta, improved=improved, regressed=regressed,
                p=mcnemar_exact(improved, regressed), ci95=list(ci))


def total(rows, key):
    values = [r.get(key, UNKNOWN) for r in rows]
    return sum(values) if values and all(isinstance(v, (int, float)) for v in values) else UNKNOWN


def costs_complete(row):
    return bool(row.get('calls_complete')) and all(
        isinstance(row.get(k), (int, float))
        for k in ('model_calls', 'prompt_tokens', 'completion_tokens'))


def analyze(run_dir):
    root = Path(run_dir)
    meta = json.loads((root / 'meta.json').read_text())
    config = meta['config']
    cells = [json.loads(p.read_text()) for p in sorted((root / 'cells').glob('*/result.json'))]
    arms = {}
    outcomes = {}
    for arm in config['arms']:
        group = [r for r in cells if r['arm'] == arm]
        n = len(group)
        outcomes[arm] = {(r['task'], r['sample']): bool(r.get('hidden_pass')) and not r['infra_void'] for r in group}
        passed = sum(outcomes[arm].values())
        arms[arm] = dict(n=n, hidden_passed=passed, hidden_rate=passed/n if n else None,
            calls_complete=bool(group) and all(costs_complete(r) for r in group),
            incomplete_cost_cells=sum(not costs_complete(r) for r in group),
            visible_passed=sum(bool(r.get('visible_pass')) for r in group),
            infra_void=sum(r['infra_void'] for r in group), false_success=sum(r.get('false_success', False) for r in group),
            wall_s=total(group, 'wall_s'), model_calls=total(group, 'model_calls'),
            prompt_tokens=total(group, 'prompt_tokens'), completion_tokens=total(group, 'completion_tokens'),
            feedback_rounds=total(group, 'vacant_feedback_rounds'),
            vacant_home_bytes=total(group, 'vacant_home_bytes'), trace_bytes=total(group, 'trace_bytes'),
            workspace_bytes={k: sum(r.get('workspace_bytes', {}).get(k, 0) for r in group)
                             for k in ('pytest_cache', 'logs', 'other')})
    a = outcomes.get('A', {})
    a2 = outcomes.get('A2', {})
    floor = paired(a, a2, config['seed'])
    comparisons = {}
    for arm in ('C', 'G'):
        if arm not in outcomes:
            continue
        comparison = paired(a, outcomes[arm], config['seed'])
        keys = a.keys() & outcomes[arm].keys()
        noise = abs(sum(int(a2[k])-int(a[k]) for k in keys)/len(keys)) if keys and keys <= a2.keys() else None
        gain = (comparison['n'] > 0 and comparison['delta'] > 0 and comparison['p'] < .05
                and noise is not None and comparison['delta'] > noise)
        comparison.update(noise_floor=noise, decision='gain' if gain else 'no measurable gain')
        if noise is None:
            comparison['note'] = 'A2 noise floor unavailable on these paired units'
        comparisons[f'{arm}-A'] = comparison
    tasks = sorted({r['task'] for r in cells})
    if config['tasks'] != ['all']:
        tasks = config['tasks']
    else:
        tasks = meta.get('task_ids', tasks)
    missing = [dict(task=t, sample=s, arm=arm) for t in tasks for s in range(1, config['samples']+1)
               for arm in config['arms'] if (t, s) not in outcomes[arm]]
    matrix = [{k: r.get(k) for k in ('task', 'sample', 'arm', 'hidden_pass', 'visible_pass', 'infra_void')}
              for r in cells]
    infra = [{k: r.get(k) for k in ('task', 'sample', 'arm', 'infra_reason')} for r in cells if r['infra_void']]
    contaminated = [{k: r.get(k) for k in ('task', 'sample', 'arm', 'contamination_evidence')}
                    for r in cells if r.get('contamination')]
    summary = dict(evidence=meta.get('evidence'), arms=arms, comparisons=comparisons,
                   aa_control=floor, missing=missing, per_task=matrix, infra_void=infra,
                   contamination=contaminated)
    (root / 'summary.json').write_text(json.dumps(summary, indent=2))
    lines = ['# Sandbox comparison', '', f"Evidence: {meta.get('evidence')}. Completed cells include infra_void in denominators.", '',
             '| Arm | Hidden pass | Visible pass | Infra void | False success heuristic |',
             '|---|---:|---:|---:|---:|']
    for arm, r in arms.items():
        lines.append(f"| {arm} | {r['hidden_passed']}/{r['n']} | {r['visible_passed']}/{r['n']} | {r['infra_void']} | {r['false_success']} |")
    lines += ['', '## Paired comparisons', '', f'A/A2 control: `{json.dumps(floor)}`']
    lines += [f'- {name}: `{json.dumps(value)}`' for name, value in comparisons.items()]
    lines += ['', '## Costs (totals)', '',
              'Incomplete call/token totals are lower bounds (>=), not final costs; UNKNOWN stays unknown. No cost means are estimated.', '',
              '| Arm | Wall s | Calls | Input tokens | Output tokens | Incomplete cells | Feedback | Vacant bytes | Trace bytes | Workspace bytes (cache/log/other) |', '|---|---:|---:|---:|---:|---:|---:|---:|---:|---|']
    for arm, r in arms.items():
        cost = {k: f">= {r[k]}" if not r['calls_complete'] and isinstance(r[k], (int, float)) else r[k]
                for k in ('model_calls', 'prompt_tokens', 'completion_tokens')}
        lines.append(f"| {arm} | {r['wall_s']} | {cost['model_calls']} | {cost['prompt_tokens']} | {cost['completion_tokens']} | {r['incomplete_cost_cells']} | {r['feedback_rounds']} | {r['vacant_home_bytes']} | {r['trace_bytes']} | {r['workspace_bytes']} |")
    lines += ['', '## Per-task matrix', '', '| Task | Sample | Arm | Hidden | Visible | Infra |', '|---|---:|---|---|---|---|']
    for r in matrix:
        lines.append('| ' + ' | '.join(str(r[k]) for k in ('task', 'sample', 'arm', 'hidden_pass', 'visible_pass', 'infra_void')) + ' |')
    lines += ['', '## Infra-void table', '', '| Task | Sample | Arm | Reason |', '|---|---:|---|---|']
    for r in infra:
        lines.append(f"| {r['task']} | {r['sample']} | {r['arm']} | {r['infra_reason']} |")
    lines += ['', '## Contamination flags (retained in denominators)', '']
    lines += [f'- `{json.dumps(r)}`' for r in contaminated] or ['None detected (heuristic, not proof of isolation).']
    lines += ['', f'Missing scheduled cells: `{json.dumps(missing)}`', '']
    (root / 'summary.md').write_text('\n'.join(lines))
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run_dir', type=Path)
    args = parser.parse_args()
    summary = analyze(args.run_dir)
    print((args.run_dir / 'summary.md').read_text())
    return summary


if __name__ == '__main__':
    main()
