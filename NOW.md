# 現在（第 1212 輪後，2026-11-07）

## r1212：CI 巡燈＋離線門禁複驗（0 模型呼叫、0 產品改動）
- ① c6f73f7f（本分支 HEAD，含 2db8afa5 合併＋beads 修正）本地 CI **🟢 5031 passed/74 skipped/0 failed**（5104 收集、839s）——r1211 預設的綠燈坐實；argan 合併帶進的 3 個新測試在內。
- ② `run_eval.py --all` 離線複驗（0 新 API 呼叫，vibe_calls 130→130）：G1 PASS（39/39・0 冤枉）、REAL14 PASS（9/9・1/5）；**PHASE3 fail-closed FAIL（rc=2）**：fixed 4／unresolved 1／error 4，STALE＝dab_039・dab_055・dab_426・dab_427。
- ③ PHASE3 紅燈**是 2db8afa5/3cf31e81 合併進的 STALE 機制在位、非回歸**：round 1199 規則變動後這 4 格舊裁決不得沿用；worker R20261107_1928-2 已驗證「PHASE3 FAIL rc=2 fail-closed＝expected behavior」；官方鎖檔 eval_phase3_glm53.json 未動（6/9＝round 1192 舊規則單 rep、round 1199 變動格未重跑、**不得宣稱現行管線即時成果**）。
- ④ extract.py 防發明機制在位（quote_is_verbatim L132／recompute type 白名單→unverified L511-521／模型自帶 unverified 一律尊重 L734-755）。

## 下一步
1. vq-el4 全 closed、bd ready 空、tickets 無新派、/srv/vlab/queue 空——等審查新派工／G2.5 後續。
2. PHASE3 現行管線重驗需線上 `--phase3`（4 格 STALE，模型呼叫）——未獲派工前不自動發起。
3. auto/argon 2db8afa5 CI 正在跑（state.json running），結果下輪巡。

## 紅線（不變）
main 不動；不手動 push；不讀 /srv/eval hidden/scorer；不繞 glm 直連 vibe；
不改 repair.py／G1 requirements.json／凍結快照；成本缺值＝UNKNOWN 不填 0。
