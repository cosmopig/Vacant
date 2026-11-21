"""Adversarial review (rc5) regression tests for `vacant do` restart mode.

Covers all 9 items (11 repros) from `tests/adversarial_rc5_repro/REPORT.md`:
1. B3 — node_modules copy for agent + sha256/mode/type/symlink content manifest + cost reporting
2. A3/A4 — `--check` manifest pinning (npm/npx/yarn/pnpm/cargo/go/make) & auto-protecting file tokens
3. D3 — write-back diff relative to start snapshot (no concurrent deletes, `appeared_during_run`, `conflict`)
4. C1 — non-UTF-8 (surrogateescape) paths safe in result.json, signed receipt, summary, audit `--strict`
5. B1 — lstat project listing before/after detecting `.git/hooks/*`, `.git/config`, symlinks, escapes
6. B2 — `VACANT_RUN_ID` env marker + Linux `/proc/*/environ` detached process detection (`null` elsewhere)
7. D1/D2 — read-only project refusal (exit 43), writable copy, non-zero agent exit shown on pass;
           subdir scan message + parent test detection
8. A1/A2 — `acceptance_dependencies_changed` flagging (Python AST & JS relative imports + fixture dirs)
9. A5 — additional test runner config files protected, restored before check, and never written back
"""
from __future__ import annotations

import json
import os
import pathlib
import shutil
import signal
import stat
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


def _latest_result_json(tmp_path: pathlib.Path) -> dict:
    files = sorted((tmp_path / "vwork").glob("restart-*/result.json"))
    assert files, "expected result.json in VACANT_WORK"
    return json.loads(files[-1].read_text(encoding="utf-8"))


# ============================================================================
# 1. B3 — node_modules isolation (copy for agent) + content manifest + cost
# ============================================================================

@needs_node
def test_b3_ws_node_modules_spoof_does_not_poison_original(tmp_path, monkeypatch, capsys):
    """b3-node-modules-spoof.sh: agent chmods ws/node_modules, writes same-size content,
    restores mtime. Because ws gets its own copy, original node_modules stays untouched,
    acceptance runs against untouched original and FAILS, and copy/hash costs are reported."""
    proj = tmp_path / "proj"
    (proj / "node_modules" / "depcheck").mkdir(parents=True)
    orig_js = "exports.ok = () => false;"
    (proj / "package.json").write_text(
        '{"name":"demo","version":"1.0.0","scripts":{"test":"node verify.test.js"}}\n', encoding="utf-8"
    )
    (proj / "verify.test.js").write_text(
        "const dc = require('depcheck');\nprocess.exit(dc.ok() ? 0 : 1);\n", encoding="utf-8"
    )
    (proj / "node_modules" / "depcheck" / "index.js").write_text(orig_js, encoding="utf-8")
    (proj / "node_modules" / "depcheck" / "package.json").write_text(
        '{"name":"depcheck","version":"1.0.0","main":"index.js"}', encoding="utf-8"
    )

    marker = tmp_path / "ws_nm_info.json"
    agent = _write_agent(tmp_path, textwrap.dedent(f"""\
        import json, os, pathlib
        root = pathlib.Path("node_modules")
        info = {{"is_symlink": root.is_symlink(), "is_dir": root.is_dir()}}
        pathlib.Path({str(marker)!r}).write_text(json.dumps(info))
        for dp, dn, fn in os.walk(root):
            os.chmod(dp, 0o755)
            for f in fn:
                os.chmod(os.path.join(dp, f), 0o644)
        p = root / "depcheck" / "index.js"
        st = os.stat(p)
        new = "exports.ok = () => true; "
        assert len(new.encode()) == st.st_size
        p.write_text(new, encoding="utf-8")
        os.utime(p, ns=(st.st_atime_ns, st.st_mtime_ns))
        """))

    rc = _run_cli_do(monkeypatch, proj, agent, prompt="make npm test pass", attempts=1)
    out = capsys.readouterr().out

    assert rc == adapters_cli.EXIT["reject"], out
    assert (proj / "node_modules" / "depcheck" / "index.js").read_text(encoding="utf-8") == orig_js
    info = json.loads(marker.read_text(encoding="utf-8"))
    assert info["is_symlink"] is False, "agent ws/node_modules must be a copy, not a symlink to original"
    assert info["is_dir"] is True

    rj = _latest_result_json(tmp_path)
    assert isinstance(rj.get("node_modules_copy_s"), (int, float)) and rj["node_modules_copy_s"] >= 0
    assert isinstance(rj.get("node_modules_hash_s"), (int, float)) and rj["node_modules_hash_s"] >= 0


