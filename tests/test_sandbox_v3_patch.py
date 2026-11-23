import shutil
import subprocess

import pytest

from ops.sandbox.v3.patch import derive_patch, normalize_setup


COMMANDS = ["sed -i 's/pytest/pytest -rA/' tox.ini",
            "sed -i 's/Jinja2>=2.3/Jinja2<3.0/' setup.py",
            "sed -i 's/requires = \\[\"setuptools\",/requires = \\[\"setuptools==68.0.0\",/' pyproject.toml"]


def setup_trees(tmp_path):
    base, handback = tmp_path / 'base', tmp_path / 'handback'
    base.mkdir()
    (base / 'tox.ini').write_text('commands = pytest pytest\nother = pytest\n')
    (base / 'setup.py').write_text('requires = ["Jinja2>=2.3"]\n')
    (base / 'pyproject.toml').write_text('requires = ["setuptools", "wheel"]\n')
    (base / 'service.py').write_text('value = 1\n')
    shutil.copytree(base, handback)
    normalized = normalize_setup({p.name: (0o100644, p.read_bytes()) for p in base.iterdir()}, COMMANDS)
    for name, (_, data) in normalized.items():
        (handback / name).write_bytes(data)
    return base, handback


def test_setup_only_handback_has_empty_patch(tmp_path):
    base, handback = setup_trees(tmp_path)
    original = (base / 'tox.ini').read_bytes()
    assert (handback / 'tox.ini').read_text() == 'commands = pytest -rA pytest\nother = pytest -rA\n'
    assert derive_patch(base, handback, setup_commands=COMMANDS) == b''
    assert (base / 'tox.ini').read_bytes() == original
    assert derive_patch(base, base) == b''
    empty = tmp_path / 'empty'
    empty.mkdir()
    assert derive_patch(empty, empty) == b''


def test_agent_changes_remain_and_patch_applies_to_normalized_base(tmp_path):
    base, handback = setup_trees(tmp_path)
    target = tmp_path / 'target'
    shutil.copytree(handback, target)
    (handback / 'service.py').write_text('value = 2\n')
    (handback / 'setup.py').write_text((handback / 'setup.py').read_text() + 'agent_change = True\n')
    (handback / 'new.py').write_text('new = True\n')
    (handback / 'tox.ini').unlink()
    patch = derive_patch(base, handback, setup_commands=COMMANDS)
    assert b'agent_change = True' in patch and b'+value = 2' in patch
    assert b'-requires = ["Jinja2>=2.3"]' not in patch
    applied = subprocess.run(['git', 'apply', '-'], input=patch, cwd=target, capture_output=True)
    assert applied.returncode == 0, applied.stderr
    for name in ('service.py', 'setup.py', 'new.py'):
        assert (target / name).read_bytes() == (handback / name).read_bytes()
    assert not (target / 'tox.ini').exists()
    assert derive_patch(base, handback, '+++ b/setup.py\n', COMMANDS) != patch


def test_test_patch_binary_and_generated_artifacts_are_excluded(tmp_path):
    base, handback = setup_trees(tmp_path)
    for root in (base, handback):
        (root / 'test_old.py').write_text('before\n')
        (root / 'data.bin').write_bytes(b'\0before')
    (handback / 'test_old.py').write_text('after\n')
    (handback / 'test_new.py').write_text('new test\n')
    (handback / 'data.bin').write_bytes(b'after')
    for directory in ('build', '__pycache__', 'pkg.egg-info', '.pytest_cache'):
        (handback / directory).mkdir()
        (handback / directory / 'generated.py').write_text('generated\n')
    (handback / 'extension.so').write_bytes(b'compiled')
    test_patch = '--- a/test_old.py\n+++ b/test_old.py\n+++ b/test_new.py\n'
    assert derive_patch(base, handback, test_patch, COMMANDS) == b''


def test_setup_normalization_rejects_unsafe_or_unknown_operations(tmp_path):
    files = {'setup.py': (0o100644, b'x\n')}
    for command in ("sed -i 's/x/y/e' setup.py", "sed -i 's/x/y/' ../outside",
                    "sed -i 's/x/y/' missing", "sed -i -e 's/x/y/' setup.py"):
        with pytest.raises(ValueError):
            normalize_setup(files, [command])
    with pytest.raises(ValueError, match='symlink'):
        normalize_setup({'setup.py': (0o120000, b'outside')}, ["sed -i 's/x/y/' setup.py"])
    with pytest.raises(ValueError, match='directories'):
        derive_patch(tmp_path / 'missing', tmp_path)
