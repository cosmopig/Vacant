# DECISION 2026-08-26（round138, Opus 5）：先分析已落盤資料；arm 順序改交錯

## 背景：被叫來做什麼

round136 設下 escalation 條件「infra_void 累積到第 3 筆同型態 ⇒ 換 Opus 判斷」，
round137 觸發並交棒。但開場檢查發現一件更重要的事：

**round126–137 連續 12 輪都是 monitoring checkpoint**，每輪只把
`g_onoff5_371_r123_20260825` 的 rows/calls 數字抄一次就 commit。
12 輪沒有人做過的事：**把已經落盤的資料拿來配對分析**。

---

## 判斷 1：3 筆 infra_void — 不介入，且 round137 的診斷方向是錯的

### 證據（原始，不是轉述）

`notes.jsonl` 三筆全部 `finish_reason=length`，reasoning 18451/23451/24791 字，content 空。
但 round137 寫「三筆都發生在 review 角色」「懷疑 review-timeout-s(250) 偏緊」——
去 `calls.jsonl` 逐筆對，**這個描述不成立**：

```
role= review agent= careful-2 timeout_s= 250 lat_ms= 152705  task= Mbpp/223
role= gen    agent= plain-2   timeout_s= 600 lat_ms= 188243  task= Mbpp/235   ← 不是 review
```

`Mbpp/235` 是 **gen** 角色，`timeout_s=600`，只用了 188 秒。

### 結論

**失敗模式是輸出 token 預算被 reasoning 燒光（`finish_reason=length`），不是逾時。**
沒有一筆的 latency 接近它自己的 timeout（152s/250s、188s/600s）。
⇒ **調 `review_timeout_s` 不可能修好它**，那是錯的旋鈕。
⇒ 本輪**不改任何實驗參數**。3/69 ≈ 4.3%，遠低於 SPEC 的 10% 門檻，
   且 runner 已正確把它們排除在分子與分母之外（`InfraVoid` ⇒ `continue`，不進 rows.jsonl）。

### 什麼條件下該推翻

- infra_void 比率超過 10%（SPEC §絕對門檻）。
- 或出現 latency **貼近** timeout 的 void ⇒ 那才是真的逾時，那時 timeout 才是對的旋鈕。

---

## 判斷 2：`sandbox_check_failed` 留在分母（分母要對）

`gain_run.py:110` — `run_python_check` 正常回傳 False ⇒ `err='sandbox_check_failed'`，
意思是**候選碼真的答錯**。真正的 infra 問題走 `CheckInfraError ⇒ InfraVoid`，
那些列根本不會進 `rows.jsonl`。⇒ 167 個配對格子全部都是「量到的」，分母正確。

---

## 判斷 3：既有資料早就能配對 —— 三條判準全部有了初步答案

`g_off371_20260825`(OFF 367 列) 與 `g_on371_20260825`(ON 167 列)：
`pool` / `instrument` / `calibration` / `request_policy` 四項 sha **逐項相同** ⇒ 可配對。
量具在 371 題全庫雙向滿分：`ref_pass 371/371`、`broken_rejected 371/371`。

新工具 `ops/gain/analyze_paired.py`（McNemar **精確**二項檢定；證據單位是
discordant pair 不是 paired point）。上線前先對手算值驗證，5/5 相符、0 faults。

### A) ON vs OFF（n=167 配對，條件一致）

```
ON    需求=產出  148/167 = 88.62%  CI95 [82.9, 92.6]
OFF   需求=產出  140/167 = 83.83%  CI95 [77.5, 88.6]
discordant：只有 ON 對 b=11，只有 OFF 對 c=3   （證據單位 = 14）
McNemar 精確雙尾 p = 0.0574
每個正確交付的呼叫數  ON=5.64  OFF=1.19
```

方向對（ON 較好 +4.8pp），但 **p=0.057 沒過 0.05**，且 ON 花 5 倍呼叫。

### B) ON vs OFF5（等預算，n=56，`g_onoff5_qwenonly_v3_20260824`）

```
ON    需求=產出  39/56 = 69.64%  CI95 [56.7, 80.1]
OFF5  需求=產出  41/56 = 73.21%  CI95 [60.4, 83.0]
discordant：只有 ON 對 b=4，只有 OFF5 對 c=6   （證據單位 = 10）
McNemar 精確雙尾 p = 0.7539
總呼叫  ON=280  OFF5=280   等預算：True ✓
```

