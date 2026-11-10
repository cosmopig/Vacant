# NOW.md — 現行輪唯一指針（本檔 ≤ 3 KB；只留現況＋下一步＋紅線）

主線：R-loop 主線（~/dev/ops/RLOOP_PLAN.md）。G2.5 已完（凍結）、G2 已完（凍結）；G3 發射＝人類核准＋真通道，不代發、不入 queue。

## 現況（r1403、2026-11-10）

r1403＝CI 紅燈查因＋現 tip 守衛全口徑複驗（工單 P20261110_1944-1、vq-el4.88 開→關；全庫唯一 open＝vq-1zf）。
- 紅燈因（本輪讀 CI log 定案）：LATEST_qwen27b＝73548bce（r1399）5142/2 failed 紅燈、2 FAILED 皆 test_reqloop_freeze_check.py＝diff_worker／diff_argon BROKEN（ci_tip_check 對在 worker/argon 而 qwen27b 缺失＝r1399 超時殘留之跨分支失同步、非產品 bug）；r1401 已補對＋GUARD_CONTENT_PIN 10→12；現 tip in-scope diff 0×2（本輪實跑）——已在樹收口。
- 現 tip 複驗（本輪全數新跑）：守衛 8 檔 108 passed（審查基線 95 之超集、0 排除、0 弱化）；freeze_check 12/12 OK FROZEN_STATE_OK rc=0；ves 7/7 OK EFFECTS_SUMMARY_OK rc=0；queue 空含隱藏；g3gate NOT_FIRED。
- CI 一次讀取（不 poll）：state.json running＝qwen27b@2ad1713cb（在跑）；3 tips（344936db／5b93e62d／6faca25c）per-sha json 無→UNKNOWN；3ae52673／8afae247／e9ea6c24（5132/0/74）＝r1394/r1395 世代 per-sha 綠（磁碟 json 核實）。

## 下一步

1. 下輪開頭一次讀取三分支現 tip per-sha CI json（2ad1713cb 綠＝三分支收口終證、紅＝查因；不 poll）。
2. 待人類：G3 --fire（vq-1zf、不代發、不入 queue）；CI 通道裁決。

## 紅線

- 不讀 /srv/eval/hidden/ 與 scorer.py；G3 不入 /srv/vlab/queue；G3 只待人類 --fire 後發射。
- main 不碰；無 push（loop 自推）；.github/workflows/ 零改動；無 reset/rebase。
- 凍結 4 檔不改（repair.py 2795 行／blob 5147f8c3…、extract.py 1217 行／blob e757aec5…、checks.py c7589c61…、run_eval.py 332cd324…）＋g25 filing（6 sha256）不改。
- 0 模型呼叫（glm 未用）；不跑 full pytest；不 sleep poll；不以改文湊進展；數字一律實跑／重算驗證。
- 簿記：STATE.md（canonical、Current State 首行最新單行條目）＋鏡像 ops/STATE.md（byte 前綴 5 行）＋NOW.md＋鏡像 ops/loop/NOW.md（byte-identical）；每輪簿記後同步 worker／argon worktree（in-scope diff 0×2）。
