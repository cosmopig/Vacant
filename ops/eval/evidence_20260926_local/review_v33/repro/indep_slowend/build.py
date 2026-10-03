"""Build a small pi record through the real hook.handle, then write the real pi extension."""
import json, os, pathlib, sys
root = pathlib.Path(sys.argv[1])
os.environ["HOME"] = str(root / "home"); os.environ["VACANT_HOME"] = str(root / "vh")
for k in ("VACANT_TRACE", "VACANT_MODE", "VACANT_HOOK_NO_STOP", "VACANT_FEEDBACK_MODE"):
    os.environ.pop(k, None)
(root / "home").mkdir(parents=True, exist_ok=True)
from vacant_network.adapters import hook, agents as AG, install as INS
p = INS.state_root() / "install.json"; p.parent.mkdir(parents=True, exist_ok=True)
p.write_text(json.dumps({"agents": {}, "mode": "evidence"}))
app = root / "app"; (app / "data").mkdir(parents=True, exist_ok=True)
(app / "data" / "sales.csv").write_text("date,amount\n2026-07-01,1200\n2026-07-02,845\n")
ASK = ("Answer the question using the files in data/. Question: what is the total amount? "
       "Write the answer to /app/answer.txt as a single number.")
(root / "ext.mjs").write_text(AG.pi_extension_text())   # the real installed extension text (stop = 600 s)
print("built", app)
