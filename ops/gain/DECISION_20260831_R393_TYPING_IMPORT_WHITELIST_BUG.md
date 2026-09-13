# round393（2026-08-31）：`_GAIN_ALLOWED_IMPORTS` 漏了 `typing`，結構性地重罰 ON

## 觸發

round392 交棒明寫「off5va 剩下的 2 個 discordant（736/790）值得找一輪逐題
檢查——round388 定性為『獨立生成雜訊』但從未真正逐題驗證」。本輪逐題查證。

## 找到什麼

`mbppplus_Mbpp/736`（`left_insertion`，標準 `bisect.bisect_left`）：
ON 的 initial 與 revised 兩次產出都寫了 `from typing import List, Union`，
邏輯完全正確（跟官方 `bisect.bisect_left` 逐位元一致），但 `visible_ok`
判定為 `False`。原因不是邏輯——`ops/gain/gain_run.py` 的
`_GAIN_ALLOWED_IMPORTS`（餵給 `vacant/checks.py` 的候選碼 import 白名單）
只有：

```
"bisect", "cmath", "collections", "functools", "heapq", "itertools",
"math", "operator", "re", "sys"
```

`typing` 不在裡面。`vacant/checks.py:_candidate_functions` 對於白名單外的
import 直接回傳 `None`（判定為找不到候選函式），這條路徑跟「邏輯錯誤」
在 `meets_demand` 的回傳值上完全無法區分，都是
`(False, "sandbox_check_failed")`。

`typing` 是純型別標註模組，**零執行期副作用**（不碰 I/O／檔案／網路／
process），被排除純屬白名單疏漏，不是刻意的安全邊界（`vacant/checks.py`
自己的沙箱 worker 只 import `collections/json/math/os/re/sys`，跟候選碼
的白名單是兩件事）。

## 全域掃描：這不是單一題的巧合，是結構性地重罰 ON

對 `runs/g_r356_3arm_20260830`（決定性 run，本輪查證當下 OFF=95/ON=76/OFF5=88）
逐題掃描 `visible_ok=False`（OFF/OFF5 則檢查最終送出碼是否因 typing 被擋）：

| arm  | visible_ok=False 總數 | 其中因 `from typing import` 被擋 | 佔比 |
|------|----:|----:|----:|
| ON   | 7 | 6 | **86%** |
| OFF  | 7 | 2 | 29% |
| OFF5 | 6 | 2 | 33% |

ON 只有 initial + revision 兩次真正機會，兩次都被同一個漏洞打中就整題
陣亡；OFF5 是 5 個獨立樣本多數決，同一個漏洞天然被稀釋（只要 5 個裡有
3 個沒用 typing 就贏）。**這是量具的偏誤，不是「哪個機制比較會寫程式」
的證據**——round388-392 建立的「ON 沒有比 OFF5 好」的結論，是在這個偏誤
還在時測到的。

逐題確認（不是只看比例）：把 736 的 ON initial code 原封不動丟進修好後
的 checker，`visible: True`、`hidden: True`——**這題 ON 本來就會對**，
只是被白名單擋下來，跟 round388 說的「獨立生成雜訊」無關。

`mbppplus_Mbpp/790`（`even_position`）驗證後是另一回事：typing 修好後
ON 的 code visible 過了，但 hidden 仍然 `False`——查官方 canonical
`all(nums[i]%2==i%2 for i in range(len(nums)))` 才發現，這題的**官方解
其實要求奇數索引也要放奇數**，題目文字跟給的唯一 assert 都沒暗示這件事。
ON 跟 OFF5 的所有樣本都只檢查了偶數索引，這題兩邊都會漏，是題目本身的
陷阱，不是白名單的問題。**round388「獨立生成雜訊」對 790 是對的，
對 736 是錯的**（誤把白名單假陰性也歸進雜訊）。

## 修法

`ops/gain/gain_run.py` 的 `_GAIN_ALLOWED_IMPORTS` 加入 `"typing"`
（純白名單擴充，沒有新增旋鈕、沒有放寬任何正確性判準）。

**量具雙向驗證**（SPEC_GAIN §5.2，修完立刻重跑）：

```
$ VACANT_EVALPLUS_PATH=.vacant-private/evalplus/MbppPlus-v0.2.0.jsonl.gz \
  python3 ops/gain/gain_run.py --out /dev/shm/r393_probe --n 179 --arms probe \
  --seed g-r212-route-20260828
── 量具驗證（先答已知答案）
   參考解通過 12/12　壞解被擋 12/12
```

兩個方向都過，白名單擴充沒有引入新的假陽性。

## 沒有動決定性 run

`runs/g_r356_3arm_20260830` 那支 PID 2266603 的長跑進程**沒有被碰**——
Python 沒有熱重載，編輯 `gain_run.py` 檔案不會影響已經在記憶體裡跑的
那份程式碼，它會繼續用舊白名單跑到完（round388-392 建立的「不要動決定性
run」鐵律原封不動）。這支 run 已收集的資料因此**全部帶有這個偏誤**，
本輪沒有重跑任何模型呼叫去修正它——見下段的離線重放。

## 離線重放：已收集的資料在修好之後會怎樣（零模型呼叫）

