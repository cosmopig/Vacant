"""隔離複本上的原始驗收量尺；不是惡意 Python 的安全沙箱。"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import signal
import stat
import subprocess
import sys
import tarfile
import tempfile
import xml.etree.ElementTree as ET

TASKS = Path(__file__).parent / 'tasks'
MAX_FILE = 1024 * 1024
MAX_TOTAL = 10 * MAX_FILE
MAX_FILES = 500
TIMEOUT = 5
SKIP = {'.git', '__pycache__', '.pytest_cache', '.venv', 'node_modules'}


def _copy(source: Path, target: Path) -> None:
    total = count = 0
    target.mkdir(parents=True, exist_ok=True)
    if source.is_symlink():
        raise ValueError('workspace must not be a symlink')
    if source.is_dir():
        for root, dirs, files in os.walk(source, followlinks=False):
            base = Path(root)
            dirs[:] = [d for d in dirs if d not in SKIP and not (base / d).is_symlink()]
            for name in files:
                path = base / name
                info = path.lstat()
                if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_FILE:
                    continue
                total += info.st_size
                count += 1
                if total > MAX_TOTAL or count > MAX_FILES:
                    raise ValueError('workspace copy limit exceeded')
                dest = target / path.relative_to(source)
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(path, dest)
    else:
        with tarfile.open(source) as archive:
            for member in archive:
                rel = Path(member.name)
                if rel.is_absolute() or '..' in rel.parts:
                    raise ValueError('unsafe archive path')
                if any(p in SKIP for p in rel.parts) or not member.isfile() or member.size > MAX_FILE:
                    continue
                total += member.size
                count += 1
                if total > MAX_TOTAL or count > MAX_FILES:
                    raise ValueError('workspace copy limit exceeded')
                dest = target / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                with archive.extractfile(member) as src, dest.open('wb') as out:
                    shutil.copyfileobj(src, out)


def _inventory(path: Path) -> dict:
    return {str(p.relative_to(path)): p.read_bytes() for p in path.rglob('*')
            if p.is_file() and not p.is_symlink() and '__pycache__' not in p.parts}


def _output_ok(spec: dict | None, workspace: Path) -> bool | None:
    if spec is None:
        return None
    rel = Path(spec['path'])
    if rel.is_absolute() or '..' in rel.parts:
        raise ValueError('unsafe output path')
    path = workspace / rel
    if not path.is_file():
        return False
    try:
        if spec['type'] == 'json':
            return json.loads(path.read_text()) == spec['equals']
        if spec['type'] == 'text':
            return all(s in path.read_text() for s in spec['contains'])
        raise ValueError('unknown output check')
    except (UnicodeError, json.JSONDecodeError):
        return False


def _pytest(workspace: Path, suite: str, home: Path) -> tuple[bool, int, int, str | None]:
    report = home / f'{suite}.xml'
    config = home / 'pytest.ini'
    config.write_text('[pytest]\n')
    code = 'import sys,pytest; sys.path.insert(0,sys.argv.pop(1)); raise SystemExit(pytest.main(sys.argv[1:]))'
    cmd = [sys.executable, '-I', '-c', code, str(workspace), suite,
           '-q', '-p', 'no:cacheprovider', '--noconftest', '-c', str(config),
           '--import-mode=importlib', f'--junitxml={report}']
    env = {'PATH': os.defpath, 'HOME': str(home), 'PYTHONNOUSERSITE': '1',
           'PYTEST_DISABLE_PLUGIN_AUTOLOAD': '1', 'LANG': 'C.UTF-8'}
    with (home / f'{suite}.log').open('wb') as log:
        proc = subprocess.Popen(cmd, cwd=workspace, env=env, stdout=log,
                                stderr=subprocess.STDOUT, start_new_session=True)
        try:
            rc = proc.wait(timeout=TIMEOUT)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL)
            proc.wait()
            return False, 0, 1, f'{suite}: timeout'
    if not report.exists():
        return False, 0, 1, f'{suite}: no pytest report (exit {rc})'
    cases = ET.parse(report).findall('.//testcase')
    failed = sum(c.find('failure') is not None or c.find('error') is not None for c in cases)
    passed = sum(c.find('failure') is None and c.find('error') is None and c.find('skipped') is None for c in cases)
    ok = rc == 0 and passed > 0 and failed == 0
    return ok, passed, failed, None if ok else f'{suite}: pytest exit {rc}'


def score(task_dir: str | Path, workspace: str | Path) -> dict:
    result = dict(visible_pass=False, hidden_pass=False, n_passed=0, n_failed=0,
                  tests_modified=False, output_file_ok=None, error=None)
    try:
        task = Path(task_dir)
        meta = json.loads((task / 'task.json').read_text())
        with tempfile.TemporaryDirectory(prefix='vacant-score-') as temp:
            root = Path(temp)
            ws = root / 'ws'
            _copy(Path(workspace), ws)
            original = task / 'repo' / 'tests'
            result['tests_modified'] = _inventory(ws / 'tests') != _inventory(original)
            for name, source in [('tests', original), ('_hidden', task / 'hidden')]:
                dest = ws / name
                if dest.exists():
                    if dest.is_dir():
                        shutil.rmtree(dest)
                    else:
                        dest.unlink()
                _copy(source, dest)
            result['output_file_ok'] = _output_ok(meta.get('output_check'), ws)
            errors = []
            for suite, key in [('tests', 'visible_pass'), ('_hidden', 'hidden_pass')]:
                home = root / suite
                home.mkdir()
                ok, passed, failed, error = _pytest(ws, suite, home)
                result[key] = ok
                result['n_passed'] += passed
                result['n_failed'] += failed
                if error:
                    errors.append(error)
            result['error'] = '; '.join(errors) or None
            if result['output_file_ok'] is False:
                result['hidden_pass'] = False
    except (OSError, ValueError, tarfile.TarError, ET.ParseError, KeyError) as exc:
        result['error'] = f'{type(exc).__name__}: {exc}'
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('task_id', choices=sorted(p.name for p in TASKS.iterdir()))
    parser.add_argument('workspace')
    args = parser.parse_args()
    result = score(TASKS / args.task_id, args.workspace)
    print(json.dumps(result, indent=2))
    return 0 if result['visible_pass'] and result['hidden_pass'] and result['output_file_ok'] is not False else 1


if __name__ == '__main__':
    raise SystemExit(main())
