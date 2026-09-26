"""Run the real hook CLI (`python -m vacant_network hook codex <Event>`) against an existing large chain,
killing SessionEnd after T seconds as Codex/Claude would; check whether session_closed was recorded."""
import json, os, pathlib, subprocess, sys, time

RUN = pathlib.Path(sys.argv[1]).resolve()          # dir with home/, vh/, proj/
SRC = sys.argv[2]                         # PYTHONPATH (11f91f87 or 7f7ec52f extract)
SID = sys.argv[3]
T = float(sys.argv[4])
PY = "/home/user/Vacant/.venv/bin/python"
env = dict(os.environ, HOME=str(RUN / "home"), VACANT_HOME=str(RUN / "vh"), PYTHONPATH=SRC)
for k in ("VACANT_TRACE", "VACANT_MODE", "VACANT_HOOK_NO_STOP", "VACANT_FEEDBACK_MODE"):
    env.pop(k, None)
proj = RUN / "proj"
ASK = ("Answer the question using the files in data/. Question: what is the total amount? "
       "Write the answer to answer.txt as a single number.")


def hook(event, timeout=None, **kw):
    payload = {"cwd": str(proj), "session_id": SID, "hook_event_name": event, **kw}
    t = time.perf_counter()
    try:
        p = subprocess.run([PY, "-m", "vacant_network", "hook", "codex", event], input=json.dumps(payload),
                           capture_output=True, text=True, env=env, timeout=timeout, cwd=str(RUN))
        return "exit", p.returncode, round(time.perf_counter() - t, 3)
    except subprocess.TimeoutExpired:
        return "KILLED", None, round(time.perf_counter() - t, 3)


print("prompt", hook("UserPromptSubmit", prompt=ASK))
for i in range(3):
    inp = {"command": f"head -{i+1} data/sales.csv"}
    hook("PreToolUse", tool_name="Bash", tool_input=inp, tool_use_id=f"{SID}-{i}")
    hook("PostToolUse", tool_name="Bash", tool_input=inp, tool_use_id=f"{SID}-{i}",
         tool_response={"stdout": "date,amount", "stderr": ""})
print("stop", hook("Stop", last_assistant_message="The total is 2045."))
# an unrecorded change after the last step (e.g. background process): only SessionEnd's close sees it
(proj / f"late_{SID}.txt").write_text("written after the last recorded step\n")
print("session_end", hook("SessionEnd", timeout=T, reason="other"))

sys.path.insert(0, SRC)
os.environ.update(HOME=env["HOME"], VACANT_HOME=env["VACANT_HOME"])
from vacant_network.trace.recorder import Recorder
evs = Recorder(proj.resolve()).events()
key = f"codex:{SID}"
mine = [e["type"] for e in evs if e.get("session") == key or
        (e.get("actor") or {}).get("session") == SID]
closed = [e for e in evs if e["type"] == "session_closed" and (e.get("actor") or {}).get("session") == SID]
gap = [e for e in evs if e["type"] == "unrecorded_change" and any(
    f"late_{SID}" in json.dumps(c) for c in e.get("changes") or [])]
print(json.dumps({"chain_events": len(evs), "session_types": mine[-6:],
                  "session_closed_recorded": bool(closed), "late_write_recorded_as_gap": bool(gap)}))
