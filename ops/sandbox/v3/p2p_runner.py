"""以原有測試的公開選擇標籤執行 pytest，不包含新增驗收測試。"""
import inspect
import json
import os
from pathlib import Path
import sys


def first_line(doc):
    return ' '.join((inspect.cleandoc(doc or '').splitlines() or [''])[0].split())


def matches(item, target):
    if item.nodeid.split('::', 1)[0] != target['file']:
        return False
    kind, label = target['kind'], target['label']
    if kind == 'exact':
        return item.nodeid == label
    if kind == 'nodeid':
        return item.nodeid == label or item.nodeid.split(' ', 1)[0] == label
    if kind == 'function':
        return getattr(item, 'originalname', None) == label or item.name == label
    if kind == 'description':
        return first_line(getattr(item.obj, '__doc__', None)) == first_line(label)
    module = getattr(item.module, '__name__', '')
    cls = getattr(getattr(item, 'cls', None), '__name__', '')
    return (item.name == target['method'] and cls == target['class'] and
            (module == target['module'] or module.endswith('.' + target['module'])))


class OnlySelected:
    def __init__(self, targets):
        import pytest

        self.targets = targets
        self.selected = set()
        self.passed = set()
        self.skipped = set()
        self.deselected = set()
        self.failed = set()
        self.label_nodes = {target['label']: set() for target in targets}

        @pytest.hookimpl(hookwrapper=True, tryfirst=True)
        def collect(config, items):
            seen = set()
            for item in items:
                found = [i for i, target in enumerate(self.targets) if matches(item, target)]
                if found:
                    seen.update(found)
                    self.selected.add(item.nodeid)
                    for index in found:
                        self.label_nodes[self.targets[index]['label']].add(item.nodeid)
            yield
            keep, drop = [], []
            for item in items:
                (keep if item.nodeid in self.selected else drop).append(item)
            self.deselected.update(self.selected - {item.nodeid for item in keep})
            missing = [t['label'] for i, t in enumerate(self.targets) if i not in seen]
            if missing or not keep:
                raise pytest.UsageError('Selected pre-existing tests missing: ' + repr(missing))
            config.hook.pytest_deselected(items=drop)
            items[:] = keep

        self.pytest_collection_modifyitems = collect

    def pytest_deselected(self, items):
        for item in items:
            if any(matches(item, target) for target in self.targets):
                self.deselected.add(item.nodeid)

    def pytest_runtest_logreport(self, report):
        if report.nodeid not in self.selected:
            return
        if report.failed:
            self.failed.add(report.nodeid)
        if report.skipped or hasattr(report, 'wasxfail'):
            self.skipped.add(report.nodeid)
        elif report.when == 'call' and report.passed:
            self.passed.add(report.nodeid)

    def incomplete(self):
        groups = {'skipped': self.skipped, 'deselected': self.deselected,
                  'not passed': self.selected - self.passed - self.skipped - self.deselected}
        for reason, names in groups.items():
            if names:
                print(f'P2P {reason}:\n' + '\n'.join(sorted(names)), file=sys.stderr)
        return any(groups.values())


def main(argv=None):
    for name in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
        os.environ[name] = '1'
    os.environ['PYTEST_DISABLE_PLUGIN_AUTOLOAD'] = '1'
    import pytest

    arguments = argv or sys.argv[1:]
    workspace, selection = map(Path, arguments[:2])
    workspace = workspace.resolve()
    config = json.loads(selection.read_text())
    if not config['django']:
        os.environ.pop('PYTEST_DISABLE_PLUGIN_AUTOLOAD', None)
    os.chdir(workspace)
    sys.path[:0] = [str(path) for path in (workspace, workspace / 'src', workspace / 'lib') if path.is_dir()]
    targets = config['selectors']
    files = sorted({t['file'] for t in targets})
    django_runner = None
    databases = None
    extra = []
    if config['django']:
        sys.path.insert(0, str(workspace / 'tests'))
        os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'test_sqlite')
        import runtests

        labels = sorted({str(Path(path).relative_to('tests')).split('/')[0] for path in files})
        setup = getattr(runtests, 'setup', None) or runtests.setup_run_tests
        parameters = inspect.signature(setup).parameters
        values = dict(verbosity=0, test_labels=labels, parallel=1, start_at=None, start_after=None)
        setup(**{key: value for key, value in values.items() if key in parameters})
        from django.test.runner import DiscoverRunner
        django_runner = DiscoverRunner(verbosity=0, interactive=False)
        django_runner.setup_test_environment()
        databases = django_runner.setup_databases()
        extra = ['-p', 'no:warnings']
    selected = OnlySelected(targets)
    try:
        code = pytest.main(['-q', '--tb=short', '-p', 'no:cacheprovider', *extra, *files], plugins=[selected])
    finally:
        if django_runner is not None:
            django_runner.teardown_databases(databases)
            django_runner.teardown_test_environment()
    if len(arguments) == 3:
        report = {name: sorted(getattr(selected, name)) for name in
                  ('selected', 'passed', 'skipped', 'deselected', 'failed')}
        report.update(pytest_exitcode=int(code), label_nodes={
            label: sorted(nodes) for label, nodes in selected.label_nodes.items()})
        Path(arguments[2]).write_text(json.dumps(report, indent=2) + '\n')
    return 1 if selected.incomplete() else code


if __name__ == '__main__':
    raise SystemExit(main())
