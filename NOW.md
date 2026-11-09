# NOW.md — Vacant 下一輪（≤3KB，每輪覆寫）

> 給人類：現況＋下一輪第一步。給 agent：照「下一輪第一步」走即可。
> 詳細歷史看 STATE.md / decisions/ / ops/audits/。此檔每輪覆寫（不累積）。

**（2026-11-09 r1329：vq-el4.51 已閉。輪始＝r1326/r1327 rc=124 殘留：r1327 修復（偽 summary 標頭假綠燈：段首＝最後一處標頭＋計數錨）只 commit 入 qwen27b 5004f847，worker/argon 未同步＋簿記鏡像漂移→freeze_check 4/10 BROKEN。本輪：驗證該修復（守衛 25 passed 含偽標頭負控；GUARD_CONTENT_PIN 三檔錨吻合）＋簿記對齊＋三分支同步＋驗收 freeze_check 10/10 OK、VERDICT: FROZEN_STATE_OK、rc=0、in-scope diff 0×2。vq-el4 52/52。CI：qwen27b@5004f847 無 json（UNKNOWN，不 poll）；最新綠三分支皆 5083/0/74。）**

## 一句話現況

r1329＝r1327 rc=124 desync 收口（vq-el4.51 closed，非代碼改動輪）：驗證 r1327 修復（守衛 25 passed＝freeze_check 18/anchors 5/ci_contract 2；GUARD_CONTENT_PIN 三檔錨吻合、解凍記錄齊全）＋簿記對齊＋worker/argon 同步 6 檔＋sync commit；驗收：freeze_check 10/10 OK、FROZEN_STATE_OK、rc=0、in-scope diff 0×2、三分支 clean。CI 一讀：qwen27b@5004f847 無 json→UNKNOWN；最新綠三分支皆 5083/0/74。全庫唯一 open＝vq-1zf（G3）待人類 --fire（未點火、未放 queue）。

## 待人類

1. **G3 --fire**（vq-1zf 唯一 open）：未點火、未放 /srv/vlab/queue/（queue 空）；點火前不排程。
2. **CI 通道裁決**：auto-ci.yml disabled_manually＝server 側狀態；不翻開關、不重診斷、不 push。

## 下一輪第一步（依序）

1. 讀 STATE.md＋本檔。
2. 看 ops/reviews/、ops/audits/、tickets/open/、/srv/vlab/queue/：有新人類指令或新 ticket 才動產品；無＝驗證輪。
3. 驗證（0 model/0 sleep/0 poll）：
   - git -C ~/dev/Vacant status --short（三分支 worktree clean?）
   - CI 一讀：ls ~/dev/ops/ci/<三分支現 HEAD>.json（有→讀；無→UNKNOWN；不重試不等）
   - python ops/reqloop/freeze_check.py（expect 10/10 OK / FROZEN_STATE_OK / rc=0）
   - python -m pytest tests/test_reqloop_freeze_check.py tests/test_reqloop_frozen_anchors.py tests/test_reqloop_ci_contract.py（expect 25 passed）
   - git diff --name-only auto/qwen27b auto/worker|auto/argon -- vacant_network tests ops（expect 0×2）
4. 簿記：STATE.md 加一線（≤5 行）、覆寫本檔、ops/STATE.md＋ops/loop/NOW.md 對齊、三分支各 commit（迴圈 auto-push；不自 push）。

## 紅線（每輪）

無 push（迴圈 auto）· .github/workflows/ 只讀 · 未讀 hidden/scorer · 凍結四檔（repair 2795 行/extract 1217 行/checks c7589c61/run_eval 332cd324）＋g2.5 filing 未改 · 無 reset/rebase · 不 sleep poll CI · G3 未點火不進 queue · 0 model calls · 不以改檔充當進度（無 ticket＝驗證/簿記/等）
