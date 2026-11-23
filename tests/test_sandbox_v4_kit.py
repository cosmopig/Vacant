import json
import os
import sys
import os
from pathlib import Path
import shlex
import sys

import pytest

from ops.sandbox.v4 import gate, kit


def test_native_recipe_uses_native_python_and_no_docker_or_host_upgrade():
    row = dict(instance_id='task', repo='sympy/sympy')
    script = ['source /opt/miniconda3/bin/activate', 'conda create -n testbed python=3.9 mpmath -y',
              'conda activate testbed', 'python -m pip install mpmath==1.3.0']
    result = kit.native_recipe(row, script, dict(python='3.9', install='python -m pip install -e .'))
    text = '\n'.join(result['commands'])
    assert 'micromamba create -c conda-forge -p "$ENV_PREFIX" python=3.9' in text
    assert 'micromamba activate "$ENV_PREFIX"' in text
    assert 'pytest==7.4.4 py==1.10.0' in text
    assert 'docker' not in text and 'apt-get' not in text
    assert result['python'] == '3.9'
    sphinx = kit.native_recipe(dict(row, repo='sphinx-doc/sphinx'), script,
                               dict(python='3.9', install='python -m pip install -e .'))
    assert any('roman==4.1' in command for command in sphinx['commands'])
    project = kit.native_recipe(dict(row, repo='pytest-dev/pytest', version='5.1'), script,
                               dict(python='3.9', install='python -m pip install -e .'))
    assert not any('pip install pytest==' in command for command in project['commands'])
    assert project['runner_environment'] == {'SETUPTOOLS_SCM_PRETEND_VERSION': '5.1'}
    assert project['commands'][0] == 'export SETUPTOOLS_SCM_PRETEND_VERSION=5.1'
    xarray = kit.native_recipe(dict(row, repo='pydata/xarray'),
        ['conda create -c conda-forge -n testbed python=3.10 -y', 'conda env update -f environment.yml'],
        dict(python='3.10'))
    assert not any(command.startswith('conda ') for command in xarray['commands'])
    assert xarray['runner_environment'] == {'PYTHONNOUSERSITE': '1'}
    assert 'python -m pip install "exceptiongroup==1.1.3"' in xarray['commands']
    astropy = kit.native_recipe(dict(row, repo='astropy/astropy', version='4.3'), script,
                               dict(python='3.9', install='python -m pip install -e .[test]'))
    assert 'python -m pip install --no-build-isolation -e .[test]' in astropy['commands']
    assert any('Cython==0.29.30' in command for command in astropy['commands'])
    assert 'python setup.py build_ext --inplace --force' in astropy['commands']


def test_changed_gate_helpers_invalidate_previously_ready_controls():
    result = dict(selection=dict(measurement=dict(native_artifact_policy=kit.NATIVE_POLICY_VERSION,
        gate_runtime_sha256=kit.digest(kit.gate_runtime.__file__),
        node_runner_sha256=kit.digest(Path(kit.__file__).with_name('node_runner.py')))))
    assert kit.current_case(result)
    result['selection']['measurement']['gate_runtime_sha256'] = 'old-runtime'
    assert not kit.current_case(result)
    assert not kit.current_case({})


def test_archived_rebuild_recovers_installed_version_and_refuses_missing_metadata(tmp_path):
    env = dict(os.environ, PATH=str(Path(sys.executable).parent) + os.pathsep + os.environ['PATH'])
    log = tmp_path / 'metadata.log'
    script = '\n'.join(['set -e', *kit.native_version_commands(dict(repo='pytest-dev/pytest')),
                        'printf "%s\\n" "$SETUPTOOLS_SCM_PRETEND_VERSION"'])
    kit.run_logged(['bash', '-c', script], tmp_path, log, 30, env)
    assert log.read_text().splitlines()[-1] == kit.version('pytest')
    script = '\n'.join(['set -e', *kit.native_version_commands(dict(repo='example/no-native-distribution-here'))])
    with pytest.raises(RuntimeError, match='command exit 1'):
        kit.run_logged(['bash', '-c', script], tmp_path, log, 30, env)


