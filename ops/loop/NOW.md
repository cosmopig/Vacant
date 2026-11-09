# NOW.md — 現況唯一真源

## 位置
2026-11-09 r1313：維護／驗證輪——CI 現 HEAD（qwen27b@82975bf8c）一次讀取＝running（始 07:41:20Z、不 poll）；守衛套件 20 passed＋repair selftest 13/13；三分支簿記同步。0 代碼改動、0 模型呼叫、0 新工單（vq-el4 49/49 全閉，無未完成項可開單）。

## 數字（本輪實測著地）
- CI 一次讀取（輪首、不 poll）：state.json qwen27b@82975bf8c running（始 07:41:20Z、參考全程 844s）；argon@ca78c53b7／worker@7a931ab3a 無 ci/<sha>.json；LATEST 三分支皆 green 且在分支（31dbb6c11／b30f71b4a／2e76bb3d58，各 5079 passed／0 failed／74 skipped）——較 r1311 記錄之 LATEST（5078/0/74）推進為較新綠跑
- 守衛套件（本輪新跑）：frozen_anchors 5＋ci_contract 2＋freeze_check 13＝20 passed
- repair --selftest（CI 門 4、離線 0 模型呼叫）：13/13 PASS rc=0
- 凍結 4 檔：repair 2795 行／blob 5147f8c3、extract 1217 行／blob e757aec5、checks c7589c61、run_eval 332cd324（anchor pin 未變）；g2.5 filing code 3/3＋sources 3/3 MATCH（freeze_check）
- vq-el4 49/49 全閉（0 open）；唯一 ready＝vq-1zf（G3）待人類 --fire；/srv/vlab/queue 空；tickets/open 空；無新人類指示（ops/ 最新仍 11-07＋附帶審查）

## 待辦（依序）
1. 待人類：G3 --fire（vq-1zf）——不點火、不入 queue
2. 待人類：CI 通道裁決（auto-ci.yml disabled_manually＝服務端狀態；不重診斷、不翻開關）
3. 下輪：CI 再一次讀取（本輪 qwen27b@82975bf8c running；若本輪簿記 commit 成為新 HEAD 則讀新 HEAD）；維持審查指示（凍結錨守衛＋CI 合約、fail-closed、輪末 VERDICT: FROZEN_STATE_OK）

## 紅線
- 不碰 main；不自 push（loop 自推）；.github/workflows/ 只讀；不讀 /srv/eval hidden＋scorer
- 凍結 4 檔＋g2.5 filing 不改；/srv/vlab/queue 不放新任務
- 缺值＝UNKNOWN（None）不填 0；不宣稱 localized 優於 generic；不宣稱等 token
- G3 待人類 --fire；無 reset/rebase；無 sleep poll；0 模型呼叫；不以改文件湊進展
