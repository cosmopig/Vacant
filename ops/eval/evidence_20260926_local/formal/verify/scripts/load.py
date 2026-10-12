import json, pathlib, re
ROOT = pathlib.Path("/tmp/claude-0/-home-user-Vacant/95e2b6b6-418f-504c-a59e-fd594ef13041/scratchpad/local/formal_v3")
def load(include_void_first=False):
    rows = {}
    dup = []
    for res in sorted(ROOT.glob("g12-off-*-s*/*/dabstep-*__*/result.json")):
        trial = res.parent
        arm_dir = trial.parents[1].name
        arm, s = arm_dir.removeprefix("g12-off-").rsplit("-s", 1)
        task = trial.name.split("__")[0].removeprefix("dabstep-")
        job = trial.parent.name
        # sanity: job name matches arm/task/sample
        assert job == f"v3local-g12-off-{arm}-{task}-s{s}", (job, arm, task, s)
        r = json.loads(res.read_text())
        vr = r.get("verifier_result") or {}
        reward = (vr.get("rewards") or {}).get("reward")
        cfg = r["config"]["agent"]["env"]["OPENROUTER_BASE_URL"]
        m = re.search(r"/up/([^/]+)/", cfg)
        up = m.group(1) if m else None
        tag = re.search(r"/t/([^/]+)/", cfg).group(1)
        assert tag == job, (tag, job)
        try:
            vout = (trial / "verifier" / "test-stdout.txt").read_text()
        except OSError:
            vout = None
        rtxt = None
        try:
            rtxt = (trial / "verifier" / "reward.txt").read_text().strip()
        except OSError:
            pass
        key = (task, arm, int(s))
        row = dict(task=task, arm=arm, sample=int(s), reward=reward, reward_txt=rtxt, upstream=up,
                   started=r.get("started_at"), exc=(r.get("exception_info") or {}).get("exception_type"),
                   answer_missing=(vout is not None and "answer.txt not found" in vout), path=str(trial))
        if key in rows:
            dup.append(key)
        rows[key] = row
    return rows, dup
if __name__ == "__main__":
    rows, dup = load()
    print(len(rows), "dups", dup)
    import collections
    print(collections.Counter((r["arm"], r["sample"]) for r in rows.values()))
    print("reward None:", [k for k, r in rows.items() if r["reward"] is None])
    print("reward values:", collections.Counter(r["reward"] for r in rows.values()))
    mism = [k for k, r in rows.items() if r["reward_txt"] is not None and float(r["reward_txt"]) != r["reward"]]
    print("reward.txt mismatch:", mism)
    print("exceptions:", collections.Counter(r["exc"] for r in rows.values()))
    print("upstream:", collections.Counter(r["upstream"] for r in rows.values()))
    # same machine within (task, sample)?
    g = collections.defaultdict(set)
    for (t, a, s), r in rows.items(): g[(t, s)].add(r["upstream"])
    print("mixed machine cells:", [k for k, v in g.items() if len(v) > 1])
    print("tasks:", len({k[0] for k in rows}))
