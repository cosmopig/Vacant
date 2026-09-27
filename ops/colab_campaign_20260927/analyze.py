#!/usr/bin/env python3
"""預註冊分析（批次與補跑都結束後跑一次）：A 對 C361 的配對比較。

    python3 analyze.py --cells <cells 目錄> --ledger <ledger.jsonl> --prefix <批次前綴> --out <輸出目錄> [--plan plan.json]

- 一格的結果＝`score.json` 的 `pass`（隱藏測試全過）；`meta.json` 的 rc／逾時；C 組的 `vacant_check.json`。
- **infra_void**（預註冊第五節）：cell.sh 沒寫 DONE、沒有可解析的 score.json、代理帳本裡這一格 0 通、
  或任何一通最終狀態不是 200／有 stream_error。void 的格子不進配對。
- **完整配對**：同一題（同一次）A 與 C361 都不是 void。
- **主要檢定（只有一個）**：`pass` 的不一致對 b＝C361 過、A 沒過；c＝A 過、C361 沒過；McNemar 精確檢定（二項，p＝0.5），雙尾，α＝0.05。
- 其餘全是描述：每個題庫分開的配對表、可見全過、假完成（可見全過但隱藏沒全過）、沒交 solution.py、逾時、
  C361 的退回次數與類別（`vacant_home` 病歷裡的 review 事件）、牆鐘、token。
"""
from __future__ import annotations

import argparse
import collections
import json
import math
import pathlib
import statistics


def binom_two_sided(b: int, c: int) -> float:
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    p = sum(math.comb(n, i) for i in range(0, k + 1)) / 2 ** n
    return min(1.0, 2 * p)


