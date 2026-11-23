"""Reproduce the preregistered paired analysis from the archived 72 cells."""
import json
import math
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[5]))
from ops.sandbox import analyze


def summarize(cells, task_ids):
    expected = {(task, sample, arm) for task in task_ids for sample in (1, 2) for arm in ('A', 'A2', 'G')}
    if (len(task_ids) != 12 or len(cells) != 72
            or {(r['task'], r['sample'], r['arm']) for r in cells} != expected):
        raise ValueError('requires all 72 distinct scheduled comparison cells')
    if any(not r['contamination_reviewed'] for r in cells):
        raise ValueError('all session audits must be complete')
    outputs = {}
    for name in ('primary', 'sensitivity'):
        excluded = {(r['task'], r['sample']) for r in cells if r['contamination'] is True}
        retained = [r for r in cells if name == 'sensitivity' or (r['task'], r['sample']) not in excluded]
        with tempfile.TemporaryDirectory(prefix='v3-paired-analysis-') as temporary:
            root = Path(temporary)
            (root / 'cells').mkdir()
            (root / 'meta.json').write_text(json.dumps(dict(evidence='external-devin-v3', task_ids=task_ids,
                config=dict(arms=['A', 'A2', 'G'], tasks=['all'], samples=2, seed=20261122))))
            for row in retained:
                cell = root / 'cells' / f"{row['task']}-s{row['sample']}-{row['arm']}"
                cell.mkdir()
                (cell / 'result.json').write_text(json.dumps(row))
            outputs[name] = analyze.analyze(root)
        for comparison in [outputs[name]['aa_control'], *outputs[name]['comparisons'].values()]:
            if comparison['n']:
                b, c = comparison['improved'], comparison['regressed']
                n = b + c
                exact = min(1, 2 * sum(math.comb(n, k) for k in range(min(b, c) + 1)) / 2**n)
                assert comparison['p'] == exact
    return outputs


if __name__ == '__main__':
    root = Path(__file__).resolve().parent
    cells = json.loads((root / 'cells.json').read_text())
    provenance = json.loads((root / 'provenance.json').read_text())
    for name, actual in summarize(cells, provenance['task_ids']).items():
        expected = json.loads((root / f'analysis-{name}.json').read_text())
        assert actual == expected, name
        print(f'PASS: {name} reproduces exactly; seed=20261122; bootstrap resamples=10000')
