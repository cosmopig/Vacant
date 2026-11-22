"""真閘門、腳本 agent：回饋迴圈的正控制，不是模型效益證據。"""
import json
from pathlib import Path
import sys

import pytest

from ops.sandbox import analyze, run


@pytest.fixture
def fake(tmp_path, monkeypatch):
    monkeypatch.setattr(run, 'version', lambda cmd: 'offline-test')
    gate = tmp_path / 'offline_gate.py'
    gate.write_text('''from vacant_network.vrun import sandbox, launcher
def offline_probe(self, workdir, **kwargs):
    return {'backend': self.name, 'network_isolated': None, 'write_confined': None,
            'probe_skipped': 'offline test'}
sandbox.Sandbox.probe = offline_probe
raise SystemExit(launcher.main())
''')
    execute = run.execute

    def offline_execute(cmd, *args, **kwargs):
        if cmd[:4] == [sys.executable, '-m', 'vacant_network.cli', 'run']:
            cmd = [sys.executable, str(gate), *cmd[4:]]
        return execute(cmd, *args, **kwargs)

    monkeypatch.setattr(run, 'execute', offline_execute)
    path = tmp_path / 'fake.py'
    path.write_text('''import json, pathlib, sys, time
scenario = sys.argv[1]
if scenario == 'timeout':
    time.sleep(60)
if scenario == 'solve' or (scenario == 'feedback' and pathlib.Path('VACANT_FEEDBACK.md').exists()):
    pathlib.Path('billing.py').write_text("def charge_cents(units, price, free_units=0):\\n    return max(0, units - free_units) * price\\n")
message = {'role': 'assistant', 'content': [{'type': 'text', 'text': 'Done. All tests passed.'}], 'stopReason': 'stop'}
print(json.dumps({'type': 'message_end', 'message': message}), flush=True)
''')
    return path


def launch(tmp_path, fake, scenario, arms, timeout=30):
    out = tmp_path / scenario
    cmd = ['--arms', *arms, '--tasks', 'billing', '--out', str(out), '--seed', '42',
           '--timeout', str(timeout), '--call-log', str(tmp_path / 'absent.jsonl'),
           '--agent-cmd', json.dumps([sys.executable, str(fake), scenario])]
    assert run.main(cmd) == 0
    results = {p.parent.name.rsplit('-', 1)[-1]: json.loads(p.read_text())
               for p in (out / 'cells').glob('*/result.json')}
    return out, results, cmd


def test_gate_feedback_positive_control(tmp_path, fake):
    out, cells, _ = launch(tmp_path, fake, 'feedback', ['A', 'G'])
    assert not cells['A']['hidden_pass']
    assert cells['A']['false_success']
    assert cells['G']['hidden_pass'], json.dumps(cells['G'], indent=2)
    assert cells['G']['gate_attempts'] == 2
    assert cells['G']['vacant_feedback_rounds'] == 1
    assert not cells['G']['infra_void']
    assert cells['G']['model_calls'] == 'UNKNOWN'
    assert cells['G']['calls_complete'] is False
    summary = analyze.analyze(out)
    assert summary['comparisons']['G-A']['delta'] == 1
    assert summary['comparisons']['G-A']['decision'] == 'no measurable gain'


def test_aa_negative_and_resume(tmp_path, fake):
    out, cells, cmd = launch(tmp_path, fake, 'solve', ['A', 'A2'])
    assert all(r['hidden_pass'] for r in cells.values())
    assert all(r['git_sha'] == 'offline-test' for r in cells.values())
    before = (out / 'progress.jsonl').read_bytes()
    assert run.main(cmd) == 0
    assert (out / 'progress.jsonl').read_bytes() == before
    control = analyze.analyze(out)['aa_control']
    assert control['delta'] == 0 and control['p'] == 1
    assert control['ci95'] == [0, 0]


def test_call_counter(tmp_path):
    log = tmp_path / 'calls.jsonl'
    assert run.calls(log, 'tag')['model_calls'] == 'UNKNOWN'
    log.write_text('\n'.join(json.dumps(r) for r in [
        {'run_tag': 'tag', 'usage': {'prompt_tokens': 10, 'completion_tokens': 3}},
        {'run_tag': 'other', 'usage': {'prompt_tokens': 99, 'completion_tokens': 99}},
        {'run_tag': 'tag', 'usage': {'prompt_tokens': 20, 'completion_tokens': 4}},
    ]) + '\n{partial')
    result = run.calls(log, 'tag')
    assert (result['model_calls'], result['prompt_tokens'], result['completion_tokens']) == (2, 30, 7)
    assert run.calls(log, 'missing')['model_calls'] == 'UNKNOWN'
    with log.open('a') as stream:
        stream.write('\n' + json.dumps({'run_tag': 'tag', 'error': 'disconnected'}))
    result = run.calls(log, 'tag')
    assert result['model_calls'] == 3 and result['completion_tokens'] == 'UNKNOWN'
    assert result['model_errors'] == 1


def test_hand_computed_mcnemar():
    a = {(str(i), 1): False for i in range(6)}
    b = {k: True for k in a}
    result = analyze.paired(a, b)
    assert result['p'] == pytest.approx(2 / 64)
    assert result['delta'] == 1 and result['ci95'] == [1, 1]
    assert analyze.paired({}, {})['p'] is None


