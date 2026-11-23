import json
import os
from pathlib import Path
import subprocess
import sys
from dataclasses import dataclass
from types import SimpleNamespace

import pytest

from ops.sandbox import analyze
from ops.sandbox.v3 import harness, score


@pytest.fixture
def bank(tmp_path):
    env = {**os.environ, 'GIT_AUTHOR_NAME': 'Test', 'GIT_COMMITTER_NAME': 'Test',
           'GIT_AUTHOR_EMAIL': 'test@example.invalid', 'GIT_COMMITTER_EMAIL': 'test@example.invalid'}
    remote, repo = tmp_path / 'remote.git', tmp_path / 'repo'
    subprocess.run(['git', 'init', '--bare', str(remote)], check=True, capture_output=True)
    repo.mkdir()

    def git(*args):
        return subprocess.check_output(['git', '-C', str(repo), *args], env=env, stderr=subprocess.PIPE,
                                       text=True).strip()

    git('init')
    for name, text in {'code.py': 'broken\n', 'tests.py': 'original\n', 'tox.ini': 'old\n',
                       '.gitignore': '**/_version.py\n*.so\n',
                       '.gitattributes': 'stamp.txt export-subst\nkept.txt export-ignore\n',
                       'stamp.txt': '$Format:%H$\n', 'kept.txt': 'public\n'}.items():
        (repo / name).write_text(text)
    git('add', 'code.py', 'tests.py', 'tox.ini', '.gitignore', '.gitattributes', 'stamp.txt', 'kept.txt')
    git('commit', '-m', 'base')
    base_sha, tree = git('rev-parse', 'HEAD'), git('rev-parse', 'HEAD^{tree}')
    ids = [f'pkg__repo-{i}' for i in range(12)]
    patch = 'diff --git a/{0} b/{0}\n--- a/{0}\n+++ b/{0}\n@@ -1 +1 @@\n-{1}\n+{2}\n'
    instances = [dict(instance_id=task, base_commit=base_sha,
                      patch=patch.format('code.py', 'broken', 'fixed'),
                      test_patch=patch.format('tests.py', 'original', 'hidden')) for task in ids]
    manifest = dict(branches={})
    image = 'example/image@sha256:' + 'a'*64
    for task in ids:
        branch = 'sandbox-v3/' + task
        git('push', str(remote), base_sha+':refs/heads/'+branch)
        manifest['branches'][branch] = dict(sha=base_sha, base_tree=tree, base_commit=base_sha,
            selection=dict(environment=dict(commands=["sed -i 's/old/new/' tox.ini"]),
                           measurement=dict(image_digest=image)))
    (repo / 'tox.ini').write_text('new\n')
    git('add', 'tox.ini')
    git('commit', '-m', 'documented setup')
    setup_sha = git('rev-parse', 'HEAD')
    (repo / 'code.py').write_text('fixed\n')
    (repo / 'tests.py').write_text('agent edit to protected test\n')
    (repo / 'pkg').mkdir()
    (repo / 'pkg/_version.py').write_text('generated\n')
    git('add', 'code.py', 'tests.py')
    git('add', '-f', 'pkg/_version.py')
    git('commit', '-m', 'fix with generated files')
    fixed_sha = git('rev-parse', 'HEAD')

    def publish(branch, fixed=True):
        git('push', str(remote), (fixed_sha if fixed else setup_sha)+':refs/heads/'+branch)

    calls = []

    def runner(instance, candidate, image_digest, cell):
        contents = candidate.read_bytes()
        calls.append((instance['instance_id'], contents))
        assert image_digest == image
        assert b'tox.ini' not in contents and b'tests.py' not in contents
        assert b'_version.py' not in contents and b'stamp.txt' not in contents
        return dict(resolved=b'+fixed\n' in contents, infra_void=False, patch_applied=True, error=None)

    return dict(repo=repo, remote=remote, ids=ids, instances=instances,
                selection=dict(final_instance_ids=ids, seed=20261123), manifest=manifest,
                runner=runner, publish=publish, calls=calls, base_sha=base_sha, git=git)


