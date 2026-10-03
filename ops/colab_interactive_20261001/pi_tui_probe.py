#!/usr/bin/env python3
"""pi_tui_probe — drive pi 0.87.1's INTERACTIVE TUI in tmux against stub_model.py and measure the facts the
i1001 interactive driver depends on.  Stdlib only; needs tmux, bwrap, root; no GPU, no paid model, no task content.

What it settles (see PI_INTERACTIVE_NOTES.md in the run's scratch / the RUNLOG for the numbers):
  ready   — the TUI accepts keys once the footer `(<provider>) <model>` is drawn (earlier keys are dropped);
  done    — `tail_state(entries)` below: what the last session-jsonl entries say (running/final/retrying/error_final);
  exit    — Ctrl-D on an empty editor (fallback `/quit`) ends pi with rc 0 in < 1 s;
  vacant  — arm C: the send-back is a `custom_message` (customType vacant-check) 0.3-0.5 s after the final
            assistant `stop`, inside the same run, and arrives at the model as a `user` message.

Usage (root):  pi_tui_probe.py --scenario plain|claim|error|errorfinal|length|abort [--arm A|C] [--cell NAME]
  Layout it expects (what vm_setup.sh makes on the VM): /opt/eval/bin/sandbox.sh, /opt/eval/pi/bin/pi,
  /opt/eval/wheel/*.whl (arm C), /srv/runs (root 711), /app and /logs/agent and /content (empty, root).
  Arm C installs Vacant in the cell exactly as cell.sh does (pipx install <wheel> && vacant install); pass
  --install-env 'HTTPS_PROXY=... PIP_CERT=... SSL_CERT_FILE=...' when the machine needs a proxy (this container does).
Writes <out>/<scenario>-<arm>/{timeline.jsonl,pane.txt,session.jsonl,stub.jsonl,result.json}.  Exit 0 = every expectation held.
"""
from __future__ import annotations

import argparse
import datetime
import glob
import json
import os
import shlex
import subprocess
import sys
import time
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
STUB = os.path.join(HERE, "stub_model.py")
INSTR = "Read goal.md and contract.md in this directory and do what they say. Use your tools to write the file."
MODEL = "gemma-4-12b-it-qat"
FOOTER = "(harbor-endpoint)"
GOAL = "# Goal\nImplement a function `add(a, b)` that returns the sum of two integers.\n"
CONTRACT = "# Contract\nWrite the implementation to `solution.py` in this directory. The function must be named `add`.\n"
SOL = "def add(a, b):\n    return a + b\n"
READS = [{"read": "goal.md"}, {"read": "contract.md"}]
SCENARIOS = {
    # plain: write the file, say done.  claim: say done without writing (Vacant should send it back, the 2nd turn writes it).
    "plain": {"turns": [{"steps": [{"write": ["solution.py", SOL]}, {"text": "Done."}]}]},
    "claim": {"turns": [{"steps": READS + [{"text": "I have written the solution to solution.py. Done."}]},
                        {"steps": [{"write": ["solution.py", SOL]}, {"text": "Fixed: solution.py now exists."}]}]},
    "error": {"turns": [{"steps": [{"error": 500, "times": 2}, {"write": ["solution.py", SOL]}, {"text": "Done."}]}]},
    "errorfinal": {"turns": [{"steps": [{"error": 500}]}]},
    "length": {"turns": [{"steps": [{"text": "cut off mid-sent", "finish": "length"}]}]},
    "abort": {"turns": [{"steps": [{"write": ["solution.py", SOL], "delay_s": 20}, {"text": "Done."}]}]},
}


EVLOG_TS = """// passive observer for the probe: logs pi lifecycle events with a wall-clock timestamp (changes nothing)
import { appendFileSync } from "node:fs";
const LOG = "/tmp/evlog.jsonl";
const EVENTS = ["agent_start", "turn_start", "turn_end", "agent_end", "agent_before_settle", "agent_settled",
                "message_end", "tool_execution_end", "session_shutdown"];
export default function (pi) {
  for (const name of EVENTS) {
    pi.on(name, async (event) => {
      try {
        const m = (event && event.message) || {};
        appendFileSync(LOG, JSON.stringify({ t: Date.now() / 1000, event: name, role: m.role, stop: m.stopReason }) + "\\n");
      } catch (e) {}
      return undefined;
    });
  }
}
"""


