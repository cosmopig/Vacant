# e015 候選設計：H-multi-review——真第二 agent 作為獨立裁決者（draft，非預註冊）

> **狀態：設計初稿（round 898，senior 指示 #4「H-multi-review 完善實驗設計與預註冊門檻」）**。
> 本稿不改任何判定、不發射任何實驗、不建任何 cell。正式預註冊＝資深審查本稿通過後
> 落 `packets/e015_*.md`（假說/臂/題組/判準/成本紅線/含方向守衛的狀態表逐條填死）→
> 發射門（六 gate，e014 先例）。底稿＝`staging/next_cycle_research_packet_draft_r875.md`
> §3.3/§4.3（證偽骨架已備、本稿把骨架展開為可執行設計）。
> 口徑繼承：p 不顯著≠證明等價；NOT_ESTABLISHED≠無效；UNKNOWN≠負結果；refusal 計失敗；
> infra_void 不進分母、永不回填；不事後挑數（H-0/AMEND1 先例）；H-12 不外推。

## 0. 為什麼是這個設計（e002/e005/e006 的教訓）

- e002 M 臂（pi）：第二 agent＝`pi -p` 另開一個新 agent、只評不代寫、一層（`arms/e002_M.md`）。
  e006 M 臂（opencode）：M 15/34（介於 C/A 之間）、成本 1.49× calls / **2.02× tokens 超紅線**、
  **H-review(M)＝UNKNOWN**——events.jsonl 無真第二 agent 證據（審查者呼叫在獨立 agent 行程、
  **不在** cell 的 events.jsonl，e006 §3）⇒「機制未量到」，不是負結果。e005 冒煙判準 #4
  （events.jsonl/stderr 有啟動第二 agent 的證據）在 e005/e006 兩度缺失。
- ⇒ 本設計的兩個修正：**①啟動證據由 harness 持有**（wrapper 寫 receipt，不靠 agent 自證）；
  **②先量「裁決能力」再量「交付影響」**（兩側 gauge 先例＝suitegauge：reference 必過＋
  已知壞 stub 必拒；單側 gauge 漏「全收/全拒」）。
- e008 dab_039＝缺失交付樣本（review 本可捕獲）——H-multi-review 的被測對象就是
  「缺失/錯誤 artifact 的被拒率」（底稿 §3.3）。
- **H-1 誠實邊界**：本實驗的「裁決者」是本地模型（gemma-4-12b-it-qat，與產出者同類）——
  Phase 1 量測的正是「模型當 referee 的鑑別力是否優於隨機」；若 Phase 1 被否，即為
  H-1「系統退化成問模型、而那測得不好」的直接實證，屬**結果**、非設計失敗。

## 1. 假說（預註冊時填死）

**H-multi-review**：有**可驗證啟動證據**＋**獨立裁決**的第二 agent（同類本地模型、只評不代寫、
一層），對「缺失/錯誤 artifact」的獨立被拒率**優於隨機**（兩側：壞的能拒、好的能收）；
且（Phase 2、條件性）在真實交付上改「缺失/錯誤 artifact」的被拒率、成本 ≤2×A。

## 2. Phase 1（核心）——裁決者校準實驗（referee calibration）

**被測**：第二 agent 對植入 artifact 集的獨立裁決能力。**不發射 agent 任務循環**——
artifact 全部取自既有完賽 run（e013/e014，官方 scorer 已給 ground truth），harness 直接
啟動 reviewer 逐件裁決。啟動證據因此**結構性可驗**（harness 寫 receipt、不靠 agent 自證），
正面消除 e005/e006 的證據缺口。

### 2.1 被裁決件（植入 artifact 集，預註冊時以 sha256 逐件釘死）

| 側 | 來源 | 數量 |
|---|---|---|
| 已知 **GOOD**（官方 scorer pass） | e013（A 28/C 27 中取）＋e014（A 13/C 14/CB 14 中取）pass 格的 `app_final` 交件 | ≥16 |
| 已知 **BAD**（官方 scorer fail） | e013（A 2/C 3）＋e014（A 13/C 12/CB 12）fail 格的交件（含 missing/invalid_output 樣本，e014 1681/1753 先例） | ≥16 |

