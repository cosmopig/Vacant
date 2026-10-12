"""R8: prepare validates test_*.py recursively and the pin hashes the whole tree, but run_suite only runs top-level *.py."""
import importlib.util, pathlib, tempfile, os
WT = pathlib.Path(os.environ["WT"])
spec = importlib.util.spec_from_file_location("b", WT / "ops/eval/native_acceptance_bridge.py")
b = importlib.util.module_from_spec(spec); spec.loader.exec_module(b)
for layout in ("top+nested", "nested-only", "data-file"):
    tmp = pathlib.Path(tempfile.mkdtemp())
    os.environ["VACANT_HOME"] = str(tmp / "h")
    ws = tmp / "app"; ws.mkdir()
    rs = tmp / "suite"; (rs / "sub").mkdir(parents=True)
    if layout == "top+nested":
        (rs / "test_a.py").write_text("def check_a():\n    from solution import add\n    assert add(2, 3) == 5\n")
        (rs / "sub/test_b.py").write_text("def check_b():\n    from solution import add\n    assert add(-1, -1) == -2\n")
        sol = "def add(a, b): return abs(a) + abs(b)\n"      # passes test_a, fails nested test_b
    elif layout == "nested-only":
        (rs / "sub/test_b.py").write_text("def check_b():\n    from solution import add\n    assert add(-1, -1) == -2\n")
        sol = "def add(a, b): return a + b\n"               # correct
    else:
        (rs / "cases.json").write_text('[[2, 3, 5], [-1, -1, -2]]')
        (rs / "test_a.py").write_text("import json, pathlib\ndef check_a():\n    from solution import add\n"
                                      "    for a, b_, c in json.loads((pathlib.Path(__file__).parent / 'cases.json').read_text()):\n"
                                      "        assert add(a, b_) == c\n")
        sol = "def add(a, b): return a + b\n"               # correct
    b.prepare(workspace=ws, task_id="T", suite=rs, deliverable="solution.py", mode="gate",
              attempts=None, feedback_rounds=3, suite_timeout_s=20,
              destination="dir:.vacant/native-release", receiver_home=tmp / "rh")
    (ws / "solution.py").write_text(sol)
    j = b.judge(workspace=ws, sandbox="none", attempt=1, receiver_home=tmp / "rh")
    print(f"{layout:12s} prepare=ok judge={j['outcome']} :: {j['results'][0]['detail'][:110]!r}")
