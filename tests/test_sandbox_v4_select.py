import json
import random
from types import SimpleNamespace

import pytest

from ops.sandbox.v4 import select


def test_inclusive_pool_exclusions_and_fraction_buckets():
    rows = [dict(instance_id=f'i{i}', repo='repo', difficulty='1-4 hours') for i in (0, 1, 4, 5, 6, 10)]
    refs = [dict(submission=f's{n}', resolved_ids=[f'i{i}' for i in (0, 1, 4, 5, 6, 10) if n < i]) for n in range(10)]
    pool, counts, excluded = select.candidates(rows, refs, set())
    assert [(r['instance_id'], r['fraction']) for r in pool] == [('i0', 0), ('i1', .1), ('i4', .4), ('i5', .5)]
    rows[0]['difficulty'] = '>4 hours'
    pool, counts, excluded = select.candidates(rows, refs, {'i5'})
    assert [r['instance_id'] for r in pool] == ['i1', 'i4']
    assert counts['eligible'] == {'0': 0, '0.1-0.4': 2, '0.5': 0}
    assert excluded == dict(difficulty=['i0'], v3=['i5'])
    assert select.candidates([], refs, set())[0] == []
    with pytest.raises(ValueError, match='exactly ten'):
        select.candidates(rows, refs[:9], set())


def test_seeded_draw_and_calibration_do_not_modify_global_rng():
    pool = [dict(instance_id=f'i{i}') for i in range(70)]
    state = random.getstate()
    assert select.SEED == 20261124 and select.CALIBRATION_SEED == 20261125
    assert select.draw(pool) == select.draw(list(reversed(pool)))
    ids = [r['instance_id'] for r in pool]
    assert select.calibration(ids) == random.Random(20261125).sample(sorted(ids), 12)
    assert len(set(select.calibration(ids))) == 12
    assert random.getstate() == state
    with pytest.raises(ValueError, match='twelve'):
        select.calibration(ids[:11])


def test_power_uses_actual_bank_size_and_v3_discordance():
    power = select.power_summary(62)
    assert power['paired_units'] == 124 and power['discordance'] == 8 / 24
    assert power['favorable_given_discordance'] == .725
    assert power['exact_power'] == pytest.approx(.805571660767604)
    assert power['target_met'] is True
    assert select.power_summary(48)['target_met'] is False


def test_minimal_cap_increase_and_no_duplicate_validation():
    ordered = [dict(instance_id=f'i{i}', repo=f'r{i%5}') for i in range(75)]
    calls = []

    def validate(keys):
        calls.extend(keys)
        return {key: dict(status='gold did not resolve' if int(key[1:]) in (4, 9, 14, 19, 24) else 'pass') for key in keys}

    state = select.choose(ordered, validate)
    assert state['status'] == 'complete' and len(state['selected']) == 62
    assert state['repo_cap'] == 13
    assert state['cap_attempts'] == [dict(repo_cap=12, selected_count=58, exhausted_draw=True),
                                     dict(repo_cap=13, selected_count=62, exhausted_draw=False)]
    assert len(calls) == len(set(calls))
    assert max(sum(r['repo'] == f'r{i}' for r in state['selected']) for i in range(5)) == 13


def test_under_target_takes_every_feasible_and_empty_is_explicit():
    ordered = [dict(instance_id=f'i{i}', repo='a' if i < 4 else 'b') for i in range(6)]
    result = select.choose(ordered, lambda keys: {key: dict(status='pass' if key != 'i0' else 'base lacks an observed FAIL_TO_PASS failure') for key in keys},
                           target=10, initial_cap=1)
    assert result['status'] == 'complete_undersized' and result['repo_cap'] == 3
    assert result['final_instance_ids'] == [f'i{i}' for i in range(1, 6)]
    assert select.choose([], lambda keys: pytest.fail('empty pool'))['status'] == 'complete_undersized'


def test_infrastructure_blocks_instead_of_becoming_a_feasibility_skip():
    row = dict(instance_id='i', repo='r')
    state = select.choose([row], lambda keys: dict(i=dict(status='blocked', error='registry unavailable')))
    assert state['status'] == 'blocked' and state['skips'] == []
    assert state['blocker'] == 'registry unavailable'
    with pytest.raises(ValueError, match='scheduled instances'):
        select.choose([row], lambda keys: {})


