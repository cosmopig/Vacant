import json, os, sys, tempfile, pathlib
sys.path.insert(0, "/tmp/claude-0/review_v3/src_um")
tmp = pathlib.Path(tempfile.mkdtemp(dir="/tmp/claude-0/review_v3/um"))
os.environ["HOME"] = str(tmp / "home"); (tmp / "home").mkdir()
os.environ["VACANT_HOME"] = str(tmp / "vh")
for k in ("VACANT_TRACE", "VACANT_MODE", "VACANT_HOOK_NO_STOP", "VACANT_FEEDBACK_MODE"):
    os.environ.pop(k, None)
from vacant_network.adapters import hook, install as INS
from vacant_network.trace import zerostop
import vacant_network
print("module from:", vacant_network.__file__)
zerostop._run_child = zerostop.check
p = INS.state_root() / "install.json"; p.parent.mkdir(parents=True, exist_ok=True)
p.write_text(json.dumps({"agents": {}, "mode": "evidence"}))
ASK = ("Answer the question using the files in data/. Question: what is the total amount? "
       "Write the answer to /app/answer.txt as a single number.")

# capture user_message from ended()
captured = []
orig = zerostop.ended
def spy(*a, **k):
    r = orig(*a, **k); captured.append(r); return r
zerostop.ended = spy

def run(agent):
    proj = tmp / f"app_{agent}"; (proj / "data").mkdir(parents=True)
    (proj / "data" / "sales.csv").write_text("date,amount\n2026-07-01,1200\n2026-07-02,845\n")
    sid = f"S-{agent}"
    if agent in ("claude", "codex"):
        base = {"cwd": str(proj), "session_id": sid}
        ev = lambda e, **kw: hook.handle(agent, e, {**base, **kw})
        ev("UserPromptSubmit", prompt=ASK, hook_event_name="UserPromptSubmit")
        inp = {"command": "ls data"}
        ev("PreToolUse", tool_name="Bash", tool_input=inp, tool_use_id="t1", hook_event_name="PreToolUse")
        ev("PostToolUse", tool_name="Bash", tool_input=inp, tool_use_id="t1", tool_response={"stdout": "sales.csv"}, hook_event_name="PostToolUse")
        out = ev("SessionEnd", reason="other", hook_event_name="SessionEnd")
    else:
        base = {"cwd": str(proj), "session_id": sid}
        ev = lambda e, **kw: hook.handle(agent, e, {**base, **kw})
        ev("prompt", prompt=ASK)
        inp = {"command": "ls data"}
        ev("pre_tool", tool="bash", call_id="c1", input=inp)
        ev("post_tool", tool="bash", call_id="c1", input=inp, output="sales.csv")
        out = ev("session_end", reason="quit", turn=15, budget=15)
    um = captured[-1].get("user_message") if captured else None
    print(f"== {agent}: render ->", repr(out))
    print(f"   ended() user_message present: {bool(um)}; shown in render output: {bool(um) and um in (out[0] + out[1])}")
    if um: print("   user_message:", um.replace(chr(10), ' | ')[:300])
    dm = list((tmp / 'vh').rglob('delivery.md'))
    print("   delivery.md files:", len(dm))

for a in ("pi", "claude", "codex", "opencode"):
    captured.clear()
    try:
        run(a)
    except Exception as e:
        print(a, "ERR", type(e).__name__, e)
