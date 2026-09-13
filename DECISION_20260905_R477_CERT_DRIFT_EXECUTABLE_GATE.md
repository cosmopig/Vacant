# R477：把「工具改動後、引用它的收官守則要重跑」從散文變成**可執行的擋門**

判準先行。本檔於工具與量測**之前** commit。round747（R476）§四.3 的推翻條件觸發了
（P4／P6 兩條都成立 ⇒ 通則缺口），該條事前指定：**R463 §一 C-1 的通則要補一句
「工具改動後，所有引用它的收官守則都要重跑」，而那句話要寫成可執行的擋門，不是散文。**
本輪就做這件事，並且只做這件事。

## 〇、與主 run 的關係

`runs/g_r461_lcb3_three_arm` 還在跑（開場 194 列、`infra_void=0`、`run_complete=False`）。
本輪 **一個 byte 都不讀它**（工具內建 G-LIVE 擋門，見 §六），也不 `git add` 它的目錄，
也不起任何新 run。本輪的產物全部是離線的 git 中繼資料比對。

## 一、缺陷（R476 已證實，本輪不重證）

R461 的附錄 C／D／E 各自寫著「這條收官指令**已經原樣跑過**」並逐字記下數字。
那是 R463 §一 C-1 立的通則。但 C-1 只約束「寫進判準之前要先跑一次」，
**沒有任何機制在「工具後來被改了」的時候叫**。R476 實測：9 格裡 3 格 `DRIFTED_SAFE`
（附錄 E.4 Y1「14 條」今天是 19 條、附錄 E.3 兩格今天改吐 `BROKEN_ROW_ACCOUNTING`）
⇒ 附錄原文的三句話今天為假，而**沒有任何自動化東西會提醒收官的人**。

R476 是**逐格重跑**發現的（7m32s，且要為每一格手寫期望值與投影）。那個做法無法擴張：
每新增一個附錄就要新增一格夾具。本輪要的是**不必重跑就能知道「該不該重跑」**的擋門。

## 二、擋門的語意（**先寫死，量完不准改**）

`ops/gain/cert_drift_gate.py`。掃 repo 根目錄的 `DECISION_*.md`，對每一個
**認證段落**判定它認證過的工具今天是否仍是當時那一份。

**定義（逐條寫死，避免事後挑）**

1. **認證標記** ＝ 行首是 markdown 標題（`^#{1,6}\s`）**且**該行含 `原樣跑過`。
   ⚠ **散文裡的「已原樣跑過」不算**（R464:19、R476:1／20 三處是散文）。這是本擋門
   第一個必須分對的東西：把散文算進來＝把沒認證過的東西當成認證過。
2. **認證範圍** ＝ 該標題所屬的**附錄區塊**（由 `^# 附錄 X` 起，到下一個 `^# 附錄` 或檔尾）。
   附錄之外的認證標題 ⇒ 範圍是「整份文件」，並記 `scope="doc"`。
