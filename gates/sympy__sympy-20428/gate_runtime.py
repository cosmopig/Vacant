"""Kit-Python coordinator for the agent-test red/green and existing P2P gate."""
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import runpy
import shlex
import shutil
import signal
import subprocess
import tarfile
import tempfile
import time


COMPILED_SOURCES = {'.c', '.cpp', '.pyx', '.h', '.cc', '.cxx', '.hh', '.hpp', '.hxx',
                    '.pxd', '.pxi', '.f', '.f90', '.f95', '.cu', '.cuh', '.rs'}
GENERATED_VERSIONS = {'_version.py', 'version.py', '__version__.py', '_version_generated.py'}


class Refusal(AssertionError):
    def __init__(self, step, nodes, reason):
        super().__init__('Step ' + step + ' refused; nodes: ' + ', '.join(nodes) + '\n' + reason)


def manifest(workspace):
    path = workspace / 'VACANT_TESTS.txt'
    if not path.is_file() or path.is_symlink():
        raise Refusal('A', ['VACANT_TESTS.txt'], 'Missing regular VACANT_TESTS.txt manifest (one test node ID per line).')
    try:
        nodes = list(dict.fromkeys(line.strip() for line in path.read_text().splitlines() if line.strip()))
    except UnicodeError as exc:
        raise Refusal('A', ['VACANT_TESTS.txt'], 'Manifest must be UTF-8 text.') from exc
    if not nodes:
        raise Refusal('A', ['VACANT_TESTS.txt'], 'Empty VACANT_TESTS.txt manifest.')
    for node in nodes:
        filename, separator, name = node.partition('::')
        relative = PurePosixPath(filename)
        if (not separator or not name or relative.is_absolute() or '..' in relative.parts
                or relative.as_posix() != filename or filename.startswith('-') or '\\' in filename
                or relative.suffix != '.py' or any(part.startswith('.') for part in relative.parts)):
            raise Refusal('A', [node], 'Expected a workspace-relative Python test file and explicit ::node ID.')
        source = workspace / filename
        if not source.is_file() or any(p.is_symlink() for p in [source, *source.parents] if p != workspace.parent):
            raise Refusal('A', [node], 'Listed test file is missing or uses a symlink.')
    return nodes


def command(arguments, cwd, deadline, step, nodes):
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise Refusal(step, nodes, 'Per-instance gate timeout exhausted.')
    env = {k: v for k, v in os.environ.items() if not k.startswith('GIT_')}
    env.update(PYTEST_DISABLE_PLUGIN_AUTOLOAD='1', OPENBLAS_NUM_THREADS='1',
               OMP_NUM_THREADS='1', MKL_NUM_THREADS='1')
    process = subprocess.Popen(arguments, cwd=cwd, env=env, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, start_new_session=True)
    try:
        stdout, stderr = process.communicate(timeout=remaining)
    except subprocess.TimeoutExpired as exc:
        os.killpg(process.pid, signal.SIGKILL)
        process.communicate()
        raise Refusal(step, nodes, 'Per-instance gate timeout exhausted.') from exc
    return process.returncode, stdout, stderr


def compiled_digest(data, workspace, interpreter, origin=None):
    for path in sorted({workspace, origin or workspace}, key=lambda item: len(os.fspath(item)), reverse=True):
        data = data.replace(os.fsencode(path), b'<WORKSPACE>')
    return hashlib.sha256(data.replace(os.fsencode(interpreter.parent.parent), b'<ENV_PREFIX>')).hexdigest()


def native_base(base, workspace, origin, baseline, normalization, config, interpreter, deadline, nodes):
    candidate = normalization['_files'](workspace, set())
    generated = config.get('generated_compiled_sources', {})
    changed = [name for name in baseline.keys() | candidate.keys()
               if Path(name).suffix.lower() in COMPILED_SOURCES and baseline.get(name) != candidate.get(name)
               and not (name not in baseline and name in candidate and
                        compiled_digest(candidate[name][1], workspace, interpreter, origin) == generated.get(name))]
    code, output, errors = command(['git', 'ls-files', '-z'], origin, deadline, 'A', nodes)
    if code:
        raise Refusal('A', nodes, 'Cannot identify untracked build artifacts: ' + errors.decode(errors='replace'))
    tracked = {os.fsdecode(name) for name in output.split(b'\0') if name}
    for directory, dirs, names in os.walk(workspace, followlinks=False):
        dirs[:] = [name for name in dirs if name not in {'.git', '.venv', '.envs', 'venv', '__pycache__'}
                   and not (Path(directory) / name).is_symlink()]
        for name in names:
            source = Path(directory) / name
            relative = source.relative_to(workspace).as_posix()
            if relative in tracked:
                continue
            binary = source.suffix.lower() in {'.so', '.pyd'}
            version_file = (name in GENERATED_VERSIONS and not source.is_symlink() and
                            re.search(br'generated|setuptools.scm|versioneer', source.read_bytes()[:2048], re.I))
            if not version_file and not (binary and not changed):
                continue
            target = base / relative
            if source.is_symlink() or any(parent.is_symlink() for parent in [target, *target.parents]):
                raise Refusal('A', nodes, 'Build artifact uses a symlink: ' + relative)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
    if changed:
        commands = config.get('base_rebuild_commands', [])
        if not commands:
            raise Refusal('A', nodes, 'Compiled sources changed but the instance base rebuild recipe is missing: ' + ', '.join(sorted(changed)))
        temporary = base.parent / 'native-build'
        temporary.mkdir()
        script = '\n'.join(['set -euo pipefail', 'export PATH=' + shlex.quote(str(interpreter.parent)) + ':"$PATH"',
                            'export VACANT_BUILD_TMP=' + shlex.quote(str(temporary)), *commands])
        code, stdout, stderr = command(['bash', '-c', script], base, deadline, 'A', nodes)
        if code:
            raise Refusal('A', nodes, 'Pristine base extension rebuild failed: ' + ', '.join(sorted(changed)) +
                          '\n' + stdout.decode(errors='replace') + stderr.decode(errors='replace'))


