# PR #82 機制冒煙（Colab G4，2026-10-02）— RUNLOG

> **這是冒煙，不是預註冊批次。** 只看機制（病歷裡的退回種類），不做統計、不宣稱效果。
> 時間一律 UTC。做法照 skill `colab-vacant-campaign`、工具沿用 `feat/colab-campaign-20260927` 的 `ops/colab_campaign_20260927/`。
> 沒有讀 `u274/raw/`。

## 要回答的事（人類 2026-10-02 的指示）

1. 跑過 `sh run_tests.sh` 之後還被判 `test_claim/none` 的格數——應該接近 0（第一批 v3.6.1：293 格）。
2. `missing_output` 有沒有觸發（第一批：0 次）。
3. 有沒有新的誤退。

## PR #82 讀後（三句話）

- 它**修的**是「零設定只在查紀錄一致性、沒有可執行驗收＋重來」這件事：新增 `ops/eval/native_acceptance_bridge.py`（任務前釘契約與收件端持有的可見測試，交件時同步凍結＋驗證、`gate`／`repair`／`conform`），**不改 `evidence.py`**。
- 第一批的兩個缺陷（不認 `sh run_tests.sh` 而誤退 `test_claim/none`；短提示下 `missing_output` 從沒觸發）是 **base 分支的零設定 v3.7** 修的（`09e3436c`／`2811267f`／`122a424c`：認任意測試腳本、從人點名的說明檔認交付物），PR #82 只是建在它上面；PR 分支的 `vacant_network/` 與 base `db2c43bb` **逐檔相同**（`git diff e4da5ebc db2c43bb -- vacant_network pyproject.toml` 為空）。
- 「可行」＝用使用者會打的安裝指令（`pipx install <wheel> && vacant install`）裝 PR 分支建的 wheel 後：跑過 `run_tests.sh` 的格子不再被退 `test_claim/none`、不交件時 `missing_output` 會觸發、而且沒有冒出新的誤退。⚠ bridge 本身**不在 wheel 裡**（`ops/eval/`，wheel 內 `native_acceptance` 0 個檔），零設定安裝不會用到它；這輪冒煙**測不到 bridge**。

## 選題（不看分數，只用第一批病歷）

- `selection.json`（種子 20261002）：
  - **misreject20**：第一批 C361 跑過 `run_tests.sh` 仍被退 `test_claim/none` 的題，LCB（v1/v2/v3 合併）抽 10、MBPP+ 抽 10。
  - **nodeliver_natural 5**：第一批 `no_solution` 且沒逾時（不論組別）的 LCB／MBPP+ 題，抽 5（剛好全是 LCB），提示與第一批相同。
  - **nodeliver_forced 5**：同那 5 題，提示換成 `Read goal.md and contract.md in this directory. Reply with the complete solution code in your final message.`
    ——引導 agent 不寫檔；`contract.md`（人點名的說明檔）要求 `solution.py`。這 5 格是**誘發**，用來看 v3.7 能不能從說明檔認出交付物。
- 只跑 C 組（`C37`），每題 1 次，共 30 格。

## 逐步紀錄

- 01:50 開工；skill 寫進 `~/.claude/skills/colab-vacant-campaign/SKILL.md`。
- 01:52 `colab new -s c5v37 --gpu G4`（READY）；本機掛 03:25Z 一律 `colab stop` 的保險。
- 01:54 VM：vLLM 0.30.0 獨立 venv＋`google/gemma-4-12B-it-qat-w4a16-ct`（model.safetensors sha256 `60b6e398…`），`serve_vllm.sh` 同第一批（FLASHINFER 採樣器關、prompt-tokens-details 開、只聽 127.0.0.1）。
- 01:57 deploy：wheel 由 PR 分支 `e4da5ebc` 的 `git archive`（pyproject.toml、README.md、LICENSE、vacant_network）在 VM 上建（uv 0.8.17、setuptools 84.0.0、`SOURCE_DATE_EPOCH=1790873779`＝e4da5ebc 的 commit 時間）
  ⇒ `vacant_network-0.8.0-py3-none-any.whl` sha256 `92ddc44d7bb545b9f3c81d923286a952d3fa23b9d2f3b81d6f530fe9aedfbc1f`；114／114 檔與 git 原檔相同。圍牆負控制 OK、ensurepip OK、代理在 127.0.0.1:18900。
- 01:59:08 發射 `p82`（`launch_batch.sh p82 plan_pr82smoke.json 30 2026-10-02T03:00:00Z SMOKE_NOT_PREREGISTERED`）；plan sha256 `ab49935b…`（VM 上）。AGENT_TIMEOUT 1800 秒同第一批。
- 02:00 前 3 格完成：C 裝上且有作用、都走到交件前檢查（`stop_reached`）。
