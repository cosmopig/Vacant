import importlib.util, json, pathlib, shutil, sys, tempfile, os
WT = pathlib.Path(sys.argv[1])
spec = importlib.util.spec_from_file_location("b", WT/"ops/eval/native_acceptance_bridge.py")
b = importlib.util.module_from_spec(spec); spec.loader.exec_module(b)

def mk(tmp):
    ws = tmp/"app"; (ws/"tests_visible").mkdir(parents=True)
    (ws/"tests_visible"/"test_visible.py").write_text("def check_add():\n    from solution import add\n    assert add(2,3)==5\n")
    (ws/"goal.md").write_text("Implement add.\n")
    return ws, tmp/"recv"

def prep(ws, recv, mode, suite=None, task="t"):
    return b.prepare(workspace=ws, task_id=task, suite=suite, deliverable="solution.py", mode=mode,
        attempts=None, feedback_rounds=3, suite_timeout_s=20, destination="dir:.vacant/native-release",
        receiver_home=recv)

print("== R1: benign file added to in-workspace suite; correct solution ==")
tmp = pathlib.Path(tempfile.mkdtemp()); ws, recv = mk(tmp)
prep(ws, recv, "conform", task="r1")
(ws/"solution.py").write_text("def add(a,b): return a+b\n")
(ws/"tests_visible"/"test_extra.py").write_text("def check_more():\n    from solution import add\n    assert add(0,0)==0\n")
for k in (1,2):
    r = b.judge(workspace=ws, sandbox="none", attempt=k, receiver_home=recv)
    print(" attempt", k, "outcome", r["outcome"], "|", r["results"][0]["status"], r["results"][0]["detail"][:90])
print(" exit code:", b.main(["judge","--workspace",str(ws),"--sandbox","none","--attempt","3","--receiver-home",str(recv)]))

print("== R2: agent edits .vacant/contract.json (required:false); wrong solution ==")
tmp = pathlib.Path(tempfile.mkdtemp()); ws, recv = mk(tmp)
prep(ws, recv, "conform", task="r2")
cp = ws/".vacant"/"contract.json"; raw = json.loads(cp.read_text())
raw["claims"][0]["required"] = False; cp.write_text(json.dumps(raw))
(ws/"solution.py").write_text("def add(a,b): return 0\n")
r = b.judge(workspace=ws, sandbox="none", attempt=1, receiver_home=recv)
print(" judge outcome:", r["outcome"], "| visible status:", r["results"][0]["status"])
rel = b.release(workspace=ws, receiver_home=recv)
print(" release:", rel.get("released"), rel.get("reasons"))

print("== R2b: agent deletes .vacant/ ==")
shutil.rmtree(ws/".vacant")
print(" judge exit:", b.main(["judge","--workspace",str(ws),"--sandbox","none","--attempt","2","--receiver-home",str(recv)]))

print("== R5: no solution.py (timeout without file) ==")
tmp = pathlib.Path(tempfile.mkdtemp()); ws, recv = mk(tmp)
prep(ws, recv, "gate", task="r5")
r = b.judge(workspace=ws, sandbox="none", attempt=1, receiver_home=recv)
print(" outcome:", r["outcome"], r.get("void"), (r.get("reasons") or [])[:2], r.get("results", [{}])[0].get("status") if r.get("results") else None)
