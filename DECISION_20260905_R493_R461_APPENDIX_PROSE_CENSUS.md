# R493：R461 附錄 **內文宣稱**的可證偽性／過期普查（B.1／B.2／C.1／C.3／D.2／E.2／H.2）

**判準檔。量測之前單獨 commit。落筆時本輪尚未讀過 `paired_ci.py`／`pooled_paired_ci.py`／
`gain_run.py`／`r447_eq5_offline.py`／`r447_gauge_capability.py` 的任何一行原始碼**
（只讀過 R461 附錄的散文與 `wc -l`／`ls`）⇒ 下面 §三 的預測是**盲的**。

## 〇 為什麼是這一輪、為什麼是這一段

1. **主 run `g_r461_lcb3_three_arm` 仍在跑**（開場 06:52 UTC，rows 323/567，PID 2895311，
   照速率還要約 6 小時）⇒ 本輪不可能收官，但**收官會直接引用這些附錄**。
2. r718 通則：「做完普查要問**收官會引用誰**」。收官的仲裁者是 §四 ＋ 附錄 B.2／C.2／D.2／E.2／H.2，
   而 **附錄 I.6 與 J.6 連兩輪具名保留**：`B.1／B.2／C.1／C.3／D.1／D.2／E.1／E.2／F／H.2`
   的**內文宣稱**從來沒有被任何普查掃過。
3. **這一型缺陷已經現身兩次、都是被普查抓到的**：R479 抓到 `E3-1 premise_stale`
   （E.3 說 `r447_gauge_capability.py`「沒有任何完整性擋門」，R472 之後有三道）、
   R480 抓到 `G3 premise_stale`（`docs=138 cert_headings=6` 今天是 141／8）。
   ⇒ **散文會過期，而 `cert_drift_gate.py` 只比工具的 blob sha，看不見散文**。
4. **本輪刻意仍不掃 R486–R490**（J.6 §〇.4 具名保留，round764 也保留）。理由同 round764 且可反駁：
   那六份每一份都已自己宣告頭條不可引用，**不在收官引用路徑上**；本段在。
   ⇒ **R486／R487／R487B／R488／R489／R490 六份到現在仍然沒有被普查掃過，下輪交棒照寫。**

## 一、要掃的是什麼——**只掃「原始碼／repo 事實」型的宣稱**

附錄散文裡有三種句子，本普查**只掃第三種**：

| 型 | 例 | 本輪掃不掃 |
|---|---|---|
| 判斷／措辭約束 | 「散文一律寫『OFF5 − OFF 的 CI 完全在 0 以上』」 | ✗（沒有真值） |
| run 上的數字 | C.4 的 `+19.17pp` | ✗（已由 `cert_drift_gate.py` 以 blob sha 覆蓋） |
| **原始碼／repo 事實** | 「`pooled_paired_ci.py:242` 硬性要求 `len(--stratum)>=2`」 | **✓ 本輪** |

**理由**：第三種是**今天可以逐字驗、而且會安靜過期**的那一種；前兩種要嘛沒有真值、
要嘛已經有機制覆蓋。

## 二、17 條宣稱（id ／ 出處 ／ 判準）——**量測前釘死，量完不准增刪**

