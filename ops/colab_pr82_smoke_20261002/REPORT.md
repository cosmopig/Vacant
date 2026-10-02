# PR #82 機制冒煙報告（Colab G4，2026-10-02）

> **冒煙，不是預註冊批次。** 30 格、只跑 C 組、每題 1 次；不做統計，數字只是描述。不宣稱「Vacant 讓 agent 做得更好」。

## 結論：部分可行

- **第一批量到的兩個缺陷，在 PR 分支建的 wheel 上都修好了**（修的是 base 分支的零設定 v3.7，PR #82 沒有動到 `vacant_network/`）：
  1. 跑過 `run_tests.sh` 之後還被判 `test_claim/none`：**0／23 格**（misreject20 裡 18 格＋nodeliver_natural 5 格都跑過；這 20 題在第一批 v3.6.1 下**每一題**都被這樣誤退過）。
  2. `missing_output`：**會觸發了**。forced 5 格裡有 3 格在交件前檢查時 solution.py 確實還沒寫，3 格都被退回、補寫之後才放行；另 2 格 agent 自己寫了檔，沒有退回（正確）。第一批 920 格是 0 次。
  3. 新的誤退：**0**。30 格一共退回 4 次（`missing_output` 3、`failed_step` 1），逐格對病歷都成立。標準提示的 25 格沒有任何退回。
- **PR #82 本身新增的 `native_acceptance_bridge.py` 這一輪沒有測到**：它在 `ops/eval/`、不在 wheel 裡（wheel 內 0 個檔），照常安裝（`vacant install`）不會用到它。要證明 bridge 可行，需要另外用 bridge 包住 pi 的一臂（契約＋收件端持有的可見測試＋`repair`）。
- 另外發現 **1 次漏退**（原本就有的缺口，不是新退化）：`lcb_v1-lcb_3674` 三次 `sh run_tests.sh` 都紅、之後沒再改、說做完 ⇒ 放行。`_failed_steps` 只算跑「自己寫的腳本」或「人在提示裡點名的材料」的失敗，而且要之後又寫過交付物（`vacant_network/trace/evidence.py:836-842`）；題目附的 `run_tests.sh` 不符合。

## 數字（`smoke_summary.json`）

| 組 | 格 | 跑過 run_tests.sh | 跑過後被退 test_claim/none | 有退回的格 | 退回種類 | 交出 solution.py | 隱藏測試通過 |
|---|---|---|---|---|---|---|---|
| misreject20（第一批被誤退過的 LCB 10＋MBPP+ 10） | 20 | 18 | **0** | 0 | — | 20 | 19 |
| nodeliver_natural（第一批沒交、沒逾時的 5 題，提示同第一批） | 5 | 5 | 0 | 0 | — | 5 | 3 |
| nodeliver_forced（同 5 題，提示改成「把程式碼回在訊息裡」） | 5 | 1 | 0 | 3 | missing_output 3、failed_step 1 | 5（3 格是退回之後才補） | 4 |

- 逾時 0、安裝失敗 0、infra_void 0；每格牆鐘 13.7–1338.5 秒。
- 隱藏測試沒過卻放行的 4 格：3 格的可見測試是綠的（Vacant 不判答案對錯，放行正確）；1 格就是上面那次漏退。
- 沒跑 `run_tests.sh` 也被放行的 2 格（`lcb_3722`、`lcb_2817`），最後的訊息都沒有說「測過／通過」⇒ 沒有要查的主張，放行正確。

## 限制

- 每題 1 次、30 格，只能說「機制有沒有動」，不能說頻率。
- nodeliver_natural 這 5 題這次都交了 ⇒ 「自然地沒交件」的情況這輪沒有出現；`missing_output` 只在誘導的 forced 組量到。forced 的提示和人的原句不同，量的是「從人點名的 contract.md 認出交付物」這條路。
- 沒有 A 組對照（只看機制，不比答對率）。
- 模型是 Colab 的 vLLM＋`gemma-4-12B-it-qat-w4a16-ct`，和 1003／1004 的 GGUF 不是逐位元同一個模型。

## 證據

- 原始紀錄：`~/Vacant_colab_raw/pr82_smoke_20261002/p82_raw.tar.xz`（sha256 `389569c34dbbe63bc8b6f721516ad689caa148ed3d89c5890bdf68f674288cb2`；含 EvalPlus 內容，**不進 repo**）。
- wheel：PR 分支 `e4da5ebc`，Linux 上建，sha256 `92ddc44d7bb545b9f3c81d923286a952d3fa23b9d2f3b81d6f530fe9aedfbc1f`，114／114 檔與 git 相同。
- 選題 `selection.json`、計畫 `plan_pr82smoke.json`（sha256 `ab49935b…`）、逐步紀錄 `RUNLOG.md`、讀病歷 `smoke_report.py`。
