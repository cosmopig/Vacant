#!/usr/bin/env python3
"""配對差值的 95% 精確條件區間（McNemar 的伴隨區間）。純標準庫、零模型呼叫。

為什麼要這支（round656）：頭條「ON 等預算打不贏 OFF5」只掛在 p=0.5413 上。
p 值只說「沒測出差異」，不說資料還容得下多大的差異。判準見
runs/_analysis_r656/CRITERION.md（先 commit 才開始量）。

方法：n_d=b+c 固定，b ~ Bin(n_d, pi)，Clopper-Pearson 取 pi 的精確區間，
映射 delta = (2*pi - 1) * n_d / n。與 McNemar 精確檢定同一個條件化，
所以「區間排除 0」必然等價於「精確 p < 0.05」——這一致性是自檢條 C。
"""
from __future__ import annotations
import argparse, json, math, os, pathlib, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from analyze_paired import load_rows, arm_rows, exact_mcnemar_p  # noqa: E402

ALPHA = 0.05          # 95%，沿用專案既有慣例，非本輪新旋鈕
PRACTICAL_PP = 5.0    # 借用 R440B L2 / round483 的實務門檻，見 CRITERION.md
MIN_PAIRED = 60       # BROKEN 門檻

# round731（R463）：量哪一個「成功」。**定義逐字照抄 pooled_paired_ci.py:42-46**，
# 不是本輪新訂口徑。這支單 run 尺一直寫死 meets_demand（r675 修了 pooled、r678 補了
# power_paired，唯獨漏掉這裡 ⇒ 同一個坑第三次）。
#   deliv        = accepted ∧ meets_demand  ← round670 §三 裁定拒交臂只由這個結算
#   meets_demand = meets_demand             ← 舊語意，**保留為預設以維持回歸相容**
# 拒交臂（CONFORM）上 meets_demand 不是交付率：gain_run.py:588 在閘門拒交時回退到
# 最後一份候選、:1586 無條件對它評分 ⇒ accepted=False ∧ meets_demand=True 可達，
# 那一格東西根本沒交出去，算成交付會**高估拒交臂**。
KEYS: dict[str, tuple[tuple[str, ...], object]] = {
    "meets_demand": (("meets_demand",),
                     lambda r: bool(r.get("meets_demand"))),
    "deliv": (("accepted", "meets_demand"),
              lambda r: bool(r.get("accepted")) and bool(r.get("meets_demand"))),
}


def _resolve_key(key: str):
    """突變點必須在被測函式**內部**、且 env 在呼叫時才讀（模組層讀 ⇒ 永遠不生效，
    長得跟「偵測條沒牙齒」一模一樣，memory 記過）。"""
    fields, ok = KEYS[key]
    if os.environ.get("MUTANT") == "M_KEY":   # 突變點：--key 是裝飾品，永遠量 meets_demand
        fields, ok = KEYS["meets_demand"]
    return fields, ok


def _binom_cdf(k: int, n: int, p: float) -> float:
    """P(X<=k)，X~Bin(n,p)。用對數遞推累加，避免 math.comb 的大整數（round656：
    原本的大整數版本在 n 上百時把 selftest 拖到逾時）。"""
    if p <= 0.0:
        return 1.0
    if p >= 1.0:
        return 1.0 if k >= n else 0.0
    lp, lq = math.log(p), math.log1p(-p)
    lc = 0.0                       # log C(n,0)
    total = 0.0
    for i in range(k + 1):
        if i:
            lc += math.log((n - i + 1) / i)
        lt = lc + i * lp + (n - i) * lq
        if lt > -745.0:
            total += math.exp(lt)
    return min(1.0, total)


_CP_CACHE: dict = {}


def clopper_pearson(k: int, n: int, alpha: float = ALPHA) -> tuple[float, float]:
    """精確二項區間，用二分反轉 CDF（不需 scipy）。"""
    if n == 0:
        return (0.0, 1.0)
    key = (k, n, alpha)
    if key in _CP_CACHE:
        return _CP_CACHE[key]
    lo = 0.0
    if k > 0:
        a, b = 0.0, 1.0
        for _ in range(80):                      # 求 P(X>=k)=alpha/2 的 p
            m = (a + b) / 2
            if 1.0 - _binom_cdf(k - 1, n, m) < alpha / 2:
                a = m
            else:
                b = m
        lo = (a + b) / 2
    hi = 1.0
    if k < n:
        a, b = 0.0, 1.0
        for _ in range(80):                      # 求 P(X<=k)=alpha/2 的 p
            m = (a + b) / 2
            if _binom_cdf(k, n, m) > alpha / 2:
                a = m
            else:
                b = m
        hi = (a + b) / 2
    _CP_CACHE[key] = (lo, hi)
    return (lo, hi)


def _pi_ci(k, nd, alpha):                          # 突變點：M1 換成常態近似
    if MUTANT == "M1":
        if nd == 0:
            return (0.0, 1.0)
        p = k / nd
        h = 1.96 * math.sqrt(max(p * (1 - p), 1e-12) / nd)
        return (max(0.0, p - h), min(1.0, p + h))
    return clopper_pearson(k, nd, alpha)


