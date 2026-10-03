import sys, json, collections
sys.path.insert(0, "/tmp/claude-0/verify_formal")
from load import load
from stats import *
rows, _ = load()
alltasks = sorted({k[0] for k in rows}, key=int)
tasks77 = [t for t in alltasks if t not in ("5", "70")]
S = [1, 2, 3]
d = per_task_diffs(rows, "A", "C2", tasks77, S)
print("distribution of C2-A per-task diffs:", sorted(collections.Counter(str(v) for v in d.values()).items()))
for nm, (x, y) in {"C2_vs_A": ("A", "C2"), "C1_vs_A": ("A", "C1"), "C2_vs_C1": ("C1", "C2")}.items():
    print(json.dumps(report(nm, per_task_diffs(rows, x, y, tasks77, S))))
# frozen function on float diffs
sys.path.insert(0, "/home/user/Vacant")
from vacant_network.research import wilcoxon_signed_rank_exact
fl = []
for t in tasks77:
    a = [int(rows[(t, "A", s)]["reward"] == 1) for s in S]; c = [int(rows[(t, "C2", s)]["reward"] == 1) for s in S]
    fl.append(sum(c) / 3 - sum(a) / 3)
print("frozen fn on float diffs:", wilcoxon_signed_rank_exact([x for x in fl if x != 0]))
print("distinct float |diffs|:", sorted(set(abs(x) for x in fl if x != 0)))
