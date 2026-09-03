#!/usr/bin/env python3
"""round658：把**多個 run** 的 ON/OFF5 配對資料合併，量頭條 Δ 的區間。

為什麼要這支（判準全文 `runs/_analysis_r658/CRITERION.md`，先 commit 才開始量）：
  round656 量出 E3 頭條的區間是 [−7.82,+16.33]pp（UNINFORMATIVE），並算出要壓到
  ±5pp 需要 ≈538 配對題，而 E3 只有 91。交棒因此寫「需要更多題」——但**沒有人查過
  磁碟上已經有多少 ON/OFF5 配對資料**（記憶規則：卡在「需要更多」先查磁碟）。

合併是**加法恆等式，不是新模型**：
  Σ(b_i−c_i)/Σn_i = (2B−N_d)/N，與單層同一個式子
  ⇒ 直接呼叫 round656 已雙向驗證的 `paired_ci.diff_ci(b,c,n)`，
  **不新增估計量、不新增可調參數**（唯一新增的是異質性檢定的 0.05，那是既有慣例）。

合併的效力來自「各層 π 相同」。**本工具檢定這個假設，不假設它成立**：
  Fisher 精確檢定 [[b1,c1],[b2,c2]]，p_het<0.05 ⇒ 判 HETEROGENEOUS，
  合併區間**不得**當頭條（CRITERION §三）。

納入規則與結果無關，只有一條：**量具必須是 round393 修好之後的尺**
（commit 4795190，2026-08-31T10:34:23Z；該 bug 對 ON 的懲罰遠大於 OFF5，
方向正好落在頭條的比較軸上）。判定用 run 起跑時刻，不用 mtime。

用法：
  python3 ops/gain/replay/pooled_paired_ci.py --selftest
  python3 ops/gain/replay/pooled_paired_ci.py --stratum S1=<dir> --stratum S2=<dir> --json out.json
"""
import argparse, hashlib, json, math, os, pathlib, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3]))
from ops.gain.replay.paired_ci import diff_ci, verdict, n_needed, ALPHA, PRACTICAL_PP
from ops.gain.analyze_paired import arm_rows

HET_ALPHA = 0.05   # 異質性擋門（既有慣例，非本輪新訂旋鈕）
MIN_PAIRED = 60    # 沿用 paired_ci 的 BROKEN 門檻


def fisher_exact_2x2(t) -> float:
    """雙尾 Fisher 精確檢定，純標準庫。t = [[a,b],[c,d]]。"""
    if MUTANT == "M4":                       # 突變點：等於沒檢定
        return 1.0
    (a, b), (c, d) = t
    n = a + b + c + d
    if n == 0:
        return 1.0
    r1, c1 = a + b, a + c

    def hyper(k):
        return math.comb(r1, k) * math.comb(n - r1, c1 - k) / math.comb(n, c1)

    lo, hi = max(0, c1 - (n - r1)), min(r1, c1)
    p_obs = hyper(a)
    tot = sum(hyper(k) for k in range(lo, hi + 1) if hyper(k) <= p_obs * (1 + 1e-9))
    return min(1.0, tot)


def pool(strata: list[dict]) -> dict:
    """合併：加總 b/c/n 後套同一條式子。M3 突變成未加權平均。"""
    B = sum(s["b"] for s in strata)
    C = sum(s["c"] for s in strata)
    N = sum(s["n"] for s in strata)
    r = diff_ci(B, C, N)
    if MUTANT == "M3":                       # 突變點：合併寫成兩層 Δ 的未加權平均
        ds = [(s["b"] - s["c"]) / s["n"] for s in strata if s["n"]]
        r = dict(r, delta=sum(ds) / len(ds) if ds else 0.0)
    return {"B": B, "C": C, "N": N, **r}


def group_totals(strata: list[dict]) -> dict:
    """依 group 標籤加總 b/c/n。沒帶 group 的層，group 就是它自己的 label
    （⇒ 兩層無標籤時退化成 round658 的逐層 2x2，逐位元相容）。"""
    out: dict = {}
    for s in strata:
        g = s.get("group") or s["label"]
        t = out.setdefault(g, {"b": 0, "c": 0, "n": 0, "labels": []})
        t["b"] += s["b"]; t["c"] += s["c"]; t["n"] += s["n"]; t["labels"].append(s["label"])
    return out