`ops/gain/reanalyze_typing_fix_r393.py`：不重跑任何模型呼叫，直接對
`runs/g_r356_3arm_20260830/calls.jsonl` 裡已經落盤的候選碼，用修好後的
checker 重跑 sandbox。OFF/ON 是直接重放已送出的碼；OFF5 因為多數決的
tie-break 有 rng，改用「拿舊白名單重建 behavior_signature bucket、取
winning bucket 代表」做近似，並用「舊白名單重放能不能重現原本記錄的
`meets_demand`」自我檢查：**88 題裡 87 題吻合**（1 題不吻合，是
`mbppplus_Mbpp/572`，n_tied_buckets=1 但 bucket 內 3 個代表都對不上，
原因未查——留給下一輪，不影響下方整體結論的方向）。

聚合結果（跑到 OFF=95/ON=76/OFF5=88 題時的快照）：

```
         OFF               ON                OFF5
old_true   71                57                 64
flip→True   2                 5                  5
flip→False  0                 0                  2   ← 見下方 OFF5 近似的但書
仍是False  22                14                 17
需求=產出（舊）  71/95=74.7%   57/76=75.0%    66/88=75.0%
需求=產出（修後）73/95=76.8%  62/76=81.6%    69/88=78.4%
```

**ON 的 flip_to_false = 0**（OFF 也是 0）——純白名單擴充只會讓 ON/OFF
變好或不變，這正是預期中的方向，沒有反例。OFF5 的 flip_to_false=2 落在
上面已知的「tie-break 近似」誤差範圍內，不當作反例證據。

配對重算主判準（ON vs OFF5，`n_paired=70` 共同題目）：

```
                    OLD（原本的量具）      NEW（修好 typing 之後）
ON  需求=產出         52/70 = 74.3%         57/70 = 81.4%
OFF5 需求=產出        52/70 = 74.3%         55/70 = 78.6%
discordant (b,c)      (4, 4)                 (4, 2)
McNemar p             1.0000                 0.6875
gap (ON − OFF5)       0.00pp                 +2.86pp
```

**OLD 那一行跟 round392 報的「主判準 ON vs OFF5 仍不顯著（p=1.0000）」
逐字元吻合**——這驗證了這支重放腳本的方法論是對的，不是在編故事。
修好之後 gap 從 0 移動到 +2.86pp、discordant 從對稱 (4,4) 變成不對稱
(4,2)，方向與量級都跟上面「ON 被 86% vs 29%/33% 不對稱重罰」的機制解釋
一致。**p=0.6875 仍未達顯著**（n 還小、OFF5 有已知近似誤差）——這不是
「找到了 ON 贏的證據」，是「找到了一個系統性偏誤，修正後差距朝 ON
的方向移動但還沒到能下結論的樣本數」。

## 對三條「有成效」判準的影響

1. 量測有訊號 ✓（不受影響）。
2. **三臂有差異**：不變——這個修正還沒讓任何一條線在統計上顯著分開，
   只是移除了一個把 ON 往下拉的偏誤來源。
3. 等預算答案：**round391/392 建立的「ON 打不贏 OFF5」的結論，是在量具
   有這個偏誤時測到的，現在不能直接引用**——正確的說法是「這個問題
   還沒有乾淨的答案，需要在修好的量具下重新累積樣本」。

## 沒做的事（照實寫）

- 沒有殺掉或重啟決定性 run（PID 2266603 全程存活、未被干預）
- 沒有用這支重放腳本的結果**取代**決定性 run 的官方 summary——它是
  「這個修正值不值得做」的證據，不是正式的實驗結果；正式結果要等
  一支在修好的量具下**全新**跑的 run（或等這支決定性 run 跑完全部
  179 題後，用同一套重放方法整批重算一次）
- 沒有解開 `mbppplus_Mbpp/572` 的重放不吻合，留給下一輪
- 沒有嘗試精確重現 OFF5 的 tie-break rng（需要原始 rng 流的精確位置，
  目前的重建是「同一套規則、不保證同一個 rng 抽樣結果」的近似）

## 推翻條件

- 若下一輪重新檢查 `mbppplus_Mbpp/572` 發現重放方法論本身有 bug
  （不只是 rng 近似的誤差）⇒ 整批「flip_to_true/false」計數要重算
- 若之後在修好的量具下**正式**跑出 ON vs OFF5 的顯著結果（不管哪個
  方向）⇒ 本文件「還沒有乾淨答案」這句話要更新成正式結論
- 若決定性 run 跑完全部 179 題後用本腳本重算，`n_paired` 大幅提升，
  p 值大幅下降 ⇒ 值得優先処理，不要又拖到下一個發現才做

## 下一步（建議，非本輪已完成）

1. 決定性 run 跑到 179/179 時，重跑 `reanalyze_typing_fix_r393.py` 拿
   完整 n 的重放結果
2. 另開一支在**修好的量具**下從頭跑的 OFF/ON/OFF5 三臂 run，作為不帶
   歷史包袱的乾淨對照（沿用同一套 seed/models/timeout 設定）
3. 查 `mbppplus_Mbpp/572` 的重放不吻合
