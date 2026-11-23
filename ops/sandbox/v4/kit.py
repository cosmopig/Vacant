"""Incremental native v4 kit preparation. Creates local artifacts only; never pushes."""
import argparse
import ast
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
import hashlib
from importlib.metadata import version
import json
import os
from pathlib import Path
import re
import runpy
import shlex
import shutil
import signal
import subprocess
import sys
import time
import traceback
import warnings

from ops.sandbox.v3 import kit as v3
from ops.sandbox.v3 import patch as v3_patch
from ops.sandbox.v3 import select as selection_tools
from ops.sandbox.v3.recipes import secure_downloads, temporary_requirements
from ops.sandbox.v4 import gate, gate_runtime


OWNER_APPROVALS = {
    'sphinx-doc__sphinx-8595': dict(date='2026-11-23', approved=True,
        step_c='Freeze base-passing existing tests from tests/test_ext_autodoc.py; official scoring unchanged.'),
    'matplotlib__matplotlib-23299': dict(date='2026-11-23', approved=True,
        step_c='Freeze only collected base-passing official P2P nodes; record the four uncollected labels as omitted.'),
    'matplotlib__matplotlib-26466': dict(date='2026-11-23', approved=True,
        step_a='Use the general owner-approved compiled-package artifact/rebuild policy.'),
    'compiled_packages': dict(date='2026-11-23', approved=True,
        step_a='Copy untracked compiled artifacts and generated version files; if compiled sources change, rebuild only the pristine base with the instance recipe.'),
    'django__django-16256': dict(date='2026-11-23', approved=True,
        provided_prompt_exception=True, byte_exact=True, same_text_all_arms=True,
        scope='Only the byte-exact official problem statement; no gate or implementation exception.'),
}
STOP_REQUESTED = False
NATIVE_POLICY_VERSION = 2
REPAIR_OMISSIONS = {'matplotlib__matplotlib-21568', 'sphinx-doc__sphinx-7462', 'astropy__astropy-13398'}
for _key in ('astropy__astropy-13398', 'scikit-learn__scikit-learn-26194',
             'astropy__astropy-14182', 'sphinx-doc__sphinx-7462'):
    OWNER_APPROVALS[_key] = dict(OWNER_APPROVALS['django__django-16256'])
OWNER_APPROVALS['native_repairs'] = dict(date='2026-11-23', approved=True,
    policy='Harness version specs are authoritative; isolate xarray user site; restore pytest SCM version; omit measured base-failing/warning-erroring P2P nodes for the three approved cases.')
OWNER_APPROVALS['replacement_policy'] = dict(date='2026-11-23', approved=True,
    policy='After one honest repair attempt replace any still-unready instance by the next feasible seeded-draw candidate under the same cap rule; redraw calibration only if affected.')


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def current_case(result):
    measured = result.get('selection', {}).get('measurement', {})
    return (measured.get('native_artifact_policy') == NATIVE_POLICY_VERSION and
            measured.get('gate_runtime_sha256') == digest(gate_runtime.__file__) and
            measured.get('node_runner_sha256') == digest(Path(__file__).with_name('node_runner.py')))


def save(path, value):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, indent=2) + '\n')
    temporary.replace(path)


def git(root, *args, data=None):
    env = {key: value for key, value in os.environ.items() if not key.startswith('GIT_')}
    env.update(GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM='1',
               GIT_AUTHOR_NAME='Devin AI', GIT_COMMITTER_NAME='Devin AI',
               GIT_AUTHOR_EMAIL='devin-ai@users.noreply.github.com',
               GIT_COMMITTER_EMAIL='devin-ai@users.noreply.github.com')
    result = subprocess.run(['git', '-C', str(root), *args], input=data, env=env,
                            capture_output=True, timeout=900)
    if result.returncode:
        raise RuntimeError('git ' + ' '.join(args[:3]) + ': ' + result.stderr.decode(errors='replace'))
    return result.stdout


def snapshot(row, root, source=None):
    key = row['instance_id']
    case = root / 'instances' / key
    case.mkdir(parents=True, exist_ok=True)
    saved = case / 'snapshot.json'
    if saved.exists():
        return json.loads(saved.read_text())
    imported = root / 'sources' / (key + '.git')
    imported.mkdir(parents=True, exist_ok=True)
    git(imported, 'init', '--bare', '--quiet', '--template=')
    git(imported, 'fetch', '--depth', '1', '--no-tags',
        source or 'https://github.com/' + row['repo'] + '.git', row['base_commit'])
    tree = git(imported, 'rev-parse', row['base_commit'] + '^{tree}').decode().strip()
    sha = git(imported, 'commit-tree', tree, '-m', 'Base workspace').decode().strip()
    branch = 'sandbox-v4/' + key
    git(imported, 'update-ref', 'refs/heads/' + branch, sha)
    workspace = root / 'kit' / key
    workspace.parent.mkdir(parents=True, exist_ok=True)
    git(root, 'clone', '--quiet', '--single-branch', '--branch', branch, str(imported), str(workspace))
    if git(workspace, 'rev-parse', 'HEAD^{tree}').decode().strip() != tree:
        raise RuntimeError('base snapshot tree mismatch')
    if b'\nparent ' in b'\n' + git(workspace, 'cat-file', '-p', 'HEAD').split(b'\n\n', 1)[0]:
        raise RuntimeError('snapshot is not history-free')
    result = dict(branch=branch, sha=sha, base_commit=row['base_commit'], base_tree=tree,
                  workspace=str(workspace), imported=str(imported), parent_count=0, exact_base_tree=True)
    save(saved, result)
    return result


