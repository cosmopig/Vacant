"""零設定重開模式（`vacant do` / `restart.py`）容量與回收治理測試（W5c，0 次模型呼叫）。

涵蓋：
1. `compact_work` 處理 `restart-<...>/attempt_k/{w,snap-*}`：剝離舊 run 的工作區副本與快照，
   保留 `result.json`、`attempt_k/logs/`、交付後的專案檔案與簽章收據；`dry_run=True` 零刪除。
2. 命名上限 `DEFAULT_RESTART_WORK_CAP_BYTES`（16 MiB，可由 `VACANT_RESTART_WORK_CAP_BYTES` 覆寫）：
   超標時連近期保留 run 的 `w`/`snap-*` 也依最舊優先剝離，並在 `vacant usage`（JSON 與人讀）顯示。
3. GC（含 `--aggressive --verify`）之後重驗專案簽章收據仍 100% 通過。
4. `vacant do` 結束時觸發既有 auto-gc（並遵守 `VACANT_HOOK_NO_GC=1`）。
5. 實測 `COPY_SKIP` 對 `.git`、`node_modules`、`.venv` 與 `target/` 的行為（未靜默修改 `COPY_SKIP`）。
"""
from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys
import textwrap
import time

import pytest

from vacant_network import cli as top_cli
from vacant_network import retention
from vacant_network.adapters import cli as adapters_cli
from vacant_network.adapters import restart as R
from vacant_network.adapters.run import COPY_SKIP, Launch
from vacant_network.trace import cli as trace_cli

TEST = textwrap.dedent("""\
    import unittest
    from sol import f
    class T(unittest.TestCase):
        def test_one(self):
            self.assertEqual(f(1), 2)
    """)
GOOD = "def f(x):\n    return x + 1\n"
BAD = "def f(x):\n    return x\n"

AGENT = textwrap.dedent("""\
    import json, os, pathlib, sys
    st = pathlib.Path(os.environ["STUB_STATE"])
    n = json.loads(st.read_text())["n"] + 1 if st.exists() else 1
    st.write_text(json.dumps({"n": n}))
    plan = os.environ["STUB_PLAN"].split(",")
    what = plan[min(n, len(plan)) - 1]
    print(f"attempt {n}: {what}")
    print(f"stderr line {n}", file=sys.stderr)
    pathlib.Path("sol.py").write_text(%r if what == "good" else %r)
    """) % (GOOD, BAD)


@pytest.fixture()
def env_proj(tmp_path, monkeypatch):
    vh = tmp_path / "vacant_home"
    vw = tmp_path / "vacant_work"
    monkeypatch.setenv("VACANT_HOME", str(vh))
    monkeypatch.setenv("VACANT_WORK", str(vw))
    monkeypatch.setenv("VACANT_HOOK_NO_GC", "1")
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "sol_test.py").write_text(TEST, encoding="utf-8")
    (proj / "sol.py").write_text("def f(x):\n    return 0\n", encoding="utf-8")
    (proj / "data.txt").write_text("payload line\n" * 400, encoding="utf-8")
    return proj, vh, vw


def _build(tmp_path: pathlib.Path, plan: str, idx: int = 0):
    script = tmp_path / f"stub_agent_{idx}.py"
    script.write_text(AGENT, encoding="utf-8")
    state = tmp_path / f"stub_state_{idx}.json"
    env = {"STUB_STATE": str(state), "STUB_PLAN": plan}

    def build(prompt: str, ws: pathlib.Path) -> Launch:
        return Launch(argv=[sys.executable, str(script), prompt], env=dict(env))

    return build


def test_compact_work_strips_old_restart_runs_keeps_logs_results_project_and_receipts(env_proj, tmp_path):
    proj, vh, vw = env_proj
    run_dirs: list[pathlib.Path] = []
    for i in range(5):
        res = R.run(proj, _build(tmp_path, "bad,good", idx=i), f"task {i}",
                    attempt_timeout_s=20, budget_s=120, agent="stub")
        assert res["accepted"] is True
        rd = pathlib.Path(res["run_dir"])
        # 明確拉開 mtime，確保舊→新排序確定
        t = time.time() - (5 - i) * 60
        os.utime(rd, (t, t))
        run_dirs.append(rd)

    # GC 前 5 次 run 的工作區與快照都在
    for rd in run_dirs:
        assert (rd / "attempt_1" / "w").is_dir()
        assert list((rd / "attempt_1").glob("snap-*"))
        assert (rd / "result.json").is_file()

    # dry-run 不得刪除任何檔案
    dry = retention.compact_work(vw, keep_runs_per_task=2, dry_run=True)
    assert dry["restart_runs_scanned"] == 5
    assert dry["restart_bytes_freed"] > 0
    assert (run_dirs[0] / "attempt_1" / "w").is_dir()

    # 實際執行：保留最新 2 次，舊的 3 次剝離 w 與 snap-*
    rep = retention.compact_work(vw, keep_runs_per_task=2, dry_run=False)
    assert rep["restart_runs_scanned"] == 5
    assert rep["restart_bytes_freed"] == dry["restart_bytes_freed"]
    assert rep["bytes_freed"] > 0

    for old_rd in run_dirs[:3]:
        assert (old_rd / "result.json").is_file()
        for k in (1, 2):
            att = old_rd / f"attempt_{k}"
            assert not (att / "w").exists(), f"old workspace should be stripped: {att / 'w'}"
            assert list(att.glob("snap-*")) == [], f"old snapshots should be stripped in {att}"
            assert (att / "logs" / "agent_stdout.log").is_file()
            assert (att / "logs" / "agent_stderr.log").is_file()
            assert f"attempt {k}:" in (att / "logs" / "agent_stdout.log").read_text(encoding="utf-8")

    for kept_rd in run_dirs[3:]:
        assert (kept_rd / "attempt_1" / "w").is_dir()
        assert list((kept_rd / "attempt_1").glob("snap-*"))
        assert (kept_rd / "result.json").is_file()

    # 交付後的專案檔案與全部 5 筆簽章收據完整無損
    assert (proj / "sol.py").read_text(encoding="utf-8") == GOOD
    assert (proj / "sol_test.py").read_text(encoding="utf-8") == TEST
    ok, why, receipts = R.verify_receipts(proj, state_root=vh)
    assert ok, why
    assert len(receipts) == 5


