#!/usr/bin/env python3
"""探索性收據分析：讓依賴有根據；遵循 CLAUDE.md 鐵律，不把值重疊當正確性。"""
import collections
import contextlib
import io
import json
import re
from pathlib import Path

if __package__:
    from .cache import CACHE as ROOT, REPO, prepare
else:
    from cache import CACHE as ROOT, REPO, prepare

GIVEN = ['acquirer_countries.csv', 'fees.json', 'manual.md', 'merchant_category_codes.csv',
         'merchant_data.json', 'payments-readme.md', 'payments.csv']
NUM = re.compile(r'(?<![\w])[-+]?\d+(?:,\d{3})*(?:\.\d+)?(?![\w])')


def nums(s):
    return {float(n.replace(',', '')) for n in NUM.findall(s)}


def answer_overlap(steps, answer):
    if answer is None or not answer.strip():
        return None
    outputs = []
    for s in steps:
        calls = {c['tool_call_id']: c for c in s.get('tool_calls', [])}
        for obs in (s.get('observation') or {}).get('results', []):
            c = calls.get(obs.get('source_call_id'), {})
            args = c.get('arguments') or {}
            if c.get('function_name') != 'bash' or (obs.get('extra') or {}).get('is_error'):
                continue
            cmd = str(args.get('command', ''))
            if 'answer.txt' in cmd or re.match(r'^\s*(?:ls|find|echo)\b', cmd):
                continue
            outputs.append(str(obs.get('content') or ''))
    corpus = '\n'.join(outputs)
    values = nums(answer)
    if values:
        return values <= nums(corpus)
    return bool(re.search(r'(?<!\w)' + re.escape(answer.strip()) + r'(?!\w)', corpus, re.I))


def trajectory_features(steps):
    finals = [s for s in steps if s.get('source') == 'agent' and s.get('message')
              and not s.get('tool_calls')]
    final = finals[-1]['message'] if finals else ''
    cutoff = steps.index(finals[-1]) if finals else len(steps)
    opened, outputs, shell_outputs = set(), [], []
    errors = 0
    for s in steps[:cutoff]:
        calls = {c['tool_call_id']: c for c in s.get('tool_calls', [])}
        for obs in (s.get('observation') or {}).get('results', []):
            c = calls.get(obs.get('source_call_id'), {})
            name, args = c.get('function_name'), c.get('arguments') or {}
            out = str(obs.get('content') or '')
            bad = bool((obs.get('extra') or {}).get('is_error'))
            errors += bad
            if bad:
                continue
            outputs.append(out)
            cmd = str(args.get('command', ''))
            # Exclude simple listing and answer-file echo/readback from shell proxy.
            if name == 'bash' and not re.match(r'^\s*(?:ls|find|echo|cat\s+(?:/app/)?answer\.txt)\b', cmd):
                shell_outputs.append(out)
            for f in GIVEN:
                if name == 'read' and f in str(args.get('path', '')):
                    opened.add(f)
                elif name == 'bash' and f in cmd and re.search(
                        r'\b(?:cat|head|tail|sed|awk|grep|rg|open|read_csv|read_json)\b', cmd):
                    opened.add(f)
    values = nums(final)
    # Numbers in paths/claims/explanations may not be the actual answer: retain tokens.
    allnums, shellnums = nums('\n'.join(outputs)), nums('\n'.join(shell_outputs))
    return dict(final_message=final, has_final_response=bool(final), final_numeric_tokens=sorted(values),
                any_final_number_in_tool_output=bool(values & allnums) if values else None,
                all_final_numbers_in_tool_output=values <= allnums if values else None,
                any_final_number_in_nontrivial_shell_output=bool(values & shellnums) if values else None,
                trajectory_opened_given_files=sorted(opened),
                trajectory_frac_given_files_opened=len(opened)/len(GIVEN),
                trajectory_has_unopened_given_files=len(opened) < len(GIVEN),
                trajectory_had_tool_error=bool(errors))