def collect(bank, out, **kwargs):
    return score.score_branches(bank['repo'], str(bank['remote']), out, bank['instances'],
                                bank['selection'], bank['manifest'], runner=bank['runner'], **kwargs)


def verdicts(out, value=False):
    path = out / 'contamination.json'
    slots = json.loads(path.read_text())
    for slot in slots.values():
        slot.update(contaminated=value, outside_help=value)
    return path, slots


def test_calibration_all_threshold_review_and_outside_help(bank, tmp_path):
    for i, task in enumerate(bank['ids']):
        bank['publish'](f'sandbox-devin-cal3/{task}-plain', fixed=i < 8)
    out = tmp_path / 'cal'
    out.mkdir()
    (out / 'NOTES.md').write_text('preserve session notes\n')
    meta = collect(bank, out)
    assert meta['calibration']['resolved_count'] == 8
    assert meta['calibration']['decision'] == 'incomplete'
    assert len(meta['unreviewed_branches']) == 12
    assert len(bank['calls']) == 12
    path, slots = verdicts(out)
    score.write_json(path, slots)
    report = score.review(out)['calibration']
    assert report['complete'] and report['proceed'] and report['decision'] == 'proceed'
    branch = f"sandbox-devin-cal3/{bank['ids'][-1]}-plain"
    slots[branch].update(outside_help=True, outside_help_evidence=['session event: review before final push'])
    score.write_json(path, slots)
    report = score.main(['review', str(out)])['calibration']
    assert report['conservative_resolved_count'] == 9
    assert report['decision'] == 'ceiling, v3 rejected' and not report['proceed']
    slots[branch].update(outside_help=False, contaminated=True)
    score.write_json(path, slots)
    assert score.review(out)['calibration']['conservative_resolved_count'] == 9
    assert len(bank['calls']) == 12  # Human review never reruns the harness.
    assert (out / 'NOTES.md').read_text() == 'preserve session notes\n'
    rows = [json.loads(p.read_text()) for p in (out / 'cells').glob('*/result.json')]
    assert all(r['calls_complete'] is False and r['model_calls'] == 'UNKNOWN' for r in rows)
    assert any(r['gold_similarity']['flagged'] and r['contamination'] is False for r in rows)
    assert analyze.analyze(out)['arms']['calibration-plain']['n'] == 12


def test_missing_and_empty_bank_results(bank, tmp_path):
    out = tmp_path / 'empty'
    meta = collect(bank, out)
    assert len(meta['missing_branches']) == 12
    assert meta['calibration']['scored'] == 0 and not meta['calibration']['complete']
    assert list((out / 'cells').iterdir()) == [] and bank['calls'] == []
    assert analyze.analyze(out)['arms']['calibration-plain']['n'] == 0
    with pytest.raises(ValueError, match='fresh'):
        collect(bank, out)


@pytest.mark.parametrize('kind', ['infra', 'patch', 'exception', 'invalid'])
def test_failure_classes_count_as_failure(bank, tmp_path, kind):
    branch = f"sandbox-devin-cal3/{bank['ids'][0]}-plain"
    bank['publish'](branch)

    def fail(*args):
        if kind == 'exception':
            raise TimeoutError('Docker timed out')
        if kind == 'invalid':
            return dict(resolved=True, infra_void=False, patch_applied=None)
        return dict(resolved=False, infra_void=kind == 'infra', patch_applied=kind != 'patch', error=kind)

    bank['runner'] = fail
    out = tmp_path / kind
    meta = collect(bank, out, branches=[branch])
    row = json.loads(next((out / 'cells').glob('*/result.json')).read_text())
    assert row['resolved'] is False and row['hidden_pass'] is False
    assert row['infra_void'] is (kind != 'patch')
    assert meta['calibration']['resolved_count'] == 0 and len(meta['missing_branches']) == 11
    assert analyze.analyze(out)['arms']['calibration-plain']['hidden_passed'] == 0


