# R478：讓認證段落自己記下 blob sha——把 R477 §10.5.1 指名的那個低報洞補起來

判準先行。本檔在工具改動與任何量測**之前** commit。R477（`75e6d3c`）的擋門
`ops/gain/cert_drift_gate.py` 已經在跑，本輪只改它的**認證時刻取得方式**，判決語意不動。

## 一、要解的洞（R477 §10.5 第 1 條原文指名）

R477 的「認證時刻」是用 `git log -S<標題原文> -- <doc>` **反推**出來的：
把那個標題字串首次寫進該文件的那個 commit，當作「附錄宣稱原樣跑過」的時刻。

失效方向是**低報**，而且是安靜的：

> 有人改寫認證標題的文字（錯字、補一個詞、換標點）⇒ `-S<新字串>` 只找得到**改寫那一次**
> ⇒ 認證時刻**往後移** ⇒ `<認證時刻>:<工具>` 的 blob 更可能等於 `HEAD:<工具>`
> ⇒ 本該 `CERT_STALE` 的格子變成 `CERT_FRESH` ⇒ **收官照原文引用了一個過期的數字**。

擋門的兩個方向不對稱：過度警報（R477 §三已知，`paired_ci.py` STALE 但數字重現）只是多跑一次；
**低報是無聲的綠燈**，正是 memory 反覆記的「安靜量不到」。所以要補的是低報這一邊。

## 二、定義（實作只准編碼本節）

1. **自記標記**（新增）＝ 認證附錄內、**行首錨定**的一行：

   ```
   - CERT-BLOB `<ops/ 底下的工具路徑>` = `<40 位小寫 hex>`
   ```

   正規式寫死為 `^\s*[-*]\s*CERT-BLOB\s+\x60(ops/[\w./-]+\.py)\x60\s*=\s*\x60([0-9a-f]{40})\x60\s*$`
   （`\x60` ＝ 反引號）。**必須 40 位全長**，不接受縮寫 sha：縮寫在未來會歧義。

2. **作用範圍**與 R477 的「被認證工具」完全相同——只有落在**有認證標題的附錄區塊**內的
   自記標記才算數。⚠ 因此**本判準檔自己雖然含有 `CERT-BLOB` 字面，卻不會被讀進去**
   （本檔沒有任何含認證標記的標題行）。這是 memory 記過的「字串比對會匹配到自己」，
   本輪用「範圍限定」而非「換字面」來擋，並用 `S1` 直接釘住它。

3. **sha 來源**（每個工具格新增欄位 `sha_source`）：
   - `recorded`：該附錄有這支工具的自記標記 ⇒ **認證時 blob 一律以自記值為準**。
   - `derived`：沒有自記標記 ⇒ 退回 R477 的 `-S` 反推（**行為與 R477 完全相同**）。

4. **交叉檢查**（本輪的重點，`recorded` 才做）：同時算出 `-S` 反推值，
   兩者不同 ⇒ 記進 `cert_sha_mismatches`（含 doc／附錄／工具／兩個 sha）。
   **這不是換掉工具格的判決**——工具格照 `recorded` 判 FRESH／STALE，
   `cert_sha_mismatches` 非空時**整份報告**升級成 `verdict=BROKEN`／`rc=2`。
   理由：低報時該工具格的 `CERT_STALE` 必須**留在原地看得見**，同時整體大聲叫。

5. **自記值的真實性檢查**：自記的 40 hex 必須真的曾經是**該路徑**的某個版本
   （列舉 `git log --format=%H -- <tool>` 每個 commit 的 `<commit>:<tool>` blob）。
   不在裡面 ⇒ 該格判 `BROKEN_CERT_SHA_NOT_IN_HISTORY`。
   這道檢查擋的是「抄錯／編造一個 sha 寫進附錄」。

## 三、rc 與判決語意（在 R477 §六之上**只加不改**）

`0` 掃到且全 FRESH／`1` 有 STALE／`2` 有任何 `BROKEN_*`、`UNSCANNED`、**或 mismatch 非空**。
R477 的四種工具格判決原樣保留，新增兩種 `BROKEN_*`：
`BROKEN_CERT_SHA_NOT_IN_HISTORY`、`BROKEN_CERT_SHA_UNPARSEABLE`。

⚠ **誠實邊界（承接 R477 §三，不准漏）**：`CERT_STALE` 仍然只表示「引用前必須重跑」，
**不表示那個數字錯了**。本輪一個字都沒有放寬這條。

## 四、加法性（memory：改欄位語意用 additive）

`cert_commit`／`cert_commits`／`blob_at_cert`／`blob_at_head`／既有四種判決字串**原值不動**。
新增的是 `sha_source`、`blob_at_cert_recorded`、`blob_at_cert_derived`、
`cert_sha_mismatches`、`slots_recorded`／`slots_derived`。
⇒ R477 落盤的 `ops/gain/data/r477_cert_drift.json` 不必重算也不會被改寫（本輪寫新檔）。

