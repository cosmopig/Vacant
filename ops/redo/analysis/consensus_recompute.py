#!/usr/bin/env python3
"""獨立重算核對（2026-11-28，只用標準函式庫、不叫模型、不 import consensus_offline.py）。

核對對象：ops/redo/analysis/consensus_offline.py 的輸出（確認批次 30 組 x 5 份初稿）。
這支做三件事，且**只讀 repo 裡已提交的資料**：
 (1) 從逐份資料（v4_b61.json selector.all.per_draft：每份的 filled／filled_correct／blank_count／evidence_score）
     重算 A、record、nonblank、最好的一份（oracle），k=5 與 k=3，含組群集 bootstrap；
 (2) 用 efamily_per_draft_pools.jsonl 重算紀錄旗標（E 家族定義）當交叉比對；
 (3) 對「逐行多數決、逐行 oracle、一致度旗標」只能做內部一致性檢查——
     這三項需要每組每行 5 份初稿的值（或同一把鍵的 HMAC），提交的資料裡**沒有**
     （expT_lines*.jsonl 只有 r1、r2；r3–r5 逐行資料不在 git）。腳本把這點明寫進輸出，不假裝重算。
第二部分（r1_r5_lines）：用 drafts_r1_r5_lines_hmac.jsonl（r1–r5 逐行 HMAC）真的重算逐行多數決、oracle、一致度旗標、
空白／平手敏感度，並用 judge_lines_all.jsonl 重算判別模型先導（AUC、門檻、校準、組合）。判別行檔沒有 set／rep／claim，
只有 HMAC 行鍵（鍵不在 git）⇒ 以檔案順序對齊，並驗證 1747 行的 領域、對錯、紀錄旗標逐行全部相符（見輸出 alignment）。
用法：consensus_recompute.py <repo_or_worktree_root> --out DIR
"""
from __future__ import annotations
import argparse, collections, json, pathlib, random, re, statistics

SEED, NB = 20261128, 2000
AUD = "ops/redo/audit"


def boot(vals):
    """以組為群集：重抽組（每組一個差值），取均值；百分位區間。種子寫死。"""
    rng = random.Random(SEED)
    n = len(vals)
    bs = sorted(sum(vals[rng.randrange(n)] for _ in range(n)) / n for _ in range(NB))
    return [round(bs[int(0.025 * NB)], 4), round(bs[int(0.975 * NB) - 1], 4)]


def load(root):
    r = pathlib.Path(root)
    v4 = json.loads((r / AUD / "expTc_20261128/expTc_confirm_analysis_20261128_v4_b61.json").read_text())
    pools = [json.loads(l) for l in (r / AUD / "expTc_20261128/efamily/efamily_per_draft_pools.jsonl").read_text().splitlines()]
    rep = json.loads((r / AUD / "consensus_20261128/consensus_offline.json").read_text())
    return v4["selector"]["all"]["per_draft"], pools, rep


def selectors(per_draft, K):
    by = collections.defaultdict(list)
    for d in per_draft:
        if d["rep"] <= K:
            by[d["set"]].append(d)
    out = {}
    for s, ds in sorted(by.items()):
        if len(ds) < K:
            continue
        prop = lambda d: d["filled_correct"] / d["n_claims"]
        rec = max(ds, key=lambda d: (int(d["evidence_score"]), -int(d["blank_count"]), -int(d["rep"])))
        nb = max(ds, key=lambda d: (int(d["n_claims"]) - int(d["blank_count"]), -int(d["rep"])))
        out[s] = {"A": statistics.mean(prop(d) for d in ds), "record": prop(rec), "nonblank": prop(nb),
                  "oracle": max(prop(d) for d in ds)}
    return out


def pairs(per, a, b):
    vals = [v[a] - v[b] for _, v in sorted(per.items())]
    return {"mean": round(sum(vals) / len(vals), 4), "ci95": boot(vals), "sets": len(vals)}


def int_solutions(N, er, fs, ei, eo, rc):
    """由報告的四位小數反推整數 (W 錯行, F 旗標行, FW 旗標內錯)；回傳所有同時吻合者。"""
    r4 = lambda a, b: round(a / b, 4) if b else None
    sol = []
    for W in range(N + 1):
        if r4(W, N) != er:
            continue
        for F in range(N + 1):
            if r4(F, N) != fs:
                continue
            for FW in range(min(F, W) + 1):
                if r4(FW, F) == ei and r4(W - FW, N - F) == eo and r4(FW, W) == rc:
                    sol.append((W, F, FW))
    return sol


def midrank_auc(pairs):
    """pairs: [(score, y)]；y=1 為正類（這裡＝錯行）。Mann-Whitney，同分取平均名次。"""
    pairs = sorted(pairs, key=lambda t: t[0]); n = len(pairs)
    npos = sum(y for _, y in pairs); nneg = n - npos
    if not npos or not nneg:
        return None
    rp = 0.0; i = 0
    while i < n:
        j = i
        while j < n and pairs[j][0] == pairs[i][0]:
            j += 1
        rp += (i + j + 1) / 2 * sum(y for _, y in pairs[i:j]); i = j
    return (rp - npos * (npos + 1) / 2) / (npos * nneg)


def auc_boot(by_set, score_of):
    """by_set: {set: [row]}；組群集 bootstrap（重抽組）。回傳 (點估計, [2.5%, 97.5%])。"""
    sets = sorted(by_set)
    pt = midrank_auc([(score_of(r), int(r["wrong"])) for s in sets for r in by_set[s]])
    rng = random.Random(SEED); vs = []
    pre = {s: [(score_of(r), int(r["wrong"])) for r in by_set[s]] for s in sets}
    for _ in range(NB):
        smp = []
        for _ in sets:
            smp += pre[sets[rng.randrange(len(sets))]]
        v = midrank_auc(smp)
        if v is not None:
            vs.append(v)
    vs.sort()
    return round(pt, 4), [round(vs[int(0.025 * len(vs))], 4), round(vs[int(0.975 * len(vs)) - 1], 4)]


def load_lines(root):
    D = [json.loads(l) for l in (root / AUD / "consensus_20261128/drafts_r1_r5_lines_hmac.jsonl").read_text().splitlines()]
    J = [json.loads(l) for l in (root / AUD / "judge_gemini_decision_20261128/judge_lines_all.jsonl").read_text().splitlines()]
    JA = json.loads((root / AUD / "judge_gemini_decision_20261128/judge_analysis.json").read_text())
    return D, J, JA


def vote_val(r, unparsed_vote):
    if not r["filled"]:
        return None
    if r["canon_parsed"] or unparsed_vote:
        return r["value_hmac"]
    return None


