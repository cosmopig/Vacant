"""Adversarial security & robustness tests for `vacant_network/adapters/restart.py`.

Every test asserts the security/correctness property that SHOULD hold against a
hostile or buggy agent running inside the workspace copy (with stub agents in the
same style as `tests/test_adapters_restart.py`).  A test that FAILS on the current
implementation demonstrates a real, reproducible vulnerability or bug.
"""
from __future__ import annotations

import json
import os
import pathlib
import signal
import subprocess
import sys
import textwrap

import pytest

from vacant_network.adapters import restart as R
from vacant_network.adapters.run import Launch

TEST = textwrap.dedent("""\
    import unittest
    from sol import f
    class T(unittest.TestCase):
        def test_one(self):
            self.assertEqual(f(1), 2)
        def test_two(self):
            self.assertEqual(f(41), 42)
    """)
GOOD = "def f(x):\n    return x + 1\n"
HALF = "def f(x):\n    return 2 if x == 1 else 0\n"
BAD = "def f(x):\n    return x\n"


@pytest.fixture()
def proj(tmp_path, monkeypatch):
    p = tmp_path / "proj"
    p.mkdir()
    (p / "sol_test.py").write_text(TEST)
    (p / "sol.py").write_text("def f(x):\n    raise NotImplementedError\n")
    (p / "README.md").write_text("make the tests pass\n")
    monkeypatch.setenv("VACANT_WORK", str(tmp_path / "work"))
    return p


def _script_build(tmp_path, body: str, name: str = "agent_attack.py"):
    script = tmp_path / name
    script.write_text(body)

    def build(prompt: str, ws: pathlib.Path) -> Launch:
        return Launch(argv=[sys.executable, str(script)], env={})

    return build


def _multi_build(tmp_path, bodies: list[str]):
    """Run bodies[0] on attempt 1, bodies[1] on attempt 2, etc."""
    state = tmp_path / "multi_state.json"
    scripts = []
    for i, body in enumerate(bodies):
        s = tmp_path / f"agent_step_{i}.py"
        s.write_text(body)
        scripts.append(str(s))
    dispatcher = tmp_path / "dispatch.py"
    dispatcher.write_text(textwrap.dedent(f"""\
        import json, pathlib, runpy
        st = pathlib.Path({str(state)!r})
        n = json.loads(st.read_text())["n"] + 1 if st.exists() else 1
        st.write_text(json.dumps({{"n": n}}))
        scripts = {scripts!r}
        runpy.run_path(scripts[min(n, len(scripts)) - 1], run_name="__main__")
        """))

    def build(prompt: str, ws: pathlib.Path) -> Launch:
        return Launch(argv=[sys.executable, str(dispatcher)], env={})

    return build


def _run_real_unittest(project: pathlib.Path, mod: str = "sol_test") -> subprocess.CompletedProcess:
    runner = (
        "import sys, unittest\n"
        "sys.path.append('.')\n"
        f"suite = unittest.TestLoader().loadTestsFromName({mod!r})\n"
        "res = unittest.TestResult()\n"
        "suite.run(res)\n"
        "ok = res.testsRun > 0 and not res.failures and not res.errors\n"
        "sys.stderr.write(f'run={res.testsRun} fail={len(res.failures)} err={len(res.errors)}\\n')\n"
        "sys.exit(0 if ok else 1)\n"
    )
    return subprocess.run(
        [sys.executable, "-B", "-P", "-c", runner],
        cwd=str(project),
        capture_output=True,
        text=True,
        timeout=15,
    )


def _restore_perms(root: pathlib.Path) -> None:
    """Restore read/write/exec bits so pytest tmp_path teardown succeeds."""
    for dp, dns, fns in os.walk(root):
        try:
            os.chmod(dp, 0o700)
        except OSError:
            pass
        for name in list(dns) + list(fns):
            p = pathlib.Path(dp) / name
            if not p.is_symlink():
                try:
                    os.chmod(p, 0o700 if p.is_dir() else 0o600)
                except OSError:
                    pass


# ============================================================================
# Category (a): Write, overwrite, or delete OUTSIDE the project or workspace
# ============================================================================

