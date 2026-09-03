"""Refuter #1 (validity) audit of the RCD proposal.

Zero model calls. Reads ONLY: runs/<run>/{rows,calls}.jsonl and the caches
already produced by the proposal's own scripts.

Purpose: build the one comparison the proposal did NOT build --
score OFF5's *actual shipped candidate* with the SAME replay labels RCD is
scored with, so that the mechanism and its baseline differ ONLY in the
selection rule and not in the measuring instrument.
"""
from __future__ import annotations
import json, math, os, pathlib, random, sys, collections

REPO = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO)); sys.path.insert(0, str(REPO / "ops" / "gain"))
os.environ.setdefault("VACANT_EVALPLUS_PATH",
                      str(REPO / ".vacant-private/evalplus/MbppPlus-v0.2.0.jsonl.gz"))
from ops.gain.replay import conformance_delivery as CD  # noqa: E402
from ops.gain.replay.exec_select import load_candidates  # noqa: E402

RUNS = ["g_r441_gemma_only_mbpp_b", "g_r356_3arm_20260830"]


def mcnemar(b, c):
    n = b + c
    if n == 0: return 1.0
    k = min(b, c)
    return min(1.0, 2 * sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n)


def boot(pairs, rng, B=5000):
    n = len(pairs); ds = []
    for _ in range(B):
        s = sum((1 if m else 0) - (1 if o else 0)
                for m, o in (pairs[rng.randrange(n)] for _ in range(n)))
        ds.append(100.0 * s / n)
    ds.sort(); return ds[int(.025 * (B - 1))], ds[int(.975 * (B - 1))]


def build(run, use_retry=True):
    CD._init()
    raw40, norm40, hr = CD._retry_labels() if use_retry else ({}, {}, {})
    raw = CD._load_raw_cache(run); nrm = CD._norm_cache(run)
    rows = CD._load_rows(run); allc = load_candidates(run)
    out = {}
    for (arm, tid), lst in sorted(allc.items()):
        if arm != "OFF5" or tid not in CD._TASKS or len(lst) != 5: continue
        recs, ok = [], True
        for i in range(5):
            r = raw.get((tid, i))
            if r is None or r.get("hidden_ok") is None: ok = False; break
            nn = nrm.get((tid, i))
            rf = CD._merge(r, raw40.get((run, tid, i)), hr.get((run, tid, i)))
            nf = (CD._merge(nn, norm40.get((run, tid, i)), None)
                  if nn and nn.get("normalized") and nn.get("hidden_ok") is not None
                  else dict(rf))
            recs.append({"idx": i, "agent_id": lst[i]["agent_id"], "raw": rf, "norm": nf,
                         "fuzz": None, "was_normalised": bool(nn and nn.get("normalized"))})
        if ok and ("OFF5", tid) in rows:
            out[tid] = recs
    return out, rows


def off5_actual_pick(recs, row):
    """Reconstruct which of the 5 candidates arm_off5 actually shipped.

    gain_run.arm_off5: outs order == `involved` order; winner's agent_id == `worker`;
    winner's bucket size == `vote_agreement`; #buckets == `n_buckets`.
    Returns (idx | None, diagnostic).
    """
    inv = row.get("involved") or []
    sigs = [c["raw"]["sig"] for c in recs]
    nb = len(set(sigs))
    buckets = collections.defaultdict(list)
    for c in recs: buckets[c["raw"]["sig"]].append(c["idx"])
    mx = max(len(v) for v in buckets.values())
    agree_ok = (row.get("vote_agreement") == mx)
    nb_ok = (row.get("n_buckets") == nb)
    cand = [c["idx"] for c in recs
            if len(buckets[c["raw"]["sig"]]) == mx
            and (not inv or (len(inv) == 5 and inv[c["idx"]] == row.get("worker")))]
    return (cand[0] if len(cand) == 1 else None), {"nb_ok": nb_ok, "agree_ok": agree_ok,
                                                   "n_cand": len(cand)}


