# Vacant (`feat/universal-coding-and-retention`) — 後續模型接手任務清單 (Agent Handoff Spec)

本文件為交接給後續 AI 模型／開發者的**具體可執行任務規格書（Actionable Task Spec）**。每個 Task 均附帶：精確檔案路徑、行號、問題根因、實作規格、以及不可作弊的驗證指令（Acceptance Gate）。

---

## 0. 環境與基準資訊（必讀）

- **工作目錄（Repo Root）**：`/home/user1/.gemini/antigravity-cli/scratch/Vacant`
- **目前分支**：`feat/universal-coding-and-retention`（最新 commit：`9189fd4`）
- **對照組基準（`main v0.9.1`）**：`/tmp/vacant_main`
- **測試用 Python Venv**：`/home/user1/.gemini/antigravity-cli/scratch/.venv/bin/pytest`
- **本地測試模型端點**：`http://100.119.113.56:1234`（模型：`gemma-4-12b-it-qat`）
- **2,111 格真實歷史軌跡庫**：`/srv/eval/archive`（唯讀，含 1,073 格 `C37` 與 1,038 格 `A` 組）
- **既有離線重播與實機測試腳本**：
  - `/home/user1/.gemini/antigravity-cli/brain/a0a1d0ed-e6be-4132-a6e6-542486531237/scratch/eval_c37_archive.py`
  - `/home/user1/.gemini/antigravity-cli/brain/a0a1d0ed-e6be-4132-a6e6-542486531237/scratch/eval_a_archive.py`
  - `/home/user1/.gemini/antigravity-cli/brain/a0a1d0ed-e6be-4132-a6e6-542486531237/scratch/live_unrigged_ab_test.py`

> **最高工程鐵律（不可違反）**：
> 1. **禁止誘導式／作弊測試**：絕不可在 Prompt 寫「先故意犯錯再修正」。所有評估必須跑在 `/srv/eval/archive` 離線重播或 `/srv/eval/staged` 原始題目上。
> 2. **零新增誤退原則（Zero New False Positives）**：任何對 `evidence.py` 的修改，重跑 2,111 格真實軌跡後，`Blocked PASS`（誤退答對格）數量**嚴禁上升**（目前 `C37 Final` 為 `4` 格、`A` 為 `1` 格）。

---

## Task 1：消滅 2,111 格真實軌跡中最後殘留的 5 格 `main` 歷史誤退（Target: `4 -> 0` in C37 Final, `1 -> 0` in A）

### 1.1 背景與精確案例
在 `commit 9189fd4` 修掉我們自己的誤退與 `main` 的 6 格 `#` 註解誤退後，2,111 格真實軌跡在最終停下（Final Stop）時，還殘留 **5 格從 `main (v0.9.1)` 繼承下來的真實誤退**：
1. **C37 的 4 格 `unsourced` 誤退**：
   - `t3L-C37-dabench-dab_055-s3` 與 `t3U-C37-dabench-dab_055-s3`：`answer.txt` 寫 `2081990`，但 stdout 印出的是浮點數 `2081990.0` 或千分位 `2,081,990`，被判 `unsourced`。
   - `t3L-C37-dabench-dab_129-s1` 與 `t3L-C37-dabench-dab_129-s3`：`answer.txt` 寫百分比 `49.67`，但 stdout 印出的是比例 `0.49666...`（相差 `100x` 的百分比轉換）或未四捨五入原值，被判 `unsourced`。
2. **A 組唯一的 1 格 `failed_step` 誤退**：
   - `t3L-A-polyglot_py-pg_pig_latin-s3`：Step 18 執行 `sed -i 's/([^]*?)/([^a-zA-Z0-9]*?)/g' pig_latin.py` 失敗（exit 1），但隨後 Agent 直接用 `write` 工具重寫了 `pig_latin.py` 並跑過 `pytest`。目前 `_failed_steps` 只檢查「後續是否有成功的 bash 指令讀取該檔」，沒檢查「該目標檔隨後是否已被 `write`/`edit` 工具覆寫並通過測試」。