def test_a1_write_back_dir_replaced_by_file_must_not_follow_nested_symlink(proj, tmp_path):
    """_through_symlink(project, 'sub') is False when project/sub is a real dir,
    but shutil.copy2(ws/'sub', project/'sub') silently targets project/sub/sub,
    following a symlink there and overwriting a file OUTSIDE the project."""
    outside = tmp_path / "outside_precious.txt"
    outside.write_text("precious\n")
    (proj / "sub").mkdir()
    os.symlink(outside, proj / "sub" / "sub")

    build = _script_build(tmp_path, textwrap.dedent(f"""\
        import pathlib, shutil
        shutil.rmtree("sub")
        pathlib.Path("sub").write_text("OVERWRITTEN\\n")
        pathlib.Path("sol.py").write_text({GOOD!r})
        """))
    R.run(proj, build, "fix it", max_attempts=1, attempt_timeout_s=20, budget_s=300)
    assert outside.read_text() == "precious\n"


def test_a2_write_back_must_not_overwrite_hardlinked_file_outside_project(proj, tmp_path):
    """shutil.copy2 writes in-place into an existing inode instead of atomic
    unlink/replace; editing a file in ws that is hard-linked in project
    overwrites the hard-linked file OUTSIDE the project."""
    outside = tmp_path / "outside_hardlink.txt"
    outside.write_text("precious\n")
    os.link(outside, proj / "shared.txt")

    build = _script_build(tmp_path, textwrap.dedent(f"""\
        import pathlib
        pathlib.Path("shared.txt").write_text("agent edit\\n")
        pathlib.Path("sol.py").write_text({GOOD!r})
        """))
    R.run(proj, build, "fix it", max_attempts=1, attempt_timeout_s=20, budget_s=300)
    assert outside.read_text() == "precious\n"
    assert (proj / "shared.txt").read_text() == "agent edit\n"


# ============================================================================
# Category (b): Delete or corrupt files in the user's project not legitimately changed
# ============================================================================

def test_b1_copy_skip_regular_file_like_git_worktree_must_not_be_deleted(proj, tmp_path):
    """copytree ignores files matching COPY_SKIP (like a git worktree's .git file),
    while _files() only skips COPY_SKIP directories. _write_back then deletes
    project/.git even though the agent never touched it."""
    git_file = proj / ".git"
    git_file.write_text("gitdir: /some/repo/.git/worktrees/wt\n")

    build = _script_build(tmp_path, f"import pathlib\npathlib.Path('sol.py').write_text({GOOD!r})\n")
    R.run(proj, build, "fix it", max_attempts=1, attempt_timeout_s=20, budget_s=300)
    assert git_file.exists(), ".git worktree file was deleted by _write_back"
    assert git_file.read_text() == "gitdir: /some/repo/.git/worktrees/wt\n"


def test_b2_agent_creating_copy_skip_file_must_not_write_into_project_git_dir(proj, tmp_path):
    """Because _files(ws) does not filter regular files against COPY_SKIP, an agent
    creating a regular file ws/.git causes shutil.copy2(ws/'.git', proj/'.git')
    to write a bogus file inside the user's .git/ directory."""
    (proj / ".git").mkdir()
    (proj / ".git" / "HEAD").write_text("ref: refs/heads/main\n")

    build = _script_build(tmp_path, textwrap.dedent(f"""\
        import pathlib
        pathlib.Path(".git").write_text("injected\\n")
        pathlib.Path("sol.py").write_text({GOOD!r})
        """))
    R.run(proj, build, "fix it", max_attempts=1, attempt_timeout_s=20, budget_s=300)
    assert not (proj / ".git" / ".git").exists()


def test_b3_chmod_111_dir_in_workspace_must_not_delete_project_files(proj, tmp_path):
    """In no-tests mode, os.walk(ws) silently skips an execute-only (0o111)
    directory (cannot list), while _through_symlink() succeeds in lstat()ing
    through 0o111 and returns False — causing _write_back to DELETE untouched
    project files."""
    (proj / "sol_test.py").unlink()
    (proj / "data").mkdir()
    (proj / "data" / "keep.txt").write_text("keep me\n")

    build = _script_build(tmp_path, "import os\nos.chmod('data', 0o111)\n")
    try:
        R.run(proj, build, "fix it", max_attempts=1, attempt_timeout_s=20, budget_s=300)
    finally:
        _restore_perms(tmp_path)
    assert (proj / "data" / "keep.txt").exists(), "data/keep.txt was deleted despite still existing in ws"
    assert (proj / "data" / "keep.txt").read_text() == "keep me\n"