def het_gate(strata: list[dict]):
    """round660：修掉「層數≠2 時擋門安靜失效」。

    round658 寫的是 `if len(strata)==2 else None`，於是六層進來 p_het=None
    ⇒ 判 HOMOGENEOUS_NOT_REJECTED ⇒ pooled_usable_as_headline=True，
    **擋門根本沒跑卻放行**。修法不新增估計量也不新增旋鈕：
    Fisher 2x2 改跑在**兩個 group 的加總 (B,C)** 上，同一個 fisher_exact_2x2、
    同一個 HET_ALPHA。group 數 ≠ 2 就回報 BROKEN，不准安靜放行。

    回傳 (p_het, broken_reason_or_None)。
    """
    if MUTANT == "M5":                       # 突變點：退回 round658 的安靜失效版
        p = fisher_exact_2x2([[strata[0]["b"], strata[0]["c"]],
                              [strata[1]["b"], strata[1]["c"]]]) if len(strata) == 2 else None
        return p, None
    groups = group_totals(strata)
    if len(groups) != 2:
        return None, (f"異質性擋門跑不了：需要恰好 2 個 group，實得 {len(groups)} 個 "
                      f"（層數={len(strata)}）。層數>2 時必須用 --stratum LABEL:GROUP=dir 指定分組。")
    (ga, gb) = [groups[k] for k in sorted(groups)]
    return fisher_exact_2x2([[ga["b"], ga["c"]], [gb["b"], gb["c"]]]), None


def stratum_from_run(d: pathlib.Path, a_arm: str, b_arm: str) -> dict:
    rows = [json.loads(l) for l in (d / "rows.jsonl").open(encoding="utf-8") if l.strip()]
    A, Bm = arm_rows(rows, a_arm), arm_rows(rows, b_arm)
    common = sorted(set(A) & set(Bm))
    missing = [t for t in common if "meets_demand" not in A[t] or "meets_demand" not in Bm[t]]
    common = [t for t in common if t not in set(missing)]
    b = sum(1 for t in common if A[t]["meets_demand"] and not Bm[t]["meets_demand"])
    c = sum(1 for t in common if Bm[t]["meets_demand"] and not A[t]["meets_demand"])
    summ = json.load((d / "summary.json").open(encoding="utf-8"))
    cond = {k: hashlib.sha256(json.dumps(summ.get(k), sort_keys=True).encode()).hexdigest()[:16]
            for k in ("pool", "instrument", "calibration", "request_policy")}
    rr = diff_ci(b, c, len(common))
    return {
        "dir": str(d), "n": len(common), "b": b, "c": c,
        "a_ok": sum(1 for t in common if A[t]["meets_demand"]),
        "b_ok": sum(1 for t in common if Bm[t]["meets_demand"]),
        "third_category_missing_meets_demand": missing,
        "delta_pp": rr["delta"] * 100, "ci95_lo_pp": rr["lo"] * 100, "ci95_hi_pp": rr["hi"] * 100,
        "n_discordant": rr["n_discordant"], "conditions_sha": cond,
        "rows_sha256_16": hashlib.sha256((d / "rows.jsonl").read_bytes()).hexdigest()[:16],
        "rows_lines": sum(1 for _ in (d / "rows.jsonl").open(encoding="utf-8")),
    }


