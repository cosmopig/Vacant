# R480（round751）：普查 R461 附錄裡最後三段沒被掃過的 —— A.4／B.3／G

**判準檔。工具與量測都在這個 commit 之後。** 上一輪（R479／round750）交棒指名的下一步：
「還沒被普查的是誰：R461 附錄 **A.4**（§二的預測對帳）、**B.3**（三個「命中不帶資訊」的警告）、
**G**（認證擋門）三段還沒被 R453 式普查掃過。其中 **B.3 與 G 都會被收官引用**。」

## 〇、合法性前提（逐條自證）

1. **主 run `runs/g_r461_lcb3_three_arm` 還在跑（PID 2895311）。本輪對它零分析。**
   工具內建硬擋門 G-LIVE：任何讀檔路徑含 `g_r461_lcb3_three_arm` 一律 `RuntimeError`，
   輸出必須帶 `live_run_reads=0`。B3-3 的重掃**具名排除**它，並另記 `runs_excluded_live`。
2. **本輪不是盲測。** 落筆前已讀過 A.4／B.3／G 的原文與 §二／§三 的原文
   ⇒ **不准宣稱 `blind_hit_rate`**。事前預測擋的是「量完再改預測」，不是「事前不知情」。
   （所有事前預測寫在本檔，本檔在工具之前 commit。）
3. **加法式**：§二／§三／§四／附錄 A–H 正文一個字都不改。若本輪有發現，
   另開附錄 I，且任何門檻／窗口／MDE／α／n／seed／worker／端點／bank 一個數字都不動。

## 一、被普查的 11 條

| id | 出處 | 原文宣稱 |
|---|---|---|
| A4-1 | A.4 第 1 列 | 事前預測「恰好 189 題」，實測 189 ⇒ HIT |
| A4-2 | A.4 第 2 列 | 事前預測「與 v2 零交集」，實測 overlap=0、union=309 ⇒ HIT |
| A4-3 | A.4 第 3 列 | 事前預測「日期 2023-05-07 → 2024-08-10」，實測逐字相同 ⇒ HIT |
| A4-4 | A.4 第 4 列＋內文 | 預測 medium 152／hard 37，實測 **135／54** ⇒ MISS；且「135+72=207、54+48=102 與 R460 逐字相同」 |
| B3-1 | B.3 第 1 點 | P-R461-3 綠燈基準率 **79.45%**（n=189、disc=19.17%、π=0.6087 下 p<0.05 的機率只有 20.55%） |
| B3-2 | B.3 第 2 點 | 數字級「38–52%」基準率 **14.09%**；判決級基準率 **30.07%**（30–60 佔 0–100）；矛盾帶共 **16.0pp** |
| B3-3 | B.3 第 3 點 | 「掃過 29 個 run，15 個臂（分佈在 9 個 run）真的超過 20%，最高 `g_off60_20260824` OFF 臂 60/60＝100%」 |
| G2-3 | G.2 第 3 點 | 收官引用任何被認證的數字之前，必須先跑 `cert_drift_gate.py` |
| G3 | G.3 | 釘死的輸出區塊：`docs=138 cert_headings=6`、`CERT_FRESH 2／CERT_STALE 2／TRIAGED 1`，以及「要先重跑那兩支」 |
| G4 | G.4 | `CERT_STALE` ≠「那個數字錯了」；反證＝`paired_ci.py` STALE 但 C.4 逐字重現 |
| G6 | G.6 | 自承「`cert_sha_mismatches = 0` 是**結構強制綠燈**，不准當『沒人改過標題』的證據」 |

## 二、分類規則（量測之前訂死）

每條吐四個獨立欄位，**不准合併**：

1. `clazz` ∈ {`EVALUABLE`, `FORCED_GREEN`, `UNRESOLVED`, `UNSCANNED`}
   - `FORCED_GREEN`：寫得出**恆等式**（用 `ast.get_source_segment` 逐字取真運算式或逐字取
     構造規則）證明它在任何資料下都成立，**且 witness 數＝0**。
   - `EVALUABLE`：找得到至少一個 witness（真實存在的、會讓它為假的狀態）。
   - `UNRESOLVED`：恆等式寫得出來但 witness 要等收官資料 ⇒ 照嚴格規則吐這個，
     **不准為了讓事前預測成真去湊條件式恆等式**（r718 規則）。
   - `UNSCANNED`：掃描目標 0 個（第三型「安靜量不到」）。
2. `executable_as_pinned`：**照附錄釘死的指令／出處**，那個量今天拿不拿得到。
   沒有任何釘死指令、也沒有任何工具會吐這個數字 ⇒ `False`（記 `no_emitter`）。