def test_b4_dir_replaced_by_file_must_not_corrupt_project_dir(proj, tmp_path):
    """Replacing directory ws/sub with regular file ws/sub causes shutil.copy2
    to write a bogus project/sub/sub file inside directory project/sub/ instead
    of replacing or rejecting it."""
    (proj / "sub").mkdir()
    (proj / "sub" / "keep.txt").write_text("old\n")

    build = _script_build(tmp_path, textwrap.dedent(f"""\
        import pathlib, shutil
        shutil.rmtree("sub")
        pathlib.Path("sub").write_text("new file\\n")
        pathlib.Path("sol.py").write_text({GOOD!r})
        """))
    R.run(proj, build, "fix it", max_attempts=1, attempt_timeout_s=20, budget_s=300)
    assert not (proj / "sub" / "sub").exists()
    assert (proj / "sub").is_file() and (proj / "sub").read_text() == "new file\n"


def test_b5_file_replaced_by_dir_must_not_crash_with_partial_write_back(proj, tmp_path):
    """_write_back runs additions/modifications before deletions. Replacing a
    regular file m.txt with directory m.txt/child.txt crashes with FileExistsError
    mid-loop, leaving alphabetically earlier files modified and later files (sol.py)
    unwritten."""
    (proj / "a.txt").write_text("orig_a\n")
    (proj / "m.txt").write_text("orig_m\n")
    (proj / "z.txt").write_text("orig_z\n")

    build = _script_build(tmp_path, textwrap.dedent(f"""\
        import pathlib
        pathlib.Path("a.txt").write_text("new_a\\n")
        pathlib.Path("m.txt").unlink()
        pathlib.Path("m.txt").mkdir()
        pathlib.Path("m.txt/child.txt").write_text("child\\n")
        pathlib.Path("z.txt").write_text("new_z\\n")
        pathlib.Path("sol.py").write_text({GOOD!r})
        """))
    res = R.run(proj, build, "fix it", max_attempts=1, attempt_timeout_s=20, budget_s=300)
    assert res["accepted"] is True
    assert (proj / "sol.py").read_text() == GOOD
    assert (proj / "z.txt").read_text() == "new_z\n"


# ============================================================================
# Category (c): Make acceptance report PASS when original tests fail on delivery
# ============================================================================

def test_c1_forged_vacant_result_sentinel_must_not_pass_acceptance(proj, tmp_path):
    """_UNITTEST_RUNNER parses the last @@VACANT_RESULT@@ line with no nonce.
    Broken candidate code can emit a forged PASS JSON via atexit (only when
    running inside vacant-acc-) so acceptance returns PASS while the delivered
    code fails the original tests."""
    evil_sol = textwrap.dedent("""\
        import atexit, json, os
        if "vacant-acc-" in os.environ.get("HOME", ""):
            fake = {"run": 2, "failures": 0, "errors": 0, "skipped": 0,
                    "unexpected_successes": 0, "load_error": None, "first_problem": None}
            atexit.register(lambda: print("\\n@@VACANT_RESULT@@" + json.dumps(fake), flush=True))

        def f(x):
            return x
        """)
    build = _script_build(tmp_path, f"import pathlib\npathlib.Path('sol.py').write_text({evil_sol!r})\n")
    res = R.run(proj, build, "fix it", max_attempts=1, attempt_timeout_s=20, budget_s=300)
    real = _run_real_unittest(proj)
    assert real.returncode != 0, "sanity check: delivered code must actually fail real tests"
    assert res["accepted"] is False


def test_c2_package_shadowing_test_module_must_not_pass_acceptance(proj, tmp_path):
    """acceptance() runs loadTestsFromName('sol_test'). Creating a package
    sol_test/__init__.py shadows sol_test.py without modifying sol_test.py
    (tests_tampered == []), causing acceptance to report PASS on broken code."""
    build = _script_build(tmp_path, textwrap.dedent(f"""\
        import pathlib
        pathlib.Path("sol.py").write_text({BAD!r})
        pathlib.Path("sol_test").mkdir()
        pathlib.Path("sol_test/__init__.py").write_text(
            "import unittest\\nclass Fake(unittest.TestCase):\\n    def test_ok(self): pass\\n"
        )
        """))
    res = R.run(proj, build, "fix it", max_attempts=1, attempt_timeout_s=20, budget_s=300)
    assert res["accepted"] is False


