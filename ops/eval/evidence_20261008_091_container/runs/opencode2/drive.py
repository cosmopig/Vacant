#!/usr/bin/env python3
"""L-fake driver for OpenCode 2.x (@opencode/cli 2.0.24) + Vacant zero-config, inside one fresh container.

usage: drive.py <build: v091|v090|none> <surface: tui|run> <port> <out_dir> [scenarios]

A "normal user": HOME=/home/u, opencode on PATH, opencode.json points to a provider (here: the scripted
fake model), then `vacant install` (nothing else), then uses `opencode` as usual.
"""
import json, os, pathlib, shlex, shutil, subprocess, sys, time

BUILD, SURFACE, PORT, OUT = sys.argv[1], sys.argv[2], int(sys.argv[3]), pathlib.Path(sys.argv[4])
ONLY = sys.argv[5].split(",") if len(sys.argv) > 5 else None
HOME = pathlib.Path("/home/u")
OUT.mkdir(parents=True, exist_ok=True)
VBIN = {"v091": "/opt/v091/bin", "v090": "/opt/v090/bin"}.get(BUILD)
PATH = ":".join(x for x in [VBIN, "/opt/npm/opencode2/bin", "/usr/local/bin", "/usr/bin", "/bin"] if x)
ENV = {"HOME": str(HOME), "PATH": PATH, "LANG": "C.UTF-8", "TERM": "xterm-256color", "USER": "u",
       "SHELL": "/bin/bash", "NODE_EXTRA_CA_CERTS": "/ca.crt"}
VH = HOME / ".vacant"
EVENTS = VH / "intake" / "hooks" / "events.jsonl"
ERRORS = VH / "intake" / "hooks" / "errors.jsonl"
INSTALL_JSON = VH / "adapters" / "install.json"

PROMPT = "Compute 6 times 7 with a quick command and write the result to answer.txt."
Z1 = {"steps": [{"run": "python3 -c 'print(6*7)'"}], "final": "Done.",
      "fix": {"steps": [{"run": "printf '42\\n' > answer.txt"}], "final": "Done. answer.txt now contains 42."}}
Z3 = {"steps": [{"run": "python3 -c \"import json;print(json.load(open('/home/u/.vacant/adapters/install.json')))\""},
                {"run": "cat /home/u/.vacant/intake/keys/*/identity.key"}],
      "final": "Done."}
Z3_PROMPT = "Show me Vacant's install settings, then print the identity key file."
SCN = {
    "Z1": ("/work/proj", PROMPT, Z1, True),
    "Z2_root": ("/", PROMPT, Z1, False),
    "Z2_home": (str(HOME), PROMPT, Z1, False),
    "Z3": ("/work/proj3", Z3_PROMPT, Z3, True),
    "DIAG": ("/work/projdiag", PROMPT, Z1, True),   # run surface only: --standalone --print-logs
}


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def sh(argv, cwd=None, timeout=300, **kw):
    return subprocess.run(argv, cwd=cwd, env=ENV, capture_output=True, text=True, timeout=timeout, **kw)


def write_user_config():
    f = HOME / ".config" / "opencode" / "opencode.json"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps({"$schema": "https://opencode.ai/config.json",
                             "provider": {"mock": {"npm": "@ai-sdk/openai-compatible", "name": "mock",
                                                   "options": {"baseURL": f"http://127.0.0.1:{PORT}/v1",
                                                               "apiKey": "sk-fake"},
                                                   "models": {"mock-model": {"name": "mock-model",
                                                                             "tool_call": True}}}},
                             "model": "mock/mock-model"}, indent=2))


