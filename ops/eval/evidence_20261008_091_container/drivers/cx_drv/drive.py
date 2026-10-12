#!/usr/bin/env python3
"""Inside container (root, fresh HOME=/home/u). drive.py BUILD SCN MODE ; BUILD v091|v090|none ; SCN Z1|Z2root|Z2home|Z3 ; MODE p|tui. Output /o. L-fake, Codex."""
import json, os, pathlib, subprocess, sys, time, shlex
build, scn, mode = sys.argv[1:4]
O = pathlib.Path("/o"); HOME = pathlib.Path("/home/u"); HOME.mkdir(parents=True, exist_ok=True)
PRE = "/opt/%s/bin:" % build if build != "none" else ""
PORT = 18080
ENV = {"HOME": str(HOME), "PATH": PRE + "/opt/agents/bin:/usr/local/bin:/usr/bin:/bin", "USER": "root",
       "LANG": "C.UTF-8", "TERM": "xterm-256color", "SHELL": "/bin/bash", "MOCK_API_KEY": "sk-fake"}
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
# the user's pre-existing codex setup (custom provider, dummy key, folder trusted) -- not Vacant
(HOME / ".codex").mkdir(parents=True, exist_ok=True)
trust = "".join(f'\n[projects."{d}"]\ntrust_level = "trusted"\n' for d in ["/work/proj", "/", str(HOME)])
(HOME / ".codex" / "config.toml").write_text('model = "mock-model"\nmodel_provider = "mock"\n\n'
    '[model_providers.mock]\nname = "mock"\n'
    f'base_url = "http://127.0.0.1:{PORT}/v1"\nwire_api = "responses"\nenv_key = "MOCK_API_KEY"\n' + trust)
sh("mkdir -p /work/proj && cd /work/proj && git init -q . && git config user.email a@b && git config user.name u && echo hi > README.md && git add . && git commit -qm init")
(O / "bodies").mkdir(exist_ok=True)
menv = dict(os.environ, MOCK_SCENARIO=str(O / "scenario.json"), MOCK_LOG=str(O / "mock.jsonl"), MOCK_BODIES=str(O / "bodies"))
mock = subprocess.Popen(["python3", "/m/mock_model.py", str(PORT)], env=menv, stdout=open(O/"mock.stdout","w"), stderr=subprocess.STDOUT)
for _ in range(50):
    if sh("(echo > /dev/tcp/127.0.0.1/%d)" % PORT)[0] == 0: break
    time.sleep(0.2)
sh(f"cp {HOME}/.codex/config.toml {O}/codex_config_before_install.toml")
if build != "none":
    rc, out = sh("vacant --version; which vacant; vacant install")
    (O / "install_transcript.txt").write_text(f"$ vacant install\n{out}\n[exit {rc}]\n")
sh(f"cp {HOME}/.codex/config.toml {O}/codex_config_after_install.toml 2>/dev/null; cp {HOME}/.codex/hooks.json {O}/codex_hooks_after_install.json 2>/dev/null")
def rows():
    p = O / "mock.jsonl"
    return [json.loads(x) for x in p.read_text().splitlines() if x.strip()] if p.is_file() else []
def post_rows(): return [r for r in rows() if r.get("proto")]
meta = {"build": build, "scn": scn, "mode": mode, "cwd": cwd}
base = ["codex", "-s", "danger-full-access", "-a", "never"]
if mode in ("p", "ph"):
    t0 = time.time()
    argv = ["codex", "exec"] + ([] if mode == "ph" else ["--json"]) + ["--skip-git-repo-check", "-s", "danger-full-access", prompt]
    rc, out = sh(f"{shlex.join(argv)} > /o/codex_stdout.jsonl 2> /o/codex_stderr.txt; echo $?", cwd=cwd, timeout=240)
    meta["exit"] = out.strip(); meta["wall"] = round(time.time() - t0, 1)
    time.sleep(5)
else:
    sess = "t"; frames = []; T0 = time.time()
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
    subprocess.run(["tmux", "new-session", "-d", "-s", sess, "-x", "160", "-y", "50",
        f"cd {shlex.quote(cwd)} && env -i {envs} {shlex.join(base)}; echo __EXITED__ $?; sleep 300"], check=True)
    ready = False
    for _ in range(120):
        snap()
        t = frames[-1][1]
        if "Ask Codex to do anything" in t: ready = True; break
        time.sleep(0.5)
    time.sleep(6)
    keys([("l", prompt), ("k", "Enter")])
    n0 = len(post_rows()); t1 = time.time(); resent = False
    while time.time() - t1 < 30 and len(post_rows()) <= n0: time.sleep(0.4); snap()
    if len(post_rows()) <= n0:
        resent = True; keys([("k", "Enter")])
    t2 = time.time(); ln, lt = -1, time.time()
    while time.time() - t2 < 200:
        n = len(post_rows()); snap()
        if n != ln: ln, lt = n, time.time()
        elif n >= 2 and time.time() - lt >= 15: break
        time.sleep(0.4)
    for _ in range(12): snap(); time.sleep(0.5)
    (O / "final_screen.txt").write_text(cap(500))
    keys([("l", "/quit"), ("k", "Enter")])
    ex = False
    for _ in range(60):
        if "__EXITED__" in cap(): ex = True; break
        time.sleep(0.5)
    subprocess.run(["tmux", "kill-session", "-t", sess], capture_output=True)
    with open(O / "frames.txt", "w") as f:
        for t, fr in frames: f.write(f"===== t={t}s =====\n{fr}\n")
    vf = [(t, fr) for t, fr in frames if "acant" in fr or "does not exist" in fr]
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
