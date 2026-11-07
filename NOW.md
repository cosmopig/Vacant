# 現在（第 1213 輪後，2026-11-07）

## r1213：PHASE3 第一批 STALE 重驗完成（工單 P20261107_2028-1 → done）
- dab_039-pi-C **unresolved→fixed**（29 calls/2505080 tok）；dab_055-pi-C unresolved→unresolved（14c/668553t、stalled）。共 4 sessions/43 calls/3173633 tokens（1004 gemma-4-12b-it-qat；raw usage；無硬 token 上限）。
- 驗收＝**BATCH1_STALE_RESOLVED_OK**（commit 3f400c5d）。兩格帶 req_effective_sha256 入官方 progress.json；離線複驗 039/055 由 STALE→RESUMED。
- 路徑偏離（已記 DECISION）：字面 `--phase3 --limit 2` 對官方 9 格 freeze fail-closed（_freeze_matches 9≠2，設計使然）→ 改 `--p3-out phase3_batch1_20261107` 新工作目錄跑同 2 格；官方 freeze.json 未動；2 行裁決併入官方 progress.json（其餘 7 行原樣；舊裁決在 3f400c5d 前 git 歷史）。

## PHASE3 現況（口徑）
- 9 格：fixed 5（039 新、378、427*、507、dabstep-10、23 中 5）＋unresolved 2（055 新、1273）＋**STALE 2（dab_426、dab_427＝第二批，未重驗）**；離線門對剩 2 格 fail-closed rc=2＝機制在位。
- 所有裁決＝開發選樣單 rep（gemma 12b 本機）；039 fixed 是單格結果，不宣稱管線普遍較好。

## 下一步
1. 等第二批工單（dab_426/427 重驗）或審查新派工。
2. 巡 CI：auto/qwen27b 3f400c5d、auto/argon 2db8afa5（輪首時皆未跑完）。

## 紅線（不變）
main 不動；不手動 push；不讀 /srv/eval hidden/scorer；不繞 glm 直連 vibe；
不改 repair.py／G1 requirements.json／凍結快照；成本缺值＝UNKNOWN 不填 0。
