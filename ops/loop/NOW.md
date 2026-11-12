# NOW.md — 現況（每輪覆寫，≤3KB）

## 狀態（2026-11-11 r1475 審查 2225 複核＋argon 再同步；#3/#4 候 worker 收斂）
- **r1475（審查 20261111_2225 五指示驗證，0 model calls）：**
  - #1 完成：argon 再同步（修前 diff_argon BROKEN＝無 counterpart；r1465 全樹鏡像程序、0 argon 独占先驗）→修後 diff_argon OK（樹恆等＋counterpart commit）。
  - #2 複核（本輪新跑）：`g3_2_extract_prerun.py --selftest`→G3_2_PRERUN_SELFTEST_OK rc=0＋`pytest tests/test_reqloop_g3_2_prerun.py` 4 passed。
  - #3/#4 受阻（如實）：worker round 88 在進（票 2158-1 stray-labd 根因審計 doing/、WIP 2 檔 M）——紅線不碰在進產物；收斂後審查升上＋worker 同步→12/12。
  - freeze_check：修前 9/12→修後 10/12；2 紅＝diff_worker＋wt_clean（同根因＝worker 在進），worker 收斂即 12/12。argon CI 2 紅同源（BROKEN 檢查下游）。
- r1473（2319-2）：G3.2 fire 結果分報＋H1_REFUTED；G 系列停候人類（不變）。
- r1472（2319-1）：G3.2 背景發射執行完（4/4 ok、128923 tok）。

## 紅線（契約，不改）
- 無 push（迴圈自動 push auto/qwen27b）、無 main、無 reset/rebase；.github/workflows/ 只讀。
- 凍結 4 檔不改：repair.py 2795 行／blob 5147f8c3…、extract.py 1217 行／blob e757aec5…、checks.py 2823 行／blob f3525b01…、run_eval.py 1298 行／blob b6d2f37f…；g25 filing（6 sha256）不變；g3.py 僅依核准工單改動。
- 不讀 /srv/eval/hidden/ 或 scorer.py；缺值 UNKNOWN 不填 0；hidden_after=UNKNOWN；同批重發非獨立樣本。
- 不寫 /srv/vlab/queue；不 poll CI；不跑 full pytest。

## 未完成（≤3，交接下輪）
1. **worker 收斂→收口**：票 2158-1（stray-labd 根因）審查＋升上；worker 簿記同步→diff_worker/wt_clean OK→freeze_check 12/12 複測（審查 #3）；#4（BACKLOG 項 10 根因更新）同票。
2. **G 系列＝候人類裁決**（停止規則已觸發）：G3.3（H0 門穩定性、1 呼叫）／G3.4／解凍 extract+checks／終止；預註冊在假說檔 §6。G3.1（1315-2）同候人類核准。
3. argon CI 2 紅＝與 mainline 2 紅同源（verdict/covers_all 下游），候 worker 收斂轉綠；不 poll CI。

## 下輪入口（≤3）
- worker round 88 收斂檢查（workerloop 狀態＋票 2158-1 產物＋WIP commit）→審查升上→12/12。
- 不碰 g3_1/g3_fire_20261111*/g3_2 既有產物；G 系列無人類核准不發射。
- 守衛：freeze_check 10/12（2 紅皆 worker 歸因）、selftest OK、anchors 綠。
