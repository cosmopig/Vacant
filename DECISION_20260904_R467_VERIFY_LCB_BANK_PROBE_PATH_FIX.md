# R467（round735, 2026-09-04）：修 `verify_lcb_bank.py` 的 `PROBE_PATH` 寫死，並讓 R466 普查對歷史可重現

**本檔是判準，在跑任何量測之前 commit。** 量測結果另一個 commit。

## 〇 這一輪為什麼做這件（取捨）

`runs/g_r461_lcb3_three_arm` 還在跑（PID 2895311，本輪 `wc -l` 重算：
35 列／3403s ＝ 97.2 s/列 × 567 列 ≈ 15.3h、剩 ≈14.4h ⇒ UTC 9/05 ~11:35）。
空窗輪。round734 交棒點名四個候選，本輪選 **#1**（修 `PROBE_PATH`），理由：

- 它是**已經造成過一次誤讀的真缺陷**（round734 差點把 `0/189` 當成「v3 沒驗過尺」寫進收官），
  不是再疊一層普查；memory 的「報告工具與量具是兩件事」就是從這個缺陷長出來的。
- 它是**純報告工具**，`gain_run.py` 一個 byte 都不動 ⇒ 對活著的 run 零影響。
- 放棄的：候選 #2（普查附錄 B–E）、#3（`summary.json` 記 `bank`）、#4（`--key` 缺口）。
  三者原樣留在交棒清單。

**推翻條件（事前）**：若實作過程中發現 `verify_lcb_bank.py` 的覆蓋率數字有被任何
**收官路徑**（R461 附錄 C／D／E 的三支工具、`gain_run.py`）讀取，則本輪降級為「只寫報告、不改碼」
——因為那就不再是純報告工具。（B1 擋門會查。）

## 一 缺陷（round734 已查證，本輪為確認式引用）

`ops/gain/verify_lcb_bank.py:36` 把 `PROBE_PATH` 寫死成 `data/lcb_probe_solutions.json`，
:140 用它算 `probe_coverage`，**不隨 `--version` 改**。而 `gain_run.py:181` 對
`bank == "lcb3"` 走的是 `data/lcb_v3_probe_solutions.json`。兩檔的 task_id 不相交
⇒ `verify_lcb_bank.py --version v3` 的 `probe_coverage` **恆為 `0/189`**，
與量具實際的覆蓋率不符。**缺陷在報告工具，不在量具。**

## 二 修法（單一真相來源，不是再抄一份對照表）

不在 `verify_lcb_bank.py` 裡新寫一份 version→檔案 的對照，而是**從 `gain_run.py` 取**：

1. version→bank 名用 `gain_run.py:77` 那個字面 dict 的**逆映射**，以 `ast` 逐字取出後 eval
   （memory 鐵律：不准自己改寫一份）。
2. bank→probe 檔用 `gain_run.LCB_PROBE_SOLUTIONS_PATH` /
   `gain_run.LCB_V3_PROBE_SOLUTIONS_PATH` 這兩個常數本身。

⇒ 日後 `gain_run.py` 再加一個 bank，這支要嘛跟著對、要嘛**吵**，不會安靜錯。

**加法性**：輸出只**新增**鍵，既有鍵的值對 v1／v2 逐字不動；`hard_fail` 的組成不動
（覆蓋率照舊「只報告不排除」）。模組層 `PROBE_PATH` 名稱**保留**（`tests/test_lcb_bank_v2.py:20` 匯入它），
語意仍是「v1/v2 的解檔」。

新增鍵：`probe_solutions_path`（實際讀的檔）、`probe_bank_name`（對應的 `--bank` 值）。
理由：`12/189` 這種數字單看無法判斷是哪個檔算出來的——把出處印在旁邊，
下一輪不必再去讀原始碼才能解讀。

## 三 R466 普查的耦合（本輪必須一起處理，否則留下安靜的壞掉）

`ops/gain/r466_r461_sec2_sec6_census.py:52` 把 `PROBE_PATH = ...` **那一整行原始碼字面**
存成 `SOURCE_CLAIMS` 的契約常數，`check_pins()` 對 **worktree 的 HEAD 版**做 `in` 比對。
本輪一改那行，重跑 R466 會吐 `source:probe_path_hardcoded` 的 drift。

