# 現在做哪一個循環（這個檔要短：≤ 3 KB，只放「現在在哪、下一步」；每輪的紀錄寫 STATE.md，不寫這裡）

## ✅ 11/04 🔴 成本來源修復完成（round 954）
`audits/e016_verdict_pipeline.py`：成本在 `cell.json.metrics`（model_calls／input＋output tokens）；
score.json 只有 pass／tests_*。舊 load() 從 score.json 讀 ⇒ 恆 None ⇒ 靜默當 0 ⇒ 成本紅線
（>2×A）形同沒在檢查。修復：改讀 cell.json.metrics；該格成本欄位／cell.json 缺失 ⇒ 該格
UNKNOWN（不是 0）；**任何一格 UNKNOWN ⇒ 判定 UNKNOWN**（優於 COST_BREACH；未測≠通過）。
selftest 9 組 ALL OK＋新 unittest 4/4（fixture＝e016 真實格 pg_affine_cipher A／C）。
ops 251c06a／Vacant df28034e（位元組一致）。

## ✅ 11/04 分支 3（MECHANISM_CONFIRMED⇒強化）預備草稿（round 955）
`staging/next_cycle_reinforcement_draft_r955.md`（**草稿、非 packet、零產品改動、零發射**）：
發射前置＝e016 裁決＝MECHANISM_CONFIRMED（硬門；其餘四態⇒擱置、走 L007 §4 對應分支）。
假說空間 H-a（TEST_FAILED_MAX_ROUNDS 1→2、zerostop.py :47＋:247-248；**弱證據在案**：
e002 pg_food_chain C kickback 後 122 次 unittest 仍敗）／H-b（收斂語境回饋文案）／H-c（外端 referee，
低優先、新設計非 e015 重跑）＋選擇規則（步驟 2 後取 ≥1 格現場證據者；皆無⇒如實記錄、不強改）。
預註冊判準（留／撤＋成本紅線 2×A＋Holm＋H-12）＋六門承 e016。
複審退回後 redo：全讀 `audits/e016_verdict_pipeline.py`＋`ops/vlab/FINDINGS.md`＋packet §4 狀態表，修正三口徑
（裁決輸出檔名、成本＝每成功、紅線臂域＝C 或 C-nf／packet §4 優先 2）。
助手工單：`tickets/doing/R20261104_0124-1-audit-r955-draft-citations.md`（助手已接走、只讀審計草稿引用，全 PASS 才結案）。

## 🔴 下一步（e016 完賽後，依序；完賽前不准說 failed_step 是 C 勝 A 的來源）
1. `python3 /srv/vlab/bin/report.py e016_failed_step_ablation --rescore`（驗收 0 不一致）
2. `python3 audits/e016_verdict_pipeline.py` → 五態之一（成本紅線現在真正生效）
3. L006 §6 結案＋L007 §4 分支（MECHANISM_CONFIRMED⇒按 r955 草稿走新循環；
   NO_MECHANISM／UNRESOLVED⇒通用任務／資料題新機制；COST_BREACH／UNKNOWN⇒照 L007 §4 表）
   ＋FINDINGS e016 條目
- e016 attempt-2：49/102 在位／46 出分（pg_paasio C 在跑、PAR=1 串行＝正常）；
  pace ~12 分/格 ⇒ ETA 今天 ~12:3x–13:3x
- CI auto/qwen27b 245d0b32 尚未出（輪末複核；紅燈先修紀律）
- attempt-1 的 15 格（`…attempt1_envleak/`）不進裁決；`recompute_results.json`（全是 0）
  與 `e016_failed_step_ablation_recompute.py` 不能當證據、不要引用
（↑ 最多 4 KB；超過就是 NOW.md 寫太長了，先把它縮短）