- **配對優先**：同題一 good 一 bad（e014 task 17＝A pass/C·CB fail；task 16＝C·CB pass/A fail；
  其餘跨臂配對）——降低題間方差、讓 McNemar 形配對可用。
- ground truth＝官方 `score.json` 的 pass/fail（非本方判斷）；reviewer **看不到**
  `score.json`、看不到 hidden/ 與 scorer（紅線；reviewer 只拿**公開任務描述＋交件檔**）。
- 抽樣固定（seed 預註冊）；不事後換件（H-0 先例）。

### 2.2 啟動與證據（harness 持有）

- wrapper `/srv/vlab/bin/review_run.py`（harness-owned，新增、預註冊前審）：
  1. 輸入＝任務描述（公開）＋artifact 目錄＋固定裁決提示（「只讀、只評、不代寫；
     末行必須為 `VERDICT: ACCEPT` 或 `VERDICT: REJECT`＋一句理由」）；
  2. 以 `pi -p`（或 `opencode run`，預註冊擇一並釘版本）啟動**第二 agent 實例**（同類模型、
     獨立行程）；
  3. 寫 `reviewer_receipt.json`（cell 內、harness 落盤）：
     `{task_id, artifact_sha256, command, argv, model_endpoint, start_ts, end_ts, exit_code,
     stdout_path, stdout_sha256, parsed_verdict ∈ {ACCEPT, REJECT, UNPARSED}}`；
  4. **啟動證據＝receipt 存在＋exit_code 已記錄＋argv 為 wrapper 命令線＋stdout_sha256 吻合**。
     （e005 冒煙判準 #4 的 harness 側強化：證據由寫入方持有，agent 無法「口頭審查」。）
- `parsed_verdict=UNPARSED`（末行格式不合法）⇒該件 **infra_void**、剔分母、不回填、不猜。

### 2.3 判準（兩側 gauge，預註冊 α=0.05）

- **側 1（對 BAD）**：拒率 p̂_reject(bad)；精確二項對 p₀=0.5（期望方向 p>0.5）；Holm 跨配對。
- **側 2（對 GOOD）**：收率 p̂_accept(good)；同法。（單側漏「全收/全拒」——suitegauge 兩側性先例。）
- **力（power）註記**：n=16/側、真值 0.8、兩側 α=0.05（臨界 X≥10 或 X≤6）⇒檢出力≈0.98；
  若真值僅 0.6（n=16）⇒檢出力低——**故狀態表以 p̂ 與 p 雙欄報告、不只看 p**。

### 2.4 狀態表（含方向守衛，R532 AMEND1 先例）

| 狀態 | 條件（全須成立） | 讀法 |
|---|---|---|
| **EFFECTIVE** | 側 1 Holm p<0.05 且 p̂_reject(bad)≥0.8 **且** 側 2 Holm p<0.05 且 p̂_accept(good)≥0.8 | referee 鑑別力優於隨機（兩側）⇒放行 Phase 2 |
| **NOT_BETTER_THAN_RANDOM** | 側 1 Holm p≥0.05（或 p̂_reject(bad)≤0.5） | **H-multi-review 被否**（機制層；Phase 2 不發射） |
| **REVERSED** | 任一侧**反方向**顯著（如 p̂_reject(good) 顯著 >0.5 或 p̂_reject(bad) 顯著 <0.5） | referee 反功能；**被否**（方向明載；不引「多代理有害」因果結論——AMEND1：無方向守衛的顯著反向曾被誤標 EFFECTIVE） |
| **UNKNOWN** | >20% 件缺啟動證據（receipt 缺/UNPARSED） | 機制未量到（e005/e006 先例）＝**非負結果** |

### 2.5 成本

- 每 reviewer 呼叫之 calls/tokens 全數報告（reviewer 在獨立行程⇒**下界**，e006 §3 先例）；
  Phase 1 無 2×A 紅線（無交付臂），但成本數據入 Phase 2 預算。

