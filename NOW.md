# NOW

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
dabstep-10 逐臂方向在兩批間翻轉＝邊界題單 rep 變異 → **不宣稱 localized 較好**；無硬 token 上限；
repair_sessions≠API 請求數；tokens 缺值＝UNKNOWN（localized good5 5 格 tokens=None，不填 0）；
hidden_after 全 UNKNOWN（本地無權重跑）；tamper/UNKNOWN 不算成功。

## 待辦（唯一）
- 11-06#4 真實 CSV/JSON 任務切片：manifest `ops/reqloop/g2/effect_manifest.json`（sha **6550d7a8…**，
  4 格 e008/e013/e014 最小對照）已凍結 **NOT_fired**，6 元素 ticket 齊；**待授權才跑**（要模型流量）。
- 9329be88 manifest 待辦：已核實解除（該 sha 即 effect_manifest.json 實際 sha；舊 NOW 待辦已不在）。

## 紅線（維持）
- 不碰 main；不自 push（loop 自動 push auto/qwen27b）；不讀 /srv/eval hidden/、scorer.py；
- 缺值=UNKNOWN 不填 0；不為「每輪有 commit」加 regex/靜態 prompt/未授權重跑/純文件修補；
- 本輪未改產品碼（審計腳本＋JSON 為 11-06#2 指定交付物，非墊場）。

## 下輪
- 若授權：跑 6550d7a8 切片（verify_frozen＋--dry-run＋無洩漏檢查先過，再 fire）。
- 未授權：維持 effects2 不動（不補快照、不排除失敗、不加重試換好結果）。
