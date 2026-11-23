"""Collect frozen v3 handbacks and score them independently with SWE-bench."""
import argparse
from difflib import SequenceMatcher
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import tempfile
import time
import uuid

from ops.sandbox.score_devin import ARMS, REPO, UNKNOWN, fetch, git
from ops.sandbox.v3.patch import derive_patch
from ops.sandbox.v3.select import DATASET_CONTENT_SHA256, HARNESS_VERSION, canonical, digest

HERE = Path(__file__).resolve().parent


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def parse_branch(branch):
    match = re.fullmatch(r'sandbox-devin-cal3/(.+)-(plain)', branch)
    if match:
        return 'calibration', match[1], match[2], 1
    match = re.fullmatch(r'sandbox-devin/v3/(.+)-(plain2|plain|vacant)-s([12])', branch)
    if match:
        return 'comparison', match[1], match[2], int(match[3])
    raise ValueError('invalid v3 handback branch: ' + branch)


def export_tree(repo, sha, target):
    target.mkdir()
    records = subprocess.check_output(['git', '--no-replace-objects', '-C', str(repo),
                                       'ls-tree', '-rz', sha]).split(b'\0')
    entries = []
    for record in filter(None, records):
        header, raw_name = record.split(b'\t', 1)
        mode, kind, oid = header.split()
        name = os.fsdecode(raw_name)
        parts = PurePosixPath(name).parts
        if (kind != b'blob' or mode not in (b'100644', b'100755', b'120000')
                or not parts or name.startswith('/') or '\\' in name
                or any(p in ('.', '..') or p.lower() == '.git' for p in parts)):
            raise ValueError('unsupported or unsafe Git tree entry: ' + name)
        entries.append((mode, oid, name))
    objects = list(dict.fromkeys(oid for _, oid, _ in entries))
    data = subprocess.check_output(['git', '--no-replace-objects', '-C', str(repo), 'cat-file', '--batch'],
                                   input=b''.join(oid+b'\n' for oid in objects))
    blobs, offset = {}, 0
    for oid in objects:
        end = data.index(b'\n', offset)
        found, kind, size = data[offset:end].split()
        if found != oid or kind != b'blob':
            raise ValueError('invalid Git object response')
        offset = end + 1
        blobs[oid] = data[offset:offset+int(size)]
        offset += int(size) + 1
    for mode, oid, name in sorted(entries, key=lambda entry: entry[0] == b'120000'):
        path = target / name
        if any(parent.is_symlink() for parent in path.parents):
            raise ValueError('symlink parent in export: ' + name)
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() or path.is_symlink():
            raise ValueError('colliding Git paths: ' + name)
        if mode == b'120000':
            path.symlink_to(os.fsdecode(blobs[oid]))
        else:
            path.write_bytes(blobs[oid])
            path.chmod(0o755 if mode == b'100755' else 0o644)


def normalized_lines(patch):
    lines = []
    in_hunk = False
    for line in patch.decode('utf-8', errors='replace').split('\n'):
        if line.startswith('diff --git '):
            in_hunk = False
        elif line.startswith('@@ '):
            in_hunk = True
        elif in_hunk and line.startswith(('+', '-')):
            text = ' '.join(line[1:].split())
            if text:
                lines.append(line[0] + text)
    return lines


def similarity(gold, candidate):
    ratio = SequenceMatcher(None, normalized_lines(gold), normalized_lines(candidate), autojunk=False).ratio()
    return dict(ratio=ratio, flagged=ratio >= .9, threshold=.9)


def call_harness(instance, patch, image_digest, cell, python, timeout):
    work = cell / 'harness'
    work.mkdir()
    request_path, result_path = work / 'request.json', work / 'result.json'
    request = dict(instance=instance, patch_path=str(patch.resolve()), image_digest=image_digest,
                   timeout=timeout, run_id='v3-' + uuid.uuid4().hex)
    write_json(request_path, request)
    command = [str(python), '-I', str(HERE / 'harness.py'), '--request', str(request_path),
               '--out', str(result_path)]
    with (work / 'stdout.log').open('wb') as stdout, (work / 'stderr.log').open('wb') as stderr:
        try:
            subprocess.run(command, cwd=work, stdout=stdout, stderr=stderr,
                           check=True, timeout=timeout+300)
        except subprocess.TimeoutExpired:
            cleanup_path = work / 'cleanup.json'
            try:
                subprocess.run([*command[:-1], str(cleanup_path), '--cleanup'], cwd=work,
                               stdout=stdout, stderr=stderr, check=True, timeout=60)
            except (OSError, subprocess.SubprocessError) as exc:
                stderr.write(f'Cleanup failed: {exc}\n'.encode())
            raise
    result = json.loads(result_path.read_text())
    if (not result.get('infra_void')
            and (result.get('harness_version') != HARNESS_VERSION
                 or result.get('image_digest') != image_digest)):
        raise ValueError('harness identity mismatch')
    return result


