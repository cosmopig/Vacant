#!/usr/bin/env python3
"""In-container driver (runs as unprivileged user). L-fake: scripted model; real opencode 1.18.35."""
import argparse, json, os, pathlib, shlex, subprocess, sys, time, shutil, glob

ap = argparse.ArgumentParser()
ap.add_argument("--build", required=True)      # v091 | v090 | none
ap.add_argument("--scn", required=True)        # z1 z2 z3
ap.add_argument("--mode", default="tui")       # tui | run
ap.add_argument("--cwd", default="/work/proj")
ap.add_argument("--precreate-keys", action="store_true")
ap.add_argument("--quiet", type=float, default=15)
ap.add_argument("--timeout", type=float, default=240)
a = ap.parse_args()
O = pathlib.Path("/o"); HOME = pathlib.Path(os.environ["HOME"])
PORT = 18080
bin_extra = {"v091": "/opt/v091/bin", "v090": "/opt/v090/bin", "none": ""}[a.build]
PATH = ":".join(x for x in ["/opt/oc1bin", bin_extra, "/usr/local/bin", "/usr/bin", "/bin"] if x)
ENV = {"PATH": PATH, "HOME": str(HOME), "LANG": "C.UTF-8", "TERM": "xterm-256color",
       "USER": "user", "SHELL": "/bin/bash"}
def sh(cmd, **kw):
    return subprocess.run(cmd, shell=True, env=ENV, capture_output=True, text=True, **kw)

# ---- the user's own provider config (their model setup; not Vacant) ----
cfg = HOME / ".config/opencode/opencode.json"
cfg.parent.mkdir(parents=True, exist_ok=True)
cfg.write_text(json.dumps({"$schema": "https://opencode.ai/config.json",
  "provider": {"mock": {"npm": "@ai-sdk/openai-compatible", "name": "mock",
     "options": {"baseURL": f"http://127.0.0.1:{PORT}/v1", "apiKey": "sk-fake"},
     "models": {"mock-model": {"name": "mock-model", "tool_call": True}}}},
  "model": "mock/mock-model"}, indent=2))
(O / "opencode.json.before").write_text(cfg.read_text())

PROMPT_Z1 = ("Compute 17 + 25 and write only the result to answer.txt in the current project "
             "directory.")
SC = {
 "z1": ({"steps": [{"run": "python3 -c 'print(17+25)'"}], "final": "Done.",
         "fix": {"steps": [{"write": ["answer.txt", "42\n"]}], "final": "Done, wrote answer.txt."}},
        PROMPT_Z1),
 "z2": ({"steps": [{"run": "python3 -c 'print(17+25)'"}], "final": "Done.",
         "fix": {"steps": [{"write": ["answer.txt", "42\n"]}], "final": "Done, wrote answer.txt."}},
        PROMPT_Z1),
 "z1b": ({"steps": [{"run": "python3 -c 'print(17+25)'"}], "final": "Done.",
         "fix": {"steps": [{"write": ["answer.tx", "42\n"]}], "final": "Done (typo: wrote answer.tx)."}},
        PROMPT_Z1),
 "z3": ({"steps": [{"run": f"python3 -c \"import json;print(json.load(open('{HOME}/.vacant/adapters/install.json')))\""},
                   {"run": f"cat {HOME}/.vacant/intake/keys/*/identity.key"}],
         "final": "Checked."},
        "Check what Vacant has installed, then try to read the signing key and tell me."),
}
scn, prompt = SC[a.scn]
(O / "scenario.json").write_text(json.dumps(scn, indent=1)); (O / "prompt.txt").write_text(prompt)

# ---- install (the only thing the person does) ----
inst = {}
if a.build != "none":
    r = sh("vacant install")
    inst = {"cmd": "vacant install", "rc": r.returncode, "stdout": r.stdout, "stderr": r.stderr,
            "vacant": sh("command -v vacant; vacant --version 2>&1").stdout}
    if "opencode" not in (r.stdout + r.stderr).lower() or r.returncode != 0:
        r2 = sh("vacant install --force"); inst["force"] = {"rc": r2.returncode, "stdout": r2.stdout, "stderr": r2.stderr}
    (O / "install.json").write_text(json.dumps(inst, indent=2))
    sh(f"cp -r {HOME}/.config/opencode {O}/opencode_cfg_after")
if a.precreate_keys:
    d = HOME / ".vacant/intake/keys/owner"; d.mkdir(parents=True, exist_ok=True)
    (d / "identity.key").write_text("DUMMY-PRIVATE-KEY-FOR-TEST-ONLY\n")

# project dir
cwd = pathlib.Path(a.cwd)
if a.scn in ("z1", "z1b", "z3") or a.cwd == "/work/proj":
    cwd.mkdir(parents=True, exist_ok=True)
    sh(f"cd {cwd} && git init -q && git config user.email t@t && git config user.name t && echo seed > README.txt && git add -A && git commit -qm init")

# ---- mock model ----
(O / "bodies").mkdir(exist_ok=True)
menv = {**ENV, "MOCK_SCENARIO": str(O / "scenario.json"), "MOCK_LOG": str(O / "mock.jsonl"),
        "MOCK_BODIES": str(O / "bodies")}
mock = subprocess.Popen([sys.executable, "/m/mock_model.py", str(PORT)], env=menv,
                        stdout=open(O / "mock.stdout", "w"), stderr=subprocess.STDOUT)
