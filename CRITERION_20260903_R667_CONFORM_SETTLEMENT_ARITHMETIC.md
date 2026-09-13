# R667：r444 收官的**結算算術**先寫死——「通過率」是哪一個分母

（2026-09-03 round667，Opus 5。**判準寫在量測之前**；本檔 commit 之後才碰 r444 的數字。
對象：`runs/g_r444_conform_mbpp`，預註冊 `DECISION_20260903_R440R_CONFORM_LIVE_PREREG.md`。
round666 已處理 P-C4；本檔處理 **P-C1／P-C1b／P-C2／P-C3／P-C5**。）

## 〇、污染揭露（先講，不是事後補）

我在本輪開場讀 `GAIN_STATE.md` 時**已經看到** round666 §六 的中途快照
（115/179 題：OFF 73.0%／CONFORM 74.8%／OFF5 72.2%，Δ=+2.6pp，leaked 23 vs 32）。
**所以本檔不是盲的預註冊。** 緩解方式只有兩條，逐條落實：

1. 能由**出處**決定的，就不由我決定——P-C1 的 +3~+6pp 帶是從 R440P 的重放來的，
   那份重放的**分子分母寫在程式碼裡**（§二 F3），照它的算法結算，不是照我的偏好。
2. 我確實要做選擇的地方，**標出偏袒方向**；已經看過中途數字而 R440R 又沒給門檻的，
   **一律降級成「只報數字、不判 PASS/FAIL」**，不准當場發明門檻（P-C3 的 `leaked`）。

## 一、本檔要解的問題

r444 收官那一輪會想跑「顯而易見的那道指令」。問題是：
**那道指令算出來的數字，跟 P-C1 問的是不是同一件事？**
零成本現在問；收官後才發現算錯，是一整個 run 的主結論被算在錯的分母上。

## 二、碼側事實（讀原始碼確認，非推測）

| # | 事實 | 位置 |
|---|---|---|
| F1 | OFF 與 OFF5 的 `accepted` **恆為 True**（無條件） | `gain_run.py:1311,1314` |
| F2 | CONFORM 拒交時仍回傳 `last` 候選，dispatch 端**無條件**用 `hidden_check` 計分 ⇒ 該列 `meets_demand` 是**沒出貨的那份碼**的離線正確性 | `gain_run.py:516-520`（註解自己寫明「那是離線評分不是出貨」） |
| F3 | R440P 重放的 `pass%`：`res[t] = None if r is None else hidden_ok`、`npass = sum(1 for t if res[t])`、分母 `n`＝**全部題目** ⇒ **拒交算不通過** | `replay/conformance_delivery.py:536-540` |
| F4 | `paired_gates.py:41`、`risk_coverage.py:45`、`rows_visible_audit.py:21` 把臂名寫死成 `("OFF","ON","OFF5")` ⇒ **CONFORM 被安靜濾掉** | 同左 |
| F5 | `analyze_paired.py` 的 `--a-arm/--b-arm` 吃自由字串（CONFORM 可用），但它比的是 `meets_demand` ⇒ 配 F2，**跑它結算 P-C1 會答到另一個問題** | `analyze_paired.py:110-114` |

**F1+F2 的合成後果**：`demand_equals_output_rate`（分母 `n_acc`＝出貨數）與
`correct_delivery_rate`（分母 `measured`＝全部量到的題）**只在 CONFORM 這一臂分岔**，
而 CONFORM 正是受測臂。用前者＝**拒交難題可以把通過率墊高**。

## 三、結算算術（本輪寫死，收官那輪照這個算）

**每題的交付指標（primary）**：`deliv(r) = bool(r["accepted"]) and bool(r["meets_demand"])`
——「有交出去**且**符合需求」。依據＝F3（出處：P-C1 的帶就是這樣算出來的）＋機制
（拒交＝這題沒有交付物）。**偏袒方向：這是保守選擇**，它替 CONFORM 的拒交記帳，
只會讓 CONFORM 的數字比另外兩種算法**低**——不是對本結論有利的那個選擇。

