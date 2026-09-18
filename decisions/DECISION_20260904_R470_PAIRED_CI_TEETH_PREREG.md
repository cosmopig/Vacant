# R470：`paired_ci.py` 有沒有牙齒——R461 頭條數字的仲裁者，15 小時後就要用它

日期：2026-09-04（round740，Opus 5）。**判準寫在任何突變、任何量測之前。**
上游：`DECISION_20260904_R461_LCB3_REPLICATION_PREREG.md` 附錄 C.2、R462 普查、R738/R739
（同型工作：對「守某條語意的測試」問它看不看得見那條語意）。

## 一、為什麼是這一支、為什麼是現在

R461 附錄 C.2 把 P-R461-1／P-R461-2 的仲裁者**逐字**釘成：

```
python3 ops/gain/replay/paired_ci.py --run runs/g_r461_lcb3_three_arm \
    --a-arm OFF5|CONFORM --b-arm OFF --key deliv
```
判決取它印出來的 **`verdict == "ON_WINS"`**。

主 run `g_r461_lcb3_three_arm` 本輪 61/567 列，ETA 約 15 小時。**收官時這支工具吐什麼，
就是 R461 的頭條結果。** 而 R468 掃過的 `tests/` 45 個模組裡，**沒有任何一個檔提到
`paired_ci`**（`grep -rln paired_ci tests/` ＝ 空）⇒ 它的保護全靠散在 `ops/gain/` 的自檢。

**本輪要答的問題：那組自檢看得見「收官會引用的那幾行」嗎？**

## 二、偵測器集合（**先定義，量測之前**）

「偵測到」＝下列任一支在該突變體底下由綠翻紅。集合封閉，量完不准追加。

| 代號 | 指令 | 基線（本輪開場實測，主工作區唯讀） |
|---|---|---|
| D1 | `python3 ops/gain/replay/paired_ci.py --selftest` | rc=0，A–E 全過 |
| D2 | `python3 ops/gain/replay/r463_key_teeth_test.py` | rc=0 |
| D3 | `python3 ops/gain/replay/pooled_paired_ci.py --selftest` | rc=0 |
| D4 | `python3 ops/gain/r462_r461_census.py --selftest` | rc=0，ALL PASS |
| D5 | **真資料回歸見證**：附錄 C.4 的兩條指令在**已收官的** `runs/g_r447_conform_lcb2` 上重跑，逐欄比對 C.4 釘死的數字 | 見 §五-3 |
| D6 | `python3 ops/gain/replay/conform_settle_ci_selftest.py --run runs/g_r444_conform_mbpp` | rc=0，10/10 PASS |

**D5 的期望值出自 R461 附錄 C.4 原文（`git show HEAD:` 取，不是本輪重新產生的基線）**：

```
CONFORM vs OFF  n=120  b=31 c=8  Δ=+19.17pp  CI[+8.80,+26.46]  p=0.0003  ON_WINS
OFF5    vs OFF  n=120  b=22 c=7  Δ=+12.50pp  CI[+3.12,+19.19]  p=0.0081  ON_WINS
```
比對欄位：`n_paired, b_discordant_a_only, c_discordant_b_only, delta_pp,
ci95_lo_pp, ci95_hi_pp, p_mcnemar_exact, verdict`（pp 取 2 位、p 取 4 位）。

### 事前排除的一支（**照實寫，不是忽略**）
`ops/gain/replay/test_pooled_key_r675.py` **在基線就是紅的**（13/14，rc=1）：它的 P1
需要 `--before <基線 json>`，沒給就直接記 FAIL。**基線已紅的東西不能當偵測器**
（它的訊號已飽和，任何突變底下都是紅）⇒ 本輪把它排除，並在交棒具名寫出這個坑：
**「少給一個選用旗標」與「真的有缺陷」在 rc 上長得一模一樣。**

## 三、突變體（源碼級，**不是 env 旗標**）

⚠ `paired_ci.py:296` 的 `MUTANT` **只在 `__main__` 才從 env 讀**（`MUTANT = ""` 在模組層）
⇒ 被 import 時 env 旗標**永遠不生效**，長得跟「偵測器沒牙齒」一模一樣（memory 記過的形狀）。
所以本輪一律**改源碼**：在 `git worktree` 的副本裡逐字替換，每次 `finally` 還原並驗 sha256。

