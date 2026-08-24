# DECISION 2026-08-24（round 56）— ON 臂「revise 從未改變結果」的反事實定位

## 背景

round 55 量到 ON 臂 52 題裡 `revision_transition` 的 `improved=0`、`harmed=0`，
並把它記為「反直覺結果，需判斷是真發現（同模型家族評審共同盲區）還是
`arm_on()` 的邏輯 bug」。本輪回答這個問題。

**本輪沒有改任何實驗條件**：沒有動 `gain_run.py`、沒有動題庫、沒有動 worker 池、
沒有 kill 或重啟正在跑的 v3 run。新增的只有一支**唯讀分析工具**
`ops/gain/analyze_revise_counterfactual.py`（不發任何模型呼叫）。

## 判準（在任何量測之前寫死，原文存 `/dev/shm/r56/CRITERIA.md`，逐字抄錄於此）

結構事實（量測前先讀 `vacant/codebench.py:653-663` 確認）：
`hidden_check = _check_code(..., base + plus)`、`visible_check = _check_code(..., base)`
⇒ **hidden 的斷言是 visible 的嚴格超集** ⇒ visible 不過必然 hidden 不過
⇒ `selected_version == "revised_both_visible_fail"`（兩版都 visible 不過）
在**結構上不可能** `improved`。

反事實量測：對每列 ON row，從 `calls.jsonl` 取 `role=gen(phase=initial)` 與
`role=revise` 的回應全文，`extract_code` 後各自跑 visible 與 hidden：
`I_v,I_h`＝初稿、`R_v,R_h`＝修訂稿。分類：

- `discarded_win`        ：交付=initial* 且 `not I_h` 且 `R_h`（丟掉能救回這題的修訂）
- `discarded_harm_avoid` ：交付=initial* 且 `I_h` 且 `not R_h`（擋掉會弄壞的修訂）
- `dead_branch`          ：`revised_both_visible_fail`（結構上不可能贏）
- `no_opportunity`       ：`I_h == R_h`

判定規則（事前）：

- `discarded_win >= 2` ⇒ 判 **(B) 選版邏輯的設計缺陷**。記 DECISION，**本輪不改 code**。
- `discarded_win == 0` 且所有 `stayed_wrong` 的 `R_h` 皆 False ⇒ 判 **(A) 機制真的無效**。
- `discarded_win == 1` ⇒ **不判定**，樣本不足，只記數字。
- 另報 `discarded_harm_avoid`：若它 >> `discarded_win`，那道 gate 是有價值的保護。

推翻條件（事前）：

1. revise 回應抽不到 python fence 的比例 > 10% ⇒ 判定全部作廢，先修解析。
2. 重算的 `I_h` 與 rows 記的 `revision_transition` 蘊含的初稿真值有任一列不一致
   ⇒ 我的 harness 有錯，全部作廢，**不准發布數字**。

## 量測結果（n=53，v3 run 的 ON 臂已完成列；量測期間該 run 仍在跑，52→53）

推翻條件檢查：`fence_missing = 0/53 = 0.0%`（未觸發）；
`harness_mismatch = []`——53 列重算的 `I_h` 與 rows 的 `revision_transition`
**全部一致**（未觸發）。兩條都沒觸發 ⇒ 數字可發布。

2×2（初稿 hidden × 修訂稿 hidden）：

```
  I_h=True   R_h=True  : 40
  I_h=True   R_h=False :  0     ← 修訂稿從未弄壞一個原本正確的初稿
  I_h=False  R_h=True  :  1     ← Mbpp/792
  I_h=False  R_h=False : 12
```

分類：`no_opportunity=46`、`dead_branch=6`、`discarded_win=1`、
`discarded_harm_avoid=0`。逐字元相同的修訂稿 19/53（35.8%）。

**⇒ 依事前規則，`discarded_win == 1` ⇒ 對 (A)/(B) 這個二分「不判定」，樣本不足。**

不依賴那道門檻、可以直接陳述的兩件事：

1. **那道 gate 的既有理由在本樣本上支持度為 0。** 原始碼註解寫
   `an unrequested rewrite must not replace an answer that peers approved`，
   但 `I_h=True, R_h=False` 這一格是 **0/53**——53 題裡修訂稿**沒有一次**
   弄壞原本正確的初稿。gate 的實測保護收益 0、實測代價 1（Mbpp/792）。