def resolve_nodes(workspace, row, omissions):
    def canonical(label):
        return re.sub(r'^(test\w*) \((\S+)\.\1\)$', r'\1 (\2)', label)

    labels = json.loads(row['PASS_TO_PASS'])
    if not labels and row.get('instance_id') == 'sphinx-doc__sphinx-8595':
        path = 'tests/test_ext_autodoc.py'
        existing = v3.symbols(workspace, [path])
        if not existing:
            raise ValueError('approved Sphinx base test file has no existing tests')
        return dict(django=False, selectors=[dict(kind='function', label=entry['name'], file=path)
                                             for entry in existing])
    retained = []
    for label in labels:
        parts = label.split('::')
        if len(parts) > 2 and (workspace / parts[0]).is_file():
            with warnings.catch_warnings():
                warnings.simplefilter('ignore', SyntaxWarning)
                tree = ast.parse((workspace / parts[0]).read_bytes())
            names = {node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)}
            names.update(node.id for node in ast.walk(tree) if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store))
            if any(name.isidentifier() and name not in names for name in parts[1:-1]):
                omissions.append(label)
                continue
        retained.append(label)
    labels = retained
    originals = {canonical(label): label for label in labels}
    if len(originals) != len(labels):
        raise ValueError('ambiguous P2P label aliases')
    adapted = dict(row, PASS_TO_PASS=json.dumps(list(originals)),
                   FAIL_TO_PASS=json.dumps([canonical(label) for label in json.loads(row['FAIL_TO_PASS'])]))
    missing = []
    config = v3.resolve(workspace, adapted, missing)
    for target in config['selectors']:
        target['label'] = originals[target['label']]
    omissions.extend(originals[label] for label in missing)
    return config


def freeze_base(broad, report, seconds, environment, row, omissions):
    key = row['instance_id']
    extra = {}
    if key in {'sphinx-doc__sphinx-8595', 'matplotlib__matplotlib-23299'} | REPAIR_OMISSIONS:
        if report['pytest_exitcode'] not in (0, 1):
            raise ValueError('base discovery had collection/environment errors')
        passed = set(report['passed']) - set(report['skipped']) - set(report['failed']) - set(report['deselected'])
        mapping = {label: sorted(set(nodes) & passed) for label, nodes in report['label_nodes'].items()
                   if set(nodes) & passed}
        omitted = [target['label'] for target in broad['selectors'] if target['label'] not in mapping]
        omissions.extend(omitted)
        extra = dict(omitted_uncollected_labels=[label for label, nodes in report['label_nodes'].items() if not nodes],
                     base_nonpassing_nodes=sorted(set(report['selected']) - passed),
                     step_c_exception=OWNER_APPROVALS.get(key, OWNER_APPROVALS['native_repairs']))
        broad = dict(broad, selectors=[target for target in broad['selectors'] if target['label'] in mapping])
        report = dict(report, selected=sorted(passed), passed=sorted(passed), skipped=[], failed=[],
                      deselected=[], pytest_exitcode=0, label_nodes=mapping)
    config = v3.freeze(broad, report, seconds, environment)
    config.update(extra)
    config['omitted_nonbase_labels'] = omissions
    return config


def restore_setup(workspace, commands):
    targets = set()
    for command in commands:
        if command.startswith('sed '):
            tokens = shlex.split(command)
            if len(tokens) != 4 or tokens[:2] != ['sed', '-i']:
                raise ValueError('unsupported tracked setup edit: ' + command)
            path = Path(tokens[3])
            if path.is_absolute() or '..' in path.parts:
                raise ValueError('unsafe setup target: ' + str(path))
            targets.add(path)
    for path in targets:
        if any(parent.is_symlink() for parent in [workspace / path, *(workspace / path).parents]):
            raise ValueError('setup target uses a symlink: ' + str(path))
        (workspace / path).write_bytes(git(workspace, 'show', 'HEAD:' + path.as_posix()))


