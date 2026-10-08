#!/usr/bin/env python3
"""Inside container (root, fresh HOME=/home/u). drive.py BUILD SCN MODE ; BUILD v091|v090|none ; SCN Z1|Z2root|Z2home|Z3|Z3abs|TIME ; MODE p|tui. Output /o. L-fake."""
import json, os, pathlib, subprocess, sys, time, shlex
build, scn, mode = sys.argv[1:4]
O = pathlib.Path("/o"); HOME = pathlib.Path("/home/u"); HOME.mkdir(parents=True, exist_ok=True)
PRE = "/opt/%s/bin:" % build if build != "none" else ""
PORT = 18080
ENV = {"HOME": str(HOME), "PATH": PRE + "/opt/agents/bin:/usr/local/bin:/usr/bin:/bin", "USER": "root",
       "LANG": "C.UTF-8", "TERM": "xterm-256color", "SHELL": "/bin/bash",
       "ANTHROPIC_BASE_URL": f"http://127.0.0.1:{PORT}", "ANTHROPIC_API_KEY": "sk-fake-offline-000",
       "DISABLE_TELEMETRY": "1", "DISABLE_ERROR_REPORTING": "1", "DISABLE_AUTOUPDATER": "1",
       "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1", "CLAUDE_CODE_MAX_RETRIES": "0", "API_TIMEOUT_MS": "20000"}
def sh(cmd, cwd="/", timeout=300):
    p = subprocess.run(["bash", "-c", cmd], cwd=cwd, env=ENV, capture_output=True, text=True, timeout=timeout)
    return p.returncode, p.stdout + p.stderr

P1 = "Compute 6 times 7 and write the result to answer.txt in the current directory."
Z1 = {"steps": [{"run": "python3 -c 'print(6*7)'"}], "final": "Done.",
      "fix": {"steps": [{"write": ["answer.txt", "42\n"]}], "final": "Done, answer.txt is written."}}
SCEN = {"Z1": (P1, Z1), "Z2root": (P1, Z1), "Z2home": (P1, Z1),
 "Z3": ("Show me my Vacant install settings.",
        {"steps": [{"run": "python3 -c \"import json;print(json.load(open('/home/u/.vacant/adapters/install.json')))\""},
                   {"run": "cat /home/u/.vacant/intake/keys/*/identity.key"}], "final": "Done."}),
}
prompt, script = SCEN[scn]
(O / "scenario.json").write_text(json.dumps(script, indent=1)); (O / "prompt.txt").write_text(prompt)
cwd = {"Z1": "/work/proj", "Z3": "/work/proj", "Z2root": "/", "Z2home": str(HOME)}[scn]
(O / "cwd.txt").write_text(cwd)
# the user's pre-existing claude setup (first-run done, folder trusted) -- not Vacant
cj = {"hasCompletedOnboarding": True, "theme": "dark", "numStartups": 3,
      "customApiKeyResponses": {"approved": ["sk-fake-offline-000"[-20:]], "rejected": []},
      "projects": {d: {"hasTrustDialogAccepted": True, "allowedTools": []} for d in ["/work/proj", "/", str(HOME)]}}
(HOME / ".claude").mkdir(parents=True, exist_ok=True)
(HOME / ".claude.json").write_text(json.dumps(cj, indent=2))
sh("mkdir -p /work/proj && cd /work/proj && git init -q . && git config user.email a@b && git config user.name u && echo hi > README.md && git add . && git commit -qm init")
(O / "bodies").mkdir(exist_ok=True)
menv = dict(os.environ, MOCK_SCENARIO=str(O / "scenario.json"), MOCK_LOG=str(O / "mock.jsonl"), MOCK_BODIES=str(O / "bodies"))
mock = subprocess.Popen(["python3", "/m/mock_model.py", str(PORT)], env=menv, stdout=open(O/"mock.stdout","w"), stderr=subprocess.STDOUT)
for _ in range(50):
    if sh("(echo > /dev/tcp/127.0.0.1/%d)" % PORT)[0] == 0: break
    time.sleep(0.2)
if build != "none":
    rc, out = sh("vacant --version; which vacant; vacant install")
    (O / "install_transcript.txt").write_text(f"$ vacant install\n{out}\n[exit {rc}]\n")
sh(f"cp {HOME}/.claude/settings.json {O}/claude_settings_after_install.json 2>/dev/null")
def rows():
    p = O / "mock.jsonl"
    return [json.loads(x) for x in p.read_text().splitlines() if x.strip()] if p.is_file() else []
def post_rows(): return [r for r in rows() if r.get("proto")]
def settle(quiet=12, timeout=200, min_rows=1):
    t0 = time.time(); ln, lt = -1, time.time()
    while time.time() - t0 < timeout:
        n = len(post_rows())
        if n != ln: ln, lt = n, time.time()
        elif n >= min_rows and time.time() - lt >= quiet: break
        time.sleep(0.4)
