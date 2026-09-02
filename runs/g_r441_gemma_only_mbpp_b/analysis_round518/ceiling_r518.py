#!/usr/bin/env python3
"""R518 P-CEIL：評審宣稱的 EXPECTED 對不對？拿官方參考解當裁判。零 API 呼叫。

判準寫在 DECISION_20260902_R518 §十一，已先 commit（c1a7c0a）才跑這支。
"""
import json, pathlib, sys, collections

ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from ops.gain.gain_run import (_canonical_solutions, parse_review_claim,      # noqa: E402
                               counterexample_check, meets_demand, load_tasks,
                               _review_vote)

RUN = ROOT / "runs/g_r441_gemma_only_mbpp_b"
summ = json.load(open(RUN / "summary.json"))
tasks = {t["task_id"]: t for t in load_tasks("evalplus", summ["seed"], summ["n"])}
refs = _canonical_solutions("evalplus")
rows = {(r["arm"], r["task_id"]): r for r in map(json.loads, open(RUN / "rows.jsonl"))}

votes = 0
parseable = 0
no_ref = 0
ok_expected = collections.Counter()      # (reviewer_said_pass) -> correct expected count
tot_by_vote = collections.Counter()
detail = []

for line in open(RUN / "calls.jsonl"):
    c = json.loads(line)
    m = c.get("meta") or {}
    if m.get("arm") != "ON" or c.get("role") != "review" or not c.get("ok"):
        continue
    tid = m["task_id"]
    if ("ON", tid) not in rows:          # void 題沒有 row，排除以對齊 501 票
        continue
    votes += 1
    claim = parse_review_claim(c["response"])
    if claim is None:
        continue
    args, expected = claim
    t = tasks[tid]
    ref = refs.get(tid)
    if not ref:
        no_ref += 1
        continue
    parseable += 1
    said_pass = _review_vote(c["response"])
    chk = counterexample_check(t.get("entry_point"), args, expected)
    good, _ = meets_demand(ref, chk, entry_point=t.get("entry_point"))
    tot_by_vote[said_pass] += 1
    ok_expected[said_pass] += int(good)
    detail.append({"task_id": tid, "said_pass": said_pass, "expected_correct": good})

n = sum(tot_by_vote.values())
k = sum(ok_expected.values())


def wilson(k, n, z=1.96):
    if not n:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5) / d
    return (max(0.0, c - h), min(1.0, c + h))


print(f"ON review votes considered (rows-aligned): {votes}")
print(f"  parseable (args, expected) with a canonical ref: {parseable}")
print(f"  parsed but task has no canonical ref (excluded): {no_ref}")
lo, hi = wilson(k, n)
print(f"\n=== P-CEIL ===")
print(f"A = reviewer's asserted EXPECTED matches the official canonical solution")
print(f"A = {k}/{n} = {k/n:.4f}   Wilson 95% [{lo:.4f}, {hi:.4f}]" if n else "A: n=0")
print(f"\nsplit by what the reviewer voted:")
for sp in (False, True):
    nn, kk = tot_by_vote[sp], ok_expected[sp]
    if nn:
        l2, h2 = wilson(kk, nn)
        print(f"  reviewer voted {'PASS' if sp else 'FAIL'}: A = {kk}/{nn} = {kk/nn:.4f}  [{l2:.4f}, {h2:.4f}]")
print(f"\nverdict per pre-registered table: "
      f"{'A < 0.80 -> bottleneck is the primitive, stop stacking rungs' if n and k/n < 0.80 else 'A >= 0.80 -> build L3'}")

json.dump({"votes": votes, "parseable": parseable, "no_ref": no_ref,
           "A_k": k, "A_n": n, "A": (k / n if n else None), "wilson": [lo, hi],
           "by_vote": {str(x): [ok_expected[x], tot_by_vote[x]] for x in tot_by_vote},
           "detail": detail},
          open(pathlib.Path(__file__).parent / "ceiling_r518.json", "w"),
          ensure_ascii=False, indent=2)
