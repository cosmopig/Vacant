"""V0：既有閘門（可見測試）當驗證器——對隱藏測試真值的準確度。**零 token、零 API 呼叫。**

資料：`runs/INDEX.json` 裡 kind=real_run、`rows.jsonl` 有 `visible_ok` 與 `meets_demand` 的 run，
只取 **OFF 臂**（單次嘗試、沒有閘門介入 ⇒ 產出的分布沒有被驗證器本身挑過）。
`visible_ok`＝確定性驗證器的裁決；`meets_demand`＝隱藏測試（GT）。
⚠ 同一題會出現在多個 run（不同模型／seed）；池化數字是「列」不是「題」，另給逐題庫、逐 run 的數。
⚠ `runs/INDEX.md`：`_analysis_*` 是衍生物，本檔不讀。
重跑：python3 ops/research_20260924/verifier/exp_visible_gate.py
"""
import collections, json, os, pathlib, sys
REPO = pathlib.Path(__file__).resolve().parents[3]
I = json.load(open(REPO / "runs/INDEX.json"))
by_fam = collections.defaultdict(lambda: collections.Counter())
per_run = []
for r in I["runs"]:
    if r.get("kind") != "real_run":
        continue
    p = REPO / "runs" / r["name"] / "rows.jsonl"
    if not p.exists():
        continue
    off = [json.loads(l) for l in open(p)]
    off = [x for x in off if x.get("arm") == "OFF" and isinstance(x.get("visible_ok"), bool)
           and isinstance(x.get("meets_demand"), bool)]
    if not off:
        continue
    fam = (r.get("bank") or {}).get("family") or "unknown"
    c = collections.Counter((x["visible_ok"], x["meets_demand"]) for x in off)
    by_fam[fam].update(c)
    per_run.append({"run": r["name"], "family": fam, "n": len(off),
                    "vis_pass_hid_pass": c[(True, True)], "vis_pass_hid_fail": c[(True, False)],
                    "vis_fail_hid_pass": c[(False, True)], "vis_fail_hid_fail": c[(False, False)]})


def summ(c):
    tp, fp, fn, tn = c[(True, True)], c[(True, False)], c[(False, True)], c[(False, False)]
    n = tp + fp + fn + tn
    return {"n_rows": n, "accept": tp + fp, "reject": fn + tn,
            "precision_of_accept": round(tp / (tp + fp), 4) if tp + fp else None,
            "leak_rate_among_accepted": round(fp / (tp + fp), 4) if tp + fp else None,
            "false_reject_rate_among_rejected": round(fn / (fn + tn), 4) if fn + tn else None,
            "accuracy": round((tp + tn) / n, 4) if n else None,
            "base_rate_hidden_pass": round((tp + fn) / n, 4) if n else None,
            "tokens_per_item": 0}


tot = collections.Counter()
for c in by_fam.values():
    tot.update(c)
out = {"pooled": summ(tot), "by_family": {k: summ(v) for k, v in sorted(by_fam.items())},
       "runs_n": len(per_run), "per_run": per_run}
dst = pathlib.Path(__file__).parent / "results" / "v0_visible_gate.json"
dst.write_text(json.dumps(out, ensure_ascii=False, indent=1))
print(json.dumps({k: out[k] for k in ("pooled", "by_family", "runs_n")}, ensure_ascii=False, indent=1))
