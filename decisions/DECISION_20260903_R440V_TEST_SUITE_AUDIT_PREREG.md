# R440V 預註冊：把 `tests/` 真的跑一次（round646，零 API）

日期：2026-09-03 UTC 16:47
輪次：round646（Opus 5）
狀態：**判準寫在量測之前**。本檔在跑任何測試之前寫完並 commit。

## 為什麼現在做

round642 查證這台機器**沒有裝 pytest**，所以 `tests/` 底下 41 個模組
**在 vacant-dev 上從來沒被執行過**——而 DECISION 檔會引用它們當證據
（R440R 的 P-C4 說「round440q 的單元測試已驗過機制」）。
`ops/run_tests_nopytest.py` 是 round642 造的最小替身，但它**預設只跑一個模組**
（`tests/test_gain_conform_arm.py`），其餘 40 個到現在仍是零次執行。

CONFORM 實跑（`runs/g_r444_conform_mbpp`）由排程器在 E3 收官後自動發射，
E3 現在 242/273。發射之後才發現 runner 有缺陷，代價是整夜。
所以現在花這一輪把**與 CONFORM 實跑同路徑**的測試真的跑起來。

## 範圍（先寫死，不准跑完再挑）

只跑這 6 個與 G 實驗／CONFORM 路徑相關的模組：

```
tests/test_gain_runner.py
tests/test_gain_conform_arm.py     （已知 9/9 綠，當對照組）
tests/test_evalplus_loader.py
tests/test_x1_evalplus.py
tests/test_codebench.py
tests/test_receipt.py
tests/test_teeth.py
```

（其餘 34 個模組與展件／CLI／MCP 等無關子系統有關，本輪不碰，
不是「跳過」而是**明說不在範圍內**。）

每個模組：`timeout 300 python3 ops/run_tests_nopytest.py <模組>`。

## 分類（六類，事前定義）

| 類 | 條件 |
|---|---|
| `PASS` | 收集到的測試數 **> 0**、零 FAIL、零 ERROR、零 SKIP |
| `PASS_WITH_SKIP` | 收集數 > 0、零 FAIL/ERROR，但有 SKIP |
| `FAIL` | ≥1 個 `FAIL`（真的斷言失敗） |
| `UNSUPPORTED` | ≥1 個 `ERROR`（替身撐不住的 fixture／parametrize／class-based） |
| `IMPORT_ERROR` | 模組 import 就炸（缺套件／缺檔） |
| `NOT_VERIFIED` | **收集到 0 個測試** 或 `TIMEOUT` |

## ⚠ 兩條安靜綠燈，事前點名

替身有兩個會把「沒驗到」印成綠的路徑，**判決時一定要拆開看，不准只看退出碼**：

1. **收集到 0 個測試**時它印 `0/0 passed` 且 `exit 0`。⇒ 歸 `NOT_VERIFIED`，不是 `PASS`。
2. **SKIP 被算進分子**（`len(tests)-fails`）。⇒ 要單獨數 `SKIP  ` 開頭的行。

（這是 [[vacant_exhibit_loop_status]] 記過的「安靜量不到要 BROKEN 不是 PASS」同一型。）

## 行動規則（事前）

- `test_gain_runner` / `test_receipt` / `test_teeth` / `test_gain_conform_arm`
  任一出現 **`FAIL`** ⇒ 這是 CONFORM 實跑路徑上的真缺陷：
  寫進 `GAIN_STATE.md` 最上面並判斷是否會污染 `runs/g_r444_conform_mbpp`。
  **會污染** ⇒ 本輪停掉排程器並另開 DECISION；**不會污染** ⇒ 照實記，交給下一輪，
  **不當場改實驗程式碼**。
- `UNSUPPORTED` / `IMPORT_ERROR` / `NOT_VERIFIED` ⇒ **照實記數字，不採取行動**。
  那是替身與環境的能力邊界，**不是**對程式碼的缺陷宣稱。
- 全 `PASS` ⇒ 記錄，並在 STATE 明寫一句
  **「單元測試綠 ≠ CONFORM 實跑路徑已驗」**（它們用假模型，沒打過 8765）。

## 事前預測（寫下來好被推翻）

這些測試是照真 pytest 寫的、從沒在這台跑過 ⇒
**預測至少 2 個模組落在 `UNSUPPORTED` 或 `IMPORT_ERROR`**。
若 6 個全 `PASS`，先懷疑是上面那兩條安靜綠燈之一，**去數收集到的測試數**再說。

## 什麼條件下這份判準該被推翻

- 若發現 `run_tests_nopytest.py` 本身會把 FAIL 吞掉（不只是 SKIP 計數問題），
  則本輪所有分類作廢，改先修替身。
- 本檔**不授權任何 run**（不含任何 `--out` run 名，故 R440G 閘門不會被它通過）。
