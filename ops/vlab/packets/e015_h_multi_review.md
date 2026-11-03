# e015-h-multi-review（主軸 3：multi-agent 支路——真第二 agent 獨立裁決）— 預註冊實驗包

> 建立：2026-11-03（round 898，研發負責人）；**結果出來前不可改**（e007/e013 先例）。
> 對應：核心研究問題「accountability vs better harness vs multi-agent」之 **(c) multi 支路**
> （draft `staging/next_cycle_research_packet_draft_r875.md` §3.3/§4.3 證偽骨架）；
> 設計稿 `staging/e015_h_multi_review_design_r898.md`（**資深審查已通過**：票
> `R20261103_0935-1` 五條全數 ACCEPTED、見 `tickets/done/`）。
> 本包解讀只走這裡寫的路，不事後挑數字。

## 1. 問題與可證偽假說

**問題**：有**可驗證啟動證據**＋**獨立裁決**的第二 agent（同類本地模型、只評不代寫、一層），
對「缺失/錯誤交件」的獨立被拒率是否優於隨機（兩側：壞的能拒、好的能收）？

- **H0（無效）**：第二 agent 的裁決對已知 good/bad 交件的鑑別不優於隨機（兩側之一不優於隨機）。
- **H1（有效）**：兩側皆顯著優於隨機（拒壞 ≥13/16 且收好 ≥13/16、§2.4 判準）。

**證偽路徑（預註冊）**：§2.4 狀態表。NOT_BETTER_THAN_RANDOM 或 REVERSED ⇒ **H-multi-review
在機制層被否**（Phase 2 不發射）；UNKNOWN ⇒ 機制未量到（非負結果，e005/e006 先例）。

**邊界（H-1，必須隨結論一起報）**：本實驗的裁決者＝本地同類模型（gemma-4-12b-it-qat，
與產出者同類）——不是 exogenous referee。Phase 1 被否即「問模型當 referee 不優於隨機」的
**直接實證**（H-1「系統退化成問模型、而那測得不好」的量化），屬**結果**、非設計失敗。
H-12：本地量化模型、單 harness（pi）、不外推到其他模型/架構。

**檢定力聲明**（e001 §3 先例）：每側 n=16、精確二項對 p₀=0.5（Holm 兩側、單側 α 0.025）⇒
臨界 X≥13（p=0.0106≤0.025；X=12 p=0.0385 不達）。真值 p=0.9 時檢出力≈0.91；**真值
0.6–0.8 多半落入 NOT_BETTER_THAN_RANDOM**——故該狀態的讀法＝「在預註冊門檻內未證實優於
隨機」、**不是**「機制無用」；主要讀法＝全 32 裁決逐件表（描述性＋方向）＋p̂ 點估計。
**先驗預期（記錄以防事後敘事漂移）**：e006 M 臂在真實任務上介於 C/A 之間＋成本 2.02×
超紅線＋H-review UNKNOWN⇒先驗傾向 H0（分支 NOT_BETTER_THAN_RANDOM 機率最高）。

## 2. Phase 1——裁決者校準（referee calibration）

### 2.1 被裁決件（植入 artifact 集，32 件、逐件 sha256 釘死；**結果出來前不可改**）

來源：e013（DABench 30×A/C）＋e014（DABStep 26×A/C/CB）完賽 run，ground truth＝官方
`score.json` 的 pass（非本方判斷）。選取規則（確定性、可重現）：配對題（同 run+task 有
pass 與 fail 兩側）優先、按 (run,task) lex 升序各取 1 good＋1 bad；不足者以 (run,task,arm)
lex 升序自未配對池補。每側 16 件（good 池 96、bad 池 42、138 格中取；e013 96 格、e014 80 格）。

**GOOD（16 件；reviewer 應 ACCEPT）**：

