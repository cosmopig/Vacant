# 現在（第 1182 輪，2026-11-07）

## 這一輪（vq-el4.3：run_eval.py 第一項——G1 擷取需求 vs 手寫需求）→ **門禁 PASS**
- **結果**：抓錯 **手寫 39/39 vs 擷取 28/39（71.8%≥70%）**；冤枉 **手寫 0 vs 擷取 0**；
  EXIT=0。`ops/reqloop/extract/out/eval_g1_glm53.json`（PASS）。
- **4 格冤枉 FP 根因（claim 級對照抓出）**：
  1. prompt 的 rowset_filter 範例 exclude 用 `op:"ne"`——檢查器 exclude＝「排除符合條件的列」，
     範例是反的；orders_monthly R5 照抄 → 只加總 CANCELLED 列（42300≠88000）。
  2. 比率定義（sla_rate＝X÷Y）被寫成 `count_if`；應 `{"type":"ratio","num":…,"den":…}`。
  3. 同行集多條件未合併：inventory_alerts 的 R1/R2 只附 exclude，缺
     `include: current_stock < safety_stock` → 行集不符。
  4. 「輸出用 lower」只套句中欄位；group_normalize 應套全部分組欄位。
- **修法（TDD，先紅後綠）**：`extract.py` build_task_prompt 範例 ne→eq＋新增 4 條常見錯誤規則
  （exclude/include 語義、條件合併要完整行集、ratio(num/den)、normalize 範圍）；
  測試 `test_task_prompt_round3_semantic_rules_r1182`；116 passed（extract+run_eval+checks）。
- **重擷取 4 題 FP**（glm，票內自授權路徑）→ 全數 no-FAIL；
  orders_monthly 5/6→6/6（bad_summary_number_mismatch 也抓到）。
- commit：`4443d9fe`（prompt＋測試）、`977e74ff`（重擷取結果＋round2/ 快照）。
- 歷史：round1＝舊提示基線（12/39、冤枉 0）、round2/＝第 2 輪（27/39、冤枉 4）。

## 下一步（bd 順序）
- **vq-el4.4（下一項，P0）**：run_eval.py 第二項——真實 14 份（9 錯 5 對）用擷取需求檢查。
- vq-el4.5：擷取需求＋localized 修復跑 9 份錯、獨立 scorer 評分。
- vq-el4.6（P1）：換模型比較 gemma vs glm53 vs glm53flash vs deepseek41。
- 已知弱點留檔：student_grades 只抓到 1/6（漏 bad_weight_calculation 等 5 份）、
  web_traffic 漏 uv_not_dedup／bad_summary_uv_summed——vq-el4.4/4.5 繼續量。

## 紅線（不變）
main 不動；不手動 push；不讀 `/srv/eval` hidden/scorer；不洩露金鑰；不繞過 `glm` 直連 vibe；
不改 `repair.py`／G1 `requirements.json`／G1 資料／凍結快照；成本缺值＝UNKNOWN 不填 0；
本輪 GLM 5.3 擷取 6 次（4 題重擷取＋2 題重複，票內授權路徑）。
