import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

from ops.sandbox.v3 import kit, p2p_runner


def row(p2p, patch='', f2p=None):
    return dict(PASS_TO_PASS=json.dumps(p2p), FAIL_TO_PASS=json.dumps(f2p or ['test_new']),
                test_patch=patch, patch='+a distinctive gold implementation line longer than forty characters\n',
                problem_statement='Change this behavior.\nExactly this prompt.\n')


def test_resolve_only_existing_test_labels_and_aliases(tmp_path):
    (tmp_path / 'tests').mkdir()
    (tmp_path / 'tests/a.py').write_text('def test_old():\n    """An old description."""\n    pass\n')
    (tmp_path / 'tests/b.py').write_text('def test_old(): pass\n')
    patch = '+++ b/tests/a.py\n+++ b/tests/b.py\n+++ b/tests/new.py\n+def test_new(): pass\n'
    config = kit.resolve(tmp_path, row(['test_old', 'An old description.', 'tests/a.py::test_old'], patch))
    assert [(r['kind'], r['file']) for r in config['selectors']] == [
        ('function', 'tests/a.py'), ('function', 'tests/b.py'), ('description', 'tests/a.py'), ('nodeid', 'tests/a.py')]
    with pytest.raises(ValueError, match='no pre-existing'):
        kit.resolve(tmp_path, row(['test_missing'], patch))
    omissions = []
    existing = kit.resolve(tmp_path, row(['tests/a.py::test_old', 'tests/a.py::test_added'], patch), omissions)
    assert len(existing['selectors']) == 1 and omissions == ['tests/a.py::test_added']
    with pytest.raises(ValueError, match='absent from base'):
        kit.resolve(tmp_path, row(['tests/new.py::test_new'], patch))
    for labels in ([], ['test_new']):
        with pytest.raises(ValueError, match='empty or overlapping'):
            kit.resolve(tmp_path, row(labels, patch))


def test_resolve_unittest_descriptor(tmp_path):
    (tmp_path / 'tests/app').mkdir(parents=True)
    (tmp_path / 'tests/app/test_models.py').write_text('class Cases:\n    def test_old(self): pass\n')
    target = kit.resolve(tmp_path, row(['test_old (app.test_models.Cases)'], '+++ b/tests/app/test_models.py'))['selectors'][0]
    item = SimpleNamespace(nodeid='tests/app/test_models.py::Cases::test_old', name='test_old',
                           module=SimpleNamespace(__name__='tests.app.test_models'), cls=SimpleNamespace(__name__='Cases'))
    assert p2p_runner.matches(item, target)
    item.name = 'test_other'
    assert not p2p_runner.matches(item, target)
    with pytest.raises(ValueError, match='ambiguous module'):
        kit.resolve(tmp_path, row(['test_old (other.Cases)'], '+++ b/tests/app/test_models.py'))


def test_runtime_selects_only_p2p_and_fails_closed(tmp_path):
    (tmp_path / 'lib').mkdir()
    (tmp_path / 'lib/_v3_dependency.py').write_text('VALUE = 1\n')
    (tmp_path / 'test_example.py').write_text(
        'from _v3_dependency import VALUE\ndef test_old(): assert VALUE == 1\n'
        'def test_other(): assert False, "must be deselected"\n')
    selection = tmp_path / 'selection.json'
    selection.write_text(json.dumps(dict(django=False, selectors=[
        dict(kind='nodeid', file='test_example.py', label='test_example.py::test_old')])))
    command = [sys.executable, '-I', str(Path(p2p_runner.__file__)), str(tmp_path), str(selection)]
    env = {**os.environ, 'PYTEST_DISABLE_PLUGIN_AUTOLOAD': '1'}
    good = subprocess.run(command, capture_output=True, text=True, env=env)
    assert good.returncode == 0, good.stdout + good.stderr
    assert '1 passed, 1 deselected' in good.stdout
    (tmp_path / 'test_example.py').write_text('def test_old(): assert False\ndef test_other(): pass\n')
    broken = subprocess.run(command, capture_output=True, text=True, env=env)
    assert broken.returncode == 1 and '1 failed, 1 deselected' in broken.stdout
    (tmp_path / 'test_example.py').write_text('def test_other(): pass\n')
    missing = subprocess.run(command, capture_output=True, text=True, env=env)
    assert missing.returncode != 0 and 'Selected pre-existing tests missing' in missing.stderr
    selection.write_text(json.dumps(dict(django=False, selectors=[])))
    empty = subprocess.run(command, capture_output=True, text=True, env=env)
    assert empty.returncode != 0