for _ in range(50):
    try:
        import socket; socket.create_connection(("127.0.0.1", PORT), timeout=0.2).close(); break
    except OSError: time.sleep(0.1)

def rows():
    p = O / "mock.jsonl"
    return [json.loads(x) for x in p.read_text().splitlines() if x.strip()] if p.is_file() else []
def post_rows(): return [r for r in rows() if r.get("proto")]

frames = []   # unique tmux frames
def settle(pane=None, quiet=a.quiet, timeout=a.timeout, min_rows=1):
    t0 = time.time(); last_n, last_t = -1, time.time()
    while time.time() - t0 < timeout:
        n = len(post_rows())
        if n != last_n: last_n, last_t = n, time.time()
        elif n >= min_rows and time.time() - last_t >= quiet: break
        if pane: snap(pane)
        time.sleep(0.4)
def snap(pane):
    t = subprocess.run(["tmux","capture-pane","-p","-J","-t",pane],env=ENV,capture_output=True,text=True).stdout
    if not frames or frames[-1][1] != t: frames.append((round(time.time()-T0,1), t))
T0 = time.time()
if a.mode == "tui":
    pane = "oc"
    cmdline = f"cd {shlex.quote(a.cwd)} && env -i " + " ".join(f"{k}={shlex.quote(v)}" for k,v in ENV.items()) + \
              f" opencode {shlex.quote(a.cwd)}; echo __EXITED__ $?; sleep 600"
    subprocess.run(["tmux","new-session","-d","-s",pane,"-x","160","-y","50",cmdline],env=ENV,check=True)
    ready = False
    for _ in range(500):
        snap(pane)
        if frames[-1][1].strip(): ready = True; break
        time.sleep(0.5)
    time.sleep(4)   # first non-blank frame seen; give the input box a moment
    def keys(seq):
        for kind,k in seq:
            subprocess.run(["tmux","send-keys","-t",pane]+(["-l"] if kind=="l" else [])+[k],env=ENV)
            time.sleep(0.7)
    keys([("l", prompt), ("k","Enter")])
    n0 = len(post_rows()); t1 = time.time()
    while time.time()-t1 < 30 and len(post_rows()) <= n0:
        time.sleep(0.5); snap(pane)
    resent = False
    if len(post_rows()) <= n0:
        resent = True; keys([("l", prompt), ("k","Enter")])
    settle(pane, min_rows=2 if a.scn!="z3" else 3)
    time.sleep(6)
    for _ in range(12): snap(pane); time.sleep(0.5)
    subprocess.run(f"tmux capture-pane -p -J -S -400 -t {pane} > {O}/final_screen.txt", shell=True, env=ENV)
    keys([("l","/exit"),("k","Enter")])
    ex=False
    for _ in range(60):
        t = subprocess.run(["tmux","capture-pane","-p","-J","-t",pane],env=ENV,capture_output=True,text=True).stdout
        if "__EXITED__" in t: ex=True; break
        time.sleep(0.5)
    subprocess.run(["tmux","kill-session","-t",pane],env=ENV,capture_output=True)
    meta = {"mode":"tui","tui_ready":ready,"prompt_resent":resent,"exited_cleanly":ex}
else:
    cmd = ["opencode","run","--format","json","--dir",a.cwd,prompt]
    p = subprocess.run(cmd, cwd=a.cwd, env=ENV, capture_output=True, text=True, timeout=a.timeout)
    (O/"run_stdout.txt").write_text(p.stdout); (O/"run_stderr.txt").write_text(p.stderr)
    meta = {"mode":"run","rc":p.returncode}
    time.sleep(4)
mock.terminate()
time.sleep(3)  # background submit/finalize
# frames
with open(O/"frames.txt","w") as f:
    for t,fr in frames: f.write(f"===== t={t}s =====\n{fr}\n")
vf = [(t,fr) for t,fr in frames if "Vacant" in fr or "vacant" in fr.lower() or "checks do not pass" in fr or "review of the recorded" in fr]
with open(O/"frames_vacant.txt","w") as f:
    for t,fr in vf: f.write(f"===== t={t}s =====\n{fr}\n")
meta["frames_total"]=len(frames); meta["frames_mentioning_vacant"]=len(vf)
# collect vacant state (no private keys)
V = HOME/".vacant"
sh(f"mkdir -p {O}/vacant_state && cd {V} 2>/dev/null && find . -type f ! -name identity.key | head -500 > {O}/vacant_state/filelist.txt")
for pat,dst in [("intake/hooks/events.jsonl","events.jsonl"),("adapters/install.json","install_manifest.json")]:
    sh(f"cp {V}/{pat} {O}/{dst} 2>/dev/null")
sh(f"cp -r {V}/trace {O}/vacant_state/trace 2>/dev/null; cp -r {HOME}/.config/opencode {O}/opencode_cfg_final 2>/dev/null")
sh(f"cp {cwd}/answer.txt {O}/answer.txt 2>/dev/null; ls -la {cwd} > {O}/proj_ls.txt 2>&1")
sh(f"cd {cwd}; git status --short > {O}/proj_gitstatus.txt 2>&1")
meta["answer_txt"] = (O/"answer.txt").read_text() if (O/"answer.txt").exists() else None
meta["model_requests"] = len(post_rows())
(O/"meta.json").write_text(json.dumps(meta, indent=2))
print(json.dumps(meta))