def line_score(cells, tie, blank_vote, unparsed_vote):
    """cells: [(rep, row)]（rep 小到大）。回傳這一行的多數決正確度（0/1，'expect' 時為期望值）與是否平手。"""
    cnt = collections.Counter(); first = {}; corr = {}
    for rp, r in cells:
        v = vote_val(r, unparsed_vote)
        if v is None:
            if not blank_vote:
                continue
            v = "∅"
        cnt[v] += 1
        if v not in first:
            first[v] = rp; corr[v] = (r["correct"] and v != "∅")
    if not cnt:
        return 0.0, False
    top = max(cnt.values()); cand = [v for v in cnt if cnt[v] == top]; tied = len(cand) > 1
    if not tied:
        return float(corr[cand[0]]), False
    if tie == "blank_loses" :
        nb = [v for v in cand if v != "∅"]
        return float(corr[min(nb, key=lambda v: first[v])]) if nb else 0.0, True
    if tie == "minr":
        return float(corr[min(cand, key=lambda v: first[v])]), True
    if tie == "maxr":
        return float(corr[max(cand, key=lambda v: first[v])]), True
    if tie == "expect":
        return sum(corr[v] for v in cand) / len(cand), True
    if tie == "lower":
        return float(all(corr[v] for v in cand)), True
    if tie == "upper":
        return float(any(corr[v] for v in cand)), True
    if tie == "wrong":
        return 0.0, True
    raise ValueError(tie)


def consensus_flags(cells_by_claim, thr_mode="base"):
    """回傳 {(rep,claim): (flag, support)}，只含有填行（值非空；解析不出的值用 HMAC 比對＝事後選定）。"""
    out = {}
    for cid, cells in cells_by_claim.items():
        vs = [(rp, r["value_hmac"]) for rp, r in cells if r["filled"]]
        if not vs:
            continue
        cnt = collections.Counter(v for _, v in vs); top = max(cnt.values()); first = {}
        for rp, v in vs:
            first.setdefault(v, rp)
        maj = min([v for v in cnt if cnt[v] == top], key=lambda v: first[v])
        for rp, v in vs:
            out[(rp, cid)] = (((v != maj) or cnt[v] <= 1) if thr_mode == "base" else cnt[v] <= thr_mode, cnt[v])
    return out


def flag_stats(rows, f):
    ff = [r for r in rows if f(r)]; nf = [r for r in rows if not f(r)]; w = sum(r["wrong"] for r in rows)
    q = lambda a, b: round(a / b, 4) if b else None
    return {"flagged_share": q(len(ff), len(rows)), "err_in": q(sum(r["wrong"] for r in ff), len(ff)),
            "err_out": q(sum(r["wrong"] for r in nf), len(nf)), "recall": q(sum(r["wrong"] for r in ff), w), "n_flagged": len(ff)}


