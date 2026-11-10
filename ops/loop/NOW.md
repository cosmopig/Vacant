# NOW.md — 現行輪唯一指針（本檔 ≤ 3 KB；只留現況＋下一步＋紅線）

主線：R-loop 主線（~/dev/ops/RLOOP_PLAN.md）。G2.5 已完（凍結、凍結）、G2 已完（凍結、凍結）；G3 發射＝人類核准＋真通道，不代發、不入 queue。

## 現況（r1391、2026-11-10）

三分支收口定案（r1390 下一步①）：CI 一次讀取（不 poll）3/3 綠——qwen27b@93707c2fa 5125 passed／74 skipped／0 failed（859s）；argon@1b93dcd04 5125／74／0（861s）；worker@86bea3a77 5125／74／0（859s）；state.json idle。3 綠 sha 皆現 3 tips（qwen27b 2752fb24c／argon 875427385／worker a9633eb4b）之祖先，diff 僅 4 簿記檔（NOW.md／STATE.md／ops/STATE.md／ops/loop/NOW.md）→代碼 byte-identical、綠 CI 覆蓋現 tip 代碼；in-scope diff 0×2。現 tip 本地重驗（全數新跑）：守衛 6 檔 88 passed（4.89s）；freeze_check 11/11 OK FROZEN_STATE_OK rc=0；ves 7/7 OK EFFECTS_SUMMARY_OK rc=0。未驗證：現 3 tips per-sha CI json→UNKNOWN（H-0、非紅燈）。

## 下一步

1. 下輪開頭一次讀取現 3 tips（2752fb24c／875427385／a9633eb4b）per-sha CI json（state.json 現 idle、待 CI tick；綠＝三分支收口終證、紅＝查因；不 poll）。
2. 待人類：G3 --fire（vq-1zf、不代發、不入 queue）；CI 通道裁決（CI 現為唯一 5125 全量綠燈通道）。
3. bd：vq-el4 家族 0 open／0 in_progress（vq-el4.78 本輪開→關）；無其它工作項；/srv/vlab/queue 空（含隱藏）。

## 紅線

- 不讀 /srv/eval/hidden/ 與 scorer.py；G3 不入 /srv/vlab/queue；G3 只待人類 --fire 後發射。
- main 不碰；無 push（loop 自推）；.github/workflows/ 零改動；無 reset/rebase。
- 凍結 4 檔不改（repair.py 2795 行／blob 5147f8c3…、extract.py 1217 行／blob e757aec5…、checks.py c7589c61…、run_eval.py 332cd324…）＋g25 filing（6 sha256）不改。
- 0 模型呼叫（glm 未用）；不跑 full pytest（只 CI 一次讀取）；不 sleep poll；不以改文湊進展；數字一律實跑／重算驗證。
- 簿記：STATE.md（canonical、Current State 首行最新單行條目、先 append 條目）＋鏡像 ops/STATE.md（5 行鏡像）＋NOW.md（repo root）＋鏡像 ops/loop/NOW.md（byte-identical）；每輪簿記後同步 worker／argon worktree。
