"""只從 base snapshot 對映原有 P2P 測試；不匯出 test patch 或參考修復。"""
import argparse
import ast
import json
from pathlib import Path
import re
import shutil

from ops.sandbox.v3.p2p_runner import first_line


def patch_paths(patch):
    return [line[6:] for line in patch.splitlines() if line.startswith('+++ b/')]


def symbols(root, paths):
    found = []
    for path in sorted(set(paths)):
        source = root / path
        if not source.is_file() or source.suffix != '.py':
            continue
        try:
            tree = ast.parse(source.read_text(encoding='utf-8-sig'))
        except (SyntaxError, UnicodeError):
            continue
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith('test'):
                found.append(dict(file=path, name=node.name, description=first_line(ast.get_docstring(node))))
    return found


def resolve(root, row, omissions=None):
    labels = json.loads(row['PASS_TO_PASS'])
    if not labels or set(labels) & set(json.loads(row['FAIL_TO_PASS'])):
        raise ValueError('empty or overlapping test selections')
    existing = [p for p in patch_paths(row['test_patch']) if (root / p).is_file()]
    index = symbols(root, existing)
    selectors = []
    inherited_names = None
    for label in labels:
        if '.py::' in label:
            path = label.split('::', 1)[0]
            target = dict(kind='nodeid', label=label, file=path)
            name = label.split('::')[-1].split('[', 1)[0]
            if name not in {r['name'] for r in symbols(root, [path])}:
                if inherited_names is None:
                    inherited_names = {r['name'] for r in symbols(root, [str(p.relative_to(root)) for p in root.rglob('*.py')])}
                if name not in inherited_names:
                    if omissions is not None:
                        omissions.append(label)
                    continue
        elif match := re.fullmatch(r'(test\w*) \(([^ ]+)\.([^.]+)\)', label):
            method, module, cls = match.groups()
            paths = [p for p in existing if p.endswith(module.replace('.', '/') + '.py') or
                     p.endswith(module.replace('.', '/') + '/__init__.py')]
            if len(paths) != 1:
                raise ValueError('ambiguous module: ' + label)
            target = dict(kind='unittest', label=label, file=paths[0], method=method, module=module, **{'class': cls})
        else:
            named = [r for r in index if r['name'] == label]
            matched = named or [r for r in index if r['description'] == first_line(label)]
            paths = sorted({r['file'] for r in matched})
            if not paths:
                if omissions is not None:
                    omissions.append(label)
                continue
            selectors.extend(dict(kind='function' if named else 'description', label=label, file=path) for path in paths)
            continue
        if not (root / target['file']).is_file():
            raise ValueError('selected test absent from base: ' + label)
        selectors.append(target)
    if not selectors:
        raise ValueError('no pre-existing tests remain: selected test absent from base')
    return dict(django=(root / 'django/__init__.py').is_file(), selectors=selectors)


def needles(row, base):
    patch = row['test_patch']
    added_functions = set(re.findall(r'^\+\s*(?:async )?def (test\w+)\(', patch, re.M))
    names = set()
    for label in json.loads(row['FAIL_TO_PASS']):
        name = label.split('::')[-1].split('[')[0].split(' (')[0]
        if name in added_functions:
            names.add(name)
    gold = {line[1:].strip() for line in row['patch'].splitlines()
            if line.startswith('+') and not line.startswith('+++') and line[1:].strip()}
    return [('introduced_test_name', s.encode()) for s in sorted(names)] + [
        ('gold_added_line', s.encode()) for s in sorted(gold)]


def scan(files, patterns, base_files):
    matches, leaks = [], []
    for kind, needle in patterns:
        base_match = next((name for name, content in base_files.items() if needle in content), None)
        base_matches = [base_match] if base_match is not None else []
        for path, content in files.items():
            if needle not in content:
                continue
            record = dict(kind=kind, needle=needle.decode(), file=path, base_matches=base_matches)
            matches.append(record)
            if not base_matches:
                leaks.append(record)
    return matches, leaks


def file_bytes(root):
    return {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*')
            if p.is_file() and not p.is_symlink() and '.git' not in p.relative_to(root).parts}


