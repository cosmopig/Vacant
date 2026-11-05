
## r981（11/04 12:20～12:45）G2 小批：e013 三真草稿凍結＋3 新重算規則（TDD）

**結果：管線推進（本輪重點），無新實驗結論。commit `e2b7b62f`（auto/qwen27b）**

1. **檢查器擴充（TDD，紅→綠）**：`kv_recomputed` 新增 3 型，全部「公開規則對公開資料」、
   重算值不進證據、無法重算=UNKNOWN：
   - `mean_int_col`（dab_055：Int64 語意，Null/空/不可解析如 '630308[495000-801000]' 忽略）
   - `max_row_first`（dab_426：max 類別、平手取檔案序第一列、輸出該列風速——「neglecting ties…first」直譯）
   - `pearson2`（dab_105：成對可解析行 Pearson、可 round；常數欄/不足 2 行=UNKNOWN）
   - +5 測試；reqloop 全組（checks+repair+g2+g1_gate）**77 passed**（r978 為 72）
2. **e013 小批凍結**（`ops/reqloop/g2/smoke_e013/`）：pi-C 臂 3 真草稿——
   dab_055(bad, lab 0/1)、dab_426(bad, lab 0/1)、dab_105(good, lab 1/1)。
   草稿/資料 hash 凍結；source 引用 e013 score.json（只引用不重跑）；hidden_after=UNKNOWN。
3. **before（本地，與 lab 記錄一致）**：dab_055 FAIL/FAIL；dab_426 格式 PASS＋重算 FAIL；
   dab_105 PASS/PASS。→ 本地裁判與 lab hidden 記錄方向一致（bad 被抓、good 放行）。
4. **live run 已啟動**（pid 1987180，6 格，qwen 同模型同預算 ≤2 輪/格；
   stdout 有緩衝——進度看 `ops/reqloop/g2/smoke_e013/runs/*.json`；log /tmp/g2_e013_run.log）。
5. 紀律：不讀 hidden/scorer；不向修復模型給 hidden 答案；成本缺值 UNKNOWN；不 push/不動 main；
   只跑相關測試；不宣稱任何提升。

## Next（r982）
1. 收 e013 小批 6 格結果（runs/ 與 log）；兩臂對照彙總＋誠實停因；若某臂換模型須同模型對照（紅線）。
2. 注意：good 草稿（dab_105）兩臂應 1 輪收斂；bad 兩份看 localized 能否依公開規則重算修正
   （dab_055 的 Int64 語意、dab_426 的「先選 storm 再取風速」是關鍵判讀）。
3. 若 6 格全落盤：寫審計（同 r978 格式：退步 0？初始 PASS 格 0 消耗？停因？成本 UNKNOWN 處理）。
4. 之後才談 e008 第二批；G1 題庫照舊不擴；E016 收尾（見上）。