def test_c3_shadowing_stdlib_unittest_in_workspace_must_not_pass_acceptance(proj, tmp_path):
    """python -B -c puts '' (cwd) at sys.path[0]. A workspace unittest.py shadows
    stdlib unittest inside _UNITTEST_RUNNER, returning a fake PASS during
    acceptance while delegating to real unittest on the delivered project."""
    shadow = textwrap.dedent("""\
        import os, sys
        if "vacant-acc-" in os.environ.get("HOME", ""):
            class TestResult:
                testsRun = 2
                failures = []
                errors = []
                skipped = []
                unexpectedSuccesses = []
            class _Suite:
                def run(self, res): return res
            class TestLoader:
                def loadTestsFromName(self, name): return _Suite()
        else:
            sys.path = [p for p in sys.path if p not in ("", ".") and not p.endswith("/proj")]
            sys.modules.pop("unittest", None)
            import unittest as _real
            globals().update(_real.__dict__)
        """)
    build = _script_build(tmp_path, textwrap.dedent(f"""\
        import pathlib
        pathlib.Path("sol.py").write_text({BAD!r})
        pathlib.Path("unittest.py").write_text({shadow!r})
        """))
    res = R.run(proj, build, "fix it", max_attempts=1, attempt_timeout_s=20, budget_s=300)
    real = _run_real_unittest(proj)
    assert real.returncode != 0, "sanity check: delivered code must fail real tests"
    assert res["accepted"] is False


def test_c4_symlinked_code_passes_acceptance_but_is_not_written_back(proj, tmp_path):
    """acceptance() follows symlinks in work (via copytree(..., symlinks=True)),
    while _write_back() skips symlinks in ws. Replacing ws/sol.py with a relative
    symlink to a passing file inside ws makes acceptance PASS while leaving
    project/sol.py completely broken."""
    build = _script_build(tmp_path, textwrap.dedent(f"""\
        import os, pathlib
        pathlib.Path("_good_impl.py").write_text({GOOD!r})
        pathlib.Path("sol.py").unlink()
        os.symlink("_good_impl.py", "sol.py")
        """))
    res = R.run(proj, build, "fix it", max_attempts=1, attempt_timeout_s=20, budget_s=300)
    if res["accepted"]:
        real = _run_real_unittest(proj)
        assert real.returncode == 0, (
            f"acceptance reported PASS but delivered project fails original tests:\n{real.stderr}"
        )


def test_c5_detached_background_process_toctou_mutates_ws_after_acceptance(proj, tmp_path):
    """A setsid() background process survives run_agent's _kill_group(), waits
    until acceptance() is running on its copy, and overwrites ws/sol.py with BAD
    before _write_back() runs. acceptance() returns PASS while pure BAD is
    delivered to project/sol.py."""
    pid_file = tmp_path / "bg.pid"
    bg_script = tmp_path / "bg_worker.py"
    bg_script.write_text(textwrap.dedent(f"""\
        import os, pathlib, sys, time
        ws = pathlib.Path(sys.argv[1])
        pathlib.Path({str(pid_file)!r}).write_text(str(os.getpid()))
        marker = ws / ".acc_running"
        deadline = time.monotonic() + 10.0
        while time.monotonic() < deadline and not marker.exists():
            time.sleep(0.02)
        if marker.exists():
            (ws / "sol.py").write_text({BAD!r})
            marker.unlink()
        """))
    sol_template = textwrap.dedent("""\
        import os, pathlib, time
        _WS = __WS__
        if os.path.abspath(os.getcwd()) != os.path.abspath(_WS):
            m = pathlib.Path(_WS) / ".acc_running"
            m.write_text("1")
            deadline = time.monotonic() + 5.0
            while time.monotonic() < deadline and m.exists():
                time.sleep(0.02)

        def f(x):
            return x + 1
        """)
    build = _script_build(tmp_path, textwrap.dedent(f"""\
        import os, pathlib, subprocess, sys
        ws = os.getcwd()
        subprocess.Popen(
            [sys.executable, {str(bg_script)!r}, ws],
            start_new_session=True,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        sol_code = {sol_template!r}.replace("__WS__", repr(ws))
        pathlib.Path("sol.py").write_text(sol_code)
        """))
    try:
        res = R.run(proj, build, "fix it", max_attempts=1, attempt_timeout_s=20, budget_s=300)
    finally:
        if pid_file.exists():
            try:
                os.kill(int(pid_file.read_text()), signal.SIGKILL)
            except (OSError, ValueError):
                pass
    if res["accepted"]:
        real = _run_real_unittest(proj)
        assert real.returncode == 0, (
            f"acceptance reported PASS but delivered sol.py is:\n{(proj / 'sol.py').read_text()}"
        )


