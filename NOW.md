# NOW.md — Vacant 下一輪（≤3KB，每輪覆寫）

> 給人類：現況＋下一輪第一步。給 agent：照「下一輪第一步」走即可。
> 詳細歷史看 STATE.md / decisions/ / ops/audits/。此檔每輪覆寫（不累積）。

**（2026-11-09 r1330 redo：五檔實開（auto-ci.yml／effects／g25 filing／extract.py／repair.py）＋依賴值重算、0 更正；驗證/待命輪內容不變（0 代碼改動／0 模型呼叫／0 新工單）。三分支 clean、diff 0×2；守衛 25 passed；freeze_check 10/10 OK rc=0；vq-el4 52/52 全閉。CI 一讀：現 3 HEAD 無 json→UNKNOWN（不 poll）；LATEST_qwen27b 紅＝r1327 rc=124 中間態（5004f847b）殘留、本輪重驗全綠。全庫唯一 open＝vq-1zf（G3）待人類 --fire。）**

## 一句話現況

r1330＝驗證/待命輪（redo 已收口：五檔實開＋依賴值重算、0 更正，見 STATE）：三分支 clean、diff 0×2；守衛 25 passed；freeze_check 10/10 OK FROZEN_STATE_OK rc=0（filing 6 sha MATCH、g3gate NOT_FIRED、bk/wt 同步）。CI 一讀（不 poll）：現 3 HEAD（9d61bb8c／b0e463d4e／e326ac1e8）無 json→UNKNOWN（running=argon@e326ac1e）；LATEST_qwen27b 紅（5004f847b＝r1327 rc=124 中間態）r1329 已收口＋本輪重驗綠，非現行缺陷；LATEST worker/argon 綠。vq-el4 52/52 全閉；全庫唯一 open＝vq-1zf（G3）待人類 --fire（未點火、未放 queue）；tickets/queue 空；無新人類指令。

## 待人類

1. **G3 --fire**（vq-1zf 唯一 open）：未點火、未放 /srv/vlab/queue/（queue 空）；點火前不排程。
2. **CI 通道裁決**：auto-ci.yml disabled_manually＝server 端 state；不翻開關、不重診斷。

## 下一輪第一步（依序）

1. 讀 STATE.md＋本檔。
2. 看 ops/reviews/、ops/audits/、tickets/open/、/srv/vlab/queue/：有新人類指令或新 ticket 才動產品；無＝驗證輪。
3. 驗證（0 model/0 sleep/0 poll）：
   - git -C ~/dev/Vacant status --short（三分支 worktree clean?）
   - CI 一讀：ls ~/dev/ops/ci/<三分支現 HEAD>.json（有→讀；無→UNKNOWN；不重試不等）
   - python ops/reqloop/freeze_check.py（expect 10/10 OK / FROZEN_STATE_OK / rc=0）
   - python -m pytest tests/test_reqloop_freeze_check.py tests/test_reqloop_frozen_anchors.py tests/test_reqloop_ci_contract.py（expect 25 passed）
   - git diff --name-only auto/qwen27b auto/worker|auto/argon -- vacant_network tests ops（expect 0×2）
4. 簿記：STATE.md 加一線、覆寫本檔、ops/STATE.md＋ops/loop/NOW.md 對齊、三分支 commit（迴圈 auto-push；不自 push）。

## 紅線（每輪）

無 push（迴圈 auto）· .github/workflows/ 只讀 · 未讀 hidden/scorer · 凍結四檔（repair 2795 行/extract 1217 行/checks c7589c61/run_eval 332cd324）＋g2.5 filing 未改 · 無 reset/rebase · 不 sleep poll CI · G3 未點火不進 queue · 0 model calls · 不以改檔充當進度（無 ticket＝驗證/簿記/等）
