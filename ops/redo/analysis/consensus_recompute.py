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
import argparse, collections, json, pathlib, random, statistics

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


def part2(root, per_draft, rep):
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
        a["p"] = b["p_supported"]; a["rec_v2"] = b["record_flag"]
    out["record_flag_E_vs_flags_v2"] = {"same_set_of_lines": all(r["rec"] == r["rec_v2"] for r in rows), "n": sum(r["rec"] for r in rows)}
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
    res["r1_r5_lines"] = part2(pathlib.Path(a.root), per_draft, rep)
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