@needs_node
def test_b3_abs_path_same_size_mtime_spoof_caught_by_content_manifest(tmp_path, monkeypatch, capsys):
    """Agent bypasses ws and writes directly to ORIGINAL project/node_modules via absolute path
    with identical byte length and restored mtime_ns. Content sha256 manifest MUST catch it,
    stop (exit 43), write nothing back, and list the changed path."""
    proj = tmp_path / "proj"
    (proj / "node_modules" / "depcheck").mkdir(parents=True)
    orig_js = "exports.ok = () => false;"
    (proj / "package.json").write_text(
        '{"name":"demo","version":"1.0.0","scripts":{"test":"node verify.test.js"}}\n', encoding="utf-8"
    )
    (proj / "verify.test.js").write_text(
        "const dc = require('depcheck');\nprocess.exit(dc.ok() ? 0 : 1);\n", encoding="utf-8"
    )
    target = proj / "node_modules" / "depcheck" / "index.js"
    target.write_text(orig_js, encoding="utf-8")
    (proj / "node_modules" / "depcheck" / "package.json").write_text(
        '{"name":"depcheck","version":"1.0.0","main":"index.js"}', encoding="utf-8"
    )

    agent = _write_agent(tmp_path, textwrap.dedent(f"""\
        import os, pathlib
        p = pathlib.Path({str(target)!r})
        os.chmod(p.parent, 0o755)
        os.chmod(p, 0o644)
        st = os.stat(p)
        new = "exports.ok = () => true; "
        assert len(new.encode()) == st.st_size
        p.write_text(new, encoding="utf-8")
        os.utime(p, ns=(st.st_atime_ns, st.st_mtime_ns))
        pathlib.Path("deliverable.txt").write_text("should not be written back\\n")
        """))

    rc = _run_cli_do(monkeypatch, proj, agent, prompt="spoof original node_modules", attempts=2)
    out = capsys.readouterr().out

    assert rc == adapters_cli.EXIT["void"], out
    assert "depcheck/index.js" in out
    assert not (proj / "deliverable.txt").exists(), "nothing may be written back after node_modules mismatch"
    rj = _latest_result_json(tmp_path)
    assert "depcheck/index.js" in rj["node_modules_changed"]
    assert rj["accepted"] is False
    assert len(rj["attempts"]) == 1


# ============================================================================
# 2. A3/A4 — `--check` manifest pinning & auto-protecting file tokens
# ============================================================================

@needs_node
def test_a3_check_npm_pins_and_restores_package_json(tmp_path, monkeypatch, capsys):
    """a3-check-manifest-rewrite.sh: `--check 'npm test'` must pin & restore package.json."""
    proj = tmp_path / "proj"
    proj.mkdir()
    orig_pkg = '{"name":"demo","version":"1.0.0","scripts":{"test":"node verify.test.js"}}\n'
    (proj / "package.json").write_text(orig_pkg, encoding="utf-8")
    (proj / "verify.test.js").write_text("process.exit(1);\n", encoding="utf-8")

    agent = _write_agent(tmp_path, textwrap.dedent("""\
        import pathlib
        pathlib.Path("package.json").write_text(
            '{"name":"demo","version":"1.0.0","scripts":{"test":"true"}}\\n', encoding="utf-8"
        )
        """))

    rc = _run_cli_do(monkeypatch, proj, agent, extra_args=["--check", "npm test"])
    out = capsys.readouterr().out

    assert rc == adapters_cli.EXIT["reject"], out
    assert (proj / "package.json").read_text(encoding="utf-8") == orig_pkg
    assert "protected (restored before check):" in out
    prot_line = [ln for ln in out.splitlines() if "protected (restored before check):" in ln][0]
    assert "package.json" in prot_line
    rj = _latest_result_json(tmp_path)
    assert rj["acceptance"]["pinned_script"] == "node verify.test.js"
    assert "package.json" in rj["attempts"][0]["tests_tampered"]


def test_a4_check_script_auto_protected(tmp_path, monkeypatch, capsys):
    """a4-check-script-rewrite.sh (bash verify.sh + python run_checks.py)."""
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "impl.py").write_text("def answer():\n    return 41\n", encoding="utf-8")
    orig_sh = f"#!/bin/bash\n{sys.executable} -c 'import impl; assert impl.answer()==42'\n"
    (proj / "verify.sh").write_text(orig_sh, encoding="utf-8")

    agent = _write_agent(tmp_path, textwrap.dedent("""\
        import pathlib
        pathlib.Path("verify.sh").write_text("#!/bin/bash\\nexit 0\\n", encoding="utf-8")
        """))

    rc = _run_cli_do(monkeypatch, proj, agent, extra_args=["--check", "bash verify.sh"])
    out = capsys.readouterr().out

    assert rc == adapters_cli.EXIT["reject"], out
    assert (proj / "verify.sh").read_text(encoding="utf-8") == orig_sh
    assert "WARNING: this check runs files in the project that the agent could change" in out
    assert "protected (restored before check):" not in out
    rj = _latest_result_json(tmp_path)
    assert "verify.sh" in rj["protected"]
    assert rj["acceptance_integrity"] == "unverified"

    # Python harness script token variant
    proj2 = tmp_path / "proj2"
    proj2.mkdir()
    (proj2 / "impl.py").write_text("def answer():\n    return 41\n", encoding="utf-8")
    orig_py = "import impl, sys\nsys.exit(0 if impl.answer() == 42 else 1)\n"
    (proj2 / "run_checks.py").write_text(orig_py, encoding="utf-8")
    agent2 = _write_agent(tmp_path, "import pathlib\npathlib.Path('run_checks.py').write_text('import sys; sys.exit(0)\\n')\n", name="agent2.py")
    rc2 = _run_cli_do(monkeypatch, proj2, agent2, extra_args=["--check", f"{sys.executable} run_checks.py"])
    out2 = capsys.readouterr().out
    assert rc2 == adapters_cli.EXIT["reject"], out2
    assert (proj2 / "run_checks.py").read_text(encoding="utf-8") == orig_py
    assert "WARNING: this check runs files in the project that the agent could change" in out2
    assert "protected (restored before check):" not in out2
    rj2 = _latest_result_json(tmp_path)
    assert "run_checks.py" in rj2["protected"]
    assert rj2["acceptance_integrity"] == "unverified"


