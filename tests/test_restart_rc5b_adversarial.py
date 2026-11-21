"""Adversarial review round 2 (rc5b) regression tests for `vacant do` restart mode.

Covers all 12 items from round-2 review (`tests/adversarial_rc5_repro/round2/REPORT.md`):
1. R1 — exclude VACANT_HOME and VACANT_WORK when inside project (copy, scan, snapshot, B1, write-back)
2. R7 — preserve original mode bits (incl. exec) when restoring protected files (`--check './verify.sh'`)
3. R8 — stop chmod-ing original project's `node_modules` (modes unchanged on SIGTERM mid-run)
4. R13+R10 — lstat manifest for `node_modules`, `node_modules_manifest_s` & `copy_s`, dereference external
             symlinks in agent copy, follow external symlinks in original manifest, reflink fallback warning
5. R9 — byte-safe encoding for all strings (prompt, argv, check cmd, env, output tails); `request_sha256`
        hashes original `os.fsencode` bytes
6. R4 — B1 lstat-only listing covers `.git` (except `.git/objects/`), `node_modules`/`.venv`/`__pycache__`/
        `.pytest_cache` at any depth, reports listing time, prominent warnings for `.git/refs|HEAD|packed-refs`
        and `.venv/**/*.pth`
7. R5 — robust `--check` parser (shell operators, `sh -c`, `bash -c`, `env`, `timeout`, `nice`, `cd`),
        protects all matching manifests (incl. nested `package.json` + pins `scripts.test`, `*.mk`, `Cargo.toml`,
        `go.mod`) and existing project file tokens at any depth; shell-expansion warning
8. R6 — reworked `acceptance_dependencies_changed`: string literals, Python/JS depth-2 transitive imports
        (incl. `jest.mock`), expanded fixture/mock/golden/data dirs, module-under-test exclusion, ordered
        list with reasons (`literal`/`import`/`dir`)
9. R12 — files created under COPY_SKIP-named dirs reported in `not_delivered` with reason (not written back)
10. R11 — `_populate_acceptance_work` uses start snapshot (not live project); outside changes handling:
          (a) no overlap -> deliver + prominent wording, (b) overlap -> write nothing back + exit 43 +
          `write_back_conflicts` + merge workspace path, (c) protected file changed -> prominent line
11. R2/R3 — Linux `PR_SET_CHILD_SUBREAPER` + `/proc/*/stat` + env marker; kills detached descendants after
            agent, after acceptance/baseline, and at end; records `{phase, pid, cmdline, killed}`; null +
            honesty message on non-Linux
12. Plan->apply TOCTOU — `_apply_write_plan` re-checks live files against start snapshot before replace/unlink
"""
from __future__ import annotations

import hashlib
import json
import os
import pathlib
import shutil
import signal
import stat
import subprocess
import sys
import textwrap
import time

import pytest

from vacant_network import audit_export as AE
from vacant_network.adapters import cli as adapters_cli
from vacant_network.adapters import restart as R
from vacant_network.adapters.run import Launch

needs_node = pytest.mark.skipif(not (shutil.which("node") and shutil.which("npm")), reason="node/npm missing")
needs_make = pytest.mark.skipif(not shutil.which("make"), reason="make missing")
needs_git = pytest.mark.skipif(not shutil.which("git"), reason="git missing")
needs_linux_proc = pytest.mark.skipif(
    not sys.platform.startswith("linux") or not os.path.isdir("/proc"),
    reason="Linux /proc required",
)


@pytest.fixture(autouse=True)
def _isolated_env(tmp_path, monkeypatch):
    monkeypatch.setenv("VACANT_HOME", str(tmp_path / "vhome"))
    monkeypatch.setenv("VACANT_WORK", str(tmp_path / "vwork"))
    monkeypatch.setenv("VACANT_HOOK_NO_GC", "1")


def _write_agent(tmp_path: pathlib.Path, body: str, name: str = "agent.py") -> pathlib.Path:
    p = tmp_path / name
    p.write_text(body, encoding="utf-8")
    return p


def _run_cli_do(monkeypatch, proj: pathlib.Path, agent_script: pathlib.Path, *,
                prompt: str = "do task", attempts: int = 1,
                extra_args: list[str] | None = None) -> int:
    monkeypatch.chdir(proj)
    argv = [
        "do",
        "--cmd", f"{sys.executable} {agent_script} {{prompt}}",
        "--prompt", prompt,
        "--attempts", str(attempts),
        "--attempt-timeout", "30",
        "--timeout", "120",
        *(extra_args or []),
    ]
    return adapters_cli.main(argv)


def _latest_result_json(work_root: pathlib.Path) -> dict:
    files = sorted(work_root.glob("restart-*/result.json"), key=lambda p: p.stat().st_mtime_ns)
    assert files, f"expected result.json in {work_root}"
    return json.loads(files[-1].read_text(encoding="utf-8"))


# ============================================================================
# Item 1 (R1) — VACANT_HOME / VACANT_WORK inside project excluded everywhere
# ============================================================================

