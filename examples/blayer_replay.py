"""blayer_replay — 兩份 B 層歸檔的**逐格對帳**（RECORD_SPEC；13 §3）。

用途：改了 `vacant/blayer.py` 之後重跑一次，證明**改的是描述、不是數字**。
比的是兩份 `cells.jsonl` 共同擁有的欄位（`value`／`ci_lo`／`ci_hi`），
**新版多出來的欄位不比**——否則「加了欄位」永遠會被判成「數字變了」。

為什麼要有這支：`_sweep` 的亂數流是靠 seed 字串排出來的，任何在 `fn` 呼叫
之間插進去的隨機消費都會整條錯位，而錯位之後每一格仍然「看起來是個數字」。
第 36 輪踩過同一類的坑（`hash()` 被 PYTHONHASHSEED 鹽化 ⇒ CI 無法重放，
而 determinism 測試剛好沒測到）。所以對帳要逐格、要印出不同的那幾格，
不是回一個 True。

用法：
    PYTHONPATH=. python3 examples/blayer_replay.py runs/blayer_1000_v2 runs/blayer_1000_v3
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

CMP_FIELDS = ("value", "ci_lo", "ci_hi")


def load(run_dir: Path) -> dict[tuple[str, str, float], dict]:
    p = run_dir / "cells.jsonl"
    out: dict[tuple[str, str, float], dict] = {}
    for line in p.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        k = (r["scenario"], r["arm"], float(r["ratio"]))
        if k in out:
            raise SystemExit(f"❌ {p} 有重複鍵 {k}——歸檔本身壞了，先修那個")
        out[k] = r
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="兩份 B 層歸檔逐格對帳")
    ap.add_argument("a")
    ap.add_argument("b")
    args = ap.parse_args()

    A, B = load(Path(args.a)), load(Path(args.b))
    only_a = sorted(set(A) - set(B))
    only_b = sorted(set(B) - set(A))
    both = sorted(set(A) & set(B))

    diffs = []
    for k in both:
        for f in CMP_FIELDS:
            if A[k][f] != B[k][f]:
                diffs.append((k, f, A[k][f], B[k][f]))

    print(f"A={args.a}（{len(A)} 格） B={args.b}（{len(B)} 格） 共同 {len(both)} 格")
    print(f"比對欄位：{CMP_FIELDS}（新版多出的欄位不比）")
    for k in only_a:
        print(f"  ⚠ 只在 A：{k}")
    for k in only_b:
        print(f"  ⚠ 只在 B：{k}")
    for k, f, va, vb in diffs[:40]:
        print(f"  ❌ {k} {f}: A={va} B={vb}")
    ok = not diffs and not only_a and not only_b
    print(f"逐格相同：{len(both) - len({d[0] for d in diffs})}/{len(both)}"
          f"{' ✅' if ok else ' ❌'}")

    # 新版多出來的描述欄，順便印一份摘要——它們是這次改動的**目的**，
    # 對帳過了但欄位全是預設值的話，等於改了個寂寞。
    extra = sorted(set(next(iter(B.values()))) - set(next(iter(A.values()))))
    if extra:
        degen = [k for k in B if B[k].get("n_unique") == 1]
        print(f"B 多出的欄位：{extra}；其中 n_unique==1（CI 塌成一點）的格："
              f"{len(degen)}/{len(B)}")
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
