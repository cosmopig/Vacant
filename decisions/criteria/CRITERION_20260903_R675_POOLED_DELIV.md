# R675 判準：併庫結算 P-E2／P-E3 的那條路，磁碟上沒有工具能走

**先寫判準再量測**（迴圈鐵律）。本檔在動任何一行程式碼、跑任何一次量測之前 commit。
零模型呼叫、零沙箱、**不碰 r445 的 run 目錄**（它活著；round673 §五）。

## 一、缺口是什麼——不是「想做得更好」，是「事前註冊的預測算不出來」

`DECISION_20260903_R445_CONFORM_BANK_EXTENSION.md` §二 註冊了兩條**必須併 371 題**才能結算的預測：

| 預測 | 內容 |
|---|---|
| P-E2 | 併 371 題後 95%CI **半寬 ≤ 3.0pp**（機械外推 2.64） |
| P-E3 | 併 371 題 discordant 對數 `n_d` 落在 **[20, 40]**（外推 27） |

磁碟上兩支候選工具都走不到：

1. **`ops/gain/replay/conform_settle.py`**：`--run` 只吃**一個** run 目錄，且 `settle()`
   在 `terminal=True` 時對 `summary.arms[a].accepted / accepted_and_meets_demand / leaked`
   做**逐列覆算的 exact 硬擋**（`conform_settle.py:240-246`）。把 r444+r445 的 rows 串成一個
   `--rows` 快照、卻只給得起一份 `summary.json` ⇒ 覆算必然對不上 ⇒ `Broken`。
   **這是它該有的行為，不是繞道的對象。** 本輪要**實測證明**它確實會擋（不是推理，見 §三 P0）。
2. **`ops/gain/replay/pooled_paired_ci.py`**：會併，但 `stratum_from_run()` 把量**寫死成
   `meets_demand`**（`pooled_paired_ci.py:107-110`）。CONFORM 是**拒交臂**，
   round670 §三 已裁定 P-C1 只由 **`deliv = accepted ∧ meets_demand`** 結算，
   `meets_demand` 在拒交臂上不是交付率。

⇒ 本輪的工作：把 `--key {meets_demand,deliv}` 接進 `pooled_paired_ci.py`，
**預設維持 `meets_demand` 以保回歸相容**，並補齊「安靜量不到」兩型的植入缺陷測試。

**不新增估計量、不新增可調參數**：`deliv` 的定義逐字取自 `conform_settle.py:270`
（`accepted ∧ meets_demand`），合併仍是同一條加法恆等式 `Σ(b−c)/Σn`，
區間仍呼叫 round656 已雙向驗證的 `paired_ci.diff_ci`。

## 二、自我約束（違反就是本輪失敗，不准事後放寬）

- 新增可調參數（門檻／旋鈕）**＝ 0**。`HET_ALPHA`、`MIN_PAIRED`、`ALPHA`、`PRACTICAL_PP` 一個都不准動。
- 預設行為（不帶 `--key`）**不得改變任何數字**。
- 不碰 `runs/g_r445_conform_mbpp_ext/`（唯讀都不做寫入）；fixture 一律建在 `/dev/shm/r675`。
- 不 `git add` r445 的 run 目錄（run 活著時未追蹤＝對 stash/checkout/reset 免疫）。

## 三、事前預測（先寫死，量完照實填，兩個方向都不准當場改判準）

| # | 預測 | 不成立代表什麼 |
|---|---|---|
| **P0** | `conform_settle.py` 餵「兩 run 串接的 rows ＋ 單一 summary」＋`terminal=True` ⇒ **BROKEN** | 若它安靜通過，代表 §一 的 exact 覆算擋門有洞，那是比本輪更嚴重的問題，本輪立刻停下來寫進 STATE |
| **P1** | `--key meets_demand`（預設）在 r444 上的輸出，與改動前版本**只差兩處**：新增的 `"key"` 欄位、`third_category_missing_meets_demand` 改名。**其他每一個路徑逐位元相同** | 預設路徑被動到 ⇒ 歷史數字不可比，改動必須回退 |
| **P2** | 把 r444 的 179 題**切成兩半**當兩層餵進去，pooled 的 `B/C/N/n_discordant/delta_pp/ci95_lo_pp/ci95_hi_pp` 與**單層跑全部**逐位元相同 | 合併不是加法恆等式 ⇒ 併庫這條路不能用 |
| **P3** | 造一個 `deliv ≠ meets_demand` 的 fixture（某題 `accepted=false, meets_demand=true`），兩個 key 給出**不同**的 `b`/`c` | `--key` 是裝飾品，沒接上 |
| **P4**（安靜量不到・型一） | rows 缺 `accepted` 欄位時 `--key deliv` 必須進 `broken_reasons`，**不准當 `False` 靜靜算過去** | 欄位消失會被誤讀成「大量拒交」＝方向性偏誤 |
| **P5**（安靜量不到・型二） | 某層配對數 `n=0`（該臂整層沒資料）必須進 `broken_reasons`。現行 `MIN_PAIRED` 只擋 pooled **總數**，一個空層會被另一層蓋過去 | 併庫會把「一個 run 掛了」偽裝成「樣本數夠」 |
| **P6** | 真資料（r444）上 `deliv` 與 `meets_demand` 的 `b/c/n` **預期相同** | round670 §六（`md ∧ ¬acc` 因 `codebench.py:664-673` 恆為 0）被推翻的訊號。**照實寫、人眼確認、不當場補判準**（r528 規則） |