2. **`improved=0` 主要是結構造成的，不是「模型救不回來」。** 13 個錯誤交付裡
   12 個修訂稿也錯（機制真的救不了），但**只有 1 個原本救得回來，而它被 gate 丟掉**。
   round55 的措辭「review+revise 對同模型家族任務沒有殺傷力」應改述為
   「可用的贏面在 53 題裡只有 1 個，且那 1 個沒有被交付」。

### `discarded_win` 唯一個案 Mbpp/792（全文在 calls.jsonl）

題目 `count_list`：數「給定的多個 list 裡有幾個 list」。
初稿（`plain-1`）`return len(input_list)`——base 測資剛好全是 list 所以 visible 過，
plus 測資有非 list 元素就錯。三位審查者 `raw_pass` **全部 True**（沒人看出來）。
修訂者（`careful-1`）在 prompt 明寫「沒有通過執行驗證的反例；不要因未證實的文字
指控改壞初稿」的情況下，仍自己改成
`return sum(1 for x in input_list if isinstance(x, list))`——正確。
交付邏輯 `if passed_review and initial_visible_ok` 命中 ⇒ 交付初稿 ⇒ 這題判錯。

## 附帶發現（本輪順手做的同題配對比較，不在事前判準內，標明為觀測）

同一批 53 題，對照 `runs/g_off60_qwenonly_20260824`（round11 就跑完的 OFF baseline）。
兩臂在這 53 題**都是 0 筆 infra_void**（ON err 全為 `sandbox_check_failed` 13 筆、
OFF 9 筆）⇒ 分母乾淨。

```
  OFF 隨機選 agent、1 通            : 44/53 = 83.0%   Wilson95% [0.708, 0.908]
  ON 初稿（信譽路由選 agent、1 通） : 40/53 = 75.5%   Wilson95% [0.624, 0.851]
  ON 實際交付（+4 通 review/revise）: 40/53 = 75.5%
  ON 若一律交付 revised            : 41/53 = 77.4%
```

McNemar 精確雙尾（配對）：

```
  ON 實際      vs OFF : 不一致格 1 / 5   p = 0.219
  ON 初稿      vs OFF : 不一致格 1 / 5   p = 0.219   ← 與上一行完全相同
  ON 一律revised vs ON 實際 : 1 / 0      p = 1.000
```

**兩條 ON-vs-OFF 的不一致格完全相同（1 對 5）**，意思是 review+revise
在那 6 個決定勝負的題目上**一題都沒有改變結果**——ON 落後 OFF 的差距，
在第 1 通呼叫（產生初稿）就已經全部產生了，跟後面 4 通無關。

**這是一個定位，不是一個結論。** 三個明講的前提：

- `p = 0.219`，兩個 Wilson 區間大幅重疊 ⇒ **方向是暗示，統計上沒有成立**。
- n=53、v3 的 ON 臂還沒跑完（60 slot）、**OFF5 臂 0 筆**。
- 若差距真的在路由：ON 用 `_route_agent`（信譽）、OFF 用 `rng.choice`（隨機），
  ON 把 47% 的題送給 `plain-1`、19% 送給 `careful-1`。但**各 agent 拿到的是
  不同的題**，per-agent 通過率沒有對題目難度做控制，n 小到 careful-1 只有 10 題
  ⇒ **「信譽路由選到比較差的 agent」目前是假說，不是量測結果。**

## 決定

1. **不改 `gain_run.py`。** 依事前規則 `discarded_win == 1` 不足以判定，
   且 v3 正在跑，改 code 等於中途變更實驗條件。
2. **不新增 arm、不換題庫、不換 worker 池。** 本輪零實驗條件變更。
3. 把上面的定位留給後續輪次，**等 v3 兩臂 `run_complete=true` 再重跑這支工具**
   （屆時 n=60 且有 OFF5，`discarded_win` 是否跨過 2 才有意義）。

## 什麼條件下這份決定該被推翻

- v3 跑完後 `discarded_win >= 2` ⇒ 事前規則自動判 (B)，該提選版邏輯的修改案。
- 若 `I_h=True, R_h=False` 那一格在 n=60 仍是 0，而 `discarded_win >= 1`
  ⇒ gate 的「保護」在整個樣本上收益恆為 0、代價為正，該提案移除 gate。
- 若後續量到 review+revise 開始改變 ON-vs-OFF 的不一致格（不再是 1/5 對 1/5）
  ⇒「差距全在第 1 通」這個定位失效，要重做。
- 若要檢驗「路由是差距來源」這個假說，**那是新增實驗條件**（例如一條
  ON-random-routing 臂），必須另開 DECISION，不可直接改現有 ON 臂。
