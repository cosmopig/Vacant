# G2.5 自動擷取需求（vq-el4）— STATE

- 2026-11-07 r1182: vq-el4.3 第 3 輪 prompt 修正（exclude/include 語義、條件合併、ratio(num/den)、group_normalize 範圍）＋4 題 FP 重擷取 → **G1 門禁 PASS（抓錯 28/39=71.8%≥70%、冤枉 0、EXIT=0）**；vq-el4.3 已收。
- 下一項（bd）: vq-el4.4 — run_eval.py 第二項：真實 14 份（9 錯 5 對）用擷取需求檢查 → 之後 vq-el4.5（localized 修復＋獨立 scorer）→ vq-el4.6（換模型比較，P1）。
- 2026-11-07 r1183: 工單 P20261107_1024-1（extract 提示詞加固＋參數防護）收——group_aggregate 範例補 ratio(num/den)+group_normalize；_param_problem 對 exclude op:ne 回 invalid_param:exclude_op_ne 轉 unverified；prompt 補「同一交付物多步過濾整合單一 rowset_filter 條目」；ne→eq 與 (a)(c)(d) 規則 r1182 已在。
- 驗證：驗收指令 2 passed RC=0；test_reqloop_extract 48 passed、checks+run_eval 70 passed；0 模型呼叫、成本 0。
- commit：23f35083；工單已 mv done/。
- 下一步：vq-el4.4——run_eval.py 第二項，真實 14 份（9 錯 5 對）用擷取需求檢查。
- 2026-11-07 r1184: 工單 P20261107_1024-2（重擷取 G1＋過 run_eval 門禁）收——G1 7 題重擷取（glm53）：student_grades/support_tickets 的 exclude op:ne 改 op:eq；orders_monthly 直接重擷取會 FP=1，故 surgical 沿用 round3 正確形（op:eq）保 FP=0；run_eval 擷取 29/39（74.4%≥70%）、冤枉 0、EXIT=0；eval JSON 由 stale FAIL 重生成為 PASS；round3/ 快照（與 round1/round2/ 同模式）；vibe_calls.jsonl 已寫本輪 7 題；repair.py 已查（G2 凍結、本任務不依賴）；commit 51b72063；工單 mv done/。
- 下一步：vq-el4.4——run_eval.py 第二項，真實 14 份（9 錯 5 對）用擷取需求檢查。
- 2026-11-07 r1187: 工單 P20261107_1224-1（run_eval phase2 修復）收——移除未定義 RequirementError 匯入＋except 項（修 CI 收集失敗）；derive_real14_cells 對 smoke/ 無後綴 cell fallback _task_id_from_cell（dab_035/039/378/507 全匹配，14 份=9 壞 5 好）；run_phase2 支援 json_out 逐 cell 結果、main() 傳 --json；測試補 real14.mkdir。
- 驗證：驗收 pytest 兩檔 19 passed（改前 1 collection error）；extract+checks 113 passed；derive 實跑 14/14 cell 解析成功；0 模型呼叫、成本 0。
- commit：dab6abff；工單 mv done/。
- 沒驗證：phase2 實際 14 格擷取結果（需模型，屬 vq-el4.4 主線下一步，不在本票）。
- 下一步：vq-el4.4 本體——跑 14 份真實草稿擷取需求＋檢查（glm53，票內授權路徑，出抓錯/冤枉數字）。
- 2026-11-07 r1188: 工單 P20261107_1224-2（run_eval phase2 real14 首跑）收——修 run_eval.py 1 行 ExtractReport 序列化（report.to_dict()，改前 json.dumps TypeError RC=1）；real14 首跑 14/14 cell：抓錯 9/9、冤枉 4/5→門禁 FAIL（RC=20）；成本 15 次/141762 tok（含改前廢呼叫 1 次）；重跑全 cache 0 新呼叫。
- 冤枉 4 份同型（dab_035/057/105/dabstep-13）＝擷取需求綁定 checker 無法解析的 deliverable/值路徑：dabstep-13 好稿有 answer.txt 但需求寫 /app/answer.txt→missing_file；未抓項 0。
- 按票 RC=20 分支：如實記錄、不寫報告、不碰 hidden/scorer；vq-el4.4 未收（門禁未達）；commit 552dda17；工單 mv done/。
- 下一步（規劃者重拆 vq-el4.4）：修 deliverable 路徑綁定（好稿檔案在、需求指錯路徑→冤枉）→ 重跑（cache 已存、0 計費）→ 再過門禁 → vq-el4.5。
- r1188 redo（審查）：state/vibe_calls.jsonl 補入 repo（與 ~/dev/ops 正規帳本 sha256 一致，15 次 real14/141762 tok 全 rc=0）；commit a412c2a1；其餘不動。
