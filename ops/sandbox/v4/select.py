"""固定 v4 題庫與校準子集；沿用 v3 的官方 gold/base 驗證，不啟動 agent。"""
from pathlib import Path
import sys

if __name__ == '__main__':
    sys.path = [str(Path(__file__).resolve().parents[3])] + [
        p for p in sys.path if Path(p or '.').resolve() != Path(__file__).resolve().parent]

import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
from importlib.metadata import version
import json
import multiprocessing
import platform
import random
import re
import shutil
import subprocess
import time

from ops.sandbox.v3 import select as v3
from vacant_network.research import mcnemar_power

SEED = 20261124
CALIBRATION_SEED = 20261125
TARGET = 62
INITIAL_CAP = 12
HERE = Path(__file__).resolve().parent


def bucket(count):
    return '0' if count == 0 else '0.5' if count == 5 else '0.1-0.4'


def buckets(rows):
    counts = Counter(bucket(r['solved_count']) for r in rows)
    return {key: counts[key] for key in ('0', '0.1-0.4', '0.5')}


def candidates(instances, refs, excluded):
    if len(refs) != 10:
        raise ValueError('exactly ten references required')
    qualified, difficulty, prior = [], [], []
    for row in sorted(instances, key=lambda r: r['instance_id']):
        solved = [r['submission'] for r in refs if row['instance_id'] in r['resolved_ids']]
        if len(solved) <= 5:
            qualified.append(dict(instance_id=row['instance_id'], repo=row['repo'],
                                  difficulty=row['difficulty'], solved_count=len(solved),
                                  fraction=len(solved) / 10, resolved_by=solved))
    eligible = []
    for row in qualified:
        if row['difficulty'] == '>4 hours':
            difficulty.append(row)
        elif row['instance_id'] in excluded:
            prior.append(row)
        else:
            eligible.append(row)
    return eligible, dict(fraction_qualified=buckets(qualified),
                         difficulty_excluded=buckets(difficulty), v3_excluded=buckets(prior),
                         eligible=buckets(eligible)), dict(
        difficulty=[r['instance_id'] for r in difficulty], v3=[r['instance_id'] for r in prior])


def draw(pool):
    ordered = sorted(pool, key=lambda r: r['instance_id'])
    random.Random(SEED).shuffle(ordered)
    return ordered


def calibration(ids):
    if len(ids) < 12:
        raise ValueError('fewer than twelve feasible instances for calibration')
    return random.Random(CALIBRATION_SEED).sample(sorted(ids), 12)


def replacement_candidates(ordered, retained, retired, cap):
    if cap < INITIAL_CAP:
        raise ValueError('replacement cap cannot be below initial cap')
    occupied = {row['instance_id'] for row in retained} | set(retired)
    counts = Counter(row['repo'] for row in retained)
    return [row for row in ordered if row['instance_id'] not in occupied and counts[row['repo']] < cap]


def replay_replacements(report):
    """Replay recorded feasibility/native outcomes without rerunning or launching anything."""
    original = report['pre_replacement_instance_ids']
    replacements = report['replacements']
    removed = [row['outgoing'] for row in replacements]
    if len(set(removed)) != len(removed) or not set(removed) <= set(original):
        raise ValueError('invalid outgoing replacement IDs')
    lookup = {row['instance_id']: row for row in report['candidates']}
    ordered = [lookup[key] for key in report['ordered_draw']]
    retained = [lookup[key] for key in original if key not in removed]
    retired = set(removed)
    cap = report['cap_attempts'][-1]['repo_cap']
    attempts = iter(report['replacement_attempts'])
    maximum = max(Counter(row['repo'] for row in ordered).values(), default=cap)
    for replacement in replacements:
        accepted = None
        while accepted is None:
            for row in replacement_candidates(ordered, retained, retired, cap):
                attempt = next(attempts, None)
                key = row['instance_id']
                if attempt is None or (attempt['instance_id'], attempt['repo_cap']) != (key, cap):
                    raise ValueError('replacement attempts do not follow seeded order and cap')
                retired.add(key)
                if attempt['official_status'] != report['validation'][key]['status']:
                    raise ValueError('replacement feasibility evidence differs')
                if attempt['official_status'] == 'blocked':
                    raise ValueError('infrastructure cannot be a replacement rejection')
                if attempt['official_status'] == 'pass':
                    if attempt.get('native_status') not in ('ready', 'blocked'):
                        raise ValueError('missing native readiness evidence')
                    if attempt['native_status'] == 'ready':
                        accepted = key
                        retained.append(row)
                        break
            if accepted is None:
                cap += 1
                if cap > maximum:
                    raise ValueError('replacement draw exhausted')
        if replacement['incoming'] != accepted or replacement['repo_cap'] != cap:
            raise ValueError('replacement differs from first ready feasible candidate')
    final = sorted((row['instance_id'] for row in retained), key=report['ordered_draw'].index)
    if next(attempts, None) is not None or final != report['final_instance_ids'] or cap != report['repo_cap']:
        raise ValueError('final bank/cap differs from replay')
    previous = report['pre_replacement_calibration_ids']
    expected = calibration(final) if set(previous) & set(removed) else previous
    if report['calibration_instance_ids'] != expected:
        raise ValueError('calibration differs from conditional seeded redraw')
    return final


