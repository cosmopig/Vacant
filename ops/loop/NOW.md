# NOW.md — 現況（≤3KB）

## 輪次／階段／狀態
r1430（2026-11-11）：**P20261111_0645-1 G3 首發後檢＋重發收案完成**（ticket→done；vq-el4.97 三條驗收全綠已關；0 產品碼、0 model calls）。
- 重發（r1429 碼、07:30Z、out=~/dev/ops/g3_fire_20261111b）：12 格 **4ok／6err／2not_run**——native_pi 4/4 ok（AMEND-2 600s 生效、147–226s/格）；glm 6× `turn_limit`＝prompt 名實不符（4 題 instruction 全 agent 式×`~/.local/bin/glm` L70-71 硬傳 `--max-turns 1 --enabled-tools none`，逐字核對）；dab_216 2 格 not_run＝QuotaGuard max_calls 後備 28（g3.py:868）<實際 31（pi 每格 ~7 calls）→停不重試（非 token 額度）。
- 08:05 postmortem 兩根因核對吻合（記票尾）；token_limit 修復證據：首發 8/8 token_limit @input 32.6k–39.3k（>30k 預設）→重發 0/6 @36.6k–39.3k（<60k）。
- 兩次發射 glm 失敗（8＋6 格）全 infra 歸因、**不計入臂間比較**、不宣布「pi 贏」、不宣稱效果改善（同批非獨立樣本）；hidden_after 12×UNKNOWN。
- 守衛：92 passed＋FROZEN_STATE_OK 11 項＋審計摘要 live OK／負控制 rc=1。

## 下一步（下一輪）
- 待人類核准（08:05 建議；紅線「重發一次、不重試、預算欄位不動」未執行）：① turn_limit 選項 a——build_cell_prompt 頂部加顯式無工具覆寫指令（no-tool 臂身分不變）② max_calls 依「pi ~7 calls/格」重測或 fire 設定顯式宣告（理由寫回票面、不靜默放寬）③ 再發射須新人類核准檔。
- hidden 打分（首發 1＋重發 4 ok）；CI 裁決；後續修法已立工單待核准。

## 關鍵約束（紅線）
- 無 push（loop 自推 auto/qwen27b）、無 main、無 reset/rebase；.github/workflows/ 只讀。
- 凍結 4 檔不改（repair.py 2795 行／blob 5147f8c3…、extract.py 1217 行／blob e757aec5…、checks.py c7589c61…、run_eval.py 332cd324…）＋g25 filing（6 sha256）不改；r1419–r1421/r1429 解凍已釘（現值 g3.py 189f4e73…／test_g3 17c69ec8…／g3_conformance e6a6d6d4…／g3gate.py 367d88fe…／test_g3gate b3ea2177…；r1420＝AMEND-1、r1429＝AMEND-2 人類裁決之合法解凍，記於 GUARD_CONTENT_PIN）。
- /srv/eval/hidden/、scorer.py 不讀；anchors 5＋filing 3/3+3/3 每輪複驗。
- /srv/vlab/queue 不寫（0 項含隱藏）；送件照 vlab 慣例；無 poll CI；無 full pytest。

## 證據與下輪驗證點
- 重發 totals（本輪重跑）：`12 4 quota {'cells': 12, 'cells_run': 10, 'model_calls': 31, 'tokens': 132917, 'tokens_missing': False}`（~/dev/ops/g3_fire_20261111b/g3_result.json）。
- glm CLI 失敗來源：`sed -n '44p;70,71p' ~/.local/bin/glm` → `--max-tokens default=30000`、`--max-turns 1 --enabled-tools none`。
- max_calls：`sed -n '868p' vacant_network/reqloop/g3.py` → `n_tasks + (arms×tasks)×max_rounds`＝28；實際 31。
- 本輪改動＝票尾收案記錄＋簿記 4 檔×3 分支＋bd close＋ticket mv done；0 產品碼、0 model calls。