def diff_ci(b: int, c: int, n: int, alpha: float = ALPHA) -> dict:
    """回傳 delta 的點估計與 95% 精確條件區間（單位：比例，非 pp）。"""
    nd = b + c
    scale = nd / n if n else 0.0
    if MUTANT == "M2":                             # 突變點：忘記乘 n_d/n
        scale = 1.0
    if nd == 0:
        return {"b": b, "c": c, "n": n, "n_discordant": 0, "delta": 0.0,
                "lo": -scale, "hi": scale, "pi_lo": 0.0, "pi_hi": 1.0,
                "p_mcnemar": 1.0}
    pl, ph = _pi_ci(b, nd, alpha)
    return {"b": b, "c": c, "n": n, "n_discordant": nd,
            "delta": (b - c) / n,
            "lo": (2 * pl - 1) * scale, "hi": (2 * ph - 1) * scale,
            "pi_lo": pl, "pi_hi": ph,
            "p_mcnemar": exact_mcnemar_p(b, c)}


def verdict(lo_pp: float, hi_pp: float) -> str:
    if lo_pp > 0:
        return "ON_WINS"
    if hi_pp <= PRACTICAL_PP:
        return "RULED_OUT"
    if lo_pp < -PRACTICAL_PP:
        return "UNINFORMATIVE"
    return "NON_INFERIOR_BUT_UNRESOLVED"


MAX_N_SEARCH = 1000


def n_needed(nd: int, n: int, target_pp: float = PRACTICAL_PP) -> int:
    """補充量（非事前註冊）：照觀測到的 discordant 比率、且假設 pi=0.5，
    要把半寬壓到 target_pp 需要多少配對題。線性放大 n_d 後直接算。"""
    if n == 0 or nd == 0:
        return -1
    rate = nd / n
    for m in range(n, MAX_N_SEARCH + 1):
        ndm = max(1, round(rate * m))
        k = round(ndm / 2)
        r = diff_ci(k, ndm - k, m)          # 直接走同一條映射，不另外手推公式
        half = (r["hi"] - r["lo"]) / 2 * 100
        if half <= target_pp:
            return m
    return -1