def test_r1_vacant_home_inside_project_keys_never_copied_into_workspace(tmp_path, monkeypatch, capsys):
    """R1(a): VACANT_HOME=<project>/.vacant with signing keys present must never appear in ws."""
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "calc.py").write_text("def add(a, b):\n    return a - b\n", encoding="utf-8")
    (proj / "test_calc.py").write_text(
        "import unittest, calc\nclass T(unittest.TestCase):\n"
        "    def test_add(self): self.assertEqual(calc.add(2, 3), 5)\n",
        encoding="utf-8",
    )

    vhome = proj / ".vacant"
    vwork = tmp_path / "vwork_ext"
    monkeypatch.setenv("VACANT_HOME", str(vhome))
    monkeypatch.setenv("VACANT_WORK", str(vwork))

    seen_keys = tmp_path / "seen_keys.json"
    agent_noop = _write_agent(tmp_path, "pass\n", name="noop.py")
    # First run creates keys and signed trace chain under proj/.vacant
    _run_cli_do(monkeypatch, proj, agent_noop, prompt="seed keys", attempts=1)
    capsys.readouterr()
    assert list(vhome.rglob("identity.key")), "setup: expected signing keys inside proj/.vacant"

    # Second run: keys already exist inside proj/.vacant; agent searches its workspace for them
    agent = _write_agent(tmp_path, textwrap.dedent(f"""\
        import json, pathlib
        keys = [str(p) for p in pathlib.Path('.').rglob('identity.key')]
        has_vacant = pathlib.Path('.vacant').exists()
        pathlib.Path({str(seen_keys)!r}).write_text(json.dumps({{"keys": keys, "has_vacant": has_vacant}}))
        pathlib.Path('calc.py').write_text('def add(a, b):\\n    return a + b\\n')
        """))
    rc = _run_cli_do(monkeypatch, proj, agent, prompt="fix add", attempts=1)
    out = capsys.readouterr().out
    assert rc == 0, out

    info = json.loads(seen_keys.read_text(encoding="utf-8"))
    assert info["keys"] == [], f"signing keys leaked into agent workspace: {info['keys']}"
    assert info["has_vacant"] is False, ".vacant state dir must not be copied into agent workspace"

    rj = _latest_result_json(vwork)
    assert not any(p.startswith(".vacant") for p in rj.get("outside_changes", []))
    assert not any(p.startswith(".vacant") for p in rj["changed"]["deleted"])
    assert list(vhome.rglob("identity.key")), "original signing keys must remain intact"


def test_r1_vacant_work_inside_project_does_not_crash(tmp_path, monkeypatch, capsys):
    """R1(b): VACANT_WORK=<project>/vw2 must not recurse or crash copytree/scan/snapshot/listing."""
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "calc.py").write_text("def add(a, b):\n    return a - b\n", encoding="utf-8")
    (proj / "test_calc.py").write_text(
        "import unittest, calc\nclass T(unittest.TestCase):\n"
        "    def test_add(self): self.assertEqual(calc.add(2, 3), 5)\n",
        encoding="utf-8",
    )

    vwork = proj / "vw2"
    vwork.mkdir()
    monkeypatch.setenv("VACANT_WORK", str(vwork))

    agent = _write_agent(tmp_path, "import pathlib\npathlib.Path('calc.py').write_text('def add(a, b):\\n    return a + b\\n')\n")
    rc = _run_cli_do(monkeypatch, proj, agent, prompt="fix add", attempts=1)
    out = capsys.readouterr().out
    assert rc == 0, out
    assert "return a + b" in (proj / "calc.py").read_text(encoding="utf-8")
    rj = _latest_result_json(vwork)
    assert rj["accepted"] is True
    assert not any(p.startswith("vw2") for p in rj.get("outside_changes", []))


# ============================================================================
# Item 2 (R7) — preserve original mode bits (incl. exec) on protected restore
# ============================================================================

def test_r7_protected_exec_bit_preserved_for_direct_check_script(tmp_path, monkeypatch, capsys):
    """R7 (e7-exec-bit-protected.sh): `--check './verify.sh'` must preserve 0755 on restore."""
    proj = tmp_path / "proj"
    proj.mkdir()
    verify = proj / "verify.sh"
    verify.write_text("#!/bin/bash\ngrep -q 'ok = () => true' dep.js\n", encoding="utf-8")
    os.chmod(verify, 0o755)
    (proj / "dep.js").write_text("exports.ok = () => false;\n", encoding="utf-8")

    # Agent fixes dep.js AND tries to tamper with verify.sh (stripping exec bit)
    agent = _write_agent(tmp_path, textwrap.dedent("""\
        import os, pathlib
        pathlib.Path('verify.sh').write_text('#!/bin/bash\\nexit 0\\n')
        os.chmod('verify.sh', 0o644)
        pathlib.Path('dep.js').write_text('exports.ok = () => true;\\n')
        """))

    rc = _run_cli_do(monkeypatch, proj, agent, prompt="fix dep", attempts=1, extra_args=["--check", "./verify.sh"])
    out = capsys.readouterr().out
    assert rc == 0, out
    rj = _latest_result_json(tmp_path / "vwork")
    assert rj["baseline"]["accept"] is False
    assert rj["baseline_error"] is None
    assert rj["accepted"] is True
    assert "verify.sh" in rj["attempts"][0]["tests_tampered"]
    assert stat.S_IMODE(verify.lstat().st_mode) == 0o755


# ============================================================================
# Item 3 (R8) — never chmod original project's node_modules
# ============================================================================

@needs_node
def test_r8_sigterm_mid_run_leaves_original_node_modules_modes_unchanged(tmp_path):
    """R8 (e8-nm-readonly-on-kill.sh): killing vacant mid-attempt must leave original node_modules 755/644."""
    proj = tmp_path / "proj"
    (proj / "node_modules" / "dep").mkdir(parents=True)
    (proj / "package.json").write_text('{"name":"t","scripts":{"test":"node verify.test.js"}}\n', encoding="utf-8")
    (proj / "verify.test.js").write_text("process.exit(0);\n", encoding="utf-8")
    dep_js = proj / "node_modules" / "dep" / "index.js"
    dep_js.write_text("exports.x = 1;\n", encoding="utf-8")
    os.chmod(proj / "node_modules", 0o755)
    os.chmod(proj / "node_modules" / "dep", 0o755)
    os.chmod(dep_js, 0o644)

    started_flag = tmp_path / "agent_started"
    agent = _write_agent(tmp_path, textwrap.dedent(f"""\
        import pathlib, time
        pathlib.Path({str(started_flag)!r}).write_text("started")
        time.sleep(30)
        """))

    env = {k: v for k, v in os.environ.items() if k != "VIRTUAL_ENV"}
    env.update(
        PYTHONPATH=str(pathlib.Path(__file__).resolve().parent.parent),
        VACANT_HOME=str(tmp_path / "vhome"),
        VACANT_WORK=str(tmp_path / "vwork"),
        VACANT_HOOK_NO_GC="1",
    )
    proc = subprocess.Popen(
        [sys.executable, "-m", "vacant_network.cli", "do",
         "--cmd", f"{sys.executable} {agent} {{prompt}}", "--prompt", "x",
         "--attempts", "1", "--attempt-timeout", "30", "--timeout", "60"],
        cwd=str(proj),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )
    try:
        deadline = time.monotonic() + 15.0
        while not started_flag.exists() and time.monotonic() < deadline:
            assert proc.poll() is None, f"vacant exited early: {proc.stderr.read().decode()}"
            time.sleep(0.05)
        assert started_flag.exists(), "agent never started"
        # Check modes WHILE agent is running, then kill vacant with SIGTERM
        assert stat.S_IMODE((proj / "node_modules").lstat().st_mode) == 0o755
        assert stat.S_IMODE(dep_js.lstat().st_mode) == 0o644
        proc.send_signal(signal.SIGTERM)
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)
    finally:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except OSError:
            pass
        os.chmod(proj / "node_modules", 0o755)
        os.chmod(proj / "node_modules" / "dep", 0o755)
        os.chmod(dep_js, 0o644)

    assert stat.S_IMODE((proj / "node_modules").lstat().st_mode) == 0o755
    assert stat.S_IMODE((proj / "node_modules" / "dep").lstat().st_mode) == 0o755
    assert stat.S_IMODE(dep_js.lstat().st_mode) == 0o644


