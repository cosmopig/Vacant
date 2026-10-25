# DECISION 20261025：可見驗收的「方言缺口」——量測、釘住與 adapter 設計

> 狀態：**量測完成＋現行語義已釘住＋adapter 設計定案；adapter 本體未實作**（被 G1–G5 門擋住，見 §7）。
> 本輪交付：量測腳本、釘住測試、本文。不改任何產品行為。

## 0. 一句話

+9.7pp 的實測效果量在「有可見測試」的題集上，但**產品路徑今天跑不到那些測試**：
題庫的測試是 `*_test.py` ＋ unittest 方言，產品只認 `test_*.py` ＋ 頂層 `check_*`／`main`。
polyglot_py 34 題，產品可跑 **0/34**（其中 1/34 是工具檔誤中命名規則的**假陽性**）。
本輪把這件事量出來、釘住現行的誠實語義、定案 adapter 的設計與放行門。

## 1. 問題：三層缺口（全部有本地證據）

| 層 | 規則（現行代碼） | 題庫的形狀 | 結果 |
|---|---|---|---|
| **L1 命名** | `test_files()` 只收 `test_*.py`（`acceptance.py:223-233`）；`has_suite` 同 glob（`launcher.py:388-389`） | polyglot_py 的測試檔叫 `*_test.py`（如 `paasio_test.py`） | 33/34 題連套件都算「不存在」⇒ `no_suite` |
| **L2 方言** | 只執行頂層 `check_*`／`main`（`acceptance.py:250-264`；driver 對兩無的檔給 `driver_error`，見 `DRIVER_SRC`） | 全部 34 題是 unittest（`class …(unittest.TestCase)`） | 就算改名對上，也是「無 check_\* ⇒ 失敗」 |
| **L3 位置** | `--suite` 不可在工作區內（`launcher.py:289-296`，防篡改） | 測試檔躺在 `workspace/` 裡 | **規則正確，保留**。題庫的權威副本天然在工作區外（C37 harness 把 `workspace/` stage 進 run 目錄，原始目錄就是外面的那份），與 demo 的「複製一份進去」一致 |

量測（可重跑，含量具自證）：

```
$ python3 ops/ref/suite_dialect_gap.py ~/dev/Vacant
self-check OK（5 種檔案：check/unittest/改名/工具檔/混合，產品行為與手算一致）
family      題數   有測試檔   產品發現   產品可跑
dabench      30        0        0        0
dabstep      79        0        0        0
databench    30        0        0        0
polyglot_py  34       34        1        0
```

- 「產品發現 1」＝ `pg_paasio`：它的 `test_utils.py` 是**工具檔**（無測試、無 dialect），
  被 `test_*` 命名規則撿到 ⇒ 執行後一筆顯式 `driver_error` ⇒ 該題**永遠失敗**。
  這是假陽性發現，不是真訊號。
- 現行行為對這 34 題是**誠實的**：量不到就 `no_suite`／顯式失敗，**沒有假通過**——
  缺口是「沒有訊號」，不是「訊號說謊」。

**邊界（誠實）**：dabench/dabstep/databench 的本地題庫**沒有**測試檔（0/30、0/79、0/30）；
C37 的 run 裡它們有測試，是 harness 側帶的。harness 的 runner 代碼不在本倉庫
（遠端 `/srv/eval`），它是否也跑 unittest 方言**不是本地證據**，本文不以此立論。
本文量的缺口完全在本地：題庫測試檔 × 產品 acceptance 代碼。

## 2. 為什麼值得修

實測效果（離線重播 `c37_final.json` cap 3，`ops/ref/offline_restart_sim.py`，零 LLM）：

```
suite        units   pass@1  flag-restart  runs  test-restart  runs  oracle@k
polyglot_py    68    37.3%         47.0%  1.49         55.9%  1.93     55.9%
ALL           331    62.3%         66.4%  1.17         77.7%  1.56     78.2%
```

- +9.7pp（flag-restart，Vacant 自己的 flag 訊號）量在 polyglot_py＝**本題庫唯一帶
  可見測試的家族**。real-signal 主線（`DECISION_20261025_REAL_SIGNAL_RESAMPLE_DESIGN.md`）
  的方向 B 要的是「可見測試當真訊號、失敗就乾淨重抽」——但真訊號這條管道今天對這批題
  **不通**：裝了 Vacant，`vacant run` 對 34 題全是 `no_suite`。
- oracle@k 55.9% 仍是上限，不是產品效果；本文不引它作任何產品宣稱（ASSIGNMENT 紅線）。

## 3. 選項

