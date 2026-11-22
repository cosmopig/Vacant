"""新題庫的真量尺正負控制、SPEC 引用與可見匯出測試。"""
import hashlib
import json
import shutil
import subprocess
import sys

import pytest

from ops.sandbox import kit, score, validate_bank
from ops.sandbox.run import gate_suite


@pytest.fixture
def bank(tmp_path):
    root = tmp_path / 'bank'
    task = root / 'candidate'
    files = {
        'task.json': json.dumps(dict(id='candidate', category='feature',
            prompt='Update the counter. Follow SPEC.md.', visible_test_cmd='python -m pytest -q tests')),
        'repo/SPEC.md': '# Counter\n## §1 Increment\ncompute(n) returns n+1.\n',
        'repo/api.py': 'def compute(n):\n    return n\n',
        'repo/tests/test_visible.py': 'from api import compute\ndef test_main():\n    assert compute(0) >= 0\n',
        'hidden/test_contract.py': 'from api import compute\ndef test_private_contract():\n    # SPEC §1\n    assert compute(1) == 2\n',
        'solution/api.py': 'def compute(n):\n    return n+1\n',
    }
    for rel, content in files.items():
        dest = task / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content)
    return root


def test_validator_real_controls(bank, capsys):
    assert validate_bank.main([str(bank)]) == 0
    assert '1/1 tasks valid' in capsys.readouterr().out


@pytest.mark.parametrize(('problem', 'message'), [
    ('no_reference', 'missing SPEC reference'), ('unknown_clause', 'unknown SPEC §2'),
    ('name_leak', 'hidden test name leaked'), ('content_leak', 'hidden file leaked'),
    ('string_reference', 'missing SPEC reference'), ('no_tests', 'no hidden test functions'),
    ('missing_spec', 'FileNotFoundError'), ('broken_solution', 'solution fails'),
    ('passing_original', 'untouched workspace passes'),
])
def test_validator_rejects_invalid_controls(bank, problem, message):
    task = bank / 'candidate'
    hidden = task / 'hidden/test_contract.py'
    if problem == 'no_reference':
        hidden.write_text(hidden.read_text().replace('# SPEC §1', '# no citation'))
    elif problem == 'unknown_clause':
        hidden.write_text(hidden.read_text().replace('§1', '§2'))
    elif problem == 'string_reference':
        hidden.write_text(hidden.read_text().replace('# SPEC §1', '"# SPEC §1"'))
    elif problem == 'name_leak':
        (task / 'repo/notes.txt').write_text('test_private_contract')
    elif problem == 'content_leak':
        (task / 'repo/copied.txt').write_text(hidden.read_text())
    elif problem == 'no_tests':
        hidden.write_text('')
    elif problem == 'missing_spec':
        (task / 'repo/SPEC.md').unlink()
    elif problem == 'broken_solution':
        (task / 'solution/api.py').write_text('def compute(n):\n    return n\n')
    elif problem == 'passing_original':
        shutil.copyfile(task / 'solution/api.py', task / 'repo/api.py')
    result = validate_bank.validate_task(task)
    assert not result['ok']
    assert any(message in error for error in result['errors'])


def test_empty_and_missing_bank(tmp_path, capsys):
    assert validate_bank.main([str(tmp_path)]) == 1
    assert 'empty bank' in capsys.readouterr().out
    assert validate_bank.main([str(tmp_path / 'absent')]) == 1


def test_score_cli_bank_and_exact_output(bank, monkeypatch, capsys, tmp_path):
    task = bank / 'candidate'
    monkeypatch.setattr(sys, 'argv', ['score', '--bank', str(bank), 'candidate', str(task / 'repo')])
    assert score.main() == 1
    assert json.loads(capsys.readouterr().out)['hidden_pass'] is False
    output = tmp_path / 'report.txt'
    spec = dict(path='report.txt', type='text_exact', equals='Café\n')
    output.write_bytes(b'Caf\xc3\xa9\n')
    assert score._output_ok(spec, tmp_path) is True
    output.write_bytes(b'Caf\xc3\xa9\r\n')
    assert score._output_ok(spec, tmp_path) is False


