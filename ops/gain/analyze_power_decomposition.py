"""配對 power 的分解讀出：required-N = n_disc(ψ) / p_disc（round83 新增）。

## 為什麼要這支工具（round83 的premise檢查）

round78 §6 的 P4 規則把「OFF 邊際失敗率」當成「量測窗口」的代理量：
失敗率太低 ⇒ 天花板 ⇒ 換更難的題（Route B）。

但三臂比較用的是**配對**檢定（McNemar），而配對檢定的資訊**只來自
discordant pairs**。邊際失敗率跟 discordant 比例是兩件事：

    required_N = n_disc_needed(ψ) / p_disc

    p_disc = P(兩臂結果不同)            ← 「難度」大致影響這一項
    ψ      = b/(b+c)，discordant 裡誰贏 ← 「機制真的比較好」影響這一項

n_disc_needed(ψ) 對 ψ→0.5 是發散的。所以當 ψ≈0.5（兩臂實際上是同一種
過程）時，**把題目變難只動分母，救不回 power**。P4 的映射假設了難度是
唯一的旋鈕，那個假設對 marginal accuracy 成立、對配對 power 不成立。

## 這支工具算什麼

1. 逐對的 b／c／n_common／p_disc／ψ／diff、**exact** McNemar p（二項尾機率）。
2. required-N：**非條件** power（n_disc ~ Binomial(N, p_disc) 一起積分掉，
   不是「假設剛好拿到 k 個 discordant」的條件 power），二分搜最小 N。
3. `resolvable_floor`：在給定題庫容量下，80% power 能分辨的**最小** |diff|。
   ——這一項才是「答不出來」的正確寫法：不是「還沒跑夠」，是
   「效應比這個題庫的解析度還小」，是一個上界，不是失敗。
4. `feasibility`：p_disc 有數學上界。兩臂 accuracy 相近且正相關時
   p_disc ≤ 2a(1-a) ≤ 0.5。把 p_disc 推到上界仍需要的 N，就是
   「再怎麼換難題也不可能低於」的下界。

⚠ 這支工具**只讀** rows.jsonl，不呼叫任何模型、不碰 relay
  （round82 事故規則：任何 gain_run.py 在跑時不得對 relay 發呼叫）。

⚠ 正確性定義沿用 analyze_fullbank_off.py：`accepted and meets_demand`，
  不是單看 meets_demand。兩支工具必須同一個定義，否則數字不能互相引用。

用法：
    python3 ops/gain/analyze_power_decomposition.py \
        --pair ON=runs/g_onoff5_qwenonly_v3_20260824 \
               OFF5=runs/g_onoff5_qwenonly_v3_20260824 \
        --bank-capacity 371 [--json OUT]
    python3 ops/gain/analyze_power_decomposition.py --self-test
"""
from __future__ import annotations

import argparse
import functools
import json
import math
from pathlib import Path

ALPHA = 0.05
POWER = 0.80
DEFAULT_CAPACITY = 371


# ── 資料讀取 ────────────────────────────────────────────────────────
def load_arm(run_dir: str, arm: str) -> dict[str, bool]:
    """回傳 {task_id: correct}；correct ＝ accepted and meets_demand。"""
    out: dict[str, bool] = {}
    for line in (Path(run_dir) / "rows.jsonl").open():
        if not line.strip():
            continue
        r = json.loads(line)
        if r.get("arm") != arm:
            continue
        out[r["task_id"]] = bool(r.get("accepted") and r.get("meets_demand"))
    return out


# ── exact McNemar ───────────────────────────────────────────────────
def _binom_pmf(k: int, n: int, p: float) -> float:
    """log 空間計算——直接用 math.comb 在 n 上千時會 OverflowError。"""
    if k < 0 or k > n:
        return 0.0
    if p <= 0.0:
        return 1.0 if k == 0 else 0.0
    if p >= 1.0:
        return 1.0 if k == n else 0.0
    lg = (math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1)
          + k * math.log(p) + (n - k) * math.log1p(-p))
    return math.exp(lg) if lg > -700 else 0.0


