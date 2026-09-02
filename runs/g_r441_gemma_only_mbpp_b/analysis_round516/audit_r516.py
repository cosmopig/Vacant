#!/usr/bin/env python3
"""R516 收官稽核：E1 (g_r441_gemma_only_mbpp_b) 最終資料上重算 R483 §3d 的判準。

只讀 rows.jsonl / calls.jsonl / notes.jsonl，不改任何實驗碼。方法釘死：
  - 混淆矩陣：真值＝`initial_meets_demand`，票＝`review_evidence[*].{raw_pass,grounded_pass}`
    （與 ops/gain/analyze_review_gate.py `confusion()` 逐字相同）
  - 叢集 bootstrap：`vacant.research.boot_ci(rows_ON, stat, n_boot=4000, seed=483)`
    ——R516 已驗證這個呼叫在 /dev/shm/r483 快照（rows sha eb324b06）上逐位重現
    R483 的 [+0.00, +12.59]（grounded）與 [-12.59, +13.27]（raw）。
  - McNemar：`vacant.research.mcnemar_exact(b, c)`（精確雙尾二項）。

用法：python3 runs/g_r441_gemma_only_mbpp_b/analysis_round516/audit_r516.py [--json out]
"""
import argparse
import collections
import hashlib
import json
import math
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from vacant.research import boot_ci, mcnemar_exact  # noqa: E402

RUN = ROOT / "runs" / "g_r441_gemma_only_mbpp_b"
SEED, NBOOT = 483, 4000


def load(p):
    return [json.loads(l) for l in p.open(encoding="utf-8") if l.strip()]


def sha8(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()[:8]


def wilson(k, n, z=1.959964):
    if not n:
        return None
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(100 * (c - h), 2), round(100 * (c + h), 2)]


def confusion(rows, field):
    TP = FP = FN = TN = 0
    for r in rows:
        t = r["initial_meets_demand"]
        for e in r["review_evidence"]:
            p = e[field]
            if p and t:
                TP += 1
            elif p and not t:
                FP += 1
            elif (not p) and t:
                FN += 1
            else:
                TN += 1
    return TP, FP, FN, TN


def diff_pp(rows, field):
    TP, FP, FN, TN = confusion(rows, field)
    n = TP + FP + FN + TN
    return 100.0 * (TN - FN) / n if n else 0.0