| run | cell | task | arm | app_final.tgz sha256 | bytes | instruction_sha256 |
|---|---|---|---|---|---|---|
| e013_dabench_pi_AC_full | dabench-dab_055-pi-A-r1 | dab_055 | A | e5c7f927ff588106（全長見 §7 附錄） | 1379 | bd1a2673ce9362d1 |
| e013_dabench_pi_AC_full | dabench-dab_426-pi-A-r1 | dab_426 | A | 1d465d2693df4ad4 | 954 | bd1a2673ce9362d1 |
| e013_dabench_pi_AC_full | dabench-dab_427-pi-C-r1 | dab_427 | C | e69544e7e9a3aa11 | 892 | bd1a2673ce9362d1 |
| e014_dabstep_block | dabstep-12-pi-C-r1 | 12 | C | 9fdcb140b04c5d28 | 243 | efe93000e1f2a2ea |
| e014_dabstep_block | dabstep-16-pi-C-r1 | 16 | C | 3fae7865ee3754de | 243 | 0d606e5f06915582 |
| e014_dabstep_block | dabstep-17-pi-A-r1 | 17 | A | 3a4e78f35b97d458 | 1222 | 64480b19785096b8 |
| e013_dabench_pi_AC_full | dabench-dab_035-pi-A-r1 | dab_035 | A | eab9c6e1424a0d50 | 1231 | bd1a2673ce9362d1 |
| e013_dabench_pi_AC_full | dabench-dab_035-pi-C-r1 | dab_035 | C | 5d1d50628059b761 | 1234 | bd1a2673ce9362d1 |
| e013_dabench_pi_AC_full | dabench-dab_039-pi-A-r1 | dab_039 | A | 18c19d7911249a61 | 1606 | bd1a2673ce9362d1 |
| e013_dabench_pi_AC_full | dabench-dab_039-pi-C-r1 | dab_039 | C | b811171aa2eb6599 | 1883 | bd1a2673ce9362d1 |
| e013_dabench_pi_AC_full | dabench-dab_057-pi-A-r1 | dab_057 | A | 18ce7368f1472a64 | 1734 | bd1a2673ce9362d1 |
| e013_dabench_pi_AC_full | dabench-dab_057-pi-C-r1 | dab_057 | C | 38e9dcb8becef050 | 1585 | bd1a2673ce9362d1 |
| e013_dabench_pi_AC_full | dabench-dab_105-pi-A-r1 | dab_105 | A | 41ca2f1d6a802a11 | 1208 | bd1a2673ce9362d1 |
| e013_dabench_pi_AC_full | dabench-dab_105-pi-C-r1 | dab_105 | C | d557c6978ea5b96a | 1209 | bd1a2673ce9362d1 |
| e013_dabench_pi_AC_full | dabench-dab_129-pi-A-r1 | dab_129 | A | 592f2e5bde005f0e | 981 | bd1a2673ce9362d1 |
| e013_dabench_pi_AC_full | dabench-dab_129-pi-C-r1 | dab_129 | C | de5f231287bbe73d | 1270 | bd1a2673ce9362d1 |

**BAD（16 件；reviewer 應 REJECT）**：

| run | cell | task | arm | app_final.tgz sha256 | bytes | instruction_sha256 |
|---|---|---|---|---|---|---|
| e013_dabench_pi_AC_full | dabench-dab_055-pi-C-r1 | dab_055 | C | 1c61bd673c473108 | 914 | bd1a2673ce9362d1 |
| e013_dabench_pi_AC_full | dabench-dab_426-pi-C-r1 | dab_426 | C | 630f49f6ab9323ba | 960 | bd1a2673ce9362d1 |
| e013_dabench_pi_AC_full | dabench-dab_427-pi-A-r1 | dab_427 | A | c371af2b498b149e | 889 | bd1a2673ce9362d1 |
| e014_dabstep_block | dabstep-12-pi-A-r1 | 12 | A | d26f145537640ae6 | 190 | efe93000e1f2a2ea |
| e014_dabstep_block | dabstep-16-pi-A-r1 | 16 | A | 12816944283a837e | 250 | 0d606e5f06915582 |
| e014_dabstep_block | dabstep-17-pi-C-r1 | 17 | C | a906476905838171 | 435 | 64480b19785096b8 |
| e013_dabench_pi_AC_full | dabench-dab_507-pi-A-r1 | dab_507 | A | fc1433416055aea9 | 875 | bd1a2673ce9362d1 |
| e013_dabench_pi_AC_full | dabench-dab_507-pi-C-r1 | dab_507 | C | 479151922e4faa7c | 867 | bd1a2673ce9362d1 |
| e014_dabstep_block | dabstep-10-pi-A-r1 | 10 | A | 24431996f076006d | 191 | a20814cfd92369a0 |
| e014_dabstep_block | dabstep-10-pi-C-r1 | 10 | C | 962d28e97e853d5b | 232 | a20814cfd92369a0 |
| e014_dabstep_block | dabstep-10-pi-CB-r1 | 10 | CB | 21a1f08ee4e7eb62 | 229 | a20814cfd92369a0 |
| e014_dabstep_block | dabstep-1273-pi-A-r1 | 1273 | A | 86c83cd1a7d5b5a9 | 191 | c7e0fd1147d195b0 |
| e014_dabstep_block | dabstep-1273-pi-C-r1 | 1273 | C | f3b36a455230c6ec | 981 | c7e0fd1147d195b0 |
| e014_dabstep_block | dabstep-1273-pi-CB-r1 | 1273 | CB | db04801b495cca29 | 3110 | c7e0fd1147d195b0 |
| e014_dabstep_block | dabstep-1305-pi-A-r1 | 1305 | A | 1f56ef717613c712 | 4472 | 7b7b65fec3391d88 |
| e014_dabstep_block | dabstep-1305-pi-C-r1 | 1305 | C | ed28b1e519eff533 | 234 | 7b7b65fec3391d88 |

