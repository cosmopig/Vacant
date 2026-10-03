# R536 預註冊（草稿，**待人類簽字才可以發射**）：追緝過的回饋有沒有讓產出更接近需求

> 狀態：**DRAFT**。凍結＝人類簽字＋這一份的 sha256 進 ledger。發射前改任何一個字都要重新簽。
> 上游：`decisions/DECISION_20260924_ACCOUNTABLE_TRACE.md` §五（今晚只有 L-fake，
> 「真模型下產出更接近需求」**必須**由這一份回答）。設計來源：`ops/accountability/design_review_fable.md` Q7。
> 格式照 R535（`decisions/DECISION_20260919_R535_RETRY_CHANNEL_PREREG.md`）：狀態表由上往下求值、
> 方向寫死、收官句逐字。

## 〇、一句話

同一個模型、同一個 agent、同樣最多三次嘗試：下一次嘗試的提示裡放**追緝過的回饋**
（RL：哪個檔哪一行寫了什麼、應該是多少、第一次出現在第幾步），相對於放**今天的泛用回饋**
（RF：主張 id＋驗證器的一句話），`accepted ∧ hidden` 的比例有沒有比較高。

### 主要交付＝三個數字（摘要與收官都照這三個講）

1. RL 與 RF 的 M1 差（pp）與 95% 區間；
2. 收斂曲線：每一臂在第 1／2／3 次嘗試之後還沒過的必要主張數平均；
3. 誘餌題（輸入裡有一個看起來合理的錯數字）與非誘餌題分開的 RL − RF。

### 為什麼不加 n（事前寫死，收官不准回頭改）

n=50 對 +10 pp 的真效果檢定力只有 **0.14–0.18**（§七）；**INCONCLUSIVE 是事前就預期最可能的落點**。
不會在看到資料之後加題。

## 一、出發點

- 論文：驗收閘門是主要增益（+14–19 pp，約 2× token）；回饋**通道**決定模型看不看得到（R535：寫檔 1/46、
  argv +86 pp）。本輪只用已量過有效的通道（argv：`vacant do` 把回饋接在下一次嘗試的提示後面）。
- 追緝（`vacant_network/trace/`）在 L-fake 下 16/16 歸因正確、回饋在 3/4 平台進了模型的下一次請求
  （`ops/accountability/evidence_20260924/`）。**那不是效果**：劇本看到回饋就照演。
- Tyen（模型自己找不到錯，但被告知位置後修得好；筆記06 L503）是 RL 可能贏的理由；
  驗證器的 detail 已經帶了一部分位置資訊（`report says X, recomputed Y`）是 RL ≈ RF 的理由。

## 二、要跑什麼

### 二-1 題庫：L1 一般任務（n=50），**確認性只有這一層**

`python ops/accountability/r536/bank.py --out <dir> --n 50 --seed 536`（確定性；`MANIFEST.json` 的
sha256 發射前凍結）。每題：12–20 列的帳本、任務＝寫出總數與最大區域；**偶數題**無誘餌、**奇數題**多一份
`inputs/notes.txt`（上週的初步總數＝真總數 ±7–15%）。可見驗收：`total`（csv_total，fact）、
`top_line`（有那一行）。**隱藏檢查**（agent 永遠看不到、不進任何回饋）：最大區域的名字對不對。

L2（程式任務）**本輪不跑**：要沿用 R535 的題庫得先做契約轉換，屬於另一份預註冊。

### 二-2 三臂（只差一個旗標）

| 臂 | `vacant do --feedback-mode` | 下一次嘗試的提示 |
|---|---|---|
| RS | `none` | 原提示；**乾淨的工作區**（重抽） |
| RF | `generic` | 原提示＋今天的泛用回饋 |
| RL | `localized` | 原提示＋追緝過的回饋（`feedback_ks1_clean` 保證沒有行動者、沒有責任字眼） |

三臂都：`--attempts 3`；契約 `hooks.stop_check=false`（工作階段裡不回饋，差別只在下一次嘗試的提示）；
追緝的病歷三臂都記（RS 也記，但不給模型看）。

### 二-3 逐字指令

```
python ops/accountability/r536/run.py --bank <bank> --agent <pi|claude|codex|opencode> \
    --out <rows.jsonl> --arms RS,RF,RL --timeout 900
python ops/accountability/r536/analyze.py <rows.jsonl> --layer L1
```

agent 用執行者自己 HOME 裡的設定連模型（團隊本機的 12B；型號、後端版本、推論模式發射前寫進
§二-4 並凍結）。harness 不碰模型端點、不帶金鑰。

### 二-4 發射前要填、填完凍結

- 模型（含量化）＝＿＿＿；後端＝＿＿＿；推論模式＝＿＿＿（R535 §二-6：推論模式會改變工具使用形狀）
- agent 與版本＝＿＿＿；`vacant` commit＝＿＿＿；題庫 `MANIFEST.json` sha256＝＿＿＿

### 二-5 可驗的不變量（發射後逐格對帳）

- 每個 (題, 臂) 恰好一列；`infra_void` 有原因。
- RF／RL 的第 2、3 次嘗試提示裡**真的有**回饋文字（`--mock` 冒煙已驗；真跑抽 5 格人工對）。
- RL 的回饋文字裡沒有行動者識別（`feedback_ks1_clean` 會擋；抽查）。