| # | 改什麼（逐字替換） | 事前預測 | 理由 |
|---|---|---|---|
| M1 | `_pi_ci`：`if MUTANT == "M1":` → `if True:`（Clopper-Pearson 換常態近似） | **DETECTED**（D1） | 自檢條 C 逐格比 McNemar |
| M2 | `diff_ci`：`if MUTANT == "M2":` → `if True:`（漏乘 `n_d/n`） | **DETECTED**（D1、D6） | D6 有具名的 M2 條 |
| M3 | `verdict`：`ON_WINS` 與 `RULED_OUT` 兩個 return 互換 | **DETECTED（只有 D5）** | D1 從不呼叫 `verdict`；D4 用 ast 取詞彙表，**詞彙沒變** |
| M4 | `verdict`：`if lo_pp > 0:` → `if lo_pp >= 0:` | **MISSED（全部）** | 邊界只在 `lo_pp == 0` 時分得開，r447 的 lo=+8.80 |
| M5 | `verdict`：`if lo_pp > 0:` → `if hi_pp > 0:`（區間只要碰到正值就宣告贏） | **MISSED（全部）** | r447 兩格本來就 `ON_WINS`；**這是最危險的一個**：它把 `NON_INFERIOR_BUT_UNRESOLVED` 讀成 `ON_WINS` |
| M6 | `main`：`if n < MIN_PAIRED:` → `if n < 0:`（拆掉 BROKEN 擋門） | **MISSED（全部）** | r447 n=120 ≥ 60，擋門本來就不觸發 |
| M7 | `main`：`b`／`c` 兩行的 `A`/`B` 互換 | **DETECTED（只有 D5）** | Δ 變號 |
| M8 | `_resolve_key`：`if os.environ.get("MUTANT") == "M_KEY":` → `if True:`（`--key` 變裝飾品） | **DETECTED**（D2） | R463 就是為它寫的 |
| M9 | `n_needed`：`for m in range(n,` → `for m in range(1,` | **DETECTED**（D1） | 自檢條 E 驗 m-1 不達標 |
| **N1**（負對照） | `main`：`b = sum(1 for t in common if ...)` → `b = len([t for t in common if ...])`（語意等價） | **MISSED（全部）** | 校準支點：證明偵測器不是亂紅 |
| **B1**（壞掉對照） | `diff_ci` 裡插一行語法錯 | **BROKEN**（不准判 DETECTED） | 校準另一個方向：看得見「安靜量不到」 |

## 四、總判決規則（**先寫死，不准量完再挑**）

- `HAS_TEETH`：M1–M9 **每一個**都被至少一支偵測器抓到，且 N1 MISSED、B1 BROKEN。
- `PARTIAL_TEETH`：有 MISSED 的突變體，但 N1 MISSED 且 B1 BROKEN。
- `NO_TEETH`：M1–M9 有 ≥5 個 MISSED。
- `BROKEN_CALIBRATION`：N1 被判 DETECTED，**或** B1 被判 DETECTED。
  ⇒ 整份普查作廢，上面三格一個都不准引用。

**「DETECTED」的定義不是 `rc≠0`**（memory 鐵律）：要指名**哪一支偵測器、哪一條檢查**變紅；
B1 那種 import／語法失敗一律歸 BROKEN。D5 的 DETECTED 要指名**哪一個欄位**對不上。

## 五、前置條件（不過就停，不准往下讀任何判決）

1. worktree 乾淨基線：D1–D4、D6 全綠（rc=0）。
2. 每次替換後 `finally` 還原，主工作區 `ops/gain/replay/paired_ci.py` 的 sha256
   開場與收尾**逐字元相同**。
3. **D5 的乾淨基線必須逐欄重現 C.4 那八個數字。** 對不上就代表 C.4 的釘值已經過期
   ——那本身是本輪的頭條發現，要停下來寫，不准繼續拿它當偵測器。

## 六、推翻條件（觸發了照實寫，不准當場補判準去修）

- 若 M4／M5／M6 其中任何一個**被抓到**：本輪「`verdict()` 與 BROKEN 擋門沒有任何自檢覆蓋」
  這個前提就是錯的，要照實寫「我猜錯了」並具名寫是誰抓到的。
- 若 N1 被抓到：見 §四，整份作廢。
- 若 D5 基線對不上 C.4：見 §五-3。
- **事前預期會多冒出一類**（P5/P7 慣例）：冒出來就人眼確認、照實寫、**不算進 P1–P6 的計數、
  不當場補判準去修**。

## 七、本輪**不做**什麼

- **不改任何產品碼。**（本輪只在 worktree 副本裡突變，主工作區產品碼一個字不動。）
- 不碰 `runs/g_r461_lcb3_three_arm`：不殺、不 `git add`、不對它跑任何分析工具。
- 不改 R461 §三／§四／附錄 B–F 的任何門檻、判決名、預測區間。
- 不 `git stash` / `checkout -- .` / `reset --hard`（live run 落盤檔在工作目錄）。
- **不因為「發現 verdict 沒被覆蓋」就當場補測試**——補不補是下一輪的判斷，
  本輪只負責把「有沒有牙齒」量出來。

## 八、事前預測表（收官對帳用）

| # | 預測 |
|---|---|
| P1 | 乾淨基線 D1–D4、D6 全綠，且 D5 逐欄重現 C.4 八個數字 |
| P2 | M1、M2、M8、M9 → DETECTED，且抓到的是 §三 指名的那一支 |
| P3 | M3、M7 → DETECTED，**且只有 D5**（D1–D4、D6 全綠） |
| P4 | **M4、M5、M6 → MISSED（六支偵測器全綠）** |
| P5 | N1 → MISSED |
| P6 | B1 → BROKEN（不是 DETECTED） |
| P7 | 會多冒出一類事前沒預期到的 |
| P8 | 主工作區產品碼 sha256 全程不變 |

**總判決預測：`PARTIAL_TEETH`**（因為 P4 預測有三個 MISSED）。