@needs_make
def test_a4_check_make_auto_protects_makefile(tmp_path, monkeypatch, capsys):
    """a4-check-script-rewrite.sh (make test): Makefile auto-protected."""
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "impl.py").write_text("def answer():\n    return 41\n", encoding="utf-8")
    orig_mk = f"test:\n\t@{sys.executable} -c \"import impl; assert impl.answer()==42\"\n"
    (proj / "Makefile").write_text(orig_mk, encoding="utf-8")

    agent = _write_agent(tmp_path, "import pathlib\npathlib.Path('Makefile').write_text('test:\\n\\t@true\\n')\n")
    rc = _run_cli_do(monkeypatch, proj, agent, extra_args=["--check", "make test"])
    out = capsys.readouterr().out

    assert rc == adapters_cli.EXIT["reject"], out
    assert (proj / "Makefile").read_text(encoding="utf-8") == orig_mk
    assert "WARNING: this check runs files in the project that the agent could change" in out
    assert "protected (restored before check):" not in out
    rj = _latest_result_json(tmp_path)
    assert "Makefile" in rj["protected"]
    assert rj["acceptance_integrity"] == "unverified"


def test_a3_check_cargo_go_yarn_pnpm_npx_manifests_pinned(tmp_path):
    """Verify manifest auto-protection for cargo, go, npx, yarn, pnpm, makefile, GNUmakefile."""
    proj = tmp_path / "multi"
    proj.mkdir()
    (proj / "package.json").write_text('{"scripts":{"test":"echo hi"}}\n', encoding="utf-8")
    (proj / "Cargo.toml").write_text('[package]\nname = "x"\n', encoding="utf-8")
    (proj / "go.mod").write_text("module x\n", encoding="utf-8")
    (proj / "GNUmakefile").write_text("test:\n\t@true\n", encoding="utf-8")

    for cmd, want in [
        ("npm test", "package.json"),
        ("npx jest", "package.json"),
        ("yarn test", "package.json"),
        ("pnpm test", "package.json"),
        ("cargo test", "Cargo.toml"),
        ("go test ./...", "go.mod"),
        ("make test", "GNUmakefile"),
    ]:
        spec = R.detect_acceptance(proj, check=cmd)
        assert want in spec.protected, f"{cmd} must auto-protect {want}"
    assert R.detect_acceptance(proj, check="yarn test").pinned_script == "echo hi"


# ============================================================================
# 3. D3 — concurrent files never deleted, conflicts preserved, normal run identical
# ============================================================================

def test_d3_concurrent_created_file_not_deleted_and_listed(tmp_path, monkeypatch, capsys):
    """d3-concurrent-delete.sh: file created in original project during run is never deleted,
    and is listed in summary, result.json, and signed receipt (`appeared_during_run`)."""
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "test_ok.py").write_text(
        "import unittest\nclass T(unittest.TestCase):\n    def test_one(self): self.assertEqual(1, 1)\n",
        encoding="utf-8",
    )
    userfile = proj / "userfile.txt"
    agent = _write_agent(tmp_path, textwrap.dedent(f"""\
        import pathlib
        # Simulate a concurrent user creating userfile.txt in the original project mid-run
        pathlib.Path({str(userfile)!r}).write_text("USER_EDIT\\n", encoding="utf-8")
        """))

    rc = _run_cli_do(monkeypatch, proj, agent, prompt="noop", attempts=1)
    out = capsys.readouterr().out

    assert rc == 0, out
    assert userfile.exists() and userfile.read_text(encoding="utf-8") == "USER_EDIT\n"
    assert "userfile.txt" in out

    rj = _latest_result_json(tmp_path)
    assert "userfile.txt" not in rj["changed"]["deleted"]
    assert "userfile.txt" in rj["appeared_during_run"]

    ok, why, receipts = R.verify_receipts(proj, state_root=tmp_path / "vhome")
    assert ok, why
    assert "userfile.txt" in receipts[0]["appeared_during_run"]
    assert "userfile.txt" not in receipts[0]["deleted"]


