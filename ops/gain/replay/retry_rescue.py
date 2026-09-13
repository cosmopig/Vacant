#!/usr/bin/env python3
"""round664：估計「把 review 的 retries 從 2 加到 4」救得回多少 infra_void。

判準見 runs/_analysis_r664/CRITERION.md（先 commit 才碰資料）。

核心觀察（碼側，brain_cline.py:169,204）：每一次 attempt 各自落盤一列，
所以「條件回復率 p_k＝第 k 次嘗試成功的比例」可以直接數，**不需要把 attempt
併回邏輯呼叫**。少一個分組步驟＝少一個易碎點。

突變體以 --mutant 指定，全部必須被自檢或對帳抓到（CRITERION §量具雙向驗證）。
"""
import argparse, collections, json, pathlib, sys

# ⚠ `non_retryable` 是**會隨世代改變的實驗條件**，不能寫死成今天的值。
# `git log -L '/non_retryable = /,+4:ops/gain/brain_cline.py'` 給出三個世代：
#   era1  4b704b3 2026-08-20 10:08  {400,401,402,403,404}
#   era2  1e29749 2026-08-24 16:01  {400,401,402,403}
#   era3  cd1fbe2 2026-08-30 17:52  {401,402,403}
# 用錯世代 ⇒ 守恆恆等式的殘差會 ≠0（所以恆等式同時在驗世代指派對不對）。
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
    """不重試的 HTTP 碼 ⇒ 即使 attempt < retries_max 也是終局失敗。"""
    err = rec.get("error") or ""
    return any(f"HTTP Error {c}:" in err for c in codes)