def native_version_commands(row):
    code = ('try:\n from importlib.metadata import version\nexcept ImportError:\n'
            ' from pkg_resources import get_distribution\n version = lambda name: get_distribution(name).version\n'
            'print(version(' + repr(row['repo'].split('/')[-1]) + '))')
    return ['SETUPTOOLS_SCM_PRETEND_VERSION="$(python -I -c ' + shlex.quote(code) + ')"',
            'export SETUPTOOLS_SCM_PRETEND_VERSION']


def native_recipe(row, env_script=None, settings=None):
    if env_script is None or settings is None:
        from swebench.harness.test_spec.test_spec import make_test_spec
        from swebench.harness.constants import MAP_REPO_VERSION_TO_SPECS
        env_script = make_test_spec(row).env_script_list
        settings = MAP_REPO_VERSION_TO_SPECS[row['repo']][row['version']]
    key, python = row['instance_id'], settings['python']
    runner_environment = {}
    if row['repo'] == 'pydata/xarray':
        runner_environment['PYTHONNOUSERSITE'] = '1'
    if row['repo'] == 'pytest-dev/pytest':
        runner_environment['SETUPTOOLS_SCM_PRETEND_VERSION'] = row['version']
    commands = [*(f'export {name}={shlex.quote(value)}' for name, value in runner_environment.items()),
                f'ENV_PREFIX="$KIT_ROOT/.envs/{key}"',
                f'mkdir -p "$KIT_ROOT/.setup/{key}"', f'cd "$KIT_ROOT/.setup/{key}"']
    extras = []
    for command in env_script:
        if command.startswith('source '):
            continue
        command = command.replace('conda create -n testbed', 'micromamba create -c conda-forge -p "$ENV_PREFIX"')
        command = command.replace('conda env create --file environment.yml',
                                  'micromamba env create -p "$ENV_PREFIX" --file environment.yml -y')
        command = command.replace('conda activate testbed', 'micromamba activate "$ENV_PREFIX"')
        command = command.replace('conda install ', 'micromamba install -c conda-forge -p "$ENV_PREFIX" ')
        command = command.replace('conda create -c conda-forge -n testbed',
                                  'micromamba create -c conda-forge -p "$ENV_PREFIX"')
        command = command.replace('conda env update ', 'micromamba env update -p "$ENV_PREFIX" ')
        if command.startswith('cat <<'):
            extras.extend(re.findall(r'(?m)^\s*- (nbconvert\[execute\][^\n]*)$', command))
            command = command.replace('nbconvert[execute]', 'nbconvert')
        commands.append(command)
    commands = temporary_requirements(commands)
    commands.extend('python -m pip install ' + shlex.quote(specifier) for specifier in extras)
    legacy = tuple(map(int, python.split('.'))) < (3, 8)
    commands += ['python -m pip install ' + ('pip==21.3.1 setuptools==59.6.0 wheel==0.37.1' if legacy else
                                           'pip==23.3.2 setuptools==68.1.2 wheel==0.41.2'),
                 f'cd "$KIT_ROOT/{key}"']
    for command in secure_downloads(settings.get('pre_install', [])):
        if 'apt-get' in command:
            packages = ('graphviz ghostscript' if row['repo'] == 'matplotlib/matplotlib' else 'graphviz')
            commands.append('micromamba install -c conda-forge -p "$ENV_PREFIX" -y ' + packages)
        else:
            commands.append(command.replace('/testbed', '$PWD'))
    install = settings.get('install', 'true')
    if row['repo'] == 'astropy/astropy' and int(row.get('version', '0').split('.')[0]) >= 4:
        commands += ['python -m pip install "Cython==0.29.30" "extension-helpers==1.2.0" "setuptools-scm<8"',
                     'python setup.py build_ext --inplace --force']
        install = install.replace('pip install ', 'pip install --no-build-isolation ')
    commands += [install]
    if row['repo'] != 'pytest-dev/pytest':
        commands += ['python -m pip install pytest==' + ('6.2.5' if legacy else '7.4.4') +
                 (' pytest-django==4.5.2' if row['repo'] == 'django/django' else '') +
                 (' roman==4.1' if row['repo'] == 'sphinx-doc/sphinx' else '') +
                     (' py==1.10.0' if row['repo'] == 'sympy/sympy' else '')]
    if row['repo'] == 'matplotlib/matplotlib':
        commands += ['python -m pip install "pandas<2" "setuptools-scm<8"']
    if key in REPAIR_OMISSIONS or row['repo'] == 'pydata/xarray':
        pins = settings.get('pip_packages', [])
        if pins:
            commands += ['python -m pip install ' + ' '.join(map(shlex.quote, pins))]
    if row['repo'] == 'pydata/xarray':
        commands += ['python -m pip install "exceptiongroup==1.1.3"']
    rebuild = [command.replace('/testbed', '$PWD').replace('/tmp/', '$VACANT_BUILD_TMP/')
               for command in secure_downloads(settings.get('pre_install', []))
               if 'apt-get' not in command and not command.startswith('sed ')]
    return dict(instance_id=key, python=python, commands=commands, runner_environment=runner_environment,
                base_rebuild_commands=[*rebuild, *native_version_commands(row), 'python setup.py build_ext --inplace'],
                native_adaptations=['micromamba/conda-forge native prefixes, not Docker images',
                    'pinned compatible pip/setuptools/wheel',
                    'apt steps replaced by environment-local conda tools; no host upgrade'])