def run(*a, **k):
    return subprocess.run(a, capture_output=True, text=True, **k)


def iso(s: str) -> float:
    return datetime.datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()


# ── what the session jsonl says (the part the driver reuses) ────────────────────────────────────
def read_entries(sess_dir: str) -> list[dict]:
    out: list[dict] = []
    for f in sorted(glob.glob(os.path.join(sess_dir, "**", "*.jsonl"), recursive=True)):
        for line in open(f, encoding="utf-8", errors="replace"):
            try:
                out.append(json.loads(line))
            except ValueError:
                pass            # a half-written last line: the next poll sees it whole
    return out


def tail_state(entries: list[dict]) -> str:
    """running | final | retrying | error_final | empty — from the last message-bearing entry.
    pi 0.87.1 has no agent_end entry in the file.  The session file does not exist before the first
    assistant message finished (so 'empty' means 'not yet', not 'dead').
      assistant stop/aborted/length -> final (a `context_edit` may trail `length`; pi does not retry it)
      assistant error + context_edit after it -> retrying (pi sleeps 2 s, 4 s, 8 s; 3 retries, then the 4th error is final)
      assistant error, nothing after -> error_final (infra_void candidate: see message.errorMessage)
      assistant toolUse / toolResult / user / custom_message -> running (a model call or a tool is in flight)"""
    msgs = [i for i, e in enumerate(entries) if e.get("type") in ("message", "custom_message")]
    if not msgs:
        return "empty"
    i = msgs[-1]
    e, m = entries[i], entries[i].get("message") or {}
    if e.get("type") == "custom_message" or m.get("role") != "assistant":
        return "running"
    sr = m.get("stopReason")
    after = [x.get("type") for x in entries[i + 1:]]
    if sr in ("stop", "aborted", "length"):
        return "final"
    if sr == "error":
        return "retrying" if "context_edit" in after else "error_final"
    return "running"        # toolUse, pending, deferred


def sess_stats(entries: list[dict]) -> dict:
    last_t = max((iso(e["timestamp"]) for e in entries if e.get("timestamp")), default=None)
    return {"n": len(entries), "state": tail_state(entries), "last_entry_t": last_t,
            "types": [f'{e.get("type")}:{(e.get("message") or {}).get("role") or e.get("customType") or ""}:'
                      f'{(e.get("message") or {}).get("stopReason") or ""}' for e in entries]}


