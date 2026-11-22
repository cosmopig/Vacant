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


def test_external_scorer_explicit_bank(tmp_path, handbacks):
    repo, remote = handbacks
    bank = tmp_path / 'custom-bank'
    shutil.copytree(score_devin.TASKS / 'billing', bank / 'billing')
    for path in (bank / 'billing/hidden').glob('*.py'):
        path.unlink()
    (bank / 'billing/hidden/test_custom.py').write_text(
        'from billing import charge_cents\ndef test_custom_bank():\n    assert charge_cents(10,25,3) == 250\n')
    out = tmp_path / 'custom-results'
    score_devin.main(['--repo', str(repo), '--remote', remote, '--out', str(out),
                     '--bank', str(bank), 'sandbox-devin/billing-plain'])
    result = json.loads((out / 'cells/billing-s1-A/result.json').read_text())
    assert result['hidden_pass'] is True
    assert json.loads((out / 'meta.json').read_text())['bank_dir'] == str(bank.resolve())
    assert len(analyze.analyze(out)['missing']) == 2


@pytest.mark.parametrize('task_id', ['credit_ledger_v2', 'credit-ledger.v2'])
def test_external_task_ids_from_bank(tmp_path, handbacks, task_id):
    repo, remote = handbacks
    env = {**os.environ, 'GIT_AUTHOR_NAME': 'Test', 'GIT_COMMITTER_NAME': 'Test',
           'GIT_AUTHOR_EMAIL': 'test@example.invalid', 'GIT_COMMITTER_EMAIL': 'test@example.invalid'}

    def git(*args):
        return subprocess.check_output(['git', '-C', str(repo), *args], env=env,
                                       stderr=subprocess.PIPE, text=True).strip()

    bank = tmp_path / 'bank'
    shutil.copytree(score_devin.TASKS / 'billing', bank / task_id)
    meta = json.loads((bank / task_id / 'task.json').read_text())
    meta['id'] = task_id
    (bank / task_id / 'task.json').write_text(json.dumps(meta))
    shutil.copytree(repo / 'billing', repo / task_id)
    git('add', task_id)
    git('commit', '-m', 'new task id')
    git('push', remote, 'HEAD:refs/heads/sandbox-devin-kit')
    git('fetch', remote, 'refs/heads/sandbox-devin/billing-plain')
    sha = git('rev-parse', 'FETCH_HEAD')
    branch = 'sandbox-devin/' + task_id + '-plain'
    git('push', remote, sha + ':refs/heads/' + branch)
    out = tmp_path / 'results'
    result = score_devin.score_branches(repo, remote, [branch], out, bank=bank)
    row = json.loads((out / f'cells/{task_id}-s1-A/result.json').read_text())
    assert result['missing_branches'] == []
    assert row['task'] == task_id and row['git_sha'] == sha and row['n_failed'] > 0


@pytest.mark.parametrize(('error', 'failed', 'infra'), [
    ('tests: timeout', 1, True), ('ValueError: invalid archive', 0, True),
    ('tests: pytest exit 1', 1, False), (None, 0, False),
])
def test_scorer_infra_overrides_hidden_pass(tmp_path, handbacks, monkeypatch, error, failed, infra):
    repo, remote = handbacks
    scored = dict(hidden_pass=True, visible_pass=not error, n_failed=failed, error=error)
    monkeypatch.setattr(score_devin, 'score', lambda *args: scored)
    out = tmp_path / 'scorer-error'
    score_devin.score_branches(repo, remote, ['sandbox-devin/billing-plain'], out)
    result = json.loads((out / 'cells/billing-s1-A/result.json').read_text())
    assert result['score']['hidden_pass'] is True
    assert result['infra_void'] is infra
    assert result['hidden_pass'] is (not infra)
    assert result['infra_reason'] == ('scorer: ' + error if infra else None)
    arm = analyze.analyze(out)['arms']['A']
    assert arm['n'] == 1 and arm['infra_void'] == int(infra)
    assert arm['hidden_passed'] == int(not infra)


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


def test_gate_uses_runtime_python(tmp_path, monkeypatch):
    import runpy
    from types import SimpleNamespace
    from ops.sandbox.run import gate_suite
    gate_suite(score_devin.TASKS / 'billing', tmp_path / 'gate', portable=True)
    source = (tmp_path / 'gate/test_visible.py').read_text()
    assert str(Path(__file__).resolve().parents[1]) not in source
    python = tmp_path / '.venv/bin/python'
    python.parent.mkdir(parents=True)
    python.touch()
    frozen = tmp_path / 'receipts/billing-1/_frozen_RUN-ON'
    frozen.mkdir(parents=True)
    monkeypatch.chdir(frozen)
    commands = []

    def execute(cmd, **kwargs):
        commands.append(cmd)
        return SimpleNamespace(returncode=0, stdout='', stderr='')

    monkeypatch.setattr(subprocess, 'run', execute)
    runpy.run_path(str(tmp_path / 'gate/test_visible.py'))['main']()
    assert commands[0][0] == str(python)
