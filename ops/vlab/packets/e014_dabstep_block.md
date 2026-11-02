# e014-dabstep-blocking（主軸 4：consumption side — blocking level）— 預註冊實驗包

> 建立：2026-11-02（round 876，研發負責人）；**結果出來前不可改**（e007/e013 先例）。
> 對應：核心研究問題「accountability vs better harness vs multi-agent」
> （draft `staging/next_cycle_research_packet_draft_r875.md` §3.4 H-acc-consume）、
> `packets/e007_dabench.md` §5.2 指引（「主軸 4，若再投入，應測『阻擋級』（controller 形式）……
> 而不是重測同一設計」）、e013 分支 4 裁決（recording side 已測：DABench 上無可測影響＋無介入紀錄；
> consumption side 從未測＝draft P-4）。
> 本包解讀只走這裡寫的路，不事後挑數字。

## 1. 問題與可證偽假說

**問題**：當下游決策者（stop-check）基於 receipt/findings 做**有真實後果**的決策——
請求的交件不存在時，session 不得結束（blocking level，不是建議）——通過率與代價有沒有改變？

- **H0（無效）**：blocking level 與 evidence level 的通過率在 noise 內，介入紀錄不改變結果。
- **H1（有效）**：blocking level > evidence level——被 hold 的缺件格真正產出交件、目標格翻轉為 pass。

**證偽路徑（預註冊）**：§5 分支表。分支 1（CB≈C＋有介入紀錄）或分支 3（CB<C）達標 ⇒ H1 在
此題集被否決；分支 4（無介入紀錄）⇒ **UNKNOWN**（機制未觸發、不是 H1 的負結果，e013 D2 先例）。

**邊界（H-2 同構，必須隨結論一起報）**：blocking level 查的是**交件存在**（`missing_output`），
不判內容正確；內容裁判是隱藏 scorer。被 hold 後內容仍錯的格＝fail、不是產品 bug。
e001 已給出該邊界的實例：9 個 missing_output kickback 格全部補檔（形式救回）、隱藏 scorer 1 pass / 8 fail。

**檢定力聲明**（e001 §3 先例）：26 對、1 rep，McNemar 檢定力極低（1/1 → p=1.0；2/0 → p=0.5）；
主要讀法是**描述性＋方向**（discordant pair 數、方向、逐格代價與機制紀錄），不報「顯著/不顯著」之外的強結論。

**先驗預期（記錄以防事後敘事漂移；不改變分支表）**：e001 顯示 agent 對 advisory kickback 已依從
（9/9 在 ≤2 回合內補檔）⇒ 預期 CB 對 C 的增量小（分支 1 機率最高）；分支 2 觸發需要
「agent 放棄/做不出、hold 才完成」的格——罕見。

## 2. 題集、臂、對照

**題集：DABStep 26 題**（e001 子集＝`/tmp/bm_tasks/dabstep` 依名稱排序前 26；同一題集、非新選、
非事後挑）。選題理由（對源）：

- e001 是**唯一**消費路徑實質觸發的全盤 run：9/26 C 格 `missing_output` kickback
  （`ops/vlab/runs_e001_pi_AC_baseline/AUDIT_dabstep_mechanism.json`，repo 版）。
- e013 DABench 30 題＝zero_ran 30/30、無介入紀錄（分支 4 裁決）⇒ 在 DABench 上測 blocking level，
  消費路徑不觸發、量到的是「無機制」（UNKNOWN）。**DABench 負對照不入本 run**（§6）。