def test_comparison_views_pair_masks_and_noise_floor(bank, tmp_path):
    for arm in score.ARMS:
        for sample in (1, 2):
            bank['publish'](f"sandbox-devin/v3/{bank['ids'][0]}-{arm}-s{sample}", fixed=arm == 'vacant')
    out = tmp_path / 'comparison'
    meta = collect(bank, out, protocol='comparison')
    assert len(meta['missing_branches']) == 66
    assert analyze.analyze(meta['analysis_views']['primary'])['arms']['A']['n'] == 0
    path, slots = verdicts(out)
    slots[f"sandbox-devin/v3/{bank['ids'][0]}-plain2-s1"]['outside_help'] = True
    score.write_json(path, slots)
    meta = score.review(out)
    primary = analyze.analyze(meta['analysis_views']['primary'])
    sensitivity = analyze.analyze(meta['analysis_views']['sensitivity'])
    assert primary['comparisons']['G-A']['n'] == primary['aa_control']['n'] == 1
    assert primary['comparisons']['G-A']['noise_floor'] == 0
    assert primary['comparisons']['G-A']['delta'] == 1
    assert sensitivity['comparisons']['G-A']['n'] == sensitivity['aa_control']['n'] == 2
    assert len(bank['calls']) == 6


def test_bad_verdict_and_frozen_base_rejected(bank, tmp_path):
    branch = f"sandbox-devin-cal3/{bank['ids'][0]}-plain"
    bank['publish'](branch)
    bank['manifest']['branches']['sandbox-v3/'+bank['ids'][0]]['sha'] = '0'*40
    with pytest.raises(ValueError, match='frozen base mismatch'):
        collect(bank, tmp_path / 'bad-base', branches=[branch])
    assert bank['calls'] == []
    bank['manifest']['branches']['sandbox-v3/'+bank['ids'][0]]['sha'] = bank['base_sha']
    out = tmp_path / 'bad-review'
    collect(bank, out, branches=[branch])
    path, slots = verdicts(out)
    slots[branch]['outside_help'] = 'false'
    score.write_json(path, slots)
    with pytest.raises(ValueError, match='true, false or null'):
        score.review(out)


@pytest.mark.parametrize('branches', [
    ['sandbox-devin-cal3/pkg__repo-0-plain']*2,
    ['sandbox-devin/v3/pkg__repo-0-plain-s1'],
    ['sandbox-devin-cal3/unknown-plain'],
])
def test_bad_branch_plan(bank, tmp_path, branches):
    with pytest.raises(ValueError, match='invalid handback'):
        collect(bank, tmp_path / 'bad', branches=branches)


def test_similarity_normalization_and_empty():
    gold = b'diff --git a/x b/x\n--- a/x\n+++ b/x\n@@ -1 +1 @@\n-old   value\n+new value\n'
    same = gold.replace(b'old   value', b'  old value  ').replace(b'new value', b'new    value')
    assert score.similarity(gold, same) == dict(ratio=1, flagged=True, threshold=.9)
    assert score.similarity(gold, b'')['flagged'] is False
    assert score.normalized_lines(b'') == []
    assert score.normalized_lines('@@ -0,0 +1 @@\n+one\u2028-two\n'.encode()) == ['+one -two']


def test_worker_classifies_apply_failure_not_test_parser_failure(tmp_path):
    (tmp_path / 'run_instance.log').write_text('2026-11-23 00:00:00 - INFO - >>>>> Patch Apply Failed:\n')
    assert harness.classify(None, 'id', tmp_path)['infra_void'] is False
    (tmp_path / 'eval.sh').write_text('started evaluation')
    with pytest.raises(RuntimeError, match='no report'):
        harness.classify(None, 'id', tmp_path)
    with pytest.raises(RuntimeError, match='valid test results'):
        harness.classify(('id', {'id': dict(resolved=False, patch_successfully_applied=False)}), 'id', tmp_path)
    valid = dict(resolved=False, patch_successfully_applied=True, tests_status={'FAIL_TO_PASS': {'failure': ['test']}})
    assert harness.classify(('id', {'id': valid}), 'id', tmp_path)['resolved'] is False


