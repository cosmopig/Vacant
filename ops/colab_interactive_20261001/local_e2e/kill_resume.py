#!/usr/bin/env python3
"""kill_resume — 本機端到端的「續跑」測試：主跑進行到一半，SIGKILL driver；記下當下的狀態；（可選）先做一次中途打包；再用同一條指令重啟 driver。

    python3 kill_resume.py --prefix t1 --min-done 4 --snapshot <kill_snapshot.json> [--interim-pack <鏡像目錄>] [--restart-cmd-file <檔>]

做的事：
  1. 等 progress.jsonl 裡主跑（前綴 `<p>-`，不含篩選的 `<p>s-`）的完成格數 ≥ min-done，而且 cells/ 裡有主跑的未完成格（真的「進行中」）；
  2. 找 driver 的 pid（指令列含 driver_i1001.py 與 --prefix），SIGKILL（不給它清理的機會；它的 tmux／pi 子行程不會被一起殺——
     這是「driver 被 OOM 殺掉」的情境，不是「整台 VM 重開」）；
  3. 寫快照：此刻已 DONE 的格子（與 meta.ended）、進行中的目錄、還活著的 cell-user 行程數、tmux socket；
  4. 中途打包（`packer.py --once`，模擬 packer 的定時一包）；
  5. 重啟：`--restart-cmd-file` 的內容就是 launch_i1001.sh 起 driver 的那條指令（RUNBOOK 的「重啟」一節）。
"""
from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

EV = Path("/srv/eval")


def sh(cmd: str) -> str:
    return subprocess.run(["bash", "-c", cmd], capture_output=True, text=True).stdout


def driver_pid(prefix: str) -> int | None:
    for ln in sh("pgrep -af driver_i1001.py").splitlines():
        if f"--prefix {prefix}" in ln and "pgrep" not in ln and "bash -c" not in ln:
            return int(ln.split()[0])
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--prefix", required=True)
    ap.add_argument("--min-done", type=int, default=4)
    ap.add_argument("--snapshot", type=Path, required=True)
    ap.add_argument("--interim-pack", type=Path)
    ap.add_argument("--restart-cmd-file", type=Path)
    ap.add_argument("--timeout", type=int, default=1500)
    ap.add_argument("--require-done", action="append", default=[], help="這些格子都 DONE 了才殺（讓注入的 500 爆發已經用完，結果才可重現）")
    a = ap.parse_args()
    P = a.prefix
    t0 = time.time()
    while time.time() - t0 < a.timeout:
        rows = []
        try:
            rows = [json.loads(x) for x in (EV / "progress.jsonl").read_text().splitlines() if x.strip()]
        except OSError:
            pass
        main_done = [r for r in rows if "cell" in r and r["cell"].startswith(P + "-")]
        cells = EV / "cells"
        inflight = [p.name for p in cells.glob(P + "-*") if not (p / "DONE").exists()] if cells.exists() else []
        if len(main_done) >= a.min_done and inflight and all((cells / c / "DONE").exists() for c in a.require_done):
            break
        time.sleep(1)
    else:
        print("timeout waiting for the kill point", file=sys.stderr)
        return 2
    pid = driver_pid(P)
    if pid is None:
        print("driver not found", file=sys.stderr)
        return 3
    os.kill(pid, signal.SIGKILL)
    time.sleep(1.5)
    cells = EV / "cells"
    done = {}
    for p in sorted(cells.glob("*")):
        if (p / "DONE").exists() and p.name.startswith(P + "-"):
            try:
                done[p.name] = json.loads((p / "meta.json").read_text()).get("ended")
            except (OSError, ValueError):
                done[p.name] = None
    inflight = sorted(p.name for p in cells.glob(P + "-*") if not (p / "DONE").exists())
    snap = {"killed_driver_pid": pid, "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "done_cells": done,
            "inflight_dirs": inflight,
            "orphan_cell_user_procs": len(sh("ps -eo user:20,args | grep -E '^[as][0-9]{6} ' | grep -v grep").splitlines()),
            "tmux_sockets": sorted(x for x in sh("ls /tmp/tmux-0 2>/dev/null").split() if x.startswith("i")),
            "driver_alive_after_kill": driver_pid(P) is not None}
    a.snapshot.write_text(json.dumps(snap, indent=1) + "\n")
    print(json.dumps({k: (v if not isinstance(v, (dict, list)) else len(v)) for k, v in snap.items()}))
    if a.interim_pack:
        print(sh(f"python3 /opt/eval/bin/packer.py --once --mirror {a.interim_pack} 2>&1 | tail -3"))
    if a.restart_cmd_file:
        cmd = a.restart_cmd_file.read_text().strip()
        subprocess.Popen(["bash", "-c", f"setsid nohup {cmd} >> /srv/eval/driver_{P}.log 2>&1 < /dev/null &"])
        time.sleep(3)
        print("restarted driver pid", driver_pid(P))
    return 0


if __name__ == "__main__":
    sys.exit(main())
