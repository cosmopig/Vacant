"""Offline simulation of a 'write-early' nudge on the 2026-09-25 formal DABstep batch (read-only).

Usage: python3 nudge_sim.py   -> writes per_run_turns.json and summary.json next to this file,
                                 prints the tables.
Definitions (all per latest run of (model, arm, task); headline excludes tasks 5 and 70):
  turn k            = k-th model request (assistant message; the zero-usage 'aborted' message pi
                      appends after Harbor's max_turns abort is not a request). Checked == runs.json
                      `requests` for all 316 runs.
  exists_end[k]     = /app/answer.txt exists after turn k's executed tool calls (parse_runs.py).
  correct stated    = a non-hedged, answer-shaped cue candidate in thinking or text that
                      scorer.py accepts (candidates.py). tiers: strict / broad; 'loose' = any
                      accepted candidate incl. hedged / not answer-shaped.
  nudge at K fires  = run has a turn K that is not its last turn and exists_end[K] is False.
"""
import collections
import json
import os
import statistics

from parse_runs import latest_runs, parse_session, heuristic_exists, trace_exists, verifier, expected
from candidates import extract, accepted, answer_shaped, text_detector, normalise_like_testsh

HERE = os.path.dirname(os.path.abspath(__file__))
KS = [4, 6, 8, 10, 12]
KS_EXTRA = [13, 14]
EXCL = {"5", "70"}


def analyse_run(key, r):
    model, arm, task = key
    gold = expected(task)
    turns, custom = parse_session(r)
    hx = heuristic_exists(turns)
    tx = trace_exists(r, turns) if arm == "C" else None
    ver = verifier(r)
    out_turns = []
    first = {"strict": None, "broad": None, "loose": None, "text_strict": None, "text_detector": None}
    latest_cand = None  # latest non-hedged answer-shaped strict/broad candidate (for 'current belief')
    for t, h in zip(turns, hx):
        k = t["turn"]
        row = {"turn": k, "stop": t["stop"], "exists_end": h["exists"],
               "trace_exists_end": (tx[k - 1]["exists"] if tx and tx[k - 1] else None),
               "writes": h["writes"], "cands": [], "text_nonempty": bool(t["text"].strip()),
               "thinking_nonempty": bool(t["thinking"].strip())}
        flags = {"strict": False, "broad": False, "loose": False, "text_strict": False}
        for src in ("thinking", "text"):
            for d in extract(t[src], "broad"):
                ok = accepted(d["cand"], gold)
                shaped = answer_shaped(d["cand"], gold)
                row["cands"].append({"src": src, "tier": d["tier"], "cand": d["cand"][:160],
                                     "hedged": d["hedged"], "shaped": shaped, "accepted": ok})
                if ok:
                    flags["loose"] = True
                    if shaped and not d["hedged"]:
                        flags["broad"] = True
                        if d["tier"] == "strict":
                            flags["strict"] = True
                            if src == "text":
                                flags["text_strict"] = True
                if shaped and not d["hedged"]:
                    latest_cand = {"turn": k, "cand": d["cand"][:160], "accepted": ok, "tier": d["tier"]}
        tso = []
        for c in t["calls"]:
            if not c["executed"] or c["is_error"]:
                continue
            lines = [x.strip() for x in c["result"].strip().split("\n") if x.strip()]
            if 1 <= len(lines) <= 2 and len(c["result"].strip()) <= 80:
                for x in lines:
                    if not answer_shaped(x, gold):
                        continue
                    tso.append({"cand": x[:160], "accepted": accepted(x, gold)})
        row["tool_short_outputs"] = tso
        det = text_detector(t["text"])
        row["text_detector"] = [{"cand": c[:160], "accepted": accepted(c, gold)} for c in det]
        row["latest_cand_so_far"] = latest_cand
        for f, v in flags.items():
            row["correct_" + f] = v
            if v and first[f] is None:
                first[f] = k
        if det and first["text_detector"] is None and any(x["accepted"] for x in row["text_detector"]):
            first["text_detector"] = k
        out_turns.append(row)
    n = len(turns)
    last_stop = turns[-1]["stop"] if turns else None
    # Harbor aborts after the 15th turn_end; g4 A 72's 15th request itself ended in a stream error.
    ended = "cap" if (n == 15 and last_stop in ("toolUse", "error")) else last_stop
    first_write = next((x["turn"] for x in out_turns if x["exists_end"]), None)
    return {
        "model": model, "arm": arm, "task": task, "job": r["job"], "trial": r["trial"],
        "gold": gold, "reward": r["reward"], "requests": r["requests"], "n_turns": n, "ended": ended,
        "verifier_exists": ver["exists"], "verifier_got": ver["got"],
        "final_exists_heuristic": out_turns[-1]["exists_end"] if out_turns else False,
        "first_write_turn": first_write,
        "first_correct_stated": first,
        "vacant_pushbacks_after_turn": [c["after_turn"] for c in custom if c["customType"] == "vacant-check"],
        "turns": out_turns,
    }