### 1.2 修改檔案與實作步驟
- **檔案**：`vacant_network/trace/evidence.py`
  1. **百分比（`×100`）與整數浮點（`.0`）同源匹配**：
     - 定位 `_num_in_pool(val_str, pool_nums, pool_text)`（約第 60–95 行）。
     - 當 `val_str` 解析為浮點數 `v`（且 `0 < abs(v) <= 100`）在 `pool_nums` 找不到直接四捨五入匹配時，檢查 `v / 100.0` 是否在 `pool_nums` 中存在精確的四捨五入匹配（例如 `pool_nums` 有 `0.49668`，`round(0.49668 * 100, 2) == 49.67`）。
     - 當 `val_str` 為整數（如 `2081990`）時，檢查 `pool_nums` 是否有 `abs(p - v) < 1e-6` 或四捨五入至整數相等的數值。
  2. **`sed -i` / 失敗指令修改目標檔已被後續 `write` 覆寫的豁免**：
     - 定位 `_failed_steps(self)`（約第 255–345 行）。
     - 若失敗的 shell step 操作的是某個交付檔 `d`（出現在 `cmd` 中），且在 `step > s["step"]` 之後，Agent 有對 `d` 執行成功的 `write`/`edit`（`w["step"] > s["step"]`），且最後一次測試通過（或後續無失敗），則豁免該次失敗的 `sed` / shell step。

### 1.3 驗收標準（Acceptance Gate）
```bash
# 1. 跑單元測試
/home/user1/.gemini/antigravity-cli/scratch/.venv/bin/pytest -q tests/test_retention.py tests/test_universal_and_coding_upgrades.py tests/test_trace*.py

# 2. 跑 2,111 格離線重播，確認：
#    - C37 Final Stop 的 Blocked PASS 由 4 降為 0
#    - A 組的 Blocked PASS 由 1 降為 0
#    - Blocked FAIL（抓錯數）不減少（C37 Stop#1 >= 133, A non-timeout >= 201）
python3 /home/user1/.gemini/antigravity-cli/brain/a0a1d0ed-e6be-4132-a6e6-542486531237/scratch/eval_c37_archive.py /home/user1/.gemini/antigravity-cli/scratch/Vacant /tmp/c37_task1.json
python3 /home/user1/.gemini/antigravity-cli/brain/a0a1d0ed-e6be-4132-a6e6-542486531237/scratch/eval_a_archive.py /home/user1/.gemini/antigravity-cli/scratch/Vacant /tmp/a_task1.json
```

---

## Task 2：針對 Coding 任務提升「攔截後救援率（Conversion Rate）」— 精準摘錄測試失敗 Assertion

### 2.1 背景與問題根因
在 P2 實機測試中，我們發現新版 `evidence.py` 在 C37 與 A 組各多抓了 **22 格 Polyglot Python 測試失敗（`failed_step: test_failed`）**，但當 `zerostop` 攔下並把回饋送給 `gemma-4-12b-it-qat` 時，目前的訊息只有：
> `Step 14 (\`python3 -m unittest ...\`) exited with Command exited with code 1; the implementation still fails its test suite. Fix the code and re-run the test command until it passes.`

為什麼這不夠？因為當對話已經累積 20~30 回合時，較小模型（如 12B）常忘記最後一次 `unittest`/`pytest` 到底是哪個 test case 報錯，或是因為已經陷入重複修改迴圈，只看到 `Command exited with code 1` 不知道該修哪個函式分支。

### 2.2 修改檔案與實作步驟
- **檔案 1**：`vacant_network/trace/evidence.py`
  - 在 `_failed_steps(self)` 建立 `sub == "test_failed"` finding 時，從該 step 的 `stdout` / `error` 中提取**最後一個失敗斷言或錯誤摘要**（最多 160 字元，例如 `FAIL: test_verse_0 ... AssertionError: ... != ...` 或 `E   AssertionError: ...`），存入 finding 的 `"test_hint"` 欄位。
  - **注意 KS1 鐵律**：`test_hint` 只能提取 step 自己印出的 stdout/stderr 原文片段（且排除路徑雜訊），不得洩漏任何外部隱藏資訊。
- **檔案 2**：`vacant_network/trace/review.py`
  - 在 `failed_step`（`sub == "test_failed"`）組裝回饋訊息時，若 `f.get("test_hint")` 存在，將其附在回饋句尾（例如：`Last failure output: <test_hint>`），並確保通過 `tests/test_trace_props.py` 的 `feedback_ks1_clean` 檢查。

### 2.3 驗收標準（Acceptance Gate）
1. `tests/test_trace_props.py`（含 `feedback_ks1_clean` 隨機模糊測試）100% 通過。
2. 執行 `/home/user1/.gemini/antigravity-cli/brain/a0a1d0ed-e6be-4132-a6e6-542486531237/scratch/live_unrigged_ab_test.py` 測試 `py_beer-song`、`py_bottle-song`、`py_wordy` 等格，對比加了 `test_hint` 前後的通過測資數與最終 `scorer.py` 通過率。

---

## Task 3：為通用資料任務（DABstep / DABench / DataBench）導入自動輕量合約推導（Auto-Inferred Intake Contract）

