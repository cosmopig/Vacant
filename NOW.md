# 現在（第 1187 輪，2026-11-07）

## r1187：工單 P20261107_1224-1（run_eval phase2 修復）收
- 移除未定義 RequirementError 匯入/except 項（修 CI 收集失敗）；derive_real14_cells
  對 smoke/ 無後綴 cell fallback _task_id_from_cell（14 份全匹配：9 壞 5 好）；
  run_phase2 支援 json_out、main() 傳 --json；測試補 real14.mkdir。
- 驗收 19 passed（改前 1 collection error）；extract+checks 113 passed；0 模型呼叫。
- commit dab6abff；工單 mv done/。

## 下一步（bd vq-el4.4 本體，P0）
- 跑 14 份真實草稿（effects2_20261106）：自動擷取需求（glm53）→ run_requirement_checks
  → 抓錯 x/9、冤枉 y/5 → 門禁（≥5/9 且 ≤1/5）→ out/real14/*.json + eval JSON。
- 已知弱點（G1 量）：student_grades 1/6、web_traffic 漏 uv_not_dedup——real14 繼續量。

## 紅線（不變）
main 不動；不手動 push；不讀 /srv/eval hidden/scorer；不繞 glm 直連 vibe；
不改 repair.py／G1 requirements.json／凍結快照；成本缺值＝UNKNOWN 不填 0。
