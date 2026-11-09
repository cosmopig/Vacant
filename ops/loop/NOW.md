# NOW.md — 現況單一事實來源

## 位置
2026-11-09 r1318：維護／驗證輪（0 代碼改動、0 模型呼叫）。vq-el4 50/50 全閉、唯一剩 vq-1zf（G3）待人類 --fire（不點火、不入隊）。本輪：上輪簿記 commit 後新 HEAD 之 CI 一次讀取（不 poll）＋守衛套件複驗＋freeze_check 10/10 OK。

## 數字（本輪實測落地）
- CI 一次讀取（無輪詢）：現 HEAD qwen27b@b4f170e1d／worker@aa40b5623／argon@19fa81b22 無 ci/<sha>.json → UNKNOWN；state.json idle=true；LATEST 三分支皆綠：qwen27b@3ea3c69fa 5080/0/74（840s、rc0）／worker@c2242076c 5080/0/74（829s、rc0）／argon@706e26972 5080/0/74（842s、rc0）
- 最近綠燈祖先＋diff（本輪新驗證）：worker c2242076c 為 aa40b5623 直接父、argon 706e26972 為 19fa81b22 直接父（merge-base --is-ancestor 驗證）；qwen27b 3ea3c69fa 為 b4f170e1d 之祖先（驗證）；三現 HEAD 對其綠燈祖先之 diff 各僅 4 簿記檔（NOW/STATE/ops 鏡像，git diff --stat 驗證）、0 產品檔
- 守衛套件（本輪新跑）：21 passed in 2.78s（freeze_check 14／anchors 5／ci_contract 2）
- freeze_check（本輪新跑、簿記前）：10/10 OK、VERDICT: FROZEN_STATE_OK rc=0（diff 0×2／filing 6/6 MATCH／g3gate NOT_FIRED／bk 同步／wt clean 3/3）
- 隊列：/srv/vlab/queue 空；tickets/open 空；ops/ 最新人類指示仍 11-07＋附帶審查；G3（vq-1zf）待人類 --fire

## TODO（依序）
1. 待人類：G3 --fire（vq-1zf）——不點火、不入隊、0 模型呼叫
2. 待人類：CI 通道裁決（auto-ci.yml disabled_manually；不重診、不翻開關）
3. 下一輪：本輪簿記 commit 後新 HEAD 之 CI 一次讀取（不輪詢）；維持審查指示（凍結 anchor 守衛＋CI contract＋VERDICT: FROZEN_STATE_OK）；CI 若仍無 json，照實記 UNKNOWN、不等待

## 紅線
- 不碰 main；不自 push（loop 自 push）；.github/workflows/ 只讀；/srv/eval hidden+scorer 不讀
- 凍結四檔＋g2.5 filing 不動；/srv/vlab/queue 不擺新任務
- 缺值＝UNKNOWN（None）、不填 0；不宣稱 localized 優於 generic、不宣稱等 token
- 不 reset/rebase；不 sleep 輪詢；0 模型呼叫；不以文件改動偽造進度
