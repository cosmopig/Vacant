#!/usr/bin/env python3
"""實驗 T：TE／TER 的離線敏感度分析（**非預註冊**，判讀之後才加；不叫任何模型）。

預註冊的實作（`expT_feedback.apply_haiku_replacements`）在 Haiku 對某一行沒有給值時（回「not found in sources」、
空白、或因 max_tokens=1024 被截斷而漏掉），把那一行改寫成「not found in sources」——草稿原本的值（包括對的）被刪掉。
這支用落盤的 `haiku_escalation.extracted` 重建兩種替代版本、用同一份嚴格評分（`expT_metrics.score_cell`）重算：
  keep_on_null：Haiku 沒給值的行保留草稿原值，只替換 Haiku 給了值的行；
  drop_truncated：排除 Haiku 回覆停在 max_tokens 的格（整對排除）。
輸出：每臂 (a)、(b)、傷害，TE−TER 的配對差與以組為群集的 bootstrap 區間（同 expT_metrics 的種子與重抽數）。
用法：expT_te_sensitivity.py <root> [--json OUT]
"""
from __future__ import annotations
import argparse, json, pathlib, random, sys
REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from ops.d2 import expT_metrics as M  # noqa: E402
from ops.d2 import expT_feedback as FB  # noqa: E402

def main() -> None:
    ap = argparse.ArgumentParser(); ap.add_argument("root"); ap.add_argument("--json"); ap.add_argument("--boot", type=int, default=2000)
    a = ap.parse_args(); root = pathlib.Path(a.root)
    plan = json.loads((root / "RUN.json").read_text())["plan_body"]; truth = M.load_manifests_with_truth(plan)
    reps = int(plan.get("reps") or 2); res = {}
    for variant in ("as_run", "keep_on_null", "drop_truncated"):
        per = {}
        for sid, st in truth.items():
            for rep in range(1, reps + 1):
                rdir = root / "cells" / sid / f"r{rep}"; c0 = (rdir / "c0" / "report.md").read_text(errors="replace")
                trunc = False; recs = {}
                for arm in ("A", "TE", "TER"):
                    cd = json.loads((rdir / arm / "cell.json").read_text())
                    final = (rdir / arm / "report.md").read_text(errors="replace")
                    h = cd.get("haiku_escalation") or {}
                    if h.get("stop_reason") == "max_tokens": trunc = True
                    if variant == "keep_on_null" and h.get("called"):
                        ex = h.get("extracted") or {}
                        ids = [k for k in (h.get("escalated_claim_ids") or []) if ex.get(k) not in (None, "")]
                        final = FB.apply_haiku_replacements(c0, st["claims"], ids, ex)
                    r = M.score_cell(cd, c0, final, st, chain_path=None, verify_chain=False)
                    recs[arm] = r
                if variant == "drop_truncated" and trunc:
                    continue
                per[(sid, rep)] = recs
        def m(arm, key):
            n = sum(len(v[arm]["lines"]) for v in per.values())
            if key == "a": return sum(x["after_status"] == "correct" for v in per.values() for x in v[arm]["lines"]) / n
            if key == "harm": return sum(v[arm]["harm_c2w_or_d"] for v in per.values()), sum(v[arm]["harm_b2w"] for v in per.values())
        # set-cluster bootstrap of TE-TER and TE-A on per-pair correct proportion
        sets = sorted({k[0] for k in per}); rng = random.Random(20261127)
        def diff(sel, t, c):
            num = sum(sum(x["after_status"] == "correct" for x in per[k][t]["lines"]) - sum(x["after_status"] == "correct" for x in per[k][c]["lines"]) for k in sel)
            den = sum(len(per[k][t]["lines"]) for k in sel); return num / den if den else 0.0
        out = {"pairs": len(per), "sets": len(sets)}
        for arm in ("A", "TE", "TER"):
            out[arm] = {"a_correct_prop": round(m(arm, "a"), 4), "harm_c2w_or_d": m(arm, "harm")[0], "harm_b2w": m(arm, "harm")[1]}
        for t, c in (("TE", "TER"), ("TE", "A"), ("TER", "A")):
            point = diff(list(per), t, c); bs = []
            for _ in range(a.boot):
                pick = [rng.choice(sets) for _ in sets]; sel = [k for s in pick for k in per if k[0] == s]
                bs.append(diff(sel, t, c))
            bs.sort(); out[f"{t}_minus_{c}_pp"] = [round(100 * point, 2), round(100 * bs[int(0.025 * a.boot)], 2), round(100 * bs[int(0.975 * a.boot) - 1], 2)]
        res[variant] = out; print(variant, json.dumps(out, ensure_ascii=False))
    if a.json: pathlib.Path(a.json).write_text(json.dumps(res, ensure_ascii=False, indent=1))

if __name__ == "__main__":
    main()
