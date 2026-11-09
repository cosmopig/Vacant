# NOW.md — 現況唯一真源

## 位置
2026-11-09 r1306 redo：交付前 redo——審查點名本輪記錄步驟未實開之 6 檔，逐檔實開（auto-ci.yml 63 行 cat／effects summary 程式載入／g25 filing cat／ci-contract test read 全文／extract.py＋repair.py wc·blob·sha·docstring）＋重算依賴引用（filing 6 sha、凍結 4 錨、ci-contract 2 tests）→ **0 更正**。本輪新跑：freeze_check 9/9 OK、VERDICT: FROZEN_STATE_OK、rc=0＋19 passed（freeze_check 12＋anchors 5＋ci_contract 2）。0 模型呼叫、0 代碼改動。

## 數字（本輪實開檔著地）
- g2.5 filing（vq-el4.14、r1228）：三門全 PASS；phase3 9 cells＝7 fixed／2 unresolved／0 r2w；cost sessions 15／API 275／tokens 15087278（raw usage、缺值⇒UNKNOWN 不填 0）
- effects（d38d2eb2 快照、50 cells 單 rep）：policy30 g7/l6、feedback_once20 g7/l4，r2w 皆 0——開發選樣（e008/e013/e014 已見題），不宣稱 localized 優於 generic、不宣稱等 token
- baseline：g2-truth 手寫需求 localized 9/9／generic 7/9（開發選樣單 rep、不宣稱較好）
- 凍結：repair.py 2795 行／extract.py 1217 行／checks c7589c61／run_eval 332cd324；filing code 3/3＋sources 3/3 MATCH（freeze_check 本輪重驗）

## 待辦（依序）
1. 待人類：G3 --fire（vq-1zf）——不點火、不入 queue
2. 待人類：CI 通道裁決（auto-ci.yml disabled_manually＝服務端狀態、檔內無 enable/disable 聲明；不重診斷、不翻開關）
3. vq-el4 46/46 全閉；/srv/vlab/queue 空；無新人類指示（ops/ 最新仍 11-07＋本輪附帶審查）
4. 下輪：新 HEAD CI 首一次讀取（不 poll）；維持資深審查指示（凍結錨守衛＋CI 合約、fail-closed、輪末 VERDICT: FROZEN_STATE_OK）

## 紅線
- 不碰 main；不自 push（loop 自推）；.github/workflows/ 只讀；不讀 /srv/eval hidden＋scorer
- 凍結 4 檔＋g2.5 filing 不改；/srv/vlab/queue 不放新任務
- 缺值＝UNKNOWN（None）不填 0；不宣稱 localized 優於 generic；不宣稱等 token
- G3 待人類 --fire；無 reset/rebase；無 sleep poll；0 模型呼叫