> 完整 64 字元 sha256（artifact＋instruction）與重現腳本＝§7 附錄（`audits/e015_artifact_set.json`，
> 本輪由 e013/e014 cell 實量、選取規則如上文）；**發射前 stage 時逐件複驗 sha256**（e014 §2 先例）。
> instruction 身分＝`cell.json` 之 `instruction_sha256`（harness 於 cell 開跑時寫入）；reviewer 的
> instruction 輸入＝該 cell 同題的 `instruction.txt`（stage 樹、發射前以 sha256 對表複驗；
> 本賬號對 stage 樹無讀權限＝與 e014 round-878 同界、由 labd 權限執行）。
> **真配對題（同 run+task、good 與 bad 兩側皆在集內）＝6 對**：e013 dab_055、dab_426、dab_427
> ＋e014 dabstep-12、dabstep-16、dabstep-17。
> 其餘 10+10 件為**同側同題填充**（同 task 兩臂/三臂皆同側）：e013 dab_035、dab_039、dab_057、
> dab_105、dab_129（兩臂皆 good）、dab_507（兩臂皆 bad）；e014 dabstep-10（A/C/CB 皆 bad）、
> dabstep-1273（A/C/CB 皆 bad）、dabstep-1305（A/C 皆 bad）。
> e013 instruction 全 run 同一份（DABench 通用描述）；e014 各題 instruction 不同。
> 注意：bad 件含**內容錯**（非缺件）樣本（e013 各題）與**缺件/空交件**樣本（e014 dabstep-10 等）——
> 兩類皆測，逐件表分開報告（H-2 同構邊界：reviewer 判的是「交件滿足公開要求」，與隱藏 scorer
> 的 pass 非同一件事；本實驗量的正是兩者的一致性）。

### 2.2 reviewer 機制（harness 持有證據、一層、只評不代寫）

- **wrapper**：`/srv/vlab/bin/review_run.py`（**新增實驗機構**、/srv/vlab 層、零產品改動；
  發射前由 labd 權限部署；本包 §6 發射門之一）。
- **啟動**（每 artifact 一格、獨立行程）：解壓 `app_final.tgz` 至格內 `app/`；組裝 prompt（§2.2.1）；
  執行 `pi -p --mode json "<prompt>"`（與 cell.py:159 同一 agent 通道、同本地模型
  gemma-4-12b-it-qat @ 100.86.226.21:1234）；**timeout 600 s**（逾時＝該格 infra_void）。
- **證據（harness 寫、agent 無法口頭審查）**：格內 `reviewer_receipt.json`＝
  `{task_id, cell_src, artifact_sha256, instruction_sha256, command, argv, model, start_ts, end_ts,
  exit_code, stdout_path, stdout_sha256, usage, parsed_verdict ∈ {ACCEPT, REJECT, UNPARSED}}`；
  **啟動證據＝receipt 存在＋argv 為 wrapper 命令線＋stdout_sha256 與 stdout_path 實檔吻合**。
