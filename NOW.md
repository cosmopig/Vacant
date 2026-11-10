# NOW — r1371 (2026-11-10)

## Current State
- vq-el4 全數已關（66 issues 0 open 0 in progress，含 epic）；全庫唯一 open＝vq-1zf（G3、待人類 --fire）。
- 本輪（r1371）CI 一次讀取（不 poll）：worker@ef5674e5（r1369 worker tip）UNKNOWN→GREEN 5107/0/74（per-sha json 落盤）；qwen27b@89d6650a・argon@8651ea64（r1369 tips）仍無 per-sha json→UNKNOWN；現 r1370 HEAD（17de139fd/6f1a1acb/5bca01512）：qwen27b running（log ~62%、無 json）、worker/argon 未跑（下輪首讀）。
- 驗收全綠（本輪全數新跑、主倉）：freeze_check 11/11 OK rc=0（diff 0×2、wt_clean 3/3、filing 3/3＋3/3 MATCH、queue 空含隱藏、g3gate NOT_FIRED+PLAN_OK、bk 同步）；ves 7/7 OK rc=0（50 格、13w0r g7l6／11w0r g7l4）；守衛 5 檔 70 passed（freeze 22／anchors 5／ci 2／ves 19／g3gate 22）；in-scope diff 0×2。
- 審查指示（1371）#1–#5 本輪全數驗證在位（三分支零漂移／守衛檔＋負控制／凍結錨點＋filing 6/6／CI 一次讀取＋簿記雙 worktree 同步 commit／G3 待人類＋queue 空）；核准 argon commit 5845434b5 已驗在歷史、0 diff、無需動作。
- Redo（審查點名 4 檔）：4 檔全數實開核實（effects 50 格／13w0r g7l6・11w0r g7l4 sha a710f7e4…；filing 3 門 PASS＋6 sha256 獨立重算 6/6 MATCH＋boundaries 6＋baseline localized 9/9 generic 7/9；extract 1217 行/blob e757aec5…；repair 2795 行/blob 5147f8c3…）——0 修正、簿記重同步三分支。
- 待人類：G3 --fire（vq-1zf、不代發、不入 queue）；CI 通道裁決。

## Next Step (r1372)
1. CI 一次讀取：現 r1370 HEAD（17de139fd/6f1a1acb/5bca01512）＋r1369 殘留（89d6650a/8651ea64）per-sha → 記 GREEN/RED（不 poll、不等待）。
2. 維持驗收：freeze_check 11/11 OK；ves 7/7 OK；守衛 70 passed；in-scope diff 0×2；queue 空（含隱藏）；g3gate NOT_FIRED。
3. 待人類：G3 --fire（vq-1zf）。

## Red lines
- 無 push；.github/workflows/ 只讀；不讀 /srv/eval/hidden/ 或 scorer.py；G3 未經人類核准不得發射（不代發 --fire、不入 queue）；/srv/vlab/queue/ 不放任務；無 reset/rebase；凍結檔（repair.py 2795 行、extract.py 1217 行、checks.py、run_eval.py）與 filing 不改；只跑相關測試、不自啟 full pytest；無 sleep poll CI。
