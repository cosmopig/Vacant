"""R671 end-to-end defect injection: drives the REAL main() of gain_run.py,
mutating only the task source, so the actual wired gate lines are executed."""
import sys, os, copy
sys.path.insert(0, os.getcwd())
import ops.gain.gain_run as G

MODE = sys.argv[1]
_real_load = G.load_tasks

ALWAYS_PASS = 'print("ok")\n'
ALWAYS_FAIL = 'raise SystemExit(1)\n'

def fake_load(bank, seed, n, **kw):
    tasks = copy.deepcopy(_real_load(bank, seed, n, **kw))
    for i, t in enumerate(tasks):
        if MODE == "mv1":                      # visible gauge accepts everything
            t["visible_check"]["code"] = ALWAYS_PASS
        elif MODE == "mv2":                    # visible gauge rejects everything
            t["visible_check"]["code"] = ALWAYS_FAIL
        elif MODE == "mv3":                    # coverage silently drops to 0
            t.pop("visible_check", None)
        elif MODE == "mv4":                    # coverage silently drops to 1
            if i > 0:
                t.pop("visible_check", None)
        elif MODE == "mv5_off":                # mv1 defect, but arm has no CONFORM
            t["visible_check"]["code"] = ALWAYS_PASS
        elif MODE == "clean":
            pass
        else:
            raise SystemExit(f"unknown mode {MODE}")
    return tasks

G.load_tasks = fake_load
sys.argv = ["gain_run.py"] + sys.argv[2:]
G.main()
