# R484 預註冊：主 run 變慢的歸因——client-side CPU 爭用 vs server-bound

run 名（R440G 閘門用）：本文件**不發射任何 run**。分析對象是既有的
`runs/g_r461_lcb3_three_arm`（PID 2895311，仍在跑）。**唯讀，零 API 呼叫。**

日期：2026-09-05 UTC 03:5x（round755，Opus 5）

## 一、為什麼問這個

round752／753／754 連續三輪把主 run 的速率下滑歸因為「本輪的 census 子行程跟它搶 CPU」：

- r752 交棒記 1.8 分／列
- r753 交棒記 4.1 分／列，並寫「因為本輪的 census 跟它搶 CPU」
- r754 交棒記 ≈75 分／列，並寫「**CPU 是共用的**，跑 26 分鐘的子行程 census 的代價比前兩輪估的大一個量級」，
  據此給出決策規則：「下一輪要嘛別跑重的東西、要嘛接受它幾乎不動」

**這三輪都沒有量過這個歸因。** 而它在機制上可疑：`gain_run.py` 的工作是對
`http://100.119.113.56:8765`（**另一台機器**）發 HTTP 請求並等回應，等待期間耗用的本機 CPU ≈ 0。
本輪開場實測 `ps` 顯示 `gain_run.py` 的 `%CPU = 0.0`、`loadavg = 0.22`。

**這條歸因是三輪的行動依據**（決定「這輪能不能做重的事」），所以它值得被量一次。
memory 的通則：**第一個歸因常是錯的**。

## 二、兩個對立假說

- **H_CPU**：列速率受限於本機 CPU 爭用。census 之類的子行程拖慢 runner **發出**請求的能力。
- **H_SERVER**：列速率受限於遠端推理端點（生成速度／排隊）。本機 CPU 工作對它幾乎沒有影響。

**鑑別的關鍵**：CPU 爭用拖慢的是「不在請求中的時間」，不會改變伺服器端生成速度；
端點退化拖慢的是「請求中的時間」。這兩者在 `calls.jsonl` 裡是分得開的兩個量。

## 三、量什麼（全部出自已落盤的 `calls.jsonl`，不新增任何呼叫）

每筆呼叫有 `ts_ms`、`latency_ms`、`usage.completion_tokens`、`ok`。

⚠ **`ts_ms` 是起始還是結束時刻，不准用記憶認定**（memory 記的是「呼叫結束時刻」，
但那是對別的 run 的觀察）。**兩種假設都算 idle gap、取「負值個數為 0」那個**；
兩個都有負值 ⇒ 記 `TS_SEMANTICS_UNRESOLVED`，本輪 P-0 判 UNRESOLVED（不准挑一個順眼的）。

- `busy_ms` ＝ Σ `latency_ms`（在請求中的時間）
- `wall_ms` ＝ 最後一筆 − 第一筆的時距
- `idle_ms` ＝ `wall_ms` − `busy_ms`（不在請求中的時間）
- `ms_per_tok` ＝ `latency_ms / completion_tokens`（**端點退化看吞吐不看延遲**，memory 通則）

**具名排除**：`completion_tokens == 0` 或缺 `usage` 的筆數不算進 `ms_per_tok`，
但**要印出被排除的筆數**（不准安靜丟）。`ok == False` 的筆數單獨印。

## 四、判準（落筆於量測之前）

**P-0（主判準，承重）**：`busy_ms / wall_ms`。
- ≥ 0.70 ⇒ **`SERVER_BOUND`**：run 的時間絕大多數花在等伺服器 ⇒ H_CPU 對總時間的解釋力上限只有 (1−比值) ⇒
  **r754 的「CPU 是共用的」歸因被推翻**。
- ≤ 0.30 ⇒ **`CLIENT_GAP_BOUND`**：時間花在請求之外 ⇒ 與 H_CPU 相容（但**不等於證明是 CPU**，
  見第六節：runner 自己的本地評分／檢查式執行也落在這段時間裡）。
- 之間 ⇒ **`MIXED`**，照實寫兩個數字，不准四捨五入成某一邊。

**P-1（端點退化的獨立檢查）**：把整段 run 依真實時鐘切成 1 小時桶，算每桶 `ms_per_tok` 中位數。
- 最後兩桶的中位數 ≥ 最初兩桶的 **1.5 倍** ⇒ `ENDPOINT_DEGRADING`（且與 census 無關，因為 census 只佔最後 ~1 小時的一部分）。
- < 1.5 倍 ⇒ `ENDPOINT_FLAT`。
- **基準率防呆**：任一桶筆數 < 10 ⇒ 該桶標 `THIN`、不參與比較，並具名列出；
  可用桶 < 4 個 ⇒ P-1 判 `UNSCANNED`（不是 `ENDPOINT_FLAT`）。

**P-2（r483 census 視窗的直接對照）**：視窗 ＝ `[artifact_mtime − 1580.9s, artifact_mtime]`
（`ops/gain/data/r483_worktree_census.json`，elapsed 出自 r754 交棒紀錄）。
- 視窗內筆數 **< 10 ⇒ 判 `UNSCANNED`，不准解讀成「沒有影響」**（memory：安靜量不到第三型）。
- 筆數足夠時比視窗內外的 `ms_per_tok` 中位數：差異 < 25% ⇒ 伺服器端生成速度不受本機 CPU 影響。

**P-3（相關性的方向）**：若 P-0 判 `SERVER_BOUND`，則 r754 觀察到的「census 期間 75 分／列」
必須有別的解釋。**本輪只准提出候選、不准當場斷定**；候選要落在「已落盤資料能分辨」的範圍內才寫。

## 五、推翻條件（觸發了就照實寫，不准當場補判準去修）

1. `ts_ms` 兩種假設都產生負 idle gap ⇒ P-0 UNRESOLVED，整份歸因結論收回。
2. `latency_ms` 有缺漏／為 0 的筆數 > 5% ⇒ `busy_ms` 不可信，P-0 UNRESOLVED。
3. 若 `busy_ms > wall_ms`（比值 > 1.0）⇒ 代表有並行請求（runner 不是單執行緒序列發送），
   ⇒ 本節的整個時間分解模型不成立，判 `MODEL_INVALID`，**不准把比值截斷成 1.0 當作 SERVER_BOUND**。
4. 若 run 在本輪量測期間結束（`run_complete=True`）⇒ 註明數字涵蓋的是完整 run 而非中途快照。

## 六、誠實邊界（落筆於量測之前）

- **`CLIENT_GAP_BOUND` 不等於「CPU 爭用」。** 請求之外的時間還包含 runner 自己跑檢查式
  （`meets_demand` 要在本機執行候選程式碼）、寫檔、以及 python 自身開銷。
  本輪**沒有**能把「本機評分」與「CPU 被別人搶走」分開的量 ⇒ 若判 `CLIENT_GAP_BOUND`，
  只准寫「與 H_CPU 相容」，**不准寫「證實了 CPU 爭用」**。
- **本輪不是盲測**：落筆前已看到 `%CPU=0.0`、`loadavg=0.22`、
  以及 calls.jsonl 的粗略時段計數（30/60/120/240 分鐘分別 5/44/120/281 筆）。
  這個先驗**明顯偏向 H_SERVER**，所以 P-0 的門檻 0.70 是在看到 busy/wall 比值**之前**釘的。
- 本輪**對主 run 的實驗內容零分析**（不看 accepted／meets_demand／臂間比較），
  只讀時間欄位與 token 計數。R461 的收官仲裁權不受影響。
- 這份判準與量測結果**分開 commit**。
