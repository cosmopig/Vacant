#!/usr/bin/env python3
"""評分器效度 1(b)(c)：確認批次全部產出（初稿 c0、回饋 A/G/T/TB、E 的 EB/ER/EN）裡被判『對』的有值行。
(b) 機械找『數字相同、但尺度／幣別／正負號／百分比／月份／期間字樣不同』的行（分臂、分題組）；
(c) 每題組隨機抽 40 行（種子 20261128）供人工核；公開輸出只有 HMAC 行鍵與分類，值另存私有檔。
兩種評分各算一次：原 strict、第二正規化器（寬鬆）。用法：scorer_correct_audit.py D1 D2 FB1 FB2 --private DIR"""
import collections, json, pathlib, random, re, sys
HERE = pathlib.Path(__file__).resolve().parent; sys.path.insert(0, str(HERE))
from audit_key import audit_hmac  # noqa: E402
from regrade_sensitivity import key_equiv_nolabel, M, _ORIG  # noqa: E402
lk = lambda *p: audit_hmac("|".join(map(str, p)))
SCALE = re.compile(r"\b(thousand|million|mllion|billion|trillion|bn|mn)\b", re.I)
SCALE_N = {"thousand": "k", "million": "m", "mllion": "m", "mn": "m", "billion": "b", "bn": "b", "trillion": "t"}
CUR = re.compile(r"(US\$|A\$|C\$|HK\$|NT\$|R\$|CN¥|JP¥|\$|€|£|¥|₹|₩|\b(?:USD|EUR|GBP|JPY|CNY|RMB|INR|CHF|KRW|CAD|AUD|HKD|SEK|NOK|DKK|BRL|TWD)\b)")
CUR_N = {"$": "usd?", "us$": "usd", "usd": "usd", "€": "eur", "eur": "eur", "£": "gbp", "gbp": "gbp", "¥": "jpy/cny", "jp¥": "jpy", "jpy": "jpy",
         "cn¥": "cny", "cny": "cny", "rmb": "cny", "₹": "inr", "inr": "inr"}
