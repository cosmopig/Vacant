# NOW.md — Vacant 下一輪（≤3KB，每輪覆寫）

> 人類看：現在狀態 + 下一輪第一步。Agent 看：直接照「下一輪第一步」做。
> 詳細歷史看 STATE.md / decisions/ / ops/audits/。本檔每輪覆寫（非追加）。

**（2026-11-09 r1327：vq-el4.51 閉關——freeze_check 偽 summary 標頭假綠燈（dummy print 偽「short test summary info」標頭＋偽 PASSED 行，舊碼取第一處標頭為段首→偽名進身份集＝OK；RED 實證）。修＝段首取最後一處標頭行＋段內行數==passed 計數錨（I-4 fail-closed）；1 負控制測試 RED→GREEN＋正控制＋2 單元；GUARD_CONTENT_PIN 解冻記錄＋錨更新 1d7841ad；三分支同步。守衛 24→25 passed；freeze_check 10/10 OK、VERDICT: FROZEN_STATE_OK、rc=0。CI：現 3 HEAD 無 json（UNKNOWN）；running=qwen27b@65e497da8（進行中）。）**

## 一句話現況

r1327 = vq-el4.51（freeze_check 身份假綠燈#3：守衛檔 dummy 測試 print 偽「short test summary info」標頭＋偽「PASSED <nodeid>」行，r1324 的段首＝第一處標頭→偽名進身份集、計數/無其它結果類全綠＝OK（r1327 RED 實證）；r1296/r1314/r1324 同族：計數守住、身份未守；H-0）實作收口＋三分支同步。修：段首＝最後一處標頭行（真 summary 於 session 結束時輸出、測試執行期 print 必在其前）＋計數錨（段內 PASSED 行數==passed；段內多一行偽行即破→BROKEN，I-4）。1 檔（ops/reqloop/freeze_check.py）＋1 測試（test_guard_suite_fake_summary_header_negative_control，含正控制）＋1 指令輸出變好（freeze_check 對偽標頭弱化守衛檔判 BROKEN（舊碼 OK）；守衛套件 24→25 passed）。vq-el4 52/52 全閉；唯一剩餘 open=vq-1zf（G3）待人類 --fire（不點火、不入 queue）。CI（一讀、不 poll）：現 3 HEAD（qwen27b 65e497da8／worker d29cfe694／argon ee71984a4）無 ci/<sha>.json→UNKNOWN；running=qwen27b@65e497da8（進行中、未出 .json）。

## 待人類

1. **G3 --fire**（vq-1zf 唯一 open）：未 fire、未放 /srv/vlab/queue/（queue 空）；fire 後才排。
2. **CI 通道決定**：auto-ci.yml 63 行、grep -ci 'enab|disab'=0（disabled_manually=server 端 state）；不翻開關、不重診斷、不 push。

## 下一輪第一步（按序）

1. 讀 STATE.md + 本檔。
2. 看 ops/reviews/、ops/audits/、tickets/open/、/srv/vlab/queue/：有人類新指令或新工單才動 product；沒有就驗證輪。
3. 驗證（0 模型/0 sleep/0 poll）：
   - git -C ~/dev/Vacant status --short + auto_worker/auto_argon 同（乾淨？）
   - CI 一讀：ls ~/dev/ops/ci/{65e497da8,d29cfe694,ee71984a4}.json（有→讀；無→UNKNOWN；state.json 只記 running，不重試不等）
   - python ops/reqloop/freeze_check.py（期望 10/10 OK / FROZEN_STATE_OK / rc=0）
   - python -m pytest tests/test_reqloop_freeze_check.py tests/test_reqloop_frozen_anchors.py tests/test_reqloop_ci_contract.py（期望 25 passed）
   - git diff --name-only auto/qwen27b <branch> -- vacant_network tests ops（期望 0×2）
4. 記帳：STATE.md 加一行（≤5 行）、覆寫本檔、ops/STATE.md + ops/loop/NOW.md 同步、三分支各 commit（loop auto-push；不手動 push）。

## 紅線（每輪）

不 push（loop 自動）· .github/workflows/ 唯讀 · hidden/scorer 不讀 · frozen 4 檔（repair 2795 行/extract 1217 行/checks c7589c61/run_eval 332cd324）+ g2.5 filing 不改 · 不 reset/rebase · 不 sleep poll CI · G3 未 fire 不放 queue · 0 模型呼叫 · 不以改檔充當進度（無工單就驗證/記帳/待命）