def build():
    prepare('formal')
    rows, missing = [], []
    runs = json.loads((REPO/'ops/eval/evidence_20260925/formal/runs.json').read_text())
    for r in runs:
        base = ROOT/'formal/jobs'/r['job']/r['trial']
        tp = base/'agent/trajectory.json'
        if not tp.exists():
            missing.append(r['trial'])
            continue
        ds = list((base/'agent').rglob('delivery.json'))
        if r['arm'] == 'C' and not ds:
            continue
        row = dict(trial_id=r['trial'], task=r['task'], model=r['model'], arm=r['arm'],
                   reward=r['reward'], rerun=r['rerun'], job=r['job'], delivery=None)
        steps = json.loads(tp.read_text())['steps']
        row.update(trajectory_features(steps))
        explicit = [c['arguments'].get('content') for s in steps for c in s.get('tool_calls', [])
                    if c.get('function_name') == 'write' and
                    str(c.get('arguments', {}).get('path', '')).endswith('/answer.txt')]
        row['last_explicit_answer_write'] = explicit[-1] if explicit else None
        row['explicit_answer_in_shell_output'] = answer_overlap(steps, row['last_explicit_answer_write'])
        if ds:
            assert len(ds) == 1
            p = ds[0]
            d = json.loads(p.read_text())
            row['delivery'] = d
            for k in ['checked', 'deliverables', 'fixed', 'unverified', 'findings', 'in_progress']:
                row[k] = d.get(k)
            for k in ['checked', 'traced', 'derived', 'exempt', 'not_typed']:
                row[k+'_count'] = d.get('checked', {}).get(k, 0)
            note = p.with_suffix('.md').read_text()
            m = re.search(r'Files in the folders named in the request: (\d+) — opened: ([^\n;]+)', note)
            denom = len(d.get('in_dirs', []))
            opened = len(d.get('dir_opened', []))
            if m:
                assert int(m[1]) == denom
                assert (0 if m[2].strip() == 'none' else len(m[2].split(', '))) == opened
                denom = int(m[1])
                opened = 0 if m[2].strip() == 'none' else len(m[2].split(', '))
            row.update(n_unverified=len(d.get('unverified', [])),
                       has_unopened_given_files=any('Given files never opened:' in x for x in d.get('unverified', [])),
                       frac_given_files_opened=opened/denom if denom else None,
                       had_findings=bool(d.get('findings')), any_fixed=bool(d.get('fixed')))
            chain = [json.loads(s) for s in p.with_name('chain.ndjson').read_text().splitlines()]
            reviews = [e for e in chain if e['type'] == 'review']
            row['stop_review_rounds'] = len(reviews)
            st = json.loads(p.with_name('zero_state.json').read_text())
            row['feedback_rounds'] = len(st.get('sessions', {}).get(d['session'], {}).get('rounds', []))
            row['review_payloads'] = [e.get('payload') for e in reviews]
            state = json.loads(p.with_name('state.json').read_text())
            objects = p.parents[2]/'objects'
            def blob(h):
                return (objects/h[:2]/h).read_text()
            index = json.loads(blob(state['last_index']))
            answer = blob(index['answer.txt'][0]) if 'answer.txt' in index else None
            row['archived_answer_value'] = answer
            row['archived_answer_in_shell_output'] = answer_overlap(steps, answer)
        rows.append(row)
        result = json.loads((base/'result.json').read_text())
        assert result['verifier_result']['rewards']['reward'] == row['reward']
    assert sum(r['arm'] == 'C' for r in rows) == 119
    assert sum(r['reward'] == 0 for r in rows if r['arm'] == 'C') == 16
    assert len({r['trial_id'] for r in rows}) == len(rows)
    (ROOT/'receipt_rows.jsonl').write_text(''.join(json.dumps(r, ensure_ascii=False)+'\n' for r in rows))
    print('Rows:', collections.Counter(r['arm'] for r in rows), 'missing trajectories:', missing)
    return rows


