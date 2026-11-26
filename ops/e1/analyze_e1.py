#!/usr/bin/env python3
"""ops.e1.analyze_e1 — E1′ 結果彙整與分臂統計分析器（聚類單位＝任務鏈）。

這支在架構裡承重什麼
====================
讀取 `ROOT/results.jsonl`（按 `(chain_id, arm, round)` 去重），以**任務鏈（chain）為聚類單位**計算：
- **主要指標（primary）**：每個臂在**最終回合**通過全部當下要求（獨立評分 `all_pass == True`）的鏈比例，
  並對 `B0` 輸出逐鏈配對表（雙過／僅處理臂過／僅 B0 過／雙不過）與精確雙尾 McNemar p 值。
- **次要指標（secondary，分臂）**：
  - 逐回合全過率（`per_round_success`）
  - 回歸率（`regression_rate`：義務層級回歸比例＋鏈層級曾發生回歸的比例）
  - 新需求完成率（`new_req_completion_rate`：總體與逐鏈平均）
  - 每鏈總 token（輸入／輸出／合計）與牆鐘時間（平均與中位數）
  - 嘗試次數（總計與每鏈平均）
  - 被拒單元數（總計與每鏈平均）
  - 針對 `S`／`S+B2`／`O`：
    - `rejected_but_correct`（有害誤拒：被拒且獨立評分判定候選正確、而提交後基線錯誤）
    - `rejected_candidate_correct`（所有被拒且候選通過獨立評分的單元，含無害重構）
    - `accepted_in_scope_but_wrong`（範圍內被接受但獨立評分不通過的單元）

誠實邊界（改碼請保留）
----------------------
- 聚類單位＝任務鏈（`chain_id`）；同鏈內各回合不獨立，因此主要檢定只看每鏈最終回合的配對二元結果。
- 含 `infra_void == True` 的鏈另行列出、不靜默混入正常分母。
- 若資料來自假 agent（selftest），本分析器只驗證指標計算管線無誤，**不可**引用為模型實驗證據。

用法：
  python3 ops/e1/analyze_e1.py ROOT [--json OUT.json]
"""
from __future__ import annotations

import argparse
import json
import math
import pathlib
import statistics
import sys
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from ops.e1 import atomic_write_json


def mcnemar_exact(b: int, c: int) -> float:
    """精確雙尾 McNemar 檢定（與 `vacant_network.research.mcnemar_exact` 同式）。"""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    return min(1.0, 2.0 * sum(math.comb(n, i) for i in range(k + 1)) / (2.0 ** n))


def load_dedup_records(root: pathlib.Path) -> list[dict]:
    """讀取 `ROOT/results.jsonl`，同一 `(chain_id, arm, round)` 以最後一筆為準。"""
    p = root / "results.jsonl"
    if not p.is_file():
        raise FileNotFoundError(f"找不到結果檔：{p}")
    by_key: dict[tuple[str, str, int], dict] = {}
    for line in p.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s:
            continue
        obj = json.loads(s)
        key = (str(obj["chain_id"]), str(obj["arm"]), int(obj["round"]))
        by_key[key] = obj
    return [by_key[k] for k in sorted(by_key)]


def _mean(vals: list[float]) -> float | None:
    return round(sum(vals) / len(vals), 4) if vals else None


def _median(vals: list[float]) -> float | None:
    return round(float(statistics.median(vals)), 4) if vals else None


