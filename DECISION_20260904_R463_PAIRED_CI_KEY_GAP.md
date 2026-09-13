# R463（round731）：R461 的收官指令跑不起來，而唯一跑得起來的那支尺量錯口徑

**判準檔。先 commit 這一份，才開始改任何程式碼。**（memory 鐵律：判準要寫在量測之前、判準與結果分開 commit）

## 〇 合法性自證（缺一不可）

本輪要修的是 `runs/g_r461_lcb3_three_arm`（20:19 UTC 發射、本輪全程活著）的**收官指令**。
修一份預註冊的收官路徑，只有在「還沒看過該假說的資料」時才合法。逐條自證：

1. **P-R461-1（OFF5−OFF）、P-R461-2（CONFORM−OFF）、P-R461-3 的估計量，本輪一個數字都沒看。**
   三條都是**配對差值**，需要 CONFORM 或 OFF5 臂的逐題結果。
2. **誠實揭露本輪確實看到的 3 個量**（都不是上述估計量）：
   - `rows.jsonl` 第 1 列（OFF 臂、`lcb_3210`）的 `meets_demand=True` ——單臂單題，非配對差值；
   - 逐臂列數 `{OFF:2, CONFORM:1, OFF5:1}` ——進度，非結果；
   - 列序 `(1,OFF)(1,CONFORM)(1,OFF5)(2,OFF)` ——排程順序，非結果。
   **CONFORM／OFF5 臂的 `meets_demand`／`accepted` 值，本輪零次讀取。**
3. **本修正不動任何窗口、門檻、MDE、預測區間、α、n、seed、worker、端點、bank。**
   落在 R462 §六.4 事前授權的「與數字無關的缺陷（詞彙／死碼／缺仲裁者）」。
4. **加法式**：R461 §三／§四／附錄 B 原文一字不改，本輪新增附錄 C；
   `paired_ci.py` 的預設行為逐位元不變（`--key` 預設 `meets_demand`）。後輪要收回仲裁權，比對原文即可。

## 一 缺陷（三段，實測）

### C-1 附錄 B 指名的收官指令**無法執行**

```
$ python3 ops/gain/replay/pooled_paired_ci.py --stratum lcb3=runs/g_r461_lcb3_three_arm \
      --a-arm CONFORM --b-arm OFF --key deliv
需要至少兩個 --stratum LABEL=dir，或 --selftest
rc=2
```

`pooled_paired_ci.py:242` 硬性要求 `len(args.stratum) >= 2`。R461 是**單一題庫的複製**，只有一層。
⇒ 附錄 B 的兩條指令**產不出 `verdict_pooled`**，P-R461-1／2 的第三個合取項照字面**沒有仲裁者**。

⚠ 這正是 R462（附錄 B 自己）要修的那個缺陷的**同型復發**：R462 修好了「判決名沒有 emitter」，
卻指名了一支**在單層上跑不起來**的工具。修詞彙時沒有把指令**實際跑一次**。
**⇒ 本輪新增一條通則：預註冊裡的收官指令，寫進判準檔之前必須先原樣跑一次（可以在別的 run 上跑）。**

### C-2 唯一跑得起來的單 run 尺**沒有 `--key`**，寫死舊口徑

`ops/gain/replay/paired_ci.py` 是單 run 版（R462 普查的 `paired_ci.verdict` 詞彙表就出自它，
`ON_WINS` 等四個字串在 `:106-111`）。全庫逐檔查 `--key` 支援：

| 工具 | `--key` | `deliv` |
|---|---|---|
| `ops/gain/replay/pooled_paired_ci.py` | ✓ | ✓ |
| `ops/gain/power_paired.py` | ✓ | ✓ |
| **`ops/gain/replay/paired_ci.py`** | **✗** | **✗** |
| `ops/gain/analyze_paired.py` | ✗ | ✗ |
| `ops/gain/replay/paired_gates.py` | ✗ | ✗ |

`paired_ci.py:208,220,221,233-235` 一律寫死 `meets_demand`。
**這是 memory 記過的坑第三次出現**（r675 修 `pooled_paired_ci.py` 時，`power_paired.py` 上原封不動躺著一份；
r678 才發現。當時沒有回頭 grep 到 `paired_ci.py`）。

### C-3 兩個口徑的分歧格**可達**，而且方向偏向假說

`deliv = accepted ∧ meets_demand`。分歧格＝`accepted=False ∧ meets_demand=True`（拒交、但東西是對的）。

可達性由原始碼確立，不是推測：
- `gain_run.py:588`　`code, worker = chosen if accepted else last` ——閘門拒交時**回退到最後一份候選**；
- `gain_run.py:1586`　`truth, err = meets_demand(code, ...)` ——**無條件**對那份回退碼評分。

⇒ 五份候選都被可見閘門打掉、但最後一份剛好是對的 ⇒ `accepted=False ∧ meets_demand=True`。
（memory 鐵律：看到 `X if cond else <fallback>` 就問下游有沒有哪個量把 fallback 當成真的選擇。這裡就有。）

`OFF`／`OFF5` 臂 `accepted` 恆為 `True`（`gain_run.py:1555` 等）⇒ 兩口徑在那兩臂**恆等**。
**⇒ P-R461-1（OFF5−OFF）不受影響；受影響的只有 P-R461-2（CONFORM−OFF）。**

