# R465（round733）：R461 §六.2 的收官義務**也沒有可執行的仲裁者**——與 C-1／D.1 同型的第三次復發

**判準檔。先 commit 這一份，才開始任何量測。**
（memory 鐵律：判準要寫在量測之前；判準與結果分開 commit）

## 〇 合法性自證（缺一不可）

要動的是 `runs/g_r461_lcb3_three_arm`（20:19 UTC 發射、本輪全程活著、23 列／567 列）的
**收官報告義務**。修一份預註冊的收官路徑，只有在「還沒看過該假說的資料」時才合法。逐條自證：

1. **P-R461-1（OFF5−OFF）、P-R461-2（CONFORM−OFF）、P-R461-3（gate vs vote）的估計量，本輪零次讀取。**
   三條都是配對差值，需要 CONFORM／OFF5 臂的逐題結果。
2. **本輪對主 run 目錄的讀取只有**：`ls` 檔名、`wc -l rows.jsonl`（=23）、`wc -l calls.jsonl`（=60）、
   `ps` 的 PID／etimes。**沒有** `cat`／`json.load` 過它的 `rows.jsonl` 或 `summary.json` 任何一列。
   （對照 r732 的誠實揭露：那一輪因 dump summary 鍵而看到 n=4 的比率。**本輪沒有重蹈。**）
3. **本修正不動任何窗口、門檻、MDE、預測區間、α、n、seed、worker、端點、bank。**
   落在 R462 §六.4 事前授權的「與數字無關的缺陷（詞彙／死碼／缺仲裁者）」。
4. **加法式**：R461 §三／§四／附錄 A／B／C／D 原文一字不改，本輪新增**附錄 E**。
   `ops/gain/r447_gauge_capability.py` 本輪**一行都不改**（只跑它、驗它）。

## 一、缺口（由原始碼與判準檔正文確立，不是量測）

R461 §六.2 寫死了一條收官報告義務：

> 好解方向改用能力下界：閘門 run 跑完後，看有幾題**任一臂通過過一次**……
> 沒被示範的題數是**「量具假象」的上界**，不是「壞了幾題」。**這個數字要跟失敗率一起報。**

`grep -n "附錄" DECISION_...R461...md` ⇒ 附錄 B／C 覆蓋 P-R461-1／2，附錄 D 覆蓋 P-R461-3。
**§六.2 沒有任何附錄覆蓋，也沒有任何一行寫出它的指令。**

⇒ 這是 C-1（附錄 C：「預測有名字、沒有可執行的仲裁者」）與 D.1（附錄 D：同型）的
**第三次復發**，而且這一次漏掉的不是一條假說，是**量具自身效度的唯一佐證**——
R461 §六.3 已事前承認 v3 的 probe 覆蓋率預期 0/189，「參考解全過」那個方向**照字面不可執行**，
§六.2 的能力下界是唯一的替代品。它沒有仲裁者 ⇒ 收官時 SPEC 的雙向驗尺規則
**兩個方向都沒有可執行的證據**。

⚠ 本輪**不**主張 §六.2 的語意有問題，只主張它**沒有指令**。語意（`any(meets_demand)`）不動。

## 二、候選工具（本輪要驗的對象）

`ops/gain/r447_gauge_capability.py`（R450 造）。它的 `passed()`:89-92 是
`any(bool(r.get("meets_demand")) for r in rs)`，**逐字就是 §六.2 的「任一臂通過過一次」**；
`n_undemonstrated`／`pct_undemonstrated`:101-102 就是 §六.2 要報的那個上界。

**驗證 run 用 `runs/g_r447_conform_lcb2`**（已收官、同三臂 `OFF/CONFORM/OFF5`、同 LCB 家族、
同 worker `gemma-4-12b-it-qat`）＝ R461 的結構孿生。**照 R463 §一 C-1 新訂的通則：
收官指令寫進判準檔之前必須先原樣跑一次。**

## 三、擋門（判準不是 `rc≠0`）

- **B1** 工具以 traceback 收場（沒吐 `verdict` 字串）⇒ 該筆記 `CRASH`，
  **不算「偵測到」**（memory：植入缺陷測試 crash 收場不算偵測到）。
- **B2** 本輪任何一次讀取 `runs/g_r461_lcb3_three_arm` 的 `rows.jsonl` 內容或 `summary.json`
  的判決量 ⇒ 整輪判 `SEQUENTIAL_PEEK`，附錄 E 不准寫，照實記進 GAIN_STATE。
- **B3** `--selftest` 不是 `SELFTEST_PASS` ⇒ 照實報，**本輪不准順手修工具**
  （改碼要另開判準）；附錄 E 仍可寫，但必須帶「自檢當時是紅的」但書。
- **B4** 掃描到的列數為 0 ⇒ 該筆 `UNSCANNED`（第三型「安靜量不到」），不准降成「通過」。