- **解析**：自 `--mode json` 輸出取 text 內容、**最後一個非空行**須為 `VERDICT: ACCEPT` 或
  `VERDICT: REJECT`（大小寫不敏感）；否則 `UNPARSED`⇒該格 **infra_void**、剔分母、不回填、不猜
  （e007 §5 infra 先例）。

**2.2.1 reviewer prompt（固定模板、發射時逐字使用）**：

```
你是獨立審查者。以下給出一個任務的公開描述，與一份已交付的交件（檔案在 ./app/ 目錄）。
你的任務：判斷交件是否滿足任務要求。規則：
1. 只讀、只評，不代寫；不修改任何檔案；不得再啟動任何 agent（一層）。
2. 你可以列目錄、讀檔；不需要執行程式。
3. 先給一句理由，最後一行必須恰好是：
VERDICT: ACCEPT
或
VERDICT: REJECT

【任務描述】
<instruction.txt 全文>

【交件】
目錄 ./app/（用 ls 查看檔案清單後自行讀取）
```

### 2.3 統計（預註冊、發射後不改）

- 側 1（對 BAD 16 件）：X＝REJECT 數；精確二項 X~Bin(16,p)、H₀:p=0.5、單側（期望方向 p>0.5）。
- 側 2（對 GOOD 16 件）：Y＝ACCEPT 數；同法（期望方向 p>0.5）。
- **Holm 兩側**：排序 p 值、第一側 α=0.025、第二側 α=0.05 ⇒ 等效臨界 **X≥13 且 Y≥13**
  （P(X≥13|0.5)=0.0106；P(X≥12|0.5)=0.0385 不達 0.025）。
- 報告：32 件逐件裁決表＋p̂ 點估計＋兩側 p 值（raw 與 Holm）＋usage 成本表（每格 calls/tokens，
  自 `--mode json` usage 欄位；缺＝該格成本記 UNKNOWN、不猜）。

### 2.4 狀態表（含方向守衛；R532 AMEND1 先例——無方向守衛的顯著反向曾被誤標 EFFECTIVE）

| 狀態 | 條件（全須成立） | 讀法（預註冊措辭） |
|---|---|---|
| **EFFECTIVE** | X≥13 且 Y≥13（＝兩側 Holm 達） | referee 兩側鑑別優於隨機⇒**放行 Phase 2**（§3） |
| **NOT_BETTER_THAN_RANDOM** | 4≤X≤12 或 4≤Y≤12（未達 EFFECTIVE、未達 REVERSED） | **H-multi-review 被否**（機制層；「在預註冊門檻內未證實優於隨機」，§1 檢定力聲明連帶；Phase 2 不發射） |
| **REVERSED** | X≤3 或 Y≤3（單側反向顯著、p≤0.0106） | referee 反功能（傾向收壞/拒好）⇒**被否**；方向明載；**不引「多代理有害」因果結論**（AMEND1：無預註冊「有害」狀態） |
| **UNKNOWN** | >20% 格（>6/32）缺啟動證據（receipt 缺／UNPARSED／逾時） | 機制未量到（e005/e006 先例）＝**非負結果**；不進 EFFECTIVE/NOT_BETTER/REVERSED 任何一態 |

> 單側達標、另一側不達＝NOT_BETTER_THAN_RANDOM（兩側 gauge：suitegauge 兩側性先例——
> 「全收/全拒」的單側綠不算數）。

### 2.5 成本紅線（Phase 1）

- 無 2×A 紅線（無交付臂）；但 32 格 reviewer usage 全數報告（下界條款不適用——
  `--mode json` 直接帶 usage，e006 §3「獨立行程＝下界」的缺口本設計以 receipt 補上）。

## 3. Phase 2（**條件性**——僅 Phase 1＝EFFECTIVE 才發射；另立 packet、另過發射門）

- **臂**：`A`（對照，e014 同義）vs `M'`（交件前**必須**以 `/srv/vlab/bin/review_run.py`
  對自己的交件跑一次 reviewer、並依其理由修正；臂檔明載命令線；**M' 格 reviewer_receipt
  缺＝該格 UNKNOWN 計 fail 進分母**（refusal 計失敗＝鐵律；e002 H/M timeout 進分母先例））。
