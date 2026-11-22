#!/usr/bin/env python3
"""凍結規則的留出檢查：遵循 CLAUDE.md 鐵律，探索集與重跑集分開。"""
import collections
import contextlib
import hashlib
import io
import inspect
import json
import math
from pathlib import Path

if __package__:
    from . import analyze_receipts as frozen
    from .cache import CACHE as WORK, REPO, prepare
else:
    import analyze_receipts as frozen
    from cache import CACHE as WORK, REPO, prepare
ORIGINAL_SHA = '06d1a91dc7e121a5b9f606d2da8cf7920757b57d7f612b03ca7a8cc429efab2d'
assert hashlib.sha256(inspect.getsource(frozen.answer_overlap).encode()).hexdigest() == ORIGINAL_SHA


def snapshot_answer(trial):
    states = list(trial.glob('agent/vacant_home/trace/projects/*/state.json'))
    if not states:
        return None
    assert len(states) == 1
    state = json.loads(states[0].read_text())
    objects = trial / 'agent/vacant_home/trace/objects'

    def blob(h):
        return (objects / h[:2] / h).read_text()

    index = json.loads(blob(state['last_index']))
    return blob(index['answer.txt'][0]) if 'answer.txt' in index else None


def explicit_answer(steps):
    # Identical extraction to formal-A discovery script; not a final-artifact proof.
    writes = [c.get('arguments', {}).get('content', '')
              for s in steps for c in s.get('tool_calls', [])
              if c.get('function_name') == 'write' and
              str(c.get('arguments', {}).get('path', '')).endswith('/answer.txt')]
    return writes[-1] if writes else None


def wilson(k, n):
    if not n:
        return 'NA'
    z = 1.959963984540054
    p = k / n
    den = 1 + z*z/n
    mid = (p + z*z/(2*n)) / den
    half = z * math.sqrt(p*(1-p)/n + z*z/(4*n*n)) / den
    return f'{k}/{n}={100*p:.1f}% [{100*(mid-half):.1f},{100*(mid+half):.1f}]'


def summarize(label, rows):
    known = [r for r in rows if r['overlap'] is not None]
    flagged = [r for r in known if not r['overlap']]
    unflagged = [r for r in known if r['overlap']]
    ff = sum(r['reward'] == 0 for r in flagged)
    uf = sum(r['reward'] == 0 for r in unflagged)
    print(f'| {label} | {len(rows)} | {len(known)} | {ff},{len(flagged)-ff} | '
          f'{uf},{len(unflagged)-uf} | {wilson(len(flagged),len(known))} | '
          f'{wilson(ff,ff+uf)} | {wilson(ff,len(flagged))} | {wilson(uf,len(unflagged))} |')
    print('COUNTS', label, dict(collections.Counter(
        (r['delivery_status'], r['reward'], r['answer_source']) for r in rows)))