| 題（lex 序） | 題樹 sha256（instruction.txt＋workspace，2026-11-02 對 `/tmp/bm_tasks/dabstep` 實量） |
|---|---|
| 1 | a414cd90f57dc2035d68d6b920199ceb265ceed9512c4ab830bf9da743114805 |
| 10 | a33742fa38183f28a9ac0b2a650465d278edbaf33907121f91dc6c24b1ccc1a8 |
| 11 | 0a702bdb61d46fa89b38eb842163435dff5fd4724ab5a59b16b782ce88fa9022 |
| 12 | ae942d01c37d496e3b0a147921e65284368e4ff1ae0ff2b02c2d68263e2c80e0 |
| 1273 | 13aee07341537a16a699b811bea40280b39cdc0828009ffd6b275f955b538da7 |
| 13 | e70314e649d9ef5a865538e02718ba9993106b65490ff0b37fa6b087598ea8fe |
| 1305 | 8e72c5cc1bb6f94909df728462d5e66e3b58cbf70fcbfd942b974800a5ebca4e |
| 14 | 29677cb4b5138de9888998e48c3482b29444aba25cff3498cb89f97bc15f8399 |
| 1464 | 0b8b79b8f788f0ec2993350932ecc52e02e3b291d2ba22044f8c56b2b37ba30b |
| 15 | 7cc911b46b3f3452bf10f1deace31968a987f6da3f1df388c43e1e1947bfc897 |
| 16 | 61ae671dff03eb82c44824ae2aaf5ea554918e419895d936eb32e8765c66ea97 |
| 1681 | 642d2717c48da2b0f45c5ad81ea51bf4a5b177d796089362a3da238c60bc3d53 |
| 17 | bf01217cec77dc60d4239204923d572d994f7880f8f6d1ef0f6843cc95a43300 |
| 1753 | 567146c833b4d4e03b7bedf28935483ca863f419f073f0cc6c458398c87a2d10 |
| 18 | 467ea0353a31f8624574fc8c92a20ebf8313ff6b4a7e9755dd1eb69aa8a56fc3 |
| 1871 | 3ed6767af12631b3187249e82e4e1e92b4b37641d399d423bb7f8d609ce48149 |
| 19 | 5d2911bc09a2f6e36e802a6e4192f840e4d4ad296ec4eb243589b2ac47109ff3 |
| 2 | 1e55b4001f3dc895e78f84e6fc6d97c731709e21d7a75feb98ae2dab8a809a4a |
| 20 | 20b4e34db2463515f080eedb327826882a4e2056005180a9bbd67319ba5099f5 |
| 21 | 25d66a3c9a490af33d842d35558f274626734b154770aabc28d6f6a9b957fdd2 |
| 22 | 49c961f1b720b7798541ff6b502ff7145b525d7eece43172799daed3230e1b6b |
| 23 | d515775830c3165a972802fe791555be39a5c13fa722624bc0a24f71fc9465bc |
| 24 | 75e256773a825147d4f3dab2cf8c7de3a6f4866208327e614c67d274cfe55603 |
| 25 | fd86967c3969c019cff2bd30af4e442b5545e7e15885e425f3c66b20470f09f6 |
| 26 | d554d30fd97d6a6ab884cfc620f592561b62e7906a5df5d36132f15885d45821 |
| 2697 | aef9cffdca73c0489257a9ebaa2cce464799d88cac0525fd5398418cd82b01ed |

> 量法：`cd /tmp/bm_tasks/dabstep/<t> && find . -type f -print0 | sort -z | xargs -0 sha256sum | sha256sum`（2026-11-02 實量；發射前 stage 時逐題複驗）。

> **round 878 驗證備註（2026-11-02，不改變上表）**：上表可對 `/tmp/bm_tasks/dabstep` 重現（26/26；
> 該樹＝instruction.txt＋空 workspace 的骨架，79 題目錄，10/22 建立）。但 cell.py 實際讀取的樹是
> `/srv/eval/staged/dabstep`（10/02，instruction＋workspace 資料＋scorer.py＋hidden；e001 所跑的樹），
> 與上表 26/26 不符；兩樹 instruction.txt 相同（抽 3/3）。故 §4「stage 時逐題對 §2 表複驗」在將要執行
> 的樹上無法通過，且不得以骨架覆蓋完整題樹。任務身分表待 senior 裁決；候選表（對 staged 樹實量）與
> 請求見 `tickets/open/R20261102_1627-1-senior-review-e014-dabstep-block.md` §4。**發射被阻**。
>
> **round 880 修訂註（2026-11-02，依 1627-1 §1.2/§6.1 留痕；原骨架表保留為歷史量值、不刪）**：
> 執行樹 `/srv/eval/staged/dabstep`＝79 題完整樹在位（round 879「消失」＝無 sudo 對 `drwx------ root
> root` 權限拒讀被誤讀為空；round 880 以 `sudo -n` 對源核實在位）。對該樹逐題實量＝**1627-1 §4
> 候選表 26/26 全符**（第 26 題＝**2697**＝`d5c88f12f517e379659aede52106369107993dee2ee53e5d3bb4b5ceae4543ea`；
> 骨架值 `aef9cffd…` 不符）⇒ **canonical 身分表＝1627-1 §4（完整樹，e001 所跑）**；上方骨架表＝
> round 877 對 `/tmp/bm_tasks/dabstep` 的量值記錄。gate 6 於 round 880 通過；e014 於 2026-11-02
> 17:49:32 發射（`7c304639`，78 格）。

**目標格（機制觸發格，e001 對源）**：`10, 1464, 1681, 17, 1753, 19, 22, 23, 2697`
（9 格 `missing_output` kickback；e001 結果：8 雙敗、1 雙過（題 22）；隱藏 scorer 1 pass / 8 fail）。