def test_recipe_preserves_legacy_python_and_secure_setup():
    row = dict(instance_id='old', repo='django/django')
    result = kit.native_recipe(row, ['conda create -n testbed python=3.6 -y', 'conda activate testbed'],
        dict(python='3.6', pre_install=['apt-get update && apt-get upgrade -y', "sed -i 's/old/new/g' setup.cfg"]))
    text = '\n'.join(result['commands'])
    assert 'python=3.6' in text and 'pytest==6.2.5 pytest-django==4.5.2' in text
    assert 'setuptools==59.6.0' in text and "sed -i 's/old/new/g' setup.cfg" in text
    assert 'apt-get' not in text and 'micromamba install' in text


def test_conda_yaml_extras_are_installed_with_pip_instead_of_invalid_conda_names():
    script = ["cat <<'EOF' > environment.yml\ndependencies:\n  - nbconvert[execute]!=6.0.0,!=6.0.1\nEOF",
              'conda env create --file environment.yml', 'conda activate testbed']
    recipe = kit.native_recipe(dict(instance_id='task', repo='owner/repo'), script, dict(python='3.11'))
    assert '  - nbconvert!=6.0.0,!=6.0.1' in recipe['commands'][3]
    assert "python -m pip install 'nbconvert[execute]!=6.0.0,!=6.0.1'" in recipe['commands']


def test_python311_unittest_label_preserves_original_provenance(tmp_path):
    source = tmp_path / 'tests/servers/test_basehttp.py'
    source.parent.mkdir(parents=True)
    source.write_text('class WSGIRequestHandlerTestCase:\n    def test_https(self): pass\n')
    label = 'test_https (servers.test_basehttp.WSGIRequestHandlerTestCase.test_https)'
    row = dict(PASS_TO_PASS=json.dumps([label]), FAIL_TO_PASS='[]',
               test_patch='+++ b/tests/servers/test_basehttp.py\n')
    omissions = []
    config = kit.resolve_nodes(tmp_path, row, omissions)
    target, = config['selectors']
    assert target['label'] == label
    assert target['module'] == 'servers.test_basehttp'
    assert target['class'] == 'WSGIRequestHandlerTestCase'
    assert target['method'] == 'test_https' and not omissions
    with pytest.raises(ValueError, match='empty or overlapping'):
        kit.resolve_nodes(tmp_path, dict(row, PASS_TO_PASS='[]'), [])


def test_sphinx_empty_official_p2p_uses_only_approved_existing_file(tmp_path):
    source = tmp_path / 'tests/test_ext_autodoc.py'
    source.parent.mkdir()
    source.write_text('def test_existing(): pass\n')
    row = dict(instance_id='sphinx-doc__sphinx-8595', PASS_TO_PASS='[]')
    config = kit.resolve_nodes(tmp_path, row, [])
    assert config['selectors'] == [dict(kind='function', file='tests/test_ext_autodoc.py', label='test_existing')]


def test_new_nested_test_classes_are_recorded_as_nonbase(tmp_path):
    (tmp_path / 'test_values.py').write_text('class Existing:\n    def test_match(self): pass\n')
    present = 'test_values.py::Existing::test_match'
    missing = 'test_values.py::MissingOuter::Existing::test_match'
    row = dict(repo='owner/repo', PASS_TO_PASS=json.dumps([present, missing]),
               FAIL_TO_PASS='["test_values.py::test_fix"]', test_patch='')
    omitted = []
    config = kit.resolve_nodes(tmp_path, row, omitted)
    assert [target['label'] for target in config['selectors']] == [present]
    assert omitted == [missing]


def test_setup_substitutions_resume_from_head_not_previous_normalization(tmp_path):
    kit.git(tmp_path, 'init', '--quiet', '--template=')
    target = tmp_path / 'setup.cfg'
    target.write_text('dependency\n')
    kit.git(tmp_path, 'add', 'setup.cfg')
    kit.git(tmp_path, 'commit', '--quiet', '-m', 'Base')
    commands = ["sed -i 's/dependency/dependency<=1.0/g' setup.cfg"]
    for _ in range(2):
        kit.restore_setup(tmp_path, commands)
        normalized = kit.v3_patch.normalize_setup(kit.v3_patch._files(tmp_path, set()), commands)
        target.write_bytes(normalized['setup.cfg'][1])
        assert target.read_text() == 'dependency<=1.0\n'
    with pytest.raises(ValueError, match='unsafe setup target'):
        kit.restore_setup(tmp_path, ["sed -i 's/a/b/g' ../outside.cfg"])