def test_d3_concurrent_edit_conflict_preserves_user_version(tmp_path, monkeypatch, capsys):
    """If original project file changed since start and agent modifies or deletes it,
    leave user's version untouched and mark it `conflict`."""
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "test_ok.py").write_text(
        "import unittest\nclass T(unittest.TestCase):\n    def test_one(self): self.assertEqual(1, 1)\n",
        encoding="utf-8",
    )
    (proj / "shared.txt").write_text("start_shared\n", encoding="utf-8")
    (proj / "delme.txt").write_text("start_delme\n", encoding="utf-8")
    (proj / "clean.txt").write_text("start_clean\n", encoding="utf-8")

    agent = _write_agent(tmp_path, textwrap.dedent(f"""\
        import pathlib
        # Concurrent user edits in original project
        pathlib.Path({str(proj / 'shared.txt')!r}).write_text("user_shared\\n", encoding="utf-8")
        pathlib.Path({str(proj / 'delme.txt')!r}).write_text("user_delme\\n", encoding="utf-8")
        # Agent edits inside ws
        pathlib.Path("shared.txt").write_text("agent_shared\\n", encoding="utf-8")
        pathlib.Path("delme.txt").unlink()
        pathlib.Path("clean.txt").write_text("agent_clean\\n", encoding="utf-8")
        """))

    rc = _run_cli_do(monkeypatch, proj, agent, prompt="edit files", attempts=1)
    out = capsys.readouterr().out

    # Round 2 (R11b): overlap between live project changes and delivered attempt writes NOTHING back and exits 43
    assert rc == adapters_cli.EXIT["void"], out
    assert (proj / "shared.txt").read_text(encoding="utf-8") == "user_shared\n"
    assert (proj / "delme.txt").read_text(encoding="utf-8") == "user_delme\n"
    assert (proj / "clean.txt").read_text(encoding="utf-8") == "start_clean\n"
    assert "overlapping" in out.lower() or "conflict" in out.lower()
    assert "shared.txt" in out and "delme.txt" in out

    rj = _latest_result_json(tmp_path)
    assert set(rj["write_back_conflicts"]) == {"shared.txt", "delme.txt"}
    assert set(rj["conflicts"]) == {"shared.txt", "delme.txt"}
    assert set(rj["changed"]["conflict"]) == {"shared.txt", "delme.txt"}
    assert rj["changed"]["modified"] == []
    assert rj["changed"]["deleted"] == []

    ok, why, receipts = R.verify_receipts(proj, state_root=tmp_path / "vhome")
    assert ok, why
    assert set(receipts[0]["write_back_conflicts"]) == {"shared.txt", "delme.txt"}
    assert set(receipts[0]["conflicts"]) == {"shared.txt", "delme.txt"}


def test_d3_normal_run_write_back_byte_identical(tmp_path, monkeypatch):
    """In a normal run (no concurrent edits), write-back add/modify/delete/keep is byte-for-byte identical to rc4."""
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "test_ok.py").write_text(
        "import unittest, mod\nclass T(unittest.TestCase):\n    def test_v(self): self.assertEqual(mod.V, 2)\n",
        encoding="utf-8",
    )
    (proj / "mod.py").write_text("V = 1\n", encoding="utf-8")
    (proj / "keep.bin").write_bytes(b"\x00\x01\x02keep")
    (proj / "drop.txt").write_text("obsolete\n", encoding="utf-8")

    agent = _write_agent(tmp_path, textwrap.dedent("""\
        import pathlib
        pathlib.Path("mod.py").write_text("V = 2\\n", encoding="utf-8")
        pathlib.Path("added.bin").write_bytes(b"\\xff\\xfeadded")
        pathlib.Path("drop.txt").unlink()
        """))

    rc = _run_cli_do(monkeypatch, proj, agent, prompt="normal update", attempts=1)
    assert rc == 0
    assert (proj / "mod.py").read_bytes() == b"V = 2\n"
    assert (proj / "keep.bin").read_bytes() == b"\x00\x01\x02keep"
    assert (proj / "added.bin").read_bytes() == b"\xff\xfeadded"
    assert not (proj / "drop.txt").exists()

    rj = _latest_result_json(tmp_path)
    assert rj["changed"]["added"] == ["added.bin"]
    assert rj["changed"]["modified"] == ["mod.py"]
    assert rj["changed"]["deleted"] == ["drop.txt"]
    assert rj["changed"]["skipped"] == []
    assert rj["appeared_during_run"] == []
    assert rj["conflicts"] == []
    assert rj["outside_changes"] == []


# ============================================================================
# 4. C1 — non-UTF-8 filename must not crash result.json, receipt, summary, or audit
# ============================================================================

