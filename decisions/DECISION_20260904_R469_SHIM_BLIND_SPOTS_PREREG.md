# R469 判準（事前）：修掉量具 `run_tests_nopytest.py` 的三個盲點，並讓自檢對它們長出牙齒

日期 2026-09-04 UTC 21:5x　輪次 round737　模型 Opus 5（預設，無 NEXT_MODEL）
**本檔在跑任何量測之前 commit。** 量測與修復是另一個 commit。

---

## 〇 為什麼是這一件（取捨，這是判斷不是量測）

主 run `runs/g_r461_lcb3_three_arm` 還要 ~16h（44 列／189×3）。本輪是空窗輪。

r736 交棒七件裡，#5 與 #6 指向**同一個檔**（量具替身 `ops/run_tests_nopytest.py`），
而且是同一種病：**量具的能力邊界會把「量不到」印成「紅的」或「零收集」**。

- #5：`pytest.importorskip` 沒實作 ⇒ `tests/test_equal_budget_rules_r446.py`
  **收集 0**。那支是**鐵律 1（等預算）**唯一的單元測試，R446 收官結論
  （round700：+4.04pp CI [+0.80,+6.53]）在這台**從來沒有被它驗過**。
- #6：`parametrize` 對**單一 argname ＋ list 值**綁錯（`["up","--help"]` 綁成 `"up"`）
  ⇒ 8 條**偽紅**，而 §五 的雙向自檢對它發綠燈。

順手第三個（r736 表格裡的最大宗，但交棒沒點名）：**`capsys` 不在 `BUILTIN`**
⇒ 18 條 SHIM ERROR 橫跨 `test_cli_eco` / `test_cli_run` / `test_trace`。

放棄的：#1（`hard_fail`）、#3 的瀏覽器面、#4、#7 的修測試。理由同 r736：
**#1 保護未來的 run 不保護 R461**；而修 `tests/` 裡的**測試本身**要等量具可信之後
才有意義——現在紅的裡面有多少是偽紅還不知道，先修測試等於在壞尺上施工。

**本輪不改任何產品碼、不改 `tests/` 底下任何一個檔。** 只改量具與量具的自檢夾具。

---

## 一 三個修法（語意先寫死，實作要照這個語意）

| # | 盲點 | 現行行為 | 要改成 | 依據 |
|---|---|---|---|---|
| F1 | `parametrize` 單 argname + list 值 | `vals` 是 list ⇒ 被 `zip` 拆開，只綁第一個元素 | **`len(pnames)==1` ⇒ 整個值原樣綁定，不拆**；`>1` 才 unpack | 真 pytest 的規則就是「看 argnames 個數」，不是「看值是不是序列」 |
| F2 | `pytest.importorskip` | `pt` 上沒有這個屬性 ⇒ import 期 AttributeError ⇒ IMPORT_ERROR、收集 0 | 匯入成功回傳 module；`ImportError` ⇒ 丟 `Skipped`（＝ SKIP 一條，不是 ERROR） | pytest 語意 |
| F3 | `capsys` | 不在 `BUILTIN` ⇒ 印 `需要這支撐不住的` 並記 ERROR | 加進 `BUILTIN`，提供 `.readouterr()` 回 `(out, err)`，function scope 每條測試重置 | pytest 語意 |

**⚠ F1 是唯一會改變既有測試判決的一項**（F2/F3 只是把 ERROR 變成可執行）。
F1 若把某條原本 PASS 的測試變 FAIL，**那是真發現不是回歸**——照實記，不准回頭改 F1 去讓它綠。

## 二 牙齒（沒有這節，上面三項就是三個沒被驗過的宣稱）

每一項都要在 `tests/shim_selfcheck/good.py` 加**正向夾具**，並滿足：

> **T：把新夾具原封不動餵給修復前的量具（`git show HEAD:ops/run_tests_nopytest.py`
> 放回同一個 import 環境跑），三項必須各自看得見——F1 ⇒ 至少 1 條 FAIL、
> F2 ⇒ 該模組 IMPORT_ERROR 或收集數掉、F3 ⇒ 至少 1 條 ERROR。**

memory 的規則照用：**驗牙齒的實驗是「拿掉修復會不會 FAIL」**，比 env 旗標突變體硬；
**修前修後對照一律 `git show HEAD:<path>`，⛔ 不要 `git stash`**（主 run 的落盤檔就在工作區）。

**⚠ F1 的夾具要避開套套邏輯**：不准寫成「斷言 shim 綁對了」這種只有新語意才寫得出來的式子。
要寫成**兩種語意給出相反答案**的最小例子：單 argname 餵 `["up","--help"]`，
斷言 `argv == ["up","--help"]`——舊語意綁成 `"up"` 必 FAIL，新語意必 PASS。
同時**保留**一條多 argname 的夾具（`"a,b"` 餵 `(1,2)`）確認 F1 沒有把 unpack 這一路弄壞。

