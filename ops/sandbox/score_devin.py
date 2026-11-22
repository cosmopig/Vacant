"""外部 Devin 分支交件的獨立量尺；缺交件不補值，不與 pi 結果混合。"""
from __future__ import annotations

import argparse
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


def score_branches(repo, remote, branches, out, kit_branch='sandbox-devin-kit', *, bank=TASKS):
    repo, out = Path(repo).resolve(), Path(out).resolve()
    bank = Path(bank).resolve()
    tasks = sorted(p.name for p in bank.iterdir() if (p / 'task.json').is_file())
    parsed = []
    for branch in branches:
        match = re.fullmatch(r'sandbox-devin/(.+)-(plain2|plain|vacant)', branch)
        if not match or match[1] not in tasks:
            raise ValueError('invalid handback branch: ' + branch)
        parsed.append((branch, match[1], match[2]))
    if len(set(branches)) != len(branches):
        raise ValueError('duplicate handback branches')
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
    (out / 'progress.jsonl').touch()
    if bank != TASKS.resolve():
        meta['bank_dir'] = str(bank)
    for branch, task, external_arm in parsed:
        sha = fetch(repo, remote, branch)
        if sha is None:
            meta['missing_branches'].append(branch)
            continue
        arm = ARMS[external_arm]
        cell = out / 'cells' / f'{task}-s1-{arm}'
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
        result = dict(task=task, sample=1, arm=arm, external_arm='devin-' + external_arm,
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
        (cell / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
        with (out / 'progress.jsonl').open('a') as stream:
            stream.write(json.dumps(result) + '\n')
    (out / 'meta.json').write_text(json.dumps(meta, indent=2) + '\n')
    return meta


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('branches', nargs='+')
    parser.add_argument('--repo', type=Path, default=REPO)
    parser.add_argument('--remote', default='origin')
    parser.add_argument('--kit-branch', default='sandbox-devin-kit')
    parser.add_argument('--bank', type=Path, default=TASKS)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args(argv)
    meta = score_branches(args.repo, args.remote, args.branches, args.out, args.kit_branch, bank=args.bank)
    print(json.dumps({'run_dir': str(args.out), 'missing_branches': meta['missing_branches']}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
