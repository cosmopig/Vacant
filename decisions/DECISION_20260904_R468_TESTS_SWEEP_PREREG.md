# R468 預註冊：`tests/` 全量掃描——45 個模組在這台機器上到底有幾條是紅的

**輪次** round736（2026-09-04 UTC 21:30–）／模型 Opus 5
**這份判準在跑任何掃描之前 commit。量測結果另開 commit。**

## 〇 為什麼是這一件（取捨，判斷不是量測）

round735 交棒給了五個候選。本輪選 **#2（全量跑 `run_tests_nopytest.py`）**，
放棄 #1（`probe_wiring_consistent` 接進 `hard_fail`）、#3（普查附錄 B–E）、
#4（`summary.json` 記 `bank`）、#5（`--key` 缺口）——四者原樣留給後輪。

理由三條：

1. **#1 保護的是未來的 run，不是 R461。** R461 的 `--arms probe` 早就跑完
   （`runs/g_r461_probe_lcb3`），改 `hard_fail` 不會改變已發生的事。
2. **`tests/` 是已知的長期盲區。** 這台沒裝 pytest（round642 查證），45 個模組
   在這台上基本沒被執行過，而 DECISION 檔會引用它們當證據。round735 是**偶然**
   撞到 `test_unknown_version_rejected` 從 round728 紅到現在沒人看見——
   **偶然撞到一條，代表沒人知道總共有幾條。**
3. 這是**測繪**不是改碼：對活著的主 run 零影響面（見 §四擋門）。

## 一 範圍與不做的事

- **做**：`tests/*.py` 全部 45 個模組各跑一次，收集數／pass／fail／error／skip 逐模組落盤，
  失敗逐條按 §三 分類。
- **不做（本輪明文禁止，避免 round735 那種越界）**：**一條測試都不修、一行產品碼都不改。**
  本輪的產物是**一張地圖**，不是修復。修哪一條、要不要修，是下一輪帶著這張地圖再開判準的事。
  （round735 順手修了 `test_lcb_bank_v2.py` 雖不違規但是越界，已記在它自己的附錄 A.2。）

## 二 事前預測（落筆時零量測；`test_lcb_bank_v2.py` 除外——round735 已知 13/13，標為確認式不計盲測）

| # | 預測 | 判 HIT 的條件 |
|---|---|---|
| P1 | 模組總數 = **45** | 掃描器報的模組數 == 45 |
| P2 | **全綠模組數落在 18–30**（點估計 24） | 落在閉區間內 |
| P3 | 全庫收集到的測試總數落在 **300–520**（點估計 400） | 落在閉區間內 |
| P4 | **至少 3 個模組**收集數 = 0 ⇒ `NOT_VERIFIED` | ≥3 |
| P5 | 除 `test_lcb_bank_v2.py` 外，**至少再有 1 個模組**含 §三 判為 `STALE` 的失敗 | ≥1 |
| P6 | 失敗總條數中，`SHIM`（替身撐不住）**多於** `STALE`+`REAL` 之和 | 嚴格大於 |
| P7 | **主 run 的 `rows.jsonl` 行數在掃描前後只增不減，且該目錄不新增／不消失任何檔** | §四 B1 全綠 |

**P2／P3 是寬區間的點估計，命中不算多強的證據；P5／P6 才是這輪真的想問的問題。**
（P6 若成立 ⇒ 這批紅燈多半是量具能力邊界，不是產品壞了；若不成立 ⇒ 反過來，那更要緊。）

**事前聲明會多冒出一類**：依 memory 的通則，預期會出現我這四類都放不進去的失敗。
出現就照實記為 `UNCLASSIFIED` 並人眼列出，**不算進上表任何一格，也不當場補分類法去吸收它**。

## 三 分類法（**在看到任何一條失敗之前寫死**）

每一條 fail/error 歸入且僅歸入一類：