def test_kit_export_is_visible_only(bank, tmp_path):
    output = tmp_path / 'kit'
    kit.main(['--bank', str(bank), '--out', str(output)])
    assert (output / 'candidate/SPEC.md').is_file()
    assert (output / 'prompts/candidate.txt').read_text() == 'Update the counter. Follow SPEC.md.'
    assert (output / '.gitignore').read_text() == '/receipts/\n'
    gate = (output / 'gates/candidate/test_visible.py').read_text()
    assert 'test_main' in gate and 'test_private_contract' not in gate
    assert not (output / 'candidate/hidden').exists()
    assert not (output / 'candidate/solution').exists()
    assert not any('test_private_contract' in p.read_text() for p in output.rglob('*') if p.is_file())
    with pytest.raises(FileExistsError):
        kit.build(bank, output)
    with pytest.raises(ValueError, match='outside'):
        kit.build(bank, bank / 'kit')
    with pytest.raises(ValueError, match='empty'):
        kit.build(tmp_path / 'kit/gates', tmp_path / 'empty-kit')


def test_v2_project_shape():
    root = score.TASKS.with_name('tasks_v2')
    tasks = sorted(p for p in root.iterdir() if (p / 'task.json').exists())
    assert len(tasks) == 12
    categories = []
    for task in tasks:
        meta = json.loads((task / 'task.json').read_text())
        categories.append(meta['category'])
        assert meta['id'] == task.name and 'SPEC.md' in meta['prompt']
        assert (task / 'repo/SPEC.md').is_file()
        assert len(list((task / 'repo').glob('*.py'))) >= 3
        lines = sum(len(p.read_text().splitlines()) for p in (task / 'repo').rglob('*.py'))
        assert 150 <= lines <= 400
    assert categories.count('bugfix') == categories.count('feature') == 5
    assert categories.count('output-file') == 2


def test_gate_embeds_all_visible_tests_and_data(bank, tmp_path):
    task = bank / 'candidate'
    nested = task / 'repo/tests/nested'
    nested.mkdir()
    (nested / 'test_visible.py').write_text(
        'from pathlib import Path\nfrom api import compute\n'
        'def test_second_file():\n    assert compute(1) == int(Path(__file__).with_name("expected.txt").read_text())\n')
    (nested / 'expected.txt').write_text('2')
    gate = tmp_path / 'gate'
    gate_suite(task, gate)
    command = [sys.executable, '-I', '-c',
               'import runpy,sys; runpy.run_path(sys.argv[1])["main"]()', str(gate / 'test_visible.py')]
    run = subprocess.run(command, cwd=task / 'repo', capture_output=True, text=True, timeout=20)
    assert run.returncode != 0 and 'test_second_file' in run.stderr
    shutil.copyfile(task / 'solution/api.py', task / 'repo/api.py')
    run = subprocess.run(command, cwd=task / 'repo', capture_output=True, text=True, timeout=20)
    assert run.returncode == 0, run.stderr
    empty = tmp_path / 'empty-task/repo/tests'
    empty.mkdir(parents=True)
    gate_suite(empty.parents[1], tmp_path / 'empty-gate')
    command[-1] = str(tmp_path / 'empty-gate/test_visible.py')
    run = subprocess.run(command, cwd=task / 'repo', capture_output=True, text=True, timeout=20)
    assert run.returncode != 0 and 'no tests ran' in run.stderr


def test_v2_frozen_directory_hashes():
    bank = score.TASKS.with_name('tasks_v2')
    frozen = json.loads((bank / 'FROZEN.json').read_text())
    tasks = sorted(p for p in bank.iterdir() if (p / 'task.json').is_file())
    assert len(tasks) == 12
    assert {p.name for p in tasks} == set(frozen['task_sha256'])
    for task in tasks:
        paths = sorted(task.rglob('*'))
        assert not any(p.is_symlink() for p in paths)
        digest = hashlib.sha256()
        for path in paths:
            if path.is_file():
                digest.update(path.relative_to(task).as_posix().encode('utf-8') + b'\0')
                digest.update(hashlib.sha256(path.read_bytes()).hexdigest().encode('ascii') + b'\n')
        assert digest.hexdigest() == frozen['task_sha256'][task.name], task.name