def part2(root, per_draft, rep, ctx=None):
    D, J, JA = load_lines(root)
    sets = sorted({r["set"] for r in D}); out = {}
    cell = collections.defaultdict(lambda: collections.defaultdict(list))   # set -> claim -> [(rep,row)]
    for r in D:
        cell[r["set"]][r["claim"]].append((r["rep"], r))
    for s in cell:
        for c in cell[s]:
            cell[s][c].sort(key=lambda t: t[0])
    ncl = {s: len(cell[s]) for s in cell}
    # --- 分母與差 1 行
    fil = collections.Counter(("cc" if r["set"].startswith("cc") else "ff") for r in D if r["filled"])
    nonparsed = collections.Counter(("cc" if r["set"].startswith("cc") else "ff") for r in D if r["filled"] and not r["canon_parsed"])
    h = collections.defaultdict(lambda: [0, 0])
    for r in D:
        h[(r["set"], r["rep"])][0] += r["filled"]; h[(r["set"], r["rep"])][1] += (r["filled"] and r["correct"])
    mism = [{"set": p["set"], "rep": p["rep"], "per_draft_filled": p["filled"], "per_draft_blank_count": p["blank_count"],
             "n_claims": p["n_claims"], "lines_filled": h[(p["set"], p["rep"])][0]} for p in per_draft
            if p["filled"] != h[(p["set"], p["rep"])][0] or p["filled_correct"] != h[(p["set"], p["rep"])][1]]
    out["denominator"] = {"filled_lines_by_domain": dict(fil), "filled_but_unparsed_by_domain": dict(nonparsed), "per_draft_vs_lines_mismatch": mism,
                          "per_draft_filled_plus_blank_ne_n": [p["set"] + "/r" + str(p["rep"]) for p in per_draft if p["filled"] + p["blank_count"] != p["n_claims"]]}
    # --- 選擇器（用 per_draft 的挑法，對錯用逐行資料）
    def prop(s, rp):
        return sum(1 for c in cell[s] for r_, r in cell[s][c] if r_ == rp and r["correct"]) / ncl[s]
    byset = collections.defaultdict(list)
    for p in per_draft:
        byset[p["set"]].append(p)
    base = {}
    for s in sets:
        ds = sorted(byset[s], key=lambda d: d["rep"])
        rec = max(ds, key=lambda d: (int(d["evidence_score"]), -int(d["blank_count"]), -int(d["rep"])))
        nb = max(ds, key=lambda d: (int(d["n_claims"]) - int(d["blank_count"]), -int(d["rep"])))
        props = {d["rep"]: prop(s, d["rep"]) for d in ds}
        lo = sum(any(r["correct"] for _, r in cell[s][c]) for c in cell[s]) / ncl[s]
        base[s] = {"A": statistics.mean(props.values()), "record": props[rec["rep"]], "nonblank": props[nb["rep"]], "oracle": max(props.values()), "line_oracle": lo}
    mean = lambda m: round(statistics.mean(v[m] for v in base.values()), 4)
    out["selectors_from_lines"] = {m: mean(m) for m in ("A", "record", "nonblank", "oracle", "line_oracle")}
    # --- 多數決與敏感度
    variants = {
        "base（空白不算票；解析不出的值當空白；平手取最小 r）": dict(tie="minr", blank_vote=False, unparsed_vote=False),
        "解析不出的值當一票（用 HMAC 比對）": dict(tie="minr", blank_vote=False, unparsed_vote=True),
        "空白算一票（解析不出的值仍當空白）": dict(tie="minr", blank_vote=True, unparsed_vote=False),
        "空白算一票＋解析不出的值當一票": dict(tie="minr", blank_vote=True, unparsed_vote=True),
        "空白算一票，但空白與值平手時值勝（空白須嚴格最多才勝）": dict(tie="blank_loses", blank_vote=True, unparsed_vote=False),
        "平手取最大 r": dict(tie="maxr", blank_vote=False, unparsed_vote=False),
        "平手＝隨機（期望值）": dict(tie="expect", blank_vote=False, unparsed_vote=False),
        "平手＝一律算錯（需要嚴格多數）": dict(tie="wrong", blank_vote=False, unparsed_vote=False),
        "平手下界（平手裡的值全對才算對）": dict(tie="lower", blank_vote=False, unparsed_vote=False),
        "平手上界（平手裡有一個對就算對）": dict(tie="upper", blank_vote=False, unparsed_vote=False),
    }
    out["majority"] = {}
    for name, kw in variants.items():
        per = {}; ntie = 0; nlines = 0
        for s in sets:
            tot = 0.0
            for c in cell[s]:
                sc, t = line_score(cell[s][c], **kw); tot += sc; ntie += t; nlines += 1
            per[s] = tot / ncl[s]
        ent = {"majority": round(statistics.mean(per.values()), 4), "tied_lines": ntie, "lines": nlines}
        for b in ("A", "record", "nonblank", "oracle"):
            vals = [per[s] - base[s][b] for s in sets]
            ent[f"vs_{b}"] = {"mean": round(sum(vals) / len(vals), 4), "ci95": boot(vals)}
        dom = {}
        for d, pf in (("companies", "cc"), ("football", "ff")):
            dom[d] = round(statistics.mean(per[s] for s in sets if s.startswith(pf)), 4)
        ent["by_domain"] = dom
        out["majority"][name] = ent
    # 有票值的對錯是否一致（同一個 HMAC 值在不同份的 correct 是否相同）
    inc = 0
    for s in sets:
        for c in cell[s]:
            d_ = {}
            for _, r in cell[s][c]:
                if r["filled"]:
                    d_.setdefault(r["value_hmac"], set()).add(r["correct"])
            inc += sum(len(v) > 1 for v in d_.values())
    out["same_value_different_correctness_groups"] = inc
    # --- 一致度旗標（統一分母）
    cf = {}
    for s in sets:
        for (rp, c), v in consensus_flags(cell[s]).items():
            cf[(s, rp, c)] = v
    rows = []   # 與 D 中有填行同序
    for r in D:
        if r["filled"]:
            fl, sup = cf[(r["set"], r["rep"], r["claim"])]
            rows.append({"set": r["set"], "rep": r["rep"], "claim": r["claim"], "dom": "companies" if r["set"].startswith("cc") else "football",
                         "wrong": not r["correct"], "cons": fl, "support": sup, "rec": r["er_target"]})
    # --- 對齊判別行
    ok = sum(1 for a, b in zip(rows, J) if a["dom"] == b["domain"] and a["wrong"] == b["wrong"] and a["rec"] == b["record_flag"])
    out["alignment"] = {"rows": len(rows), "judge_rows": len(J), "match_domain_wrong_record_by_position": ok,
                        "record_flag_total_E_family(er_target)": sum(r["rec"] for r in rows), "record_flag_total_judge_file": sum(j["record_flag"] for j in J),
                        "note": "判別行檔沒有 set／rep／claim；以檔案順序對齊，三個屬性 1747 行全部相符才採用。flags_v2 與 E 家族『同一組 473 行』的核對只在這個對齊成立下成立"}
    if ok != len(rows):
        out["alignment"]["WARNING"] = "未全部對上，判別相關結果不可用"
        return out
    for a, b in zip(rows, J):
        a["p"] = b["p_supported"]; a["rec_v2"] = b["record_flag"]; a["key"] = b["key"]
    out["record_flag_E_vs_flags_v2"] = {"same_set_of_lines": all(r["rec"] == r["rec_v2"] for r in rows), "n": sum(r["rec"] for r in rows)}
    if ctx is not None:
        ctx["rows"] = rows
    flags = {}
    for dom in ("football", "companies", "all"):
        rr = [r for r in rows if dom == "all" or r["dom"] == dom]
        e = {"lines": len(rr), "error_rate": round(sum(r["wrong"] for r in rr) / len(rr), 4),
             "consensus（事後定義：≠多數值或同意份數≤1）": flag_stats(rr, lambda r: r["cons"]),
             "consensus 只用 同意份數≤1": flag_stats(rr, lambda r: r["support"] <= 1),
             "consensus 同意份數≤2": flag_stats(rr, lambda r: r["support"] <= 2),
             "record": flag_stats(rr, lambda r: r["rec"])}
        flags[dom] = e
    out["flags_unified_denominator"] = flags
    # --- 判別模型
    jd = {}
    for dom in ("football", "companies", "all"):
        rr = [r for r in rows if dom == "all" or r["dom"] == dom]
        bys = collections.defaultdict(list)
        for r in rr:
            bys[r["set"]].append(r)
        e = {"lines": len(rr)}
        # AUC（正類＝錯行）；cscore＝1−同意份數/5（連續的一致度分數）
        sc = {"judge_unsupported(1-p)": lambda r: 1 - r["p"], "consensus_support_score(1-support/5)": lambda r: 1 - r["support"] / 5,
              "consensus_flag(binary,事後)": lambda r: float(r["cons"]), "record_flag(binary)": lambda r: float(r["rec"])}
        e["auc"] = {k: dict(zip(("auc", "ci95"), auc_boot(bys, f))) for k, f in sc.items()}
        # 排序平均：各分數在該領域全體上的中位名次（同分平均）正規化到 0–1 後平均；名次只算一次，bootstrap 重抽組
        def rank_map(f):
            vs = sorted(f(r) for r in rr); rk = {}; i = 0; n = len(vs)
            while i < n:
                j = i
                while j < n and vs[j] == vs[i]:
                    j += 1
                rk[vs[i]] = ((i + j + 1) / 2) / n; i = j
            return rk
        rj = rank_map(sc["judge_unsupported(1-p)"]); rc = rank_map(sc["consensus_support_score(1-support/5)"])
        comb = lambda r: (rj[1 - r["p"]] + rc[1 - r["support"] / 5]) / 2
        e["auc"]["rank_average(judge, consensus_support_score)"] = dict(zip(("auc", "ci95"), auc_boot(bys, comb)))
        e["auc_note"] = "排序平均＝兩個分數各自在本領域全體上的（同分平均）名次比例，取平均；名次在全資料上算一次，bootstrap 只重抽組（名次不重算）"
        th = {}
        for t in (0.1, 0.3, 0.5, 0.7, 0.9):
            th[f"p<{t}"] = flag_stats(rr, lambda r, t=t: r["p"] < t)
        e["judge_thresholds"] = th
        e["POST_HOC_combinations"] = {
            "consensus OR judge p<0.5（事後：門檻與組合都看過資料才選）": flag_stats(rr, lambda r: r["cons"] or r["p"] < 0.5),
            "record OR judge p<0.5（事後）": flag_stats(rr, lambda r: r["rec"] or r["p"] < 0.5),
            "consensus OR judge p<0.3（事後，只為看門檻敏感度）": flag_stats(rr, lambda r: r["cons"] or r["p"] < 0.3),
            "consensus OR judge p<0.7（事後，只為看門檻敏感度）": flag_stats(rr, lambda r: r["cons"] or r["p"] < 0.7),
        }
        hi = [r for r in rr if r["p"] >= 0.9]; lo = [r for r in rr if r["p"] < 0.1]
        e["p>=0.9"] = {"n": len(hi), "correct_rate": round(sum(not r["wrong"] for r in hi) / len(hi), 4) if hi else None}
        e["p<0.1"] = {"n": len(lo), "correct_rate": round(sum(not r["wrong"] for r in lo) / len(lo), 4) if lo else None}
        bins = collections.defaultdict(lambda: [0, 0, 0.0])
        for r in rr:
            b = min(9, int(r["p"] * 10)); bins[b][0] += 1; bins[b][1] += (not r["wrong"]); bins[b][2] += r["p"]
        e["calibration"] = {f"{b/10:.1f}-{(b+1)/10:.1f}": {"n": v[0], "mean_p": round(v[2] / v[0], 3), "correct_rate": round(v[1] / v[0], 3)} for b, v in sorted(bins.items())}
        jd[dom] = e
    out["judge"] = jd
    # --- 與執行方 judge_analysis.json 逐項比對
    cmpx = []
    def cmp_(name, mine, theirs):
        cmpx.append({"item": name, "recomputed": mine, "reported": theirs, "match": mine == theirs})
    for dom in ("football", "companies", "all"):
        R = JA["by_domain"][dom]; m = jd[dom]
        cmp_(f"{dom} auc_judge", m["auc"]["judge_unsupported(1-p)"]["auc"], R["auc_judge_unsupported"])
        for t in th:
            for k in ("flagged_share", "err_in", "err_out", "recall"):
                cmp_(f"{dom} judge {t} {k}", m["judge_thresholds"][t][k], R["judge"][t][k])
        for k in ("flagged_share", "err_in", "err_out", "recall"):
            cmp_(f"{dom} record {k}", flags[dom]["record"][k], R["record_flag"][k])
            cmp_(f"{dom} consensus {k}", flags[dom]["consensus（事後定義：≠多數值或同意份數≤1）"][k], R["consensus_flag"][k])
            cmp_(f"{dom} OR {k}", m["POST_HOC_combinations"]["consensus OR judge p<0.5（事後：門檻與組合都看過資料才選）"][k], R["consensus_OR_judge_p<0.5"][k])
        for b, v in R["calibration_p_supported_vs_correct"].items():
            cmp_(f"{dom} calib {b}", m["calibration"][b], v)
    out["judge_vs_reported"] = {"items": len(cmpx), "mismatch": [c for c in cmpx if not c["match"]]}
    return out


