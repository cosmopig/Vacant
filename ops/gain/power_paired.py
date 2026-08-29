#!/usr/bin/env python3
"""配對設計的「訊號 vs 雜訊」與 power 分析（round260 新增）。

為什麼要這支工具（round260）：
  round252-259 連續 8 輪把 discordant pair 的數字**按輪次**報，並且開始把
  「這一輪 b 跳了 +2」當成訊號候選。那是用錯單位：一輪是牆鐘窗口，一輪裡
  出現幾個 discordant pair 取決於那 500s 剛好跑完幾題。analyze_paired.py 的
  docstring 早就寫了「證據單位是 discordant pair」。

  這支工具做兩件 analyze_paired.py 沒做的事：
    1. 把 discordant pair 按**到達順序**（B 臂 rows.jsonl 的行序）排成序列，
       在序列上檢定「最近 k 個是否同向」——這才是「訊號轉向」的正確檢定。
    2. Power：在觀測到的 discordant rate 下，配對上限 n 能偵測到多大的效果
       （MDE），以及若真實效果就是觀測值需要多少配對數。若後者超過題庫大小，
       那是「這個設計答不出這個問題」的結構性結論。

判準寫在量測之前，見 GAIN_STATE round260。
"""
import argparse
import json
import math
import pathlib


def exact_mcnemar_p(b: int, c: int) -> float:
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    tail = sum(math.comb(n, i) for i in range(k + 1)) / (2 ** n)
    return min(1.0, 2 * tail)


def load_arm(d: pathlib.Path, arm: str) -> list[dict]:
    rows = [json.loads(l) for l in (d / "rows.jsonl").open(encoding="utf-8") if l.strip()]
    return [r for r in rows if r.get("arm") == arm]


def mde_at_n(n_paired: int, disc_rate: float) -> dict:
    """n_paired 個配對、discordant rate 給定時，雙尾 α=0.05 下的最小可偵測效果。

    回傳能達到 p<0.05 的最小 |b-c|，以及換算成的 rate difference（|b-c|/n）。
    """
    n_disc = round(n_paired * disc_rate)
    if n_disc == 0:
        return {"n_disc_expected": 0, "min_gap": None, "mde_pp": None}
    for gap in range(0, n_disc + 1):
        # b+c = n_disc, |b-c| = gap  ⇒ 需要 gap 與 n_disc 同奇偶
        if (n_disc - gap) % 2:
            continue
        b = (n_disc + gap) // 2
        c = n_disc - b
        if exact_mcnemar_p(b, c) < 0.05:
            return {
                "n_disc_expected": n_disc,
                "min_gap": gap,
                "min_split": [b, c],
                "mde_pp": 100.0 * gap / n_paired,
            }
    return {"n_disc_expected": n_disc, "min_gap": None, "mde_pp": None}


