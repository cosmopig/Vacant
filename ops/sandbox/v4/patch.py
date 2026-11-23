"""v4 canonical patch: retain agent tests, excluding only the root manifest."""
import os
from pathlib import Path
import subprocess
import tempfile

from ops.sandbox.v3 import patch as v3


def derive_patch(base, handback, test_patch='', setup_commands=()):
    base, handback = Path(base), Path(handback)
    if not base.is_dir() or not handback.is_dir():
        raise ValueError('base and handback directories required')
    excluded = {'VACANT_TESTS.txt'}
    baseline = v3._files(base, excluded)
    before = v3.normalize_setup(baseline, setup_commands)
    after = v3._files(handback, excluded)
    for name, raw in baseline.items():
        if (before[name] != raw and name in after and after[name][0] != 0o120000
                and after[name][1] == raw[1]):
            after[name] = (after[name][0], before[name][1])
    binary = {name for name, (_, data) in [*before.items(), *after.items()] if b'\0' in data}
    before = {name: value for name, value in before.items() if name not in binary}
    after = {name: value for name, value in after.items() if name not in binary}
    with tempfile.TemporaryDirectory(prefix='sandbox-v4-patch-') as temporary:
        root = Path(temporary)
        repo, blobs = root / 'repo.git', root / 'blobs'
        blobs.mkdir()
        environment = {k: v for k, v in os.environ.items() if not k.startswith('GIT_')}
        environment.update(GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM='1')
        subprocess.run(['git', 'init', '--bare', '--quiet', '--template=', str(repo)], check=True, env=environment)

        def git(*args, data=None, index=None):
            env = {**environment, **({'GIT_INDEX_FILE': str(index)} if index else {})}
            return subprocess.run(['git', '--git-dir', str(repo), *args], input=data,
                                  cwd=blobs, env=env, check=True, capture_output=True).stdout

        contents = list(dict.fromkeys(data for _, data in [*before.values(), *after.values()]))
        for index, data in enumerate(contents):
            (blobs / str(index)).write_bytes(data)
        hashes = git('hash-object', '-w', '--no-filters', '--stdin-paths',
                     data=''.join(str(i)+'\n' for i in range(len(contents))).encode()).splitlines()
        objects = dict(zip(contents, hashes))

        def tree(files, name):
            entries = b''.join(f'{mode:o} '.encode() + objects[data] + b'\t' + os.fsencode(path) + b'\0'
                               for path, (mode, data) in sorted(files.items()))
            git('update-index', '-z', '--index-info', data=entries, index=root / name)
            return git('write-tree', index=root / name).decode().strip()

        left, right = tree(before, 'before.index'), tree(after, 'after.index')
        return git('diff', '--no-ext-diff', '--no-textconv', '--no-renames', '--no-color',
                   '--full-index', '--src-prefix=a/', '--dst-prefix=b/', '--patch', left, right)