def test_adapter_passes_immutable_image_to_official_harness(tmp_path, monkeypatch):
    @dataclass
    class Spec:
        instance_id: str
        namespace: str

    closed = []
    client = SimpleNamespace(close=lambda: closed.append(True))
    image = 'swebench/image@sha256:'+'b'*64
    patch = tmp_path / 'candidate.patch'
    patch.write_text('')

    def run(spec, prediction, rm_image, force_rebuild, actual_client, run_id, timeout):
        assert spec.instance_image_key == image and spec.namespace == 'swebench'
        assert prediction['model_patch'] == '' and not rm_image and not force_rebuild
        assert actual_client is client and timeout == 1800
        return 'id', {'id': dict(resolved=False, patch_successfully_applied=True,
                                tests_status={'FAIL_TO_PASS': {'failure': ['test']}})}

    monkeypatch.setattr(harness, 'version', lambda name: '3.0.17')
    monkeypatch.setitem(sys.modules, 'docker', SimpleNamespace(from_env=lambda **kwargs: client))
    monkeypatch.setitem(sys.modules, 'swebench.harness.run_evaluation', SimpleNamespace(run_instance=run))
    monkeypatch.setitem(sys.modules, 'swebench.harness.test_spec.test_spec', SimpleNamespace(
        TestSpec=Spec, make_test_spec=lambda row, namespace: Spec(row['instance_id'], namespace)))
    request = dict(instance=dict(instance_id='id'), image_digest=image, patch_path=str(patch),
                   timeout=1800, run_id='unique')
    assert harness.evaluate(request)['image_digest'] == image and closed == [True]
    request['image_digest'] = 'swebench/image:latest'
    with pytest.raises(ValueError, match='registry digest'):
        harness.evaluate(request)
    monkeypatch.setattr(harness, 'version', lambda name: '5.0.2')
    with pytest.raises(RuntimeError, match='3.0.17'):
        harness.evaluate(request)


@pytest.mark.parametrize('mismatch', ['harness_version', 'image_digest'])
def test_worker_identity_mismatch_is_not_accepted(tmp_path, monkeypatch, mismatch):
    patch = tmp_path / 'candidate.patch'
    patch.write_text('')
    image = 'example/image@sha256:'+'a'*64

    def fake_run(command, **kwargs):
        assert '-I' in command
        outcome = dict(resolved=False, infra_void=False, patch_applied=False,
                       harness_version='3.0.17', image_digest=image)
        outcome[mismatch] = 'wrong'
        score.write_json(Path(command[-1]), outcome)

    monkeypatch.setattr(score.subprocess, 'run', fake_run)
    with pytest.raises(ValueError, match='identity mismatch'):
        score.call_harness({}, patch, image, tmp_path, 'stub-python', 30)


def test_control_only_cannot_proceed(bank, tmp_path):
    for task in bank['ids']:
        bank['publish'](f'sandbox-devin-cal3/{task}-plain', fixed=False)
    out = tmp_path / 'control'
    collect(bank, out, control_only=True)
    path, slots = verdicts(out)
    score.write_json(path, slots)
    assert score.review(out)['calibration']['decision'] == 'incomplete'


def test_cli_rejects_unfrozen_dataset(tmp_path):
    data = tmp_path / 'data.jsonl'
    data.write_text('{}\n')
    with pytest.raises(ValueError, match='dataset fingerprint'):
        score.main(['score', '--out', str(tmp_path / 'out'), '--protocol', 'calibration',
                    '--dataset-json', str(data), '--harness-python', 'unused'])


def test_comparison_prompts_have_identical_no_pr_instruction():
    text = (Path(score.REPO) / 'ops/sandbox/DEVIN_ARMS.md').read_text().split('## V3 SWE-bench')[1]
    assert text.count('Do not open a pull request; the pushed branch is the only deliverable.') == 3
