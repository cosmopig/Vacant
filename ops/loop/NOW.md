# NOW.md — Vacant Loop 目前位置（agent-facing；只放「目前位置、下一步」；≤ 3 KB、覆蓋不追加）

## 目前狀態（r1305）
- r1305（ticket P20261109_0445-1）：vq-el4.46 驗收收口完成——pytest -k test_diff_sync_counterpart_anchor 1 passed、全檔 12 passed、freeze_check 9/9 OK VERDICT: FROZEN_STATE_OK rc=0、vq-el4.46 CLOSED（r1304 fb291dfb1 已閉，本輪不重閉）；vq-el4 46/46 全閉、0 open；兩 worktree 0 staged、in-scope diff 0×2；ticket → done/。
- CI（輪首報）：三分支 HEAD（qwen27b aab63481／argon 2786d8ef／worker c324bda9）CI 還沒跑完；不 poll。
- 隊列：唯一 ready＝vq-1zf（G3）待人類 --fire（不點火、不入 queue）；/srv/vlab/queue 空；無新人類指示（ops/ 最新仍 11-07）。

## 下一步（依序）
1. 本輪新 HEAD（qwen27b 簿記 commit／worker＋argon 簿記 sync）CI 一次讀取（不 poll）；若 RED 讀 ci log 診斷、不推測。
2. bd ready：有新工單才做；G3（vq-1zf）仍未點火（待人類 --fire）。
3. 簿記：每輪 STATE.md（1 行條目、插入 Current State 頂端）＋NOW.md（覆蓋）＋ops/ 鏡像（bk_state：鏡像＝canonical 前 4 行＝標題＋表頭＋最新條目行；bk_now：byte-identical）＋2 worktree（checkout 4 簿記檔＋commit）；commit 後複跑 freeze_check。
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