def report(use_retry=True):
    tag = "WITH 40s retry labels" if use_retry else "NO retry (10s, as the live run)"
    print(f"\n################ {tag} ################")
    pooled = collections.defaultdict(list)
    for run in RUNS:
        data, rows = build(run, use_retry)
        tids = sorted(data)
        n = len(tids)
        shipped = {t: bool(rows[("OFF5", t)]["meets_demand"]) for t in tids}
        rcd, off5act, off5act_id, diag = {}, {}, {}, collections.Counter()
        for t in tids:
            r, _ = CD.pol_gate_vote(data[t], "norm")
            rcd[t] = None if r is None else bool(r["norm"]["hidden_ok"])
            i, d = off5_actual_pick(data[t], rows[("OFF5", t)])
            off5act_id[t] = i
            diag["nb_ok"] += d["nb_ok"]; diag["agree_ok"] += d["agree_ok"]
            diag["identified"] += (i is not None)
            off5act[t] = None if i is None else bool(data[t][i]["raw"]["hidden_ok"])
        idd = [t for t in tids if off5act[t] is not None]
        print(f"\n===== {run}  n={n} =====")
        print(f"  sig-bucket reconstruction vs live run: n_buckets match {diag['nb_ok']}/{n}, "
              f"vote_agreement match {diag['agree_ok']}/{n}, shipped candidate uniquely "
              f"identified {diag['identified']}/{n}")
        # label asymmetry, measured directly on the SAME code object
        dis_up = sum(1 for t in idd if off5act[t] and not shipped[t])
        dis_dn = sum(1 for t in idd if shipped[t] and not off5act[t])
        print(f"  LABEL ASYMMETRY on OFF5's own shipped candidate (n={len(idd)}): replay says "
              f"PASS where live said FAIL: {dis_up};  replay FAIL where live PASS: {dis_dn}")
        print(f"    -> OFF5 re-scored with replay labels: "
              f"{sum(1 for t in idd if off5act[t])}/{len(idd)} = "
              f"{100*sum(1 for t in idd if off5act[t])/len(idd):.2f}%  vs live rows.jsonl "
              f"{sum(1 for t in idd if shipped[t])}/{len(idd)} = "
              f"{100*sum(1 for t in idd if shipped[t])/len(idd):.2f}%")
        rng = random.Random(7)
        for label, base in (("OFF5 as shipped (rows.jsonl, live labels) [proposal's headline]",
                             {t: shipped[t] for t in idd}),
                            ("OFF5 actual pick, SAME replay labels  [like-for-like]",
                             {t: off5act[t] for t in idd})):
            b = sum(1 for t in idd if rcd[t] and not base[t])
            c = sum(1 for t in idd if not rcd[t] and base[t])
            lo, hi = boot([(bool(rcd[t]), bool(base[t])) for t in idd], random.Random(11))
            mp = sum(1 for t in idd if rcd[t]); bp = sum(1 for t in idd if base[t])
            print(f"  RCD {mp}/{len(idd)}={100*mp/len(idd):.2f}%  vs  {label}: "
                  f"{bp}/{len(idd)}={100*bp/len(idd):.2f}%  Δ={100*(mp-bp)/len(idd):+.2f}pp  "
                  f"b={b} c={c} p={mcnemar(b,c):.4f}  CI[{lo:+.2f},{hi:+.2f}]")
        for t in idd:
            pooled["rcd"].append(bool(rcd[t])); pooled["ship"].append(shipped[t])
            pooled["act"].append(bool(off5act[t]))
    N = len(pooled["rcd"])
    for label, key in (("OFF5 as shipped (live labels)", "ship"),
                       ("OFF5 actual pick, same replay labels", "act")):
        m, o = pooled["rcd"], pooled[key]
        b = sum(1 for i in range(N) if m[i] and not o[i])
        c = sum(1 for i in range(N) if o[i] and not m[i])
        lo, hi = boot(list(zip(m, o)), random.Random(13))
        print(f"\nPOOLED n={N}: RCD {sum(m)}={100*sum(m)/N:.2f}%  vs {label} {sum(o)}="
              f"{100*sum(o)/N:.2f}%  Δ={100*(sum(m)-sum(o))/N:+.2f}pp b={b} c={c} "
              f"p={mcnemar(b,c):.4f} CI[{lo:+.2f},{hi:+.2f}]")


if __name__ == "__main__":
    report(use_retry=True)
    report(use_retry=False)
