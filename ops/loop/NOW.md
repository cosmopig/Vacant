# NOW.md — 現況單一事實來源

## 位置
2026-11-09 r1317 redo：redo review 點名之五檔（auto-ci.yml、effects_20261105_summary.json、g25_all_gates_filing.json、extract.py、repair.py）本輪全數實際開啟＋依賴值獨立重算，0 修正；review 指出的 sha 值本輪以 git rev-parse／LATEST json 重算，NOW.md 只含重算值。現況：vq-el4 50/50 全閉、唯一剩 vq-1zf（G3）待人類 --fire（不點火、不入隊）；LATEST 三分支全綠（argon@706e26972c88db179cc6734d0a7ffe14e3805c25 5080/0/74＝r1317 輪 running 之 run 本輪收口綠燈）；guard suite 21 passed；freeze_check 10/10 OK VERDICT: FROZEN_STATE_OK；三分支簿記同步、in-scope diff 0×2。

## 數字（本輪實測落地）
- 五檔實開（本輪）：auto-ci.yml 63 行/2695B、grep enab|disab 0 命中（rc=1）、最後 commit d9f27dd27、4 測試步（reqloop*/FROZEN_SOURCE_SHA stepchain/repair --selftest）、concurrency cancel-in-progress；effects 60228B/sha a710f7e4、50 cells（current 50/local 45）、policy30 w2r 13（g7/l6）r2w 0、once20 w2r 11（g7/l4）r2w 0、scope_note 逐字；g2.5 filing 4681B/sha 6e5afb46、gates 3 門 PASS（g1 39/39 false_acc 0／real14 9/9 good 5 errors 0／phase3 9 cells fixed 7 unresolved 2 errors 0）、code 3 sha＋sources 3 sha 本輪獨立重算 6/6 MATCH；extract.py 1217 行/blob e757aec50c16bc6481cd88545672d50884c83f40/sha 51abfec319d21813…；repair.py 2795 行/blob 5147f8c3ea1b5e9ee50531aca0382971e912c243/sha c860fc235a6102a67f…
- Guard suite（本輪新跑）：21 passed（freeze_check 14/anchors 5/ci_contract 2）
- freeze_check（本輪新跑、簿記前）：10/10 OK、VERDICT: FROZEN_STATE_OK rc=0（anchors 5 身份齊/ci_contract 2 身份齊/diff 0×2/filing code 3/3+sources 3/3 MATCH/g3gate NOT_FIRED+PLAN_OK/bk_state+bk_now 同步/wt_clean 3/3 clean）
- CI 一次性重讀（無輪詢）：LATEST qwen27b@3ea3c69faf7cf5e2ab46648de553786daf5de17d 綠 5080/0/74（840s rc0）、worker@a550efa7e92141006471c8b5b5c528e5a08c2e01 綠 5079/0/74（836s rc0）、argon@706e26972c88db179cc6734d0a7ffe14e3805c25 綠 5080/0/74（842s rc0、per-sha artifact 存在）；目前三分支 HEAD（本輪 rev-parse：ae9cbb443606642d8d2157908cdf4d24b62c9f84／c2242076cc435cd56010a01e4c4f5c6a6527fc7c／0605fab6208acdb5ddaba327877c80029177a60e）無 ci/<sha>.json；state.json 已不在（瞬時 run-state 檔，不再引用、缺值 UNKNOWN）
- 隊列：vq-el4 50/50 全閉（0 open）；唯一剩 vq-1zf（G3）待人類 --fire；/srv/vlab/queue 空；tickets/open 空；ops/ 最新仍 11-07＋本次隨附 review、無更新人類指令

## TODO（依序）
1. 待人類：G3 --fire（vq-1zf）——不點火、不入隊
2. 待人類：CI 通道裁決（auto-ci.yml disabled_manually＝server-side state；不重診、不翻開關）
3. 下一輪：對本 redo 輪簿記 commit 後之新 HEAD 一次性 CI 讀（不輪詢）；維持 review 指示（凍結 anchor guard＋CI contract、fail-closed、收尾 VERDICT: FROZEN_STATE_OK）

## 紅線
- 不碰 main；不自 push（loop 自 push）；.github/workflows/ 只讀；/srv/eval hidden+scorer 不讀
- 凍結四檔＋g2.5 filing 不動；/srv/vlab/queue 不擺新任務
- 缺值＝UNKNOWN（None）、不填 0；不宣稱 localized 優於 generic、不宣稱等 token
- G3 待人類 --fire；不 reset/rebase；不 sleep 輪詢；0 模型呼叫；不以文件改動偽造進度
