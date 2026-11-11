# NOW.md — 現況（每輪更新，≤3KB）

## 狀態（2026-11-11 r1436）
- 唯一工單 P20261111_0840-1-g3-refire-c-prompt-override-and-maxcalls（vq-kax，AMEND-3 已批）：
  ①prompt 無工具覆寫（r1435 完成：NO_TOOL_OVERRIDE 頂部、round1+修復輪、2 測）②max_calls
  重測（本輪完成：PI_SESSION_CALL_CAP＝8（實測 pi 單 session max，fire b dab_144 raw）＋
  max_calls_bound 逐臂上界，c 計畫 48≥31＝fire b 實際；3 測負控先紅後綠；pin 解凍記錄）
  ③c 重發已發射（systemd vacant-g3-fire-20261111c、out＝~/dev/ops/g3_fire_20261111c、
  approval＝AMEND3、單發不重試）→結果下輪確認。
- CI 兩分支紅燈（freeze_check 4 案）根因：r1435 in-scope 改動未同步 worker/argon 工作樹＋
  NOW.md 紅線契約行缺（r1434 覆寫）＋STATE 鏡像尾行過時——本輪三項皆修（worktree 同步＋
  紅線行自磁碟實算恢復＋鏡像更新）。

## 紅線（契約，不改）
- 無 push（loop 自推 auto/qwen27b）、無 main、無 reset/rebase；.github/workflows/ 只讀。
- 凍結 4 檔不改：repair.py 2795 行／blob 5147f8c3…、extract.py 1217 行／blob e757aec5…、checks.py 2823 行／blob f3525b01…、run_eval.py 1298 行／blob b6d2f37f…；g25 filing（6 sha256）不改；g3.py 改動僅依 vq-kax 工單（AMEND-3 為其授權，執行順序照工單）。
- /srv/eval/hidden/、scorer.py 不讀；缺值 UNKNOWN 不填 0；hidden_after＝UNKNOWN；同批重發非獨立樣本、不宣稱臂 superiority。
- /srv/vlab/queue 不寫；無 poll CI；無 full pytest。

## 本輪工作（r1436）
- g3.py：舊 max_calls 式把「一次 pi session」當 1 call（PiChannel.call 內部 N 通 API
  呼叫、QuotaGuard 累計 RoundUsage.calls）→4 題×3 臂 28＜fire b 實際 31→假停
  （2 格 not_run/quota）。新 max_calls_bound＝n＋Σ臂 n×rounds×（pi 8｜1）；仍嚴上界、
  撞額＝停不重試；無 pi 臂每輪＝1 call（既有形狀）；預算欄位不動。
- 測試 29 passed（含 3 新測）；GUARD_CONTENT_PIN r1436 解凍記錄（g3.py
  5a94c167…／test_g3 3ed315e3…，磁碟實算）。
- c fire 10:10 UTC 發射；本輪 0 模型呼叫（模型呼叫全經 fire）。

## 未完成（≤3，下輪接手）
1. 確認 c fire 結果（g3_fire_20261111c/g3_result.json；12 格皆 ok/error/not_run 之一；
   若再撞 quota/turn_limit＝infra 歸因、不重試）→ticket 收案兩行＋三分支同步。
2. （若 c 仍 0/4 content_reverify）H1 已證偽→停、升級人類（G3.1 預註冊）。
3. worker/argon 同步 commit 已建、push 由 loop/人類（無 push 紅線）。

## 下輪入口（≤3）
- 讀 doing/ 工單→`systemctl --user status vacant-g3-fire-20261111c`→結果 JSON→收案簿記。
- 守衛：g3 3 檔＋anchors＋freeze_check（12 項）須全綠（含 now_redline、diff_worker/argon）。
