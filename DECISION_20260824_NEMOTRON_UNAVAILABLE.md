# DECISION 2026-08-24 — relay 不提供 nemotron，改用單一模型池（qwen only）

## 發現（量到的，不是猜的）

`g_off60_relay2_20260824`（round 4 啟動）跑到 8/60 成功、**6 筆 infra_void**
時被本輪終止（PID 1771290，SIGTERM，乾淨結束）。

1. **`notes.jsonl` 的 6 筆 infra_void 全部是 404 on nemotron**，且不是單一
   worker（round 4 猜測是 `hasty-2` 專屬）——本輪查到 `careful-2`、`plain-2`
   也一樣 404。三個都失敗，`careful-1`／`plain-1`／`hasty-1`（qwen）沒有一筆錯。
2. **直接查 `curl http://100.119.113.56:8765/v1/models`**：回傳清單只有
   `qwen_qwen3.6-35b-a3b`、`gemma-4-12b-it-qat`、一個 embedding 模型——
   **完全沒有 nemotron**。不是這個節點暫時不認得某種命名，是這個中轉
   現在根本沒有服務 nemotron。
3. **根因鎖定**：`gain_run.py:728-732` 把 `--models` 清單用 `i % len(models)`
   round-robin 分給 6 個 agent（`careful-1/2, plain-1/2, hasty-1/2`）。傳兩個
   模型時，index 為奇數的 agent（所有 `-2` 尾碼）全部分到清單第二個
   model（nemotron）。**這是決定性的、不是隨機的**——只要 nemotron 不可達，
   剛好一半的 agent 保證 100% 失敗，不管跑幾題。

## 決定

**改用單一模型池：`--models qwen/qwen3.6-35b-a3b`（只填一個）。**
`i % len(models)` 在 `len(models)==1` 時所有 agent 都拿到同一個模型，
不會再有「保證失敗的那一半 agent」。

## 這是條件改變，不是修 bug

- 原本三臂設計假設 6-agent 池橫跨兩個模型家族（qwen＋nemotron）。
  改成單一模型後，**OFF 池只剩 qwen 一種模型**，ON／OFF5 若要跟這份
  OFF 對照，也必須用同一個單一模型池（三臂同池是硬條件，SPEC_GAIN 已定）。
- **放棄的是什麼**：「原池（qwen+nemotron 混合）」這個實驗條件，
  不是因為它不值得跑，而是因為 nemotron 現在不可達，跑了就是在量
  「後端故障率」不是「模型能力」。
- **什麼條件下該被推翻**：如果之後 `curl .../v1/models` 重新列出
  nemotron，應該回頭用雙模型池重跑一次 OFF baseline，跟單模型池的
  結果對照，確認 f 有沒有因為換池而系統性偏移。

## 舊 run 的處置

`runs/g_off60_relay2_20260824/`（8/60，6 infra_void，中止於本輪）
**保留不刪**，落盤當「nemotron 不可達」的證據，不當 OFF baseline 使用
（`infra_void` 6 筆已經逼近 `>6` 擋門，且失敗全部是同一根因，繼續跑
只會讓 infra_void 線性累積到 60 題約 26 筆，遠超擋門，沒有量測價值）。

新 run：`runs/g_off60_qwenonly_20260824/`，同一組 seed/n/policy，
只換 `--models` 為單一 qwen。