def test_approved_base_only_freeze_records_uncollected_omissions():
    broad = dict(django=False, selectors=[dict(kind='nodeid', file='test_old.py', label=node)
                                         for node in ('test_old.py::test_yes', 'test_old.py::test_absent')])
    report = dict(selected=['test_old.py::test_yes'], passed=['test_old.py::test_yes'],
                  failed=[], skipped=[], deselected=[], pytest_exitcode=0,
                  label_nodes={'test_old.py::test_yes': ['test_old.py::test_yes'], 'test_old.py::test_absent': []})
    omitted = []
    frozen = kit.freeze_base(broad, report, 1, dict(instance_id='task'),
                             dict(instance_id='matplotlib__matplotlib-23299'), omitted)
    assert frozen['selectors'] == [dict(kind='exact', label='test_old.py::test_yes', file='test_old.py')]
    assert omitted == frozen['omitted_uncollected_labels'] == ['test_old.py::test_absent']
    with pytest.raises(ValueError, match='collection/environment'):
        kit.freeze_base(broad, dict(report, pytest_exitcode=3), 1, {},
                        dict(instance_id='matplotlib__matplotlib-23299'), [])
    with pytest.raises(ValueError):
        kit.freeze_base(broad, dict(report, passed=[]), 1, {},
                        dict(instance_id='matplotlib__matplotlib-23299'), [])
    for key in kit.REPAIR_OMISSIONS:
        failed = dict(report, selected=['test_old.py::test_yes', 'test_old.py::test_bad'],
                      failed=['test_old.py::test_bad'], pytest_exitcode=1,
                      label_nodes={**report['label_nodes'], 'test_old.py::test_bad': ['test_old.py::test_bad']})
        expanded = dict(broad, selectors=broad['selectors'] +
                        [dict(kind='nodeid', file='test_old.py', label='test_old.py::test_bad')])
        result = kit.freeze_base(expanded, failed, 1, dict(instance_id=key), dict(instance_id=key), [])
        assert result['base_nonpassing_nodes'] == ['test_old.py::test_bad']
        assert result['selectors'] == frozen['selectors']


