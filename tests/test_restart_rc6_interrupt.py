"""rc6(1): Ctrl-C / SIGINT / SIGTERM handling in `vacant do` restart mode.

Verifies:
1. Sending SIGINT to the single `vacant` process.
2. Sending SIGINT to the entire foreground process group (`os.setpgrp` + `os.killpg`,
   simulating real terminal Ctrl-C).
3. Sending SIGTERM to the `vacant` process.

In every case:
- exit code is 130
- no Python traceback in stdout or stderr
- output clearly states interrupted, project unchanged, and working directory path (safe to delete)
- project tree is byte-for-byte identical before and after
- signed receipt exists, verifies cleanly, and is marked interrupted
- `vacant audit list` / `show` reports the verified interrupted record
- no leftover agent, child, or detached `setsid` descendant processes remain alive
"""
from __future__ import annotations

import hashlib
import json
import os
import pathlib
import signal
import subprocess
import sys
import textwrap
import time

import pytest

from vacant_network import audit_export as AE
from vacant_network.adapters import restart as R

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]


def _tree_digest(root: pathlib.Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for p in sorted(root.rglob("*")):
        rel = p.relative_to(root).as_posix()
        if p.is_symlink():
            out[rel] = "link:" + os.readlink(p)
        elif p.is_file():
            out[rel] = hashlib.sha256(p.read_bytes()).hexdigest()
        elif p.is_dir():
            out[rel] = "dir"
    return out


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    # Check zombie state on Linux /proc
    stat_p = pathlib.Path(f"/proc/{pid}/stat")
    if stat_p.exists():
        try:
            txt = stat_p.read_text(encoding="utf-8", errors="replace")
            rp = txt.rfind(")")
            if rp != -1:
                state = txt[rp + 2:].split()[0]
                if state == "Z":
                    return False
        except OSError:
            return False
    return True


def _make_project(proj: pathlib.Path) -> None:
    proj.mkdir(parents=True, exist_ok=True)
    (proj / "calc.py").write_text("def add(a, b):\n    return a - b\n", encoding="utf-8")
    (proj / "test_calc.py").write_text(
        textwrap.dedent("""\
            import unittest, calc
            class T(unittest.TestCase):
                def test_add(self):
                    self.assertEqual(calc.add(2, 3), 5)
        """),
        encoding="utf-8",
    )


def _write_sleeper_agent(tmp_path: pathlib.Path, pid_file: pathlib.Path) -> pathlib.Path:
    """Fake agent that modifies its workspace copy, spawns a normal child and a detached
    `setsid` grandchild, records all 3 PIDs to `pid_file`, and waits to be interrupted."""
    agent = tmp_path / "slow_agent.py"
    agent.write_text(
        textwrap.dedent(f"""\
            import json, os, pathlib, subprocess, sys, time

            # Write into the isolated workspace copy (must NOT affect real project on interrupt)
            pathlib.Path("calc.py").write_text("def add(a, b):\\n    return a + b\\n", encoding="utf-8")
            pathlib.Path("partial.txt").write_text("half-baked\\n", encoding="utf-8")

            child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
            detached = subprocess.Popen(
                [sys.executable, "-c", "import time; time.sleep(60)"],
                start_new_session=True,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            pids = {{"agent": os.getpid(), "child": child.pid, "detached": detached.pid}}
            tmp = pathlib.Path({str(pid_file) + ".tmp"!r})
            tmp.write_text(json.dumps(pids), encoding="utf-8")
            os.replace(tmp, {str(pid_file)!r})
            time.sleep(60)
        """),
        encoding="utf-8",
    )
    return agent


def _run_and_interrupt(
    tmp_path: pathlib.Path,
    *,
    mode: str,
) -> None:
    proj = tmp_path / "proj"
    _make_project(proj)
    before_tree = _tree_digest(proj)

    vh = tmp_path / "vhome"
    vw = tmp_path / "vwork"
    pid_file = tmp_path / "pids.json"
    agent = _write_sleeper_agent(tmp_path, pid_file)

    env = {k: v for k, v in os.environ.items() if k != "VIRTUAL_ENV"}
    env.update(
        PYTHONPATH=str(REPO_ROOT),
        VACANT_HOME=str(vh),
        VACANT_WORK=str(vw),
        VACANT_HOOK_NO_GC="1",
    )
    cmd = [
        sys.executable, "-m", "vacant_network.cli", "do",
        "--cmd", f"{sys.executable} {agent} {{prompt}}",
        "--prompt", "fix calc",
        "--attempt-timeout", "60",
        "--timeout", "120",
    ]
    popen_kw: dict = {
        "cwd": str(proj),
        "env": env,
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.PIPE,
        "stderr": subprocess.PIPE,
        "text": True,
    }
    if mode == "killpg_sigint":
        popen_kw["preexec_fn"] = os.setpgrp

    proc = subprocess.Popen(cmd, **popen_kw)
    pids: dict[str, int] = {}
    try:
        deadline = time.monotonic() + 20.0
        while time.monotonic() < deadline:
            if pid_file.exists():
                pids = json.loads(pid_file.read_text(encoding="utf-8"))
                break
            if proc.poll() is not None:
                out, err = proc.communicate(timeout=5)
                pytest.fail(f"vacant exited before agent started: rc={proc.returncode}\nout={out}\nerr={err}")
            time.sleep(0.05)
        assert pids, "timed out waiting for fake agent to start"

        if mode == "single_sigint":
            os.kill(proc.pid, signal.SIGINT)
        elif mode == "killpg_sigint":
            os.killpg(proc.pid, signal.SIGINT)
        elif mode == "sigterm":
            os.kill(proc.pid, signal.SIGTERM)
        else:
            raise ValueError(mode)

        stdout, stderr = proc.communicate(timeout=20)
    finally:
        # Ensure nothing leaks if an assertion fails mid-test
        for p in pids.values():
            try:
                os.kill(p, signal.SIGKILL)
            except OSError:
                pass
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=5)

    combined = stdout + stderr
    assert proc.returncode == 130, f"expected 130, got {proc.returncode}\nstdout:\n{stdout}\nstderr:\n{stderr}"
    assert "Traceback" not in combined, f"unexpected traceback:\n{combined}"
    assert "KeyboardInterrupt" not in combined, f"unexpected KeyboardInterrupt:\n{combined}"
    assert "interrupted" in stdout.lower(), f"missing interrupted notice:\n{stdout}"
    assert "project unchanged" in stdout.lower(), f"missing project unchanged notice:\n{stdout}"
    assert "safe to delete" in stdout.lower(), f"missing delete hint:\n{stdout}"

    # Working directory exists and is mentioned in stdout
    run_dirs = sorted(vw.glob("restart-*"))
    assert len(run_dirs) == 1, f"expected 1 run_dir, got {run_dirs}"
    run_dir = run_dirs[0]
    assert str(run_dir) in stdout, f"run_dir {run_dir} not in stdout:\n{stdout}"

    # Project directory is byte-for-byte unchanged
    after_tree = _tree_digest(proj)
    assert after_tree == before_tree, f"project modified on interrupt: before={before_tree} after={after_tree}"

    # result.json marked interrupted
    rj = json.loads((run_dir / "result.json").read_text(encoding="utf-8"))
    assert rj.get("interrupted") is True
    assert rj.get("accepted") is None
    assert rj.get("delivered_attempt") == 0
    expected_sig = "SIGTERM" if mode == "sigterm" else "SIGINT"
    assert rj.get("interrupt_signal") == expected_sig
    assert rj.get("receipt", {}).get("recorded") is True

    # Signed receipt exists, verifies offline, and is marked interrupted
    ok, msg, receipts = R.verify_receipts(proj, state_root=vh)
    assert ok, f"receipt verification failed: {msg}"
    assert len(receipts) == 1
    assert receipts[0].get("interrupted") is True
    assert receipts[0].get("interrupt_signal") == expected_sig
    assert receipts[0].get("run_id") == run_dir.name
    assert receipts[0].get("accepted") is None

    # `vacant audit` sees the verified interrupted record
    recs = AE.collect_all(vacant_home=vh, work_root=vw)
    restart_recs = [r for r in recs if r["kind"] == "restart"]
    assert len(restart_recs) == 1
    assert restart_recs[0]["acceptance"]["result"] == "interrupted"
    assert restart_recs[0]["signature"]["verified"] is True
    assert restart_recs[0]["details"].get("interrupted") is True
    show_txt = AE.format_show(restart_recs[0])
    assert "result=interrupted" in show_txt

    # No leftover processes (agent, normal child, detached setsid grandchild)
    deadline = time.monotonic() + 3.0
    while time.monotonic() < deadline:
        alive = {k: p for k, p in pids.items() if _pid_alive(p)}
        if not alive:
            break
        time.sleep(0.05)
    alive = {k: p for k, p in pids.items() if _pid_alive(p)}
    assert not alive, f"leftover processes still alive after interrupt: {alive}"


