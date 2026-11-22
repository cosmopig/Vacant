"""只從 base snapshot 對映原有 P2P 測試；不匯出 test patch 或參考修復。"""
import argparse
import ast
import json
import math
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
    new_parameter_functions = set()
    parameter_added = False
    for line in row['test_patch'].splitlines():
        if line.startswith('@@') or line.startswith('+++'):
            parameter_added = False
        elif line.startswith('+') and '@pytest.mark.parametrize' in line:
            parameter_added = True
        elif line.startswith(('+', ' ')) and (definition := re.match(r'\s*(?:async )?def (test\w+)\(', line[1:])):
            if parameter_added:
                new_parameter_functions.add(definition.group(1))
            parameter_added = False
    for label in labels:
        if '.py::' in label:
            path = label.split('::', 1)[0]
            target = dict(kind='nodeid', label=label, file=path)
            name = label.split('::')[-1].split('[', 1)[0]
            if '[' in label and name in new_parameter_functions:
                tree = ast.parse((root / path).read_text(encoding='utf-8-sig'))
                functions = [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name]
                if functions and not any('parametrize' in ast.dump(d) for n in functions for d in n.decorator_list):
                    if omissions is not None:
                        omissions.append(label)
                    continue
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
            if inherited_names is None:
                inherited_names = {r['name'] for r in symbols(root, [str(p.relative_to(root)) for p in root.rglob('*.py')])}
            if method not in inherited_names:
                if omissions is not None:
                    omissions.append(label)
                continue
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


def freeze(config, report, seconds, environment):
    if not math.isfinite(seconds) or seconds <= 0:
        raise ValueError('invalid measured runtime')
    if report['pytest_exitcode'] != 0 or report['failed'] or report['deselected']:
        raise ValueError('base has failing or deselected variants')
    passed = set(report['passed']) - set(report['skipped'])
    mapping = {label: sorted(set(nodes) & passed) for label, nodes in report['label_nodes'].items()}
    if not mapping or set(mapping) != {t['label'] for t in config['selectors']} or not all(mapping.values()):
        raise ValueError('uncovered pre-existing P2P labels')
    if set(report['selected']) != passed | set(report['skipped']):
        raise ValueError('base variants did not execute')
    nodes = sorted({node for values in mapping.values() for node in values})
    return dict(django=config['django'], selectors=[dict(kind='exact', label=node, file=node.split('::')[0])
                for node in nodes], label_nodes=mapping, base_skipped_nodes=report['skipped'],
                measured_base_seconds=seconds, timeout_s=max(120, math.ceil(3 * seconds + 30)),
                interpreter=f".envs/{environment['instance_id']}/bin/python", environment=environment)


WRAPPER = '''import json, os, pathlib, subprocess

def main():
    root = next(p for p in pathlib.Path(os.getcwd()).parents
                if (p / ".venv/bin/python").is_file() and (p / "gates").is_dir())
    suite = root / "gates" / INSTANCE
    config = json.loads((suite / "selection.json").read_text())
    interpreter = root / config["interpreter"]
    assert interpreter.is_file(), "Install the instance environment: " + str(interpreter)
    proc = subprocess.run([str(interpreter), "-I", str(suite / "runner.py"),
                           os.getcwd(), str(suite / "selection.json")],
                          capture_output=True, text=True, timeout=config["timeout_s"] - 10,
                          env={**os.environ, "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1"})
    assert proc.returncode == 0, proc.stderr + proc.stdout
'''

