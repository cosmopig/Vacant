#!/usr/bin/env python3
import sys, pathlib, json, collections, hashlib
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import voidclass as V

STRATA = [
    ("S1", "A", "runs/g_r441_gemma_only_mbpp_b",       "2026-09-02 09:33", "post"),
    ("S2", "A", "runs/g_r443_gemma_lcb",               "2026-09-03",       "post"),
    ("S3", "B", "runs/g_onoff5_qwenonly_v3_20260824",  "2026-08-24 11:28", "pre"),
    ("S4", "B", "runs/g_onoff5_371_r123_20260825",     "2026-08-25 22:43", "pre"),
    ("S5", "B", "runs/g_het3_r278_20260829",           "2026-08-29 10:23", "pre"),
    ("S6", "B", "runs/g_r356_3arm_20260830",           "2026-08-30 17:53", "post(+58s)"),
]

out = {"strata": []}
unparsed_total = 0
print("=" * 78)
print("Q1  每層每臂的 void 類別組成")
print("=" * 78)
for label, grp, d, start, era in STRATA:
    rd = pathlib.Path(d)
    voids = V.load_voids(rd)
    succ = V.load_rows_success(rd)
    by_arm = collections.defaultdict(collections.Counter)
    for arm, tid, msg in voids:
        by_arm[arm][V.classify(msg)] += 1
    total = collections.Counter()
    for c in by_arm.values():
        total.update(c)
    unparsed_total += total.get("UNPARSED", 0)
    # Q3 可補量
    rec = sum(1 for arm, tid, _ in voids if succ.get(tid, set()) - {arm})
    rate = rec / len(voids) if voids else None
    sha = hashlib.sha256(open(rd / "rows.jsonl", "rb").read()).hexdigest()[:16]
    nrows = sum(1 for _ in open(rd / "rows.jsonl"))
    print(f"\n{label} [{grp}] {d}  起跑 {start}  400政策={era}")
    print(f"   rows={nrows} sha16={sha}  void 總數={len(voids)}")
    for arm in sorted(by_arm):
        items = ", ".join(f"{k}={v}" for k, v in by_arm[arm].most_common())
        print(f"   {arm:<7} n={sum(by_arm[arm].values()):<4} {items}")
    if total:
        top, topn = total.most_common(1)[0]
        print(f"   >> 主類 {top} {topn}/{sum(total.values())} = "
              f"{100*topn/sum(total.values()):.1f}%")
    if rate is not None:
        print(f"   >> Q3 可補量（同 run 另一臂成功過）= {rec}/{len(voids)} = {100*rate:.1f}%")
    # Q2
    at = V.http400_attempts(rd)
    if at:
        print(f"   >> Q2 HTTP400 呼叫的 attempt 分佈 = {dict(sorted(at.items()))}"
              f"  最大 attempt={max(at)}")
    else:
        print(f"   >> Q2 HTTP400 失敗呼叫 = 0 筆")
    out["strata"].append({
        "label": label, "group": grp, "dir": d, "start": start, "policy_era": era,
        "rows": nrows, "rows_sha256_16": sha, "void_total": len(voids),
        "by_arm": {k: dict(v) for k, v in by_arm.items()},
        "total_by_class": dict(total),
        "recoverable": rec, "recoverable_rate": rate,
        "http400_attempt_hist": {str(k): v for k, v in at.items()},
    })

print("\n" + "=" * 78)
print(f"UNPARSED 總數 = {unparsed_total}   "
      f"{'✔ P-R662-4 成立' if unparsed_total == 0 else '✘ BROKEN：分類法沒窮舉完'}")
out["unparsed_total"] = unparsed_total
json.dump(out, open(pathlib.Path(__file__).parent / "voidclass_6strata.json", "w"),
          ensure_ascii=False, indent=2)
