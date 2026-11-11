# NOW.md — 現在狀態（每輪更新，≤3KB）

## 狀態（2026-11-11 r1444）
- r1444（1152-2）：stray-labd audit evidence chain 審查＋重做＋升上。審查發現 4 缺陷（未修前）：--selftest 空轉綠燈（兩分支皆 OK＋exit 0、mock 設自己環境零作用）、「2 passed」含 1 個 pass 空轉、已提交報告非本工具所產（schema 不符）且其第 2 個「進程」是 pi session（pgrep -f 誤配 prompt 文字）、1 死代碼函數。修：audit 純函數化＋selftest 6 組真實控制（假 process table、任一失敗→BROKEN rc=1；變異元驗證轉紅）＋matcher 收緊（python 解釋器＋labd.py 尾配）＋報告由工具實跑產出（1 實例 pid 1734、findings []）；8 真測試 passed；auto/worker 187568ca6→mainline 升上＋雙 worktree 同步。
- freeze_check 11/12：唯一紅＝diff_worker＝worker 並行 WIP 票 1215-1（3 檔、doing/ 在進、13:13–13:17 UTC）——如實呈紅（同 r1440/r1443 型）、不碰在進產物、未審查不升上 mainline（紅線）；原 stray 3 檔已兩側同 blob、不再計差異。

## 紅線（契約，不改）
- 無 push（迴圈自動 push auto/qwen27b）、無 main、無 reset/rebase；.github/workflows/ 只讀。
- 凍結 4 檔不改：repair.py 2795 行／blob 5147f8c3…、extract.py 1217 行／blob e757aec5…、checks.py 2823 行／blob f3525b01…、run_eval.py 1298 行／blob b6d2f37f…；g25 filing（6 sha256）不改；g3.py 改動僅依核准工單（vq-kax AMEND-3 為其核准；1152-1 unverified 原因持久化依該票），執行順序以工單為準。
- 不讀 /srv/eval/hidden/ 或 scorer.py；缺值 UNKNOWN 不填 0；hidden_after=UNKNOWN；同批重發非獨立樣本，不宣稱臂優。
- 不寫 /srv/vlab/queue；不 poll CI；不跑 full pytest。

## 未完成（≤3，交接下輪）
1. 1215-1（hidden_file_in_workspace 收緊）：worker doing/ 在進（WIP 61e884e6f 13:17）；收案後下輪審查＋升上→freeze_check 12/12。
2. G3.1 H1/H2 裁決：c 發 4/4 格完成 ≥1 輪 content_reverify 但 final_verdict 全 UNKNOWN、claims 全未測得——裁決歸人類（預註冊升級、vq-kax 待核准）。
3. hidden 打分：10 格 ok 有 answer（native_pi 2＋reqlist_only 4＋full_rloop 4），人類/vlab 側。

## 下輪入口（≤3）
- 1215-1 審查（若已收案）→升上→freeze_check 12/12；若仍在進→如實呈紅、續不碰。
- bd ready（vq-kax 狀態＋人類裁決）→下一票；doing/＝1215-1。
- 守衛：g3 四檔＋anchors＋freeze_check（除上項外）全綠。
