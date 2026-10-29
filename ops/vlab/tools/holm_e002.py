#!/usr/bin/env python3
"""holm_e002 — e002 預註冊多重性校正的一次性腳本（round 130/132）。

背景與規則（不污染量具）：
- e002 研究包 §4 預註冊：4 組 A_vs_X 的 McNemar 雙尾 p 用 Holm–Bonferroni 作確認線；
  未校正 p 只作描述。預註冊命令是讀 REPORT.json 的 `A_vs_X.mcnemar_p_two_sided`，
  本腳本是該命令的檔案化版本（同一輸入、同一函數、同一輸出語義）。
- 規則（round 130 STATE DECISION 5）：Holm 校正在 report.py 外執行；本腳本只讀
  REPORT.json（與原始格子），不改共用量具（cell.py / labd.py / report.py）。

用法：
  python3 ops/vlab/tools/holm_e002.py <exp> [--base /srv/vlab/runs] [--alpha 0.05]
      [--arms C,H,M,S] [--out PATH]

行為：
- 主路徑（預註冊）：REPORT.json 有 A_vs_X.mcnemar_p_two_sided ⇒ 直接取用。
- 回退路徑（僅當某組缺失/為 null，且原始格子存在）：從 <base>/<exp>/*/score.json
  逐題配對重算該組 McNemar 雙尾 p（b = X 過 A 敗，c = X 敗 A 過；雙尾精確二項）。
  回退組在輸出裡標記 "source": "recomputed"（與 "report_json" 區分）。
- Holm：優先 `vacant_network.research.holm_bonferroni`（研究堆棧同一支）；
  import 失敗時用內嵌 step-down（同一演算法，輸出標記 "holm_impl": "inline"）。

退出碼：0 正常；1 無 REPORT.json 且無原始格子（無事可做）；2 REPORT.json 格式不符。
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

ARMS_DEFAULT = ("C", "H", "M", "S")


def mcnemar_exact_two_sided(b: int, c: int) -> float:
    """雙尾精確 McNemar：K ~ Binomial(b+c, 0.5)，p = 2*min(P(K<=b), P(K<=c))，截到 1。

    b+c == 0 時回 1.0（無配對分歧，無證據；與 vacant_network.research.mcnemar_exact
    的約定一致——若可 import 則以該函數為準，本函數只是離線回退）。
    """
    n = b + c
    if n == 0:
        return 1.0
    lo, hi = min(b, c), max(b, c)
    tail = sum(math.comb(n, k) for k in range(lo + 1)) / (2 ** n)
    return min(1.0, 2.0 * tail)


def holm_step_down(pvals: list[float], alpha: float = 0.05) -> list[float]:
    """Holm step-down（inline 回退）：排序後 p_adj_(i) = max_{k<=i} (m-k+1)*p_(k)。"""
    m = len(pvals)
    order = sorted(range(m), key=lambda i: pvals[i])
    adj = [0.0] * m
    running = 0.0
    for rank, idx in enumerate(order):
        running = max(running, (m - rank) * pvals[idx])
        adj[idx] = min(1.0, running)
    return adj


def load_report_p(base: Path, exp: str, arms: tuple[str, ...]) -> dict[str, float | None]:
    rpath = base / exp / "REPORT.json"
    if not rpath.is_file():
        return {}
    r = json.loads(rpath.read_text())
    paired = r.get("paired") if isinstance(r.get("paired"), dict) else {}
    out: dict[str, float | None] = {}
    for x in arms:
        blk = paired.get("A_vs_" + x)
        if not isinstance(blk, dict):
            blk = r.get("A_vs_" + x)
        if not isinstance(blk, dict):
            out[x] = None
            continue
        p = blk.get("mcnemar_p_two_sided")
        out[x] = float(p) if isinstance(p, (int, float)) else None
    return out


def cell_outcome(d: Path) -> tuple[str | None, bool | None]:
    """從格子目錄名解析臂與任務；score.json 給 pass（None = infra/未分）。"""
    parts = d.name.split("-")
    # <suite>-<task>-<agent>-<arm>-r<rep>；task 是 pg_xxx（單 token），arm 是單大寫字母
    if len(parts) < 5:
        return None, None
    arm, rep = parts[-2], parts[-1]
    if not (len(arm) == 1 and arm.isalpha()) or not rep.startswith("r"):
        return None, None
    sp = d / "score.json"
    if not sp.is_file():
        return None, None
    try:
        s = json.loads(sp.read_text())
    except Exception:
        return None, None
    v = s.get("pass")
    return arm, (bool(v) if isinstance(v, bool) else None)


def recompute_pair(base: Path, exp: str, x: str) -> tuple[float | None, dict]:
    """回退路徑：從原始格子重算 A_vs_X 的 McNemar 雙尾 p。

    任一邊（A 或 X）沒有格子 ⇒ 回 (None, ...)：該組「量不到」（UNKNOWN），
    不進 Holm 集、不記 p=1.0——「未測」不等於「無差異」（H-1/H-4 語義）。
    """
    expdir = base / exp
    if not expdir.is_dir():
        raise SystemExit(2)
    a: dict[str, bool] = {}
    xa: dict[str, bool] = {}
    for d in sorted(expdir.iterdir()):
        if not d.is_dir() or ".infra-" in d.name:
            continue
        arm, res = cell_outcome(d)
        if arm is None or res is None:
            continue
        task = "-".join(d.name.split("-")[1:-3])
        if arm == "A":
            a[task] = res
        elif arm == x:
            xa[task] = res
    if not a or not xa:
        return None, {"n_tasks_common": 0, "n_A": len(a), "n_X": len(xa),
                      "note": "arm absent — not measured, excluded from Holm set"}
    common = set(a) & set(xa)
    b = sum(1 for t in common if xa[t] and not a[t])
    c = sum(1 for t in common if a[t] and not xa[t])
    return mcnemar_exact_two_sided(b, c), {
        "n_tasks_common": len(common), "b": b, "c": c,
        "n_A": len(a), "n_X": len(xa),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("exp")
    ap.add_argument("--base", default="/srv/vlab/runs")
    ap.add_argument("--alpha", type=float, default=0.05)
    ap.add_argument("--arms", default=",".join(ARMS_DEFAULT))
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)

    base = Path(args.base)
    arms = tuple(a.strip() for a in args.arms.split(",") if a.strip())
    if "A" in arms:
        ap.error("A 是基線臂，不進校正組")

    report_p = load_report_p(base, args.exp, arms)
    ps: dict[str, float] = {}
    absent: dict[str, dict] = {}
    meta: dict[str, dict] = {}
    for x in arms:
        p = report_p.get(x)
        if p is not None:
            ps[x] = p
            meta[x] = {"source": "report_json"}
            continue
        try:
            p2, detail = recompute_pair(base, args.exp, x)
        except SystemExit:
            continue
        if p2 is None:
            absent[x] = detail
            continue
        ps[x] = p2
        meta[x] = {"source": "recomputed", **detail}

    if not ps:
        print(f"無事可做：{base}/{args.exp} 沒有 REPORT.json 的 A_vs_{{C,H,M,S}}，也沒有原始格子可重算", file=sys.stderr)
        return 1

    try:
        from vacant_network.research import holm_bonferroni
        corr = list(holm_bonferroni(list(ps.values())))
        holm_impl = "vacant_network.research.holm_bonferroni"
    except Exception:
        corr = holm_step_down(list(ps.values()))
        holm_impl = "inline (step-down)"

    result = {
        "schema": "vacant.holm/1",
        "exp": args.exp,
        "alpha": args.alpha,
        "m": len(ps),
        "holm_impl": holm_impl,
        "pairs": {},
        "absent_pairs": absent,
    }
    for (x, p), p_adj in zip(ps.items(), corr):
        result["pairs"][x] = {
            "p_raw": p,
            "p_holm": p_adj,
            "significant_at_alpha": p_adj < args.alpha,
            **meta[x],
        }

    out = json.dumps(result, ensure_ascii=False, indent=2)
    print(out)
    if args.out:
        op = Path(args.out)
        op.parent.mkdir(parents=True, exist_ok=True)
        op.write_text(out + "\n")
        print(f"# wrote {op}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
