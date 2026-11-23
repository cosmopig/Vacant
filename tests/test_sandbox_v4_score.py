from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
from types import SimpleNamespace

import pytest

from ops.sandbox.v4 import audit, gates, images, score


@pytest.fixture
def bank(tmp_path):
    repo, remote = tmp_path / 'repo', tmp_path / 'remote.git'
    repo.mkdir()
    env = {**os.environ, 'GIT_AUTHOR_NAME': 'Test', 'GIT_COMMITTER_NAME': 'Test',
           'GIT_AUTHOR_EMAIL': 'test@example.invalid', 'GIT_COMMITTER_EMAIL': 'test@example.invalid'}

    def git(*args):
        return subprocess.check_output(['git', '-C', str(repo), *args], env=env, stderr=subprocess.PIPE).decode().strip()

    git('init', '--quiet')
    subprocess.run(['git', 'init', '--bare', str(remote)], check=True, capture_output=True)
    (repo / 'code.py').write_text('before\n')
    git('add', 'code.py')
    git('commit', '-qm', 'base')
    base, tree = git('rev-parse', 'HEAD'), git('rev-parse', 'HEAD^{tree}')
    ids = [f'task-{i:02}' for i in range(62)]
    selection = dict(final_instance_ids=ids, calibration_instance_ids=ids[:12], seed=20261124,
                     validation={t: dict(status='pass', repo_digests=['example/image@sha256:' + 'a'*64]) for t in ids})
    manifest = dict(cases={t: dict(status='ready', snapshot=dict(sha=base, base_tree=tree, base_commit=base),
                                  selection=dict(environment=dict(commands=[]), measurement={})) for t in ids})
    git('push', str(remote), *[base + ':refs/heads/sandbox-v4/' + t for t in ids[:12]])
    (repo / 'code.py').write_text('after\n')
    gold = git('diff') + '\n'
    (repo / 'test_agent.py').write_text('def test_agent(): assert True\n')
    (repo / 'VACANT_TESTS.txt').write_text('test_agent.py::test_agent\n')
    git('add', 'code.py', 'test_agent.py', 'VACANT_TESTS.txt')
    git('commit', '-qm', 'handback')
    handback = git('rev-parse', 'HEAD')
    instances = [dict(instance_id=t, base_commit=base, patch=gold, test_patch='') for t in ids]
    branches = score.schedule(selection, 'calibration')
    sessions = {b: f'session-{i}' for i, b in enumerate(branches)}
    calls = []

    def runner(instance, candidate, image, cell):
        calls.append(instance['instance_id'])
        contents = candidate.read_bytes()
        assert b'VACANT_TESTS.txt' not in contents and b'test_agent.py' in contents
        assert image == 'example/image@sha256:' + 'a'*64
        return dict(resolved=ids.index(instance['instance_id']) < 8, infra_void=False, patch_applied=True)

    def publish():
        git('push', str(remote), *[handback + ':refs/heads/' + b for b in branches])

    def collect(out, **kwargs):
        return score.collect(repo, str(remote), out, instances, selection, manifest, protocol='calibration',
                             sessions=sessions, runner=runner, **kwargs)

    return SimpleNamespace(**locals())


def load(path):
    return json.loads(path.read_text())


def reviewed(out):
    verdicts = load(out / 'contamination.json')
    for value in verdicts.values():
        value.update(contaminated=False, outside_help=False, reviewer='fixture reviewer',
                     evidence=['full session access audit'], outside_help_evidence=['PR/review receipt and final-push audit'])
    score.write_json(out / 'contamination.json', verdicts)
    return verdicts