def test_validation_cache_binds_inputs_and_report_bytes(tmp_path, monkeypatch):
    row = dict(instance_id='i')
    report = tmp_path / 'report.json'
    report.write_text('{}')
    calls = []

    def validate(*args):
        calls.append(args)
        return dict(status='pass', controls=dict(gold=dict(report_path=str(report), report_sha256=select.v3.digest(report.read_bytes()))))

    monkeypatch.setattr(select.v3, 'validate_instance', validate)
    args = (row, str(tmp_path), 1800, dict(validator='frozen'))
    assert select.validate_cached(args) == select.validate_cached(args)
    assert len(calls) == 1
    with pytest.raises(ValueError, match='fingerprint'):
        select.validate_cached((row, str(tmp_path), 1800, dict(validator='different')))
    report.write_text('changed')
    with pytest.raises(ValueError, match='evidence changed'):
        select.validate_cached(args)
    saved = json.loads((tmp_path / 'instances/i/validation.json').read_text())
    assert saved['outcome']['status'] == 'pass'


@pytest.mark.parametrize('message', ['image pull failed: HTTP 429', 'TOOMANYREQUESTS', 'pull rate-limit exceeded'])
def test_pull_rate_limits_retry_same_instance_with_capped_backoff(tmp_path, monkeypatch, message):
    row = dict(instance_id='i')
    calls, sleeps = [], []

    def validate(*args):
        calls.append(args)
        if len(calls) <= 4:
            raise select.v3.InfrastructureError(message)
        return dict(status='pass')

    monkeypatch.setattr(select.v3, 'validate_instance', validate)
    monkeypatch.setattr(select.time, 'sleep', sleeps.append)
    assert select.validate_with_backoff(row, tmp_path, 1800) == dict(status='pass')
    assert calls == [(row, tmp_path, 1800)] * 5
    assert sleeps == [900, 1800, 3600, 3600]


def test_non_rate_limit_error_still_blocks_without_sleep(tmp_path, monkeypatch):
    def fail(*args):
        raise select.v3.InfrastructureError('image pull failed: HTTP 503')

    monkeypatch.setattr(select.v3, 'validate_instance', fail)
    monkeypatch.setattr(select.time, 'sleep', lambda _: pytest.fail('unexpected retry'))
    assert select.validate_cached((dict(instance_id='i'), str(tmp_path), 1800, {})) == (
        'i', dict(status='blocked', error='image pull failed: HTTP 503'))
    assert not (tmp_path / 'instances/i/validation.json').exists()


def test_local_inspect_404_is_retried_and_old_rejection_cache_is_cleared(tmp_path, monkeypatch):
    row = dict(instance_id='i')
    context = {}
    cache = tmp_path / 'instances/i/validation.json'
    cache.parent.mkdir(parents=True)
    unavailable = dict(status='instance image unavailable', error='404 No such image: local inspect after pull')
    cache.write_text(json.dumps(dict(input_sha256=select.v3.digest(select.v3.canonical(dict(instance=row, context=context))),
                                    outcome=unavailable)))
    calls, sleeps = [], []

    def validate(*args):
        assert not cache.exists(), 'transient result cached as a rejection'
        calls.append(args)
        return unavailable if len(calls) < 3 else dict(status='pass')

    monkeypatch.setattr(select.v3, 'validate_instance', validate)
    monkeypatch.setattr(select.time, 'sleep', sleeps.append)
    assert select.validate_cached((row, str(tmp_path), 1800, context)) == ('i', dict(status='pass'))
    assert len(calls) == 3 and sleeps == [900, 1800]
    assert json.loads(cache.read_text())['outcome'] == dict(status='pass')


def test_disk_guard_stops_before_validation(tmp_path, monkeypatch):
    monkeypatch.setattr(select.shutil, 'disk_usage', lambda _: SimpleNamespace(total=100, used=85, free=15))
    monkeypatch.setattr(select.v3, 'validate_instance', lambda *args: pytest.fail('disk guard bypassed'))
    with pytest.raises(select.v3.InfrastructureError, match='85%'):
        select.validate_with_backoff(dict(instance_id='i'), tmp_path, 1800)


