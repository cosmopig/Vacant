"""在釘死的官方 image 量測 base P2P，凍結節點與 timeout；不套用任何 patch。"""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import io
import json
from pathlib import Path
import shlex
import tarfile
import time

from ops.sandbox.v3 import kit
from ops.sandbox.v3.recipes import secure_downloads


def measure(key, row, snapshot, pinned, work):
    import docker
    from swebench.harness.test_spec.test_spec import make_test_spec
    from swebench.harness.constants import MAP_REPO_VERSION_TO_SPECS

    work = work.resolve()
    case = work / key
    case.mkdir(parents=True, exist_ok=True)
    omissions = []
    broad = kit.resolve(Path(snapshot['workspace']), row, omissions)
    (case / 'discovery.json').write_text(json.dumps(broad))
    runner = Path(__file__).with_name('p2p_runner.py').resolve()
    spec = make_test_spec(row)
    settings = MAP_REPO_VERSION_TO_SPECS[row['repo']][row['version']]
    commands = [line.replace('conda create -n testbed', f'conda create --prefix "$PWD/.envs/{key}"')
                .replace('conda env create --file environment.yml', f'conda env create --prefix "$PWD/.envs/{key}" --file environment.yml')
                .replace('conda activate testbed', f'conda activate "$PWD/.envs/{key}"')
                for line in spec.env_script_list if not line.startswith('source ')]
    pytest_version = '6.2.5' if settings['python'] == '3.6' else '7.4.4'
    pytest_install = f'python -m pip install pytest=={pytest_version}' + (' pytest-django==4.5.2' if broad['django'] else '')
    if row['repo'] == 'sympy/sympy':
        pytest_install += ' py==1.10.0'
    commands += [f'cd {shlex.quote(key)}', *[command.replace('/testbed', '$PWD') for command in settings.get('pre_install', [])],
                 settings.get('install', 'true'), pytest_install]
    environment = dict(instance_id=key, python=settings['python'], commands=secure_downloads(commands))
    saved = case / 'selection.json'
    if saved.exists():
        cached = json.loads(saved.read_text())
        evidence = cached.get('measurement', {})
        if (evidence.get('runner_sha256') == hashlib.sha256(runner.read_bytes()).hexdigest()
                and evidence.get('image_id') == pinned['image_id']
                and cached['environment'] == environment
                and set(cached['label_nodes']) == {t['label'] for t in broad['selectors']}
                and cached['omitted_nonbase_labels'] == omissions):
            print(key, 'CACHED', cached['measured_base_seconds'], cached['timeout_s'], flush=True)
            return key, cached
    client = docker.from_env()
    image = client.images.get(pinned['repo_digests'][0])
    if image.id != pinned['image_id']:
        raise ValueError('pinned image changed: ' + key)
    container = client.containers.run(image.id, ['tail', '-f', '/dev/null'], detach=True,
        volumes={str(work): {'bind': str(work), 'mode': 'rw'},
                 str(runner.parent): {'bind': '/gate', 'mode': 'ro'}})
    def run(command):
        result = container.exec_run(['bash', '-c', command], workdir='/testbed')
        return result.exit_code, result.output.decode(errors='replace')
    try:
        base = shlex.quote(row['base_commit'])
        changed = container.exec_run(['git', 'diff', '--name-only', '-z', row['base_commit']], workdir='/testbed')
        archive = io.BytesIO()
        with tarfile.open(fileobj=archive, mode='w') as tar:
            for raw_path in changed.output.split(b'\0'):
                if not raw_path:
                    continue
                path = raw_path.decode()
                blob = container.exec_run(['git', 'show', row['base_commit'] + ':' + path], workdir='/testbed')
                if blob.exit_code:
                    raise ValueError('unexpected image-only tracked file: ' + path)
                mode = container.exec_run(['git', 'ls-tree', row['base_commit'], '--', path], workdir='/testbed').output.split()[0]
                entry = tarfile.TarInfo(path)
                entry.mode = int(mode, 8) & 0o777
                entry.size = len(blob.output)
                tar.addfile(entry, io.BytesIO(blob.output))
        if changed.output:
            container.put_archive('/testbed', archive.getvalue())
        code, output = run(f'git diff --exit-code {base}')
        if code or output.strip():
            raise ValueError('instance image is not unchanged base: ' + output)
        python = '/opt/miniconda3/envs/testbed/bin/python'
        code, output = run(pytest_install.replace('python', python, 1))
        (case / 'setup.log').write_text(output)
        if code:
            raise ValueError('pytest setup failed: ' + key)
        command = f'{python} -I /gate/p2p_runner.py /testbed {case}/discovery.json {case}/discovery-report.json'
        code, output = run(command)
        (case / 'discovery.log').write_text(output)
        report = json.loads((case / 'discovery-report.json').read_text())
        config = kit.freeze(broad, report, 1, environment)
        (case / 'selection.json').write_text(json.dumps(config, indent=2) + '\n')
        start = time.monotonic()
        code, output = run(f'{python} -I /gate/p2p_runner.py /testbed {case}/selection.json {case}/base-report.json')
        seconds = time.monotonic() - start
        (case / 'base.log').write_text(output)
        final = json.loads((case / 'base-report.json').read_text())
        if code or final['skipped'] or final['deselected'] or final['failed']:
            raise ValueError('frozen base P2P failed: ' + key)
        config = kit.freeze(broad, report, seconds, environment)
        config['omitted_nonbase_labels'] = omissions
        config['measurement'] = dict(image_id=image.id, image_digest=pinned['repo_digests'][0],
            runner_sha256=hashlib.sha256(runner.read_bytes()).hexdigest(), container_id=container.id,
            base_report_sha256=hashlib.sha256((case / 'base-report.json').read_bytes()).hexdigest())
        (case / 'selection.json').write_text(json.dumps(config, indent=2) + '\n')
        print(key, 'PASS', round(seconds, 3), config['timeout_s'], flush=True)
        return key, config
    finally:
        container.stop(timeout=1)
        container.remove()
        client.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset-json', type=Path, required=True)
    parser.add_argument('--snapshots', type=Path, required=True)
    parser.add_argument('--work', type=Path, required=True)
    args = parser.parse_args()
    rows = {r['instance_id']: r for r in map(json.loads, args.dataset_json.read_text().splitlines())}
    snapshots = json.loads(args.snapshots.read_text())
    selection = json.loads(Path(__file__).with_name('SELECTION.json').read_text())
    results, errors = [], {}
    with ThreadPoolExecutor(2) as pool:
        futures = {pool.submit(measure, key, rows[key], snapshots[key],
                   selection['validation'][key], args.work): key for key in snapshots}
        for future in as_completed(futures):
            try:
                results.append(future.result())
            except Exception as exc:
                key = futures[future]
                errors[key] = str(exc)
                print(key, 'ERROR', str(exc), flush=True)
    (args.work / 'errors.json').write_text(json.dumps(errors, indent=2) + '\n')
    if errors:
        raise ValueError('base P2P preflight failed: ' + repr(errors))
    (args.work / 'measurements.json').write_text(json.dumps(dict(results), indent=2) + '\n')


if __name__ == '__main__':
    main()
