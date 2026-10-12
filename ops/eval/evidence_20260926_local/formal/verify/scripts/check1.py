import json, collections
rows = json.load(open("/tmp/claude-0/verify_formal/rows.json"))
C = collections.Counter
print("per arm/sample:", C((r["arm"], r["sample"]) for r in rows))
keys = C((r["task"], r["arm"], r["sample"]) for r in rows)
print("dup cells:", [k for k,v in keys.items() if v>1])
print("n_trials_in_job !=1:", [(r["job"], r["n_trials_in_job"]) for r in rows if r["n_trials_in_job"]!=1])
tasks = sorted({r["task"] for r in rows}, key=int); print("tasks", len(tasks), "has 5/70:", "5" in tasks, "70" in tasks)
# every task x arm x sample present
miss = [(t,a,s) for t in tasks for a in ("A","C1","C2") for s in (1,2,3) if (t,a,s) not in keys]
print("missing cells", miss)
print("agent by arm:", C((r["arm"], r["agent"]) for r in rows))
print("tag ok:", C(r["tag"] == f"v3local-g12-off-{r['arm']}-{r['task']}-s{r['sample']}" for r in rows))
print("job name == tag:", C(r["job"] == r["tag"] for r in rows))
print("think:", C(r["think"] for r in rows)); print("up:", C((r["arm"], r["up"]) for r in rows))
print("kwargs:", C(json.dumps(r["kwargs"], sort_keys=True) for r in rows)); print("model:", C(r["model"] for r in rows))
print("datasets:", C(json.dumps(r["datasets"][0]["path"]) for r in rows))
print("dataset task name match:", C(r["datasets"][0]["task_names"] == [f"dabstep-{r['task']}"] for r in rows))
print("pipx/vacant in log by arm:", C((r["arm"], r["pipx_in_log"], r["vacant_install_in_log"]) for r in rows))
print("vacant_home exists by arm:", C((r["arm"], r["vh_exists"]) for r in rows))
print("ext hash by arm:", C((r["arm"], r["ext"]) for r in rows))
print("vc c_arm_ok by arm:", C((r["arm"], (r["vc"] or {}).get("c_arm_ok") if isinstance(r["vc"], dict) else r["vc"]) for r in rows))
print("install_json:", C((r["arm"], json.dumps((r["vc"] or {}).get("install_json")) if isinstance(r["vc"], dict) else None) for r in rows))
print("nudges>0 by arm:", C((r["arm"], bool((r["vc"] or {}).get("nudges"))) for r in rows if isinstance(r["vc"], dict)))
print("ended_notes>0 by arm:", C((r["arm"], bool((r["vc"] or {}).get("ended_notes"))) for r in rows if isinstance(r["vc"], dict)))
print("delivery singular/plural by arm:", C((r["arm"], r["dm_singular"], r["dm_plural_turns"]) for r in rows))
# rewards
def norm(x):
    if x is None: return None
    return float(x)
bad = [(r["task"],r["arm"],r["sample"],r["reward"],r["reward_txt"]) for r in rows if (r["reward_txt"] is None) or norm(r["reward"]) != float(r["reward_txt"])]
print("reward mismatch vs reward.txt:", bad)
print("reward values:", C(r["reward"] for r in rows))
print("exceptions:", C((r["arm"], r["sample"], r["exc"]) for r in rows if r["exc"]))
print([ (r["task"],r["arm"],r["sample"],r["exc"],r["reward"]) for r in rows if r["exc"]])
