# personal preference pilot result

1. 決策：inconclusive。P5 was not run. Human calibration answers, holdout labels, and blind reviews are not in this repository, so no preference result is reported.
這一節若對到 fixture_plumbing 列，那些列只證明管線能跑完；它們不是本人採用，也不是模型試驗。
2. 實驗身份：見 freeze manifest。此報告不填模型試驗的 SHA。
3. 完成格數：arm rows 48。預定 screen 為 48 列、36 個獨立請求。
4. Stage 1：沒有封存的保留標籤，不計算準確率。
5. Stage 2：客觀檢查與本人採用分開。沒有盲評時採用率留空，不填 0。
6. 成本：見 metrics。本地端點不推導美元；沒有成功交付時不填每成功成本 0。
7. 具體改善與失敗：沒有真人試驗，不列假的改善。
8. 限制：N=1 尚未發生。合成任務。沒有無個人資料對照組。非原生工具 agent。
9. 下一步：先由本人填 C01–C16，再跑一次端點相容性預檢。
10. 重算：python -m vacant_network.personal report --run-dir <run>。不需要再呼叫模型。

## metrics

```json
{
  "planned_arm_pass_rows": 48,
  "observed_rows": 48,
  "planned_independent_requests": 36,
  "independent_requests": 36,
  "per_arm_final": {
    "A": {
      "final_denominator": 6,
      "final_rows": 6,
      "adopt_as_is": null,
      "joint_adopt": null,
      "missing_reviews": [
        "T03",
        "T05",
        "T06",
        "T04",
        "T01",
        "T02"
      ],
      "objective_pass": 6
    },
    "B": {
      "final_denominator": 6,
      "final_rows": 6,
      "adopt_as_is": null,
      "joint_adopt": null,
      "missing_reviews": [
        "T03",
        "T05",
        "T06",
        "T04",
        "T01",
        "T02"
      ],
      "objective_pass": 6
    },
    "C": {
      "final_denominator": 6,
      "final_rows": 6,
      "adopt_as_is": null,
      "joint_adopt": null,
      "missing_reviews": [
        "T03",
        "T05",
        "T06",
        "T04",
        "T01",
        "T02"
      ],
      "objective_pass": 6
    },
    "D": {
      "final_denominator": 6,
      "final_rows": 6,
      "adopt_as_is": null,
      "joint_adopt": null,
      "missing_reviews": [
        "T03",
        "T05",
        "T06",
        "T04",
        "T01",
        "T02"
      ],
      "objective_pass": 6
    }
  },
  "per_representation_first_draft": {
    "SUMMARY": {
      "unique_first_drafts_denominator": 6,
      "unique_first_drafts": 6,
      "adopt_as_is": null,
      "joint_adopt": null,
      "missing_reviews": [
        "T03",
        "T05",
        "T06",
        "T04",
        "T01",
        "T02"
      ]
    },
    "STRUCTURED": {
      "unique_first_drafts_denominator": 6,
      "unique_first_drafts": 6,
      "adopt_as_is": null,
      "joint_adopt": null,
      "missing_reviews": [
        "T03",
        "T05",
        "T06",
        "T04",
        "T01",
        "T02"
      ]
    }
  },
  "regressions": [],
  "status_counts": {
    "completed": 48
  },
  "actual_known_cost_usd": null,
  "unknown_usage_calls": 36,
  "gross_completion_tokens": 0,
  "wall_ms": 0,
  "cost_per_joint_adoption": null,
  "cost_per_joint_adoption_note": "no adopted delivery that also passed the objective check; per-success cost is not computable and is not zero",
  "equivalent_arm_cost_usd": {
    "A": 0.0,
    "B": 0.0,
    "C": 0.0,
    "D": 0.0
  },
  "equivalent_cost_note": "each arm includes a full copy of the shared first draft; do not add the four figures into the bill",
  "failed_rows_kept": []
}
```
