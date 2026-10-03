import os, sys, time, json, pathlib, tempfile
sys.path.insert(0, '/tmp/claude-0/review_v3/src')
td = pathlib.Path(tempfile.mkdtemp(dir='/tmp/claude-0/review_v3/probe'))
os.environ['HOME'] = str(td/'home'); (td/'home').mkdir()
os.environ['VACANT_HOME'] = str(td/'vh')
from vacant_network.adapters import install as INS
p = INS.state_root()/'install.json'; p.parent.mkdir(parents=True, exist_ok=True)
p.write_text(json.dumps({"agents": {}, "mode": "evidence"}))
ws = td/'app'; (ws/'data').mkdir(parents=True); (ws/'data'/'s.csv').write_text('a,b\n1,2\n')
from vacant_network.adapters import hook
from vacant_network.trace.recorder import Recorder
from vacant_network.trace import zerostop
N = int(sys.argv[1])
def ev(event, sid, **kw):
    return hook.handle("codex" if event in ("PreToolUse","PostToolUse","SessionEnd","UserPromptSubmit","Stop") else "pi", event, {"cwd": str(ws), "session_id": sid, **kw})
t0=time.time()
# old sessions accumulate in the same project chain
for s in range(N):
    sid=f"old{s}"
    hook.handle("codex","UserPromptSubmit",{"cwd":str(ws),"session_id":sid,"hook_event_name":"UserPromptSubmit","prompt":"Write the answer to answer.txt"})
    for i in range(10):
        inp={"command":f"ls data {i}"}
        hook.handle("codex","PreToolUse",{"cwd":str(ws),"session_id":sid,"hook_event_name":"PreToolUse","tool_name":"Bash","tool_input":inp,"tool_use_id":f"t{s}_{i}"})
        hook.handle("codex","PostToolUse",{"cwd":str(ws),"session_id":sid,"hook_event_name":"PostToolUse","tool_name":"Bash","tool_input":inp,"tool_use_id":f"t{s}_{i}","tool_response":"s.csv"})
print("build", time.time()-t0, "events", len(Recorder(ws).events()))
t0=time.time(); r=zerostop.ended("codex", f"old{N-1}", str(ws), mode="evidence"); t1=time.time()
print("ended() s:", round(t1-t0,3), r.get("ended"))
t0=time.time(); Recorder(ws).events(); print("one events() s:", round(time.time()-t0,3))
