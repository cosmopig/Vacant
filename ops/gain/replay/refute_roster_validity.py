"""REFUTER #1 (validity) — audit of ROSTER-TRIAGE. Read-only, zero model calls."""
from __future__ import annotations
import collections, json, pathlib, sys, hashlib
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from roster_budget import ROSTER, load_pool, load_rows, vote_dist, vfilter, policy_fixed, score, boot_ci, mcnemar_exact

RUNS = ["g_r441_gemma_only_mbpp_b", "g_r356_3arm_20260830"]

for run in RUNS:
    pool, rows = load_pool(run), load_rows(run)
    print("="*90); print(run); print("="*90)
    # --- 1. pool composition: what arms make up a "complete 7-pool"? ---
    comp = collections.Counter()
    kept, dropped = [], []
    for tid, cs in pool.items():
        key = tuple(sorted(collections.Counter(c.arm for c in cs).items()))
        if len(cs) == 7 and ("OFF5", tid) in rows and sum(1 for x in cs if x.arm=="OFF5")==5:
            kept.append(tid); comp[key] += 1
        else:
            dropped.append(tid)
    print(f"kept(7-pool)={len(kept)}  other={len(dropped)}  pool_tasks={len(pool)}")
    for k, v in comp.most_common():
        print("   composition", dict(k), "->", v)
    # --- 2. matched-set: does dropping flatter? OFF5 shipped acc kept vs dropped ---
    def acc(ids, arm="OFF5"):
        z = [rows[(arm,t)]["meets_demand"] for t in ids if (arm,t) in rows]
        return (sum(z)/len(z)*100, len(z)) if z else (float("nan"),0)
    all_off5 = [t for (a,t) in rows if a=="OFF5"]
    dr = [t for t in all_off5 if t not in set(kept)]
    print(f"OFF5 shipped acc: kept {acc(kept)[0]:.2f}% (n={acc(kept)[1]})   "
          f"dropped {acc(dr)[0]:.2f}% (n={acc(dr)[1]})   all {acc(all_off5)[0]:.2f}% (n={acc(all_off5)[1]})")
    # --- 3. instrument fidelity on the OFF arm (1 candidate, no lottery) ---
    ag = mism = rev = 0; off_ship = off_rep = 0
    for tid in kept:
        offc = [c for c in pool[tid] if c.arm=="OFF"]
        if len(offc)!=1 or ("OFF",tid) not in rows: continue
        r_ = bool(offc[0].hidden_ok); s_ = bool(rows[("OFF",tid)]["meets_demand"])
        ag += (r_==s_); mism += (r_!=s_); rev += (r_ and not s_)
        off_rep += r_; off_ship += s_
    n_off = ag+mism
    print(f"OFF-arm instrument: agree {ag}/{n_off}={ag/max(n_off,1)*100:.1f}%  mismatch {mism} "
          f"(of which replay=PASS/runtime=FAIL: {rev})   replay acc {off_rep/max(n_off,1)*100:.2f}% "
          f"vs shipped {off_ship/max(n_off,1)*100:.2f}%  => instrument delta {(off_rep-off_ship)/max(n_off,1)*100:+.2f}pp")
    # --- 4. hidden pass rate by arm-of-origin inside the pool (GT-leak channel) ---
    by = collections.defaultdict(lambda:[0,0])
    for tid in kept:
        for c in pool[tid]:
            by[c.arm][0]+=c.hidden_ok; by[c.arm][1]+=1
    for a,(o,n) in sorted(by.items()):
        print(f"  pool candidate hidden pass rate  arm={a:5s} {o}/{n} = {o/n*100:.2f}%")
    # persona mix by arm (is ON's router hidden-informed skew real?)
    for a in ("OFF","OFF5","ON"):
        pc = collections.Counter(c.v.persona for tid in kept for c in pool[tid] if c.arm==a)
        print(f"  persona mix arm={a:5s}", dict(pc.most_common()))
    # --- 5. does visible_ok imply identical sig? (is the "agreement" rule vacuous?) ---
    same = diff = 0
    for tid in kept:
        vs = [c.v for c in pool[tid] if c.v.visible_ok]
        for i in range(len(vs)):
            for j in range(i+1,len(vs)):
                if vs[i].sig==vs[j].sig: same+=1
                else: diff+=1
    print(f"  pairs of visible_ok candidates in same task: same sig {same}, different sig {diff} "
          f"({same/max(same+diff,1)*100:.2f}% identical)")
    # --- 6. sig fallback rate (did _split_visible fail?) ---
    fb = sum(1 for tid in kept for c in pool[tid] if c.v.visible_total<=1)
    tot = sum(len(pool[tid]) for tid in kept)
    print(f"  visible_grade fallback (visible_total<=1): {fb}/{tot}")
