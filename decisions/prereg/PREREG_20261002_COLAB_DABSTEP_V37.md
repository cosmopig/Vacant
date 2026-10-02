<!-- 狀態：**凍結**（agent 在發射之前 commit；見最下面「授權」）。發射之後這一份與它釘住的東西不准再改；要改＝另一份預註冊。 -->

# 預註冊：DABstep 正式 77 題 × pi＋使用者安裝的零設定 Vacant v3.7（Colab G4、gemma-4-12b QAT）

依據：`decisions/prereg/PREREG_20260926_ZERO_CONFIG_V3_LOCAL.md`（同一組題目、同一個 15 回合設定；當時 v3 對沒裝 51.9%→59.3%、Wilcoxon 精確 p＝0.021，
`decisions/conclusions/CONCLUSION_20260926_ZERO_CONFIG_V3_LOCAL.md`）；`decisions/DECISION_20260926_ZERO_CONFIG_V3.md` §十（v3.6 提醒預設關）、§十一（v3.7）；
`ops/colab_pr82_smoke_20261002/REPORT.md`（v3.7 在 Colab 的機制冒煙）。

## 一、為什麼是這個題組

人類 2026-10-02：「測完整的 3.7，直接在環境內做 pi＋install vacant 這樣的模擬；找一個題組真的完整跑過，題組必須是在過去有效的」。
「pi＋使用者安裝指令（零設定）」這個設定下，過去**唯一**量到顯著差別的就是這 77 題（15 回合上限）。那次的差來自 v3 的回合預算提醒；
v3.6 起提醒預設關 ⇒ 照常安裝的 v3.7 和開了提醒的 v3.7 分成兩組，各自和沒裝比。

## 二、問題

1. **主要**：照常安裝的 v3.7（C37）答對率和沒裝（A）有沒有不同？（雙尾）
2. 次要：開提醒的 v3.7（C37R）和 A、和 C37 有沒有不同？（v3 那次的效果在 v3.7＋提醒上還在不在）

## 三、三組

| 組 | 做什麼 |
|---|---|
| A | pi 0.87.1，Harbor 的 pi agent 做法（`pi --print --mode json …`、自訂端點 models.json、15 回合擴充），沒裝 Vacant |
| C37 | 同上，pi 開跑前在那一格使用者的環境打：`pipx install <wheel> && PI_CODING_AGENT_DIR=/tmp/harbor-pi-agent vacant install` |
| C37R | 同上，但安裝指令是 `vacant install --budget-reminder` |

不設任何 Vacant 環境變數、不寫契約。

## 四、釘住的東西

| 項目 | 值 |
|---|---|
| 題目 | 正式 79 題（`ops/eval/evidence_20260925/pilot/FORMAL_MANIFEST.json`，sha256 `ddf4a962…7319`）。69 題取自 `laude-institute/harbor-datasets@e25eec6e`、10 題由 Harbor `adapters/dabstep`（`harbor@6cb9ff31`）`--split dev` 重新產生；**79 題的 `tests/` tree sha256 全部等於 manifest**（本機 2026-10-02 核過，staging 程式不符就停） |
| 資料 | HuggingFace `adyen/DABstep` `data/context/` 7 個檔，sha256 全部等於 manifest 的 pin |
| 環境 | 沒有 Docker：每格一個新 Linux 使用者＋bwrap（`ops/colab_campaign_20260927/sandbox.sh`），`/app/data/` 放 7 個資料檔、工作目錄 `/app`；python3＝Colab 系統的（pandas 已有，版本記在發射紀錄） |
| 提示 | 題目的 `instruction.md` 原文（Harbor 把它整段當 pi 的提示；`cell.sh` 用 `$(cat)` 讀，結尾換行會被去掉） |
| 回合上限 | 15：Harbor `pi.py@6cb9ff31` 的 `max-turns.ts` 逐字（系統提示加「You have a hard budget of 15 model turns…」、第 15 個 `turn_end` 呼叫 `ctx.abort()`） |
| 每格時限 | 1800 秒（題目 task.toml 的 agent timeout） |
| 計分 | 題目自己的 `tests/test.sh` 逐字執行（只換路徑），`reward==1` 為對；計分使用者另開、圍牆裡跑（`dabstep_score.py`） |
| 模型 | vLLM 0.30.0＋`google/gemma-4-12B-it-qat-w4a16-ct`（model.safetensors sha256 `60b6e398…aa6bfa3`），旗標同 `ops/colab_campaign_20260927/backend/serve_vllm.sh`；思考預設關 |
| Vacant | v3.7：PR #82 分支 `e4da5ebc` 的 `vacant_network/`（與 base `db2c43bb` 逐檔相同），VM 上建 wheel，114 檔與 git 比對；wheel sha256 記在發射紀錄 |
| 工具 | `ops/colab_dabstep_v37_20261002/{cell.sh,stage_dabstep.py,dabstep_score.py,analyze_dabstep.py}`＋`ops/colab_campaign_20260927/` 其餘工具（本 commit 的版本；發射紀錄記每支 sha256） |
| 並行 | 45 個位置（一個單位＝一題一次的三組同時開） |
| 種子 | 20261002（`driver.py`：題目順序與組別順序） |

