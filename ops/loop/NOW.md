# NOW.md — 現況（每輪更新，≤3KB）

## 狀態（2026-11-11 r1450 G3 輸入 contract 接線）
- **r1450（票 P20261111_1516-1，c79af8cf6）：g3.py 擷取 user_text 漏附 contract.md 已修**（helper＋call site＋prerun 同口徑＋新測試，answer.txt 範例案 old→new 解旗，0 model calls）。**redo 補正**（假說檔已補開）：H2.0 報告 14 條實際 deliverable 皆描述性短句（prompt L1028 禁止）→ 修復後 user_text 重測 **0/14 解旗**（證據 ops/audits/g3_1_contract_fix_report_recheck_20261111.json）→ **H2_0_REFUTED（r1447a）不被推翻、§4 停止規則維持**；票尾 redo 段已補。
- r1449：argon 同步 24 in-scope 檔→diff_argon 0 differ；diff_worker 殘留＝1215-1 3 檔（在進未升上，誠實紅）。vq-kax 3 項已落地；收案被 1215-1 阻塞。
- r1447/a：G3.1 H2.0=H2_0_REFUTED（3e45e212）；r1442 凍結（809dae937）；r1444 stray-labd（3127a77ad）。
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
- bd ready＋1215-1 收案狀態；qwen doing/ 現空，等規劃者下一票。
- CI 三分支核：python3 /home/user1/dev/ops/ci_status.py（新 tip 跑完後）。
- 守衛：anchors 5 passed、freeze_check（除 1215-1 項）全綠；test_reqloop_g3 34 passed（r1450 量）。
