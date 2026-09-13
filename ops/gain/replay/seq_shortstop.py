#!/usr/bin/env python3
"""round665：把 round664 的「提早停」檢查從**逐列**改成**逐邏輯呼叫序列**。

判準見 runs/_analysis_r665/CRITERION.md（先 commit 才碰資料）。

為什麼要改（碼側，brain_cline.py:117-252）：重試迴圈每個 attempt 各落一列，
只有 401/402/403 會 break。所以一個「重試到底」的失敗序列，它的中間列**必然**
滿足 round664 用的條件（`attempt < retries_max` 且非 401/402/403）——
那個檢查在機制上分不出「提早停」與「還在重試」。

逐序列的定義：分組鍵 = (agent_id, role, sha1(prompt), api)；
真提早停 = 該組最大 attempt 的那一列 ok=False 且 max_attempt < retries_max 且非提早 break。

突變體以 --mutant 指定（N1/N2/N3/N4），全部必須被抓到（CRITERION §量具雙向驗證）。
"""
import argparse, collections, hashlib, json, pathlib, sys

ERA_NON_RETRYABLE = {
    1: {400, 401, 402, 403, 404},
    2: {400, 401, 402, 403},
    3: {401, 402, 403},
}


def load(path):
    rows = []
    for ln in pathlib.Path(path).read_text().splitlines():
        ln = ln.strip()
        if ln:
            rows.append(json.loads(ln))
    return rows


def is_early_break(rec, codes):
    err = rec.get("error") or ""
    return any(f"HTTP Error {c}:" in err for c in codes)


def key_of(rec, mutant):
    h = hashlib.sha1((rec.get("prompt") or "").encode()).hexdigest()[:16]
    if mutant == "N1":                     # 拿掉 prompt ⇒ 不同邏輯呼叫會被併在一起
        return (rec.get("agent_id"), rec.get("role"), rec.get("api"))
    return (rec.get("agent_id"), rec.get("role"), h, rec.get("api"))


