"""rc4 對 rc5 的政策差分：同一組情境、同一個假 agent，分別用兩版的 `vacant do --cmd` 跑，
比較 結束碼、accepted、delivered_attempt、每次嘗試的 accept/passed/run、以及跑完後專案樹（逐檔 sha256）。
用法：python3 policy_diff.py <rc4_tree> <rc5_tree> <out_dir>
"""
import hashlib, json, os, pathlib, shutil, subprocess, sys, textwrap

PY = "/home/user1/dev/Vacant/.venv/bin/python"
RC4, RC5, OUT = map(pathlib.Path, sys.argv[1:4])

AGENT = textwrap.dedent(r'''
import json, os, pathlib, sys
state = pathlib.Path(os.environ["PD_STATE"])
n = int(state.read_text()) + 1 if state.exists() else 1
state.write_text(str(n))
plan = json.loads(os.environ["PD_PLAN"])
step = plan[min(n, len(plan)) - 1]
for rel, content in step.get("write", {}).items():
    p = pathlib.Path(rel); p.parent.mkdir(parents=True, exist_ok=True); p.write_text(content)
for rel in step.get("delete", []):
    pathlib.Path(rel).unlink(missing_ok=True)
sys.exit(step.get("rc", 0))
''')

CALC_TEST = textwrap.dedent('''
import unittest, calc
class T(unittest.TestCase):
    def test_add(self): self.assertEqual(calc.add(2, 3), 5)
    def test_sub(self): self.assertEqual(calc.sub(5, 3), 2)
    def test_mul(self): self.assertEqual(calc.mul(2, 3), 6)
''')
BAD = "def add(a,b): return a-b\ndef sub(a,b): return a+b\ndef mul(a,b): return a+b\n"
GOOD = "def add(a,b): return a+b\ndef sub(a,b): return a-b\ndef mul(a,b): return a*b\n"
PART = "def add(a,b): return a+b\ndef sub(a,b): return a-b\ndef mul(a,b): return a+b\n"
ONE = "def add(a,b): return a+b\ndef sub(a,b): return a+b\ndef mul(a,b): return a+b\n"

def py_proj(d):
    (d / "calc.py").write_text(BAD); (d / "test_calc.py").write_text(CALC_TEST)
    (d / "old_notes.txt").write_text("remove me\n"); (d / "keep.txt").write_text("keep\n")
    (d / "sub").mkdir(); (d / "sub" / "data.txt").write_text("d\n")

def npm_proj(d):
    (d / "package.json").write_text('{"name":"x","version":"1.0.0","scripts":{"test":"node m.test.js"}}')
    (d / "m.js").write_text("const h=require('helper');module.exports.val=()=>h.base()+1;\n")
    (d / "m.test.js").write_text("const m=require('./m');process.exit(m.val()===5?0:1);\n")
    nm = d / "node_modules" / "helper"; nm.mkdir(parents=True)
    (nm / "index.js").write_text("module.exports.base=()=>3;\n")
    (nm / "package.json").write_text('{"name":"helper","main":"index.js"}')

def none_proj(d):
    (d / "README.txt").write_text("hello\n")

def check_proj(d):
    (d / "app.py").write_text("v = 1\n")
    (d / "check.py").write_text("import app, sys; sys.exit(0 if app.v == 2 else 1)\n")

SOL_TEST = textwrap.dedent('''
import unittest
from solution import add
class T(unittest.TestCase):
    def test_add(self): self.assertEqual(add(2, 3), 5)
''')

def new_mod_proj(d):
    (d / "test_solution.py").write_text(SOL_TEST)

QUEUE_BAD = textwrap.dedent('''\
class Q:
    def __init__(self): self.items = []
    def push(self, x): self.items.append(x)
    def pop(self): return self.items.pop()
''')
QUEUE_GOOD = textwrap.dedent('''\
class Q:
    def __init__(self): self.items = []
    def push(self, x): self.items.append(x)
    def pop(self): return self.items.pop(0)
''')
QUEUE_TEST = textwrap.dedent('''\
import unittest
from queue import Q
class T(unittest.TestCase):
    def test_fifo(self):
        q = Q(); q.push(1); q.push(2); self.assertEqual(q.pop(), 1)
''')