# ---------- 第三部分：錯行分類（judge_v2v3_20261128）與公司組量具修正後的訊號 ----------
EQUIV = ("U-等值", "K-等值")
_AGE = re.compile(r";?\s*\d+\s+years?\s+ago", re.I)


def _canon(v):
    """獨立重寫的 canon_strict（expT_feedback.canon_strict 的行為：只留數字記號，去千分位與尾端 .0，其餘文字全部忽略）。"""
    if v is None:
        return None
    t = [("v" + x[1:].lstrip("v")) if x.lower().startswith("v") else x.replace(",", "")
         for x in re.findall(r"v?\d+(?:\.\d+){2,}|\d[\d,]*(?:\.\d+)?", v.strip().strip("`*").strip())]
    t = [x[:-2] if x.endswith(".0") else x for x in t]
    return "|".join(t) if t else None


def _age_equiv(val, ans):
    return bool(_AGE.search(ans)) and _canon(val) is not None and _canon(val) == _canon(_AGE.sub("", ans))


def stat_boot(by_set, fn):
    sets = sorted(by_set); rng = random.Random(SEED); vs = []
    for _ in range(NB):
        smp = []
        for _ in sets:
            smp += by_set[sets[rng.randrange(len(sets))]]
        v = fn(smp)
        if v is not None:
            vs.append(v)
    vs.sort()
    return [round(vs[int(0.025 * len(vs))], 4), round(vs[int(0.975 * len(vs)) - 1], 4)]


def part3(root, rows):
    d = root / AUD / "judge_v2v3_20261128"
    E = [json.loads(l) for l in (d / "err_taxonomy_lines.jsonl").read_text().splitlines()]
    S_ = json.loads((d / "err_taxonomy_summary.json").read_text())["by_domain"]
    out = {"note": "事後探索；分類規則 PLAN.md（1cfc8efd0）先於結果（1e4a110a2）提交；答案鍵與頁面不在 git，無法重新分類，只能核對分類結果的計數與下游訊號"}
    byk = {r["key"]: r for r in rows}
    miss = [e["key"] for e in E if e["key"] not in byk]
    bad = [e["key"] for e in E if e["key"] in byk and (not byk[e["key"]]["wrong"] or byk[e["key"]]["set"] != e["set"] or abs(byk[e["key"]]["p"] - e["p_v1"]) > 1e-12)]
    wrong_all = {dom: sum(1 for r in rows if r["dom"] == dom and r["wrong"]) for dom in ("companies", "football")}
    out["join_check"] = {"err_lines": len(E), "keys_missing_in_judge_rows": len(miss), "wrong_or_set_or_p_mismatch": len(bad),
                         "wrong_lines_from_hmac_rows": wrong_all, "wrong_lines_in_taxonomy": dict(collections.Counter(e["domain"] for e in E))}
    # 計數重算與 summary 比對
    mine = {}
    for dom in ("companies", "football"):
        ee = [e for e in E if e["domain"] == dom]; cnt = collections.Counter(e["class"] for e in ee)
        pv = {c: {"n": len([e for e in ee if e["class"] == c]), "mean_p": round(statistics.mean(e["p_v1"] for e in ee if e["class"] == c), 3),
                  "p>=0.9": sum(e["p_v1"] >= 0.9 for e in ee if e["class"] == c), "p<0.5": sum(e["p_v1"] < 0.5 for e in ee if e["class"] == c)} for c in cnt}
        er = collections.Counter(e["equiv_rule"] for e in ee if e["equiv_rule"])
        mine[dom] = {"wrong_lines": len(ee), "by_class": dict(cnt), "v1_prob_by_class": pv, "equiv_rules": dict(er),
                     "equiv_rule_by_class": {f"{c}|{e['equiv_rule']}": 0 for c in cnt for e in ee if e["equiv_rule"]}}
        mine[dom]["equiv_rule_by_class"] = dict(collections.Counter(f"{e['class']}|{e['equiv_rule']}" for e in ee if e["equiv_rule"]))
        R = S_[dom]
        mine[dom]["matches_summary"] = (R["wrong_lines"] == len(ee) and R["by_class"] == dict(cnt) and R["equiv_rules"] == dict(er)
                                        and all(R["v1_prob_by_class"][c] == pv[c] for c in pv))
    out["recomputed"] = mine
    c = mine["companies"]; nq = c["by_class"].get("U-等值", 0) + c["by_class"].get("K-等值", 0)
    unp = c["by_class"].get("U-等值", 0) + c["by_class"].get("U", 0)
    nfill_c = sum(1 for r in rows if r["dom"] == "companies")
    out["headline"] = {"wrong_companies": c["wrong_lines"], "equiv_lines": nq, "equiv_share": round(nq / c["wrong_lines"], 4),
                       "unparsed_lines": unp, "unparsed_equiv": c["by_class"].get("U-等值", 0), "parsed_equiv": c["by_class"].get("K-等值", 0),
                       "parsed_equiv_age": c["equiv_rule_by_class"].get("K-等值|age", 0), "age_total": c["equiv_rules"].get("age", 0),
                       "remaining_wrong": c["wrong_lines"] - nq, "denominator_excluding_equiv": nfill_c - nq,
                       "remaining_error_excluding": round((c["wrong_lines"] - nq) / (nfill_c - nq), 4),
                       "remaining_error_if_relabelled_correct": round((c["wrong_lines"] - nq) / nfill_c, 4)}
    # 第二正規化器邊界（合成案例，不是資料裡的值）
    cases = [   # (說明, 值, 答案, 語意上真的相同嗎)
        ("值＝完整日期、答案＝同日期＋N years ago", "April 4, 1976", "April 4, 1976; 49 years ago", True),
        ("值＝只寫年份", "1976", "April 4, 1976; 49 years ago", False),
        ("值＝錯的日", "April 5, 1976", "April 4, 1976; 49 years ago", False),
        ("值＝錯的年", "April 4, 1977", "April 4, 1976; 49 years ago", False),
        ("值＝錯的月名、日年相同", "May 4, 1976", "April 4, 1976; 49 years ago", False),
        ("值＝日年相同、他語月名（語意相同）", "4 avril 1976", "April 4, 1976; 49 years ago", True),
        ("值＝只寫年份＋年齡括號", "1976 (49 years ago)", "April 4, 1976; 49 years ago", False),
        ("答案沒有 years ago（規則不啟動）", "May 4, 1976", "April 4, 1976", False),
    ]
    out["age_rule_boundary_synthetic"] = [{"case": a_, "rule_says_equal": _age_equiv(v_, ans_), "semantically_equal": exp,
                                           "misjudge": _age_equiv(v_, ans_) != exp} for a_, v_, ans_, exp in cases]
    out["age_rule_note"] = "canon_strict 只留數字記號、忽略所有文字；年齡規則等於『日與年的數字都相同』，月名寫錯也判相等；值是否在頁上由別的欄位（判別 p、頁面比對）另證，不由這條規則證"
    out["ticker_rule_note"] = "代號規則：值抽出的（交易所, 代號）非空且為答案抽出集合的子集；值只寫答案兩個上市地中的一個也算相等（可能偏寬）；只寫代號不寫交易所抽不出對，不算（留在 U）；代號大小寫不分交易所、代號轉大寫。無法在這裡重跑（答案鍵不在 git）"
    # 修正後的訊號（公司組）
    eq_keys = {e["key"] for e in E if e["class"] in EQUIV}
    part_keys = {e["key"] for e in E if e["class"] == "R-部分"}
    cls_of = {e["key"]: e["class"] for e in E}
    sig = {}
    for dom in ("companies", "football"):
        rr0 = [r for r in rows if r["dom"] == dom]
        versions = {"原樣（量具等值算錯）": [dict(r) for r in rr0],
                    "排除量具等值": [dict(r) for r in rr0 if r["key"] not in eq_keys],
                    "量具等值改標為對": [dict(r, wrong=(r["wrong"] and r["key"] not in eq_keys)) for r in rr0],
                    "排除量具等值＋R-部分": [dict(r) for r in rr0 if r["key"] not in eq_keys and r["key"] not in part_keys]}
        dsig = {}
        for vn, rr in versions.items():
            bys = collections.defaultdict(list)
            for r in rr:
                bys[r["set"]].append(r)
            e = {"lines": len(rr), "wrong": sum(r["wrong"] for r in rr), "error_rate": round(sum(r["wrong"] for r in rr) / len(rr), 4)}
            scs = {"judge(1-p)": lambda r: 1 - r["p"], "consensus_support_score(1-support/5)": lambda r: 1 - r["support"] / 5,
                   "consensus_flag(binary)": lambda r: float(r["cons"]), "record_flag(binary)": lambda r: float(r["rec"])}
            e["auc"] = {k: dict(zip(("auc", "ci95"), auc_boot(bys, f))) for k, f in scs.items()}
            def inout(flagf):
                def fn(smp):
                    f_ = [r for r in smp if flagf(r)]; n_ = [r for r in smp if not flagf(r)]
                    if not f_ or not n_:
                        return None
                    return sum(r["wrong"] for r in f_) / len(f_) - sum(r["wrong"] for r in n_) / len(n_)
                return fn
            for nm, ff_ in (("record_flag", lambda r: r["rec"]), ("consensus_flag", lambda r: r["cons"])):
                st = flag_stats(rr, ff_)
                st["err_in_minus_out"] = round(st["err_in"] - st["err_out"], 4)
                st["err_in_minus_out_ci95"] = stat_boot(bys, inout(ff_))
                e[nm] = st
            dsig[vn] = e
        sig[dom] = dsig
    out["signals_after_correction"] = sig
    return out


