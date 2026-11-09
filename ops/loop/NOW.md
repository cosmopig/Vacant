# NOW.md — Vacant Loop 目前位置（agent-facing；只放「目前位置、下一步」；≤ 3 KB、覆蓋不追加）

## 目前狀態（r1304）
- r1303（vq-el4.46：diff_worker/diff_argon 結構性假紅燈閉環——跨分支 diff 錨定同步對應 commit、非 live tip）被 rc=124 中斷，r1304 收尾完成：19 passed＋freeze_check 9/9 FROZEN_STATE_OK（三分支）、in-scope diff 0×2、worktree 已同步（worker 65e98e0f3／argon 6cdf6b029）、vq-el4.46 已閉（vq-el4 46/46 全閉）。
- CI（r1304 一次讀取、非 poll）：qwen27b@7492f2c65 GREEN 5077/0/74；argon@8ee9fe968 GREEN 5077/0/74；worker@368768d77 RED 2 failed＝r1301 同型結構性假紅（被測輪已同步、tip 已前進、舊守衛量 live tip）——根因即 vq-el4.46 已修；runner 現跑 argon@e9f8b9aee（in progress、舊守衛代碼）。新 HEAD CI：loop 自推、下輪首一次讀取、不 poll。
- 隊列：唯一 ready＝vq-1zf（G3）待人類 --fire（不點火、不入 queue）；/srv/vlab/queue 空；tickets/open 空；無新人類指示（ops/ 最新仍 11-07）。

## 下一步（依序）
1. 三分支新 HEAD（qwen27b 簿記 commit／worker 65e98e0f3＋簿記 sync／argon 6cdf6b029＋簿記 sync）CI 一次讀取（不 poll）；若 RED 讀 ci log 診斷、不推測（注意：argon@e9f8b9aee 在跑 job 若 RED＝vq-el4.46 同型假紅、非回歸）。
2. bd ready：有新工單才做；G3（vq-1zf）仍未點火（待人類 --fire）。
3. 簿記：每輪 STATE.md（≤5 行）＋NOW.md（覆蓋）＋ops/ 鏡像（byte 同步）＋2 worktree（checkout 4 簿記檔＋commit）；commit 後複跑 freeze_check。
4. 不改 .github/workflows/；不讀 /srv/eval hidden／scorer。

## 邊界
- G3（vq-1zf）待人類核准、未核准不發射、不入 queue。
- 凍結 4 檔：repair.py 2795 行／extract.py 1217 行／checks.py c7589c61／run_eval.py 332cd324＋g25_all_gates_filing 未改。
- 無 push（loop 自推）、無 reset/rebase、無 sleep poll、0 model calls。

## 11-06 人類指示（保留、勿改）
1. g7/l6（feedback_once20）＋g7/l4（policy30）0 right→wrong：repair 對已正確 cell 非破壞性、保住既有正確。
2. generic 在未見任務上優於 localized；若未見上不優就不上 localized（g5）。
3. hidden_after 全 UNKNOWN（無權重跑）、不宣稱 hidden 測試上有效。
註：11-06 指示括註之 phase 標籤與實開檔對調（實為 policy30＝g7/l6、feedback_once20＝g7/l4——r1301 redo 實開接地；指示檔不改、待人類）。