**P6 是預期不是發現**：round670 §六 已裁定「deliv 與 meets_demand 同值是構造不是巧合」，
所以收官文字**不准**寫成「因為換了正確交付指標所以如何」。換 key 的價值是**防禦性的**：
判準指名哪個量，工具就要量哪個量，並且**驗證**這個巧合而不是假設它。

## 四、推翻條件（事前寫死）

- **P1 或 P2 任一不成立** ⇒ 併庫路徑不可用。r445 收官**只報新 192 題的乾淨檢定**，
  並在 `GAIN_STATE.md` 明寫「P-E2／P-E3 無法結算」，不准用別的算法硬湊一個數字。
- **P0 不成立** ⇒ 本輪停止改碼，改寫 `conform_settle.py` 擋門有洞的報告。
- 本輪**不預測 r445 的結果**，也不看 r445 的中途數字來調任何東西。

## 五、本輪不做什麼

- 不起任何 gain_run（SPEC_GAIN §7，一端點一 run）。
- 不殺、不催、不 `git add` r445。
- 不改 `gain_run.py`（實驗程式碼），只改分析側。

---

## 六、addendum（本輪中途加的——先聲明這是偏離 §三 的事前清單）

**這一節不是事前預測。** 它是在 P0–P6 量完之後、看到管路預演的輸出才決定加的，
所以**照 r528 的規則明寫出來**，不假裝它一直在判準裡。

**觸發它的觀察**：管路預演（r444 + r445 中途快照）印出兩層的 `conditions_sha.instrument`
**不相等**（`c5a9…` vs `a58c…`）。逐欄比對之後，兩個原因都是良性的：

1. `instrument.detail` 是**逐題**紀錄，兩層題目本來就不重疊（交集 0 題）⇒ sha 必然不同。
2. r445 多了 `visible_*` 四個欄位（round671 才接進去的可見閘門檢查），r444 跑的時候還沒有。

⇒ **`conditions_sha` 對 `instrument` 這一欄什麼都沒說**：不相等既不是問題也不是保證，
因為它保證會不相等。而工具的 docstring 早就宣告了一條納入規則
（「量具必須是修好之後的尺」），卻**只印 sha、靠人眼判斷**——收官那一次會有人
看到 sha 不等就恐慌，或者揮揮手放行。兩個方向都錯。

**改法**：換成機制導出的判別量——該層的量具必須**雙向滿分**
（`ref_pass == n` 且 `broken_rejected == n` 且 `n > 0`），不滿分就進 `broken_reasons`。
**新增可調參數仍然是 0**：合格線是 `== n`，`n` 由該層自己的量具紀錄導出，不是我挑的數字。

**代價（照實寫）**：§三 P1 的允許差異清單因此多了每層一個 `instrument_two_way` 區塊。
P1 的**實質保證沒有被放寬**——`changed == []`（任何一個既有值變了都會露出來）原封不動，
而且本輪用既有的 M3 突變（把合併寫成未加權平均）**實測證明它有牙齒**：
M3 之下 `changed = ['.pooled.delta_pp']`。

新增預測（同樣先寫再量）：P7 量具不滿分的層 ⇒ BROKEN／P7-M9 突變被抓／
P8 `summary` 沒有 `instrument` 區塊 ⇒ BROKEN（安靜量不到）／P9 r444 真資料雙向滿分。

## 七、量測結果（14/14，原始輸出 `runs/_analysis_r675/TEST_pooled_key.txt`）

| # | 結果 | 數字 |
|---|---|---|
| P0 | **成立** | `BROKEN: OFF5.accepted：summary=179 vs 逐列覆算=358`，rc=2 |
| P1 | **成立** | 新增路徑全是 `.key`／`.instrument_two_way.*`／改名的新名，`值變了=[]` |
| P2 | **成立** | 兩半併＝單層全部，`B=9 C=4 N=179 n_d=13 Δ=+2.7933pp CI[−1.6597,+5.9419]` 逐位元相同 |
| P3 | **成立** | 造 6 格「符合需求但被拒交」：`meets_demand b/c=9/4` vs `deliv b/c=9/10` |
| P4 | **成立** | 缺 `accepted` ⇒ `第三類 179 題缺 accepted/meets_demand 欄位`，rc=1 |
| P5 | **成立** | n=0 的層 ⇒ `配對數 n=0…不是「沒有差異」`，rc=1（改動前**安靜放行**，實測過） |
| P6 | **成立（如事前所料）** | r444 上 `deliv` 與 `meets_demand` 的 B/C/N/Δ/CI 逐位元相同；`md ∧ ¬acc = 0`（537 列直接數） |
| P7/P8/P9 | **成立** | 見 §六 |

**四個突變全部被抓**：M6（`--key` 是裝飾品）、M7（缺欄位當 False）、
M8（空層放行）、M9（量具不滿分放行）。既有 round658/660 selftest 無回歸。

### 過程中真的抓到兩個 bug（不是演練，是本輪自己寫壞的）

1. `ok` 這個名字被量具區塊蓋掉 ⇒ `TypeError: 'bool' object is not callable`（會炸，好抓）。
2. `missing` 這個名字被量具區塊蓋掉 ⇒ **不會炸**：`n` 正確掉到 0，但
   `third_category_missing_fields` 被換成不相干的空清單 ⇒ 工具會報
   「這一層 n=0、但沒有缺欄位」＝**診斷是錯的**。P4 抓到了它。
   這正是「安靜量不到」該有的樣子：**不是沒印，是印了一個錯的**。