# ── tmux ────────────────────────────────────────────────────────────────────────────────────────
class Pane:
    def __init__(self, sock: str, conf: str):
        self.sock, self.conf = sock, conf

    def tm(self, *a):
        return run("tmux", "-L", self.sock, *a)

    def start(self, cmd: str) -> float:
        self.tm("kill-server")
        r = self.tm("-f", self.conf, "new-session", "-d", "-s", self.sock, "-x", "160", "-y", "50",
                    f"{cmd}; echo __PANE_EXIT_$?__; sleep 3600")
        assert r.returncode == 0, r.stderr
        return time.time()

    def text(self, hist: bool = False) -> str:
        a = ["capture-pane", "-p", "-J", "-t", self.sock]
        if hist:
            a[1:1] = ["-S", "-"]
        return self.tm(*a).stdout

    def type(self, s: str) -> None:        # single line only; multi-line -> load-buffer + paste-buffer -p
        self.tm("send-keys", "-t", self.sock, "-l", s)

    def key(self, k: str) -> None:
        self.tm("send-keys", "-t", self.sock, k)

    def kill(self) -> None:
        self.tm("kill-server")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--scenario", required=True, choices=sorted(SCENARIOS))
    ap.add_argument("--arm", default="A", choices=["A", "C"])
    ap.add_argument("--cell", default=None)
    ap.add_argument("--user", default=None)
    ap.add_argument("--port", type=int, default=18931)
    ap.add_argument("--out", default=os.path.join(HERE, "probe_out"))
    ap.add_argument("--idle-s", type=float, default=15.0, help="quiet period after a final state before 'done'")
    ap.add_argument("--wall-s", type=float, default=120.0)
    ap.add_argument("--sandbox", default="/opt/eval/bin/sandbox.sh")
    ap.add_argument("--runs-root", default="/srv/runs")
    ap.add_argument("--install-env", default="", help="env for the arm-C install step (proxy/CA), 'K=V K=V'")
    ap.add_argument("--evlog", action="store_true", help="also load a passive pi extension that logs agent_end / agent_settled times")
    ap.add_argument("--keep", action="store_true", help="keep the cell dir and user")
    a = ap.parse_args()
    cell = a.cell or f"probe-{a.scenario}-{a.arm}".lower()
    user = a.user or ("pp%06d" % (zlib.crc32(cell.encode()) % 10**6))
    C = os.path.join(a.runs_root, cell)
    out = os.path.join(a.out, f"{a.scenario}-{a.arm}")
    os.makedirs(out, exist_ok=True)
    res: dict = {"scenario": a.scenario, "arm": a.arm, "idle_s": a.idle_s, "expect": {}, "problems": []}

    # cell (as cell.sh): fresh user, home/tmp/app/agentlog 700, models.json 600
    if run("id", user).returncode != 0:
        run("useradd", "-M", "-d", f"/home/{user}", "-s", "/bin/bash", "-K", "UMASK=077", user)
    run("rm", "-rf", C)
    for d in ("home", "tmp", "app", "agentlog"):
        os.makedirs(os.path.join(C, d))
    os.chmod(C, 0o711)
    open(os.path.join(C, "app", "goal.md"), "w").write(GOAL)
    open(os.path.join(C, "app", "contract.md"), "w").write(CONTRACT)
    os.makedirs(os.path.join(C, "tmp", "harbor-pi-agent"))
    base = f"http://127.0.0.1:{a.port}/v1"
    json.dump({"providers": {"harbor-endpoint": {"baseUrl": base, "apiKey": "$OPENROUTER_API_KEY",
              "api": "openai-completions", "models": [{"id": MODEL}]}}},
              open(os.path.join(C, "tmp", "harbor-pi-agent", "models.json"), "w"), indent=2)
    run("chown", "-R", f"{user}:{user}", *[os.path.join(C, d) for d in ("home", "tmp", "app", "agentlog")])
    for d in ("home", "tmp", "app", "agentlog"):
        os.chmod(os.path.join(C, d), 0o700)
    os.chmod(os.path.join(C, "tmp", "harbor-pi-agent", "models.json"), 0o600)
    sbx = ["bash", a.sandbox, user, C]

    if a.arm == "C":                                    # the user's install command, in the user's sandbox
        wheel = sorted(glob.glob("/opt/eval/wheel/*.whl"))[0]
        r = run(*sbx, *shlex.split(a.install_env), "--", "bash", "-c",
                f"set -euo pipefail; pipx install '{wheel}' && mkdir -p /tmp/harbor-pi-agent && "
                f"PI_CODING_AGENT_DIR=/tmp/harbor-pi-agent vacant install")
        open(os.path.join(out, "install.log"), "w").write(r.stdout + r.stderr)
        res["install_rc"] = r.returncode
        assert r.returncode == 0, "vacant install failed: see install.log"

    if a.evlog:
        ed = os.path.join(C, "tmp", "harbor-pi-agent", "extensions")
        os.makedirs(ed, exist_ok=True)
        open(os.path.join(ed, "evlog.ts"), "w").write(EVLOG_TS)
        run("chown", "-R", f"{user}:{user}", os.path.join(C, "tmp", "harbor-pi-agent"))

    script = os.path.join(out, "stub_script.json")
    json.dump(SCENARIOS[a.scenario], open(script, "w"))
    slog = os.path.join(out, "stub.jsonl")
    if os.path.exists(slog):
        os.unlink(slog)
    run("pkill", "-f", f"[s]tub_model.py --port {a.port} ")
    stub = subprocess.Popen([sys.executable, STUB, "--port", str(a.port), "--script", script, "--log", slog],
                            stdout=open(os.path.join(out, "stub.out"), "w"), stderr=subprocess.STDOUT)
    time.sleep(0.8)
    conf = os.path.join(out, "tmux.conf")
    open(conf, "w").write("set -g history-limit 50000\n")
    pane = Pane(cell, conf)
    inner = ("mkdir -p /logs/agent/pi/sessions && PI_CODING_AGENT_DIR=/tmp/harbor-pi-agent exec pi "
             "--session-dir /logs/agent/pi/sessions --provider harbor-endpoint --model \"$MODEL\"")
    cmd = " ".join(shlex.quote(x) for x in sbx + ["OPENROUTER_API_KEY=sk-dummy", f"OPENROUTER_BASE_URL={base}",
                                                 f"MODEL={MODEL}", "TERM=xterm-256color", "PI_OFFLINE=1", "--", "bash", "-c", inner])
    sess_dir = os.path.join(C, "agentlog", "pi", "sessions")
    hook_dir = os.path.join(C, "home", ".vacant")
    tl = open(os.path.join(out, "timeline.jsonl"), "w")

    def log(kind: str, **kw):
        tl.write(json.dumps({"t": round(time.time() - t0, 3), "kind": kind, **kw}, ensure_ascii=False) + "\n")
        tl.flush()

    t0 = pane.start(cmd)
    try:
        # (a) ready: the footer is drawn.  Typing earlier is dropped (pi flushes input when it enters raw mode).
        while time.time() - t0 < 30 and FOOTER not in pane.text():
            time.sleep(0.05)
        res["ready_s"] = round(time.time() - t0, 2)
        res["expect"]["ready_within_10s"] = FOOTER in pane.text() and res["ready_s"] < 10
        time.sleep(0.5)
        pane.type(INSTR)
        time.sleep(0.2)
        pane.key("Enter")
        t_enter = time.time()
        log("enter")
        aborted = False
        done_at = None
        last_sig, last_change = None, time.time()
        while time.time() - t_enter < a.wall_s:
            if a.scenario == "abort" and not aborted and time.time() - t_enter > 3:
                pane.key("Escape")
                aborted = True
                log("key", key="Escape")
            ents = read_entries(sess_dir)
            st = sess_stats(ents)
            nreq = len(open(slog).read().splitlines()) if os.path.exists(slog) else 0
            hook = run("pgrep", "-u", user, "-f", "vacant_network hook").stdout.split() if a.arm == "C" else []
            sig = (st["n"], nreq, tuple(hook))
            if sig != last_sig:
                log("change", session_n=st["n"], state=st["state"], requests=nreq, hook_procs=len(hook))
                last_sig, last_change = sig, time.time()
            # done = a final state AND nothing moved for idle_s AND no hook process alive
            if st["state"] in ("final", "error_final") and not hook and time.time() - last_change >= a.idle_s:
                done_at = time.time()
                break
            time.sleep(0.2)
        res["done"] = done_at is not None
        res["wall_to_done_s"] = round((done_at or time.time()) - t_enter, 2)
        ents = read_entries(sess_dir)
        res["final_state"] = tail_state(ents)
        res["entries"] = sess_stats(ents)["types"]
        # (c) exit: Ctrl-D on the empty editor; fallback /quit
        t_x = time.time()
        pane.key("C-d")
        gone = False
        for _ in range(60):
            time.sleep(0.1)
            if "__PANE_EXIT_" in pane.text():
                gone = True
                break
        if not gone:
            pane.type("/quit")
            time.sleep(0.4)
            pane.key("Enter")
            for _ in range(60):
                time.sleep(0.1)
                if "__PANE_EXIT_" in pane.text():
                    gone = True
                    res["problems"].append("Ctrl-D did not exit; /quit did")
                    break
        res["exit_clean"] = gone and "__PANE_EXIT_0__" in pane.text()
        res["exit_s"] = round(time.time() - t_x, 2)
        res["procs_left_after_exit"] = len(run("pgrep", "-u", user).stdout.split())
        open(os.path.join(out, "pane.txt"), "w").write(pane.text(hist=True))
        ents = read_entries(sess_dir)
        with open(os.path.join(out, "session.jsonl"), "w") as f:
            for e in ents:
                f.write(json.dumps(e, ensure_ascii=False) + "\n")
        # send-back facts (arm C): delay from the final assistant `stop` to the `custom_message`
        cm = [i for i, e in enumerate(ents) if e.get("type") == "custom_message"]
        res["sendbacks"] = []
        for i in cm:
            prev = [e for e in ents[:i] if e.get("type") == "message" and (e.get("message") or {}).get("role") == "assistant"]
            if prev:
                res["sendbacks"].append({"customType": ents[i].get("customType"),
                                         "after_final_assistant_s": round(iso(ents[i]["timestamp"]) - iso(prev[-1]["timestamp"]), 3)})
        evp = os.path.join(C, "tmp", "evlog.jsonl")
        if a.evlog and os.path.exists(evp):
            evs = [json.loads(x) for x in open(evp)]
            open(os.path.join(out, "evlog.jsonl"), "w").write("".join(json.dumps(e) + "\n" for e in evs))
            res["evlog_events"] = [(round(e["t"] - evs[0]["t"], 3), e["event"], e.get("role"), e.get("stop")) for e in evs]
            ae = [e["t"] for e in evs if e["event"] == "agent_end"]
            st_ = [e["t"] for e in evs if e["event"] == "agent_settled"]
            res["agent_end_to_sendback_s"] = [round(iso(ents[i]["timestamp"]) - max(x for x in ae if x <= iso(ents[i]["timestamp"])), 3)
                                              for i in cm if any(x <= iso(ents[i]["timestamp"]) for x in ae)]
            res["last_agent_settled_to_exit_s"] = round(t_x - st_[-1], 2) if st_ else None
            res["agent_settled_count"] = len(st_)
        rows = [json.loads(x) for x in open(slog)] if os.path.exists(slog) else []
        res["requests"] = len(rows)
        sb = next((r for r in rows if r["user_msgs"] >= 2), None)       # first request after a send-back
        res["sendback_request"] = ({"msg_roles": sb["msg_roles"], "last_user_head": sb["last_user_head"][:80]} if sb else None)
        res["first_request_sha256"] = {k: rows[0][k] for k in ("system_sha256", "tools_sha256", "body_sha256")} if rows else None
    finally:
        pane.kill()
        for _ in range(5):
            run("pkill", "-KILL", "-u", user)
            if run("pgrep", "-u", user).returncode != 0:
                break
            time.sleep(0.5)
        stub.terminate()
        tl.close()

    ex = res["expect"]
    fs = res["final_state"]
    want = {"plain": "final", "claim": "final", "error": "final", "errorfinal": "error_final",
            "length": "final", "abort": "final"}[a.scenario]
    ex["final_state_is_" + want] = fs == want
    ex["done_detected"] = res["done"]
    ex["exit_clean_rc0"] = res["exit_clean"]
    ex["no_process_left"] = res["procs_left_after_exit"] == 0
    if a.scenario == "claim" and a.arm == "C":
        ex["sendback_arrived_inside_run"] = len(res["sendbacks"]) >= 1 and res["sendbacks"][0]["after_final_assistant_s"] < 3
        ex["sendback_is_user_role_to_model"] = bool(res["sendback_request"]) and res["sendback_request"]["msg_roles"][-1] == "user"
        ex["solution_written_after_sendback"] = os.path.exists(os.path.join(C, "app", "solution.py"))
    if a.scenario == "claim" and a.arm == "A":
        ex["no_sendback_without_vacant"] = not res["sendbacks"]
        ex["solution_absent"] = not os.path.exists(os.path.join(C, "app", "solution.py"))
    if a.scenario in ("plain", "error"):
        ex["solution_written"] = os.path.exists(os.path.join(C, "app", "solution.py"))
    ok = all(ex.values())
    res["ok"] = ok
    json.dump(res, open(os.path.join(out, "result.json"), "w"), indent=2)
    print(json.dumps({k: res[k] for k in ("scenario", "arm", "ready_s", "done", "wall_to_done_s", "final_state",
                                           "exit_clean", "exit_s", "sendbacks", "ok")}), flush=True)
    for k, v in ex.items():
        if not v:
            print("  EXPECTATION FAILED:", k)
    if not a.keep:
        run("rm", "-rf", C)
        run("userdel", user)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
