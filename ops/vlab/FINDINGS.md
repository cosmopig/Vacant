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

## 2026-10-29 · e002_hypothesis_arms · polyglot_py 五臂完賽（主軸 4 追蹤）

**狀態**（2026-10-30 17:0x 最終）：e002 **五臂完賽**——A/C/H/M/S 五臂各 34/34 完成
（REPORT.json `infra` 9 格不進分母；重新評分不一致 0 格）。
預註冊確認線（Holm 4 組比較，`ops/packets/e002.md` §4）**已判定（最終）**：Holm 校正後
四組（C/H/M/S vs A）p_holm 皆＝1.0，全數未達統計顯著水準（α=0.05）——誠實記錄、不作過度宣稱。
**本節只有客觀觀察，不是判定。**

**設定**：gemma-4-12b-it-qat、pi 0.87.1、polyglot_py 34 題、A/C 同題配對。
**來源**：`/srv/vlab/runs/e002_hypothesis_arms/REPORT.{json,md}`（report.py 由原始格重算；
rescore_mismatch＝[]＝0）。

**數字（本批）**：A 18/34（52.94%）vs C 22/34（64.71%）；A_only＝3、C_only＝7、
McNemar exact 雙側 p＝0.3438（distinct_tasks＝34、淨正 7／淨負 3）；成本（描述性）：
A 65.72 呼叫/成功・1,550,104 token/成功・逾時 8，C 67.95 呼叫/成功・1,716,779 token/成功・
逾時 4（皆取自 REPORT.json `per_arm.{A,C}`；配對數取自 `A_vs_C`）。預註冊成本紅線
（C_C ≤ 2×C_A）：呼叫 67.95 ≤ 131.44（＝2×65.72，由 REPORT.json
`per_arm.A.calls_per_success`×2 算出）、token 1,716,779 ≤ 3,100,208（＝2×1,550,104，
同式）——**未觸發**（中間值）。

**H/M/S 臂完賽數字（2026-10-30 最終回寫）**：H 15/34（44.12%）——成本（描述性）：130.2 呼叫/
成功・3,858,922 token/成功・逾時 11；M 15/34（44.12%）——成本（描述性，主行程下界）：116.13 呼叫/成功・
3,180,187 token/成功・逾時 8；S 20/34（58.82%）——成本（描述性）：71.65 呼叫/成功・1,782,990 token/成功・
逾時 6（皆取自 REPORT.json `per_arm.{H,M,S}`）。
跨臂配對（REPORT.json `paired`）：A_vs_H A_only＝5、H_only＝2、McNemar exact 雙側
p＝0.4531（未達顯著）；A_vs_M A_only＝6、M_only＝3、McNemar exact 雙側 p＝0.5078
（未達顯著；distinct_tasks＝34）；A_vs_S 配對 34、A_only＝3、S_only＝5、McNemar exact 雙側
p＝0.7266（未達顯著）。預註冊成本紅線（`e002.md` §4：任一臂 `calls_per_success` 或
`tokens_per_success` > 2×A＝131.44 呼叫 / 3,100,208 token 且通過率未顯著提升 ⇒ 記「不划算」）：
C（1.11×A token）與 S（1.15×A token）**未觸發**；**H 臂（3,858,922 token/成功＝2.49×A）與
M 臂（3,180,187 token/成功＝2.05×A，且未含子 agent 端點成本）皆突破 2×A token 紅線且通過率低於 A，
依預註冊判準記「不划算」**（另 `WIRING_GAUGE.json` 顯示 M 臂僅 14/34 格有啟動第二 agent 證據，
其餘 20/34 格退化為提示式自檢）。

**跨批一致性（兩批 A/C，非重現論證）**：

| 批 | Vacant build（C 臂） | A | C | A_only/C_only | p（雙側，raw） | 呼叫/成功 A vs C |
|---|---|---|---|---|---|---|
| e001 | `dd2c6746` | 15/34 | 20/34 | 2/7 | 0.1797 | 117.07 vs 86.20 |
| e002 | `cf62d258` | 18/34 | 22/34 | 3/7 | 0.3438 | 65.72 vs 67.95 |

數字來源：e001 行＝repo 版 `ops/vlab/runs_e001_pi_AC_baseline/REPORT_polyglot_py_subset.json`
（見上節 e001 polyglot 來源行；e001-dabstep 包 §8 規定 /srv/vlab 同名檔是 dabstep-2697 前
的舊 25 對快照，**不可引用**）；e002 行＝上段 REPORT.json。Vacant build：e002 C 臂＝
REPORT.json `per_arm.C.vacant_sha`＝`cf62d258…`；e001 C 臂＝job 檔
`/srv/vlab/done/01_e001.json` `vacant_sha`＝`dd2c6746…`（e001 子集 REPORT 不帶該欄）。

