#!/usr/bin/env python3
"""實驗一確認性判定：把批 A（軟體＋公司）與批 B（足球員）的逐條標記列合併（以組為群集），照預註冊
（exp1_flags_prereg.json＋amend1＋amend2）判定：三類合併判定、三類各自並列；**若合併通過但軟體＋公司單獨不過，結論寫成不過**。
用法：exp1_combine.py --a A.json --b B.json --out OUT.json"""
from __future__ import annotations

import argparse
import collections
import json
import pathlib
import random


def summarize(rs: list[dict], boot: int = 2000) -> dict:
    n = len(rs)
    fl = sum(r["flagged"] for r in rs)
    er = sum(r["error"] for r in rs)
    tp = sum(r["flagged"] and r["error"] for r in rs)
    in_rate = tp / fl if fl else None
    out_rate = (er - tp) / (n - fl) if n - fl else None
    sets = sorted({r["set"] for r in rs})
    by_set = {s: [r for r in rs if r["set"] == s] for s in sets}
    rng = random.Random(20261126)
    recs = []
    for _ in range(boot if er else 0):
        pick = [rng.choice(sets) for _ in sets]
        e2 = sum(r["error"] for s in pick for r in by_set[s])
        t2 = sum(r["error"] and r["flagged"] for s in pick for r in by_set[s])
        if e2:
            recs.append(t2 / e2)
    recs.sort()
    fs, rc = (fl / n if n else None), (tp / er if er else None)
    lo = recs[int(0.05 * len(recs))] if recs else None
    ratio = (in_rate / out_rate) if in_rate is not None and out_rate else None
    erate = er / n if n else None
    if fs is None or rc is None:
        v = "n/a"
    elif rc < 0.5 or fs > max(0.5, erate + 0.25):
        v = "FAIL"
    elif rc >= 0.7 and (lo or 0) >= 0.6 and (ratio is None or ratio >= 3) and fs <= max(0.3, erate + 0.15):
        v = "PASS"
    else:
        v = "UNRESOLVED"
    et = collections.Counter((r.get("etype", r["status"]), r["flagged"]) for r in rs if r["error"])
    return {"units": n, "sets": len(sets), "flagged_share": fs, "errors": er, "error_rate": erate, "recall": rc,
            "recall_lower95": lo, "error_rate_flagged": in_rate, "error_rate_unflagged": out_rate, "rate_ratio": ratio,
            "verdict": v, "errors_by_type": {f"{k}|{'flagged' if f else 'missed'}": c for (k, f), c in sorted(et.items())},
            "recall_by_type": {t: (et[(t, True)] / (et[(t, True)] + et[(t, False)])) if (et[(t, True)] + et[(t, False)]) else None
                               for t in sorted({k for k, _ in et})},
            "plain": {"look_share": fs, "miss_share_of_errors": (1 - rc) if rc is not None else None,
                      "random_same_size_miss_share": (1 - fs) if fs is not None else None}}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--a", required=True)
    ap.add_argument("--b", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    rows = []
    for tag, p in (("A", a.a), ("B", a.b)):
        for r in json.loads(pathlib.Path(p).read_text())["rows"]:
            rows.append({**r, "set": f"{tag}_{r['set']}"})
    sc = [r for r in rows if not r["domain"].startswith("football")]
    res = {"combined": summarize(rows), "software_plus_companies": summarize(sc),
           "by_domain": {d: summarize([r for r in rows if r["domain"] == d]) for d in sorted({r["domain"] for r in rows})},
           "combined_excl_missing": summarize([r for r in rows if r["status"] != "missing"]),
           "sc_excl_missing": summarize([r for r in sc if r["status"] != "missing"])}
    v, vsc = res["combined"]["verdict"], res["software_plus_companies"]["verdict"]
    res["final_verdict"] = "FAIL" if (v == "PASS" and vsc != "PASS") else v
    res["rule"] = "三類合併判定；若合併通過但軟體＋公司單獨不過，結論寫成不過（預註冊修正 1）。"
    pathlib.Path(a.out).write_text(json.dumps(res, ensure_ascii=False, indent=1))
    keep = ("units", "sets", "flagged_share", "errors", "error_rate", "recall", "recall_lower95", "rate_ratio", "verdict")
    brief = {}
    for k, v in res.items():
        if isinstance(v, dict) and "units" in v:
            brief[k] = {kk: (round(vv, 3) if isinstance(vv, float) else vv) for kk, vv in v.items() if kk in keep}
        elif k != "by_domain":
            brief[k] = v
    print(json.dumps(brief, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
