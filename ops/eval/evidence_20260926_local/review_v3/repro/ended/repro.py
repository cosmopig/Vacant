"""Reproduce: ended() writes 'Ended before the agent said it was done' when stop didn't append review."""
import json, os, pathlib, subprocess, sys, tempfile
sys.path.insert(0, "/home/user/Vacant")

def setup(tag):
    base = pathlib.Path(tempfile.mkdtemp(prefix=f"ended_{tag}_", dir="/tmp/claude-0/review_v3/ended"))
    home = base / "home"; home.mkdir()
    os.environ["HOME"] = str(home)
    os.environ["VACANT_HOME"] = str(base / "vh")
    for k in ("VACANT_TRACE", "VACANT_MODE", "VACANT_HOOK_NO_STOP", "VACANT_FEEDBACK_MODE"):
        os.environ.pop(k, None)
    from vacant_network.adapters import install as INS
    p = INS.state_root() / "install.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"agents": {}, "mode": "evidence"}))
    app = base / "app"; (app / "data").mkdir(parents=True)
    (app / "data" / "sales.csv").write_text("date,amount\n2026-07-01,1200\n2026-07-02,845\n")
    return app

ASK = ("Answer the question using the files in data/. Question: what is the total amount? "
       "Write the answer to /app/answer.txt as a single number.")

def ev(agent, app, event, sid="S", **kw):
    from vacant_network.adapters import hook
    out, err, code = hook.handle(agent, event, {"cwd": str(app), "session_id": sid, **kw})
    return json.loads(out) if out.strip().startswith("{") else out

def bash(agent, app, n, cmd, output="", write=None):
    inp = {"command": cmd}
    ev(agent, app, "pre_tool", tool="bash", call_id=f"c{n}", input=inp)
    for rel, c in (write or {}).items():
        (app / rel).write_text(c)
    ev(agent, app, "post_tool", tool="bash", call_id=f"c{n}", input=inp, output=output)

def note(app):
    from vacant_network.trace.recorder import Recorder
    r = Recorder(app)
    md = r.dir / "delivery.md"
    types = [e["type"] for e in r.events()]
    return (md.read_text() if md.is_file() else "<no delivery.md>"), types

from vacant_network.trace import zerostop

# --- (a) opencode run: plugin skips stop (NONINTERACTIVE), dispose sends session_end with no reason
app = setup("a_opencode")
zerostop._run_child = zerostop.check
ev("opencode", app, "prompt", prompt=ASK)
bash("opencode", app, 1, "python3 -c 'print(2045)' > /app/answer.txt", "", write={"answer.txt": "2045\n"})
# agent went idle normally (said it was done); plugin sends NO stop in `opencode run`; dispose:
print("(a) session_end ->", ev("opencode", app, "session_end"))
md, types = note(app)
print("(a) events:", types)
print("(a) delivery.md:\n" + md)

# --- (b) pi: stop check timed out -> no review event; then quit
app = setup("b_pi_timeout")
def _timeout(req):
    raise subprocess.TimeoutExpired(cmd="check", timeout=zerostop.CHECK_TIMEOUT_S)
zerostop._run_child = _timeout
ev("pi", app, "prompt", prompt=ASK)
bash("pi", app, 1, "echo 2045 > /app/answer.txt", "", write={"answer.txt": "2045\n"})
print("(b) stop ->", ev("pi", app, "stop", final_text="The answer 2045 is in /app/answer.txt.", turn=3, budget=15))
print("(b) session_end ->", ev("pi", app, "session_end", reason="quit", turn=3, budget=15))
md, types = note(app)
print("(b) events:", types)
print("(b) delivery.md:\n" + md)

# --- (b2) pi: stop child crashed (nonzero exit) -> no review
app = setup("b2_pi_crash")
def _crash(req):
    raise RuntimeError("check exited 1: boom")
zerostop._run_child = _crash
ev("pi", app, "prompt", prompt=ASK)
bash("pi", app, 1, "echo 2045 > /app/answer.txt", "", write={"answer.txt": "2045\n"})
print("(b2) stop ->", ev("pi", app, "stop", final_text="Done."))
print("(b2) session_end ->", ev("pi", app, "session_end", reason="quit"))
md, types = note(app)
print("(b2) delivery.md head:", [l for l in md.splitlines() if l.startswith("- ")])

# --- control: stop ran normally -> no ended note
app = setup("ctl")
zerostop._run_child = zerostop.check
ev("pi", app, "prompt", prompt=ASK)
bash("pi", app, 1, "echo 2045 > /app/answer.txt", "", write={"answer.txt": "2045\n"})
print("(ctl) stop ->", ev("pi", app, "stop", final_text="The answer is in /app/answer.txt."))
ev("pi", app, "session_end", reason="quit")
md, types = note(app)
print("(ctl) events:", types, "| ended-head in note:", "Ended before" in md)
