#!/usr/bin/env python3
"""
G1 門禁評估腳本：檢查器看不看得到真的錯（不呼叫模型）。

職責：
- 遍歷 ops/reqloop/g1/tasks/ 底下的任務目錄。
- 檢驗 good/ 交付物是否 100% 通過（冤枉數 = 0）。
- 檢驗各 bad_*/ 交付物是否被檢查器精準抓出（抓錯率 ≥ 80%）。
- 輸出結構化 Markdown 表格與判定結果。
"""

from __future__ import annotations

import pathlib
import sys

# 將 repo 加入 sys.path 確保可載入 vacant_network
REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from vacant_network.reqloop.requirements import RequirementSet
from vacant_network.reqloop.checks import run_requirement_checks


def required_verified(items, results) -> bool:
    """Every declared required claim must occur exactly once and explicitly PASS."""
    required = [item.id for item in items if item.required]
    if not required or len(required) != len(set(required)):
        return False
    return all(
        len(matches := [c for c in results if c.claim_id == claim_id]) == 1
        and matches[0].status == "PASS"
        for claim_id in required
    )


def evaluate_task(task_dir: pathlib.Path) -> dict:
    req_file = task_dir / "requirements.json"
    if not req_file.is_file():
        return {"error": f"Missing requirements.json in {task_dir}"}

    req_set = RequirementSet.load(req_file)

    results = {
        "task_id": task_dir.name,
        "good_evaluated": False,
        "good_verified": False,
        "good_false_positive": False,
        "good_results": [],
        "bad_cases": [],
    }

    # 1. 驗證 good/
    good_dir = task_dir / "good"
    if good_dir.is_dir():
        results["good_evaluated"] = True
        claim_results = run_requirement_checks(task_dir, req_set, good_dir)
        results["good_results"] = claim_results
        results["good_verified"] = required_verified(req_set.items, claim_results)
        failed_claims = [c for c in claim_results if c.status == "FAIL"]
        if failed_claims:
            results["good_false_positive"] = True
            results["good_fp_details"] = [f"{c.claim_id}: {c.detail}" for c in failed_claims]

    # 2. 驗證各 bad_*/
    for item in sorted(task_dir.iterdir()):
        if item.is_dir() and item.name.startswith("bad_"):
            error_type = item.name.removeprefix("bad_")
            claim_results = run_requirement_checks(task_dir, req_set, item)
            failed_claims = [c for c in claim_results if c.status == "FAIL"]
            caught = len(failed_claims) > 0
            
            counterexamples = []
            for c in failed_claims:
                ces = c.evidence.get("counterexamples", [])
                if ces:
                    counterexamples.extend(ces)

            results["bad_cases"].append({
                "case_name": item.name,
                "error_type": error_type,
                "caught": caught,
                "failed_claims": [c.claim_id for c in failed_claims],
                "failure_details": [c.detail for c in failed_claims],
                "counterexamples": counterexamples,
            })

    return results


def main() -> int:
    tasks_root = pathlib.Path(__file__).parent / "tasks"
    if not tasks_root.is_dir():
        print(f"錯誤：找不到任務目錄 {tasks_root}")
        return 1

    task_dirs = sorted([p for p in tasks_root.iterdir() if p.is_dir() and (p / "requirements.json").is_file()])
    if not task_dirs:
        print(f"錯誤：在 {tasks_root} 內未找到任何有效任務")
        return 1

    total_good = 0
    total_fp = 0
    total_bad = 0
    total_caught = 0
    total_unverified = 0

    print("# G1 門禁驗證報告：內容重算檢查器鑑別力")
    print()
    print("| 任務 | 案例 | 類型 | 預期 | 檢查判定 | 抓錯判定 | 關鍵證據 / 反例 |")
    print("|---|---|---|---|---|---|---|")

    for t_dir in task_dirs:
        res = evaluate_task(t_dir)
        task_id = res["task_id"]
        if not res["good_verified"]:
            total_unverified += 1

        # 印出 good/
        if res["good_evaluated"]:
            total_good += 1
            if res["good_false_positive"]:
                total_fp += 1
                verdict = "FAIL (冤枉)"
                caught_str = "❌ 冤枉"
                detail = "; ".join(res.get("good_fp_details", []))
            elif not res["good_verified"]:
                verdict = "UNKNOWN"
                caught_str = "未完整驗證"
                detail = "必要條目缺失、重複或非 PASS；不能放行"
            else:
                verdict = "PASS"
                caught_str = "✅ 正確放行"
                detail = "所有必備條目重算完全符合"
            print(f"| `{task_id}` | `good` | 正確交付物 | PASS | {verdict} | {caught_str} | {detail} |")

        else:
            print(f"| `{task_id}` | `good` | 缺少正確對照 | PASS | UNKNOWN | 未驗證 | 不得通過 G1 |")

        # 印出各 bad_*/
        for b in res["bad_cases"]:
            total_bad += 1
            if b["caught"]:
                total_caught += 1
                verdict = "FAIL (已抓出)"
                caught_str = "✅ 成功抓錯"
            else:
                verdict = "PASS (漏抓)"
                caught_str = "❌ 漏抓"

            # 摘要反例
            ev_summary = ""
            if b["failure_details"]:
                ev_summary = b["failure_details"][0]
            print(f"| `{task_id}` | `{b['case_name']}` | {b['error_type']} | FAIL | {verdict} | {caught_str} | {ev_summary} |")

    # 統計彙整
    catch_rate = (total_caught / total_bad * 100.0) if total_bad > 0 else 0.0
    passed_g1 = (total_good > 0 and total_bad > 0 and total_unverified == 0
                 and catch_rate >= 80.0 and total_fp == 0)

    print()
    print("## 門禁指標彙整")
    print(f"- **正確交付物總數**：{total_good}")
    print(f"- **未完整驗證的正確對照**：{total_unverified}（門檻：0）")
    print(f"- **冤枉數 (False Positives)**：{total_fp}（門檻：0）")
    print(f"- **錯誤交付物總數**：{total_bad}")
    print(f"- **成功抓錯數 (Caught)**：{total_caught}")
    print(f"- **漏抓數 (Missed)**：{total_bad - total_caught}")
    print(f"- **內容錯誤抓錯率**：{catch_rate:.1f}%（門檻：≥ 80.0%）")
    print()
    if passed_g1:
        print("🏆 **G1 驗證結論：PASS**（抓錯率達標且零冤枉，檢查器具備真重算鑑別力）")
        return 0
    else:
        print("❌ **G1 驗證結論：FAIL**（正確對照未完整 PASS、抓錯率未達標或存在冤枉，需修正檢查器）")
        return 20


if __name__ == "__main__":
    sys.exit(main())
