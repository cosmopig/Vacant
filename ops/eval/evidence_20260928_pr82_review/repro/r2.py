import importlib.util, json, pathlib, shutil, sys, tempfile, os
WT = pathlib.Path(sys.argv[1])
spec = importlib.util.spec_from_file_location("b", WT/"ops/eval/native_acceptance_bridge.py")
b = importlib.util.module_from_spec(spec); spec.loader.exec_module(b)
from vacant_network.intake import contract as C
from vacant_network.adapters.hookpolicy import HookEvent, decide_stop
from vacant_network.intake import flow

def mk(tmp):
    ws = tmp/"app"; (ws/"tests_visible").mkdir(parents=True)
    (ws/"tests_visible"/"test_visible.py").write_text("def check_add():\n    from solution import add\n    assert add(2,3)==5\n")
    (ws/"goal.md").write_text("Implement add.\n")
    return ws, tmp/"recv"
def prep(ws, recv, mode, suite=None, task="t"):
    return b.prepare(workspace=ws, task_id=task, suite=suite, deliverable="solution.py", mode=mode,
        attempts=None, feedback_rounds=3, suite_timeout_s=20, destination="dir:.vacant/native-release",
        receiver_home=recv)

print("== R2: agent repoints visible_suite in .vacant/contract.json; wrong solution ==")
tmp = pathlib.Path(tempfile.mkdtemp()); ws, recv = mk(tmp)
prep(ws, recv, "conform", task="r2")
fake = ws/"mytests"; fake.mkdir(); (fake/"test_x.py").write_text("def check_ok():\n    pass\n")
cp = ws/".vacant"/"contract.json"; raw = json.loads(cp.read_text())
print(" inputs before:", raw["inputs"])
raw["inputs"]["visible_suite"]["path"] = "mytests"; raw["inputs"]["visible_suite"]["sha256"] = C.path_sha256(fake)
cp.write_text(json.dumps(raw))
(ws/"solution.py").write_text("def add(a,b): return 0\n")
r = b.judge(workspace=ws, sandbox="none", attempt=1, receiver_home=recv)
print(" judge outcome:", r["outcome"], "| status:", r["results"][0]["status"], r["results"][0]["detail"][:60])
rel = b.release(workspace=ws, receiver_home=recv)
print(" release:", rel.get("released"), [x[:100] for x in rel.get("reasons") or []])

print("== R2b: agent deletes .vacant/ (e.g. cleanup) ==")
shutil.rmtree(ws/".vacant")
print(" judge exit:", b.main(["judge","--workspace",str(ws),"--sandbox","none","--attempt","2","--receiver-home",str(recv)]))

print("== R4: CONFORM attempt 2 from a pristine template (workspace reset) ==")
tmp = pathlib.Path(tempfile.mkdtemp()); ws, recv = mk(tmp)
tmpl = tmp/"template"; shutil.copytree(ws, tmpl)
prep(ws, recv, "conform", task="r4")
(ws/"solution.py").write_text("def add(a,b): return 0\n")
print(" attempt1:", b.judge(workspace=ws, sandbox="none", attempt=1, receiver_home=recv)["outcome"])
shutil.rmtree(ws); shutil.copytree(tmpl, ws)   # fresh attempt starts from the template
(ws/"solution.py").write_text("def add(a,b): return a+b\n")
print(" attempt2 judge exit:", b.main(["judge","--workspace",str(ws),"--sandbox","none","--attempt","2","--receiver-home",str(recv)]))
try:
    prep(ws, recv, "conform", task="r4")
    print(" re-prepare after reset OK -> attempt 2 judged:", b.judge(workspace=ws, sandbox="none", attempt=2, receiver_home=recv)["outcome"])
except Exception as e:
    print(" re-prepare:", type(e).__name__, e)

print("== R5: no solution.py ==")
tmp = pathlib.Path(tempfile.mkdtemp()); ws, recv = mk(tmp)
prep(ws, recv, "gate", task="r5")
r = b.judge(workspace=ws, sandbox="none", attempt=1, receiver_home=recv)
print(" outcome:", r["outcome"], "void", r.get("void"), (r.get("reasons") or [])[:1])

print("== R3: repair mode, receiver-owned suite not visible inside agent sandbox ==")
tmp = pathlib.Path(tempfile.mkdtemp()); ws, recv = mk(tmp)
ext = tmp/"srv_receiver_suite"; shutil.copytree(ws/"tests_visible", ext)
prep(ws, recv, "repair", suite=ext, task="r3")
(ws/"solution.py").write_text("def add(a,b): return 0\n")
hidden_from_agent = tmp/"_moved"; ext.rename(hidden_from_agent)   # agent's bwrap view: path absent
os.environ["VACANT_HOME"] = str(tmp/"agent_home")
c = C.load(ws/".vacant"/"contract.json")
ev = HookEvent(agent="pi", kind="stop", cwd=str(ws), session_id="s1")
d = decide_stop(ev, c, check_fn=lambda cc, d_: flow.check(cc, d_, sandbox="none"))
print(" stop decision:", d.action, {k: d.record.get(k) for k in ("outcome","not_agent_fixable","round")})
hidden_from_agent.rename(ext)
d = decide_stop(ev, c, check_fn=lambda cc, d_: flow.check(cc, d_, sandbox="none"))
print(" (suite visible) stop decision:", d.action, {k: d.record.get(k) for k in ("outcome","round")}, d.reason[:80].replace("\n"," "))
