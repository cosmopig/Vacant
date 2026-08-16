"""blayer_diff — B 層 48 對的**差值統計**（13 §3；17 §P4；19 號圖 L5 的 Holm 家族）。

第 36–38 輪一路用的是「on 的 CI 與 off 的 CI 重不重疊」。那個問法有兩個病：

1. **重疊 ≠ 沒有差異、不重疊 ≠ 有差異。** 對的問法是差值本身的區間——
   兩條各自的 CI 可以重疊而差值的 CI 仍不含 0。
2. **48 對＝48 次比較，沒有校正。** 第 38 輪把它誠實標成「探索性描述」，
   但標註不是校正。

這一支換成：`diff = mean(on) − mean(off)` 的 bootstrap 95% CI ＋ 置換檢定 p 值
＋ **Holm–Bonferroni**（`vacant/research.py` 已有，同一支函式不另寫）。

**資料來源是 `samples.jsonl` 的原始值**，不是 `cells.jsonl` 的三個摘要數。
只存 mean 與兩個端點，等於在落盤那一刻鎖死「之後還能問什麼問題」——
第 38 輪想算差值 CI 就因為原始值沒留而必須重跑整組 224s。

誠實邊界（跑之前就寫死，逐字進輸出）：

- 1000 顆種子是**模擬重複**不是母體抽樣。p 值回答的是「把 on/off 標籤打散，
  還會不會看到這麼大的差」，**不是**「這個機制在真實生態有效」。
- 六情境是確定性離線機制模擬（假腦、合成攻擊），驗機制承重不是生態效果。
- Holm 控的是族錯誤率，**不會**讓退化（兩邊皆常數）的格變成強證據——
  退化仍單獨點名（`degenerate`）。
- `same_source` 在 ratio<0.5 是 `return 0.0` 早退：那幾格**沒量**，不是量到 0。
  名單從 `blayer_check.NOT_MEASURED` 匯入，不在這裡另抄一份。

用法：
    PYTHONPATH=. python3 examples/blayer_diff.py --selftest-only
    PYTHONPATH=. python3 examples/blayer_diff.py runs/blayer_1000_v3
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from examples.blayer_check import NOT_MEASURED  # noqa: E402  單一真相來源
from vacant.blayer import RATIOS, SAMPLES_NAME, SCENARIOS  # noqa: E402
from vacant.research import holm_bonferroni  # noqa: E402

ALPHA = 0.05
N_BOOT = 2000
N_PERM = 10000

# 第 38 輪（B-CI-48）判「分不開」的 10 對，抄進來當**交叉檢查對象**：
# 換一套統計就該問「舊結論裡最弱的那部分會不會翻掉」，而不是只看新數字好不好看。
# 6 個 ratio=0（沒注入攻擊 ⇒ 本來就該分不開）＋ 4 個 same_source 的 n/m（沒量）。
PRIOR_UNSEPARABLE: tuple[tuple[str, float], ...] = tuple(
    [(sc, 0.0) for sc in SCENARIOS] + [("same_source", r) for r in (0.1, 0.2, 0.3, 0.4)]
)


def _mean(xs: list[float]) -> float:
    return sum(xs) / len(xs)


def diff_stats(on_vals: list[float], off_vals: list[float], *,
               n_boot: int = N_BOOT, n_perm: int = N_PERM, seed: int = 0) -> dict:
    """`mean(on) − mean(off)` 的 bootstrap 百分位 CI ＋ 雙尾置換檢定 p。

    兩臂的種子字串不同（`blayer._sweep` 把 `on` 寫進 seed）⇒ **不是配對樣本**，
    所以 bootstrap 是兩臂各自重抽、置換是把兩臂合併後重貼標籤。用配對法會
    假設一個不存在的配對關係，把區間算窄。

    p 值用 `(1+#{|perm| ≥ |obs|}) / (n_perm+1)`：分子加 1 是因為觀測到的那個
    排列本身也是排列之一，不加會讓 p 可以是 0，而檢定解析度不可能無限。
    """
    rng = random.Random(seed)
    n_on, n_off = len(on_vals), len(off_vals)
    obs = _mean(on_vals) - _mean(off_vals)

    boots: list[float] = []
    for _ in range(n_boot):
        a = sum(on_vals[rng.randrange(n_on)] for _ in range(n_on)) / n_on
        b = sum(off_vals[rng.randrange(n_off)] for _ in range(n_off)) / n_off
        boots.append(a - b)
    boots.sort()

    def pct(p: float) -> float:
        i = min(len(boots) - 1, max(0, int(round(p / 100.0 * (len(boots) - 1)))))
        return boots[i]

    lo, hi = pct(2.5), pct(97.5)

    pool = on_vals + off_vals
    tot = sum(pool)
    hit = 0
    eps = 1e-12
    for _ in range(n_perm):
        rng.shuffle(pool)
        s_on = sum(pool[:n_on])
        d = s_on / n_on - (tot - s_on) / n_off
        if abs(d) >= abs(obs) - eps:
            hit += 1
    p = (1 + hit) / (n_perm + 1)

    return {"diff": obs, "ci_lo": lo, "ci_hi": hi, "p": p,
            "ci_excludes_0": not (lo <= 0.0 <= hi),
            "ci_width": hi - lo,
            "degenerate": len(set(on_vals)) == 1 and len(set(off_vals)) == 1,
            "n_unique_on": len(set(on_vals)), "n_unique_off": len(set(off_vals))}


def _pair_seed(scenario: str, ratio: float) -> int:
    """種子由 (scenario, ratio) 的 sha256 決定——不用 `hash()`（PYTHONHASHSEED
    鹽化，每個行程不同 ⇒ 印出來的 CI 下一輪重放不出來，`blayer._sweep` 已踩過）。"""
    return int(hashlib.sha256(f"diff:{scenario}:{ratio}".encode()).hexdigest()[:8], 16)


# --- 探針自驗（先用已知答案的輸入考它，再拿去量未知的）------------------------
def selftest(*, n_boot: int = 400, n_perm: int = 2000) -> bool:
    """四個**答案事先知道**的 fixture。錯一個就 exit 1——不准拿沒驗過的尺去量。

    (a) 明顯有差   ：off 基準、on 全體 +5      → CI 不含 0、p 觸底
    (b) 樣本不同但無差：on 是 off 每個值 ±0.001 交錯（均值精確相等）
                        → 兩邊都有變異、CI 含 0、p 大。**不靠運氣**：
                          真差恰為 0，不是「抽到剛好沒差」
    (c) 兩邊各自恆定但值不同：舊法會判「零寬 sep*」（最弱的證據）；
                             新法 diff-CI 寬度也是 0，但**不含 0** ⇒ 這一格
                             真的有差，弱的是「不確定性被低估」不是「結論錯」
    (d) 兩邊同一個常數：diff=0、CI=[0,0] 含 0、p=1.0
    """
    base = [random.Random(f"probe:{i}").random() for i in range(1000)]
    cases = []

    a = diff_stats([x + 5 for x in base], base, n_boot=n_boot, n_perm=n_perm, seed=1)
    cases.append(("a 明顯有差", a,
                  abs(a["diff"] - 5.0) < 1e-9 and a["ci_excludes_0"]
                  and a["p"] <= 2.0 / (n_perm + 1) and not a["degenerate"]))

    on_b = [x + (0.001 if i % 2 == 0 else -0.001) for i, x in enumerate(base)]
    b = diff_stats(on_b, base, n_boot=n_boot, n_perm=n_perm, seed=2)
    cases.append(("b 樣本不同但無差", b,
                  abs(b["diff"]) < 1e-9 and not b["ci_excludes_0"]
                  and b["p"] > 0.05 and b["ci_width"] > 0))

    c = diff_stats([3.0] * 1000, [1.0] * 1000, n_boot=n_boot, n_perm=n_perm, seed=3)
    cases.append(("c 兩邊皆常數、值不同", c,
                  abs(c["diff"] - 2.0) < 1e-9 and c["ci_excludes_0"]
                  and c["ci_width"] == 0.0 and c["degenerate"]
                  and c["p"] <= 2.0 / (n_perm + 1)))

    d = diff_stats([0.0] * 1000, [0.0] * 1000, n_boot=n_boot, n_perm=n_perm, seed=4)
    cases.append(("d 兩邊同一常數", d,
                  d["diff"] == 0.0 and not d["ci_excludes_0"]
                  and d["ci_width"] == 0.0 and d["p"] == 1.0 and d["degenerate"]))

    # Holm 本身也考一題已知答案：[0.01, 0.02, 0.03] × m=3 step-down
    # → 0.03 / 0.04 / 0.03 →（單調化）0.03 / 0.04 / 0.04
    holm = holm_bonferroni([0.01, 0.02, 0.03])
    holm_ok = all(abs(x - y) < 1e-12 for x, y in zip(holm, [0.03, 0.04, 0.04]))
    cases.append(("e Holm 已知答案", {"adj": [round(x, 4) for x in holm]}, holm_ok))

    ok = True
    for name, got, passed in cases:
        ok = ok and passed
        brief = {k: (round(v, 6) if isinstance(v, float) else v)
                 for k, v in got.items() if k in ("diff", "ci_lo", "ci_hi", "p",
                                                  "ci_width", "degenerate", "adj")}
        print(f"  {'✅' if passed else '❌'} 探針 {name}: {brief}")
    print(f"探針自驗：{sum(1 for _, _, p in cases if p)}/{len(cases)}"
          f"{' ✅' if ok else ' ❌ ——尺是壞的，量出來的都不算'}")
    return ok


# --- 讀歸檔 -------------------------------------------------------------------
def load_samples(run_dir: Path) -> dict[tuple[str, str, float], list[float]]:
    p = run_dir / SAMPLES_NAME
    if not p.exists():
        raise SystemExit(
            f"❌ 找不到 {p}——這份歸檔是 2026-08-16 之前跑的（只有 cells.jsonl 的\n"
            f"   三個摘要數，沒有原始值）。差值統計算不了，要用新版 blayer 重跑。")
    out: dict[tuple[str, str, float], list[float]] = {}
    for line in p.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        out[(r["scenario"], r["arm"], float(r["ratio"]))] = r["values"]
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="B 層 48 對差值統計＋Holm 校正")
    ap.add_argument("run_dir", nargs="?", default=None)
    ap.add_argument("--selftest-only", action="store_true")
    ap.add_argument("--n-boot", type=int, default=N_BOOT)
    ap.add_argument("--n-perm", type=int, default=N_PERM)
    ap.add_argument("--alpha", type=float, default=ALPHA)
    args = ap.parse_args()

    print("=== 探針自驗（已知答案）===")
    if not selftest():
        raise SystemExit(1)
    if args.selftest_only:
        raise SystemExit(0)
    if not args.run_dir:
        raise SystemExit("用法：blayer_diff.py <run_dir>（或 --selftest-only）")

    run_dir = Path(args.run_dir)
    samples = load_samples(run_dir)

    pairs: list[tuple[str, float]] = []
    for sc in SCENARIOS:
        for r in RATIOS:
            if (sc, "on", r) in samples and (sc, "off", r) in samples:
                pairs.append((sc, r))

    print(f"\n=== 差值統計（{len(pairs)} 對；n_boot={args.n_boot}、"
          f"n_perm={args.n_perm}）===")
    rows = []
    for sc, r in pairs:
        st = diff_stats(samples[(sc, "on", r)], samples[(sc, "off", r)],
                        n_boot=args.n_boot, n_perm=args.n_perm,
                        seed=_pair_seed(sc, r))
        st.update(scenario=sc, ratio=r,
                  not_measured=r in NOT_MEASURED.get(sc, ()))
        rows.append(st)

    adj = holm_bonferroni([x["p"] for x in rows])
    for x, a in zip(rows, adj):
        x["p_adj"] = a
        x["sig"] = a < args.alpha

    # 一張 6×8：`+`＝Holm 後顯著、`.`＝不顯著、`*`＝顯著但兩邊皆常數（退化）、
    # `n`＝NOT_MEASURED（根本沒跑機制）。退化與非退化分開標，理由同第 38 輪。
    print("\n         " + "".join(f"{r:>6.1f}" for r in RATIOS))
    for sc in SCENARIOS:
        cells = []
        for r in RATIOS:
            x = next((y for y in rows if y["scenario"] == sc and y["ratio"] == r), None)
            if x is None:
                cells.append("  n/a")
            elif x["not_measured"]:
                cells.append("    n")
            elif x["sig"]:
                cells.append("    *" if x["degenerate"] else "    +")
            else:
                cells.append("    .")
        print(f"  {sc:22s}" + "".join(f"{c:>6s}" for c in cells))
    print("  + 顯著（Holm 後 adj p<%.2f）  * 顯著但兩邊皆常數（退化）"
          "  . 不顯著  n 沒量（NOT_MEASURED）" % args.alpha)

    n_sig = sum(1 for x in rows if x["sig"])
    n_degen_sig = sum(1 for x in rows if x["sig"] and x["degenerate"])
    n_ci = sum(1 for x in rows if x["ci_excludes_0"])
    print(f"\nHolm 後顯著 {n_sig}/{len(rows)}（其中 {n_degen_sig} 對兩邊皆常數＝退化）；"
          f"差值 CI 不含 0 者 {n_ci}/{len(rows)}")

    # --- 變異結構三分（D-DEGEN）------------------------------------------------
    # 第 38 輪的 `sep*` ＝「**至少一邊**零寬」，這裡的 `degenerate` ＝「**兩邊皆**常數」
    # ——兩個定義不同，31 與 21 不能互換著讀。所以三種都印出來，並把換算寫明。
    def _cls(x: dict) -> str:
        a, b = x["n_unique_on"] == 1, x["n_unique_off"] == 1
        return "both" if a and b else ("one" if a != b else "neither")

    buckets = {"both": [], "one": [], "neither": []}
    for x in rows:
        buckets[_cls(x)].append(x)
    print("\n變異結構三分（`sd`／`n_unique` 這次才存進歸檔，第 38 輪只能回頭讀原始碼）：")
    for k, label in (("both", "兩邊皆常數"), ("one", "恰一邊常數"),
                     ("neither", "兩邊都有變異")):
        b = buckets[k]
        print(f"  {label:6s} {len(b):2d} 對（其中顯著 {sum(1 for x in b if x['sig'])}）")
    at_least_one_sig = sum(1 for x in rows if x["sig"] and _cls(x) in ("both", "one"))
    print(f"  ⇒ 顯著的 {n_sig} 對裡「至少一邊零寬」＝ {at_least_one_sig} 對"
          f"（這才是可以跟第 38 輪那個 31 直接比的數）")

    print("\n=== 逐對明細（48 列）===")
    print(f"  {'scenario':20s} {'r':>4s} {'diff':>10s} {'ci_lo':>10s} {'ci_hi':>10s} "
          f"{'adj_p':>7s} {'uniq on/off':>12s}  結論")
    for x in rows:
        tag = ("沒量" if x["not_measured"] else
               ("顯著" if x["sig"] else "不顯著")
               + ("（兩邊皆常數）" if x["sig"] and x["degenerate"] else ""))
        print(f"  {x['scenario']:20s} {x['ratio']:4.1f} {x['diff']:10.4f} "
              f"{x['ci_lo']:10.4f} {x['ci_hi']:10.4f} {x['p_adj']:7.4f} "
              f"{x['n_unique_on']:5d}/{x['n_unique_off']:<6d} {tag}")
    print(f"單一 p 的解析度下限 1/{args.n_perm + 1} = {1 / (args.n_perm + 1):.5f}；"
          f"Holm 後下限 {len(rows) / (args.n_perm + 1):.5f}"
          f"（{'<' if len(rows) / (args.n_perm + 1) < args.alpha else '≥'} α={args.alpha}）")

    # --- 事先寫死的閘門（判準在 STATE.md 第 39 輪，做之前寫的）------------------
    gates: list[tuple[str, bool, str]] = []

    prior = [x for x in rows if (x["scenario"], x["ratio"]) in PRIOR_UNSEPARABLE]
    align = [x for x in prior if not x["sig"]]
    gates.append(("D-ALIGN 第38輪判分不開的 10 對，新法也不顯著",
                  len(align) == len(PRIOR_UNSEPARABLE) == len(prior),
                  f"{len(align)}/{len(PRIOR_UNSEPARABLE)}"))

    gates.append(("D-COUNT Holm 後顯著 ≥30 對", n_sig >= 30, f"{n_sig}/{len(rows)}"))

    nm = [x for x in rows if x["not_measured"]]
    nm_zero = [x for x in nm if x["diff"] == 0.0]
    gates.append(("D-NM 4 個 NOT_MEASURED 格被標出且 diff 恰為 0",
                  len(nm) == 4 and len(nm_zero) == 4, f"{len(nm_zero)}/4（共標出 {len(nm)}）"))

    print("\n=== 閘門（判準事先寫死）===")
    ok = True
    for name, passed, detail in gates:
        ok = ok and passed
        print(f"  {'✅' if passed else '❌'} {name}：{detail}")

    print("\n=== 誠實邊界（逐字，不是附註）===")
    for i, line in enumerate((
        "1000 顆種子是模擬重複不是母體抽樣 ⇒ p 值回答的是「把 on/off 標籤打散還會不會"
        "看到這麼大的差」，不是「機制在真實生態有效」。",
        "六情境是確定性離線機制模擬（假腦、合成攻擊），驗機制承重不是生態效果。",
        "Holm 控族錯誤率，不會讓退化格（兩邊皆常數）變強證據——退化仍單獨標 `*`。",
        "NOT_MEASURED 那幾格是「沒量」不是「量到 0」（same_source ratio<0.5 早退）。",
    ), 1):
        print(f"  {i}. {line}")

    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