README = '''# Task workspaces and pre-existing-test gates

Vacant and its wrapper require Python >=3.11. Repository tests use separate
per-instance interpreters, not this Python. At this kit root:

```bash
PYTHON="${PYTHON:-python3.11}"
"$PYTHON" -m venv .venv
. .venv/bin/activate
python -m pip install git+https://github.com/cosmopig/Vacant 'pytest>=7,<8' 'setuptools<81'
```

Clone only your assigned `sandbox-v3/INSTANCE` branch into `INSTANCE/` under
this kit root (`git clone --single-branch --depth 1 --branch ...`). Read
`prompts/INSTANCE.txt` at the kit root: it is exactly the problem statement.
The workspace is an independent history-free base snapshot. With Conda
initialized, use the instance's Python version and harness setup commands below
from this kit root, creating `.envs/INSTANCE/bin/python`. Do not substitute a
newer interpreter. No environment is bundled with the workspace.
Install all dependencies needed by the selected tests, not only the project's
minimal runtime dependencies. The scikit-learn workspace needs pandas; use
the harness constraints below rather than separately upgrading NumPy/SciPy.
The commands are taken from the official harness environment and repository
installation specifications, adapting only environment/workspace paths. Pytest
and pytest-django are added where listed. Django uses its own DiscoverRunner
for database setup; other projects load their environment's pytest plugins.
System provisioning commands require operator privileges and must be reviewed
for the host; the measured images already contain these system packages.
Do not install a released copy of the project in place of the workspace source.

Only the gated arm uses the selected pre-existing tests and feedback. They
reveal which existing tests must stay green; this is part of the intervention.
Other arms do not inspect gates. Newly added tests are excluded even when their
labels appear in the passing-test list. There are no newly introduced acceptance tests
or reference fixes here. Concrete base-passing node IDs are frozen, covering
every retained label. Ambiguous descriptions exclude base-skipped variants;
no failing-at-base variant is dropped. Every selected case must actually pass: skipped,
deselected, missing and unexecuted cases cause refusal with their IDs in feedback.

From `INSTANCE/`, with a fresh receipts directory each time:

```bash
TIMEOUT=$(../.venv/bin/python -c 'import json; print(json.load(open("../gates/INSTANCE/selection.json"))["timeout_s"])')
../.venv/bin/vacant run --workspace . --suite ../gates/INSTANCE \\
  --run-dir ../receipts/INSTANCE-N --test-timeout "$TIMEOUT" \\
  --sandbox none --retry none -- true
```

Use at most three submissions (N=1,2,3). The runner invokes only selected test
nodes through `.envs/INSTANCE/bin/python` and pytest with the repository's
own fixtures/conftest. BLAS/OMP/MKL threads are fixed to one inside the runner.
Timeouts are max(120, ceil(3 * measured base P2P seconds + 30)), measured in
each pinned official image. It does not run all tests or apply a test patch.
'''


def build(rows, snapshots, out, measurements=None):
    out = Path(out)
    if measurements is None or set(measurements) != set(snapshots):
        raise ValueError('successful per-instance measurements required')
    configs = {key: measurements[key] for key in snapshots}
    out.mkdir(parents=True)
    (out / 'prompts').mkdir()
    (out / 'gates').mkdir()
    for key, config in configs.items():
        (out / 'prompts' / f'{key}.txt').write_text(rows[key]['problem_statement'])
        gate = out / 'gates' / key
        gate.mkdir()
        (gate / 'test_gate.py').write_text(WRAPPER.replace('INSTANCE', repr(key)))
        shutil.copyfile(Path(__file__).with_name('p2p_runner.py'), gate / 'runner.py')
        public = {field: config[field] for field in ('django', 'selectors', 'interpreter', 'timeout_s')}
        (gate / 'selection.json').write_text(json.dumps(public, indent=2) + '\n')
    (out / '.gitignore').write_text('/receipts/\n/.venv/\n/.envs/\n')
    recipes = []
    for key, config in configs.items():
        env = config['environment']
        recipes.append(f"\n## {key}\n\nPython {env['python']}; measured base P2P {config['measured_base_seconds']:.3f}s; "
                       f"gate timeout {config['timeout_s']}s.\n\n```bash\n" + '\n'.join(env['commands']) + '\n```\n')
    (out / 'README.md').write_text(README + ''.join(recipes))
    return configs


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset-json', type=Path, required=True)
    parser.add_argument('--snapshots', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--measurements', type=Path, required=True)
    args = parser.parse_args(argv)
    rows = {r['instance_id']: r for r in map(json.loads, args.dataset_json.read_text().splitlines())}
    snapshots = json.loads(args.snapshots.read_text())
    configs = build(rows, snapshots, args.out, json.loads(args.measurements.read_text()))
    print(json.dumps({key: len(config['selectors']) for key, config in configs.items()}))


if __name__ == '__main__':
    main()