**能說**：
- 兩批（同模型/同 agent/同任務庫）方向一致（C 較高）、皆不顯著（0.1797、0.3438）。
  按 round 130 BACKLOG 規則（e001 C@`dd2c6746` vs e002 C@`cf62d258`：一致＝無版本/環境
  紅旗）——**無紅旗**。
- e002 C 臂與 S 臂成本紅線未觸發（1.11×A 與 1.15×A token）；H 臂（2.49×A token）與 M 臂（≥2.05×A token）
  觸發預註冊 `>2×A` 成本紅線，依 `e002.md` §4 記為「不划算」。
- A/C/H/M/S 五臂 34/34 完賽（A 18/34、C 22/34、S 20/34、H 15/34、M 15/34）——
  這些是**已確立事實**（完賽與配對數字），Holm 校正後四組 p_holm 皆＝1.0。

**不能說**：
- 兩批 C 臂的 Vacant build **不同**（`dd2c6746` vs `cf62d258`）：跨批比較是
  **版本/環境一致性檢查，不是獨立機制重現**，不能當重現證據引用，更不得池成一個 n
  （紅線 4）。
- 不顯著 ≠ 無效也 ≠ 有效：兩批皆**未建立**（unresolved，不是負結果）。
- e002 的 Holm 4 組校正判準（預註冊，`ops/packets/e002.md` §4）**已判定（最終，10/30 17:0x）**：
  四組（C/H/M/S vs A）p_raw 0.3438/0.4531/0.5078/0.7266 → p_holm 皆＝1.0、**全數未達統計顯著**
  （α=0.05）——誠實記錄：預註冊假設全數未建立（unresolved，不是負結果），不作過度宣稱。
  「不顯著」≠「無效」；本節任何數字不得用於「假說被證明」之類表述。

## 2026-10-29 · 主軸 2 ·「~/.vacant 從零開始一天長多少」（真機跨日序列收口）

**量具**：`ops/vlab/tools/growth_report.py`（round 187 新增；唯讀；上限常數直接
import `vacant_network.retention`＝`DEFAULT_TRACE_BUDGET_BYTES` 64 MiB、
`STABLE_ENVELOPE_BYTES` 256 MiB；證據不足＝UNKNOWN 不假 PASS；
`tests/test_vlab_tools.py::test_growth_report_selftest_and_verdict_semantics` 紅綠對照在內）。
**序列**（兩份 JSONL 併排去重）：`~/.vacant/growth.jsonl`（round 186 起 auto gc
每次真跑自動記）＋ `~/dev/ops/data/vacant_growth.jsonl`（手動快照）＝ 30 點跨 44.2h（2026-10-28T20:20 → 2026-10-30T16:32）：

| ts | 總計 | trace | objects | gc |
|---|---|---|---|---|
| 10/28 20:20 | 82.3 MiB | 65.0 MiB | 821 | ok, target_reached=true |
| 10/29 00:48 | 35.2 MiB | 17.7 MiB | 522 | ok, true |
| 10/29 09:32 | 51.3 MiB | 34.2 MiB | 537 | ok, true |
| 10/29 14:46 | 49.7 MiB | 32.3 MiB | 750 | ok, true |
| 10/29 17:44 | 50.1 MiB | 32.6 MiB | 620 | ok, true |
| 10/29 20:53 | 50.7 MiB | 33.1 MiB | 548 | ok, true |
| 10/29 22:22 | 50.7 MiB | 33.1 MiB | 574 | ok, true |
| 10/29 23:28 | 50.9 MiB | 33.2 MiB | 568 | ok, true |
| 10/30 00:28 | 51.5 MiB | 33.8 MiB | 629 | ok, true |
| 10/30 01:29 | 51.6 MiB | 33.8 MiB | 585 | ok, true |
| 10/30 02:34 | 51.8 MiB | 34.0 MiB | 568 | ok, true |
| 10/30 03:06 | 52.4 MiB | 34.5 MiB | 725 | ok, true |
| 10/30 03:37 | 52.7 MiB | 34.8 MiB | 567 | ok, true |
| 10/30 04:45 | 53.5 MiB | 35.5 MiB | 590 | ok, true |
| 10/30 05:45 | 52.7 MiB | 35.5 MiB | 586 | ok, true |
| 10/30 06:47 | 53.3 MiB | 36.1 MiB | 587 | ok, true |
| 10/30 07:33 | 53.8 MiB | 36.4 MiB | 598 | ok, true |
| 10/30 08:02 | 54.4 MiB | 37.0 MiB | 577 | ok, true |
| 10/30 08:08 | 54.5 MiB | 37.0 MiB | 591 | ok, true |
| 10/30 08:13 | 54.5 MiB | 37.1 MiB | 596 | ok, true |
| 10/30 09:14 | 55.5 MiB | 37.9 MiB | 597 | ok, true |
| 10/30 10:14 | 56.6 MiB | 38.7 MiB | 641 | ok, true |
| 10/30 11:16 | 57.5 MiB | 39.5 MiB | 684 | ok, true |
| 10/30 12:17 | 57.8 MiB | 40.6 MiB | 704 | ok, true |
| 10/30 13:17 | 58.2 MiB | 40.9 MiB | 710 | ok, true |
| 10/30 14:18 | 59.1 MiB | 41.6 MiB | 706 | ok, true |
| 10/30 15:19 | 60.0 MiB | 42.4 MiB | 718 | ok, true |
| 10/30 16:32 | 61.8 MiB | 44.0 MiB | 948 | ok, true |
| 10/30 18:51 | 54.1 MiB | 24.3 MiB | 380 | ok, true |