def score_handback(repo, remote, sha, instance, record, cell, runner):
    base_branch = 'sandbox-v3/' + instance['instance_id']
    base_sha = fetch(repo, remote, base_branch)
    if (base_sha != record['sha'] or record['base_commit'] != instance['base_commit']
            or git(repo, '--no-replace-objects', 'rev-parse', base_sha+'^{tree}') != record['base_tree']):
        raise ValueError('frozen base mismatch: ' + base_branch)
    base, handback = cell / 'base', cell / 'handback'
    export_tree(repo, base_sha, base)
    export_tree(repo, sha, handback)
    config = record['selection']
    candidate = derive_patch(base, handback, instance['test_patch'], config['environment']['commands'])
    patch = cell / 'candidate.patch'
    patch.write_bytes(candidate)
    with tempfile.TemporaryDirectory(prefix='v3-gold-') as temporary:
        gold = Path(temporary) / 'gold'
        shutil.copytree(base, gold, symlinks=True)
        subprocess.run(['git', 'apply', '--whitespace=nowarn', '-'], cwd=gold,
                       input=instance['patch'].encode(), check=True, capture_output=True)
        gold_patch = derive_patch(base, gold, instance['test_patch'])
    secondary = similarity(gold_patch, candidate)
    started = time.monotonic()
    try:
        outcome = runner(instance, patch, config['measurement']['image_digest'], cell)
        if (type(outcome.get('resolved')) is not bool or type(outcome.get('infra_void')) is not bool
                or (not outcome['infra_void'] and type(outcome.get('patch_applied')) is not bool)
                or (outcome['resolved'] and (outcome['infra_void'] or outcome.get('patch_applied') is not True))):
            raise ValueError('invalid harness outcome')
    except Exception as exc:
        outcome = dict(resolved=False, infra_void=True, patch_applied=None,
                       error=f'{type(exc).__name__}: {exc}')
    write_json(cell / 'harness-result.json', outcome)
    return dict(score=outcome, resolved=outcome['resolved'] and not outcome['infra_void'],
                hidden_pass=outcome['resolved'] and not outcome['infra_void'], visible_pass=None,
                infra_void=outcome['infra_void'], infra_reason=outcome.get('error') if outcome['infra_void'] else None,
                base_sha=base_sha, base_tree=record['base_tree'],
                patch_sha256=digest(candidate), patch_bytes=len(candidate),
                gold_similarity=secondary, harness_wall_s=time.monotonic()-started,
                image_digest=config['measurement']['image_digest'], harness_version=HARNESS_VERSION)


