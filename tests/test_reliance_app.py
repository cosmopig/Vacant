"""展場案例完整性；配對統計案例明確標為合成（非真人資料）。"""

import copy
import json

import pytest

from ops.reliance import aggregate, build_cases


@pytest.fixture(scope='module')
def bank():
    return aggregate.manifest()


def test_committed_cases_match_real_archive(bank):
    built = build_cases.build()
    assert bank == built
    assert len(bank['cases']) == 12
    assert sum(c['reward'] for c in bank['cases']) == 6
    assert len({c['task'] for c in bank['cases']}) == 12
    assert len({c['model'] for c in bank['cases']}) == 2
    assert set(build_cases.MANUAL) <= {c['id'] for c in bank['cases']}
    assert len(build_cases.OUT.read_bytes()) < 300_000
    rows = {r['trial_id']: r for r in build_cases.select_rows()}
    for c in bank['cases']:
        r = rows[c['id']]
        trial = build_cases.archive.CACHE / 'formal/jobs' / r['job'] / r['trial_id']
        gt = json.loads((trial / 'result.json').read_text())['verifier_result']['rewards']['reward']
        assert c['reward'] == gt
        assert not r['in_progress']
        assert all(len(s['command']) <= 200 and len(s['output']) <= 300 for s in c['steps'])


def synthetic_export(bank, pid, record_correct=True, plain_correct=False):
    """合成：以真實案例 ID 配上人工製造的判斷，不是真人回覆。"""
    rs = []
    for reward in (0, 1):
        pool = [c for c in bank['cases'] if c['reward'] == reward][:4]
        for i, c in enumerate(pool):
            condition = 'record' if i < 2 else 'plain'
            correct = record_correct if condition == 'record' else plain_correct
            accept = bool(reward) == correct
            rs.append(dict(case_id=c['id'], condition=condition, reward=reward,
                           decision='accept' if accept else 'reject', confidence=80, time_ms=1200))
    return dict(schema_version=1, case_version=bank['version'], participant_id=pid,
                seed=42, synthetic=True, responses=rs)


def test_three_synthetic_exports(bank):
    exports = [synthetic_export(bank, f'synthetic-{i}') for i in range(3)]
    report = aggregate.aggregate(exports)
    assert '合成測試資料（非真人結果）' in report
    assert 'n=3' in report
    assert 'p=0.25' in report
    assert '+100.0' in report and '-100.0' in report


def test_ties_are_omitted_from_sign_test():
    assert aggregate.sign_test([0, 0]) == (1.0, 0)
    assert aggregate.sign_test([1, -1, 0]) == (1.0, 2)


def test_empty_exports_rejected():
    with pytest.raises(ValueError, match='no exported'):
        aggregate.aggregate([])
    with pytest.raises(ValueError, match='JSON object'):
        aggregate.aggregate([[]])


def test_duplicate_and_partial_exports_rejected(bank):
    e = synthetic_export(bank, 'synthetic-1')
    with pytest.raises(ValueError, match='duplicate'):
        aggregate.aggregate([e, e])
    broken = copy.deepcopy(e)
    broken['responses'].pop()
    with pytest.raises(ValueError, match='8 distinct'):
        aggregate.aggregate([broken])


def test_tampered_reward_and_invalid_time_rejected(bank):
    e = synthetic_export(bank, 'synthetic-1')
    e['responses'][0]['reward'] = 1
    with pytest.raises(ValueError, match='reward'):
        aggregate.aggregate([e])
    e = synthetic_export(bank, 'synthetic-1')
    e['responses'][0]['time_ms'] = float('nan')
    with pytest.raises(ValueError, match='time'):
        aggregate.aggregate([e])
