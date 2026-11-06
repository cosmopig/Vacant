# NOW

## r1136（2026-11-06，未提交 @ auto/qwen27b）

完成 11-06#4「獨立可見檢查給出可重現的內容反例」＋工單「目前行為」要素——**此前缺的離線 baseline 命令**。
交付（1 檔＋1 測試，純新增 147 行，不改既有行為）：
- `vacant_network/reqloop/g2.py`：新增 `--baseline`（離線、不呼叫模型、不發射、不改凍結檔）：對
  **目前（未修復）**草稿跑獨立可見檢查（run_requirement_checks），逐條目輸出 status（PASS/FAIL/UNKNOWN）
  ＋可重現內容反例（detail/evidence）。這是發射前的「before」基準——沒有它，真跑後無法證明「修復只改未滿足產物」。
- `tests/test_reqloop_g2.py`：新增 `test_realtask_baseline_offline_and_leakfree`（兩草稿皆真壞＝各有 required FAIL；
  重算答案 1628/0.020500 不出現於整段 JSON；草稿自身錯值 2081990.36/0.120132 可出現＝內容反例；main --baseline 回 0）。

驗證（離線、零模型呼叫）：
- `python3 -m vacant_network.reqloop.g2 --manifest ops/reqloop/g2/realtask_manifest.json --baseline` → EXIT=0；
  兩草稿 required 0/2・0/1 PASS（dab_055 not_an_integer＋均值未取整；dabstep-1273 not_a_number prose）。
- 整段 `--json` 輸出＝2656 bytes（重算自 live 命令 `… --baseline --json | wc -c`＝2656；in-code `len(json.dumps(...).encode())`＝2655＋print 換行 1）：1628/0.020500 缺席、2081990.36/0.120132（草稿自身錯值）在場＝內容反例。
- pytest：test_reqloop_g2.py 40/40 過；reqloop/repair/checks 掃全部過。

必附口徑：離線（不呼叫模型、不發射）；測量不是門（算出＝0；PASS/FAIL 是結果、不是失敗）；缺值＝UNKNOWN；
不宣稱 localized 較好（開發選樣、單 rep）。真實 6550d7a8 切片仍 **NOT_fired**（發射要授權、要模型流量）。

## r1135（2026-11-06，已提交 0fa90edd @ auto/qwen27b）

完成 11-06 最高優先 #2：effects2_20261106（28 格 @4d4b8102，排除 dabstep-1753）raw 彙整必答。
交付：`ops/audits/effects2_20261106_analyze.py`（`--selftest` 負控先跑，SELFTEST_OK）＋
`ops/audits/effects2_20261106_analysis.json`（RC=0，ANALYSIS_OK）。bd vq-5nz.49 已關（commit＋驗收行）。

**三問（同起點草稿＋同預算，11-06#2）**
- 同草稿公平性：14 題雙臂 `draft_sha256`（原草稿目錄指紋）全部相等；manifest 16 檔 pin 與快照檔案全相符。
- ① localized 是否多修：本批 bad9 localized **9/9** vs generic **7/9**（generic blocked：dab_055 max_rounds、dabstep-10 stalled）→ 本批內 localized 多修 2 題（dabstep-10、dabstep-23）。
- ② 對→錯：good5 雙臂全 pass（localized 全 no_gap 0 呼叫），對→錯 **0**、tamper **0**。跨批（同 9 題 vs d38d2eb2 逐臂）：generic 7/9→7/9（dabstep-10 退步、dabstep-1273 新增修復）；localized 6/9→9/9。
- ③ 成本：bad9 localized 347 calls/9,691,033 tok vs generic 235 calls/5,576,588 tok（差 112 calls/4,114,445 tok，買 +2 題修復；差額最大格 dabstep-10 +5.82M tok/+132 calls）；good5 localized 0 呼叫 vs generic 49 calls/1.20M tok（省）。全 14 題 sessions 16(g) vs 11(l)。

**必附口徑**：開發選樣（e008/e013/e014 已見題）、單 rep、單碼態；本批排除 1753，跨批只比同 9 題；
上列成本數（235/347 calls、5,576,588/9,691,033 tok、差 112 calls/4,114,445 tok）已逐格自
contrast/g2_result_*.json raw cost 重算核實；multideliv 資料夾（summary.md 等）屬 r1104 另一
FIRED 批次（draft 集合無重疊），不影響本批口徑。
dabstep-10 逐臂方向在兩批間翻轉＝邊界題單 rep 變異 → **不宣稱 localized 較好**；無硬 token 上限；
repair_sessions≠API 請求數；tokens 缺值＝UNKNOWN（localized good5 5 格 tokens=None，不填 0）；
hidden_after 全 UNKNOWN（本地無權重跑）；tamper/UNKNOWN 不算成功。

## 待辦（唯一）
- 11-06#4 真實 CSV/JSON 任務切片：manifest `ops/reqloop/g2/realtask_manifest.json`（sha **6550d7a8…**，
  e013 dab_055 CSV 均值＋e014 dabstep-1273 JSON 費率，2 草稿×2 臂＝4 格）已凍結 **NOT_fired**，
  6 元素 ticket 齊；**待授權才跑**（要模型流量）。
- 9329be88 manifest 待辦：已核實解除（該 sha 即 effect_manifest.json 實際 sha；舊 NOW 待辦已不在）。

## 紅線（維持）
- 不碰 main；不自 push（loop 自動 push auto/qwen27b）；不讀 /srv/eval hidden/、scorer.py；
- 缺值=UNKNOWN 不填 0；不為「每輪有 commit」加 regex/靜態 prompt/未授權重跑/純文件修補；
- 本輪未改產品碼（審計腳本＋JSON 為 11-06#2 指定交付物，非墊場）。

## 下輪
- 若授權：跑 6550d7a8 切片（離線三門先過：verify_frozen＋--dry-run＋**--baseline**（無洩漏＋目前行為基準），再 fire）。
- 未授權：維持 effects2 不動（不補快照、不排除失敗、不加重試換好結果）。
