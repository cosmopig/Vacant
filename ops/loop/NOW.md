# NOW.md — 現況（每輪覆寫，≤3KB）

## 狀態（2026-11-12 r1476；審查 2225 輪：#1/#2/#4 完成、#3 候 worker 收斂）
- **r1476（0 model calls）：**
  - #1 完成：`git merge --no-edit auto/argon`→ef553d26a（預驗 `git diff --name-only`=0 檔、零內容差；argon 今為 mainline 祖先、is-ancestor 實證）。DECISION：審查明示指示＝授權；「合併前查 CI」例外＝零內容差＋同源紅燈（worker 殘留），見 STATE r1476。
  - #2 複核（本輪重跑）：`g3_2_extract_prerun.py --selftest`→G3_2_PRERUN_SELFTEST_OK rc=0＋`pytest tests/test_reqloop_g3_2_prerun.py` 4 passed；report verdict H0_MET 未變（未改檔）。
  - #4 完成：BACKLOG.md 項 10 stray-labd 根因 UNKNOWN→已查明（本輪自行機械核驗 session 原文：01a1a112／message 93a55755／toolCall B2yTy6xl…／nohup 命令／TS 11:15:40.431Z；PID 734502/733374 關聯；審計票 2158-1 worker 在進）。
  - #3 受阻（如實）：worker round 88 在跑（gemma timeout 2700s、00:15 UTC 發射）——紅線不碰在進產物；收斂後審查升上＋worker 同步→12/12。
  - freeze_check：10/12（2 紅＝diff_worker＋wt_clean，皆歸因 worker WIP）；diff_argon OK。
- r1475＋redo（前輪）：argon 再同步＋驗收複核＋5 點名檔開啟重算 0 更正；H0_MET 1/4。
- r1473（2319-2）：G3.2 fire 結果分報＋H1_REFUTED；G 系列停候人類（不變）。

## 紅線（契約，不改）
- 無 push（迴圈自動 push auto/qwen27b）、無 main、無 reset/rebase；.github/workflows/ 只讀。
- 凍結 4 檔不改：repair.py 2795 行／blob 5147f8c3…、extract.py 1217 行／blob e757aec5…、checks.py 2823 行／blob f3525b01…、run_eval.py 1298 行／blob b6d2f37f…；g25 filing（6 sha256）不變；g3.py 僅依核准工單改動。
- 不讀 /srv/eval/hidden/ 或 scorer.py；缺值 UNKNOWN 不填 0；hidden_after=UNKNOWN；同批重發非獨立樣本。
- 不寫 /srv/vlab/queue；不 poll CI；不跑 full pytest。

## 未完成（≤3，交接下輪）
1. **worker 收斂→收口**：票 2158-1（stray-labd 根因審計）審查＋升上；worker 簿記同步→diff_worker/wt_clean OK→freeze_check 12/12 複測（審查 #3）。
2. **G 系列＝候人類裁決**（停止規則已觸發）：G3.3（H0 門穩定性、1 呼叫）／G3.4／解凍 extract+checks／終止；預註冊在假說檔 §6。G3.1（1315-2）同候人類核准。
3. CI：mainline＋argon 紅燈同源（freeze_check 下游 2 項、worker 殘留致），候 worker 收斂轉綠；不 poll。

## 下輪入口（≤3）
- worker round 88 收斂檢查（workerloop 狀態＋票 2158-1 產物＋WIP commit）→審查升上→12/12。
- 不碰 g3_1／g3_fire_20261111*／g3_2 既有產物；G 系列無人類核准不發射。
- 守衛：freeze_check 10/12（2 紅皆 worker 歸因）、selftest OK、anchors 綠。