零點＝10/28 08:14 人工清場（ASSIGNMENT 備份 `1003 D:/vlab_backup/vacant_data_20261028_0814.tgz`，
sha256 `49e8be1b…4068`）；10/28 08:16 舊碼（round 139 store-on-copy）曾回灌 542 MB / 17,097 blobs，
round 142 起 store-on-change＋64 MiB 預算後才出現上表序列。

**能說**（2026-10-30 16:3x 真機 `growth_report.py` verdict=PASS，rc=0）：
- **一天長多少：24h 視窗最大增長 16.3 MiB**（2G repo 全日開發＋e002 實驗負載下）。
- 範圍 35.2–82.3 MiB：峰值 82.3 MiB 是 10/28 20:20 舊日累積，次日 gc 削至 35.2 MiB；
  惟 10/29 14:46（49.7 MiB / trace 32.3 MiB）至 10/30 16:32（61.8 MiB / trace 44.0 MiB）
  連續 26 個小時點呈現單調緩升（+12.1 MiB），主因是 `compact_trace` 第一階段原先未對
  `unrecorded_change` 檔案 blob 與已過期工作階段之 `prompt` blob 套用 `min_kept_seq` 視窗
  （且未達 64 MiB 前第二階段 `_sweep_to_target` 不啟動）；該視窗漏洞已於 `auto/argon` 修復，
  在真機 `~/.vacant` 上可立即多回收 8.34 MiB（399 個過期 blob）——**10/30 18:50 真機驗證（round 337）**：
  auto_gc 實測釋放 9,482,666 B（9.04 MiB、974 檔、trace 948→378 blobs 保留、ok＋target_reached），
  總計 64,827,429 B（61.8 MiB，16:32 點）→ 56,752,169 B（54.1 MiB，gc 後）；`gc --verify` verify_ok=True（8/8 專案）、
  `growth_report.py` verdict=PASS；前後數字全見 disk_top_priority.md §1（10/30 18:51 續記）。
- 全程 ≤ 256 MiB 穩態封頂的 32%（82.3/256）；最新 61.8 MiB（24.1%）、
  最新 trace 44.0 MiB ≤ 64 MiB 上限。
- 這是**真機 `~/.vacant`** 的跨日序列（30 點、44.2h），不是模擬、不是單點。

**不能說**：
- 不能說「上限永遠不會被觸發」：64 MiB 是 trace objects 的**軟**上限（disk_top_priority §1
  誠實邊界），工作集過大時會暫超待 gc 收回；10/28 20:20 的 trace 65.0 MiB 就是暫超實例
  （量具因此只對**最新點**判 FAIL，歷史峰値只記在 `peak_overrun`）。
- 不能外推到別的使用模式：序列是「單機、單使用者、單 repo、兩日」，負載＝日常開發＋
  e002 實驗；更高並發／更多 repo 需重新量（H-12 同口徑）。
- e002 全臂最終（10/30 17:0x，S 臂 34/34 完賽）：四量具（report.py --rescore／e002_wiring_gauge／
  envelope_compliance／p02_carm_audit）全部 rc=0，五臂各 34/34（A 18、C 22、H 15、M 15、S 20 pass）；
  C 臂 34/34 `vacant_home_bytes` 已最終回寫，A/H/M/S 臂不裝 Vacant 故依設計 N/A；
  p02_carm_audit e002 live rc=0：C 臂 34/34、c_installed_FAIL=0、score 22 pass／12 fail 與 REPORT.json 一致、
  tasks_with_complete_record 31/34（3 題 NO_EVIDENCE＝鏈上無 review 條目的誠實記錄、非 FAIL）；
  **全臂最終分析回寫完成**（本項收口，disk_top_priority §5-4）。

