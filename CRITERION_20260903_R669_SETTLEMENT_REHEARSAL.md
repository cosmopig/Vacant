# R669 判準：收官那一刻的硬擋門，從來沒有在真資料上被執行過

（2026-09-03，round669，Opus 5。**寫在量測之前**。r444 仍在跑，本檔 commit 之後才碰數字。）

## 〇 污染揭露（誠實邊界，先講）

寫這份判準之前，我**已經看過**以下 r444 的數字，因此凡由它們可推導的預測一律
降級成「只報數字」，不當預測記分：

- round667／668 的中途快照：`deliv` Δ=+3.20pp、`leaked` CONFORM=26 vs OFF5=37、
  拒交驅動佔 72.7%、`md∧¬acc`=0。
- launch.log 的累計呼叫：CONFORM 133 題 196 次（⇒ P-C2 的 ≤2.0 實質已可見）。
- **本輪開場為了判斷風險是否已實現，我跑過 `grep -c infra_void notes.jsonl` → 0。**
  因此 P-R669-E（r444 最終 void 數）**不是預測，是收尾照實回報**。

下面的 P-R669-A~D **全部是關於工具在人造 fixture 上的行為**，不是關於 r444 的實驗數字。
這是刻意的設計：這一輪要驗的是尺，不是結果。

## 一 這一輪要解的問題

round666／667／668 分別替 P-C4／P-C1・P-C1b・P-C2・P-C3a・P-C5／P-C3b 造了尺。
六條主張現在都有尺了。**但那三支尺的 `terminal=True` 分支，從來沒有在真資料上跑過**——
每一次實測都是中途快照（`terminal=False`），而那正是硬擋門被**降級成照實報 skew** 的分支。

收官只會發生一次。那一次跑的是**沒被執行過的那條路徑**。

## 二 已確認的碼側事實（讀原始碼，行號可查）

| # | 事實 | 位置 |
|---|---|---|
| H1 | 每列的 `calls_used = calls[0] − calls_before` ⇒ 逐列和 ≡ **非 void** 格子消耗的呼叫 | `gain_run.py:1386` |
| H2 | summary 的 `calls_per_task = calls_n / measured`，`calls_n = s["calls"][0]`（該臂**全部**呼叫）、`measured = processed − n_void` | `gain_run.py:1256-1258,1278` |
| H3 | `except InfraVoid` 只做 `n_void += 1` 然後 `continue`，**不把 `calls[0]` 回捲**到 `calls_before` | `gain_run.py:1329-1337`（`calls_before` 存在於 1303 但 void 路徑沒用它） |
| H4 | `InfraVoid` 由**沙箱驗證器**丟出（不是模型呼叫），而 `arm_conform`／`arm_off` 都是**先 `calls[0] += 1` 再**跑 `meets_demand(visible)` ⇒ **一個 void 格子可以已經吃掉 1~5 次呼叫** | `gain_run.py:133,277,224,492` |

⇒ **H1+H2+H3+H4 合起來：只要某臂 `n_void > 0` 且那些 void 格子消耗過呼叫，
`summary.calls_per_task` 與逐列覆算就 _在健康的 run 上_ 必然不相等。**

而 `conform_settle.py:163-171` 在 `terminal=True` 時對這個差**硬擋 BROKEN**。
⇒ 那是一個**在健康資料上會誤報的擋門**，且只在收官那一刻、只在有 void 時才會現形。

**這個「exact equality」不是碼所蘊含的不變量**——碼蘊含的是
`summary.calls = 逐列和 + void 格子消耗`，而 void 格子的消耗**沒有任何地方逐格記錄**。

## 三 事前預測（跑之前寫死）

| # | 預測 | 判準 |
|---|---|---|
| **P-R669-A** | 健康、**平衡**（三臂列數相同）、`n_void=0` 的 fixture，`terminal` 強制為 true ⇒ `conform_settle.py` rc=0、`live_snapshot_skew==[]`、`settlement_ready==true` | rc 與 JSON 欄位 |
| **P-R669-B** | 同一份 fixture **加入一個吃掉呼叫的 void 格子**（移掉該列、summary.calls 不動、`n_void=1`、`processed` 不變）⇒ 現行 `conform_settle.py` **BROKEN**＝**在健康資料上誤報** | rc=2 且 reason 提到 calls_per_task |
| **P-R669-C** | 同一份 void fixture 餵 `leak_decomp.py` ⇒ **不**誤報（它的跨來源欄位 leaked／accepted／accepted_and_meets_demand 都對 void 免疫） | rc=0 |
| **P-R669-D** | 修好之後：void fixture 通過（rc=0），而**真的**呼叫數竄改（在 `n_void=1` 的掩護下加大 summary.calls 超過上界）**仍然 BROKEN** ⇒ 牙齒沒掉 | 兩個方向都要成立 |
| P-R669-E | r444 最終 `n_void`（三臂） | **不是預測**（§〇 已污染），收尾照實回報 |

## 四 修法規則（**先寫死，不准跑完再挑**）

若 P-R669-B 成立（誤報），**不准**用以下任一方式「修」：
- ❌ 刪掉這個擋門；
- ❌ 把它無條件降級成 report-only；
- ❌ 加一個可調的容差旋鈕。

**唯一允許的修法是「換成碼真正蘊含的不變量」，且必須淨變嚴：**

1. `n_void == 0` ⇒ **維持現行 exact equality**（牙齒原封不動）。
2. `n_void > 0` ⇒ exact equality 不被碼蘊含，換成**兩條碼蘊含的界**：
   - `summary.calls >= 逐列和`（void 只可能往上加），且
   - `summary.calls − 逐列和 <= n_void × max(該臂逐列 calls_used)`
     （每個 void 格子最多吃掉一格的上限；**上界由資料導出，零新旋鈕**）。
3. **同時補上三條對 void 免疫、且碼精確蘊含的 exact 檢查**（這是「淨變嚴」的來源）：
   - `summary.accepted == 逐列 accepted 數`
   - `summary.accepted_and_meets_demand == 逐列 (accepted ∧ meets_demand) 數`
   - `summary.processed == 逐列數 + n_void`  ← **這條會抓到「列不見了」**，是現行工具沒有的
4. 輸出 JSON 必須明寫這一臂走的是哪一層（`calls_check: "exact" | "bounded(n_void=k)"`），
   **不准安靜降級**。

## 五 推翻條件

- 若 P-R669-B **不**成立（現行工具在 void fixture 上照樣 rc=0）⇒ 我對 H1-H4 的推理有錯，
  照實寫「推理錯了」，並去查是哪一條事實錯，**不改工具**。
- 若修完之後 P-R669-D 的反向測試（真竄改）**沒有** BROKEN ⇒ 修法讓牙齒掉了，
  必須回退，不准留著。
- 若 r444 收官時三臂 `n_void` 皆為 0 ⇒ 本輪的修**在 r444 上不改變任何數字**
  （第 1 層），這要照實寫成「這輪修的是下一個 run 的地雷，不是這個 run 的結論」。

## 六 不碰的東西

- **r444 的檔案全程唯讀**：fixture 一律建在 `/dev/shm/r669/`，不寫回 run 目錄。
- `gain_run.py` **一個字都不改**（它正在跑）。本輪只動 `ops/gain/replay/` 底下的離線尺。
