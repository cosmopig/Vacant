"""本機 bare repo 假交件：外部分支的量尺、缺件與污染證據。"""
import json
import os
from pathlib import Path
import shutil
import subprocess

import pytest

from ops.sandbox import analyze, score_devin


@pytest.fixture
def handbacks(tmp_path):
    env = {**os.environ, 'GIT_AUTHOR_NAME': 'Test', 'GIT_COMMITTER_NAME': 'Test',
           'GIT_AUTHOR_EMAIL': 'test@example.invalid', 'GIT_COMMITTER_EMAIL': 'test@example.invalid'}

    def git(path, *args):
        return subprocess.check_output(['git', '-C', str(path), *args], env=env,
                                       stderr=subprocess.PIPE, text=True).strip()

    bare = tmp_path / 'remote.git'
    subprocess.run(['git', 'init', '--bare', str(bare)], check=True, capture_output=True)
    seed = tmp_path / 'seed'
    seed.mkdir()
    git(seed, 'init')
    task = score_devin.TASKS / 'billing'
    shutil.copytree(task / 'repo', seed / 'billing')
    git(seed, 'add', 'billing')
    git(seed, 'commit', '-m', 'visible kit')
    git(seed, 'push', str(bare), 'HEAD:refs/heads/sandbox-devin-kit')
    delivery = tmp_path / 'delivery'
    shutil.copytree(task / 'repo', delivery)
    git(delivery, 'init')
    git(delivery, 'add', 'billing.py', 'tests')
    git(delivery, 'commit', '-m', 'untouched')
    for arm in ('plain', 'plain2'):
        git(delivery, 'push', str(bare), f'HEAD:refs/heads/sandbox-devin/billing-{arm}')
    shutil.copytree(task / 'solution', delivery, dirs_exist_ok=True)
    (delivery / 'NOTE.md').write_text('ops/sandbox/tasks/billing/solution/billing.py')
    git(delivery, 'add', 'billing.py', 'NOTE.md')
    git(delivery, 'commit', '-m', 'fixed with contamination marker')
    git(delivery, 'push', str(bare), 'HEAD:refs/heads/sandbox-devin/billing-vacant')
    return seed, str(bare)


def test_score_external_branches(tmp_path, handbacks):
    repo, remote = handbacks
    out = tmp_path / 'results'
    branches = ['sandbox-devin/billing-' + arm for arm in ('plain', 'plain2', 'vacant')]
    branches.append('sandbox-devin/stock-plain')
    meta = score_devin.score_branches(repo, remote, branches, out)
    assert meta['evidence'] == 'external-devin'
    assert meta['missing_branches'] == ['sandbox-devin/stock-plain']
    rows = [json.loads(line) for line in (out / 'progress.jsonl').read_text().splitlines()]
    assert len(rows) == 3
    assert {r['arm']: r['hidden_pass'] for r in rows} == {'A': False, 'A2': False, 'G': True}
    for row in rows:
        assert row['git_sha'] and row['kit_sha']
        assert row['prompt_tokens'] == 'UNKNOWN' and not row['calls_complete']
        assert not row['infra_void']
        assert (out / 'cells' / f"billing-s1-{row['arm']}" / 'workspace.tar').is_file()
    assert rows[-1]['contamination']
    assert rows[-1]['contamination_evidence'][0]['source'] == 'diff.patch'
    summary = analyze.analyze(out)
    assert summary['evidence'] == 'external-devin'
    assert summary['aa_control']['delta'] == 0
    assert summary['comparisons']['G-A']['delta'] == 1
    assert len(summary['missing']) == 33
    assert not (out / 'cells/stock-s1-A').exists()
    with pytest.raises(ValueError, match='already exists'):
        score_devin.score_branches(repo, remote, branches, out)


def test_missing_external_branches(tmp_path, handbacks):
    repo, remote = handbacks
    out = tmp_path / 'missing'
    score_devin.main(['--repo', str(repo), '--remote', remote, '--out', str(out),
                     'sandbox-devin/stock-plain'])
    assert (out / 'progress.jsonl').read_text() == ''
    summary = analyze.analyze(out)
    assert summary['arms']['A']['n'] == 0 and len(summary['missing']) == 36


@pytest.mark.parametrize('branches', [
    ['sandbox-devin/billing-plain', 'sandbox-devin/billing-plain'],
    ['sandbox-devin/unknown-plain'], ['sandbox-devin/billing-other'], ['--bad'],
])
def test_invalid_handback_names(tmp_path, branches):
    with pytest.raises(ValueError):
        score_devin.score_branches(tmp_path, 'unused', branches, tmp_path / 'out')
    assert not (tmp_path / 'out').exists()


def test_fetch_errors_are_not_missing(tmp_path, handbacks):
    repo, remote = handbacks
    assert score_devin.fetch(repo, remote, 'absent') is None
    with pytest.raises(subprocess.CalledProcessError):
        score_devin.fetch(repo, str(tmp_path / 'no-repo'), 'sandbox-devin-kit')


def test_gate_uses_runtime_python(tmp_path):
    from ops.sandbox.run import gate_suite
    gate_suite(score_devin.TASKS / 'billing', tmp_path / 'gate', portable=True)
    source = (tmp_path / 'gate/test_visible.py').read_text()
    assert 'pathlib.Path(os.getcwd()).parent / ".venv/bin/python"' in source
    assert str(Path(__file__).resolve().parents[1]) not in source
