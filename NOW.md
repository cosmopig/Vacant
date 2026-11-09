# NOW.md — 現況單一事實來源

## 位置
2026-11-09 r1318 redo：redo 審查指出 r1318 未實際開啟任務點名五檔——本輪五檔全數實開＋依賴值獨立重算，0 更正。vq-el4 50/50 全閉、唯一剩 vq-1zf（G3）待人類 --fire（不點火、不入隊）。

## 數字（本輪實測落地）
- 五檔實開（本 redo 輪）：auto-ci.yml 63 行/2695B、最後 commit d9f27dd27、grep enab|disab 0 命中（rc=1、檔案內無啟禁聲明）；effects 60228B/sha a710f7e4、50 格(50/45)、policy30 w2r g7/l6 r2w 0、once20 w2r g7/l4 r2w 0、scope_note 逐字（開發選樣/無硬 token 上限/單 rep 不宣稱優/hidden_after UNKNOWN/缺值 None）；g2.5 filing 4681B/sha 6e5afb46、三 gate 全 PASS（g1 39/39 false_acc 0／real14 9/9 errors 0／phase3 fixed 7 unresolved 2 errors 0）、code 3-sha＋sources 3-sha 本輪獨立重算 6/6 MATCH；extract.py 1217 行/blob e757aec5/sha 51abfec3、規則 1-4 逐字；repair.py 2795 行/blob 5147f8c3/sha c860fc23、規則逐字（FAIL→UNKNOWN 不算修好／退步記 regressed／連續兩次無缺口⇒停止）
- CI 一次讀取（r1318、無輪詢）：現 HEAD qwen27b@b4f170e1d／worker@aa40b5623／argon@19fa81b22 無 ci/<sha>.json → UNKNOWN；state.json idle=true；LATEST 三分支皆綠（qwen27b@3ea3c69fa 5080/0/74／worker@c2242076c 5080/0/74／argon@706e26972 5080/0/74）
- 最近綠燈祖先＋diff（r1318 驗證）：worker c2242076c、argon 706e26972 為現 HEAD 直接父；qwen27b 3ea3c69fa 為現 HEAD 之祖先；三現 HEAD 對綠燈祖先 diff 各僅 4 簿記檔、0 產品檔
- 守衛套件（本輪新跑）：21 passed（freeze_check 14／anchors 5／ci_contract 2）
- freeze_check（本輪新跑、簿記前）：10/10 OK、VERDICT: FROZEN_STATE_OK rc=0
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
