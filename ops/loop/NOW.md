# NOW.md — r1265（2026-11-08，第 1265 輪）

## 本輪結論（一句）
主線 G2.5 已完結且全綠（`run_eval --all` EXIT 0、三門 PASS、242 測綠、anchors 5、in-scope diff 0）；唯一剩餘工作 G3 已備妥但阻塞於人類核准——本輪無實質代碼改動、未造假進展。

## 事實（本輪全部實跑／直接開啟）
- `run_eval.py --all` EXIT 0：G1 抓錯 39/39・冤枉 0；REAL14 9/9・冤枉 0/5；PHASE3 fixed7／unresolved2／rejected0／right_to_wrong0／error0（0 新模型呼叫、離線重算）。
- reqloop 相關測試 242 passed；anchors（frozen）5 passed×3 分支；in-scope diff 三分支 0。
- `g3gate --plan` EXIT 0：12 格（4 題×3 臂）、verify_frozen OK、budget OK、NOT FIRED（0 model calls）。
- **〔redo〕三檔本輪直接開啟核實**（此前只引 r1264 文字，現已落地）：
  - `extract.py` 1217 行/blob `e757aec50c16…`＝G2.5 擷取驗證層，fail-closed（逐字 quote、`SUPPORTED_VERIFIERS` 閉集、解析失敗→空集、`GlmClient` 唯一模型入口）。
  - `repair.py` 2795 行/blob `5147f8c3ea1b…`＝G2 修復切片（權威快照輸入、來源改寫→exit 20、FAIL→UNKNOWN≠修好、PASS 退步記 `regressed`、session≠API calls 分開、缺值＝None、opt-in）。
  - `effects_20261105_summary.json` sha256 `a710f7e4…`，程式載入重算：50 cells、**current_code 50/50 與獨立一致（0 分歧）**、local 45/50（5 分歧＝舊 checker）、policy30 w2r13(g7/l6)/r2w0/pg10/sw7、once20 w2r11(g7/l4)/r2w0/sw9、api_calls 915+457 vs sessions 35+20。
- bd：vq-el4 全 27 項 closed；唯一 open＝vq-1zf（G3，等人類核准）。
- 0 model calls（queue 空、vibe_calls 今日 0）；未讀 /srv/eval hidden 與 scorer.py。

## 下一輪先做
1. **需人類**：核准 G3 發射（`--fire`）或指派其他 in-scope 工作——主線已完結、無其他可單方推進的代碼工作（未核准前禁 `--fire`／入 queue／未授權模型呼叫）。
2. 確認三分支 CI 轉綠（一次、不 poll）；若紅燈且屬本次變更相關才修。
3. 每輪守：anchors 5 passed＋in-scope diff 0（簿記鏡像同步 worker/argon）。

## 紅線（本輪全守）
0 model calls・無 git push（迴圈自推 qwen27b）・.github/workflows/ 只讀・無 reset/rebase/branch -f・repair.py/extract.py/checks.py/run_eval.py/filing 未改・未讀 /srv/eval hidden 與 scorer.py・無 sleep 輪詢。