## 四、要查的五筆（**清單寫在量測之前，不准事後增刪**）

| 代號 | 問題 | intent |
|---|---|---|
| **Y1** | `--selftest` 現在是綠的嗎 | guard |
| **Y2** | 在結構孿生 `g_r447_conform_lcb2` 上跑得起來嗎、`verdict` 是什麼、`n_tasks_complete` 多少 | evidence |
| **Y3** | 它有沒有 R464 那型**旗標預設值陷阱**（`--bank` 之類、忘了帶就安靜翻掉判決） | guard |
| **Y4** | 它的 `_deliv` 與 P-R461-1／2 收官尺 `paired_ci.py --key deliv` 的 `deliv` **是不是同一個布林函式** | evidence |
| **Y5** | **run 沒跑完就跑它會怎樣**：有沒有 `run_complete`／列數擋門，還是安靜吐 `OK` 配一個小分母 | guard |

## 五、事前預測（**誠實標註哪幾筆不是盲測**）

⚠ 寫本檔之前，我為了決定要不要採用這支工具，已經**逐行讀過** `r447_gauge_capability.py` 全文
（246 行）。所以 **Y3／Y5 是「確認已知」不是盲測**，記 `CONFIRMATORY`，**不准計入命中率**。
Y1／Y2／Y4 在寫本檔時尚未量過，是盲測。

| 代號 | 事前預測 | 盲？ |
|---|---|---|
| **Y1** | `SELFTEST_PASS`、rc=0（12 條 ck 全綠，含 M1／M2／M4／M5／M6 五個突變體） | 盲 |
| **Y2** | `verdict=="OK"`、`n_tasks_complete==120`、`n_tasks_partial_excluded==0`、`window_doubt_triggered==false` | 盲 |
| **Y3** | **沒有**旗標預設值陷阱：`main()`:230 只吃 `sys.argv[1]` 當 run 目錄，**零個** `--bank`／`--seed`／`--n`，題目來源完全不介入 ⇒ R464 那型翻不了它 | CONFIRMATORY |
| **Y4** | 兩者**同一個布林函式**（`accepted ∧ meets_demand`）⇒ §六.2 與 P-R461-1／2 口徑一致，不必在附錄 E 加口徑但書 | 盲 |
| **Y5** | **沒有**完整性擋門：把已收官 run 的 `rows.jsonl` 截成前綴（模擬跑到一半）餵給它，會吐 `verdict=="OK"` 配一個**小很多的** `n_tasks_complete`，且**不發任何警告** ⇒ 收官守則必須自己加「`run_complete==true` 且 `n_tasks_complete==189`」 | CONFIRMATORY |

⚠ Y5 的截斷測試**只用 `g_r447_conform_lcb2` 的列**，不碰主 run（B2）。

## 六、推翻條件（觸發了照實寫，不准當場補判準）

1. **Y1 紅** ⇒ B3：照實報、本輪不修工具、附錄 E 帶但書。
2. **Y2 的 `verdict` 不是 `OK`**（例如 `BROKEN_BC_MISMATCH`／`BROKEN_CONTRACT_DRIFT`）
   ⇒ **這支工具現在就不能當 §六.2 的仲裁者**，附錄 E 只准寫「候選工具在結構孿生上是紅的」，
   **不准**改工具或改 §六.2 讓它變綠。
3. **Y4 若兩者不同** ⇒ 附錄 E **必須**寫明「§六.2 的能力口徑與 P-R461-1／2 的交付口徑不同」，
   並具名列出分歧格；**不准**為了對齊而改任一支工具的預設。
4. **Y5 若真的有擋門**（預測 MISS）⇒ 照實記 MISS，附錄 E 不用加那條守則。
5. 若量完之後我想「順手把 §六.2 的 50% 窗口疑慮門檻調一調」——**不准**。
   那是 R461 在沒看資料時訂的，本輪也沒看資料，沒有任何新資訊足以動它。
6. **本輪不對 R461 的三條假說下任何判斷，也不預測它們的值。**

## 七、本輪不做

不發射任何 run、不殺主 run、不 `git add` 主 run 目錄（未追蹤＝對 stash／checkout／reset 免疫）、
不改 `gain_run.py`（runner 改動對活著的 run 無效，且會動熱檔案）、
不改 `r447_gauge_capability.py` 一行、不改 `analyze_paired.py`／`replay/paired_gates.py` 的
`--key` 缺口（R463 刻意留的，仍在）、不改任何門檻／窗口／MDE／α／n／seed／bank、
不碰 1004／8765／8766 設定、不碰展件。

## 八、授權的 run 名（R440G 閘門）

本判準**不授權任何 `gain_run.py` 的 run**。純離線唯讀工具：
`ops/gain/r447_gauge_capability.py`（既有，不改）。
