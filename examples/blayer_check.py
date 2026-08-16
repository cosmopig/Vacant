"""B 層歸檔包的**事後判準**：CI 分不分得開、重跑重不重現、包合不合格。

為什麼另外寫一支而不是加進 `vacant/blayer.py`：那支裡的 `_verdict` 六條是
13 §3 訂的預註冊，改它就不是預註冊了。這裡三條（B-CI／B-DET／B-PACK）是
**外加的、更嚴的**問法，跟那六條各自獨立成立或不成立——`_verdict` 比的是
點值，而「拆掉它數字必須變」這句話真正要的是**區間分得開**。

ratio 不是這支挑的，是照 `blayer._verdict` 的原始碼抄的（見 `CITED_RATIO`）：
挑格子就是挑一個會過的判準。

而「挑格子」這句話對 B-CI 自己一樣成立——只驗那 6 格，「其他 42 對其實分不開」
永遠不會浮出來。所以另外有 **B-CI-48**：把 6 情境 × 8 ratio 的 48 對全部掃一遍。
它**不是及格閘門**（`ratio=0` 沒注入攻擊，on/off 本來就該一樣，要它分開才是 bug），
是描述；閘門仍然只有 `CITED_RATIO` 那 6 格，沒有放寬也沒有換格。

selftest 先跑：量具要先在**已知答案**上答對（一定重疊的、一定不重疊的），
再拿去量未知的。B-CI-48 的掃描函式也一樣，先在三個合成 fixture
（全分得開／全分不開／事先算好的混合）上答對才准拿去量真資料。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

# 照 vacant/blayer.py `_verdict` 抄的：每個情境的判準自己引用哪一格。
CITED_RATIO = {
    "sig_attribution": 0.7,
    "same_source": 0.7,
    "probation_whitewash": 0.7,
    "reviewer_stake": 0.7,
    "decay_slash": 0.7,
    "memory_wipe": 0.5,
}


# 同樣照 `vacant/blayer.py` 的原始碼抄的：**這些格根本沒有跑機制**，
# 情境函式在算之前就 `return 0.0`（不是「跑了、量到 0」）。
#   same_source         L167 `if ratio < 0.5: return 0.0`（克隆團要 ≥5 人才成群）
#   probation_whitewash L247 `n_white = round(7*ratio); if not whites: return 0.0`
#   memory_wipe         L315 `n_fam  = round(20*ratio); if n_fam == 0: return 0.0`
#   sig_attribution     L133 `forged = round(10*ratio)` ⇒ ratio=0 灌 0 票（無早退但無攻擊）
# 為什麼要單獨列：`cells.jsonl` 六個情境都是齊頭 8 格，**「沒量」與「量了得 0」
# 在歸檔裡長得一模一樣**。不點名的話，這張網格看起來覆蓋 0→70%，實際上沒有。
NOT_MEASURED = {
    "same_source": (0.1, 0.2, 0.3, 0.4),   # ratio=0 另由 Q-ZERO 管，不重複計
}


def disjoint(a: tuple[float, float], b: tuple[float, float]) -> bool:
    """兩個閉區間**不重疊**？（端點相接算重疊——分不開就是分不開）"""
    return a[1] < b[0] or b[1] < a[0]


# B-CI-48 的四種結局。**`sep_degen` 要跟 `sep` 分開數**：CI 寬度 0 表示
# bootstrap 重抽到的全是同一個值，而 bootstrap 對全同值樣本會低估不確定性
# ——0/1000 的真 95% 上界約 3/1000（rule of three），不是 0。靠零寬 CI 得到的
# 「分得開」是最弱的那一種，不能跟有變異的 disjoint 混為一談。
KINDS = {
    "sep": "分得開（兩邊 CI 都有寬度）",
    "sep*": "分得開，但至少一邊 CI 寬度為 0（見 rule of three 註）",
    "ovl": "分不開（CI 重疊，點值不同）",
    "same": "完全相同（點值與兩端點都一樣 ⇒ 這一格 on/off 沒有任何差別）",
    "miss": "缺格",
}


def _rule_of_three(n: int) -> float:
    """全 0（或全同值）樣本的保守 95% 上界 ≈ 3/n。用來說明零寬 CI 有多假。"""
    return 3.0 / n if n else float("inf")


def pair_scan(cells: dict[tuple[str, str, float], dict]) -> list[dict]:
    """B-CI-48：對 `cells` 裡出現的每一個 (scenario, ratio) 比一次 on vs off。

    回傳每對一筆，含 `kind`（見 `KINDS`）與 `gap`（正＝相距，負＝重疊多少）。
    順序照 `cells` 的插入順序（＝`cells.jsonl` 的行序），不重新排序——
    重排會讓兩輪之間的表對不起來。
    """
    seen: list[tuple[str, float]] = []
    for sc, _arm, r in cells:
        if (sc, r) not in seen:
            seen.append((sc, r))

    out: list[dict] = []
    for sc, r in seen:
        on, off = cells.get((sc, "on", r)), cells.get((sc, "off", r))
        if on is None or off is None:
            out.append({"scenario": sc, "ratio": r, "kind": "miss", "gap": None,
                        "on": None, "off": None, "n_seeds": None})
            continue
        a, b = (on["ci_lo"], on["ci_hi"]), (off["ci_lo"], off["ci_hi"])
        d = disjoint(a, b)
        degen = a[0] == a[1] or b[0] == b[1]
        if d:
            kind = "sep*" if degen else "sep"
        elif on["value"] == off["value"] and a == b:
            kind = "same"
        else:
            kind = "ovl"
        gap = (b[0] - a[1]) if a[1] < b[0] else (a[0] - b[1])
        out.append({"scenario": sc, "ratio": r, "kind": kind, "gap": gap,
                    "on": on["value"], "off": off["value"],
                    "on_ci": a, "off_ci": b, "degenerate": degen,
                    "n_seeds": on.get("n_seeds")})
    return out


def _fixture(specs: list[tuple[str, float, str]]) -> dict[tuple, dict]:
    """合成已知答案的 cells。`want` ∈ {sep, sep*, ovl, same}，直接照定義擺數字。"""
    cells: dict[tuple, dict] = {}
    for sc, r, want in specs:
        if want == "sep":       on, off = (1.0, 0.9, 1.1), (5.0, 4.9, 5.1)
        elif want == "sep*":    on, off = (0.0, 0.0, 0.0), (5.0, 4.9, 5.1)
        elif want == "ovl":     on, off = (1.0, 0.5, 2.0), (1.5, 1.0, 3.0)
        elif want == "same":    on, off = (2.0, 1.0, 3.0), (2.0, 1.0, 3.0)
        else:                   raise ValueError(want)
        for arm, (v, lo, hi) in (("on", on), ("off", off)):
            cells[(sc, arm, r)] = {"scenario": sc, "arm": arm, "ratio": r,
                                   "n_seeds": 1000, "value": v, "ci_lo": lo, "ci_hi": hi}
    return cells


def selftest() -> bool:
    """已知答案兩題。答錯就不准拿去量真資料。"""
    cases = [
        ("已知重疊（同一個區間跟自己比）", (0.0, 0.0), (0.0, 0.0), False),
        ("已知重疊（部分交疊）", (0.0, 3.0), (2.5, 7.0), False),
        ("已知不重疊", (0.0, 0.0), (5.0, 7.0), True),
        ("已知不重疊（反向）", (5.0, 7.0), (0.0, 0.0), True),
        ("端點相接＝重疊", (0.0, 2.0), (2.0, 4.0), False),
    ]
    ok = True
    for label, a, b, want in cases:
        got = disjoint(a, b)
        mark = "✅" if got == want else "❌"
        if got != want:
            ok = False
        print(f"  {mark} {label}: disjoint({a},{b}) = {got}（要 {want}）")

    # xcheck 的已知答案：一定一致的、一定不一致的、一定缺格的
    base = {("s", "on", 0.0): {"n_seeds": 8, "value": 1.0, "ci_lo": 0.9, "ci_hi": 1.1}}
    drift = {("s", "on", 0.0): {"n_seeds": 8, "value": 1.000001, "ci_lo": 0.9, "ci_hi": 1.1}}
    for label, a, b, want in [
        ("已知一致（同一份跟自己比）", base, base, True),
        ("已知不一致（value 差 1e-6）", base, drift, False),
        ("已知缺格（右邊是空的）", base, {}, False),
    ]:
        got = xcheck(a, b)[0]
        mark = "✅" if got == want else "❌"
        if got != want:
            ok = False
        print(f"  {mark} {label}: xcheck = {got}（要 {want}）")

    # pair_scan 的已知答案三題（Q-PROBE）。量具答不對這三題，B-CI-48 的
    # 「42 對裡有 k 對分不開」就只是一個沒有來源的數字。
    all_sep = [(f"s{i}", i / 10, "sep") for i in range(48)]
    all_ovl = [(f"s{i}", i / 10, "ovl") for i in range(48)]
    #                                    ↓ 事先算好：sep 5、sep* 3、ovl 2、same 4
    mixed = ([("m", i / 100, "sep") for i in range(5)]
             + [("m", 1 + i / 100, "sep*") for i in range(3)]
             + [("m", 2 + i / 100, "ovl") for i in range(2)]
             + [("m", 3 + i / 100, "same") for i in range(4)])
    for label, specs, want in [
        ("已知全部分得開", all_sep, {"sep": 48}),
        ("已知全部分不開", all_ovl, {"ovl": 48}),
        ("已知混合（事先算好）", mixed, {"sep": 5, "sep*": 3, "ovl": 2, "same": 4}),
    ]:
        got = dict(Counter(p["kind"] for p in pair_scan(_fixture(specs))))
        mark = "✅" if got == want else "❌"
        if got != want:
            ok = False
        print(f"  {mark} {label}: pair_scan = {got}（要 {want}）")

    # 缺格不准被算成「分不開」——靜默吞掉缺格會讓 42 對變成一個樂觀的分母。
    holed = _fixture([("h", 0.0, "sep")])
    del holed[("h", "off", 0.0)]
    got_miss = pair_scan(holed)[0]["kind"]
    mark = "✅" if got_miss == "miss" else "❌"
    if got_miss != "miss":
        ok = False
    print(f"  {mark} 已知缺格: pair_scan = {got_miss!r}（要 'miss'）")
    return ok


def _index(rows: list[dict], label: str) -> tuple[dict[tuple, dict], list[str]]:
    """照 (scenario, arm, ratio) 建索引。**重複鍵要點名**——直接塞 dict 會
    靜默吃掉重複，而「重複鍵」正是第 36 輪 arm 標錯時的可見症狀。"""
    out: dict[tuple, dict] = {}
    dup: list[str] = []
    for c in rows:
        k = (c["scenario"], c["arm"], round(c["ratio"], 6))
        if k in out:
            dup.append(f"{label} 重複鍵 {k}")
        out[k] = c
    return out, dup


def load_cells(run_dir: Path) -> dict[tuple[str, str, float], dict]:
    rows = [json.loads(l) for l in
            (run_dir / "cells.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    return _index(rows, "cells.jsonl")[0]


def load_ledger_cells(run_dir: Path) -> list[dict]:
    """事件帳裡的 CELL 事件（RUN_START／VERDICT／RUN_END 不算格子）。"""
    rows = [json.loads(l) for l in
            (run_dir / "ledger_events.jsonl").read_text(encoding="utf-8").splitlines()
            if l.strip()]
    return [r for r in rows if r.get("type") == "B_LAYER_CELL"]


# 兩份歸檔對同一格必須說同一件事的欄位。
XCHK_FIELDS = ("n_seeds", "value", "ci_lo", "ci_hi")


def xcheck(a: dict[tuple, dict], b: dict[tuple, dict]) -> tuple[bool, list[str]]:
    """P-XCHK：`cells.jsonl` 與 `ledger_events.jsonl` 對同一格說的話一致嗎？

    為什麼要問：這是兩條**各自寫檔**的路徑（一條跑完寫、一條邊跑邊寫）。
    HANDOFF §8 最後一條——兩份程式各自被正確地修改了不同次數，漂移就發生了，
    不需要有人犯錯。第 36 輪的 arm 標錯就是這個形狀。
    """
    problems = []
    only_a, only_b = sorted(set(a) - set(b)), sorted(set(b) - set(a))
    if only_a:
        problems.append(f"cells.jsonl 有而 ledger 沒有的格 {len(only_a)}：{only_a[:3]}")
    if only_b:
        problems.append(f"ledger 有而 cells.jsonl 沒有的格 {len(only_b)}：{only_b[:3]}")
    for k in sorted(set(a) & set(b)):
        diff = {f: (a[k].get(f), b[k].get(f))
                for f in XCHK_FIELDS if a[k].get(f) != b[k].get(f)}
        if diff:
            problems.append(f"{k} 兩份不一致：{diff}")
    return (not problems), problems


def main() -> None:
    ap = argparse.ArgumentParser(description="B 層歸檔包的事後判準")
    ap.add_argument("run_dir", nargs="?", default="runs/blayer_1000")
    ap.add_argument("--replica", default=None,
                    help="獨立重跑的目錄（B-DET：cells.jsonl sha256 要逐字元相同）")
    ap.add_argument("--expect-seeds", type=int, default=1000)
    ap.add_argument("--selftest-only", action="store_true")
    args = ap.parse_args()

    print("探針自驗（已知答案）：")
    st = selftest()
    print(f"  {'✅ 兩邊都答對' if st else '❌ 量具壞了 —— 不報 B-CI'}")
    if args.selftest_only:
        raise SystemExit(0 if st else 1)
    if not st:
        raise SystemExit(1)

    run_dir = Path(args.run_dir)
    cells = load_cells(run_dir)
    ok = True

    print("\nB-CI（on／off 的 95% CI 不重疊，格子照 _verdict 引用的那一格）：")
    for name, ratio in CITED_RATIO.items():
        on = cells.get((name, "on", ratio))
        off = cells.get((name, "off", ratio))
        if on is None or off is None:
            print(f"  ❌ {name:22s} ratio={ratio} 找不到格子")
            ok = False
            continue
        a = (on["ci_lo"], on["ci_hi"])
        b = (off["ci_lo"], off["ci_hi"])
        d = disjoint(a, b)
        ok = ok and d
        gap = (b[0] - a[1]) if a[1] < b[0] else (a[0] - b[1])
        print(f"  {'✅' if d else '❌'} {name:22s} r={ratio}  "
              f"on {on['value']:.4f} [{a[0]:.4f},{a[1]:.4f}]  "
              f"off {off['value']:.4f} [{b[0]:.4f},{b[1]:.4f}]  gap={gap:+.4f}")

    print("\nB-CI-48（全部 48 對；**描述不是閘門**——ratio=0 沒注入攻擊，"
          "on/off 本來就該一樣）：")
    pairs = pair_scan(cells)
    by_sc: dict[str, list[dict]] = {}
    for p in pairs:
        by_sc.setdefault(p["scenario"], []).append(p)
    ratios = sorted({p["ratio"] for p in pairs})
    print("       " + " ".join(f"{r:>5.1f}" for r in ratios))
    for sc, ps in by_sc.items():
        # `n/m` 是**原始碼來源**的標註（NOT_MEASURED），不是從數字猜的——
        # 從 cells.jsonl 分不出「沒量」與「量了得 0」，那正是問題本身。
        row = {p["ratio"]: ("n/m" if p["ratio"] in NOT_MEASURED.get(sc, ())
                            else p["kind"]) for p in ps}
        print(f"  {sc:22s} " + " ".join(f"{row.get(r, '-'):>5s}" for r in ratios))
    tally = Counter(p["kind"] for p in pairs)
    print(f"  合計 {len(pairs)} 對：" +
          "、".join(f"{k}={tally.get(k, 0)}" for k in KINDS))
    for k, desc in KINDS.items():
        if tally.get(k):
            print(f"     {k:5s} {desc}")

    # Q-ZERO：ratio=0 ＝ 沒注入攻擊，分開了就是情境函式有 bug。**這條是閘門**
    # （比原本嚴，不是放寬）——它問的是「情境函式對不對」，不是「機制有沒有效」。
    z_bad = [p for p in pairs if p["ratio"] == 0.0 and p["kind"] in ("sep", "sep*")]
    z_ok = not z_bad
    ok = ok and z_ok
    print(f"\nQ-ZERO（ratio=0 的 {sum(1 for p in pairs if p['ratio'] == 0.0)} 對"
          f"必須分不開）：{'✅ 全部分不開' if z_ok else '❌ 沒注入攻擊卻分開了'}")
    for p in z_bad:
        print(f"     ❌ {p['scenario']} on={p['on']} off={p['off']}")

    # Q-DEGEN：靠零寬 CI 得到的 disjoint 要另外標，它是最弱的那一種。
    nz = [p for p in pairs if p["ratio"] > 0.0]
    n_sep = sum(1 for p in nz if p["kind"] == "sep")
    n_sepd = sum(1 for p in nz if p["kind"] == "sep*")
    n = next((p["n_seeds"] for p in pairs if p["n_seeds"]), args.expect_seeds)
    print(f"\nQ-DEGEN／Q-PRED（ratio≥0.1 的 {len(nz)} 對；**分母照事先預測寫死**）："
          f"分得開 {n_sep + n_sepd} 對，其中 {n_sepd} 對靠零寬 CI（sep*）；"
          f"分不開 {len(nz) - n_sep - n_sepd} 對")

    # 沒跑機制的格要點名，但**不准拿去改 Q-PRED 的分母**——事後換分母
    # 剛好會讓數字變好看，那正是「做完再想判準」的形狀。兩個數字都印。
    nm = [p for p in nz if p["ratio"] in NOT_MEASURED.get(p["scenario"], ())]
    if nm:
        real = [p for p in nz if p not in nm]
        r_sep = sum(1 for p in real if p["kind"] in ("sep", "sep*"))
        print(f"     ⚠ 其中 {len(nm)} 對**根本沒跑機制**（情境函式早退回 0，見 "
              f"NOT_MEASURED）：" + "、".join(f"{p['scenario']}@{p['ratio']}" for p in nm))
        print(f"       ⇒ 真正量過的是 {len(real)} 對，{r_sep} 對分得開。"
              f"**Q-PRED 仍以事先寫死的 {len(nz)} 對為準**（{n_sep + n_sepd}/{len(nz)}）；"
              f"換分母只會讓數字變好看，不採用。")
        print(f"       ⇒ 真正的後果是**覆蓋率**：這張網格看起來掃了 0→70%，"
              f"same_source 實際只有 3 個操作點有資料。")
    if n_sepd:
        print(f"     ⚠ 零寬 CI 的 rule-of-three 保守上界 ≈ 3/{n} = "
              f"{_rule_of_three(n):.4f}，不是 0。**sep* 是最弱的那種分得開。**")
    print("     ⚠ CI 重疊 ≠ 沒有差異（差值的 CI 才是對的問法）；48 對＝48 次比較，"
          "本輪未做多重比較校正 ⇒ 這張表是探索性描述，不是 48 個檢定。")

    print("\nB-N（每格 seeds ＝ 17 §P4 的 ≥1000）：")
    bad = sorted({c["n_seeds"] for c in cells.values()} - {args.expect_seeds})
    n_ok = not bad
    ok = ok and n_ok
    print(f"  {'✅' if n_ok else '❌'} {len(cells)} 格，n_seeds "
          f"{'全部 = ' + str(args.expect_seeds) if n_ok else '出現 ' + str(bad)}")

    print("\nP-XCHK（cells.jsonl 與 ledger_events.jsonl 對同一格說同一件事）：")
    led_rows = load_ledger_cells(run_dir)
    led, dup = _index(led_rows, "ledger")
    arms = Counter(k[1] for k in led)
    x_ok, x_problems = xcheck(cells, led)
    x_ok = x_ok and not dup
    ok = ok and x_ok
    print(f"  {'✅' if x_ok else '❌'} ledger CELL {len(led_rows)} 筆／"
          f"cells.jsonl {len(cells)} 行；arm {dict(arms)}；重複鍵 {len(dup)}")
    for p in x_problems + dup:
        print(f"     ❌ {p}")

    if args.replica:
        print("\nB-DET（同 base-seed 重跑，cells.jsonl sha256 逐字元相同）：")
        h1 = hashlib.sha256((run_dir / "cells.jsonl").read_bytes()).hexdigest()
        h2 = hashlib.sha256((Path(args.replica) / "cells.jsonl").read_bytes()).hexdigest()
        d_ok = h1 == h2
        ok = ok and d_ok
        print(f"  {'✅' if d_ok else '❌'} {h1}\n     {'' if d_ok else '≠ '}{h2}")

        print("\nP-DET-LEDGER（事件帳去掉 ts_ms 後逐字元相同）：")
        # ts_ms 是真的牆鐘時間、本來就不會一樣——事件帳的時間欄位是紀錄不是
        # 計算結果。去掉它之後**其餘全部**必須可重放，否則 CI/value 就漂了。
        def _strip(d: Path) -> str:
            rows = [json.loads(l) for l in
                    (d / "ledger_events.jsonl").read_text(encoding="utf-8").splitlines()
                    if l.strip()]
            body = [json.dumps({k: v for k, v in r.items() if k != "ts_ms"},
                               ensure_ascii=False, sort_keys=True) for r in rows]
            return hashlib.sha256("\n".join(body).encode()).hexdigest()
        g1, g2 = _strip(run_dir), _strip(Path(args.replica))
        l_ok = g1 == g2
        ok = ok and l_ok
        print(f"  {'✅' if l_ok else '❌'} {g1}\n     {'' if l_ok else '≠ '}{g2}")

    print("\nB-PACK（CLAUDE.md 紀錄紅線：不 pack ＝ 沒跑過）：")
    from vacant.record import check
    p_ok, problems = check(run_dir)
    ok = ok and p_ok
    print(f"  {'✅' if p_ok else '❌'} ok={p_ok} problems={problems}")

    print(f"\n總判：{'全過 ✅' if ok else '有失敗 ❌（照報，不放寬）'}")
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    sys.exit(main())
