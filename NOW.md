# NOW.md — 現況唯一真源

## 位置
2026-11-09 r1309：實質進展（vq-el4.48 開→關）——審查指示 #3 機械化：freeze_check 新增 wt_clean（三分支 worktree in-scope 殘留守衛）。洞（本輪實證、TDD RED 先）：in-scope 殘留存在時舊 9 項仍 FROZEN_STATE_OK rc=0＝假綠；新檢查抓到（BROKEN 點名檔）；MANDATED 9→10。本輪新跑：20 passed（freeze_check 13／anchors 5／ci_contract 2、was 19）＋freeze_check 10/10 OK VERDICT: FROZEN_STATE_OK rc=0＋三分支同步（diff 0×2）＋三 worktree in-scope 狀態全 clean。0 模型呼叫。

## 數字（本輪實測著地）
- wt_clean（r1309 新）：attached→量 qwen27b/worker/argon 三 worktree in-scope（vacant_network/tests/ops）殘留（staged/未 commit/未追蹤、點名檔）；任一 worktree 缺＝未測量→BROKEN（fail-closed I-4）；detached（CI 沙盒）→只量 checkout 本身（r1300 被測 commit 口徑、detail 點名 scope、不冒充已量）
- 驗收：20 passed（was 19）＋freeze_check 10/10 OK rc=0（was 9/9）＋in-scope diff 0×2（auto/worker@2b7e98bef／auto/argon@ecb494a79 vs auto/qwen@c65c98173）
- CI 一次讀取（不 poll）：三分支現 HEAD（553aa1da/d7d64fc4/03b4e38f）皆無 ci/<sha>.json（r1306 redo sync 輪；runner 正跑 argon@0959f856、state.json running）；LATEST（舊 SHA）全綠 5078/0/74
- 凍結：repair.py 2795 行／extract.py 1217 行／checks c7589c61／run_eval 332cd324；filing code 3/3＋sources 3/3 MATCH（freeze_check 本輪重驗）

## 待辦（依序）
1. 待人類：G3 --fire（vq-1zf）——不點火、不入 queue
2. 待人類：CI 通道裁決（auto-ci.yml disabled_manually＝服務端狀態、檔內無 enable/disable 聲明；不重診斷、不翻開關）
3. vq-el4 47/47 全閉（vq-el4.48 本輪開→關）；/srv/vlab/queue 空；無新人類指示（ops/ 最新仍 11-07＋本輪附帶審查）
4. 下輪：本輪新 HEAD 之 CI 首一次讀取（qwen27b 簿記 HEAD／worker／argon sync HEAD、不 poll）；維持資深審查指示（凍結錨守衛＋CI 合約、fail-closed、輪末 VERDICT: FROZEN_STATE_OK）

## 紅線
- 不碰 main；不自 push（loop 自推）；.github/workflows/ 只讀；不讀 /srv/eval hidden＋scorer
- 凍結 4 檔＋g2.5 filing 不改；/srv/vlab/queue 不放新任務
- 缺值＝UNKNOWN（None）不填 0；不宣稱 localized 優於 generic；不宣稱等 token
- G3 待人類 --fire；無 reset/rebase；無 sleep poll；0 模型呼叫；不以改文件湊進展
