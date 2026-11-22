"""rc5-final 對 rc6 的政策差分：
- 原有 13 個情境：寫回結果、結束碼、accepted、delivered_attempt、attempts、calls、專案樹逐檔 sha256 必須與 rc5-final 完全相同。
- 第 14 個情境（py_baseline_already_pass）：寫回結果與所有政策欄位完全相同，僅輸出標題不同（rc6 先講測試原本就全過）。
- 第 15 個情境（ctrl_c_interrupt）：預期不同——rc5-final 印出 Python traceback 且沒有收據；rc6 沒有 traceback、印單行中斷訊息、專案逐位元組不動、寫出標為 interrupted 的簽章收據並 exit 130。

用法：
  python3 tests/adversarial_rc5_repro/policy_diff_rc5_rc6.py [rc5_vacant_bin] [rc6_tree] [out_dir]
"""
from __future__ import annotations

import hashlib
import json
import os
import pathlib
import shutil
import signal
import subprocess
import sys
import tempfile
import textwrap
import time

PY = "/home/user1/dev/Vacant/.venv/bin/python"
DEFAULT_RC5 = pathlib.Path.home() / "dev" / "ops" / "rc5final_venv" / "bin" / "vacant"
DEFAULT_RC6 = pathlib.Path(__file__).resolve().parents[2]

