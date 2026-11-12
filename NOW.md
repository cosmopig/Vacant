# NOW.md — 現況（每輪覆寫，≤3KB）

## 狀態（2026-11-12 r1477；票 P20261112_0119-1 完成→done/）
- **r1477（0 model calls）：G3.3 預註冊凍結落地、驗收鏈 RC=0：**
  - `ops/reqloop/g3_3/manifest.json`（plan/1；arms=[full_rloop]；tasks=[dab_725] 4 檔 sha256；seen_set＝g3_2 27∪{587,657,517}→unseen=[dab_725]；budget 1 格/300s/2M 日/glm/quota_fail_closed；approval→g3_vq-1zf_fire_20261111.json）
  - `ops/reqloop/g3_3/tasks/dab_725/`（diff -r 0 vs g3_2 副本）
  - `ops/reqloop/g3_3_candidate_hypothesis.md`（H2 獨立確立：3 次獨立 extract ≥2/3 確定性→成立／1/3 達→否決→G 系列停）
  - `ops/audits/g3_3_precheck.py --selftest`→VERDICT: G3_3_PRECHECK_OK（local==ref==manifest 4 檔＋選題規則機械核＝H0 預跑恰 1 題達＝dab_725）
  - `tests/test_reqloop_g3_3_manifest.py` 3 passed；g3 家族 71 passed；官方乾跑 DRY-RUN OK（0 模型呼叫）。commit `ad34e32b9`。
- r1476（前輪）：argon 合併 ef553d26a（0 內容差）＋驗收複核全綠＋BACKLOG #10 根因；#3 候 worker。

## 紅線（契約，不改）
- 無 push（迴圈自推 auto/qwen27b）、無 main、無 reset/rebase；.github/workflows/ 只讀。
- 凍結 4 檔不改（r1477 0 改動）：repair.py 2795／extract.py 1217／checks.py 2823／run_eval.py 1298；g3_1/g3_2 歷史不改。
- 不讀 /srv/eval/hidden/ 或 scorer.py；缺值 UNKNOWN 不填 0；hidden_after=UNKNOWN。
- 不寫 /srv/vlab/queue；不 poll CI；不跑 full pytest。

## 未完成（≤3，交接下輪）
1. **G3.3 fire＝候人類裁決**（凍結已備：manifest＋tasks＋precheck＋單測全綠；H2＝dab_725 第 3 次獨立 extract、1 呼叫、參考 7313 tok；否決→G 系列停止上報；成立→G3.4 共識門）。
2. **worker 收斂→收口**：票 2158-1 審查＋升上；worker 簿記同步→diff_worker/wt_clean OK→freeze_check 12/12（r1476 #3）。
3. CI：mainline＋argon 紅燈同源（worker 殘留 freeze_check 下游 2 項），候 worker 收斂轉綠；不 poll。

## 下輪入口（≤3）
- G3.3：人類核准後才發射（`python3 -m vacant_network.reqloop.g3 --manifest ops/reqloop/g3_3/manifest.json --fire --approval /home/user1/dev/ops/approvals/g3_vq-1zf_fire_20261111.json`）；未核准不發射。
- worker round 88 收斂檢查（workerloop 狀態＋票 2158-1 產物＋WIP commit）→審查升上→12/12。
- 守衛：freeze_check 10/12（2 紅皆 worker 歸因）、g3_3 precheck selftest OK、anchors 綠（下輪補跑）。