def analyze_root(root: pathlib.Path) -> dict[str, Any]:
    root = root.expanduser().resolve()
    records = load_dedup_records(root)
    run_meta = json.loads((root / "RUN.json").read_text(encoding="utf-8")) if (root / "RUN.json").is_file() else {}

    # 依 arm -> chain_id -> [records sorted by round]
    by_arm: dict[str, dict[str, list[dict]]] = {}
    for r in records:
        by_arm.setdefault(r["arm"], {}).setdefault(r["chain_id"], []).append(r)

    for chains in by_arm.values():
        for cid in chains:
            chains[cid].sort(key=lambda x: int(x["round"]))

    arms_order = [a for a in ("B0", "B0x3", "B2", "S", "S+B2", "O") if a in by_arm]
    for a in sorted(by_arm):
        if a not in arms_order:
            arms_order.append(a)

    arm_stats: dict[str, dict[str, Any]] = {}
    final_pass_by_arm_chain: dict[str, dict[str, bool]] = {}

    for arm in arms_order:
        chains = by_arm[arm]
        valid_cids: list[str] = []
        void_cids: list[str] = []
        for cid, recs in sorted(chains.items()):
            if any(bool(r.get("infra_void")) for r in recs):
                void_cids.append(cid)
            else:
                valid_cids.append(cid)

        n_chains = len(valid_cids)
        final_pass_map: dict[str, bool] = {}
        round_pass_counts: dict[int, list[bool]] = {}

        chain_any_reg = 0
        total_reg_oblig = 0
        total_prev_pass_still_req = 0

        total_new_req = 0
        total_new_pass = 0
        chain_new_rates: list[float] = []

        chain_walls: list[float] = []
        chain_tokens_in: list[int] = []
        chain_tokens_out: list[int] = []
        chain_tokens_total: list[int] = []
        chain_attempts: list[int] = []
        chain_rejected: list[int] = []

        rej_harmful_total = 0
        rej_cand_correct_total = 0
        acc_in_scope_wrong_total = 0

        for cid in valid_cids:
            recs = chains[cid]
            last_r = recs[-1]
            fp = bool((last_r.get("eval") or {}).get("all_pass"))
            final_pass_map[cid] = fp

            c_reg = 0
            c_new_t = 0
            c_new_p = 0
            c_wall = 0.0
            c_tin = 0
            c_tout = 0
            c_has_tok = True
            c_att = 0
            c_rej = 0

            for r in recs:
                rn = int(r["round"])
                round_pass_counts.setdefault(rn, []).append(bool((r.get("eval") or {}).get("all_pass")))
                rc = int(r.get("regression_count") or 0)
                c_reg += rc
                total_reg_oblig += rc
                total_prev_pass_still_req += int(r.get("still_required_prev_passing_count") or 0)

                nt = int(r.get("new_req_total") or 0)
                np = int(r.get("new_req_passed") or 0)
                c_new_t += nt
                c_new_p += np
                total_new_req += nt
                total_new_pass += np

                c_wall += float(r.get("wall_s") or 0.0)
                if r.get("tokens_in") is None or r.get("tokens_out") is None:
                    c_has_tok = False
                else:
                    c_tin += int(r["tokens_in"])
                    c_tout += int(r["tokens_out"])
                c_att += int(r.get("attempts_count") or 0)
                c_rej += len(r.get("rejected_units") or [])

                rej_harmful_total += len(r.get("rejected_but_correct") or [])
                rej_cand_correct_total += len(r.get("rejected_candidate_correct") or [])
                acc_in_scope_wrong_total += len(r.get("accepted_in_scope_but_wrong") or [])

            if c_reg > 0:
                chain_any_reg += 1
            if c_new_t > 0:
                chain_new_rates.append(c_new_p / c_new_t)
            chain_walls.append(c_wall)
            if c_has_tok:
                chain_tokens_in.append(c_tin)
                chain_tokens_out.append(c_tout)
                chain_tokens_total.append(c_tin + c_tout)
            chain_attempts.append(c_att)
            chain_rejected.append(c_rej)

        final_pass_by_arm_chain[arm] = final_pass_map
        n_final_pass = sum(1 for ok in final_pass_map.values() if ok)

        per_round = {
            str(rn): {
                "passed": sum(1 for x in vals if x),
                "total": len(vals),
                "rate": round(sum(1 for x in vals if x) / len(vals), 4) if vals else None,
            }
            for rn, vals in sorted(round_pass_counts.items())
        }

        entry: dict[str, Any] = {
            "n_chains": n_chains,
            "n_infra_void_chains": len(void_cids),
            "infra_void_chains": void_cids,
            "primary_final_all_pass_count": n_final_pass,
            "primary_final_all_pass_rate": round(n_final_pass / n_chains, 4) if n_chains else None,
            "per_round_success": per_round,
            "regression_chain_count": chain_any_reg,
            "regression_chain_rate": round(chain_any_reg / n_chains, 4) if n_chains else None,
            "regression_obligation_count": total_reg_oblig,
            "regression_obligation_denom": total_prev_pass_still_req,
            "regression_obligation_rate": round(total_reg_oblig / total_prev_pass_still_req, 4)
            if total_prev_pass_still_req
            else None,
            "new_req_passed": total_new_pass,
            "new_req_total": total_new_req,
            "new_req_completion_rate": round(total_new_pass / total_new_req, 4) if total_new_req else None,
            "new_req_chain_mean_rate": _mean(chain_new_rates),
            "wall_s_per_chain_mean": _mean(chain_walls),
            "wall_s_per_chain_median": _median(chain_walls),
            "wall_s_total": round(sum(chain_walls), 3),
            "tokens_in_per_chain_mean": _mean([float(x) for x in chain_tokens_in]),
            "tokens_out_per_chain_mean": _mean([float(x) for x in chain_tokens_out]),
            "tokens_total_per_chain_mean": _mean([float(x) for x in chain_tokens_total]),
            "tokens_total_per_chain_median": _median([float(x) for x in chain_tokens_total]),
            "attempts_total": sum(chain_attempts),
            "attempts_per_chain_mean": _mean([float(x) for x in chain_attempts]),
            "rejected_units_total": sum(chain_rejected),
            "rejected_units_per_chain_mean": _mean([float(x) for x in chain_rejected]),
        }
        if arm in ("S", "S+B2", "O"):
            entry["scope_diagnostics"] = {
                "rejected_but_correct_harmful": rej_harmful_total,
                "rejected_candidate_correct_all": rej_cand_correct_total,
                "accepted_in_scope_but_wrong": acc_in_scope_wrong_total,
            }
        arm_stats[arm] = entry

    # 以鏈為聚類單位與 B0 做配對比較
    paired_vs_b0: dict[str, dict[str, Any]] = {}
    if "B0" in final_pass_by_arm_chain:
        b0_map = final_pass_by_arm_chain["B0"]
        for arm in arms_order:
            if arm == "B0":
                continue
            amap = final_pass_by_arm_chain[arm]
            common = sorted(set(b0_map) & set(amap))
            both_pass = sum(1 for c in common if b0_map[c] and amap[c])
            arm_only = sum(1 for c in common if (not b0_map[c]) and amap[c])
            b0_only = sum(1 for c in common if b0_map[c] and (not amap[c]))
            both_fail = sum(1 for c in common if (not b0_map[c]) and (not amap[c]))
            paired_vs_b0[arm] = {
                "n_paired_chains": len(common),
                "both_pass": both_pass,
                "arm_only_pass": arm_only,
                "b0_only_pass": b0_only,
                "both_fail": both_fail,
                "mcnemar_exact_p": round(mcnemar_exact(arm_only, b0_only), 6),
            }

    return {
        "schema": "vacant.e1.analysis/1",
        "root": str(root),
        "plan_id": run_meta.get("plan_id"),
        "cluster_unit": "chain_id",
        "arms": arm_stats,
        "paired_vs_B0": paired_vs_b0,
    }


