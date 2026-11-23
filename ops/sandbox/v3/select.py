"""以公開結果固定 v3 候選池；gold/base 容器驗證不含任何 agent run。"""
from pathlib import Path
import sys

if __name__ == '__main__':
    # Keep this filename from shadowing the stdlib select extension.
    sys.path = [p for p in sys.path if Path(p or '.').resolve() != Path(__file__).resolve().parent]

import argparse
from collections import Counter
import hashlib
from importlib.metadata import version
import json
import os
import platform
import random
import re
import shutil
import subprocess

EXPERIMENTS_SHA = '40f164d5b8f1d249bf95a6df8b74b577fd8e519d'
DATASET = 'princeton-nlp/SWE-bench_Verified'
DATASET_SHA = 'c104f840cc67f8b6eec6f759ebc8b2693d585d4a'
DATASET_CONTENT_SHA256 = '4f74c5cff0d5838cd8026295d7ed61ed8171147207ead7d795ff18c977712ae2'
HARNESS_VERSION = '3.0.17'
SEED = 20261123
BASE_PATCH = ('diff --git a/.swebench_v3_base_control b/.swebench_v3_base_control\n'
              'new file mode 100644\n--- /dev/null\n+++ b/.swebench_v3_base_control\n'
              '@@ -0,0 +1 @@\n+base control; no source or test changes\n')


def digest(data):
    return hashlib.sha256(data).hexdigest()


def canonical(data):
    return json.dumps(data, sort_keys=True, separators=(',', ':')).encode()


def git(repo, *args):
    return subprocess.check_output(['git', '-C', str(repo), *args], text=True)


def references(repo, instances):
    import yaml

    ids = {r['instance_id'] for r in instances}
    paths = git(repo, 'ls-tree', '-r', '--name-only', EXPERIMENTS_SHA,
                '--', 'evaluation/verified').splitlines()
    files = set(paths)
    ranked = []
    for path in paths:
        if not re.fullmatch(r'evaluation/verified/[^/]+/results/results.json', path):
            continue
        raw = git(repo, 'show', f'{EXPERIMENTS_SHA}:{path}').encode()
        resolved = json.loads(raw)['resolved']
        if not isinstance(resolved, list) or any(not isinstance(x, str) for x in resolved):
            raise ValueError('invalid resolved list: ' + path)
        root = Path(path).parent.parent.as_posix()
        metadata_path = next((root + '/' + name for name in ('metadata.yaml', 'metadata.yml')
                              if root + '/' + name in files), None)
        metadata_raw = git(repo, 'show', f'{EXPERIMENTS_SHA}:{metadata_path}').encode() if metadata_path else b''
        metadata = yaml.safe_load(metadata_raw) or {}
        submission = Path(root).name
        info = metadata.get('info', {})
        date = metadata.get('date') or info.get('date')
        date_source = 'metadata' if date else 'submission directory prefix'
        if not date and re.match(r'^\d{8}_', submission):
            date = f'{submission[:4]}-{submission[4:6]}-{submission[6:8]}'
        solved = set(resolved) & ids
        ranked.append(dict(submission=submission, name=info.get('name', submission),
                           date=str(date) if date else None, date_source=date_source,
                           resolved_count=len(solved), denominator=len(ids),
                           resolve_rate=len(solved) / len(ids), results_path=path,
                           results_sha256=digest(raw), metadata_path=metadata_path,
                           metadata_sha256=digest(metadata_raw) if metadata_path else None,
                           outside_dataset_count=len(set(resolved) - ids), resolved_ids=sorted(solved)))
    ranked.sort(key=lambda r: (-r['resolved_count'], r['submission']))
    if len(ranked) < 10:
        raise ValueError('fewer than ten public Verified result files')
    return ranked[:10], [{k: v for k, v in r.items() if k != 'resolved_ids'} for r in ranked]


def candidates(instances, refs):
    result = []
    if len(refs) != 10:
        raise ValueError('exactly ten references required')
    for row in sorted(instances, key=lambda r: r['instance_id']):
        solved_by = [r['submission'] for r in refs if row['instance_id'] in r['resolved_ids']]
        if 0 < len(solved_by) < 5:
            result.append(dict(instance_id=row['instance_id'], repo=row['repo'], difficulty=row['difficulty'],
                               solved_count=len(solved_by), fraction=len(solved_by) / 10, resolved_by=solved_by))
    return result


