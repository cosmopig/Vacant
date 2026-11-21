"""展場小型研究材料：依 20260925 零設定評測裁決，僅匯出真實歸檔短摘錄。"""

import contextlib
import io
import json
import random
import re
from pathlib import Path

if __package__:
    from . import analyze_receipts as archive
    from . import claims
else:
    import analyze_receipts as archive
    import claims

SEED = 20260925
OUT = Path(__file__).parent / 'app/cases.js'
MANUAL = {
    'dabstep-21__5p3Vq2a': '人工核對：訊息寫 138,336 筆；各商戶輸出加總為 138,236 筆。這個筆數衝突不等於答案本身錯誤。',
    'dabstep-66__Vv7edGs': '人工核對：只有一道比較用 Python 指令；未見第二道獨立核對。約數 54.7／56.6 本身有輸出支持。',
}


def select_rows():
    with contextlib.redirect_stdout(io.StringIO()):
        rows = archive.build()
    eligible = [r for r in rows if r['arm'] == 'C' and not r['in_progress']
                and r.get('archived_answer_value', '').strip() and r['final_message'].strip()]
    rng = random.Random(SEED)
    chosen = []
    used_tasks = set()
    for reward in (0, 1):
        pool = sorted([r for r in eligible if r['reward'] == reward], key=lambda r: r['trial_id'])
        rng.shuffle(pool)
        pool.sort(key=lambda r: r['trial_id'] not in MANUAL)
        group = []
        for preferred in [r for r in pool if r['trial_id'] in MANUAL]:
            if preferred['task'] not in used_tasks:
                group.append(preferred)
                used_tasks.add(preferred['task'])
        for model in sorted({r['model'] for r in pool}):
            if not any(r['model'] == model for r in group):
                pick = next(r for r in pool if r['model'] == model and r['task'] not in used_tasks)
                group.append(pick)
                used_tasks.add(pick['task'])
        for r in pool:
            if len(group) == 6:
                break
            if r['task'] not in used_tasks:
                group.append(r)
                used_tasks.add(r['task'])
        assert len(group) == 6
        chosen.extend(group)
    rng.shuffle(chosen)
    return chosen


def build():
    cases = []
    for row in select_rows():
        trial = archive.CACHE / 'formal/jobs' / row['job'] / row['trial_id']
        steps = json.loads((trial / 'agent/trajectory.json').read_text())['steps']
        final = [s for s in steps if s.get('source') == 'agent' and s.get('message') and not s.get('tool_calls')][-1]
        before = steps[:steps.index(final)]
        answer = row['archived_answer_value'].strip()
        source = next((i + 1 for i, s in enumerate(before) if archive.answer_overlap([s], answer)), None)
        timeline = []
        for i, step in enumerate(before):
            calls = {c['tool_call_id']: c for c in step.get('tool_calls', [])}
            for obs in (step.get('observation') or {}).get('results', []):
                c = calls.get(obs.get('source_call_id'), {})
                tool, args = c.get('function_name', 'unknown'), c.get('arguments') or {}
                command = str(args.get('command', args.get('path', '')))
                output = str(obs.get('content') or '')
                pos = output.lower().find(answer.lower()) if i + 1 == source else -1
                start = max(0, pos - 65) if pos >= 0 else 0
                read = []
                if tool == 'read':
                    read = [str(args.get('path', ''))]
                elif tool == 'bash' and claims.READ_COMMAND.search(command):
                    read = sorted(set(claims.FILE.findall(command)))
                timeline.append(dict(step=i + 1, tool=tool, command=command[:200],
                                     output=output[start:start + 300], files_read=read,
                                     error=bool((obs.get('extra') or {}).get('is_error'))))
        prompt = next(s['message'] for s in steps if s.get('source') == 'user')
        match = re.search(r'Here is the question you need to answer:\s*(.*?)\n\n', prompt, re.S)
        question = match[1] if match else prompt[:600]
        audit = claims.audit_run(dict(row, dataset='formal'), steps, answer)
        process = [dict(text=c['text'][:400], kind=c['kind'], status=c['status'],
                        reason=c['reason'], steps=[s + 1 for s in c['evidence_steps']])
                   for c in audit['claims'][:4]]
        note = next((trial / 'agent').rglob('delivery.md')).read_text().splitlines()
        cases.append(dict(id=row['trial_id'], task=row['task'], model=row['model'],
                          question=question, message=row['final_message'], answer=answer,
                          steps=timeline, delivery_lines=note, answer_source=source,
                          process_claims=process, manual_note=MANUAL.get(row['trial_id']),
                          reward=int(row['reward'])))
    return dict(version=2, selection_seed=SEED, source='DABstep / pi / local models / 2026-09-25', cases=cases)


def serialize(data):
    return 'window.RELIANCE_CASES = ' + json.dumps(data, ensure_ascii=False, indent=2) + ';\n'


if __name__ == '__main__':
    output = serialize(build())
    assert len(output.encode()) < 300_000
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(output)
    print(f'CASES 12 (6 wrong / 6 right), {len(output.encode())} bytes -> {OUT}')
