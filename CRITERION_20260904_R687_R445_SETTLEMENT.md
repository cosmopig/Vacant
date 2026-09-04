# CRITERION R687 — r445 收官執行判準

**寫作時刻：2026-09-04 00:40 UTC。r445 尚未收官（rows 425/576）。**
本檔在跑任何一支收官工具之前寫完並 commit。

---

## 零、污染揭露（我在寫本檔之前已經看過什麼）

必須逐條寫出來，否則下一輪無法判斷本輪有沒有「看完數字再訂判準」：

1. **我看過 r445 的中途快照**（本輪開場唯讀對帳，rows=425/576）：
   `meets_demand` CONFORM 113 / OFF 102 / OFF5 102，`accepted` CONFORM 131 / OFF 142 / OFF5 141，
   三臂 `infra_void` 全 0。**這是有方向性的資訊**（CONFORM 的粗計數高於 OFF5）。
2. 我看過 r444 已凍結的收官數字（round672／round686 引用過）：
   deliv CI `[-1.66, +5.94]pp`、b/c = 9/4、n_d=13、disc_rate 0.0726。
3. 我看過 round682 合成 fixture 印出的 `ON_WINS ／ +11.98pp ／ HIT=5 MISS=3`
   ——round682 §「fixture 的實質數字全部作廢」已明令不准引用，本輪不引用。

**為什麼看過 (1) 仍不算「量完再訂判準」**：本輪**一條判定規則都不新訂**。
收官的判定口徑全部是**前幾輪在看不到這些數字時就凍結**的：

| 用到的規則 | 凍結於 | 本輪動了嗎 |
|---|---|---|
| 四格表（`CONFORM_WINS`／`RULED_OUT`／`UNINFORMATIVE`／`NON_INFERIOR_BUT_UNRESOLVED`），ALPHA=0.05、PRACTICAL_PP=5.0 | `CRITERION_...R670...md` §三 | **未動** |
| 四格 × 成本不對稱各自准寫／禁寫什麼 | `CRITERION_...R684...md` §二 | **未動** |
| 交付率口徑 `deliv = accepted ∧ meets_demand`、三種算法並列輸出「不是給人挑」 | `CRITERION_...R667...md` :40/:47/:59-60 | **未動** |
| 八條預測 P-E1..P-E8 | `DECISION_20260903_R445_CONFORM_BANK_EXTENSION.md` §二/§四 | **未動** |
| UNRESOLVED 必須同時寫 MDE 3.50pp／N₈₀≈703 兩句；Q4 推翻條件 | round678 §六 | **未動** |
| 四個 r444 口徑的鍵不准抄進 r445 收官文字 | round677 §二/§四 | **未動** |

⇒ **本輪對「規則」的自由度是零**，我唯一能做的是照跑、照抄、照裁決。
若我在收官後想改任何一格判定規則，那是**下一輪**的事，且要單獨開判準檔。

---

## 一、前置閘門（不過就不准收官，且不准「差幾行也算」）

收官只在**同時**滿足下列三條時才准開始：

```
G1  rows.jsonl 行數 == 576（192 × 3），且三臂各 192
G2  summary.json 的 run_complete == true 且 run_terminal == true
G3  ps -eo cmd | grep -c "^python3 ops/gain/gain_run\.py"  == 0（行程已退出）
```

任一條不滿足 ⇒ **本輪不收官**，照實寫「r445 未收官」並交棒。
**不准**因為「只差幾行」就提前跑第 2/3 行——`--final` 的擋門就是為了這個而存在。

G1–G3 全過之後**第一件事**（round671 鐵律：run 一退出就落盤進 git）：
`git add` r445 的 run 目錄並 commit。run 活著時不 add，退出後立刻 add。

---

## 二、收官五行（原封不動，順序不准換，逐行記 rc）

```bash
mkdir -p runs/_analysis_r445

# 0) 併庫前提（rc=2 = 前提不成立，不是「工具壞了」）
python3 ops/gain/replay/pool_precheck.py \
  --runs runs/g_r444_conform_mbpp runs/g_r445_conform_mbpp_ext \
  --criterion CRITERION_20260903_R680_POOL_PRECONDITIONS.md \
  --code-attest runs/_analysis_r680/CODE_ATTEST.md \
  --json runs/_analysis_r445/pool_precheck.json

# 1) 併庫（**必帶 --key deliv**；忘了帶會在第 2 行被 Q9a 擋成 rc=2，
#    那是「你量錯東西了」，不是「工具壞了」——round686 §四）
python3 ops/gain/replay/pooled_paired_ci.py \
  --stratum r444=runs/g_r444_conform_mbpp --stratum r445=runs/g_r445_conform_mbpp_ext \
  --a-arm CONFORM --b-arm OFF5 --key deliv --json runs/_analysis_r445/pooled_deliv.json

# 2) 八條預測逐條判（--final）
python3 ops/gain/replay/r445_predcheck.py --run runs/g_r445_conform_mbpp_ext \
  --pooled-json runs/_analysis_r445/pooled_deliv.json --final \
  --json runs/_analysis_r445/predcheck.json

# 3) P-C1 四格表（口徑照 round670 §三，不現場另訂）
python3 ops/gain/replay/conform_settle.py --run runs/g_r445_conform_mbpp_ext

# 4) 收官後重跑投影（已非期中，可餵 r445）
python3 ops/gain/power_paired.py --a-run runs/g_r445_conform_mbpp_ext --a-arm CONFORM \
  --b-run runs/g_r445_conform_mbpp_ext --b-arm OFF5 --key deliv --n-cap 371 \
  --json runs/_analysis_r445/power_r445_deliv.json
```

