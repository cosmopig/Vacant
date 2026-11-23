"""保留釘死的官方映像；429 不變成任務拒絕，依 15→30→60 分鐘重試。"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import shutil
import subprocess
import time


HERE = Path(__file__).resolve().parent


def log(message):
    print(datetime.now(timezone.utc).isoformat(timespec='seconds'), message, flush=True)


def image_for(selection, task):
    outcome = selection['validation'][task]
    images = outcome['repo_digests']
    if outcome['status'] != 'pass' or len(images) != 1 or not re.fullmatch(r'[^\s@]+@sha256:[0-9a-f]{64}', images[0]):
        raise ValueError('one feasibility-verified image digest required: ' + task)
    return images[0]


def retryable(error):
    return bool(re.search(r'\b429\b|too\s*many\s*requests|rate[ _-]*limit|pull limit|'
                          r'\b50[234]\b|timed? ?out|timeout|connection reset|unexpected EOF|TLS handshake', str(error), re.I))


def ensure_image(image, *, sleep=time.sleep, run=subprocess.run, disk=shutil.disk_usage):
    delay = 900
    while True:
        found = run(['docker', 'image', 'inspect', image], capture_output=True, text=True)
        if found.returncode == 0:
            log('Keeping pinned image ' + image)
            return
        usage = disk('/')
        if usage.used / usage.total >= .85:
            log('Disk guard: >=85% used; preserving images and waiting 900s')
            sleep(900)
            continue
        log('Pulling pinned image ' + image)
        pulled = run(['docker', 'pull', image], capture_output=True, text=True)
        if pulled.returncode == 0:
            continue
        error = pulled.stdout + '\n' + pulled.stderr
        if not retryable(error):
            raise RuntimeError('Image pull failed: ' + error[-8000:])
        log(f'Retrying SAME image in {delay}s: {error[-2000:]}')
        sleep(delay)
        delay = min(delay * 2, 3600)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--selection', type=Path, default=HERE / 'SELECTION.json')
    args = parser.parse_args(argv)
    selection = json.loads(args.selection.read_text())
    for task in selection['calibration_instance_ids']:
        log('Calibration image: ' + task)
        ensure_image(image_for(selection, task))
    log('All twelve calibration images retained; no image cleanup requested')


if __name__ == '__main__':
    main()