# ---------- 第四部分：重評敏感度（regrade）重算 ----------
def boot_q(vals, n=2000, seed=20261127):
    """與 ops/d2/expTc_confirm_analysis.boot 同一演算法（種子 20261127、百分位索引規則）；重寫、未 import。"""
    rng = random.Random(seed); k = len(vals); ms = []
    for _ in range(n):
        ms.append(sum(vals[rng.randrange(k)] for _ in range(k)) / k)
    ms.sort()
    q = lambda p: round(ms[min(n - 1, max(0, int(p * n) - (1 if p > 0.5 else 0)))], 4)
    return [q(0.025), q(0.975)]


def perm_q(vals, n=10000, seed=20261130):
    rng = random.Random(seed); obs = abs(sum(vals) / len(vals)); hit = 0
    for _ in range(n):
        if abs(sum(v if rng.random() < 0.5 else -v for v in vals) / len(vals)) >= obs - 1e-12:
            hit += 1
    return round((hit + 1) / (n + 1), 5)


def holm_q(ps):
    items = sorted((p, k) for k, p in ps.items() if p is not None); m = len(items); out = {}; run = 0.0
    for i, (p, k) in enumerate(items):
        run = max(run, min(1.0, (m - i) * p)); out[k] = round(run, 5)
    return out


def summ4(by):
    vals = [sum(by[s]) / len(by[s]) for s in sorted(by)]
    return {"diff": round(sum(vals) / len(vals), 4), "ci95": boot_q(vals), "perm_p": perm_q(vals), "sets": len(vals)}


def hyper_upper(N, n, alpha=0.05):
    """抽 n 個（不放回）全部合格時，母體 N 中不合格數 M 的 95% 上界：最大的 M 使 P(0 不合格)≥alpha。"""
    best = 0
    for M in range(N + 1):
        pr = 1.0
        for i in range(n):
            pr *= max(0, (N - M - i)) / (N - i)
        if pr >= alpha:
            best = M
    return best


