#!/usr/bin/env python3
"""D2′ 第三輪稽核（11-25）要求的補充數字，一律由程式產生、不手抄：

1. 分週期類型的成本：F（有事實改動）、N＋Z（頁面沒變或只有無關改動）各自的 token 總和與比值（同一套 cluster bootstrap、
   97.5% 雙側區間，和確認性家族一致）；主要臂一次 agent 都沒叫的週期數，以及 b 的 token 有多少花在那些週期。
2. 分台的成本比（--strata 1003:s01-s40,1004:s41-s60）。
3. 候選集合的大小（第 1 週期候選檢查裡帶著值的候選頁數；平均、兩個以上的比例）——第三輪的覆蓋率是「候選集合含正確頁」，是超集合。
4. 主要臂的交辦裡不必要的（宣稱的真值那一週期沒變）：原因分成「只有錯的候選頁變了」「正確頁變了但這個值沒變（雜訊片段）」「沒有出處」。

用法：cycle_costs.py --root R --manifest M --primary cCGR --d-arm d_diff [--metric tokens] [--strata ...] [--out J]
"""
from __future__ import annotations

import argparse
import collections
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from analyze_d2 import compute_cost_ratio, draw_cluster_weights, load_harness, _extract_metric  # noqa: E402


def ratio(costs, num, den, metric, keep, sets, weights):
    sub = {k: v for k, v in costs.items() if keep(k[0], k[2])}
    r = compute_cost_ratio(sub, num, den, metric, set_ids=sets, weights=weights, ci_level=0.975)
    return {"point": r.get("point"), "ci": r.get("ci"), "n": r.get("n_paired_used")}


def total(costs, arm, metric, keep):
    return sum(_extract_metric(v, metric) or 0 for k, v in costs.items() if k[1] == arm and keep(k[0], k[2]))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--primary", default="cCGR")
    ap.add_argument("--d-arm", default="d_diff")
    ap.add_argument("--metric", default="tokens")
    ap.add_argument("--strata", default="")
    ap.add_argument("--exclude-sets", default="", help="敏感度分析：剔除這些組（逗號分隔）")
    ap.add_argument("--out")
    a = ap.parse_args()
    root = pathlib.Path(a.root).expanduser()
    man = json.loads(pathlib.Path(a.manifest).expanduser().read_text())
    msets = {s["set"]: s for s in man["sets"]}
    _r, costs = load_harness(root)
    excl = {x for x in a.exclude_sets.split(",") if x}
    costs = {k: v for k, v in costs.items() if k[0] not in excl and int(k[2]) > 0}
    sets = sorted({k[0] for k in costs})
    weights = draw_cluster_weights(len(sets), n_boot=10000, seed=20261125)
    ctype = {(s, c["cycle"]): c.get("type", "F") for s in sets for c in msets[s]["cycles"]}
    P, D, M = a.primary, a.d_arm, a.metric
    out: dict = {"root": root.name, "primary": P, "d_arm": D, "metric": M, "sets": len(sets), "excluded": sorted(excl)}
    groups = {"F": lambda s, c: ctype[(s, int(c))] == "F", "N+Z": lambda s, c: ctype[(s, int(c))] in ("N", "Z"),
              "N": lambda s, c: ctype[(s, int(c))] == "N", "Z": lambda s, c: ctype[(s, int(c))] == "Z",
              "all": lambda s, c: True}
    tab = {}
    for g, keep in groups.items():
        row = {arm: total(costs, arm, M, keep) for arm in ("b", P, D)}
        row["b/" + P] = ratio(costs, "b", P, M, keep, sets, weights)
        row[D + "/" + P] = ratio(costs, D, P, M, keep, sets, weights)
        tab[g] = row
    out["by_cycle_type"] = tab
    # 主要臂沒叫 agent 的週期
    idle = {(k[0], int(k[2])) for k, v in costs.items() if k[1] == P and not v.get("ran")}
    b_tok_all = total(costs, "b", M, lambda s, c: True)
    b_tok_idle = total(costs, "b", M, lambda s, c: (s, int(c)) in idle)
    out["primary_idle_cycles"] = {"idle": len(idle), "of": sum(1 for k in costs if k[1] == P),
                                  "b_metric_share_in_idle": (b_tok_idle / b_tok_all) if b_tok_all else None}
    # 分台
    if a.strata:
        st = {}
        for part in a.strata.split(","):
            name, rng = part.split(":")
            lo, hi = (int(x[1:]) for x in rng.split("-"))
            keep = (lambda lo, hi: (lambda s, c: lo <= int(s[1:]) <= hi))(lo, hi)
            ss = [s for s in sets if lo <= int(s[1:]) <= hi]
            w = draw_cluster_weights(len(ss), n_boot=10000, seed=20261125)
            sub = {k: v for k, v in costs.items() if keep(k[0], k[2])}
            st[name] = {"b/" + P: ratio(sub, "b", P, M, lambda s, c: True, ss, w),
                        D + "/" + P: ratio(sub, D, P, M, lambda s, c: True, ss, w)}
        out["strata"] = st
    # 候選集合大小與不必要的交辦
    sizes = []
    unnecessary = collections.Counter()
    handed_total = 0
    for s in sets:
        sm = msets[s]
        rep = root / "cells" / s / "c0" / "report.md"
        if not rep.exists():
            continue
        lines = rep.read_text().splitlines()
        line_of = {}
        for cl in sm["claims"]:
            ln = next((i + 1 for i, x in enumerate(lines) if x.strip().startswith(cl["template_line"].strip())), None)
            if ln:
                line_of[ln] = cl
        for k in range(1, len(sm["cycles"]) + 1):
            cdir = root / "cells" / s / P / f"cycle_{k}"
            scp = cdir / "sources_check.json"
            cyc = cdir / "cycle.json"
            if not scp.exists() or not cyc.exists():
                continue
            sc = json.loads(scp.read_text())
            per = {c["line"]: c for c in sc.get("claims", [])}
            if k == 1:
                for c in sc.get("claims", []):
                    if c["line"] in line_of and c.get("per_url"):
                        sizes.append(len(c["per_url"]))
            handed = (json.loads(cyc.read_text()).get("sources_check") or {}).get("handed_lines") or []
            for ln in handed:
                handed_total += 1
                cl = line_of.get(ln)
                if cl is None:
                    unnecessary["line not a claim (draft changed it)"] += 1
                    continue
                if sm["truth"][k][cl["id"]] != sm["truth"][k - 1][cl["id"]]:
                    continue
                c = per.get(ln) or {}
                if c.get("status") == "no_source":
                    unnecessary["no source (handed every cycle)"] += 1
                    continue
                changed = [u for u, st in (c.get("per_url") or {}).items() if st != "unchanged"]
                srcs = cl.get("source_pages") or [cl.get("source_page")]
                if any(u.rsplit("/", 1)[-1] in srcs for u in changed):
                    unnecessary["correct page changed, value did not (noise segment)"] += 1
                else:
                    unnecessary["only a wrong candidate page changed"] += 1
    out["candidate_set_size_cycle1"] = {"claims": len(sizes), "mean": (sum(sizes) / len(sizes)) if sizes else None,
                                        "share_ge2": (sum(x >= 2 for x in sizes) / len(sizes)) if sizes else None}
    out["handed"] = {"total": handed_total, "unnecessary": sum(unnecessary.values()), "by_reason": dict(unnecessary)}
    txt = json.dumps(out, ensure_ascii=False, indent=1)
    if a.out:
        pathlib.Path(a.out).expanduser().write_text(txt + "\n")
    print(txt)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
