"""歸檔讀取與外部快取；依 CLAUDE.md 鐵律，不把原始題庫輸出寫進 repo。"""

import hashlib
import os
import tarfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CACHE = Path(os.environ.get('VACANT_RELIANCE_CACHE',
                            Path.home() / '.cache/vacant/reliance')).expanduser().resolve()
if CACHE.is_relative_to(REPO):
    raise ValueError('VACANT_RELIANCE_CACHE must be outside the repository')


def prepare(dataset):
    if dataset == 'formal':
        archives = [REPO / 'ops/eval/evidence_20260925/formal/formal_jobs.tar.xz']
        dest = CACHE / 'formal'
    elif dataset in ('u274', 's36nc'):
        archives = sorted((REPO / 'ops/eval/evidence_20260927_nocap' /
                           dataset / 'raw').glob('chunk_*.tar.xz'))
        dest = CACHE / 'heldout' / dataset
    elif dataset in ('localformal', 's36'):
        subdir = 'formal' if dataset == 'localformal' else 's36'
        archives = [REPO / 'ops/eval/evidence_20260926_local' / subdir /
                    (subdir + '_jobs.tar.xz')]
        dest = CACHE / 'heldout' / dataset
    else:
        raise ValueError(f'unknown dataset: {dataset}')
    if not archives:
        raise FileNotFoundError(f'no repository archives for {dataset}')
    dest.mkdir(parents=True, exist_ok=True)
    for archive in archives:
        digest = hashlib.sha256(archive.read_bytes()).hexdigest()
        marker = dest / ('.' + archive.name + '.sha256')
        if marker.exists() and marker.read_text() == digest:
            continue
        with tarfile.open(archive) as tar:
            members = [m for m in tar if m.isfile() and
                       (dest / m.name).resolve().is_relative_to(dest) and
                       Path(m.name).name not in {'identity.key', 'identity.pub', 'vacant_id'}]
            tar.extractall(dest, members=members, filter='data')
        marker.write_text(digest)
    return dest