## 三、指標

- **M1（主要）**＝`accepted ∧ hidden_pass`（reject 記 0）。理由同 R535 §三：只看 accepted 會把
  「對著可見驗收改」算成進步。
- 次要（描述）：accepted、hidden_pass、收斂曲線、每臂牆鐘時間、第 1 次嘗試的失敗率。
- token：各 agent 的輸出格式不一，本輪**不當判準**；後端有記錄就附表。

## 四、事前預測（在看到任何資料之前寫死）

- L1 全部：RL − RF ∈ [0, +10] pp（點估計），**狀態 INCONCLUSIVE**。
- 誘餌題：RL − RF ≥ +10 pp（RL 的回饋會指出「同一個值在 inputs/notes.txt 第 2 行」與應有的值；
  RF 只說「report says X, recomputed Y」——**兩者都給了正確值**，差別在來源與位置）。
- 非誘餌題：RL − RF ≈ 0。
- RL、RF 都 > RS（回饋帶正確值；R535 的方向）。
- 若 RL ≈ RF 全面成立：**這也是結果**——位置與來源對收斂沒有額外價值，追緝的價值只在給人的報告
  （問題被提出來、指到那一步），不在收斂。收官照實寫，不叫失敗。

## 五、統計

- 確認性檢定**只有一個**：L1 上 RL vs RF 的 M1，McNemar 精確雙尾（`research.mcnemar_exact`），
  α=0.05。只有一層 ⇒ Holm 家族大小 1。
- 方向寫死成定義式（`analyze.paired(rows, "RF", "RL")`）：`b`＝RF 失敗 ∧ RL 通過（RL 贏）、
  `c`＝RF 通過 ∧ RL 失敗。
- 區間：配對差 (b−c)/n 的 95% Wald 區間（只用來判 RULED_OUT 的上緣）。
- 次要（RL vs RS、RF vs RS、誘餌／非誘餌分層）一律描述，不進狀態。

## 六、狀態表（照抄，由上往下，第一個成立的就是狀態）

| # | 狀態 | 判準 | 方向護欄 |
|---|---|---|---|
| 1 | `INVALID` | `infra_void` > 10% | 觸發 ⇒ 任何數字都不得引用 |
| 2 | `NOT_TRIGGERED` | 三臂合併的第 1 次嘗試失敗率 < 0.6 | 單邊（題目太容易，回饋沒有機會起作用） |
| 3 | `CONFIRMED_POSITIVE` | p < 0.05 **且 b > c** | 只有 RL 贏才算 |
| 4 | `CONFIRMED_NEGATIVE` | p < 0.05 **且 c > b** | RL 輸而顯著 ⇒ 在地化回饋反而更差，是真的結論 |
| 5 | `RULED_OUT` | 不顯著 **且** 95% 上緣 < +15 pp | 單邊（上緣） |
| 6 | `INCONCLUSIVE` | 以上皆非 | **預設落點，不是失敗** |

### 收官句（逐字）

- `CONFIRMED_POSITIVE`：「在 L1（n=<n>）上，把追緝過的回饋接進下一次嘗試，相對於泛用回饋，
  `accepted ∧ hidden` 高 <Δ> pp（95% 區間 <lo>–<hi>；b=<b>, c=<c>, p=<p>）。
  **這是對 <模型>＋<agent>＋本題庫的結論，不可外推。**」
- `INCONCLUSIVE`：「在 L1（n=<n>）上，本輪沒有區分開追緝過的回饋與泛用回饋（點估計 <Δ> pp，
  95% 區間 <lo>–<hi>，p=<p>）。依 §七，本輪對 +10 pp 的檢定力只有 <power>，
  **『沒顯著』不可以讀成『沒有效果』。**」
- `RULED_OUT`：「RL − RF 的 95% 上緣 <hi> pp < +15 pp ⇒ ±15 pp 內未區分開。」（禁語：「等價」。）

## 七、檢定力（`research.mcnemar_power`，n=50，α=0.05）

| 不一致比例 | 真效果 | ψ | 檢定力 |
|---|---|---|---|
| 0.3 | +10 pp | 0.667 | 0.179 |
| 0.4 | +10 pp | 0.625 | 0.143 |
| 0.3 | +20 pp | 0.833 | 0.699 |
| 0.4 | +20 pp | 0.750 | 0.547 |
| 0.4 | +30 pp | 0.875 | 0.939 |

## 八、作廢與停止

- 發射後改碼（`vacant_network/`、`ops/accountability/r536/`）⇒ 整輪作廢重來。
- 模型端點掛掉、agent 崩潰 ⇒ 那一格 `infra_void`，三臂一起剔除；> 10% ⇒ `INVALID`。
- 不得與別輪併 n；不得事後改 M1 的定義；不得只報有利的分層。

## 九、誠實邊界（收官照抄）

1. 一個模型、一個 agent、一個題庫：**不可外推**到別的模型、別的平台、別種任務。
2. 回饋都帶了正確值（RF 的 detail 也有）；本輪量的是「位置＋來源＋步驟」**加上去**的價值，
   不是「有沒有回饋」。
3. `--mock` 冒煙（L-fake）只證明管線；任何效果數字都不能從它來。
