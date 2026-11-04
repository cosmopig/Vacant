# 需求：學生成績分班統計

請依 `grades.csv` 產出學期成績統計：

1. 排除 `status` 為 `WITHDRAWN` 的休退學記錄。
2. 同一 `student_id` 若出現多筆，只保留第一筆。
3. 總評成績 `total_score = midterm_score × 0.4 + final_score × 0.6`；`total_score ≥ 60.0` 為及格。
4. 產出 `class_summary.csv`，欄位：`class_name, student_count, passing_count, pass_rate, average_score`
   - `pass_rate` = 該班及格人數 / 該班修課人數（小數點後 2 位）
   - `average_score` = 該班 total_score 平均（小數點後 2 位）
5. 產出 `summary.md`，須明確載明「全年級及格率」（百分比，小數點後 2 位）與「全年級平均總評」（小數點後 2 位）。
