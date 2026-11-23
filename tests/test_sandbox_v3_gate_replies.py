import importlib.util
import json
from pathlib import Path

import pytest

PATH = Path(__file__).resolve().parents[1] / 'ops/sandbox/v3/results/devin-v3-cmp-20261123/parse_gates.py'
SPEC = importlib.util.spec_from_file_location('parse_gates', PATH)
parser = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(parser)
PASS = '[vacant run] RUN-ON　交付（visible_pass）　1/1 次　ws abc→abc'


def row(body='', final=''):
    return dict(branch='branch', session_id='session', messages=body, final_reply=final)


def event(body, event_id='event-one'):
    return f'[devin] @ 123 ({event_id})\n{body}'


@pytest.mark.parametrize('mark,reason,code,verdict', [
    ('infra_void', 'agent_spawn_failed', 22, 'infra_void'),
    ('infra_void', 'launcher_exception', 22, 'infra_void'),
    ('infra_void', 'ws_moved_during_freeze', 22, 'infra_void'),
    ('infra_void', 'ws_reset_failed', 22, 'infra_void'),
    ('infra_void', 'ks1_violation', 22, 'infra_void'),
    ('拒交', 'no_suite', 20, 'refused'),
    ('拒交', 'attempts_exhausted', 20, 'refused'),
    ('拒交', 'visible_fail', 20, 'refused'),
    ('未 gate', 'ungated', 0, 'ungated'),
    ('交付', 'visible_pass', 0, 'accepted'),
])
def test_every_numbered_cli_outcome_is_counted_before_accepted_retry(mark, reason, code, verdict):
    first = f'Submission 1 EXIT={code}\n```\n[vacant run] RUN-ON　{mark}（{reason}）　1/1 次　ws def→def\nEXIT={code}\n```'
    initial = parser.parse_cell(row(event(first)))
    assert initial['number_of_submissions'] == 1
    assert initial['submissions'][0]['exit_code'] == code
    assert initial['final_gate_verdict'] == verdict
    assert initial['gate_never_run'] == ('UNKNOWN' if mark == 'infra_void' else reason in ('ungated', 'no_suite'))
    second = f'\nSubmission 2 EXIT=0\n```\n{PASS}\nEXIT=0\n```'
    result = parser.parse_cell(row(event(first + second)))
    assert result['number_of_submissions'] == 2
    assert [s['exit_code'] for s in result['submissions']] == [code, 0]
    assert [s['verdict'] for s in result['submissions']] == [verdict, 'accepted']
    assert result['final_gate_verdict'] == 'accepted'
    assert result['gate_never_run'] is False


def test_decodes_full_json_and_deduplicates_history():
    body = f'Gate submission 1 (exit 0):\n```\n{PASS}\nEXIT 0\n```'
    final = '--- event-one ---\ncontents: ' + json.dumps(dict(message=body))
    result = parser.parse_cell(row(event(body[:20]), final))
    assert result['number_of_submissions'] == 1 and result['gate_never_run'] is False
    assert result['submissions'][0]['exit_code'] == 0
    repeated = parser.parse_cell(row(event(body) + '\n' + event(body, 'event-two')))
    assert repeated['number_of_submissions'] == 1


def test_empty_and_prompt_text_do_not_imply_runs():
    assert parser.parse_cell(row())['final_gate_verdict'] == 'UNKNOWN'
    result = parser.parse_cell(row('[user] Exit 0 means accepted; at most 3 submissions.\n' + event('Starting work.')))
    assert result['number_of_submissions'] == 'UNKNOWN' and result['gate_never_run'] == 'UNKNOWN'
    assert parser.parse_cell(row(event('I never ran the gate.')))['gate_never_run'] is True


@pytest.mark.parametrize('mark,reason', [('未 gate', 'ungated'), ('拒交', 'no_suite')])
@pytest.mark.parametrize('number', [2, 3])
def test_missing_earlier_submissions_do_not_imply_gate_never_ran(mark, reason, number):
    body = f'Submission {number}\n```\n[vacant run] RUN-ON　{mark}（{reason}）　1/1 次\n```'
    result = parser.parse_cell(row(event(body)))
    assert result['gate_never_run'] == 'UNKNOWN'
    assert result['number_of_submissions'] == 'UNKNOWN'
    assert parser.parse_cell(row(event('I did not run the gate.\n' + body)))['gate_never_run'] is True
    if number == 3:
        sparse = body.replace('Submission 3', 'Submission 1') + '\n' + body
        assert parser.parse_cell(row(event(sparse)))['gate_never_run'] == 'UNKNOWN'


def test_unknown_and_other_exit_codes_are_not_inferred_from_verdict():
    body = f'Submission 1\n```\n{PASS}\n```'
    assert parser.parse_cell(row(event(body)))['submissions'][0]['exit_code'] == 'UNKNOWN'
    assert parser.parse_cell(row(event(body.replace('Submission 1', 'Submission 1 exit 7'))))['submissions'][0]['exit_code'] == 7


def test_rejects_malformed_final_and_duplicate_rows(tmp_path):
    with pytest.raises(json.JSONDecodeError):
        parser.parse_cell(row(final='contents: {bad'))
    path = tmp_path / 'rows.json'
    path.write_text(json.dumps([row(), row()]))
    with pytest.raises(ValueError):
        parser.parse_export(path)
