#!/usr/bin/env python3
"""wave2.py — the R535 three-arm design, run against a real agent.

Why this bank and not the previous one
-------------------------------------
The R534-style bank I ran first hit a ceiling: unaided, the agent already
passed 19/20 hidden checks, so there was no headroom for a gate to move. R535
was purpose-built for exactly that failure mode. Its manifest states the design
intent verbatim: S1 targets a >=0.8 first-attempt visible-fail rate and S2
0.4-0.8, so that "a single shot fails but a retry has a chance to recover" is
a property of the BANK rather than of luck. The manifest also states that the
expected rate is a design intent, not a measurement, and that both must be
reported side by side. That is done at the end.

Arms (the manifest's own logic, including its ceiling arm)
---------------------------------------------------------
PC    ceiling.  workspace task file = TASK_explicit.md (renamed to TASK.md),
      1 attempt, no gate, no retry. Without it, "the loop did not help" has
      two indistinguishable explanations: the agent saw the feedback and did not
      act on it, versus it could not write the function even when told plainly.
      PC cuts the second one. The manifest's own rule: PC < 0.5 => the stratum
      is CEILING_TOO_LOW and the pipeline question was never posed.

RP0   floor.    workspace task file = TASK.md (interface NOT given), 1 attempt,
      no gate, no retry. This is "the agent unaided".

RPL   treatment. Same TASK.md as RP0. After each attempt the candidate is frozen
      and the PINNED VISIBLE suite is re-run on the frozen copy; on a
      non-accepting verdict the next attempt is a FRESH full native session
      whose prompt carries the visible suite's own failure text. Up to
      --max-attempts, matching `vacant run --retry revise`'s default ceiling.
      The gate itself is the 3.7 branch's native acceptance bridge
      (prepare/judge/release), so accept/refuse/release is a signed decision
      over a content-addressed artifact, not a convention.

      The loop is written out here rather than borrowed, because the branch's
      own repair mode depends on a native Stop hook that opencode does not
      provide (measured: see OPENCODE_STOP_GAP below). What is NOT written out
      here is the gate: judging, freezing and release all come from the branch.

Ruler
-----
`vacant_network.vrun.acceptance.run_suite` with suite="hidden" -- the exact
runner the R535 manifest names (`不准另寫第二把尺`). No second ruler exists in
this file.

Red lines honoured
------------------
* The hidden tree is copied into a fresh grading directory together with the
  candidate, only after the arm finished. It is never inside a workspace and
  never appears in any prompt.
* Feedback is the VISIBLE suite's own failure text. Hidden checks are never
  quoted back (repo rule A4).
* A refusal is a failure and stays in the denominator. A run that produced no
  file is a failure, not a missing observation.
* PC and RP are single-shot by design. RPL's extra attempts are recorded, and
  the report shows RPL's attempt count so "it spent more" is never read as
  "it was better at the same budget".
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent
BANK = ROOT / "r535_bank"
BRIDGE = ROOT / "bridge" / "native_acceptance_bridge.py"
OUT = ROOT / "runs2"
PY = sys.executable

OPENCODE = os.path.expanduser("~/.opencode/bin/opencode")
MODEL = os.environ.get("WAVE2_MODEL", "openrouter/stealth/space-bunny-alpha")

BASE_PROMPT = (
    "Read TASK.md and do what it says. Write the file it names in this "
    "directory. Finish when the file is saved."
)


def sh(cmd, cwd=None, timeout=None, env=None):
    return subprocess.run(cmd, shell=isinstance(cmd, str), cwd=cwd, env=env,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          timeout=timeout)


def task_ids(stratum=None, only=None, limit=None):
    if only:
        return only.split(",")
    # only real task dirs: the bank also carries a `_verify` scratch dir
    ds = sorted(p.name for p in BANK.iterdir()
                 if p.is_dir() and (p.name.startswith("s1_") or p.name.startswith("s2_")))
    if stratum:
        ds = [d for d in ds if d.startswith(stratum.lower() + "_")]
    return ds[:limit] if limit else ds


def stage(ws: pathlib.Path, tid: str, template: str) -> None:
    """The workspace is the task file and nothing else.

    tests_visible/ and hidden/ never enter it. That is not tidiness: `vacant run`
    refuses a --suite under the workspace ("agent 改得到的驗收不是驗收"), and the
    R535 manifest records that the R534 layout, which put tests_visible/ inside
    the workspace, is why its gate had nothing to intercept.
    """
    ws.mkdir(parents=True)
    shutil.copy2(BANK / tid / template, ws / "TASK.md")
    # A self-contained project, so the agent cannot wander outside the task.
    subprocess.run(["git", "init", "-q"], cwd=ws, stdout=subprocess.DEVNULL,
                   stderr=subprocess.DEVNULL)


def visible_detail(judge: dict, limit: int = 1800) -> str:
    """The visible suite's own failure text. Nothing else."""
    parts = []
    for r in judge.get("results", []):
        if r.get("status") == "PASS":
            continue
        d = str(r.get("detail") or "")
        parts.append(d)
    return "\n".join(parts)[:limit]