def test_restart_work_named_cap_enforced_and_reported_in_usage(env_proj, tmp_path, monkeypatch, capsys):
    proj, vh, vw = env_proj
    (proj / "big.txt").write_text("0123456789abcdef\n" * 2000, encoding="utf-8")  # ~34 KB

    # 設極小上限（20 KiB），讓 2 次近期 run 合計（~270 KB）必然超限
    small_cap = 20 * 1024
    monkeypatch.setenv("VACANT_RESTART_WORK_CAP_BYTES", str(small_cap))

    for i in range(2):
        res = R.run(proj, _build(tmp_path, "bad,good", idx=10 + i), f"cap task {i}",
                    attempt_timeout_s=20, budget_s=120, agent="stub")
        assert res["accepted"] is True

    # GC 前 usage 報告必須點名 restart_work 超上限
    u_before = retention.usage_report(vh, vw)
    assert u_before["areas"]["restart_work"] > small_cap
    assert u_before["budget"]["restart_work"]["cap_bytes"] == small_cap
    assert u_before["budget"]["restart_work"]["within_budget"] is False
    assert u_before["envelope"]["within_envelope"] is False
    g_map = {g["name"]: g for g in u_before["envelope"]["groups"]}
    assert g_map["restart_work"]["bytes"] == u_before["areas"]["restart_work"]
    assert g_map["restart_work"]["cap_bytes"] == small_cap

    rc_u = top_cli.main(["usage"])
    assert rc_u == 0
    out_u = capsys.readouterr().out
    assert "restart_work" in out_u
    assert "超上限" in out_u

    # 執行 gc_all(verify=True)：超命名上限時連近期 run 的 w/snap-* 也要剝離以壓回上限內
    grep = retention.gc_all(root=vh, work_root=vw, verify=True)
    assert grep["verify_ok"] is True
    assert grep["work"]["restart_bytes_remaining"] <= small_cap

    # GC 後 usage 報告回到上限與封頂內
    u_after = retention.usage_report(vh, vw)
    assert u_after["areas"]["restart_work"] <= small_cap
    assert u_after["budget"]["restart_work"]["within_budget"] is True
    assert u_after["envelope"]["within_envelope"] is True

    # result.json、logs、專案檔與簽章收據全部完好
    for rd in vw.glob("restart-*"):
        assert (rd / "result.json").is_file()
        assert (rd / "attempt_1" / "logs" / "agent_stdout.log").is_file()
    assert (proj / "sol.py").read_text(encoding="utf-8") == GOOD
    ok, why, receipts = R.verify_receipts(proj, state_root=vh)
    assert ok, why
    assert len(receipts) == 2


def test_aggressive_gc_and_auto_gc_preserve_receipts_and_pass_reverify(env_proj, tmp_path, monkeypatch, capsys):
    proj, vh, vw = env_proj
    res = R.run(proj, _build(tmp_path, "bad,good", idx=20), "aggressive test",
                attempt_timeout_s=20, budget_s=120, agent="stub")
    assert res["accepted"] is True
    rd = pathlib.Path(res["run_dir"])

    rc = top_cli.main(["gc", "--aggressive", "--verify", "--json"])
    assert rc == 0
    rep = json.loads(capsys.readouterr().out)
    assert rep["verify_ok"] is True
    assert rep["verified_projects"] >= 1
    assert rep["work"]["restart_bytes_freed"] > 0

    # 工作區與快照已清，result.json、logs、交付專案與收據鏈均完好
    assert not (rd / "attempt_1" / "w").exists()
    assert list((rd / "attempt_1").glob("snap-*")) == []
    assert (rd / "result.json").is_file()
    assert (rd / "attempt_1" / "logs" / "agent_stdout.log").is_file()
    assert (proj / "sol.py").read_text(encoding="utf-8") == GOOD

    ok, why, receipts = R.verify_receipts(proj, state_root=vh, expected_head=res["receipt"])
    assert ok, why
    assert len(receipts) == 1
    monkeypatch.chdir(proj)
    assert trace_cli.main(["trace", "verify"]) == 0
    assert capsys.readouterr().out.startswith("OK ")


