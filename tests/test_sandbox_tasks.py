"""十二題的正負控制：量尺必須獨立於 agent 留下的測試。"""
import io
import json
from pathlib import Path
import shutil
import tarfile

import pytest

from ops.sandbox import score as scorer

TASKS = sorted(scorer.TASKS.iterdir())


@pytest.mark.parametrize('task', TASKS, ids=lambda p: p.name)
def test_task_controls(task, tmp_path):
    meta = json.loads((task / 'task.json').read_text())
    assert meta['id'] == task.name
    assert meta['visible_test_cmd'] == 'python -m pytest -q tests'
    assert not (task / 'repo' / '_hidden').exists()
    assert not set(p.name for p in (task / 'hidden').glob('*.py')) & set(
        p.name for p in (task / 'repo').rglob('*.py'))
    ws = tmp_path / 'ws'
    shutil.copytree(task / 'repo', ws)
    negative = scorer.score(task, ws)
    assert not negative['hidden_pass'], negative
    assert not negative['tests_modified']
    assert negative['n_failed'] > 0
    if meta['category'] == 'bugfix':
        assert not negative['visible_pass']
    if meta.get('output_check'):
        assert negative['output_file_ok'] is False

    (ws / 'tests' / 'test_visible.py').unlink()
    tampered = scorer.score(task, ws)
    assert tampered['tests_modified']
    assert not tampered['hidden_pass']
    if meta['category'] == 'bugfix':
        assert not tampered['visible_pass']

    shutil.copytree(task / 'repo' / 'tests', ws / 'tests', dirs_exist_ok=True)
    shutil.copytree(task / 'solution', ws, dirs_exist_ok=True)
    outside = tmp_path / 'outside'
    outside.mkdir()
    (outside / 'secret.py').write_text('raise RuntimeError("followed outside symlink")')
    (ws / 'outside').symlink_to(outside, target_is_directory=True)
    (ws / 'secret.py').symlink_to(outside / 'secret.py')
    (ws / 'oversized').write_bytes(b'x' * (scorer.MAX_FILE + 1))
    copy = tmp_path / 'copy'
    scorer._copy(ws, copy)
    assert not (copy / 'outside').exists()
    assert not (copy / 'secret.py').exists()
    assert not (copy / 'oversized').exists()
    positive = scorer.score(task, ws)
    assert positive['visible_pass'] and positive['hidden_pass'], positive
    assert not positive['tests_modified']
    assert positive['output_file_ok'] is not False
    assert positive['n_passed'] > 0 and positive['n_failed'] == 0
    assert positive['error'] is None
    assert not list(ws.glob('_hidden'))
    if meta.get('output_check'):
        (ws / meta['output_check']['path']).write_text('{broken')
        assert scorer._output_ok(meta['output_check'], ws) is False


def test_tar_workspace_and_unsafe_members(tmp_path):
    task = scorer.TASKS / 'billing'
    ws = tmp_path / 'ws'
    shutil.copytree(task / 'repo', ws)
    shutil.copytree(task / 'solution', ws, dirs_exist_ok=True)
    archive = tmp_path / 'ws.tar'
    with tarfile.open(archive, 'w') as tar:
        for p in ws.rglob('*'):
            if p.is_file():
                tar.add(p, arcname=str(p.relative_to(ws)))
        link = tarfile.TarInfo('outside')
        link.type = tarfile.SYMTYPE
        link.linkname = '/etc/passwd'
        tar.addfile(link)
    assert scorer.score(task, archive)['hidden_pass']
    with tarfile.open(archive, 'w') as tar:
        bad = tarfile.TarInfo('../escape')
        bad.size = 1
        tar.addfile(bad, io.BytesIO(b'x'))
    assert 'unsafe archive path' in scorer.score(task, archive)['error']
    assert not (tmp_path / 'escape').exists()


def test_missing_workspace_and_limits(tmp_path, monkeypatch):
    task = scorer.TASKS / 'billing'
    assert scorer.score(task, tmp_path / 'missing')['error']
    ws = tmp_path / 'ws'
    shutil.copytree(task / 'repo', ws)
    monkeypatch.setattr(scorer, 'MAX_FILES', 1)
    assert 'copy limit exceeded' in scorer.score(task, ws)['error']


def test_timeout_is_not_a_pass(tmp_path, monkeypatch):
    task = scorer.TASKS / 'billing'
    ws = tmp_path / 'ws'
    shutil.copytree(task / 'repo', ws)
    (ws / 'billing.py').write_text('while True: pass\n')
    monkeypatch.setattr(scorer, 'TIMEOUT', 0.2)
    result = scorer.score(task, ws)
    assert not result['visible_pass'] and not result['hidden_pass']
    assert 'timeout' in result['error']
    assert result['n_failed'] == 2


def test_output_path_validation(tmp_path):
    with pytest.raises(ValueError, match='unsafe output'):
        scorer._output_ok({'path': '../escape'}, tmp_path)