| id | 出處 | 宣稱（判準逐字化之後要檢的東西） | intent |
|---|---|---|---|
| `B1-1` | B.1 | `paired_ci.verdict()` 的字串字面詞彙表恰為 `{NON_INFERIOR_BUT_UNRESOLVED, ON_WINS, RULED_OUT, UNINFORMATIVE}` | evidence |
| `B1-2` | B.1 | `ops/gain/**/*.py` 全庫吐得出字面 `"OFF5_WINS"` 的 emitters ＝ `[]` | evidence |
| `B1-3` | B.1 | 同上，`"CONFORM_WINS"` 的 emitters ＝ `[]` | evidence |
| `B2-1` | B.2／C.2 | `paired_ci.py` 有 `--key`，且 **argparse default ＝ `meets_demand`**（舊語意） | evidence |
| `B2-2` | B.2／C.2 | `paired_ci.py` 吃 `--run`／`--a-arm`／`--b-arm`，且產物有頂層 `verdict` 鍵 | evidence |
| `C1-1` | C.1 | `pooled_paired_ci.py` **第 242 行**是 `len(strata)>=2` 的擋門；單一 `--stratum` 實跑 `rc=2` | evidence |
| `C2-1` | C.2 | `paired_ci.py` 內 `PRACTICAL_PP == 5.0` 且 `MIN_PAIRED == 60` | evidence |
| `C3-1` | C.3 | 分析路徑上 `deliv` 的定義是 `accepted ∧ meets_demand` | evidence |
| `C3-2` | C.3 | **`gain_run.py:588`** 是「拒交時回退到最後一份候選」那一行 | evidence |
| `C3-3` | C.3 | **`gain_run.py:1586`** 是「無條件對它評分」那一行 | evidence |
| `D2-1` | D.2 | `r447_eq5_offline.py` 的 `--bank` **argparse default ＝ `lcb2`** | evidence |
| `D2-2` | D.2 | `--seed`／`--n` 有「取自 run 自己的 `summary.json`」的退路（原始碼裡讀得到） | evidence |
| `D2-3a` | D.2 | 「全庫 **41 份** `summary.json`」——**份數**今天仍是 41 | evidence |
| `D2-3b` | D.2 | 「**沒有任何一份**記 `bank`」——實質宣稱今天仍成立 | evidence |
| `E2-1` | E.2 | **`r447_gauge_capability.py:89-92`** 的 `passed()` 是 `any(bool(r.get("meets_demand")) for r in rs)` | evidence |
| `E2-2` | E.2 | **`main()`:228-241** 只吃 `sys.argv[1]` 當 run 目錄，且**沒有** `--bank`／`--seed`／`--n` 任何旗標 | evidence |
| `H2-1` | H.2 | H-2／H-3 兩段釘死的 inline 指令今天在孿生 run `g_r447_conform_lcb2` 上原樣跑得起來，且重現 H.3 的 `CONFORM rows=120`／`格數=0`／`voided_tasks=0` | evidence |

**兩條校準控制（不算在 17 條裡，是擋門）：**

- `C_POS`：一條構造上為真的宣稱（`paired_ci.py` 是存在的檔）⇒ **必須 `VERIFIED`**。
- `C_NEG`：`C2-1` 的刻意錯版（`MIN_PAIRED == 999`）⇒ **必須 `REFUTED`**。
  只有正對照時「什麼都判 VERIFIED」也會全綠 ⇒ **雙向校準是必要的**（r718 通則）。

**分類詞彙**（每條同時記 `class` 與 `premise_stale`）：

- `class ∈ {EVALUABLE, FORCED_GREEN, UNRESOLVED, UNSCANNED}`
  - `FORCED_GREEN`＝這條宣稱在結構上不可能為假（要具名 witness 母體與 witness 數）。
  - `UNSCANNED`＝掃描器根本沒找到目標（第三型「安靜量不到」），**不是綠燈**。
- `premise_stale ∈ {True, False}`＝散文陳述的事實今天為假。
  ⚠ **`premise_stale=True` 不等於「結論錯了」**（同 `CERT_STALE` 的誤讀警告）：
  行號漂移多半只代表「引用時要重新定位」，實質語意可能沒變。
  ⇒ 每條 stale 都要另記 `substantive_change`（實質語意有沒有變），兩者分開報。

## 三、事前預測（**盲**，落筆時沒讀過那五支工具的原始碼）

**逐條 `premise_stale`：**

- 預測 **`True`（過期）3 條**：`E2-1`、`E2-2`、`D2-3a`。
  - `E2-1`／`E2-2` 的理由**不是猜**：附錄 H.1 自己記著「**R472 之後**
    `r447_gauge_capability.py` 已有三道擋門」，而附錄 E 是 round733 寫的、R472 在其後
    ⇒ 該檔在 E.2 落筆之後被加過碼 ⇒ `:89-92`／`:228-241` 兩組行號極可能已經位移。
  - `D2-3a` 的理由：「41 份」是快照型計數，`runs/` 今天有 216 個目錄
    ⇒ 同 R480 對 G.3 的判法（快照不是可重跑的宣稱）。
