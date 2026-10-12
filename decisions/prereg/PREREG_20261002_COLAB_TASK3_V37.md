<!-- 狀態：**凍結**（agent 在發射之前 commit）。發射之後不准再改；要改＝另一份預註冊。 -->

# 預註冊：任務導向三題庫 94 題 × pi＋照常安裝的零設定 Vacant v3.7（Colab G4，兩小時批次）

依據：人類 2026-10-02「找個兩個小時的任務導向的題目去做，兩個小時內要做完的，去比較結果給我」；
同日 `PREREG_20261002_COLAB_DABSTEP_V37.md`（同一套工具、同一個 wheel）與其結論；題庫與量具 `ops/colab_campaign_20260927/PLAN_BATCH2_TASK3.md`、`task3_gauge.json`。

## 一、問題（只有一個）

不設回合上限、一般使用的提示下，照常安裝 v3.7（C37）和沒裝（A）的答對率有沒有不同？（雙尾）

## 二、組、題、跑法

| 項目 | 值 |
|---|---|
| 組 | A（沒裝）／C37（`pipx install <wheel> && PI_CODING_AGENT_DIR=/tmp/harbor-pi-agent vacant install`，不設任何 Vacant 環境變數、不寫契約、提醒預設關） |
| 題 | DABench 30、DataBench 30、Polyglot Python 34（`ops/vacantrun/task_banks_20260927`，分支 `worktree-agent-a60e6be4976f52c82` @ `027a6a16`；`stage_task_bank.py` 打包）；量具在 Mac 上正控制 94／94、負控制 376／376 |
| 提示 | 第一批同一句：`Read goal.md and contract.md in this directory and do what they say. Use your tools to write the file.` |
| agent | pi 0.87.1 `--print --mode json`（Harbor 的跑法）；**不設回合上限**（`MAX_TURNS` 空） |
| 模型 | 同 DABstep 批次（vLLM 0.30.0＋gemma-4-12B-it-qat-w4a16-ct，sha256 `60b6e398…`，思考關） |
| Vacant | 同 DABstep 批次的 wheel（PR #82 `e4da5ebc`，sha256 `92ddc44d…`） |
| 工具 | `ops/colab_dabstep_v37_20261002/cell.sh`（sha256 `d7d0eedf…`，同 DABstep 批次）＋`ops/colab_campaign_20260927/` 其餘；分析 `ops/colab_task3_v37_20261002/analyze_task3.py`（本 commit） |
| 每格時限 | **1200 秒**（第一批 1800；為了兩小時內收完。逾時照算，兩組一樣） |
| 位置 | 48；種子 20261002；計畫 `plan_t3.json`（94 題 × 2 組 × 最多 3 次） |
| 停止 | **發射後約 70 分鐘**不開新單位（時間寫在發射紀錄），已開的跑完；只看時間不看分數。收完 ⇒ 檔案介面確認 ⇒ `colab stop` |

## 三、void 與分析

- void：沒有分數或模型一則回答都沒有；最後補跑一次，補跑也 void ⇒ 那題那次兩組都拿掉並列出。C 組裝不上照算。
- **主要檢定**：每題在完整各次的平均答對率，C37 − A，`research.wilcoxon_signed_rank_exact`（非零差 > 24 題時函式用常態近似）雙尾 α＝0.05；只有 1 次完整 ⇒ McNemar 精確。
- 描述：分題庫的平均、每組每次答對／沒交／答錯、Vacant 的動作（退回幾次、種類、退回後答對幾格）、傷害（退回前已交且對、最後錯）。

## 四、事先寫死的說法

- 顯著、C37 較好：「在這 94 題任務導向題、Colab 上的 gemma-4-12b QAT、pi 0.87.1（`--print`）、不設回合上限下，照常安裝 v3.7 的答對率較高（p＝…）」＋機制拆解。
- 不顯著：「這一輪沒有量到差別」＋點估計；不說「沒有效果」。
- 任何方向都不外推到互動介面（這批是 `--print`）、別的模型。
- 已知：i1001 在 TUI 下的篩選 A 已有 8／10、8／10、7／10（天花板高、檢定力有限）。

## 授權

人類 2026-10-02 對話原話（見第一行依據）。agent 凍結、人類沒有逐條簽字。