| 判準 | 怎麼算 | 判定帶（來自 R440R，不改） |
|---|---|---|
| **P-C1** | `deliv` 率之差 CONFORM − OFF5，分母＝兩臂都量到的配對題集 | +3~+6pp ⇒ 中；否則照實寫落在哪 |
| **P-C1b** | 對 `deliv` 做 McNemar 精確檢定；b＝只有 CONFORM 交對、c＝只有 OFF5 交對 | p ∈ [0.02, 0.20] |
| **P-C2** | `summary.arms.CONFORM.calls_per_task`，並用 `sum(calls_used)/measured` 獨立覆算，兩者須相符 | ≤2.0 中；>4.5 觸發 R440R §四 中止 |
| **P-C3a** 拒交率 | CONFORM 列中 `accepted=False` 的比例（分母 measured） | 3–10% |
| **P-C3b** `leaked` | 每臂 `accepted ∧ ¬meets_demand` 的**個數**（＝summary 的 `leaked` 定義） | ⚠ **只報數字，不判 PASS/FAIL**（見下） |
| **P-C5** | 每臂 `notes.jsonl` 的 `infra_void` 數 /（measured+void） | <20%；>10% 另印 SPEC §7 警告 |
| **P-C4** | 依 round666：**只結算前半**（`receipt_head` 齊備）；鏈為 **UNVERIFIABLE** | **不准**當成 §四「為假」的中止條件 |

**P-C3b 為什麼降級**：R440R 只寫「明顯低於 OFF5」，**沒有數字**；而我已經看過中途的
23 vs 32。此刻發明任何門檻都是照著已知結果訂的。⇒ 收官只報 `leaked` 的絕對數與配對
不一致格數，**並在下一份預註冊裡把它寫成數字**。

**三種算法一律並列輸出**（`deliv` / `meets_demand` 單獨 / `demand_equals_output`），
但**只有 `deliv` 那一欄結算 P-C1**。並列是為了讓讀的人看得見差多少，不是給人挑。

## 四、事前預測（跑工具之前寫下）

| # | 預測 |
|---|---|
| P-R667-1 | `paired_gates.py runs/g_r444_conform_mbpp` 印出 `arms=['OFF','OFF5']`（CONFORM 缺席）且 **rc=0**＝安靜漏掉 |
| P-R667-2 | CONFORM 有 `meets_demand ∧ ¬accepted` 的列（>0）；OFF 與 OFF5 該計數＝**0**（F1 推論） |
| P-R667-3 | 以 `deliv` 算的 Δ(CONFORM−OFF5) **嚴格小於**以 `meets_demand` 算的 Δ |
| P-R667-4 | `demand_equals_output_rate(CONFORM) > correct_delivery_rate(CONFORM)`；OFF/OFF5 兩者相等 |
| P-R667-5 | 新工具在 4 種植入缺陷下翻成 **BROKEN**（不是安靜給數字） |

**推翻條件（觸發就照實寫，不當場補判準）**：
- 若 F3 讀錯（+4.47pp 其實出自別的分母）⇒ P-C1 的metric 錨消失，收官**只能並列報三種算法、不判 PASS/FAIL**。
- 若 P-R667-2 反過來（OFF/OFF5 也有 `meets_demand ∧ ¬accepted`）⇒ F1 的讀法錯，整份 §三 重寫。

## 五、給收官那一輪（fable）的操作

1. `python3 ops/gain/replay/conform_settle.py --run runs/g_r444_conform_mbpp --json <out>`
   ——零 API、零沙箱，只讀已落盤欄位。
2. **不要**用 `paired_gates.py` 結算 CONFORM（F4）。
3. 用 `analyze_paired.py` 當交叉檢核可以，但**要知道它報的是 `meets_demand` 那一欄**（F5），
   不是 P-C1 的量。
4. P-C4 照 round666 §四；P-C3b 照本檔 §三 只報數字。
