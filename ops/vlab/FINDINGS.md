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

## 2026-10-29 · e001_pi_AC_baseline · polyglot_py 34 對（主軸 1 & 3：程式題基線）

**設定**：gemma-4-12b-it-qat、pi harness、polyglot_py 34 題、1 rep、A/C 同題配對。
**來源**：`ops/vlab/runs_e001_pi_AC_baseline/REPORT_polyglot_py_subset.{json,md}`（repo
commit `4480d6f9`）。

**數字**：A 15/34（44.12%）vs C 20/34（58.82%）；A_only＝2、C_only＝7、McNemar exact
雙側 p＝0.1797；成本（描述性）：A 117.07 呼叫/成功・3,299,729 token/成功・均牆 627.5s・
逾時 6，C 86.20 呼叫/成功・2,346,870 token/成功・均牆 607.7s・逾時 4、
`vacant_home_bytes` 合計 5,224,614 B（≈151 KB/格）。

**能說**：
- 在 polyglot_py 34 對中觀察到 C 臂 20/34（58.82%）對 A 臂 15/34（44.12%）
  （A_only＝2、C_only＝7）的**正向傾向**。
- C 臂的逐題紀錄是可究責的：34/34 格有完整 C 臂紀錄（test 檔引用＋執行證據，
  `P02_CARM_AUDIT.json`：review_allow 30／review_continue 2／review_other 0）；
  60/60 C 格 `vacant_home` 在 256 MiB 穩態封頂內（`ENVELOPE_COMPLIANCE.json`
  verdict＝PASS）——這是紀錄層面的合規，不是成效。

**不能說**：
- 單一 rep 下 `McNemar p＝0.1797` 未達 α＝0.05，**不能宣稱已證明 C 臂顯著優於 A 臂**；
  「正向傾向」只是本批觀察。
- 成本差（86.20 vs 117.07 呼叫/成功）為描述性，未做顯著性檢驗，不能當結論引用。

## 2026-10-29 · e001_pi_AC_baseline · 全體 60 對匯總（polyglot_py 34 + dabstep 26）

**設定**：同上，全部 60 題（34 polyglot_py＋26 dabstep）、1 rep。
**來源**：`/srv/vlab/runs/e001_pi_AC_baseline/REPORT.{json,md}`（rescore_mismatch＝0；
repo 內子集檔為同源 commit 版）＋ 上兩節。

**數字**：A 28/60（46.67%）vs C 34/60（56.67%）；A_only＝2、C_only＝8、McNemar exact
雙側 p＝0.1094（distinct_tasks＝60）；成本（描述性）：A 113.14 呼叫/成功・
3,187,094 token/成功・逾時 7・均牆 454.6s，C 77.44 呼叫/成功・2,058,161 token/成功・
逾時 5・均牆 417.9s、`vacant_home_bytes` 合計 23,756,010 B（≈392 KB/格）；
14 格 infra 不進分母。

**能說**：
- 全體 60 對觀察到 C 臂 34/60（56.67%）對 A 臂 28/60（46.67%）（A_only＝2、
  C_only＝8）的正向傾向；C 臂成本更低（77.44 vs 113.14 呼叫/成功、
  2.06M vs 3.19M token/成功）是**描述性**觀察。

**不能說**：
- 單一 rep 下 `McNemar p＝0.1094` 未達 α＝0.05，不能宣稱已證明 C 臂顯著優於 A 臂；
  兩子集方向一致（C 較高）是傾向，不是顯著性。
- 程式題與不同介入機制（H/M/S/C）的比較由 `e002_hypothesis_arms` 檢驗——本批只有
  A/C 兩臂，不能對 H/M/S 下任何結論。

## 2026-10-29 · e002_hypothesis_arms · polyglot_py A/C 中間（主軸 4 追蹤）

**狀態**：e002 進行中——A、C 臂各 34/34 完成（infra 2 格不進分母），H 4/34、M/S 未開始。
預註冊確認線（Holm 4 組比較，`ops/packets/e002.md` §4）需全批完成才能判定 H-acc 等假設。
**本節只有中間觀察，不是判定。**

**設定**：gemma-4-12b-it-qat、pi 0.87.1、polyglot_py 34 題、A/C 同題配對。
**來源**：`/srv/vlab/runs/e002_hypothesis_arms/REPORT.{json,md}`（report.py 由原始格重算；
rescore_mismatch＝[]＝0）。

**數字（本批）**：A 18/34（52.94%）vs C 22/34（64.71%）；A_only＝3、C_only＝7、
McNemar exact 雙側 p＝0.3438（distinct_tasks＝34、淨正 7／淨負 3）；成本（描述性）：
A 65.72 呼叫/成功・1,550,104 token/成功・逾時 8，C 67.95 呼叫/成功・1,716,779 token/成功・
逾時 4。預註冊成本紅線（C_C ≤ 2×C_A）：呼叫 67.95 ≤ 131.44、token 1.72M ≤ 3.10M——
**未觸發**（中間值）。

**跨批一致性（兩批 A/C，非重現論證）**：

| 批 | Vacant build（C 臂） | A | C | A_only/C_only | p（雙側，raw） | 呼叫/成功 A vs C |
|---|---|---|---|---|---|---|
| e001 | `dd2c6746` | 15/34 | 20/34 | 2/7 | 0.1797 | 117.07 vs 86.20 |
| e002 | `cf62d258` | 18/34 | 22/34 | 3/7 | 0.3438 | 65.72 vs 67.95 |

**能說**：
- 兩批（同模型/同 agent/同任務庫）方向一致（C 較高）、皆不顯著（0.1797、0.3438）。
  按 round 130 BACKLOG 規則（e001 C@`dd2c6746` vs e002 C@`cf62d258`：一致＝無版本/環境
  紅旗）——**無紅旗**。
- e002 C 臂成本紅線未觸發（中間值）。

**不能說**：
- 兩批 C 臂的 Vacant build **不同**（`dd2c6746` vs `cf62d258`）：跨批比較是
  **版本/環境一致性檢查，不是獨立機制重現**，不能當重現證據引用，更不得池成一個 n
  （紅線 4）。
- 不顯著 ≠ 無效也 ≠ 有效：兩批皆**未建立**（unresolved，不是負結果）。
- e002 的 Holm 校正 p 未定（H/M/S 未完成）；H-acc/H-harness/H-multi/H-stakes 判定全部
  待批完成；本節任何數字不得提前用於判定。
