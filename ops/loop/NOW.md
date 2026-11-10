# NOW.md — 現行輪唯一指針（本檔 ≤ 3 KB；只留現況＋下一步＋紅線）

主線：R-loop 主線（~/dev/ops/RLOOP_PLAN.md）。G2.5 已完（凍結、凍結）、G2 已完（凍結、凍結）；G3 發射＝人類核准＋真通道，不代發、不入 queue。

## 現況（r1398、2026-11-10）

r1398＝真產品 bug 修復（vq-el4.86 開→關，vq-el4.63/r1397 同型）：GUARD_CONTENT_PIN 擴覆蓋缺口——G3 發射管線對 vacant_network/reqloop/g3.py（667 行，r1373 vq-1zf.6）＋tests/test_reqloop_g3.py（18 測紅線守衛檔、審查指示 #1 點名 7 檔之一）建於各建錨輪後、從未釘住（忘了釘住得到的綠燈＝H-0 同構）。RED 實證（本輪新跑）：模組→「直接印 fire 成功」stub＋測試檔→同名 dummy（18 真名 assert True、計數不變全綠）→舊 guard_content_violations 回 []＝假綠燈；18 行為級信號隨 swap 即消、唯一抓得住＝pin。修：補釘該對（8→10 檔；無自釘循環、r1347/r1365 先例「可釘且必須釘」）＋負控／正控測試；ruler 零改動。
- 驗收（本輪全數新跑）：守衛 7 檔 97 passed（freeze 26／anchors 5／ci 2／ves 19／g3gate 22／g3 18／now_redline 5；96→97、0 弱化）；freeze_check 12/12 OK FROZEN_STATE_OK rc=0（diff 0×2、filing 3/3＋3/3、queue 空含隱藏、g3gate NOT_FIRED、now_redline OK）；ves 7/7 OK；三分支碼同步（qwen27b f382399c6／worker 4d4a74551／argon 41c4b4ff9、in-scope diff 0×2）。
- CI 一次讀取（輪首、不 poll）：本輪新 tips per-sha CI 未跑→UNKNOWN（非紅燈）；LATEST 三綠（b21eaba94／e9ea6c243／062cd4334 各 5132/0/74）皆現 tips 祖先（merge-base 實查），至輪首 tip 之 diff＝1 守衛測試檔（r1397、本地 96 passed）＋4 簿記檔→產品碼已綠 CI 覆蓋。
- bd：vq-el4.86 開→關（本輪）；vq-1zf（G3）仍等人類 --fire、不代發、不入 queue；/srv/vlab/queue 空（含隱藏）。

## 下一步

1. 下輪開頭一次讀取三分支現 tip per-sha CI json（綠＝收口終證、紅＝查因；不 poll）。
2. 待人類：G3 --fire（vq-1zf、不代發、不入 queue）；CI 通道裁決（CI 現為唯一全量綠燈通道）。

## 紅線

- 不讀 /srv/eval/hidden/ 與 scorer.py；G3 不入 /srv/vlab/queue；G3 只待人類 --fire 後發射。
- main 不碰；無 push（loop 自推）；.github/workflows/ 零改動；無 reset/rebase。
- 凍結 4 檔不改（repair.py 2795 行／blob 5147f8c3…、extract.py 1217 行／blob e757aec5…、checks.py c7589c61…、run_eval.py 332cd324…）＋g25 filing（6 sha256）不改。
- 0 模型呼叫（glm 未用）；不跑 full pytest（只 CI 一次讀取）；不 sleep poll；不以改文湊進展；數字一律實跑／重算驗證。
- 簿記：STATE.md（canonical、Current State 首行最新單行條目、先 append 條目）＋鏡像 ops/STATE.md（5 行鏡像）＋NOW.md（repo root）＋鏡像 ops/loop/NOW.md（byte-identical）；每輪簿記後同步 worker／argon worktree。
