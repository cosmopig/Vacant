# G3.1 候選預註冊假說（待人類核准 → manifest 凍結 → 發射清單）

- 狀態：**候選（candidate）**。核准前不發射、不凍結 manifest；本檔 0 model calls。
- 依據（全部來自已入庫數據，不捏造）：
  - `ops/audits/g3_fire_20261111b_summary.json`＋raw（b 發：ok 4/12 全 native_pi；glm 臂 6/8 turn_limit＋2/8 quota）
  - `ops/audits/g3_fire_20261111_summary.json`（a 發：ok 1/12；glm 臂 8/8 token_limit）
  - `ops/audits/g3_fire_20261111b_interpretation.md`（本輪解讀；full_rloop content_reverify 0/8 輪、兩發合計）
  - `bd ready`：vq-kax（AMEND-3 已核准：build_cell_prompt 顯式無工具覆寫＋max_calls 依 pi 臂重測＋20261111c 重發一次）

## 1. 重發經驗總結：哪些環節易修／易停滯

**已實證可跑（易修＝已通）：**
- 需求擷取（glm53）：b 發 4/4 題成功、各 1 次呼叫（6611/7855/6563/7363 tok）——需求類型涵蓋
  均值/標準差（dab_129、dab_216）、中位數（dab_176）、雙總體分布＋均值/標準差/正態判斷（dab_144，14 req）。
- native_pi 基線臂（qwen3.8-27b，pi agent 工作區）：b 發 4/4 產出（14458–44174 tok）；
  a 發 3/4 的 300s timeout 在 b 發（600s/格）消失。

**易停滯（兩發一致、與需求類型無關）：**
- **glm 答題通道（reqlist_only＋full_rloop 兩臂）8/8 格停滯**：a 發 8/8 token_limit、
  b 發 6/8 turn_limit＋2/8 quota，全部死在 round 1 答題階段、`content_recheck`（g3.py:1001–1004）
  在控制流上未被觸及。4 種需求類型（均值/中位數/標準差/分布判斷）在同一通道上同樣停滯
  → 停滯是**通道層**故障（agent CLI 未產出純文本 answer 即撞 turn/token 上限），
  不是某種需求類型難修。
- **無法總結「哪類需求易修」**：因為 0/8 格產生過任何 content_reverify 輪次，
  修復數據點＝0。任何「某類需求更易修」的說法在本數據下都是未測得（UNKNOWN），不預註冊。

## 2. G3.1 可證偽假說（帶分母與判停規則）

### H1（主假說）——機制可達性
> 在 vq-kax 修法（build_cell_prompt 頂部顯式無工具覆寫＋max_calls 依 pi 臂 ~7 calls/格重測）
> 生效後，g3_fire_20261111c（同批 4 題 × 3 臂、不重試、預算欄位不動）中，
> **full_rloop ≥ 1/4 格完成 ≥ 1 輪 content_reverify，且該輪 ≥ 1 條 claim 由 checks 程式重算
> （PASS/FAIL/UNKNOWN 任一，非模型自評）**。

- 判定：c 發 raw 中 full_rloop 4 格 `content_reverify.rounds` 非空且含 `claims` 記錄。
- **證偽條件：0/4 格達標 → H1 被否決**，G 系列停在此層、升級人類（不自行再加提示規則工單）。
- 這是 G3.1 唯一必須先回答的問題；H2 只在 H1 通過時才進入判定。

### H2（次假說，條件於 H1 通過）——抓到並修好一種內容錯誤
> 在 H1 達標的格中，**round 1 出現已確認缺口（必需 claim FAIL 或缺必要答案項）的格數若 ≥ 1，
> 則其中 ≥ 1/1（即全部出現缺口的格）在 round 2 的 diff 中 fixed ≥ 1 且 regressed = 0**；
> 若 round 1 全格無已確認缺口，H2 記 **not_applicable**（不得記通過、不得記否決）。

- 口徑：diff 只在兩輪都有真實重算結果時才記（g3.py 既有守衛）；UNKNOWN 不算缺口也不算通過（I-4）。
- 這是**方向性、單 rep** 結論；不宣稱臂 superiority、不遷移到其他模型/題（H-12）。
- 顯式非目標：G3.1 **不**回答「R-loop 比基線多修好」——那需要 hidden 打分（人類/vlab 側）
  與 ≥2 rep，是 G3.2+ 的問題，本輪不預註冊、不預支結論。

## 3. 候選題單（發射清單）

| # | task | 批記 | 備註 |
|---|---|---|---|
| 1 | dab_129 | 同批（a/b/c 同題，不得當獨立樣本） | 4 req：mean_fare、std_dev_fare |
| 2 | dab_144 | 同批 | 14 req：dem/gop 均值/標準差/分布 |
| 3 | dab_176 | 同批 | 5 req：median_age |
| 4 | dab_216 | 同批 | 10 req：mean、std_dev |

- 發射範圍＝上表 4 題 × 3 臂（與 vq-kax 票面一致：20261111c、一次、不重試）。
- **候選（需另獲核准才入批）：** 2 題新未見描述統計題（均值/中位數/標準差同族，
  來自 dabstep 真實切片、e008/e014 同源）——僅在 c 發 H1 通過且 2M/日額度餘量允許時提議；
  核准前不發射、不佔額度。
- 選題口徑：不讀 hidden/scorer、不按隱藏分數反推；只要求「可見內容檢查能給結構化反例」
  （checks 可重算的 claim）。

## 4. 成本與停滯規則

- c 發預算欄位照 vq-kax 票面不動（daily_token_cap 2M、quota_fail_closed、不重試）；
  缺值 UNKNOWN 不填 0。
- 停滯規則（承接 2026-11-06 定案第 3 條）：若 c 發 H1 仍 0/4，停止沿同一路線新增錯誤字串
  regex／靜態提示／同題重試工單，升級人類裁決通道方案；連續 2 輪無功能程式變更即縮範圍。

## 5. 核准與凍結流程（G 系列自續）

假設（本檔 §2）→ 人類核准 → manifest 凍結（題單＋模型＋預算＋判停規則入 manifest、hash 入審計）
→ 發射（vq-kax → c 發）→ 審計摘要（g3_fire_20261111c_summary.json，同 b 發腳本口徑）
→ 解讀（帶分母、UNKNOWN 不填 0）→ G3.2 候選假說。
