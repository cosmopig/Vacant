# NOW.md — 現況（每輪覆寫、≤3KB）

## 狀態（2026-11-12 r1512；審查門§5兩步完成：Step 1 複核全綠＋e015 驗收 PASS→三分支收斂；freeze_check 10/12→12/12 FROZEN_STATE_OK；票 1136-1 驗收結案）
- **較上輪好的命令：** `python3 ops/audits/e015_closure_check.py --selftest` RC=1（JSONDecodeError）→RC=0 `VERDICT: E015_CLOSURE_OK`（陽性＋4 負控、零實盤寫入）；`pytest tests/test_e015_closure_check.py` 3 failed→3 passed；`python3 ops/reqloop/freeze_check.py` 10/12 FROZEN_STATE_BROKEN→12/12 FROZEN_STATE_OK。
- **Step 1（審查者 2026-11-12）複核全綠：** 9a61b624d 為 qwen27b 祖先；4 檔三分支 byte-identical；f1..f4 無殘留（dabench 4 task＋ref）；precheck `VERDICT: G3_2_PRECHECK_OK` RC=0；fire `VERDICT: G3_2_FIRE_SUMMARY_SELFTEST_OK` RC=0；pytest g3_2 兩檔 12 passed。
- **Step 2（e015 驗收）PASS（以收斂版）：** 收斂版＝樹內 VERDICT 快照（sha d0e29884 釘、與 /srv 現盤損傷脫鉤）＋裁決管線 fe94c689 獨立重算＋BACKLOG 結案註記（a2829e9c）＋packet 非空；pytest 3 passed。誠實披露：源出 r1508 fix-on-behalf（票內已披露）、非 worker 自收斂（WIP f-string SyntaxError、未收斂、收編時取代）。
- **三分支收斂：** qwen27b@1e7bfd9c5；argon@8102536b5（e015 4 檔＋l008/e014 stale 變體對齊 qwen 收斂版）；worker@5e36fd5d2（採收斂版＋移除 pipeline 分叉副本 cbb071d3＋ticket 鏡像對齊）；in-scope diff 皆 0 檔；worktree 3/3 clean。
- **紅線：** 無 push（loop 自推 auto/qwen27b）、main 未動、無 reset/rebase、.github/workflows/ 只讀、hidden/scorer 未讀、未跑 full pytest；
- 凍結 4 檔不改：repair.py 2795 行／blob 5147f8c3…、extract.py 1217 行／blob e757aec5…、checks.py c7589c61…、run_eval.py 332cd324…；g25 filing（6 sha256）；g3_1/g3_2 歷史未動。

## 未完（≤3、交下輪）
1. 三新 HEAD CI 一次讀取（qwen 1e7bfd9c5／argon 8102536b5／worker 5e36fd5d2；紅→log 根因不猜、不 poll；argon 上輪紅＝freeze_check 2 failed，收斂後預期轉綠）。
2. e015 殘留（獨立項、非本票）：/srv/vlab/runs/e015_h_multi_review/VERDICT.json 現盤損傷（line 1780）——驗收以快照＋獨立重算為依據、不受影響；現盤修復候下輪。
3. 候人類裁決：L008 樣本量/預算（未發射、0 呼叫）；e013 票（bounced/）候規劃者修驗收 grep；G 系列（vq-kax）；0820-1（open/）候 worker 重驗項1→升三分支。

## 下輪入口（≤3）
- CI 一次讀取（ci_status.py 三分支、不 poll）。
- g3_2 前置已綠（precheck 6/6 task、manifest 凍結、ref 可達、無殘留）→ 可發射 fire_summary（round 900 先例 447s/32 格）——候審查者訊號、不自發。
- 守衛：NOW.md ≤3KB、ops/loop/NOW.md 與 root byte-identical（cp 鏡像）、ops/STATE.md＝canonical Current State 前綴鏡像（bk_state 契約）、紅線契約行逐字保留（now_redline 機器解析）、bd ready 空。