def review_block(rows):
    out = {}
    for field in ("raw_pass", "grounded_pass"):
        TP, FP, FN, TN = confusion(rows, field)
        n = TP + FP + FN + TN
        lo, hi = boot_ci(rows, lambda s, f=field: diff_pp(s, f), n_boot=NBOOT, seed=SEED)
        # 每票獨立二項（只當方向參考，票 3 張一組同題）
        fails = TN + FN
        p0 = (FP + TN) / n  # 無資訊時 FAIL 票命中率＝錯初稿比率
        binom = sum(math.comb(fails, k) * p0 ** k * (1 - p0) ** (fails - k)
                    for k in range(TN, fails + 1)) if fails else None
        # 非預註冊的附帶量（不進判準）：下界未四捨五入、bootstrap 分佈落在 ≤0 的比率、
        # 換 seed 的下界範圍——只用來說明「下界＝0」是碰 0 還是剛好卡在 0。
        rng_vals = []
        import random as _r
        _rng = _r.Random(SEED)
        for _ in range(NBOOT):
            rng_vals.append(diff_pp([rows[_rng.randrange(len(rows))] for _ in range(len(rows))], field))
        rng_vals.sort()
        p_le0 = sum(1 for v in rng_vals if v <= 0) / len(rng_vals)
        seed_lo = [round(boot_ci(rows, lambda s, f=field: diff_pp(s, f), n_boot=NBOOT, seed=sd)[0], 2)
                   for sd in (1, 2, 3, 4, 5)]
        out[field] = {
            "votes": n, "TP": TP, "FP": FP, "FN": FN, "TN": TN,
            "_nonprereg_lower_unrounded": lo, "_nonprereg_boot_frac_le_0": round(p_le0, 4),
            "_nonprereg_lower_seeds_1to5": seed_lo,
            "fail_votes": fails, "fail_vote_rate": round(fails / n, 4),
            "accuracy": round((TP + TN) / n, 4),
            "always_pass_baseline": round((TP + FN) / n, 4),
            "diff_pp": round(100.0 * (TN - FN) / n, 2),
            "cluster_bootstrap_95ci_pp": [round(lo, 2), round(hi, 2)],
            "bootstrap": {"seed": SEED, "n_boot": NBOOT, "cluster": "ON row (task)",
                          "impl": "vacant.research.boot_ci"},
            "fail_vote_precision": round(TN / fails, 3) if fails else None,
            "recall_on_wrong_drafts": round(TN / (TN + FP), 3) if (TN + FP) else None,
            "binom_one_sided_p_vs_no_info": (f"{binom:.2e}" if binom is not None else None),
        }
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json")
    args = ap.parse_args()

    rows = load(RUN / "rows.jsonl")
    calls = load(RUN / "calls.jsonl")
    notes = load(RUN / "notes.jsonl")
    summary = json.loads((RUN / "summary.json").read_text())
    res = {"snapshot": {
        "rows_lines": len(rows), "rows_sha256_8": sha8(RUN / "rows.jsonl"),
        "calls_lines": len(calls), "calls_sha256_8": sha8(RUN / "calls.jsonl"),
        "notes_lines": len(notes), "notes_sha256_8": sha8(RUN / "notes.jsonl"),
        "summary_run_complete": summary.get("run_complete"),
        "summary_arms_processed": {a: summary["arms"][a]["processed"] for a in summary["arms"]},
        "summary_arms_complete": {a: summary["arms"][a]["complete"] for a in summary["arms"]},
        "summary_arms_infra_void": {a: summary["arms"][a]["infra_void"] for a in summary["arms"]},
    }}

    by = collections.defaultdict(list)
    for r in rows:
        by[r["arm"]].append(r)
    n_tasks = summary["arms"]["ON"]["tasks"]
    voids = [n for n in notes if "infra_void" in n]
    void_by_arm = collections.Counter(n["arm"] for n in voids)

    # ---- 對帳 ----
    mc = collections.Counter((c.get("model_configured"), c.get("model")) for c in calls)
    err_calls = [c for c in calls if not c.get("ok")]
    err_kinds = collections.Counter((c.get("error") or "").split(":")[0][:40] for c in err_calls)
    err_by_role = collections.Counter(c.get("role") for c in err_calls)
    attempts = collections.Counter(c.get("attempt") for c in calls)
    server_model = collections.Counter(
        (c.get("meta") or {}).get("model") for c in calls if (c.get("meta") or {}).get("model"))
    row_err = collections.Counter((r.get("err") or "")[:40] for r in rows if r.get("err"))
    dup = [k for k, v in collections.Counter((r["arm"], r["task_id"]) for r in rows).items() if v > 1]
    i2task = {}
    misalign = 0
    for r in rows:
        prev = i2task.setdefault(r["i"], r["task_id"])
        misalign += int(prev != r["task_id"])
    on_i = {r["i"] for r in by["ON"]}
    on_gaps = sorted(set(range(1, n_tasks + 1)) - on_i)
    gap_tasks = sorted(i2task[i] for i in on_gaps if i in i2task)
    void_tasks = sorted(n["task_id"] for n in voids if n["arm"] == "ON")
    res["reconcile"] = {
        "calls_model_configured_vs_model": {f"{k[0]}|{k[1]}": v for k, v in mc.items()},
        "calls_with_server_meta_model": dict(server_model),
        "calls_err_total": len(err_calls), "calls_err_kinds": dict(err_kinds),
        "calls_err_by_role": dict(err_by_role),
        "calls_attempt_hist": {str(k): v for k, v in attempts.items()},
        "rows_err_kinds": dict(row_err),
        "rows_per_arm": {a: len(by[a]) for a in ("OFF", "ON", "OFF5")},
        "dup_arm_task": dup, "cross_arm_i_misalign": misalign,
        "ON_i_gaps": on_gaps, "ON_gap_task_ids": gap_tasks,
        "notes_infra_void_task_ids_ON": void_tasks,
        "gaps_equal_void_notes": gap_tasks == void_tasks,
        "void_by_arm": dict(void_by_arm),
        "ON_void_rate_over_processed": round(void_by_arm["ON"] / n_tasks, 4),
        "ON_void_rate_over_measured_plus_void": round(
            void_by_arm["ON"] / (len(by["ON"]) + void_by_arm["ON"]), 4),
    }

    # ---- 三臂 ----
    arms = {}
    for a in ("OFF", "ON", "OFF5"):
        rs = by[a]
        n = len(rs)
        meets = sum(1 for r in rs if r["meets_demand"])
        acc = sum(1 for r in rs if r["accepted"])
        acc_ok = sum(1 for r in rs if r["accepted"] and r["meets_demand"])
        arms[a] = {
            "n": n, "meets": meets, "rate": round(meets / n, 4),
            "fail_rate": round(1 - meets / n, 4),
            "fail_rate_wilson95": wilson(n - meets, n),
            "accepted": acc, "accepted_and_meets": acc_ok, "leaked": acc - acc_ok,
            "void": void_by_arm.get(a, 0),
            "calls": summary["arms"][a]["calls"],
        }
    res["arms"] = arms

    # ---- 配對 McNemar ----
    def paired(a, b_):
        ta = {r["task_id"]: r["meets_demand"] for r in by[a]}
        tb = {r["task_id"]: r["meets_demand"] for r in by[b_]}
        common = sorted(set(ta) & set(tb))
        b = sum(1 for t in common if ta[t] and not tb[t])
        c = sum(1 for t in common if tb[t] and not ta[t])
        return {"common": len(common), "b": b, "c": c,
                "p_exact": round(mcnemar_exact(b, c), 4),
                "a_rate": round(sum(ta[t] for t in common) / len(common), 4),
                "b_rate": round(sum(tb[t] for t in common) / len(common), 4),
                "paired_gap_pp": round(100.0 * (b - c) / len(common), 2)}
    res["paired"] = {"ON_vs_OFF5": paired("ON", "OFF5"), "ON_vs_OFF": paired("ON", "OFF"),
                     "OFF5_vs_OFF": paired("OFF5", "OFF")}
    # 漏出（accepted 且 not meets）配對：描述性、非 §3d 判準
    la = {r["task_id"]: (r["accepted"] and not r["meets_demand"]) for r in by["ON"]}
    lb = {r["task_id"]: (r["accepted"] and not r["meets_demand"]) for r in by["OFF5"]}
    com = sorted(set(la) & set(lb))
    b = sum(1 for t in com if la[t] and not lb[t]); c = sum(1 for t in com if lb[t] and not la[t])
    res["paired"]["leak_ON_vs_OFF5_nonprereg"] = {
        "common": len(com), "ON_leaked": sum(la[t] for t in com), "OFF5_leaked": sum(lb[t] for t in com),
        "b": b, "c": c, "p_exact": round(mcnemar_exact(b, c), 6),
        "ON_rejected": sum(1 for r in by["ON"] if not r["accepted"]),
        "ON_rejected_but_correct": sum(1 for r in by["ON"] if not r["accepted"] and r["meets_demand"])}

    # ---- 評審票 ----
    on = by["ON"]
    res["review_E1"] = {"label": "E1 g_r441_gemma_only_mbpp_b (gemma reviewers on gemma drafts)",
                        "n_tasks": len(on), **review_block(on)}
    res["review_E1"]["status"] = dict(collections.Counter(
        e["status"] for r in on for e in r["review_evidence"]))
    res["review_E1"]["revision_transition"] = dict(collections.Counter(
        r["revision_transition"] for r in on))
    res["review_E1"]["selected_version"] = dict(collections.Counter(r["selected_version"] for r in on))
    res["review_E1"]["reviewer_models"] = dict(collections.Counter(
        m for r in on for m in r["reviewer_models"]))

    # ---- §3d 判準 ----
    g = res["review_E1"]["grounded_pass"]
    lo, hi = g["cluster_bootstrap_95ci_pp"]
    pt = g["diff_pp"]
    void_rate = res["reconcile"]["ON_void_rate_over_processed"]
    p_on_off5 = res["paired"]["ON_vs_OFF5"]["p_exact"]
    res["s3d"] = {
        "override_void_gt_10pct": void_rate > 0.10,
        "cond1_lower_gt_0": lo > 0, "cond1_point_gt_5pp": pt > 5.0,
        "branch": ("1_addendum" if (lo > 0 and pt > 5.0) else "2_n179_cannot_separate_0"),
        "cond3_ON_beats_OFF5_p_lt_005": p_on_off5 < 0.05,
        "numbers": {"grounded_diff_pp": pt, "ci95": [lo, hi],
                    "ON_void_rate": void_rate, "ON_vs_OFF5_p": p_on_off5},
    }
    txt = json.dumps(res, indent=2, ensure_ascii=False)
    print(txt)
    if args.json:
        pathlib.Path(args.json).write_text(txt + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
