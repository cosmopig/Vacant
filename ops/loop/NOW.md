# NOW.md — 現況（每輪覆寫、≤3KB）

## 狀態（2026-11-12 r1495；票 P20261112_0748-1 e013 成本重算量具；產物在樹全綠；驗收 grep 壞 → bounced/）
- **工作完成且全綠（commit 760ed5774）：** ops/audits/e013_recompute.py（120 行；--selftest 正控制＋負1（舊 events 無 metrics→標記異常隔離、非 0.0 合格）＋負2（pass=None infra→嚴排除分母）全綠，VERDICT: E013_RECOMPUTE_OK RC=0；活體 A 30 格 calls 26.93/tokens 583095、C 30 格 14.41/244937、excluded=0）＋tests/test_e013_recompute.py（3 passed）＋BACKLOG.md line 101 [ ]→[x]＋結案註記（repo 與 ~/dev/ops 兩份）。
- **驗收指令本身壞（票面描述錯→bounced/）：** `grep -F "- [x]"` 被 GNU grep 前導 dash 當選項→「invalid option -- ' '」rc=2、與檔案內容無關（實證 `echo '- [x] x' | grep -F "- [x]"` 亦 rc=2）；機械等價修正式 `grep -E "e013_recompute" ops/BACKLOG.md | grep -F -- "- [x]"` rc=0（line 101 含 `- [x]`）。依輪規「驗收指令本身壞掉」條款票移 bounced/、候規劃者修驗收 grep 重驗；產物已入庫、無需重做。
- **較上輪好的命令：** `python3 ops/audits/e013_recompute.py --selftest`→RC=0（上輪檔案不存在 exit 1；本輪正＋2 負控制＋活體全綠）。
- **紅線：** 無 push（loop 自推）、main 未動、無 reset/rebase、.github/workflows/ 只讀、hidden/scorer 未讀、凍結 4 檔＋filing 6 sha 未改（anchors 5 passed）、0 model calls、未跑 full pytest、不以文書改動充實進度（本輪實質＝e013 量具新碼＋測試＋BACKLOG 收口，皆可機械複核）。

## 紅線（契約、不變）
- 不 push（loop 自推 auto/qwen27b）、不 main、不 reset/rebase；.github/workflows/ 只讀。
- 凍結 4 檔不改：repair.py 2795 行／blob 5147f8c3…、extract.py 1217 行／blob e757aec5…、checks.py c7589c61…、run_eval.py 332cd324…；g25 filing（6 sha256）；g3_1/g3_2 歷史不改。
- 不讀 /srv/eval/hidden/ 或 scorer.py；缺值 UNKNOWN、不補 0。
- 不寫 /srv/vlab/queue；CI 不 poll；不跑 full pytest。

## 未完（≤3、交下輪）
1. e013 票（bounced/）：候規劃者把驗收 grep 改為 `grep -F -- "- [x]"`（或 `-e`）重驗；產物已在樹（760ed5774）、無需重做。
2. CI 一次讀取（ci_status.py、不 poll）：三新 HEAD 跑件中（r1491 記錄）；若紅→讀 log 根因不猜。
3. G 系列候人類裁決（vq-kax）：解凍 extract/checks 或終止；新 G 票不接。

## 下輪入口（≤3）
- e013 驗收指令修好後重驗（產物在樹、只須跑驗收指令；票在 bounced/）。
- ci_status.py 一次讀取（不 poll）：若紅→讀 log 根因不猜；若綠→記錄數字。
- 守衛：anchors 綠、freeze_check 12/12、鏡像 byte-identical、NOW.md ≤3KB。
