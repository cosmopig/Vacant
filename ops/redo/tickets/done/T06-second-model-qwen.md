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
- commit：screen16 計畫 `ops/redo/plans/screen16_pi_qwen27b.json`（92bad7505687）；結果 `ops/redo/results/screen16_qwen27b_REPORT.md`
- 驗收指令的實際輸出（逐字貼最後一行）：`screen16_pi_qwen27b: UNRESOLVED  16/16 對  A=13/16  R3=15/16  b=0 c=2  infra_void 對=0` ⇒ go_rule（c ≥ b+3）未達＝**NO-GO**
- 沒做完的：依 go_rule 停在篩選，不發射 qwen 的 34×5、不改條件重篩。結論只能寫：**篩選題組是替 gemma 挑的**——qwen 在這 16 題上 A 已過 13/16（平均 87 秒、0 次逾時），兩臂都過 13 對，重開幾乎沒有可補的失敗；不可寫成「qwen 上沒效」。要量 qwen 得用對 qwen 有難度、事先沒看過結果的題（另開票、另預註冊）。