# ============================================================================
# Category (d): Exceed budget_s by a lot, hang, or crash delivering nothing
# ============================================================================

def test_d1_per_directory_acceptance_timeout_exceeds_budget_by_multiples(proj, tmp_path):
    """acceptance() passes timeout_s independently to every directory in by_dir
    instead of using a shared deadline, allowing N test directories to burn
    N * acc_t seconds far past budget_s."""
    (proj / "sol_test.py").unlink()
    sub_test = textwrap.dedent("""\
        import sys, unittest
        sys.path.insert(0, "..")
        from sol import f
        class T(unittest.TestCase):
            def test_one(self):
                self.assertEqual(f(1), 2)
        """)
    for i in range(4):
        d = proj / f"d{i}"
        d.mkdir()
        (d / f"t{i}_test.py").write_text(sub_test)

    slow_sol = "import time\ntime.sleep(2.0)\ndef f(x):\n    return x\n"
    build = _script_build(tmp_path, f"import pathlib\npathlib.Path('sol.py').write_text({slow_sol!r})\n")
    res = R.run(proj, build, "fix it", max_attempts=1, attempt_timeout_s=2.0, budget_s=3.0, min_attempt_s=0.5)
    assert res["total_wall_s"] <= 4.5, f"exceeded budget_s=3.0 by {res['total_wall_s'] - 3.0:.1f}s"


def test_d2_acc_timeout_5s_floor_exceeds_small_budget(proj, tmp_path):
    """run() clamps acc_t to max(5.0, ...) even when budget_s is nearly exhausted,
    pushing total_wall_s to >3x budget_s."""
    build = _script_build(tmp_path, textwrap.dedent("""\
        import pathlib, time
        pathlib.Path("sol.py").write_text("import time\\ntime.sleep(20)\\ndef f(x): return x\\n")
        time.sleep(20)
        """))
    res = R.run(proj, build, "fix it", max_attempts=1, attempt_timeout_s=2.0, budget_s=2.0, min_attempt_s=0.5)
    assert res["total_wall_s"] <= 3.5, f"exceeded budget_s=2.0: total_wall_s={res['total_wall_s']}"


def test_d3_fifo_in_workspace_crashes_run_and_delivers_nothing(proj, tmp_path):
    """Creating a FIFO in ws on attempt 2 makes shutil.copytree in acceptance()
    crash with shutil.Error, aborting the entire run so attempt 1 (HALF) is
    never delivered."""
    build = _multi_build(tmp_path, [
        f"import pathlib\npathlib.Path('sol.py').write_text({HALF!r})\n",
        f"import os, pathlib\nos.mkfifo('pipe')\npathlib.Path('sol.py').write_text({BAD!r})\n",
    ])
    res = R.run(proj, build, "fix it", max_attempts=2, attempt_timeout_s=20, budget_s=300)
    assert res["delivered_attempt"] == 1
    assert (proj / "sol.py").read_text() == HALF


def test_d4_test_replaced_by_directory_crashes_acceptance_and_delivers_nothing(proj, tmp_path):
    """Replacing sol_test.py with a directory makes acceptance() crash with
    IsADirectoryError on f.write_bytes(want), preventing delivery of attempt 1."""
    build = _multi_build(tmp_path, [
        f"import pathlib\npathlib.Path('sol.py').write_text({HALF!r})\n",
        "import os, pathlib\npathlib.Path('sol_test.py').unlink()\nos.mkdir('sol_test.py')\n",
    ])
    res = R.run(proj, build, "fix it", max_attempts=2, attempt_timeout_s=20, budget_s=300)
    assert res["delivered_attempt"] == 1
    assert (proj / "sol.py").read_text() == HALF


def test_d5_test_parent_dir_replaced_by_file_crashes_acceptance_and_delivers_nothing(proj, tmp_path):
    """Replacing a test's parent directory (tests/) with a regular file makes
    acceptance() crash with FileExistsError on f.parent.mkdir(), preventing
    delivery of attempt 1."""
    (proj / "sol_test.py").unlink()
    (proj / "tests").mkdir()
    (proj / "tests" / "sol_test.py").write_text(
        TEST.replace("from sol import f", "import sys; sys.path.insert(0, '..'); from sol import f")
    )
    build = _multi_build(tmp_path, [
        f"import pathlib\npathlib.Path('sol.py').write_text({HALF!r})\n",
        "import pathlib, shutil\nshutil.rmtree('tests')\npathlib.Path('tests').write_text('not a dir')\n",
    ])
    res = R.run(proj, build, "fix it", max_attempts=2, attempt_timeout_s=20, budget_s=300)
    assert res["delivered_attempt"] == 1
    assert (proj / "sol.py").read_text() == HALF


