"""指定題庫的可見材料匯出；不建立 git 分支、不匯出隱藏驗收。"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import sys

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ops.sandbox.run import gate_suite
from ops.sandbox.score import TASKS, SKIP


def build(bank, out):
    bank, out = Path(bank).resolve(), Path(out).resolve()
    if bank == out or bank in out.parents:
        raise ValueError('kit output must be outside the bank')
    tasks = sorted(p for p in bank.iterdir() if (p / 'task.json').is_file())
    if not tasks:
        raise ValueError('empty bank')
    out.mkdir(parents=True)
    (out / 'gates').mkdir()
    (out / 'prompts').mkdir()
    for task in tasks:
        shutil.copytree(task / 'repo', out / task.name,
                        ignore=shutil.ignore_patterns(*SKIP), symlinks=True)
        gate_suite(task, out / 'gates' / task.name, portable=True)
        prompt = json.loads((task / 'task.json').read_text())['prompt']
        (out / 'prompts' / f'{task.name}.txt').write_text(prompt)
    (out / '.gitignore').write_text('/receipts/\n')
    (out / 'README.md').write_text(
        'Visible task workspaces, exact prompts and visible-only gates; no hidden tests or '
        'reference solutions are exported. Install Vacant and pytest in `.venv` at this '
        'kit root; submit from a task directory using a new `../receipts/<task>-N` '
        'run directory for each manual gate submission.\n')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bank', type=Path, default=TASKS)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args(argv)
    build(args.bank, args.out)
    print(f'Kit written to {args.out}')


if __name__ == '__main__':
    main()