| | 做法 | 判定 |
|---|---|---|
| **a. 方言 adapter（採）** | acceptance 多認 unittest 方言；命名規則**選擇性**擴充（§4.1） | 零新依賴（`unittest` 是 stdlib）、零新必設、現行 check 方言逐字不動 |
| b. 逐題 suitespec | 把每題的 unittest 翻譯成 `check_*` 套件 | 34 題 × 人手翻譯；題庫一長就崩；且翻譯本身就是第二套尺（H-8 的翻版） |
| c. 維持現狀、只寫文件 | 使用者自己改檔名＋改方言 | 等於把產品效果讓給「會改測試的人」；方向 B 落空 |

採 a。**命名層（L1）單獨不算一個選項**：只擴 glob 不接 adapter，會把 33/34 題從
「無訊號」翻成「顯式失敗」——語義變了但還是沒有訊號，純粹把誠實換成更吵的誠實。
命名與方言必須一起上。

## 4. adapter 設計（V1）

### 4.1 命名（L1）：選擇性，不改預設

- **V1 採 opt-in**：`--suite-naming both`（或 `VACANT_SUITE_NAMING=both`）時
  `test_files()`／`has_suite` 額外收 `*_test.py`。預設（`test_*.py` 只）**逐字不變**。
- 理由：擴 glob 會讓「目錄裡放著慣性 `x_test.py`」的既有使用者，套件從「不存在」
  變成「存在且失敗」——這是**既有行為改變**，違反本輪「無問題時與未安裝同形」的
  保守鐵律的延伸讀法。opt-in 把它變成一個明確的選擇，收據裡要留下這個旗標的值。
- 後路：若 G 門全綠且證據顯示題庫就是主流形狀，再論預設翻轉——那是下一次裁決，
  要單獨的 A/B 證據，不搭這輪的便車。

### 4.2 方言偵測（L2）：靜態、逐檔、四值

對每個被發現的 `.py` 檔做 AST 分類（不執行）：

| 分類 | 判據（頂層） |
|---|---|
| `check` | 有 `def check_*` 或 `def main`（現行） |
| `unittest` | 有 `import unittest`（含 `from unittest import …`）**且**有 `class … (unittest.TestCase)` 子類 |
| `mixed` | 兩類都有 |
| `none` | 都沒有（含 `test_utils.py` 這種工具檔） |

- `check`：照現行 driver，一個 byte 都不變（G3 用 sha256 驗）。
- `unittest`：走 §4.3 的新 driver 分支。
- `mixed`：**顯式 `protocol` 失敗**（fail-closed）。不猜、不拆半跑——一個檔案兩套
  語義，跑哪半都是猜。
- `none`：**維持現行的顯式 `driver_error`**（不靜默跳過）。理由：
  `test_files()` 的 docstring 已把這寫成產品哲學——「多跑了一個不是測試的東西」與
  「漏跑了一個測試」都會讓分數說謊。套件目錄是凍結在工作區外的（L3＋唯讀綁入），
  agent 執行中加減不了檔，所以「不跳過」沒有防篡改代價；跳過反而開一個
  「把失敗測試改名叫工具檔」的想像空間。題庫的 `test_utils.py` 是**題庫側的命名
  失格**，正解是題庫把 helper 改名成 `_support.py` 形狀（產品 docstring 已示範），
  不是產品替它兜底。

### 4.3 unittest 執行（新 driver 分支）

同一個沙箱、同一個 nonce 記錄協議、同一個對帳（`_reconcile`）：

1. import 測試模組（與現行 driver 同形：workspace 進 `sys.path`、stdout 捕獲）。
2. 宣告清單（靜態，父行程算）：AST 走頂層 `TestCase` 子類，每個 `test*` 方法
   記 `ClassName.method`。
3. 執行：`unittest.TestLoader().loadTestsFromModule(mod)` 逐 case 跑
   （`TestLoader` 的順序＝`dir()` 字典序，跨機器決定性 ⇒ I-6 成立）。
   `setUp`／`tearDown` 是 unittest 語義的一部分，照跑。
4. 每 case 一筆記錄：`case=ClassName.method`、`kind=pass|assert|exception|protocol`、
   `message`、`output`（截斷規則沿用）；尾上 `{"end": true, "ran": N}`。
5. 對帳沿用 `declared × reported`：**宣告了沒跑、跑了沒宣告、重複——任一即該檔失敗**
   （I-4：零案例的檔案＝失敗，不是「空＝過」）。

### 4.4 不變的東西（負清單）

- L3 防篡改規則**不動**（§1 表）。
- check 方言的 driver、對帳、回饋文字、落盤形狀：**逐字不動**（G3）。
- 沙箱：**同一個**（H-6 邊界不變：应用層加固，不是 OS 邊界）。
- 收據、chain、retry 迴圈：不碰。
- 依賴：只加 stdlib（`unittest`、`ast` 已在用）。**零新 runtime 依賴。**

### 4.5 明寫出來的邊界（adapter 落地後依然成立）

