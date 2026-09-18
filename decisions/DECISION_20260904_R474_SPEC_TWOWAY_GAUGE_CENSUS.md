# R474（round744）：把可證偽性／植入缺陷普查的範圍從 R461 擴大到 **SPEC_GAIN 自己引用的尺**，
# 並補「壞樁方向」的全庫掃描

**判準寫在量測之前，本檔與量測結果分開 commit。**
接 R473（round743）交棒第 2 點：「R472 §一 的清單只涵蓋 R461 這一份預註冊；
還沒被普查的是 R459 §十二 與 SPEC_GAIN 自己引用的尺 ⇒ 值得做的是**擴大清單**，不是加深已覆蓋的那幾支。」

**合法性前提**：`runs/g_r461_lcb3_three_arm` 還在跑（PID 2895311）。
**本輪對它不跑任何分析工具**（只 `wc -l`／`sha256sum`／讀 `summary.json` 的 `run_complete`／`run_terminal`
做進度同步），也**不讀它的 probe 落盤紀錄**——本輪要的那個數字一律**離線從 bank 檔重新導出**，
理由是「重新導出」比「引用該 run 自己的紀錄」更硬，且不動它的目錄。

---

## §一 清單怎麼導（機械，可重跑）

```bash
grep -noE "(ops/gain/|vacant/|tests/)?[a-z_0-9]+\.py" DECISION_20260904_R459_R447_SETTLEMENT.md SPEC_GAIN.md
sed -n '11,23p' DECISION_20260904_R459_R447_SETTLEMENT.md    # R459 §〇「先驗尺再信數字」實跑的五支
```

已知（**唯讀源碼檢視，在本檔落筆之前完成，因此不是預測，是記錄**）：

- R459 §〇 實跑五支：`r447_mutation_check.py`／`r447_schema_precheck`／`calls_audit`／
  `receipt_chain_audit`／`r447_gauge_capability`。
- SPEC_GAIN 具名四處：`ops/gain/gain_run.py`、`vacant/codebench.py`（V/GT 分離的釘子）、
  `vacant/entrycost.py`（`reviewer_correlation`）、`tests/test_pulse.py::test_defect_budget_actually_binds`。
- `ops/gain/verify_lcb_bank.py` 與 `ops/gain/check_bank_precision.py` **`grep -c selftest` ＝ 0**
  ——bank 驗收這條線上，兩支尺都沒有任何自檢。

## §二 本輪挑的那一個洞（判斷，不是量測）

SPEC_GAIN §「自我驗證」寫死：**「量具雙向驗證每次正式跑之前都要做：官方參考解要全過、壞解要全擋。
任一方向不滿分就停。」** 實作是 `gain_run.probe_instrument()`（:200–253）。

源碼事實（唯讀，已確認）：

```python
covered = [t for t in tasks if refs.get(t["task_id"])][:sample]   # :227
for t in covered:
    ok_good, _ = meets_demand(ref,  hidden, ...)     # 正方向：要過
    ok_bad,  _ = meets_demand(stub, hidden, ...)     # 反方向：要擋
```

**兩個方向共用同一個 `covered` 濾網。** 但反方向的樣本是
`def <entry>(*a, **k): return None` 這個樁——**它不需要參考解**。
於是「壞解要全擋」這半邊的覆蓋率被一個只有正方向才需要的條件壓到跟正方向一樣低。

這正是「安靜量不到」的第三型（掃描掃到的目標數比實際少）。它遮住的失效模式是
**「hidden_check 什麼都判通過」**——那會同時抬高三條臂、長得跟天花板效應一模一樣，
而天花板效應正是這個實驗一開始就卡住的東西（LOOP_PROMPT 開頭）。

**本輪要做的**：造 `ops/gain/r474_stub_sweep.py`，對指定 bank 的**每一題**餵同一個樁，
分類每一題的 `hidden_check` 與 `visible_check`，零 API、只讀 bank 檔、不碰任何 run 目錄。

**不動的**：`gain_run.py` 任何一行（`probe_instrument` 的口徑本輪不改，只量它的盲區）、
R461 的任何門檻／窗口／MDE／α／n／seed／worker／端點／bank、任何既有落盤資料。

### §二.1 事前寫死的分類（三類，不准事後合併）

| 類 | 條件 | 意義 |
|---|---|---|
| `STUB_REJECTED` | 樁跑完、`meets_demand` 回 False，且失敗訊息**不是**載入／語法級錯誤 | 這一題的反方向有證據 |
| `STUB_ACCEPTED` | 樁回 True | **缺陷**：這一題對任何東西都放行 |
| `CHECK_UNUSABLE` | 檢查式本身壞掉（樁與**任何**輸入都不可能過的 harness 級錯誤，例如檢查碼語法錯／import 失敗／逾時） | **不是**綠燈，要單獨數 |