- **SHIM** — 替身缺能力。判準：例外型別是 `AttributeError`／`TypeError`／`NameError`
  且 traceback 最深的 frame 落在 `ops/run_tests_nopytest.py`；或
  `ModuleNotFoundError` 指向這台沒裝的第三方套件；或訊息明指 pytest 未支援特性
  （`conftest`／`autouse`／fixture 吃 fixture）。**⇒ 產品沒事，量具不夠力。**
- **STALE** — 測試過期。判準：`AssertionError`（或 `pytest.raises` 沒抛），
  **且** `git log` 顯示被斷言的那個產品契約在測試最後一次修改**之後**被**有意**改掉
  （要指出那個 commit）。**⇒ 測試該改，產品沒事。**
- **REAL** — 真缺陷。判準：`AssertionError`，且找不到 STALE 要求的那個「產品後來改了」的 commit
  ⇒ 現行產品碼與現行仍宣稱成立的契約不符。**⇒ 產品該修。**
- **ENV** — 環境／外部依賴：需要網路、需要 8765／1234 端點、需要 `runs/` 底下不存在的資料。
  （與 SHIM 分開，因為它不是替身的錯。）
- **UNCLASSIFIED** — 以上都放不進去。**必須具名列出，不得塞進最近的一格。**

⚠ **分類靠證據不靠印象**：判 STALE 一定要貼出那個 commit 的 sha；貼不出來就是 REAL 或 UNCLASSIFIED。
（memory：沒有基準率／沒有證據的「支持」是空洞綠燈。）

## 四 擋門（違反任何一條 ⇒ 本輪作廢重寫）

- **B1（主 run 免疫）**：掃描前後各記一次主 run 目錄的 `ls` 與 `wc -l rows.jsonl`。
  要求：檔案集合相同、每個檔只增不減、`rows.jsonl` 行數單調不減。
  **不 `git add` 該目錄；不 `git stash`／`checkout -- .`／`reset --hard`。**
- **B2（不改碼）**：收尾 `git diff --name-only` 對 `tests/`、`ops/gain/`、`world/`、
  `ops/gain/gain_run.py`／`brain_cline.py`／`codebench.py`／三個 bank jsonl／兩個 probe json
  **必須為空**。本輪只准新增 `DECISION_20260904_R468_*.md`、掃描腳本與其輸出、`GAIN_STATE.md`。
- **B3（不動實驗條件）**：門檻／窗口／α／n／seed／worker／端點／bank 一個都不准動。
- **B4（隔離）**：每個模組跑在**獨立 subprocess**、`timeout 120`、`TMPDIR=/dev/shm`。
  逾時的模組記為 `TIMEOUT` 並歸 `ENV`，不重試、不延長。

## 五 量具的量具（先證明掃描器會叫，再信它的綠燈）

跑掃描之前先跑 `ops/run_tests_selfcheck.py`（雙向自檢）。
**不滿足「good 全過、bad 被抓、empty 判 NOT_VERIFIED」就停手，不在壞尺上測繪。**

## 六 推翻條件（事前寫）

- 若 `run_tests_selfcheck.py` 不過 ⇒ 本輪降級為「只報告自檢失敗」，不出地圖。
- 若掃描過程中 B1 任一項違反 ⇒ **立刻停止掃描**，本輪只寫事故報告。
- 若某模組 import 時就會動到 `runs/` 或發網路請求 ⇒ 該模組記 `ENV` 並**跳過**，
  不為了湊完整度去改它。

## 七 誠實邊界（事前聲明）

- **本輪已經看過主 run 的一個估計量**：開場探索時跑了 `meets_demand` 的**全體**計數
  （未分臂）。這是**一次真實的偷看**，照實記在 `GAIN_STATE.md`，
  不因為「沒分臂所以不影響比較」就略過不寫。此後本輪不再讀 `rows.jsonl` 的任何欄位，
  只讀 `wc -l`。
- 這張地圖說的是「**這台機器上、用這支替身**跑出來的結果」，不是「pytest 會怎麼判」。
  替身的能力邊界寫在 `run_tests_nopytest.py` 的 docstring，SHIM 那一類全部繼承那個邊界。
