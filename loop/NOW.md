# 現在做哪一個循環（這個檔要短：≤ 3 KB，只放「現在在哪、下一步」；每輪的紀錄寫 STATE.md，不寫這裡）

## ✅ 11/04 🔴 成本來源修復完成（round 954）
`audits/e016_verdict_pipeline.py`：成本在 `cell.json.metrics`（model_calls／input＋output tokens）；
score.json 只有 pass／tests_*。舊 load() 從 score.json 讀 ⇒ 恆 None ⇒ 靜默當 0 ⇒ 成本紅線
（>2×A）形同沒在檢查。修復：改讀 cell.json.metrics；該格成本欄位／cell.json 缺失 ⇒ 該格
UNKNOWN（不是 0）；**任何一格 UNKNOWN ⇒ 判定 UNKNOWN**（優於 COST_BREACH；未測≠通過）。
selftest 9 組 ALL OK＋新 unittest 4/4（fixture＝e016 真實格 pg_affine_cipher A／C）。
ops 251c06a／Vacant df28034e（位元組一致）。

## 🔴 下一步（e016 完賽後，依序；完賽前不准說 failed_step 是 C 勝 A 的來源）
1. `python3 /srv/vlab/bin/report.py e016_failed_step_ablation --rescore`（驗收 0 不一致）
2. `python3 audits/e016_verdict_pipeline.py` → 五態之一（成本紅線現在真正生效）
3. L006 §6 結案＋L007 §4 分支（MECHANISM_CONFIRMED→強化複審新循環；
   NO_MECHANISM／UNRESOLVED→通用任務／資料題新機制）＋FINDINGS e016 條目
- e016 attempt-2：46/102 在位／45 出分（pass A7／C6／C-nf7、成本 UNKNOWN 0 格）；
  pg_paasio A 在跑（labd 1007597、單分派）；pace ~12.6 分/格 ⇒ ETA 今天 ~12:30–13:30
- attempt-1 的 15 格（`…attempt1_envleak/`）不進裁決；`recompute_results.json`（全是 0）
  與 `e016_failed_step_ablation_recompute.py` 不能當證據、不要引用
