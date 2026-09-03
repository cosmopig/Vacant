"""R440W: two-way validate the CONFORM decision gauge (visible_check) on the exact 179."""
import json, sys, os
sys.path.insert(0, os.getcwd())
from ops.gain.gain_run import (load_tasks, _canonical_solutions,
                               _visible_test_slicer, meets_demand)

tasks = load_tasks("evalplus", "g-r212-route-20260828", 179)
refs = _canonical_solutions("evalplus")
print(f"loaded tasks = {len(tasks)}", flush=True)

rows = []
for i, t in enumerate(tasks, 1):
    tid = t["task_id"]
    ep = t.get("entry_point")
    vis = t.get("visible_check", {}).get("code")
    r = {"task_id": tid, "entry_point": ep, "has_ref": bool(refs.get(tid)),
         "has_visible": bool(vis)}
    sl = _visible_test_slicer(vis) if vis else None
    r["slicer_ok"] = sl is not None
    r["n_visible_tests"] = sl[0] if sl else None
    if vis and refs.get(tid):
        ok_g, msg_g = meets_demand(refs[tid], vis, entry_point=ep)
        ok_b, _ = meets_demand(f"def {ep or '_f'}(*a, **k):\n    return None\n",
                               vis, entry_point=ep)
        r["ref_pass_visible"] = bool(ok_g)
        r["stub_rejected_visible"] = bool(not ok_b)
        r["err"] = msg_g[:200]
    rows.append(r)
    if i % 25 == 0:
        print(f"  ...{i}/{len(tasks)}", flush=True)

json.dump(rows, open("/dev/shm/r440w_rows.json", "w"))
cov = [r for r in rows if r["has_ref"] and r["has_visible"]]
m1 = sum(r["ref_pass_visible"] for r in cov)
m2 = sum(r["stub_rejected_visible"] for r in cov)
print("\n=== R440W ===")
print(f"M3 covered (has ref & visible) = {len(cov)}/{len(tasks)}")
print(f"M1 ref passes visible          = {m1}/{len(cov)}")
print(f"M2 stub rejected by visible    = {m2}/{len(cov)}")
print(f"M4 slicer recognised           = {sum(r['slicer_ok'] for r in rows)}/{len(rows)}")
zero = [r["task_id"] for r in rows if r["n_visible_tests"] == 0]
print(f"M4 n_visible_tests == 0        = {len(zero)}  {zero[:10]}")
print(f"no visible_check at all        = {sum(not r['has_visible'] for r in rows)}")
print("M1 failures:", [r["task_id"] for r in cov if not r["ref_pass_visible"]][:15])
print("M2 failures:", [r["task_id"] for r in cov if not r["stub_rejected_visible"]][:15])
