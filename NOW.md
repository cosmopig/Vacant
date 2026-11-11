# NOW.md — 現況（每輪更新，≤3KB）

## 狀態（2026-11-11 r1458 e016 envleak 審計票 bounce）
- **r1458（票 P20261111_1716-2，bounced/）：驗收期望值與數據矛盾，未實作**。負控制要 violations==15「A 臂 15 格全洩漏」；attempt1 實量＝14 cell.json／11 PI 洩漏／3 合規 smoke（list_ops，14:15 早於 14:34:40 發射）／2 格無 cell.json（book-C rc=-15、bowling-A）；官方 DECISION_20261103_E016_ENVLEAK_FIX.md §4.2 自書「15 格含 3 合規 smoke 格」。正控制口徑（PI 殘留＋排 .infra 5 目錄＋FSR＝臂參數）下負控制＝11 非 15；「任何 VACANT_」口徑則正控制＝34 破。改數硬過＝製造綠燈，拒絕；票尾已寫全證據＋重拆建議。
- r1450（票 1516-1，c79af8cf6）：g3.py 擷取 user_text 漏附 contract.md 已修＋redo 補正（0/14 解旗、H2_0_REFUTED 不被推翻）。
- r1449：argon 24 檔同步→diff_argon 0；diff_worker 殘留＝1215-1 3 檔（誠實紅）。r1447/a：H2.0=REFUTED；r1442 凍結；r1444 stray-labd。
- CI：三分支新 tip 待跑完，下輪 ci_status.py 核（不 poll）。

## 紅線（契約，不改）
- 不 push（loop 自動 push auto/qwen27b）、不 main、不 reset/rebase；.github/workflows/ 只讀。
- 凍結 4 檔不改：repair.py 2795 行／blob 5147f8c3…、extract.py 1217 行／blob e757aec5…、checks.py 2823 行／blob f3525b01…、run_eval.py 1298 行／blob b6d2f37f…；g25 filing（6 sha256）不變；g3.py 僅依核准工單改動。
- 不讀 /srv/eval/hidden/ 或 scorer.py；缺值＝UNKNOWN 不 0；hidden_after=UNKNOWN。
- 不寫 /srv/vlab/queue；不 poll CI；不跑 full pytest。

## 未完成（≤3，交下輪）
1. 1215-1（hidden_file_in_workspace 收緊）：worker 在進；收案後下輪審查＋升上→diff_worker/wt_clean 轉 OK→freeze_check 全綠。
2. vq-kax 收案：待「守衛全綠」（被 1 阻塞）→ bd close 理由＝commit SHA＋驗收末行。
3. hidden 計分：10 cells ok 有答案，人側/vlab 側。

## 下輪入口（≤3）
- bd ready＋1215-1 收案狀態；qwen doing/ 現空（1716-1、1716-2 皆 bounced/，等規劃者重拆或新票）。
- CI 三分支核：python3 /home/user1/dev/ops/ci_status.py（新 tip 跑完後）。
- 守衛：anchors 5 passed、freeze_check（除 1215-1 項）全綠；test_reqloop_g3 34 passed（r1450 量）。
（MEMORY 上限 6 KB、NOW 上限 3 KB；超過的部分沒有附上，請先把它縮短）
