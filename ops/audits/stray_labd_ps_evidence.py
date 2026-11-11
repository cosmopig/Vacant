#!/usr/bin/env python3
"""stray labd 進程審計證據鏈（ticket R20261111_1152-2；2026-11-11 r1444 重做：消除空轉 selftest）。

判準（audit()）：
- 0 或 1 個「真」labd 實例，且父進程非 shell、父環境無 VACANT_PI_* → OK
- 多實例 / 父進程為 shell / 父環境帶 VACANT_PI_* → VIOLATION

「真」實例判定（is_labd）：cmdline 中有一個參數以 labd.py 結尾、且前一參數是
python 解釋器。避免 pgrep -f 式子串誤配——prompt/args 內含 "labd.py" 文字
的 pi session 等進程不算（舊版報告誤配實例即此因，見 r1444 審查記錄）。

審計邏輯對注入的 process table 純函數化（audit/is_labd 不碰系統），
--selftest 用假 process table 跑 5 組正/負控制，全部通過才印
VERDICT: STRAY_LABD_AUDIT_OK；任一控制不符即印
VERDICT: STRAY_LABD_SELFTEST_BROKEN 且 exit 1（I-4：未測量≠通過）。

退出：0=OK 或 selftest 全控制通過；1=VIOLATION 或 selftest 有控制失敗；2=內部錯。
"""
import glob
import json
import os
import sys
import time

SHELLS = {"sh", "bash", "zsh", "dash", "ash"}
PYTHON = {"python", "python2", "python3"}


def is_labd(args):
    return any(
        a.endswith("labd.py") and (i == 0 or os.path.basename(args[i - 1]) in PYTHON)
        for i, a in enumerate(args)
    )


def audit(processes):
    """processes: [{"pid","ppid","uid","cmdline":[...],"env":{..}|None,
    "parent_cmdline":[...]|None,"parent_env":{..}|None}] → 判定 dict。純函數。"""
    violations = []
    if len(processes) > 1:
        violations.append({"type": "multiple_instances", "pids": [p["pid"] for p in processes]})
    for p in processes:
        pc = p.get("parent_cmdline") or []
        if pc and os.path.basename(pc[0]) in SHELLS:
            violations.append({"type": "stray_shell_parent", "pid": p["pid"],
                               "parent_pid": p["ppid"], "parent": pc[0]})
        pi_env = sorted(k for k in (p.get("parent_env") or {}) if k.startswith("VACANT_PI_"))
        if pi_env:
            violations.append({"type": "stray_pi_env_parent", "pid": p["pid"],
                               "parent_pid": p["ppid"], "vars": pi_env})
    return {"status": "VIOLATION" if violations else "OK",
            "instances": len(processes), "violations": violations}


def scan_repo_shell_scripts(root, exclude=("runs",)):
    """靜態掃描 repo 內 shell 腳本中無 single-instance 守護的 labd.py 啟動點（findings，非 violation）。
    runs/ 為 2026-09 歷史實驗腳本，不在「現行啟動路徑」範圍內，排除。"""
    findings = []
    for path in sorted(glob.glob(os.path.join(root, "**", "*.sh"), recursive=True)):
        if any(part in exclude for part in path.split(os.sep)):
            continue
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
        except OSError:
            continue
        for i, line in enumerate(lines, 1):
            if "labd.py" in line and not any(
                    g in line for g in ("pidfile", "flock", "single_instance", "single-instance")):
                findings.append({"file": path, "line": i, "text": line.strip()[:200]})
    return findings


def _read_args(pid):
    try:
        with open(f"/proc/{pid}/cmdline", "rb") as f:
            return [a.decode("utf-8", "replace") for a in f.read().split(b"\0") if a]
    except OSError:
        return []