# ============================================================================
# Item 4 (R13 + R10) — lstat manifest, symlink deref & tracking, timings, reflink warn
# ============================================================================

@needs_node
def test_r10_nm_external_symlink_dereferenced_in_agent_copy(tmp_path, monkeypatch, capsys):
    """R10(a) (e10-b3-symlink-write-through.sh): absolute symlink inside node_modules pointing outside
    is dereferenced in agent's copy so writing through it cannot touch original project."""
    proj = tmp_path / "proj"
    (proj / "node_modules").mkdir(parents=True)
    (proj / "pkgsrc" / "mypkg").mkdir(parents=True)
    orig_code = "exports.ok = () => false;\n"
    (proj / "pkgsrc" / "mypkg" / "index.js").write_text(orig_code, encoding="utf-8")
    os.symlink(str(proj / "pkgsrc" / "mypkg"), str(proj / "node_modules" / "mypkg"))
    (proj / "package.json").write_text('{"name":"t","scripts":{"test":"node verify.test.js"}}\n', encoding="utf-8")
    (proj / "verify.test.js").write_text(
        "const dep = require('mypkg');\nif (!dep.ok()) process.exit(1);\n", encoding="utf-8"
    )

    agent = _write_agent(tmp_path, textwrap.dedent("""\
        import pathlib
        pathlib.Path("node_modules/mypkg/index.js").write_text("exports.ok = () => true;\\n")
        """))

    rc = _run_cli_do(monkeypatch, proj, agent, prompt="poison via symlink", attempts=1)
    out = capsys.readouterr().out
    assert rc == adapters_cli.EXIT["reject"], out
    assert (proj / "pkgsrc" / "mypkg" / "index.js").read_text(encoding="utf-8") == orig_code
    rj = _latest_result_json(tmp_path / "vwork")
    assert rj["accepted"] is False
    assert isinstance(rj.get("node_modules_manifest_s"), (int, float))
    assert isinstance(rj.get("copy_s"), (int, float))


@needs_node
def test_r10_nm_external_symlink_target_tracked_by_manifest(tmp_path, monkeypatch, capsys):
    """R10(b): direct write to target of external symlink inside node_modules is caught as node_modules_modified."""
    proj = tmp_path / "proj"
    (proj / "node_modules").mkdir(parents=True)
    (proj / "pkgsrc" / "mypkg").mkdir(parents=True)
    target = proj / "pkgsrc" / "mypkg" / "index.js"
    target.write_text("exports.ok = () => false;\n", encoding="utf-8")
    os.symlink(str(proj / "pkgsrc" / "mypkg"), str(proj / "node_modules" / "mypkg"))
    (proj / "package.json").write_text('{"name":"t","scripts":{"test":"node verify.test.js"}}\n', encoding="utf-8")
    (proj / "verify.test.js").write_text(
        "const dep = require('mypkg');\nif (!dep.ok()) process.exit(1);\n", encoding="utf-8"
    )

    agent = _write_agent(tmp_path, textwrap.dedent(f"""\
        import pathlib
        pathlib.Path({str(target)!r}).write_text("exports.ok = () => true;\\n")
        pathlib.Path("deliverable.txt").write_text("nope\\n")
        """))

    rc = _run_cli_do(monkeypatch, proj, agent, prompt="direct write to symlink target", attempts=1)
    out = capsys.readouterr().out
    assert rc == adapters_cli.EXIT["void"], out
    assert not (proj / "deliverable.txt").exists()
    rj = _latest_result_json(tmp_path / "vwork")
    assert rj["node_modules_changed"], "expected external symlink target write in node_modules_changed"
    assert any("mypkg" in p for p in rj["node_modules_changed"])


@needs_node
def test_r13_nm_lstat_manifest_timings_and_reflink_fallback_warning(tmp_path, monkeypatch, capsys):
    """R13 (e12-nm-perf.sh): lstat manifest avoids full sha256 on large node_modules, records
    node_modules_manifest_s and copy_s, and prints a warning when reflink copy falls back."""
    proj = tmp_path / "proj"
    (proj / "node_modules" / "pkg").mkdir(parents=True)
    for i in range(40):
        d = proj / "node_modules" / "pkg" / f"d{i}"
        d.mkdir()
        for j in range(15):
            (d / f"f{j}.js").write_text("x" * 2048, encoding="utf-8")
    (proj / "package.json").write_text('{"name":"t","scripts":{"test":"node verify.test.js"}}\n', encoding="utf-8")
    (proj / "verify.test.js").write_text("process.exit(0);\n", encoding="utf-8")

    # Force reflink probe failure to guarantee fallback warning is exercised even on reflink-capable FS
    orig_run = subprocess.run

    def _no_reflink_run(cmd, *a, **kw):
        if isinstance(cmd, (list, tuple)) and any("--reflink=always" in str(x) for x in cmd):
            return subprocess.CompletedProcess(cmd, 1, b"", b"reflink not supported")
        return orig_run(cmd, *a, **kw)

    monkeypatch.setattr(R.subprocess, "run", _no_reflink_run)
    agent = _write_agent(tmp_path, "import pathlib; pathlib.Path('out.txt').write_text('ok\\n')\n")
    rc = _run_cli_do(monkeypatch, proj, agent, prompt="hi", attempts=1)
    out = capsys.readouterr().out
    assert rc == 0, out
    assert "reflink" in out.lower() and ("fallback" in out.lower() or "fell back" in out.lower() or "plain copy" in out.lower())

    rj = _latest_result_json(tmp_path / "vwork")
    assert isinstance(rj.get("node_modules_manifest_s"), (int, float)) and rj["node_modules_manifest_s"] >= 0
    assert isinstance(rj.get("copy_s"), (int, float)) and rj["copy_s"] >= 0
    # Verify lstat manifest catches same-size write with restored mtime via ctime_ns
    m1 = R._nm_manifest(proj / "node_modules")
    f0 = proj / "node_modules" / "pkg" / "d0" / "f0.js"
    st = f0.stat()
    time.sleep(0.02)
    f0.write_text("y" * 2048, encoding="utf-8")
    os.utime(f0, ns=(st.st_atime_ns, st.st_mtime_ns))
    m2 = R._nm_manifest(proj / "node_modules")
    assert "pkg/d0/f0.js" in R._nm_diff(m1, m2)