**等預算下 ON 沒有打贏 OFF5**，點估計甚至略輸 3.6pp，p=0.75 ＝ 兩者分不出來。

⚠ 誠實標註：n=56、discordant 只有 10 ⇒ **檢定力很低**，這不是「證明 ON 沒用」，
是「在這個 n 下看不到 ON 的優勢」。兩者不同。另外 v3 run 的絕對通過率
（69/73%）明顯低於 371 run（83/88%），因為它是 n=60 的另一組抽樣，
**不要跨 run 比絕對數字**，只在 run 內配對比。

### 對「有成效」三條判準

1. **量測有訊號**：✓ 但擦邊。OFF 在這 167 題失敗 16.2%（round94 全庫 21.5%），
   落在人類設的 20–60% 窗口的**下緣或略低**。照實記，不美化。
2. **三臂有差異**：△ ON vs OFF 方向明確但 p=0.057；ON vs OFF5 完全分不出來。
3. **等預算的答案**：✓ **有初步答案了——ON 打不贏 OFF5。** 人類明講「打不贏也算有成效」。

---

## 判斷 4：arm 順序要改交錯（本輪**不執行**，寫成規格交棒）

### 這個 run 還要跑多久（12 輪沒有人算過）

```
PID 1875845 已跑 05:06:56，完成 69 列（全部是 ON）
371 題 × 2 臂 = 742 列 ⇒ 267 秒/列
剩 673 列 × 267s ≈ 50 小時   （每輪 20 分鐘 ⇒ 約 150 輪 monitoring）
第一列 OFF5 還要等 302 列 ON ≈ 22 小時
```

### 為什麼順序是設計缺陷

`gain_run.py:836` 是 `for arm in arms:` 外層、`for i, t in enumerate(tasks)` 內層
⇒ **ON 全部 371 題跑完才會碰第一題 OFF5**。後果：
**這個 run 在第 22 小時之前被中斷的話，OFF5 資料是零**，
而 OFF5 正是唯一能回答「等預算誰贏」的臂（判準 3）。
已經有 3 筆 infra_void；50 小時的單點失敗風險不該押在最重要的那條腿上。

### 交錯是「統計上免費」的（已驗證，不是假設）

- `tasks = load_tasks(...)` 在 `gain_run.py:718`，**arm 迴圈之外**建一次 ⇒ 兩臂題序相同。
- `rng = random.Random(f"{seed}:{arm}")` 每臂各一顆；`rep`、`calls` 也是每臂各一份。
- `grep -n "random\." ops/gain/gain_run.py | grep -v rng` ⇒ **空**，沒有共用的全域亂數狀態。

⇒ 每臂的 rng 抽樣序列只取決於「該臂依題序處理的順序」，交錯不改變它。
**交錯後每一格 (arm, task) 的抽樣與現在逐字元相同**，只是執行順序不同。

### 建議（給下一輪執行，要在開場 20 分鐘內定案）

改成 `for task: for arm:`，並加 resume（讀既有 `rows.jsonl` 的 (arm, task_id) 跳過已完成格）。
resume 保住現在這 69 列 ON，不用重跑 5 小時。
之後**任何時刻中斷，都拿得到 k 題的完整配對樣本**。

### 什麼條件下該推翻這個建議

- 若 resume 沒辦法保證「跳過」與「重跑」對 rng 狀態等價（例如 rep 累積順序被改變）
  ⇒ 寧可不要 resume，接受重跑 5 小時，也不要弄出一個 rng 狀態不明的 run。
- 若人類認為 50 小時可以接受、且不在意中途拿不到 OFF5 ⇒ 維持現狀即可。

### 本輪為什麼不動手

改 runner 是實驗進行中的手術，需要植入缺陷測試（證明 resume 真的跳對格子）。
本輪剩餘時間不足以驗證；**未經驗證就改 runner，是把一個慢的實驗換成一個壞的實驗**。
本輪不 kill、不改參數、不動 `ops/gain/gain_run.py`。

---

## 本輪實際做了什麼 / 沒做什麼

做了：新增 `ops/gain/analyze_paired.py`（含手算驗證）、跑出 A/B 兩份配對分析、
       落盤到 `runs/_analysis_r138/`、推翻 round137 的 review-timeout 假說。
沒做：沒 kill 任何 run、沒改 `gain_run.py`、沒改任何實驗參數、沒刪任何 run 目錄。