**每一行的 stdout 原文存檔**進 `runs/_analysis_r445/SETTLEMENT_R687.md`，不摘要、不截斷。

---

## 三、本輪註冊的預測（**關於收官路徑，不是關於 CONFORM 的結論**）

結論面的預測是已凍結的 P-E1..P-E8，本輪不另訂。以下八條問的是「這條路走不走得通」：

| # | 預測 | 判準（指名該看到的量，不寫 `rc≠0`） |
|---|---|---|
| **P-R687-1** | 五行在**真**收官目錄上全部 rc=0 | 五個退出碼逐行記錄；任一非 0 要先分類（工具壞／前提不成立／量錯東西）再處置 |
| **P-R687-2** | 第 2 行 `NOT_EVALUATED=0` 且 `BROKEN=0` | 這兩個計數（round682 只在 fixture 上證明過，真目錄是第一次） |
| **P-R687-3** | 第 0 行 `POOLABLE`，C1/C3/C4=HIT、C2=UNVERIFIABLE_NO_CODE_VERSION | 四個 C 的字面判定；void spread 用**新分母**（round686 §五 改成 processed） |
| **P-R687-4** | 第 3 行 terminal exact 覆算三臂皆 `exact` 通過 | 三臂各自的 exact 標記（round682 說這要到收官那一刻才第一次通電） |
| **P-R687-5** | 第 1 行產物的 `key` 欄位 == `deliv` | 直接讀 `pooled_deliv.json` 的 `key`；不是看指令有沒有打對 |
| **P-R687-6** | r445 單獨的 `disc_rate` 落在 `[0.036, 0.145]`（round678 Q4 未觸發）⇒ 投影仍有效 | 第 4 行印的 `disc_rate`。**落在區間外 ⇒ round678 投影作廢，不准沿用 3.50pp／703** |
| **P-R687-7** | 三臂 `infra_void` 收官時仍 0（中止門檻 20% 未觸發） | summary 三臂的 void 計數 |
| **P-R687-8** | CONFORM 的 `calls_per_task` 顯著低於 5.00 ⇒ round684 §二 的成本不對稱前提成立 | 印出的 c/t；若 ≥4.5 則 P-E6/ABORT 相關格另議 |

**P-R687-E（不是預測，照實回報）**：併庫 371 題的 deliv CI 與四格表判定、
新 192 題單獨的 CI、r444 原始 179 題的 CI ——**三份都要報**（round682 §六）。

---

## 四、事前寫死的推翻條件

1. **Q4（沿用 round678）**：r445 的 `disc_rate` 若 < 0.036 或 > 0.145，
   round678 的投影（MDE 3.50pp、N₈₀≈703）**作廢**，收官文字不准引用那兩個數，
   改寫「投影前提失效、本輪未重算」。
2. **若五行中任一行 rc≠0**：先按 round682 判準的 A/B/C 三類分類
   （A=工具壞、B=前提不成立、C=我量錯東西），**不准當場改工具去讓它變綠**——
   除非是 A 類且修法不改任何既有輸出鍵。
3. **若 G1 過但 G2 的 `run_terminal` 為 false**：以 G2 為準，不收官。
   行數對不代表 runner 認為自己跑完了。
4. **若冒出事前沒預期到的一類**：照實寫、人眼確認、**不算進上面八條的計數**、
   **不當場補判準**（記憶鐵律，round678 §五、round684 都踩過）。

---

## 五、本輪不做的事（事前綁死）

- 不改任何臂的邏輯、門檻、判定口徑、八條預測、四格表、`equal_budget_comparison_valid`。
- 不改 `pooled_paired_ci.py`／`power_paired.py`／`conform_settle.py` 的既有輸出鍵。
- run 未退出前：不 `git add` r445 目錄、不 stash、不 checkout、不 reset、不殺、不催。
- 修前修後對照一律 `git show HEAD:<path>`，**不用 `git stash`**（round686 §十 的自我檢討）。
- 不起第二個 gain_run、不寫 `local` 到 NEXT_MODEL、不 `touch STOP`、
  不動 1004／8765／8766、不碰展件。