**臂**（同題、同模型、同 harness、同 cell.py；唯一差異＝Vacant 安裝設定）：

| 臂 | 安裝 | 語義 |
|---|---|---|
| A | 不裝 Vacant | 基線 |
| C | `vacant install --agents pi`（mode=evidence，同 e001/e013 C 臂） | advisory：≤2 回合 kickback，然後放行 |
| CB | `vacant install --agents pi --mode block`（新 mode，§3） | blocking：`missing_output` 未解⇒session 不得結束，直到解或撞 1800s 上限 |

26 題 × 3 臂 × 1 rep ＝ **78 格**。

**模型／harness／量具**：1004 gemma-4-12b-it-qat（共用、A/C/CB 相同）；pi（lab tools 版）；
`/srv/vlab/bin/cell.py`（含 `--system-site-packages` 修復，L001）；PAR=1（labd 串行，e013 先例）；
格逾時 1800s（e007/e013 先例）；`vacant_sha`＝實作 block mode 的 commit（**不得用舊 sha**，e012 先例）——
C 臂＝同一 commit 在 mode=evidence 下的行為（與 e013 的 C 臂設定同形、不同 build；跨 build 只記 pattern、不記 Δ，e007 §4 規則）。

**成本紅線**（預註冊）：CB/A 或 CB/C 的 calls 或 input tokens **>2×** ⇒ 加「不值」
（draft §4／e007 §5.2 紅線）。

## 3. 代碼改動（下一輪實作；**紅燈測試先**——cycle 鐵律：先有失敗測試）

**產品**（`~/dev/Vacant`，`auto/qwen27b`）：

1. `vacant_network/adapters/mode.py`：`MODES` 加 `"block"`；docstring 記語義與 fail-open 邊界。
2. `vacant_network/adapters/cli.py` `cmd_install`：新 `--mode {observe,evidence,block}`
   （預設 None＝保留既有／`setdefault("evidence")` 現行為不動），寫入 `install.json`。
   產品原則 3 符合：這是**使用者真的會輸入的安裝旗標**，非 `VACANT_MODE` 測試變數。
3. `vacant_network/trace/zerostop.py::_decide`：block 分支——
   pushable 中有 `missing_output` ⇒ `action="continue"`（**不受 `ZERO_MAX_ROUNDS=2` 上限**，
   round 計數照記、可審計）；其他 pushable findings（`unsourced`/`unread`/`test_failed`）
   維持 evidence 預算（≤2 回合）；無 pushable ⇒ `allow`。
   **不變式**：check subprocess 任何錯誤⇒仍 `allow`（fail-open：agent 永不被 Vacant 故障鎖住）；
   `off`/`observe`/`evidence` 路徑 byte-identical（no-op 不變式）；pi extension 零改動
   （`stopCheck()` 已處理 `action=continue`→send，e008 dab_039 已實證多回合可行）。
4. 紅燈測試（改動前存在並失敗）：
   - `test_block_mode_holds_session_when_missing_output_unresolved`（evidence 2 回合後 allow；block 仍 continue）
   - `test_block_mode_allows_when_missing_output_resolved`
   - `test_block_mode_other_findings_keep_evidence_budget`（unsourced 在 block 下仍 ≤2 回合）
   - `test_block_mode_fail_open_on_error`
   - `test_install_writes_mode_block` ＋ `test_current_mode_reads_block`
5. **CI 綠是發射門**（e012/e013 先例）；合入後 qwen27b CI 綠才可落 queue。

**lab**（`/srv/vlab/bin/cell.py`）：一行——`arm=="CB"` ⇒ install 參數加 `["--mode","block"]`
（cell.py:125 既有規則「C 開頭＝裝 Vacant」天然涵蓋 CB；其餘臂零改動）。

## 4. 來源

- 題集：`/tmp/bm_tasks/dabstep`（79 題；取 §2 所列 26 題）；發射前 stage 入 `/srv/eval/staged/dabstep`
  （e001/e007 先例：題庫路徑 `/srv/eval/staged/<suite>`；stage 時逐題對 §2 sha 表複驗）。
- 目標格與 e001 機制紀錄：`ops/vlab/runs_e001_pi_AC_baseline/AUDIT_dabstep_mechanism.json`（repo 版，
  e001 §8 警告：`/srv/vlab/runs/e001_pi_AC_baseline/` 同名檔是舊 25 對快照、不可引用）。
- 假說與骨架：`packets/e007_dabench.md` §5.2、`staging/next_cycle_research_packet_draft_r875.md` §3.4/§4、
  `packets/e013_dabench_full.md` §5（分支表格式）/§7（成本邊界）。