def format_report(summary: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append(f"# E1′ Analysis — {summary.get('plan_id') or summary['root']}")
    lines.append(f"Cluster unit: `{summary['cluster_unit']}`")
    lines.append("")
    lines.append("## Primary & Secondary Summary by Arm")
    lines.append(
        "| Arm | Chains | Final All-Pass | Chain Reg. | Oblig. Reg. | New-Req Comp. | "
        "Attempts/Ch | Rejected/Ch | Tokens/Ch | Wall(s)/Ch |"
    )
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for arm, st in summary["arms"].items():
        fp = f"{st['primary_final_all_pass_count']}/{st['n_chains']} ({st['primary_final_all_pass_rate']})"
        cr = f"{st['regression_chain_count']}/{st['n_chains']} ({st['regression_chain_rate']})"
        orr = f"{st['regression_obligation_count']}/{st['regression_obligation_denom']} ({st['regression_obligation_rate']})"
        nr = f"{st['new_req_passed']}/{st['new_req_total']} ({st['new_req_completion_rate']})"
        tok = str(st["tokens_total_per_chain_mean"]) if st["tokens_total_per_chain_mean"] is not None else "n/a"
        lines.append(
            f"| {arm} | {st['n_chains']} | {fp} | {cr} | {orr} | {nr} | "
            f"{st['attempts_per_chain_mean']} | {st['rejected_units_per_chain_mean']} | "
            f"{tok} | {st['wall_s_per_chain_mean']} |"
        )

    lines.append("")
    lines.append("## Per-Round Success Rate")
    for arm, st in summary["arms"].items():
        parts = [f"r{rn}={v['passed']}/{v['total']}" for rn, v in st["per_round_success"].items()]
        lines.append(f"- **{arm}**: " + ", ".join(parts))

    scope_arms = [(a, st["scope_diagnostics"]) for a, st in summary["arms"].items() if "scope_diagnostics" in st]
    if scope_arms:
        lines.append("")
        lines.append("## Scope Diagnostics (S / S+B2 / O)")
        lines.append("| Arm | Rejected-but-Correct (Harmful) | Rejected Candidate-Pass (All) | Accepted-in-Scope-but-Wrong |")
        lines.append("|---|---:|---:|---:|")
        for arm, sd in scope_arms:
            lines.append(
                f"| {arm} | {sd['rejected_but_correct_harmful']} | "
                f"{sd['rejected_candidate_correct_all']} | {sd['accepted_in_scope_but_wrong']} |"
            )

    if summary.get("paired_vs_B0"):
        lines.append("")
        lines.append("## Paired Final-Round Comparison vs B0 (Cluster = Chain)")
        lines.append("| Arm | Paired | Both Pass | Arm Only | B0 Only | Both Fail | McNemar p |")
        lines.append("|---|---:|---:|---:|---:|---:|---:|")
        for arm, pv in summary["paired_vs_B0"].items():
            lines.append(
                f"| {arm} | {pv['n_paired_chains']} | {pv['both_pass']} | "
                f"{pv['arm_only_pass']} | {pv['b0_only_pass']} | {pv['both_fail']} | {pv['mcnemar_exact_p']} |"
            )

    lines.append("")
    lines.append(
        "> Honesty boundary: Cluster = chain. Mechanism-level harness measurement; "
        "EvalPlus code chains have no behavior-change round; fake-agent selftest numbers are pipeline checks only."
    )
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description="E1′ 結果分析器（聚類＝任務鏈）")
    ap.add_argument("root", type=pathlib.Path, help="實驗輸出目錄 ROOT")
    ap.add_argument("--json", type=pathlib.Path, dest="json_out", help="選用：將完整 JSON 摘要寫入路徑")
    args = ap.parse_args()

    summary = analyze_root(args.root)
    if args.json_out is not None:
        atomic_write_json(args.json_out, summary)
    print(format_report(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
