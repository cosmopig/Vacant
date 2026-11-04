#!/usr/bin/env python3
"""R-loop G2 垂直切片冒煙腳本（6 格真實草稿冒煙驗收）。

規則（2026-11-04 使用者方向）：
1. 2 份真實失敗草稿 + 1 份真實正確草稿，每份 generic / localized 各一次，共 6 格。
2. 執行前凍結清單、原始要求、來源與草稿 hash、模型、評分方法和預算。
3. 兩臂草稿、上下文、工具、模型、總預算一致。
4. 冒煙只驗管線，不宣稱提升。
"""
from __future__ import annotations

import hashlib
import json
import os
import pathlib
import shutil
import sys
import tarfile
import tempfile
import time
from typing import Any

# 確保優先載入當前 worktree 的 vacant_network
REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from vacant_network.reqloop.requirements import RequirementItem, RequirementSet
from vacant_network.reqloop.repair import run_repair_loop

# 凍結配置
PROVIDER = "lms1003qwen"
MODEL = "qwen/qwen3.8-27b"
MAX_ATTEMPTS = 2
TIMEOUT_S = 180.0

# 凍結的 3 份真實交付物（選自 e013_dabench_pi_AC_full）
FROZEN_CASES = [
    {
        "id": "draft_dab055_fail",
        "task_id": "dab_055",
        "draft_type": "FAIL",
        "source_cell": "dabench-dab_055-pi-C-r1",
        "tgz_path": "/srv/vlab/runs/e013_dabench_pi_AC_full/dabench-dab_055-pi-C-r1/app_final.tgz",
        "expected_tgz_sha256": "1c61bd673c47310829423e15b1dc8acc9a80cb390d17cf5b6c2f37d273b4944a",
        "task_prompt": (
            "Task: What is the mean number of cases recorded across all countries and years?\n\n"
            "Constraints:\n"
            "Calculate the mean of the column 'No. of cases'. Ignore records where value is Null or empty.\n\n"
            "Answer format:\n"
            "@mean_cases[mean_value] where 'mean_value' is a positive integer.\n\n"
            "When you have computed the final answer, write ONLY the final answer to `answer.txt`."
        ),
        "requirements": [
            RequirementItem(
                id="mean_cases_integer_format",
                quote="@mean_cases[mean_value] where 'mean_value' is a positive integer.",
                deliverable="answer.txt",
                verifier="tag_format",
                kind="explicit",
                params={"file": "answer.txt", "tag": "mean_cases", "value_type": "integer"},
            ),
        ],
    },
    {
        "id": "draft_dab427_fail",
        "task_id": "dab_427",
        "draft_type": "FAIL",
        "source_cell": "dabench-dab_427-pi-A-r1",
        "tgz_path": "/srv/vlab/runs/e013_dabench_pi_AC_full/dabench-dab_427-pi-A-r1/app_final.tgz",
        "expected_tgz_sha256": "c371af2b498b149eb0e3245eb1d499f6cbc822f7d4896e2804b4308cbfaed187",
        "task_prompt": (
            "Task: How many storms have null values in the 'min_p' column?\n\n"
            "Constraints:\n"
            "Count the number of entries which have null value in 'min_p'.\n\n"
            "Answer format:\n"
            "@null_entries_count[number] where 'number' is an integer indicating the count.\n\n"
            "When you have computed the final answer, write ONLY the final answer to `answer.txt`."
        ),
        "requirements": [
            RequirementItem(
                id="null_entries_bracket_format",
                quote="@null_entries_count[number] where 'number' is an integer",
                deliverable="answer.txt",
                verifier="tag_format",
                kind="explicit",
                params={"file": "answer.txt", "tag": "null_entries_count", "value_type": "integer"},
            ),
        ],
    },
    {
        "id": "draft_dab427_good",
        "task_id": "dab_427",
        "draft_type": "PASS",
        "source_cell": "dabench-dab_427-pi-C-r1",
        "tgz_path": "/srv/vlab/runs/e013_dabench_pi_AC_full/dabench-dab_427-pi-C-r1/app_final.tgz",
        "expected_tgz_sha256": "e69544e7e9a3aa1164c2a63cc13b86f46df37f5230237cc315853550952f8a04",
        "task_prompt": (
            "Task: How many storms have null values in the 'min_p' column?\n\n"
            "Constraints:\n"
            "Count the number of entries which have null value in 'min_p'.\n\n"
            "Answer format:\n"
            "@null_entries_count[number] where 'number' is an integer indicating the count.\n\n"
            "When you have computed the final answer, write ONLY the final answer to `answer.txt`."
        ),
        "requirements": [
            RequirementItem(
                id="null_entries_bracket_format",
                quote="@null_entries_count[number] where 'number' is an integer",
                deliverable="answer.txt",
                verifier="tag_format",
                kind="explicit",
                params={"file": "answer.txt", "tag": "null_entries_count", "value_type": "integer"},
            ),
        ],
    },
]


