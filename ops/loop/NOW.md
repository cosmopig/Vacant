# NOW.md — 現況（每輪更新，≤3KB）

## 狀態（2026-11-11 r1437）
- G3 重發 c 審計摘要收案（P20261111_0914-1→done，commit ba665989f）：12/12 格跑完
  （stop_reason=None、max_calls 修正生效、無 not_run）；native_pi 2ok/2err（600s timeout
  infra）、reqlist_only 4/4 ok、full_rloop 4/4 ok（content_reverify 4/4×1 輪、
  final_verdict 全 UNKNOWN、claims 全 None）；tokens 383921＝355734+28187
  （known_usages=14、缺值 UNKNOWN 不填 0）；hidden_after 12/12 UNKNOWN。
- G3.1：H1 機制可達性達門檻（4/4 格完成≥1 輪 content_reverify；a+b 合計 0/8 輪）；
  H2 未測得（final_verdict/claims 全 UNKNOWN/None）→裁決歸人類（依預註冊）；
  10 格 ok 有 answer 待 hidden 打分（人類/vlab 側）。
- 簿記：修 r1436 中斷殘留——bk_state 鏡像（443608B 非 canonical 前綴）依約定重建
  （標題＋Current State＋最新條目）、bk_now 鏡像 cp、worker/argon worktree 同步
  （in-scope diff 0×2）、freeze_check 12/12 FROZEN_STATE_OK。

## 紅線（契約，不改）
- 無 push（loop 自推 auto/qwen27b）、無 main、無 reset/rebase；.github/workflows/ 只讀。
- 凍結 4 檔不改：repair.py 2795 行／blob 5147f8c3…、extract.py 1217 行／blob e757aec5…、checks.py 2823 行／blob f3525b01…、run_eval.py 1298 行／blob b6d2f37f…；g25 filing（6 sha256）不改；g3.py 改動僅依 vq-kax 工單（AMEND-3 為其授權，執行順序照工單）。
- /srv/eval/hidden/、scorer.py 不讀；缺值 UNKNOWN 不填 0；hidden_after＝UNKNOWN；同批重發非獨立樣本、不宣稱臂 superiority。
- /srv/vlab/queue 不寫；無 poll CI；無 full pytest。

## 未完成（≤3，下輪接手）
1. G3.1 H1/H2 裁決：c 4/4 格完成≥1 輪 content_reverify 但 final_verdict 全 UNKNOWN、
   claims verdict 全 None——H2（缺口格 fixed≥1 且 regressed=0）未測得；裁決歸人類
   （依預註冊升級）。
2. hidden 打分：10 格 ok 有 answer（native_pi 2＋reqlist_only 4＋full_rloop 4），
   人類/vlab 側。
3. worker/argon 同步 commit 本輪已建；push 由 loop/人類（無 push 紅線）；CI 重跑
   驗證不 poll。

## 下輪入口（≤3）
- bd ready（vq-kax 狀態＋人類裁決）→下一張工單；doing/ 現空。
- 守衛：g3 3 檔＋anchors＋freeze_check（12 項）須全綠（含 now_redline、diff_worker/argon）。