**這是對的行為（大聲壞掉，不是安靜壞掉），但會讓一份已收官的歷史普查變成不可重現。**
修法：`SOURCE_CLAIMS` 的讀取**釘在它稽核的那個 commit**（`952f883`，R466 量測 commit），
用 `git show <pin>:<path>`，其餘讀取（bank 檔、判準檔）維持讀 worktree。
輸出新增 `source_pin`。**這是 memory「加法性對照要釘改動前的 commit 不是 HEAD」的直接套用。**

## 四 事前預測（**盲＝落筆時未量**；確認式另標，不計入盲測命中率）

| # | 預測 | 盲？ |
|---|---|---|
| P1 | 修好後 `--version v3` 的 `probe_coverage == "12/189"` | **確認式**（round734 交棒已寫 v3:0/12） |
| P2 | 修好後 `--version v1`／`v2` 的**每一個既有鍵**與修前 (`git show HEAD:`) 逐字元相同；差異只有新增鍵 | 盲 |
| P3 | v3 被覆蓋的 12 個 task_id ＝ `lcb_v3_probe_solutions.json` 的**全部** key（無孤兒 key，即該檔 key 集合 ⊆ v3 bank 的 id 集合） | 盲 |
| P4 | `--version v1`／`v2`／`v3` 三者修好後的 `sys.exit` 退出碼與修前相同 | 盲 |
| P5 | 重跑 R466（釘 commit 後）產出的 JSON，除新增的 `source_pin` 外與已 commit 的 `ops/gain/data/r466_census.json` **逐鍵相同**（含 `blind_hit_rate`、`class_counts`） | 盲 |
| P6 | `tests/test_lcb_bank_v2.py` 在 `ops/run_tests_nopytest.py` 下**收集數不減**且全過 | 盲 |

**P3 的推翻條件**：若該檔有 key 不在 v3 bank 內（孤兒），照實寫成 MISS，
**不准當場改判準去修**——那代表手寫解檔與 bank 之間另有一個沒被任何尺看見的缺口，
要寫進交棒而不是本輪吞掉。

## 五 植入缺陷測試（判準寫「偵測器該看到的那個量」，不是 `rc≠0`）

自檢腳本 `ops/gain/r467_selftest.py`。突變體由 `R467_MUTANT` 環境變數選擇，
**一律在被測函式內部生效**（memory：寫在模組層的突變體永遠不生效，長得跟「沒牙齒」一樣），
且與正式腳本同一個 import 環境。

| 突變體 | 植入什麼 | 判準：偵測器該看到的量 |
|---|---|---|
| M1 `hardcode_v1v2` | `probe_path_for()` 無視 version、恆回 v1/v2 檔 | `--version v3` 的 `probe_coverage` 變回 `"0/189"` |
| M2 `always_v3` | 恆回 v3 檔 | `--version v2` 的 `probe_coverage` 變成 `"0/120"` |
| M3 `report_mismatch` | 回報的 `probe_solutions_path` 與**實際讀的**檔不一致 | 一致性斷言吐 `PROBE_PATH_REPORT_MISMATCH` |
| M4 `bad_inverse` | version→bank 逆映射寫死成恆等（`v3`→`v3`）而非 `v3`→`lcb3` | 取映射時 `KeyError` 被轉成 `PROBE_BANK_MAP_BROKEN`，**不是**安靜 fallback |
| M5 `drop_source_pin` | R466 的 `SOURCE_CLAIMS` 讀回 worktree（不釘 commit） | R466 的 `drift` 含 `source:probe_path_hardcoded` |

**M3 的夾具紀律**：報告值與實際讀取值**必須分別取得**——報告值取自輸出 JSON、
實際讀取值取自被 monkeypatch 的 `open`／讀檔側記錄。若兩者同源，這條擋門結構上不可能被看見
（memory r695：夾具若把 B 從 A 導出，一致性擋門任何夾具都看不見）。

**M4 的必要性**：`bad_inverse` 檢查的是「安靜 fallback」這一類——若實作寫成
`MAP.get(v, "lcb")`，M1/M2/M3 三個突變體**都抓不到**它，因為 v1/v2 照樣對、v3 也剛好…
不對。所以 M4 要單獨存在，且判準要求**吵**（具名錯誤），不是回一個預設值。