def analyse(calls_path, era, mutant=None, plant=False, mode="v1"):
    codes = set() if mutant == "N4" else ERA_NON_RETRYABLE[era]
    recs = load(calls_path)
    out = {"n_records": len(recs), "era": era}
    if not recs:                                        # N3：空層必須 BROKEN
        out["status"] = "BROKEN"; out["reason"] = "calls.jsonl 讀到 0 列"
        return out

    work = [r for r in recs if r.get("role") != "preflight"]

    # ---- N2 植入缺陷：刪掉某一個「有 attempt=2 的 review 失敗組」的 attempt=2 列 ----
    if plant:
        groups = collections.defaultdict(list)
        for r in work:
            if r.get("role") == "review":
                groups[key_of(r, None)].append(r)
        victim = None
        for k, rs in groups.items():
            if max(x["attempt"] for x in rs) == 2 and not any(x.get("ok") for x in rs):
                victim = k; break
        if victim is None:
            out["status"] = "BROKEN"; out["reason"] = "找不到可植入的序列"
            return out
        work = [r for r in work
                if not (key_of(r, None) == victim and r["attempt"] == 2)]
        out["planted_group"] = str(victim)

    # ---- 分組 ----
    groups = collections.defaultdict(list)
    for r in work:
        groups[key_of(r, mutant)].append(r)

    # ---- 推翻條件：同組出現重複 attempt ⇒ AMBIGUOUS（不報 0）----
    dup_groups = sum(1 for rs in groups.values()
                     if len(set(x["attempt"] for x in rs)) != len(rs))
    out["groups"] = len(groups)
    out["dup_attempt_groups"] = dup_groups

    # ---- P-R665-5 完整性：attempt>=2 必有 attempt-1 的同組前驅 ----
    orphan = 0
    for rs in groups.values():
        ats = set(x["attempt"] for x in rs)
        orphan += sum(1 for a in ats if a >= 2 and (a - 1) not in ats)
    out["orphan_attempts"] = orphan
    n_ge2 = sum(1 for r in work if r["attempt"] >= 2)
    out["records_attempt_ge2"] = n_ge2
    if n_ge2 and orphan > 0.01 * n_ge2:
        out["status"] = "BROKEN"; out["reason"] = f"孤兒 attempt {orphan}/{n_ge2} >1%"
        return out

    # ---- v2：組內照檔案順序切序列（CRITERION_v2.md）----
    # 機制：gain_run.py:298,700,896 三處明寫依序送出、無併發 ⇒ 檔案順序即真實時序，
    # 同一邏輯呼叫的 attempt 嚴格遞增；attempt 不再遞增就是新的邏輯呼叫。
    if mode == "v2":
        seqs = []
        for rs in groups.values():                 # rs 保持檔案順序（append 而來）
            cur = []
            for r in rs:
                if cur and r["attempt"] <= cur[-1]["attempt"]:
                    seqs.append(cur); cur = []
                cur.append(r)
            if cur:
                seqs.append(cur)
        # P-R665-6 自檢：每條序列必須從 attempt=1 開始且連續
        bad = sum(1 for sq in seqs
                  if [x["attempt"] for x in sq] != list(range(1, len(sq) + 1)))
        out["v2_seqs"] = len(seqs)
        out["v2_noncontiguous_seqs"] = bad
        if seqs and bad > 0.01 * len(seqs):
            out["status"] = "BROKEN"
            out["reason"] = f"v2 序列不連續 {bad}/{len(seqs)} >1%"
            return out
        units = seqs
    else:
        units = list(groups.values())

    # ---- 逐序列：review 的失敗序列與真提早停 ----
    def seq_stat(role_filter):
        fail_seq = short_seq = 0
        for rs in units:
            if not role_filter(rs[0]):
                continue
            last = max(rs, key=lambda x: x["attempt"])
            if last.get("ok"):
                continue
            fail_seq += 1
            if last["attempt"] < (last.get("retries_max") or 0) \
               and not is_early_break(last, codes):
                short_seq += 1
        return fail_seq, short_seq

    rev_fail_seq, rev_short_seq = seq_stat(lambda r: r.get("role") == "review")
    out["review_fail_seqs"] = rev_fail_seq
    out["review_true_shortstop_seqs"] = rev_short_seq
    out["review_shortstop_rate"] = (rev_short_seq / rev_fail_seq) if rev_fail_seq else None

    # ---- P-R665-1：round664 逐列標記的「提早停」有多少其實有後繼列 ----
    r664_flagged = has_succ = 0
    for rs in units:
        if rs[0].get("role") != "review":
            continue
        ats = set(x["attempt"] for x in rs)
        for r in rs:
            if r.get("ok"):
                continue
            if r["attempt"] < (r.get("retries_max") or 0) and not is_early_break(r, codes):
                r664_flagged += 1
                if (r["attempt"] + 1) in ats:
                    has_succ += 1
    out["r664_rowwise_flagged"] = r664_flagged
    out["of_which_have_successor"] = has_succ
    out["successor_rate"] = (has_succ / r664_flagged) if r664_flagged else None

    # ---- P-R665-4：逐序列數 ON 臂 review 的 void 序列 ----
    on_rev_void = 0
    for rs in units:
        if rs[0].get("role") != "review":
            continue
        if (rs[0].get("meta") or {}).get("arm") != "ON":
            continue
        last = max(rs, key=lambda x: x["attempt"])
        if last.get("ok"):
            continue
        if last["attempt"] >= (last.get("retries_max") or 0) or is_early_break(last, codes):
            on_rev_void += 1
    out["on_review_void_seqs"] = on_rev_void

    # ---- P-R665-3：review 的 retries_max 組態 ----
    out["review_retries_max_cfg"] = sorted(
        {r.get("retries_max") for r in work if r.get("role") == "review"})
    if mode == "v2":
        # 建構上組內不可能有重複 attempt（自檢：P-R665-9）
        dup_in_units = sum(1 for sq in units
                           if len(set(x["attempt"] for x in sq)) != len(sq))
        out["v2_dup_attempt_units"] = dup_in_units
        out["status"] = "BROKEN" if dup_in_units else "OK"
        if dup_in_units:
            out["reason"] = "v2 序列內仍有重複 attempt（切法錯）"
    else:
        out["status"] = "AMBIGUOUS" if dup_groups else "OK"
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", nargs="+", required=True, help="層名=run目錄=世代")
    ap.add_argument("--mutant", default=None, choices=["N1", "N2", "N3", "N4"])
    ap.add_argument("--mode", default="v1", choices=["v1", "v2"],
                    help="v1=分組鍵當序列（CRITERION.md）；v2=組內照檔案順序切序列（CRITERION_v2.md）")
    ap.add_argument("--json", default=None)
    a = ap.parse_args()
    res = {}
    for spec in a.runs:
        name, d, era = spec.split("=")
        d = pathlib.Path(d)
        calls = d / "calls.jsonl"
        if a.mutant == "N3":
            calls = d / "__empty_r665__.jsonl"
            calls.write_text("")
        try:
            res[name] = analyse(calls, int(era), a.mutant, plant=(a.mutant == "N2"), mode=a.mode)
        finally:
            if a.mutant == "N3" and calls.exists():
                calls.unlink()
    txt = json.dumps(res, indent=2, ensure_ascii=False)
    if a.json:
        pathlib.Path(a.json).write_text(txt)
    print(txt)
    return 0


if __name__ == "__main__":
    sys.exit(main())