def part4(root, rows):
    d = root / AUD / "judge_v2v3_20261128"; o_dir = root / AUD / "expTc_20261128"
    ld = lambda p: json.loads(p.read_text())
    ver = {"original": (ld(o_dir / "expTc_confirm_analysis_20261128_v4_b61.json"), o_dir / "efamily", ld(o_dir / "expTc_escalation_analysis_20261128.json")),
           "regraded": (ld(d / "regrade/expTc_confirm_analysis_regrade_b61.json"), d / "regrade/efamily_regrade", ld(d / "regrade/expTc_escalation_regrade.json"))}
    RS = ld(d / "regrade_sensitivity.json")
    out = {"note": "重評＝strict_status 換寬鬆版（原判對照舊；原判錯但合第二正規化器者改判對），其餘參數不變。這裡用各 json 內的逐格資料與 efamily 逐份資料獨立重算（演算法同 ops/d2 的 boot／perm／holm，種子 20261127／20261130）。"}
    res = {}; cmpl = []
    def cmp_(name, mine, theirs):
        cmpl.append({"item": name, "recomputed": mine, "reported": theirs, "match": mine == theirs})
    for vn, (c, ef, e) in ver.items():
        cells = c["per_pair_arm_cells"]
        def fb(a, b, pre=""):
            by = collections.defaultdict(list)
            for k, x in cells.items():
                s, r, arm = k.split("/")
                if arm != a or not s.startswith(pre) or x.get("infra_void"):
                    continue
                y = cells.get(f"{s}/{r}/{b}")
                if y is None or y.get("infra_void"):
                    continue
                by[s].append(x["correct_prop_after"] - y["correct_prop_after"])
            return summ4(by)
        rows_ = [json.loads(l) for l in (ef / "efamily_per_draft_arm.jsonl").read_text().splitlines()]
        dd = {(r["set"], r["rep"], r["arm"]): r["correct"] / r["n_claims"] for r in rows_}
        has_f = {(r["set"], r["rep"]): r.get("sent_filled", 0) > 0 for r in rows_ if r["arm"] == "ER"}
        def ee(a, b, pre="", need_filled=False):
            by = collections.defaultdict(list)
            for (s, rp, arm), v in dd.items():
                if arm == a and s.startswith(pre) and (s, rp, b) in dd and (not need_filled or has_f[(s, rp)]):
                    by[s].append(v - dd[(s, rp, b)])
            return summ4(by)
        pd_ = c["selector"]["all"]["per_draft"]; byset = collections.defaultdict(list)
        for p_ in pd_:
            byset[p_["set"]].append(p_)
        rr = {"record_random": {}, "record_nonblank": {}}
        for s_, ds in byset.items():
            prop = lambda x: x["correct_prop"]
            rec = max(ds, key=lambda x: (int(x["evidence_score"]), -int(x["blank_count"]), -int(x["rep"])))
            nb = max(ds, key=lambda x: (int(x["n_claims"]) - int(x["blank_count"]), -int(x["rep"])))
            rr["record_random"][s_] = [prop(rec) - statistics.mean(prop(x) for x in ds)]
            rr["record_nonblank"][s_] = [prop(rec) - prop(nb)]
        r_ = {"feedback": {f"{a}_vs_{b}": fb(a, b) for a, b in (("T", "TB"), ("T", "G"), ("TB", "G"), ("G", "A"), ("T", "A"), ("TB", "A"))},
              "selector": {"record_vs_random": summ4(rr["record_random"]), "record_vs_nonblank": summ4(rr["record_nonblank"])},
              "E": {"ER_vs_A": ee("ER", "A"), "ER_vs_EN": ee("ER", "EN", need_filled=True), "ER_vs_EB": ee("ER", "EB")},
              "companies": {"T_vs_TB": fb("T", "TB", "cc"), "T_vs_G": fb("T", "G", "cc"), "ER_vs_A": ee("ER", "A", "cc"),
                            "ER_vs_EN": ee("ER", "EN", "cc", True), "ER_vs_EB": ee("ER", "EB", "cc")}}
        r_["holm_confirm"] = holm_q({"record_vs_random": r_["selector"]["record_vs_random"]["perm_p"], "record_vs_nonblank": r_["selector"]["record_vs_nonblank"]["perm_p"],
                                     "T_vs_TB": r_["feedback"]["T_vs_TB"]["perm_p"], "T_vs_G": r_["feedback"]["T_vs_G"]["perm_p"]})
        r_["holm_E"] = holm_q({k: v["perm_p"] for k, v in r_["E"].items()})
        # 各臂正確率（組加權）
        am = {}
        for arm in ("A", "G", "T", "TB"):
            by = collections.defaultdict(list)
            for k, x in cells.items():
                s, r, a = k.split("/")
                if a == arm and not x.get("infra_void"):
                    by[s].append(x["correct_prop_after"])
            am[f"feedback_{arm}"] = round(statistics.mean(statistics.mean(v) for v in by.values()), 4)
        for arm, nm in (("A", "drafts_c0"), ("EB", "E_EB"), ("ER", "E_ER"), ("EN", "E_EN")):
            by = collections.defaultdict(list)
            for (s, rp, a), v in dd.items():
                if a == arm:
                    by[s].append(v)
            am[nm] = round(statistics.mean(statistics.mean(v) for v in by.values()), 4)
        hp = [json.loads(l) for l in (ef / "efamily_hp_per_set.jsonl").read_text().splitlines()]
        am["E_HP"] = round(statistics.mean(h["correct"] / h["n_claims"] for h in hp), 4)
        r_["arm_correct_setweighted_all"] = am
        res[vn] = r_
        # 與 json 內報告值比對（原樣與重評各比自己那份）
        for k_, v_ in r_["feedback"].items():
            if k_ in c["feedback"]["all"]:
                for f_ in ("diff", "ci95", "perm_p"):
                    cmp_(f"{vn} feedback {k_} {f_}", v_[f_], c["feedback"]["all"][k_][f_])
        for k_ in ("record_vs_random", "record_vs_nonblank"):
            for f_ in ("diff", "ci95", "perm_p"):
                cmp_(f"{vn} selector {k_} {f_}", r_["selector"][k_][f_], c["selector"]["all"][k_][f_])
        for k_ in r_["E"]:
            for f_ in ("diff", "ci95", "perm_p"):
                cmp_(f"{vn} E {k_} {f_}", r_["E"][k_][f_], e["main"][k_][f_])
        for k_ in ("T_vs_TB", "T_vs_G"):
            for f_ in ("diff", "ci95", "perm_p"):
                cmp_(f"{vn} companies {k_} {f_}", r_["companies"][k_][f_], c["b35_feedback_by_domain"]["companies"]["all"][k_][f_])
        for k_ in ("ER_vs_A", "ER_vs_EN", "ER_vs_EB"):
            for f_ in ("diff", "ci95", "perm_p"):
                cmp_(f"{vn} E companies {k_} {f_}", r_["companies"][k_][f_], e["strata_B35"]["company"][k_][f_])
        for k_, v_ in r_["holm_confirm"].items():
            cmp_(f"{vn} holm confirm {k_}", v_, c["holm"][k_])
        for k_, v_ in r_["holm_E"].items():
            cmp_(f"{vn} holm E {k_}", v_, e["holm_family2"][k_])
    out["recomputed"] = res
    arm_rep = {}
    for k_, v_ in res["original"]["arm_correct_setweighted_all"].items():
        key = {"feedback_A": "feedback_A|all", "feedback_G": "feedback_G|all", "feedback_T": "feedback_T|all", "feedback_TB": "feedback_TB|all", "drafts_c0": "drafts_c0|all",
               "E_EB": "E_EB|all", "E_ER": "E_ER|all", "E_EN": "E_EN|all", "E_HP": "E_HP|all"}[k_]
        for vn, rv in (("original", "original"), ("regraded", "regraded")):
            cmp_(f"arm {k_} {vn}", res[vn]["arm_correct_setweighted_all"][k_], RS["arm_correct_prop_setweighted"][rv][key])
    # 重評前後的差：逐份 filled_correct 變化（公司／足球）與步驟 0 的等值行（以 (set,rep) 對）比對 ⇒ 寬鬆版 vs 看欄名版
    po = {(p["set"], p["rep"]): p for p in ver["original"][0]["selector"]["all"]["per_draft"]}
    pr = {(p["set"], p["rep"]): p for p in ver["regraded"][0]["selector"]["all"]["per_draft"]}
    E_ = [json.loads(l) for l in (d / "err_taxonomy_lines.jsonl").read_text().splitlines()]
    byk = {r["key"]: r for r in rows}
    lab = collections.Counter((byk[e["key"]]["set"], byk[e["key"]]["rep"]) for e in E_ if e["class"] in EQUIV)
    delta = {k: pr[k]["filled_correct"] - po[k]["filled_correct"] for k in po}
    diffs = [k for k in po if delta[k] != lab.get(k, 0)]
    other = [k for k in po if (pr[k]["n_claims"], pr[k]["blank_count"], pr[k]["evidence_score"]) != (po[k]["n_claims"], po[k]["blank_count"], po[k]["evidence_score"])]
    ef_o = {(r["set"], r["rep"]): r["correct"] for r in (json.loads(l) for l in (ver["original"][1] / "efamily_per_draft_arm.jsonl").read_text().splitlines()) if r["arm"] == "A"}
    ef_r = {(r["set"], r["rep"]): r["correct"] for r in (json.loads(l) for l in (ver["regraded"][1] / "efamily_per_draft_arm.jsonl").read_text().splitlines()) if r["arm"] == "A"}
    out["lenient_vs_label_version"] = {
        "total_flipped_by_regrade_in_150_drafts": sum(delta.values()), "total_label_version_equiv_lines": sum(lab.values()),
        "by_domain_regrade": {dm: sum(v for (s, _), v in delta.items() if s.startswith(p)) for dm, p in (("companies", "cc"), ("football", "ff"))},
        "drafts_where_counts_differ": len(diffs), "drafts": 150,
        "evidence_score_blank_count_n_claims_changed_drafts": len(other),
        "efamily_A_arm_flip_equals_selector_flip": all(ef_r[k] - ef_o[k] == delta[(k[0], int(k[1][1:]))] for k in ef_o),
        "note": "只能在『每份草稿翻轉行數』層級比對（逐行比對要答案鍵）；150 份全部相同、總數相同，但不排除同一份內一行對調"}
    # 有無被改判卻判決變動的欄位：T_harm_not_more_than_G 等非 verdict 欄位
    o0, r0 = ver["original"][0], ver["regraded"][0]
    out["non_verdict_field_changes"] = {"T_harm_not_more_than_G": [o0["T_harm_not_more_than_G"], r0["T_harm_not_more_than_G"]],
                                        "verdict_equal": o0["verdict"] == r0["verdict"] and ver["original"][2]["verdict"] == ver["regraded"][2]["verdict"],
                                        "qualifiers_equal": o0["qualifiers"] == r0["qualifiers"]}
    ident = {k: o0[k] == r0[k] for k in ("schema", "infra_rule", "fb_plan_sha256", "pairs_total", "pairs_valid", "void_pairs_infra", "start_check_failed",
                                          "misaligned_G_T", "blank_draft_pairs", "heuristic_success_pairs_descriptive", "suspicious_flag_pairs")}
    ident["drafts_runs"] = o0["drafts_runs"] == r0["drafts_runs"]
    ident["per_arm_cells_count_tokens_wall_equal"] = all(o0["per_arm"][a][f] == r0["per_arm"][a][f] for a in o0["per_arm"] for f in ("cells", "rounds_mean", "tokens_mean", "wall_mean", "future_truth_lines"))
    out["identity_fields_equal"] = ident
    # 答案鍵附帶文字（其他批次）
    B = ld(d / "answer_key_artifacts_other_batches.json")["batches"]
    tot = {k: sum(g["lines"] for g in v.get("affected_by_group", {}).values()) for k, v in B.items()}
    cA = collections.Counter(); 
    for k in ("exp1_cA_1003", "exp1_cA_1004"):
        for g in B[k]["affected_by_group"].values():
            for f, n in g["fields"].items():
                cA[f] += n
    sc = collections.Counter(B["exploratory_expT"]["affected_by_group"]["sc"]["fields"])
    out["answer_key_artifacts"] = {"affected_lines_by_batch": tot, "lines_total_cA": sum(sum(g.values()) if False else 0 for g in []) or sum(v for k in ("exp1_cA_1003", "exp1_cA_1004") for v in B[k]["lines_by_group"].values()),
                                   "sc_lines": B["exploratory_expT"]["lines_by_group"]["sc"], "sc_affected": tot["exploratory_expT"],
                                   "cA_fields_equal_sc_fields": dict(cA) == dict(sc), "cA_affected": tot["exp1_cA_1003"] + tot["exp1_cA_1004"],
                                   "cB_affected": tot["exp1_cB_1003"] + tot["exp1_cB_1004"], "d2prime_r5real_affected": tot["d2prime_r5real_1003"] + tot["d2prime_r5real_1004"]}
    # 抽查：樣本是否照種子重現、組成、上界
    A_ = ld(d / "equiv_audit.json"); cl = {e["key"]: e["class"] for e in E_}
    rng = random.Random(SEED); reproduced = {}
    for cls in sorted({e["class"] for e in E_}):
        grp = [e for e in E_ if e["class"] == cls]; rng.shuffle(grp)
        if cls in EQUIV:
            reproduced[cls] = [e["key"] for e in grp[:20]] == A_["equiv_audit_sample"][cls]["keys"]
    n_k, n_u = sum(1 for e in E_ if e["class"] == "K-等值"), sum(1 for e in E_ if e["class"] == "U-等值")
    out["equiv_audit"] = {"sample_reproduced_by_seed_20261128": reproduced,
                          "sample_keys_in_class": {c: all(cl.get(k) == c for k in A_["equiv_audit_sample"][c]["keys"]) for c in EQUIV},
                          "checked_agree": {c: [A_["equiv_audit_sample"][c]["n_checked"], A_["equiv_audit_sample"][c]["agree"]] for c in EQUIV},
                          "population": {"K-等值": n_k, "U-等值": n_u},
                          "upper_bound_95_disagreeing_lines_hypergeometric": {"K-等值": hyper_upper(n_k, 20), "U-等值": hyper_upper(n_u, 20), "both(40 of 184)": hyper_upper(n_k + n_u, 40)},
                          "U_not_equivalent_lines": [{"class_in_taxonomy": cl.get(x["key"]), "field": x["field"], "reason": x["reason"]} for x in A_["U_not_equivalent_companies"]],
                          "note": "『一致』的判準（語意相同）沒有寫在 git；月名不同、只寫一個上市地各有幾行：資料裡沒有值，無法直接數，只能給抽樣上界。5 條真不合格都在 U（不在等值集合）"}
    out["vs_reported"] = {"items": len(cmpl), "mismatch": [c for c in cmpl if not c["match"]]}
    # 公司組旗標（重評）：比對 flags_regrade.json
    FR = ld(d / "flags_regrade.json")["by_domain"]
    fm = []
    rc = [dict(r) for r in rows if r["dom"] == "companies"]
    for r in rc:
        r["wrong2"] = r["wrong"] and cl.get(r["key"]) not in EQUIV
    q4 = lambda x: None if x is None else round(x, 4)
    def st2(f):
        ff = [r for r in rc if f(r)]; nf = [r for r in rc if not f(r)]; w = sum(r["wrong2"] for r in rc)
        return {"flagged_share": q4(len(ff) / len(rc)), "err_in": q4(sum(r["wrong2"] for r in ff) / len(ff)), "err_out": q4(sum(r["wrong2"] for r in nf) / len(nf)),
                "recall": q4(sum(r["wrong2"] for r in ff) / w), "n_flagged": len(ff)}
    mine = {"record_flag": st2(lambda r: r["rec"]), "consensus_flag": st2(lambda r: r["cons"]), "judge_v1_p<0.5": st2(lambda r: r["p"] < 0.5)}
    for k_, v_ in mine.items():
        fm.append({"item": k_, "recomputed": v_, "reported": FR["companies|regraded"][k_], "match": v_ == FR["companies|regraded"][k_]})
    for k_, f_, rk in (("auc_judge_v1", lambda r: 1 - r["p"], "judge"), ("auc_record_flag", lambda r: float(r["rec"]), "rec"), ("auc_consensus_flag", lambda r: float(r["cons"]), "cons")):
        v_ = round(midrank_auc([(f_(r), int(r["wrong2"])) for r in rc]), 4)
        fm.append({"item": k_, "recomputed": v_, "reported": FR["companies|regraded"][k_], "match": v_ == FR["companies|regraded"][k_]})
    out["company_flags_regraded_vs_reported"] = fm
    return out


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("root"); ap.add_argument("--out", required=True); a = ap.parse_args()
    per_draft, pools, rep = load(a.root)
    res = {"note": "只用已提交資料；逐行多數決／逐行 oracle／一致度旗標無法由提交資料重算（見 not_recomputable）。",
           "seed": SEED, "bootstrap": f"組群集，{NB} 次，percentile [int(.025*B), int(.975*B)-1]", "recomputed": {}, "vs_reported": []}
    cmpl = lambda name, mine, theirs: res["vs_reported"].append(
        {"item": name, "recomputed": mine, "reported": theirs, "match": (mine == theirs), "diff": None if mine is None or theirs is None or isinstance(mine, list) else round(mine - theirs, 4)})
    for K in (5, 3):
        per = selectors(per_draft, K)
        means = {m: round(statistics.mean(v[m] for v in per.values()), 4) for m in ("A", "record", "nonblank", "oracle")}
        dom = {d: {m: round(statistics.mean(v[m] for s, v in per.items() if s.startswith(p)), 4) for m in means}
               for d, p in (("companies", "cc"), ("football", "ff"))}
        cm = {f"{x}_vs_{y}": pairs(per, x, y) for x, y in (("record", "A"), ("nonblank", "A"), ("record", "nonblank"), ("oracle", "record"))}
        res["recomputed"][f"k{K}"] = {"sets": len(per), "means": means, "by_domain": dom, "comparisons": cm}
        R = rep["k"][str(K)]
        for m in means:
            cmpl(f"k{K} mean {m}", means[m], R["means"]["A" if m == "A" else m])
        for d in dom:
            for m in means:
                cmpl(f"k{K} {d} {m}", dom[d][m], R["by_domain_means"][d][m])
    # 與 v4 selector 區塊的 record_vs_random／record_vs_nonblank（他們的選擇器分析，bootstrap 實作可能不同）
    # 一致度數字內部一致性：由報告的比例反推整數計數，檢查是否存在同時吻合的整數解
    res["flag_internal_consistency"] = {}
    fl = rep["flags_k5_filled_lines"]
    pd_dom = {"companies": "cc", "football": "ff", "all": ""}
    for d, p in pd_dom.items():
        filled = sum(x["filled"] for x in per_draft if x["set"].startswith(p))
        wrong = filled - sum(x["filled_correct"] for x in per_draft if x["set"].startswith(p))
        f = fl[d]
        ent = {"filled_from_per_draft": filled, "filled_reported": f["filled_lines"], "filled_match": filled == f["filled_lines"],
               "error_rate_from_per_draft": round(wrong / filled, 4), "error_rate_reported": f["error_rate"],
               "error_rate_match": round(wrong / filled, 4) == f["error_rate"],
               "filled_diff": filled - f["filled_lines"],
               "wrong_from_per_draft": wrong, "wrong_implied_by_reported": round(f["error_rate"] * f["filled_lines"]),
               "wrong_diff": wrong - round(f["error_rate"] * f["filled_lines"]),
               "diff_all_wrong_lines": (filled - f["filled_lines"]) == (wrong - round(f["error_rate"] * f["filled_lines"]))}
        for kind in ("consensus", "record"):
            g = f[kind]
            s = int_solutions(f["filled_lines"], f["error_rate"], g["flagged_share"], g["err_in"], g["err_out"], g["recall"])
            ent[kind] = {"integer_solutions(W,F,FW)": s, "coherent": len(s) >= 1}
        res["flag_internal_consistency"][d] = ent
    # 交叉比對：E 家族定義的紀錄旗標（er_flagged_filled），不同於 flags_v2 定義，數字預期接近但不相同
    ef = {}
    for d, p in pd_dom.items():
        q = [x for x in pools if x["set"].startswith(p)]
        F = sum(x["er_flagged_filled"] for x in q); FW = sum(x["er_flagged_filled_wrong"] for x in q)
        U = sum(x["unflagged_filled"] for x in q); UW = sum(x["unflagged_filled_wrong"] for x in q)
        ef[d] = {"filled": F + U, "err_in": round(FW / F, 4), "err_out": round(UW / U, 4), "recall": round(FW / (FW + UW), 4),
                 "flagged_share": round(F / (F + U), 4)}
    res["efamily_record_flag_crosscheck"] = ef
    res["not_recomputable_superseded_by_r1_r5_lines"] = {
        "reason": "逐行多數決、逐行 oracle、一致度旗標都要每組每行 5 份初稿的（canon_strict）值或 HMAC；git 裡只有 r1、r2 的逐行 HMAC（expT_lines_hmac.jsonl，且 before_matches_k 比的是教材修訂，不是初稿之間），"
                  "r3–r5 只有每份的彙總（filled、filled_correct、evidence_score、旗標池計數）。初稿根目錄與 flags_v2.json 不在 git。",
        "items": ["majority", "line_oracle", "majority_vs_*", "consensus flag err_in/err_out/recall", "flag overlap", "tie/blank variants"]}
    ctx = {}
    res["r1_r5_lines"] = part2(pathlib.Path(a.root), per_draft, rep, ctx)
    res["judge_v2v3_taxonomy"] = part3(pathlib.Path(a.root), ctx.get("rows"))
    res["regrade_sensitivity"] = part4(pathlib.Path(a.root), ctx.get("rows"))
    out = pathlib.Path(a.out); out.mkdir(parents=True, exist_ok=True)
    (out / "consensus_recompute.json").write_text(json.dumps(res, ensure_ascii=False, indent=1))
    bad = [r for r in res["vs_reported"] if not r["match"]]
    print("recomputed items:", len(res["vs_reported"]), "mismatch:", len(bad))
    for r in bad:
        print(r)
    print(json.dumps(res["recomputed"]["k5"]["comparisons"], ensure_ascii=False))
    print(json.dumps(res["flag_internal_consistency"], ensure_ascii=False))
    print(json.dumps(ef, ensure_ascii=False))


if __name__ == "__main__":
    main()