# ============================================================================
# Item 5 (R9) — byte-safe encoding for all strings (prompt, check, tails, audit)
# ============================================================================

def test_r9_surrogate_prompt_and_check_produce_verified_receipt_and_audit(tmp_path, monkeypatch, capsys):
    """R9 (e9-c1-surrogate-prompt.sh): non-UTF-8 prompt must hash raw bytes and yield a verified receipt."""
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "calc.py").write_text("def add(a, b):\n    return a - b\n", encoding="utf-8")
    (proj / "test_calc.py").write_text(
        "import unittest, calc\nclass T(unittest.TestCase):\n"
        "    def test_add(self): self.assertEqual(calc.add(2, 3), 5)\n",
        encoding="utf-8",
    )
    agent = _write_agent(tmp_path, "import pathlib; pathlib.Path('calc.py').write_text('def add(a, b):\\n    return a + b\\n')\n")

    raw_prompt = os.fsdecode(b"bad\xffprompt")
    rc = _run_cli_do(monkeypatch, proj, agent, prompt=raw_prompt, attempts=1)
    out = capsys.readouterr().out
    assert rc == 0, out

    rj = _latest_result_json(tmp_path / "vwork")
    assert rj["receipt"]["recorded"] is True, rj["receipt"]

    ok, why, receipts = R.verify_receipts(proj, state_root=tmp_path / "vhome")
    assert ok, why
    assert len(receipts) == 1
    assert receipts[0]["request_sha256"] == hashlib.sha256(b"bad\xffprompt").hexdigest()

    home = str(tmp_path / "vhome")
    work = str(tmp_path / "vwork")
    audit_rc = AE.main(["list", "--vacant-home", home, "--work-root", work, "--strict", "--require-signed"])
    audit_out = capsys.readouterr().out
    assert audit_rc == 0, audit_out
    data_lines = [ln for ln in audit_out.splitlines() if ln.startswith("restart:")]
    assert len(data_lines) == 1 and "unsigned" not in data_lines[0] and "yes" in data_lines[0], audit_out

    exp_out = AE.export_jsonl(AE.collect_all(vacant_home=home, work_root=work))
    exp_out.encode("utf-8")  # must be strict valid UTF-8


# ============================================================================
# Item 6 (R4) — B1 lstat listing covers .git (except objects/), nm, .venv, __pycache__, .pytest_cache
# ============================================================================