def table(title, rows, features):
    nfail = sum(r['reward'] == 0 for r in rows)
    print(f'\n## {title}: n={len(rows)}, fail={nfail}/{len(rows)} ({nfail/len(rows):.1%})')
    print('|Feature|Pass present/known|Fail present/known|present: fail,pass → P(fail)|absent: fail,pass → P(fail)|')
    print('|---|---:|---:|---:|---:|')
    for label, fn in features:
        bins = collections.Counter((r['reward'] == 0, fn(r)) for r in rows if fn(r) is not None)
        fp, pp, fa, pa = [bins[k] for k in [(True, True), (False, True), (True, False), (False, False)]]
        def rate(a,b):
            return f'{a}/{b} ({a/b:.1%})' if b else 'NA'
        print(f'|{label}|{rate(pp, pp+pa)}|{rate(fp, fp+fa)}|{fp},{pp} → {rate(fp,fp+pp)}|{fa},{pa} → {rate(fa,fa+pa)}|')


def main():
    rows = build()
    c = [r for r in rows if r['arm'] == 'C']
    a = [r for r in rows if r['arm'] == 'A']
    receipt = [
        ('Any unverified', lambda r: r['n_unverified'] > 0),
        ('Unopened given files', lambda r: r['has_unopened_given_files']),
        ('All given files opened', lambda r: r['frac_given_files_opened'] == 1),
        ('Any findings', lambda r: r['had_findings']),
        ('Any fixed', lambda r: r['any_fixed']),
        ('In progress', lambda r: r['in_progress']),
        ('Any checked value', lambda r: r['checked_count'] > 0),
        ('Any traced value', lambda r: r['traced_count'] > 0),
        ('Any derived value', lambda r: r['derived_count'] > 0),
        ('Every checked value traced [checked>0]', lambda r: r['traced_count'] == r['checked_count'] if r['checked_count'] else None),
        ('Any script-written untraced value', lambda r: r['not_typed_count'] > 0),
        ('Any feedback round', lambda r: r['feedback_rounds'] > 0),
        ('Multiple Stop reviews', lambda r: r['stop_review_rounds'] > 1),
    ]
    proxy = [
        ('Has final response', lambda r: r['has_final_response']),
        ('Final response has numbers', lambda r: bool(r['final_numeric_tokens'])),
        ('Any final number in tool output [numeric only]', lambda r: r['any_final_number_in_tool_output']),
        ('All final numbers in tool output [numeric only]', lambda r: r['all_final_numbers_in_tool_output']),
        ('Any final number in nontrivial shell output [numeric only]', lambda r: r['any_final_number_in_nontrivial_shell_output']),
        ('Proxy unopened given files', lambda r: r['trajectory_has_unopened_given_files']),
        ('Any tool error', lambda r: r['trajectory_had_tool_error']),
    ]
    table('C receipts', c, receipt)
    table('C trajectory proxies', c, proxy)
    table('Actual archived C answer overlap (not a causal proof)', c, [
        ('Answer value in non-answer-file shell output', lambda r: r['archived_answer_in_shell_output'])])
    table('A explicit write answer overlap (subset; may not be final artifact)', a, [
        ('Last explicit answer write value in shell output', lambda r: r['explicit_answer_in_shell_output'])])
    table('A all trajectories', a, proxy)
    table('A final responses only', [r for r in a if r['has_final_response']], proxy)
    table('C completed receipts only', [r for r in c if not r['in_progress']], receipt[:3]+receipt[6:9])
    print('\nContinuous feature means (pass, fail):')
    for k in ['n_unverified','frac_given_files_opened','checked_count','traced_count','derived_count','feedback_rounds','stop_review_rounds']:
        print(k, {out: round(sum(r[k] for r in c if r['reward'] == out)/sum(r['reward'] == out for r in c), 4) for out in [1,0]})
    for model in ['g4', 'q38']:
        table('C model '+model, [r for r in c if r['model'] == model], receipt[:3]+receipt[6:9])
    print('\nReceipt round distributions:', {k: dict(collections.Counter(r[k] for r in c)) for k in ['feedback_rounds', 'stop_review_rounds']})
    print('C in-progress trials:', [(r['trial_id'], r['reward']) for r in c if r['in_progress']])
    for arm in ['C', 'A']:
        subset = [r for r in rows if r['arm'] == arm]
        print(arm, 'trajectory opened-file lower bound distribution:', dict(collections.Counter(len(r['trajectory_opened_given_files']) for r in subset)))


if __name__ == '__main__':
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        main()
    report = output.getvalue()
    (ROOT/'receipt_analysis.md').write_text(report)
    print(report, end='')