## 3. Phase 2（條件性——僅 Phase 1＝EFFECTIVE 才發射）——交付影響臂

- **臂**：`A`（對照）vs `M'`（agent 交件前**必須**以 `/srv/vlab/bin/review_run.py` 啟動
  reviewer 並依其意見修正；臂檔明載命令線；receipt 缺⇒該格 UNKNOWN 進分母＝fail，
  refusal 計失敗）。
- **題組**：DABStep 26（e014 先例）或 DABench 30（e013 先例）——預註冊擇一、1 rep。
- **判準**：McNemar（A vs M'，配對）＋Holm；成本 ≤2×A（超⇒記「不划算」，e006 H/M 先例）；
  infra_void 剔分母；狀態表含方向守衛（同 §2.4 形）；**UNKNOWN 條款**（M' 格 receipt 缺⇒
  依 e006 條款記 UNKNOWN、不計臂失敗、報告註記機制訊號——e005/e006 兩度 UNKNOWN 後，
  本臂證據由 harness 持有、條款應顯著收緊：>20% 缺證據⇒整臂 UNKNOWN）。
- **力**：e013/e014 兩端皆噪音內⇒本相仅在 Phase 1 證明 referee 非隨機後才有信息量；
  非 e006 M 臂複測（機制已改：證據 harness 持有＋兩側 gate 前置）。

## 4. 邊界（繼承、不可協商）

- H-1（裁決者＝本地模型、非 exogenous referee；Phase 1 被否即 H-1 的直接實證）；
  H-12（gemma-4-12b-it-qat 本地量化、單 harness、不外推）；
  reviewer 只讀公開描述＋交件、不觸 hidden/scorer（紅線）；
  refusal 計失敗、infra_void 不進分母、不回填；不事後挑數；成本與結果同報（e006 先例）。

## 5. 非本設計（防誤讀）

- 不量「多代理架構普遍更強」——只量「真第二 agent 的獨立裁決」這一個機制軸；
- Phase 1 不量交付改善（那是 Phase 2）；Phase 1 被否＝核心研究問題在
  (a) accountability／(b) harness／(c) multi 三軸中 (c) 的**機制層**被否，
  剩 (a)/(b) 已有 e013/e014/e002/e006 證據（皆噪音內或不優）——核心研究問題即有
  可回填的完整圖景（底稿 §0 問句的 (c) 支路收口）；
- 不改 Vacant 產品行為（wrapper 在 /srv/vlab、實驗機構層；vacant_network 零改動）。

## 6. 待辦（机械步驟，依序）

1. 資深審查本稿（ticket 在案）——通過/異議（附理由）。
2. 通過⇒`packets/e015_*.md` 正式預註冊：§2.1 artifact 集逐件 sha256 釘死、seed 釘死、
   reviewer 命令線與版本釘死、§2.3/§2.4 判準逐字入包、§3 Phase 2 臂與題組擇一填死。
3. 發射門（六 gate，e014 先例）：senior 審查＋CI 綠＋磁碟≥4G＋queue 空＋sha 釘死＋逐題 preflight。
4. 發射→完賽管線（對標 `audits/e014_completion_pipeline.py`）→裁決→回填 FINDINGS＋底稿 §1/§2/§3。

## 7. 參考

底稿 `staging/next_cycle_research_packet_draft_r875.md`（§0/§3.3/§4.3/§6.3）；
`packets/e002.md`（M 臂定義）、`packets/e005_opencode_five_arm_smoke.md`（判準 #4）、
`packets/e006_opencode_polyglot.md`（M=UNKNOWN＋成本下界）、`arms/e002_M.md`（審查者機制）；
`audits/e013_dabench_pi_AC_full.md`、`audits/e014_completion_pipeline.py`（artifact 源＋管線先例）；
suitegauge 兩側性（`vacant_network/suitegauge.py:30-33` 文檔先例）；
`decisions/DECISION_20260917_R532_STRONGER_MODEL_PREREG.md`（AMEND1 方向守衛先例）。