@needs_git
def test_r4_b1_listing_covers_git_refs_head_new_nm_nested_nm_venv_and_warns(tmp_path, monkeypatch, capsys):
    """R4 (e4-b1-listing-gaps.sh): all .git (except objects/), new root nm, nested nm, .venv, __pycache__."""
    proj = tmp_path / "proj"
    proj.mkdir()
    subprocess.run(["git", "init", "-q", str(proj)], check=True)
    subprocess.run(["git", "-C", str(proj), "config", "user.email", "t@t"], check=True)
    subprocess.run(["git", "-C", str(proj), "config", "user.name", "t"], check=True)
    (proj / "calc.py").write_text("def add(a, b):\n    return a - b\n", encoding="utf-8")
    (proj / "test_calc.py").write_text(
        "import unittest, calc\nclass T(unittest.TestCase):\n"
        "    def test_add(self): self.assertEqual(calc.add(2, 3), 5)\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "-C", str(proj), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(proj), "commit", "-qm", "init"], check=True)

    agent = _write_agent(tmp_path, textwrap.dedent(f"""\
        import pathlib, subprocess
        pathlib.Path('calc.py').write_text('def add(a, b):\\n    return a + b\\n')
        orig = pathlib.Path({str(proj)!r})
        (orig / '.git' / 'refs' / 'heads' / 'pwned-branch').write_text('0'*40 + '\\n')
        (orig / '.git' / 'HEAD.evil').write_text('ref: refs/heads/pwned-branch\\n')
        subprocess.run(['git', '--git-dir', str(orig / '.git'), 'update-ref', 'refs/heads/hijacked', 'HEAD'], check=True)
        (orig / 'node_modules' / 'evilpkg').mkdir(parents=True)
        (orig / 'node_modules' / 'evilpkg' / 'index.js').write_text('module.exports = 1;\\n')
        (orig / 'sub' / 'lib' / 'node_modules' / 'dep2').mkdir(parents=True)
        (orig / 'sub' / 'lib' / 'node_modules' / 'dep2' / 'index.js').write_text('module.exports = 1;\\n')
        (orig / 'tools' / '.venv' / 'lib' / 'python3.12' / 'site-packages').mkdir(parents=True)
        (orig / 'tools' / '.venv' / 'lib' / 'python3.12' / 'site-packages' / 'evil.pth').write_text('import os\\n')
        (orig / 'pkg' / '__pycache__').mkdir(parents=True)
        (orig / 'pkg' / '__pycache__' / 'x.pyc').write_bytes(b'abc')
        (orig / 'plain_escape.txt').write_text('plain\\n')
        """))

    rc = _run_cli_do(monkeypatch, proj, agent, prompt="escape all", attempts=1)
    out = capsys.readouterr().out
    assert rc == 0, out

    rj = _latest_result_json(tmp_path / "vwork")
    oc = set(rj["outside_changes"])
    for expected in [
        ".git/refs/heads/pwned-branch",
        ".git/refs/heads/hijacked",
        ".git/HEAD.evil",
        "node_modules/evilpkg/index.js",
        "sub/lib/node_modules/dep2/index.js",
        "tools/.venv/lib/python3.12/site-packages/evil.pth",
        "pkg/__pycache__/x.pyc",
        "plain_escape.txt",
    ]:
        assert expected in oc, f"missing {expected} from outside_changes={sorted(oc)}"
    assert isinstance(rj.get("lstat_listing_s"), (int, float)) and rj["lstat_listing_s"] >= 0
    # Prominent warnings for .git/refs|HEAD and .venv .pth
    assert "WARNING" in out and ".git/refs" in out
    assert "WARNING" in out and "evil.pth" in out


# ============================================================================
# Item 7 (R5) — robust --check parsing, nested manifests, shell expansion warning
# ============================================================================

@needs_node
@pytest.mark.parametrize("check_cmd,target_pkg", [
    ("sh -c 'npm test'", "package.json"),
    ("env sh -c 'npm test'", "package.json"),
    ("timeout 30 npm test", "package.json"),
    ("nice -n 5 bash -c 'npm test'", "package.json"),
    ("npm --prefix sub test", "sub/package.json"),
    ("cd sub && npm test", "sub/package.json"),
])
def test_r5_check_wrappers_and_nested_package_json_protected(tmp_path, monkeypatch, capsys, check_cmd, target_pkg):
    """R5 (e5-a3-check-wrap.sh): wrappers & nested manifests must protect and pin package.json."""
    proj = tmp_path / "proj"
    (proj / "sub").mkdir(parents=True)
    orig_pkg = '{"name":"t","scripts":{"test":"node verify.test.js"}}\n'
    for base in (proj, proj / "sub"):
        (base / "package.json").write_text(orig_pkg, encoding="utf-8")
        (base / "verify.test.js").write_text(
            "const dep = require('./dep.js');\nif (!dep.ok()) process.exit(1);\n", encoding="utf-8"
        )
        (base / "dep.js").write_text("exports.ok = () => false;\n", encoding="utf-8")

    agent = _write_agent(tmp_path, textwrap.dedent(f"""\
        import json, pathlib
        p = pathlib.Path({target_pkg!r})
        d = json.loads(p.read_text())
        d['scripts']['test'] = 'true'
        p.write_text(json.dumps(d))
        """))

    rc = _run_cli_do(monkeypatch, proj, agent, prompt="cheat", attempts=1, extra_args=["--check", check_cmd])
    out = capsys.readouterr().out
    assert rc == adapters_cli.EXIT["reject"], out
    assert (proj / target_pkg).read_text(encoding="utf-8") == orig_pkg


def test_r5_check_nested_make_cargo_go_tokens_and_shell_expansion_warning(tmp_path, monkeypatch, capsys):
    """R5: nested Makefiles/*.mk, Cargo.toml, go.mod, file tokens inside wrappers, and shell expansion warning."""
    proj = tmp_path / "proj"
    (proj / "sub").mkdir(parents=True)
    (proj / "scripts").mkdir(parents=True)
    (proj / "Makefile").write_text("test:\n\t@true\n", encoding="utf-8")
    (proj / "sub" / "rules.mk").write_text("all:\n\t@true\n", encoding="utf-8")
    (proj / "sub" / "Cargo.toml").write_text("[package]\nname='a'\n", encoding="utf-8")
    (proj / "sub" / "go.mod").write_text("module a\n", encoding="utf-8")
    (proj / "scripts" / "check.sh").write_text("#!/bin/bash\nexit 0\n", encoding="utf-8")
    (proj / "sub" / "run.py").write_text("import sys; sys.exit(0)\n", encoding="utf-8")

    s_make = R.detect_acceptance(proj, check="env FOO=1 timeout 10 sh -c 'make -C sub test'")
    assert {"Makefile", "sub/rules.mk"} <= set(s_make.protected)

    s_cargo = R.detect_acceptance(proj, check="cd sub && cargo test")
    assert "sub/Cargo.toml" in s_cargo.protected

    s_go = R.detect_acceptance(proj, check="nice go test ./...")
    assert "sub/go.mod" in s_go.protected

    s_tok = R.detect_acceptance(proj, check=f"sh -c 'cd sub && {sys.executable} run.py' && bash ./scripts/check.sh")
    assert {"sub/run.py", "scripts/check.sh"} <= set(s_tok.protected)

    # Shell expansion warning in summary
    agent = _write_agent(tmp_path, "pass\n")
    monkeypatch.setenv("VACANT_TEST_CMD", "true")
    rc = _run_cli_do(monkeypatch, proj, agent, prompt="x", attempts=1, extra_args=["--check", "$VACANT_TEST_CMD"])
    out = capsys.readouterr().out
    assert rc == 0, out
    assert "the check command uses shell expansion; Vacant could not see which files it runs" in out


# ============================================================================
# Item 8 (R6) — reworked acceptance_dependencies_changed
# ============================================================================

def test_r6_acceptance_dependencies_literals_transitive_dirs_and_no_mut_noise(tmp_path, monkeypatch, capsys):
    """R6 (e6-a1-unflagged-deps.sh): root literal, data/, transitive py/js imports, jest.mock,
    ordered with reasons, and sole direct import (module under test) NOT flagged."""
    # (1) Root expected.txt literal + sole direct import calc.py NOT flagged
    proj = tmp_path / "p_root"
    proj.mkdir()
    (proj / "calc.py").write_text("def add(a, b):\n    return a - b\n", encoding="utf-8")
    (proj / "expected.txt").write_text("5", encoding="utf-8")
    (proj / "test_calc.py").write_text(textwrap.dedent("""\
        import unittest, pathlib, calc
        class T(unittest.TestCase):
            def test_add(self):
                want = int(pathlib.Path('expected.txt').read_text().strip())
                self.assertEqual(calc.add(2, 3), want)
        """), encoding="utf-8")

    # Legitimate fix of calc.py only -> acceptance_dependencies_changed must be EMPTY (no MUT noise!)
    agent_good = _write_agent(tmp_path, "import pathlib; pathlib.Path('calc.py').write_text('def add(a, b):\\n    return a + b\\n')\n", name="good.py")
    rc = _run_cli_do(monkeypatch, proj, agent_good, prompt="fix", attempts=1)
    out = capsys.readouterr().out
    assert rc == 0, out
    rj = _latest_result_json(tmp_path / "vwork")
    assert rj["acceptance_dependencies_changed"] == [], f"MUT should not be flagged: {rj['acceptance_dependencies_changed']}"

    # Poisoning root expected.txt -> flagged with reason 'literal'
    (proj / "calc.py").write_text("def add(a, b):\n    return a - b\n", encoding="utf-8")
    agent_poison = _write_agent(tmp_path, "import pathlib; pathlib.Path('expected.txt').write_text('-1')\n", name="poison.py")
    rc = _run_cli_do(monkeypatch, proj, agent_poison, prompt="poison", attempts=1)
    out = capsys.readouterr().out
    assert rc == 0, out
    rj = _latest_result_json(tmp_path / "vwork")
    deps = rj["acceptance_dependencies_changed"]
    assert any(d["path"] == "expected.txt" and "literal" in d["reasons"] for d in deps), deps
    assert "expected.txt" in out and "literal" in out

    # (2) data/ dir + transitive Python import (test -> helpers -> helpers2)
    proj2 = tmp_path / "p_trans"
    (proj2 / "data").mkdir(parents=True)
    (proj2 / "impl.py").write_text("def answer(): return 41\n", encoding="utf-8")
    (proj2 / "helpers2.py").write_text("EXPECTED = 42\n", encoding="utf-8")
    (proj2 / "helpers.py").write_text("import helpers2\ndef expected(): return helpers2.EXPECTED\n", encoding="utf-8")
    (proj2 / "data" / "val.txt").write_text("42", encoding="utf-8")
    (proj2 / "test_impl.py").write_text(textwrap.dedent("""\
        import unittest, impl, helpers
        class T(unittest.TestCase):
            def test_a(self):
                self.assertEqual(impl.answer(), helpers.expected())
        """), encoding="utf-8")
    agent_t = _write_agent(tmp_path, textwrap.dedent("""\
        import pathlib
        pathlib.Path('helpers2.py').write_text('EXPECTED = 41\\n')
        pathlib.Path('data/val.txt').write_text('41')
        """), name="trans.py")
    rc2 = _run_cli_do(monkeypatch, proj2, agent_t, prompt="poison trans", attempts=1)
    out2 = capsys.readouterr().out
    assert rc2 == 0, out2
    rj2 = _latest_result_json(tmp_path / "vwork")
    deps2 = {d["path"]: d["reasons"] for d in rj2["acceptance_dependencies_changed"]}
    assert "helpers2.py" in deps2 and "import" in deps2["helpers2.py"]
    assert "data/val.txt" in deps2 and "dir" in deps2["data/val.txt"]

    # (3) JS depth-2 transitive import + jest.mock('./mocked') + __mocks__/golden/mocks dirs
    js_root = tmp_path / "p_js"
    js_root.mkdir()
    (js_root / "app.js").write_text("exports.v = 1;\n", encoding="utf-8")
    (js_root / "h1.js").write_text("const h2 = require('./h2');\nexports.x = h2.y;\n", encoding="utf-8")
    (js_root / "h2.js").write_text("exports.y = 42;\n", encoding="utf-8")
    (js_root / "mocked.js").write_text("exports.m = 1;\n", encoding="utf-8")
    test_src = b"const app = require('./app');\nconst h1 = require('./h1');\njest.mock('./mocked');\n"
    res_js = R._find_acceptance_dependencies(
        {"app.test.js": test_src},
        {"app.test.js", "app.js", "h1.js", "h2.js", "mocked.js", "golden/g.txt", "__mocks__/m.js", "mocks/x.py"},
        {"h2.js", "mocked.js", "golden/g.txt", "__mocks__/m.js", "mocks/x.py"},
        source_root=js_root,
    )
    by_path = {d["path"]: d["reasons"] for d in res_js}
    assert "h2.js" in by_path and "import" in by_path["h2.js"]
    assert "mocked.js" in by_path and "import" in by_path["mocked.js"]
    assert "golden/g.txt" in by_path and "dir" in by_path["golden/g.txt"]
    assert "__mocks__/m.js" in by_path and "dir" in by_path["__mocks__/m.js"]
    assert "mocks/x.py" in by_path and "dir" in by_path["mocks/x.py"]


# ============================================================================
# Item 9 (R12) — COPY_SKIP-named dirs created by agent listed in not_delivered
# ============================================================================

def test_r12_copy_skip_created_files_listed_as_not_delivered(tmp_path, monkeypatch, capsys):
    """R12 (e15-copskip-silent-drop.sh): files created under nested COPY_SKIP dirs are not delivered
    and are listed in result.json['not_delivered'] and summary with reason."""
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "calc.py").write_text("def add(a, b): return a - b\n", encoding="utf-8")
    (proj / "test_calc.py").write_text(
        "import unittest, calc\nclass T(unittest.TestCase):\n"
        "    def test_add(self): self.assertEqual(calc.add(2, 3), 5)\n",
        encoding="utf-8",
    )
    agent = _write_agent(tmp_path, textwrap.dedent("""\
        import pathlib
        pathlib.Path('calc.py').write_text('def add(a, b): return a + b\\n')
        for rel, body in [
            ('vendor/node_modules/lib.js', 'module.exports=1\\n'),
            ('sub/.venv/f.txt', 'x\\n'),
            ('pkg/__pycache__/g.txt', 'y\\n'),
        ]:
            p = pathlib.Path(rel)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(body)
        """))

    rc = _run_cli_do(monkeypatch, proj, agent, prompt="fix", attempts=1)
    out = capsys.readouterr().out
    assert rc == 0, out
    # Delivery unchanged: none of those files exist in project
    assert not (proj / "vendor" / "node_modules" / "lib.js").exists()
    assert not (proj / "sub" / ".venv" / "f.txt").exists()
    assert not (proj / "pkg" / "__pycache__" / "g.txt").exists()

    rj = _latest_result_json(tmp_path / "vwork")
    nd = rj.get("not_delivered")
    assert isinstance(nd, list) and len(nd) == 3, nd
    nd_paths = {item["path"]: item["reason"] for item in nd}
    assert set(nd_paths) == {"vendor/node_modules/lib.js", "sub/.venv/f.txt", "pkg/__pycache__/g.txt"}
    assert all(nd_paths.values())
    assert "not delivered" in out.lower()
    assert "vendor/node_modules/lib.js" in out


