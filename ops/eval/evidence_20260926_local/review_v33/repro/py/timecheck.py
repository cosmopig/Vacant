import json, os, pathlib, sys, time
root = pathlib.Path(sys.argv[1])
os.environ["HOME"] = str(root / "home"); os.environ["VACANT_HOME"] = str(root / "vh")
sys.path.insert(0, "/home/user/Vacant")
from vacant_network.trace import zerostop
from vacant_network.trace.recorder import Recorder
app = root / "app"
rec = Recorder(app)
n = sum(1 for _ in open(rec.chain_path))
# fresh (no verified mark) vs incremental
st = zerostop._load_state(rec); st.pop("verified", None); zerostop._save_state(rec, st)
t = time.time(); out = zerostop._run_child({"ws": str(app), "platform": "pi", "session": "OLD", "final_text": None})
t1 = time.time() - t
t = time.time(); out = zerostop._run_child({"ws": str(app), "platform": "pi", "session": "OLD", "final_text": None})
t2 = time.time() - t
print(json.dumps({"chain_entries": n, "check_from_genesis_s": round(t1, 2), "check_incremental_s": round(t2, 2), "ran": out.get("ran")}))