# ---------------------------------------------------------------- selftest
def selftest() -> int:
    fails = []
    # A: b=c => 點估計 0 且區間跨 0
    r = diff_ci(12, 12, 81)
    if not (abs(r["delta"]) < 1e-12 and r["lo"] < 0 < r["hi"]):
        fails.append(f"A: b=c 區間沒跨 0 或點估計非 0 -> {r['lo']:.4f},{r['hi']:.4f}")
    # B: c=0、n_d 夠大 => 下界必須 > 0
    r = diff_ci(20, 0, 81)
    if not r["lo"] > 0:
        fails.append(f"B: b=20,c=0 下界沒離開 0 -> lo={r['lo']:.4f}")
    # C: 「區間排除 0」<=> 「精確 p<0.05」逐格相同
    bad = []
    for b in range(0, 26):
        for c in range(0, 26):
            if b + c == 0:
                continue
            r = diff_ci(b, c, 81)
            excl = (r["lo"] > 0) or (r["hi"] < 0)
            sig = exact_mcnemar_p(b, c) < 0.05
            if excl != sig:
                bad.append((b, c, excl, sig))
    if bad:
        fails.append(f"C: 區間/檢定不一致 {len(bad)} 格，例：{bad[:3]}")
    # D: 點估計在區間內，且區間 ⊆ [-n_d/n, +n_d/n]
    bad = []
    for (b, c, n) in [(14, 10, 81), (3, 1, 81), (30, 5, 91), (0, 7, 81), (1, 0, 200)]:
        r = diff_ci(b, c, n)
        cap = r["n_discordant"] / n
        if not (r["lo"] <= r["delta"] <= r["hi"]):
            bad.append(f"點估計不在區間內 b={b} c={c}")
        if r["lo"] < -cap - 1e-9 or r["hi"] > cap + 1e-9:
            bad.append(f"區間超出 ±n_d/n b={b} c={c} cap={cap:.4f} [{r['lo']:.4f},{r['hi']:.4f}]")
    if bad:
        fails.append("D: " + "; ".join(bad))
    # E: 補充量 n_needed 必須與 diff_ci 自洽（m 達標、m-1 不達標）
    m = n_needed(24, 82)
    if m <= 0:
        fails.append("E: n_needed 找不到解")
    else:
        def half_at(mm):
            ndm = max(1, round(24 / 82 * mm)); k = round(ndm / 2)
            rr = diff_ci(k, ndm - k, mm)
            return (rr["hi"] - rr["lo"]) / 2 * 100
        if half_at(m) > PRACTICAL_PP + 1e-9:
            fails.append(f"E: n_needed={m} 但半寬 {half_at(m):.3f}pp 仍 > {PRACTICAL_PP}")
        if m > 1 and half_at(m - 1) <= PRACTICAL_PP + 1e-9:
            fails.append(f"E: n_needed={m} 不是最小值，m-1 半寬 {half_at(m-1):.3f}pp 也達標")
    for f in fails:
        print("SELFTEST FAIL:", f)
    if fails:
        return 1
    print("SELFTEST PASS: A(跨0) B(離開0) C(與McNemar逐格一致 676 格) D(點估計在內+上限) E(n_needed 與 diff_ci 自洽)")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run")
    ap.add_argument("--a-arm", default="ON")
    ap.add_argument("--b-arm", default="OFF5")
    ap.add_argument("--json")
    ap.add_argument("--key", default="meets_demand", choices=sorted(KEYS),
                    help="量哪一個成功；拒交臂（CONFORM）請用 deliv（round670 §三）。"
                         "預設 meets_demand 保回歸相容")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        return selftest()
    if not args.run:
        print("需要 --run 或 --selftest"); return 2

    d = pathlib.Path(args.run)
    rows = load_rows(d)
    A, B = arm_rows(rows, args.a_arm), arm_rows(rows, args.b_arm)
    common = sorted(set(A) & set(B))

    fields, ok = _resolve_key(args.key)
    # 第三類：缺欄位的 row 照實計、不進分母（缺 accepted 會被讀成「拒交」＝方向性偏誤）
    missing = [t for t in common
               if any(f not in A[t] or f not in B[t] for f in fields)]
    common = [t for t in common if t not in set(missing)]
    n = len(common)

    import hashlib
    summ = json.load((d / "summary.json").open(encoding="utf-8"))
    cond = {}
    for key in ("pool", "instrument", "calibration", "request_policy"):
        cond[key] = hashlib.sha256(json.dumps(summ.get(key), sort_keys=True).encode()).hexdigest()[:16]
    # 同一個 run 內兩臂共用 summary 的四項條件 => 恆同；照實記出處
    conditions_all_same = True

    b = sum(1 for t in common if ok(A[t]) and not ok(B[t]))
    c = sum(1 for t in common if ok(B[t]) and not ok(A[t]))
    r = diff_ci(b, c, n)
    lo_pp, hi_pp, d_pp = r["lo"] * 100, r["hi"] * 100, r["delta"] * 100

    broken = []
    if n < MIN_PAIRED:
        broken.append(f"n_paired={n} < {MIN_PAIRED}")
    if not conditions_all_same:
        broken.append("conditions_all_same=false")

    out = {
        "run": str(d), "a_arm": args.a_arm, "b_arm": args.b_arm,
        "key": args.key,
        "n_paired": n, "third_category_missing_meets_demand": missing,
        "a_ok": sum(1 for t in common if ok(A[t])),
        "b_ok": sum(1 for t in common if ok(B[t])),
        "b_discordant_a_only": b, "c_discordant_b_only": c,
        "n_discordant": r["n_discordant"],
        "delta_pp": d_pp, "ci95_lo_pp": lo_pp, "ci95_hi_pp": hi_pp,
        "pi_hat": (b / r["n_discordant"]) if r["n_discordant"] else None,
        "pi_ci95": [r["pi_lo"], r["pi_hi"]],
        "p_mcnemar_exact": r["p_mcnemar"],
        "practical_pp": PRACTICAL_PP,
        "verdict": "BROKEN" if broken else verdict(lo_pp, hi_pp),
        "broken_reasons": broken,
        "conditions_sha": cond,
        "supplement_n_needed_for_halfwidth_5pp": n_needed(r["n_discordant"], n),
    }
    print(f"run={d}  {args.a_arm} vs {args.b_arm}  n_paired={n}"
          + (f"  第三類(缺 meets_demand)={len(missing)}" if missing else "  第三類=0"))
    print(f"  {args.a_arm} 對 {out['a_ok']}/{n}={out['a_ok']/n*100:.2f}%   "
          f"{args.b_arm} 對 {out['b_ok']}/{n}={out['b_ok']/n*100:.2f}%")
    print(f"  discordant: b(只有{args.a_arm}對)={b}  c(只有{args.b_arm}對)={c}  n_d={r['n_discordant']}")
    print(f"  Δ = {d_pp:+.2f}pp    95% 精確條件區間 [{lo_pp:+.2f}, {hi_pp:+.2f}]pp")
    print(f"  McNemar 精確 p = {r['p_mcnemar']:.4f}   （區間排除0 <=> p<0.05，自檢條 C）")
    print(f"  判定（CRITERION 事前表，門檻 ±{PRACTICAL_PP}pp）：{out['verdict']}")
    if broken:
        print("  BROKEN:", "; ".join(broken))
    print(f"  [補充，非判定量] 要把半寬壓到 ±{PRACTICAL_PP}pp 需配對題 ≈ "
          f"{out['supplement_n_needed_for_halfwidth_5pp']}")
    if args.json:
        pathlib.Path(args.json).write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    return 0


MUTANT = ""
if __name__ == "__main__":
    import os
    MUTANT = os.environ.get("PAIRED_CI_MUTANT", "")
    sys.exit(main())