def exact_mcnemar_p(b: int, c: int) -> float:
    """雙尾 exact binomial test（H0: ψ=0.5），n_disc=0 時回 1.0。"""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    tail = sum(_binom_pmf(i, n, 0.5) for i in range(k + 1))
    return min(1.0, 2 * tail)


@functools.lru_cache(maxsize=None)
def _reject_set(n_disc: int, alpha: float = ALPHA) -> tuple[int, ...]:
    """n_disc 固定時，雙尾 exact test 會拒絕 H0 的 b 值集合。

    拒絕域是對稱的兩條尾巴 ⇒ 只要找出最大的 k 使 2*P(B<=k) <= alpha，
    不必逐點呼叫 exact_mcnemar_p（那是 O(n^2)，n 上千時跑不完）。"""
    if n_disc == 0:
        return ()
    cum = 0.0
    kmax = -1
    for k in range(n_disc + 1):
        cum += _binom_pmf(k, n_disc, 0.5)
        if min(1.0, 2 * cum) <= alpha:
            kmax = k
        else:
            break
    if kmax < 0:
        return ()
    return tuple(sorted(set(range(0, kmax + 1))
                        | set(range(n_disc - kmax, n_disc + 1))))


def conditional_power(n_disc: int, psi: float, alpha: float = ALPHA) -> float:
    return sum(_binom_pmf(b, n_disc, psi) for b in _reject_set(n_disc, alpha))


def unconditional_power(n: int, p_disc: float, psi: float,
                        alpha: float = ALPHA) -> float:
    """n_disc ~ Binomial(n, p_disc) 一起積掉——不是條件 power。"""
    if n <= 0 or p_disc <= 0:
        return 0.0
    total = 0.0
    for k in range(n + 1):
        w = _binom_pmf(k, n, p_disc)
        if w < 1e-12:
            continue
        total += w * conditional_power(k, psi, alpha)
    return total


def required_n(p_disc: float, psi: float, *, power: float = POWER,
               alpha: float = ALPHA, cap: int = 20000) -> int | None:
    """達到 power 所需的最小總題數 N；超過 cap 回 None（＝實務上不可及）。"""
    if p_disc <= 0 or abs(psi - 0.5) < 1e-9:
        return None
    lo, hi = 1, 64
    while hi <= cap and unconditional_power(hi, p_disc, psi, alpha) < power:
        lo, hi = hi, hi * 2
    if hi > cap:
        return None
    while lo < hi:
        mid = (lo + hi) // 2
        if unconditional_power(mid, p_disc, psi, alpha) >= power:
            hi = mid
        else:
            lo = mid + 1
    return lo


def resolvable_floor(n: int, p_disc: float, *, power: float = POWER,
                     alpha: float = ALPHA, step: float = 0.005) -> dict:
    """題庫容量 n 固定時，80% power 能分辨的最小 |diff|（pp）。

    diff = p_disc * (2ψ - 1)。掃 ψ 從 0.5 往上，找第一個達標的。"""
    psi = 0.5 + step
    while psi < 1.0:
        if unconditional_power(n, p_disc, psi, alpha) >= power:
            return {"min_psi": round(psi, 4),
                    "min_abs_diff_pp": round(p_disc * (2 * psi - 1) * 100, 3)}
        psi += step
    return {"min_psi": None, "min_abs_diff_pp": None}


