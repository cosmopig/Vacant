"""以 branch/session 配對接收 v3 session-event 掃描輸出；人工裁定才完成兩項稽核。"""
import argparse
import json
from pathlib import Path

from ops.sandbox.v3.select import digest
from ops.sandbox.v4.state import run_lock, write_json


def ingest(out, source):
    with run_lock(out):
        return _ingest(out, source)


def _ingest(out, source):
    out, source = Path(out), Path(source)
    meta = json.loads((out / 'meta.json').read_text())
    records = json.loads(source.read_text())
    if not isinstance(records, list) or len({r['branch'] for r in records}) != len(records):
        raise ValueError('audit export must contain distinct branch records')
    verdicts = json.loads((out / 'contamination.json').read_text())
    applied = []
    cells = {r['branch']: r for r in (json.loads(p.read_text()) for p in (out / 'cells').glob('*/result.json'))}
    for row in records:
        branch = row['branch']
        if branch not in meta['expected_branches'] or meta['sessions'].get(branch) != row['session_id']:
            raise ValueError('audit export branch/session mismatch')
        if branch not in cells:
            continue
        flags = [row.get(key) for key in ('contaminated', 'outside_help')]
        if any(value is not None and type(value) is not bool for value in flags):
            raise ValueError('audit verdicts must be true, false or null')
        if not any(type(value) is bool for value in flags):
            continue
        if (row.get('handback_sha') != cells[branch]['git_sha'] or not row.get('reviewer')
                or row.get('access_audit_complete') is not True or row.get('outside_help_audit_complete') is not True
                or not row.get('final_push_evidence') or not row.get('pr_review_evidence')):
            raise ValueError('completed audits need reviewer, scored SHA, final-push and PR/review evidence')
        for key in ('evidence', 'outside_help_evidence'):
            if not isinstance(row.get(key), list) or not row[key]:
                raise ValueError('nonempty evidence lists required for both audits')
        verdicts[branch].update({key: row[key] for key in ('contaminated', 'outside_help', 'reviewer',
                                                          'handback_sha', 'session_id', 'evidence', 'outside_help_evidence')})
        verdicts[branch]['outside_help_evidence'] += [row['final_push_evidence'], row['pr_review_evidence']]
        verdicts[branch]['audit_source_sha256'] = digest(source.read_bytes())
        applied.append(branch)
    archive = out / 'audit-sources'
    archive.mkdir(exist_ok=True)
    (archive / (digest(source.read_bytes()) + '.json')).write_bytes(source.read_bytes())
    write_json(out / 'contamination.json', verdicts)
    return dict(applied_branches=applied, source_sha256=digest(source.read_bytes()))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--export', type=Path, required=True)
    args = parser.parse_args(argv)
    print(json.dumps(ingest(args.out, args.export), indent=2))


if __name__ == '__main__':
    main()