def _read_env(pid):
    try:
        with open(f"/proc/{pid}/environ", "rb") as f:
            raw = f.read().split(b"\0")
    except OSError:
        return None
    env = {}
    for kv in raw:
        if b"=" in kv:
            k, v = kv.split(b"=", 1)
            env[k.decode("utf-8", "replace")] = v.decode("utf-8", "replace")[:200]
    return env


def _ancestors():
    out, pid = set(), os.getpid()
    for _ in range(64):
        try:
            with open(f"/proc/{pid}/status") as f:
                for line in f:
                    if line.startswith("PPid:"):
                        pid = int(line.split()[1])
                        break
        except OSError:
            break
        if pid in (0, 1) or pid in out:
            break
        out.add(pid)
    return out


def collect_processes():
    skip = _ancestors() | {os.getpid()}
    out = []
    for name in filter(str.isdigit, os.listdir("/proc")):
        pid = int(name)
        if pid in skip:
            continue
        args = _read_args(pid)
        if not is_labd(args):
            continue
        ppid = 0
        try:
            with open(f"/proc/{pid}/status") as f:
                for line in f:
                    if line.startswith("PPid:"):
                        ppid = int(line.split()[1])
        except OSError:
            pass
        out.append({"pid": pid, "ppid": ppid, "cmdline": args,
                    "env": _read_env(pid),
                    "parent_cmdline": [] if ppid in skip else _read_args(ppid),
                    "parent_env": _read_env(ppid) if ppid not in skip else None})
    return out


def P(pid=100, ppid=1, parent_cmdline=None, parent_env=None):
    return {"pid": pid, "ppid": ppid, "uid": "1000",
            "cmdline": ["python3", "/srv/vlab/bin/labd.py"], "env": None,
            "parent_cmdline": parent_cmdline, "parent_env": parent_env}


def selftest():
    results = []

    def record(name, got, want):
        ok = got == want
        results.append(ok)
        print(f"control {name}: expected={want} got={got} {'PASS' if ok else 'FAIL'}")

    a = audit([P()])
    record("A_managed_single", (a["status"], a["instances"]), ("OK", 1))
    b = audit([P(ppid=7, parent_cmdline=["/bin/bash", "-c", "x"])])
    record("B_shell_parent", (b["status"], b["violations"][0]["type"]), ("VIOLATION", "stray_shell_parent"))
    c = audit([P(ppid=7, parent_cmdline=["/usr/bin/python3", "pi"],
                 parent_env={"VACANT_PI_PARENT": "true", "HOME": "/x"})])
    record("C_pi_env_parent", (c["status"], c["violations"][0]["type"]), ("VIOLATION", "stray_pi_env_parent"))
    d = audit([P(pid=1), P(pid=2)])
    record("D_multiple", (d["status"], d["violations"][0]["type"]), ("VIOLATION", "multiple_instances"))
    record("E_matcher_pos", is_labd(["python3", "/srv/vlab/bin/labd.py"]), True)
    record("E_matcher_neg", is_labd(["pi", "-p", "工單文字提到 labd.py 及其父進程"]), False)

    if all(results):
        print("VERDICT: STRAY_LABD_AUDIT_OK")
        return 0
    print("VERDICT: STRAY_LABD_SELFTEST_BROKEN")
    return 1


def main():
    if "--selftest" in sys.argv[1:]:
        return selftest()
    try:
        procs = collect_processes()
        res = audit(procs)
        root = os.getcwd()
        report = {"timestamp": time.time(), "status": res["status"],
                  "instances": res["instances"], "violations": res["violations"],
                  "launch_script_findings": scan_repo_shell_scripts(root),
                  "evidence": procs}
        out = os.path.join(root, "ops", "audits", "labd_process_audit_report.json")
        os.makedirs(os.path.dirname(out), exist_ok=True)
        with open(out, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(json.dumps(res, ensure_ascii=False))
        print(f"report: {out}")
        return 1 if res["status"] == "VIOLATION" else 0
    except Exception as e:
        print(f"internal error: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
