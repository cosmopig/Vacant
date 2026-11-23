"""v4 分支輪詢與獨立官方計分；重用 v3 匯出、harness、審核與配對量尺。"""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import re
import shutil
import time

from ops.sandbox import analyze
from ops.sandbox.v3 import score as v3
from ops.sandbox.v3.select import DATASET_CONTENT_SHA256, HARNESS_VERSION, canonical, digest
from ops.sandbox.v4 import audit, gates, images, patch
from ops.sandbox.v4.state import run_lock, write_json


HERE = Path(__file__).resolve().parent


def parse_branch(branch):
    match = re.fullmatch(r'sandbox-devin-cal4/(.+)-(plain)', branch)
    if match:
        return 'calibration', match[1], match[2], 1
    match = re.fullmatch(r'sandbox-devin/v4/(.+)-(plain2|plain|vacant)-s([12])', branch)
    if match:
        return 'comparison', match[1], match[2], int(match[3])
    raise ValueError('invalid v4 handback branch: ' + branch)


def schedule(selection, protocol):
    ids, calibration = selection['final_instance_ids'], selection['calibration_instance_ids']
    if len(ids) != 62 or len(set(ids)) != 62 or len(calibration) != 12 or len(set(calibration)) != 12 or not set(calibration) <= set(ids):
        raise ValueError('v4 requires the frozen 62-instance bank and its twelve-instance calibration subset')
    if any(not re.fullmatch(r'[A-Za-z0-9_.-]+', task) or task in ('.', '..') for task in ids):
        raise ValueError('unsafe instance ID')
    if protocol == 'calibration':
        return [f'sandbox-devin-cal4/{task}-plain' for task in calibration]
    if protocol == 'comparison':
        return [f'sandbox-devin/v4/{task}-{arm}-s{s}' for task in ids for arm in v3.ARMS for s in (1, 2)]
    raise ValueError('invalid protocol')


def session_map(path, expected):
    data = json.loads(Path(path).read_text())
    if not isinstance(data, dict) or not all(isinstance(k, str) and isinstance(v, str) and v for k, v in data.items()):
        raise ValueError('sessions must map branch names (or calibration instance IDs) to session IDs')
    result = {(k if k.startswith('sandbox-') else f'sandbox-devin-cal4/{k}-plain'): v for k, v in data.items()}
    if len(result) != len(data) or not set(result) <= set(expected) or len(set(result.values())) != len(result):
        raise ValueError('unexpected branch or duplicate session ID')
    return result


def validate_sessions(sessions, expected):
    if (not isinstance(sessions, dict) or not set(sessions) <= set(expected)
            or not all(isinstance(s, str) and s for s in sessions.values())):
        raise ValueError('invalid session map')
    if len(set(sessions.values())) != len(sessions):
        raise ValueError('duplicate session ID bound to multiple branches')


def slot(session=None, sha=None):
    return dict(contaminated=None, outside_help=None, evidence=[], outside_help_evidence=[],
                reviewer=None, session_id=session, handback_sha=sha)


def cell_path(out, branch):
    protocol, task, external_arm, sample = parse_branch(branch)
    arm = 'calibration-plain' if protocol == 'calibration' else v3.ARMS[external_arm]
    return Path(out) / 'cells' / f'{task}-s{sample}-{arm}'


def official_runner(python, timeout):
    def run(instance, candidate, image, cell):
        images.ensure_image(image)
        attempt, delay = 0, 900
        while True:
            attempt += 1
            directory = cell / 'attempts' / str(attempt)
            directory.mkdir(parents=True)
            outcome = v3.call_harness(instance, candidate, image, directory, python, timeout)
            logs = '\n'.join(p.read_text(errors='replace')[-100000:] for p in directory.rglob('*.log'))
            if not outcome.get('infra_void') or not images.retryable(str(outcome.get('error')) + logs):
                return outcome
            images.log(f'{instance["instance_id"]}: retrying SAME candidate in {delay}s; infrastructure pull error')
            time.sleep(delay)
            delay = min(delay * 2, 3600)
    return run


def review(out):
    with run_lock(out):
        return _review(out)