def power_summary(size):
    q, delta = 8 / 24, .15
    psi = (q + delta) / (2 * q)
    power = mcnemar_power(2 * size, q, psi, alpha=.05)
    return dict(instances=size, paired_units=2 * size, discordance=q, target_gain=delta,
                favorable_given_discordance=psi, alpha=.05, exact_power=power,
                target_power=.8, target_met=power >= .8,
                model='Independent paired Bernoulli outcomes; K~Binomial(n,q), B|K~Binomial(K,psi); two-sided exact McNemar.')


def choose(ordered, validate_many, checkpoint=lambda state: None, *, target=TARGET,
           initial_cap=INITIAL_CAP, jobs=3):
    cache, history = {}, []
    state = dict(selected=[], final_instance_ids=[], validation=cache, skips=[],
                 cap_attempts=history, repo_cap=initial_cap, status='incomplete', blocker=None)
    maximum = max(Counter(r['repo'] for r in ordered).values(), default=initial_cap)
    for cap in range(initial_cap, max(initial_cap, maximum) + 1):
        selected, skips, counts = [], [], Counter()
        state.update(selected=selected, final_instance_ids=[], skips=skips, repo_cap=cap)
        for index, row in enumerate(ordered):
            key = row['instance_id']
            if counts[row['repo']] >= cap:
                skips.append(dict(instance_id=key, reason=f'repo cap ({cap})'))
                continue
            if key not in cache:
                pending = [r['instance_id'] for r in ordered[index:]
                           if r['instance_id'] not in cache and counts[r['repo']] < cap][:jobs]
                results = validate_many(pending)
                if set(results) != set(pending):
                    raise ValueError('validator results do not match scheduled instances')
                cache.update(results)
                blocked = next((r for r in results.values() if r['status'] == 'blocked'), None)
                if blocked:
                    state.update(status='blocked', blocker=blocked['error'])
                    checkpoint(state)
                    return state
            if cache[key]['status'] == 'pass':
                selected.append(row)
                counts[row['repo']] += 1
                state['final_instance_ids'].append(key)
            else:
                skips.append(dict(instance_id=key, reason=cache[key]['status']))
            checkpoint(state)
            if len(selected) == target:
                break
        history.append(dict(repo_cap=cap, selected_count=len(selected),
                            exhausted_draw=len(selected) < target))
        all_checked = len(cache) == len(ordered)
        total_pass = sum(r['status'] == 'pass' for r in cache.values())
        if len(selected) == target or (all_checked and len(selected) == total_pass):
            state['status'] = 'complete' if len(selected) == target else 'complete_undersized'
            state['cap_reason'] = ('Initial cap suffices.' if cap == initial_cap else
                'Every smaller cap exhausted the seeded draw below target; this is the smallest '
                'cap reaching target, or including every feasible instance when fewer than target exist.')
            checkpoint(state)
            return state
    raise RuntimeError('selection exhausted caps without including all feasible instances')


def write_json(path, data):
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(data, indent=2) + '\n')
    temporary.replace(path)


def log(message):
    print(f'{datetime.now(timezone.utc).isoformat(timespec="seconds")} {message}', flush=True)


