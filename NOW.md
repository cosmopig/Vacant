# NOW.md — 現行輪唯一指針（本檔 ≤ 3 KB；只留現況＋下一步＋紅線）

主線：R-loop 主線（~/dev/ops/RLOOP_PLAN.md）。G2.5 已完（凍結、凍結）、G2 已完（凍結、凍結）；G3 發射＝人類核准＋真通道，不代發、不入 queue。

## 現況（r1391 redo、2026-11-10）

r1391 redo＝審查點名 4 檔實開＋依賴值獨立重算（vq-el4.79 開→關），0 更正：
- effects_20261105_summary.json（json.load 實開）：60,228 B／sha a710f7e4…／50 格（local 45／current 50）；cells_detail 獨立重算：policy30 13w／0r（g7／l6）、保住 10／仍錯 7、35 sess／915 api／33,670,510 tok（None 5 格）；once20 11w／0r（g7／l4）、保住 0／仍錯 9、20 sess／457 api／19,503,953 tok——與檔級欄位全 MATCH。
- g25_all_gates_filing.json（json.load 實開）：4,681 B／sha 6e5afb46…／三門全 PASS；6 sha256 獨立重算 6/6 MATCH（extract.py 51abfec3…／checks.py c7589c61…／run_eval.py 332cd324…／phase1-3 3c6fb35a…／6b7cb831…／ada235bb…）。
- extract.py（head 實開）：1,217 行、blob e757aec5＝錨點 pin、fail-closed 組裝層。
- repair.py（head 實開）：2,795 行、blob 5147f8c3＝錨點 pin、G2 局部修復切片。
r1391 三分支收口定案（不變）：CI 一次讀取 3/3 綠（93707c2fa／1b93dcd04／86bea3a77 各 5125／74／0）；3 綠 sha 皆現 tips 之祖先、diff 僅 4 簿記檔→代碼 byte-identical；in-scope diff 0×2；現 tip 本地 88 passed／freeze 11/11／ves 7/7。未驗證：現 3 tips per-sha CI json→UNKNOWN（H-0、非紅燈）。

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
