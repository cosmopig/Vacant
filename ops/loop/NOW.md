# NOW.md — 現況（每輪更新，≤3KB）

## 狀態（2026-11-11 r1449 三分支簿記同步）
- **r1449（審查指示 #1）：argon 同步 24 in-scope 檔（g3_1 凍結/預跑門＋2 測試）＋簿記 4 檔（同 blob）→ diff_argon 0 file differ（OK）**。worker 同集合已同步（1215-1 dirty 檔未碰）；diff_worker 殘留＝1215-1 3 檔（在進未升上，誠實紅，待收案＋下輪審查升上）。全量 merge 被否決：會帶入 1215-1 WIP（違反不碰在進產物）；指令所列 labd 檔兩分支皆已有（r1444 升上）。
- vq-kax 3 項已落地（NO_TOOL_OVERRIDE＋負控制測試、max_calls_bound、c 再發射 12/12 格跑完歸因）；殘留＝「守衛全綠」中 diff_worker/wt_clean 被 1215-1 阻塞。
- r1448：bk_now 復 OK；其紅線行半形斜線本輪實測 3/5 紅（與「5 passed」記錄不符），已自磁碟重算改全形→5/5 綠；r1447/a：G3.1 H2.0=H2_0_REFUTED（3e45e212）；r1442：G3.1 凍結（809dae937）；r1444：stray-labd 升上（3127a77ad）。
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
- bd ready（vq-kax 剩 1 項）＋1215-1 收案狀態；qwen doing/ 現空。
- CI 三分支核：python3 /home/user1/dev/ops/ci_status.py（新 tip 跑完後）。
- 守衛：g3 4 檔＋anchors＋freeze_check（除 1215-1 項）全綠。
