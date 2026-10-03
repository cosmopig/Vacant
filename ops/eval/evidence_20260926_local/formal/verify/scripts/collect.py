import json, pathlib, re, collections, hashlib, sys
F = pathlib.Path("/tmp/claude-0/-home-user-Vacant/95e2b6b6-418f-504c-a59e-fd594ef13041/scratchpad/local/formal_v3")
rows = []
for res in sorted(F.glob("g12-off-*-s*/*/dabstep-*__*/result.json")):
    trial = res.parent; job = trial.parent; armdir = job.parent.name
    arm, s = armdir.removeprefix("g12-off-").rsplit("-s", 1)
    task = trial.name.split("__")[0].removeprefix("dabstep-")
    r = json.loads(res.read_text())
    vr = r.get("verifier_result") or {}
    reward = (vr.get("rewards") or {}).get("reward", vr.get("reward"))
    rt = trial / "verifier" / "reward.txt"
    rtxt = rt.read_text().strip() if rt.is_file() else None
    cfg = json.loads((job / "config.json").read_text())
    ag = cfg["agents"][0]
    base = ag["env"].get("OPENROUTER_BASE_URL")
    m = re.search(r"/t/([^/]+)/up/([^/]+)/think/([^/]+)/", base or "")
    joblog = (job / "job.log").read_text(errors="replace") if (job / "job.log").is_file() else ""
    vh = trial / "agent" / "vacant_home"
    inst = vh / "adapters" / "install.json"
    ext = None
    if inst.is_file():
        d = json.loads(inst.read_text())
        for op in (d.get("agents", {}).get("pi", {}) or {}).get("ops", []):
            if op.get("path", "").endswith("vacant.ts"):
                ext = op.get("sha256")
    vc = trial / "agent" / "vacant_check.json"
    vcd = None
    if vc.is_file():
        try: vcd = json.loads(vc.read_text().strip().splitlines()[-1])
        except Exception: vcd = "unparseable"
    dm = list(vh.glob("trace/projects/*/delivery.md")) if vh.is_dir() else []
    dmt = "\n".join(p.read_text(errors="replace") for p in dm)
    rows.append(dict(task=task, arm=arm, sample=int(s), job=job.name, trial=trial.name,
        started=r.get("started_at"), finished=r.get("finished_at"), reward=reward, reward_txt=rtxt,
        exc=(r.get("exception_info") or {}).get("exception_type"),
        agent=ag["name"], tag=m and m.group(1), up=m and m.group(2), think=m and m.group(3),
        kwargs=ag.get("kwargs"), model=ag.get("model_name"),
        pipx_in_log=("pipx install" in joblog), vacant_install_in_log=("vacant install" in joblog),
        vh_exists=vh.exists(), ext=ext, vc=vcd, n_trials_in_job=len(list(job.glob("dabstep-*__*"))),
        dm_singular=("A budget reminder was sent after turn" in dmt),
        dm_plural_turns=bool(re.search(r"Budget reminders were sent after turns \d+\.", dmt)),
        datasets=cfg.get("datasets")))
json.dump(rows, open("/tmp/claude-0/verify_formal/rows.json","w"), indent=0, default=str)
print(len(rows))
