# NOW.md — Vacant 下一輪（≤3KB，每輪覆寫）

> 人類看：現在狀態 + 下一輪第一步。Agent 看：直接照「下一輪第一步」做。
> 詳細歷史看 STATE.md / decisions/ / ops/audits/。本檔每輪覆寫（非追加）。

**（2026-11-09 r1326：驗證/待命輪，0 程式碼/0 模型/0 新工單。CI：worker@313c39102 結案 5083/74/0 rc0 840s green；running=qwen27b@65e497da8（13:33:55Z，進行中）；d29cfe694/ee71984a4 無 json（UNKNOWN）。各分支最新綠至 HEAD 差異僅 2 vq-el4.50 product 檔（本輪 24 passed）+ 帳務檔。freeze_check 10/10 OK，VERDICT: FROZEN_STATE_OK，rc=0。）**

## 一句話現況

r1326 = 驗證/待命輪（vq-el4 51/51 全關；vq-1zf=G3 待人類 --fire；0 新工單/audit/指令）：三分支 HEAD（qwen27b 65e497da8 / worker d29cfe694 / argon ee71984a4）worktree 乾淨、in-scope diff 0×2；CI（一讀、不 poll）：worker@313c39102 結案 5083/74/0 rc0 840s green；running=qwen27b@65e497da8（13:33:55Z，進行中）；d29cfe694/ee71984a4 無 json（UNKNOWN）；各分支最新綠至 HEAD 差異僅 vq-el4.50 兩 product 檔（worker 僅帳務檔）+ 帳務檔。守衛 24 passed；freeze_check 10/10 OK、VERDICT: FROZEN_STATE_OK（filing 6/6 MATCH、g3 NOT_FIRED、bk 同步、wt 3/3 clean）。

## 待人類

1. **G3 --fire**（vq-1zf 唯一 open）：未 fire、未放 /srv/vlab/queue/（queue 空）；fire 後才排。
2. **CI 通道決定**：auto-ci.yml 63 行、grep -ci 'enab|disab'=0（本輪重算；disabled_manually=server 端 state）；r1325 redo 實測本地 vacant-ci 可用（rc0/5082 pass/863s）；不翻開關、不重診斷、不 push。

## 下一輪第一步（按序）

1. 讀 STATE.md + 本檔。
2. 看 ops/reviews/、ops/audits/、tickets/open/、/srv/vlab/queue/：有人類新指令或新工單才動 product；沒有就驗證輪。
3. 驗證（0 模型/0 sleep/0 poll）：
   - git -C ~/dev/Vacant status --short + auto_worker/auto_argon 同（乾淨？）
   - CI 一讀：ls ~/dev/ops/ci/{65e497da8,d29cfe694,ee71984a4}.json（有→讀；無→UNKNOWN；state.json 只記 running，不重試不等）
   - python ops/reqloop/freeze_check.py（期望 10/10 OK / FROZEN_STATE_OK / rc=0）
   - python -m pytest tests/test_reqloop_freeze_check.py tests/test_reqloop_frozen_anchors.py tests/test_reqloop_ci_contract.py（期望 24 passed）
   - git diff --name-only auto/qwen27b <branch> -- vacant_network tests ops（期望 0×2）
4. 記帳：STATE.md 加一行（≤5 行）、覆寫本檔、ops/STATE.md + ops/loop/NOW.md 同步、三分支各 commit（loop auto-push；不手動 push）。

## 紅線（每輪）

不 push（loop 自動）· .github/workflows/ 唯讀 · hidden/scorer 不讀 · frozen 4 檔（repair 2795 行/extract 1217 行/checks c7589c61/run_eval 332cd324）+ g2.5 filing 不改 · 不 reset/rebase · 不 sleep poll CI · G3 未 fire 不放 queue · 0 模型呼叫 · 不以改檔充當進度（無工單就驗證/記帳/待命）