def _review(out):
    out = Path(out)
    meta = json.loads((out / 'meta.json').read_text())
    if meta.get('version') != 4:
        raise ValueError('not a v4 run')
    if meta['protocol'] == 'calibration' and meta.get('calibration'):
        meta['calibration'].update(complete=False, proceed=False, decision='incomplete')
        write_json(out / 'calibration.json', meta['calibration'])
    validate_sessions(meta['sessions'], meta['expected_branches'])
    verdicts = json.loads((out / 'contamination.json').read_text())
    for branch in meta.get('changed_branches', []):
        cell = cell_path(out, branch)
        if cell.exists():
            archive = out / 'superseded' / f'{cell.name}-{time.time_ns()}'
            archive.parent.mkdir(exist_ok=True)
            shutil.move(str(cell), archive)
            write_json(archive / 'audit.json', verdicts[branch])
        verdicts[branch] = slot(meta['sessions'].get(branch))
    write_json(out / 'contamination.json', verdicts)
    rows = []
    for path in sorted((out / 'cells').glob('*/result.json')):
        try:
            row = json.loads(path.read_text())
        except (ValueError, UnicodeError):
            row = None
        required = {'branch', 'git_sha', 'task', 'sample', 'arm', 'resolved', 'infra_void', 'gold_similarity', 'manifest_present'}
        if not isinstance(row, dict) or not required <= row.keys():
            archive = out / 'unreadable' / f'{path.parent.name}-{time.time_ns()}'
            archive.parent.mkdir(exist_ok=True)
            shutil.move(str(path.parent), archive)
            branch = next((b for b in meta['expected_branches'] if cell_path(out, b) == path.parent), None)
            if branch:
                write_json(archive / 'audit.json', verdicts[branch])
                verdicts[branch] = slot(meta['sessions'].get(branch))
            continue
        rows.append(row)
    write_json(out / 'contamination.json', verdicts)
    branches = [r['branch'] for r in rows]
    if len(set(branches)) != len(branches) or not set(branches) <= set(meta['expected_branches']):
        raise ValueError('duplicate or unscheduled scored cells')
    for row in rows:
        verdict = verdicts[row['branch']]
        flags = [verdict.get(k) for k in ('contaminated', 'outside_help')]
        invalid = (any(value is not None and type(value) is not bool for value in flags)
                   or not all(isinstance(verdict.get(k), list) for k in ('evidence', 'outside_help_evidence')))
        mismatched = (any(value is not None for value in flags) and
                      (not verdict.get('reviewer') or not row.get('session_id')
                       or verdict.get('session_id') != row['session_id'] or verdict.get('handback_sha') != row['git_sha']
                       or meta['sessions'].get(row['branch']) != row['session_id']))
        if invalid or mismatched:
            verdicts[row['branch']] = {**slot(row.get('session_id'), row['git_sha']),
                                      'pending_reason': 'invalid or stale audit binding; pending re-audit'}
    write_json(out / 'contamination.json', verdicts)
    meta['missing_branches'] = [b for b in meta['expected_branches'] if b not in branches
                                or b in meta.get('changed_branches', []) or b in meta.get('poll_errors', {})]
    write_json(out / 'meta.json', meta)
    meta = v3.review(out, version=4)
    if meta.get('changed_branches') and meta['protocol'] == 'calibration':
        meta['calibration'].update(complete=False, proceed=False, decision='incomplete')
        write_json(out / 'calibration.json', meta['calibration'])
    for name, directory in meta.get('analysis_views', {}).items():
        summary = analyze.analyze(directory)
        summary['analysis_complete'] = not meta['missing_branches'] and not meta['unreviewed_branches'] and not meta['control_only'] and not meta.get('changed_branches')
        for comparison in summary['comparisons'].values():
            comparison['preregistered_result'] = comparison['decision'] if summary['analysis_complete'] else 'incomplete'
            comparison['largest_gain_not_ruled_out'] = comparison['ci95'][1] if comparison['ci95'] and comparison['decision'] != 'gain' else None
            if not summary['analysis_complete']:
                comparison['decision'] = 'incomplete'
        write_json(Path(directory) / 'summary.json', summary)
        if not summary['analysis_complete']:
            markdown = Path(directory) / 'summary.md'
            markdown.write_text('**Provisional: scheduled outcomes or audits are incomplete.**\n\n' + markdown.read_text())
        write_json(out / f'analysis-{name}.json', summary)
    write_json(out / 'meta.json', meta)
    secondary = dict(gold_similarity_threshold=.9,
                     gold_similarity_flags=[r['branch'] for r in rows if r['gold_similarity'] and r['gold_similarity']['flagged']],
                     gold_similarity_unmeasured=[r['branch'] for r in rows if r['gold_similarity'] is None],
                     manifest_presence={r['branch']: r['manifest_present'] for r in rows},
                     agent_costs=v3.UNKNOWN, receipt_verification=v3.UNKNOWN)
    if (out / 'gate-export.json').is_file():
        evidence = gates.parse_export(out / 'gate-export.json', rows, meta['sessions'])
        write_json(out / 'gate-evidence.json', evidence)
        secondary['vacant_gate'] = evidence
    write_json(out / 'secondary.json', secondary)
    return meta


