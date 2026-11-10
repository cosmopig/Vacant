# NOW.md — 現行輪唯一指針（本檔 ≤ 3 KB；只留現況＋下一步＋紅線）

主線：R-loop 主線（~/dev/ops/RLOOP_PLAN.md）。G2.5 已完（凍結、凍結）、G2 已完（凍結、凍結）；G3 發射＝人類核准＋真通道，不代發、不入 queue。

## 現況（r1396 redo、2026-11-10）

r1396 redo＝實開審查點名 4 檔＋獨立重算依賴值（vq-el4.84 開→關）——**0 修正、r1396 條目維持**：effects_20261105_summary.json 實開（60,228 B、sha256 a710f7e4… 與 ves pin 全同；自 cells_detail 重算：policy30 w2r=13（g7/l6）r2w=0、once20 w2r=11（g7/l4）r2w=0、sess/api/tok totals 全與檔內一致）；g25_all_gates_filing.json 實開（4,681 B、三門全 PASS、6 sha256 全數對 live 檔重算全 MATCH）；extract.py 實開（1,217 行、blob e757aec5…、fail-closed 結構）；repair.py 實開（2,795 行、blob 5147f8c3…）。
- r1396（前輪、CI 巡燈）：現 3 tips per-sha json 無→UNKNOWN（worker tip 在跑）；LATEST 三綠（3ae526734 5132/74/0／05766d8bf 5130/74/0／8afae2473 5132/74/0）覆蓋現 tip 碼；上輪 qwen27b@3ae52673 綠懸置定案；本地驗收全綠（95 passed／freeze 12/12／ves 7/7）；三分支同步（b21eaba94／4cb6717de／787148d74）。
- bd：vq-el4.84 開→關（本輪）；vq-el4.83 開→關（r1396）；vq-1zf（G3）仍等人類 --fire、不代發、不入 queue；/srv/vlab/queue 空（含隱藏）。

## 下一步

1. 下輪開頭一次讀取三分支現 tip per-sha CI json（現 tips：qwen27b e4bea31b9…／worker e9ea6c243…（在跑）／argon 4a95082e2…；綠＝三分支收口終證、紅＝查因；不 poll）。
2. 待人類：G3 --fire（vq-1zf、不代發、不入 queue）；CI 通道裁決（CI 現為唯一全量綠燈通道）。

## 紅線

- 不讀 /srv/eval/hidden/ 與 scorer.py；G3 不入 /srv/vlab/queue；G3 只待人類 --fire 後發射。
- main 不碰；無 push（loop 自推）；.github/workflows/ 零改動；無 reset/rebase。
- 凍結 4 檔不改（repair.py 2795 行／blob 5147f8c3…、extract.py 1217 行／blob e757aec5…、checks.py c7589c61…、run_eval.py 332cd324…）＋g25 filing（6 sha256）不改。
- 0 模型呼叫（glm 未用）；不跑 full pytest（只 CI 一次讀取）；不 sleep poll；不以改文湊進展；數字一律實跑／重算驗證。
- 簿記：STATE.md（canonical、Current State 首行最新單行條目、先 append 條目）＋鏡像 ops/STATE.md（5 行鏡像）＋NOW.md（repo root）＋鏡像 ops/loop/NOW.md（byte-identical）；每輪簿記後同步 worker／argon worktree。