# ============================================================================
# Item 10 (R11) — start snapshot in acceptance; overlap->exit 43; protected line
# ============================================================================

def test_r11_acceptance_uses_start_snapshot_not_live_project(tmp_path, monkeypatch, capsys):
    """R11 (e11-acceptance-live-files.sh): direct write to live project does NOT make acceptance pass."""
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "impl.py").write_text("def answer():\n    return 41\n", encoding="utf-8")
    (proj / "test_impl.py").write_text(
        "import unittest, impl\nclass T(unittest.TestCase):\n"
        "    def test_a(self): self.assertEqual(impl.answer(), 42)\n",
        encoding="utf-8",
    )
    agent = _write_agent(tmp_path, textwrap.dedent(f"""\
        import pathlib
        pathlib.Path({str(proj / 'impl.py')!r}).write_text("def answer():\\n    return 42\\n")
        """))

    rc = _run_cli_do(monkeypatch, proj, agent, prompt="direct write", attempts=2)
    out = capsys.readouterr().out
    assert rc == adapters_cli.EXIT["reject"], out
    rj = _latest_result_json(tmp_path / "vwork")
    assert rj["accepted"] is False
    assert len(rj["attempts"]) == 2 and all(a["accept"] is False for a in rj["attempts"])
    assert "impl.py" in rj["outside_changes"]
    assert "your project changed during the run, not by this delivery:" in out
    assert "not checked and not touched" in out