def collect(repo, remote, out, instances, selection, manifest, *, protocol, sessions=None,
            runner=None, harness_python=None, timeout=1800, control_only=False):
    repo, out = Path(repo).resolve(), Path(out).resolve()
    if out == repo or repo in out.parents or out == v3.REPO or v3.REPO in out.parents:
        raise ValueError('results must be outside the repository')
    expected = schedule(selection, protocol)
    sessions = {} if sessions is None else sessions
    validate_sessions(sessions, expected)
    if timeout <= 0:
        raise ValueError('timeout must be positive')
    if runner is None:
        if harness_python is None:
            raise ValueError('harness Python is required')
        runner = official_runner(harness_python, timeout)
    instances_by_id = {r['instance_id']: r for r in instances}
    scorer_revision = v3.git(v3.REPO, 'rev-parse', 'HEAD')
    ids = selection['calibration_instance_ids'] if protocol == 'calibration' else selection['final_instance_ids']
    records = {}
    for task in ids:
        case = manifest['cases'][task]
        record = {**case['snapshot'], 'selection': deepcopy(case['selection'])}
        if case['status'] != 'ready' or record['base_commit'] != instances_by_id[task]['base_commit']:
            raise ValueError('unready instance or bank base mismatch: ' + task)
        record['selection']['measurement']['image_digest'] = images.image_for(selection, task)
        records[task] = record
    fingerprints = dict(selection=digest(canonical(selection)), manifest=digest(canonical(manifest)),
                        dataset=digest(canonical(instances)))
    out.mkdir(parents=True, exist_ok=True)
    with run_lock(out):
        if (out / 'meta.json').exists():
            meta = json.loads((out / 'meta.json').read_text())
            if (meta.get('version') != 4 or meta['protocol'] != protocol or meta['fingerprints'] != fingerprints
                    or meta['remote'] != str(remote) or meta['control_only'] != control_only
                    or meta['harness_timeout_s'] != timeout or meta['expected_branches'] != expected):
                raise ValueError('resume inputs differ from frozen scoring run')
        else:
            if any(p.name not in ('.score.lock', 'NOTES.md', 'SESSIONS.txt') for p in out.iterdir()):
                raise ValueError('unrecognized existing output directory')
            meta = dict(version=4, protocol=protocol, evidence='v4-harness-control' if control_only else 'external-devin-v4',
                        calibration_only=protocol == 'calibration', control_only=control_only,
                        task_ids=ids, expected_branches=expected, remote=str(remote), fingerprints=fingerprints,
                        git_sha=v3.git(v3.REPO, 'rev-parse', 'HEAD'), harness_version=HARNESS_VERSION,
                        harness_timeout_s=timeout, sessions={},
                        config=dict(arms=['calibration-plain'] if protocol == 'calibration' else list(v3.ARMS.values()),
                                    tasks=['all'], samples=1 if protocol == 'calibration' else 2, seed=20261122),
                        implementation_sha256={str(p.relative_to(HERE.parent.parent)): digest(p.read_bytes()) for p in
                                               [Path(v3.__file__), Path(v3.__file__).with_name('harness.py'),
                                                HERE / 'score.py', HERE / 'patch.py', HERE / 'images.py', HERE / 'gates.py',
                                                HERE / 'audit.py', HERE / 'state.py', Path(analyze.__file__), gates.LEGACY]})
            write_json(out / 'meta.json', meta)
            write_json(out / 'contamination.json', {b: slot() for b in expected})
        for branch, session in sessions.items():
            if branch in meta['sessions'] and meta['sessions'][branch] != session:
                raise ValueError('cannot replace a bound session ID')
        validate_sessions({**meta['sessions'], **sessions}, expected)
        meta['sessions'].update(sessions)
        (out / 'cells').mkdir(exist_ok=True)
        meta.setdefault('changed_branches', [])
        meta.setdefault('poll_errors', {})
        write_json(out / 'meta.json', meta)
        meta = _review(out)
        for branch in expected:
            _, task, external_arm, sample = parse_branch(branch)
            arm = 'calibration-plain' if protocol == 'calibration' else v3.ARMS[external_arm]
            cell = cell_path(out, branch)
            try:
                sha = v3.fetch(repo, remote, branch)
            except Exception as exc:
                meta['poll_errors'][branch] = f'{type(exc).__name__}: {exc}'
                write_json(out / 'meta.json', meta)
                meta = _review(out)
                continue
            meta['poll_errors'].pop(branch, None)
            if (cell / 'result.json').exists():
                result = json.loads((cell / 'result.json').read_text())
                if result['git_sha'] != sha:
                    meta['changed_branches'].append(branch)
                    write_json(out / 'meta.json', meta)
                    meta = _review(out)
                elif not result.get('session_id') and branch in meta['sessions']:
                    result['session_id'] = meta['sessions'][branch]
                    write_json(cell / 'result.json', result)
                    continue
                else:
                    continue
            if sha is None:
                continue
            if cell.exists():
                recovery = out / 'interrupted' / f'{cell.name}-{time.time_ns()}'
                recovery.parent.mkdir(exist_ok=True)
                shutil.move(str(cell), recovery)
            cell.mkdir()
            images.log('Scoring ' + branch + ' @ ' + sha)
            try:
                result = v3.score_handback(repo, remote, sha, instances_by_id[task], records[task], cell, runner,
                                           base_prefix='sandbox-v4/', patch_deriver=patch.derive_patch,
                                           allow_unchanged_gitlinks=True)
            except Exception as exc:
                result = dict(resolved=False, infra_void=True, error=f'{type(exc).__name__}: {exc}',
                              error_stage='score_preparation', patch_applied=None, gold_similarity=None,
                              base_sha=records[task]['sha'], base_tree=records[task]['base_tree'],
                              patch_sha256=None, patch_bytes=None, harness_wall_s=None,
                              image_digest=records[task]['selection']['measurement']['image_digest'],
                              harness_version=HARNESS_VERSION)
                images.log(branch + ': recorded infra_void; continuing other cells: ' + result['error'])
            root_manifest = cell / 'handback' / 'VACANT_TESTS.txt'
            result.update(task=task, sample=sample, arm=arm, external_arm='devin-' + external_arm,
                          branch=branch, git_sha=sha, evidence=meta['evidence'], protocol=protocol,
                          scorer_git_sha=scorer_revision,
                          session_id=meta['sessions'].get(branch), calls_complete=False,
                          manifest_present=root_manifest.exists() or root_manifest.is_symlink(),
                          **{k: v3.UNKNOWN for k in ('model_calls', 'prompt_tokens', 'completion_tokens', 'wall_s',
                                                     'vacant_feedback_rounds', 'vacant_home_bytes', 'trace_bytes')})
            write_json(cell / 'result.json', result)
            verdicts = json.loads((out / 'contamination.json').read_text())
            verdicts[branch] = slot(result['session_id'], sha)
            write_json(out / 'contamination.json', verdicts)
            meta['changed_branches'] = [b for b in meta['changed_branches'] if b != branch]
            write_json(out / 'meta.json', meta)
            if protocol == 'calibration':
                _review(out)
        verdicts = json.loads((out / 'contamination.json').read_text())
        for branch in expected:
            verdicts[branch]['session_id'] = meta['sessions'].get(branch)
        write_json(out / 'contamination.json', verdicts)
        write_json(out / 'meta.json', meta)
        return _review(out)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('score', 'watch', 'review'))
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--protocol', choices=('calibration', 'comparison'), default='calibration')
    parser.add_argument('--repo', type=Path, default=v3.REPO)
    parser.add_argument('--remote', default='origin')
    parser.add_argument('--dataset-json', type=Path)
    parser.add_argument('--harness-python', type=Path)
    parser.add_argument('--sessions', type=Path)
    parser.add_argument('--audit-export', type=Path)
    parser.add_argument('--poll-seconds', type=float, default=300)
    parser.add_argument('--timeout', type=int, default=1800)
    parser.add_argument('--control-only', action='store_true')
    args = parser.parse_args(argv)
    if args.command == 'review':
        return review(args.out)
    if args.dataset_json is None or args.harness_python is None or args.poll_seconds <= 0:
        parser.error('dataset, harness Python and positive polling interval required')
    instances = [json.loads(line) for line in args.dataset_json.read_text().splitlines() if line.strip()]
    if digest(canonical(instances)) != DATASET_CONTENT_SHA256:
        raise ValueError('dataset fingerprint mismatch')
    selection = json.loads((HERE / 'SELECTION.json').read_text())
    manifest = json.loads((HERE / 'KIT.json').read_text())
    while True:
        sessions = session_map(args.sessions, schedule(selection, args.protocol)) if args.sessions else {}
        meta = collect(args.repo, args.remote, args.out, instances, selection, manifest, protocol=args.protocol,
                       sessions=sessions, harness_python=args.harness_python.absolute(), timeout=args.timeout,
                       control_only=args.control_only)
        if args.audit_export and args.audit_export.is_file():
            audit.ingest(args.out, args.audit_export)
            meta = review(args.out)
        images.log(json.dumps({k: meta[k] for k in ('missing_branches', 'unreviewed_branches', 'changed_branches', 'calibration') if k in meta}))
        complete = not meta['missing_branches'] and not meta['unreviewed_branches'] and not meta['changed_branches']
        if args.command == 'score' or complete:
            return meta
        time.sleep(args.poll_seconds)


if __name__ == '__main__':
    main()