def test_calibration_empty_incremental_audits_and_conservative_gate(bank, tmp_path):
    out = tmp_path / 'results'
    report = bank.collect(out)['calibration']
    assert report['scored'] == 0 and report['decision'] == 'incomplete'
    bank.publish()
    report = bank.collect(out)['calibration']
    assert report['scored'] == 12 and report['resolved_count'] == 8 and not report['proceed']
    assert len(bank.calls) == 12
    verdicts = reviewed(out)
    assert score.review(out)['calibration']['proceed']
    branch = bank.branches[-1]
    verdicts[branch]['outside_help'] = True
    score.write_json(out / 'contamination.json', verdicts)
    report = score.review(out)['calibration']
    assert report['decision'] == 'ceiling, v4 rejected' and report['conservative_resolved_count'] == 9
    verdicts[branch]['contaminated'] = None
    score.write_json(out / 'contamination.json', verdicts)
    assert score.review(out)['calibration']['decision'] == 'incomplete'
    bank.collect(out)
    assert len(bank.calls) == 12
    assert load(out / 'secondary.json')['manifest_presence'] == dict.fromkeys(bank.branches, True)


def test_calibration_resume_rejects_inputs_and_changed_branch(bank, tmp_path):
    out = tmp_path / 'results'
    bank.publish()
    bank.collect(out)
    reviewed(out)
    bank.selection['seed'] += 1
    with pytest.raises(ValueError, match='resume inputs differ'):
        bank.collect(out)
    bank.selection['seed'] -= 1
    (bank.repo / 'note.txt').write_text('later commit\n')
    bank.git('add', 'note.txt')
    bank.git('commit', '-qm', 'later delivery')
    bank.git('push', str(bank.remote), 'HEAD:refs/heads/' + bank.branches[0])
    meta = bank.collect(out)
    assert meta['changed_branches'] == [bank.branches[0]]
    assert meta['calibration']['decision'] == 'incomplete' and len(bank.calls) == 12


def test_control_cannot_clear_and_audit_identity_must_match(bank, tmp_path):
    bank.publish()
    out = tmp_path / 'results'
    bank.collect(out, control_only=True)
    verdicts = reviewed(out)
    assert not score.review(out)['calibration']['proceed']
    verdicts[bank.branches[0]]['session_id'] = 'wrong-session'
    score.write_json(out / 'contamination.json', verdicts)
    with pytest.raises(ValueError, match='audit must bind'):
        score.review(out)


def test_audit_ingestion_keeps_raw_scan_unknown_and_requires_pr_push_evidence(bank, tmp_path):
    bank.publish()
    out, source = tmp_path / 'results', tmp_path / 'audit.json'
    bank.collect(out)
    rows = [dict(branch=b, session_id=bank.sessions[b], browser_events=0, hits={}) for b in bank.branches]
    score.write_json(source, rows)
    assert audit.ingest(out, source)['applied_branches'] == []
    assert score.review(out)['calibration']['decision'] == 'incomplete'
    for row in rows:
        row.update(contaminated=False, outside_help=False, reviewer='fixture reviewer', handback_sha=bank.handback,
                   access_audit_complete=True, outside_help_audit_complete=True,
                   evidence=['session events reviewed'], outside_help_evidence=['PR/review events reviewed'],
                   final_push_evidence='final push timestamp and SHA verified', pr_review_evidence='no review received before push')
    rows[0].pop('pr_review_evidence')
    score.write_json(source, rows)
    with pytest.raises(ValueError, match='final-push and PR/review evidence'):
        audit.ingest(out, source)
    rows[0]['pr_review_evidence'] = 'full event log reviewed'
    score.write_json(source, rows)
    assert len(audit.ingest(out, source)['applied_branches']) == 12
    assert score.review(out)['calibration']['proceed']