**判準（事前）**：`STUB_ACCEPTED == 0` 且 `CHECK_UNUSABLE == 0` 才算反方向在該 bank 上滿分。
`CHECK_UNUSABLE > 0` 不准算進 `STUB_REJECTED`——那就是把「量不到」寫成「量到 0」。

### §二.2 事前寫死的誠實邊界（收官不准漏）

樁掃描是**單邊**保證：它能抓「什麼都判通過」，**抓不到**「什麼都判失敗」。
後者只有正方向（要參考解）能抓，而 lcb3 的參考解只有手寫的那幾題。
⇒ 本輪的產出**不能**寫成「lcb3 的量具雙向驗證已達 100%」，只能寫成
「反方向覆蓋率從 N/189 提到 189/189，正方向仍是 N/189」。

## §三 事前預測（量測前寫定；對錯都照實記）

| # | 預測 |
|---|---|
| P1 | 離線重算 lcb3 的 `covered`（`sample=0`＝全驗）⇒ **12** 題（記憶裡的 12/189；若不是 12，照實記並更正記憶） |
| P2 | 189 題的 `hidden_check` 樁掃描：**`STUB_ACCEPTED == 0`** |
| P3 | 189 題的 `hidden_check` 樁掃描：**`CHECK_UNUSABLE == 0`** |
| P4 | `visible_check` 存在的題數 == **189**（每題都有），且其 `STUB_ACCEPTED == 0` |
| P5 | 新尺自帶自檢：合成夾具「什麼都判通過的 check」⇒ 必須被判 `STUB_ACCEPTED`；「正常 check」⇒ `STUB_REJECTED`；「語法壞掉的 check」⇒ `CHECK_UNUSABLE`（**不准落進 `STUB_REJECTED`**）。三格全中才算尺有牙齒 |
| P6 | 植入缺陷測試（外部、源碼級突變，跑在 worktree 上）：把「`CHECK_UNUSABLE` 這一類整段刪掉、併進 `STUB_REJECTED`」⇒ 自檢必須**紅**且**指名**是 `unusable` 那一條；crash 收場記 `BROKEN`，不算 caught |
| P7 | 現存 `ops/gain/*.py` **沒有**任何一支已經在做全庫樁掃描（`grep` 樁字面 `return None` ＋ `\[:sample\]` 導出）⇒ 本輪不是重造輪子 |
| P8 | 新增可調參數 **0**：樁的字面、合格線（全對才過）都沿用 `probe_instrument` 的既有口徑，`ast` 掃新檔的模組層數值常數只准是「重跑用的路徑／類名字串」 |

## §四 推翻條件（觸發了就照實寫，不准當場補判準去修）

- **R1**：P2 或 P3 被推翻（有題目放行樁，或檢查式壞掉）⇒ **這是 lcb3 題庫的缺陷，直接影響正在跑的
  `g_r461_lcb3_three_arm`**。做法是：把 task_id 逐個列進 `GAIN_STATE.md` **最上面**、
  寫進本輪 commit，**不准**自己改 bank、不准中止那個 run（改 bank 會讓已跑的列與未跑的列不同尺）。
- **R2**：P5 任何一格沒中 ⇒ 尺沒有牙齒，本輪記失敗、不得引用 P2/P3/P4 的數字當結論。
- **R3**：P1 若不是 12 ⇒ 記憶裡「真實覆蓋率 12/189」過期，要在 STATE 寫更正，且不得回頭改本檔。
- **R4**：若樁掃描期間 `g_r461_lcb3_three_arm` 的 `rows.jsonl` 行數不再增加或 `infra_void` 由 0 變正
  ⇒ 記為「本輪的本機 CPU 佔用可能污染了那個 run」，照實寫進誠實邊界（開跑前後各量一次行數）。

## §五 誠實邊界（本檔即寫死）

1. 本輪是**補上偵測**與**擴大普查範圍**，不是找到 R461 數字的缺陷。
2. 樁掃描是單邊保證（§二.2）。
3. 本輪的本機 subprocess 用量（189×2 次沙箱執行）與 r738–r743 的突變測試同級；
   量測前後各記一次 live run 行數當守恆量（R4）。
4. §一 的清單擴大到 R459 §〇 ＋ SPEC_GAIN，**仍未涵蓋** R440Z／R450／R452 等更早的預註冊
   所引用的尺——下一輪的盲點在那裡，本檔不假裝已經蓋完。