def queue_proj(d):
    (d / "queue.py").write_text(QUEUE_BAD)
    (d / "test_queue.py").write_text(QUEUE_TEST)

STATS_BAD = "def median(xs):\n    return sorted(xs)[0]\n"
STATS_BROKEN = "def median(xs):\n    return None\n"
STATS_TEST = textwrap.dedent('''\
import unittest
from statistics import median
class T(unittest.TestCase):
    def test_median(self):
        self.assertEqual(median([3, 1, 2]), 2)
        self.assertEqual(median([5, 9, 7]), 7)
''')

def stats_proj(d):
    (d / "statistics.py").write_text(STATS_BAD)
    (d / "test_stats.py").write_text(STATS_TEST)

MYCAL_BAD = "def days_in_feb(y):\n    return 28\n"
MYCAL_GOOD = "def days_in_feb(y):\n    return 29 if (y % 4 == 0 and y % 100 != 0) or y % 400 == 0 else 28\n"
MYCAL_TEST = textwrap.dedent('''\
import unittest
import mycal
class T(unittest.TestCase):
    def test_leap(self):
        self.assertEqual(mycal.days_in_feb(2024), 29)
        self.assertEqual(mycal.days_in_feb(2023), 28)
''')

def mycal_pkg_proj(d):
    (d / "mycal.py").write_text(MYCAL_BAD)
    (d / "tests").mkdir()
    (d / "tests" / "__init__.py").write_text("")
    (d / "tests" / "test_mycal.py").write_text(MYCAL_TEST)

SCEN = {
 "py_fix_first": (py_proj, [], [{"write": {"calc.py": GOOD, "new_mod.py": "X=1\n"}, "delete": ["old_notes.txt"]}]),
 "py_fail_then_fix": (py_proj, [], [{"write": {"calc.py": BAD + "#a1\n"}}, {"write": {"calc.py": GOOD}}]),
 "py_never_best_is_2": (py_proj, [], [{"write": {"calc.py": ONE}}, {"write": {"calc.py": PART}}, {"write": {"calc.py": ONE + "#3\n"}}]),
 "py_tamper_test": (py_proj, [], [{"write": {"test_calc.py": "import unittest\nclass T(unittest.TestCase):\n    def test_x(self): pass\n"}}]),
 "py_rc_nonzero_but_pass": (py_proj, [], [{"write": {"calc.py": GOOD}, "rc": 3}]),
 "py_delete_subdir_file": (py_proj, [], [{"write": {"calc.py": GOOD}, "delete": ["sub/data.txt"]}]),
 "py_new_module": (new_mod_proj, [], [{"write": {"solution.py": "def add(a, b): return a + b\n"}}]),
 "none_add": (none_proj, [], [{"write": {"out.txt": "done\n"}}]),
 "check_fix_second": (check_proj, ["--check", f"{PY} check.py"], [{"write": {"app.py": "v = 3\n"}}, {"write": {"app.py": "v = 2\n"}}]),
 "npm_fix_second": (npm_proj, [], [{"write": {"m.js": "module.exports.val=()=>4;\n"}}, {"write": {"m.js": "const h=require('helper');module.exports.val=()=>h.base()+2;\n"}}]),
 "py_stdlib_name_fixed": (queue_proj, [], [{"write": {"queue.py": QUEUE_GOOD}}]),
 "py_stdlib_name_broken": (stats_proj, [], [{"write": {"statistics.py": STATS_BROKEN}}]),
 "py_tests_package": (mycal_pkg_proj, [], [{"write": {"mycal.py": MYCAL_GOOD}}]),
}

EXPECTED_DIFF = {
    "py_stdlib_name_fixed": {"accepted": True, "exit": 0},
    "py_stdlib_name_broken": {"accepted": False, "exit": 40},
    "py_tests_package": {"accepted": True, "exit": 0},
}