def review(out):
    out = Path(out)
    meta = json.loads((out / 'meta.json').read_text())
    verdicts = json.loads((out / 'contamination.json').read_text())
    if set(verdicts) != set(meta['expected_branches']):
        raise ValueError('contamination slots differ from scheduled branches')
    for slot in verdicts.values():
        if any(slot[key] is not None and type(slot[key]) is not bool for key in ('contaminated', 'outside_help')):
            raise ValueError('contaminated and outside_help must be true, false or null')
        if not all(isinstance(slot.get(key), list) for key in ('evidence', 'outside_help_evidence')):
            raise ValueError('contamination evidence must be a list')
    rows = []
    for path in sorted((out / 'cells').glob('*/result.json')):
        row = json.loads(path.read_text())
        verdict = verdicts[row['branch']]
        flags = [verdict['contaminated'], verdict['outside_help']]
        complete = all(type(value) is bool for value in flags)
        effective = True if any(value is True for value in flags) else False if complete else None
        row.update(contamination=effective, access_contamination=verdict['contaminated'],
                   outside_help=verdict['outside_help'],
                   contamination_evidence=verdict['evidence']+verdict['outside_help_evidence'],
                   contamination_reviewed=complete)
        write_json(path, row)
        rows.append(row)
    (out / 'progress.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
    meta['unreviewed_branches'] = [r['branch'] for r in rows if not r['contamination_reviewed']]
    if meta['protocol'] == 'calibration':
        count = sum(r['resolved'] for r in rows)
        conservative = sum(r['resolved'] or r['contamination'] is True for r in rows)
        complete = not meta['missing_branches'] and not meta['unreviewed_branches'] and not meta['control_only']
        decision = 'incomplete' if not complete else 'proceed' if conservative <= 8 else 'ceiling, v3 rejected'
        report = dict(resolved_count=count, conservative_resolved_count=conservative, scored=len(rows),
                      planned=12, threshold=8, complete=complete, proceed=complete and conservative <= 8,
                      decision=decision, infra_void=sum(r['infra_void'] for r in rows),
                      outside_help=sum(r['outside_help'] is True for r in rows),
                      missing_branches=meta['missing_branches'], unreviewed_branches=meta['unreviewed_branches'])
        write_json(out / 'calibration.json', report)
        meta['calibration'] = report
    else:
        review_hash = digest(canonical(verdicts))
        archive = out / 'reviews' / review_hash
        archive.mkdir(parents=True, exist_ok=True)
        write_json(archive / 'contamination.json', verdicts)
        meta['analysis_views'] = {}
        for name in ('primary', 'sensitivity'):
            view = archive / name
            (view / 'cells').mkdir(parents=True, exist_ok=True)
            retained, excluded = [], []
            for task in meta['task_ids']:
                for sample in (1, 2):
                    unit = [r for r in rows if r['task'] == task and r['sample'] == sample]
                    reason = ('missing arms' if {r['arm'] for r in unit} != set(ARMS.values()) else
                              'synthetic control' if meta['control_only'] else
                              'contaminated' if name == 'primary' and any(r['contamination'] is True for r in unit) else
                              'unreviewed' if name == 'primary' and any(not r['contamination_reviewed'] for r in unit) else None)
                    if reason:
                        excluded.append(dict(task=task, sample=sample, reason=reason))
                    else:
                        retained.extend(unit)
            for row in retained:
                directory = view / 'cells' / f"{row['task']}-s{row['sample']}-{row['arm']}"
                directory.mkdir(exist_ok=True)
                write_json(directory / 'result.json', row)
            write_json(view / 'meta.json', {**meta, 'analysis_view': name, 'excluded_units': excluded,
                                           'review_sha256': review_hash,
                                           'analysis_complete': not meta['missing_branches']
                                           and not meta['unreviewed_branches'] and not meta['control_only']})
            meta['analysis_views'][name] = str(view)
    write_json(out / 'meta.json', meta)
    return meta


def score_branches(repo, remote, out, instances, selection, manifest, *, protocol='calibration',
                   branches=(), runner=None, harness_python=None, timeout=1800, control_only=False):
    repo, out = Path(repo).resolve(), Path(out).resolve()
    ids = selection['final_instance_ids']
    if len(ids) != 12 or len(set(ids)) != 12:
        raise ValueError('v3 requires the whole twelve-instance bank')
    rows = {r['instance_id']: r for r in instances}
    if protocol not in ('calibration', 'comparison'):
        raise ValueError('invalid protocol')
    if timeout <= 0:
        raise ValueError('timeout must be positive')
    expected = ([f'sandbox-devin-cal3/{task}-plain' for task in ids] if protocol == 'calibration' else
                [f'sandbox-devin/v3/{task}-{arm}-s{s}' for task in ids for arm in ARMS for s in (1, 2)])
    branches = list(branches) or expected
    if len(set(branches)) != len(branches) or any(b not in expected for b in branches):
        raise ValueError('duplicate, mixed or invalid handback branches')
    if ((out.exists() and (not out.is_dir() or any(p.name not in ('NOTES.md', 'SESSIONS.txt') for p in out.iterdir())))
            or out == REPO or REPO in out.parents):
        raise ValueError('use a fresh output directory outside the repository')
    for task in ids:
        record = manifest['branches']['sandbox-v3/'+task]
        if rows[task]['base_commit'] != record['base_commit']:
            raise ValueError('bank base commit mismatch: ' + task)
    if runner is None:
        if not harness_python:
            raise ValueError('harness Python is required')
        runner = lambda instance, patch, image, cell: call_harness(instance, patch, image, cell, harness_python, timeout)
    (out / 'cells').mkdir(parents=True)
    meta = dict(evidence='v3-harness-control' if control_only else 'external-devin-v3', protocol=protocol,
                calibration_only=protocol == 'calibration', control_only=control_only, task_ids=ids,
                config=dict(arms=['calibration-plain'] if protocol == 'calibration' else list(ARMS.values()),
                            tasks=['all'], samples=1 if protocol == 'calibration' else 2, seed=selection['seed']),
                remote=str(remote), requested_branches=branches, expected_branches=expected,
                unrequested_branches=[b for b in expected if b not in branches],
                selection_sha256=digest(canonical(selection)), manifest_sha256=digest(canonical(manifest)),
                git_sha=git(REPO, 'rev-parse', 'HEAD'), harness_version=HARNESS_VERSION,
                harness_timeout_s=timeout, dataset_sha256=digest(canonical(instances)),
                implementation_sha256={name: digest((HERE / name).read_bytes())
                                       for name in ('score.py', 'harness.py', 'patch.py')},
                note='Raw outcomes; comparison primary analysis uses the reviewed primary view, not this root.')
    delivered = []
    for branch in branches:
        sha = fetch(repo, remote, branch)
        if sha is None:
            continue
        _, task, external_arm, sample = parse_branch(branch)
        arm = 'calibration-plain' if protocol == 'calibration' else ARMS[external_arm]
        cell = out / 'cells' / f'{task}-s{sample}-{arm}'
        cell.mkdir()
        result = score_handback(repo, remote, sha, rows[task], manifest['branches']['sandbox-v3/'+task], cell, runner)
        result.update(task=task, sample=sample, arm=arm, external_arm='devin-'+external_arm,
                      branch=branch, git_sha=sha, evidence=meta['evidence'], protocol=protocol,
                      calls_complete=False,
                      **{k: UNKNOWN for k in ('model_calls', 'prompt_tokens', 'completion_tokens', 'wall_s',
                                             'vacant_feedback_rounds', 'vacant_home_bytes', 'trace_bytes')})
        write_json(cell / 'result.json', result)
        delivered.append(branch)
    meta['missing_branches'] = [b for b in expected if b not in delivered]
    write_json(out / 'meta.json', meta)
    write_json(out / 'contamination.json', {
        b: dict(contaminated=None, outside_help=None, evidence=[], outside_help_evidence=[], reviewer=None)
        for b in expected})
    return review(out)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    refresh = sub.add_parser('review')
    refresh.add_argument('run_dir', type=Path)
    collect = sub.add_parser('score')
    collect.add_argument('branches', nargs='*')
    collect.add_argument('--repo', type=Path, default=REPO)
    collect.add_argument('--remote', default='origin')
    collect.add_argument('--out', type=Path, required=True)
    collect.add_argument('--protocol', choices=('calibration', 'comparison'), required=True)
    collect.add_argument('--dataset-json', type=Path, required=True)
    collect.add_argument('--harness-python', type=Path, required=True)
    collect.add_argument('--timeout', type=int, default=1800)
    collect.add_argument('--control-only', action='store_true')
    args = parser.parse_args(argv)
    if args.command == 'review':
        meta = review(args.run_dir)
    else:
        instances = [json.loads(line) for line in args.dataset_json.read_text().splitlines() if line.strip()]
        if digest(canonical(instances)) != DATASET_CONTENT_SHA256:
            raise ValueError('dataset fingerprint mismatch')
        if args.timeout <= 0:
            raise ValueError('timeout must be positive')
        meta = score_branches(args.repo, args.remote, args.out, instances,
                              json.loads((HERE / 'SELECTION.json').read_text()),
                              json.loads((HERE / 'KIT.json').read_text()), protocol=args.protocol,
                              branches=args.branches, harness_python=args.harness_python.resolve(),
                              timeout=args.timeout, control_only=args.control_only)
    print(json.dumps({k: meta[k] for k in ('missing_branches', 'unreviewed_branches', 'calibration', 'analysis_views') if k in meta}))
    return meta


if __name__ == '__main__':
    main()
