# NOW.md — 現況唯一真源

## 位置
2026-11-09 r1316 redo：redo 點出任務點名未實開的 5 檔（auto-ci.yml／effects_20261105_summary／g25_all_gates_filing／extract.py／repair.py）——本輪逐檔實開＋獨立重算（50 格 13 g7/l6＋11 g7/l4、0 假回歸、filing 6 sha MATCH、extract 1217 行 e757aec5 51abfec3、repair 2795 行 5147f8c3、auto-ci 63 行 0 disab/enab），0 更正；r1316 狀態不變（vq-el4.49 已閉、21 passed、FROZEN_STATE_OK、0 模型呼叫）。前情 r1316：vq-el4.49 開→關（首次 2 failed＝diff_worker 未同步＝真實陳述→worker 0e61c7575 同步後全綠）；vq-el4 50/50 全閉、唯一剩餘＝vq-1zf（G3）待人類 --fire。

## 數字（本輪實測著地）
- 守衛套件（本輪新跑）：21 passed（freeze_check 14 含 test_guard_suite_identity_negative_controls：(a) 5 dummy 非期望名→BROKEN 且點名缺失／(b) 期望名齊→OK／(c) 2 dummy→BROKEN 點名／(d) 齊→OK＋計數負控制(e) skipped 同型；anchors 5；ci_contract 2）
- freeze_check（本輪新跑）：10/10 OK、VERDICT: FROZEN_STATE_OK rc=0（anchors 身份齊 5 passed／ci_contract 身份齊 2 passed／diff_worker 0 files @0e61c7575／diff_argon 0 files @31182c54e／filing code 3/3＋sources 3/3 MATCH／g3gate NOT_FIRED＋PLAN_OK／bk_state＋bk_now 同步／wt_clean 3/3）
- 期望名 vs 兩守衛檔實際測試名：7/7 精確吻合（grep ^def test_ 核對）
- CI 一次讀取（不 poll）：qwen27b@3ea3c69fa 無 ci/<sha>.json（state.json idle）；LATEST worker@a550efa7 green 5079/0/74；LATEST argon@c235031f green 5079/0/74
- vq-el4 50/50 全閉（0 open）；唯一剩餘＝vq-1zf（G3）待人類 --fire；/srv/vlab/queue 空；tickets/open 空；無新人類指示（ops/ 最新仍 11-07＋附帶審查）

## 待辦（依序）
1. 待人類：G3 --fire（vq-1zf）——不點火、不入 queue
2. 待人類：CI 通道裁決（auto-ci.yml disabled_manually＝服務端狀態；不重診斷、不翻開關）
3. 下輪：CI 再一次讀取（qwen27b@3ea3c69fa 本輪無工件、runner idle；若本輪簿記 commit 成為新 HEAD 則讀新 HEAD）；維持審查指示（凍結錨守衛＋CI 合約、fail-closed、輪末 VERDICT: FROZEN_STATE_OK）

## 紅線
- 不碰 main；不自 push（loop 自推）；.github/workflows/ 只讀；不讀 /srv/eval hidden＋scorer
- 凍結 4 檔＋g2.5 filing 不改；/srv/vlab/queue 不放新任務
- 缺值＝UNKNOWN（None）不填 0；不宣稱 localized 優於 generic；不宣稱等 token
- G3 待人類 --fire；無 reset/rebase；無 sleep poll；0 模型呼叫；不以改文件湊進展
