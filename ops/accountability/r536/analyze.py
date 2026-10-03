#!/usr/bin/env python3
"""R536 收官計算：照預註冊（`decisions/prereg/PREREG_20260924_R536_LOCALIZED_FEEDBACK.md`
§五、§六）由上往下求狀態，**不做任何預註冊沒寫的事**。

    python ops/accountability/r536/analyze.py <rows.jsonl> [--layer L1]

輸出：各臂 M1、主要檢定（RL vs RF，McNemar 精確雙尾）、次要（描述）、收斂曲線、狀態。
"""
from __future__ import annotations

import argparse
import json
import math
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
from vacant_network.research import mcnemar_exact  # noqa: E402

INVALID_VOID = 0.10
NOT_TRIGGERED_FAIL1 = 0.6
RULED_OUT_UPPER = 0.15


def load(p: pathlib.Path) -> list[dict]:
    return [json.loads(x) for x in p.read_text().splitlines() if x.strip()]


def paired(rows: list[dict], a: str, b: str) -> tuple[int, int, int]:
    """b＝「a 失敗 ∧ b 通過」（b 臂贏）；c＝「a 通過 ∧ b 失敗」。方向寫死成定義式（R535 §五-1a）。"""
    by: dict[str, dict[str, bool]] = {}
    for r in rows:
        if r.get("infra_void"):
            continue
        by.setdefault(r["item"], {})[r["arm"]] = bool(r.get("M1"))
    both = [v for v in by.values() if a in v and b in v]
    bb = sum(1 for v in both if not v[a] and v[b])
    cc = sum(1 for v in both if v[a] and not v[b])
    return bb, cc, len(both)


def newcombe_diff_ci(b: int, c: int, n: int) -> tuple[float, float]:
    """配對差（b−c）/n 的 95% 區間（Wald 近似，n 小時保守讀；只拿來判 RULED_OUT 的上緣）。"""
    if n == 0:
        return (-1.0, 1.0)
    d = (b - c) / n
    var = ((b + c) / n - d * d) / n
    h = 1.96 * math.sqrt(max(var, 0.0))
    return d - h, d + h


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("rows")
    ap.add_argument("--layer", default="L1")
    a = ap.parse_args()
    rows = load(pathlib.Path(a.rows))
    arms = sorted({r["arm"] for r in rows})
    n_all = len(rows)
    void = sum(1 for r in rows if r.get("infra_void"))
    out: dict = {"layer": a.layer, "rows": n_all, "void": void,
                 "evidence_level": sorted({r.get("evidence_level") for r in rows})}
    for arm in arms:
        rs = [r for r in rows if r["arm"] == arm and not r.get("infra_void")]
        curve = []
        for k in range(3):
            vals = [r["failing_required"][min(k, len(r["failing_required"]) - 1)]
                    for r in rs if r.get("failing_required")]
            curve.append(round(sum(v or 0 for v in vals) / len(vals), 3) if vals else None)
        out[arm] = {"n": len(rs), "M1": sum(1 for r in rs if r.get("M1")),
                    "accepted": sum(1 for r in rs if r.get("accepted")),
                    "first_attempt_fail": sum(1 for r in rs if (r.get("outcomes") or ["?"])[0]
                                              != "accept"),
                    "convergence_failing_required_by_attempt": curve}
    state = None
    if n_all and void / n_all > INVALID_VOID:
        state = "INVALID"
    first = [r for r in rows if not r.get("infra_void")]
    fail1 = sum(1 for r in first if (r.get("outcomes") or ["?"])[0] != "accept")
    if state is None and first and fail1 / len(first) < NOT_TRIGGERED_FAIL1:
        state = "NOT_TRIGGERED"
    b, c, n = paired(rows, "RF", "RL")
    p = mcnemar_exact(b, c)
    lo, hi = newcombe_diff_ci(b, c, n)
    out["primary"] = {"test": "McNemar exact, RL vs RF on M1", "b_RL_wins": b, "c_RF_wins": c,
                      "n_pairs": n, "p": p, "diff": (b - c) / n if n else None,
                      "ci95": [lo, hi]}
    if state is None:
        if p < 0.05 and b > c:
            state = "CONFIRMED_POSITIVE"
        elif p < 0.05 and c > b:
            state = "CONFIRMED_NEGATIVE"
        elif hi < RULED_OUT_UPPER:
            state = "RULED_OUT"
        else:
            state = "INCONCLUSIVE"
    out["state"] = state
    for x, y in (("RS", "RL"), ("RS", "RF")):
        bb, cc, nn = paired(rows, x, y)
        out[f"secondary_{y}_vs_{x}"] = {"b": bb, "c": cc, "n": nn, "p": mcnemar_exact(bb, cc)}
    if any(r.get("evidence_level") == "L-fake" for r in rows):
        out["WARNING"] = "L-fake rows present: plumbing only, no effect claims"
    print(json.dumps(out, indent=1, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
