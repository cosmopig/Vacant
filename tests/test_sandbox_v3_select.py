import json
import random
import sys
from types import SimpleNamespace

import pytest

from ops.sandbox.v3 import select


def test_references_rank_results_only_at_pinned_commit(monkeypatch):
    instances = [dict(instance_id=f'i{i}') for i in range(20)]
    files = {}
    for i in range(12):
        root = f'evaluation/verified/20260101_submission{i:02}'
        count = 20 if i < 2 else 20 - i
        files[root + '/results/results.json'] = json.dumps(dict(resolved=[f'i{n}' for n in range(count)]))
        suffix = 'yml' if i == 0 else 'yaml'
        files[root + '/metadata.' + suffix] = json.dumps(dict(info=dict(name=f'Name {i}'), tags=dict(checked=False)))

    def git(repo, *args):
        if args[0] == 'ls-tree':
            assert select.EXPERIMENTS_SHA in args
            return '\n'.join(reversed(list(files)))
        assert args[0] == 'show' and args[1].startswith(select.EXPERIMENTS_SHA + ':')
        return files[args[1].split(':', 1)[1]]

    monkeypatch.setattr(select, 'git', git)
    monkeypatch.setitem(sys.modules, 'yaml', SimpleNamespace(safe_load=json.loads))
    refs, ranking = select.references('unused', instances)
    assert len(refs) == 10 and len(ranking) == 12
    assert [r['submission'] for r in refs] == [f'20260101_submission{i:02}' for i in range(10)]
    assert refs[0]['name'] == 'Name 0' and refs[0]['resolve_rate'] == 1
    assert refs[0]['metadata_path'].endswith('.yml')
    assert refs[0]['date'] == '2026-01-01' and refs[0]['date_source'] == 'submission directory prefix'
    assert all('resolved_ids' not in row for row in ranking)
    with pytest.raises(ValueError, match='fewer than ten'):
        monkeypatch.setattr(select, 'git', lambda *args: '')
        select.references('unused', instances)


def test_candidate_fraction_boundaries_and_stable_draw():
    instances = [dict(instance_id=f'i{i}', repo='r', difficulty='<15 min fix') for i in (0, 1, 4, 5, 10)]
    refs = [dict(submission=f's{n}', resolved_ids=[f'i{i}' for i in (0, 1, 4, 5, 10) if n < i]) for n in range(10)]
    pool = select.candidates(instances, refs)
    assert [(r['instance_id'], r['fraction']) for r in pool] == [('i1', 0.1), ('i4', 0.4)]
    assert pool[1]['resolved_by'] == ['s0', 's1', 's2', 's3']
    assert select.candidates([], refs) == []
    with pytest.raises(ValueError, match='exactly ten'):
        select.candidates(instances, refs[:9])
    state = random.getstate()
    assert select.SEED == 20261123
    assert select.draw(pool) == select.draw(list(reversed(pool)))
    assert random.getstate() == state
    assert select.draw([]) == []


def test_feasibility_filters_repo_cap_and_complete_draw():
    ordered = [dict(instance_id=f'i{i}', repo=f'r{i//6}', difficulty='<15 min fix') for i in range(24)]
    ordered[0]['difficulty'] = '>4 hours'
    calls = []

    def validate(key):
        calls.append(key)
        return dict(status={'i1': 'gold did not resolve', 'i2': 'base lacks an observed FAIL_TO_PASS failure'}.get(key, 'pass'))

    checkpoints = []
    result = select.choose(ordered, validate, lambda state: checkpoints.append(json.loads(json.dumps(state))))
    assert result['status'] == 'complete' and len(result['final_instance_ids']) == 12
    assert all(sum(r['repo'] == f'r{i}' for r in result['selected']) == 3 for i in range(4))
    assert 'i0' not in calls and 'i9' not in calls and 'i21' not in calls
    assert {r['reason'] for r in result['skips']} == {
        'difficulty >4 hours', 'repo cap (3)', 'gold did not resolve', 'base lacks an observed FAIL_TO_PASS failure'}
    assert checkpoints[-1] == result


def test_empty_and_infrastructure_are_not_instance_rejections():
    empty = select.choose([], lambda key: pytest.fail('must not validate empty pool'))
    assert empty['status'] == 'insufficient feasible candidates' and empty['selected'] == []

    def blocked(key):
        raise select.InfrastructureError('registry unavailable')

    result = select.choose([dict(instance_id='i', repo='r', difficulty='1-4 hours')], blocked)
    assert result['status'] == 'blocked' and result['blocker'] == 'registry unavailable'
    assert result['skips'] == [] and result['final_instance_ids'] == []


def test_observed_failures_handles_unittest_subtests_without_false_matches():
    name = 'test_method (package.SomeTests)'
    other = 'test_method (package.OtherTests)'
    output = f"FAIL: {name} (parameter='value')\nTraceback...\n"
    assert select.observed_failures([name, other], {'test_method': 'FAILED'}, output) == [name]
    assert select.observed_failures([name], {name: 'ERROR'}, '') == [name]
    assert select.observed_failures([name], {name: 'PASSED'}, '') == []
    assert select.observed_failures([name], {}, 'prefix FAIL: ' + name) == []
    assert select.observed_failures([], {}, '') == []


def test_no_docker_stops_before_validation(tmp_path, monkeypatch, capsys):
    instances = [dict(instance_id='i', repo='r', difficulty='<15 min fix')]
    data = tmp_path / 'data.jsonl'
    data.write_text(json.dumps(instances[0]) + '\n')
    monkeypatch.setattr(select, 'DATASET_CONTENT_SHA256', select.digest(select.canonical(instances)))
    refs = [dict(submission=f's{n}', resolved_ids=['i'] if n == 0 else []) for n in range(10)]
    monkeypatch.setattr(select, 'references', lambda *args: (refs, []))
    monkeypatch.setattr(select, 'version', lambda name: select.HARNESS_VERSION)
    monkeypatch.setattr(select.platform, 'platform', lambda: 'test-platform')
    monkeypatch.setattr(select.subprocess, 'run', lambda *args, **kwargs: SimpleNamespace(returncode=1, stderr='daemon unavailable'))
    monkeypatch.setattr(select, 'validate_instance', lambda *args: pytest.fail('Docker must gate validation'))
    out = tmp_path / 'selection.json'
    assert select.main(['--experiments', 'unused', '--dataset-json', str(data), '--work-dir', str(tmp_path), '--out', str(out)]) == 2
    result = json.loads(out.read_text())
    assert result['candidate_count'] == 1 and result['final_instance_ids'] == []
    assert result['validation'] == {} and result['status'] == 'blocked'
    assert result['environment']['docker_error'] == 'daemon unavailable'
    assert json.loads(capsys.readouterr().out)['candidate_count'] == 1
    data.write_text('{}\n')
    with pytest.raises(ValueError, match='dataset content differs'):
        select.main(['--experiments', 'unused', '--dataset-json', str(data), '--work-dir', str(tmp_path), '--out', str(out)])
