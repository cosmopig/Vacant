# NOW.md — r1265（2026-11-08，第 1265 輪）

## 本輪結論（一句）
主線 G2.5 已完結且全綠（`run_eval --all` EXIT 0、三門 PASS、242 測綠、anchors 5、in-scope diff 0）；唯一剩餘工作 G3 已備妥但阻塞於人類核准——本輪無實質代碼改動、未造假進展。

## 事實（本輪全部實跑／直接開啟）
- `run_eval.py --all` EXIT 0：G1 抓錯 39/39・冤枉 0；REAL14 抓錯 9/9・冤枉 0/5；PHASE3 fixed7／unresolved2／rejected0／right_to_wrong0／error0（0 新模型呼叫、離線重算）。
- reqloop 相關測試 242 passed（extract／checks／run_eval／extract_run_eval／g1_gate／g2／g3gate）。
- anchors（tests/test_reqloop_frozen_anchors.py）5 passed；repair.py 2795 行/5147f8c3、extract.py 1217 行/e757aec5 未變。
- in-scope diff：qwen27b↔worker 0、qwen27b↔argon 0；三分支 HEAD 皆純簿記 commit。
- `g3gate --plan` EXIT 0：12 格（4 題×3 臂）、verify_frozen OK、budget OK、NOT FIRED（0 model calls）。
- bd：vq-el4 全 27 項 closed；唯一 open＝vq-1zf（G3，等人類核准）；無 in_progress、無 open 工單。
- CI：三分支 HEAD pending（prompt 給定、未 poll）；auto-ci.yml disabled_manually（r1264 已升級人類）。
- 0 model calls（queue 空、vibe_calls 今日 0 筆）；未讀 /srv/eval hidden 與 scorer.py。

## 下一輪先做
1. **需人類**：核准 G3 發射（`--fire`）或指派其他 in-scope 工作——主線已完結、無其他可單方推進的代碼工作（未核准前禁 `--fire`／入 queue／產生未授權模型呼叫）。
2. 確認三分支 CI 轉綠（一次、不 poll）；若紅燈且屬本次變更相關才修。
3. 每輪守：anchors 5 passed＋in-scope diff 0（簿記鏡像同輪同步 worker/argon）。

## 紅線（本輪全守）
0 model calls・無 git push（迴圈自推 qwen27b）・.github/workflows/ 只讀・無 reset/rebase/branch -f・repair.py/extract.py/checks.py/run_eval.py/filing 未改・未讀 /srv/eval hidden 與 scorer.py・無 sleep 輪詢。
