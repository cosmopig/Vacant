# NOW.md — 現行輪唯一指針（本檔 ≤ 3 KB；只留現況＋下一步＋紅線）

主線：R-loop 主線（~/dev/ops/RLOOP_PLAN.md）。G2.5 已完（凍結）、G2 已完（凍結）；G3 發射＝人類核准＋真通道，不代發、不入 queue。

## 現況（r1407、2026-11-10）

r1407＝驗證＋簿記輪：本輪改善之命令輸出＝`python3 ops/reqloop/ci_tip_check.py`：r1406 NO_COVERAGE×3／CI_TIP_BROKEN rc=1 → 本輪 **VERDICT: CI_TIP_OK rc=0**（全數新跑）。
- 三分支收口：qwen27b@9e47d350f PEER_COVERED（綠祖先 9131e49aa、peer=worker@146037568 COVERED、root tree 恆等 65b226f68a70…＝位元組恆等）；worker@146037568 COVERED（綠祖先 5a74f7534、diff 純 4 簿記檔）；argon@0fb7f5fa5 PEER_COVERED——＝r1405 is_green 碼 CI 收口機械終證（state.json 一次讀取：CI 在跑、在跑≠已綠、不 poll）。
- 驗收（本輪全數新跑）：守衛 8 檔 109 passed（基線 108 之超集、0 排除、0 弱化）；freeze_check 12/12 FROZEN_STATE_OK rc=0（anchors 5、ci_contract 2、diff 0×2、filing 3/3＋3/3、queue 空含隱藏、g3gate NOT_FIRED、wt_clean 3/3、now_redline OK）；ves 7/7 EFFECTS_SUMMARY_OK rc=0（13w0r g7/l6、11w0r g7/l4、reference MATCH）；GUARD_CONTENT_PIN 12/12 MATCH（獨立重算）；凍結錨實算＝repair 2795 行／blob 5147f8c3、extract 1217 行／blob e757aec5。
- redo（審查點名）：effects 摘要（60228 B pin MATCH）＋g25 filing（全文）直接開啟；數字逐項相符、6 sha 6/6 MATCH；0 更正。
- 環境：無新人類指示（ops/ 最新 11-07）、tickets/open 空、/srv/vlab/queue 空、vq-el4 92/92 全閉、全庫唯一 open＝vq-1zf（G3）待人類 --fire、不代發、不入 queue。
- 簿記：canonical＝STATE.md＋NOW.md；鏡像＝ops/STATE.md＋ops/loop/NOW.md（byte-identical）；三分支同步後 in-scope diff 0×2。

## 下一步

1. 下輪開頭重跑 `python3 ops/reqloop/ci_tip_check.py`（一次讀取、不 poll）：仍 CI_TIP_OK 且 tips 未動＝收口穩定；轉紅＝查因（不預設退步）。
2. 待人類：G3 --fire（vq-1zf、不代發、不入 queue）；CI 通道裁決（auto-ci.yml disabled_manually、本地 vacant-ci 實效通道；不翻開關、不重複診斷）。

## 紅線

- 不讀 /srv/eval/hidden/ 與 scorer.py；G3 不入 /srv/vlab/queue；G3 只待人類 --fire 後發射。
- main 不碰；無 push（loop 自推）；.github/workflows/ 零改動；無 reset/rebase。
- 凍結 4 檔不改（repair.py 2795 行／blob 5147f8c3…、extract.py 1217 行／blob e757aec5…、checks.py c7589c61…、run_eval.py 332cd324…）＋g25 filing（6 sha256）不改。
- 0 模型呼叫（glm 未用）；不跑 full pytest；不 sleep poll；不以改文湊進展；數字一律實跑／重算驗證。
- 簿記：STATE.md（canonical、Current State 首行最新單行條目）＋鏡像 ops/STATE.md（byte 前綴）＋NOW.md＋鏡像 ops/loop/NOW.md（byte-identical）；每輪簿記後同步 worker／argon worktree（in-scope diff 0×2）。