def test_comparison_full_372_cells_primary_sensitivity_and_null_bound(bank, tmp_path):
    bank.publish()
    out = tmp_path / 'results'
    bank.collect(out)
    prototype = load(next((out / 'cells').glob('*/result.json')))
    for path in (out / 'cells').glob('*/result.json'):
        path.unlink()
    meta = load(out / 'meta.json')
    expected = score.schedule(bank.selection, 'comparison')
    meta.update(protocol='comparison', calibration_only=False, task_ids=bank.ids, expected_branches=expected,
                sessions={b: f'comparison-session-{i}' for i, b in enumerate(expected)},
                config=dict(arms=['A', 'A2', 'G'], tasks=['all'], samples=2, seed=20261122))
    meta.pop('calibration', None)
    verdicts = {}
    for i, branch in enumerate(expected):
        _, task, external, sample = score.parse_branch(branch)
        row = {**deepcopy(prototype), 'branch': branch, 'task': task, 'sample': sample, 'arm': score.v3.ARMS[external],
               'external_arm': 'devin-' + external, 'protocol': 'comparison', 'session_id': meta['sessions'][branch],
               'hidden_pass': sample == 1, 'resolved': sample == 1}
        directory = out / 'cells' / str(i)
        directory.mkdir()
        score.write_json(directory / 'result.json', row)
        verdicts[branch] = {**score.slot(row['session_id'], row['git_sha']), 'reviewer': 'fixture',
                            'contaminated': False, 'outside_help': i == 0}
    score.write_json(out / 'meta.json', meta)
    score.write_json(out / 'contamination.json', verdicts)
    report = score.review(out)
    assert not report['missing_branches'] and not report['unreviewed_branches']
    primary, sensitivity = (load(out / f'analysis-{name}.json') for name in ('primary', 'sensitivity'))
    assert primary['comparisons']['G-A']['n'] == primary['aa_control']['n'] == 123
    assert sensitivity['comparisons']['G-A']['n'] == sensitivity['aa_control']['n'] == 124
    assert primary['analysis_complete']
    assert primary['comparisons']['G-A']['largest_gain_not_ruled_out'] == primary['comparisons']['G-A']['ci95'][1]


def test_schedule_validation_and_session_mapping(bank, tmp_path):
    assert len(score.schedule(bank.selection, 'comparison')) == 372
    assert score.parse_branch('sandbox-devin/v4/task-00-plain2-s2') == ('comparison', 'task-00', 'plain2', 2)
    for branch in ('sandbox-devin-cal3/task-00-plain', 'sandbox-devin/v4/task-00-vacant-s3', 'sandbox-devin-cal4/task-00-vacant'):
        with pytest.raises(ValueError, match='invalid v4'):
            score.parse_branch(branch)
    path = tmp_path / 'sessions.json'
    score.write_json(path, dict(zip(bank.ids[:12], bank.sessions.values())))
    assert score.session_map(path, bank.branches) == bank.sessions
    bank.selection['final_instance_ids'].pop()
    with pytest.raises(ValueError, match='frozen 62-instance'):
        score.schedule(bank.selection, 'calibration')


@pytest.mark.parametrize('failed', ['A', 'B', 'C'])
def test_gate_parser_extracts_refusal_step_without_receipt_claim(failed):
    body = f'Submission 1\nStep {failed} refused; nodes: test_agent.py::test_agent\n[vacant run] RUN-ON 拒交（visible_fail） 1/1 次\nexit=20\n```'
    result = gates.parse_cell(dict(branch='branch', session_id='session', messages='', final_reply=body))
    steps = result['submissions'][0]['steps']
    assert steps == {s: 'pass' if s < failed else 'fail' if s == failed else 'not_run' for s in 'ABC'}
    assert result['receipt_verification'] == 'UNKNOWN'


def test_gate_parser_empty_acceptance_manifest_and_wrong_session(tmp_path):
    row = dict(branch='branch', session_id='session', messages='', final_reply='no raw gate output')
    assert gates.parse_cell(row)['number_of_submissions'] == 'UNKNOWN'
    row['final_reply'] = 'Submission 1\n[vacant run] RUN-ON 交付（visible_pass） 1/1 次\nexit=0\n```'
    source = tmp_path / 'gates.json'
    score.write_json(source, [row])
    cells = [dict(branch='branch', git_sha='sha', manifest_present=False)]
    parsed = gates.parse_export(source, cells, {'branch': 'session'})['cells'][0]
    assert parsed['submissions'][0]['steps'] == dict.fromkeys('ABC', 'pass')
    assert parsed['manifest_present'] is False and parsed['gate_to_final_handback_binding'] == 'UNKNOWN'
    with pytest.raises(ValueError, match='session mismatch'):
        gates.parse_export(source, cells, {'branch': 'another'})