def test_c1_nonutf8_filename_writes_signed_receipt_and_audit_strict_verifies(tmp_path, monkeypatch, capsys):
    """c1-nonutf8-receipt.sh: agent creates `bad-\\xff-name.txt`.
    CLI must NOT exit 2; signed receipt must be written; `vacant audit list --strict` exits 0 & verified."""
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "test_ok.py").write_text(
        "import unittest\nclass T(unittest.TestCase):\n    def test_one(self): self.assertEqual(1, 1)\n",
        encoding="utf-8",
    )

    agent = _write_agent(tmp_path, 'open(b"bad-\\xff-name.txt", "wb").write(b"x")\n')
    rc = _run_cli_do(monkeypatch, proj, agent, prompt="add non-utf8 file", attempts=1)
    out = capsys.readouterr()

    assert rc == 0, f"expected exit 0, got {rc}; out={out.out!r}; err={out.err!r}"
    assert os.path.isfile(os.path.join(os.fsencode(proj), b"bad-\xff-name.txt"))

    rj = _latest_result_json(tmp_path)
    assert rj["receipt"]["recorded"] is True
    assert rj["non_utf8_paths"] is True
    assert rj["changed"]["added"] == ["bad-\\xff-name.txt"]

    ok, why, receipts = R.verify_receipts(proj, state_root=tmp_path / "vhome")
    assert ok, why
    assert len(receipts) == 1
    assert receipts[0]["non_utf8_paths"] is True
    assert receipts[0]["written_back"][0]["path"] == "bad-\\xff-name.txt"

    # `vacant audit list --strict` must exit 0 and show verified with no mismatch
    home = str(tmp_path / "vhome")
    work = str(tmp_path / "vwork")
    audit_rc = AE.main(["list", "--vacant-home", home, "--work-root", work, "--strict"])
    audit_out = capsys.readouterr().out
    assert audit_rc == 0, audit_out
    data_lines = [ln for ln in audit_out.splitlines() if ln.startswith("restart:")]
    assert len(data_lines) == 1 and "unreadable" not in data_lines[0] and "unsigned" not in data_lines[0], audit_out

    recs = AE.collect_all(vacant_home=home, work_root=work)
    restart_recs = [r for r in recs if r["kind"] == "restart"]
    assert len(restart_recs) == 1
    assert restart_recs[0]["signature"]["verified"] is True
    gap_codes = [g["code"] for g in restart_recs[0]["gaps"]]
    assert "result_json_mismatch" not in gap_codes


# ============================================================================
# 5. B1 — direct escapes leave visible record (.git/hooks, .git/config, symlinks)
# ============================================================================

@needs_git
def test_b1_direct_escape_detected_for_git_hooks_config_and_symlinks(tmp_path, monkeypatch, capsys):
    """b1-direct-escape.sh: agent plants .git/hooks/post-commit, edits .git/config,
    plants a symlink, and creates a regular file directly in project.
    Detection only: exit code unchanged (40), nothing reverted, all listed in summary/result/receipt,
    and .git/hooks highlighted prominently."""
    import subprocess
    proj = tmp_path / "proj"
    proj.mkdir()
    subprocess.run(["git", "init", "-q", str(proj)], check=True)
    subprocess.run(["git", "-C", str(proj), "config", "user.email", "t@t"], check=True)
    subprocess.run(["git", "-C", str(proj), "config", "user.name", "t"], check=True)
    (proj / "test_x.py").write_text(
        "import unittest\nclass T(unittest.TestCase):\n    def test_fail(self): self.assertEqual(1, 2)\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "-C", str(proj), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(proj), "commit", "-qm", "init"], check=True)

    agent = _write_agent(tmp_path, textwrap.dedent(f"""\
        import os, pathlib
        orig = pathlib.Path({str(proj)!r})
        hook = orig / ".git" / "hooks" / "post-commit"
        hook.parent.mkdir(parents=True, exist_ok=True)
        hook.write_text("#!/bin/bash\\necho HOOK_FIRED\\n", encoding="utf-8")
        os.chmod(hook, 0o755)
        cfg = orig / ".git" / "config"
        cfg.write_text(cfg.read_text(encoding="utf-8") + "\\n# touched\\n", encoding="utf-8")
        os.symlink("/etc/hostname", orig / "planted_link")
        (orig / "pwned_regular.txt").write_text("PWNED\\n", encoding="utf-8")
        """))

    rc = _run_cli_do(monkeypatch, proj, agent, prompt="fix test", attempts=1)
    out = capsys.readouterr().out

    # Detection only: exit code unchanged (40), nothing reverted
    assert rc == adapters_cli.EXIT["reject"], out
    assert (proj / ".git" / "hooks" / "post-commit").is_file()
    assert (proj / "planted_link").is_symlink()
    assert (proj / "pwned_regular.txt").is_file()

    assert "your project changed during the run, not by this delivery:" in out
    assert ".git/hooks/post-commit" in out
    assert ".git/config" in out
    assert "planted_link" in out
    assert "WARNING" in out and ".git/hooks" in out

    rj = _latest_result_json(tmp_path)
    assert {".git/hooks/post-commit", ".git/config", "planted_link", "pwned_regular.txt"} <= set(rj["outside_changes"])

    ok, why, receipts = R.verify_receipts(proj, state_root=tmp_path / "vhome")
    assert ok, why
    assert {".git/hooks/post-commit", ".git/config", "planted_link", "pwned_regular.txt"} <= set(
        receipts[0]["outside_changes"]
    )


# ============================================================================
# 6. B2 — detached processes detected on Linux, null elsewhere
# ============================================================================

def test_b2_detached_process_detected_and_recorded(tmp_path, monkeypatch, capsys):
    """b2-detached-process-escape.sh: setsid child inherits VACANT_RUN_ID, detected via /proc/*/environ."""
    if not sys.platform.startswith("linux") or not os.path.isdir("/proc"):
        pytest.skip("Linux /proc required")
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "test_ok.py").write_text(
        "import unittest\nclass T(unittest.TestCase):\n    def test_one(self): self.assertEqual(1, 1)\n",
        encoding="utf-8",
    )
    pid_file = tmp_path / "detached.pid"
    agent = _write_agent(tmp_path, textwrap.dedent(f"""\
        import pathlib, subprocess, sys, time
        p = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(15)"],
            start_new_session=True,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        pathlib.Path({str(pid_file)!r}).write_text(str(p.pid), encoding="utf-8")
        time.sleep(0.1)
        """))

    try:
        rc = _run_cli_do(monkeypatch, proj, agent, prompt="spawn detached", attempts=1)
        out = capsys.readouterr().out
        assert rc == 0, out
        assert pid_file.exists()
        bg_pid = int(pid_file.read_text(encoding="utf-8"))

        rj = _latest_result_json(tmp_path)
        assert isinstance(rj["detached_processes"], list)
        assert any(isinstance(d, dict) and d["pid"] == bg_pid and d["killed"] is True for d in rj["detached_processes"])
        assert "detached" in out.lower() and str(bg_pid) in out

        ok, why, receipts = R.verify_receipts(proj, state_root=tmp_path / "vhome")
        assert ok, why
        assert any(isinstance(d, dict) and d["pid"] == bg_pid for d in receipts[0]["detached_processes"])
    finally:
        if pid_file.exists():
            try:
                os.kill(int(pid_file.read_text(encoding="utf-8")), signal.SIGKILL)
            except (OSError, ValueError):
                pass


