# round430（2026-09-01）：typing 白名單修正的重放分析被冷落 33 輪，重跑後方向翻盤（仍未顯著）

## 背景

`DECISION_20260831_R393_TYPING_IMPORT_WHITELIST_BUG.md`（round393）發現
`_GAIN_ALLOWED_IMPORTS` 漏了 `typing`，結構性地重罰 ON（ON 只有
initial+revision 兩次機會，同一漏洞命中率遠高於 OFF5 的 5 樣本多數決）。
修法是純白名單擴充（已落地在 `gain_run.py` 原始碼），但決定性 run
（PID 2266603）從 round356 啟動至今**從未重啟**——Python 不會熱重載，
這條 run 收集的所有 `rows.jsonl`/`meets_demand` 全部帶著舊白名單的偏誤，
且永遠不會自我修正。round393 因此寫了離線重放工具
`ops/gain/reanalyze_typing_fix_r393.py`（零模型呼叫，對 `calls.jsonl`
已落盤的候選碼用修好的 checker 重跑 sandbox），round393→394→395→397
連續 4 輪重跑，追蹤這個修正對 ON vs OFF5 配對比較的影響：

| round | n_paired | gap(ON−OFF5) | McNemar p |
|-------|---------:|-------------:|----------:|
| 393   | 70       | +2.86pp       | —         |
| 394   | ~70      | +2.82pp       | 0.6875    |
| 395   | 73       | +2.74pp       | 0.6875    |
| 397   | 74       | +2.70pp       | 0.6875    |

方向穩定（+2.7~2.9pp，ON 領先），但 round397 之後**完全沒人再重跑這支
腳本**——round398-429（32 輪）全部只用**未修正**的 `rows.jsonl` 原始
`meets_demand` 做配對分析（`analyze_paired.py`／`analyze_off5v.py`／
`analyze_off5va.py` 全部讀 `rows.jsonl` 現成欄位，不套用 typing 修正）。
`DECISION_20260831_R411_ON_VS_OFF5_EQUAL_BUDGET_CONCLUSION.md`（round411，
目前的「正式結論」）與其後每一輪的重跑（round428/429/430 開場快照）
都是在這個已知偏誤下測的，卻從未在文字裡帶這個警語。

## 本輪做的事

重跑 `python3 ops/gain/reanalyze_typing_fix_r393.py`（零模型呼叫），
資料已從 round397 的 OFF=95/ON=76/OFF5=88 長到 OFF=155/ON=102/OFF5=132：

```
OFF   n=155  flip_to_true=4  flip_to_false=0  typing_used_old_false=6
ON    n=102  flip_to_true=8  flip_to_false=0  typing_used_old_false=9
OFF5  n=132  flip_to_true=6  flip_to_false=2  typing_used_old_false=2
OFF5 bucket-reconstruction sanity: checked=132 mismatch=1（仍是
  mbppplus_Mbpp/572，跟 round393 起同一個已知不吻合，未新增同類案例）
```

`flip_to_false=0` 對 OFF/ON 維持（純白名單擴充只會讓分數變好或不變，
方向正確，無反例）；OFF5 的 `flip_to_false=2` 落在已知的 tie-break
近似誤差範圍內（round393 建立的但書，未變）。

用 `/dev/shm/r393_reanalysis_detail.json` 的 `new_truth` 欄位重算配對
McNemar（方法與 `analyze_paired.py` 一致：交集 task_id、`new_truth` 當
需求=產出）：

```
n_paired = 92
ON   new_truth  78/92 = 84.78%
OFF5 new_truth  75/92 = 81.52%
discordant：只有 ON 對 b=5，只有 OFF5 對 c=2
McNemar 精確雙尾 p = 0.453125
gap (ON − OFF5) = +3.26pp
```

## 這跟本輪稍早重跑的「官方」R411 指標矛盾

同一份資料、同一輪、用**未修正**的 `analyze_paired.py`（R411 的方法）：

```
n_paired = 92（同一批任務）
ON   需求=產出  70/92 = 76.09%
OFF5 需求=產出  72/92 = 78.26%
discordant：只有 ON 對 b=5，只有 OFF5 對 c=7
McNemar p = 0.7744
gap (ON − OFF5) = −2.17pp（OFF5 領先）
```