def selftest() -> int:
    """只驗**本輪新增的**合併與異質性那段；diff_ci 本身 round656 已驗過。"""
    fails = []
    # P1：合併是加法恆等式——某層歸零後必須與另一層逐位元相同
    one = pool([{"b": 14, "c": 10, "n": 82}])
    two = pool([{"b": 14, "c": 10, "n": 82}, {"b": 0, "c": 0, "n": 0}])
    if json.dumps(one, sort_keys=True) != json.dumps(two, sort_keys=True):
        fails.append("P1: 加了一個全零層之後結果變了 ⇒ 合併不是加法恆等式")
    # P2：合併 != 兩層 Δ 的未加權平均（n 差 10 倍）
    s = [{"b": 20, "c": 0, "n": 200}, {"b": 0, "c": 4, "n": 20}]
    got = pool(s)["delta"]
    want = (20 - 0 + 0 - 4) / 220
    unweighted = ((20 - 0) / 200 + (0 - 4) / 20) / 2
    if abs(got - want) > 1e-12:
        fails.append(f"P2: 合併 Δ={got:.6f} 不等於 Σ(b−c)/Σn={want:.6f}")
    elif abs(got - unweighted) < 1e-12:
        fails.append("P2: 合併 Δ 等於未加權平均 ⇒ 沒有照 n 加權")
    # P3：Fisher 對稱（轉置同值）
    t = [[14, 10], [7, 3]]
    if abs(fisher_exact_2x2(t) - fisher_exact_2x2([[t[0][0], t[1][0]], [t[0][1], t[1][1]]])) > 1e-12:
        fails.append("P3: Fisher 對轉置給出不同 p")
    # P4：異質性有牙齒——完全相反的表必須 <0.05
    p_opp = fisher_exact_2x2([[20, 0], [0, 20]])
    if not (p_opp < HET_ALPHA):
        fails.append(f"P4: [[20,0],[0,20]] 的 p_het={p_opp:.4f} 沒有 <{HET_ALPHA} ⇒ 檢定沒牙齒")
    # ---- round660 新增：擋門在層數 != 2 時不准安靜失效 ----
    def _st(label, group, b, c, n):
        return {"label": label, "group": group, "b": b, "c": c, "n": n}

    # P5：六層兩 group、兩 group 方向完全相反 ⇒ 必須判 HETEROGENEOUS
    opp = [_st("S1", "A", 10, 0, 60), _st("S2", "A", 10, 0, 60),
           _st("S3", "B", 0, 10, 60), _st("S4", "B", 0, 10, 60),
           _st("S5", "B", 0, 5, 60), _st("S6", "B", 0, 5, 60)]
    p_opp6, err6 = het_gate(opp)
    if err6 is not None:
        fails.append(f"P5: 六層兩 group 卻回報擋門跑不了：{err6}")
    elif p_opp6 is None or not (p_opp6 < HET_ALPHA):
        fails.append(f"P5: 兩 group 方向完全相反，p_het={p_opp6} 沒有 <{HET_ALPHA} "
                     f"⇒ 擋門在層數!=2 時沒牙齒（round658 的安靜失效）")

    # P7：層數 >2 但沒帶 group（⇒ group 數 != 2）必須回報 BROKEN，不准安靜放行
    nogrp = [_st("S1", None, 10, 0, 60), _st("S2", None, 10, 0, 60), _st("S3", None, 0, 10, 60)]
    p_ng, err_ng = het_gate(nogrp)
    if err_ng is None or p_ng is not None:
        fails.append(f"P7: 三層無 group 竟然放行（p_het={p_ng}, err={err_ng}）⇒ 擋門安靜失效")

    # P7b：兩層無 group 必須與 round658 逐位元相容（退化成逐層 2x2）
    two = [_st("S1", None, 14, 10, 82), _st("S2", None, 11, 12, 167)]
    p_two, err_two = het_gate(two)
    ref = fisher_exact_2x2([[14, 10], [11, 12]])
    if err_two is not None or p_two is None or abs(p_two - ref) > 1e-12:
        fails.append(f"P7b: 兩層無 group 的 p_het={p_two} 與 round658 的 {ref} 不逐位元相同")

    for f in fails:
        print("FAIL:", f)
    print("SELFTEST", "FAIL" if fails else "PASS", f"(MUTANT={MUTANT or 'none'})")
    return 1 if fails else 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stratum", action="append", default=[], help="LABEL=dir")
    ap.add_argument("--a-arm", default="ON")
    ap.add_argument("--b-arm", default="OFF5")
    ap.add_argument("--json")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        return selftest()
    if len(args.stratum) < 2:
        print("需要至少兩個 --stratum LABEL=dir，或 --selftest"); return 2

    strata = []
    for spec in args.stratum:
        label, _, path = spec.partition("=")
        label, _, group = label.partition(":")
        st = stratum_from_run(pathlib.Path(path), args.a_arm, args.b_arm)
        strata.append({"label": label, "group": group or None, **st})

    p_het, gate_err = het_gate(strata)
    pooled = pool(strata)
    lo_pp, hi_pp, d_pp = pooled["lo"] * 100, pooled["hi"] * 100, pooled["delta"] * 100

    broken = []
    if gate_err:
        broken.append(gate_err)
    if pooled["N"] < MIN_PAIRED:
        broken.append(f"N_pooled={pooled['N']} < {MIN_PAIRED}")
    for s in strata:
        if s["third_category_missing_meets_demand"]:
            broken.append(f"{s['label']}: 第三類 {len(s['third_category_missing_meets_demand'])} 題缺 meets_demand")

    if p_het is None:
        het = "GATE_NOT_RUN"          # round660：擋門沒跑成功就不准說「未拒絕同質」
    elif p_het < HET_ALPHA:
        het = "HETEROGENEOUS"
    else:
        het = "HOMOGENEOUS_NOT_REJECTED"
    signs = {(1 if s["b"] > s["c"] else -1 if s["c"] > s["b"] else 0) for s in strata}
    out = {
        "strata": strata,
        "p_het_fisher": p_het, "het_alpha": HET_ALPHA, "het_verdict": het,
        "pooled": {"B": pooled["B"], "C": pooled["C"], "N": pooled["N"],
                   "n_discordant": pooled["n_discordant"],
                   "delta_pp": d_pp, "ci95_lo_pp": lo_pp, "ci95_hi_pp": hi_pp,
                   "pi_ci95": [pooled["pi_lo"], pooled["pi_hi"]]},
        "verdict_pooled": verdict(lo_pp, hi_pp),
        "pooled_usable_as_headline": het == "HOMOGENEOUS_NOT_REJECTED" and not broken,
        "groups": group_totals(strata),
        "opposite_direction_strata": len(signs - {0}) > 1,
        "practical_pp": PRACTICAL_PP,
        "supplement_n_needed_for_halfwidth_5pp": n_needed(pooled["n_discordant"], pooled["N"]),
        "broken_reasons": broken,
    }
    js = json.dumps(out, ensure_ascii=False, indent=2)
    if args.json:
        pathlib.Path(args.json).write_text(js + "\n", encoding="utf-8")
    print(js)
    return 1 if broken else 0


MUTANT = ""
if __name__ == "__main__":
    MUTANT = os.environ.get("POOLED_CI_MUTANT", "")
    raise SystemExit(main())