MON = re.compile(r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\b", re.I)
PER = re.compile(r"\b(FY|Q[1-4]|H[12]|fiscal)\b", re.I)


def markers(s):
    s = s or ""
    return {"scale": {SCALE_N[m.group(1).lower()] for m in SCALE.finditer(s)},
            "cur": {CUR_N.get(m.group(1).lower(), m.group(1).lower()) for m in CUR.finditer(s)},
            "neg": bool(re.search(r"(^|[\s:])[-−]\s?\d|\bloss\b|\bminus\b", s, re.I)),   # 括號數字不算負號（足球『(進球)』）；區間的 – 不算
            "pct": "%" in s or bool(re.search(r"\bper\s?cent\b", s, re.I)),
            "mon": {m.group(1).lower()[:3] for m in MON.finditer(s)}, "per": {m.group(1).lower() for m in PER.finditer(s)}}


def diff_kinds(v, a):
    mv, ma = markers(v), markers(AGE_SUB(a)); out = []
    for k in ("scale", "cur", "mon", "per"):
        if mv[k] and ma[k] and mv[k] != ma[k]:
            if not (k == "cur" and ({"usd?"} <= mv[k] | ma[k]) and (mv[k] | ma[k]) <= {"usd?", "usd"}):
                out.append(f"{k}_conflict")
        elif ma[k] and not mv[k]:
            out.append(f"{k}_omitted")
        elif mv[k] and not ma[k]:
            out.append(f"{k}_extra")
    for k in ("neg", "pct"):
        if mv[k] != ma[k]:
            out.append(f"{k}_mismatch")
    return out


AGE_SUB = lambda a: re.sub(r";?\s*\d+\s+years?\s+ago", "", a or "", flags=re.I)


def main():
    d1, d2, f1, f2 = [pathlib.Path(x) for x in sys.argv[1:5]]; priv = pathlib.Path(sys.argv[sys.argv.index("--private") + 1]); priv.mkdir(parents=True, exist_ok=True)
    plan = json.loads((d1 / "RUN.json").read_text())["plan_body"]; truth = M.load_manifests_with_truth(plan)
    reps = []
    for root in (d1, d2):
        reps += [(p, "c0") for p in root.glob("cells/*/r[1-5]/c0/report.md")]
        reps += [(p, p.parts[-2]) for p in root.glob("escalation/*/r[1-5]/E[BRN]/report.md")]
    for root in (f1, f2):
        reps += [(p, p.parts[-2]) for p in root.glob("cells/*/r[1-5]/*/report.md") if p.parts[-2] in ("A", "G", "T", "TB")]
    out = {}
    for mode in ("strict", "second"):
        rows = []
        for p, arm in reps:
            sid = next(x for x in p.parts if x.startswith(("cc-", "ff-"))); rep = next(x for x in p.parts if re.fullmatch(r"r\d", x))
            vals = M.SD.parse_report(p.read_text(errors="replace"), truth[sid]["claims"])
            for c in truth[sid]["claims"]:
                v = vals.get(c["id"])
                if v in (None, "") or not str(v).strip():
                    continue
                a = truth[sid]["truth"][0][c["id"]]
                ok = _ORIG(v, c["id"], truth[sid]["truth"], 0) == "correct" or (mode == "second" and key_equiv_nolabel(v, a) is not None)
                if not ok:
                    continue
                dk = diff_kinds(str(v), str(a))
                rows.append({"key": lk(sid, rep, arm, c["id"]), "arm": arm, "set": sid, "domain": "companies" if sid.startswith("cc") else "football",
                             "field": c.get("label") if sid.startswith("cc") else "apps (goals)", "kinds": dk, "_v": v, "_a": a})
        tab = collections.defaultdict(collections.Counter)
        for r in rows:
            for k in r["kinds"] or ["none"]:
                tab[f"{r['domain']}|{k}"][r["arm"]] += 1
        flagged = [r for r in rows if r["kinds"]]
        out[mode] = {"judged_correct_lines": len(rows), "by_domain": dict(collections.Counter(r["domain"] for r in rows)),
                     "marker_diff_lines": len(flagged), "marker_diff_by_domain": dict(collections.Counter(r["domain"] for r in flagged)),
                     "marker_diff_by_kind_arm": {k: dict(v) for k, v in sorted(tab.items()) if not k.endswith("|none")},
                     "marker_diff_by_field": dict(collections.Counter(f"{r['domain']}|{r['field']}" for r in flagged))}
        (priv / f"marker_diff_{mode}.jsonl").write_text("".join(json.dumps({k: r[k] for k in ("key", "arm", "set", "field", "kinds", "_v", "_a")}, ensure_ascii=False) + "\n" for r in flagged))
        if mode == "second":
            rng = random.Random(20261128); samp = []
            for dom in ("companies", "football"):
                grp = sorted([r for r in rows if r["domain"] == dom], key=lambda r: r["key"]); rng.shuffle(grp); samp += grp[:40]
            (priv / "manual_sample_80.jsonl").write_text("".join(json.dumps({k: r[k] for k in ("key", "arm", "set", "domain", "field", "_v", "_a")}, ensure_ascii=False) + "\n" for r in samp))
            out["manual_sample_keys"] = {dom: [r["key"] for r in samp if r["domain"] == dom] for dom in ("companies", "football")}
    o = HERE.parent / "audit/scorer_validity_20261128/judged_correct_marker_audit.json"
    o.write_text(json.dumps({"note": "1(b)：被判對的行中『數字相同但字樣不同』的機械篩選（無值）；1(c) 抽樣行鍵。行鍵＝HMAC(set|rep|arm|claim)。", **out}, ensure_ascii=False, indent=1))
    print(json.dumps({m: {k: out[m][k] for k in ("judged_correct_lines", "by_domain", "marker_diff_lines", "marker_diff_by_domain", "marker_diff_by_field")} for m in ("strict", "second")}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
