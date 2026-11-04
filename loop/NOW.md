# 現在做哪一個循環（這個檔要短：≤ 3 KB，只放「現在在哪、下一步」；每輪的紀錄寫 STATE.md，不寫這裡）

## ✅ 11/04 收口 runbook 預備完成（round 957）
`staging/e016_closeout_runbook_r957.md`（**staging、非 packet、零產品改動、零發射**）：
§0 前置（done/ 門＋rescore 不一致 0，非 0⇒停不裁決）→§1 裁決（`audits/e016_verdict_pipeline.py`
exit 0＝非 UNKNOWN／20＝UNKNOWN／10＝仍 INCOMPLETE；輸出 `e016_failed_step_ablation_verdict.json`）
→§2 五態逐字表（packet §4 條件＋讀法｜L007 §4 後續；round 957 逐字核對原檔、packet md5 兩 repo 一致）
→§3 結案寫三處（L006 §6 追加／L007 §4 標記不改原文／FINDINGS 正典＝Vacant repo、格式照 e015 條目）
＋兩 repo 鏡像 md5＋§4 共同紅線（L007 §4 逐字）＋attempt-1 排除。管線 selftest 10 組 ALL OK（本輪重跑 RC=0）。

## 🔴 下一步（e016 完賽那一輪，照 runbook 依序執行；完賽前只監控）
1. `ls /srv/vlab/done/16_e016_failed_step_ablation.json`（labd 已完賽；缺＝還在跑）
2. `python3 /srv/vlab/bin/report.py e016_failed_step_ablation --rescore`（驗收不一致 0；非 0⇒停）
3. `python3 audits/e016_verdict_pipeline.py` → 五態之一
4. 照 runbook §2 對應行**逐字**執行：
   1 UNKNOWN＝非負結果、infra 修復後重裁決、不寫機制結論；
   2 COST_BREACH＝機制判定不成立、不改產品、併讀 §2.5 成本病態；
   3 MECHANISM_CONFIRMED＝強化＝新 cycle＋新 packet（r955 草稿、TDD 先、六門＋senior 審查後才提升）；
   4 NO_MECHANISM＝C 勝＝採樣⇒不改產品、誠實記錄（不寫「kickback 無用」因果）；
   5 UNRESOLVED＝未建立（非負非正）、不改產品；候選 (b) 外端 referee／(a) H-harness-budget（低優先）
   ＋結案寫三處（L006 §6／L007 §4／FINDINGS e016 條目）＋兩 repo 鏡像＋commit
- e016 attempt-2：54/102 在位（49 出分）、02:14 events 活躍＝健康；pace ~12–16 分/格⇒ETA 11/04 下午–11/05 中午；
  盤餘 62G、queue 空、无双分派
- CI auto/qwen27b：271169fa 待出（輪末複核、紅燈先修紀律）；argon/worker 綠 4670
- 助手票 `R20261104_0124-1`（r955 草稿引用審計）在 doing/（最後活躍 01:46、不接手；全 PASS＋R&D 核驗後移 done/）
- attempt-1 的 15 格（`…attempt1_envleak/`）不進裁決；`recompute_results.json`（全是 0）與
  `e016_failed_step_ablation_recompute.py` 不能當證據、不要引用
