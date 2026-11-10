# NOW.md — 現行輪唯一指針（本檔 ≤ 3 KB；只留現況＋下一步＋紅線）

主線：R-loop 主線（~/dev/ops/RLOOP_PLAN.md）。G2.5 已完（凍結、凍結）、G2 已完（凍結、凍結）；G3 發射＝人類核准＋真通道，不代發、不入 queue。

## 現況（r1394、2026-11-10）

r1394＝收尾 r1393（auto rc=124）未竟之 vq-el4.81（開→關）：r1393 把紅線轉抄守衛接進一鍵 ruler（11→12 項 now_redline、唯一實現 redline_violations）但漏更 GUARD_CONTENT_PIN（守衛照設計抓到、3 測試紅＝r1386 同型遺漏）＋2 檔未同步 worker/argon（diff BROKEN）。本輪：pin 依紀律補（cfbfba31…→42ab72d2…、解凍記錄留案）＋freeze_check docstring 虛記更正＋三分支同步（worker@67107afc6／argon@d43a9aab1）。
- 驗收（本輪全數新跑）：freeze_check 12/12 OK VERDICT: FROZEN_STATE_OK rc=0（now_redline OK、diff 0×2、anchors 5／ci 2、filing 3/3＋3/3、queue 空含隱藏、g3gate NOT_FIRED）；守衛 6 檔 77 passed；in-scope diff 0×2。
- CI 一次讀取（輪首、不 poll）：argon tip 🟢 5130/74；qwen27b r1392 🟢 5130/74、本輪新 sha 無 per-sha json→UNKNOWN；worker 05766d8b running→UNKNOWN。
- bd：vq-el4.81 開→關（本輪）；vq-1zf（G3）仍等人類 --fire、不代發、不入 queue；/srv/vlab/queue 空（含隱藏）。

## 下一步

1. 下輪開頭一次讀取三分支現 tip per-sha CI json（本輪新 sha：qwen27b 8d7284de4…／worker 67107afc6…／argon d43a9aab1…；綠＝三分支收口終證、紅＝查因；不 poll）。
2. 待人類：G3 --fire（vq-1zf、不代發、不入 queue）；CI 通道裁決（CI 現為唯一全量綠燈通道）。

## 紅線

- 不讀 /srv/eval/hidden/ 與 scorer.py；G3 不入 /srv/vlab/queue；G3 只待人類 --fire 後發射。
- main 不碰；無 push（loop 自推）；.github/workflows/ 零改動；無 reset/rebase。
- 凍結 4 檔不改（repair.py 2795 行／blob 5147f8c3…、extract.py 1217 行／blob e757aec5…、checks.py c7589c61…、run_eval.py 332cd324…）＋g25 filing（6 sha256）不改。
- 0 模型呼叫（glm 未用）；不跑 full pytest（只 CI 一次讀取）；不 sleep poll；不以改文湊進展；數字一律實跑／重算驗證。
- 簿記：STATE.md（canonical、Current State 首行最新單行條目、先 append 條目）＋鏡像 ops/STATE.md（5 行鏡像）＋NOW.md（repo root）＋鏡像 ops/loop/NOW.md（byte-identical）；每輪簿記後同步 worker／argon worktree。
