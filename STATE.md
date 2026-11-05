
## r1043（11/05 09:26–09:50）讀 contrast3 全結果：4/6 格閉合、2 敗格精確歸因＋新票 vq-5nz.21

**結果：P1 對照 6 格全讀完（本輪無 repo 改動、無 commit；證據 `~/dev/ops/contrast3_20261105/`）。**

1. **contrast3（3 草稿×2 臂，單次重現 dev 樣本，不作效力宣稱）**：before(d38d2eb2) generic 3/3·localized 1/3；
   after(8e6fa47d) generic 2/3·localized 2/3。dab_507 兩臂皆 PASS（after 成本 loc 1.19M→21.7K tok）；
   dabstep-23 generic PASS/localized stalled；dabstep-10 generic stalled/localized PASS（翻轉，n=1 不可歸因）。
   獨立 scorer 與本地門 6 格全同向（4 PASS/2 FAIL、零分歧）。成本真值見 before_after.json（api_model_calls_true/tokens_true/wall_ms_total）。
2. **dabstep-23 localized 精確歸因**：r1 同一 python3 一行式重複 34 次、每次同一 SyntaxError（`;` 後接 `if` 非法）；
   detect_tool_loop 已觸發、r2 提示已點名「本輪禁止重複該命令、已得到結果後直接推導」——但該命令每次都失敗、從無結果；
   r2 模型寫出正確 calculate_fraud.py 並跑通（結果可得）後仍重複壞命令 15 次、未寫 answer.txt。
   → 新票 **vq-5nz.21**（P2）：「重複命令每次都失敗」應針對性提示錯誤類＋具體語法規則（寫 .py 執行、跑通即寫入交付物）。
3. **vq-5nz.19**：worker 29a10294 15→1（`test_reqloop_g1_gate.py::test_real_fixture_bank` assert 20==0）；
   HEAD 已進 30e1e7de（CI 未跑完）——仍等助手修綠再驗收。vq-6rp：/srv/vlab/queue 仍空（0 任務）。
4. 紀律：未讀 hidden/scorer、未寫離線審計腳本充當進度、未 push、未動 main、未跑全量 pytest。

## r1029（11/05）審查輪 20261105：P0 核對＋P1 單格對照發射＋P2 crash→giveup 提示（vq-kpb）

**結果：P0 核對完成（2aa0c077 五項修復全數在樹）；P1 已發射（背景跑，待收）；P2 TDD 全綠。

1. **P0（審查指示）**：`2aa0c077`（auto/argon）已含於 auto/qwen27b——merge `ca5dce9c`＋
   `c7077528`（EACCES 寫入修復）；五項修復逐項核對在樹：prepare_workspace 剝離
   verifier/params/recompute/note（20431c0）、crash 偵測誤報排除＋`tool_execution_end`
   且 `isError≠False` 才掃、period-2 交替死迴圈、`count_if`＋CSV 引號逗號 hint、
   policy30 `wall_ms_total=4398675` 補齊。reqloop 152 測試全綠。
2. **P1（審查指示）**：dabstep-23（迴圈）/dabstep-10（表頭+1）/dab_507（引號逗號）
   3 草稿 × 兩臂 × 1 輪單格對照，獨立目錄 `~/dev/ops/effects_p1_20261105`（未觸凍結批）。
   base 副本逐檔 hash 對照凍結一致（data 符號連結解引用；首次發射死連結失敗證據
   `failure_0843_dangling_symlink.json`，修後重發）；before＝凍結 independent.json
   （localized 敗：dab_507 fb20、dabstep-23 兩格、dabstep-10 兩格；generic 3 格皆 PASS＝
   regression 檢查）；after＝當前 HEAD 重跑＋independent_score 獨立評分；缺值 UNKNOWN。
3. **P2（審查指示）**：TDD（先紅後綠）——localized 提示在上一輪 `crash_giveup_suspected`
   觀察時新增針對性行：禁止裸 `except: pass` / `except: return False` 靜默吞掉解析錯誤、
   讓例外浮現或顯式計數（dabstep-1753 失效模式）；generic 對照臂定義不變；hint 靜態、
   不帶重算值。reqloop 4 檔 **155 passed**＋repair selftest 11/11。
4. 紀律：未 push、未讀 hidden/scorer.py、effects 快照只讀；P1 背景跑（progress.json 實時）。

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