# ── 分解 ────────────────────────────────────────────────────────────
def decompose(a: dict[str, bool], b_: dict[str, bool], name_a: str, name_b: str,
              capacity: int = DEFAULT_CAPACITY) -> dict:
    common = sorted(set(a) & set(b_))
    n = len(common)
    b = sum(1 for t in common if a[t] and not b_[t])       # a 贏
    c = sum(1 for t in common if b_[t] and not a[t])       # b 贏
    n_disc = b + c
    p_disc = n_disc / n if n else 0.0
    psi = (b / n_disc) if n_disc else None
    acc_a = sum(a[t] for t in common) / n if n else None
    acc_b = sum(b_[t] for t in common) / n if n else None
    diff_pp = (acc_a - acc_b) * 100 if n else None

    out = {
        "pair": f"{name_a} vs {name_b}", "n_common": n,
        "b_%s_only" % name_a: b, "c_%s_only" % name_b: c,
        "n_discordant": n_disc, "p_disc": round(p_disc, 4),
        "psi": round(psi, 4) if psi is not None else None,
        "acc_a": round(acc_a, 4) if acc_a is not None else None,
        "acc_b": round(acc_b, 4) if acc_b is not None else None,
        "diff_pp": round(diff_pp, 3) if diff_pp is not None else None,
        "exact_mcnemar_p": round(exact_mcnemar_p(b, c), 6),
        "bank_capacity": capacity,
    }
    if psi is None or p_disc == 0:
        out["required_n_at_observed_effect"] = None
        out["answerable_within_capacity"] = False
        out["note"] = "沒有 discordant pair ⇒ 這一對的 power 無法從本資料估計"
        return out

    # ψ 對稱：power 只看 |ψ-0.5|
    psi_eff = max(psi, 1 - psi)
    req = required_n(p_disc, psi_eff)
    out["psi_effective"] = round(psi_eff, 4)
    out["required_n_at_observed_effect"] = req
    out["answerable_within_capacity"] = bool(req is not None and req <= capacity)
    out["resolvable_floor_at_capacity"] = resolvable_floor(capacity, p_disc)

    # 可行性下界：把 p_disc 推到「等 accuracy 正相關」的數學上界 0.5，
    # ψ 維持在觀測值——這是「換再難的題也不可能低於」的 N。
    best = required_n(0.5, psi_eff)
    out["feasibility_bound"] = {
        "max_p_disc_equal_acc": 0.5,
        "required_n_at_max_p_disc": best,
        "still_impossible_at_capacity": bool(best is None or best > capacity),
        "why": "兩臂 accuracy 相近且正相關時 p_disc ≤ 2a(1-a) ≤ 0.5；"
               "把 p_disc 推到 0.5 仍需這個 N ⇒ 難度旋鈕的極限",
    }
    return out