def validate_with_backoff(row, work, timeout):
    delay = 900
    while True:
        usage = shutil.disk_usage(work)
        if usage.used / usage.total >= .85:
            raise v3.InfrastructureError('disk usage is at least 85%; stopped, not an instance rejection')
        try:
            result = v3.validate_instance(row, work, timeout)
            if result['status'] != 'instance image unavailable':
                return result
            reason = 'Unverified image unavailability (pull-stream errors may be masked): ' + result.get('error', '')
        except v3.InfrastructureError as exc:
            if not re.search(r'\b429\b|too\s*many\s*requests|rate[ _-]*limit|pull limit', str(exc), re.I):
                raise
            reason = 'Pull rate limit: ' + str(exc)
        log(f'{row["instance_id"]}; retrying SAME instance in {delay}s: {reason}')
        time.sleep(delay)
        delay = min(delay * 2, 3600)


def cleanup_instance_image(outcome):
    image_id = outcome.get('image_id')
    if not image_id:
        return
    for command in (['docker', 'image', 'inspect', image_id], ['docker', 'rmi', image_id]):
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode:
            if 'no such image' in result.stderr.lower():
                return
            raise v3.InfrastructureError(f'instance image cleanup failed: {result.stderr.strip()}')
    log(f'Removed cached instance image {image_id}; shared layers referenced by other images are retained')


