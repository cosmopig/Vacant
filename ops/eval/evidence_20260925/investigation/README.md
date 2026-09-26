# 調查（2026-09-26）：零設定 Vacant 在 DABstep 上為什麼沒有量到差別

總報告：[`docs/ZERO_CONFIG_EVAL_REPORT_2026-09-26.md`](../../../../docs/ZERO_CONFIG_EVAL_REPORT_2026-09-26.md)（第七到十一節用的就是這裡的東西）。

## 怎麼做的

人類要求「不要開太大量的 workflow，精準地找到問題」。所以只開了兩個小 workflow，每個 agent 都是**唯讀**、每個數字都要附 檔:行：

| workflow | agent | 做什麼 | 輸出 |
|---|---|---|---|
| `verify-dabstep-results`（`wf_ddd550e2-42a`，2026-09-26 早） | `recompute:scores`、`recompute:costs`、`recompute:vacant-behaviour`、`critic` | 三個 agent 各自從原始檔重算分數／花費／Vacant 的動作，批評者對照 | `verify_dabstep_results.json`；更正寫進結論檔 §七 |
| `why-zero-config-null`（`wf_65a4afe4-f8e`） | `past-results` | 過去（09-25 之前）量過「Vacant 有沒有讓交付變好」的每一個實驗：誰握著生成、裁判是什麼、效果多大、原檔准許的說法 | `past_results.{json,md}` |
| 同上 | `failure-taxonomy` | 正式批次 77 題主要分析裡每一個失敗的跑（82 跑）分類；錯答案 27 跑逐一讀逐字稿；零設定檢查的上限 | `failure_taxonomy.{json,md}`；它用的唯讀抽取腳本在 `helpers/` |
| 同上 | `literature` | 只用 `docs/LITERATURE_GAP_2026-09-18.md` 已查證的條目，回答文獻怎麼預測這個結果 | `literature.{json,md}` |

兩個 workflow 的腳本原樣存在 `workflow_*.js`（腳本裡的路徑是當時這台雲端機器的暫存區）。
`*.md` 是同名 `*.json` 的可讀版（內容相同、只換排版）。

另外一份不是 agent 做的：`two_runs.json`＝`ops/eval/formal/explore_two_runs.py` 的輸出——把每一題的 A、C 兩跑當成
同一題的兩次獨立作答，估「沒交就重開一跑」和「兩跑答案對不對得上」。**探索性**：同一批題、事後才想到、不是預註冊。

## 我另外對過的

agent 的關鍵數字寫進總報告之前，我逐一回原檔核對過：r447 的 +19.17（p＝0.0003）、R460R 五次的 CONFORM−OFF 與 H-MIX−CONFORM、
G 實驗的 p＝0.4531、R535 的 S1 5/50 vs 48/50；失敗分類裡「gemma C 第 44 題第 6 回合已經算出 61.855069、到第 15 回合都沒寫檔」
與「gemma C 33 個失敗裡 30 個沒走到交件前檢查」（後者用 `formal/runs.json` 的 `vacant_check.stop_reached` 獨立數過）。

## agent 自己寫下的限制（摘要；全文在各 json 的 `caveats`）

- 過去實驗：r447、r461、EQ5 的數字引自彙整文件（`VACANT_ARCHITECTURE_AND_RESULTS`／`JOURNEY`），沒有逐一開原始裁決檔；R530／R533／R534 沒找到收官數字。
- 失敗分類：「答案已經在手上」是從模型自己的思考文字抽出來、用那一題的評分程式評過，約 15 跑人工讀過上下文；沒有重跑。
  第 67／68／69 題歸為推理錯、第 60 題歸為標籤問題，是 agent 的判斷。
- 文獻：那一批 109 筆沒有一篇讀過全文，全部是摘要層級；「放在 agent 迴圈外、只看紀錄的監控能不能提升正確率」查證過的文獻沒有涵蓋。