def test_rc6_interrupt_single_process_sigint(tmp_path):
    """SIGINT sent directly to the single vacant process."""
    _run_and_interrupt(tmp_path, mode="single_sigint")


def test_rc6_interrupt_foreground_pgrp_sigint(tmp_path):
    """SIGINT sent to the entire foreground process group (os.setpgrp + os.killpg, real Ctrl-C)."""
    _run_and_interrupt(tmp_path, mode="killpg_sigint")


def test_rc6_interrupt_sigterm(tmp_path):
    """SIGTERM sent to the vacant process."""
    _run_and_interrupt(tmp_path, mode="sigterm")


def test_sigint_during_write_back_is_deferred_and_project_not_half_written(tmp_path, monkeypatch):
    """寫回途中收到 Ctrl-C：不能走「專案沒有被改動」的中斷路徑（那時專案已經寫了一部分）。
    rc6 把寫回到 result.json 這段當臨界區：訊號延後，寫回完整做完，照常交件，訊息說明收到過中斷。"""
    proj = tmp_path / "proj"
    _make_project(proj)
    (proj / "extra.py").write_text("X = 1\n", encoding="utf-8")
    agent = tmp_path / "agent.py"
    agent.write_text(textwrap.dedent("""\
        import pathlib
        pathlib.Path('calc.py').write_text('def add(a, b):\\n    return a + b\\n')
        pathlib.Path('extra.py').write_text('X = 2\\n')
        pathlib.Path('new_mod.py').write_text('Y = 3\\n')
    """), encoding="utf-8")
    real_write_back = R._write_back
    calls = []

    def _write_back_with_sigint(*a, **kw):
        calls.append(1)
        os.kill(os.getpid(), signal.SIGINT)  # 模擬寫回途中按 Ctrl-C：handler 在下一個 bytecode 邊界就會被叫到
        time.sleep(0.05)
        return real_write_back(*a, **kw)

    monkeypatch.setattr(R, "_write_back", _write_back_with_sigint)
    res = R.run(proj, lambda p, ws: R.Launch(argv=[sys.executable, str(agent)], env={}), "fix",
                max_attempts=1, attempt_timeout_s=30, budget_s=60)
    assert calls, "write-back was not reached"
    assert not res.get("interrupted")
    assert res.get("interrupt_deferred") == "SIGINT"
    assert res["accepted"] is True
    # 寫回是完整的：三個改動都在，沒有寫一半
    assert (proj / "calc.py").read_text() == "def add(a, b):\n    return a + b\n"
    assert (proj / "extra.py").read_text() == "X = 2\n"
    assert (proj / "new_mod.py").read_text() == "Y = 3\n"
    msg = R.summary(res)
    assert "project unchanged" not in msg
    assert "SIGINT arrived while Vacant was writing" in msg
    assert res["receipt"].get("recorded") is True


def test_second_sigint_and_sigterm_during_write_back_still_wait(tmp_path, monkeypatch):
    """臨界區裡第二次 SIGINT、再加一次 SIGTERM：仍然等寫回完成，記第一個訊號。"""
    proj = tmp_path / "proj"
    _make_project(proj)
    agent = tmp_path / "agent.py"
    agent.write_text("import pathlib\npathlib.Path('calc.py').write_text('def add(a, b):\\n    return a + b\\n')\n",
                     encoding="utf-8")
    real_write_back = R._write_back

    def _write_back_with_signals(*a, **kw):
        for sig in (signal.SIGINT, signal.SIGINT, signal.SIGTERM):
            os.kill(os.getpid(), sig)
            time.sleep(0.02)
        return real_write_back(*a, **kw)

    monkeypatch.setattr(R, "_write_back", _write_back_with_signals)
    res = R.run(proj, lambda p, ws: R.Launch(argv=[sys.executable, str(agent)], env={}), "fix",
                max_attempts=1, attempt_timeout_s=30, budget_s=60)
    assert not res.get("interrupted")
    assert res.get("interrupt_deferred") == "SIGINT"
    assert res["accepted"] is True
    assert (proj / "calc.py").read_text() == "def add(a, b):\n    return a + b\n"