# Manual audit (read transcripts; see README section "manual audit") of every headline gemma run
# that never wrote answer.txt. T1 = first turn at which the model states the scorer-accepted value as
# its result (not hedged); switch = first turn at which it adopts a different (wrong) answer;
# conf: 'committed' (states it as the answer and keeps it), 'leaning' (states it as a result while
# still weighing an alternative interpretation), 'weak' (only conditional / hedged).
# Runs not listed = no scorer-accepted answer found (regex + gold-anchored search + reading).
MANUAL = {
    ("g4", "A", "3"): (10, None, "committed"), ("g4", "A", "7"): (10, None, "committed"),
    ("g4", "A", "10"): (13, None, "weak"), ("g4", "A", "15"): (7, None, "leaning"),
    ("g4", "A", "16"): (12, None, "leaning"), ("g4", "A", "17"): (10, 13, "leaning"),
    ("g4", "A", "18"): (7, None, "committed"), ("g4", "A", "19"): (11, None, "committed"),
    ("g4", "A", "39"): (7, None, "committed"), ("g4", "A", "47"): (8, None, "leaning"),
    ("g4", "A", "48"): (11, None, "committed"), ("g4", "A", "58"): (7, None, "committed"),
    ("g4", "A", "62"): (14, None, "committed"), ("g4", "A", "65"): (4, None, "committed"),
    ("g4", "A", "66"): (4, None, "committed"), ("g4", "A", "1273"): (13, None, "weak"),
    ("g4", "A", "1305"): (15, None, "committed"), ("g4", "A", "1753"): (15, None, "leaning"),
    ("g4", "C", "3"): (12, None, "committed"), ("g4", "C", "7"): (11, None, "committed"),
    ("g4", "C", "10"): (13, None, "committed"), ("g4", "C", "12"): (5, None, "committed"),
    ("g4", "C", "16"): (9, None, "leaning"), ("g4", "C", "17"): (8, None, "leaning"),
    ("g4", "C", "19"): (7, None, "committed"), ("g4", "C", "21"): (9, None, "leaning"),
    ("g4", "C", "23"): (13, None, "committed"), ("g4", "C", "28"): (11, None, "committed"),
    ("g4", "C", "32"): (15, None, "committed"), ("g4", "C", "39"): (9, None, "leaning"),
    ("g4", "C", "40"): (7, None, "committed"), ("g4", "C", "44"): (6, None, "committed"),
    ("g4", "C", "58"): (10, None, "committed"), ("g4", "C", "61"): (15, None, "committed"),
    ("g4", "C", "72"): (15, None, "leaning"), ("g4", "C", "1273"): (12, None, "committed"),
    ("g4", "C", "1305"): (9, None, "committed"), ("g4", "C", "1681"): (14, None, "leaning"),
    ("g4", "C", "1871"): (13, None, "leaning"),
}


def classify_manual(run, K, confs=("committed", "leaning")):
    """Like classify() but (iii)/(iv) from the manual audit; (iii) requires T1 <= K and no switch by K."""
    if run["n_turns"] <= K or run["turns"][K - 1]["exists_end"]:
        return None
    if run["verifier_exists"]:
        return "ii_wrote_correct" if run["reward"] == 1.0 else "v_wrote_wrong"
    lab = MANUAL.get((run["model"], run["arm"], run["task"]))
    if lab and lab[2] in confs:
        t1, sw, _ = lab
        if t1 <= K and (sw is None or sw > K):
            return "iii_never_wrote_correct_by_K"
        if t1 <= K:
            return "iii_switched_away_by_K"
        return "iv_never_wrote_correct_after_K"
    return "vi_never_wrote_never_correct"


def classify(run, K, tier="broad"):
    """Return None if the nudge does not fire at K, else category string."""
    if run["n_turns"] <= K:
        return None  # run ended at or before K (Stop path, not the nudge)
    if run["turns"][K - 1]["exists_end"]:
        return None
    if run["verifier_exists"]:
        return "ii_wrote_correct" if run["reward"] == 1.0 else "v_wrote_wrong"
    fc = run["first_correct_stated"][tier]
    if fc is not None and fc <= K:
        return "iii_never_wrote_correct_by_K"
    if fc is not None:
        return "iv_never_wrote_correct_after_K"
    return "vi_never_wrote_never_correct"