def test_native_controls_inherit_environment_tools(tmp_path):
    root = tmp_path / 'kit'
    workspace = root / 'task'
    workspace.mkdir(parents=True)
    (workspace / 'sample').mkdir()
    (workspace / 'sample/__init__.py').write_text('VALUE = 0\n')
    (workspace / 'test_old.py').write_text('import subprocess\nfrom pathlib import Path\ndef test_old():\n'
        '    assert ("test_v4_kit_" + "red_green_control") not in Path(__file__).read_text()\n'
        '    assert subprocess.check_output(["native-kit-tool"]).strip() == b"ready"\n')
    kit.git(workspace, 'init', '--quiet', '--template=')
    kit.git(workspace, 'add', 'sample/__init__.py', 'test_old.py')
    kit.git(workspace, 'commit', '--quiet', '-m', 'base')
    binary = root / '.envs/task/bin'
    binary.mkdir(parents=True)
    (binary / 'python').write_text('#!/bin/sh\nexec ' + shlex.quote(sys.executable) + ' "$@"\n')
    (binary / 'python').chmod(0o755)
    tool = binary / 'native-kit-tool'
    tool.write_text('#!/bin/sh\necho ready\n')
    tool.chmod(0o755)
    config = dict(django=False, selectors=[dict(kind='exact', label='test_old.py::test_old', file='test_old.py')],
                  interpreter='.envs/task/bin/python', timeout_s=120, environment=dict(commands=[]),
                  provenance='x' * 200_000)
    suite = gate.write_suite(root, 'task', config)
    result = kit.native_controls(workspace, suite, config, dict(repo='sample/project'), tmp_path,
                                 dict(os.environ, PATH=str(binary) + os.pathsep + os.environ['PATH']))
    assert result['red_green']['A'] == result['red_green']['B'] == result['red_green']['C'] == 'pass'
    assert result['p2p_regression'] == 'refused at C'
    assert not (workspace / 'test_v4_kit_control.py').exists()
    assert (workspace / 'sample/__init__.py').read_text() == 'VALUE = 0\n'
    broad = dict(config, selectors=[*config['selectors'],
                                   dict(kind='exact', label='test_old.py::test_absent', file='test_old.py')])
    discovery = tmp_path / 'discovery.json'
    report = tmp_path / 'discovered.json'
    kit.save(discovery, broad)
    kit.run_logged([sys.executable, '-I', '-B', str(Path(kit.__file__).with_name('discover.py')),
                    str(Path(kit.v3.__file__).with_name('p2p_runner.py')), str(workspace), str(discovery), str(report)],
                   workspace, tmp_path / 'discovery.log', 30,
                   dict(os.environ, PATH=str(binary) + os.pathsep + os.environ['PATH']))
    collected = json.loads(report.read_text())
    assert collected['passed'] == ['test_old.py::test_old']
    assert collected['label_nodes']['test_old.py::test_absent'] == []
    path = workspace / 'test_old.py'
    path.write_text(path.read_text() + '\nimport pytest\n'
        '@pytest.mark.parametrize("value", [12, 12])\ndef test_counter(value): assert value\n'
        '@pytest.mark.parametrize("value", [12, 12, 120])\ndef test_exact(value): assert value\n'
        '@pytest.mark.parametrize("path", [__file__])\ndef test_path(path): assert path\n')
    aliases = ['test_old.py::test_counter[120]', 'test_old.py::test_counter[121]',
               'test_old.py::test_path[/test_old.py]', 'test_old.py::test_exact[120]']
    kit.save(discovery, dict(config, selectors=[*config['selectors'],
        *(dict(kind='nodeid', label=node, file='test_old.py') for node in aliases)]))
    arguments = [sys.executable, '-I', '-B', str(Path(kit.__file__).with_name('discover.py'))]
    tail = [str(Path(kit.v3.__file__).with_name('p2p_runner.py')), str(workspace), str(discovery), str(report)]
    environment = dict(os.environ, PATH=str(binary) + os.pathsep + os.environ['PATH'])
    kit.run_logged([*arguments, *tail], workspace, tmp_path / 'pruned.log', 30, environment)
    pruned = json.loads(report.read_text())
    assert len(pruned['passed']) == 2
    assert pruned['native_aliases'] == {}
    kit.run_logged([*arguments, '--strict', *tail], workspace, tmp_path / 'aliases.log', 30, environment)
    adapted = json.loads(report.read_text())
    assert len(adapted['passed']) == 5
    assert all(len(adapted['label_nodes'][label]) == 1 for label in aliases)
    assert set(adapted['native_aliases']) == set(aliases[:3])


