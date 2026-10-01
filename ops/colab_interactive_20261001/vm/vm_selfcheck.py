#!/usr/bin/env python3
"""vm_selfcheck — 在花 GPU 之前，用「機制替身模型」把互動式管線整條走一遍（VM 上跑，也能在任何有 tmux＋bwrap＋root 的機器上跑）。

    python3 vm_selfcheck.py --out /srv/eval/_selfcheck [--scenarios a,k,r,timeout,void,c] [--idle-s 4]
                            [--bridge-py /opt/eval/bridgevenv/bin/python] [--install-env 'HTTPS_PROXY=… PIP_CERT=…']

這支在架構裡承重什麼：真模型每段 session 要幾分鐘到半小時，管線有 bug（打字被吃掉、頁腳等不到、完成偵測太早／太晚、
bridge 在這台機器的 bwrap 起不來、K 的就地新 session 沒帶到回報、R 複本沒複製…）到那時才發現就是燒運算單位。
所以：合成的小題目（`solve_add`；沒有任何真題庫內容）＋ `smoke_stub.py`（按內容選回合的替身模型）＋真的 pi TUI／tmux／bwrap／
orproxy／bridge／計分器，走過每一條路：
  a       A 線：打字→完成偵測→Ctrl-D→計分（沒有巢狀）
  k       A＋K＋R：A 寫錯的解 → K judge 退回 → 同一工作區就地新 session（帶可見檢查的回報）→ accept → release → 計分被放行的成品；
          R＝A（有交件、沒逾時 ⇒ 不重試）
  r       A 什麼都沒寫 → R 在複本上用同一句重試並寫對；K 也走一遍
  timeout 撞牆鐘上限（rc 124）：不是 void；R 重試
  void    模型端一律 500 ⇒ session void（原因記下）
  driver  driver_i1001 整條：3 個單位（A［＋C］＋巢狀 R／K）、4 個位置、第一個對話被注入 500 ⇒ 該線 void 並以 v2 重跑一次；
          跑完再叫一次 driver ⇒ 一個單位都不重開（續跑）；DRIVER_DONE 與 `_run_` 紀錄格都在
  c       C 線：真的 `pipx install <wheel> && vacant install`，替身模型先「說做完卻沒寫」，Vacant 送回，第二輪寫對（要 wheel 與 pipx）
每個情境有自己的預期（寫在 EXPECT）；全部成立才 exit 0。`bridge` 在這台機器起不來時會**自動換上 bwrap 的 /proc 綁定墊片**
（Colab 不准掛新 /proc；第一批的 sandbox.sh 就是用 `--bind /proc /proc`），並把結果記進 selfcheck.json 的 `bridge_shim`，
發射紀錄會讀它。
誠實邊界：替身模型不會「解題」，所以這裡驗的是**管線與紀錄**，不是 agent 的表現；真 vLLM 下的延遲分布、真的 gemma 的行為
都沒有被這個檢查證明。
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import tui_cell  # noqa: E402
from tui_cell import Cfg, load_ledger, log  # noqa: E402
from tui_lib import INSTR_SENTENCE, SlotPool  # noqa: E402

RIGHT = "def solve_add(a, b):\n    return a + b\n"
WRONG = "def solve_add(a, b):\n    return a - b\n"
GOAL = "# Goal\n\nImplement `solve_add(a, b)` that returns the sum of two integers.\n"
CONTRACT = ("# Contract\n\nWrite your answer in `solution.py` at the root of this workspace.\n\n"
            "- Define a top-level function named `solve_add`.\n\nThe checks that ship with this task are in `tests_visible/`. "
            "Run them with:\n\n    sh run_tests.sh\n")
RUN_TESTS_SH = r'''#!/bin/sh
exec python3 - "$@" <<'PY'
import importlib.util, os, sys, traceback
sys.path.insert(0, os.getcwd())
failed = 0
d = os.path.join(os.getcwd(), "tests_visible")
for name in sorted(os.listdir(d)):
    if not (name.startswith("test_") and name.endswith(".py")):
        continue
    spec = importlib.util.spec_from_file_location("vis_" + name[:-3], os.path.join(d, name))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    for cname, fn in [(n, v) for n, v in vars(mod).items() if n.startswith("check_") and callable(v)]:
        try:
            fn()
        except Exception as e:
            failed += 1
            print("FAIL %s::%s  %s: %s" % (name, cname, type(e).__name__, e))
        else:
            print("pass %s::%s" % (name, cname))
print("%d check(s) failed" % failed)
sys.exit(1 if failed else 0)
PY
'''
VISIBLE = ('import solution\n\n\ndef check_visible_01():\n    got = solution.solve_add(2, 3)\n'
           '    assert got == 5, "args=%r got=%r want=%r" % ((2, 3), got, 5)\n')
HIDDEN = ('import solution\n\n\ndef check_h1():\n    assert solution.solve_add(10, 5) == 15\n\n\n'
          'def check_h2():\n    assert solution.solve_add(-1, 1) == 0\n\n\ndef check_h3():\n    assert solution.solve_add(0, 0) == 0\n')


def make_task(root: Path, scorers: Path) -> dict:
    t = root / "task"
    shutil.rmtree(t, ignore_errors=True)
    (t / "workspace" / "tests_visible").mkdir(parents=True)
    (t / "hidden" / "tests_visible").mkdir(parents=True)
    (t / "workspace" / "goal.md").write_text(GOAL)
    (t / "workspace" / "contract.md").write_text(CONTRACT)
    (t / "workspace" / "run_tests.sh").write_text(RUN_TESTS_SH)
    (t / "workspace" / "tests_visible" / "test_visible.py").write_text(VISIBLE)
    (t / "hidden" / "tests_visible" / "test_visible.py").write_text(VISIBLE)
    (t / "hidden" / "test_hidden.py").write_text(HIDDEN)
    shutil.copy2(scorers / "code_suite.py", t / "scorer.py")
    (t / "instruction.txt").write_text(INSTR_SENTENCE + "\n")
    return {"bank": "lcb_selfcheck", "id": "solve_add", "dir": str(t), "role": "selfcheck", "deliverable": "solution.py",
            "k": True, "screened": False}


def wait_port(port: int, secs: float = 10.0) -> bool:
    import socket
    t0 = time.time()
    while time.time() - t0 < secs:
        with socket.socket() as s:
            s.settimeout(0.3)
            if s.connect_ex(("127.0.0.1", port)) == 0:
                return True
        time.sleep(0.2)
    return False


class Servers:
    def __init__(self, out: Path, stub_port: int, proxy_port: int, bin_dir: Path, proxy_dir: Path):
        self.out, self.stub_port, self.proxy_port, self.bin_dir, self.proxy_dir = out, stub_port, proxy_port, bin_dir, proxy_dir
        self.stub: subprocess.Popen | None = None
        self.proxy: subprocess.Popen | None = None

    def start_stub(self, script: dict) -> None:
        self.stop_stub()
        (self.out / "stub_script.json").write_text(json.dumps(script))
        env = {**os.environ, "NO_PROXY": "127.0.0.1,localhost", "no_proxy": "127.0.0.1,localhost"}
        self.stub = subprocess.Popen([sys.executable, str(self.bin_dir / "smoke_stub.py"), "--port", str(self.stub_port),
                                      "--script", str(self.out / "stub_script.json"), "--log", str(self.out / "stub.jsonl")],
                                     stdout=open(self.out / "stub.out", "w"), stderr=subprocess.STDOUT, env=env)
        assert wait_port(self.stub_port), "stub did not start"

    def stop_stub(self) -> None:
        if self.stub:
            self.stub.terminate()
            try:
                self.stub.wait(5)
            except subprocess.TimeoutExpired:
                self.stub.kill()
            self.stub = None

    def start_proxy(self) -> None:
        pdir = self.proxy_dir
        pdir.mkdir(parents=True, exist_ok=True)
        (self.out / "proxy.json").write_text(json.dumps({
            "models": {"gemma-4-12b-it-qat": {}}, "upstreams": {"g4": f"http://127.0.0.1:{self.stub_port}"},
            "host_id": "selfcheck", "retry_waits": [1, 2], "budget_usd": 1000000}))
        env = {**os.environ, "NO_PROXY": "127.0.0.1,localhost", "no_proxy": "127.0.0.1,localhost"}
        self.proxy = subprocess.Popen([sys.executable, str(self.bin_dir / "orproxy.py"), "--config", str(self.out / "proxy.json"),
                                       "--out", str(pdir), "--host", "127.0.0.1", "--port", str(self.proxy_port)],
                                      stdout=open(self.out / "proxy.log", "w"), stderr=subprocess.STDOUT, env=env)
        assert wait_port(self.proxy_port), "proxy did not start"

    def stop(self) -> None:
        self.stop_stub()
        if self.proxy:
            self.proxy.terminate()
            self.proxy = None


def bridge_probe(cfg: Cfg, out: Path, shim_dir: Path) -> dict:
    """bridge 的驗證沙箱（bwrap --unshare-all --proc /proc）在這台機器起不起得來；起不來就試 /proc 綁定墊片。
    agent 帳號用 `nobody`（bridge 的邊界檢查要求工作區不屬於 receiver 的帳號）。"""
    work = out / "bridge_probe"
    shutil.rmtree(work, ignore_errors=True)
    (work / "ws" / "tests_visible").mkdir(parents=True)
    (work / "ws" / "tests_visible" / "test_visible.py").write_text(VISIBLE)
    res: dict = {"plain": None, "shim": None, "shim_used": False, "ok": False}
    for label, env in (("plain", {}), ("shim", {"PATH": str(shim_dir)})):
        if label == "shim":
            shim_dir.mkdir(parents=True, exist_ok=True)
            real = shutil.which("bwrap") or "/usr/bin/bwrap"
            (shim_dir / "bwrap").write_text(
                "#!/bin/bash\n# i1001 墊片：Colab 不准掛新 /proc ⇒ 把 `--proc /proc` 換成 `--bind /proc /proc`（同第一批 sandbox.sh）\n"
                "args=()\nwhile [ $# -gt 0 ]; do\n  if [ \"$1\" = --proc ]; then args+=(--bind \"$2\" \"$2\"); shift 2; continue; fi\n"
                "  args+=(\"$1\"); shift\ndone\n" + f"exec {real} \"${{args[@]}}\"\n")
            (shim_dir / "bwrap").chmod(0o755)
        c = Cfg(**{**cfg.__dict__, "bridge_env": env})
        c.eval_root = work / f"eval_{label}"
        ws = work / f"ws_{label}"
        shutil.copytree(work / "ws", ws)
        (ws / "solution.py").write_text(RIGHT)
        ch = subprocess.run(["chown", "-R", "nobody:nogroup", str(ws)], capture_output=True, text=True)
        if ch.returncode != 0:
            res.setdefault("notes", []).append(f"chown to nobody failed ({ch.stderr.strip()[:100]}): bridge will refuse a same-account workspace")
        rh = c.eval_root / "receivers" / f"probe_{label}"
        rh.parent.mkdir(parents=True, exist_ok=True)
        rh.parent.chmod(0o700)
        rc, js, err = tui_cell.bridge(c, "prepare", "--workspace", str(ws), "--task-id", f"probe-{label}", "--mode", "conform",
                                      "--attempts", "3", "--deliverable", "solution.py", "--receiver-home", str(rh),
                                      "--sandbox", "bwrap")
        res[label] = {"prepare_rc": rc, "err": err[-300:]}
        if rc == 0:
            jrc, jres, jerr = tui_cell.bridge(c, "judge", "--workspace", str(ws), "--attempt", "1", "--sandbox", "bwrap",
                                              "--receiver-home", str(rh))
            res[label].update({"judge_rc": jrc, "outcome": (jres or {}).get("outcome"), "err2": jerr[-300:]})
            if jrc == 0:
                res["shim_used"] = (label == "shim")
                res["ok"] = True
                return res
    return res


def result_row(metas: dict) -> dict:
    return {k: ({"cell": v["cell"], "void": v.get("void"), "void_reason": v.get("void_reason")} if isinstance(v, dict) else v)
            for k, v in metas.items()}


def load(p: Path) -> dict:
    try:
        return json.loads(p.read_text())
    except (OSError, ValueError):
        return {}


def score_of(cfg: Cfg, cell: str) -> dict:
    p = cfg.cells / cell / "score.json"
    try:
        return json.loads(p.read_text().strip().splitlines()[-1])
    except (OSError, ValueError, IndexError):
        return {}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, default=Path("/srv/eval/_selfcheck"))
    ap.add_argument("--scenarios", default="a,k,r,timeout,void,driver,c")
    ap.add_argument("--bin-dir", type=Path, default=HERE)
    ap.add_argument("--runs-root", type=Path, default=Path("/srv/runs"))
    ap.add_argument("--scorers", type=Path, default=None, help="含 code_suite.py 的目錄（預設 <bin>/scorers 或 ../scorers）")
    ap.add_argument("--stub-port", type=int, default=18941)
    ap.add_argument("--proxy-port", type=int, default=18905)
    ap.add_argument("--idle-s", type=float, default=4.0)
    ap.add_argument("--agent-timeout", type=int, default=25, help="只用在 timeout 情境")
    ap.add_argument("--bridge-py", default="/opt/eval/bridgevenv/bin/python")
    ap.add_argument("--bridge-script", default="/opt/eval/bridge/ops/eval/native_acceptance_bridge.py")
    ap.add_argument("--install-env", default="")
    ap.add_argument("--wheel", default="")
    ap.add_argument("--shim-dir", type=Path, default=None)
    ap.add_argument("--no-c-in-driver", action="store_true", help="driver 情境不跑 C 線（預設有 wheel 就跑，要 pipx）")
    a = ap.parse_args()
    out: Path = a.out
    out.mkdir(parents=True, exist_ok=True)
    scorers = a.scorers or next((p for p in (a.bin_dir / "scorers", a.bin_dir.parent / "scorers") if (p / "code_suite.py").exists()), None)
    assert scorers, "code_suite.py not found; pass --scorers"
    import shlex
    cfg = Cfg(eval_root=out / "eval", runs_root=a.runs_root, bin_dir=a.bin_dir, proxy=f"http://127.0.0.1:{a.proxy_port}",
              idle_s=a.idle_s, bridge_py=a.bridge_py, bridge_script=a.bridge_script, install_env=shlex.split(a.install_env),
              wheel=a.wheel)
    cfg.eval_root.mkdir(parents=True, exist_ok=True)
    (cfg.eval_root / "proxy").mkdir(exist_ok=True)
    task = make_task(out, scorers)
    summary: dict = {"started": tui_cell.now(), "scenarios": {}, "idle_s": a.idle_s}
    servers = Servers(out, a.stub_port, a.proxy_port, a.bin_dir, cfg.eval_root / "proxy")
    # 先量 bridge（沒有它 K 不能跑）
    shim_dir = a.shim_dir or (out / "shim")
    probe = bridge_probe(cfg, out, shim_dir)
    summary["bridge_probe"] = probe
    summary["bridge_shim"] = bool(probe.get("shim_used"))
    if probe.get("shim_used"):
        cfg.bridge_env = {"PATH": str(shim_dir)}
    log(f"bridge probe: {json.dumps(probe)}")
    want = [s for s in a.scenarios.split(",") if s]
    needs_bridge = [s for s in want if s in ("k", "r", "timeout", "driver")]
    ok_all = bool(probe.get("ok")) or not needs_bridge
    servers.start_stub({"plain": ["right"], "solutions": {"right": RIGHT, "wrong": WRONG}})
    servers.start_proxy()
    pool = SlotPool(4)
    try:
        for sc in want:
            if sc in needs_bridge and not probe.get("ok"):
                summary["scenarios"][sc] = {"ok": False, "failed_expectations": ["bridge unavailable on this machine (see bridge_probe)"]}
                continue
            summary["scenarios"][sc] = (run_driver_scenario(cfg, task, servers, a) if sc == "driver"
                                        else run_scenario(sc, cfg, task, servers, pool, a))
            ok_all = ok_all and summary["scenarios"][sc]["ok"]
            log(f"scenario {sc}: ok={summary['scenarios'][sc]['ok']} {summary['scenarios'][sc].get('failed_expectations')}")
    finally:
        servers.stop()
    summary["ok"] = ok_all
    summary["ended"] = tui_cell.now()
    (out / "selfcheck.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1) + "\n")
    print(json.dumps({"ok": ok_all, "bridge_shim": summary["bridge_shim"],
                      "scenarios": {k: v["ok"] for k, v in summary["scenarios"].items()}}))
    return 0 if ok_all else 1


def run_scenario(sc: str, cfg: Cfg, task: dict, servers: Servers, pool: SlotPool, a: argparse.Namespace) -> dict:
    sols = {"right": RIGHT, "wrong": WRONG}
    plan = {"a": ["right"], "k": ["wrong", "right"], "r": ["none", "right"], "timeout": ["slow", "right"],
            "void": ["error"], "c": ["claim"]}[sc]
    servers.start_stub({"plain": plan, "fix": "right", "solutions": sols, "slow_s": 120})
    c = Cfg(**{k: v for k, v in cfg.__dict__.items()})
    if sc == "timeout":
        c.agent_timeout = a.agent_timeout
    ledger = load_ledger(c)
    prefix = f"sc-{sc}"
    c.cells.mkdir(parents=True, exist_ok=True)
    nested = {"a": (), "k": ("R", "K"), "r": ("R", "K"), "timeout": ("R", "K"), "void": (), "c": ()}[sc]
    t0 = time.time()
    if sc == "c":
        metas = {"C": tui_cell.run_c_group(c, ledger, pool, dict(task, k=False), prefix=prefix)}
    else:
        metas = tui_cell.run_a_group(c, ledger, pool, dict(task, k=bool(nested)), prefix=prefix, nested=nested)
    res: dict = {"seconds": round(time.time() - t0, 1), "metas": result_row(metas)}
    failed: list[str] = []

    def expect(name: str, cond: bool) -> None:
        if not cond:
            failed.append(name)

    A = metas.get("A") or {}
    s1 = (A.get("sessions") or [{}])[0]
    if sc == "a":
        sa = score_of(c, A["cell"])
        expect("A not void", not A.get("void"))
        expect("done by idle_final", s1.get("done_reason") == "idle_final")
        expect("exit clean rc0", s1.get("exit_clean") is True)
        expect("typed text matched", s1.get("typed_ok") is True)
        expect("score pass", sa.get("pass") is True)
        expect("pane captured", (c.cells / A["cell"] / "panes" / "pane-1.txt").exists())
        expect("ledger saw calls", (s1.get("ledger") or {}).get("calls", 0) >= 2)
        expect("no late write", s1.get("late_write_after_done") is False)
        expect("no leftover procs", not s1.get("leftover_procs"))
    elif sc in ("k", "r", "timeout"):
        R, K = metas.get("R") or {}, metas.get("K") or {}
        sa, sr, sk = (score_of(c, x["cell"]) if x else {} for x in (A, R, K))
        expect("A not void", not A.get("void"))
        expect("R not void", not R.get("void"))
        expect("K not void", not K.get("void"))
        expect("K ran with bridge", bool(K) and (K.get("k") or {}).get("attempts"))
        expect("workspace had bridge contract", A.get("workspace_has_bridge_contract") is True)
        if sc == "k":
            expect("A fails (wrong first)", sa.get("pass") is False)
            expect("K attempts reject then accept", [x["rc"] for x in K["k"]["attempts"]] == [40, 0])
            expect("K released", K["k"].get("released") is True)
            expect("K passes", sk.get("pass") is True)
            expect("K used 2 sessions", K.get("n_sessions") == 2)
            expect("fix instruction was typed", (c.cells / K["cell"] / "fix_instruction_2.txt").exists())
            expect("R = A (no retry)", R.get("retry_needed") is False and R.get("n_sessions") == 1)
            expect("R score = A score", sr.get("pass") is False)
            expect("fix session saw the checks", "visible checks" in (c.cells / K["cell"] / "fix_instruction_2.txt").read_text())
            expect("receiver records copied", (c.cells / K["cell"] / "receiver").is_dir())
            expect("no private key copied", not list((c.cells / K["cell"] / "receiver").rglob("*.key")))
        if sc == "r":
            expect("A not delivered", A.get("delivered") is False)
            expect("A fails", sa.get("pass") is False)
            expect("R retried", R.get("retry_needed") is True and R.get("n_sessions") == 2)
            expect("R retry reason no_deliverable", (R.get("retry_reasons") or [None])[0] == "no_deliverable")
            expect("R passes", sr.get("pass") is True)
            expect("K passes via fix", sk.get("pass") is True and K["k"].get("released") is True)
        if sc == "timeout":
            expect("A timed out", A.get("timeout") is True and s1.get("rc") == 124)
            expect("A timeout is not void", not A.get("void"))
            expect("R retried after timeout", R.get("retry_needed") is True and (R.get("retry_reasons") or [None])[0] == "timeout")
    elif sc == "void":
        expect("A void", A.get("void") is True)
        expect("void reason is infra", str(A.get("void_reason", "")).startswith(("model_error_final", "proxy_non200")))
        expect("group flagged void", metas.get("void") is True)
    elif sc == "c":
        C = metas.get("C") or {}
        expect("C not void", not C.get("void"))
        expect("install ok", C.get("install_rc") == 0)
        expect("c_arm_ok", C.get("c_arm_ok") is True)
        expect("send-back arrived inside the run", ((C.get("sessions") or [{}])[0].get("sendbacks") or 0) >= 1)
        expect("C passes after send-back", score_of(c, C["cell"]).get("pass") is True)
        expect("no contract in C workspace", C.get("workspace_has_bridge_contract") is False)
    res["failed_expectations"] = failed
    res["ok"] = not failed
    return res


def run_driver_scenario(cfg: Cfg, task: dict, servers: Servers, a: argparse.Namespace) -> dict:
    import driver_i1001
    out = cfg.eval_root
    st = out / "staged"
    shutil.rmtree(st, ignore_errors=True)
    for stale in list(cfg.cells.glob("scd-*")) + [cfg.cells / "_run_scd"]:           # 只清這個情境自己的格子，別的情境的證據留著
        shutil.rmtree(stale, ignore_errors=True)
    for f in ("progress.jsonl", "DRIVER_DONE", "STOP"):
        (out / f).unlink(missing_ok=True)
    tasks = []
    for i in (1, 2, 3):
        d = st / "lcb_selfcheck" / f"u{i}"
        shutil.copytree(task["dir"], d)
        tasks.append({"bank": "lcb_selfcheck", "id": f"u{i}", "dir": str(d), "role": "selfcheck", "deliverable": "solution.py",
                      "k": True, "screened": False})
    (st / "tasks_index.json").write_text(json.dumps([{k: t[k] for k in ("bank", "id", "dir", "role")} for t in tasks]))
    (st / "MANIFEST.json").write_text(json.dumps({"screen_sample": {}}))
    with_c = bool(cfg.wheel_path()) and not a.no_c_in_driver
    arms = ["A", "C"] if with_c else ["A"]
    plan = {"schema": "i1001.plan/1", "kind": "main", "seed": 1, "arms": arms, "nested": ["R", "K"], "samples": [1],
            "k_banks": ["lcb_selfcheck"], "tasks": tasks, "estimate": {"units": 3}}
    (out / "plan_in.json").write_text(json.dumps(plan))
    servers.start_stub({"plain": ["right"], "fix": "right", "solutions": {"right": RIGHT, "wrong": WRONG}, "fail_window_s": 6})
    argv = ["--phase", "main", "--plan", str(out / "plan_in.json"), "--staged", str(st), "--slots", "4", "--prefix", "scd",
            "--final", "--stop-file", str(out / "STOP"), "--eval-root", str(out), "--runs-root", str(cfg.runs_root),
            "--bin-dir", str(cfg.bin_dir), "--proxy", cfg.proxy, "--bridge-py", cfg.bridge_py, "--bridge-script", cfg.bridge_script,
            "--idle-s", str(cfg.idle_s), "--install-env", " ".join(cfg.install_env)]
    if cfg.bridge_env.get("PATH"):
        argv += ["--shim-dir", cfg.bridge_env["PATH"]]
    if a.wheel:
        argv += ["--wheel", a.wheel]
    t0 = time.time()
    rc = driver_i1001.main(argv)
    secs = round(time.time() - t0, 1)
    rows = [json.loads(x) for x in (out / "progress.jsonl").read_text().splitlines() if x.strip()]
    metas = {d.name: load(d / "meta.json") for d in cfg.cells.glob("scd-*")}
    done = {d.name: (d / "DONE").exists() for d in cfg.cells.glob("scd-*")}
    voids = [r for r in rows if r["void"]]
    finals = {}
    for r in rows:
        finals[(r["unit"], r["arm"])] = r        # 後面的 attempt 蓋掉前面的
    failed: list[str] = []

    def expect(name: str, cond: bool) -> None:
        if not cond:
            failed.append(name)

    expect("driver rc 0", rc == 0)
    expect("every cell has DONE", bool(done) and all(done.values()))
    expect("the injected 500 window produced void groups", len(voids) >= 1)
    expect("the void group was rerun as attempt 2", all(any(r["attempt"] == 2 and r["unit"] == v["unit"] and r["arm"] == v["arm"]
                                                           for r in rows) for v in voids))
    expect("final attempts are not void", all(not r["void"] for r in finals.values()))
    expect("every unit has A, R, K (and C)", all(((u, arm) in finals) for u in {r["unit"] for r in rows}
                                                 for arm in (["A", "R", "K"] + (["C"] if with_c else []))))
    expect("DRIVER_DONE written", (out / "DRIVER_DONE").exists())
    expect("run record cell", (cfg.cells / "_run_scd" / "DONE").exists())
    expect("no score in progress.jsonl", not any("pass" in r or "score" in r for r in rows))
    n_rows = len(rows)
    (out / "DRIVER_DONE").unlink()
    rc2 = driver_i1001.main(argv)
    rows2 = [json.loads(x) for x in (out / "progress.jsonl").read_text().splitlines() if x.strip()]
    expect("resume: second run starts nothing", rc2 == 0 and len(rows2) == n_rows)
    return {"seconds": secs, "ok": not failed, "failed_expectations": failed, "rows": len(rows), "voids": len(voids),
            "metas": {k: {"void": v.get("void"), "void_reason": v.get("void_reason"), "n_sessions": v.get("n_sessions")}
                      for k, v in metas.items()}}


if __name__ == "__main__":
    sys.exit(main())