def n_needed_for_power(p_b: float, power: float = 0.80, alpha: float = 0.05) -> int:
    """真實 discordant 偏向 p_b 時，要多少 discordant pair 才有 `power` 的檢出力。

    用精確二項的正規近似（Casagrande-Pike 風格的基本式），只求量級。
    """
    if abs(p_b - 0.5) < 1e-9:
        return -1
    z_a = 1.959963985
    z_b = 0.8416212336
    d = abs(p_b - 0.5)
    num = z_a * 0.5 + z_b * math.sqrt(p_b * (1 - p_b))
    return math.ceil((num / d) ** 2)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--a-run", required=True)
    ap.add_argument("--a-arm", required=True)
    ap.add_argument("--b-run", required=True)
    ap.add_argument("--b-arm", required=True)
    ap.add_argument("--n-cap", type=int, required=True,
                    help="配對上限（通常是先跑完那一臂的列數）")
    ap.add_argument("--bench-size", type=int, default=378, help="題庫總題數")
    ap.add_argument("--json")
    args = ap.parse_args()

    A = {r["task_id"]: r for r in load_arm(pathlib.Path(args.a_run), args.a_arm)}
    b_rows = load_arm(pathlib.Path(args.b_run), args.b_arm)  # 保持行序 = 到達順序

    seq = []          # 到達順序的 discordant 事件
    n_paired = 0
    for r in b_rows:
        t = r["task_id"]
        if t not in A:
            continue
        n_paired += 1
        a_ok, b_ok = bool(A[t]["meets_demand"]), bool(r["meets_demand"])
        if a_ok and not b_ok:
            seq.append(("b", t))
        elif b_ok and not a_ok:
            seq.append(("c", t))

    letters = "".join(s for s, _ in seq)
    nb, nc = letters.count("b"), letters.count("c")
    p_all = exact_mcnemar_p(nb, nc)

    # T1 / T2：序列尾端的同向檢定
    def tail_test(k: int) -> dict:
        tail = letters[-k:]
        if len(tail) < k:
            return {"k": k, "available": False}
        maj = max(tail.count("b"), tail.count("c"))
        # 單尾：最近 k 個中 >=maj 同向（指定方向）的機率
        p_one = sum(math.comb(k, i) for i in range(maj, k + 1)) / (2 ** k)
        return {"k": k, "available": True, "tail": tail, "majority": maj,
                "p_one_sided": p_one}

    t1, t2 = tail_test(5), tail_test(8)
    triggered = []
    if t1.get("available") and t1["majority"] == 5:
        triggered.append("T1")
    if t2.get("available") and t2["majority"] >= 7:
        triggered.append("T2")
    if p_all < 0.05:
        triggered.append("T3")

    disc_rate = (nb + nc) / n_paired if n_paired else 0.0
    mde = mde_at_n(args.n_cap, disc_rate)
    p_b_obs = nb / (nb + nc) if (nb + nc) else 0.5
    need_disc = n_needed_for_power(p_b_obs)
    need_paired = (math.ceil(need_disc / disc_rate) if need_disc > 0 and disc_rate > 0
                   else -1)

    out = {
        "n_paired_now": n_paired,
        "arrival_sequence": letters,
        "b_only": nb, "c_only": nc,
        "mcnemar_exact_p_two_sided": p_all,
        "tail_test_5": t1, "tail_test_8": t2,
        "triggered": triggered,
        "verdict": "signal_worth_following" if triggered else "noise",
        "discordant_rate": disc_rate,
        "n_cap": args.n_cap,
        "mde_at_cap": mde,
        "observed_p_b": p_b_obs,
        "disc_pairs_needed_80pct_power": need_disc,
        "paired_tasks_needed_80pct_power": need_paired,
        "bench_size": args.bench_size,
        "reachable_with_bench": (0 < need_paired <= args.bench_size)
                                if need_paired > 0 else None,
    }

    print(f"配對數（目前）n = {n_paired}")
    print(f"discordant 到達序列（{len(letters)} 個）：{letters}")
    print(f"  b（只有 {args.a_arm} 對）={nb}   c（只有 {args.b_arm} 對）={nc}")
    print(f"  全序列 McNemar 精確雙尾 p = {p_all:.4f}")
    print()
    for t in (t1, t2):
        if t.get("available"):
            print(f"  最近 {t['k']} 個 = {t['tail']}  同向最多 {t['majority']}/{t['k']}"
                  f"  單尾 p = {t['p_one_sided']:.4f}")
        else:
            print(f"  最近 {t['k']} 個：序列不足，無法檢定")
    print(f"觸發的推翻條件：{triggered or '無'}  ⇒ 判定：{out['verdict']}")
    print()
    print(f"discordant rate = {100*disc_rate:.2f}%")
    if mde["min_gap"] is not None:
        print(f"n={args.n_cap} 時預期 discordant≈{mde['n_disc_expected']}，"
              f"要 p<0.05 最少要 {mde['min_split'][0]}:{mde['min_split'][1]} "
              f"（|b-c|≥{mde['min_gap']}）⇒ MDE = {mde['mde_pp']:.2f} pp")
    else:
        print(f"n={args.n_cap} 時預期 discordant≈{mde['n_disc_expected']}，"
              f"**任何分裂都達不到 p<0.05**")
    if need_disc > 0:
        print(f"若真實效果＝觀測值（p_b={p_b_obs:.3f}），80% power 需要 "
              f"{need_disc} 個 discordant pair ⇒ 約 {need_paired} 個配對任務")
        print(f"題庫只有 {args.bench_size} 題 ⇒ 可達？ {out['reachable_with_bench']}")
    else:
        print("觀測到的 p_b 正好 0.5，無法反推所需 n")

    if args.json:
        pathlib.Path(args.json).write_text(json.dumps(out, ensure_ascii=False, indent=2),
                                           encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