def analyse(calls_path, summary_path, era, mutant=None):
    codes = ERA_NON_RETRYABLE[era]
    recs = load(calls_path)
    out = {"n_records": len(recs), "era": era, "non_retryable": sorted(codes)}

    # ---- P-R664-5 完整性：欄位缺漏 >1% ⇒ BROKEN（不是 PASS、不是 0%）----
    need = ("role", "attempt", "ok", "retries_max", "timeout_s")
    missing = sum(1 for r in recs if any(r.get(k) is None for k in need))
    out["missing_field_records"] = missing
    if not recs:                                    # M4：安靜的空層必須是 BROKEN
        out["status"] = "BROKEN"
        out["reason"] = "calls.jsonl 讀到 0 列"
        return out
    if missing > 0.01 * len(recs):
        out["status"] = "BROKEN"
        out["reason"] = f"必要欄位缺漏 {missing}/{len(recs)} > 1%"
        return out

    work = [r for r in recs if r.get("role") != "preflight"]

    # ---- 條件回復率 p_k：只取 retries_max>=4 的角色（gen／revise）----
    deep = [r for r in work if (r.get("retries_max") or 0) >= 4]
    if mutant == "M1":
        # 全 attempt 混在一起算 ok 比例，而非逐 k ⇒ 自檢的非遞增性質會露餡
        tot = len(deep) or 1
        ok = sum(1 for r in deep if r.get("ok"))
        p = {k: ok / tot for k in (1, 2, 3, 4)}
        reach = {k: tot for k in (1, 2, 3, 4)}
    else:
        reach = collections.Counter(r["attempt"] for r in deep)
        okc = collections.Counter(r["attempt"] for r in deep if r.get("ok"))
        p = {k: (okc[k] / reach[k]) if reach[k] else None for k in sorted(reach)}

    # 自檢（抓 M1）：**守恆恆等式**，不是單調性。
    # 走到第 k 次的列數，必須等於第 k-1 次「失敗且可重試」的列數。
    # （單調性太弱——常數序列也滿足 >=，M1 就是這樣溜過去的。）
    ks = sorted(reach)
    fail_retryable = collections.Counter(
        r["attempt"] for r in deep
        if not r.get("ok") and not is_early_break(r, codes))
    residuals = {}
    for k in ks:
        if k == 1:
            continue
        residuals[str(k)] = reach[k] - fail_retryable[k - 1]
    out["reach_by_attempt"] = {str(k): reach[k] for k in ks}
    out["p_by_attempt"] = {str(k): p[k] for k in ks}
    out["selfcheck_reach_residuals"] = residuals
    out["selfcheck_reach_conserved"] = all(v == 0 for v in residuals.values())

    # ---- void 呼叫序列：重試用盡，或 401/402/403 提早 break ----
    def is_void(r):
        if mutant == "M2":
            return not r.get("ok")          # 所有失敗列 ⇒ 與 summary 對不上
        if r.get("ok"):
            return False
        return r["attempt"] >= (r.get("retries_max") or 0) or is_early_break(r, codes)

    voids = [r for r in work if is_void(r)]
    by_role = collections.Counter(r["role"] for r in voids)
    on_voids = [r for r in voids if (r.get("meta") or {}).get("arm") == "ON"]
    on_by_role = collections.Counter(r["role"] for r in on_voids)

    role_filter = (lambda r: True) if mutant == "M3" else (lambda r: r["role"] == "review")
    review_voids = [r for r in on_voids if role_filter(r)]

    # 推翻條件：review 失敗大量停在 attempt < retries_max 且非 401/402/403
    # ⚠ round665 實測：**這兩個欄位是逐列判斷，量不到「提早停」**。
    #   重試迴圈每個 attempt 各落一列（brain_cline.py:117-252），所以一個
    #   「重試到底」的失敗序列，它的中間列必然滿足下面這個條件。
    #   round665 逐序列重算（ops/gain/replay/seq_shortstop.py --mode v2）：
    #   被這裡標到的 42/18/5/14/12/60 列 **100% 都有 attempt+1 的後繼列**，
    #   真提早停率 0/108 = 0.00%。⇒ 這兩個欄位**不可用來判推翻條件**，
    #   要判就用 seq_shortstop.py。此處保留原樣只為讓 round664 的數字可重現。
    rev_fail = [r for r in work if r["role"] == "review" and not r.get("ok")]
    rev_short = [r for r in rev_fail
                 if r["attempt"] < (r.get("retries_max") or 0) and not is_early_break(r, codes)]
    out["review_fail_records"] = len(rev_fail)
    out["review_fail_stopped_short"] = len(rev_short)

    # ---- 寬鬆救援估計 ----
    p3, p4 = p.get(3), p.get(4)
    if p3 is None or p4 is None:
        rescue, rescue_note = None, "p3/p4 未定義（該層沒有 attempt>=3 的深重試列）"
    else:
        rescue = len(review_voids) * (1 - (1 - p3) * (1 - p4))
        rescue_note = None
    out["void_by_role"] = dict(by_role)
    out["on_void_by_role"] = dict(on_by_role)
    out["on_void_total"] = len(on_voids)
    out["review_void_on"] = len(review_voids)
    out["review_share_of_on_void"] = (len(review_voids) / len(on_voids)) if on_voids else None
    out["rescue_estimate"] = rescue
    out["rescue_note"] = rescue_note
    out["rescue_frac_of_on_void"] = (rescue / len(on_voids)) if (rescue is not None and on_voids) else None

    # ---- 逾時混淆：失敗列上 review 與 gen 的設定逾時 ----
    def med(vals):
        v = sorted(vals)
        return v[len(v) // 2] if v else None
    out["timeout_review_fail_median"] = med([r["timeout_s"] for r in rev_fail])
    out["timeout_gen_fail_median"] = med(
        [r["timeout_s"] for r in work if r["role"] == "gen" and not r.get("ok")])
    out["timeout_review_cfg"] = sorted({r["timeout_s"] for r in work if r["role"] == "review"})
    out["timeout_gen_cfg"] = sorted({r["timeout_s"] for r in work if r["role"] == "gen"})

    # ---- 對帳（抓 M2）：void 序列數 vs summary.json 的 infra_void ----
    sm = {}
    sp = pathlib.Path(summary_path)
    if sp.exists():
        sm = json.loads(sp.read_text())
    out["summary_infra_void"] = find_void_counts(sm)
    out["status"] = "OK"
    return out


def find_void_counts(sm):
    """summary.json 各臂的 infra_void 數（結構隨世代不同，找得到才報）。"""
    found = {}
    def walk(node, path):
        if isinstance(node, dict):
            for k, v in node.items():
                if "void" in k.lower() and isinstance(v, (int, float)):
                    found[".".join(path + [k])] = v
                walk(v, path + [k])
        elif isinstance(node, list):
            for i, v in enumerate(node):
                walk(v, path + [str(i)])
    walk(sm, [])
    return found


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", nargs="+", required=True,
                    help="層名=run目錄=世代 的清單（世代見 ERA_NON_RETRYABLE）")
    ap.add_argument("--mutant", default=None, choices=["M1", "M2", "M3", "M4"])
    ap.add_argument("--json", default=None)
    a = ap.parse_args()

    res = {}
    for spec in a.runs:
        name, d, era = spec.split("=")
        era = int(era)
        d = pathlib.Path(d)
        calls = d / "calls.jsonl"
        if a.mutant == "M4":
            calls = d / "__nonexistent__.jsonl"     # 模擬安靜的空層
            if not calls.exists():
                calls.write_text("")
        try:
            res[name] = analyse(calls, d / "summary.json", era, a.mutant)
        finally:
            if a.mutant == "M4" and calls.exists() and calls.name.startswith("__"):
                calls.unlink()
    txt = json.dumps(res, indent=2, ensure_ascii=False)
    if a.json:
        pathlib.Path(a.json).write_text(txt)
    print(txt)
    return 0


if __name__ == "__main__":
    sys.exit(main())
