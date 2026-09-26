"""Benchmark: session_end hook cost in zero-config mode at 11f91f87, vs chain size.
Split into zerostop.ended() time and the rest (_trace(session_end) etc.)."""
import json, os, pathlib, sys, time, shutil

BASE = pathlib.Path("/tmp/claude-0/review_v3/f_sessend/run")
if BASE.exists():
    shutil.rmtree(BASE)
(BASE / "home").mkdir(parents=True)
os.environ["HOME"] = str(BASE / "home")
os.environ["VACANT_HOME"] = str(BASE / "vh")
for k in ("VACANT_TRACE", "VACANT_MODE", "VACANT_HOOK_NO_STOP", "VACANT_FEEDBACK_MODE"):
    os.environ.pop(k, None)
sys.path.insert(0, "/tmp/claude-0/review_v3/f_sessend")

from vacant_network.adapters import hook, install as INS
from vacant_network.trace import zerostop
from vacant_network.trace.recorder import Recorder

p = INS.state_root() / "install.json"
p.parent.mkdir(parents=True, exist_ok=True)
p.write_text(json.dumps({"agents": {}, "mode": "evidence"}))
zerostop._run_child = zerostop.check     # in-process (no python startup)

proj = BASE / "proj"
(proj / "data").mkdir(parents=True)
(proj / "data" / "sales.csv").write_text("date,amount\n2026-07-01,1200\n2026-07-02,845\n")
ASK = ("Answer the question using the files in data/. Question: what is the total amount? "
       "Write the answer to answer.txt as a single number.")

AGENT = sys.argv[1] if len(sys.argv) > 1 else "codex"
targets = [int(x) for x in (sys.argv[2] if len(sys.argv) > 2 else "2000,5000,10000,20000").split(",")]

_t_ended = [0.0]
_orig_ended = zerostop.ended
def timed_ended(*a, **k):
    t = time.perf_counter()
    try:
        return _orig_ended(*a, **k)
    finally:
        _t_ended[0] = time.perf_counter() - t
zerostop.ended = timed_ended

def h(event, sid, **kw):
    return hook.handle(AGENT, event, {"cwd": str(proj), "session_id": sid,
                                      "hook_event_name": event, **kw})

n = 0
def session(sid, steps, stop=True, end=True):
    global n
    h("UserPromptSubmit", sid, prompt=ASK)
    for i in range(steps):
        n += 1
        inp = {"command": f"cat data/sales.csv | head -{i % 5 + 1}"}
        h("PreToolUse", sid, tool_name="Bash", tool_input=inp, tool_use_id=f"{sid}-t{i}")
        h("PostToolUse", sid, tool_name="Bash", tool_input=inp, tool_use_id=f"{sid}-t{i}",
          tool_response={"stdout": "date,amount\n2026-07-01,1200", "stderr": ""})
    t_stop = None
    if stop:
        t = time.perf_counter()
        h("Stop", sid, last_assistant_message="The total is 2045.")
        t_stop = time.perf_counter() - t
    t_end = None
    if end:
        _t_ended[0] = 0.0
        t = time.perf_counter()
        h("SessionEnd", sid, reason="other")
        t_end = time.perf_counter() - t
    return t_stop, t_end

rec = Recorder(proj.resolve())
def _count():
    return sum(1 for _ in open(rec.chain_path, 'rb')) if rec.chain_path.is_file() else 0
s = 0
t0 = time.time()
for tgt in targets:
    while _count() < tgt:
        s += 1
        session(f"bulk{s}", 150, stop=False, end=True)
    s += 1
    ts, te = session(f"meas{s}", 5, stop=True, end=True)
    ev_n = sum(1 for _ in open(rec.chain_path, "rb"))
    print(json.dumps({"agent": AGENT, "chain_events": ev_n,
                      "stop_s": round(ts, 3), "session_end_total_s": round(te, 3),
                      "ended_s": round(_t_ended[0], 3),
                      "rest_s": round(te - _t_ended[0], 3),
                      "chain_bytes": rec.chain_path.stat().st_size,
                      "elapsed_build_s": round(time.time() - t0, 1)}), flush=True)
# check what ended returned for the last session
evs = Recorder(proj.resolve()).events()
print("last types:", [e["type"] for e in evs[-6:]])
