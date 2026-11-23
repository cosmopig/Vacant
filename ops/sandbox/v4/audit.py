"""以 branch/session 配對接收 v3 session-event 掃描輸出；人工裁定才完成兩項稽核。"""
import argparse
from collections import Counter
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
    raw = source.read_bytes()
    source_hash = digest(raw)
    archive = out / 'audit-sources'
    archive.mkdir(exist_ok=True)
    (archive / (source_hash + '.json')).write_bytes(raw)
    try:
        records = json.loads(raw)
        if not isinstance(records, list):
            raise ValueError('audit export must be a list')
    except (ValueError, UnicodeError) as exc:
        result = dict(applied_branches=[], rejected_branches={}, source_sha256=source_hash, export_error=str(exc))
        write_json(out / 'audit-ingestion.json', result)
        return result
    verdicts = json.loads((out / 'contamination.json').read_text())
    applied, rejected, cells = [], {}, {}
    for path in (out / 'cells').glob('*/result.json'):
        try:
            cell = json.loads(path.read_text())
            cells[cell['branch']] = cell
        except (ValueError, UnicodeError, KeyError, TypeError):
            continue
    counts = Counter(row.get('branch') for row in records if isinstance(row, dict) and isinstance(row.get('branch'), str))
    for index, row in enumerate(records):
        branch = row.get('branch') if isinstance(row, dict) else None
        try:
            if branch not in meta['expected_branches'] or meta['sessions'].get(branch) != row.get('session_id'):
                raise ValueError('audit export branch/session mismatch')
            if counts[branch] != 1:
                raise ValueError('duplicate audit records')
            if branch not in cells:
                raise ValueError('awaiting scored delivery')
            flags = [row.get(key) for key in ('contaminated', 'outside_help')]
            if any(value is not None and type(value) is not bool for value in flags):
                raise ValueError('audit verdicts must be true, false or null')
            if not any(type(value) is bool for value in flags):
                continue
            if row.get('handback_sha') != cells[branch]['git_sha']:
                raise ValueError('stale audit SHA; pending re-audit of current delivery')
            if (not row.get('reviewer') or row.get('access_audit_complete') is not True
                    or row.get('outside_help_audit_complete') is not True
                    or not row.get('final_push_evidence') or not row.get('pr_review_evidence')):
                raise ValueError('completed audits need reviewer, scored SHA, final-push and PR/review evidence')
            for key in ('evidence', 'outside_help_evidence'):
                if not isinstance(row.get(key), list) or not row[key]:
                    raise ValueError('nonempty evidence lists required for both audits')
            verdicts[branch].update({key: row[key] for key in ('contaminated', 'outside_help', 'reviewer',
                                                              'handback_sha', 'session_id', 'evidence', 'outside_help_evidence')})
            verdicts[branch]['outside_help_evidence'] += [row['final_push_evidence'], row['pr_review_evidence']]
            verdicts[branch]['audit_source_sha256'] = source_hash
            applied.append(branch)
        except (ValueError, TypeError, KeyError) as exc:
            rejected[branch if isinstance(branch, str) else f'record-{index}'] = str(exc)
    write_json(out / 'contamination.json', verdicts)
    result = dict(applied_branches=applied, rejected_branches=rejected, source_sha256=source_hash)
    write_json(out / 'audit-ingestion.json', result)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--export', type=Path, required=True)
    args = parser.parse_args(argv)
    print(json.dumps(ingest(args.out, args.export), indent=2))


if __name__ == '__main__':
    main()