def draw(pool):
    ordered = sorted(pool, key=lambda r: r['instance_id'])
    random.Random(SEED).shuffle(ordered)
    return ordered


def observed_failures(names, statuses, output):
    lines = output.splitlines()
    return [name for name in names if statuses.get(name) in ('FAILED', 'ERROR') or any(
        line == f'{marker}: {name}' or line.startswith(f'{marker}: {name} ')
        for line in lines for marker in ('FAIL', 'ERROR'))]


class InfrastructureError(RuntimeError):
    pass


def choose(ordered, validate, checkpoint=lambda state: None):
    state = dict(selected=[], final_instance_ids=[], skips=[], validation={}, blocker=None, status='incomplete')
    counts = Counter()
    for row in ordered:
        instance_id = row['instance_id']
        reason = None
        if row['difficulty'] == '>4 hours':
            reason = 'difficulty >4 hours'
        elif counts[row['repo']] >= 3:
            reason = 'repo cap (3)'
        else:
            try:
                outcome = validate(instance_id)
            except InfrastructureError as exc:
                state.update(blocker=str(exc), status='blocked')
                state['validation'][instance_id] = dict(status='blocked', error=str(exc))
                checkpoint(state)
                return state
            state['validation'][instance_id] = outcome
            if outcome['status'] != 'pass':
                reason = outcome['status']
        if reason:
            state['skips'].append(dict(instance_id=instance_id, reason=reason))
        else:
            state['selected'].append(row)
            state['final_instance_ids'].append(instance_id)
            counts[row['repo']] += 1
        checkpoint(state)
        if len(state['selected']) == 12:
            state['status'] = 'complete'
            checkpoint(state)
            return state
    state['status'] = 'insufficient feasible candidates'
    checkpoint(state)
    return state