- **H-2 照樣**：過了 unittest 套件 ≠ 滿足需求；gauge 照樣要兩面（合成 reference 要過、
  已知壞 stub 要拒）。本地題庫沒有 reference 解 ⇒ gauge 用合成件。
- **H-8 照樣**：新 driver 分支是**新可信面**——driver 的錯會讓所有機器一致地錯，
  所以 G1 的自檢件要包含「driver 自己量得到自己的壞」。
- **無逐 case 逾時**（V1）：整檔逾時照舊（`test_timeout_s`）。一個 case 卡死會燒掉
  整檔預算——與現行 check 方言的形狀**對齊**（現行也沒有逐 check 逾時），不是新洞。
- **只認頂層**：巢狀 TestCase、`subTest` 展開、`setUpModule` 級 fixture 的宣告對帳
  不在 V1 的「宣告清單」內（執行照跑，宣告只數頂層 `test*` 方法）——與 check 方言
  「只認頂層」對齊。
- 檔尾 `unittest.main()`：import 時即跑 ⇒ `import` 失敗（誠實），不特殊處理。
  題庫 34 題無一如此（它們被當 library import）。

## 5. 釘住了什麼（本輪交付）

- `tests/test_visible_suite_dialect.py`（7 條，全綠）把**現行誠實語義**釘成測試：
  `*_test.py` 不可見 ⇒ `no_suite`／`ungated`；改名 `test_*` ⇒ 顯式 `driver_error`
  失敗；工具檔 ⇒ 同；check 方言對照組照樣過。
  ⚠ adapter 落地時這批測試**要依 G 門同步改寫，不准直接刪**——被刪的釘住測試
  等於把語義變遷藏起來（H-0 教訓的可執行版）。
- `ops/ref/suite_dialect_gap.py`（自檢＋題庫普查，落 `suite_dialect_gap.json`）：
  量具先自證（5 種檔案的手算對照），再量題庫。重跑即複核。

## 6. 放行門（全綠才准實作）

| 門 | 內容 | 驗法 |
|---|---|---|
| **G1** | adapter 自檢件：對的實作要過；已知壞 stub 要拒；零案例 unittest 檔＝失敗；`mixed`＝顯式失敗；工具檔（`none`）＝顯式失敗不跳過 | 新測試檔，含負向控制 |
| **G2** | **跨方言同意**：挑 ≥5 題，把 unittest case 人工翻成 `check_*` 版；同一份實作在兩方言下**同過同不過**；壞實作兩邊都要紅 | 翻譯對照表落盤（`ops/ref/`） |
| **G3** | check 方言回歸：`tests/test_vacant_run*.py`＋新釘住測試全綠；同一 check 套件的 driver 輸出 sha256 前後一致 | 現行測試＋digest 對照 |
| **G4** | 零新必設、零新 runtime 依賴（stdlib only）、預設行為逐字不變（`--suite-naming` 預設＝現行） | 代码審查＋`test_no_suite_*` 類測試綠 |
| **G5** | opt-in 下 `test_*.py` 與 `*_test.py` 都發現；helper 不跳過；`none` 方言＝顯式失敗；收據留下旗標值 | e2e 測試（do-nothing agent，零模型呼叫） |

## 7. 本輪做與不做

**做了**：量測（§1 表＋JSON）、釘住測試（§5）、本設計。commit 在 `auto/qwen27b`。
**不做**：adapter 實作（被 G1–G5 擋住，下一輪先做 G1 的自檢件與 G2 的翻譯對照表）、
L1 預設翻轉（§4.1 後路）、`dabench/dabstep/databench` 的測試缺口（本地題庫無測試檔，
無從量起；等 harness 側把測試檔進題庫再論）。

## 8. 證據路徑

- 量測：`ops/ref/suite_dialect_gap.py` ＋ `ops/ref/suite_dialect_gap.json`
- 釘住：`tests/test_visible_suite_dialect.py`（7 條）
- 效果數字：`ops/ref/offline_restart_sim.py` ＋ `ops/ref/c37_final.json`（cap 3；
  polyglot_py 68 units、ALL 331 units）
- 現行規則代碼：`vacant_network/vrun/acceptance.py:223-264`（`test_files`／
  `_declared_from_source`）、`DRIVER_SRC`（driver_error 分支）、
  `vacant_network/vrun/launcher.py:289-296`（L3）、`:388-389`（has_suite）、
  `:577-596`（no_suite/ungated）
- 上游決定：`decisions/DECISION_20261025_REAL_SIGNAL_RESAMPLE_DESIGN.md`（方向 B）
- 語義變遷先例：`decisions/` 內 H-0（`AGENTS.md` §7）——綠燈是忘傳旗標傳出來的，
  就是這個洞的成因；本輪的 G 門全部「預設＝現行」正是對這條的防禦。
