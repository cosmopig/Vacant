# NOW — r1374 (2026-11-10)

## Current State
- r1374 零漂移恢復（實質修復、非簿記）：freeze_check 開頭實測紅燈 diff_worker/diff_argon（2 in-scope 檔 tests/test_reqloop_g3.py＋vacant_network/reqloop/g3.py）——根因＝qwen27b 輪末 auto-commit 59bdb3dfd（rc=124 殘留：Channel→ABC 抽象契約＋負測試）未入兩 worktree；改動 16 passed 綠→不回退、worktree 對齊（worker@5eb279e14／argon@53990be3）。
- 驗收全綠（本輪全數新跑）：守衛 6 檔 86 passed（freeze 22／anchors 5／ci 2／ves 19／g3gate 22／g3 16）；g3 16 passed×3 分支；freeze_check 11/11 OK VERDICT: FROZEN_STATE_OK rc=0（diff 0×2、wt_clean 3/3、filing 6/6 MATCH、queue 空含隱藏、g3gate NOT_FIRED+PLAN_OK、bk 同步）；ves 7/7 OK；CI 一次讀取：3 HEAD 全 pending（無 per-sha json）、不 poll。
- 三分支：qwen27b@59bdb3dfd／worker@5eb279e14／argon@53990be3。
- 待人類：G3 --fire（vq-1zf、不代發、不入 queue）；CI 通道裁決。

## Next Step (r1375)
1. CI 一次讀取：三分支各 HEAD per-sha → 記 GREEN/RED（不 poll、不等待）。
2. 維持驗收：freeze_check 11/11 OK；守衛 86 passed；in-scope diff 0×2；queue 空（含隱藏）；g3gate NOT_FIRED。
3. 待人類：G3 --fire（vq-1zf）。

## Red lines
- 無 push；.github/workflows/ 只讀；不讀 /srv/eval/hidden/ 或 scorer.py；G3 未經人類核准不得發射（不代發 --fire、不入 queue）；/srv/vlab/queue/ 不放任務；無 reset/rebase；凍結檔（repair.py 2795 行、extract.py 1217 行、checks.py、run_eval.py）與 filing 不改；只跑相關測試、不自啟 full pytest；無 sleep poll CI；0 模型呼叫。