**同一個 n=92、同一批任務，未修正版本說 OFF5 領先 2.17pp，typing 修正版本
說 ON 領先 3.26pp——方向相反。** 兩者共同點：p 值都遠未達顯著（0.77 vs
0.45），所以「ON 與 OFF5 在等預算下沒有統計上可分辨的差異」這句話**沒有
被推翻**——但 R411 原文與 round428/429 的措辭「點估計方向持續偏向 OFF5」
只在未修正版本下成立，**在已知偏誤修正後方向是相反的**，這是本輪之前
34 輪沒人交代清楚的落差。

`b/c` discordant 组的變化也值得注意：未修正版 c=7（只有 OFF5 對），
修正後 c=2（只有 OFF5 對）——5 個原本判給 OFF5 的 discordant pair 在
typing 修正後翻成 ON 也對（`flip_to_true` 主要發生在 ON），這跟
round393 的機制解釋完全吻合：ON 的 initial/revision 兩次嘗試常常
邏輯正確但被白名單擋下，OFF5 的 5 樣本多數決天然稀釋同一漏洞。

## 趨勢：p 值隨 n 增長持續下降，方向從未翻轉

```
n_paired   74 → 92
p         0.6875 → 0.453125
gap      +2.70pp → +3.26pp
```

4 個獨立檢查點（round393/394/395/397，現在加上 round430）方向一致、
量級穩定甚至略升，p 值單調下降。**這不是「已經是穩定態」的統計特徵**
（跟 R411 用未修正資料觀察到的「12-13 個檢查點 p 值釘在天花板」不同）——
這是「還在收斂、且往顯著的方向收斂」的特徵。不能因此下結論說 ON 會贏，
但也不能繼續引用 R411 的「方向持續偏向 OFF5」而不帶這個警語。

## 對三條「有成效」判準的影響

1. 量測有訊號：不變。
2. **三臂有差異**：兩個版本都不顯著，但**點估計方向哪一邊領先取決於
   用哪份分析**——這件事本身需要被交代，不能只報未修正版本。
3. 等預算答案：**R411「ON 沒有顯著贏 OFF5」这句话本身沒被推翻**（兩個
   版本 p 值都遠未達顯著），但 R411 原文與後續 12+ 輪的「方向持續偏向
   OFF5」的措辭，只在已知有偏誤的量具下成立，需要更正。

## 沒做的事（照實寫）

- 沒有推翻 R411 的核心結論（無顯著差異）——只更正了「哪個方向領先」
  這句附帶措辭的前提
- 沒有殺掉或干預 PID 2266603
- 沒有修改任何 `ops/gain/*.py` 的邏輯（`gain_run.py` 的 typing 修正
  round393 就已經落地，本輪只是重跑既有的重放工具）
- 沒有解開 `mbppplus_Mbpp/572` 的重放不吻合（維持 round393 起的已知
  但書，未新增同類案例）
- 沒有把 typing 修正版的數字寫成新的「正式結論」——p 值仍不顯著，
  兩個版本目前都只能說「無法分辨」，只是方向的敘事需要更正

## 建議（給下一輪／run_complete=true 時）

1. **`run_complete=true` 時的最終分析，必須用 `reanalyze_typing_fix_r393.py`
   的重放結果，不能只用 `analyze_paired.py` 讀原始 `rows.jsonl`**——
   後者的偏誤是已知的、永遠不會自我修正（PID 2266603 這條 run 的
   生命週期內都帶著它）
2. 每次重跑 off5v／off5va／R411 主判準，**都應該同時重跑
   `reanalyze_typing_fix_r393.py`**，兩邊都報，不要只報其中一個
   （這是繼 round429「off5v 要帶 off5va 警語」之後，第二條「重跑一個
   判準要連帶重跑它的已知修正版」規則）
3. 若 p 值下降的趨勢在 179/179 完整資料時仍未反轉、且跨過 0.05，
   這會是本輪之前 429 輪都沒有機會看到的新結論，需要 sonnet/opus
   判斷是不是真的顯著（不是純同步工作）

## 推翻條件

- 若下一次重跑 `reanalyze_typing_fix_r393.py` 時 `flip_to_false` 對
  ON 或 OFF 不再是 0 ⇒ 「純白名單擴充只會變好或不變」的方向保證被打破，
  這份文件的機制解釋需要重新檢查
- 若 `mbppplus_Mbpp/572` 之外出現第二個 OFF5 bucket-reconstruction
  不吻合的案例 ⇒ tie-break 近似的誤差可能比目前認為的大，typing 修正版
  的 OFF5 數字需要打折扣看待