def tree(d):
    out = {}
    for p in sorted(d.rglob("*")):
        rel = p.relative_to(d).as_posix()
        if p.is_symlink(): out[rel] = "link:" + os.readlink(p)
        elif p.is_file(): out[rel] = hashlib.sha256(p.read_bytes()).hexdigest()[:16]
        elif p.is_dir(): out[rel] = "dir"
    return out

def run(tree_root, name):
    proj_maker, extra, plan = SCEN[name]
    base = OUT / tree_root.name / name
    shutil.rmtree(base, ignore_errors=True); base.mkdir(parents=True)
    proj = base / "proj"; proj.mkdir(); proj_maker(proj)
    agent = base / "agent.py"; agent.write_text(AGENT)
    env = {k: v for k, v in os.environ.items() if k != "VIRTUAL_ENV"}
    env.update(PYTHONPATH=str(tree_root), VACANT_HOME=str(base / "vh"), VACANT_WORK=str(base / "vw"),
               PD_STATE=str(base / "state"), PD_PLAN=json.dumps(plan), VACANT_HOOK_NO_GC="1")
    cmd = [PY, "-m", "vacant_network.cli", "do", "--cmd", f"{PY} {agent} {{prompt}}", "--prompt", "fix it",
           "--attempt-timeout", "60", "--timeout", "300", *extra]
    p = subprocess.run(cmd, cwd=proj, env=env, capture_output=True, text=True, timeout=900)
    rj = sorted((base / "vw").glob("restart-*/result.json"))
    r = json.loads(rj[-1].read_text()) if rj else {}
    att = [(a.get("attempt"), a.get("accept"), a.get("passed"), a.get("run")) for a in r.get("attempts", [])]
    return {"exit": p.returncode, "accepted": r.get("accepted"), "delivered": r.get("delivered_attempt"),
            "attempts": att, "calls": int((base / "state").read_text()) if (base / "state").exists() else 0,
            "tree": tree(proj)}, p.stdout + p.stderr

same_total = 0
same_ok = 0
exp_total = 0
exp_ok = 0
for name in SCEN:
    a, la = run(RC4, name); b, lb = run(RC5, name)
    same = a == b
    if name in EXPECTED_DIFF:
        exp_total += 1
        want = EXPECTED_DIFF[name]
        rc5_correct = (b["accepted"] == want["accepted"] and b["exit"] == want["exit"])
        ok = (not same) and rc5_correct
        exp_ok += int(ok)
        tag = "EXPECTED-DIFF" if ok else "UNEXPECTED"
        print(f"{tag:<14} {name}: exit {a['exit']}/{b['exit']} accepted {a['accepted']}/{b['accepted']} "
              f"delivered {a['delivered']}/{b['delivered']} calls {a['calls']}/{b['calls']} "
              f"attempts rc4={a['attempts']} rc5={b['attempts']}")
        if not ok:
            print(f"    expected diff with rc5={want}, got same={same} rc5=(exit={b['exit']}, accepted={b['accepted']})")
            (OUT / f"{name}.rc4.log").write_text(la); (OUT / f"{name}.rc5.log").write_text(lb)
    else:
        same_total += 1
        same_ok += int(same)
        tag = "SAME" if same else "DIFF"
        print(f"{tag:<14} {name}: exit {a['exit']}/{b['exit']} accepted {a['accepted']}/{b['accepted']} "
              f"delivered {a['delivered']}/{b['delivered']} calls {a['calls']}/{b['calls']} attempts {a['attempts']}")
        if not same:
            for k in a:
                if a[k] != b[k]: print(f"    {k}: rc4={a[k]}\n    {' '*len(k)}  rc5={b[k]}")
            (OUT / f"{name}.rc4.log").write_text(la); (OUT / f"{name}.rc5.log").write_text(lb)
print(f"\n{same_ok}/{same_total} identical; {exp_ok}/{exp_total} expected differences correct")
sys.exit(0 if (same_ok == same_total and exp_ok == exp_total) else 1)