**額外一條（memory r706）**：若某突變體之下 `verdict` 不變，就把「突變後 verdict 不變」
本身釘成該格的判準，不要沿用「verdict 必須改判」——否則是「乾淨 PASS／植入缺陷仍 PASS」的假測試。

## 六 擋門

- **B1（不准碰活著的 run）**：本輪不讀、不寫、不 `git add` `runs/g_r461_lcb3_three_arm`。
  對主 run 的存取只允許 `wc -l` 與 `ps`。
- **B2（不准改實驗程式碼）**：`ops/gain/gain_run.py`、`ops/gain/brain_cline.py`、
  `vacant/codebench.py`、`ops/gain/data/lcb_bank_v*.jsonl`、
  `ops/gain/data/lcb*probe_solutions.json` 本輪**一個 byte 都不改**（收尾用 `git diff --stat` 驗）。
- **B3（不准改門檻／窗口／α／n／seed／worker／端點／bank）**。
- **B4**：判準（本檔）與量測結果分開 commit。

## 七 收尾義務

1. 六條預測逐條對帳，**盲測命中率單獨算**，MISS 照實寫。
2. `git diff --stat` 貼進 `GAIN_STATE.md`，證明 B2 成立。
3. 推完驗遠端 sha 與本地逐字元相同。
4. 若 P5 為假（R466 重跑對不上），**不准改 R466 去湊**——寫進交棒。

---

# 附錄 A（量測後追加；§一–§七 原文一字未改）

## A.1 六條預測對帳

| # | 預測 | 實測 | 對帳 |
|---|---|---|---|
| P1 | `--version v3` 覆蓋率 `12/189` | `12/189`（`lcb3` / `lcb_v3_probe_solutions.json`）| HIT（**確認式，不計盲測**）|
| P2 | v1／v2 既有鍵逐字相同、差異只有新增鍵 | 兩者既有 16 鍵**值差異 0**；新增恰 4 鍵 | **HIT（盲）** |
| P3 | v3 覆蓋的 12 個 id ＝ probe 檔全部 key、無孤兒 | 孤兒 0、`covered == keys`、\|covered\|=12 | **HIT（盲）** |
| P4 | 三個 version 退出碼與修前相同 | 修前 0/0/0、修後 0/0/0 | **HIT（盲）** |
| P5 | R466 重跑除 `source_pin` 外逐鍵相同 | 唯一差異 `+/facts/pins/source_pin_commit`；`verdict=OK`、`blind_hit_rate=5/5`、`class_counts` 不變 | **HIT（盲）** |
| P6 | `test_lcb_bank_v2.py` 收集數不減**且全過** | 收集數 13→13（不減 ✓）；但**修前修後都是 12/13、1 紅** | **MISS（盲）** |

**盲測 4/5 命中（P2/P3/P4/P5 HIT、P6 MISS）**；P1 為確認式，不計入。

## A.2 P6 為什麼 MISS —— 這是本輪最有價值的副產物

`test_unknown_version_rejected` 斷言 `LiveCodeBenchLoader(version="v3")` 要拋 `ValueError`。
那是 **v3 還不存在時寫的**；round728 把 v3 建成真的 bank 之後這條就**過期**了
（memory 的三分法：**測試過期**／替身缺能力／真缺陷 —— 這是第一類，`AssertionError` 不是 `AttributeError`）。
載入器本身沒壞：`version="v99"` 照樣拋 `ValueError: 未知的 LCB bank 版本：v99（可用：['v1','v2','v3']）`。

**它從 round728 起一直是紅的，沒有人看見** —— 因為這台沒裝 pytest，`tests/` 長期沒被真的跑過。
用 `git show 7a9cd84:` 取修前版重跑，紅的是同一條 ⇒ **與本輪改動無關，是既有的**。

**本輪的越界動作（照實記）**：修了這條測試（`v99` 取代 `v3`，並加一句釘住「v3 現在合法」）。
判準 §六 B2 的禁改清單裡**沒有** `tests/`，所以不違反 B2，但**也不在本輪預先宣告的範圍內**。
理由是語意的、不是結果導向的：該測試的意圖（未知版本要被拒收）原樣保留，只是換一個真的未知的版本；
留著一條已知過期的紅燈，會讓 P6 這種「收集數＋全綠」的判準永遠不可能成立。
**P6 仍記 MISS，不因為事後修好就改判。**