def test_history_free_snapshot_exact_prompt_and_leak_audit(tmp_path):
    upstream = tmp_path / 'upstream'
    upstream.mkdir()
    kit.git(upstream, 'init', '--quiet', '--template=')
    (upstream / 'test_old.py').write_text('def test_old(): assert True\n')
    kit.git(upstream, 'add', 'test_old.py')
    kit.git(upstream, 'commit', '--quiet', '-m', 'upstream history one')
    (upstream / 'behavior.py').write_text('VALUE = 0\n')
    kit.git(upstream, 'add', 'behavior.py')
    kit.git(upstream, 'commit', '--quiet', '-m', 'upstream history two')
    sha = kit.git(upstream, 'rev-parse', 'HEAD').decode().strip()
    root = tmp_path / 'build'
    root.mkdir()
    row = dict(instance_id='task', repo='owner/repo', base_commit=sha, problem_statement='Issue\nexactly.\n')
    info = kit.snapshot(row, root, upstream.as_uri())
    workspace = Path(info['workspace'])
    assert info['branch'] == 'sandbox-v4/task'
    assert info == kit.snapshot(row, root, 'must not refetch')
    assert info['base_tree'] == kit.git(upstream, 'rev-parse', 'HEAD^{tree}').decode().strip()
    assert b'\nparent ' not in b'\n' + kit.git(workspace, 'cat-file', '-p', 'HEAD').split(b'\n\n')[0]
    config = dict(django=False, selectors=[dict(file='test_old.py', kind='exact', label='test_old.py::test_old')],
                  interpreter='.envs/task/bin/python', timeout_s=120, environment=dict(commands=[]))
    suite = gate.write_suite(root / 'kit', 'task', config)
    prompt = root / 'kit/prompts/task.txt'
    prompt.parent.mkdir()
    prompt.write_bytes(row['problem_statement'].encode())
    assert kit.audit_case(row, info, suite, [('gold', b'never_export_this_secret')], prompt)['nonbase_leak_matches'] == 0
    (suite / 'bad.txt').write_text('never_export_this_secret')
    with pytest.raises(RuntimeError, match='non-base leak'):
        kit.audit_case(row, info, suite, [('gold', b'never_export_this_secret')], prompt)
    prompt.write_text('changed')
    with pytest.raises(RuntimeError, match='byte-exact'):
        kit.audit_case(row, info, suite, [], prompt)
    (suite / 'bad.txt').unlink()
    official = 'Issue supplies this example: acreate.alters_data = True\n'
    approved = dict(row, instance_id='django__django-16256', problem_statement=official)
    prompt.write_bytes(official.encode())
    patterns = [('gold_added_line', b'acreate.alters_data = True')]
    audit = kit.audit_case(approved, info, suite, patterns, prompt)
    assert len(audit['provided_prompt_exceptions']) == 1 and audit['nonbase_leak_matches'] == 0
    assert audit['base_exception_matches'] == 0
    for key in ('astropy__astropy-13398', 'scikit-learn__scikit-learn-26194',
                'astropy__astropy-14182', 'sphinx-doc__sphinx-7462'):
        approved_prompt = tmp_path / (key + '.txt')
        approved_prompt.write_bytes(official.encode())
        reviewed = kit.audit_case(dict(approved, instance_id=key), info, suite, patterns, approved_prompt)
        assert len(reviewed['provided_prompt_exceptions']) == 1
    (suite / 'bad.txt').write_text('acreate.alters_data = True')
    with pytest.raises(RuntimeError, match='non-base leak'):
        kit.audit_case(approved, info, suite, patterns, prompt)
    prompt.write_text(official + 'edited')
    with pytest.raises(RuntimeError, match='byte-exact'):
        kit.audit_case(approved, info, suite, patterns, prompt)


def test_leak_fingerprints_do_not_match_inside_other_identifiers():
    patterns = [('gold_added_line', b'a = []')]
    assert kit.scan({'runner.py': b'extra = []'}, patterns, {}) == ([], [])
    matches, leaks = kit.scan({'runner.py': b'a = []'}, patterns, {'base.py': b'extra = []'})
    assert len(matches) == len(leaks) == 1
    assert kit.scan({'runner.py': b'a = []'}, patterns, {'base.py': b'a = []'})[1] == []
    assert not kit.fingerprint_in(b'test_new', b'test_newer()')
    assert kit.fingerprint_in(b'test_new', b'test_new()')
    assert kit.scan({}, [], {}) == ([], [])


def test_logged_errors_are_not_silently_ignored(tmp_path):
    log = tmp_path / 'setup.log'
    with pytest.raises(RuntimeError, match='command exit 7'):
        kit.run_logged(['sh', '-c', 'echo failure; exit 7'], tmp_path, log, 5)
    assert log.read_text() == 'failure\n'
    kit.run_logged(['sh', '-c', 'exit 1'], tmp_path, log, 5, allow_failure=True)


def test_readme_native_bootstrap_is_pinned_and_includes_ready_recipes(tmp_path, monkeypatch):
    (tmp_path / 'kit').mkdir()
    tooling = tmp_path / 'tooling'
    (tooling / 'info').mkdir(parents=True)
    (tooling / 'info/index.json').write_text(json.dumps(dict(version='2.10.0', build='0')))
    (tooling / 'micromamba.tar.bz2').write_bytes(b'bootstrap archive')
    monkeypatch.setattr(kit, 'git', lambda *args, **kwargs: b'framework-sha\n')
    config = dict(environment=dict(python='3.9', commands=['micromamba activate "$ENV_PREFIX"']),
                  measured_base_seconds=1.2, timeout_s=120)
    kit.readme(tmp_path, ['task', 'unready'], dict(task=dict(status='ready', selection=config),
               unready=dict(status='blocked')), tooling / 'bin/micromamba')
    text = (tmp_path / 'kit/README.md').read_text()
    assert 'Vacant@framework-sha' in text and 'python=3.11 -y' in text
    assert kit.digest(tooling / 'micromamba.tar.bz2') in text
    assert 'micromamba activate "$ENV_PREFIX"' in text and '## task' in text
    assert '## unready' not in text