- runs 路徑：`/srv/vlab/runs/e014_dabstep_block_pi_ACB/`（78 格）；REPORT 落 `/srv/vlab/done/`。
- `vacant_sha`：實作 commit（TBD，下一輪紅→綠後填入；queue 檔與 C 臂同 sha）。

## 5. 回填（分支表＋方向守衛＋成本疊層）

**主比較：CB vs C**（後果增量）。次比較：CB vs A、C vs A（描述性、低檢定力已聲明）。
**介入紀錄**＝CB 格 Vacant 鏈上有 `action=continue` review event；**hold event**＝round≥3 的
`continue`（只有 block mode 會出現）；**refusal 格**＝格逾時（wall≥1800s）且最後 review event
`action=continue`（session 被 hold 到上限）＝refusal＝**fail、進分母**（refusal 計失敗＝鐵律；
e002 H/M timeout 格進分母先例；非 infra_void——infra 只限 rc=3 模型崩潰，e007 §5 先例）。

| 分支（方向守衛；狀態由方向＋證據定義、非 p 單獨定義，R532 AMEND1 先例） | 觸發條件 | 結論 |
|---|---|---|
| 1 | CB≈C（discordant pairs 各 ≤1、或 ≤2/2 對稱）**＋** 有介入紀錄（≥1 hold event 或 refusal 格） | 「後果在此題集不改變結果」——**H1 被否**（consumption 已測、無效果）；成本在紅線內⇒記「blocking level 在此題集中性」；核心研究問題得一個決定性數據點（consumption 不是效果來源） |
| 2 | CB>C（CB_only>C_only）**＋** 每個 CB_only pair 有因果鏈（CB 格：hold event→finding 解→pass；同題 C 格：left_open 結束或無 hold） | **H-acc-consume 首個正向證據**（限「此題集、此模型、1 rep」，不外推＝H-12 同構） |
| 3 | CB<C（C_only>CB_only）**＋** CB 敗格＝refusal（hold 到上限逾時） | 強制續跑有傷害（預算燒盡、L003/F-7 pattern）；NOT_WORTH／P0 候選（若成 pattern）；blocking 範圍或措辭需重審 |
| 4 | CB 臂無介入紀錄（zero_ran 26/26、無 continue、無 hold） | 機制在此題集未觸發⇒**UNKNOWN**（非 H1 負結果）；先疑量具/環境（e013 分支 4＝L001 教訓先例）；e001 已證此題集會觸發⇒不觸發＝量具問題、P0 |

**成本疊層（任何分支皆適用）**：CB/A 或 CB/C calls 或 input tokens >2× ⇒ 加「不值」。
**鐵律**：p 不顯著≠證明等價；NOT_ESTABLISHED≠無效；UNKNOWN≠負結果；refusal 計失敗；
infra（rc=3）不進分母、不回填；不事後挑數。

## 6. 不做的事

- 不把 DABStep 26 對與 DABench 30 對池化（e001 §6 先例）。
- 不引用 `/srv/eval` 隱藏 scorer 內容解釋任何一格。
- 不為單一格改產品（L004 先例）。
- 本 run 不跑 DABench 負對照（若分支 2 觸發、資源允許，另開新包做——那測的是「效果是否依賴機制觸發」）。
- 不報「證明有/沒有幫助」：報「在此設定、此模型、26 題、1 rep 下看到/沒看到差別」＋代價（e001 §6）。
- **發射門（全部滿足才發射）**：senior 審查通過（draft＋本包）＋產品 CI 綠＋磁碟 free≥4G＋queue 空＋
  `vacant_sha`＝實作 commit（ANCESTOR 有效）＋78 格 queue 檔逐題對 §2 清單。
  **「senior 審查通過」定義（round 876 補充）**：Argon reviewloop 在 `reviews/` 或票上回填「通過／異議」才算；
  **起草方同一側的自批不計**（round 876 實例：工單 R20261102_1505-1 被併發 worker 以「gemma (assistant)」簽名回填「通過」，
  該簽核不滿足本門——見 STATE round 876）。

## 7. 回填欄位（e007 §5 格式）

pass（三臂、配對、McNemar 低力聲明）＋成本（每成功 calls/tokens、C/A 與 CB/A 與 CB/C、逾時/refusal 數、
vacant_home_bytes）＋機制（CB 臂：hold events、round 分佈、refusal 格逐格讀、目標格 9 題逐格讀）＋
分支標籤（1/2/3/4）＋成本疊層＋邊界聲明（H-2、檢定力、1 rep）。