def test_r11_overlap_writes_nothing_back_and_exits_43(tmp_path, monkeypatch, capsys):
    """R11(b) (e16-d3-conflict.sh): overlap between live project changes and delivered attempt writes
    NOTHING back (no partial delivery), exits 43, lists conflicts + merge workspace dir."""
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "calc.py").write_text("def add(a, b): return a - b\n", encoding="utf-8")
    (proj / "shared.py").write_text("X = 1\n", encoding="utf-8")
    (proj / "test_calc.py").write_text(
        "import unittest, calc\nclass T(unittest.TestCase):\n"
        "    def test_add(self): self.assertEqual(calc.add(2, 3), 5)\n",
        encoding="utf-8",
    )
    agent = _write_agent(tmp_path, textwrap.dedent(f"""\
        import pathlib
        # Concurrent edit in original project on shared.py
        pathlib.Path({str(proj / 'shared.py')!r}).write_text("X = 99\\n")
        # Agent edits both calc.py and shared.py in workspace
        pathlib.Path("calc.py").write_text("def add(a, b): return a + b\\n")
        pathlib.Path("shared.py").write_text("X = 2\\n")
        """))

    rc = _run_cli_do(monkeypatch, proj, agent, prompt="fix", attempts=1)
    out = capsys.readouterr().out
    assert rc == adapters_cli.EXIT["void"], out
    # NOTHING written back: calc.py still original buggy, shared.py still user's X=99
    assert (proj / "calc.py").read_text(encoding="utf-8") == "def add(a, b): return a - b\n"
    assert (proj / "shared.py").read_text(encoding="utf-8") == "X = 99\n"

    rj = _latest_result_json(tmp_path / "vwork")
    assert rj["write_back_conflicts"] == ["shared.py"]
    assert rj["changed"]["modified"] == [] and rj["changed"]["added"] == [] and rj["changed"]["deleted"] == []
    assert "shared.py" in out
    assert rj["attempts"][0]["workspace"] in out

    ok, why, receipts = R.verify_receipts(proj, state_root=tmp_path / "vhome")
    assert ok, why
    assert receipts[0]["write_back_conflicts"] == ["shared.py"]


def test_r11_protected_file_changed_in_original_printed_prominently(tmp_path, monkeypatch, capsys):
    """R11(c): a protected test/config file changed in original during run is non-overlapping (delivers),
    and gets its own prominent line in the summary."""
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "calc.py").write_text("def add(a, b): return a - b\n", encoding="utf-8")
    (proj / "test_calc.py").write_text(
        "import unittest, calc\nclass T(unittest.TestCase):\n"
        "    def test_add(self): self.assertEqual(calc.add(2, 3), 5)\n",
        encoding="utf-8",
    )
    agent = _write_agent(tmp_path, textwrap.dedent(f"""\
        import pathlib
        pathlib.Path('calc.py').write_text('def add(a, b): return a + b\\n')
        # Someone modifies test_calc.py in the original project during run
        pathlib.Path({str(proj / 'test_calc.py')!r}).write_text('# edited during run\\n')
        """))

    rc = _run_cli_do(monkeypatch, proj, agent, prompt="fix", attempts=1)
    out = capsys.readouterr().out
    assert rc == 0, out
    assert (proj / "calc.py").read_text(encoding="utf-8") == "def add(a, b): return a + b\n"
    assert "a protected test/config file changed in your project during the run:" in out
    assert "test_calc.py" in out


# ============================================================================
# Item 11 (R2/R3) — PR_SET_CHILD_SUBREAPER + killing detached descendants
# ============================================================================