@pytest.mark.parametrize('blocked', [False, True])
def test_incremental_admission_and_failed_instance_retention(tmp_path, monkeypatch, blocked):
    dataset = tmp_path / 'dataset.jsonl'
    rows = [dict(instance_id=key, repo='owner/repo', test_patch='', patch='', FAIL_TO_PASS='[]')
            for key in ('first', 'second')]
    dataset.write_text('\n'.join(json.dumps(row) for row in rows) + '\n')
    selection = tmp_path / 'selection.json'
    selection.write_text(json.dumps(dict(final_instance_ids=['first'], status='complete' if blocked else 'incomplete')))
    monkeypatch.setattr(kit, 'version', lambda _: kit.selection_tools.HARNESS_VERSION)
    monkeypatch.setattr(kit.selection_tools, 'DATASET_CONTENT_SHA256',
                        kit.selection_tools.digest(kit.selection_tools.canonical(rows)))
    prepared = []

    def prepare(row, *args):
        prepared.append(row['instance_id'])
        return dict(instance_id=row['instance_id'], status='blocked' if blocked else 'ready',
                    phase='native environment setup', error='setup failed' if blocked else '')

    class FinishedInspection(Exception):
        pass

    def readme(root, admitted, cases, mamba):
        if len(admitted) == 2:
            raise FinishedInspection()
        selection.write_text(json.dumps(dict(final_instance_ids=['first', 'second'], status='incomplete')))

    monkeypatch.setattr(kit, 'prepare', prepare)
    monkeypatch.setattr(kit, 'readme', readme)
    monkeypatch.setattr(kit, 'finalize', lambda *args: pytest.fail('must not publish an incomplete/failed bank'))
    root = tmp_path / 'build'
    argv = ['--dataset-json', str(dataset), '--selection', str(selection), '--root', str(root),
            '--micromamba', str(tmp_path / 'mamba'), '--jobs', '1']
    if blocked:
        assert kit.main(argv) == 2
        state = json.loads((root / 'KIT.json').read_text())
        assert state['admitted'] == ['first'] and state['cases']['first']['status'] == 'blocked'
        assert 'first' in json.loads((root / 'BLOCKERS.json').read_text())
    else:
        with pytest.raises(FinishedInspection):
            kit.main(argv)
        state = json.loads((root / 'KIT.json').read_text())
        assert prepared == ['first', 'second'] == state['admitted'] == state['ready']
    assert state['pushed'] is False


def test_completed_cap_redraw_reconciles_63_incremental_admissions(tmp_path, monkeypatch):
    keys = ['astropy__astropy-13033'] + [f'final-{index}' for index in range(62)]
    rows = [dict(instance_id=key, repo='owner/repo', test_patch='', patch='', FAIL_TO_PASS='[]') for key in keys]
    dataset = tmp_path / 'dataset.jsonl'
    dataset.write_text('\n'.join(json.dumps(row) for row in rows))
    selection = tmp_path / 'selection.json'
    selection.write_text(json.dumps(dict(final_instance_ids=keys[1:], status='complete')))
    root = tmp_path / 'build'
    root.mkdir()
    cases = {key: dict(instance_id=key, status='ready') for key in keys}
    kit.save(root / 'KIT.json', dict(admitted=keys, cases=cases))
    monkeypatch.setattr(kit, 'version', lambda _: kit.selection_tools.HARNESS_VERSION)
    monkeypatch.setattr(kit.selection_tools, 'DATASET_CONTENT_SHA256',
                        kit.selection_tools.digest(kit.selection_tools.canonical(rows)))
    monkeypatch.setattr(kit, 'current_case', lambda _: True)
    monkeypatch.setattr(kit, 'readme', lambda *args: None)
    monkeypatch.setattr(kit, 'prepare', lambda *args: pytest.fail('ready bank must not rebuild'))

    def finalized(root, state, lookup):
        assert state['admitted'] == state['ready'] == keys[1:]
        assert len(state['cases']) == 62
        assert state['superseded_cases'][keys[0]]['case'] == cases[keys[0]]

    monkeypatch.setattr(kit, 'finalize', finalized)
    assert kit.main(['--dataset-json', str(dataset), '--selection', str(selection), '--root', str(root),
                     '--micromamba', str(tmp_path / 'mamba')]) == 0