def test_cleanup_follows_cache_write_and_runs_on_cache_hit(tmp_path, monkeypatch):
    row = dict(instance_id='i')
    cache = tmp_path / 'instances/i/validation.json'
    calls = []
    outcome = dict(status='pass', image_id='sha256:instance', controls={})
    monkeypatch.setattr(select.v3, 'validate_instance', lambda *args: outcome)

    def run(command, **kwargs):
        assert json.loads(cache.read_text())['outcome'] == outcome
        calls.append(command)
        return SimpleNamespace(returncode=0, stderr='')

    monkeypatch.setattr(select.subprocess, 'run', run)
    args = (row, str(tmp_path), 1800, {})
    assert select.validate_cached(args) == ('i', outcome)
    monkeypatch.setattr(select.v3, 'validate_instance', lambda *args: pytest.fail('cached control rerun'))
    assert select.validate_cached(args) == ('i', outcome)
    assert calls == [['docker', 'image', 'inspect', 'sha256:instance'], ['docker', 'rmi', 'sha256:instance']] * 2


def test_replacement_candidates_keep_seeded_order_and_cap():
    ordered = [dict(instance_id=str(index), repo=repo) for index, repo in enumerate(['a'] * 13 + ['b', 'c'])]
    assert select.replacement_candidates(ordered, ordered[:12], {'13'}, 12) == [ordered[14]]
    assert select.replacement_candidates(ordered, ordered[:12], {'13'}, 13) == [ordered[12], ordered[14]]
    assert select.replacement_candidates([], [], set(), 12) == []
    with pytest.raises(ValueError, match='initial cap'):
        select.replacement_candidates(ordered, [], set(), 11)


def test_replacement_replay_checks_order_evidence_and_calibration():
    rows = [dict(instance_id=str(index), repo='a') for index in range(14)]
    original = [row['instance_id'] for row in rows[:12]]
    final = [row['instance_id'] for row in rows[1:13]]
    report = dict(candidates=rows, ordered_draw=original + ['12', '13'],
        pre_replacement_instance_ids=original, pre_replacement_calibration_ids=original,
        replacements=[dict(outgoing='0', incoming='12', repo_cap=12)], cap_attempts=[dict(repo_cap=12)],
        replacement_attempts=[dict(instance_id='12', repo_cap=12, official_status='pass', native_status='ready')],
        validation={'12': dict(status='pass')}, final_instance_ids=final, repo_cap=12,
        calibration_instance_ids=select.calibration(final))
    assert select.replay_replacements(report) == final
    with pytest.raises(ValueError, match='seeded order'):
        select.replay_replacements(dict(report, replacement_attempts=[]))
    with pytest.raises(ValueError, match='calibration'):
        select.replay_replacements(dict(report, calibration_instance_ids=original))
    attempt = dict(report['replacement_attempts'][0], official_status='blocked')
    with pytest.raises(ValueError, match='infrastructure'):
        select.replay_replacements(dict(report, replacement_attempts=[attempt], validation={'12': dict(status='blocked')}))
    empty = dict(report, replacements=[], replacement_attempts=[], final_instance_ids=original,
                 calibration_instance_ids=original)
    assert select.replay_replacements(empty) == original


def test_cleanup_absent_images_and_real_errors(monkeypatch):
    monkeypatch.setattr(select.subprocess, 'run', lambda *args, **kwargs: pytest.fail('no image to remove'))
    select.cleanup_instance_image(dict(status='instance image unavailable'))
    monkeypatch.setattr(select.subprocess, 'run', lambda *args, **kwargs: SimpleNamespace(returncode=1, stderr='No such image: abc'))
    select.cleanup_instance_image(dict(image_id='abc'))
    monkeypatch.setattr(select.subprocess, 'run', lambda *args, **kwargs: SimpleNamespace(returncode=1, stderr='image in use'))
    with pytest.raises(select.v3.InfrastructureError, match='image in use'):
        select.cleanup_instance_image(dict(image_id='abc'))
