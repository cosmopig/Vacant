"""Preparation-only collection of existing base nodes; never used by Step C."""
import json
from pathlib import Path
import runpy
import re
import sys


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    strict = bool(argv and argv[0] == '--strict')
    if strict:
        argv.pop(0)
    tree = Path(argv[1])
    sys.path[:0] = [str(path) for path in (tree, tree / 'src', tree / 'lib') if path.is_dir()]
    namespace = runpy.run_path(argv[0])
    original_class = namespace['OnlySelected']
    original_matches = namespace['matches']
    exact = set()

    def canonical(label):
        label = re.sub(r'\[/[^\]]*/([^/\]]+)\]$', r'[/\1]', label)
        return re.sub(r'(?<=\d)_(\d+)\]$', r'\1]', label)

    def matches(item, target):
        return original_matches(item, target) or (strict and target['kind'] == 'nodeid' and target['label'] not in exact and
            item.nodeid.split('::', 1)[0] == target['file'] and canonical(item.nodeid) == canonical(target['label']))

    class CollectedOnly(original_class):
        def __init__(self, targets):
            import pytest

            super().__init__(targets)
            original_collect = self.pytest_collection_modifyitems

            @pytest.hookimpl(hookwrapper=True, tryfirst=True)
            def collect(config, items):
                exact.update(target['label'] for target in self.targets if any(original_matches(item, target) for item in items))
                if not strict:
                    self.targets = [target for target in self.targets
                                    if any(matches(item, target) for item in items)]
                yield from original_collect(config, items)

            self.pytest_collection_modifyitems = collect

    namespace['main'].__globals__['OnlySelected'] = CollectedOnly
    namespace['main'].__globals__['matches'] = matches
    code = namespace['main'](argv[1:])
    if len(argv) == 4 and Path(argv[3]).is_file():
        path = Path(argv[3])
        report = json.loads(path.read_text())
        report['native_aliases'] = {label: nodes for label, nodes in report['label_nodes'].items()
                                    if strict and label not in exact and nodes}
        path.write_text(json.dumps(report, indent=2) + '\n')
    return code


if __name__ == '__main__':
    raise SystemExit(main())
