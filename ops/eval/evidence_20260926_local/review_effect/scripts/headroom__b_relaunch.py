"""(b) relaunch ceiling and (c) best-of/consistency ceiling on the local formal batch."""
import json, collections, itertools, sys, re, random
sys.path.insert(0, "/tmp/claude-0/review_effect/headroom")
from scorer import question_scorer

R = json.load(open("/tmp/claude-0/review_effect/headroom/runs.json"))
EXC = {"5", "70"}
R = [r for r in R if r["task"] not in EXC]
by = collections.defaultdict(dict)
for r in R:
    by[(r["arm"], r["task"])][r["sample"]] = r
tasks = sorted({r["task"] for r in R}, key=int)
ARMS = ["A", "C1", "C2"]


def ok(r):
    return r["reward"] == 1.0


def has_file(r):
    return r["file"] is not False


def flagged(r):
    """Vacant's own at-delivery signal on the final state: review sent back and never allowed afterwards."""
    vc = r.get("vc") or {}
    acts = vc.get("review_actions") or []
    return bool(acts) and acts[-1] != "allow"


def end_reason(r):
    p = r["pi"]
    st = [s for t, s in p["stops"]]
    if r["exc"] == "AgentTimeoutError":
        return "timeout"
    if p["turns"] >= 15 and (st[-1:] == ["error"] or len([s for s in st if s == "toolUse"]) >= 15):
        return "cap"
    return f"stop:{st[-1] if st else None}"


print("NF end reasons by arm:")
for a in ARMS:
    print(a, dict(collections.Counter(end_reason(r) for r in R if r["arm"] == a and not has_file(r))))
print("final review action distribution (C arms):")
for a in ("C1", "C2"):
    print(a, dict(collections.Counter(tuple((r.get("vc") or {}).get("review_actions") or []) for r in R if r["arm"] == a)))


def policy_eval(arm, trigger, max_attempts):
    """Average over all orderings of the 3 samples: attempt k+1 only if trigger(attempt k). Returns (acc, extra_attempts_per_task, extra_requests_per_task)."""
    acc = extra = extra_req = 0.0
    n = 0
    for t in tasks:
        runs = [by[(arm, t)][s] for s in (1, 2, 3)]
        perms = list(itertools.permutations(runs, 3))
        for perm in perms:
            chosen = None
            used = 0
            for k in range(max_attempts):
                used += 1
                cur = perm[k]
                chosen = cur
                if not trigger(cur):
                    break
            acc += ok(chosen)
            extra += used - 1
            extra_req += sum(perm[i]["nreq"] for i in range(1, used))
        n += 1
        acc_t = None
    P = 6
    return acc / (n * P), extra / (n * P), extra_req / (n * P)


base_req = {a: sum(r["nreq"] for r in R if r["arm"] == a) / len([r for r in R if r["arm"] == a]) for a in ARMS}
print("\nmean requests per run:", {a: round(v, 2) for a, v in base_req.items()})
print("\n=== (b) relaunch ceilings (fresh attempt = another sample of the same arm/task; averaged over orderings) ===")
trig_nf = lambda r: not has_file(r)
trig_nf_or_flag = lambda r: (not has_file(r)) or flagged(r)
trig_oracle = lambda r: not ok(r)
for a in ARMS:
    base = sum(ok(r) for r in R if r["arm"] == a) / len([r for r in R if r["arm"] == a])
    for name, trig in (("no-file", trig_nf), ("no-file-or-flag", trig_nf_or_flag), ("ORACLE wrong-or-no-file", trig_oracle)):
        for m in (2, 3):
            acc, ex, exr = policy_eval(a, trig, m)
            print(f"{a:3s} base {base:.3f}  relaunch on {name:24s} up to {m} attempts: acc {acc:.3f} ({(acc-base)*100:+.1f} pp)  extra attempts/task {ex:.2f}  extra requests/task {exr:.1f} (+{exr/base_req[a]*100:.0f}% of a run)")

# cross-arm: A first attempt; relaunch uses C2 (i.e. what if relaunch + v3 reminder)
print("\n=== (c) best-of / consistency (reference only: conflicts with 'never picks an answer') ===")


def norm(g):
    return None if g is None else g.strip()


def same(a, b):
    if a is None or b is None:
        return False
    try:
        return question_scorer(a, b) and question_scorer(b, a)
    except Exception:
        return a.strip().lower() == b.strip().lower()


for a in ARMS:
    maj = pass3 = agree2 = agree2_ok = 0
    for t in tasks:
        runs = [by[(a, t)][s] for s in (1, 2, 3)]
        pass3 += any(ok(r) for r in runs)
        answers = [r for r in runs if has_file(r) and r["got"] is not None]
        # majority among delivered answers (plurality with >=2 agreeing), else first delivered
        best = None
        for r in answers:
            cnt = sum(1 for q in answers if same(r["got"], q["got"]))
            if cnt >= 2:
                best = r
                break
        if best is not None:
            agree2 += 1
            agree2_ok += ok(best)
            maj += ok(best)
        elif answers:
            maj += ok(answers[0])
    n = len(tasks)
    base = sum(ok(r) for r in R if r["arm"] == a) / len([r for r in R if r["arm"] == a])
    print(f"{a}: mean single {base:.3f}; majority-of-3 {maj/n:.3f}; pass@3 (oracle) {pass3/n:.3f}; tasks with >=2 agreeing answers {agree2}/{n}, of which correct {agree2_ok}")

# pooled across arms (9 runs) oracle
pool = sum(any(ok(by[(a, t)][s]) for a in ARMS for s in (1, 2, 3)) for t in tasks)
never = [t for t in tasks if not any(ok(by[(a, t)][s]) for a in ARMS for s in (1, 2, 3))]
always = [t for t in tasks if all(ok(by[(a, t)][s]) for a in ARMS for s in (1, 2, 3))]
print(f"pooled pass@9 {pool}/{len(tasks)} = {pool/len(tasks):.3f}; never solved in 9 runs: {len(never)} {never}; always solved: {len(always)}")
