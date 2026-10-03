import importlib.util, pathlib, os, sys
WT = pathlib.Path(os.environ["WT"])
spec = importlib.util.spec_from_file_location("b", WT / "ops/eval/native_acceptance_bridge.py")
b = importlib.util.module_from_spec(spec); spec.loader.exec_module(b)
base = pathlib.Path(sys.argv[1])
ws = base / "app"; ws.mkdir(parents=True)
rs = base / "srv/eval/receiver/T/tests_visible"; rs.mkdir(parents=True)
(rs / "test_visible.py").write_text("def check_add():\n    from solution import add\n    assert add(2, 3) == 5\n")
rh = base / "srv/eval/receiver/T/vacant"
os.environ["VACANT_HOME"] = str(base / "evalhome")
b.prepare(workspace=ws, task_id="T", suite=rs, deliverable="solution.py", mode="repair",
          attempts=None, feedback_rounds=3, suite_timeout_s=20,
          destination="dir:.vacant/native-release", receiver_home=rh)
(ws / "solution.py").write_text("def add(a, b): return 0\n")
