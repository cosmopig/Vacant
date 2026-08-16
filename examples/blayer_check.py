"""B 層歸檔包的**事後判準**：CI 分不分得開、重跑重不重現、包合不合格。

為什麼另外寫一支而不是加進 `vacant/blayer.py`：那支裡的 `_verdict` 六條是
13 §3 訂的預註冊，改它就不是預註冊了。這裡三條（B-CI／B-DET／B-PACK）是
**外加的、更嚴的**問法，跟那六條各自獨立成立或不成立——`_verdict` 比的是
點值，而「拆掉它數字必須變」這句話真正要的是**區間分得開**。

ratio 不是這支挑的，是照 `blayer._verdict` 的原始碼抄的（見 `CITED_RATIO`）：
挑格子就是挑一個會過的判準。

selftest 先跑：量具要先在**已知答案**上答對（一定重疊的、一定不重疊的），
再拿去量未知的。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
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


def disjoint(a: tuple[float, float], b: tuple[float, float]) -> bool:
    """兩個閉區間**不重疊**？（端點相接算重疊——分不開就是分不開）"""
    return a[1] < b[0] or b[1] < a[0]


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
    return ok


def load_cells(run_dir: Path) -> dict[tuple[str, str, float], dict]:
    out = {}
    with (run_dir / "cells.jsonl").open(encoding="utf-8") as f:
        for line in f:
            c = json.loads(line)
            out[(c["scenario"], c["arm"], round(c["ratio"], 6))] = c
    return out


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

    print("\nB-N（每格 seeds ＝ 17 §P4 的 ≥1000）：")
    bad = sorted({c["n_seeds"] for c in cells.values()} - {args.expect_seeds})
    n_ok = not bad
    ok = ok and n_ok
    print(f"  {'✅' if n_ok else '❌'} {len(cells)} 格，n_seeds "
          f"{'全部 = ' + str(args.expect_seeds) if n_ok else '出現 ' + str(bad)}")

    if args.replica:
        print("\nB-DET（同 base-seed 重跑，cells.jsonl sha256 逐字元相同）：")
        h1 = hashlib.sha256((run_dir / "cells.jsonl").read_bytes()).hexdigest()
        h2 = hashlib.sha256((Path(args.replica) / "cells.jsonl").read_bytes()).hexdigest()
        d_ok = h1 == h2
        ok = ok and d_ok
        print(f"  {'✅' if d_ok else '❌'} {h1}\n     {'' if d_ok else '≠ '}{h2}")

    print("\nB-PACK（CLAUDE.md 紀錄紅線：不 pack ＝ 沒跑過）：")
    from vacant.record import check
    p_ok, problems = check(run_dir)
    ok = ok and p_ok
    print(f"  {'✅' if p_ok else '❌'} ok={p_ok} problems={problems}")

    print(f"\n總判：{'全過 ✅' if ok else '有失敗 ❌（照報，不放寬）'}")
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    sys.exit(main())
