# NOW.md — Vacant 現況（≤3KB；本檔覆寫不追加，歷史看 STATE.md）

## 現況（r1582、2026-11-13、0 model calls）
- 本輪（票 P20261113_1358-3 done）：D4 凍結 spec loader——票面功能（vacant_network/reqloop/specs.py load_frozen_specs/SpecIntegrityError、fail-closed 零部分結果）已於 1e8c83274 入樹；本輪＝全數驗收複驗＋三分支收斂（票驗收必需：freeze_check 輪首 BROKEN 2 項 diff_worker/diff_argon）＋結案。
- 三分支收斂（r1533 先例、r1270 程序；前提：兩 worktree 乾淨、該工作無票面依據——tickets/ 只有 qwen）：argon 4 檔分歧（840cbee5e run_g4 tasks_dir 自動注入＝未授權 run_g4 接線、本票紅線；85167539b specs.py dict 輸入擴充）＋worker 42 檔分歧（00:47 merge 後落後 qwen、缺 g4/g4gate/specs/replay_claims 等＋自身 WIP 85956c78f/d5acca4e6）→兩側改以 qwen canonical 取代（checkout auto/qwen27b in-scope＋簿記 4 檔＋worker git rm 自身 1 檔；無 reset/rebase；舊工作 git show 可復原）。
- 驗收（全綠、本輪新跑）：pytest tests/test_reqloop_frozen_specs.py 5 passed；pytest tests/test_reqloop_frozen_anchors.py＋tests/test_reqloop_now_redline.py 10 passed；freeze_check VERDICT: FROZEN_STATE_OK 12/12 RC=0；票尾 3 行→mv done/。

## 紅線
- 凍結／受控解凍：repair.py 2795 行／blob 5147f8c3…、run_eval.py 1298 行／blob b6d2f37f…（仍凍結）；extract.py 1295 行／blob b502741b…、checks.py 2907 行／blob d401a8ae…（受控解凍、只加法、預設＝舊行為）；g25 filing（6 sha256）；g3_1/g3_2 歷史未動。
- 無 push（loop 自推 auto/qwen27b）；main 未動；無 reset/rebase；.github/workflows/ 只讀；hidden/scorer 未讀；未跑全 pytest；0 model calls。
- G4 真發射仍須人類簽核（human_signoff=null）；本輪 0 發射；run_g4/g4gate 接線未做（1507-2/1708-1 另步授權）。
- CI：輪首 qwen 15 紅＝freeze_check/now_redline 系；本輪簿記＋收斂後本分支應轉綠、待 CI 證實；argon 2 紅／worker 11 紅＝既有，兩分支新 HEAD 收斂後應轉綠、待 CI 證實。

## 下一步
1. open/ 4 張（1507-1 D1 rootcause、1507-2 g4gate 接線、1708-1 g3.run_g4 接線、1708-2 D1 missing-param 守衛）→doing/ 取票照做。
2. G4 發射需人類簽核；不做 closure-check／結案量具類（11-13 §1 禁止）。
3. 達成效門（≥30/76 確定性＋負控制 0 假 PASS）前不發新真模型實驗。
