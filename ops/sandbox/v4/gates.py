"""沿用 v3 回覆解析器；A/B/C 是回覆所報，不冒充獨立 receipt 驗證。"""
import importlib.util
import json
from pathlib import Path
import re

from ops.sandbox.v3.select import digest


LEGACY = Path(__file__).resolve().parents[1] / 'v3/results/devin-v3-cmp-20261123/parse_gates.py'
SPEC = importlib.util.spec_from_file_location('sandbox_v3_gate_parser', LEGACY)
V3 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(V3)
UNKNOWN = V3.UNKNOWN


def parse_cell(row):
    result = V3.parse_cell(row)
    for submission in result['submissions']:
        steps = {step: UNKNOWN for step in 'ABC'}
        basis = UNKNOWN
        failures = set(re.findall(r'\bStep ([ABC]) refused\b', submission['excerpt']))
        if (submission['verdict'] == 'accepted' and submission['exit_code'] in (0, UNKNOWN)
                and '（visible_pass）' in submission['raw_verdict_line'] and not failures):
            steps = dict.fromkeys('ABC', 'pass')
            basis = 'Inferred from reported v4 gate acceptance; not independent step receipts.'
        elif submission['verdict'] == 'refused' and submission['exit_code'] in (20, UNKNOWN) and len(failures) == 1:
            failed = next(iter(failures))
            steps = {step: 'pass' if step < failed else 'fail' if step == failed else 'not_run' for step in 'ABC'}
            basis = 'Reported refusal step; earlier passes inferred from sequential v4 gate.'
        submission.update(steps=steps, step_verdict_basis=basis)
    return result


def parse_export(path, scored, sessions):
    raw = Path(path).read_bytes()
    rows = json.loads(raw)
    if len({r['branch'] for r in rows}) != len(rows):
        raise ValueError('duplicate gate-export branch')
    cells = {r['branch']: r for r in scored}
    parsed = []
    for row in rows:
        if sessions.get(row['branch']) != row['session_id']:
            raise ValueError('gate evidence session mismatch')
        item = parse_cell(row)
        cell = cells.get(row['branch'], {})
        item.update(manifest_present=cell.get('manifest_present', UNKNOWN),
                    manifest_handback_sha=cell.get('git_sha', UNKNOWN))
        parsed.append(item)
    return dict(source_sha256=digest(raw), cells=parsed,
                measurement='Reply-reported stdout; step inference is labeled. Manifest presence is measured in the scored Git tree.',
                receipt_verification=UNKNOWN, actual_total_executions=UNKNOWN)