WRAPPER = '''import json, os, pathlib, subprocess

def main():
    root = next(p for p in pathlib.Path(os.getcwd()).parents
                if (p / ".venv/bin/python").is_file() and (p / "gates").is_dir())
    suite = root / "gates" / INSTANCE
    proc = subprocess.run([str(root / ".venv/bin/python"), "-I", str(suite / "runner.py"),
                           os.getcwd(), str(suite / "selection.json")],
                          capture_output=True, text=True, timeout=1800,
                          env={**os.environ, "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1"})
    assert proc.returncode == 0, proc.stdout + proc.stderr
'''

README = '''# Task workspaces and pre-existing-test gates

Vacant requires Python >=3.11. Use **Python 3.11** for these legacy workspaces:
newer interpreters can break base behavior before any edit. At this kit root:

```bash
PYTHON="${PYTHON:-python3.11}"
"$PYTHON" -m venv .venv
. .venv/bin/activate
python -m pip install git+https://github.com/cosmopig/Vacant 'pytest>=7,<8' 'setuptools<81'
```

Clone only your assigned `sandbox-v3/INSTANCE` branch into `INSTANCE/` under
this kit root (`git clone --single-branch --depth 1 --branch ...`). Read
`prompts/INSTANCE.txt` at the kit root: it is exactly the problem statement.
The workspace is an independent history-free base snapshot. Install the
repository's own dependencies using this kit-root environment; no environment
is bundled with the workspace. Django additionally needs `pytest-django`.
Install all dependencies needed by the selected tests, not only the project's
minimal runtime dependencies. The scikit-learn workspace needs pandas (for
example `python -m pip install 'pandas>=1.5,<2.1'` with compatible NumPy/SciPy).
The pytest range supports older repository hooks; setuptools supplies the
legacy distutils compatibility module on Python 3.12. Match any further
repository-specific dependency constraints before using its gate.
Do not install a released copy of the project in place of the workspace source.

Only the gated arm uses the selected pre-existing tests and feedback. They
reveal which existing tests must stay green; this is part of the intervention.
Other arms do not inspect gates. Newly added tests are excluded even when their
labels appear in the passing-test list. There are no newly introduced acceptance tests
or reference fixes here. Parser labels are mapped to base test modules; labels
that describe several inherited/parameterized cases select those same labels,
not all tests in the module. Every selected case must actually pass: skipped,
deselected, missing and unexecuted cases cause refusal with their IDs in feedback.

From `INSTANCE/`, with a fresh receipts directory each time:

```bash
../.venv/bin/vacant run --workspace . --suite ../gates/INSTANCE \\
  --run-dir ../receipts/INSTANCE-N --sandbox none --retry none -- true
```

Use at most three submissions (N=1,2,3). The runner invokes only selected test
labels through the kit-root venv's Python and pytest, with the repository's
own fixtures/conftest. It does not run all tests or apply a separate test patch.
'''


def build(rows, snapshots, out):
    out = Path(out)
    configs = {key: resolve(Path(info['workspace']), rows[key]) for key, info in snapshots.items()}
    out.mkdir(parents=True)
    (out / 'prompts').mkdir()
    (out / 'gates').mkdir()
    for key, config in configs.items():
        (out / 'prompts' / f'{key}.txt').write_text(rows[key]['problem_statement'])
        gate = out / 'gates' / key
        gate.mkdir()
        (gate / 'test_gate.py').write_text(WRAPPER.replace('INSTANCE', repr(key)))
        shutil.copyfile(Path(__file__).with_name('p2p_runner.py'), gate / 'runner.py')
        (gate / 'selection.json').write_text(json.dumps(config, indent=2) + '\n')
    (out / '.gitignore').write_text('/receipts/\n/.venv/\n')
    (out / 'README.md').write_text(README)
    return configs


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset-json', type=Path, required=True)
    parser.add_argument('--snapshots', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args(argv)
    rows = {r['instance_id']: r for r in map(json.loads, args.dataset_json.read_text().splitlines())}
    snapshots = json.loads(args.snapshots.read_text())
    configs = build(rows, snapshots, args.out)
    print(json.dumps({key: len(config['selectors']) for key, config in configs.items()}))


if __name__ == '__main__':
    main()
