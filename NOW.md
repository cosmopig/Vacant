# NOW.md — 現行輪唯一指針（本檔 ≤ 3 KB；只留現況＋下一步＋紅線）

主線：R-loop 主線（~/dev/ops/RLOOP_PLAN.md）。G2.5 已完（凍結）、G2 已完（凍結）；G3 發射＝人類核准＋真通道，不代發、不入 queue。

## 現況（r1405、2026-11-10）

r1405＝ci_tip_check is_green 假綠燈洞修復（vq-el4.90 開→關；全庫唯一 open 仍 vq-1zf）。
- 洞（TDD RED 實證）：r1399 初版 is_green 只驗 `green is True`＋`failed==0`＋`errors==0`，不驗 `passed`、計數不驗型——記錄 `{green:true, passed:0, failed:0, errors:0}`（零通過＝未測量）被舊碼判 TIP_GREEN→CI_TIP_OK rc＝0 假綠燈；`{failed:false, errors:false}`（json bool、False==0）亦被讀成零失敗＝同型（I-4「a suite that reported zero tests fails」、r1272 空檔 vacuous 同族）。
- 修：is_green 收緊為嚴格 int（排除 bool）——`green is True` 且 `passed` int>0 且 `failed` int==0 且 `errors` int==0；缺欄位／錯型／零通過＝非綠（fail-closed）。改善之命令輸出＝該負控場景從 CI_TIP_OK（假綠燈）到 RED／CI_TIP_BROKEN rc=1（新負控測試 RED→GREEN）。
- 驗收（本輪全數新跑）：守衛 8 檔 109 passed（ci_tip_check 10→11；r1404 108 基線超集、0 弱化）；freeze_check 12/12 FROZEN_STATE_OK rc=0；ves 7/7 EFFECTS_SUMMARY_OK rc=0；g3gate 22 passed NOT_FIRED；queue 空（含隱藏）；live ci_tip_check → CI_TIP_OK rc=0（真記錄 passed≈5145 int、不受收緊影響）；in-scope diff 0×2。
- pin 紀律：GUARD_CONTENT_PIN 仍 12 檔；本輪合法改動 2 檔（ruler＋其測試）顯式更新錨（舊→新 sha256、本輪自磁碟實算非轉抄）＋解凍記錄留案於 pin 條目。

## 下一步

1. 下輪開頭重跑 ci_tip_check.py（一次讀取、不 poll）：維持 CI_TIP_OK＝收口成立；若 tips 前移→UNKNOWN／NO_COVERAGE 非退步、當時再驗。
2. 待人類：G3 --fire（vq-1zf、不代發、不入 queue）；CI 通道裁決（GitHub auto-ci.yml disabled_manually、本地 vacant-ci 為實效通道）。

## 紅線

- 不讀 /srv/eval/hidden/ 與 scorer.py；G3 不入 /srv/vlab/queue；G3 只待人類 --fire 後發射。
- main 不碰；無 push（loop 自推）；.github/workflows/ 零改動；無 reset/rebase。
- 凍結 4 檔＋filing sha256 未改（repair.py 2795 行 blob 5147f8c3…、extract.py 1217 行 blob e757aec5…、checks.py c7589c61…、run_eval.py 332cd324…；ops/audits/g25_all_gates_filing.json 6 sha256 相符）。
- GUARD_CONTENT_PIN 12 檔須與磁碟真值一致；任何守衛檔改動必須同步更新錨並記錄解凍理由。