def run_attempt(ws, prompt, out_prefix, timeout):
    env = dict(os.environ)
    env["OPENROUTER_API_KEY"] = (ROOT / ".openrouter_key").read_text().strip()
    t0 = time.time()
    timed_out = False
    try:
        # --dir and git init, exactly as vacant_network/adapters/agents.py::
        # opencode_build does it. Passing cwd alone is NOT enough: opencode picks
        # its own project root, and with no .git anywhere above it, the observed
        # behaviour was to run against a parent directory and report "there is no
        # TASK.md in the working directory".
        p = subprocess.run(
            [OPENCODE, "run", "--format", "json", "--dir", str(ws),
             "-m", MODEL, prompt],
            cwd=ws, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=timeout)
        out, err, rc = p.stdout, p.stderr, p.returncode
    except subprocess.TimeoutExpired as e:
        timed_out = True
        out, err, rc = (e.stdout or b""), (e.stderr or b""), 124
    (out_prefix.with_suffix(".agent.jsonl")).write_bytes(out)
    (out_prefix.with_suffix(".agent.err")).write_bytes(err)
    return rc, timed_out, round(time.time() - t0, 1)


def grade(tid: str, cell: pathlib.Path) -> dict:
    """Score with the repo's own ruler. Hidden is copied in only now."""
    sol = cell / "workspace" / "solution.py"
    with tempfile.TemporaryDirectory(prefix="w2g_") as td:
        ws = pathlib.Path(td)
        if sol.is_file():
            shutil.copy2(sol, ws / "solution.py")
        # run_suite copies the suite itself into verify_root and cleans up
        code = (
            "import json,sys,pathlib\n"
            "from vacant_network.vrun.acceptance import run_suite\n"
            "from vacant_network.vrun.sandbox import Sandbox\n"
            f"ws=pathlib.Path({str(ws)!r})\n"
            f"suite=pathlib.Path({str(BANK / tid / 'hidden')!r})\n"
            f"vr=pathlib.Path({str(ws / '_vr')!r})\n"
            "s=Sandbox()\n"
            "r=run_suite(s, ws, suite, suite='hidden', task_id=%r, verify_root=vr)\n"
            "print('<<<G>>>'+json.dumps(r, default=str))\n" % tid)
        p = subprocess.run([PY, "-c", code], stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE, text=True, timeout=600)
    raw = ""
    for line in p.stdout.splitlines():
        if line.startswith("<<<G>>>"):
            raw = line[7:]
    if not raw:
        return {"hidden_pass": False, "grader_error": True,
                "grader_stderr": p.stderr[-400:],
                "has_solution": sol.is_file()}
    r = json.loads(raw)
    return {"hidden_pass": bool(r.get("all_pass")),
            "checks_total": r.get("total"), "checks_passed": r.get("passed"),
            "has_solution": sol.is_file()}


def arm_pc(tid, timeout):
    cell = OUT / f"{tid}__PC"
    shutil.rmtree(cell, ignore_errors=True)
    cell.mkdir(parents=True)
    ws = cell / "workspace"
    stage(ws, tid, "TASK_explicit.md")
    rc, to, wall = run_attempt(ws, BASE_PROMPT, cell / "a1", timeout)
    g = grade(tid, cell)
    rec = {"task": tid, "arm": "PC", "attempts": 1, "agent_rc": rc,
           "timed_out": to, "wall_s": wall, "gate_verdict": "none (ceiling arm)",
           "delivered": g["has_solution"], **g}
    rec["correct"] = bool(rec["delivered"] and rec.get("hidden_pass"))
    (cell / "rec.json").write_text(json.dumps(rec, indent=2, ensure_ascii=False))
    return rec


