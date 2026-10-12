import sys, json
sys.path.insert(0, "/home/user/Vacant/ops/eval/local")
import analyze_local as al
A="/tmp/claude-0/-home-user-Vacant/95e2b6b6-418f-504c-a59e-fd594ef13041/scratchpad/local/analysis_formal"
S="/tmp/claude-0/-home-user-Vacant/95e2b6b6-418f-504c-a59e-fd594ef13041/scratchpad/local"
# recompute cells from raw (reads only), then summarize
rows = al.cells(__import__("pathlib").Path(S+"/formal_v3"), __import__("pathlib").Path(S+"/ledger"), __import__("pathlib").Path("/tmp/claude-0/-home-user-Vacant/95e2b6b6-418f-504c-a59e-fd594ef13041/scratchpad/dabstep_pinned/formal"), "v3local")
summ = al.summarize(rows, ("C2","A"), [("C1","A"),("C2","C1")])
old = json.load(open(A+"/summary.json"))
for k in ("per_arm_sample","primary","secondary","pooled_per_task","noise_between_samples","paired_within_sample"):
    print(k, "same" if json.dumps(summ[k], sort_keys=True, default=str)==json.dumps(old[k], sort_keys=True, default=str) else "DIFFERENT")
oldc = json.load(open(A+"/cells.json"))
strip = lambda rs: sorted((r["task"], r["arm"], r["sample"], r["reward"], r["job"], r["trial"], r["upstream"], r["infra_void"], r["answer_file"]) for r in rs)
print("cells core fields same:", strip(rows) == strip(oldc))
