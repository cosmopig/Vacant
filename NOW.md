# NOW.md — 現況（每輪覆寫，≤3KB）

## 狀態（2026-11-12 r1479；票 P20261112_0119-2 完成→done/）
- **r1479：G3.3 H2 判定落定＝H2_REFUTED → 停止規則啟動、G 系列停止、候人類裁決：**
  - dab_725 第 3 次獨立 extract（glm53、同 input 9ba533c0…）：5 需求 0 確定性（全 deliverable_not_in_request）；3 呼叫軌跡 2→0→0、達 1/3 → 單呼叫 H0 門＝呼叫隨機（非孤立漂移）。
  - 成本 1 通 7249 tok（raw 帳本）、0 answer 呼叫、完整批未發射。
  - 證據：`ops/audits/g3_3_h0_stability_report.json`；假說檔 H2 標記 REFUTED；驗收 selftest OK＋3 測 RC=0；commit `2d01c6463`。
  - **上報人類（停止規則）：G 系列停止。候裁：解凍 extract.py/checks.py（交付物命名強化／重算集擴充）或終止 G 系列（假說 §5-3）；vq-kax（G3 重發殘留）維持 IN_PROGRESS 候裁。新 G 系列工單不接；不加同題重試／靜態 prompt／錯誤字串 regex。**
- r1478（前輪）：腳本＋單測已寫（4509bd9e7、rc=124 未收尾）；本輪補完驗收＋--run＋簿記。

## 紅線（契約，不改）
- 無 push（迴圈自推 auto/qwen27b）、無 main、無 reset/rebase；.github/workflows/ 只讀。
- 凍結 4 檔不改；g3_1/g3_2 歷史不改（本輪僅按票更新 g3_3 假說檔狀態段）。
- 不讀 /srv/eval/hidden/ 或 scorer.py；缺值 UNKNOWN 不填 0。
- 不寫 /srv/vlab/queue；不 poll CI；不跑 full pytest。

## 未完成（≤3，交接下輪）
1. **G 系列候人類裁決**（H2_REFUTED 停止規則）：解凍 extract/checks 或終止 G 系列；vq-kax 候裁；新 G 票不接。
2. **worker 收斂→收口**：票 2158-1 審查＋升上；worker 簿記同步→freeze_check 12/12（r1476 #3）。
3. CI：mainline＋argon 紅燈同源（worker 殘留 freeze_check 下游 2 項），候 worker 收斂轉綠；不 poll。

## 下輪入口（≤3）
- G 系列工作＝停止（候裁）。做 worker 收斂檢查（workerloop 狀態＋票 2158-1 產物＋WIP commit）→審查升上→12/12。
- 守衛：anchors 綠（下輪補）、freeze_check 10/12（2 紅皆 worker 歸因）。
- 若人類對 G 系列裁決（解凍／終止）→依裁決開新票；不代決。