RC5_BIN = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_RC5
RC6_TREE = pathlib.Path(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_RC6
OUT = pathlib.Path(sys.argv[3]) if len(sys.argv) > 3 else pathlib.Path(tempfile.mkdtemp(prefix="pdiff-rc5-rc6-"))

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

SLEEP_AGENT = textwrap.dedent(r'''
import json, os, pathlib, time
pathlib.Path("calc.py").write_text("def add(a,b): return a+b\n", encoding="utf-8")
pid_file = pathlib.Path(os.environ["PD_PID_FILE"])
tmp = pid_file.with_suffix(".tmp")
tmp.write_text(json.dumps({"agent": os.getpid()}), encoding="utf-8")
os.replace(tmp, pid_file)
time.sleep(60)
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
    (d / "calc.py").write_text(BAD)
    (d / "test_calc.py").write_text(CALC_TEST)
    (d / "old_notes.txt").write_text("remove me\n")
    (d / "keep.txt").write_text("keep\n")
    (d / "sub").mkdir()
    (d / "sub" / "data.txt").write_text("d\n")


def py_good_proj(d):
    (d / "calc.py").write_text(GOOD)
    (d / "test_calc.py").write_text(CALC_TEST)
    (d / "keep.txt").write_text("keep\n")


def npm_proj(d):
    (d / "package.json").write_text('{"name":"x","version":"1.0.0","scripts":{"test":"node m.test.js"}}')
    (d / "m.js").write_text("const h=require('helper');module.exports.val=()=>h.base()+1;\n")
    (d / "m.test.js").write_text("const m=require('./m');process.exit(m.val()===5?0:1);\n")
    nm = d / "node_modules" / "helper"
    nm.mkdir(parents=True)
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
QUEUE_TEST = textwrap.dedent('''
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
STATS_TEST = textwrap.dedent('''
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
MYCAL_TEST = textwrap.dedent('''
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


# Original 13 scenarios from policy_diff_rc4_rc5.py + scenario 14 (baseline already passing)
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
    "py_baseline_already_pass": (py_good_proj, [], [{}]),
}


def tree(d):
    out = {}
    for p in sorted(d.rglob("*")):
        rel = p.relative_to(d).as_posix()
        if p.is_symlink():
            out[rel] = "link:" + os.readlink(p)
        elif p.is_file():
            out[rel] = hashlib.sha256(p.read_bytes()).hexdigest()[:16]
        elif p.is_dir():
            out[rel] = "dir"
    return out


def _base_cmd_and_env(which: str, base: pathlib.Path) -> tuple[list[str], dict[str, str]]:
    env = {k: v for k, v in os.environ.items() if k not in ("VIRTUAL_ENV", "PYTHONPATH")}
    env.update(
        VACANT_HOME=str(base / "vh"),
        VACANT_WORK=str(base / "vw"),
        VACANT_HOOK_NO_GC="1",
    )
    if which == "rc5":
        return [str(RC5_BIN), "do"], env
    env["PYTHONPATH"] = str(RC6_TREE)
    return [PY, "-m", "vacant_network.cli", "do"], env


def run_normal(which: str, name: str):
    proj_maker, extra, plan = SCEN[name]
    base = OUT / which / name
    shutil.rmtree(base, ignore_errors=True)
    base.mkdir(parents=True)
    proj = base / "proj"
    proj.mkdir()
    proj_maker(proj)
    agent = base / "agent.py"
    agent.write_text(AGENT)
    cmd_prefix, env = _base_cmd_and_env(which, base)
    env.update(PD_STATE=str(base / "state"), PD_PLAN=json.dumps(plan))
    cmd = [
        *cmd_prefix,
        "--cmd", f"{PY} {agent} {{prompt}}",
        "--prompt", "fix it",
        "--attempt-timeout", "60",
        "--timeout", "300",
        *extra,
    ]
    p = subprocess.run(cmd, cwd=proj, env=env, capture_output=True, text=True, timeout=900)
    rj = sorted((base / "vw").glob("restart-*/result.json"))
    r = json.loads(rj[-1].read_text()) if rj else {}
    att = [(a.get("attempt"), a.get("accept"), a.get("passed"), a.get("run")) for a in r.get("attempts", [])]
    return {
        "exit": p.returncode,
        "accepted": r.get("accepted"),
        "delivered": r.get("delivered_attempt"),
        "attempts": att,
        "calls": int((base / "state").read_text()) if (base / "state").exists() else 0,
        "tree": tree(proj),
    }, p.stdout + p.stderr


def run_ctrl_c(which: str):
    base = OUT / which / "ctrl_c_interrupt"
    shutil.rmtree(base, ignore_errors=True)
    base.mkdir(parents=True)
    proj = base / "proj"
    proj.mkdir()
    py_proj(proj)
    before = tree(proj)
    agent = base / "sleep_agent.py"
    agent.write_text(SLEEP_AGENT)
    pid_file = base / "pid.json"
    cmd_prefix, env = _base_cmd_and_env(which, base)
    env["PD_PID_FILE"] = str(pid_file)
    cmd = [
        *cmd_prefix,
        "--cmd", f"{PY} {agent} {{prompt}}",
        "--prompt", "fix it",
        "--attempt-timeout", "60",
        "--timeout", "120",
    ]
    proc = subprocess.Popen(
        cmd,
        cwd=proj,
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        preexec_fn=os.setpgrp,
    )
    agent_pid = None
    try:
        deadline = time.monotonic() + 20.0
        while time.monotonic() < deadline:
            if pid_file.exists():
                agent_pid = json.loads(pid_file.read_text())["agent"]
                break
            if proc.poll() is not None:
                break
            time.sleep(0.05)
        os.killpg(proc.pid, signal.SIGINT)
        out, err = proc.communicate(timeout=20)
    finally:
        if agent_pid:
            try:
                os.kill(agent_pid, signal.SIGKILL)
            except OSError:
                pass
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=5)
    after = tree(proj)
    chains = list((base / "vh").glob("trace/projects/*/chain.ndjson"))
    has_interrupted_receipt = False
    for cp in chains:
        for line in cp.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            ev = json.loads(line)
            if ev.get("type") == "restart_receipt" and ev.get("payload", {}).get("interrupted") is True:
                has_interrupted_receipt = True
    combined = out + err
    return {
        "exit": proc.returncode,
        "tree_unchanged": before == after,
        "has_traceback": "Traceback" in combined,
        "has_interrupted_msg": ("interrupted" in out.lower() and "project unchanged" in out.lower()),
        "has_interrupted_receipt": has_interrupted_receipt,
    }, combined


same_total = 0
same_ok = 0
msg_only_ok = 0
exp_diff_ok = 0

for name in SCEN:
    a, la = run_normal("rc5", name)
    b, lb = run_normal("rc6", name)
    same = a == b
    if name == "py_baseline_already_pass":
        rc5_head = next((ln for ln in la.splitlines() if ln.startswith("[vacant] ")), "")
        rc6_head = next((ln for ln in lb.splitlines() if ln.startswith("[vacant] ")), "")
        msg_changed = (
            "acceptance passed on attempt" in rc5_head
            and "tests were already passing before the agent ran" in rc6_head
        )
        ok = same and msg_changed
        msg_only_ok += int(ok)
        tag = "SAME-POLICY" if ok else "UNEXPECTED"
        print(f"{tag:<14} {name}: exit {a['exit']}/{b['exit']} accepted {a['accepted']}/{b['accepted']} "
              f"delivered {a['delivered']}/{b['delivered']} calls {a['calls']}/{b['calls']} "
              f"attempts {a['attempts']} (headline changed={msg_changed})")
        if not ok:
            print(f"    same={same} rc5_head={rc5_head!r} rc6_head={rc6_head!r}")
    else:
        same_total += 1
        same_ok += int(same)
        tag = "SAME" if same else "DIFF"
        print(f"{tag:<14} {name}: exit {a['exit']}/{b['exit']} accepted {a['accepted']}/{b['accepted']} "
              f"delivered {a['delivered']}/{b['delivered']} calls {a['calls']}/{b['calls']} attempts {a['attempts']}")
        if not same:
            for k in a:
                if a[k] != b[k]:
                    print(f"    {k}: rc5={a[k]}\n    {' '*len(k)}  rc6={b[k]}")
            (OUT / f"{name}.rc5.log").write_text(la)
            (OUT / f"{name}.rc6.log").write_text(lb)

c5, lc5 = run_ctrl_c("rc5")
c6, lc6 = run_ctrl_c("rc6")
ctrl_ok = (
    c5["has_traceback"] is True
    and c5["has_interrupted_receipt"] is False
    and c6["exit"] == 130
    and c6["tree_unchanged"] is True
    and c6["has_traceback"] is False
    and c6["has_interrupted_msg"] is True
    and c6["has_interrupted_receipt"] is True
)
exp_diff_ok += int(ctrl_ok)
tag = "EXPECTED-DIFF" if ctrl_ok else "UNEXPECTED"
print(f"{tag:<14} ctrl_c_interrupt: rc5={c5} rc6={c6}")
if not ctrl_ok:
    (OUT / "ctrl_c.rc5.log").write_text(lc5)
    (OUT / "ctrl_c.rc6.log").write_text(lc6)

print(f"\n{same_ok}/{same_total} original scenarios identical; "
      f"{msg_only_ok}/1 baseline-pass policy identical (message-only diff); "
      f"{exp_diff_ok}/1 Ctrl-C expected diff correct")
sys.exit(0 if (same_ok == same_total and msg_only_ok == 1 and exp_diff_ok == 1) else 1)