class Mock:
    def __init__(self, d: pathlib.Path, scn: dict):
        self.d = d
        (d / "scenario.json").write_text(json.dumps(scn, indent=2))
        env = {"PATH": "/usr/bin:/bin", "MOCK_SCENARIO": str(d / "scenario.json"),
               "MOCK_LOG": str(d / "mock.jsonl"), "MOCK_RAW": str(d / "requests_raw.jsonl")}
        self.p = subprocess.Popen(["python3", "/lab/mock_raw.py", str(PORT)], env=env,
                                  stdout=subprocess.DEVNULL, stderr=open(d / "mock.stderr", "w"))
        time.sleep(1.0)

    def rows(self):
        p = self.d / "mock.jsonl"
        return [json.loads(x) for x in p.read_text().splitlines() if x.strip()] if p.is_file() else []

    def stop(self):
        self.p.terminate()
        self.p.wait()


def settle(m: Mock, since: int, quiet: float, timeout: float):
    t0 = time.time(); last_n, last_t = -1, time.time()
    while time.time() - t0 < timeout:
        n = len(m.rows())
        if n != last_n:
            last_n, last_t = n, time.time()
        elif n > since and time.time() - last_t >= quiet:
            break
        time.sleep(0.5)
    return m.rows()


def nlines(p):
    return len(p.read_text().splitlines()) if p.is_file() else 0


def tmux(*a):
    return subprocess.run(["tmux", *a], capture_output=True, text=True, env={**os.environ, **ENV})


def screen(hist=0):
    a = ["capture-pane", "-p", "-J", "-t", "u"]
    if hist:
        a[3:3] = ["-S", f"-{hist}"]
    return tmux(*a).stdout


def run_scenario(name):
    cwd, prompt, scn, git = SCN[name]
    d = OUT / name
    d.mkdir(parents=True, exist_ok=True)
    if git:
        pathlib.Path(cwd).mkdir(parents=True, exist_ok=True)
        sh(["git", "init", "-q", cwd])
    ev0, er0 = nlines(EVENTS), nlines(ERRORS)
    m = Mock(d, scn)
    res = {"scenario": name, "cwd": cwd, "prompt": prompt, "surface": SURFACE, "build": BUILD}
    t0 = time.time()
    if SURFACE == "run":
        try:
            extra = ["--standalone", "--print-logs", "--log-level", "debug"] if name == "DIAG" else []
            cp = sh(["opencode", "run", *extra, prompt], cwd=cwd, timeout=240)
            res["rc"] = cp.returncode
            (d / "run.stdout.txt").write_text(cp.stdout)
            (d / "run.stderr.txt").write_text(cp.stderr)
        except subprocess.TimeoutExpired as e:
            res["rc"] = "timeout"
            (d / "run.stdout.txt").write_text((e.stdout or b"").decode() if isinstance(e.stdout, bytes) else (e.stdout or ""))
        res["client_exit_s"] = round(time.time() - t0, 1)
        n_at_exit = len(m.rows())
        res["requests_at_client_exit"] = n_at_exit
        # the background service may keep going after the client exits (feedback sent by the plugin)
        time.sleep(25)
        rows = settle(m, 0, 10, 60)
        res["requests_after_client_exit"] = len(rows) - n_at_exit
    else:
        envs = " ".join(f"{k}={shlex.quote(v)}" for k, v in ENV.items())
        cmd = f"cd {shlex.quote(cwd)} && env -i {envs} opencode; echo __EXITED__ $?; sleep 900"
        tmux("kill-session", "-t", "u")
        tmux("new-session", "-d", "-s", "u", "-x", "160", "-y", "50", cmd)
        t = time.time()
        while time.time() - t < 60 and "Ask anything" not in screen():
            time.sleep(0.5)
        res["ready"] = "Ask anything" in screen()
        time.sleep(2)
        (d / "screen.0_ready.txt").write_text(screen())
        tmux("send-keys", "-t", "u", "-l", prompt); time.sleep(1.0)
        tmux("send-keys", "-t", "u", "Enter")
        t = time.time()
        while time.time() - t < 30 and not m.rows():
            time.sleep(0.5)
        if not m.rows():
            res["prompt_resent"] = True
            tmux("send-keys", "-t", "u", "Enter")
        snaps = []
        t = time.time()
        last = None
        while time.time() - t < 240:
            s = screen()
            if s != last:
                snaps.append(f"===== t+{time.time()-t0:.1f}s =====\n{s}")
                last = s
            rows = m.rows()
            if rows and time.time() - max(r["t"] for r in rows) > 20 and time.time() - t > 30:
                break
            time.sleep(1.0)
        (d / "screen.1_timeline.txt").write_text("\n".join(snaps))
        (d / "screen.2_settled.txt").write_text(screen())
        (d / "screen.2_settled_history.txt").write_text(screen(2000))
        tmux("send-keys", "-t", "u", "-l", "/exit"); time.sleep(1.0)
        tmux("send-keys", "-t", "u", "Enter")
        t = time.time()
        while time.time() - t < 30 and "__EXITED__" not in screen():
            time.sleep(0.5)
        time.sleep(5)
        (d / "screen.3_after_exit.txt").write_text(screen(2000))
        res["exited"] = "__EXITED__" in screen()
        tmux("kill-session", "-t", "u")
        time.sleep(8)       # session_end hooks
    m.stop()
    res["wall_s"] = round(time.time() - t0, 1)
    rows = m.rows()
    res["n_requests"] = len(rows)
    res["requests"] = [{k: r.get(k) for k in ("n", "k", "fed_back", "reply", "tool")} for r in rows]
    res["feedback_seen_by_model"] = [r.get("feedback") for r in rows if r.get("fed_back")][:1]
    evs = EVENTS.read_text().splitlines()[ev0:] if EVENTS.is_file() else []
    (d / "events.jsonl").write_text("\n".join(evs) + ("\n" if evs else ""))
    ers = ERRORS.read_text().splitlines()[er0:] if ERRORS.is_file() else []
    (d / "errors.jsonl").write_text("\n".join(ers) + ("\n" if ers else ""))
    res["events_kinds"] = [json.loads(x).get("kind") for x in evs]
    res["answer_txt"] = (pathlib.Path(cwd) / "answer.txt").read_text() if (pathlib.Path(cwd) / "answer.txt").is_file() else None
    (d / "result.json").write_text(json.dumps(res, indent=2, ensure_ascii=False))
    log(name, json.dumps({k: res[k] for k in res if k not in ("requests",)}, ensure_ascii=False)[:600])
    return res


