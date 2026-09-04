import subprocess, json, glob, os, time, sys
ROOT = "/home/user1/vacant/Vacant"
mods = sorted(glob.glob(os.path.join(ROOT, "tests/test_*.py")))
env = dict(os.environ, TMPDIR="/dev/shm", PYTHONDONTWRITEBYTECODE="1")
out = []
for m in mods:
    rel = os.path.relpath(m, ROOT)
    t0 = time.time()
    try:
        p = subprocess.run([sys.executable, "ops/run_tests_nopytest.py", rel],
                           cwd=ROOT, env=env, capture_output=True, text=True, timeout=120)
        rc, so, se = p.returncode, p.stdout, p.stderr
        timed_out = False
    except subprocess.TimeoutExpired as e:
        rc, so, se, timed_out = -9, (e.stdout or b"").decode("utf8","replace"), (e.stderr or b"").decode("utf8","replace"), True
    out.append({"module": rel, "rc": rc, "timeout": timed_out,
                "secs": round(time.time()-t0, 1), "stdout": so, "stderr": se})
    print(f"{rel:45s} rc={rc} {'TIMEOUT' if timed_out else ''} {round(time.time()-t0,1)}s", flush=True)
json.dump(out, open("/dev/shm/r468_sweep_raw.json", "w"), ensure_ascii=False, indent=1)
print("modules:", len(out))
