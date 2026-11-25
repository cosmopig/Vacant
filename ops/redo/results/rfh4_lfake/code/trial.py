import json, os, pathlib, shutil, sys
from vacant_network.adapters import agents as A
from vacant_network.adapters import run as RUN
from vacant_network.adapters.hookpolicy import feedback_text
from vacant_network.intake import contract as C
from vacant_network.intake import flow, keys
root = pathlib.Path(sys.argv[1]); mode = sys.argv[2]
os.environ["VACANT_HOME"] = str(root / mode / "vh"); os.environ["VACANT_WORK"] = str(root / mode / "work")
keys.init_local()
p = root / mode / "proj"
shutil.copytree(pathlib.Path(os.path.expanduser("~/dev/ops/ref/bm_tasks/polyglot_py/pg_proverb/workspace")), p)
(p / ".vacant").mkdir()
raw = C.scaffold("pg_proverb", deliverable=["proverb.py"])
raw["inputs"] = {"tests": {"path": "proverb_test.py"}}
raw["claims"] = [{"id": "tests", "verifier": "command", "authority": "fact",
                  "params": {"argv": ["sh", "-c", "cp \"$VACANT_INPUT_TESTS\" proverb_test.py && python3 -m unittest -q proverb_test"], "timeout_s": 120}}]
raw["attempts"] = {"max": 3}
cp = p / ".vacant" / "contract.json"; cp.write_text(json.dumps(raw)); C.lock(cp)
log = root / mode / "prompts"; log.mkdir(); os.environ["LFAKE_LOG"] = str(log)
task = flow.open_task(cp)
prompt = (pathlib.Path(os.path.expanduser("~/dev/ops/ref/bm_tasks/polyglot_py/pg_proverb/instruction.txt")).read_text().strip())
res = RUN.do(task, agent="generic", build=A.generic_build([sys.executable, "-I", os.environ["LFAKE_AGENT"], "{prompt}"]),
             prompt=prompt, sandbox="none", timeout_s=600, feedback=lambda r: feedback_text(r, task.contract), feedback_mode=mode)
print(mode, res.get("outcome"), len(res["attempts"]), res.get("stopped"), [a.get("failing_required") for a in res["attempts"]], pathlib.Path(res["workspace"]).name)
