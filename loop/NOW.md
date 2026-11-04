# 現在做哪一個循環（這個檔要短：≤ 3 KB，只放「現在在哪、下一步」；每輪的紀錄寫 STATE.md，不寫這裡）

## ✅ 11/04 主管 #1 驗收＋缺分計數修復（round 956）
`audits/e016_verdict_pipeline.py`：slice 修復（endswith）與 done/ 門已在案（1821-1 票）；
兩驗收判準實跑達標（selftest ALL OK、live 48/102 正確非 0）。剩餘缺口＝「連 -r1 目錄都缺」
的格不計 missing（完賽後缺 ≥21 格仍對剩餘格出裁決＝靜默忽略缺格）⇒TDD 修復：
`missing_total＝missing_scored＋max(0,102−total)`，run() 於 INCOMPLETE 門後套用；
selftest 10 組 ALL OK（case 10＝5 計數斷言＋80 格⇒UNKNOWN）；live INCOMPLETE 48/102 RC=10
（進行中行為不變）；cost unittest 4/4；ops 1c54b4a／Vacant db745925（md5 位元組一致）。
argon 合併審查：c9a811fe 已為 qwen27b 祖先⇒無待合 commit；CI 0527d915 綠 4670，
e70ec0ec＋db745925 待下窗口（產品碼自綠後未變）。

## ✅ 11/04 分支 3（MECHANISM_CONFIRMED⇒強化）預備草稿（round 955）
`staging/next_cycle_reinforcement_draft_r955.md`（**草稿、非 packet、零產品改動、零發射**）：
發射前置＝e016 裁決＝MECHANISM_CONFIRMED（硬門；其餘四態⇒擱置、走 L007 §4 對應分支）。
假說空間 H-a（TEST_FAILED_MAX_ROUNDS 1→2、弱證據在案）／H-b（收斂語境回饋）／H-c（外端 referee）
＋選擇規則＋預註冊判準（留／撤＋成本紅線 2×A＋Holm＋H-12）＋六門承 e016。
助手工單 `R20261104_0124-1`（草稿引用只讀審計）在 doing/（助手已接走、全 PASS 才結案）。

## 🔴 下一步（e016 完賽後，依序；完賽前不准說 failed_step 是 C 勝 A 的來源）
1. `python3 /srv/vlab/bin/report.py e016_failed_step_ablation --rescore`（驗收 0 不一致）
2. `python3 audits/e016_verdict_pipeline.py` → 五態之一（成本紅線＋完賽缺分計數現在真正生效）
3. L006 §6 結案＋L007 §4 分支（MECHANISM_CONFIRMED⇒按 r955 草稿走新循環；
   NO_MECHANISM／UNRESOLVED⇒通用任務／資料題新機制；COST_BREACH／UNKNOWN⇒照 L007 §4 表）
   ＋FINDINGS e016 條目
- e016 attempt-2：48/102 在位（47 出分、A16/C16/C-nf16）；pace ~12–16 分/格、餘 54 格
  ⇒ETA 11/04 下午–11/05 中午；盤餘 62G、queue 空、无双分派
- CI auto/qwen27b：e70ec0ec/db745925 待出（輪末複核；紅燈先修紀律）
- attempt-1 的 15 格（`…attempt1_envleak/`）不進裁決；`recompute_results.json`（全是 0）
  與 `e016_failed_step_ablation_recompute.py` 不能當證據、不要引用
