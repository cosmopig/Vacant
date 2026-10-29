# vlab FINDINGS — 能說／不能說的句子（依 ASSIGNMENT.md「結論寫入本檔」）

每條：日期、實驗、數字（含分母與來源）、能說的句子、不能說的句子。
引用數字一律以 repo 內 commit 過的證據為準；`/srv/vlab/runs/*` 是原始格資料，
其匯總檔若與 repo 版 sha256 不同＝舊快照，不引用。

## 2026-10-29 · e001_pi_AC_baseline · dabstep 26 對（主軸 4：資料分析題）

**設定**：gemma-4-12b-it-qat、pi harness、dabstep 26 題、1 rep、A/C 同題同 seed 配對。
**來源**：`ops/vlab/runs_e001_pi_AC_baseline/REPORT_dabstep_subset.{json,md}`（26 對版，
sha256 83cebaf8…/dbcc0c85…）＋ `AUDIT_dabstep_mechanism.json`（79c0e7b4…）；
計畫：`ops/vlab/packets/e001_dabstep_analysis.md` §1–7（預註冊）＋ §8（本次解讀）。

**數字**：A 13/26（50.0%）vs C 14/26（53.8%）；A_only＝0、C_only＝1（dabstep-24）、
McNemar exact 雙側 p＝1.0；成本（描述性）：A 108.62 呼叫/成功・3,057,129 token/成功・
均牆 228.5s・逾時 1，C 64.93 呼叫/成功・1,645,720 token/成功・均牆 169.6s・逾時 1、
`vacant_home_bytes` 合計 18,531,396 B（≈713 KB/格）。機制：9 格 `missing_output`
kickback（全部被退回後補檔、final_action=allow），該 9 格隱藏 scorer 1 過 8 掛；
26 格 C 臂 app_final 全無可見測試檔（test 類檢查在本題庫休眠）。

**能說**：
- 在此設定下，**看不到可歸因 Vacant 的影響**（1 對差異、p＝1.0；且該對不歸因機制，見下）。
- 唯一 discordant 對（dabstep-24）已逐格核實：A 格 `answer_exists=false`（agent rc=0
  但從頭到尾沒寫 answer 檔）、C 格 `n_rounds=0, findings=[]`——**C 臂的過不是機制
  退回後改對的**，是跨 run 隨機差。
- 機制**有**在該題庫抓到 L-fake 形狀（9 格 missing_output 被退回、agent 補檔），
  但被退回的 9 格 8/9 仍掛在內容正確上——gate 保的是交付物形狀，不是內容對錯
  （H-2 同構；對資料分析題，「內容正確」本就不在該機制管轄內）。
- C 臂成本更低（64.93 vs 108.62 呼叫/成功、1.65M vs 3.06M token/成功）是
  **描述性**觀察：n＝26、1 rep、配對成本差未做顯著性檢驗，不能當結論引用。

**不能說**：
- 不能說「Vacant 在資料分析題上有效／無效」——樣本 26 題 1 rep，功效不足，
  且唯一差異對已核實與機制無關；正確說法是「看不到可歸因機制的影響」。
- 不能說「C 比 A 好」——14 vs 13、p＝1.0，且該 1 對不是機制造成的。
- 不能把 9 格 kickback 的 1 過 8 掛讀成「機制讓答案更差」或「機制沒用」——
  它抓的是 missing/empty output 形狀；內容正確從不在判準內。
- 不能引用 `/srv/vlab/runs/e001_pi_AC_baseline/` 的 25 對版匯總檔（dabstep-2697
  完成前的舊快照）。
- **e003（dabstep 全 79 題×2 rep）不發射**（分支 2 前提「L-fake 被退回後改對」
  未被本批支持）；主軸 4 就此記為「無可測影響」，資源轉主軸 2。
