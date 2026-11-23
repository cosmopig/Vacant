"""Runs under instance Python (including 3.6); records exact-node call outcomes."""
import inspect
import json
import os
from pathlib import Path
import sys


class Outcomes:
    def __init__(self, nodes):
        import pytest

        self.nodes = set(nodes)
        self.selected, self.passed, self.failed = set(), set(), set()
        self.body_failed, self.skipped, self.deselected = set(), set(), set()

        @pytest.hookimpl(hookwrapper=True, tryfirst=True)
        def collect(items):
            self.selected.update(item.nodeid for item in items if item.nodeid in self.nodes)
            yield
            keep = [item for item in items if item.nodeid in self.nodes]
            items[:] = keep

        self.pytest_collection_modifyitems = collect

        @pytest.hookimpl(hookwrapper=True)
        def makereport(item, call):
            result = yield
            report = result.get_result()
            code = getattr(getattr(item, 'obj', None), '__code__', None)
            if (item.nodeid in self.nodes and report.when == 'call' and report.failed
                    and not hasattr(report, 'wasxfail') and call.excinfo is not None
                    and code is not None
                    and any(entry.frame.code.raw is code for entry in call.excinfo.traceback)):
                self.body_failed.add(item.nodeid)

        self.pytest_runtest_makereport = makereport

    def pytest_deselected(self, items):
        self.deselected.update(item.nodeid for item in items if item.nodeid in self.nodes)

    def pytest_runtest_logreport(self, report):
        if report.nodeid not in self.nodes:
            return
        if report.failed:
            self.failed.add(report.nodeid)
        if report.skipped or hasattr(report, 'wasxfail'):
            self.skipped.add(report.nodeid)
        elif report.when == 'call' and report.passed:
            self.passed.add(report.nodeid)


def main():
    for name in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
        os.environ[name] = '1'
    workspace, request, report = map(Path, sys.argv[1:])
    config = json.loads(request.read_text())
    if config['django']:
        os.environ['PYTEST_DISABLE_PLUGIN_AUTOLOAD'] = '1'
    else:
        os.environ.pop('PYTEST_DISABLE_PLUGIN_AUTOLOAD', None)
    os.chdir(workspace)
    sys.path[:0] = [str(path) for path in (workspace, workspace / 'src', workspace / 'lib') if path.is_dir()]
    import pytest

    files = sorted({node.split('::', 1)[0] for node in config['nodes']})
    runner, databases, extra = None, None, []
    if config['django']:
        sys.path.insert(0, str(workspace / 'tests'))
        os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'test_sqlite')
        import runtests
        labels = sorted({str(Path(path).relative_to('tests')).split('/')[0] for path in files})
        setup = getattr(runtests, 'setup', None) or runtests.setup_run_tests
        values = dict(verbosity=0, test_labels=labels, parallel=1, start_at=None, start_after=None)
        parameters = inspect.signature(setup).parameters
        setup(**{key: value for key, value in values.items() if key in parameters})
        from django.test.runner import DiscoverRunner
        runner = DiscoverRunner(verbosity=0, interactive=False)
        runner.setup_test_environment()
        databases = runner.setup_databases()
        extra = ['-p', 'no:warnings']
    outcomes = Outcomes(config['nodes'])
    try:
        code = pytest.main(['-q', '--tb=short', '--continue-on-collection-errors', '-p', 'no:cacheprovider',
                            *extra, *files], plugins=[outcomes])
    finally:
        if runner is not None:
            runner.teardown_databases(databases)
            runner.teardown_test_environment()
    evidence = {key: sorted(getattr(outcomes, key)) for key in
                ('selected', 'passed', 'failed', 'body_failed', 'skipped', 'deselected')}
    evidence['pytest_exitcode'] = int(code)
    report.write_text(json.dumps(evidence, indent=2) + '\n')
    return int(code)


if __name__ == '__main__':
    raise SystemExit(main())
