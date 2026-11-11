# NOW.md — 現況（每輪覆寫，≤3KB）

## 狀態（2026-11-11 r1465：審查指示 #1——bk_now 鏡像修復＋argon 同步；freeze_check 4 紅→2 紅）
- 修前 4 紅（實測）：diff_worker/diff_argon/bk_now/wt_clean。修後：bk_now OK（cp NOW.md→ops/loop/NOW.md；鏡像原為 r1461 舊內容，本輪重算 git show 4a995163a:ops/loop/NOW.md | wc -c = 2786B）＋diff_argon OK（argon worktree 全樹鏡像 mainline 737ba92ca＋commit，8 檔＝簿記 3＋in-scope 5，in-scope diff 0）。
- 審查 redo（交付前）：2786B 承傳數改有實測證據；5 點名檔實開核對皆與記錄相符（effects summary 60228B、l007 147 行＋selftest 重跑 OK、extract 1217 行/blob e757aec5…、repair 2795 行/blob 5147f8c3…、票 1152-1 文檔通讀＋g3_1 precheck 重跑 OK）。
- DECISION: 不字面 merge auto/argon｜argon diff 僅 4 簿記檔（r1461 內容、252 行 delta），合併會以舊覆新；慣例＝mainline canonical＋argon 鏡像（r1270/r1461 實證）。
- 剩 2 紅皆 worker 在進（如實）：diff_worker（無 sync counterpart；worker 領先 1843-2 WIP）＋wt_clean（worker worktree 2 檔 M）。worker round 20:15 發射、其輪末自動 commit。

## 紅線（契約，不改）
- 不 push（loop 自動 push auto/qwen27b）、不 main、不 reset/rebase；.github/workflows/ 只讀。
- 凍結 4 檔不改：repair.py 2795 行／blob 5147f8c3…、extract.py 1217 行／blob e757aec5…、checks.py 2823 行／blob f3525b01…、run_eval.py 1298 行／blob b6d2f37f…；g25 filing（6 sha256）不變；g3.py 僅依核准工單改動。
- 不讀 /srv/eval/hidden/ 或 scorer.py；缺值＝UNKNOWN 不 0；hidden_after=UNKNOWN。
- 不寫 /srv/vlab/queue；不 poll CI；不跑 full pytest。

## 未完成（≤3，交下輪）
1. 1843-2：worker 在進（round 20:15）；收斂後串行審查（同檔 ops/audits/labd_instance_and_env_audit.py；基線＝本輪 mainline commit）。
2. worker 收斂＋審查升上後：三分支 freeze_check 復測（期望 12/12）＋tests/test_reqloop_freeze_check verdict 綠；CI（不 poll）。
3. G3.1 H2.0 重發待人類裁決（H2_0_REFUTED r1447a 仍有效；manifest freeze 已完成——本輪重跑 g3_1_precheck --selftest VERDICT: G3_1_PRECHECK_OK、4 題全過）。

## 下輪入口（≤3）
- bd ready＋tickets/doing（現 1843-2、worker 在進）；worker 活躍時不碰其 worktree。
- 守衛基線：anchors 5 passed；freeze_check 期望 10/12（2 紅＝diff_worker/wt_clean，worker 在進，收斂後應收斂）。
- worker WIP 輪末自動 commit 後，先復測 freeze_check 再審查 1843-2。
