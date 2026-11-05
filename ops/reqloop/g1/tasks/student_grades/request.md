<<<<<<< HEAD
# 學生成績處理需求

請根據提供的 `grades.csv` 資料進行以下處理：

## 處理規則
1. **資料過濾**：
   - 排除所有 `status == 'WITHDRAWN'` 的記錄。
   - 排除重複的 `student_id`（若有重複，僅保留第一筆出現的記錄）。

2. **成績計算**：
   - 計算每位學生的學期總評成績：`total_score = midterm_score * 0.4 + final_score * 0.6`。
   - 判定是否及格：若 `total_score >= 60.0` 為「及格」。

3. **產出要求**：
   - 產出 `class_summary.csv`，包含以下欄位：
     - `class_name`
     - `student_count`（該班級有效學生總數）
     - `passing_count`（該班級及格人數）
     - `pass_rate`（及格率，保留兩位小數）
     - `average_score`（該班級所有有效學生的平均總評成績，保留兩位小數）

   - 產出 `summary.md`，內容需包含：
     - 全年級全體學生的總及格率。
     - 全年級全體學生的平均總評成績。
=======
# 需求：學生成績分班統計

請依 `grades.csv` 產出學期成績統計：

1. 排除 `status` 為 `WITHDRAWN` 的休退學記錄。
2. 同一 `student_id` 若出現多筆，只保留第一筆。
3. 總評成績 `total_score = midterm_score × 0.4 + final_score × 0.6`；`total_score ≥ 60.0` 為及格。
4. 產出 `class_summary.csv`，欄位：`class_name, student_count, passing_count, pass_rate, average_score`
   - `pass_rate` = 該班及格人數 / 該班修課人數（小數點後 2 位）
   - `average_score` = 該班 total_score 平均（小數點後 2 位）
5. 產出 `summary.md`，須明確載明「全年級及格率」（百分比，小數點後 2 位）與「全年級平均總評」（小數點後 2 位）。
>>>>>>> auto/argon