def test_default_restart_cap_shown_in_usage_and_fits_in_256mib_envelope(env_proj, tmp_path, capsys):
    proj, vh, vw = env_proj
    R.run(proj, _build(tmp_path, "good", idx=30), "usage check",
          attempt_timeout_s=20, budget_s=120, agent="stub")

    rep = retention.usage_report(vh, vw)
    assert rep["budget"]["restart_work"]["cap_bytes"] == retention.DEFAULT_RESTART_WORK_CAP_BYTES == 16 * 1024 * 1024
    assert rep["budget"]["restart_work"]["runs"] == 1
    assert rep["budget"]["restart_work"]["within_budget"] is True

    # 穩態封頂不變量：state_dir 所有命名上限 + restart_work 命名上限 ≤ 256 MiB
    acct = rep["envelope"]["accounting"]
    assert acct["all_caps_sum"] + retention.DEFAULT_RESTART_WORK_CAP_BYTES <= retention.STABLE_ENVELOPE_BYTES

    rc = top_cli.main(["usage"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "restart_work" in out
    assert "16 MiB" in out
    assert "含 1 次 restart" in out


def test_vacant_do_triggers_auto_gc_and_respects_no_gc_env(env_proj, tmp_path, monkeypatch, capsys):
    proj, vh, vw = env_proj
    monkeypatch.delenv("VACANT_HOOK_NO_GC", raising=False)
    script = tmp_path / "do_gc_agent.py"
    script.write_text(AGENT, encoding="utf-8")
    monkeypatch.setenv("STUB_STATE", str(tmp_path / "do_gc_state.json"))
    monkeypatch.setenv("STUB_PLAN", "good")
    monkeypatch.chdir(proj)

    real_popen = subprocess.Popen
    gc_spawns: list[tuple[list[str], dict]] = []

    def spy_popen(cmd, *a, **kw):
        if isinstance(cmd, (list, tuple)) and "gc" in cmd and "--auto" in cmd:
            gc_spawns.append((list(cmd), dict(kw)))

            class _Dummy:
                pid = 99999

            return _Dummy()
        return real_popen(cmd, *a, **kw)

    monkeypatch.setattr(subprocess, "Popen", spy_popen)

    rc = adapters_cli.main([
        "do", "--cmd", f"{sys.executable} {script} {{prompt}}",
        "--prompt", "trigger auto gc", "--attempt-timeout", "20",
    ])
    assert rc == 0
    capsys.readouterr()
    assert len(gc_spawns) == 1
    gc_cmd, gc_kw = gc_spawns[0]
    assert "vacant_network" in gc_cmd and "gc" in gc_cmd and "--auto" in gc_cmd
    assert gc_kw.get("start_new_session") is True

    # VACANT_HOOK_NO_GC=1 時不觸發 auto-gc
    gc_spawns.clear()
    monkeypatch.setenv("VACANT_HOOK_NO_GC", "1")
    rc2 = adapters_cli.main([
        "do", "--cmd", f"{sys.executable} {script} {{prompt}}",
        "--prompt", "skip auto gc", "--attempt-timeout", "20",
    ])
    assert rc2 == 0
    capsys.readouterr()
    assert gc_spawns == []


def test_copy_skip_behavior_for_large_dirs(env_proj, tmp_path):
    """確認現行 COPY_SKIP 行為（不靜默改動）：.git/node_modules/.venv 跳過，target/ 會被複製。"""
    proj, _vh, _vw = env_proj
    for d in (".git", "node_modules", ".venv", "target"):
        (proj / d).mkdir()
        (proj / d / "blob.bin").write_bytes(b"X" * 8192)

    assert {".git", "node_modules", ".venv"} <= COPY_SKIP
    assert "target" not in COPY_SKIP

    res = R.run(proj, _build(tmp_path, "good", idx=40), "check copy_skip",
                attempt_timeout_s=20, budget_s=120, agent="stub")
    assert res["accepted"] is True
    att1 = pathlib.Path(res["run_dir"]) / "attempt_1"
    ws = att1 / "w"
    snap = next(att1.glob("snap-*"))

    for skipped in (".git", ".venv"):
        assert not (ws / skipped).exists()
        assert not (snap / skipped).exists()
    # node_modules（rc5）：agent 工作區拿到獨立副本（非指向原專案的 symlink），快照仍跳過、絕不寫回
    assert (ws / "node_modules").is_dir() and not (ws / "node_modules").is_symlink()
    assert not (snap / "node_modules").exists()
    # target/ 目前不在 COPY_SKIP：會進工作區也會進快照
    assert (ws / "target" / "blob.bin").is_file()
    assert (snap / "target" / "blob.bin").is_file()