def arm_rp0(tid, timeout):
    cell = OUT / f"{tid}__RP0"
    shutil.rmtree(cell, ignore_errors=True)
    cell.mkdir(parents=True)
    ws = cell / "workspace"
    stage(ws, tid, "TASK.md")
    rc, to, wall = run_attempt(ws, BASE_PROMPT, cell / "a1", timeout)
    g = grade(tid, cell)
    rec = {"task": tid, "arm": "RP0", "attempts": 1, "agent_rc": rc,
           "timed_out": to, "wall_s": wall, "gate_verdict": "none (no gate)",
           "delivered": g["has_solution"], **g}
    rec["correct"] = bool(rec["delivered"] and rec.get("hidden_pass"))
    (cell / "rec.json").write_text(json.dumps(rec, indent=2, ensure_ascii=False))
    return rec


def arm_rpn(tid, timeout, max_attempts):
    """RETRY-NOSUITE：RPL 的預算對照，**沒有任何可見套件**。

    為什麼非有不可（`decisions/reviews/C5_NATIVE_ACCEPTANCE_20260928/README.md`
    §7 與 FINDINGS §「實驗設計」逐字）：RPL 的第 1 次嘗試就是 RP0 的那一跑，
    而 RPL 平均用了 1.79 次。於是 RPL 對 RP0 的差距裡，同時混著兩件事——
    「回饋讓 agent 修對了東西」與「它只是多跑了 0.79 次」。這個設計是**巢狀**的，
    所以直接拿 RPL 對 RP0 做 McNemar 會把嘗試次數一起算進去。

    這一臂把嘗試次數與 session 形狀對齊，只拿掉回饋：

      * 同樣的上限、同樣「每次全新原生 session」、同樣的時限；
      * 沒有可見套件、沒有閘門、沒有裁決、沒有 release；
      * 失敗時下一個提示詞只說「再做一次」，不含任何驗收內容。

    RPL − RPN 才是「回饋的邊際貢獻」；RPN − RP0 是「只是多跑幾次」的貢獻。
    兩者分開報，不合加成一個數字。
    """
    cell = OUT / f"{tid}__RPN"
    shutil.rmtree(cell, ignore_errors=True)
    cell.mkdir(parents=True)
    ws = cell / "workspace"
    stage(ws, tid, "TASK.md")
    env = dict(os.environ)
    env["OPENROUTER_API_KEY"] = (ROOT / ".openrouter_key").read_text().strip()
    attempts_used, total_wall = 0, 0.0
    rc, timed_out = None, False
    for n in range(1, max_attempts + 1):
        rc, timed_out, wall = run_attempt(ws, BASE_PROMPT, cell / f"a{n}", timeout)
        total_wall += wall
        attempts_used = n
        sol = ws / "solution.py"
        # A file exists, but RPN deliberately never checks it: the whole point is
        # that this arm has no acceptance signal at all.
        if sol.is_file() and sol.stat().st_size > 0:
            break
    g = grade(tid, cell)
    rec = {"task": tid, "arm": "RPN", "attempts": attempts_used,
           "wall_s": round(total_wall, 1), "agent_rc": rc, "timed_out": timed_out,
           "judge_outcome": None, "refusal_reason": None,
           "gate_verdict": "none (budget-matched control, no suite at all)",
           "delivered": g["has_solution"], **g}
    rec["correct"] = bool(rec["delivered"] and rec.get("hidden_pass"))
    (cell / "rec.json").write_text(json.dumps(rec, indent=2, ensure_ascii=False))
    return rec


