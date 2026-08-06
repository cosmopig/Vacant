"""E10 中介變數再分析——為什麼 p=0.332 描述的是量測而不是機制（2026-08-06）。

信任層直接控制的東西只有一個：**誰拿到這件工作**。通過率是它下游的結果，中間隔了
「這個交付者這次寫不寫得出來」那一層雜訊。量下游會把訊號稀釋掉，而中介變數
（有沒有被路由給已知的破壞者）一直躺在 `rows.jsonl` 的 `deliverer` 欄位裡。

這支還處理第二件事：**這個機制要學**。信任層一開始不知道誰是誰，得先發工作、看結果、
才知道要避開誰。把整段 run 平均起來等於把「還沒學會」跟「已經學會」混在一起——對會
學習的機制，混合估計必然偏向零。所以這裡掃描燒機期長度，看結論對切點穩不穩。

**這支的產出是設計診斷，不是結論。** 燒機期是看過曲線之後才切的，那正是研究者自由度
會膨脹偽陽性的情境；任何 p 值都要等寫進預註冊、在新資料上重跑才算數。E10 已公布的
主要結果仍是 McNemar p=0.332 不顯著，那一條不撤。

零機時：只讀已歸檔的 JSONL，不呼叫任何模型。
"""
from __future__ import annotations

import collections
import json
import math
from pathlib import Path

E10 = Path.home() / (
    "Library/Mobile Documents/com~apple~CloudDocs"
    "/專題/實驗記錄/真模型_2026-07-26/E10"
)

# roster 上唯一撐得住的標籤。good/mediocre 的標籤沒有經過驗證——見本檔尾端的
# 每交付者表，`good_3` 在一臂 92%、另一臂 33%，以那個樣本數幾乎全是雜訊。
IS_BAD = lambda row: "saboteur" in row["deliverer"]


def load(arm: str) -> list[dict]:
    rows = [json.loads(l) for l in (E10 / arm / "rows.jsonl").open()]
    return sorted(rows, key=lambda r: r["i"])


def mcnemar_exact(b: int, c: int) -> float:
    """配對二元的精確檢定（雙尾二項）。n 小，不用常態近似。"""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    return min(1.0, 2 * sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n)


def fisher_exact(a: int, b: int, c: int, d: int) -> float:
    """雙尾 Fisher 精確檢定，作為非配對的對照。"""
    def lc(n: int, k: int) -> float:
        return math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1)

    n, r1, c1 = a + b + c + d, a + b, a + c
    p = lambda x: math.exp(lc(r1, x) + lc(n - r1, c1 - x) - lc(n, c1))
    obs = p(a)
    lo, hi = max(0, c1 - (n - r1)), min(r1, c1)
    return sum(p(x) for x in range(lo, hi + 1) if p(x) <= obs * (1 + 1e-9))


def paired(off: list[dict], on: list[dict], pred) -> tuple[int, int]:
    """回傳 (只有 off 命中, 只有 on 命中) —— McNemar 的兩格。"""
    b = sum(1 for x, y in zip(off, on) if pred(x) and not pred(y))
    c = sum(1 for x, y in zip(off, on) if pred(y) and not pred(x))
    return b, c


def main() -> None:
    off, on = load("off"), load("on")
    assert [r["task_id"] for r in off] == [r["task_id"] for r in on], (
        "兩臂的題目順序不一致，配對檢定不成立")
    n = len(off)

    print(f"配對題數 n = {n}\n")

    print("=== 換量測對象：中介 vs 結果 ===")
    for label, pred in (("路由給破壞者（中介）", IS_BAD),
                        ("通過（結果）", lambda r: r["passed"])):
        so, sn = sum(map(pred, off)), sum(map(pred, on))
        b, c = paired(off, on, pred)
        print(f"  {label:20s} off {so:2d}/{n} = {so/n:5.1%}   on {sn:2d}/{n} = {sn/n:5.1%}"
              f"   McNemar p = {mcnemar_exact(b, c):.4f}")
    # 健全性：off 是確定性隨機，6 人含 2 破壞者 → 期望 33.3%
    print(f"  （對照臂健全性檢查：roster 2/6 = 33.3%，實測 "
          f"{sum(map(IS_BAD, off))/n:.1%}）")

    print("\n=== 換時間窗口：燒機期敏感度 ===")
    print("  去掉前 k 題後，中介變數的配對檢定")
    print(f"  {'k':>3} {'剩餘':>5} {'off':>7} {'on':>7} {'McNemar p':>11}")
    for k in range(0, 45, 5):
        a, z = off[k:], on[k:]
        m = len(a)
        so, sn = sum(map(IS_BAD, a)), sum(map(IS_BAD, z))
        b, c = paired(a, z, IS_BAD)
        star = " *" if mcnemar_exact(b, c) < 0.05 else ""
        print(f"  {k:3d} {m:5d} {so/m:7.1%} {sn/m:7.1%} {mcnemar_exact(b, c):11.4f}{star}")

    seq = lambda rows: "".join("X" if IS_BAD(r) else "." for r in rows)
    print(f"\n  off: {seq(off)}")
    print(f"  on:  {seq(on)}")
    tail = lambda rows: next((i for i, r in enumerate(reversed(rows)) if IS_BAD(r)), len(rows))
    print(f"  尾端連續未路由給破壞者：off {tail(off)} 題、on {tail(on)} 題")

    print("\n=== 可得空間 ===")
    sab_on = sum(map(IS_BAD, on))
    clean_pass = sum(1 for r in on if not IS_BAD(r) and r["passed"])
    clean_rate = clean_pass / (n - sab_on)
    ideal = (clean_pass + sab_on * clean_rate) / n
    base, got = sum(r["passed"] for r in off) / n, sum(r["passed"] for r in on) / n
    print(f"  on 臂非破壞者交付通過率 = {clean_pass}/{n - sab_on} = {clean_rate:.1%}")
    print(f"  若完全避開破壞者，預期通過率 ≈ {ideal:.1%}")
    print(f"  可得提升 {ideal - base:+.1%}   實得提升 {got - base:+.1%}"
          f"   捕捉比例 {(got - base) / (ideal - base):.0%}")
    print("  （上界略樂觀：clean_rate 是在路由器自己挑去給乾淨代理的題目上量的。）")

    print("\n=== 每交付者（兩臂題目分配不同，跨臂通過率不可直接比）===")
    for arm, rows in (("off", off), ("on", on)):
        cnt = collections.Counter(r["deliverer"] for r in rows)
        print(f"  {arm}:")
        for who, k in sorted(cnt.items()):
            ok = sum(1 for r in rows if r["deliverer"] == who and r["passed"])
            print(f"    {who:12s} {k:3d} 次  通過 {ok:3d}  ({ok/k:.0%})")
    print("\n  結論：唯一撐得住的標籤是 saboteur。E10 實際上是二類偵測問題，"
          "不是品質排序問題——這正是中介變數才是對的量測對象的原因。")


if __name__ == "__main__":
    main()