## 2026-10-29 · 主軸 2 ·「fixed 安裝面也有命名上限」（packet §4 誠實缺口收口）

**改動**（round 190，小改動＋紅燈測試先行）：`ENVELOPE_COMPONENTS` 的 4 個 `fixed`
組件（adapters / gc_report.json / gc_last.json / gc.lock）從「只有『不增長』的語義
保證、無命名上限」升級為每個都有命名位元組上限
`retention.DEFAULT_FIXED_COMPONENT_BYTES`＝1 MiB（平時幾 KiB，25 倍餘裕）；
`envelope_accounting` 新增 `fixed_overrun`（{name: {bytes, cap_bytes}}）與
`fixed_within_caps`；`byte_caps_sum` 現在含 fixed 上限（168.25→172.25 MiB ≤ 256 MiB）；
`usage_report().envelope.within_envelope` 多一個條件 `fixed_within_caps`（fixed 面越限
＝「固定不增長」被打破，量具不得宣稱在封頂內）。fixed 面沒有回收路徑——量具只報告、
不刪除（fail-open）。
**證據**：`tests/test_retention.py::test_envelope_fixed_components_have_named_caps`＋
`test_envelope_accounting_flags_fixed_component_overrun`（紅燈先行、adapters 灌
1 MiB+16 KiB 越限點名＋不刪除＋`within_envelope` False）＋
`test_envelope_byte_caps_sum_within_stable`（加總含 fixed 上限）；
`tests/test_retention.py` 39 passed；四驗收檔 91 passed（RC=0）。
**能說**：
- 「fixed 組件若實際增長」從「要靠人類注意到」變成量具自動點名
  （`envelope_accounting().fixed_overrun`／`vacant usage` 的 `within_envelope` False）。
- 真機 `~/.vacant` 實測：`fixed_overrun={}`、`fixed_within_caps=True`、
  `byte_caps_sum`=172.25 MiB ≤ 256 MiB、`within_envelope=True`（20.09%）。
**不能說**：
- 不能說 fixed 面「有回收路徑」——越限時量具只報告，清理仍是人的動作
  （adapters 是安裝面，Vacant 不刪自己語義不認得的增長）。
- 1 MiB 是**警報上限**不是硬刪上限：選值＝現行實測（~40 KiB）的 25 倍，
  若某版本合理增大 adapters，應在此表調大命名上限並留記錄，而非讓量具常紅。

## 2026-10-30 · 主軸 2 ·「count-based 分組也有命名總上限」（packet §4 最後一個誠實缺口收口）＋ e002 C 臂最終回寫

**改動**（round 192，小改動＋紅燈測試先行）：`trace/projects` 步鏈＋索引、`intake`、
`quarantine` 三個 count-based 分組向來只有**機制**上限（50 步回收／2 MiB 每檔／每 task
2 裁決）、**沒有總位元組上限**——檔案數／專案數／步數隨時間累積時可長期增長，量具偵測
不到。round 192 新增 `retention.COMPONENT_TOTAL_CAPS` 命名總上限：trace 整體
＝objects 64＋projects 子 **32 MiB**（`DEFAULT_TRACE_PROJECTS_CAP_BYTES`）、intake
**8 MiB**（`DEFAULT_INTAKE_TOTAL_CAP_BYTES`）、quarantine **16 MiB**
（`DEFAULT_QUARANTINE_TOTAL_CAP_BYTES`）；`envelope_accounting` 新增通用 `overrun`
（{name: {bytes, cap_bytes}}，fixed 與 count-based 都在內）＋`within_caps`，
`fixed_overrun`／`fixed_within_caps` 保留為 fixed 子集（round 190 欄位同義）；新增
`all_caps_sum`＝所有命名上限加總（172.25＋32＋8＋16＝**228.25 MiB ≤ 256 MiB**）＋
`all_caps_sum_within_envelope`；`usage_report().envelope.within_envelope` 改為要求
`within_caps`；`vacant usage` 人讀輸出點名越限組件（`⚠ <name> 超命名上限: X / Y`）。
**能說**：
- 「count-based 分組無上限增長」從「要靠人類注意到」變成量具自動點名
  （`envelope_accounting().overrun`／`vacant usage` 的 `within_envelope` False）。