## A.3 §五 M5 的判準寫錯了 —— 記 MISS，不當場補判準

§五 M5 原文：「R466 的 `drift` 含 `source:probe_path_hardcoded`」。**實測 MISS。**
真正漂移的是 `source:coverage_uses_probe_path` 與 `source:coverage_expr` 這兩條（main() 裡的），
`probe_path_hardcoded` **沒有**漂移 —— 因為 `PROBE_PATH = ...` 那一行本輪**刻意保留**
（`tests/test_lcb_bank_v2.py:20` 匯入它），只是不再拿去算覆蓋率。

落筆時沒想到「被修掉的是使用端、不是宣告端」。**§五 M5 原文不改**（後輪要收回仲裁權）；
自檢腳本改釘語意上正確的量，**並且把「為什麼那條沒漂移」也做成一條斷言**
（斷言那行字面今天仍在 worktree），免得下輪把「沒漂移」誤讀成「偵測器沒牙齒」。
突變體的牙齒本身沒有問題：`verdict` 確實變成 `SOURCE_DRIFT`。

## A.4 實作過程中被真的跑出來的一個 bug（推理推不出來）

`ast.get_source_segment` 取出的 `_default = (A if cond else B)` 運算式，**不含原本包住它的括號**；
那個三元式跨兩行 ⇒ 直接 `eval` 吐 `SyntaxError: expected 'else' after 'if' expression`。
補一層括號再 eval。**這是跑第一次才看出來的**，不是想出來的
（memory 有同型紀錄：`regress.sh` 的 stdout 覆寫也是跑一次最小重現才看出來的）。

## A.5 自檢與擋門

- `ops/gain/r467_selftest.py`：**收集 33 條、失敗 0**（`SELFTEST_PASS`）。
  五個突變體各自被指名捕獲，判準都寫「偵測器該看到的那個量」：
  M1→v3 覆蓋率退回 `0/189`；M2→v2 變 `0/120`；M3→`PROBE_PATH_REPORT_MISMATCH`
  且**覆蓋率仍是 12/189**（證明只翻了回報側）；M4→`PROBE_BANK_MAP_BROKEN` 且
  **覆蓋率是 `null` 不是 `0/189`**；M5→`SOURCE_DRIFT`。
- `r466` 自檢：**16 條全綠**（收集數與 round734 相同，不是「沒變紅」而是**總數沒變**）。
- `ops/run_tests_selfcheck.py`：三向自檢通過（good 16/16、bad 9/11 被抓、empty 判 `NOT_VERIFIED`）
  ⇒ 才信 `run_tests_nopytest.py` 的綠燈。
- **B1**：主 run 全程只有 `wc -l`（35→41）與 `ps`；沒讀、沒寫、沒 `git add`。
- **B2**：`git diff --name-only` 對禁改清單八個檔**輸出為空**。
- **B3**：門檻／窗口／α／n／seed／worker／端點／bank 一個都沒動。
- §〇 的推翻條件**沒有觸發**：`grep -rn verify_lcb_bank --include=*.py --include=*.sh`
  在 `runs/` 之外**零命中** ⇒ 沒有任何收官路徑的程式讀它，確實是純報告工具。

## A.6 誠實邊界

- `ops/gain/data/r466_census.json` **刻意沒有重新產生**：它是 R466 的歷史產物，
  P5 已證明今天重跑能逐鍵重現它（＋一個新鍵）。留原檔比覆蓋掉更能對帳。
- 本輪**沒有**讓「接線不一致」變成 fail-closed（`hard_fail` 組成照 §二 承諾沒動）。
  M3／M1 之下 `rc` 仍是 0，只有 JSON 裡的 `probe_wiring_error` 會吵。
  **這是照判準走的取捨，但它留下一個真的缺口**：CI 式的「看 rc」用法會漏掉接線錯誤。
  要不要把它接進 `hard_fail`，留給下一輪另開判準 —— 不在本輪事後加。
- P1 是確認式（round734 交棒已寫 v3:0/12），**不計入盲測命中率**。
