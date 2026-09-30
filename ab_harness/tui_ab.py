#!/usr/bin/env python3
"""tui_ab.py — the A/B, run through pi's REAL interactive TUI.

Why the TUI and not `pi -p`
---------------------------
`pi -p` is a different code path (the non-interactive mode), so a headless run
says nothing about the interactive interface -- and the interactive interface is
the thing being measured. Each cell here is a real tmux session with a real
terminal size, driven by real keystrokes, and the agent's answer comes back the
way a person's would: rendered in the pane.

Arms
----
A  plain     pi with NO Vacant extension at all. One turn.
B  gate      pi + Vacant, feedback OFF (the shipped default). One turn. This is
             what "open pi and it's on" gives you with no configuration: the
             gate judges at settle and says so.
C  loop      pi + Vacant, VACANT_PI_GATE_FEEDBACK=revise, up to 3 rounds. The
             failure text goes back into the same session and the agent gets to
             act on it.

B and C differ ONLY in the feedback flag, so C - B is the feedback's marginal
value, which is the number the earlier opencode batch could not separate.

What is measured
----------------
  settled       the agent finished a turn and the gate spoke (B/C), or the turn
                ended (A)
  gate_verdict  what the gate said, read out of the TUI
  delivered     the gate accepted (B/C) -- arm A has no gate
  hidden_pass   scored afterwards from the hidden tree, never in any pane
  rounds        how many settle rounds it took (C)

Honest bounds carried into the report
-------------------------------------
* The interactive gate MARKS; it does not block. Files stay in the workspace.
  "delivered" here means the gate accepted, not that anything was withheld.
* arm A has no gate, so "delivered" is vacuously true there. That is the point of
  the contrast, not a confound.
* The B/C grade the agent can SEE (the visible suite lives in the workspace, which
  is what an interactive user has). The hidden tree is only ever used for scoring
  after the session is over.
* "未認證（級別 B'）" in the pane is the repo's own grading saying the model
  channel was only partially mediated. It is recorded, not explained away.
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import time

ROOT = pathlib.Path("/home/user1/ab-20260928")
BANK = ROOT / "r535_bank"
OUT = ROOT / "runs_tui"
TUI = ROOT / "tui.sh"
PY_EXE = ROOT / "venv" / "bin" / "python"
UPSTREAM = "http://100.86.226.21:1234/v1"
MODEL = "gemma-4-12b-it-qat"
PI_ENV_EXT = pathlib.Path("/tmp/pi_ext_with_vacant")     # arm B/C
PI_ENV_PLAIN = pathlib.Path("/tmp/pi_ext_plain")          # arm A

PROMPT = ("Read TASK.md, then write solution.py so the checks in tests_visible/ "
          "pass. Verify with: sh run_tests.sh")
#
# A voided turn is re-run from a clean workspace, never scored. Two is enough to
# separate "this pi session stalls sometimes" from "this arm always stalls".
MAX_ATTEMPTS = 3


def sh(*args, **kw):
    return subprocess.run(list(args), capture_output=True, text=True,
                          timeout=kw.get("timeout", 300))


def stage_agent_dir(arm: str) -> pathlib.Path:
    """Each arm gets its own PI_CODING_AGENT_DIR so 'no Vacant' really means none.

    Uninstalling between every cell would be slow and would leave the system in a
    different state each time. A per-arm agent dir differs in exactly one thing:
    whether extensions/vacant.ts is present.
    """
    src = pathlib.Path.home() / ".pi" / "agent"
    d = PI_ENV_PLAIN if arm == "A" else PI_ENV_EXT
    shutil.rmtree(d, ignore_errors=True)
    d.mkdir(parents=True)
    for f in ("models.json", "auth.json"):
        if (src / f).is_file():
            shutil.copy2(src / f, d / f)
    if arm != "A":
        (d / "extensions").mkdir(exist_ok=True)
        shutil.copy2(src / "extensions" / "vacant.ts", d / "extensions" / "vacant.ts")
    # ⚠ THIS IS THE WHOLE A/B, AND I GOT IT WRONG THE FIRST TIME.
    #   Writing `models.json` does not make pi SELECT that provider. Without a
    #   launch-time pin pi uses its own default, which in the measured run landed
    #   on `openrouter`/`moonshotai/kimi-k2.6` — a different model, a different
    #   host, and not one byte through this run's proxy. Arm A therefore scored a
    #   model failure as an agent failure. The repo already hit this on
    #   2026-09-22 and wrote the same note at gateshim.py:578-582.
    #   `settings.json`'s defaultProvider/defaultModel is pi's documented startup
    #   default, so pin it in EVERY arm. Arms B/C also get the extension's
    #   setModel() call, but the pin is what makes the three arms comparable --
    #   the only intended difference between them is the extension file.
    (d / "settings.json").write_text(json.dumps({
        "defaultProvider": "lms1004", "defaultModel": MODEL,
        "lastChangelogVersion": "0.87.1"}, indent=2), encoding="utf-8")
    return d


def stage_workspace(tid: str) -> pathlib.Path:
    ws = OUT / f"{tid}__ws"
    shutil.rmtree(ws, ignore_errors=True)
    ws.mkdir(parents=True)
    (ws / "TASK.md").write_bytes((BANK / tid / "TASK.md").read_bytes())
    tv = ws / "tests_visible"
    tv.mkdir()
    shutil.copy2(BANK / tid / "tests_visible" / "test_visible.py", tv / "test_visible.py")
    sh("git", "init", "-q", cwd=ws)
    return ws


def pane(sess: str) -> str:
    return subprocess.run([str(TUI), "pane", sess], capture_output=True,
                          text=True, timeout=60).stdout


def scrollback(sess: str, lines: int = 4000) -> str:
    """The WHOLE scrollback, not just the visible pane.

    tui.sh `pane` captures only the visible ~50 lines. That is not enough for arm
    C, which is the only arm that runs several settle rounds: the verdicts from
    earlier rounds scroll out of view, so the loop's own per-round judgements --
    the variable being measured -- would be silently lost. Read the history.
    """
    return subprocess.run(
        ["tmux", "capture-pane", "-p", "-S", f"-{lines}", "-t", sess],
        capture_output=True, text=True, timeout=60).stdout


def wait_for_settle(sess: str, arm: str, limit: int) -> tuple[str, str]:
    """Wait until the turn is over. Returns (outcome, pane).

    The rule that works for a multi-round session: **the turn is over when the
    TUI has been idle, not when the gate first speaks.**

    I first wrote "B/C settle on the first gate banner" and it was wrong twice
    over. On the first smoke run it fired before the agent had written anything
    and scored the cell as a failure. Once stalls were added it fired on arm C's
    FIRST round banner; because arm C then starts its next round, the final
    snapshot caught round 2 still thinking -- tokens frozen at `↑5.9k ↓79` --
    while round 1's verdict had already scrolled out of the visible pane. The
    cell read `settled: true` with `gate_accepted: null`. Both halves of that
    were the harness lying, not the arm.

    So: poll the full scrollback, count gate banners, and settle only once the
    working indicator has been gone for several polls. Every round's banner
    passes through the history, so both the count and the per-round text are
    recoverable afterwards.

    outcome is one of:
      settled   the turn finished and (for B/C) the gate spoke at least once
      stalled   the turn never finished -- working indicator up, token counter frozen
      timeout   no idle state within `limit` polls

    A stalled turn is NOT an agent failure and is never scored as one. The
    measured cause was a pi session that stopped mid-turn after the model called
    a tool that does not exist (`ls_r`), fell back to a shell call, and then
    produced nothing more while the backend itself stayed healthy (a 2s
    `say ok` immediately after). A failed model call is neither a right answer
    nor a wrong one; it is a void, and a void is re-run, not counted.
    """
    # ⚠ The gate prints a PROLOGUE first: `Vacant 閘門：驗收來源 dir:tests_visible
    #   （…）；快照 sha256 …`. That line starts with the same prefix as a verdict
    #   but carries no verdict. Matching it made `saw_gate` true before the gate
    #   had judged anything, so arm C reported `settled` right after the prologue
    #   and every cell came back with `gate_accepted: null` and a truncated
    #   "banner" that was the prologue. A real verdict always carries a mark:
    #   `✓` accepted, `✗` refused, `⚠` infra_void. Require the mark.
    gate_re = re.compile(r"Vacant 閘門[:：]\s*[✓✗⚠]")
    work_re = re.compile(r"[⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏]\s*Working")
    tok_re = re.compile(r"[↑↓]\d+[^\n]{0,24}")
    idle_for = 0
    frozen_tok: str | None = None
    frozen_for = 0
    last = ""
    saw_gate = False
    for _ in range(limit):
        time.sleep(3)
        p = scrollback(sess)
        if gate_re.search(p):
            saw_gate = True
        working = bool(work_re.search(p))
        idle_for = 0 if working else idle_for + 1
        if idle_for >= 4 and (saw_gate or arm == "A"):
            return "settled", p
        # stall, for every arm: still working but the token counter has not moved
        mt = tok_re.findall(p)
        tl = mt[-1] if mt else ""
        if working and tl == frozen_tok:
            frozen_for += 1
            if frozen_for >= 12:          # ~36s of a frozen counter while working
                return "stalled", p
        else:
            frozen_for, frozen_tok = 0, (tl if working else None)
        last = p
    return "timeout", last


def read_verdict(p: str) -> dict:
    """Read every gate verdict out of the scrollback, not just the first.

    Arm C speaks the gate once per settle round, so the pane holds a sequence of
    banners. The verdict that decides the cell is the LAST one; the sequence is
    kept in `gate_rounds` because "how many rejections before it accepted" is the
    thing the loop arm exists to measure. Taking only the first match (as this
    did) would have reported arm C's first rejection as its result.
    """
    out: dict[str, object] = {}
    # Only verdict lines. See the note on `gate_re` in wait_for_settle: the
    # prologue shares the prefix and is not a decision.
    banners = re.findall(r"Vacant 閘門[:：]\s*[✓✗⚠]\s*([^\n]*)", p)
    if banners:
        out["gate_rounds"] = len(banners)
        out["gate_banner"] = banners[-1].strip()[:220]
        out["gate_banner_all"] = [b.strip()[:160] for b in banners]
    m2 = re.findall(r"可見驗收全過（(\d+)/(\d+)）", p)
    m3 = re.findall(r"拒交裁決（([a-z_]+)[，,]\s*可見驗收 (\d+)/(\d+)）", p)
    # ⚠ Decide once, from the LAST banner, and let `visible` follow that decision.
    #   Setting `visible` from the last accept and then overwriting it with the
    #   last reject reported `1/2` on a cell whose final round was `2/2` -- the two
    #   fields disagreed with each other inside one record, which is exactly the
    #   kind of self-contradiction that must not survive into a report.
    if banners:
        last = banners[-1]
        if "可見驗收全過" in last:
            out["gate_accepted"] = True
        elif m3:
            out["gate_accepted"] = False
            out["stop_reason"] = m3[-1][0]
        # The two banner shapes are not the same string. Accepted reads
        # `可見驗收全過（2/2）`; rejected reads `可見驗收 0/2）` -- a comma, a
        # space, and NO opening paren, because the paren was already spent on the
        # stop reason. A regex written for the accept shape alone returns None on
        # every reject, which is how a rejected cell ended up with no `visible`
        # at all. Both the full-width and half-width bracket are tolerated.
        vis = re.search(r"可見驗收(?:全過)?\s*[（(]?\s*(\d+)\s*/\s*(\d+)\s*[）)]", last)
        if vis:
            out["visible"] = f"{vis.group(1)}/{vis.group(2)}"
    elif m2:
        out["gate_accepted"] = True
        out["visible"] = f"{m2[-1][0]}/{m2[-1][1]}"
    elif m3:
        out["gate_accepted"] = False
        out["stop_reason"] = m3[-1][0]
        out["visible"] = f"{m3[-1][1]}/{m3[-1][2]}"
    m4 = re.findall(r"wire (\d+) 通", p)
    if m4:
        out["wire_calls"] = int(m4[-1])
    m5 = re.findall(r"收據 (\S+)", p)
    if m5:
        out["receipt_dir"] = m5[-1]
    m6 = re.findall(r"未認證（級別 ([A-Z']+)）", p)
    if m6:
        out["tier"] = m6[-1]
    if "infra_void" in p:
        out["infra_void"] = True
    # The model/provider the TUI status line reports for the turn that ran.
    # Recorded per cell so the report can REFUSE to compare cells that did not
    # run the same model -- that check is what would have caught arm A silently
    # running moonshotai/kimi-k2.6 while the plan said gemma-4-12b-it-qat.
    ms = re.findall(r"\(([a-z0-9_]+)\)\s+([A-Za-z0-9._/\-]+)", p)
    if ms:
        prov, mod = ms[-1]
        out["seen_provider"], out["seen_model"] = prov, mod
    mp = re.findall(r"([a-z0-9_]+)/([A-Za-z0-9._/\-]+)\s+•", p)
    if mp:
        out["seen_provider"], out["seen_model"] = mp[-1]
    return out


def grade(tid: str, ws: pathlib.Path) -> dict:
    """Hidden scoring, strictly after the session. Never in the pane."""
    sol = ws / "solution.py"
    code = (
        "import json,pathlib,sys,tempfile,shutil\n"
        "from vacant_network.vrun.acceptance import run_suite\n"
        "from vacant_network.vrun.sandbox import Sandbox\n"
        f"sol=pathlib.Path({str(sol)!r})\n"
        f"suite=pathlib.Path({str(BANK / tid / 'hidden')!r})\n"
        "td=tempfile.mkdtemp()\n"
        "g=pathlib.Path(td)\n"
        "if sol.is_file(): shutil.copy2(sol, g/'solution.py')\n"
        "r=run_suite(Sandbox(), g, suite, suite='hidden', task_id=%r,"
        " verify_root=g/'_v')\n"
        "print('<<<G>>>'+json.dumps(r, default=str))\n" % tid)
    p = subprocess.run([str(PY_EXE), "-c", code], capture_output=True, text=True,
                       timeout=600, cwd=str(ROOT))
    raw = ""
    for line in p.stdout.splitlines():
        if line.startswith("<<<G>>>"):
            raw = line[7:]
    if not raw:
        return {"hidden_pass": False, "grader_error": p.stderr[-300:],
                "has_solution": sol.is_file()}
    r = json.loads(raw)
    return {"hidden_pass": bool(r.get("all_pass")),
            "checks_total": r.get("total"), "checks_passed": r.get("passed"),
            "has_solution": sol.is_file()}


def one(tid: str, arm: str, settle_limit: int) -> dict:
    """Run one cell, re-running it if the turn VOIDED rather than settled.

    A void is a stall or a timeout -- a turn that produced no judgeable outcome.
    The repo's rule is that a failed model call is neither a right answer nor a
    wrong one, so a voided cell is re-run from a clean workspace and is never
    scored. `attempts` and `voids` are recorded so the report can show them
    rather than quietly dropping them.
    """
    outcome, p = "timeout", ""
    for attempt in range(1, MAX_ATTEMPTS + 1):
        p = _one_try(tid, arm, settle_limit, attempt)
        outcome = p.pop("_outcome")
        if outcome == "settled":
            break
        # voided: clean up and try again from scratch
        subprocess.run([str(TUI), "stop", f"ab_{tid}_{arm}"], capture_output=True)
        subprocess.run([str(TUI), "stop", f"ab_{tid}_{arm}_r{attempt}"],
                       capture_output=True)
        time.sleep(5)
    cell = OUT / f"{tid}__{arm}"
    rec = json.loads((cell / "rec.json").read_text())
    rec["attempts"] = attempt
    rec["voids"] = attempt - 1
    rec["outcome"] = outcome
    if outcome != "settled":
        # A voided cell has no verdict. It must not be counted as a refusal or a
        # delivery in any rate, so both are nulled rather than defaulted.
        rec["delivered"] = None
        rec["correct"] = None
        rec["hidden_pass"] = None
        rec["VOID"] = outcome
    (cell / "rec.json").write_text(json.dumps(rec, indent=2, ensure_ascii=False))
    return rec


def _one_try(tid: str, arm: str, settle_limit: int, attempt: int) -> str:
    ws = stage_workspace(tid)
    agent_dir = stage_agent_dir(arm)
    suffix = "" if attempt == 1 else f"_r{attempt}"
    sess = f"ab_{tid}_{arm}{suffix}"
    env = {
        "PI_CODING_AGENT_DIR": str(agent_dir),
        "VACANT_AGENT_MODEL": MODEL,
        "PATH": f"{pathlib.Path.home() / '.local/bin'}:{os.environ.get('PATH','')}",
    }
    if arm == "C":
        env["VACANT_PI_GATE_FEEDBACK"] = "revise"
    cmd = "env " + " ".join(f"{k}={v}" for k, v in env.items()) + " bash -lc pi"
    subprocess.run([str(TUI), "stop", sess], capture_output=True)
    subprocess.run([str(TUI), "start", sess, str(ws), cmd], capture_output=True,
                   timeout=120)
    time.sleep(18)
    subprocess.run([str(TUI), "line", sess, PROMPT], capture_output=True, timeout=60)
    outcome, p = wait_for_settle(sess, arm, settle_limit)
    time.sleep(2)
    p = scrollback(sess)
    cell = OUT / f"{tid}__{arm}"
    cell.mkdir(parents=True, exist_ok=True)
    (cell / "pane.txt").write_text(p, encoding="utf-8")
    subprocess.run([str(TUI), "stop", sess], capture_output=True)

    v = read_verdict(p)
    # `None` is a real value here, not a missing one. `gate_accepted` is None when
    # the gate spoke an infra_void, which is neither an acceptance nor a refusal,
    # and `bool(None)` would have filed it under "refused" -- turning a void into
    # a counted failure, the one thing the repo's own infra_void rule forbids.
    if arm == "A":
        delivered: bool | None = True          # no gate; see the note in the module docstring
    else:
        delivered = v.get("gate_accepted") if "gate_accepted" in v else None
    g = grade(tid, ws)
    # hard check, recorded rather than assumed: did the turn run the planned model?
    want = MODEL
    got = v.get("seen_model")
    model_ok = (got == want) if got else None
    rec = {"task": tid, "arm": arm, "settled": outcome == "settled",
           "turn_outcome": outcome, "attempt": attempt,
           "model": MODEL, "seen_model": got, "model_ok": model_ok,
           "upstream": UPSTREAM,
           "feedback": "revise" if arm == "C" else ("off" if arm == "B" else "n/a"),
           "extension": arm != "A",
           "delivered": delivered, **v, **g}
    rec["correct"] = (bool(delivered) and rec["hidden_pass"]
                      if delivered is not None else None)
    if model_ok is False:
        rec["INVALID"] = f"ran {got}, planned {want}"
    (cell / "rec.json").write_text(json.dumps(rec, indent=2, ensure_ascii=False))
    # keep the workspace with the cell so the artefact is inspectable
    shutil.rmtree(cell / "workspace", ignore_errors=True)
    shutil.copytree(ws, cell / "workspace", dirs_exist_ok=True)
    rec["_outcome"] = outcome
    return rec


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", required=True, choices=["A", "B", "C"])
    ap.add_argument("--tasks", required=True, help="comma list of task ids")
    ap.add_argument("--settle-limit", type=int, default=100,
                    help="max 3s polls to wait for settle")
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    for tid in a.tasks.split(","):
        tid = tid.strip()
        if not tid:
            continue
        try:
            r = one(tid, a.arm, a.settle_limit)
            print(json.dumps({k: r.get(k) for k in
                              ("task", "arm", "settled", "delivered", "hidden_pass",
                               "correct", "gate_accepted", "visible", "wire_calls",
                               "seen_model", "INVALID")}, ensure_ascii=False), flush=True)
        except Exception as e:                      # noqa: BLE001
            print(json.dumps({"task": tid, "arm": a.arm,
                              "error": f"{type(e).__name__}: {e}"}), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