## 五、事前預測（落筆於任何量測之前；命中與否照字面記，不准回頭改）

- **P1**：加完自記標記後，真實工具格 `slots_recorded = 4`、`slots_derived = 0`。
- **P2**：四個工具格的判決**與 R477 逐格相同**——`pooled_paired_ci.py` FRESH、
  `paired_ci.py` STALE、`r447_eq5_offline.py` FRESH、`r447_gauge_capability.py` STALE。
  （加法性的回歸：自記值＝今天的反推值 ⇒ 判決不該動。若不同，是我抄錯 sha 或範圍解析錯。）
- **P3**：`cert_sha_mismatches` 今天 **＝ 0**。
  🔴 **這是結構強制綠燈，事前就標明**（R453 可證偽性普查的分類）：自記值是照今天的
  `-S` 反推值抄進去的，兩者今天不可能不同。它的 `intent = guard`（防未來的標題改寫），
  **不是 evidence**——收官**不准**拿 `mismatches=0` 當「沒有人改過標題」的證據。
  它有沒有牙齒只能由 `M9` 證明，不能由今天的真資料證明。
- **P4**：`BROKEN_CERT_SHA_NOT_IN_HISTORY = 0`（四個自記值都在各自路徑的歷史裡）。
  這條**不是**強制綠燈：§二.5 的歷史列舉方法可能寫錯（例如漏了改名、漏了 merge 側邊），
  真的寫錯今天就會紅。
- **P5**：`docs_scanned = 139`（R477 那次 138 ＋ 本判準檔 1）、`cert_headings` 仍為 **6**。
- **P6**（本輪的主張，只能由突變體證明）：模擬「標題被改寫」的 `M9`——強迫 `-S` 反推
  回到 `HEAD` ——之下，**新擋門的 `CERT_STALE` 格數不變（仍為 2）且 `cert_sha_mismatches = 2`
  且 `rc = 2`**；而同時關掉自記優先的 `M9+M10`（＝R477 的舊行為）**`CERT_STALE` 掉到 0 且 `rc = 0`**。
  ⇒ 「舊版會低報、新版不會」是被實際重現的，不是宣稱的。
  mismatch 預測 2 不是 4：兩個 FRESH 格的自記值本來就等於 `HEAD` blob，強迫後仍相等。
- **P7**：模組層**數值**常數新增數 = 0（R476／R477 的滾動預測；計數器與正規式不算數值常數）。
- **P8**：本判準檔自己貢獻 **0** 個認證群組（§二.2 的自我匹配擋門）。

**推翻條件**：P2 有任何一格與 R477 不同 ⇒ 本輪不准宣稱「加法性成立」，要停下來查是抄錯
還是解析錯，並把原始輸出留著。P6 任一半不成立 ⇒ 本輪的主張作廢，照實寫「洞沒補起來」。

## 六、突變體（每一條都要指名「該看到哪個量變」，crash 收場算 BROKEN 不算偵測到）

| 代號 | 植入什麼 | 該看到的量 |
|---|---|---|
| `S1` | （不是突變體，是擋門）本判準檔必須貢獻 0 群組 | `groups` 裡沒有本檔名 |
| `M8_BAD_RECORDED` | 把讀進來的自記 sha 換成一個合法格式但不存在的 40 hex | `BROKEN_CERT_SHA_NOT_IN_HISTORY > 0` 且 `rc=2` |
| `M9_HEADING_REWRITTEN` | 強迫 `introducing_commit` 回 `HEAD`（＝標題被改寫的效果） | `CERT_STALE` 仍為 2、`mismatches=2`、`rc=2` |
| `M10_IGNORE_RECORDED` | 忽略自記值、只用反推（＝R477 舊行為）；與 M9 併用 | `CERT_STALE → 0`、`rc=0`（重現低報） |
| `M11_LOADBEARING` | 把「自記優先」那段**實體刪掉**放回同一 import 環境，再加 M9 | 同 M10：`CERT_STALE → 0` |
| `M12_RE_STALE` | 自記標記正規式改成掃不到的字面 | `slots_recorded → 0`（安靜量不到第一型要看得見） |

`M11` 是比 env 旗標更硬的那一種（memory：檔內 `MUTANT` 旗標答不了「刪掉正式那行會不會紅」）。
`M8`／`M12` 的突變**一律在被測函式內部生效**（memory：寫在模組層永遠不生效）。

## 七、接線與範圍

- 接進 `tests/`（沿用 `ops/run_tests_nopytest.py`），接線本身要有植入缺陷測試。
- **本輪不碰主 run** `runs/g_r461_lcb3_three_arm`：不殺、不 `git add` 它的目錄、
  不跑任何分析工具、不重算 ETA。`cert_drift_gate.py` 內建的 G-LIVE 擋門保留，
  輸出 `live_run_reads` 必須是 0。
- **本輪不改**：掃描範圍仍只有 repo 根 `DECISION_*.md`（R477 §10.5.2 的第二個洞留給後輪）。
