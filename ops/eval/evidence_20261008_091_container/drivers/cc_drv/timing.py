import json, os, subprocess, sys, time, statistics, pathlib
build = sys.argv[1]
HOME = "/home/u"; os.makedirs(HOME+"/.claude", exist_ok=True)
ENV = {"HOME": HOME, "PATH": f"/opt/{build}/bin:/opt/agents/bin:/usr/local/bin:/usr/bin:/bin", "LANG": "C.UTF-8"}
subprocess.run("mkdir -p /work/proj && cd /work/proj && git init -q . && echo hi > README.md", shell=True, env=ENV)
print(subprocess.run("vacant install", shell=True, env=ENV, capture_output=True, text=True).stdout[:200])
st = json.load(open(HOME+"/.claude/settings.json"))
cmds = {ev: st["hooks"][ev][0]["hooks"][0]["command"] for ev in st["hooks"]}
print("PreToolUse cmd:", cmds["PreToolUse"])
def payload(ev, i, sid):
    d = {"session_id": sid, "transcript_path": f"/tmp/nonexist.jsonl", "cwd": "/work/proj", "permission_mode": "acceptEdits",
         "hook_event_name": ev}
    if ev == "UserPromptSubmit": d["prompt"] = "Compute 6 times 7 and write answer.txt"
    if ev in ("PreToolUse", "PostToolUse"):
        d.update(tool_name="Bash", tool_input={"command": f"echo {i}"}, tool_use_id=f"toolu_{i}")
        if ev == "PostToolUse": d["tool_response"] = {"stdout": str(i), "stderr": "", "interrupted": False}
    return json.dumps(d)
def call(ev, i, sid):
    t = time.perf_counter()
    p = subprocess.run(cmds[ev], shell=True, input=payload(ev, i, sid), env=ENV, capture_output=True, text=True, cwd="/work/proj")
    return time.perf_counter() - t, p.returncode, p.stdout[:100]
sid = "timing-session-1"
call("UserPromptSubmit", 0, sid)
res = {}
# pure PreToolUse x20 (no Post between)
res["pre_only"] = [call("PreToolUse", i, sid) for i in range(1, 21)]
# realistic Pre+Post pairs x20 (report Pre times)
pre = []; post = []
for i in range(21, 41):
    pre.append(call("PreToolUse", i, sid)); post.append(call("PostToolUse", i, sid))
res["pre_in_pairs"] = pre; res["post_in_pairs"] = post
out = {}
for k, v in res.items():
    ts = [x[0] for x in v]
    out[k] = {"n": len(ts), "total_s": round(sum(ts), 3), "mean_ms": round(1000*statistics.mean(ts), 1),
              "median_ms": round(1000*statistics.median(ts), 1), "max_ms": round(1000*max(ts), 1), "rcs": sorted({x[1] for x in v})}
print(json.dumps(out, indent=1))
json.dump({"build": build, "summary": out, "raw_s": {k: [round(x[0], 4) for x in v] for k, v in res.items()}}, open("/o/timing.json", "w"), indent=1)