**方向**：用 `meets_demand` 會把「CONFORM 拒絕交付、但回退碼碰巧正確」算成 CONFORM 的一次交付
⇒ **高估 CONFORM** ⇒ 偏向 R461 想證的方向。這是本缺陷必須在看資料前修掉的理由。

## 二 修正範圍（只做這些，多做的都算違規）

1. `paired_ci.py` 新增 `--key {meets_demand,deliv}`，**預設 `meets_demand`**（回歸相容），
   KEYS 表與缺欄位擋門**逐字照抄** `pooled_paired_ci.py:42-46,121-127`（不是本輪新訂口徑）。
2. 輸出新增 `"key"` 欄位（下游要能驗產物自己記的 key——memory：旗標預設是舊語意時必驗）。
3. R461 新增**附錄 C**：把收官指令改成單 run 尺的正確呼叫。**不改任何門檻與判決名對應表。**

**不做**：不動 `analyze_paired.py`／`paired_gates.py`（本次收官不經過它們；要改另開判準，避免順手擴大範圍）。
不動 `pooled_paired_ci.py`。不動活著的 run。

## 三 這把尺算不算有牙齒——**事前寫死**

### 3.1 什麼**不算**牙齒

在 `runs/g_r447_conform_lcb2` 上跑兩個 key 得到相同答案，**不算驗證**。
實測該 run 的分歧格是**空的**（120 題 CONFORM：113 accepted、7 refused，7 個全部 `meets_demand=False`）
⇒ 兩 key 必然同值 ⇒ 那是「乾淨 PASS、植入缺陷仍 PASS」的假測試形狀。
**r447 只當回歸對照用**（證明沒改壞舊行為），**不當牙齒證明**。

### 3.2 什麼**才算**牙齒（兩條，都要過）

- **T1 合成夾具**：手造 rows，CONFORM 臂**含至少一格** `accepted=False ∧ meets_demand=True`，
  且該格在 OFF 臂為 False。則 `--key meets_demand` 與 `--key deliv` 必須吐出**不同的 b／c**。
  兩者相同 ⇒ FAIL。
- **T2 具名突變體 `M_KEY`**：把 `--key` 做成裝飾品（永遠取 `meets_demand`）。
  T1 在突變體底下必須 FAIL，**且判準要指名「b／c 這個量沒有變」**，不准只寫 `rc≠0`
  （memory：突變體放錯目錄害 import 失敗也是 rc≠0＝infra 壞掉被誤判成偵測器有牙齒）。
  突變點必須寫在**被測函式內部**（memory：寫在模組層永遠不生效，長得跟沒牙齒一模一樣）。

### 3.3 夾具的自我限制（事前承認）

T1 的夾具由本輪手寫，**不共用被測檔的 helper**（memory r699：夾具由被測模組自己的 helper 造 ⇒ 驗不到真資料 schema）。
代價：夾具驗得到「口徑選擇」，驗不到「真資料欄位名對不對」——後者由 3.1 的 r447 回歸對照補。
**兩者都不是完整覆蓋，照實寫。**

## 四 事前預測（**含基準率**，收官時對帳）

| # | 預測 | 基準率 | 何時判 |
|---|---|---|---|
| P-R463-1 | `paired_ci.py --key deliv` 與 `--key meets_demand` 在 **r447** 上吐出**相同** b／c | 高（分歧格已實測為空）⇒ **這是構造不是預測**，記 `CONFIRMATORY`、不算命中 | 本輪 |
| P-R463-2 | T1 合成夾具上兩 key **不同**，且 `M_KEY` 突變體底下變成相同 | 低（若相同就是修正沒生效） | 本輪 |
| P-R463-3 | `runs/g_r461_lcb3_three_arm` 的 CONFORM 臂，收官時 `accepted=False ∧ meets_demand=True` 的格數 **≥ 1** | **約 40–70%**（r447 是 0/7 拒交格；189 題約 11 個拒交格，逐格分歧率 p∈[0.05,0.10] ⇒ P(≥1)∈[0.43,0.69]）。**區間寬是誠實的，不假裝精確** | **收官**（本輪不准量，量了就是偷看 CONFORM 臂） |

## 五 推翻條件（觸發就照實寫，**不准當場補判準去修**）

1. 若 `paired_ci.py` 其實有別的方式吃 `deliv`（例如上游 `analyze_paired.load_rows` already 投影過），
   則 C-2 的嚴重性被高估 ⇒ 照實改寫 C-2，並保留原文。
2. 若 T1 造不出分歧格（＝ C-3 的可達性推理錯了），則**整份 R463 的前提垮掉** ⇒
   停止修改、還原 `paired_ci.py`、把「可達性推理錯在哪」寫進 GAIN_STATE。
3. 若加了 `--key` 之後 r447 的**預設**輸出與修改前**不逐字相同**，則加法性宣稱為假 ⇒ 回滾。

## 六 誠實邊界

- 本輪**不會**在 `runs/g_r461_lcb3_three_arm` 上跑任何 `paired_ci.py`（那是偷看）。
  修好的尺要到該 run 自己跑完才第一次用在它身上。
- P-R463-3 是**唯一**需要等資料的預測，其餘兩條本輪就判完。
- C-1 的通則（「收官指令要先跑過一次」）是**本輪新訂**的，適用於後續所有預註冊，
  不追溯要求重跑已收官的 R444／R445／R446／R459。