def current_belief_at(run, K):
    lc = run["turns"][K - 1]["latest_cand_so_far"]
    if lc is None:
        return "none"
    return "correct" if lc["accepted"] else "wrong"


def main():
    L = latest_runs()
    runs = [analyse_run(k, r) for k, r in sorted(L.items(), key=lambda x: (x[0][0], x[0][1], int(x[0][2])))]
    json.dump(runs, open(os.path.join(HERE, "per_run_turns.json"), "w"), ensure_ascii=False, indent=1)
    head = [r for r in runs if r["task"] not in EXCL]
    summary = {"n_runs_all": len(runs), "n_runs_headline": len(head)}

    # ---- validation
    val = collections.Counter()
    for r in runs:
        val["requests==turns" if r["requests"] == r["n_turns"] else "requests!=turns"] += 1
        val["final heuristic==verifier" if r["final_exists_heuristic"] == r["verifier_exists"] else "final MISMATCH"] += 1
        for t in r["turns"]:
            if t["trace_exists_end"] is not None:
                val["C trace turn agree" if t["trace_exists_end"] == t["exists_end"] else "C trace turn DISAGREE"] += 1
    summary["validation"] = dict(val)
    print("validation", dict(val))

    # ---- baseline outcome per model/arm
    print("\n== outcomes (headline 77 tasks)")
    base = {}
    for m in ("g4", "q38"):
        for a in ("A", "C", "A+C"):
            rs = [r for r in head if r["model"] == m and (a == "A+C" or r["arm"] == a)]
            c = collections.Counter()
            for r in rs:
                if r["verifier_exists"]:
                    c["wrote_correct" if r["reward"] == 1.0 else "wrote_wrong"] += 1
                else:
                    c["no_answer_" + str(r["ended"])] += 1
            base[f"{m} {a}"] = dict(c, n=len(rs))
            print(f"{m} {a:3s} n={len(rs)}", dict(c))
    summary["outcomes"] = base

    # ---- nudge tables
    cats = ["ii_wrote_correct", "v_wrote_wrong", "iii_never_wrote_correct_by_K", "iii_switched_away_by_K",
            "iv_never_wrote_correct_after_K", "vi_never_wrote_never_correct"]
    summary["nudge"] = {}

    def table(label, fn, arms=("A+C", "A", "C"), models=("g4", "q38"), show=True):
        if show:
            print(f"\n== write-early nudge: {label}")
            print("model arm   K  n fires (ii)wrote-correct[correct-stated-by-K] (v)wrote-wrong (iii)rescuable "
                  "(iii')switched (iv)correct-after-K (vi)never-correct | ended<=K-no-answer")
        for m in models:
            for a in arms:
                rs = [r for r in head if r["model"] == m and (a == "A+C" or r["arm"] == a)]
                for K in KS + KS_EXTRA:
                    cl = {id(r): fn(r, K) for r in rs}
                    c = collections.Counter(cl.values())
                    fired = sum(v for k, v in c.items() if k)
                    ii_ready = sum(1 for r in rs if cl[id(r)] == "ii_wrote_correct"
                                   and r["first_correct_stated"]["broad"] is not None
                                   and r["first_correct_stated"]["broad"] <= K)
                    ended_before = sum(1 for r in rs if r["n_turns"] <= K and not r["verifier_exists"])
                    row = {"n": len(rs), "fires": fired, **{k: c.get(k, 0) for k in cats},
                           "ii_correct_stated_by_K_regex_broad": ii_ready,
                           "ended_by_K_without_answer": ended_before}
                    summary["nudge"][f"{label}|{m}|{a}|K={K}"] = row
                    if show:
                        print(f"{m:4s}{a:4s}{K:3d}{len(rs):4d}{fired:5d}   {row['ii_wrote_correct']:3d}[{ii_ready:3d}]"
                              f"{row['v_wrote_wrong']:14d}{row['iii_never_wrote_correct_by_K']:15d}"
                              f"{row['iii_switched_away_by_K']:12d}{row['iv_never_wrote_correct_after_K']:18d}"
                              f"{row['vi_never_wrote_never_correct']:18d} | {ended_before}")

    table("manual audit (committed+leaning)", classify_manual)
    table("manual audit (committed only)", lambda r, K: classify_manual(r, K, ("committed",)), arms=("A+C",))
    for tier in ("strict", "broad", "loose"):
        table(f"regex tier={tier}", lambda r, K, t=tier: classify(r, K, t), arms=("A+C",))

    # ---- first-write turn distribution
    print("\n== turn at which answer.txt was first written")
    summary["first_write"] = {}
    for m in ("g4", "q38"):
        for a in ("A+C", "A", "C"):
            for outcome in ("correct", "wrong"):
                rs = [r for r in head if r["model"] == m and (a == "A+C" or r["arm"] == a)
                      and r["verifier_exists"] and ((r["reward"] == 1.0) == (outcome == "correct"))]
                fw = [r["first_write_turn"] for r in rs]
                hist = collections.Counter(fw)
                cum = {K: sum(1 for x in fw if x <= K) for K in KS + KS_EXTRA + [15]}
                d = {"n": len(fw), "hist": {str(k): hist[k] for k in sorted(hist)},
                     "median": statistics.median(fw) if fw else None,
                     "p90": sorted(fw)[int(0.9 * (len(fw) - 1))] if fw else None,
                     "cum_written_by_K": cum}
                summary["first_write"][f"{m}|{a}|{outcome}"] = d
                print(f"{m} {a:3s} {outcome:7s} n={len(fw):3d} median={d['median']} p90={d['p90']} "
                      f"hist={d['hist']} cum<=K={cum}")

    # ---- candidate-answer detection at turn end
    print("\n== candidate-answer detection at turn end (eligible = not the run's last turn, answer.txt absent)")
    summary["detector"] = {}

    def pr(a, b):
        return round(a / b, 3) if b else None

    DET = {
        "text": lambda t: t["text_detector"],
        "thinking_strict": lambda t: [{"cand": c["cand"], "accepted": c["accepted"]} for c in t["cands"]
                                      if c["src"] == "thinking" and c["tier"] == "strict" and not c["hedged"] and c["shaped"]],
        "thinking_broad": lambda t: [{"cand": c["cand"], "accepted": c["accepted"]} for c in t["cands"]
                                     if c["src"] == "thinking" and not c["hedged"] and c["shaped"]],
        "tool_short_output": lambda t: t["tool_short_outputs"],
    }
    for m in ("g4", "q38"):
        rs = [r for r in head if r["model"] == m]
        d = {"eligible_turns": 0, "with_visible_text": 0, "with_thinking": 0}
        for name in DET:
            d[name] = collections.Counter()
        man_targets = [r for r in rs if (lab := MANUAL.get((r["model"], r["arm"], r["task"])))
                       and lab[2] in ("committed", "leaning") and lab[0] <= 14 and r["n_turns"] > lab[0]]
        for r in rs:
            inhand = False
            for t in r["turns"][:-1]:
                if t["exists_end"]:
                    continue
                inhand = inhand or t["correct_broad"]
                d["eligible_turns"] += 1
                d["with_visible_text"] += t["text_nonempty"]
                d["with_thinking"] += t["thinking_nonempty"]
                for name, f in DET.items():
                    got = f(t)
                    cnt = d[name]
                    cnt["label_inhand_regex"] += inhand
                    if got:
                        cnt["fires"] += 1
                        cnt["fires_cand_accepted"] += any(x["accepted"] for x in got)
                        cnt["fires_and_inhand_regex"] += inhand
        for name, f in DET.items():
            cnt = d[name]
            hit = 0
            for r in man_targets:
                t1, sw, _ = MANUAL[(r["model"], r["arm"], r["task"])]
                last_ok = min(14, (sw - 1) if sw else 14, r["n_turns"] - 1)
                if any(f(t) and any(x["accepted"] for x in f(t)) for t in r["turns"][t1 - 1:last_ok]
                       if not t["exists_end"]):
                    hit += 1
            cnt = dict(cnt)
            cnt["precision_cand_accepted"] = pr(cnt.get("fires_cand_accepted", 0), cnt.get("fires", 0))
            cnt["precision_inhand_regex"] = pr(cnt.get("fires_and_inhand_regex", 0), cnt.get("fires", 0))
            cnt["recall_turns_inhand_regex"] = pr(cnt.get("fires_and_inhand_regex", 0), cnt.get("label_inhand_regex", 0))
            cnt["run_recall_manual"] = f"{hit}/{len(man_targets)}"
            d[name] = cnt
        summary["detector"][m] = d
        print(m, f"eligible={d['eligible_turns']} visible_text={d['with_visible_text']} thinking={d['with_thinking']}")
        for name in DET:
            c = d[name]
            print(f"   {name:18s} fires={c.get('fires', 0):4d} cand_accepted={c.get('fires_cand_accepted', 0):4d} "
                  f"prec(cand ok)={c['precision_cand_accepted']} prec(in-hand)={c['precision_inhand_regex']} "
                  f"recall(turns in-hand)={c['recall_turns_inhand_regex']} run-recall(manual)={c['run_recall_manual']}")
    json.dump(summary, open(os.path.join(HERE, "summary.json"), "w"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