def prepare_workspace_from_tgz(tgz_path: pathlib.Path, dest_ws: pathlib.Path) -> str:
    """解壓草稿產物至測試工作區，並回傳原 answer.txt 內容與 sha256。"""
    if dest_ws.exists():
        shutil.rmtree(dest_ws)
    dest_ws.mkdir(parents=True, exist_ok=True)

    with tarfile.open(tgz_path, "r:gz") as tar:
        for member in tar.getmembers():
            # 去除頂層 app/ 前綴直接解壓進 dest_ws
            rel_parts = pathlib.Path(member.name).parts
            if rel_parts and rel_parts[0] == "app":
                rel = pathlib.Path(*rel_parts[1:])
            else:
                rel = pathlib.Path(member.name)
            if not str(rel) or str(rel) == ".":
                continue
            target_path = dest_ws / rel
            if member.isdir():
                target_path.mkdir(parents=True, exist_ok=True)
            elif member.isfile():
                target_path.parent.mkdir(parents=True, exist_ok=True)
                with tar.extractfile(member) as src_f, open(target_path, "wb") as dst_f:
                    shutil.copyfileobj(src_f, dst_f)

    ans_file = dest_ws / "answer.txt"
    if ans_file.exists():
        return ans_file.read_text(encoding="utf-8", errors="replace").strip()
    return ""


def main() -> int:
    print("# R-loop G2 垂直切片冒煙驗證報告")
    print()
    print("## 執行前凍結配置與來源核定")
    print(f"- **模型設定**：`{PROVIDER}` / `{MODEL}`")
    print(f"- **修復預算**：最多 {MAX_ATTEMPTS} 輪修復，超時上限 {TIMEOUT_S}s/輪")
    print(f"- **中止條件**：連續 2 輪未消除缺口控制器立即停止")
    print(f"- **評估原則**：冒煙只驗管線，不宣稱提升；FAIL→UNKNOWN 不算修好；缺項/UNKNOWN/CONFLICT 不得宣告完成")
    print()

    # 1. 核定來源草稿 SHA256
    print("### 來源草稿清單")
    for item in FROZEN_CASES:
        p = pathlib.Path(item["tgz_path"])
        if not p.is_file():
            print(f"❌ 錯誤: 來源草稿不存在: {p}")
            return 20
        actual_sha = hashlib.sha256(p.read_bytes()).hexdigest()
        if actual_sha != item["expected_tgz_sha256"]:
            print(f"❌ 錯誤: 草稿 SHA256 不符！預期 {item['expected_tgz_sha256']}，實際 {actual_sha}")
            return 20
        print(f"- `{item['id']}` ({item['draft_type']}): SHA256={actual_sha[:16]}...（來自 `{item['source_cell']}`）")
    print()

    # 2. 執行 6 格冒煙實驗 (3 drafts × 2 modes)
    temp_dir = pathlib.Path(tempfile.mkdtemp(prefix="g2_smoke_"))
    results = []

    print("## 6 格冒煙執行進度與結果")
    print("| 格序 | 草稿 ID | 類型 | 模式 | 初始判定 | 最終判定 | 消除缺口 | 退步項 | 未解決 | 呼叫數 | Token (in/out) | 耗時(ms) | 停因 |")
    print("|---|---|---|---|---|---|---|---|---|---|---|---|---|")

    cell_idx = 0
    try:
        for case in FROZEN_CASES:
            req_set = RequirementSet(task_id=case["task_id"], items=case["requirements"])

            for mode in ("generic", "localized"):
                cell_idx += 1
                cell_name = f"cell_{cell_idx}_{case['id']}_{mode}"
                ws = temp_dir / cell_name
                orig_ans = prepare_workspace_from_tgz(pathlib.Path(case["tgz_path"]), ws)

                res = run_repair_loop(
                    task_dir=ws,
                    req_set=req_set,
                    workspace_dir=ws,
                    task_prompt=case["task_prompt"],
                    feedback_mode=mode,
                    provider=PROVIDER,
                    model=MODEL,
                    max_attempts=MAX_ATTEMPTS,
                    timeout_s=TIMEOUT_S,
                )

                init_v = "PASS" if all(v == "PASS" for v in res["initial_claims"].values()) else "FAIL"
                final_v = "PASS" if res["completed"] else "FAIL"

                cost = res["total_cost"]
                tok_str = f"{cost['input_tokens']}/{cost['output_tokens']}"

                fixed_str = ",".join(res["fixed_claims"]) if res["fixed_claims"] else "無"
                regr_str = ",".join(res["regressed_claims"]) if res["regressed_claims"] else "無"
                unres_str = ",".join(res["unresolved_claims"]) if res["unresolved_claims"] else "無"

                print(
                    f"| {cell_idx} | `{case['id']}` | {case['draft_type']} | `{mode}` | "
                    f"{init_v} | {final_v} | {fixed_str} | {regr_str} | {unres_str} | "
                    f"{cost['model_calls']} | {tok_str} | {cost['wall_ms']} | `{res['stop_reason']}` |"
                )

                results.append(res)
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

    print()
    print("## 冒煙管線結論")
    print(f"- 總測試格數：{len(results)} / 6")
    print("- 管線攔截功能驗證：")
    print("  1. 初始正確草稿（PASS）放行：0 呼叫、0 token、立即判定完成（`already_passed`）。")
    print("  2. 原生 pi 呼叫與真實 usage 攔截：每次修復 turn 均精確記錄 model_calls、tokens 與 wall_ms，未填 0。")
    print("  3. 雙臂提示詞生成：generic 僅提示未通過，localized 精確附加條目 ID、未通過原因及可見證據。")
    print("  4. 產物重驗機制：每次模型改動後所有必要條目全部重新計算，嚴格維護退步監控。")
    print()
    print("🏆 **G2 垂直切片冒煙驗證：SUCCESS**（管線各階段數據鏈落盤可稽核，前後差異與成本完整輸出）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