def test_d6_readonly_tampered_test_crashes_acceptance_and_delivers_nothing(proj, tmp_path):
    """Editing sol_test.py and chmod 0o444 causes copytree to preserve read-only
    mode, crashing acceptance() with PermissionError on f.write_bytes(want)."""
    build = _multi_build(tmp_path, [
        f"import pathlib\npathlib.Path('sol.py').write_text({HALF!r})\n",
        "import os, pathlib\npathlib.Path('sol_test.py').write_text('# tampered\\n')\nos.chmod('sol_test.py', 0o444)\n",
    ])
    try:
        res = R.run(proj, build, "fix it", max_attempts=2, attempt_timeout_s=20, budget_s=300)
    finally:
        _restore_perms(tmp_path)
    assert res["delivered_attempt"] == 1
    assert (proj / "sol.py").read_text() == HALF


def test_d7_chmod_000_file_in_workspace_crashes_acceptance_and_delivers_nothing(proj, tmp_path):
    """Creating an unreadable (0o000) file in ws makes shutil.copytree in
    acceptance() crash with shutil.Error (PermissionError), preventing delivery
    of attempt 1."""
    build = _multi_build(tmp_path, [
        f"import pathlib\npathlib.Path('sol.py').write_text({HALF!r})\n",
        "import os, pathlib\npathlib.Path('secret.txt').write_text('x')\nos.chmod('secret.txt', 0o000)\n",
    ])
    try:
        res = R.run(proj, build, "fix it", max_attempts=2, attempt_timeout_s=20, budget_s=300)
    finally:
        _restore_perms(tmp_path)
    assert res["delivered_attempt"] == 1
    assert (proj / "sol.py").read_text() == HALF


def test_d8_malformed_vacant_result_marker_crashes_acceptance_and_delivers_nothing(proj, tmp_path):
    """Printing a malformed @@VACANT_RESULT@@ line causes json.loads / splitlines()[0]
    in acceptance() to raise an unhandled IndexError/JSONDecodeError, aborting
    the run so attempt 1 (HALF) is never delivered."""
    crash_sol = textwrap.dedent("""\
        import os, sys
        sys.stdout.write("\\n@@VACANT_RESULT@@not-json\\n")
        sys.stdout.flush()
        os._exit(0)
        """)
    build = _multi_build(tmp_path, [
        f"import pathlib\npathlib.Path('sol.py').write_text({HALF!r})\n",
        f"import pathlib\npathlib.Path('sol.py').write_text({crash_sol!r})\n",
    ])
    res = R.run(proj, build, "fix it", max_attempts=2, attempt_timeout_s=20, budget_s=300)
    assert res["delivered_attempt"] == 1
    assert (proj / "sol.py").read_text() == HALF


def test_d9_acceptance_timeout_leaks_grandchild_process(proj, tmp_path):
    """acceptance() invokes subprocess.run without start_new_session=True or
    killpg. A grandchild holding stdout open causes a full timeout and survives
    as an orphan after acceptance() returns."""
    pid_file = tmp_path / "orphan.pid"
    sol_code = textwrap.dedent(f"""\
        import os, pathlib, subprocess, sys
        p = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
        pathlib.Path({str(pid_file)!r}).write_text(str(p.pid))

        def f(x):
            return x + 1
        """)
    build = _script_build(tmp_path, f"import pathlib\npathlib.Path('sol.py').write_text({sol_code!r})\n")
    try:
        R.run(proj, build, "fix it", max_attempts=1, attempt_timeout_s=2.0, budget_s=2.0, min_attempt_s=0.5)
        assert pid_file.exists()
        pid = int(pid_file.read_text())
        alive = True
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            alive = False
        assert not alive, f"grandchild pid {pid} leaked alive after acceptance() timed out"
    finally:
        if pid_file.exists():
            try:
                os.kill(int(pid_file.read_text()), signal.SIGKILL)
            except (OSError, ValueError):
                pass
