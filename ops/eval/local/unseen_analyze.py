"""沒用過的題的預註冊批次的分析（`decisions/prereg/PREREG_20260927_NOCAP_UNSEEN.md` 第六節；2026-09-27）。

    python3 ops/eval/local/unseen_analyze.py --jobs <jobs> --ledger <代理 ledger 目錄> --io <代理 io.jsonl> \
        --dataset <釘死的 450 題目錄> --prefix u274 --c-arm C361 --out <輸出目錄>

- 每一格的評分、例外、請求數、機器、`infra_void` 用 `analyze_local.cells`（正式批次與留出批次用的同一支）。
- **主要檢定（只有一個）**：第 1 次、兩組都有評分且都不是 infra_void 的題＝完整配對；
  `C 單獨對`＝C 對、A 不對，`A 單獨對` 反之；**McNemar 精確檢定，雙尾 α＝0.05**（`research.mcnemar_exact`）。
- 描述（不檢定）：每組答對／答錯／沒交；多出來的錯；C 的退回（類別、之後的結果）、**傷害**（第一次退回那一刻答案檔已經是對的、最後錯）；
  A「說做完卻沒寫檔」；1800 秒時限；每台機器；infra_void 清單；第一通請求兩組逐位元組相同（不變式）。
  退回與傷害的重建用 `s36nc_analyze.one`（S36-nocap 用的同一支）。
"""
from __future__ import annotations

import argparse
import collections
import json
import pathlib
import sys
from typing import Any

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from analyze_local import cells, invariants  # noqa: E402
from s36nc_analyze import lab, mcnemar_exact, one  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--jobs", required=True, type=pathlib.Path)
    ap.add_argument("--ledger", required=True, type=pathlib.Path)
    ap.add_argument("--io", type=pathlib.Path)
    ap.add_argument("--dataset", required=True, type=pathlib.Path)
    ap.add_argument("--prefix", required=True)
    ap.add_argument("--c-arm", required=True)
    ap.add_argument("--sample", type=int, default=1)
    ap.add_argument("--out", required=True, type=pathlib.Path)
    a = ap.parse_args(argv)
    C, S = a.c_arm, a.sample
    rows = [r for r in cells(a.jobs, a.ledger, a.dataset, a.prefix) if r["sample"] == S and r["arm"] in ("A", C)]
    cell: dict[tuple[str, str], dict[str, Any]] = {}
    for r in rows:
        trial = a.jobs / f"g12-off-{r['arm']}-s{S}" / r["job"] / r["trial"]
        r["detail"] = one(trial, a.dataset, r["task"])
        cell[(r["task"], r["arm"])] = r
    tasks = sorted({t for t, _ in cell}, key=int)
    void = [t for t in tasks if any((t, x) in cell and cell[(t, x)]["infra_void"] for x in ("A", C))]
    pairs = [t for t in tasks if (t, "A") in cell and (t, C) in cell and t not in void]
    half = [t for t in tasks if t not in void and ((t, "A") in cell) != ((t, C) in cell)]
    L = {k: lab(r["detail"]) for k, r in cell.items()}
    c_only = sum(1 for t in pairs if L[(t, C)] == "right" and L[(t, "A")] != "right")
    a_only = sum(1 for t in pairs if L[(t, "A")] == "right" and L[(t, C)] != "right")
    tally = {x: dict(collections.Counter(L[(t, x)] for t in pairs)) for x in ("A", C)}
    cd = [cell[(t, C)]["detail"] | {"task": t} for t in pairs]
    ad = [cell[(t, "A")]["detail"] for t in pairs]
    mo = [d for d in cd if any("missing_output" in k for k in d["sendbacks"])]
    harm = [d for d in cd if d["first_sendback"] and d["answer_at_first_sendback_ok"] == 1 and lab(d) != "right"]
    unknown = [d["task"] for d in cd if d["first_sendback"] and d["answer_at_first_sendback"] is None
               and not d["no_file_at_first_sendback"] and lab(d) != "right"]
    kinds = collections.Counter(k for d in cd for k in {k for ks in d["sendbacks"] for k in ks})
    after = collections.Counter(f"{k}:{lab(d)}" for d in cd for k in {k for ks in d["sendbacks"] for k in ks})
    by_up: dict[str, dict[str, int]] = {}
    for t in pairs:
        for x in ("A", C):
            b = by_up.setdefault(f"{cell[(t, x)].get('upstream')}:{x}", {"runs": 0, "right": 0})
            b["runs"] += 1
            b["right"] += int(L[(t, x)] == "right")
    summ = {
        "primary": {"test": "mcnemar_exact_two_sided", "pairs": len(pairs), f"{C}_only_right": c_only,
                    "A_only_right": a_only, "p": mcnemar_exact(c_only, a_only),
                    "right": {x: sum(1 for t in pairs if L[(t, x)] == "right") for x in ("A", C)}},
        "tally": tally, "extra_wrong": tally[C].get("wrong", 0) - tally["A"].get("wrong", 0),
        "infra_void_tasks": void, "half_pairs_not_analysed": half,
        "C_runs_with_a_sendback": sum(1 for d in cd if d["sendbacks"]),
        "C_missing_output_sendback_runs": len(mo), "sendback_kinds_runs": dict(kinds),
        "end_state_after_sendback_kind": dict(sorted(after.items())),
        "harm": [{"task": d["task"], "answer_before": d["answer_at_first_sendback"]} for d in harm],
        "sendback_ended_wrong_value_before_unknown": unknown,
        "A_said_done_without_file": sum(1 for d in ad if d["final_stop"] == "stop" and d["missing"]),
        "timeouts": {x: sum(1 for t in pairs if cell[(t, x)]["exception"] == "AgentTimeoutError") for x in ("A", C)},
        "by_machine": by_up,
        "invariants": invariants(a.io, [cell[(t, x)] for t in pairs for x in ("A", C)], a.prefix),
    }
    a.out.mkdir(parents=True, exist_ok=True)
    (a.out / "cells.json").write_text(json.dumps(list(cell.values()), ensure_ascii=False, indent=1, default=str) + "\n")
    (a.out / "summary.json").write_text(json.dumps(summ, ensure_ascii=False, indent=1, default=str) + "\n")
    print(json.dumps(summ, ensure_ascii=False, indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
