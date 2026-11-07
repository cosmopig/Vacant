# G2.5 自動擷取需求（vq-el4）— STATE

- 2026-11-07 r1182: vq-el4.3 第 3 輪 prompt 修正（exclude/include 語義、條件合併、ratio(num/den)、group_normalize 範圍）＋4 題 FP 重擷取 → **G1 門禁 PASS（抓錯 28/39=71.8%≥70%、冤枉 0、EXIT=0）**；vq-el4.3 已收。
- 下一項（bd）: vq-el4.4 — run_eval.py 第二項：真實 14 份（9 錯 5 對）用擷取需求檢查 → 之後 vq-el4.5（localized 修復＋獨立 scorer）→ vq-el4.6（換模型比較，P1）。
- 2026-11-07 r1183: 工單 P20261107_1024-1（extract 提示詞加固＋參數防護）收——group_aggregate 範例補 ratio(num/den)+group_normalize；_param_problem 對 exclude op:ne 回 invalid_param:exclude_op_ne 轉 unverified；prompt 補「同一交付物多步過濾整合單一 rowset_filter 條目」；ne→eq 與 (a)(c)(d) 規則 r1182 已在。
- 驗證：驗收指令 2 passed RC=0；test_reqloop_extract 48 passed、checks+run_eval 70 passed；0 模型呼叫、成本 0。
- commit：23f35083；工單已 mv done/。
- 下一步：vq-el4.4——run_eval.py 第二項，真實 14 份（9 錯 5 對）用擷取需求檢查。