def check(workspace, suite, base_workspace=None):
    workspace, suite = Path(workspace).resolve(), Path(suite).resolve()
    base_workspace = Path(base_workspace).resolve() if base_workspace is not None else workspace
    config = json.loads((suite / 'selection.json').read_text())
    nodes = manifest(workspace)
    deadline = time.monotonic() + config['timeout_s'] - 10
    interpreter = suite.parent.parent / config['interpreter']
    if not interpreter.is_file():
        raise Refusal('A', nodes, 'Install the instance interpreter: ' + str(interpreter))
    paths = config.get('nodeid_paths', {})
    for target in config['selectors']:
        for kind, current in (('workspace', workspace), ('environment', interpreter.parent.parent)):
            if paths.get(kind):
                target['label'] = target['label'].replace(paths[kind], str(current))
    with tempfile.TemporaryDirectory(prefix='vacant-v4-gate-') as temporary:
        scratch = Path(temporary)
        base = scratch / 'base'
        base.mkdir()
        code, archive, errors = command(['git', 'archive', '--format=tar', 'HEAD'], base_workspace, deadline, 'A', nodes)
        if code:
            raise Refusal('A', nodes, 'Cannot archive pristine git HEAD: ' + errors.decode(errors='replace'))
        try:
            with tarfile.open(fileobj=io.BytesIO(archive)) as stream:
                stream.extractall(base, filter='data')
            normalization = runpy.run_path(str(suite / 'setup_normalization.py'))
            files = normalization['_files'](base, set())
            normalized = normalization['normalize_setup'](files, config['setup_commands'])
            for name, (mode, data) in normalized.items():
                if (mode, data) != files[name]:
                    (base / name).write_bytes(data)
            native_base(base, workspace, base_workspace, normalized, normalization, config,
                        interpreter, deadline, nodes)
            for filename in {node.split('::', 1)[0] for node in nodes}:
                target = base / filename
                if any(p.is_symlink() for p in [target, *target.parents]):
                    raise ValueError('base test path uses a symlink: ' + filename)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes((workspace / filename).read_bytes())
        except (OSError, ValueError, tarfile.TarError) as exc:
            raise Refusal('A', nodes, 'Cannot prepare pristine base: ' + str(exc)) from exc
        request = scratch / 'nodes.json'
        request.write_text(json.dumps(dict(nodes=nodes, django=config['django'])))
        for step, tree in (('A', base), ('B', workspace)):
            report = scratch / (step + '.json')
            code, stdout, stderr = command([str(interpreter), '-I', '-B', str(suite / 'node_runner.py'),
                                            str(tree), str(request), str(report)], workspace, deadline, step, nodes)
            evidence = json.loads(report.read_text()) if report.is_file() else {}
            if step == 'A':
                ok = bool(set(evidence.get('body_failed', [])) & set(nodes))
                reason = 'At least one listed node must be collected and fail inside its test body on base; collection/import, setup errors and skips do not count.'
            else:
                ok = (code == 0 and set(evidence.get('passed', [])) == set(nodes)
                      and set(evidence.get('selected', [])) == set(nodes)
                      and not any(evidence.get(key) for key in ('failed', 'skipped', 'deselected')))
                reason = 'Every listed node must be collected and pass on the candidate, with none skipped or deselected.'
            if not ok:
                raise Refusal(step, nodes, reason + '\n' + stdout.decode(errors='replace') + stderr.decode(errors='replace'))
        p2p_nodes = [target['label'] for target in config['selectors']]
        selected = scratch / 'p2p-selection.json'
        selected.write_text(json.dumps(config))
        launch = ('import sys,runpy; from pathlib import Path; runner=sys.argv[1]; '
                  'tree=Path(sys.argv[2]); sys.path[:0]=[str(p) for p in '
                  '(tree,tree/"src",tree/"lib") if p.is_dir()]; '
                  'sys.argv=sys.argv[1:]; runpy.run_path(runner,run_name="__main__")')
        code, stdout, stderr = command([str(interpreter), '-I', '-B', '-c', launch,
                                        str(suite / 'p2p_runner.py'), str(workspace), str(selected)],
                                       workspace, deadline, 'C', p2p_nodes)
        if code:
            raise Refusal('C', p2p_nodes, stdout.decode(errors='replace') + stderr.decode(errors='replace'))
    return dict(A='pass', B='pass', C='pass', nodes=nodes)