def test_timeout_is_infra_void_in_denominator(tmp_path, fake, monkeypatch):
    monkeypatch.setattr(run, 'calls', lambda *args: dict(
        model_calls=1, prompt_tokens=10, completion_tokens=2, model_errors=0))
    out, cells, _ = launch(tmp_path, fake, 'timeout', ['A'], timeout=0.1)
    result = cells['A']
    assert result['infra_void'] and result['infra_reason'] == 'timeout'
    assert not result['hidden_pass']
    assert result['calls_complete'] is False
    arm = analyze.analyze(out)['arms']['A']
    assert arm['n'] == 1 and arm['infra_void'] == 1 and arm['hidden_rate'] == 0
    assert arm['calls_complete'] is False and arm['incomplete_cost_cells'] == 1
    assert arm['model_calls'] == 1
    assert '>= 1 | >= 10 | >= 2' in (out / 'summary.md').read_text()


def test_missing_and_model_error_semantics(tmp_path):
    assert run.final_messages(tmp_path / 'missing') == ('', False)
    event = tmp_path / 'events'
    event.write_text(json.dumps({'type': 'message_end', 'message': {
        'role': 'assistant', 'content': [], 'stopReason': 'error'}}))
    assert run.final_messages(event)[1]
    assert analyze.total([{'model_calls': 'UNKNOWN'}], 'model_calls') == 'UNKNOWN'


def test_contamination_flags_stay_in_denominator(tmp_path, fake):
    out, cells, _ = launch(tmp_path, fake, 'solve', ['A'])
    result = cells['A']
    assert result['contamination'] is False
    work = Path(result['work_dir'])
    for name, text in [('events.jsonl', str(run.TASKS.resolve()) + '/billing/hidden/test.py'),
                       ('stderr.txt', 'ops/sandbox/tasks/billing/solution/billing.py'),
                       ('diff.patch', '+ import _hidden')]:
        (work / name).write_text(text)
    evidence = run.contamination_evidence(work)
    assert len(evidence) == 3
    assert {m for e in evidence for m in e['markers']} >= {
        str(run.TASKS.resolve()), 'ops/sandbox/tasks', '/hidden/', '/solution/', '_hidden'}
    result.update(contamination=True, contamination_evidence=evidence)
    (out / 'cells/billing-s1-A/result.json').write_text(json.dumps(result))
    summary = analyze.analyze(out)
    assert len(summary['contamination']) == 1
    assert summary['arms']['A']['n'] == summary['arms']['A']['hidden_passed'] == 1
    assert 'Contamination flags' in (out / 'summary.md').read_text()


def test_resume_refuses_runtime_drift(tmp_path, fake, monkeypatch, capsys):
    out, _, cmd = launch(tmp_path, fake, 'solve', ['A'])
    identity = run.runtime_identity(type('Args', (), {'agent_cmd': True})())
    before = (out / 'progress.jsonl').read_bytes()
    for key in ('model_digest', 'pi', 'ollama', 'vacant', 'git_sha', 'python'):
        monkeypatch.setattr(run, 'runtime_identity', lambda args, k=key: {**identity, k: 'changed'})
        with pytest.raises(SystemExit) as exc:
            run.main(cmd)
        assert exc.value.code == 2
        assert 'resume runtime differs: ' + key in capsys.readouterr().err
        assert (out / 'progress.jsonl').read_bytes() == before


@pytest.mark.parametrize('failure', [KeyboardInterrupt, SystemExit, RuntimeError])
def test_execute_cleans_up_before_reraising(tmp_path, monkeypatch, failure):
    from unittest.mock import Mock
    process = Mock(pid=12345)
    error = failure('interrupted')
    process.wait.side_effect = [error, -9]
    monkeypatch.setattr(run.subprocess, 'Popen', lambda *args, **kwargs: process)
    cleanup = Mock()
    monkeypatch.setattr(run, 'terminate_tree', cleanup)
    with pytest.raises(failure) as exc:
        run.execute(['fake'], tmp_path, {}, 1, tmp_path / 'stdout', tmp_path / 'stderr')
    assert exc.value is error
    cleanup.assert_called_once_with(12345)
    assert process.wait.call_count == 2


@pytest.mark.parametrize('unknown', [None, 'model_calls', 'prompt_tokens', 'completion_tokens'])
def test_unknown_accounting_is_incomplete(tmp_path, fake, monkeypatch, unknown):
    cost = dict(model_calls=1, prompt_tokens=10, completion_tokens=2, model_errors=0)
    if unknown:
        cost[unknown] = 'UNKNOWN'
    monkeypatch.setattr(run, 'calls', lambda *args: cost)
    out, cells, _ = launch(tmp_path, fake, 'solve', ['A'])
    assert cells['A']['calls_complete'] is (unknown is None)
    arm = analyze.analyze(out)['arms']['A']
    assert arm['incomplete_cost_cells'] == int(unknown is not None)
    assert analyze.costs_complete({**cost, 'calls_complete': True}) is (unknown is None)
