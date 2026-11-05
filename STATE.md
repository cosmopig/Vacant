
## r1028（11/05）vq-5nz.18：本地門 vs 獨立 scorer 分歧根因修復（歧義→UNKNOWN，TDD）

**結果：4 分歧格中 2 題（4 格）判定為檢查器缺陷並修復；dabstep-1753 判定非檢查器缺陷（轉 vq-6rp）。vq-5nz.18 已閉。

1. **dabstep-1273（3 格本地假 PASS→獨立 reward 0）**：`_scheme_fee_avg` 靜默 `bool(None)=False`
   排除 is_credit=null 行（123 行→0.117667）；owner 口徑含 null（144 行→0.120132，manual.md
   明示 null＝適用所有值；effects 純數字 0.120132 得 reward 1，e014 prose 同值被拒＝格式非值）。
   修：匹配行 is_credit=null → UnknownSource→UNKNOWN。
2. **dab_055（1 格本地假 FAIL→獨立 reward 1）**：`mean_int_col` 靜默忽略 544 個
   '630308[495000-801000]' 型格（312 純整數→2199.55）；owner 口徑取首數值（856 行→2081990）。
   修：任一格非空非純整數 → UnknownSource→UNKNOWN；'100.0'→100 各語意一致仍解析。
3. **重排**：`check_plain_recomputed`/`check_kv_recomputed` 先驗交付物格式（FAIL 屬交付物事實）
   再重算（資料側可 UNKNOWN）——保「bad 草稿必有一條必需 FAIL」紅線（e014 prose 草稿仍 FAIL）。
4. 防洩漏：重算值與兩種解讀值皆不進 detail/evidence（僅引歧義格原文）。
5. 證據：effects 凍結批 6 格重放——dabstep-1273 4 格、dab_055 2 格全 UNKNOWN（原假
   PASS/FAIL）；dabstep-1753 4 格本地與獨立同向未解決＝模型側硬缺口（vq-6rp，不改驗證器）。
6. 紀律：未讀 scorer.py/hidden；effects 快照只讀；tests/test_reqloop* **125 passed**（+3 先紅後綠）；
   未 push；0 模型呼叫。

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

## Next（r1029）
1. vq-6rp（dabstep-1753 模型側硬缺口）待點名：需先由需求方給出可執行 acceptance 口徑，
   否則按 H-1 前提不成立處理；不讀 scorer.py/hidden 設計解法。
2. vq-5nz.6（G2 停滯草稿換方法驗證，預註冊待點名）：點名前不發射（未點名＝未發射紅線）。
3. vq-p9g：CI 穩定 xpass 後除 xfail marker；vq-ifn：P99 門重設計（鑑別測試）。
4. 同型邊界判定已記錄於 vq-5nz.18 描述：count_if/zcount3/col_stats/max_row_first 的
   「不可解析格跳過」屬可辯護口徑（無觀察分歧）；未來 effects 若現同型分歧再按 vq-5nz.18 流程處理。
5. 紀律：未點名＝未發射；缺值 UNKNOWN；不向修復模型餵 hidden 答案；不 push/不動 main。
