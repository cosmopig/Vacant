# NOW — r1373 (2026-11-10)

## Current State
- vq-1zf.6 G3 發射管線 g3.py 收尾完成（r1372 rc=124 中斷的接線）：修 5 處（RC_PLAN 本地定義／RoundUsage.to_dict() 落盤／撞額度不再提前 return、剩餘 cells 記 not_run／需求清單移入臂段使三臂任務+資料段逐字相同／_count_lines Py3.12）＋本層取回撞額度標記（凍結 extract 吞例外、不得降級為空清單繼續發）。
- 驗收全綠（本輪全數新跑、主倉）：g3 3 errors/12 failed → 15 passed；守衛 5 檔 85 passed（freeze 22／anchors 5／ci 2／ves 19／g3gate 22／g3 15）；freeze_check 11/11 OK rc=0 ×3 worktree（diff 0×2、wt_clean 3/3、filing 3/3＋3/3 MATCH、queue 空含隱藏、g3gate NOT_FIRED+PLAN_OK、bk 同步）；ves 7/7 OK rc=0；in-scope diff 0×2。
- 三分支零漂移：qwen27b@62c3fa28b（收尾）／worker@e573864d2／argon@c636d3021（sync commits）。
- 待人類：G3 --fire（vq-1zf、不代發、不入 queue）——管線已可發射（假通道全路徑驗證、0 模型呼叫）、僅待人類核准＋真通道接入；CI 通道裁決。

## Next Step (r1374)
1. CI 一次讀取：三分支各 HEAD per-sha → 記 GREEN/RED（不 poll、不等待）。
2. 維持驗收：freeze_check 11/11 OK；ves 7/7 OK；守衛 85 passed；in-scope diff 0×2；queue 空（含隱藏）；g3gate NOT_FIRED。
3. 待人類：G3 --fire（vq-1zf）。

## Red lines
- 無 push；.github/workflows/ 只讀；不讀 /srv/eval/hidden/ 或 scorer.py；G3 未經人類核准不得發射（不代發 --fire、不入 queue）；/srv/vlab/queue/ 不放任務；無 reset/rebase；凍結檔（repair.py 2795 行、extract.py 1217 行、checks.py、run_eval.py）與 filing 不改；只跑相關測試、不自啟 full pytest；無 sleep poll CI。