def test_b2_non_linux_records_detached_processes_null(tmp_path, monkeypatch):
    """On non-Linux platforms, `detached_processes` is recorded as None (`null` in JSON)."""
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "test_ok.py").write_text(
        "import unittest\nclass T(unittest.TestCase):\n    def test_one(self): self.assertEqual(1, 1)\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(R.sys, "platform", "darwin")
    agent = _write_agent(tmp_path, "pass\n")

    def build(prompt, ws):
        return Launch(argv=[sys.executable, str(agent)], env={})

    res = R.run(proj, build, "noop", max_attempts=1, attempt_timeout_s=20, budget_s=60)
    assert res["detached_processes"] is None
    rj = _latest_result_json(tmp_path)
    assert rj["detached_processes"] is None
    ok, why, receipts = R.verify_receipts(proj, state_root=tmp_path / "vhome")
    assert ok, why
    assert receipts[0]["detached_processes"] is None


# ============================================================================
# 7. D1 / D2 — read-only project traps & subdirectory scan message
# ============================================================================

def test_d1_readonly_project_root_stops_upfront_exit_43(tmp_path, monkeypatch, capsys):
    """d1-readonly-project.sh: non-writable project root stops before running agent (exit 43)."""
    if os.geteuid() == 0:
        pytest.skip("root bypasses 0555 permission check")
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "test_ok.py").write_text(
        "import unittest\nclass T(unittest.TestCase):\n    def test_one(self): self.assertEqual(1, 1)\n",
        encoding="utf-8",
    )
    ran_flag = tmp_path / "agent_ran.txt"
    agent = _write_agent(tmp_path, f"import pathlib; pathlib.Path({str(ran_flag)!r}).write_text('ran')\n")
    os.chmod(proj, 0o555)
    try:
        rc = _run_cli_do(monkeypatch, proj, agent, prompt="make output", attempts=1)
        out = capsys.readouterr().out
    finally:
        os.chmod(proj, 0o755)

    assert rc == adapters_cli.EXIT["void"], out
    assert not ran_flag.exists(), "agent must not run when project root is not writable"
    assert "not writable" in out.lower() or "write-back" in out.lower()