3. **被認證的工具** ＝ 該範圍內**可執行指令行**上的路徑：行內出現
   `python3 <path>.py`（可含 `$ ` 前綴、可含續行 `\`）。
   ⚠ 只在散文／反引號裡被提到的檔名（如 C.4 的 `r463_key_teeth_test.py`、
   D.4 的 `r447_eq5_offline.py:145`）**不算被認證**——它們不是那條被跑過的指令。
4. **認證時刻** ＝ 用 `git log -S<認證標題原文> -- <doc>` 取**最早**的那個 commit
   （＝該標題被寫進檔案的那次）。同一附錄有多個認證標題時取**最早**的（保守）。
5. **每一支工具的判決**（比 blob sha，不比 mtime、不比 commit 數）：
   - `CERT_FRESH`  `git rev-parse <cert_commit>:<tool>` 與 `git rev-parse HEAD:<tool>` **逐字元相同**
   - `CERT_STALE`  兩者不同 ⇒ **引用該附錄的數字之前必須重跑**
   - `BROKEN_TOOL_ABSENT_AT_CERT` 認證當時 repo 裡沒有這支工具（＝認證段落自己有問題）
   - `BROKEN_TOOL_GONE` 今天 HEAD 上沒有這支工具
   - `BROKEN_NO_CERT_COMMIT` `-S` 找不到任何 commit（標題原文與歷史對不上）

## 三、`CERT_STALE` 的**誠實邊界**（這段是本檔最重要的一段，收官不准漏）

**`CERT_STALE` 的意思是「必須重跑才能引用」，不是「那個數字變了」。**

R476 的實測已經先證明這兩件事必須分開：`paired_ci.py` 在附錄 C.4 認證之後**確實被改過**
（R471，`6ad574e`），但 C.4 的 `+19.17pp`／`+12.50pp` 今天**逐字重現**。
⇒ 本擋門在「數字有沒有變」這個問題上是**刻意過度警報**的：它只看 blob 有沒有動。

⚠ 因此**事前寫死**：任何人（包含後面的輪次）**不准**把 `CERT_STALE` 讀成
「附錄那個數字是錯的」或「那個結論被推翻」。它只產生一個義務：**重跑一次再引用**。
反過來 `CERT_FRESH` 是強的：工具逐 byte 相同 ⇒ 同輸入必得同輸出（除非環境變）。

**這也是為什麼本擋門不取代 R476 的重跑**：兩者一個問「該不該重跑」（便宜、可擴張），
一個問「重跑之後數字一不一樣」（貴、要手寫期望值）。收官要的是**先跑本擋門，
它叫的那幾支才要動用 R476 那種逐格重跑**。

## 四、事前預測（`blind` ＝ 落筆時我不知道答案；`informed` ＝ 已知，不計入盲測命中率）

| # | blind? | 預測 |
|---|---|---|
| P1 | **blind** | 全庫掃到的**認證標題**數 ＝ **5**，且**全部**在 `DECISION_20260904_R461_LCB3_REPLICATION_PREREG.md`；R464／R476 那三處散文**一個都不入選** |
| P2 | **blind** | 被認證的**相異工具**數 ＝ **4**：`pooled_paired_ci.py`／`paired_ci.py`／`r447_eq5_offline.py`／`r447_gauge_capability.py` |
| P3 | informed | `r447_eq5_offline.py` 判 `CERT_FRESH`（R476 的負對照：它在附錄之前定版、之後未改） |
| P4 | informed | `paired_ci.py` 與 `r447_gauge_capability.py` 判 `CERT_STALE`（R476 已知這兩支被改過） |
| P5 | **blind** | 附錄 C 的工具集**含 `pooled_paired_ci.py`**（C.1 那條 `rc=2` 的失敗示範也是被認證的事實，R476 也把它記成一格）⇒ 該格不是誤報 |
| P6 | **blind** | `BROKEN_*` ＝ **0** 格 |
| P7 | **blind** | 本輪**新增可調參數 0 個**（`ast` 掃模組層數值常數賦值）、**live run 讀取 0**（輸出 `live_run_reads`） |
| P8 | **blind** | 擋門判 `CERT_STALE` 的工具裡，**至少 1 支**其 R476 對應格是 `REPRODUCED`（＝過度警報是真的存在的，§三 不是假想） |

⚠ **綠燈基準率**：P3／P4 是「照 R476 已知結論核對」型 ⇒ 命中不帶資訊，只有**反例**帶資訊
（若 P3 反了代表我的 cert-commit 定位錯）。真正帶資訊的是 **P1／P2／P5／P8**。

## 五、雙向校準與植入缺陷（缺任一項則本輪分類全部作廢）

`--selftest` 必須含下列每一條，且每一條要指名**它該看到哪個量變化**（不是只看 rc≠0）：

- **真資料負對照**：`r447_eq5_offline.py` ⇒ `CERT_FRESH`（有一支不叫的，才排除「什麼都判 STALE」）
- **真資料正對照**：`paired_ci.py` ⇒ `CERT_STALE`（有一支會叫的，才排除「什麼都判 FRESH」）
- **M1 散文誤收**：把認證標記的比對放寬成「整行含 原樣跑過」（不要求行首是標題）
  ⇒ 認證標題數必須從 5 變成 8（R464／R476 三處散文混進來）⇒ 測試要紅
- **M2 恆綠**：把 blob 比對改成永遠回 `CERT_FRESH` ⇒ `CERT_STALE` 格數必須掉到 0 ⇒ 測試要紅
- **M3 安靜量不到（regex 過期）**：把指令行 regex 改成匹配不到的字串
  ⇒ 必須吐 `BROKEN_NO_TOOLS`／rc=2，**不准吐 rc=0「全部乾淨」**
- **M4 安靜量不到（掃到 0 份文件）**：文件 glob 改成匹配不到
  ⇒ 必須吐 `UNSCANNED`／rc=2，**不准**跟「掃過而且都乾淨」同一個判決
- **M5 承重牆**：把 §二.5 的 blob 比對**整段刪掉**（不是改旗標）⇒ 必須紅；
  若仍紅於別的偵測條，記 `STILL_RED_ELSEWHERE` 並指名。
- ⚠ 突變一律要在**被測函式內部**生效（memory：寫在模組層的 `MUTANT` 旗標永遠不生效，
  長得跟「偵測條沒牙齒」一模一樣）。

## 六、擋門自己的擋門

- **G-LIVE**：任何含 `g_r461_lcb3_three_arm` 的路徑一律 `RuntimeError`；輸出 `live_run_reads`。
- **rc 語意**（寫死）：`0` ＝ 掃到東西且全部 `CERT_FRESH`；`1` ＝ 有 `CERT_STALE`；
  `2` ＝ 有 `BROKEN_*` 或 `UNSCANNED`。**「沒掃到東西」不准回 0。**

## 七、推翻條件（觸發了照實寫，**不准當場補判準去修**）

1. **P3 反了**（負對照被判 STALE）⇒ 我的 cert-commit 定位方法壞掉 ⇒ 本輪所有 `CERT_*` 作廢，
   只准寫「量不出來」。
2. **五條突變體任一條沒紅**（且不是 `STILL_RED_ELSEWHERE`）⇒ 該偵測條沒牙齒，
   照實記 `MISSED`，**不准**把它從清單裡刪掉。
3. **掃出 `BROKEN_*`** ⇒ 先查是不是夾具／路徑問題（R476 的教訓：BROKEN 多半是夾具），
   查明之前不准記成 `CERT_STALE` 或 `CERT_FRESH`。
4. 若 P1／P2 落空 ⇒ 照實記 MISS 並寫出實際數字；**不准回頭改本檔的預測**。

## 八、接線（沒接線的尺沒有牙齒）

擋門要接進 `tests/`（這台沒有 pytest ⇒ 用 `ops/run_tests_nopytest.py` 跑）。
**驗收方式：接線前後看「收集數／PASS 總數」有沒有變**（memory：零收集會印 0/0 passed＋exit 0），
而不是看有沒有變紅。接線本身也要植入一次缺陷證明那一行會叫。

## 九、本檔沒有動的東西

R461 的任何門檻、判決名、n、seed、worker、端點、bank；R476 的四格分類與它的 JSON 產物；
主 run 的任何檔案。本檔**不修改** `paired_ci.py`／`r447_gauge_capability.py`／
`r447_eq5_offline.py` 的任何一行——本輪只是**觀測**它們的 blob。

---

# 十、量測之後追記（round748，**§一–§九 一字未改**，預測帳照原文結算）

## 10.1 事前預測結算

| # | blind? | 預測 | 實測 | 判 |
|---|---|---|---|---|
| P1 | **blind** | 認證標題 5，全在 R461 | **6**，第 6 個是 `DECISION_...R476...md:1`（文件標題） | **MISS** |
| P2 | **blind** | 相異工具 4，四個具名 | 4，且**逐一相同** | HIT |
| P3 | informed | `r447_eq5_offline.py` FRESH | `CERT_FRESH`（+0 commits） | HIT（不計盲測） |
| P4 | informed | `paired_ci.py`／`r447_gauge_capability.py` STALE | `CERT_STALE`（+1／+3） | HIT（不計盲測） |
| P5 | **blind** | 附錄 C 含 `pooled_paired_ci.py` | 含，且判 `CERT_FRESH` | HIT |
| P6 | **blind** | `BROKEN_*` ＝ 0 | 原始量測 **`BROKEN_NO_TOOLS` ＝ 1** | **MISS** |
| P7 | **blind** | 新增可調參數 0／live run 讀取 0 | 模組層數值常數 **1**（`_LIVE_READS = 0`）／`live_run_reads=0` | **前半字面 MISS**、後半 HIT |
| P8 | **blind** | ≥1 支 STALE 工具其 R476 對應格是 `REPRODUCED` | `paired_ci.py` STALE 而 R476 的 `C4_conform_vs_off`／`C4_off5_vs_off` 皆 `REPRODUCED` | HIT |

**盲測：4 HIT／2 MISS（＋P7 前半字面 MISS）。沒有回頭改任何一條預測。**

⚠ **P1 與 P6 其實是同一個事件被數了兩次**（都是 R476 的標題行）——
這是 r718 記過的同型帳目缺陷（同一事件在兩條判準下各記一次），**照實記，不合併**。

⚠ **P7 前半照 §四 的字面（`ast` 掃模組層數值常數）判 MISS**：那一個是計數器 `_LIVE_READS`，
語意上不是旋鈕（沒有任何判決依它變）。**但判準寫的是字面，就照字面記 MISS**，
不回頭改判準去讓它變成 HIT（R476 的 `SUBPROC_TIMEOUT_S` 是同一個處理方式）。

## 10.2 §七.3 觸發：`BROKEN_NO_TOOLS` 的分診結果

判準 §七.3 事前寫「掃出 `BROKEN_*` ⇒ 先查是不是夾具／路徑問題，查明之前不准記成
`CERT_STALE`／`CERT_FRESH`」。查明結果：

`DECISION_20260904_R476_R461_CLOSING_ARBITER_DRIFT.md:1` 是**文件標題在引用標記**
（`……說「已原樣跑過」，但那之後工具被改了`），該文件全篇 **0 條** `python3 ops/` 指令行
⇒ 它不是認證段落。§二.1 的定義（標題行＋含標記）照字面收得到它。

**處置（這是量測之後新增的機制，照實標記）**：**定義一個字都不改**，改用
`ops/gain/data/r477_cert_exemptions.json` 人工分診名單，判 `TRIAGED_NOT_A_CERT`：

- 條目**不刪**、仍列在輸出裡，只是換一個判決名（memory：誤報要留在名單只加註「看過＝誤報」）。
- **原始數字永久保留**：`counts_raw` 欄位＋`ops/gain/data/r477_cert_drift_RAW_PREEXEMPT.json`
  （豁免機制存在**之前**跑的那一次，`verdict=BROKEN`、rc=2）⇒ 後輪要收回仲裁權隨時可以。
- **豁免只對 `BROKEN_NO_TOOLS` 生效**，碰到 `CERT_STALE` 一律拒絕並記 `exemptions_refused`
  （自檢 M6 專門釘這條；M7 關掉名單驗原始 `BROKEN` 會回來）。

## 10.3 自檢 12 條全綠（含真資料雙向校準）

```
A_realdata_negative_control_fresh   PASS  eq5_offline=['CERT_FRESH']
B_realdata_positive_control_stale   PASS  paired_ci=['CERT_STALE'] pooled=['CERT_FRESH']
C_not_all_one_box                   PASS  counts={'CERT_FRESH':2,'CERT_STALE':2,'TRIAGED_NOT_A_CERT':1}
M1_prose_inflates_headings          PASS  6 -> 12
M2_always_fresh_kills_stale         PASS  stale 2 -> 0
M3_stale_regex_is_broken_not_clean  PASS  rc=2 counts={'BROKEN_NO_TOOLS':3,'TRIAGED_NOT_A_CERT':1}
M4_no_docs_is_unscanned_not_ok      PASS  rc=2 verdict=UNSCANNED
D_rc_semantics                      PASS  base rc=1 spec=1 verdict=STALE_CERTS_PRESENT
E_no_live_reads                     PASS  live_run_reads=0
M6_exemption_cannot_silence_stale   PASS  stale 2 -> 2, refused=5
M7_without_exemptions_broken_returns PASS m7 rc=2 BROKEN_NO_TOOLS=1 == base counts_raw
M5_deleting_blob_compare_goes_red   PASS  刪掉後 rc=0 CERT_STALE_present=False（乾淨版 rc=1 有 STALE）
selftest SELFTEST_PASS 12/12
```

兩個**夾具缺陷**在路上被自己的擋門抓到，照實記：
1. `B` 原本用 `endswith("paired_ci.py")` ⇒ **連 `pooled_paired_ci.py` 一起吃掉**（改比 basename）。
2. `M5` 第一發 `BASELINE_BROKEN: 標記數 begin=2 end=2` ⇒ **搜尋標記的那兩行自己含有標記**
   （memory 的「用字串比對會匹配到自己」同型）。乾淨基線擋門擋住了，沒被誤記成「沒牙齒」。

## 10.4 接線（§八）與它自己的植入缺陷測試

`tests/test_cert_drift_gate_r477.py`，`python3 ops/run_tests_nopytest.py tests/...`：
**收集 3 個、3/3 PASS**（接線前該檔不存在＝收集 0）。測試裡**不寫死任何絕對數字**
（認證格數會隨附錄增減；寫死＝安靜衰減成永遠紅），只驗「偵測器有牙齒」與「rc 語意自洽」。

植入缺陷兩型，各跑一次（改的是**被測工具**，不是測試）：

```
[乾淨]        3/3 pass, 0 fail => PASS
[缺陷1 恆綠]  2/3 pass, 1 fail => FAIL      # blob 比對改成 elif False
[缺陷2 掃到0份] 1/3 pass, 2 fail => FAIL     # DOC_GLOB 改成掃不到 ⇒ 安靜量不到也要紅
[還原後]      3/3 pass, 0 fail => PASS      # 還原 sha256 前 16 逐字元相同
```

## 10.5 誠實邊界（收官不准漏）

1. **本擋門不取代 R476 的逐格重跑**：它只回答「該不該重跑」，不回答「重跑後數字一不一樣」。
2. **認證時刻是用 `git log -S<標題原文>` 反推的**，不是附錄自己記的 sha。
   ⇒ 若有人**改寫了認證標題的文字**，`-S` 會定位到改寫那次（較晚）⇒ 擋門會**低報** STALE。
   C-1′ 第 2 條（認證段落自己記 blob sha）就是為了拔掉這個反推，**但今天的擋門還沒有讀那個欄位**
   ——現存附錄都還沒有記 sha。**這是下一輪可做的事，不是今天已經做到的事。**
3. 掃描範圍只有 repo 根目錄的 `DECISION_*.md`（138 份）。`ops/` 底下的說明、`GAIN_STATE.md`、
   `SPEC_GAIN.md` 裡若有認證語句，**今天掃不到**（`docs_scanned` 有記，可事後核對）。
4. 主 run `runs/g_r461_lcb3_three_arm` **本輪零讀取**（`live_run_reads=0`），也沒有 `git add` 它。