def test_description_and_parameter_label_matching():
    item = SimpleNamespace(nodeid='tests/a.py::test_a[case-Length of x]', name='test_a[case-Length of x]',
                           originalname='test_a', obj=SimpleNamespace(__doc__='An old description.\nMore.'))
    assert p2p_runner.matches(item, dict(kind='nodeid', file='tests/a.py', label='tests/a.py::test_a[case-Length'))
    assert p2p_runner.matches(item, dict(kind='function', file='tests/a.py', label='test_a'))
    assert p2p_runner.matches(item, dict(kind='description', file='tests/a.py', label='An old description.'))
    assert not p2p_runner.matches(item, dict(kind='function', file='tests/b.py', label='test_a'))


def test_runtime_refuses_skips_deselection_and_collection_skips(tmp_path):
    test = tmp_path / 'test_selected.py'
    test.write_text('import pytest\n@pytest.mark.skip(reason="missing optional dependency")\ndef test_old(): pass\ndef test_other(): pass\n')
    selection = tmp_path / 'selection.json'
    selection.write_text(json.dumps(dict(django=False, selectors=[
        dict(kind='nodeid', file=test.name, label='test_selected.py::test_old')])))
    command = [sys.executable, '-I', str(Path(p2p_runner.__file__)), str(tmp_path), str(selection)]
    env = {**os.environ, 'PYTEST_DISABLE_PLUGIN_AUTOLOAD': '1'}
    skipped = subprocess.run(command, capture_output=True, text=True, env=env)
    assert skipped.returncode != 0 and 'P2P skipped:' in skipped.stderr
    assert 'test_selected.py::test_old' in skipped.stderr
    test.write_text('def test_old(): pass\ndef test_other(): pass\n')
    deselected = subprocess.run(command, capture_output=True, text=True, env={**env, 'PYTEST_ADDOPTS': '-k other'})
    assert deselected.returncode != 0 and 'P2P deselected:' in deselected.stderr
    assert 'test_selected.py::test_old' in deselected.stderr
    test.write_text('import pytest\npytest.importorskip("_missing_v3_test_dependency")\ndef test_old(): pass\n')
    uncollected = subprocess.run(command, capture_output=True, text=True, env=env)
    assert uncollected.returncode != 0 and 'Selected pre-existing tests missing' in uncollected.stderr
    assert 'test_selected.py::test_old' in uncollected.stderr


def test_export_is_exact_prompt_and_visible_selectors_only(tmp_path):
    root = tmp_path / 'base'
    root.mkdir()
    (root / 'test_old.py').write_text('def test_old(): pass\n')
    metadata = row(['test_old.py::test_old'], '+++ b/test_old.py\n+def test_new(): pass\n')
    out = tmp_path / 'kit'
    configs = kit.build({'task': metadata}, {'task': dict(workspace=str(root))}, out)
    assert configs['task']['selectors'][0]['label'] == 'test_old.py::test_old'
    assert (out / 'prompts/task.txt').read_bytes() == metadata['problem_statement'].encode()
    assert (out / '.gitignore').read_text() == '/receipts/\n/.venv/\n'
    exported = kit.file_bytes(out)
    assert set(path.split('/')[0] for path in exported) == {'.gitignore', 'README.md', 'prompts', 'gates'}
    assert not any(b'test_new' in text or b'distinctive gold' in text for text in exported.values())
    compile((out / 'gates/task/test_gate.py').read_text(), '<gate>', 'exec')
    with pytest.raises(FileExistsError):
        kit.build({'task': metadata}, {'task': dict(workspace=str(root))}, out)


def test_leak_checks_distinguish_base_exceptions():
    metadata = row(['test_old'], '+def test_new(): pass\n')
    patterns = kit.needles(metadata, {})
    assert {kind for kind, _ in patterns} == {'introduced_test_name', 'gold_added_line'}
    files = {'code.py': b'test_new\na distinctive gold implementation line longer than forty characters\n'}
    matches, leaks = kit.scan(files, patterns, {})
    assert len(matches) == len(leaks) == 2
    matches, leaks = kit.scan(files, patterns, files)
    assert len(matches) == 2 and leaks == []
    assert kit.scan({}, patterns, {}) == ([], [])
    metadata['patch'] = '+short_fix()\n+\n'
    assert ('gold_added_line', b'short_fix()') in kit.needles(metadata, {})
