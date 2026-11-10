# NOW.md — 現行輪唯一指針（本檔 ≤ 3 KB；只留現況＋下一步＋紅線）

主線：R-loop 主線（~/dev/ops/RLOOP_PLAN.md）。G2.5 已完（凍結、凍結）、G2 已完（凍結、凍結）；G3 發射＝人類核准＋真通道，不代發、不入 queue。

## 現況（r1397、2026-11-10）

r1397＝真產品 bug 修復（vq-el4.85 開→關）：GUARD_CONTENT_PIN 擴覆蓋缺口——NOW.md 紅線轉抄守衛檔 tests/test_reqloop_now_redline.py（freeze_check 第 12 項 now_redline 唯一實現）r1392 建立後從未釘住（vq-el4.63 同型）。RED 雙實證：同名 stub 換檔（redline_violations→[]）→ guard_content_violations 回 []＝假綠燈；真 check_now_redline 對該 stub 判 OK——紅線契約行被整行掏空的 NOW.md 仍 ('now_redline', True, …)＝完整假綠燈（H-0 同構）。修：補釘 6ce235db…（pin 7→8 檔；該檔不含 pin、無自釘循環）＋負控／正控測試；ruler 位元組零改動。
- 驗收（本輪全數新跑）：守衛 7 檔 96 passed（freeze 25／anchors 5／ci 2／ves 19／g3gate 22／g3 18／now_redline 5；95→96、0 弱化）；freeze_check 12/12 OK FROZEN_STATE_OK rc=0（diff 0×2、filing 3/3＋3/3、queue 空含隱藏、g3gate NOT_FIRED、now_redline OK）；ves 7/7 OK；三分支同步（b09b4a695／bb6de7a41／c7354d62d、in-scope diff 0×2、內容恆等）。
- CI 一次讀取（輪首＋輪尾、不 poll）：現 3 tips per-sha CI 還沒跑完→UNKNOWN（非紅燈）；LATEST 三綠（3ae526734 5132/74/0／05766d8bf 5130/74/0／8afae2473 5132/74/0）覆蓋上輪碼。
- bd：vq-el4.85 開→關（本輪）；vq-1zf（G3）仍等人類 --fire、不代發、不入 queue；/srv/vlab/queue 空（含隱藏）。

## 下一步

1. 下輪開頭一次讀取三分支現 tip per-sha CI json（現 tips：qwen27b b09b4a695…／worker bb6de7a41…／argon c7354d62d…；綠＝三分支收口終證、紅＝查因；不 poll）。
2. 待人類：G3 --fire（vq-1zf、不代發、不入 queue）；CI 通道裁決（CI 現為唯一全量綠燈通道）。

## 紅線

- 不讀 /srv/eval/hidden/ 與 scorer.py；G3 不入 /srv/vlab/queue；G3 只待人類 --fire 後發射。
- main 不碰；無 push（loop 自推）；.github/workflows/ 零改動；無 reset/rebase。
- 凍結 4 檔不改（repair.py 2795 行／blob 5147f8c3…、extract.py 1217 行／blob e757aec5…、checks.py c7589c61…、run_eval.py 332cd324…）＋g25 filing（6 sha256）不改。
- 0 模型呼叫（glm 未用）；不跑 full pytest（只 CI 一次讀取）；不 sleep poll；不以改文湊進展；數字一律實跑／重算驗證。
- 簿記：STATE.md（canonical、Current State 首行最新單行條目、先 append 條目）＋鏡像 ops/STATE.md（5 行鏡像）＋NOW.md（repo root）＋鏡像 ops/loop/NOW.md（byte-identical）；每輪簿記後同步 worker／argon worktree。
