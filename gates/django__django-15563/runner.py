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
        self.targets = targets

    def pytest_collection_modifyitems(self, config, items):
        import pytest

        seen, keep, drop = set(), [], []
        for item in items:
            selected = [i for i, target in enumerate(self.targets) if matches(item, target)]
            if selected:
                seen.update(selected)
                keep.append(item)
            else:
                drop.append(item)
        missing = [t['label'] for i, t in enumerate(self.targets) if i not in seen]
        if missing or not keep:
            raise pytest.UsageError('Selected pre-existing tests missing: ' + repr(missing))
        config.hook.pytest_deselected(items=drop)
        items[:] = keep


def main(argv=None):
    import pytest

    workspace, selection = map(Path, (argv or sys.argv[1:]))
    workspace = workspace.resolve()
    config = json.loads(selection.read_text())
    os.chdir(workspace)
    sys.path.insert(0, str(workspace))
    targets = config['selectors']
    files = sorted({t['file'] for t in targets})
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
        extra = ['-p', 'pytest_django.plugin']
    return pytest.main(['-q', '--tb=short', '-p', 'no:cacheprovider', *extra, *files],
                       plugins=[OnlySelected(targets)])


if __name__ == '__main__':
    raise SystemExit(main())
