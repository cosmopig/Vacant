# T06 — 換模型：qwen3.8-27b（S4；H-12：數字不跨模型轉移）

**前提**：T04 的 state＝EFFECTIVE。**規模**：只新增計畫檔；0 行碼。

## 步驟
1. 複製 `screen16_pi_gemma12b.json` → `screen16_pi_qwen27b.json`、`redo1_…` → `redo1_pi_qwen27b_polyglot34.json`：
   只改 `id` 與 `providers`（provider 名稱看 `~/.pi/agent/models.json`，過去是 `lms1003qwen`、模型 `qwen/qwen3.8-27b`）。
   `prereg.question` 的模型名一起改，其餘一字不動。commit。
2. ⚠ 這 16 題是用 gemma 的結果挑的，對 qwen 不一定是「時過時不過」的題。所以 qwen 的篩選規則照舊，
   但 NO-GO 時結論要寫「篩選題組是替 gemma 挑的」，不可以寫成「qwen 上沒效」。
3. 照 T02／T03／T04 跑與寫結論（root 與結果檔名帶 `qwen27b`）。

## 禁止
- 兩台機器不要同時跑兩個模型的批次在同一台上（延遲是實驗條件）。
- 不把 gemma 與 qwen 的對數合起來算一個 p 值。

## 票尾（做完填這三行，再把票移到 done）
- commit：
- 驗收指令的實際輸出（逐字貼最後一行）：
- 沒做完的：