### 3.1 背景與問題根因
我們在 P2 實證中看到：**Zero-Config 只能抓表面格式與執行錯，無法驗證資料合理性**（例如 `dabstep-1753` 修好了格式但選出來的 ID 是錯的；或是某些題目要求輸出「介於 0 到 1 的相關係數」、「非負整數筆數」、「特定欄位名稱」，模型卻輸出了負數或空陣列 `[]`）。
同時，我們已經在 `vacant_network/intake/verifiers.py` 實作了 `syntax_valid` 與 `answer_format`，但只有在專案有 `.vacant/contract.json` 時才會觸發。

### 3.2 修改檔案與實作步驟
- **檔案 1**：`vacant_network/trace/evidence.py`（`_invalid_outputs` 的 `contract_shape` 擴充）
  - 在不增加誤退的前提下，從 `goal_text` 提取明確的數值／結構約束：
    1. **空集合交付攔截**：若交付檔 `answer.txt` 內容為空的 JSON list/dict（`[]`, `{}`, `[""]`），而 `goal_text` 詢問的是 `Which ...` / `List the ...` / `What are the ...`（且 stdout 中明明有非空輸出），標記為 `invalid_output (sub="empty", detail="empty collection []")`。
    2. **未解析的 Python 物件字串攔截**：若 `answer.txt` 出現 `<function `, `<generator object`, `DataFrame`, `Series([],` 等 Python `repr()` 殘留字串，標記為 `invalid_output (sub="stub")`。
- **檔案 2**：`vacant_network/intake/verifiers.py`
  - 為 `answer_format` verifier 增加 `forbid_empty_collection: bool = True` 與 `numeric_range: [min, max]` 參數支援，讓使用者在定義 `.vacant/contract.json` 時能直接約束數值範圍（例如機率題 `[0.0, 1.0]`、相關係數 `[-1.0, 1.0]`）。

### 3.3 驗收標準（Acceptance Gate）
1. 在 `tests/test_universal_and_coding_upgrades.py` 新增對應單元測試並全數通過。
2. 跑 2,111 格離線重播（`eval_c37_archive.py` 與 `eval_a_archive.py`），確認 **0 新增誤退**，並記錄多攔截到的真實失敗格清單。

---

## Task 4：將 `retention.py` (`vacant gc`) 深度整合至评测框架與 CLI 預設工作流

### 4.1 背景與目標
`vacant_network/runtime/retention.py` 已在 60 個真實 `C37` 歷史目錄上驗證可省下 **64.1% ~ 85%+** 磁碟空間，且 `Recorder.verify()` 與 `Evidence.run()` 100% 零損壞。下一步是讓長期跑 benchmark 或生產環境的使用者無需手動介入即可受惠。

### 4.2 修改檔案與實作步驟
1. **檔案**：`vacant_network/runtime/retention.py` 與 `vacant_network/cli.py`
   - 在 `vacant gc` 新增 `--verify` 旗標：執行清理後自動對所有保留的 session 呼叫 `Recorder.verify()`，並在 JSON 輸出中回報 `"verified_sessions": N, "verify_ok": True`，讓使用者對磁碟清理具備 100% 信心。
   - 新增 `--older-than-hours <float>` 過濾器：允許只壓縮／清理超過指定小時數的舊 session 與舊 task，避免干擾正在並行執行的其他 session。
2. **檔案**：`tests/test_retention.py`
   - 新增 `--verify` 與 `--older-than-hours` 的端到端測試。

### 4.3 驗收標準（Acceptance Gate）
```bash
/home/user1/.gemini/antigravity-cli/scratch/.venv/bin/pytest -q tests/test_retention.py
```

---

## Task 5：端到端小規模實機 A/B Benchmark（`r535_bank` / `staged` 抽樣三方對決）

### 5.1 執行步驟
當上述 Task 1 ~ Task 4 完成後，使用本地模型 `http://100.119.113.56:1234`（`gemma-4-12b-it-qat`）執行一場無作弊的 3 組對照實測（每組 15~20 題）：
- **組別 A（Solo）**：不掛載 Vacant。
- **組別 M（Main `v0.9.1`）**：掛載 `/tmp/vacant_main`。
- **組別 N（New Branch）**：掛載 `/home/user1/.gemini/antigravity-cli/scratch/Vacant`。
- **輸出指標**：
  1. 官方 `scorer.py` 通過率（Pass Rate）
  2. 攔截率（Block Rate）與誤退率（False Positive Rate）
  3. 攔截後救援成功率（Fail -> Pass Conversion Rate）
  4. 開啟 `VACANT_AUTO_GC=1` 後的最終磁碟佔用（MB）對比
