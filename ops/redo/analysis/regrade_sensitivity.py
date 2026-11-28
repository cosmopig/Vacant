#!/usr/bin/env python3
"""事後敏感度（2026-11-28；不叫模型）：用「第二正規化器」重評。把 ops.d2.expT_metrics.strict_status 換成寬鬆版
（原判對的照舊；原判不是對的，若合 K 規則——答案去掉『; N years ago』後等值，或答案裡的（交易所, 代號）對包含值的全部對——改判對），
然後原封不動執行既有的分析程式（同參數），輸出另存。第二正規化器的規則是看資料後定的（judge_v2v3_20261128/PLAN.md 步驟 0）。
代號規則在這裡不看欄位名（strict_status 拿不到欄位名），改以「答案裡抽得出交易所代號對」為條件；在確認批次上與看欄位名的版本逐行比對見 --selfcheck。
用法：regrade_sensitivity.py <分析程式.py> -- <該程式原本的參數…>
      regrade_sensitivity.py --selfcheck R1 R2"""
from __future__ import annotations
import pathlib, runpy, sys
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import judge_pages as P  # noqa: E402
from ops.d2 import expT_metrics as M  # noqa: E402

_ORIG = M.strict_status
STATS = {"calls": 0, "flipped_age": 0, "flipped_ticker": 0}


def key_equiv_nolabel(val, ans):
    if val is None or ans is None:
        return None
    cv = M.canon_strict(val)
    if cv is not None and P.AGE_RE.search(ans) and cv == M.canon_strict(P.AGE_RE.sub("", ans)):
        return "age"
    vp, ap = P.ticker_pairs(val), P.ticker_pairs(ans)
    if vp and ap and vp <= ap:
        return "ticker"
    return None


def lenient_status(val, cid, truth, k=0):
    STATS["calls"] += 1
    s = _ORIG(val, cid, truth, k)
    if s == "correct" or val is None or not str(val).strip():
        return s
    e = key_equiv_nolabel(val, truth[k].get(cid))
    if e:
        STATS["flipped_" + e] += 1
        return "correct"
    return s


def selfcheck(roots):
    import json
    roots = [pathlib.Path(r) for r in roots]
    plan = json.loads((roots[0] / "RUN.json").read_text())["plan_body"]; truth = M.load_manifests_with_truth(plan)
    agree = dis = 0
    for root in roots:
        for c0 in sorted(root.glob("cells/*/r[1-5]/c0")):
            sid = c0.parts[-3]
            vals = M.SD.parse_report((c0 / "report.md").read_text(errors="replace"), truth[sid]["claims"])
            for c in truth[sid]["claims"]:
                v = vals.get(c["id"])
                if v in (None, "") or _ORIG(v, c["id"], truth[sid]["truth"], 0) == "correct":
                    continue
                a = P.key_equiv(v, truth[sid]["truth"][0][c["id"]], c.get("label", "")) is not None
                b = key_equiv_nolabel(v, truth[sid]["truth"][0][c["id"]]) is not None
                agree += a == b; dis += a != b
    print(json.dumps({"agree": agree, "disagree": dis}))


def main():
    if sys.argv[1] == "--selfcheck":
        return selfcheck(sys.argv[2:4])
    target = sys.argv[1]; args = sys.argv[sys.argv.index("--") + 1:]
    M.strict_status = lenient_status
    sys.argv = [target] + args
    try:
        runpy.run_path(target, run_name="__main__")
    finally:
        print("REGRADE_STATS", STATS, file=sys.stderr)


if __name__ == "__main__":
    main()