3. `premise_stale`：正文陳述的**原始碼／資料事實**今天還成不成立（散文版的 `CERT_STALE`）。
4. `intent` ∈ {`evidence`（收官拿來當佐證，強制綠燈要警告）, `guard`（防 infra，強制綠燈是設計如此）}
   —— **量測之前標**（r718 規則）。

另加 `reproducible_offline`：`executable_as_pinned=False` 的散文數字，本輪能不能用
獨立重算把它復現（容差寫死 **±0.5pp**，絕對數字要求逐字相同）。復現不了 ⇒ 記
`NUMBER_NOT_REPRODUCIBLE`，**不改原文**，只在附錄 I 記。

## 三、事前預測（`intent` 與四欄，量測之前）

| id | intent | `clazz` | `exec` | `stale` | 備註 |
|---|---|---|---|---|---|
| A4-1 | evidence | **FORCED_GREEN** | True | False | 我預測 `build_lcb_bank.py` 是 1:1 轉換、不過濾不去重 ⇒ 189=119+37+33 由輸入行數強制 |
| A4-2 | evidence | **FORCED_GREEN** | True | False | v3 的三個來源檔與 v2 的來源不相交 ⇒ task_id 零交集由構造強制；union=309=189+120 是恆等式 |
| A4-3 | evidence | EVALUABLE | True | False | 日期由資料內容決定，構造規則沒有釘日期 |
| A4-4 | evidence | EVALUABLE | True | False | 已記 MISS |
| B3-1 | evidence | EVALUABLE | **False** | False | 沒有任何工具吐 79.45%（只在散文裡）；預測可離線復現（±0.5pp） |
| B3-2 | evidence | EVALUABLE | **False** | False | 同上；**且我預測 14.09／30.07 至少一個復現不了**——照原文自己寫的規則「佔 0–100」，38–52 應得 14.0、30–60 應得 30.0 |
| B3-3 | guard | EVALUABLE | True | **True** | 重掃得到的 run 數今天必然 > 29（新 run 一直在生）⇒ 正文那三個計數過期 |
| G2-3 | guard | EVALUABLE | True | False | R479 已原樣跑過 |
| G3 | guard | EVALUABLE | True | **True** | R479 今天量到 docs=140／cert_headings=8、FRESH 3 ⇒ 釘死區塊過期 |
| G4 | guard | EVALUABLE | True | False | 反證是 R476／R479 兩次逐字重現 |
| G6 | guard | **FORCED_GREEN** | True | False | 原文自承；本輪只驗「自承標得對」 |

**命中率的分母是 11×3（class／exec／stale），不是 11。** `reproducible_offline` 另外報。

## 四、推翻條件（觸發了照實寫，不准當場補判準）

- **R-1**：任一條我預測 `FORCED_GREEN` 的，找得到真 witness ⇒ 記 MISS，**照 EVALUABLE 寫**。
- **R-2**：B3-1 離線復現與 79.45% 差 > 0.5pp ⇒ 記 `NUMBER_NOT_REPRODUCIBLE`，
  **不准反過來說原文錯**——先分「我的重算模型與原文不同」與「原文算錯」，兩個都寫。
- **R-3**：冒出第 12 類（判準沒預期到的）⇒ 照實寫、人眼確認、**不算進命中計數、不當場補判準**。
- **R-4**：若 G-LIVE 擋門觸發（`live_run_reads>0`）⇒ 整份 `verdict=BROKEN`，rc=2，本輪作廢。

## 五、自檢要求（缺一不可）

1. 乾淨基線每條一個 check。
2. 植入缺陷（`R480_MUTANT` env，**在被測函式內部生效**，不在模組層）：
   - M1 拿掉 G-LIVE 擋門 ⇒ 掃到主 run ⇒ 要 `BROKEN_LIVE_READ`（不是 crash）。
   - M2 掃描目標清空但擋門留著 ⇒ `UNSCANNED`（第三型安靜量不到的正對照）。
   - M3 刪掉 `UNSCANNED` 擋門且目標清空 ⇒ 不再叫（M2 的負對照）。
   - M4 恆等式證明器改成「什麼都判 FORCED」⇒ 校準擋門要叫（正對照＝已知恆假死碼、
     負對照＝自由統計量，**雙向**）。
   - M5 `reproducible_offline` 的容差改成無限寬 ⇒ 復現判定失去牙齒 ⇒ 要叫。
3. **突變字串照檔案裡的字元寫**，`old not in clean` 一律當 BROKEN。
4. 接進 `tests/`，接線本身要植入缺陷測試（恆綠一型、量不到一型）。

## 六、本判準**沒有**動的東西

§二／§三／§四 的窗口、門檻、MDE、α、n、seed、worker、端點、bank、A.4 的預測帳原文、
附錄 B／C／D／E／F／G／H 的任何一行。**一個數字都沒有動。**
