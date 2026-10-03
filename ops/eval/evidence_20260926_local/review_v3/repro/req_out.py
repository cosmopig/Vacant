import sys, pathlib, glob, types, os
sys.path.insert(0, "/home/user/Vacant")
from vacant_network.trace import evidence as E

files = ["data/acquirer_countries.csv","data/fees.json","data/manual.md","data/merchant_category_codes.csv",
         "data/merchant_data.json","data/payments-readme.md","data/payments.csv"]
class TR:
    initial = "i0"
    def index(self, idx): return {f: None for f in files}
    def latest_index(self): return "i0"
class Rec: workspace = pathlib.Path("/app")
ev = E.Evidence.__new__(E.Evidence)
ev.rec = Rec(); ev.tr = TR(); ev.notes = {}
root = "/tmp/claude-0/-home-user-Vacant/95e2b6b6-418f-504c-a59e-fd594ef13041/scratchpad/dabstep_pinned/formal"
for d in sorted(glob.glob(root + "/dabstep-*")):
    t = open(d + "/instruction.md").read()
    outs = ev.requested_outputs([t])
    named, in_dirs = ev.materials([t], "i0")
    given = set(named) | set(in_dirs)
    extra = [(r, raw) for r, raw in outs if r != "answer.txt" and r not in given]
    if extra or outs != [("answer.txt", "/app/answer.txt")]:
        print(os.path.basename(d), outs, "given:", sorted(given)[:3], "EXTRA:", extra)
print("done")