- 預測 **`False`（沒過期）14 條**：其餘全部，含 `C3-2`／`C3-3` 兩條 `gain_run.py` 行號
  （R492 明記該檔上一輪一個 byte 沒改）。
- **聚合預測：`2 <= n_premise_stale <= 5`。**（逐條全押 False 會與「10% 基準率×17 條」矛盾，
  這一條是把聚合信念也寫成可證偽的。）

**逐條 `class`：** 預測 17 條全 `EVALUABLE`，**沒有** `FORCED_GREEN`、**沒有** `UNSCANNED`。
（本輪自認**最可能錯的一條**：`B1-2`／`B1-3` 的 emitters — 「全庫沒有任何 .py 吐得出這個字串」
很可能是**構造強制綠燈**，因為那兩個判決名是 R462 憑空造出來的、本來就不存在於任何工具。）

**`substantive_change`：** 預測 **0 條**（行號漂移不改語意）。

## 四、推翻條件（觸發了照實寫，**不准當場補判準去修**）

1. `n_claims_scanned != 17` ⇒ `verdict=BROKEN_SCAN_COUNT`（第三型安靜量不到），不准報任何分類。
2. `C_POS != VERIFIED` 或 `C_NEG != REFUTED` ⇒ `verdict=BROKEN_CALIBRATION`。
3. 任何開檔路徑含 `g_r461_lcb3_three_arm` ⇒ `RuntimeError`；報告必須印 `live_reads=0`。
   （G-LIVE 硬擋門，盲測不得被破壞。）
4. 突變體未照預註冊行為 ⇒ 報 `BROKEN_MUTATION`，**不准宣稱本尺有牙齒**。
5. 若某條 `substantive_change=True` 且它會改變一條收官指令 ⇒ **本輪必須開附錄把指令補正**，
   不准只寫「注意一下」。
6. 若 `n_premise_stale` 落在 `[2,5]` 之外 ⇒ 聚合預測 **MISS**，照實記。

## 五、突變體（`r493_mutation_check.py`；**M1／M4／M5 是真的原始碼突變**，另存檔並驗 `old in src`）

| id | 突變 | 預註冊行為 |
|---|---|---|
| `M0` | 乾淨基線 | `verdict=CENSUS_OK`、17 條、校準雙向過 |
| `M1` | 把 `B1-1` 期望詞彙表裡的 `ON_WINS` 拿掉 | `B1-1` ⇒ `REFUTED`（其餘不動） |
| `M2` | 刪掉 `C_NEG` 控制 | `BROKEN_CALIBRATION` |
| `M3` | 拿掉 G-LIVE 擋門 | 證明擋門有牙齒（拿掉就讀得到主 run 路徑） |
| `M4` | 行號檢查改成恆真 | 事前預測為 stale 的 `E2-1`／`E2-2` 變 `premise_stale=False` ⇒ 看得見 |
| `M5` | 刪掉一條宣稱（16 條） | `BROKEN_SCAN_COUNT` |

⚠ r473 通則：檔內旗標型突變體答不了「把正式那行整段刪掉會不會紅」。
**M1／M4／M5 一律另存突變檔並先斷言 `old in src`**（memory：突變字串要照檔案裡的字元寫）。

## 六、本輪**不**做的

- 不收官、不讀主 run 任何檔、不起／不殺任何 run、不碰 `world/`／`design/`／`vacant_hm`。
- **不改 R461 附錄的任何一行原文**（本輪產物是加法式的附錄 K）。
- 不改 `paired_ci.py`／`pooled_paired_ci.py`／`gain_run.py`／`r447_eq5_offline.py`／
  `r447_gauge_capability.py` 任何一行——**本尺只讀它們**。
- 不動任何門檻／窗口／MDE／α／n／seed／worker／端點／bank。
- 不掃 R486–R490（§〇.4 具名保留）。

## 七、新增可調參數

**0 個。** 本尺沒有任何門檻旋鈕：每條宣稱是逐字比對或恆等式，`n_claims_scanned==17` 是
常數不是可調門檻。若實作時發現需要旋鈕，照實寫進附錄 K，不准假裝是零。