def validate_instance(instance, work, timeout=1800):
    import docker
    from swebench.harness.grading import get_logs_eval
    from swebench.harness.run_evaluation import run_instance
    from swebench.harness.test_spec.test_spec import make_test_spec

    if version('swebench') != HARNESS_VERSION:
        raise InfrastructureError('validation requires swebench==' + HARNESS_VERSION)
    if shutil.disk_usage(work).free < 20 * 1024 ** 3:
        raise InfrastructureError('less than 20 GiB free before validation; stopped, not an instance rejection')
    client = docker.from_env(timeout=1800)
    try:
        spec = make_test_spec(instance, namespace='swebench')
        before = {image.id for image in client.images.list()}
        try:
            client.images.get(spec.instance_image_key)
        except docker.errors.ImageNotFound:
            try:
                client.images.pull(spec.instance_image_key)
            except docker.errors.ImageNotFound as exc:
                return dict(status='instance image unavailable', error=str(exc))
            except docker.errors.APIError as exc:
                raise InfrastructureError('image pull failed: ' + str(exc)) from exc
        image = client.images.get(spec.instance_image_key)
        evidence = dict(image=spec.instance_image_key, image_id=image.id,
                        repo_digests=image.attrs.get('RepoDigests', []), controls={})
        run_id = 'v3-' + digest(canonical(dict(instance=instance, harness=HARNESS_VERSION,
                                              experiments=EXPERIMENTS_SHA, timeout=timeout,
                                              image_id=image.id, base_patch=BASE_PATCH)))[:16]
        old_cwd = Path.cwd()
        try:
            os.chdir(work)
            for control, patch in (('gold', instance['patch']), ('base', BASE_PATCH)):
                prediction = dict(instance_id=instance['instance_id'], model_name_or_path=control, model_patch=patch)
                print(f"Validating {instance['instance_id']} {control}", flush=True)
                result = run_instance(spec, prediction, False, False, client, run_id, timeout=timeout)
                log_dir = work / 'logs/run_evaluation' / run_id / control / instance['instance_id']
                if not result:
                    raise InfrastructureError(f'no {control} harness report for {instance["instance_id"]}; see {log_dir}')
                report = result[1][instance['instance_id']]
                statuses, found = get_logs_eval(spec, log_dir / 'test_output.txt')
                f2p = report.get('tests_status', {}).get('FAIL_TO_PASS', {})
                evidence['controls'][control] = dict(resolved=report['resolved'],
                    fail_to_pass_success=len(f2p.get('success', [])), fail_to_pass_failure=len(f2p.get('failure', [])),
                    report_path=str(log_dir / 'report.json'), report_sha256=digest((log_dir / 'report.json').read_bytes()))
                if not found or not report.get('patch_successfully_applied') or not statuses:
                    raise InfrastructureError(f'invalid {control} test output for {instance["instance_id"]}; see {log_dir}')
                if control == 'gold' and not report['resolved']:
                    return dict(status='gold did not resolve', **evidence)
                if control == 'base':
                    failures = observed_failures(f2p.get('failure', []), statuses,
                                                 (log_dir / 'test_output.txt').read_text())
                    evidence['controls'][control]['observed_fail_to_pass_failures'] = failures
                    if report['resolved'] or not failures:
                        return dict(status='base lacks an observed FAIL_TO_PASS failure', **evidence)
            return dict(status='pass', **evidence)
        finally:
            os.chdir(old_cwd)
            if image.id not in before:
                client.images.remove(spec.instance_image_key)
    except docker.errors.DockerException as exc:
        raise InfrastructureError(str(exc)) from exc
    finally:
        client.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--experiments', type=Path, required=True)
    parser.add_argument('--dataset-json', type=Path)
    parser.add_argument('--work-dir', type=Path, required=True)
    parser.add_argument('--out', type=Path, default=Path(__file__).with_name('SELECTION.json'))
    args = parser.parse_args(argv)
    if args.dataset_json:
        instances = [json.loads(line) for line in args.dataset_json.read_text().splitlines()]
    else:
        from datasets import load_dataset
        instances = list(load_dataset(DATASET, revision=DATASET_SHA, split='test'))
    if digest(canonical(instances)) != DATASET_CONTENT_SHA256:
        raise ValueError('dataset content differs from pinned Verified revision')
    refs, ranking = references(args.experiments, instances)
    pool = candidates(instances, refs)
    ordered = draw(pool)
    try:
        docker_info = subprocess.run(['docker', 'info', '--format', '{{json .}}'], capture_output=True, text=True)
        docker_ok = docker_info.returncode == 0
        docker_error = docker_info.stderr if not docker_ok else None
        engine = json.loads(docker_info.stdout)['ServerVersion'] if docker_ok else None
    except FileNotFoundError as exc:
        docker_ok, docker_error, engine = False, str(exc), None
    args.work_dir = args.work_dir.resolve()
    args.work_dir.mkdir(parents=True, exist_ok=True)
    report = dict(experiments_repo='https://github.com/swe-bench/experiments', experiments_sha=EXPERIMENTS_SHA,
                  dataset=DATASET, dataset_revision=DATASET_SHA, dataset_content_sha256=DATASET_CONTENT_SHA256,
                  seed=SEED, tie_break='resolved_count descending, submission directory ascending',
                  fraction_rule='0 < resolved_count/10 < 0.5', difficulty_exclusion='>4 hours',
                  repo_cap=3, target_size=12, references=refs, submission_ranking=ranking,
                  candidate_count=len(pool), candidates=pool, ordered_draw=[r['instance_id'] for r in ordered],
                  environment=dict(python=sys.version, platform=platform.platform(), docker_available=docker_ok,
                                   docker_server_version=engine, docker_error=docker_error,
                                   disk_free_bytes=shutil.disk_usage(args.work_dir).free,
                                   harness_version=version('swebench'), validation_timeout_s=1800),
                  selected=[], final_instance_ids=[], skips=[], validation={}, blocker=None, status='candidate list only')

    def checkpoint(state):
        report.update(state)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=2) + '\n')

    checkpoint({})
    if docker_ok:
        lookup = {r['instance_id']: r for r in instances}
        choose(ordered, lambda key: validate_instance(lookup[key], args.work_dir), checkpoint)
    else:
        checkpoint(dict(status='blocked', blocker='Docker unavailable; candidates not harness-validated'))
    print(json.dumps(dict(status=report['status'], candidate_count=len(pool),
                          final_instance_ids=report['final_instance_ids'], blocker=report['blocker'])))
    return 0 if report['status'] == 'complete' else 2


if __name__ == '__main__':
    raise SystemExit(main())