**自檢的寫死數字要一起改**（`good` 的 `n`/`ok`、`bad` 的 `n`/`fail`/`ok`）。
memory：**加完夾具要看 PASS「總數」有沒有變，不是看有沒有變紅**——
若 `n` 沒有跟著新增的夾具數上升，就是夾具被安靜漏收，判 BROKEN。

## 三 事前預測（對帳表在收尾逐條寫 HIT/MISS/UNRESOLVED）

| # | 預測 | 怎麼算 REFUTED |
|---|---|---|
| P1 | F1 之後 `test_cli_eco.py` 那 **8 條 UNCLASSIFIED 偽紅**至少 6 條不再是 FAIL | 少於 6 條改善 ⇒ 那 8 條不是（只是）parametrize 造成的，要重新分類 |
| P2 | F2 之後 `test_equal_budget_rules_r446.py` 收集數 **≥ 8** 且不再 IMPORT_ERROR | 仍收集 0 ⇒ F2 沒解決真正的阻塞 |
| P3 | 承 P2，該模組**全部 PASS**（0 fail 0 error） | 有任一 fail ⇒ **這是本輪最重要的發現**：鐵律 1 的單元測試在這台是紅的，要單獨開一節寫，並判它屬 SHIM／STALE／REAL 哪一類 |
| P4 | F3 之後三個 capsys 模組的 **18 條 SHIM ERROR 全部消失**（變 PASS 或 FAIL，但不再是「撐不住」） | 還有 capsys 造成的 ERROR ⇒ F3 不完整 |
| P5 | 牙齒 T 三項全部看得見 | 任一項在舊量具上照樣綠 ⇒ **該夾具沒有牙齒，該項修復等於沒被驗過**，要照實寫「F<n> 未驗證」 |
| P6 | 端點吞吐**沒有**單調衰退：把 `calls.jsonl` 依 `ts_ms` 切 4 個等量桶，逐桶 `completion_tokens / (latency_ms/1000)` 的中位數，**不會**單調下降且末桶 ≥ 0.7×首桶 | 單調下降且末桶 < 0.7×首桶 ⇒ 端點真的在退化，ETA 上升有物理原因，要升級 fable 並寫進交棒 |
| P7 | 會**多冒出一類**現在沒預期到的東西（memory 規則：事前就要預期它） | 沒冒出來就記 MISS；冒出來要**人眼確認、不算進上面任何計數、不當場補判準去修** |

**基準率（沒有基準率的「支持」是空洞綠燈）**：P5 的反面不是稀有事件——
r736 記錄過「乾淨 PASS、植入缺陷仍 PASS」在這個 repo 真實發生過（`test_off5_votes_on_behavior_not_source_text`），
所以 P5 是真的有可能 REFUTED，不是構造恆真。

## 四 擋門（違反就停）

- **B1 主 run 免疫**：不殺 `g_r461_lcb3_three_arm`、不另起 gain_run、
  **不 `git add` 它的目錄**（未追蹤＝對 stash/checkout/reset 免疫）。
  ⛔ 全程不准 `git stash` / `git checkout -- .` / `reset --hard` / `pull --rebase --autostash`。
- **B2 判準與結果分開 commit**：本檔先進 git，量測結果後進。
- **B3 不改產品碼、不改 `tests/`**：本輪只准動 `ops/run_tests_nopytest.py`、
  `ops/run_tests_selfcheck.py`、`tests/shim_selfcheck/*`。
- **B4 自檢通過才信任何測試結果**：`run_tests_selfcheck.py` 沒過就不准引用本輪任何模組判決。
- **B5 P6 是唯讀**：只讀 `calls.jsonl`，零 API、不打 8765/8766 的寫入端點。

## 五 誠實邊界（事前寫）

1. 本輪**不會**讓 `tests/` 全綠，也不打算。目標是**讓紅的是真的紅**。
2. F2/F3 讓更多測試「開始執行」⇒ **本輪的 fail 數上升是預期中的、是進步不是退步**。
   交棒要分開寫「因為量具長出能力而新看見的 fail」與「原本就看得見的 fail」。
3. P3 若 REFUTED，本輪**只記錄不修**（B3）。修 R446 測試是下一輪帶著判準做的事。
4. P6 只用 `calls.jsonl` 的既有欄位離線算，**不重跑一秒**；`ts_ms` 依 memory
   是**呼叫結束時刻**，兩種假設（起始／結束）都算，取「負值 0 個」那個。
5. 本輪 `tests/` 全量重掃**會跟主 run 搶 CPU**（r736 實測污染過 ETA）⇒
   **本輪不重跑 45 個模組**，只跑受影響的那 8 個以內，且 ETA 觀測值本輪不更新。

## 六 推翻條件（觸發了照實寫，不當場補判準去修）

- 若 F1 讓**原本 PASS** 的測試變紅 ⇒ 逐條列出來，判「真發現」而不是回退 F1。
- 若牙齒 T 有任一項不成立 ⇒ 該項標「未驗證」，**不准**因為「看起來是對的」就當已驗。
- 若 P6 判端點退化 ⇒ 本輪不下「ETA 一定會繼續漲」的結論（4 桶的解析度撐不起趨勢外推），
  只寫「有／沒有訊號」＋桶值。