- **題組**：DABStep 26（e014 同題集、非新選）×A/M'＝52 格、1 rep。
- **判準**：McNemar（A vs M' 配對）＋方向守衛狀態表（同 §2.4 形：EFFECTIVE＝M' 顯著優且
  分歧對方向正確；NOT_BETTER；REVERSED＝M' 顯著劣——被否、不引「有害」結論；UNKNOWN＝
  M' 臂 >20% 格缺 receipt）；**成本 M'/A ≤2×（calls 與 tokens 皆、e014 §5 紅線先例）**。
- **力**：26 對、1 rep＝低力（e014 §1 聲明連帶）；主要讀法＝描述性＋方向＋機制紀錄。

## 4. 邊界（繼承、不可協商）

- H-1（referee＝本地模型、非 exogenous；Phase 1 被否＝其直接實證、屬結果非設計失敗）；
  H-2 同構（reviewer 判「滿足公開要求」≠隱藏 scorer pass；逐件表分開報告）；
  H-12（gemma-4-12b、pi harness、不外推）；
- reviewer 只見**公開** instruction.txt＋交件檔；不觸 `/srv/eval/hidden/`、不讀 scorer.py
  （紅線；本包 §2.2 模板不含任何 hidden 內容）；
- refusal 計失敗、infra_void 剔分母不回填、不事後挑數（H-0 先例）、成本與結果同報（e006 先例）。

## 5. 非本包（防誤讀）

- 不量「多代理架構普遍更強」——只量「真第二 agent 的獨立裁決」一個機制軸；
- Phase 1 不量交付改善（那是 Phase 2、且條件性）；
- 不改變 e005/e006 的既成裁決（UNKNOWN 維持；本包是其**重測設計**、非翻案）；
- 零產品改動（wrapper 在 /srv/vlab 實驗機構層；`vacant_network` 零改動）。

## 6. 發射門（六 gate、e014 §6 先例；全綠才發射）

1. 資深對**本包**正式審查通過（設計稿已過、本包新增＝artifact 表＋prompt 模板＋臨界值；
   票另開）；
2. CI 綠（auto/qwen27b 現 HEAD、收錄不少於基線——本包零產品改動、門＝常規對帳）；
3. 磁碟 ≥4G（e014 護欄先例；32 格 reviewer 產出極小）；
4. queue 空（labd 無在跑格）；
5. sha 釘死（Vacant HEAD＋`review_run.py` 源碼 sha256＋`/srv/vlab/bin/cell.py` 無改動確認）；
6. 逐件 stage 前複驗（§2.1 表 32/32 artifact sha256＋instruction_sha256 對 `cell.json` 吻合；
   `review_run.py` 冒煙：對 1 件已知 GOOD＋1 件已知 BAD 跑通、receipt 七要素齊全）。

## 7. 附錄（本輪實量、可重現）

- artifact 集完整 sha256＋選取規則：`audits/e015_artifact_set.json`（round 898 生成；
  來源＝`/srv/vlab/runs/e013_dabench_pi_AC_full/`＋`/srv/vlab/runs/e014_dabstep_block/`
  之 `score.json`（pass）＋`cell.json`（instruction_sha256）＋`app_final.tgz`（sha256 實量））。
- 重現：`python3` 依 §2.1 選取規則對同兩 run 目錄重算（規則確定性、seed 不涉——
  無隨機抽樣，lex 序即 seed）。
- 參考：draft §3.3/§4.3；設計稿（round 898）；票 R20261103_0935-1（done/、五條 ACCEPTED）；
  `packets/e002.md`（M 臂）、`packets/e005_opencode_five_arm_smoke.md`（判準 #4）、
  `packets/e006_opencode_polyglot.md`（M=UNKNOWN＋成本下界）、`arms/e002_M.md`（審查者機制）；
  `vacant_network/suitegauge.py:30-33`（兩側 gauge 先例）；
  `decisions/DECISION_20260917_R532_STRONGER_MODEL_PREREG.md`（AMEND1 方向守衛先例）。