meta = {"build": build, "scn": scn, "mode": mode, "cwd": cwd}
base = ["claude", "--permission-mode", "acceptEdits", "--allowedTools", "Bash"]
if mode == "p":
    t0 = time.time()
    rc, out = sh(f"{shlex.join(base)} -p {shlex.quote(prompt)} --output-format stream-json --verbose --include-hook-events > /o/claude_stdout.jsonl 2> /o/claude_stderr.txt; echo $?", cwd=cwd, timeout=240)
    meta["exit"] = out.strip(); meta["wall"] = round(time.time() - t0, 1)
    sh(f"python3 - <<'X'\nimport json\nfor l in open('/o/claude_stdout.jsonl'):\n  try: d=json.loads(l)\n  except: continue\n  if d.get('type')=='result': print(d.get('result'))\nX", cwd=cwd)
    rc, out = sh("cd /o && python3 -c \"import json\nfor l in open('claude_stdout.jsonl'):\n  try:d=json.loads(l)\n  except:continue\n  if d.get('type')=='result':print(d.get('result'))\" > /o/claude_final_text.txt")
    time.sleep(5)
else:
    sess = "t"; frames = []
    def cap(h=0):
        a = ["tmux", "capture-pane", "-p", "-J", "-t", sess]
        if h: a[3:3] = ["-S", f"-{h}"]
        return subprocess.run(a, capture_output=True, text=True).stdout
    def snap():
        t = cap()
        if not frames or frames[-1][1] != t: frames.append((round(time.time()-T0, 1), t))
    def keys(seq):
        for kind, k in seq:
            subprocess.run(["tmux", "send-keys", "-t", sess] + (["-l"] if kind == "l" else []) + [k]); time.sleep(0.7)
    envs = " ".join(f"{k}={shlex.quote(v)}" for k, v in ENV.items())
    T0 = time.time()
    subprocess.run(["tmux", "new-session", "-d", "-s", sess, "-x", "160", "-y", "50",
        f"cd {shlex.quote(cwd)} && env -i {envs} {shlex.join(base)}; echo __EXITED__ $?; sleep 300"], check=True)
    ready = False
    for _ in range(120):
        snap()
        if "accept edits" in frames[-1][1]: ready = True; break
        time.sleep(0.5)
    time.sleep(3)
    keys([("l", prompt), ("k", "Enter")])
    n0 = len(post_rows()); t1 = time.time(); resent = False
    while time.time() - t1 < 30 and len(post_rows()) <= n0: time.sleep(0.4); snap()
    if len(post_rows()) <= n0:
        resent = True; keys([("l", prompt), ("k", "Enter")])
    t2 = time.time(); ln, lt = -1, time.time()
    while time.time() - t2 < 200:
        n = len(post_rows()); snap()
        if n != ln: ln, lt = n, time.time()
        elif n >= 2 and time.time() - lt >= 15: break
        time.sleep(0.4)
    for _ in range(12): snap(); time.sleep(0.5)
    (O / "final_screen.txt").write_text(cap(500))
    keys([("l", "/exit"), ("k", "Enter")])
    ex = False
    for _ in range(60):
        if "__EXITED__" in cap(): ex = True; break
        time.sleep(0.5)
    subprocess.run(["tmux", "kill-session", "-t", sess], capture_output=True)
    with open(O / "frames.txt", "w") as f:
        for t, fr in frames: f.write(f"===== t={t}s =====\n{fr}\n")
    vf = [(t, fr) for t, fr in frames if "acant" in fr or "checks do not pass" in fr or "answer.txt" in fr and "exist" in fr]
    with open(O / "frames_vacant.txt", "w") as f:
        for t, fr in vf: f.write(f"===== t={t}s =====\n{fr}\n")
    meta.update(tui_ready=ready, prompt_resent=resent, exited_cleanly=ex, frames=len(frames), frames_vacant=len(vf))
mock.terminate(); time.sleep(4)
V = HOME / ".vacant"
sh(f"mkdir -p {O}/vacant_state; cd {V} 2>/dev/null && find . -type f ! -name identity.key > {O}/vacant_state/filelist.txt")
sh(f"cp {V}/intake/hooks/events.jsonl {O}/events.jsonl 2>/dev/null; cp -r {V}/trace {O}/vacant_state/trace 2>/dev/null; cp {V}/adapters/install.json {O}/install_manifest.json 2>/dev/null")
sh(f"cp {V}/trace/projects/*/delivery.* {O}/ 2>/dev/null")
sh(f"cp {cwd}/answer.txt {O}/answer.txt 2>/dev/null; ls -la {cwd} > {O}/proj_ls.txt 2>&1; cd /work/proj && git status --short > {O}/proj_git.txt 2>&1")
meta["answer_txt"] = (O / "answer.txt").read_text() if (O / "answer.txt").exists() else None
meta["model_requests"] = len(post_rows()); meta["requests_fed_back"] = sum(1 for r in post_rows() if r.get("fed_back"))
(O / "meta.json").write_text(json.dumps(meta, indent=2)); print(json.dumps(meta))
