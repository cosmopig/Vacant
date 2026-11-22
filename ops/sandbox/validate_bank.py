"""題庫正負控制與明示規格溯源；靜態引用檢查不代替需求人工審查。"""
from __future__ import annotations

import argparse
import ast
import io
import json
from pathlib import Path
import re
import shutil
import sys
import tempfile
import tokenize

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ops.sandbox.score import score


def validate_task(task):
    task = Path(task)
    errors = []
    try:
        meta = json.loads((task / 'task.json').read_text())
        for key in ('id', 'category', 'prompt', 'visible_test_cmd'):
            if not isinstance(meta.get(key), str) or not meta[key]:
                errors.append('missing metadata: ' + key)
        if meta.get('id') != task.name:
            errors.append('id differs from directory')
        spec = (task / 'repo/SPEC.md').read_text()
        clauses = set(re.findall(r'^#{1,6}\s+§(\d+)\b', spec, re.M))
        if not clauses:
            errors.append('no numbered SPEC clauses')
        visible = [p.read_text(errors='replace') for p in (task / 'repo').rglob('*')
                   if p.is_file() and not p.is_symlink() and '__pycache__' not in p.parts]
        hidden = list((task / 'hidden').rglob('*.py'))
        count = 0
        for path in hidden:
            source = path.read_text()
            if source.strip() and any(source.strip() in text for text in visible):
                errors.append(f'hidden file leaked: {path.name}')
            comments = [t for t in tokenize.generate_tokens(io.StringIO(source).readline)
                        if t.type == tokenize.COMMENT]
            for node in ast.walk(ast.parse(source)):
                if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) or not node.name.startswith('test_'):
                    continue
                count += 1
                if any(re.search(r'\b' + re.escape(node.name) + r'\b', text) for text in visible):
                    errors.append('hidden test name leaked: ' + node.name)
                start = min([node.lineno] + [d.lineno for d in node.decorator_list]) - 1
                refs = {ref for t in comments if start <= t.start[0] <= node.end_lineno
                        for ref in re.findall(r'#\s*SPEC\s+§(\d+)\b', t.string)}
                if not refs:
                    errors.append('missing SPEC reference: ' + node.name)
                for ref in refs - clauses:
                    errors.append(f'unknown SPEC §{ref}: {node.name}')
        if not count:
            errors.append('no hidden test functions')
        if errors:
            return dict(task=task.name, ok=False, errors=errors)
        negative = score(task, task / 'repo')
        with tempfile.TemporaryDirectory(prefix='bank-solution-') as temp:
            workspace = Path(temp) / 'ws'
            shutil.copytree(task / 'repo', workspace)
            shutil.copytree(task / 'solution', workspace, dirs_exist_ok=True)
            positive = score(task, workspace)
        if negative['hidden_pass']:
            errors.append('untouched workspace passes hidden tests')
        if not positive['visible_pass'] or not positive['hidden_pass'] or positive['error']:
            errors.append('solution fails: ' + json.dumps(positive))
        if negative['error'] and ('timeout' in negative['error'] or not negative['n_failed']):
            errors.append('negative control scorer error: ' + negative['error'])
        return dict(task=task.name, ok=not errors, errors=errors,
                    hidden_tests=count, negative=negative, positive=positive)
    except (OSError, ValueError, SyntaxError, tokenize.TokenError) as exc:
        return dict(task=task.name, ok=False, errors=[f'{type(exc).__name__}: {exc}'])


def validate_bank(bank):
    tasks = sorted(p for p in Path(bank).iterdir() if p.is_dir() and (p / 'task.json').exists())
    if not tasks:
        raise ValueError('empty bank')
    return [validate_task(task) for task in tasks]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('bank_dir', type=Path)
    args = parser.parse_args(argv)
    try:
        rows = validate_bank(args.bank_dir)
    except (OSError, ValueError) as exc:
        print(f'FAIL: {exc}')
        return 1
    for row in rows:
        print(f"{row['task']}: " + ('PASS (original hidden fails; solution visible+hidden pass; SPEC references and isolation OK)'
                                   if row['ok'] else 'FAIL: ' + '; '.join(row['errors'])))
    passed = sum(row['ok'] for row in rows)
    print(f'{passed}/{len(rows)} tasks valid')
    return 0 if passed == len(rows) else 1


if __name__ == '__main__':
    raise SystemExit(main())
