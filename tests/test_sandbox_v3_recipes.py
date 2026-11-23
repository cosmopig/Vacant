import hashlib
import io
import os
import shlex
import subprocess
import sys
import tarfile

from ops.sandbox.v3 import recipes


def test_qhull_download_is_https_pinned_and_fail_closed(tmp_path):
    commands = recipes.secure_downloads([
        'QHULL_URL="http://www.qhull.org/download/qhull-2020-src-8.0.2.tgz"',
        'wget -O "$QHULL_TAR" "$QHULL_URL"',
        'tar -xvzf "$QHULL_TAR" -C "$QHULL_BUILD_DIR"',
    ])
    assert recipes.QHULL_URL in commands[0] and recipes.QHULL_SHA256 in commands[1]
    assert 'curl --fail --location --proto "=https"' in commands[2]
    assert commands[-2].endswith('|| exit 1')
    archive = tmp_path / 'archive.tgz'
    out = tmp_path / 'out'
    out.mkdir()
    with tarfile.open(archive, 'w:gz') as tar:
        member = tarfile.TarInfo('payload')
        member.size = 2
        tar.addfile(member, io.BytesIO(b'ok'))
    env = {**os.environ, 'QHULL_TAR': str(archive), 'QHULL_BUILD_DIR': str(out)}
    script = '\n'.join(commands[-2:]).replace('python -I', shlex.quote(sys.executable) + ' -I')
    refused = subprocess.run(['bash', '-c', script], env={**env, 'QHULL_SHA256': recipes.QHULL_SHA256}, capture_output=True)
    assert refused.returncode != 0 and b'sha256 mismatch' in refused.stderr
    assert not list(out.iterdir())
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    accepted = subprocess.run(['bash', '-c', script], env={**env, 'QHULL_SHA256': digest}, capture_output=True)
    assert accepted.returncode == 0 and (out / 'payload').read_bytes() == b'ok'
    archive.unlink()
    missing = subprocess.run(['bash', '-c', script], env={**env, 'QHULL_SHA256': digest}, capture_output=True)
    assert missing.returncode != 0
    assert recipes.secure_downloads([]) == []
    assert recipes.secure_downloads(['echo normal']) == ['echo normal']
    assert recipes.secure_downloads(commands) == commands
