"""展場案例完整性；配對統計案例明確標為合成（非真人資料）。"""

import copy
import json
import re
import shutil
import subprocess

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
    broken = copy.deepcopy(e)
    broken['case_version'] = bank['version'] - 1
    with pytest.raises(ValueError, match='unsupported schema/case version'):
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


@pytest.fixture(scope='module')
def rendered_end(bank):
    node = shutil.which('node')
    if node is None:
        pytest.skip('node 不在 PATH 上；瀏覽器互動另作檢查')
    state = synthetic_export(bank, 'synthetic-ui')
    state['phase'] = 'end'
    for r in state['responses']:
        r['correct'] = r['condition'] == 'record'
    for condition, confidence in [('record', [50, 50, 75, 100]), ('plain', [50, 75, 75, 75])]:
        for row, value in zip([r for r in state['responses'] if r['condition'] == condition], confidence):
            row['confidence'] = value
    script = r"""
const fs = require('node:fs'), vm = require('node:vm');
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
const nodes = {}, get = id => nodes[id] ||= {innerHTML:'', textContent:'',
  setAttribute(name, value){this[name]=value;}};
let allowClear = false, removed = false;
vm.runInNewContext(fs.readFileSync(process.argv[1], 'utf8'), {
  window:{RELIANCE_CASES:input.bank, scrollTo(){}},
  document:{querySelector:get},
  localStorage:{getItem:()=>JSON.stringify(input.state), removeItem(){removed=true;}},
  confirm:()=>allowClear
});
get('#resume').onclick();
const html = get('#app').innerHTML, progress = get('#progress')['aria-label'];
get('#restart').onclick();
const cancelled = {progress:get('#progress')['aria-label'], removed};
allowClear = true;
get('#restart').onclick();
console.log(JSON.stringify({html, progress, cancelled, removed,
  clearedHTML:get('#app').innerHTML, clearedProgress:get('#progress')['aria-label'],
  clearedDots:get('#progress').innerHTML}));
"""
    result = subprocess.run([node, '-e', script, str(build_cases.OUT.parent / 'app.js')],
                            input=json.dumps(dict(bank=bank, state=state)),
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_confidence_charts_are_condition_specific(rendered_end):
    html = rendered_end['html']
    record = re.search(r'data-confidence="record">(.*?)</section>', html).group(1)
    plain = re.search(r'data-confidence="plain">(.*?)</section>', html).group(1)
    assert '加看 Vacant 紀錄' in record and '只看 agent 說的' in plain
    assert '2/2 正確' in record and '1/1 正確' in record
    assert '0/1 正確' in plain and '0/3 正確' in plain
    assert '把握 90–100%：無回答' in plain
    assert '無回答' not in record
    assert 'bar-fill without' in plain


def test_clear_resets_progress_immediately_and_cancel_preserves_it(rendered_end):
    assert rendered_end['progress'] == '8 / 8 完成'
    assert rendered_end['cancelled'] == dict(progress='8 / 8 完成', removed=False)
    assert rendered_end['removed']
    assert rendered_end['clearedProgress'] == '8 回合，尚未開始'
    assert rendered_end['clearedDots'].count('class="dot ') == 8
    assert 'done' not in rendered_end['clearedDots']
    assert '我願意參與，開始' in rendered_end['clearedHTML']
    assert 'id="resume"' not in rendered_end['clearedHTML']


def test_visual_comparison_keeps_four_tokens_per_condition(rendered_end):
    html = rendered_end['html']
    record = re.search(r'<section class="lane record">(.*?)</section>', html).group(1)
    plain = re.search(r'<section class="lane plain">(.*?)</section>', html).group(1)
    assert record.count('class="round-token ') == 4
    assert plain.count('class="round-token ') == 4
    assert record.count('round-token solid') == 4
    assert plain.count('round-token hollow') == 4
    assert 'accepted-wrong' in plain
    assert 'time-col without' in html