def heldout(dataset):
    prepare(dataset)
    base = REPO / 'ops/eval/evidence_20260927_nocap' / dataset
    if dataset == 'u274':
        cells = json.loads((base / 'analysis/cells.json').read_text())
        selected = {c['trial']: c for c in cells}
    elif dataset == 's36nc':
        cells = json.loads((base / 'analysis.json').read_text())['cells']
        selected = {(str(c['task']), c['arm'], c['sample']): c for c in cells}
    elif dataset == 'localformal':
        base = REPO / 'ops/eval/evidence_20260926_local/formal'
        cells = json.loads((base / 'cells.json').read_text())
        selected = {c['trial']: c for c in cells}
    else:
        base = REPO / 'ops/eval/evidence_20260926_local/s36'
        cells = [json.loads(s) for s in (base / 'progress.jsonl').read_text().splitlines()]
        selected = {(str(c['task']), c['arm'], c['sample']): c for c in cells}
    rows = []
    trajectories = sorted((WORK / 'heldout' / dataset).rglob('trajectory.json'))
    skipped = 0
    seen = set()
    for trajectory in trajectories:
        trial = trajectory.parent.parent
        task = trial.name.split('__')[0].split('-')[1]
        tag = trial.parent.name
        arm = tag.split('-')[-3]
        sample = int(tag.rsplit('-s', 1)[1])
        key = trial.name if dataset in ('u274', 'localformal') else (task, arm, sample)
        if key not in selected:
            skipped += 1
            continue
        cell = selected[key]
        assert key not in seen
        seen.add(key)
        result = json.loads((trial / 'result.json').read_text())
        reward = result['verifier_result']['rewards']['reward']
        assert reward in (0.0, 1.0) and reward == cell.get('reward', reward)
        assert float((trial / 'verifier/reward.txt').read_text()) == reward
        steps = json.loads(trajectory.read_text())['steps']
        verifier_stdout = (trial / 'verifier/test-stdout.txt').read_text()
        delivered = (cell['answer_file'] if dataset in ('u274', 'localformal') else
                     not cell['missing'] if dataset == 's36nc' else '\nGot: ' in verifier_stdout)
        have_snapshot = arm != 'A' and (trial / 'agent/vacant_home/trace/objects').is_dir()
        source = 'snapshot' if have_snapshot else 'explicit_write_proxy'
        answer = snapshot_answer(trial) if have_snapshot else explicit_answer(steps)
        # A historical write is not treated as a final delivery when archive says no file.
        if not delivered:
            answer = None
        overlap = frozen.answer_overlap(steps, answer)
        rows.append(dict(dataset=dataset, arm=arm, trial_id=trial.name, task=task,
                         sample=sample, reward=reward, answer=answer, overlap=overlap,
                         answer_source=source, trajectory=str(trajectory),
                         delivery_status=('known' if overlap is not None else
                                          'empty_answer' if delivered and answer is not None else
                                          'unrecoverable_answer' if delivered else 'no_file')))
    for key in selected.keys() - seen:
        cell = selected[key]
        rows.append(dict(dataset=dataset, arm=cell['arm'], trial_id=cell['trial'],
                         task=cell['task'], sample=cell['sample'], reward=cell['reward'],
                         answer=None, overlap=None, answer_source='missing_trajectory',
                         delivery_status='missing_trajectory'))
    assert len(rows) == len(selected), (dataset, len(rows), len(selected))
    assert len({r['trial_id'] for r in rows}) == len(rows)
    print('ARCHIVE', dataset, 'selected',len(rows),'excluded replacements/infra',skipped)
    return rows


def main():
    print('FROZEN_RULE_SHA256', ORIGINAL_SHA)
    allrows = []
    print('| Dataset/arm | All runs | Known answers | Flagged fail,pass | Not flagged fail,pass | Flagged share (known) | Recall (known wrong) | P(fail|flagged) | P(fail|not flagged) |')
    print('|---|---:|---:|---|---|---|---|---|---|')
    formal = frozen.build()
    for arm in ['C', 'A']:
        source = [r for r in formal if r['arm'] == arm]
        mapped = [dict(r, overlap=r['archived_answer_in_shell_output'] if arm == 'C'
                       else r['explicit_answer_in_shell_output'],
                       answer_source='snapshot' if arm == 'C' else 'explicit_write_proxy',
                       delivery_status='formal_original_cohort') for r in source]
        summarize('Formal '+arm, mapped)
        if arm == 'A':
            summarize('Formal A final response', [r for r in mapped if r['has_final_response']])
    for dataset in ['u274', 's36nc', 'localformal', 's36']:
        rows = heldout(dataset)
        for arm in sorted({r['arm'] for r in rows}):
            summarize(dataset+' '+arm, [r for r in rows if r['arm'] == arm])
        allrows.extend(rows)
    discovery_tasks = {str(r['task']) for r in formal}
    for dataset in ['u274', 's36nc', 'localformal', 's36']:
        taskset = {r['task'] for r in allrows if r['dataset'] == dataset}
        print('TASK_OVERLAP',dataset,len(taskset & discovery_tasks),'of',len(taskset))
    (WORK / 'heldout_receipt_rows.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in allrows))
    print('CHECKED selected trial uniqueness, per-run reward vs archived cells and verifier reward.txt; all assertions passed')


if __name__ == '__main__':
    report = io.StringIO()
    with contextlib.redirect_stdout(report):
        main()
    (WORK / 'heldout_receipt_analysis.md').write_text(report.getvalue())
    print(report.getvalue(), end='')