def validate_cached(task):
    row, root, timeout, context = task
    work = Path(root) / 'instances' / row['instance_id']
    work.mkdir(parents=True, exist_ok=True)
    cache = work / 'validation.json'
    identity = v3.digest(v3.canonical(dict(instance=row, context=context)))
    if cache.exists():
        saved = json.loads(cache.read_text())
        if saved['input_sha256'] != identity:
            raise ValueError('validation cache fingerprint mismatch: ' + row['instance_id'])
        if saved['outcome']['status'] == 'instance image unavailable':
            cache.unlink()
            log(f'Cleared unverified image-unavailable cache for {row["instance_id"]}')
            return validate_cached(task)
        for control in saved['outcome'].get('controls', {}).values():
            if v3.digest(Path(control['report_path']).read_bytes()) != control['report_sha256']:
                raise ValueError('cached harness evidence changed: ' + row['instance_id'])
        try:
            cleanup_instance_image(saved['outcome'])
        except v3.InfrastructureError as exc:
            return row['instance_id'], dict(status='blocked', error=str(exc))
        log(f'Using cached validation for {row["instance_id"]}: {saved["outcome"]["status"]}')
        return row['instance_id'], saved['outcome']
    try:
        result = validate_with_backoff(row, work, timeout)
        write_json(cache, dict(input_sha256=identity, outcome=result))
        log(f'Cached validation for {row["instance_id"]}: {result["status"]}')
        cleanup_instance_image(result)
    except v3.InfrastructureError as exc:
        return row['instance_id'], dict(status='blocked', error=str(exc))
    return row['instance_id'], result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--experiments', type=Path, required=True)
    parser.add_argument('--dataset-json', type=Path, required=True)
    parser.add_argument('--work-dir', type=Path, required=True)
    parser.add_argument('--out', type=Path, default=HERE / 'SELECTION.json')
    parser.add_argument('--overwrite-frozen', action='store_true',
                        help='Explicitly permit replacing a completed frozen bank and its calibration.')
    parser.add_argument('--jobs', type=int, choices=(1, 2, 3, 4), default=2)
    parser.add_argument('--timeout', type=int, default=1800)
    args = parser.parse_args(argv)
    if args.out.exists() and not args.overwrite_frozen:
        previous = json.loads(args.out.read_text())
        if previous.get('status', '').startswith('complete'):
            missing_calibration = not previous.get('calibration_instance_ids')
            missing_power = not previous.get('power')
            if not missing_calibration and not missing_power:
                parser.error('refusing to overwrite frozen bank; use --overwrite-frozen or a different --out')
            ids = previous.get('final_instance_ids')
            if not ids:
                parser.error('completed checkpoint has no saved instance IDs; refusing to replace it')
            if missing_calibration:
                previous['calibration_instance_ids'] = calibration(ids)
            if missing_power:
                previous['power'] = power_summary(len(ids))
            write_json(args.out, previous)
            log(f'Resumed completed checkpoint: preserved {len(ids)} IDs and validation; finalized metadata offline')
            return 0
    log(f'Starting v4 selector: jobs={args.jobs}, target={TARGET}, initial cap={INITIAL_CAP}; pull backoff=900..3600s')
    if version('swebench') != v3.HARNESS_VERSION:
        raise ValueError('requires swebench==' + v3.HARNESS_VERSION)
    instances = [json.loads(line) for line in args.dataset_json.read_text().splitlines()]
    if v3.digest(v3.canonical(instances)) != v3.DATASET_CONTENT_SHA256:
        raise ValueError('dataset content differs from pinned Verified revision')
    refs, ranking = v3.references(args.experiments, instances)
    prior = json.loads((HERE.parent / 'v3/SELECTION.json').read_text())
    if refs != prior['references']:
        raise ValueError('reference submissions differ from frozen v3 references')
    excluded = prior['final_instance_ids']
    if len(excluded) != 12 or len(set(excluded)) != 12:
        raise ValueError('expected exactly twelve frozen v3 instance IDs')
    pool, counts, exclusions = candidates(instances, refs, set(excluded))
    ordered = draw(pool)
    args.work_dir = args.work_dir.resolve()
    args.work_dir.mkdir(parents=True, exist_ok=True)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    info = subprocess.run(['docker', 'info', '--format', '{{json .}}'], capture_output=True, text=True)
    context = dict(harness_version=v3.HARNESS_VERSION, timeout_s=args.timeout,
                   validator_sha256=v3.digest(Path(v3.__file__).read_bytes()),
                   experiments_sha=v3.EXPERIMENTS_SHA, dataset_revision=v3.DATASET_SHA)
    report = dict(experiments_repo='https://github.com/swe-bench/experiments',
        experiments_sha=v3.EXPERIMENTS_SHA, dataset=v3.DATASET, dataset_revision=v3.DATASET_SHA,
        dataset_content_sha256=v3.DATASET_CONTENT_SHA256, references=refs, submission_ranking=ranking,
        fraction_rule='0 <= resolved_count/10 <= 0.5', strict_rule_eligible_count=counts['eligible']['0.1-0.4'],
        widening_reason=f"Strict 0 < fraction < 0.5 leaves only {counts['eligible']['0.1-0.4']} eligible instances after v3 exclusion; owner approved inclusive endpoints.",
        v3_selection_sha256=v3.digest((HERE.parent / 'v3/SELECTION.json').read_bytes()),
        target_size=TARGET, initial_repo_cap=INITIAL_CAP, seed=SEED, calibration_seed=CALIBRATION_SEED,
        draw_rule='Sort eligible IDs, then Python random.Random(seed).shuffle; first feasible under cap.',
        calibration_rule='random.Random(20261125).sample(sorted(final_instance_ids), 12)',
        candidate_count=len(pool), fraction_bucket_counts=counts, pool_exclusions=exclusions,
        candidates=pool, ordered_draw=[r['instance_id'] for r in ordered],
        candidate_repo_counts=dict(Counter(r['repo'] for r in pool)), validation_context=context,
        environment=dict(python=sys.version, platform=platform.platform(),
            disk_free_bytes=shutil.disk_usage(args.work_dir).free, parallel_processes=args.jobs,
            docker_available=info.returncode == 0,
            docker_server_version=json.loads(info.stdout)['ServerVersion'] if info.returncode == 0 else None),
        selected=[], final_instance_ids=[], calibration_instance_ids=[], status='incomplete', blocker=None)

    def checkpoint(state):
        report.update(state)
        write_json(args.out, report)

    checkpoint({})
    if info.returncode:
        checkpoint(dict(status='blocked', blocker=info.stderr))
        return 2
    lookup = {r['instance_id']: r for r in instances}
    with ProcessPoolExecutor(max_workers=args.jobs, mp_context=multiprocessing.get_context('spawn')) as executor:
        def validate_many(keys):
            tasks = [(lookup[key], str(args.work_dir), args.timeout, context) for key in keys]
            return dict(executor.map(validate_cached, tasks))

        state = choose(ordered, validate_many, checkpoint, jobs=args.jobs)
    if state['status'].startswith('complete'):
        report['calibration_instance_ids'] = calibration(state['final_instance_ids'])
        report['power'] = power_summary(len(state['final_instance_ids']))
        checkpoint({})
    print(json.dumps(dict(status=report['status'], selected=len(report['final_instance_ids']),
                          repo_cap=report.get('repo_cap'), blocker=report['blocker'])))
    return 0 if report['status'].startswith('complete') else 2


if __name__ == '__main__':
    raise SystemExit(main())
