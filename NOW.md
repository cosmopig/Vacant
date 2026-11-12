# NOW.md — Vacant 現況（≤3KB；本檔每輪覆寫，歷史入 STATE.md）

## 現況（r1530，2026-11-12，0 model calls）
- 本輪實質＝e015 閉環檢查預設含 live（票 vq-el4.105、r1528 盲區收口）：e015_closure_check.py 原只核 repo 快照、live 現盤須另跑哨兵才看得到；現預設併入 live（相符→OK 行、損傷→VIOLATION rc=1、缺位→UNKNOWN rc=2（看不到≠PASS））＋selftest live 整合正/負控制＋1 新測試；TDD RED→GREEN。
- 驗收（本輪全數新跑、全綠）：pytest e015 closure＋live 兩測試檔→7 passed；closure --selftest→VERDICT: E015_CLOSURE_OK（live 整合 3 控制生效）；plain rc=0 含 live 行；審查§3（e013）--selftest E013_CLOSURE_OK＋3 passed；freeze_check 12/12（worktree 同步後）。
- DECISION：argon 合併不執行——輪首 CI 三分支一次讀皆 pending（規則：該 sha 須🟢；5407≥5407 已滿足）；下輪輪首再讀一次。審查§2 完成：0820-1 已結案（r1507/done/）之陳舊行移除；cp 鏡像口徑維持。

## 紅線
- 凍結 4 檔不改：repair.py 2795 行／blob 5147f8c3…、extract.py 1217 行／blob e757aec5…、checks.py c7589c61…、run_eval.py 332cd324…；g25 filing（6 sha256）；g3_1/g3_2 歷史未動。
- 無 push（loop 自推 auto/qwen27b）；main 未動；無 reset/rebase；.github/workflows/ 只讀；hidden/scorer 未讀；未跑全 pytest。
- NOW.md ≤3KB；ops/loop/NOW.md cp 鏡像 byte-identical；ops/STATE.md＝根 STATE.md 位元組前綴（bk_state）。
- 不以文書改動充實進度：本輪實質＝量具＋測試 2 檔（e015 closure live 整合＋1 新測試），全可機械複核。

## 下一步
1. 下輪輪首 CI 三分支一次讀（ci_status.py、不 poll）：紅→讀 log 根因、不猜；argon🟢→merge auto/argon＋驗收（freeze_check 12/12＋pytest tests/test_reqloop_freeze_check.py 27 passed）。
2. vq-el4 現全閉（vq-el4.105 已 done）；下一票候人類/審查點名或新產品真 bug（CI 紅燈、真 bug 為例外通道）。
3. G 系列維持停止態、0 呼叫；vq-kax 候人類裁決。