def arm_rpl(tid, timeout, max_attempts):
    """Gate + fresh-session retry, with the visible suite's feedback in-prompt."""
    cell = OUT / f"{tid}__RPL"
    rh = ROOT / "receivers2" / tid
    # prepare pins a read-only suite at <receiver_home>-suite and refuses to
    # overwrite it, so a re-run must clear that sibling too, not just the home.
    shutil.rmtree(rh, ignore_errors=True)
    shutil.rmtree(rh.with_name(rh.name + "-suite"), ignore_errors=True)
    shutil.rmtree(cell, ignore_errors=True)
    cell.mkdir(parents=True)
    ws = cell / "workspace"
    stage(ws, tid, "TASK.md")

    prep = sh([PY, str(BRIDGE), "prepare", "--workspace", str(ws), "--task-id", tid,
               "--mode", "conform", "--attempts", str(max_attempts),
               "--suite", str(BANK / tid / "tests_visible"),
               "--receiver-home", str(rh), "--insecure-same-account"],
              timeout=300)
    (cell / "prepare.json").write_bytes(prep.stdout)
    (cell / "prepare.err").write_bytes(prep.stderr)
    if prep.returncode != 0:
        rec = {"task": tid, "arm": "RPL", "prepare_failed": True,
               "prepare_err": prep.stderr.decode(errors="replace")[-400:],
               "attempts": 0, "delivered": False, "hidden_pass": False,
               "correct": False, "gate_verdict": "prepare failed (infra)"}
        (cell / "rec.json").write_text(json.dumps(rec, indent=2, ensure_ascii=False))
        return rec

    # The real `vacant loop`, not a reimplementation of it: the loop under test
    # must be the one that ships. Its check is the bridge's prepare/judge/release
    # path, wired through VACANT_INTAKE_ROOT + VACANT_CONTRACT_PATH because the
    # bridge keeps the signed contract one level above the intake root.
    env = dict(os.environ)
    env["OPENROUTER_API_KEY"] = (ROOT / ".openrouter_key").read_text().strip()
    env["VACANT_INTAKE_ROOT"] = str(rh / "intake")
    env["VACANT_CONTRACT_PATH"] = str(rh / "contract.json")
    loop_json = cell / "loop.json"
    r = sh([str(ROOT / "venv" / "bin" / "vacant"), "loop",
            "--workspace", str(ws), "--suite", str(BANK / tid / "tests_visible"),
            "--attempts", str(max_attempts), "--feedback", "prompt",
            "--timeout", str(timeout), "--intake-root", str(rh / "intake"),
            "--json", "--",
            OPENCODE, "run", "--format", "json", "--dir", str(ws),
            "-m", MODEL, BASE_PROMPT],
           env=env, timeout=timeout * max_attempts + 900)
    (cell / "loop.stdout").write_bytes(r.stdout)
    (cell / "loop.stderr").write_bytes(r.stderr)
    (loop_json).write_bytes(r.stdout)
    try:
        lr = json.loads(r.stdout)
    except Exception:
        lr = {}
    delivered = lr.get("verdict") == "accept"
    outcome = "accept" if delivered else "exhausted"
    attempt = lr.get("attempts_used", 0)
    g = grade(tid, cell)
    rec = {"task": tid, "arm": "RPL", "attempts": attempt,
           "loop_exit": r.returncode, "loop_verdict": lr.get("verdict"),
           "attempts_detail": lr.get("attempts", []),
           "wall_s": lr.get("wall_s"),
           "judge_outcome": outcome,
           "refusal_reason": None if delivered else str(lr.get("verdict")),
           "gate_verdict": "vacant loop: {}".format(lr.get("verdict")),
           "delivered": delivered, **g}
    rec["correct"] = bool(delivered and rec.get("hidden_pass"))
    (cell / "rec.json").write_text(json.dumps(rec, indent=2, ensure_ascii=False))
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", required=True, choices=["PC", "RP0", "RPL", "RPN"])
    ap.add_argument("--task", default=None)
    ap.add_argument("--stratum", default=None, choices=["S1", "S2", None])
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--timeout", type=float, default=600.0)
    ap.add_argument("--max-attempts", type=int, default=3)
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    for tid in task_ids(a.stratum, a.task, a.limit):
        try:
            if a.arm == "PC":
                r = arm_pc(tid, a.timeout)
            elif a.arm == "RP0":
                r = arm_rp0(tid, a.timeout)
            elif a.arm == "RPN":
                r = arm_rpn(tid, a.timeout, a.max_attempts)
            else:
                r = arm_rpl(tid, a.timeout, a.max_attempts)
            print(json.dumps({k: r.get(k) for k in
                              ("task", "arm", "attempts", "delivered",
                               "hidden_pass", "correct", "judge_outcome",
                               "wall_s", "gate_verdict")}, ensure_ascii=False),
                  flush=True)
        except Exception as e:
            print(json.dumps({"task": tid, "arm": a.arm, "error": repr(e)[:300]},
                             ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
