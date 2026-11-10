# NOW.md — 現行輪唯一指針（本檔 ≤ 3 KB；只留現況＋下一步＋紅線）

主線：R-loop 主線（~/dev/ops/RLOOP_PLAN.md）。G2.5 已完（凍結、凍結）、G2 已完（凍結、凍結）；G3 發射＝人類核准＋真通道，不代發、不入 queue。

## 現況（r1392、2026-11-10）

r1392＝閉上審查指示 #4 缺口（vq-el4.80 開→關）：NOW.md 紅線「凍結 4 檔＋filing 6 sha256」引文 vs 磁碟此前無機械檢查（轉抄錯一個前綴／行數、或契約行被刪，全仍全綠＝H-0 同型）。新守衛 tests/test_reqloop_now_redline.py（1 檔、5 案：綠燈 1＋負控制 4）：
- 紅線聲明本輪自磁碟重算核實（0 漂移、0 更正）：repair.py 2795 行／blob 5147f8c3…、extract.py 1217 行／blob e757aec5…（git hash-object 同式）；checks.py c7589c61…、run_eval.py 332cd324…（sha256sum）；filing 6 欄位皆非 null 64-hex。
- 驗收（本輪全數新跑）：新檔 5 passed in 0.05s；test_reqloop_*.py 446 passed 0 failed（含新 5 案）；freeze_check 11/11 OK FROZEN_STATE_OK（anchors 5／ci 2 身份齊、diff 0×2、filing 3/3＋3/3、queue 空含隱藏、g3gate NOT_FIRED）；ves 7/7 OK。
- CI 一次讀取（輪首、不 poll）：現 3 tips（f1082bb6b／beaf01880／6cf526b92）per-sha json 無→UNKNOWN（H-0、非紅燈）；2752fb24c（5125/74/0 綠）＝qwen27b tip 祖先、至 tip 全 diff 僅 4 簿記檔→代碼 byte-identical；argon/worker in-scope 碼≡qwen27b tip（diff 0×2 本輪實跑）。
- bd：vq-el4.80 開→關；vq-el4 家族 0 open／0 in_progress；vq-1zf（G3）仍等人類 --fire；/srv/vlab/queue 空（含隱藏）。

## 下一步

1. 下輪開頭一次讀取現 3 tips per-sha CI json（state.json 現 idle、待 CI tick；綠＝三分支收口終證、紅＝查因；不 poll）。
2. 待人類：G3 --fire（vq-1zf、不代發、不入 queue）；CI 通道裁決（CI 現為唯一 5125 全量綠燈通道）。
3. 候選（BACKLOG 已記）：新紅線守衛接進 freeze_check 一命令尺（須記 GUARD_CONTENT_PIN 變更、下輪級）。

## 紅線

- 不讀 /srv/eval/hidden/ 與 scorer.py；G3 不入 /srv/vlab/queue；G3 只待人類 --fire 後發射。
- main 不碰；無 push（loop 自推）；.github/workflows/ 零改動；無 reset/rebase。
- 凍結 4 檔不改（repair.py 2795 行／blob 5147f8c3…、extract.py 1217 行／blob e757aec5…、checks.py c7589c61…、run_eval.py 332cd324…）＋g25 filing（6 sha256）不改。
- 0 模型呼叫（glm 未用）；不跑 full pytest（只 CI 一次讀取）；不 sleep poll；不以改文湊進展；數字一律實跑／重算驗證。
- 簿記：STATE.md（canonical、Current State 首行最新單行條目、先 append 條目）＋鏡像 ops/STATE.md（5 行鏡像）＋NOW.md（repo root）＋鏡像 ops/loop/NOW.md（byte-identical）；每輪簿記後同步 worker／argon worktree。
