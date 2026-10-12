import json, pathlib, hashlib, collections
D = pathlib.Path("/tmp/claude-0/-home-user-Vacant/95e2b6b6-418f-504c-a59e-fd594ef13041/scratchpad/dabstep_pinned/formal")
man = json.loads(pathlib.Path("/home/user/Vacant/ops/eval/evidence_20260925/pilot/FORMAL_MANIFEST.json").read_text())
def tree_sha(d, skip_pyc=True):
    h = hashlib.sha256()
    for f in sorted(p for p in d.rglob("*") if p.is_file()):
        if skip_pyc and "__pycache__" in f.parts: continue
        h.update(str(f.relative_to(d)).encode() + b"\0" + f.read_bytes() + b"\0")
    return h.hexdigest()
bad = [t["task"] for t in man["tasks"] if tree_sha(D / f"dabstep-{t['task']}" / "tests") != t["tests_sha256"]]
print("manifest tasks", len(man["tasks"]), "tests_sha mismatches (excluding __pycache__):", bad)
pyc = [p for p in D.rglob("__pycache__")]
print("__pycache__ dirs:", len(pyc), sorted({str(p.stat().st_mtime)[:10] for p in pyc})[:3])
F = pathlib.Path("/tmp/claude-0/-home-user-Vacant/95e2b6b6-418f-504c-a59e-fd594ef13041/scratchpad/local/formal_v3")
ck = collections.defaultdict(set)
for res in F.glob("g12-off-*-s*/*/dabstep-*__*/result.json"):
    r = json.loads(res.read_text()); ck[r["task_name"]].add(r.get("task_checksum"))
print("tasks with >1 task_checksum across runs:", {k: len(v) for k,v in ck.items() if len(v)>1})
formal79 = json.loads(pathlib.Path("/home/user/Vacant/ops/eval/pilot/tasks.json").read_text())["formal_79"]
print("formal_79 == manifest tasks:", sorted(formal79, key=int) == sorted([t["task"] for t in man["tasks"]], key=int))