## 五、跑法、停止、void

- 先跑 1 題 × 3 組的冒煙＋計分器量具（每題把 test.sh 裡的正解寫進 answer.txt 要過；不寫檔要不過），**冒煙不看分數、不進分析**。
- 主跑：第 1 次（79 題×3 組）排完才排第 2 次，最多 3 次。**時間上限＝發射後 3 小時**（過了不開新單位，已開的跑完）；只看時間，不看分數。
- 運算單位護欄：帳號餘額低於 45 CU 就放停止檔（留給其他批次）。收完、本機驗過 sha256 ⇒ 立刻 `colab stop`。
- void：沒有分數（`pass` 為 null）或模型一則回答都沒有。最後照順序補跑一次；補跑也 void ⇒ 那一題那一次的三組都從分析拿掉並列出。C 組裝不上照算（意向治療）。

## 六、分析（`analyze_dabstep.py`，本 commit 的版本；收完跑一次）

- 77 題（去掉 5、70，同前兩批）。完整的次數＝三組 77 題都有分數（或依 void 規則拿掉）。
- **主要檢定（只有一個）**：每題在完整各次的平均答對率，C37 − A，Wilcoxon 符號等級精確雙尾 α＝0.05（差 0 的題去掉）；只有 1 次完整 ⇒ McNemar 精確。
- 次要（Holm，家族 2）：C37R − A、C37R − C37。
- 描述：每組每次答對／沒交答案檔／答錯；Vacant 的動作（交件前檢查、退回類別、提醒、ended 說明）；第一次交件之後被退回、最後答對的格數。

## 七、事先寫死的說法

- 主要顯著、C37 較好：「在這 77 題、Colab 上的 gemma-4-12b QAT、pi 0.87.1、15 回合上限下，照常安裝 v3.7 的答對率較高（p＝…）」；並同時說 15 回合上限是評測設定。
- 主要不顯著：「這一輪沒有量到差別」＋點估計；**不說**「沒有效果」。
- C37R − A 顯著較好：「開了回合預算提醒的 v3.7 在這個設定下答對率較高」，並一定要說提醒預設關、只在系統提示寫了回合上限時作用。
- 任何一組顯著較差：照實寫。
- 不外推到別的模型、別的題庫、沒有上限的使用；不說「Vacant 讓 agent 做得更好」。

## 八、已知的偏差（和 2026-09-26 本機批次比）

1. 模型同一組 QAT 權重但格式與引擎不同（vLLM w4a16 vs LM Studio GGUF）；思考都關。
2. 沒有 Docker：bwrap＋新使用者；python／pandas 是 Colab 的，不是 Harbor 映像（Ubuntu 24.04＋pip pandas）的；網路是通的。
3. 題目、資料、測試逐位元相同（sha256 核過）；提示原文相同；回合擴充逐字相同。
4. 選這個題組是因為它過去有效：題目與 v3 的設計不是獨立的（v3 是看過這批紀錄設計的）。這一份不是留出驗證。

## 授權

人類 2026-10-02（對話原話）：「測完整的3.7直接在環境內做pi + install vacant這樣的模擬 找一個題組真的完整跑過，題組必須是在過去有效的」。
這一份由 agent 在發射前凍結；**人類沒有逐條簽字**——結果只能說「預註冊的 Colab 批次量到／沒量到」。