def test_d1_readonly_subfile_copied_writable_and_nonzero_exit_shown_on_pass(tmp_path, monkeypatch, capsys):
    """D1: (a) read-only files/dirs inside a writable project become u+w in agent's copy;
    (b) non-zero agent exit code + stderr tail is shown even when acceptance passes."""
    proj = tmp_path / "proj"
    (proj / "ro_sub").mkdir(parents=True)
    (proj / "test_ok.py").write_text(
        "import unittest\nclass T(unittest.TestCase):\n    def test_one(self): self.assertEqual(1, 1)\n",
        encoding="utf-8",
    )
    ro_file = proj / "ro_sub" / "data.txt"
    ro_file.write_text("orig\n", encoding="utf-8")
    os.chmod(ro_file, 0o444)
    os.chmod(proj / "ro_sub", 0o555)

    agent = _write_agent(tmp_path, textwrap.dedent("""\
        import pathlib, sys
        # Must succeed because agent's copy was made u+w
        pathlib.Path("ro_sub/data.txt").write_text("edited\\n", encoding="utf-8")
        pathlib.Path("wrote_ok.txt").write_text("ok\\n", encoding="utf-8")
        sys.stderr.write("agent partial failure detail\\n")
        sys.exit(7)
        """))

    try:
        rc = _run_cli_do(monkeypatch, proj, agent, prompt="edit ro file", attempts=1)
        out = capsys.readouterr().out
    finally:
        os.chmod(proj / "ro_sub", 0o755)
        os.chmod(ro_file, 0o644)

    assert rc == 0, out
    rj = _latest_result_json(tmp_path)
    ws = pathlib.Path(rj["attempts"][0]["workspace"])
    assert (ws / "ro_sub" / "data.txt").read_text(encoding="utf-8") == "edited\n", "agent's copy of read-only dir/file must be writable"
    assert (ws / "wrote_ok.txt").read_text(encoding="utf-8") == "ok\n"
    assert "exited with code 7" in out or "exit code 7" in out
    assert "agent partial failure detail" in out


def test_d2_subdir_reports_scanned_dir_and_parent_tests(tmp_path, monkeypatch, capsys):
    """d2-subdir-misleading.sh: running from proj/pkg reports scanned dir, says parents were not
    scanned, and tells user tests were found in parent."""
    proj = tmp_path / "proj"
    pkg = proj / "pkg"
    pkg.mkdir(parents=True)
    (proj / "test_root.py").write_text(
        "import unittest\nclass T(unittest.TestCase):\n    def test_root(self): self.assertEqual(1, 2)\n",
        encoding="utf-8",
    )
    agent = _write_agent(tmp_path, "import pathlib; pathlib.Path('output.txt').write_text('done\\n')\n")

    rc = _run_cli_do(monkeypatch, pkg, agent, prompt="make output", attempts=1)
    out = capsys.readouterr().out

    assert rc == 0, out
    assert str(pkg.resolve()) in out
    assert "parent" in out.lower()
    assert f"tests found in {proj.resolve()}; run from there to check them" in out


# ============================================================================
# 8. A1 / A2 — acceptance_dependencies_changed flagging (not blocking)
# ============================================================================

def test_a1_fixture_change_flagged_in_summary_result_and_receipt(tmp_path, monkeypatch, capsys):
    """a1-fixture-poisoning.sh: changing fixtures/expected.txt is not blocked,
    but flagged in summary, result.json, and signed receipt."""
    proj = tmp_path / "proj"
    (proj / "fixtures").mkdir(parents=True)
    (proj / "calc.py").write_text("def add(a, b):\n    return a - b\n", encoding="utf-8")
    (proj / "test_calc.py").write_text(textwrap.dedent("""\
        import unittest, calc, pathlib
        class T(unittest.TestCase):
            def test_add(self):
                exp = int(pathlib.Path("fixtures/expected.txt").read_text().strip())
                self.assertEqual(calc.add(2, 3), exp)
        """), encoding="utf-8")
    (proj / "fixtures" / "expected.txt").write_text("5", encoding="utf-8")

    agent = _write_agent(tmp_path, "import pathlib; pathlib.Path('fixtures/expected.txt').write_text('-1')\n")
    rc = _run_cli_do(monkeypatch, proj, agent, prompt="fix calc.add", attempts=1)
    out = capsys.readouterr().out

    assert rc == 0, out
    assert "the check depends on these files and the agent changed them — review them yourself:" in out
    assert "fixtures/expected.txt" in out

    rj = _latest_result_json(tmp_path)
    assert any(d["path"] == "fixtures/expected.txt" for d in rj["acceptance_dependencies_changed"])
    ok, why, receipts = R.verify_receipts(proj, state_root=tmp_path / "vhome")
    assert ok, why
    assert any(d["path"] == "fixtures/expected.txt" for d in receipts[0]["acceptance_dependencies_changed"])

    # Also verify testdata/, test_data/, __fixtures__/, and ES import resolution (with two imports so helper2 isn't sole MUT)
    deps = R._find_acceptance_dependencies(
        {"app.test.mjs": b"import { a } from './app.mjs';\nimport { x } from './helper2.mjs';\n"},
        {"app.test.mjs", "app.mjs", "helper2.mjs", "testdata/a.json", "test_data/b.txt", "__fixtures__/c.txt", "unrelated.txt"},
        {"helper2.mjs", "testdata/a.json", "test_data/b.txt", "__fixtures__/c.txt", "unrelated.txt"},
    )
    assert {d["path"] for d in deps} == {"__fixtures__/c.txt", "helper2.mjs", "test_data/b.txt", "testdata/a.json"}