def test_image_backoff_same_digest_retained_and_fatal_error():
    calls, delays, pulls = [], [], [429, 429, 429, 429, 0]
    present = False

    def run(command, **kwargs):
        nonlocal present
        calls.append(command)
        if command[1] == 'image':
            return SimpleNamespace(returncode=0 if present else 1, stdout='', stderr='')
        code = pulls.pop(0)
        present = code == 0
        return SimpleNamespace(returncode=code, stdout='', stderr='429 Too Many Requests' if code else '')

    usage = lambda _: SimpleNamespace(used=50, total=100)
    images.ensure_image('pinned@sha256:digest', run=run, sleep=delays.append, disk=usage)
    assert delays == [900, 1800, 3600, 3600]
    assert all(c[-1] == 'pinned@sha256:digest' for c in calls)
    assert all('rmi' not in c for c in calls)
    with pytest.raises(RuntimeError, match='Image pull failed'):
        images.ensure_image('missing', run=lambda *a, **k: SimpleNamespace(returncode=1, stdout='', stderr='404 not found'),
                            sleep=delays.append, disk=usage)


def test_official_transport_retry_retains_attempts(tmp_path, monkeypatch):
    monkeypatch.setattr(images, 'ensure_image', lambda image: None)
    outcomes = iter([dict(infra_void=True, error='429 Too Many Requests'), dict(resolved=True, infra_void=False)])
    monkeypatch.setattr(score.v3, 'call_harness', lambda *a: next(outcomes))
    delays = []
    monkeypatch.setattr(score.time, 'sleep', delays.append)
    result = score.official_runner(Path('/python'), 1800)(dict(instance_id='task'), tmp_path / 'patch', 'image', tmp_path)
    assert result['resolved'] and delays == [900]
    assert (tmp_path / 'attempts/1').is_dir() and (tmp_path / 'attempts/2').is_dir()


def test_missing_manifest_and_harness_error_are_recorded(bank, tmp_path):
    bank.publish()
    (bank.repo / 'VACANT_TESTS.txt').unlink()
    bank.git('add', '-u')
    bank.git('commit', '-qm', 'without manifest')
    bank.git('push', str(bank.remote), 'HEAD:refs/heads/' + bank.branches[0])

    def runner(*args):
        raise RuntimeError('ordinary harness error, not a pull limit')

    out = tmp_path / 'results'
    result = score.collect(bank.repo, str(bank.remote), out, bank.instances, bank.selection, bank.manifest,
                           protocol='calibration', sessions=bank.sessions, runner=runner)
    assert result['calibration']['infra_void'] == 12 and not result['calibration']['proceed']
    assert load(out / 'secondary.json')['manifest_presence'][bank.branches[0]] is False


def test_disk_guard_waits_without_deleting_images():
    states = iter([SimpleNamespace(used=86, total=100), SimpleNamespace(used=50, total=100)])
    delays, calls = [], []
    present = False

    def run(command, **kwargs):
        nonlocal present
        calls.append(command)
        if command[1] == 'image':
            return SimpleNamespace(returncode=0 if present else 1, stdout='', stderr='')
        present = True
        return SimpleNamespace(returncode=0, stdout='', stderr='')

    images.ensure_image('image', run=run, sleep=delays.append, disk=lambda _: next(states))
    assert delays == [900] and all('rmi' not in c for c in calls)


def test_gate_conflicting_exit_is_unknown():
    row = dict(branch='branch', session_id='session', messages='',
               final_reply='Submission 1\n[vacant run] RUN-ON 交付（visible_pass） 1/1 次\nexit=20\n```')
    assert gates.parse_cell(row)['submissions'][0]['steps'] == dict.fromkeys('ABC', 'UNKNOWN')
