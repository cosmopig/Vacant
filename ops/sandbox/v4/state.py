"""單一 run writer 與原子 JSON；計分和人工稽核共用同一把鎖。"""
from contextlib import contextmanager
import fcntl
import json
from pathlib import Path


@contextmanager
def run_lock(out):
    with (Path(out) / '.score.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield


def write_json(path, value):
    temporary = path.with_name(path.name + '.tmp')
    temporary.write_text(json.dumps(value, indent=2) + '\n')
    temporary.replace(path)