def load_cells(cells: pathlib.Path, prefix: str) -> dict[str, dict]:
    out = {}
    for d in sorted(cells.glob(f"{prefix}-*")):
        r = {"cell": d.name, "done": (d / "DONE").exists()}
        for f in ("meta.json", "score.json"):
            try:
                r[f.split(".")[0]] = json.loads((d / f).read_text().strip().splitlines()[-1] if f == "score.json"
                                                else (d / f).read_text())
            except (OSError, ValueError, IndexError):
                r[f.split(".")[0]] = None
        try:
            r["check"] = json.loads((d / "vacant_check.json").read_text().strip().splitlines()[-1])
        except (OSError, ValueError, IndexError):
            r["check"] = None
        out[d.name] = r
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cells", required=True, type=pathlib.Path)
    ap.add_argument("--ledger", required=True, type=pathlib.Path)
    ap.add_argument("--prefix", required=True)
    ap.add_argument("--out", required=True, type=pathlib.Path)
    a = ap.parse_args()
    cells = load_cells(a.cells, a.prefix)
    led = collections.defaultdict(list)
    for ln in a.ledger.read_text().splitlines():
        try:
            x = json.loads(ln)
        except ValueError:
            continue
        if x.get("tag", "").startswith(a.prefix + "-"):
            led[x["tag"]].append(x)
    # 格子名＝<prefix>-<arm>-<bank>-<id>-s<n>
    rows = []
    for name, r in cells.items():
        rest = name[len(a.prefix) + 1:]
        arm, _, rest = rest.partition("-")
        unit, _, s = rest.rpartition("-s")
        bank = unit.split("-", 1)[0]
        calls = led.get(name, [])
        void_reasons = []
        if not r["done"]:
            void_reasons.append("no DONE")
        if not isinstance(r["score"], dict) or "pass" not in r["score"]:
            void_reasons.append("no score")
        if not calls:
            void_reasons.append("0 model calls")
        if any(x.get("status") != 200 or x.get("stream_error") for x in calls):
            void_reasons.append("proxy non-200/stream_error")
        meta = r["meta"] or {}
        chk = r["check"] or {}
        rows.append({"cell": name, "arm": arm, "bank": bank, "unit": unit, "sample": s, "void": void_reasons,
                     "pass": bool((r["score"] or {}).get("pass")), "visible_pass": bool((r["score"] or {}).get("visible_pass")),
                     "false_done": bool((r["score"] or {}).get("false_done")),
                     "no_solution": str((r["score"] or {}).get("note", "")).startswith("no "),
                     "timeout": bool(meta.get("timeout")), "wall_s": meta.get("wall_s"), "install_rc": meta.get("install_rc"),
                     "c_arm_ok": chk.get("c_arm_ok"), "reviews": chk.get("reviews"), "review_actions": chk.get("review_actions"),
                     "calls": len(calls), "prompt_tokens": sum((x.get("usage") or {}).get("prompt_tokens") or 0 for x in calls),
                     "completion_tokens": sum((x.get("usage") or {}).get("completion_tokens") or 0 for x in calls)})
    by_unit = collections.defaultdict(dict)
    for r in rows:
        by_unit[(r["unit"], r["sample"])][r["arm"]] = r
    pairs = [(u, d["A"], d["C361"]) for u, d in by_unit.items() if "A" in d and "C361" in d and not d["A"]["void"] and not d["C361"]["void"]]
    incomplete = sorted(f"{u[0]}-s{u[1]}" for u, d in by_unit.items() if not ("A" in d and "C361" in d) or d.get("A", {}).get("void") or d.get("C361", {}).get("void"))

    def table(ps):
        b = sum(1 for _, x, y in ps if y["pass"] and not x["pass"])
        c = sum(1 for _, x, y in ps if x["pass"] and not y["pass"])
        both = sum(1 for _, x, y in ps if x["pass"] and y["pass"])
        neither = len(ps) - b - c - both
        return {"pairs": len(ps), "A_pass": both + c, "C361_pass": both + b, "b_C_only": b, "c_A_only": c,
                "both": both, "neither": neither, "p_mcnemar_exact_two_sided": binom_two_sided(b, c)}

    res = {"prefix": a.prefix, "primary": table(pairs), "by_bank": {}, "void_cells": [r["cell"] + ": " + ", ".join(r["void"]) for r in rows if r["void"]],
           "incomplete_units": incomplete}
    for bank in sorted({r["bank"] for r in rows}):
        res["by_bank"][bank] = table([p for p in pairs if p[1]["bank"] == bank])
    desc = {}
    for arm in ("A", "C361"):
        rs = [x for _, *ab in pairs for x in ab if x["arm"] == arm]
        w = [x["wall_s"] for x in rs if x["wall_s"] is not None]
        desc[arm] = {"n": len(rs), "pass": sum(x["pass"] for x in rs), "visible_pass": sum(x["visible_pass"] for x in rs),
                     "false_done": sum(x["false_done"] for x in rs), "no_solution": sum(x["no_solution"] for x in rs),
                     "timeouts": sum(x["timeout"] for x in rs), "wall_p50": statistics.median(w) if w else None,
                     "calls": sum(x["calls"] for x in rs), "prompt_tokens": sum(x["prompt_tokens"] for x in rs),
                     "completion_tokens": sum(x["completion_tokens"] for x in rs)}
    cs = [x for _, _, x in pairs]
    acts = collections.Counter(a for x in cs for a in (x["review_actions"] or []))
    desc["C361_vacant"] = {"c_arm_ok": sum(1 for x in cs if x["c_arm_ok"]), "install_fail": sum(1 for x in cs if x["install_rc"] not in (0, None)),
                           "cells_with_review": sum(1 for x in cs if (x["reviews"] or 0) > 0), "review_actions": dict(acts),
                           "cells_sent_back": sum(1 for x in cs if any(v != "allow" for v in (x["review_actions"] or [])))}
    res["descriptive"] = desc
    a.out.mkdir(parents=True, exist_ok=True)
    (a.out / "report.json").write_text(json.dumps(res, ensure_ascii=False, indent=1))
    (a.out / "cells.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
    p = res["primary"]
    md = [f"# 分析報告（{a.prefix}）", "", "## 主要檢定（預註冊第六節）", "",
          f"完整配對 {p['pairs']}；A 過 {p['A_pass']}、C361 過 {p['C361_pass']}；不一致對 b（只有 C361 過）＝{p['b_C_only']}、"
          f"c（只有 A 過）＝{p['c_A_only']}；McNemar 精確雙尾 p＝{p['p_mcnemar_exact_two_sided']:.4g}（α＝0.05）。", "",
          "## 各題庫（描述）", "", "| 題庫 | 配對 | A 過 | C361 過 | 只有 C 過 | 只有 A 過 | p（描述用） |", "|---|---|---|---|---|---|---|"]
    for bank, t in res["by_bank"].items():
        md.append(f"| {bank} | {t['pairs']} | {t['A_pass']} | {t['C361_pass']} | {t['b_C_only']} | {t['c_A_only']} | {t['p_mcnemar_exact_two_sided']:.3g} |")
    md += ["", "## 描述", "", "```json", json.dumps(desc, ensure_ascii=False, indent=1), "```", "",
           f"infra_void 格子 {len(res['void_cells'])}；不完整的單位 {len(incomplete)}（清單在 report.json）。"]
    (a.out / "report.md").write_text("\n".join(md) + "\n")
    print("\n".join(md))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