# ── self-test（先證明它在已知答案上會叫，再信它的綠燈）────────────
def self_test() -> int:
    fails = []

    def chk(cond, msg):
        if not cond:
            fails.append(msg)

    # 1. exact McNemar 對照 round77 已發表的數字（b=6,c=1 ⇒ p=0.125）
    chk(abs(exact_mcnemar_p(6, 1) - 0.125) < 1e-9,
        f"exact_mcnemar_p(6,1)={exact_mcnemar_p(6,1)} 應為 0.125（round77 已發表）")
    chk(abs(exact_mcnemar_p(4, 6) - 0.7539) < 1e-3,
        f"exact_mcnemar_p(4,6)={exact_mcnemar_p(4,6)} 應≈0.7539（round77 已發表）")
    chk(abs(exact_mcnemar_p(5, 2) - 0.453125) < 1e-6,
        f"exact_mcnemar_p(5,2)={exact_mcnemar_p(5,2)} 應≈0.4531（round77 已發表）")
    chk(exact_mcnemar_p(0, 0) == 1.0, "n_disc=0 應回 p=1.0")

    # 2. power 單調性：ψ 越極端所需 N 越小
    n_60 = required_n(0.18, 0.60)
    n_75 = required_n(0.18, 0.75)
    chk(n_60 is not None and n_75 is not None and n_75 < n_60,
        f"required_n 應隨 ψ 變極端而下降，得到 {n_60} / {n_75}")
    # p_disc 越大所需 N 越小（分母）
    chk(required_n(0.36, 0.60) < n_60,
        "required_n 應隨 p_disc 上升而下降")
    # ψ=0.5 ⇒ 不可能
    chk(required_n(0.18, 0.5) is None, "ψ=0.5 應回 None（永遠測不出來）")

    # 3. 植入缺陷：非條件 power 必須真的把 n_disc 的隨機性積掉。
    #    ⚠ 第一版寫成「非條件 < 期望 n_disc 的條件 power」是**錯的測試**：
    #      exact test 的 power 對 n_disc 是鋸齒狀不是凹的，實測 0.7656 > 0.7639。
    #      改用兩個不會被鋸齒影響的性質：
    #    (a) p_disc=1（每題都 discordant）⇒ 非條件必須**恆等於**條件；
    chk(abs(unconditional_power(50, 1.0, 0.70) - conditional_power(50, 0.70)) < 1e-9,
        "p_disc=1 時非條件 power 應恆等於條件 power")
    #    (b) p_disc=0.5 ⇒ 必須明顯低於「全部都是 discordant」的條件 power，
    #        否則就是沒有積掉 n_disc（直接把 n 當 n_disc 用）。
    chk(unconditional_power(50, 0.5, 0.70) < conditional_power(50, 0.70) - 0.05,
        f"p_disc=0.5 的非條件 power({unconditional_power(50, 0.5, 0.70):.4f}) 應明顯"
        f"低於條件 power({conditional_power(50, 0.70):.4f})——相等代表 n 被當成 n_disc")

    # 4. 端到端：合成一對已知 b/c 的 rows
    a = {f"t{i}": True for i in range(50)}
    b_ = dict(a)
    for i in range(6):            # a 贏 6
        b_[f"t{i}"] = False
    for i in range(6, 7):         # b 贏 1
        a[f"t{i}"] = False
    d = decompose(a, b_, "A", "B", capacity=371)
    chk(d["b_A_only"] == 6 and d["c_B_only"] == 1,
        f"decompose b/c 應為 6/1，得到 {d['b_A_only']}/{d['c_B_only']}")
    chk(abs(d["exact_mcnemar_p"] - 0.125) < 1e-9, "端到端 p 應為 0.125")

    # 5. 植入缺陷：正確性定義必須是 accepted AND meets_demand
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        p = Path(td)
        (p / "rows.jsonl").write_text(
            json.dumps({"arm": "X", "task_id": "t1",
                        "accepted": False, "meets_demand": True}) + "\n"
            + json.dumps({"arm": "X", "task_id": "t2",
                          "accepted": True, "meets_demand": True}) + "\n")
        got = load_arm(str(p), "X")
        chk(got == {"t1": False, "t2": True},
            f"accepted=False 但 meets_demand=True 必須算不正確，得到 {got}")

    for f in fails:
        print("FAIL:", f)
    print(f"self-test: 5 groups, {len(fails)} failure(s)")
    return 1 if fails else 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pair", nargs=2, action="append", default=[],
                    metavar="NAME=RUNDIR",
                    help="兩個 NAME=RUNDIR；可重複給多對")
    ap.add_argument("--bank-capacity", type=int, default=DEFAULT_CAPACITY)
    ap.add_argument("--json", default=None)
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()

    if args.self_test:
        return self_test()
    if not args.pair:
        ap.error("需要至少一組 --pair")

    results = []
    for spec_a, spec_b in args.pair:
        na, da = spec_a.split("=", 1)
        nb, db = spec_b.split("=", 1)
        results.append(decompose(load_arm(da, na), load_arm(db, nb),
                                 na, nb, args.bank_capacity))
    out = {"alpha": ALPHA, "power_target": POWER,
           "correctness": "accepted and meets_demand", "pairs": results}
    print(json.dumps(out, ensure_ascii=False, indent=2))
    if args.json:
        Path(args.json).write_text(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