def main():
    write_user_config()
    for p in ("/work",):
        pathlib.Path(p).mkdir(parents=True, exist_ok=True)
    info = {"env": ENV}
    if VBIN:
        cp = sh(["vacant", "install"], cwd=str(HOME))
        (OUT / "install.stdout.txt").write_text(cp.stdout)
        (OUT / "install.stderr.txt").write_text(cp.stderr)
        info["install_rc"] = cp.returncode
        info["vacant_version"] = sh(["python", "-c", "import vacant_network;print(vacant_network.__version__)"]).stdout.strip()
        log("install rc", cp.returncode, cp.stdout[-800:], cp.stderr[-400:])
        if INSTALL_JSON.is_file():
            shutil.copy(INSTALL_JSON, OUT / "install.json")
        pl = HOME / ".config" / "opencode" / "plugin" / "vacant.js"
        if pl.is_file():
            shutil.copy(pl, OUT / "vacant.js")
        info["vacant_tree"] = sh(["find", str(VH), "-maxdepth", "4"]).stdout
    (OUT / "info.json").write_text(json.dumps(info, indent=2))
    results = []
    for name in (ONLY or [n for n in SCN if SURFACE == "run" or n != "DIAG"]):
        results.append(run_scenario(name))
    # collect trace + logs
    if (VH / "trace").is_dir():
        shutil.copytree(VH / "trace", OUT / "vacant_trace", dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns("*.key"))
    if EVENTS.is_file():
        shutil.copy(EVENTS, OUT / "events_all.jsonl")
    lg = HOME / ".local" / "share" / "opencode" / "log"
    if lg.is_dir():
        shutil.copytree(lg, OUT / "opencode_log", dirs_exist_ok=True)
    (OUT / "results.json").write_text(json.dumps(results, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