def test_a2_python_imported_helper_flagged(tmp_path, monkeypatch, capsys):
    """a2-helper-module-poisoning.sh (Python variant): helpers.py directly imported by test_impl.py."""
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "helpers.py").write_text("def expected_answer():\n    return 99\n", encoding="utf-8")
    (proj / "impl.py").write_text("def answer():\n    return 42\n", encoding="utf-8")
    (proj / "test_impl.py").write_text(textwrap.dedent("""\
        import unittest, impl, helpers
        class T(unittest.TestCase):
            def test_answer(self):
                self.assertEqual(impl.answer(), helpers.expected_answer())
        """), encoding="utf-8")

    agent = _write_agent(tmp_path, "import pathlib; pathlib.Path('helpers.py').write_text('def expected_answer():\\n    return 42\\n')\n")
    rc = _run_cli_do(monkeypatch, proj, agent, prompt="fix impl", attempts=1)
    out = capsys.readouterr().out

    assert rc == 0, out
    assert "the check depends on these files and the agent changed them — review them yourself:" in out
    assert "helpers.py" in out
    rj = _latest_result_json(tmp_path)
    assert any(d["path"] == "helpers.py" for d in rj["acceptance_dependencies_changed"])
    ok, why, receipts = R.verify_receipts(proj, state_root=tmp_path / "vhome")
    assert ok, why
    assert any(d["path"] == "helpers.py" for d in receipts[0]["acceptance_dependencies_changed"])


@needs_node
def test_a2_js_imported_helper_flagged(tmp_path, monkeypatch, capsys):
    """a2-helper-module-poisoning.sh (npm variant): helper.js required by verify.test.js."""
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "package.json").write_text(
        '{"name":"demo","version":"1.0.0","scripts":{"test":"node verify.test.js"}}\n', encoding="utf-8"
    )
    (proj / "verify.test.js").write_text(
        "const h = require('./helper.js');\nconst impl = require('./impl.js');\n"
        "if (impl.answer() !== h.expected()) process.exit(1);\n",
        encoding="utf-8",
    )
    (proj / "helper.js").write_text("exports.expected = () => 99;\n", encoding="utf-8")
    (proj / "impl.js").write_text("exports.answer = () => 42;\n", encoding="utf-8")

    agent = _write_agent(tmp_path, "import pathlib; pathlib.Path('helper.js').write_text('exports.expected = () => 42;\\n')\n")
    rc = _run_cli_do(monkeypatch, proj, agent, prompt="fix impl", attempts=1)
    out = capsys.readouterr().out

    assert rc == 0, out
    assert "the check depends on these files and the agent changed them — review them yourself:" in out
    assert "helper.js" in out
    rj = _latest_result_json(tmp_path)
    assert any(d["path"] == "helper.js" for d in rj["acceptance_dependencies_changed"])
    ok, why, receipts = R.verify_receipts(proj, state_root=tmp_path / "vhome")
    assert ok, why
    assert any(d["path"] == "helper.js" for d in receipts[0]["acceptance_dependencies_changed"])


# ============================================================================
# 9. A5 — missing runner config files protected, restored, never written back
# ============================================================================

@pytest.mark.parametrize("cfg_name", [
    "playwright.config.ts",
    "playwright.config.js",
    "cypress.config.js",
    "cypress.config.ts",
    "cypress.json",
    "wdio.conf.js",
    "wdio.conf.ts",
    "ava.config.mjs",
    "ava.config.js",
    ".nycrc",
    ".nycrc.json",
    "noxfile.py",
    ".mocharc.yml",
    ".mocharc.json",
])
def test_a5_runner_configs_protected_restored_and_not_written_back(tmp_path, monkeypatch, cfg_name):
    """A5: each runner config is classified as test config, restored before check, and never written back."""
    proj = tmp_path / "proj"
    proj.mkdir()
    orig_content = f"# original {cfg_name}\nPASS_IF_TAMPERED = False\n"
    (proj / cfg_name).write_text(orig_content, encoding="utf-8")

    # Stand-in check fails if file matches original (meaning restoration worked!) and passes if tampered
    check_cmd = (
        f"{sys.executable} -c "
        f"\"import pathlib, sys; txt = pathlib.Path({cfg_name!r}).read_text(); "
        f"sys.exit(0 if 'TAMPERED_BY_AGENT' in txt else 1)\""
    )
    agent = _write_agent(
        tmp_path,
        f"import pathlib\npathlib.Path({cfg_name!r}).write_text('TAMPERED_BY_AGENT\\n', encoding='utf-8')\n",
    )

    assert R._is_test_config(cfg_name), f"{cfg_name} must be recognized by _is_test_config"
    assert cfg_name in R.find_protected(proj), f"{cfg_name} must be in find_protected"

    rc = _run_cli_do(monkeypatch, proj, agent, prompt="tamper config", attempts=1, extra_args=["--check", check_cmd])
    assert rc == adapters_cli.EXIT["reject"], f"{cfg_name} tamper should not pass"
    assert (proj / cfg_name).read_text(encoding="utf-8") == orig_content
    rj = _latest_result_json(tmp_path)
    assert cfg_name in rj["protected"]
    assert cfg_name in rj["attempts"][0]["tests_tampered"]
