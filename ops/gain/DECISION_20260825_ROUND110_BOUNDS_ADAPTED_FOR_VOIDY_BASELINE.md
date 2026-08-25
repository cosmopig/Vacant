# round110：`analyze_void_bounds.py` 在 OFF vs ON（371 題）這組配對上直接跑會 BROKEN，原因與繞法

## 問題

round109 交棒寫「下一輪先跑區間法（`ops/gain/analyze_void_bounds.py`）」。
本輪照做，直接跑：

```
python3 ops/gain/analyze_void_bounds.py runs/g_on371_20260825 \
  --off-baseline runs/g_off371_20260825
```

結果：

```
BROKEN: OFF baseline 題目清單不完整（367 筆 / n=371）
```

## 為什麼

`analyze_void_bounds.py`（round77 寫）的前提是 `--off-baseline` 那個 run
本身 **complete=true、無 void**——它從 baseline 的 `rows.jsonl` 取
`arm=="OFF"` 的 task_id 當作「全題目清單」，並斷言這份清單長度必須等於
`summary.json` 的 `n`（見該檔 126–130 行）。這個假設在 round77 當時成立
（`g_off60_qwenonly_20260824` 是乾淨的 60/60）。

但本輪的 baseline `g_off371_20260825` 自己也有 4 個 infra_void（round94/109
已記錄），所以 `arm=="OFF"` 的 row 只有 367 筆，觸發這個斷言，腳本判
BROKEN 並直接返回——**不是腳本壞了，是它的前提在這組資料上不成立**，
沒有以修改 §7 或動態放寬斷言的方式繞過它。

## 繞法（不改動 `analyze_void_bounds.py`，另外手算）

同一套 round77 pre-registered 規則（規則 A：void-proof 區間排序；
規則 B：共同子集配對 McNemar），但全題目清單 `T` 改用「OFF baseline 的
attempted 總數」（measured ∪ void = 371，OFF 這邊剛好 371/371 attempted
只是 4 格沒量到），而不是「OFF 的 measured 清單」。ON 這邊的「未量到」
定義擴大為 `void ∪ 尚未開始跑的題目`——這兩者對區間法而言是同一件事
（結果未知、要往悲觀/樂觀兩端算），這正是 docstring 第 10–20 行講的
「不管實際結果是什麼」的精神，套用在「還沒跑到」上是同一個恆等式，
不是新假設。

指令與完整輸出見本輪 `GAIN_STATE.md` round110 小節。結論：

- OFF：k=288, measured=367, void=4, T=371 ⇒ 區間 [77.63%, 78.71%]（很窄，
  因為 void 只佔 1.08%）。
- ON：k=86, measured=99, 未量到=272（48 void + 224 尚未開始）, T=371 ⇒
  區間 [23.18%, 96.50%]（極寬，因為只跑了 147/371 attempted）。
- **規則 A：兩區間重疊，不可判定。**
- **規則 B（99 題共同子集配對）**：OFF-only 對 3、ON-only 對 2，
  diff(ON-OFF)=-1.01pp，`mcnemar_exact_p=1.0`——與 round108 的 PRELIMINARY
  讀數方向一致（OFF 略高），仍然不顯著，n_common 太小（5 個 discordant
  pair）。

## 推翻條件

- 若之後 `g_on371` 跑完 371/371（或 void 率大降），直接套用原版
  `analyze_void_bounds.py`（不再繞）——屆時 OFF baseline 仍有 4 個 void，
  這個 BROKEN 障礙**不會自動消失**，除非同時修 baseline 的清單來源，或
  在 `off-baseline` 上也做一次同樣的手算繞法。**下一輪若要跑原版腳本，
  先預期會再 BROKEN 一次，不要當成意外重查半天。**
- 若手算的 `T` 取數（371）被證明跟 OFF/ON 兩個 run 實際共用的題序不一致
  （例如 seed 相同但抽樣邏輯有版本差異），這份分析全部作廢——本輪沒有
  逐一核對 371 個 task_id 在兩個 run 裡完全相同，只核對了 seed 欄位相同
  與 OFF attempted 數等於 n。

## 進度速度估計（新資訊，之前沒有輪次算過）

`g_on371`（PID 1849859）從 round94 啟動（約 2026-08-25 09:20 UTC）到本輪
量測時（17:38 UTC）經過約 497 分鐘，attempted 147/371 次。平均 3.38
分鐘/attempted。若維持此速率，剩餘 224 次 attempted 還需要約 **12.6
小時**。這代表「等它跑完再用原版區間法」不會在接下來幾輪內達成——
後續輪次應該預期持續是 PRELIMINARY 讀數，不必每輪重新意外於「還沒
resolve」。
