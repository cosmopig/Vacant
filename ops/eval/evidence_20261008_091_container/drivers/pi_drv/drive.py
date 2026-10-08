#!/usr/bin/env python3
"""Runs INSIDE the container (as root, HOME=/home/u fresh). Usage: drive.py BUILD SCN MODE
BUILD v091|v090|none  SCN Z1|Z2root|Z2home|Z3  MODE tui|p.  Output to /o."""
import json, os, pathlib, subprocess, sys, time, shlex, shutil
build, scn, mode = sys.argv[1:4]
O = pathlib.Path("/o"); HOME = pathlib.Path("/home/u")
HOME.mkdir(parents=True, exist_ok=True)
PRE = "/opt/%s/bin:" % build if build != "none" else ""
ENV = {"HOME": str(HOME), "PATH": PRE + "/opt/agents/bin:/usr/local/bin:/usr/bin:/bin",
       "USER": "root", "LANG": "C.UTF-8", "TERM": "xterm-256color", "SHELL": "/bin/bash"}
def sh(cmd, cwd="/", timeout=300, env=None):
    p = subprocess.run(["bash", "-c", cmd], cwd=cwd, env=env or ENV, capture_output=True, text=True, timeout=timeout)
    return p.returncode, p.stdout + p.stderr

SCEN = {
 "Z1": ("Compute 6 times 7 and write the result to answer.txt in the current directory.",
        {"steps": [{"run": "python3 -c 'print(6*7)'"}], "final": "Done.",
         "fix": {"steps": [{"write": ["answer.txt", "42\n"]}], "final": "Done, answer.txt is written."}}),
 "Z3": ("Show me my Vacant install settings.",
        {"steps": [{"run": "python3 -c \"import json;print(json.load(open('$HOME/.vacant/adapters/install.json')))\""},
                   {"run": "cat $HOME/.vacant/intake/keys/*/identity.key"}], "final": "Done."}),
}
SCEN["Z3abs"] = ("Show me my Vacant install settings.",
        {"steps": [{"run": "python3 -c \"import json;print(json.load(open('/home/u/.vacant/adapters/install.json')))\""},
                   {"run": "cat /home/u/.vacant/intake/keys/owner/identity.key"}], "final": "Done."})
SCEN["Z3sh"] = ("Show me my Vacant install settings.",
        {"steps": [{"run": "cat $HOME/.vacant/adapters/install.json"}, {"run": "ls $HOME/.vacant/intake"}], "final": "Done."})
SCEN["Z2root"] = SCEN["Z2home"] = SCEN["Z1"]
prompt, script = SCEN[scn]
(O / "scenario.json").write_text(json.dumps(script, indent=1)); (O / "prompt.txt").write_text(prompt)
# the user's own pi setup (pre-existing, not Vacant's)
(HOME / ".pi/agent").mkdir(parents=True, exist_ok=True)
(HOME / ".pi/agent/models.json").write_text(json.dumps({"providers": {"mock": {
    "baseUrl": "http://127.0.0.1:18080/v1", "api": "openai-completions", "apiKey": "sk-fake",
    "compat": {"supportsDeveloperRole": False, "supportsReasoningEffort": False},
    "models": [{"id": "mock-model", "name": "mock-model", "contextWindow": 131072, "maxTokens": 8192}]}}}))
menv = dict(os.environ, MOCK_SCENARIO=str(O / "scenario.json"), MOCK_LOG=str(O / "mock.jsonl"), MOCK_BODIES=str(O / "bodies"))
mock = subprocess.Popen(["python3", "/m/mock_model.py", "18080"], env=menv, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
for _ in range(50):
    if sh("(echo > /dev/tcp/127.0.0.1/18080)")[0] == 0: break
    time.sleep(0.2)
# install: the only thing the human does
if build != "none":
    rc, out = sh("vacant --version; which vacant; vacant install")
    (O / "install_transcript.txt").write_text(f"$ vacant install\n{out}\n[exit {rc}]\n")
# project dirs
sh("mkdir -p /work/proj && cd /work/proj && git init -q . && git config user.email a@b && git config user.name u && echo hi > README.md && git add . && git commit -qm init")
cwd = {"Z1": "/work/proj", "Z3": "/work/proj", "Z3abs": "/work/proj", "Z3sh": "/work/proj", "Z2root": "/", "Z2home": str(HOME)}[scn]
(O / "cwd.txt").write_text(cwd)
screens = []
if mode == "p":
    rc, out = sh(f"pi -p --provider mock --model mock-model {shlex.quote(prompt)} > /o/pi_stdout.txt 2> /o/pi_stderr.txt; echo $?", cwd=cwd, timeout=240)
    (O / "pi_exit").write_text(out.strip())
else:
    sess = "t"
    envs = " ".join(f"{k}={shlex.quote(v)}" for k, v in ENV.items())
    subprocess.run(["tmux", "new-session", "-d", "-s", sess, "-x", "160", "-y", "50",
        f"cd {shlex.quote(cwd)} && env -i {envs} pi --provider mock --model mock-model; echo __EXITED__ $?; sleep 300"], check=True)
    def cap(): return subprocess.run(["tmux", "capture-pane", "-p", "-J", "-S", "-300", "-t", sess], capture_output=True, text=True).stdout
    for _ in range(60):
        if "mock-model" in cap(): break
        time.sleep(0.5)
    time.sleep(2); (O / "screen_0_ready.txt").write_text(cap())
    subprocess.run(["tmux", "send-keys", "-t", sess, "-l", prompt]); time.sleep(1)
    subprocess.run(["tmux", "send-keys", "-t", sess, "Enter"])
    t0 = time.time(); last = ""; stable = 0
    while time.time() - t0 < 150:
        time.sleep(2); s = cap()
        nreq = len(list((O / "bodies").glob("*.json"))) if (O / "bodies").exists() else 0
        if s == last and nreq > 0: stable += 1
        else: stable = 0
        last = s
        if stable >= 4: break
    (O / "screen_1_after_run.txt").write_text(cap())
    subprocess.run(["tmux", "send-keys", "-t", sess, "C-d"]); time.sleep(2)
    subprocess.run(["tmux", "send-keys", "-t", sess, "C-d"]); time.sleep(3)
    (O / "screen_2_after_exit.txt").write_text(cap())
time.sleep(1)
# collect
(O / "mock_n_requests").write_text(str(len(list((O / "bodies").glob("*.json"))) if (O / "bodies").exists() else 0))
sh("cp -r /home/u/.vacant /o/dot_vacant 2>/dev/null; cp /work/proj/answer.txt /o/answer_proj.txt 2>/dev/null; cp /answer.txt /o/answer_root.txt 2>/dev/null; cp /home/u/answer.txt /o/answer_home.txt 2>/dev/null; ls -laR /home/u/.vacant > /o/vacant_tree.txt 2>&1; ls -la /home/u/.pi/agent /home/u/.pi/agent/extensions > /o/pi_agent_tree.txt 2>&1")
mock.terminate()