- 所有命名位元組上限加總 228.25 MiB ≤ 256 MiB 封頂有常規測試把關
  （`test_envelope_counted_components_have_named_total_caps`）——封頂不再是紙面數字。
- e002 **C 臂最終**：envelope_compliance 34 格全 PASS（未超 256 MiB 穩態封頂）、題目 benchmark 評分 22/34 PASS（64.71%）、1 infra（NA 不進分母）、
  `vacant_home_bytes` min 29,089 B／median 105,134 B／max 316,854 B（≈28.4–309.4 KB/格）、
  rescore mismatch 0、envelope_compliance verdict=PASS、四量具 rc=0（18/18 階段值
  35,563/161,209/290,622 為中間值）。
- e002 **C 臂未通過 12 題型態分析**（round 207 回寫；來源＝`ops/vlab/tools/e002_carm_failures.py`
  EXIT=0 客觀輸出：34 格中 12 格未通過＝4 逾時＋8 未收斂，22+12＝34 與上條 22/34 口徑一致）：
  - **4 逾時格**（agent rc=124 牆鐘逾時；測試進度為 score.json 記錄值）：**forth 52/54、grep 17/25、
    hangman 5/7、sgf_parsing 17/23**（其中 forth/grep/sgf_parsing 為 `stop_checks=0, rejections=0` 未及收件即逾時；
    hangman 為 `stop_checks=1, rejections=1`，被退回 1 次後於重試中逾時，最後 hint：`test_after_10_failures_the_game_is_over:
    AssertionError: 'ongoing' != 'lose'`）。**react 實為 PASS 格**（score.json `pass=true`、14/14），不屬逾時題——
    更正先前審查指示「第 4 逾時題為 react」之誤記，實為 **sgf_parsing**。
  - **8 未收斂格**（agent rc=0、測試未過）：bottle_song 1/7、food_chain 3/10、go_counting 10/11、
    paasio 23/25、poker 33/37、rest_api 6/9、scale_generator 12/17、zipper 9/14。
  - 退回次數：其中 7 格退回 1 次（`stop_checks=2, rejections=1`，1 round 後仍 open，最後 hint 為
    「step N (python3 -m unittest X_test.py) had failed」）；**zipper 為 `stop_checks=1, rejections=0`**
    （`vacant_home.tgz` 內 `events.jsonl`、`chain.ndjson` 與 `delivery.json` 明確記錄 `action="allow", rounds_used=0`，
    因 `021c8924` 修補前 `python3 zipper_test.py` 跑 0 測試 exit 0，zerostop 見 `findings=[]` 放行並 unlink 暫存 `rounds_*.json`；
    已修補 `e002_carm_failures.py` 讀取 `events.jsonl`/`chain.ndjson`，不再誤報為 UNKNOWN）。
  - 口徑：本條是失敗格客觀型態記錄（哪題、測試進度、退回次數、最後 hint），可查證、可重算
    （重跑該工具即得同輸出）；不作為「C 臂較好」的證據，也不證明任何成效。
**證據**：`tests/test_retention.py::test_envelope_counted_components_have_named_total_caps`＋
`test_envelope_accounting_flags_counted_component_overrun`（intake 8 MiB+16K、
quarantine 16 MiB+16K 越限點名＋不刪除＋`within_envelope` False）＋
`test_envelope_accounting_flags_trace_projects_overrun`（trace/projects 灌 96 MiB+16K
越限點名＋不刪除）；`tests/test_retention.py` **42 passed**（39→42）；四驗收檔
（envelope_compliance／vlab_tools／universal_and_coding_upgrades／retention）**94 passed
（RC=0）**；真機 `vacant usage` 實測 **52.22 MB / 256 MiB（20.4%）✓、overrun={}、
within_caps=True、all_caps_sum 228.25 MiB ≤ 256 MiB**。
**不能說**：
- 不能說這些分組「有回收路徑」——越限時量具只報告、不刪除（fail-open）；
  `trace/projects/chain.ndjson` 是記責記錄，GC 向來不碰，這是語義決定不是漏做。
- 32/8/16 MiB 是**警報上限**不是硬刪上限：選值＝現行實測（projects 5.46 MB／intake
  1.94 MB／quarantine 0 B）的 ≥3 倍，長期超限時應調大常數並留記錄，不該靠量具假裝沒事。
- e002 全臂最終**已完成**（10/30 17:0x）：五臂各 34/34、四量具全 rc=0、Holm 4 組校正後
  p_holm 皆＝1.0 全數未達統計顯著（誠實記錄、不作過度宣稱）；全臂回寫完成（disk_top_priority §5-4）。
