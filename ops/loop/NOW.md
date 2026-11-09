# NOW.md — 現況唯一真源

## 位置
2026-11-09 r1317：維護／驗證輪（0 代碼改動、0 模型呼叫、0 新工單）——vq-el4 50/50 全閉、唯一剩餘 vq-1zf（G3）待人類 --fire（不點火、不入 queue）；審查 20261109_0911 指示 #1-5 全部維持。本輪要點：qwen27b@3ea3c69fa 上輪在跑→本輪收口綠燈 5080/0/74；守衛套件 21 passed；freeze_check 10/10 OK、VERDICT: FROZEN_STATE_OK；三分支簿記同步、in-scope diff 0×2。

## 數字（本輪實測著地）
- 守衛套件（本輪新跑）：21 passed（freeze_check 14／anchors 5／ci_contract 2）
- freeze_check（本輪新跑）：10/10 OK、VERDICT: FROZEN_STATE_OK rc=0（anchors 身份齊 5 passed／ci_contract 身份齊 2 passed／diff 0×2 @cc922716e、@706e26972／filing code 3/3＋sources 3/3 MATCH／g3gate NOT_FIRED＋PLAN_OK／bk_state＋bk_now 同步／wt_clean 3/3 clean）
- CI 一次讀取（不 poll）：qwen27b@3ea3c69fa 上輪在跑→本輪 green 5080/0/74（840s、pytest_rc 0）；現 HEAD 89716a48／cc922716／706e2697 無 ci/<sha>.json（state.json running argon@706e2697、ts 1794216498）；LATEST worker@a550efa7 green 5079/0/74、argon@c235031f green 5079/0/74
- 隊列：vq-el4 50/50 全閉（0 open）；唯一剩餘 vq-1zf（G3）待人類 --fire；/srv/vlab/queue 空；tickets/open 空；無新人類指示（ops/ 最新仍 11-07＋附帶審查 20261109_0911）

## 待辦（依序）
1. 待人類：G3 --fire（vq-1zf）——不點火、不入 queue
2. 待人類：CI 通道裁決（auto-ci.yml disabled_manually＝服務端狀態；不重診斷、不翻開關）
3. 下輪：CI 再一次讀取（本輪簿記新 HEAD＝qwen27b 本輪 commit、worker/argon 同步 commit；不 poll）；維持審查指示（凍結錨守衛＋CI 合約、fail-closed、輪末 VERDICT: FROZEN_STATE_OK）

## 紅線
- 不碰 main；不自 push（loop 自推）；.github/workflows/ 只讀；不讀 /srv/eval hidden＋scorer
- 凍結 4 檔＋g2.5 filing 不改；/srv/vlab/queue 不放新任務
- 缺值＝UNKNOWN（None）不填 0；不宣稱 localized 優於 generic；不宣稱等 token
- G3 待人類 --fire；無 reset/rebase；無 sleep poll；0 模型呼叫；不以改文件湊進展