def test_reconciliation_keeps_incomplete_cases_and_records_late_results(tmp_path):
    state = dict(admitted=['kept', 'pending'], cases={})
    kit.reconcile_selection(state, dict(status='incomplete', final_instance_ids=[]), tmp_path)
    assert state['admitted'] == ['kept', 'pending']
    complete = dict(status='complete', final_instance_ids=['kept'])
    kit.reconcile_selection(state, complete, tmp_path)
    state['cases']['pending'] = dict(status='blocked', error='late failure')
    kit.reconcile_selection(state, complete, tmp_path)
    assert state['admitted'] == ['kept'] and state['cases'] == {}
    assert state['superseded_cases']['pending']['case']['error'] == 'late failure'


def test_completed_redraw_removes_tracked_and_late_exports_before_finalization(tmp_path, monkeypatch):
    public = tmp_path / 'kit'
    for key in ('old', 'new'):
        (public / 'gates' / key).mkdir(parents=True)
        (public / 'gates' / key / 'gate.py').write_text('pass\n')
        (public / 'prompts').mkdir(exist_ok=True)
        (public / 'prompts' / (key + '.txt')).write_text(key)
    for name in ('README.md', '.gitignore'):
        (public / name).write_text('')
    kit.git(public, 'init', '--quiet', '--template=')
    kit.git(public, 'symbolic-ref', 'HEAD', 'refs/heads/sandbox-devin-kit-v4')
    kit.git(public, 'add', '--', 'gates/old', 'prompts/old.txt')
    kit.git(public, '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid',
            'commit', '--quiet', '-m', 'Previous bank')
    state = dict(admitted=['old', 'new'], cases={key: dict(snapshot={}) for key in ('old', 'new')})
    state['superseded_cases'] = dict(new=dict(reason='Earlier provisional selection'))
    completed = dict(status='complete', final_instance_ids=['new'])
    kit.reconcile_selection(state, dict(completed, status='incomplete'), public)
    assert (public / 'prompts/old.txt').exists()
    with pytest.raises(RuntimeError, match='unexpected'):
        kit.audit_exports(public, ['new'])
    kit.reconcile_selection(state, completed, public)
    assert not (public / 'gates/old').exists() and not (public / 'prompts/old.txt').exists()
    (public / 'gates/old').mkdir()
    (public / 'prompts/old.txt').write_text('late export')
    kit.reconcile_selection(state, completed, public, active=['old'])
    assert (public / 'gates/old').exists() and (public / 'prompts/old.txt').exists()
    kit.reconcile_selection(state, completed, public)
    kit.audit_exports(public, ['new'])
    monkeypatch.setattr(kit.v3, 'needles', lambda *args: [])
    monkeypatch.setattr(kit, 'audit_case', lambda *args: {})
    monkeypatch.setattr(kit, 'save', lambda *args: None)
    for role in ('AUTHOR', 'COMMITTER'):
        monkeypatch.setenv('GIT_' + role + '_NAME', 'Fixture')
        monkeypatch.setenv('GIT_' + role + '_EMAIL', 'fixture@example.invalid')
    kit.finalize(tmp_path, state, dict(new={}))
    tracked = kit.git(public, 'ls-tree', '-r', '--name-only', 'HEAD').decode().splitlines()
    assert set(tracked) == {'.gitignore', 'README.md', 'gates/new/gate.py', 'prompts/new.txt'}


@pytest.mark.parametrize('folder', ['gates', 'prompts'])
def test_export_audit_rejects_unlisted_task_directories(tmp_path, folder):
    public = tmp_path / 'kit'
    kit.audit_exports(public, [])
    (public / folder / 'unlisted').mkdir(parents=True)
    with pytest.raises(RuntimeError, match='unexpected'):
        kit.finalize(tmp_path, dict(admitted=[], cases={}), {})


def test_export_audit_refuses_missing_bank_exports(tmp_path):
    with pytest.raises(RuntimeError, match='missing'):
        kit.audit_exports(tmp_path, ['missing'])
