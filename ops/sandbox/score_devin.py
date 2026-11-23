"""外部 Devin 分支交件的獨立量尺；缺交件不補值，不與 pi 結果混合。"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ops.sandbox.run import REPO, TASKS, UNKNOWN, contamination_evidence
from ops.sandbox.score import score

ARMS = {'plain': 'A', 'plain2': 'A2', 'vacant': 'G'}
V2_BANK = TASKS.with_name('tasks_v2')


def parse_branch(branch):
    for protocol, pattern in (
        ('calibration', r'sandbox-devin-cal/(.+)-(plain)'),
        ('v2', r'sandbox-devin/v2/(.+)-(plain2|plain|vacant)-s([12])'),
        ('v1', r'sandbox-devin/(.+)-(plain2|plain|vacant)'),
    ):
        match = re.fullmatch(pattern, branch)
        if match:
            return protocol, match[1], match[2], int(match[3]) if protocol == 'v2' else 1
    raise ValueError('invalid handback branch: ' + branch)


def frozen_bank(bank, tasks):
    frozen = json.loads((bank / 'FROZEN.json').read_text())
    if len(tasks) != 12 or set(tasks) != set(frozen['task_sha256']):
        raise ValueError('v2 bank differs from FROZEN.json')
    for task in tasks:
        root = bank / task
        digest = hashlib.sha256()
        for path in sorted(root.rglob('*')):
            if path.is_symlink():
                raise ValueError('symlink in frozen bank: ' + str(path))
            if path.is_file():
                digest.update(path.relative_to(root).as_posix().encode('utf-8') + b'\0')
                digest.update(hashlib.sha256(path.read_bytes()).hexdigest().encode('ascii') + b'\n')
        if digest.hexdigest() != frozen['task_sha256'][task]:
            raise ValueError('v2 bank differs from FROZEN.json: ' + task)
    return frozen


def git(repo, *args):
    return subprocess.check_output(['git', '-C', str(repo), *args], text=True, timeout=120).strip()


def fetch(repo, remote, branch):
    ref = 'refs/heads/' + branch
    found = subprocess.run(['git', '-C', str(repo), 'ls-remote', '--exit-code',
                            '--heads', remote, ref], capture_output=True, text=True, timeout=120)
    if found.returncode == 2:
        return None
    found.check_returncode()
    git(repo, 'fetch', '--no-tags', remote, ref)
    return git(repo, 'rev-parse', 'FETCH_HEAD^{commit}')


def score_branches(repo, remote, branches, out, kit_branch=None, *, bank=None, protocol='auto'):
    repo, out = Path(repo).resolve(), Path(out).resolve()
    branches = list(branches)
    parsed = [(branch, *parse_branch(branch)) for branch in branches]
    protocols = {row[1] for row in parsed}
    if protocol not in ('auto', 'v1', 'calibration', 'v2'):
        raise ValueError('unknown protocol: ' + protocol)
    if protocol == 'auto':
        protocol = next(iter(protocols)) if protocols else 'v1'
    if protocols - {protocol}:
        raise ValueError('mixed handback protocols are not allowed')
    is_v2 = protocol in ('calibration', 'v2')
    bank = Path(bank if bank is not None else V2_BANK if is_v2 else TASKS).resolve()
    if is_v2 and bank != V2_BANK.resolve():
        raise ValueError('v2 protocols require the frozen v2 bank')
    tasks = sorted(p.name for p in bank.iterdir() if (p / 'task.json').is_file())
    frozen = frozen_bank(bank, tasks) if is_v2 else None
    for branch, _, task, _, _ in parsed:
        if task not in tasks:
            raise ValueError('invalid handback branch: ' + branch)
    if len(set(branches)) != len(branches):
        raise ValueError('duplicate handback branches')
    expected = branches
    if is_v2:
        expected = ([f'sandbox-devin-cal/{task}-plain' for task in tasks] if protocol == 'calibration' else
                    [f'sandbox-devin/v2/{task}-{arm}-s{sample}' for task in tasks
                     for arm in ARMS for sample in (1, 2)])
        if not branches:
            branches = list(expected)
            parsed = [(branch, *parse_branch(branch)) for branch in branches]
    kit_branch = kit_branch or ('sandbox-devin-kit-v2' if is_v2 else 'sandbox-devin-kit')
    if out == REPO or REPO in out.parents:
        raise ValueError('output directory must be outside the repository')
    if out.exists():
        raise ValueError('output directory already exists; use a fresh run directory')
    kit_sha = fetch(repo, remote, kit_branch)
    if kit_sha is None:
        raise ValueError('missing kit branch: ' + kit_branch)
    out.mkdir(parents=True)
    (out / 'cells').mkdir()
    meta = dict(evidence='external-devin', task_ids=tasks,
                config=dict(arms=list(ARMS.values()), tasks=['all'], samples=1, seed=20261122),
                remote=remote, kit_branch=kit_branch, kit_sha=kit_sha,
                git_sha=git(REPO, 'rev-parse', 'HEAD'), python=sys.version,
                requested_branches=list(branches), missing_branches=[],
                note='External manual gate arm; no model costs or final-message claims collected.')
    if is_v2:
        meta.update(protocol=protocol, bank_freeze=frozen, expected_branches=expected,
                    unrequested_branches=[b for b in expected if b not in branches],
                    calibration_only=protocol == 'calibration')
        meta['config']['samples'] = 2 if protocol == 'v2' else 1
        if protocol == 'calibration':
            meta['evidence'] = 'external-devin-calibration'
            meta['config']['arms'] = ['calibration-plain']
    (out / 'progress.jsonl').touch()
    if bank != TASKS.resolve():
        meta['bank_dir'] = str(bank)
    results = []
    for branch, _, task, external_arm, sample in parsed:
        sha = fetch(repo, remote, branch)
        if sha is None:
            meta['missing_branches'].append(branch)
            continue
        arm = 'calibration-plain' if protocol == 'calibration' else ARMS[external_arm]
        cell = out / 'cells' / f'{task}-s{sample}-{arm}'
        cell.mkdir()
        archive = cell / 'workspace.tar'
        with archive.open('wb') as stream:
            subprocess.run(['git', '-C', str(repo), 'archive', '--format=tar', sha],
                           stdout=stream, check=True, timeout=120)
        diff = subprocess.check_output(['git', '-C', str(repo), 'diff', '--no-ext-diff',
                                       '--no-textconv', f'{kit_sha}:{task}', sha], timeout=120)
        (cell / 'diff.patch').write_bytes(diff)
        evidence = contamination_evidence(cell, bank)
        scored = score(bank / task, archive)
        infra = bool(scored['error'] and ('timeout' in scored['error'] or not scored['n_failed']))
        result = dict(task=task, sample=sample, arm=arm, external_arm='devin-' + external_arm,
                      branch=branch, git_sha=sha, kit_sha=kit_sha,
                      evidence='external-devin', score=scored,
                      hidden_pass=scored['hidden_pass'] and not infra,
                      visible_pass=scored['visible_pass'] and not infra,
                      infra_void=infra, infra_reason='scorer: ' + scored['error'] if infra else None,
                      contamination=bool(evidence), contamination_evidence=evidence,
                      calls_complete=False,
                      **{k: UNKNOWN for k in ('model_calls', 'prompt_tokens',
                                             'completion_tokens', 'wall_s',
                                             'vacant_feedback_rounds', 'vacant_home_bytes',
                                             'trace_bytes')})
        if is_v2:
            result.update(protocol=protocol, calibration_only=protocol == 'calibration',
                          evidence=meta['evidence'])
            if protocol == 'calibration':
                result['external_arm'] = 'devin-calibration-plain'
        results.append(result)
        (cell / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
        with (out / 'progress.jsonl').open('a') as stream:
            stream.write(json.dumps(result) + '\n')
    if is_v2:
        delivered = {row['branch'] for row in results}
        meta['missing_branches'] = [b for b in expected if b not in delivered]
    if protocol == 'calibration':
        passed = sum(row['hidden_pass'] for row in results)
        complete = not meta['missing_branches']
        decision = 'incomplete' if not complete else 'proceed' if passed <= 8 else 'ceiling, v2 rejected'
        report = dict(hidden_passed=passed, scored=len(results), planned=12, threshold=8,
                      complete=complete, proceed=complete and passed <= 8, decision=decision,
                      infra_void=sum(row['infra_void'] for row in results),
                      missing_branches=meta['missing_branches'])
        meta['calibration'] = report
        (out / 'calibration.json').write_text(json.dumps(report, indent=2) + '\n')
        (out / 'calibration.md').write_text(
            f'# V2 calibration only\n\nHidden-pass: {passed} among {len(results)} scored '
            f'(12 planned). Bank gate: ≤8/12. Decision: **{decision}**.\n'
            'Calibration is never part of a comparison; missing branches are not imputed.\n')
    (out / 'meta.json').write_text(json.dumps(meta, indent=2) + '\n')
    return meta


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('branches', nargs='*')
    parser.add_argument('--repo', type=Path, default=REPO)
    parser.add_argument('--remote', default='origin')
    parser.add_argument('--kit-branch')
    parser.add_argument('--bank', type=Path)
    parser.add_argument('--protocol', choices=('auto', 'v1', 'calibration', 'v2'), default='auto')
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args(argv)
    if not args.branches and args.protocol in ('auto', 'v1'):
        parser.error('branches are required for the v1 protocol')
    meta = score_branches(args.repo, args.remote, args.branches, args.out, args.kit_branch,
                          bank=args.bank, protocol=args.protocol)
    report = {'run_dir': str(args.out), 'missing_branches': meta['missing_branches']}
    if 'calibration' in meta:
        report['calibration'] = meta['calibration']
    print(json.dumps(report))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
