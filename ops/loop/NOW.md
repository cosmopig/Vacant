# NOW.md — 現行輪唯一指針（本檔 ≤ 3 KB；只留現況＋下一步＋紅線）

主線：R-loop 主線（~/dev/ops/RLOOP_PLAN.md）。G2.5 已完（凍結、凍結）、G2 已完（凍結、凍結）；G3 發射＝人類核准＋真通道，不代發、不入 queue。

## 現況（r1395、2026-11-10）

r1395＝審查指示 #1 守衛套件口徑對帳（vq-el4.82 開→關）：r1394「守衛 6 檔 77 passed」把 tests/test_reqloop_g3.py（18 案、G3 發射管線紅線守衛）排除計數、無留案理由（審查基線 88＝r1390/r1391 口徑含 g3 18；r1392 446 passed 亦含）＝未記錄之口徑收窄。本輪恢復 7 檔全口徑（0 ruler 改、0 產品碼改、pin 未動）。
- 驗收（本輪全數新跑）：守衛 7 檔 95 passed rc=0（freeze_check 24／anchors 5／ci 2／ves 19／g3gate 22／g3 18／now_redline 5；88 基線之超集、0 弱化）；freeze_check 12/12 OK FROZEN_STATE_OK rc=0（diff 0×2、filing 3/3＋3/3、queue 空含隱藏、g3gate NOT_FIRED）；ves 7/7 OK EFFECTS_SUMMARY_OK rc=0（policy30 13w0r g7/l6、once20 11w0r g7/l4、reference MATCH）。
- CI（一次讀取、不 poll）：state.json running＝qwen27b@3ae52673（現 tip）；LATEST 三檔 🟢 5130/0/74（d7b1939c／05766d8b／3c442302、皆現 tips 之祖先）；現 3 tips（3ae52673／840a7fd4／8afae247）per-sha json 無→UNKNOWN（H-0、非紅燈；tip 本地驗收全綠）。
- bd：vq-el4.82 開→關（本輪）；vq-1zf（G3）仍等人類 --fire、不代發、不入 queue；/srv/vlab/queue 空（含隱藏）。

## 下一步

1. 下輪開頭一次讀取三分支現 tip per-sha CI json（現 tips：qwen27b 3ae52673…（在跑）／worker 840a7fd4…／argon 8afae247…；綠＝三分支收口終證、紅＝查因；不 poll）。
2. 待人類：G3 --fire（vq-1zf、不代發、不入 queue）；CI 通道裁決（CI 現為唯一全量綠燈通道）。

## 紅線

- 不讀 /srv/eval/hidden/ 與 scorer.py；G3 不入 /srv/vlab/queue；G3 只待人類 --fire 後發射。
- main 不碰；無 push（loop 自推）；.github/workflows/ 零改動；無 reset/rebase。
- 凍結 4 檔不改（repair.py 2795 行／blob 5147f8c3…、extract.py 1217 行／blob e757aec5…、checks.py c7589c61…、run_eval.py 332cd324…）＋g25 filing（6 sha256）不改。
- 0 模型呼叫（glm 未用）；不跑 full pytest（只 CI 一次讀取）；不 sleep poll；不以改文湊進展；數字一律實跑／重算驗證。
- 簿記：STATE.md（canonical、Current State 首行最新單行條目、先 append 條目）＋鏡像 ops/STATE.md（5 行鏡像）＋NOW.md（repo root）＋鏡像 ops/loop/NOW.md（byte-identical）；每輪簿記後同步 worker／argon worktree。