def run_logged(arguments, cwd, path, timeout, env=None, allow_failure=False):
    with path.open('ab') as stream:
        process = subprocess.Popen(arguments, cwd=cwd, stdout=stream, stderr=subprocess.STDOUT,
                                   env=env, start_new_session=True)
        try:
            code = process.wait(timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()
            raise RuntimeError(f'command timeout; see {path}') from exc
    if code and not allow_failure:
        raise RuntimeError(f'command exit {code}; see {path}')


def base_files(info):
    workspace = Path(info['workspace'])
    found = {}
    listing = git(workspace, 'ls-tree', '-rz', 'HEAD')
    entries = [record.split(b'\t', 1) for record in listing.split(b'\0') if record]
    blobs = [(header.split()[2], name.decode()) for header, name in entries if header.split()[1] == b'blob']
    raw = git(workspace, 'cat-file', '--batch', data=b''.join(oid + b'\n' for oid, _ in blobs))
    offset = 0
    for _, name in blobs:
        end = raw.index(b'\n', offset)
        size = int(raw[offset:end].split()[-1])
        found[name] = raw[end + 1:end + 1 + size]
        offset = end + size + 2
    return found


def fingerprint_in(needle, content):
    left_word = needle[:1].isalnum() or needle[:1] == b'_'
    right_word = needle[-1:].isalnum() or needle[-1:] == b'_'
    offset = content.find(needle)
    while offset >= 0:
        end = offset + len(needle)
        left = content[offset - 1:offset] if offset else b''
        right = content[end:end + 1]
        if (not left_word or not (left.isalnum() or left == b'_')) and (
                not right_word or not (right.isalnum() or right == b'_')):
            return True
        offset = content.find(needle, offset + 1)
    return False


def scan(files, patterns, baseline):
    matches, leaks = [], []
    for kind, needle in patterns:
        base_match = next((name for name, data in baseline.items() if fingerprint_in(needle, data)), None)
        for path, content in files.items():
            if fingerprint_in(needle, content):
                record = dict(kind=kind, needle=needle.decode(), file=path,
                              base_matches=[base_match] if base_match is not None else [])
                matches.append(record)
                if base_match is None:
                    leaks.append(record)
    return matches, leaks


def audit_case(row, info, suite, patterns, prompt):
    files = base_files(info)
    if max(map(len, files.values()), default=0) > 100_000_000:
        raise RuntimeError('base contains a file larger than 100 MB')
    exported = {f'gates/{row["instance_id"]}/{name}': data for name, data in v3.file_bytes(suite).items()}
    exported['prompts/' + row['instance_id'] + '.txt'] = prompt.read_bytes()
    if prompt.read_bytes() != row['problem_statement'].encode():
        raise RuntimeError('prompt is not byte-exact')
    relevant = [(kind, needle) for kind, needle in patterns if any(fingerprint_in(needle, data) for data in exported.values())]
    matches, leaks = scan(exported, relevant, files)
    provided = []
    if OWNER_APPROVALS.get(row['instance_id'], {}).get('provided_prompt_exception'):
        provided = [record for record in leaks if record['file'] == 'prompts/' + row['instance_id'] + '.txt']
        leaks = [record for record in leaks if record not in provided]
    if leaks:
        raise RuntimeError('non-base leak matches: ' + json.dumps(leaks[:5]))
    return dict(exact_base_tree=True, parent_count=0, nonbase_leak_matches=0,
                base_exception_matches=len(matches) - len(provided), files=len(files),
                largest_file_bytes=max(map(len, files.values()), default=0), patterns=len(patterns),
                provided_prompt_exceptions=provided)


def gate_controls(workspace, suite, config, row):
    runtime = runpy.run_path(str(suite / 'gate_runtime.py'))
    check, refusal = runtime['check'], runtime['Refusal']
    modules = {'pytest-dev/pytest': '_pytest', 'scikit-learn/scikit-learn': 'sklearn',
               'matplotlib/matplotlib': 'matplotlib', 'pylint-dev/pylint': 'pylint',
               'psf/requests': 'requests', 'sphinx-doc/sphinx': 'sphinx',
               'mwaskom/seaborn': 'seaborn', 'pydata/xarray': 'xarray'}
    module = modules.get(row['repo'], row['repo'].split('/')[0])
    implementation = next(workspace / prefix / module / '__init__.py' for prefix in ('', 'src', 'lib')
                          if (workspace / prefix / module / '__init__.py').is_file())
    test = workspace / Path(config['selectors'][0]['file']).with_name('test_v4_kit_control.py')
    conftest = workspace / 'conftest.py'
    manifest = workspace / 'VACANT_TESTS.txt'
    originals = {path: path.read_bytes() if path.exists() else None for path in (implementation, test, conftest, manifest)}
    name = 'test_v4_kit_red_green_control'
    node = test.relative_to(workspace).as_posix() + '::' + name
    try:
        implementation.write_bytes(originals[implementation] + b'\n_v4_kit_control = 1\n')
        test.write_bytes((originals[test] or b'') + ('\n\ndef ' + name + '():\n    import ' + module +
                        '\n    assert getattr(' + module + ', "_v4_kit_control", 0) == 1\n').encode())
        manifest.write_text(node + '\n')
        accepted = check(workspace, suite)
        conftest.write_bytes((originals[conftest] or b'') + ('\n\n_v4_old_setup = globals().get("pytest_runtest_setup")\n'
            'def pytest_runtest_setup(item):\n    if item.nodeid == ' + repr(config['selectors'][0]['label']) +
            ':\n        import pytest\n        pytest.fail("v4 kit P2P control")\n'
            '    if _v4_old_setup is not None:\n        _v4_old_setup(item)\n').encode())
        try:
            check(workspace, suite)
        except refusal as exc:
            if not str(exc).startswith('Step C refused;'):
                raise
            return dict(red_green=accepted, p2p_regression='refused at C', test=node)
        raise RuntimeError('gate accepted a deliberate P2P regression')
    finally:
        for path, data in originals.items():
            if data is None:
                path.unlink(missing_ok=True)
            else:
                path.write_bytes(data)


def native_controls(workspace, suite, config, row, case, env):
    script = ('import json,sys; from pathlib import Path; '
              'from ops.sandbox.v4.kit import gate_controls,save; '
              'save(Path(sys.argv[5]), gate_controls(Path(sys.argv[1]),Path(sys.argv[2]),'
              'json.loads(Path(sys.argv[3]).read_text()),dict(repo=sys.argv[4])))')
    source = case / 'control-input.json'
    save(source, config)
    run_logged([sys.executable, '-c', script, str(workspace), str(suite), str(source),
                row['repo'], str(case / 'controls.json')], Path(__file__).resolve().parents[3],
                case / 'controls.log', 2 * config['timeout_s'] + 30, env)
    return json.loads((case / 'controls.json').read_text())


def prepare(row, root, mamba, patterns):
    key = row['instance_id']
    case = root / 'instances' / key
    case.mkdir(parents=True, exist_ok=True)
    phase = 'snapshot'
    try:
        info = snapshot(row, root)
        workspace = Path(info['workspace'])
        phase = 'resolve P2P'
        omissions = []
        broad = resolve_nodes(workspace, row, omissions)
        save(case / 'discovery.json', broad)
        environment = native_recipe(row)
        save(case / 'environment.json', environment)
        script = ['set -euo pipefail', 'export KIT_ROOT=' + shlex.quote(str(root / 'kit')),
                  'export MAMBA_ROOT_PREFIX=' + shlex.quote(str(root / 'mamba')),
                  'export PATH=' + shlex.quote(str(mamba.parent)) + ':"$PATH"',
                  'eval "$(micromamba shell hook --shell bash)"', *environment['commands']]
        (case / 'setup.sh').write_text('\n'.join(script) + '\n')
        phase = 'native environment setup'
        env = dict(os.environ, OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1', MKL_NUM_THREADS='1',
                   CMAKE_BUILD_PARALLEL_LEVEL='2', MAX_JOBS='2', NPY_NUM_BUILD_JOBS='2')
        env.update(environment['runner_environment'])
        restore_setup(workspace, environment['commands'])
        run_logged(['bash', str(case / 'setup.sh')], root / 'kit', case / 'setup.log', 3600, env)
        interpreter = root / 'kit/.envs' / key / 'bin/python'
        env['PATH'] = str(interpreter.parent) + os.pathsep + env.get('PATH', os.defpath)
        phase = 'P2P discovery and measurement'
        runner = Path(v3.__file__).with_name('p2p_runner.py')
        report_path = case / 'discovery-report.json'
        started = time.monotonic()
        discovery = [str(Path(__file__).with_name('discover.py'))]
        if key != 'matplotlib__matplotlib-23299':
            discovery.append('--strict')
        discovery.append(str(runner))
        run_logged([str(interpreter), '-I', '-B', *discovery, str(workspace), str(case / 'discovery.json'),
                    str(report_path)], workspace, case / 'discovery.log', 1800, env, allow_failure=True)
        elapsed = time.monotonic() - started
        report = json.loads(report_path.read_text())
        if any(len(nodes) > 1 for nodes in report.get('native_aliases', {}).values()):
            raise ValueError('ambiguous native parameter-node alias')
        config = freeze_base(broad, report, elapsed, environment, row, omissions)
        config['runner_environment'] = environment['runner_environment']
        config['base_rebuild_commands'] = environment['base_rebuild_commands'] if (workspace / 'setup.py').is_file() else []
        tracked = {os.fsdecode(name) for name in git(workspace, 'ls-files', '-z').split(b'\0') if name}
        config['generated_compiled_sources'] = {name: gate_runtime.compiled_digest(data, workspace, interpreter)
            for name, (mode, data) in v3_patch._files(workspace, set()).items()
            if name not in tracked and Path(name).suffix.lower() in gate_runtime.COMPILED_SOURCES}
        config['nodeid_paths'] = dict(workspace=str(workspace), environment=str(interpreter.parent.parent))
        save(case / 'selection.json', config)
        phase = 'frozen P2P confirmation'
        run_logged([str(interpreter), '-I', '-B', str(Path(__file__).with_name('discover.py')), '--strict', str(runner), str(workspace), str(case / 'selection.json'),
                    str(case / 'base-report.json')], workspace, case / 'base.log', config['timeout_s'], env)
        base_report = json.loads((case / 'base-report.json').read_text())
        if base_report['selected'] != base_report['passed'] or any(base_report[k] for k in ('failed', 'skipped', 'deselected')):
            raise RuntimeError('frozen nodes did not all execute and pass')
        config['measurement'] = dict(runner_sha256=digest(runner), selectors_sha256=v3.selectors_sha256(config),
                    base_report_sha256=digest(case / 'base-report.json'), native=True, no_docker_images=True,
                    native_artifact_policy=NATIVE_POLICY_VERSION, gate_runtime_sha256=digest(gate_runtime.__file__))
        phase = 'v4 gate controls'
        suite = gate.write_suite(root / 'kit', key, config)
        config['measurement'].update(gate_runtime_sha256=digest(suite / 'gate_runtime.py'),
                                     node_runner_sha256=digest(suite / 'node_runner.py'))
        controls = native_controls(workspace, suite, config, row, case, env)
        phase = 'leak audit'
        prompt = root / 'kit/prompts' / (key + '.txt')
        prompt.parent.mkdir(exist_ok=True)
        prompt.write_bytes(row['problem_statement'].encode())
        audit = audit_case(row, info, suite, patterns, prompt)
        result = dict(status='ready', instance_id=key, snapshot=info, selection=config,
                      controls=controls, audit=audit, ready_at=time.time())
        save(case / 'ready.json', result)
        return result
    except Exception as exc:
        result = dict(status='blocked', instance_id=key, phase=phase, error=str(exc),
                      traceback=traceback.format_exc(), logs=str(case))
        save(case / 'blocked.json', result)
        return result
    finally:
        prefix = root / 'kit/.envs' / key
        if prefix.is_dir():
            shutil.rmtree(prefix)


def readme(root, admitted, cases, mamba):
    metadata = json.loads((mamba.parents[1] / 'info/index.json').read_text())
    archive = mamba.parents[1] / 'micromamba.tar.bz2'
    url = ('https://api.anaconda.org/download/conda-forge/micromamba/' + metadata['version'] +
           '/linux-64/micromamba-' + metadata['version'] + '-' + metadata['build'] + '.tar.bz2')
    vacant_sha = git(Path(__file__).resolve().parents[3], 'rev-parse', 'HEAD').decode().strip()
    text = ['# v4 native task kit',
        'Clone only your assigned history-free `sandbox-v4/<id>` into `<id>/`. Read `prompts/<id>.txt`.',
        'Do not look up upstream fixes, SWE-bench data, another branch, or another session.',
        'Do not open a pull request; the pushed branch is the only deliverable.',
        'Kit root bootstrap (Linux x86_64; native environments, no Docker pulls):', '```bash',
        'KIT_ROOT="$PWD"', 'mkdir -p .tools', 'curl --fail --location --proto "=https" --tlsv1.2 ' +
        shlex.quote(url) + ' --output .tools/micromamba.tar.bz2',
        'echo "' + digest(archive) + '  .tools/micromamba.tar.bz2" | sha256sum --check',
        'tar -xjf .tools/micromamba.tar.bz2 -C .tools bin/micromamba',
        'export PATH="$KIT_ROOT/.tools/bin:$PATH"', 'export MAMBA_ROOT_PREFIX="$KIT_ROOT/.mamba"',
        'eval "$(micromamba shell hook --shell bash)"', '```',
        'Vacant wrapper: Python >=3.11; tests: the instance Python, never a stdlib shim.',
        '```bash', 'micromamba create -c conda-forge -p "$KIT_ROOT/.venv" python=3.11 -y',
        '.venv/bin/python -m pip install git+https://github.com/cosmopig/Vacant@' + vacant_sha, '```',
        'Vacant arm: write root VACANT_TESTS.txt, one explicit test node ID per line.',
        'A: pristine base plus only listed candidate test files must exhibit a test-body failure.',
        'B: every listed node must execute and pass on the candidate. C: frozen pre-existing P2P.',
        'Collection/import/setup failures and skips do not qualify as red. Every refusal names step and nodes.',
        'Only the root manifest is dropped from handback patches; retain your tests.',
        'At most 3 submissions. Do not edit gates/. Keep base HEAD unchanged until gating.',
        'Run from <id>/, with receipts under this kit root:', '```bash',
        'TIMEOUT=$(../.venv/bin/python -c \'import json; print(json.load(open("../gates/<id>/selection.json"))["timeout_s"])\')',
        '../.venv/bin/vacant run --workspace . --suite ../gates/<id> --run-dir ../receipts/<id>-N '
        '--test-timeout "$TIMEOUT" --sandbox none --retry none -- true', '```',
        'Gate acceptance is not hidden correctness, a security boundary, or a zero-config installation effect.']
    for key in admitted:
        if key not in cases or cases[key]['status'] != 'ready':
            continue
        config = cases[key]['selection']
        text += ['\n## ' + key, f'Python {config["environment"]["python"]}; measured base P2P '
                 f'{config["measured_base_seconds"]:.3f}s; timeout {config["timeout_s"]}s.',
                 '```bash', *config['environment']['commands'], '```']
        if config.get('base_rebuild_commands'):
            text += ['Step A base-only native rebuild recipe when compiled sources change:',
                     '```bash', *config['base_rebuild_commands'], '```']
    (root / 'kit/README.md').write_text('\n\n'.join(text) + '\n')
    (root / 'kit/.gitignore').write_text('/receipts/\n/.venv/\n/.envs/\n/.tools/\n/.setup/\n/.mamba/\n' +
                                       ''.join('/' + key + '/\n' for key in admitted))


def finalize(root, state, lookup):
    patterns = list(dict.fromkeys(p for key in state['admitted'] for p in v3.needles(lookup[key], {})))
    public_root = root / 'kit'
    common = [(public_root / name).read_bytes() for name in ('README.md', '.gitignore')]
    unchecked = {needle for _, needle in patterns if any(fingerprint_in(needle, data) for data in common)}
    for key in state['admitted']:
        info = state['cases'][key]['snapshot']
        state['cases'][key]['audit'] = audit_case(lookup[key], info, public_root / 'gates' / key,
                                                   patterns, public_root / 'prompts' / (key + '.txt'))
        if unchecked:
            baseline = base_files(info)
            unchecked = {needle for needle in unchecked if not any(fingerprint_in(needle, data) for data in baseline.values())}
    if unchecked:
        raise RuntimeError('README/gitignore has non-base leak matches; publishing blocked')
    git(public_root, 'init', '--quiet', '--template=')
    git(public_root, 'symbolic-ref', 'HEAD', 'refs/heads/sandbox-devin-kit-v4')
    paths = ['README.md', '.gitignore']
    for key in state['admitted']:
        paths.extend(['gates/' + key, 'prompts/' + key + '.txt'])
    git(public_root, 'add', '--', *paths)
    git(public_root, 'commit', '--quiet', '-m', 'Frozen v4 native task kit')
    state.update(status='ready; all 62 audited; local branches only', final_leak_audit='pass',
                 kit_sha=git(public_root, 'rev-parse', 'HEAD').decode().strip(), pushed=False)
    save(root / 'KIT.json', state)
    save(Path(__file__).with_name('KIT.json'), state)


def reconcile_selection(state, selected):
    if not selected['status'].startswith('complete'):
        return
    final = set(selected['final_instance_ids'])
    superseded = (set(state['admitted']) | set(state['cases'])) - final
    for key in superseded:
        record = state.setdefault('superseded_cases', {}).setdefault(key, dict(
            reason='Not present in the completed selector bank after cap redraw.'))
        if key in state['cases']:
            record['case'] = state['cases'].pop(key)
    state['admitted'] = [key for key in state['admitted'] if key in final]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--selection', type=Path, default=Path(__file__).with_name('SELECTION.json'))
    parser.add_argument('--dataset-json', type=Path, required=True)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--micromamba', type=Path, required=True)
    parser.add_argument('--jobs', type=int, choices=(1, 2), default=2)
    args = parser.parse_args(argv)
    if version('swebench') != selection_tools.HARNESS_VERSION:
        raise ValueError('requires swebench==' + selection_tools.HARNESS_VERSION)
    rows = list(map(json.loads, args.dataset_json.read_text().splitlines()))
    if selection_tools.digest(selection_tools.canonical(rows)) != selection_tools.DATASET_CONTENT_SHA256:
        raise ValueError('dataset differs from frozen revision')
    lookup = {row['instance_id']: row for row in rows}
    root = args.root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    (root / 'kit').mkdir(exist_ok=True)
    state_file = root / 'KIT.json'
    state = json.loads(state_file.read_text()) if state_file.exists() else dict(
        status='preparing', admitted=[], cases={}, kit_branch='sandbox-devin-kit-v4', pushed=False)
    state['owner_approvals'] = json.loads(json.dumps(OWNER_APPROVALS))
    state['status'] = 'preparing'
    state['cases'] = {key: result for key, result in state['cases'].items()
                      if result['status'] != 'ready' or current_case(result)}
    for ready in (root / 'instances').glob('*/ready.json'):
        result = json.loads(ready.read_text())
        if result['instance_id'] in state['admitted'] and current_case(result):
            state['cases'][result['instance_id']] = result
    first_ten = root / 'first-10.json'
    inflight = {}
    with ThreadPoolExecutor(max_workers=args.jobs) as executor:
        while True:
            selected = json.loads(args.selection.read_text())
            reconcile_selection(state, selected)
            for key in selected['final_instance_ids']:
                if key not in state['admitted']:
                    state['admitted'].append(key)
            if selected['status'].startswith('complete') and len(state['admitted']) > 62:
                raise RuntimeError('selector admitted more than 62 IDs; owner decision required, none dropped')
            patterns = list(dict.fromkeys(pattern for key in state['admitted'] for pattern in v3.needles(lookup[key], {})))
            pending = [key for key in state['admitted'] if key not in state['cases'] and key not in inflight.values()]
            pending.sort(key=lambda key: (key not in OWNER_APPROVALS, lookup[key]['repo'] != 'sympy/sympy'))
            for key in ([] if STOP_REQUESTED or (root / 'PAUSE').exists() else pending[:args.jobs - len(inflight)]):
                if shutil.disk_usage(root).free < 25 * 1024 ** 3:
                    raise RuntimeError('native builder paused below 25 GiB free; selector left untouched')
                inflight[executor.submit(prepare, lookup[key], root, args.micromamba.resolve(), patterns)] = key
                print('START ' + key, flush=True)
            completed, _ = wait(inflight, timeout=30, return_when=FIRST_COMPLETED) if inflight else (set(), set())
            for future in completed:
                key = inflight.pop(future)
                result = future.result()
                state['cases'][key] = result
                print(result['status'].upper() + ' ' + key + ' ' + result.get('error', ''), flush=True)
                if result['status'] == 'blocked':
                    save(root / 'BLOCKERS.json', {k: v for k, v in state['cases'].items() if v['status'] == 'blocked'})
            reconcile_selection(state, selected)
            state['ready'] = [key for key in state['admitted'] if state['cases'].get(key, {}).get('status') == 'ready']
            state['inflight'] = list(inflight.values())
            state['selector_status'] = selected['status']
            state['updated_at'] = time.time()
            for key in OWNER_APPROVALS:
                result = state['cases'].get(key, {})
                if result.get('status') == 'ready':
                    state['owner_approvals'][key].update(
                        frozen_nodes=[target['label'] for target in result['selection']['selectors']],
                        omitted_nodes=result['selection'].get('omitted_nonbase_labels', []))
            save(state_file, state)
            save(root / 'BLOCKERS.json', {key: result for key, result in state['cases'].items() if result['status'] == 'blocked'})
            if (STOP_REQUESTED or (root / 'PAUSE').exists()) and not inflight:
                return 0
            readme(root, state['admitted'], state['cases'], args.micromamba.resolve())
            if len(state['ready']) >= 10 and not first_ten.exists():
                save(first_ten, dict(instance_ids=state['ready'][:10], ready_at=time.time()))
                print('MILESTONE first 10 kit-ready: ' + json.dumps(state['ready'][:10]), flush=True)
            if selected['status'].startswith('complete'):
                if set(selected['final_instance_ids']) != set(state['admitted']):
                    raise RuntimeError('frozen/admitted IDs differ from selector final bank; owner decision required')
                if len(state['ready']) == 62 and not inflight:
                    finalize(root, state, lookup)
                    return 0
                if not inflight and all(key in state['cases'] for key in state['admitted']):
                    state['status'] = 'blocked; no instance dropped'
                    save(state_file, state)
                    return 2
            if not inflight:
                time.sleep(30)


if __name__ == '__main__':
    def stop_after_active(signum, frame):
        global STOP_REQUESTED
        STOP_REQUESTED = True

    signal.signal(signal.SIGTERM, stop_after_active)
    raise SystemExit(main())
