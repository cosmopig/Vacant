#!/usr/bin/env python3
"""R497 附錄（**事後，不在判準 §二 的表上，不改頭條判決**）。

理由：R489.analyse 只吃 `is_chat(r)` 的列，而判準 §二 的 ENDOGENOUS 三條是在
**全部**閘道列上算的（其中約七成是 GET 輪詢）⇒ 母體不同 ⇒ 那三格
**不能**當成「梯子量的那些量不隨位置動」的證據（memory：母體保真要用被測檔自己的過濾器）。
本檔用 R489 自己的過濾器重算同樣三條，結果**單獨報**。
"""
from __future__ import annotations
import json, pathlib, sys, statistics

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from ops.gain import r495_empirical_census as R495     # noqa: E402
from ops.gain import r496_equal_n_windows as R496      # noqa: E402
from ops.gain import r497_segment_composition as R497  # noqa: E402
from ops.gain import r489_permutation_placebo as R489  # noqa: E402

snap = json.loads((ROOT / R495.SNAPSHOT).read_text(encoding="utf-8"))
rows = sorted([r for r in snap["rows"] if r.get("ts") is not None], key=lambda r: r["ts"])
wins = R496.index_windows(len(rows))
print(f"全部列={len(rows)}  is_chat={sum(1 for r in rows if R489.is_chat(r))}  "
      f"is_analysable(chat 內)={sum(1 for r in rows if R489.is_chat(r) and R489.is_analysable(r))}")

DEFS = {
    "median_latency_ms": lambda rs: R497._median([r.get("latency_ms") for r in rs]),
    "mean_completion_tokens": lambda rs: R497._mean([r.get("completion_tokens") for r in rs]),
    "median_ms_per_tok": lambda rs: R497._median(
        [r["latency_ms"] / r["completion_tokens"] for r in rs
         if r.get("latency_ms") is not None and r.get("completion_tokens")]),
    "n_chat": lambda rs: float(len(rs)),
}
for filt_name, filt in (("chat", R489.is_chat),
                        ("chat+analysable", lambda r: R489.is_chat(r) and R489.is_analysable(r))):
    print(f"\n=== 母體 = {filt_name}")
    for name, fn in DEFS.items():
        vals, xs, ys = [], {}, {}
        for N, i, lo, hi in wins:
            sub = [r for r in rows[lo:hi] if filt(r)]
            v = fn(sub)
            vals.append(v)
            if v is not None:
                xs.setdefault(N, []).append(float(lo)); ys.setdefault(N, []).append(float(v))
        per = {N: R497.spearman(xs[N], ys[N]) for N in xs}
        cls, _ = R497.classify(False, per, vals)
        rho = {str(k): (None if v is None else round(v, 4)) for k, v in sorted(per.items())}
        print(f"  {name:24s} {cls:18s} rho={rho}")
        print(f"    values={[None if v is None else round(v, 3) for v in vals]}")