@needs_linux_proc
def test_r2_subreaper_catches_and_kills_env_scrubbed_detached_process(tmp_path, monkeypatch, capsys):
    """R2 (e2-b2-env-i.sh): setsid + env -i / env -u detached writers are caught and killed."""
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "calc.py").write_text("def add(a, b): return a - b\n", encoding="utf-8")
    (proj / "test_calc.py").write_text(
        "import unittest, calc\nclass T(unittest.TestCase):\n"
        "    def test_add(self): self.assertEqual(calc.add(2, 3), 5)\n",
        encoding="utf-8",
    )
    late1 = proj / "late_env_i.txt"
    late2 = proj / "late_env_u.txt"
    agent = _write_agent(tmp_path, textwrap.dedent(f"""\
        import os, pathlib, subprocess, time
        pathlib.Path('calc.py').write_text('def add(a, b): return a + b\\n')
        subprocess.Popen(
            ["setsid", "env", "-i", "/bin/sh", "-c", "sleep 2; echo ESC > {late1}"],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        env2 = {{k: v for k, v in os.environ.items() if k != "VACANT_RUN_ID"}}
        subprocess.Popen(
            ["setsid", "/bin/sh", "-c", "sleep 2; echo ESC2 > {late2}"],
            env=env2, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        time.sleep(0.2)
        """))

    rc = _run_cli_do(monkeypatch, proj, agent, prompt="spawn scrubbed detached", attempts=1)
    out = capsys.readouterr().out
    assert rc == 0, out
    rj = _latest_result_json(tmp_path / "vwork")
    det = rj["detached_processes"]
    assert isinstance(det, list) and len(det) >= 2, det
    assert all(isinstance(d, dict) and {"phase", "pid", "cmdline", "killed"} <= set(d) for d in det), det
    assert any(d["phase"] == "agent" and d["killed"] is True for d in det), det
    assert "detached" in out.lower() and str(len(det)) in out

    # Wait past the 2s sleep: killed processes must never write the late files
    time.sleep(2.5)
    assert not late1.exists(), "detached env -i process was not killed!"
    assert not late2.exists(), "detached env -u process was not killed!"


@needs_linux_proc
def test_r3_subreaper_catches_and_kills_acceptance_spawned_detached_process(tmp_path, monkeypatch, capsys):
    """R3 (e3-b2-check-spawned.sh): detached process spawned during acceptance is caught and killed."""
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "impl.py").write_text("def ok(): return False\n", encoding="utf-8")
    (proj / "test_impl.py").write_text(
        "import unittest, impl\nclass T(unittest.TestCase):\n"
        "    def test_ok(self): self.assertTrue(impl.ok())\n",
        encoding="utf-8",
    )
    late_chk = proj / "late_check.txt"
    impl_payload = (
        "import subprocess, time\n"
        "def ok(): return True\n"
        f"subprocess.Popen(['setsid', '/bin/sh', '-c', 'sleep 2; echo CHECK > {late_chk}'], "
        "stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)\n"
        "time.sleep(0.15)\n"
    )
    agent = _write_agent(tmp_path, f"import pathlib\npathlib.Path('impl.py').write_text({impl_payload!r})\n")

    rc = _run_cli_do(monkeypatch, proj, agent, prompt="arm check detached", attempts=1)
    out = capsys.readouterr().out
    assert rc == 0, out
    rj = _latest_result_json(tmp_path / "vwork")
    det = rj["detached_processes"]
    assert isinstance(det, list) and len(det) >= 1, det
    assert any(d["phase"] == "acceptance" and d["killed"] is True for d in det), det

    time.sleep(2.5)
    assert not late_chk.exists(), "acceptance-spawned detached process was not killed!"


def test_r2_non_linux_detached_null_and_summary_note(tmp_path, monkeypatch):
    """R2: on non-Linux, detached_processes is null and summary states this layer does not exist."""
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "test_ok.py").write_text(
        "import unittest\nclass T(unittest.TestCase):\n    def test_one(self): self.assertEqual(1, 1)\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(R.sys, "platform", "darwin")
    agent = _write_agent(tmp_path, "pass\n")
    res = R.run(proj, lambda p, ws: Launch(argv=[sys.executable, str(agent)], env={}),
                "noop", max_attempts=1, attempt_timeout_s=20, budget_s=60)
    assert res["detached_processes"] is None
    msg = R.summary(res)
    assert any(
        "detached" in ln.lower() and ("not available" in ln.lower() or "does not exist" in ln.lower())
        for ln in msg.splitlines()
        if not ln.strip().startswith(("scanned:", "attempts and logs:"))
    ), msg


# ============================================================================
# Item 12 — Plan -> apply TOCTOU re-check in _apply_write_plan
# ============================================================================

def test_item12_apply_write_plan_toctou_rechecks_start_snapshot(tmp_path):
    """Item 12: if live project file changes between plan and apply, _apply_write_plan skips it
    and marks it as a conflict instead of overwriting/deleting the raced edit."""
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "mod.txt").write_text("start_mod\n", encoding="utf-8")
    (proj / "del.txt").write_text("start_del\n", encoding="utf-8")
    (proj / "ok.txt").write_text("start_ok\n", encoding="utf-8")

    start_hashes = R._scan_file_hashes(proj)

    ws = tmp_path / "ws"
    ws.mkdir()
    (ws / "mod.txt").write_text("agent_mod\n", encoding="utf-8")
    (ws / "ok.txt").write_text("agent_ok\n", encoding="utf-8")
    # del.txt omitted (deleted by agent)

    snap = R._snapshot_workspace(ws, tmp_path / "snap")
    plan = R._plan_write_back(proj, snap, set(), start_hashes=start_hashes)
    assert plan.modified == ["mod.txt", "ok.txt"]
    assert plan.deleted == ["del.txt"]
    assert plan.conflicts == []

    # Simulate TOCTOU race AFTER plan, BEFORE apply!
    (proj / "mod.txt").write_text("raced_user_mod\n", encoding="utf-8")
    (proj / "del.txt").write_text("raced_user_del\n", encoding="utf-8")

    changed = R._apply_write_plan(proj, snap, plan, tmp_path / "bkp", start_hashes=start_hashes)
    assert (proj / "mod.txt").read_text(encoding="utf-8") == "raced_user_mod\n"
    assert (proj / "del.txt").read_text(encoding="utf-8") == "raced_user_del\n"
    assert (proj / "ok.txt").read_text(encoding="utf-8") == "agent_ok\n"
    assert set(changed["conflict"]) == {"mod.txt", "del.txt"}
    assert changed["modified"] == ["ok.txt"]
    assert changed["deleted"] == []
