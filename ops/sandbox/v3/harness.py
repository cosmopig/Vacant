"""Isolated adapter for the pinned official harness; never imported by a handback."""
import argparse
from dataclasses import asdict, dataclass
from importlib.metadata import version
import json
from pathlib import Path
import re


def classify(result, instance_id, log_dir):
    if result:
        report = result[1][instance_id]
        if (type(report.get('resolved')) is not bool
                or report.get('patch_successfully_applied') is not True
                or not report.get('tests_status')):
            raise RuntimeError('harness report has no valid test results')
        return dict(resolved=report['resolved'], infra_void=False,
                    patch_applied=True, error=None, report=report)
    log = log_dir / 'run_instance.log'
    text = log.read_text(errors='replace') if log.exists() else ''
    if (not (log_dir / 'eval.sh').exists()
            and re.search(r'^\d{4}-[^\n]+ - INFO - >>>>> Patch Apply Failed:', text, re.M)):
        return dict(resolved=False, infra_void=False, patch_applied=False,
                    error='candidate patch did not apply', report=None)
    raise RuntimeError('harness produced no report; inspect run_instance.log')


def evaluate(request):
    if version('swebench') != '3.0.17':
        raise RuntimeError('requires swebench==3.0.17')
    import docker
    from swebench.harness.run_evaluation import run_instance
    from swebench.harness.test_spec.test_spec import TestSpec, make_test_spec

    @dataclass
    class PinnedSpec(TestSpec):
        pinned_image: str = ''

        @property
        def instance_image_key(self):
            return self.pinned_image

    image = request['image_digest']
    if not re.fullmatch(r'[^\s@]+@sha256:[0-9a-f]{64}', image):
        raise ValueError('a registry digest, not a mutable image tag, is required')
    row = request['instance']
    spec = PinnedSpec(**asdict(make_test_spec(row, namespace='swebench')), pinned_image=image)
    client = docker.from_env(timeout=60)
    try:
        pred = dict(instance_id=row['instance_id'], model_name_or_path='handback',
                    model_patch=Path(request['patch_path']).read_bytes().decode('utf-8'))
        result = run_instance(spec, pred, False, False, client, request['run_id'],
                              timeout=request['timeout'])
        log_dir = Path('logs/run_evaluation') / request['run_id'] / 'handback' / row['instance_id']
        return {**classify(result, row['instance_id'], log_dir),
                'image_digest': spec.instance_image_key, 'harness_version': version('swebench'),
                'log_dir': str(log_dir.resolve())}
    finally:
        client.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--request', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--cleanup', action='store_true')
    args = parser.parse_args()
    request = json.loads(args.request.read_text())
    try:
        if args.cleanup:
            import docker
            client = docker.from_env(timeout=30)
            try:
                name = f"sweb.eval.{request['instance']['instance_id'].lower()}.{request['run_id']}"
                try:
                    client.containers.get(name).remove(force=True)
                except docker.errors.NotFound:
                    pass
                result = dict(cleanup_complete=True)
            finally:
                client.close()
        else:
            result = evaluate(request)
    except Exception as exc:
        result = dict(resolved=False, infra_void=True, patch_applied=None,
                      error=f'{type(exc).__name__}: {exc}', report=None)
    args.out.write_text(json.dumps(result, indent=2) + '\n')


if __name__ == '__main__':
    main()
