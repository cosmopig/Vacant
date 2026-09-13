"""P-R671-7 conservation: hidden-side probe output must be bit-identical
before (git HEAD, pre-patch) and after (working tree) the R671 change."""
import sys, os, json, subprocess, importlib.util, pathlib
sys.path.insert(0, os.getcwd())

pre = pathlib.Path("/dev/shm/r671_gain_run_pre.py")
pre.write_text(subprocess.run(
    ["git", "show", "HEAD:ops/gain/gain_run.py"], capture_output=True,
    text=True, check=True).stdout, encoding="utf-8")

def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec); sys.modules[name] = m
    spec.loader.exec_module(m); return m

POST = load("ops/gain/gain_run.py", "gr_post")
PRE  = load(str(pre), "gr_pre")

BANK, SEED, N = "evalplus", "g-r212-route-20260828", 8
tasks = POST.load_tasks(BANK, SEED, N)
sink = lambda o: None
a = PRE.probe_instrument(tasks, sink, sample=0 or N, bank=BANK)
b = POST.probe_instrument(tasks, sink, sample=0 or N, bank=BANK)

KEYS = ("n", "ref_pass", "broken_rejected", "detail")
diffs = [k for k in KEYS if json.dumps(a[k], sort_keys=True) != json.dumps(b[k], sort_keys=True)]
print("P-R671-7 hidden-side conserved keys:", KEYS)
print("pre :", {k: a[k] for k in KEYS[:3]})
print("post:", {k: b[k] for k in KEYS[:3]})
print("detail sha equal:", json.dumps(a["detail"], sort_keys=True) == json.dumps(b["detail"], sort_keys=True))
print("DIFF COUNT =", len(diffs), diffs)
print("new visible keys present:", sorted(k for k in b if k.startswith("visible")))
print("visible numbers (n=%d):" % N,
      {k: b[k] for k in ("visible_n", "visible_ref_pass", "visible_stub_rejected")})
print("PRE has visible keys:", sorted(k for k in a if k.startswith("visible")), "(must be empty)")
sys.exit(0 if not diffs else 1)
