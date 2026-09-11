# R460R 預註冊：H-MIX vs CONFORM 的**五次獨立複製**（LCB v2、120 題、六臂、新 seed × 5）

（2026-09-11，Opus 實作、待 Fable 稽核。**在任何 r460r 資料之前**——本檔寫完時
`runs/` 底下沒有任何 `g_r460r*` 目錄，五顆 seed 在 50 個 `runs/*/summary.json` 裡
一次都沒出現過，證明指令見 §七-1。零模型呼叫、零 ssh。）

本檔授權的東西**只有**：下面 §一 那 30 個 run 名字、五顆 seed、
以及 §四 的排程器與 §五 的稽核量具 v2。其餘一律照
`DECISION_20260907_R460_HARNESS_PREREG.md`（以下簡稱 **R460 預註冊**）——
**門檻、家族、分母、區間、四狀態、winner's curse 免責，一個字都沒有動。**

---

## 〇、要解的問題：R460 的 +13.33pp 是不是複製得出來

R460 的收官（`DECISION_20260911_R460_FABLE_AUDIT_HARNESS.md`）判 H-MIX
**EFFECTIVE**：對 CONFORM +13.33pp、95% CI [+4.22, +19.46]、Holm p_adj=0.0112、
假交付 29→14、token 與 CONFORM 相同。那份裁決自己寫著兩條限制：

- **單一 run、n=120**；§九 的推翻條件第一條就是「在別的題庫上預註冊複製而 c ≥ b
  ⇒ 降為『一次顯著』」。
- **winner's curse**：n=120 對 +10pp 的檢定力只有 0.43–0.63 ⇒ 能被判顯著的點估計
  被截斷在 MDE 以上 ⇒ **+13.33pp 是上偏估計**。

本 run 問的是**同一個題庫上的取樣穩定性**：同樣 120 題、同樣六臂、同樣預算，
只換 seed（⇒ 換題序、換 persona 指派、換模型取樣），**重跑五次**，
每一次各自套 R460 §六 那套事前規則。

### 本 run **不**回答什麼（收官不准借用）

1. **不**回答「換題庫還成不成立」——那是 LCB v3 的事（R460 §九 的推翻條件）。
   五次複製共用同一個 120 題題庫 ⇒ **題目層級的效果**（這批題剛好適合迴圈）
   在五次之間是**完全相關**的，複製不掉。這一條寫在 §六-2 的誠實邊界，
   收官必須原樣帶著。
2. **不**回答「H-PI／H-OC 哪條比較好」（R460 §六-(7)-6 的禁令照舊）。
3. **不**回答「效果量是多少」——五次的點估計**不准平均**，也**不准併 n**（§二-3）。

---

## 一、30 個 run 名字、五顆 seed、逐塊指令

每一次複製 ＝ **120 題切成六塊 × 20 題**，六臂交錯（`for task: for arm`），
與 R460 逐字相同。五次複製 ＝ 30 塊。

| 複製 | seed | 六個 run 目錄 |
|---|---|---|
| 1 | `g-r460r1-lcb2` | `runs/g_r460r1_harness_lcb2_a1`、`runs/g_r460r1_harness_lcb2_a2`、`runs/g_r460r1_harness_lcb2_a3`、`runs/g_r460r1_harness_lcb2_b1`、`runs/g_r460r1_harness_lcb2_b2`、`runs/g_r460r1_harness_lcb2_b3` |
| 2 | `g-r460r2-lcb2` | `runs/g_r460r2_harness_lcb2_a1`、`runs/g_r460r2_harness_lcb2_a2`、`runs/g_r460r2_harness_lcb2_a3`、`runs/g_r460r2_harness_lcb2_b1`、`runs/g_r460r2_harness_lcb2_b2`、`runs/g_r460r2_harness_lcb2_b3` |
| 3 | `g-r460r3-lcb2` | `runs/g_r460r3_harness_lcb2_a1`、`runs/g_r460r3_harness_lcb2_a2`、`runs/g_r460r3_harness_lcb2_a3`、`runs/g_r460r3_harness_lcb2_b1`、`runs/g_r460r3_harness_lcb2_b2`、`runs/g_r460r3_harness_lcb2_b3` |
| 4 | `g-r460r4-lcb2` | `runs/g_r460r4_harness_lcb2_a1`、`runs/g_r460r4_harness_lcb2_a2`、`runs/g_r460r4_harness_lcb2_a3`、`runs/g_r460r4_harness_lcb2_b1`、`runs/g_r460r4_harness_lcb2_b2`、`runs/g_r460r4_harness_lcb2_b3` |
| 5 | `g-r460r5-lcb2` | `runs/g_r460r5_harness_lcb2_a1`、`runs/g_r460r5_harness_lcb2_a2`、`runs/g_r460r5_harness_lcb2_a3`、`runs/g_r460r5_harness_lcb2_b1`、`runs/g_r460r5_harness_lcb2_b2`、`runs/g_r460r5_harness_lcb2_b3` |

塊 → offset 的對應**五次相同**：a1 `--offset 0`、a2 `--offset 20`、a3 `--offset 40`、
b1 `--offset 60`、b2 `--offset 80`、b3 `--offset 100`。

每一塊的指令逐字（`<OUT>`／`<OFFSET>`／`<SEED>` 取上表，其餘六格 30 塊完全相同）：

```
python3 ops/gain/gain_run.py \
  --out <OUT> --n 20 --offset <OFFSET> \
  --decision DECISION_20260911_R460R_FIVE_REPLICATIONS_PREREG.md \
  --seed <SEED> --arms OFF,CONFORM,OFF5,HPI,HOC,HMIX --bank lcb2 \
  --models gemma-4-12b-it-qat --probe-sample 0 --gauge-scope bank \
  --request-timeout-s 1200 --review-timeout-s 380 --retries 4
```

### 與 R460 唯一的三處不同（每一處都有理由，都不動判準）

| 項 | R460 | R460R | 為什麼 |
|---|---|---|---|
| `--seed` | `g-r440-lcb2`（重用 r447 的） | **五顆新 seed**，彼此不同 | 複製的定義就是「重新抽一次」。⚠ LCB v2 bank 就是 120 題、`--n 20 × 6` 取全部 ⇒ **seed 只打亂順序、不抽樣**（R460 §二-4 實測）⇒ 五次複製的**題目集合完全相同**，換的是題序、persona 指派與模型取樣。**這是本 run 最重要的誠實邊界**，見 §六-2 |
| `--gauge-scope` | a 組 `slice`（3/3、3/3、4/4）、b 組 `bank`（12/12） | **30 塊全部 `bank`（12/12）** | R460 的 b1 在 slice 模式下量到 0/0 而正確地拒跑（後 60 題只有 2 題有參考解 ⇒ 任何三等分必有一塊 0）。bank 模式對**整個題庫**驗兩個方向 ⇒ 與切法無關、比 slice **更強**，而且它不進任何一條臂的執行路徑 |
| 端點 | 固定表（a 組一顆、b 組一顆） | **由排程器分配**（§四） | 30 塊要跑，兩顆卡的可用併發不同（1004×3、1003×1）。固定表在這個規模下只會讓卡空轉 |

**其餘完全相同**：bank `lcb2`（120 題，sha256 前 16 碼 `b98f027213e2469a`）、
六臂、`HARNESS_BUDGET`（max_calls 5／max_tokens 32,000／max_wall_s 900／
sandbox_timeout_s 10／truncation_retries 1／doom_threshold 2）、
模型 `gemma-4-12b-it-qat`、`--request-timeout-s 1200`（牆鐘護欄 1260 s）、
`--review-timeout-s 380`、`--retries 4`、`--probe-sample 0`、agent pool 六 persona。

### seed 授權（發射器逐字對釘）

發射器 `ops/gain/launch_harness_rep_block.sh` 要求 DECISION 內文含逐字的
`SEED_AUTHORIZED_SET: <seed> <- <集合，或 NONE>`，並掃過**所有**
`runs/*/summary.json`（扣掉本 run 自己那 30 個名字、r447、與 R460 那六塊），
命中集合必須**恰好等於**授權集合。多一個或少一個都停——「少一個」代表
被引用的 run 不見了，而**量不到不是通過**。

```
SEED_AUTHORIZED_SET: g-r460r1-lcb2 <- NONE
SEED_AUTHORIZED_SET: g-r460r2-lcb2 <- NONE
SEED_AUTHORIZED_SET: g-r460r3-lcb2 <- NONE
SEED_AUTHORIZED_SET: g-r460r4-lcb2 <- NONE
SEED_AUTHORIZED_SET: g-r460r5-lcb2 <- NONE
```

`NONE` ＝ 這顆 seed **一次都沒被用過**。⚠ 這比 R460 的「授權重用」**更嚴**：
R460 允許一個具名的舊 run，本 run 一個都不允許。
⚠ 排除清單裡的 r447 與 R460 六塊，對這五顆 seed 是**可證明的 no-op**
（它們的 seed 是 `g-r440-lcb2`，永遠不會命中）；照樣寫進去是因為 Fable R4
指名了它，而且哪天有人拿這支發一顆重用的 seed 時，那一格才不會變成
「當初為什麼少了一個名字」。牙齒逐條可驗：`tests/test_r460r_scheduler.py`
把發射器裡那段掃描原封不動抽出來實跑——**任何**不在排除清單裡的 run 用了
這五顆 seed，照樣 `abort_seed_set_mismatch`。

---

## 二、決策規則：**R460 §六 一個字沒改，逐次獨立套用**

### 二-1　逐次判（Fable R2）

- 每一次複製 **各自** 走一次 `ops/gain/analyze_r460.py`（六塊一起餵），
  得到 `per_arm.*`／`paired.*`／`holm.*`／`decision.*`。
- **Holm 家族仍然是 6 個檢定**（3 條 H 臂 × OFF／CONFORM），
  **在那一次複製之內**調整。⚠ **不准**把五次的 30 個檢定丟進同一個 Holm——
  那會把「複製」偷偷變成「一個 n=600 的實驗」。
- 四狀態（`EFFECTIVE`／`COSTLY_BUT_REAL`／`RULED_OUT`／`INCONCLUSIVE`）
  的門檻逐字是 R460 §六-(4)：(i) Δ_O ≥ +25.0pp ∧ Δ_C ≥ +10.0pp、
  (ii) Holm 兩者 p_adj < 0.05、(iii) `tpc_incl_void ≤ OFF5 的`、
  (iv) 假交付 ≤ CONFORM + 5.0pp。
- **主要假設 ＝ H-MIX vs CONFORM**（R460 §六-(4) 逐字）。
- E-1..E-7 的效力前提照舊；**E-7 的拓撲那一格改判 `scheduled`**（§四-3）。

### 二-2　彙總（**描述性**，事前註冊）

`ops/gain/analyze_r460r.py` 印四樣東西，一樣都不准少：

1. 五次之中 H-MIX 判成 `EFFECTIVE`／`COSTLY_BUT_REAL`／`INCONCLUSIVE`／
   `RULED_OUT` 各幾次（`aggregate.verdict_counts_HMIX`）。
2. 五個 Δ_C 與**未調整**的 95% CI（`aggregate.delta_c_pp_by_rep`／`ci95_by_rep`）。
   每一次引用區間都要逐字附「區間未做多重比較調整；仲裁以 analyzer 為準」。
3. 五個 Holm `p_adj`（`aggregate.holm_p_adj_by_rep`）與顯著次數。
4. **宣稱規則**（事前寫死，`aggregate.statement_rule`）：

> **5/5 同號（Δ_C > 0）且 ≥4/5 Holm 顯著 ⇒ 可以寫「複製穩定」；
> 否則逐次照實列**——不准挑一次、不准平均、不准寫「多數支持」。

判到哪一句就逐字印在 `aggregate.statement`。**沒有隨機效應模型、
沒有 meta-analysis、沒有合併效果量**：那些都需要把五次當成獨立樣本，
而五次共用同一批題目（§六-2），獨立性不成立。

### 二-3　禁令（沿用＋新增）

1. **不准併 n**（R449C §六-2、R460 §六-(7)-3）。`analyze_r460r.py` 裡**沒有**
   任何把五次 rows 接起來的路徑；`aggregate` 的欄位形狀自己說得出來
   （selftest `J_aggregate_has_no_pooled_estimate` 逐條驗）。
2. **不准**看到數字之後改窗、改仲裁欄位、改分母、改家族、改狀態定義。
3. **不准**挑「跑得最好的那一次」當代表，也**不准**把五個點估計平均。
4. **不准**把某一次的 INCONCLUSIVE 讀成「等價」「打平」「迴圈沒用」
   （R460 §六-(7)-5）。
5. **不准**跨複製配對（五次的 `task_id` 完全重疊，但那是**不同的模型取樣**，
   不是同一格的重複測量；把它當配對等於假設 persona 指派與題序不影響結果）。
6. **不准**只跑完三次就結算。少於五次 ⇒ `aggregate.reps_analyzed < 5`
   ⇒ 宣稱規則自動落在「逐次照實列」，而且要寫清楚跑了幾次。

---

## 三、事前預測（P-R1..P-R5）——**逐次判，先寫死**

錨一律是 R460 的實測值，**錨不是門檻**：

| # | 預測 | 仲裁欄位（那一次複製自己的） | R460 錨 |
|---|---|---|---|
| **P-R1** | Δ_C > 0 | `paired.HMIX_vs_CONFORM.delta_pp` | +13.33pp |
| **P-R2** | Δ_C ≥ **+10.0pp**（點估計） | 同上 | +13.33pp |
| **P-R3** | Holm 後顯著 | `holm.HMIX_vs_CONFORM.p_adj < 0.05` | 0.0112 |
| **P-R4** | 假交付 H-MIX **<** CONFORM | `per_arm.HMIX.false_delivery_pp` vs `per_arm.CONFORM.false_delivery_pp` | 14 件 vs 29 件 |
| **P-R5** | token/題 H-MIX ≤ **1.2 ×** CONFORM | `tokens.HMIX.tokens_per_task` ÷ `tokens.CONFORM.tokens_per_task` | 5,677 vs 5,805（0.978×） |

### 三-1　**寫在資料之前的預期**（Fable R2 指名要寫）

- **winner's curse**：R460 的 +13.33pp 是**能被判顯著**的點估計，
  它被截斷在 MDE 以上 ⇒ **上偏**。⇒ **複製跑的點估計預期會比 +13.33 小**，
  而且 **P-R2（≥ +10pp）在某幾次複製失敗是預期之內的事**，不是「效果消失」。
- **檢定力**：n=120 對 +10pp 的檢定力是 **0.43–0.63**（R460 §五）。
  ⇒ **就算真值真的是 +10pp，五次裡預期只有 2–3 次通過 P-R3。**
  「5 次裡 2 次顯著」**不是**反證；「5 次全部顯著」也**不是**加碼的理由。
  這兩句話由 `analyze_r460r.py` 每次執行都印
  （`aggregate.power_expectation`／`winners_curse_disclaimer`），不印不准結算。
- 因此本檔**事前**就說清楚：宣稱規則要求 ≥4/5 Holm 顯著，
  而事前預期只有 2–3/5 ⇒ **「複製穩定」這句話事前就是一個高門檻，
  達不到是常態不是失敗**。達不到時要寫的是「五次的 Δ_C 分別是 …，
  其中 k 次顯著」，不是「複製失敗」。

---

## 四、排程器（Fable R3／R4）

發射器：`ops/gain/launch_harness_rep_block.sh`（**一次一塊**）。
排程器：`ops/gain/schedule_harness_reps.py`（30 塊的佇列與槽位）。

### 四-1　佇列與槽

- **佇列順序**：`r1a1 r1a2 r1a3 r1b1 r1b2 r1b3 r2a1 … r5b3`（依複製排，不交錯）。
  理由：一次複製的六塊全跑完才判得了它（少一塊 ⇒ `block_count_not_6` ⇒ 那次 INVALID）
  ⇒ 依複製排的話每收完六塊就多一個可判的結果。
- **槽**：`1004#1`、`1004#2`、`1004#3`、`1003#1` ＝ **1004 三個、1003 一個**。
  - 1004 ＝ `http://100.86.226.21:1234/v1/chat/completions`，實測 3 併發不掉速
    （2026-09-08；R460 的 b 組三塊在上面跑完 120/120/120、void 0）。
  - 1003 ＝ `http://100.119.113.56:1234/v1/chat/completions`，
    **一次只准一塊**：那台在 262k context 之下 `decode() failed: bad alloc`、
    重載成 49k 之後三併發長生成又撞 `Context size has been exceeded`／
    `bad allocation`（兩次當機的紀錄在
    `DECISION_20260908_R460_FABLE_LAUNCH_NOTES.md` §四）。
  - **任何一塊都不准走 hub**（`8765`）；發射器 `abort_hub_endpoint` 硬擋。
- **first-fit**：依佇列順序，每一塊找第一個**允許它**的空槽。
  ⇒ **第一輪會發的四塊逐字是**：
  `r1a1→1004#1`、`r1a2→1004#2`、`r1a3→1004#3`、`r1b1→1003#1`。
- ⚠ **`--reps`／`--hosts` 只篩，不改這張表**（round460r-2）。
  `SLOTS` 與 `REPS` 是「註冊了什麼」，旗標是「這次排什麼」。
  **2026-09-11 人類指示之下實際發的是 `--reps 1 2 3 --hosts 1004`**
  ⇒ 三個槽、18 塊，第一輪發的是 `r1a1→1004#1`、`r1a2→1004#2`、`r1a3→1004#3`
  （逐字見 §一〇）。`--hosts` 打錯字 ⇒ 中止，不默默退回四個槽。
- ⚠ **`<OUT>.endpoint` 認不出來 ⇒ 封鎖全部端點**（fail closed）。
  「檔案不見了」與「寫著一個不在槽表上的端點」是同一件事：
  不知道那塊在哪一顆卡上，就不能再往任何一顆加負載。
  （認得出來但這次沒被 `--hosts` 選中的**不算**認不出來——
  那塊的負載明確落在別顆卡，不影響這顆還剩幾格。）

### 四-2　收與重排

- 每 **60 s** 輪詢一次。某塊 `summary.json` 的 `run_terminal=true`
  **且每一臂 `infra_void / processed ≤ 20%`** ⇒ 放掉那個槽，記成完成。
- **terminal 但某臂 void > 20%**，或**行程死了又沒有 terminal** ⇒
  該塊的目錄、`.launch.log`、`.backend.json`、`.endpoint` 整組搬到
  `runs/_aborted/<name>_void_<ts>`（撞名加尾碼），**只重排一次、只准上 1004**。
  - 20% 那條線沿用 R460 §十／§六-(6)-c（void 率 > 20% ⇒ 資料不進結論）。
  - **只重排一次**：重排無上限＝「一直重試到資料看起來正常為止」＝選擇性重跑，
    會把後端的壞運氣洗成資料。用完兩次還壞 ⇒ 記成**放棄**，留給人裁決。
  - **只准上 1004**：1003 已經在同一個 harness 上死過兩次，把重排丟回去
    等於用同一個已知會壞的形狀再賭一次。
- 重排的塊**回到它在佇列裡原本的位置**（佇列永遠是 §四-1 的正規順序，
  排程器每一輪都從磁碟重推，不維護一份可變的佇列）。
  ⇒ 同一次複製的塊天然排在後面幾次複製之前，那一次不會被自己最後一塊拖到最後。
  ⚠ 這不會 head-of-line blocking：重排的塊如果只等得到 1003 的空槽，
  排程器會跳過它去發下一塊，1003 的槽不會空轉；它留在原位，
  下一輪 1004 一空就輪到它（`test_requeued_block_does_not_block_the_head_of_the_line`）。

### 四-3　收官時的拓撲對帳（analyzer 這一側）

`ops/gain/analyze_r460.py` 新增 `--topology scheduled`，
`topology.variant == "scheduled"`。保留的不變量（每一條都是 E-7 真正承重的）：

1. **一塊一端點**（塊內六臂交錯 ⇒ 同一題的六臂同後端、同行程、同塊）；
2. 塊間 `task_id` 兩兩零交集、**聯集恰好 120**；
3. **不走 hub**；
4. **塊數 6**；
5. **逐端點的「同時在跑的塊數」≤ 上限**——1004 ≤ 3、1003 ≤ 1。
   ⚠ 這條**從資料算**：每一塊在 `calls.jsonl` 上有一段
   `[第一通 ts_ms, 最後一通 ts_ms + latency_ms]` 的時間窗，
   同一顆端點上重疊的窗數就是那一刻的併發度。
   排程器的槽位是**事前**的閘門，這條是**事後**的對帳——排程器說了不算。
   名單外的端點一律 `endpoint_not_registered`（沒登記上限 ≠ 沒有上限）；
   算不出時間窗一律 `block_ts_unrecorded`（**算不出不是通過**）。
   逐塊端點與對應關係記在 `topology.endpoint_of_block`、
   `topology.blocks_per_endpoint`、`topology.max_concurrent_by_endpoint`。

**舊的兩種 variant 沒有被吃掉**：`fixed`（預設）仍然判
`two_backends_3_3`／`one_backend_6`，R460 的六塊重跑 analyzer 逐字不變
（selftest `Q6i_fixed_mode_is_unchanged`）。突變體 **M12** 專門證明
「併發上限那條沒有牙齒的話會全綠通過」（`Q6f` 必須變紅）。

### 四-4　P-H0 在複製跑**不判**

R460 的 P-H0 錨是「r447 前 60 題的 32/60」，而那個錨的前提是**同一顆 seed
⇒ 同題序**。五次複製換了 seed ⇒ 題序不同 ⇒ **那個錨在這批資料上不存在**。
硬讀會拿一個**別的** 60 題去對一個對不上的錨，而且還會印出看起來很正常的
HIT／MISS。⇒ `--rep k` 之下 `prereg.P-H0.hit == "NOT_APPLICABLE"`。
後端漂移在複製跑裡由「五次之間 OFF 的差異」自己承擔（描述性印出），**不另設窗**。

---

## 五、V/GT 稽核量具 v2（Fable R5）——**事前的量具驗證，寫在資料之前**

### 五-1　改了什麼

`ops/gain/harness_vgt_audit.py` 的 v1 把**整段送出文字**當掃描對象。
R460 六塊因此共報 **90 筆**違規，而 Fable 逐筆分類之後**全部**是偽陽性
（`DECISION_20260911_R460_FABLE_AUDIT_HARNESS.md` §一）。
**量具偽陽性會把真訊號淹掉**：90 筆噪音之下，第 91 筆真的洩漏沒有人看得出來。

v2 的判準改成**這段文字是誰寫的**：

- **(a)** 題目原文（`task['prompt']`）逐字扣掉——六臂共用、與 OFF 相同。
- **(b)** **assistant 訊息完全不掃**。（flattened 線路模式下整段對話被攤平成
  一則 user 訊息 ⇒ 先依 `--- REPLY n ---` 標記切回角色再套這一條。
  R460 六塊全是 multiturn ⇒ 這段在 R460 上不改變任何數字；
  它擋的是**下一次**線路退回攤平模式時量具安靜地變回 v1。）
- **(c)** 回饋訊息裡的回聲不算 harness 的話，三條、各自很窄：
  - needle 逐字在該題 `visible_check` 原始碼裡（D7：可見測資照設計就給 worker 看）；
  - needle **等於**（不是包含）harness 用**自己那支解析器**（`parse_selftests`）
    從**同一次請求**的模型回覆裡讀出來的某個 `SELFTEST` 值；
  - needle **只出現在 `got=` 那一段裡**（沙箱回聲）——它逐字是
    `repr(候選函式(*可見測資的 args))`，harness 沒有任何管道把隱藏 GT 放進去；
    真要從隱藏側取值，變的會是 `args=`／`want=`／`you expected=`，**那三格照查**。
    這一條記成 `excused_as="got_sandbox_echo"` 並計入 `excused_by_rule`
    ——**留證，不是掃描前塗掉**（見 §五-1b）。
- **(d)** 凍結的 Rules 那行照舊扣掉（`exec(` 唯一的合法出處）。

其餘 harness 寫進 system／user 的文字**一律照查**；`system` 訊息**一格豁免都不給**
（**`got=` 也是一格豁免 ⇒ system 連它都不吃**）；
`CODE_NEEDLES`（`__tests`／`__aeq`／`__canon`）**不給 (c) 的豁免**——
驗收碼原始碼被貼進 user 訊息永遠是紅的，**藏在 `got=` 後面也一樣**。

### 五-1b　round460r-2：v2 初版的三處 must-fix（仍在任何 r460r 資料之前）

Fable 稽核 v2 的實作時抓到三件事：文件說的與程式碼做的不一致。三件事同源
——v2 初版把 (c) 的 `got=` 做成「**掃描前把整段換成佔位字串**」，
而那個實作細節同時踩到三格。逐條，改的都是量具不是判準：

| # | v2 初版做的 | 為什麼是錯的 | 現在做的 |
|---|---|---|---|
| 1 | `redact_harness_text` **不分角色** ⇒ `system` 也吃 `got=` 塗抹 | §五-1 自己寫著「`system` 一格豁免都不給」，而 `got=` 就是一格豁免。persona 文字沒有沙箱回聲的理由 | `system` 只扣 (a)＋(d)；`system` 裡的 `got=<隱藏 repr>` 是**紅的** |
| 2 | `CODE_NEEDLES` 掃的是**塗抹後**的文字 | `hint: got=x __tests = [...]` 之下 `__tests` 被整段吃掉 ⇒ **把驗收碼原始碼藏在 `got=` 後面就能過稽核**。`got=` 的合法性論證撐得住**值層級**的 repr（那一段是某個函式的回傳值），撐不住 `__tests` 這種**識別字** | `CODE_NEEDLES` 掃**只扣掉 (a)＋(d)** 的文字；`hidden_case_leak` 才掃扣掉 `got=` 之後的文字 |
| 3 | 塗掉之後那一筆**沒有任何紀錄** | §五-3 的對帳表寫著「`got=` 沙箱回聲 1」，而那個 1 是**人工**數出來的，機器不吐 ⇒ 豁免被靜音 | 進 `excused`（`excused_as="got_sandbox_echo"`）並計入 `excused_by_rule`，與另外兩條豁免同一個形狀 |

三處都有反向負控，見 §五-4。

### 五-2　**與 Fable R5 原文的一處明文偏離**

R5 寫的是「the immediately preceding assistant message」。**實測擋不住**：
HOC 的 `SELFTEST` 引述來自**計畫輪**的回覆（同一次請求裡的第一則 assistant），
不是緊鄰的前一則——照原文寫，R460 b1／b2 的 14 筆仍然會是紅的。

因此範圍放寬成「同一次請求裡的**任何一則** assistant 訊息」，
但**同時把判準收得比原文更緊**：不是子字串比對，而是「**等於** harness
自己解出來的那個 `SELFTEST` 值」。理由是模型寫 `["NS", 1]`、harness 印
`['NS', 1]`（`repr` 單引號）——子字串比對本來就會漏（R460 b2 實測 2 筆），
而子字串比對又會過寬（`'[1, 2]' in '[1, 2, 3]'`）。
**淨效果是豁免面比 R5 原文小。** 放寬的邊界是**同一次請求**：
那段字已經在模型的 context 裡，回貼給它傳不了新資訊。

### 五-3　**事前的量具驗證結果**（在 r460r 任何資料之前跑完）

指令（六塊 × 兩個 scope，零模型呼叫）：

```
for b in a1 a2 a3 b1 b2 b3; do
  for sc in v1 v2; do
    python3 ops/gain/harness_vgt_audit.py --run runs/g_r460_harness_lcb2_$b \
      --bank lcb2 --scope $sc --out ops/gain/replay/r460/vgt_${sc}_${b}.json
  done
done
```

| 塊 | v1 違規 | v2 違規 | v2 豁免（可見驗收碼／SELFTEST／`got=`） |
|---|---|---|---|
| a1 | 1 | **0** | 0 ／ 0 ／ 0 |
| a2 | 5 | **0** | 0 ／ 0 ／ 0 |
| a3 | 1 | **0** | 0 ／ 0 ／ 0 |
| b1 | 31 | **0** | 4 ／ 12 ／ **1** |
| b2 | 2 | **0** | 0 ／ 2 ／ 0 |
| b3 | 50 | **0** | 0 ／ 0 ／ 0 |
| **合計** | **90** | **0（六塊全 CLEAN）** | 4 ／ 14 ／ **1** |

⚠ **round460r-2 之後 `got=` 那一欄由機器自己吐**（`excused_by_rule.got_sandbox_echo`）。
v2 初版是掃描前塗掉 ⇒ 那個 1 只存在於人工分類裡；現在
`ops/gain/replay/r460/vgt_v2_b1.json` 自己寫著它。
`tests/test_r460r_scheduler.py::test_recorded_audit_v2_evidence_matches_a_fresh_run`
逐格對釘上面這張表（不是只對一個總數）。

90 筆逐筆對帳（機械規則對每一筆只記**第一條**適用的排除理由；
重算腳本見 §七-2）：

| 去向 | 筆數 |
|---|---|
| (a) 題目原文 | 54 |
| (b) assistant 訊息 | 17 |
| (c) SELFTEST 豁免 | 14 |
| (c) 可見驗收碼豁免 | 4 |
| (c) `got=` 沙箱回聲 | 1 |
| **仍是違規** | **0** |

（與 R460 收官那份**人工**分類總數相同、分格不同：人工分的是
「題目原文 54／SELFTEST 22／模型回覆 8／可見回聲 5／Rules 1」。
兩份都是 90，差別在把「模型自己把 Rules 那行改寫」這類歸到哪一格。）

### 五-4　牙齒（放寬必須有反向負控）

`tests/test_r460r_scheduler.py` 與既有的 `tests/test_gain_harness_arms.py`
一起釘住下面每一條，缺一條就等於把稽核關掉：

- 把一個**真的**隱藏 case 的 repr 塞進 harness 自己寫的 user 訊息 ⇒ **VIOLATION**；
- 塞進 **system** 訊息 ⇒ **VIOLATION**（system 不給任何豁免）；
- 塞進 **system** 訊息的 `got=` 後面 ⇒ **VIOLATION**（§五-1b 第 1 條；
  `test_v2_system_message_gets_no_got_excuse_either`）；
- 塞進 `got=` **以外**的欄位（`want=`／`args=`／`you expected=`）⇒ **VIOLATION**；
- 把驗收碼原始碼貼進 user 訊息 ⇒ **VIOLATION**（CODE needle 不給豁免）；
- 同一行的 `got=x __tests = [...]` ⇒ **VIOLATION**（§五-1b 第 2 條；
  `test_v2_got_does_not_launder_a_code_needle_on_the_same_line`）；
- needle 只在 user 訊息的 `got=` 裡 ⇒ **CLEAN 但留一筆**
  `excused_as="got_sandbox_echo"`（§五-1b 第 3 條；
  `test_v2_records_the_got_excusal_instead_of_redacting_it_silently`）；
- `--scope v1` 在六塊上仍然逐字重現 **90**（收官紀錄可重跑）；
- 對不到題目的 `task_id` ⇒ **VIOLATION**（沒有檢查不准冒充沒有違規）。

### 五-5　量具的誠實邊界（沿用）

`TRIVIAL_NEEDLE_REPRS`（`True`／`False`／`None`／`0`／`1`／`-1`／`[]`／`{}`／
`()`／`''`／`""`）與 `MIN_NEEDLE_CHARS = 6` **一個字沒動**，
`needles_skipped_trivial` 照樣逐塊印出來——跳過的東西要說出來，
不能讓「沒有違規」順手把「沒有檢查」蓋掉。

---

## 六、誠實邊界（收官必須原樣帶著，一條都不准掉）

1. **五次複製不是五個獨立實驗。** 同一個題庫、同一顆模型、同一套 prompt；
   換的只有 seed（題序、persona 指派）與模型取樣。
2. **題目層級的效果複製不掉。** 五次共用**同一批 120 題** ⇒
   「這批題剛好適合把失敗訊息貼回去改」這個可能性在五次之間是**完全相關**的。
   ⇒ 就算 5/5 同號且全部顯著，能講的也只是「**在這 120 題上**穩定」，
   **不是**「這個機制普遍成立」。換題庫的複製是 LCB v3 的事，本 run 不回答。
3. **單一模型、單一後端家族。** 兩顆卡載的都是 `gemma-4-12b-it-qat`。
4. **兩顆卡的設定不同**（1003 的 context 是 49k、1004 是它自己的原設定）
   ⇒ 塊落在哪一顆是**題目層級**的干擾項（同一塊的六臂同卡）⇒
   配對差分把它消掉，但**塊間點估計不得互相比較**（R460 §六-(0) 照舊）。
   ⚠ 複製跑多一件事：**同一次複製的六塊可能落在不同卡上**，
   而分配是排程器當場決定的（誰先空誰先拿）⇒ 這是**在配對之內被消掉**的干擾，
   但它讓「這一次複製整體比另一次高」多背一個解釋。跨次比幅度只看區間重疊。
5. **時間漂移。** 30 塊要跑很久（R460 六塊約 7–8 小時；30 塊即使四併發也要好幾天），
   後端狀態、機器負載都會漂。複製之間的差異**不能**全部歸給取樣。
6. **重排的塊只在 1004 上。** 被重排過的塊因此系統性地不在 1003 上 ⇒
   若某一次複製有塊被重排，那一次的端點組成與別次不同。逐次記在
   `topology.endpoint_of_block`，收官要照實列。
7. **放棄的塊。** 一塊用完兩次還壞 ⇒ 那一次複製只有五塊 ⇒
   `block_count_not_6` ⇒ **那一次 INVALID，不判**。
   **不准**就地把 §二 的門檻搬到 n=100 上重讀（R460 §六-(6)-i 的同一條）。
8. **P-H0 不判**（§四-4）⇒ 本 run 沒有「後端有沒有漂」的事前探針。
9. **量具 v2 是新的。** 它在 R460 的資料上驗過（§五-3），但它**沒有**在
   「真的有洩漏」的**真實** run 上驗過——負控全是人工植入的。

### round460r-2 新增的三條（都在任何 r460r 資料之前；不動任何門檻／規則）

10. **這一輪全部塊都在同一顆後端上（1004）。** §一 的表寫著「端點由排程器分配」，
    而 2026-09-11 的人類指示把 1003 整顆拿走（§一〇）⇒ 實際上 r1–r3 的 18 塊
    **全部落在 1004**。後果逐條，收官要原樣帶著：
    - §六-4 那句「塊落在哪一顆卡是題目層級的干擾項」在這一輪**消失**了
      （沒有跨卡的對比）⇒ 這是**更乾淨**不是更髒；
    - 但它換成另一件事：**1004 這一顆的狀態變成整批資料的共同因子**。
      那顆卡在這幾天的任何漂移（其他人的負載、重載模型、驅動）會**同時**
      打到五次複製，而複製本來想量的就是「除了 seed 以外都一樣時的變異」。
      ⇒ 跨次差異**不能**全部歸給取樣（§六-5 的時間漂移在單卡之下更重，不是更輕）；
    - §六-6「重排的塊只在 1004 上」在這一輪是**恆真的**（所有塊都在 1004）
      ⇒ 那一條的干擾在這一輪不存在，收官不必為它加註但也不准把它刪掉
      （r4／r5 若在別的條件下跑，它會回來）。

11. **跨複製的逐端點併發要另外對帳一次。** 逐次的
    `topology.max_concurrent_by_endpoint` 只把**那一次自己的六塊**放進掃描線，
    而排程器的槽位是**跨複製**共用的：r1 的最後一塊還在跑時 r2 的第一塊就發出去了
    ⇒ 逐次全綠仍然可能整體超賣，而超賣**看起來只是比較慢**。
    ⇒ `ops/gain/analyze_r460r.py` 的 `global_topology` 把**全部複製的全部塊**
    丟進**同一條**掃描線重算，上限用同一張凍結表（1004 ≤ 3、1003 ≤ 1）。
    超過 ⇒ `endpoint_concurrency_exceeded_global` ⇒ 退出碼 1。
    名單外的端點 ⇒ `endpoint_not_registered`；算不出時間窗 ⇒ `block_ts_unrecorded`
    （**兩條都是「算不出不是通過」**，與逐次那條逐字相同）。
    峰值那一刻是哪幾塊同時在跑記在 `global_topology.peak_witness`——
    違規要指得出人，不是只報一個數字。
    ⚠ **這仍然是事後對帳**：事前的閘門在排程器的槽位，排程器說了不算。

12. **發不出去也是一次嘗試。** 發射器 preflight 擋下來（探針沒過、
    `abort_launchlog_exists`、seed 集合不符…… ＝ rc != 0）時 runner 根本沒起來
    ⇒ 磁碟上沒有 summary、沒有行程 ⇒ 那一塊下一輪還是 PENDING。
    不記一筆的話排程器會**每 60 秒重發一次、永遠**，而最常見的那個 abort
    （`.launch.log` 已存在）自己就不可能自癒。
    ⇒ sidecar 搬到 `runs/_aborted/<name>_preflight_<ts>/`（**沒東西可搬也留空目錄**，
    目錄本身就是計數單位），與 `_void_` **合計**計入 `MAX_ATTEMPTS`；
    兩次就放棄並寫進 log，留給人裁決。
    ⚠ 這**不是**新的重排權限：上限仍然是 2，只是把「發不出去」也算進那個 2 裡面
    ——放寬的是計數面，收緊的是重試面。
    ⚠ 後果與 §六-7 同一條：某塊放棄 ⇒ 那一次複製只有五塊 ⇒ `block_count_not_6`
    ⇒ **那一次 INVALID，不判**。

---

## 七、自我驗證（發射前做完，零 API、零 ssh，逐條可重跑）

### 七-1　五顆 seed 是新的

```
python3 - <<'PY'
import glob, json
seeds = {}
for f in sorted(glob.glob("runs/*/summary.json")):
    try: seeds.setdefault(json.load(open(f, encoding="utf-8")).get("seed"), []).append(f)
    except Exception: pass
for k in range(1, 6):
    print(f"g-r460r{k}-lcb2 ->", seeds.get(f"g-r460r{k}-lcb2"))
PY
```

2026-09-11 實跑：掃過 **50** 個 `runs/*/summary.json`，
`g-r460r1-lcb2` … `g-r460r5-lcb2` **五顆全部是 `None`（一次都沒被用過）**；
`g-r440-lcb2` 命中 7 個（r447 ＋ R460 六塊），與 R460 的紀錄一致。
`runs/` 底下 `g_r460r*` 目錄：**0 個**。

### 七-2　量具 v2 的逐筆對帳可重算

§五-3 那張對帳表由 `ops/gain/replay/r460/vgt_v1_*.json`（＝既有的 `vgt_*.json`）
與 `ops/gain/replay/r460/vgt_v2_*.json` 兩組落盤檔重算；
兩組都由上面那個 for 迴圈產生，**零模型呼叫**。

### 七-3　analyzer 沒有漂

```
python3 ops/gain/analyze_r460.py --selftest         # 含 Q6e..Q6i 五條新的
python3 ops/gain/analyze_r460.py --mutation-check   # 含 M12
python3 ops/gain/analyze_r460r.py --selftest        # 在 R460 六塊上對釘已知答案
```

`analyze_r460r.py --selftest` 逐條釘住 R460 的收官數字：
H-MIX 84.17%、CONFORM 70.83%、Δ_C +13.33pp、Holm p_adj 0.0112、
假交付 14 vs 29、裁決 `EFFECTIVE`——**任何一個對不上就表示本輪動到了仲裁值**。

### 七-4　排程器的乾跑

**槽表全開時**（`--reps`／`--hosts` 都不給）：

```
python3 ops/gain/schedule_harness_reps.py --dry-run
```

第一輪會發的四塊（first-fit、槽位順序 1004#1/#2/#3 → 1003#1）：

```
r1a1 (offset 0)  → 1004#1  http://100.86.226.21:1234/v1/chat/completions
r1a2 (offset 20) → 1004#2  http://100.86.226.21:1234/v1/chat/completions
r1a3 (offset 40) → 1004#3  http://100.86.226.21:1234/v1/chat/completions
r1b1 (offset 60) → 1003#1  http://100.119.113.56:1234/v1/chat/completions
```

**2026-09-11 人類指示之下實際要跑的那一行**（§一〇）：

```
python3 ops/gain/schedule_harness_reps.py --dry-run --reps 1 2 3 --hosts 1004
```

⇒ 槽只有 `1004#1/#2/#3`、佇列 18 塊（`r1a1 … r3b3`）、
第一輪發 `r1a1`／`r1a2`／`r1a3`，`1003` 那一格只出現在「本次停用 1003」那一句裡。
對釘：`tests/test_r460r_scheduler.py::test_dry_run_with_the_humans_flags_shows_1004x3_and_eighteen_blocks`。

假 `runs/` 的完整模擬（含收官、void 45% ⇒ 作廢重排、行程死掉 ⇒ 作廢重排、
第二次又壞 ⇒ 放棄、殺掉排程器再起來計畫不變）：
`tests/test_r460r_scheduler.py::test_full_simulation_slot_allocation_and_requeue`
與 `::test_simulation_dead_process_without_terminal_is_requeued`。
preflight 失敗的模擬（rc != 0 ⇒ sidecar 搬走、計入重排、兩次放棄）：
`::test_preflight_failure_counts_toward_max_attempts_and_then_gives_up`。

---

## 八、中止準則（發射之後，什麼情況要停）

1. **某一次複製的任一臂 void 率 > 20%**（以進入分析的資料算）⇒ 那一次不判
   （R460 §十）。塊層級的同一條線由排程器在收塊時就攔下來（§四-2）。
2. **同一塊連續兩次被作廢** ⇒ 排程器記成放棄並繼續跑別的塊；
   **那一次複製因此少一塊 ⇒ INVALID**（§六-7）。要救它必須另開 DECISION。
3. **兩顆後端在同一個小時內各自失敗 ≥ 1 塊** ⇒ 停下來，先查後端不查資料。
4. **`--scope v2` 的稽核在任何一塊報出違規** ⇒ 整個 run 作廢
   （SPEC_GAIN §7；R460 §九 的推翻條件第二條）。
5. 跑完五次之前**不得**發布任何彙總數字（§二-3 的第 6 條）。

---

## 九、這份預註冊自己的邊界

- 本檔由 Opus 實作、**待 Fable 稽核**。§五-2 那處與 R5 原文的偏離是本檔最需要
  被看一眼的地方；若 Fable 判定不接受，量具改回「immediately preceding」之後
  R460 六塊會剩 14 筆紅的，必須在發射之前解決。
- 本檔**沒有**改動 R460 §六 的任何一格。若收官時發現需要改，那就是另一份 DECISION。
- 發射由稽核 session 之外的人執行；本檔只出檔案與指令。

---

## 一〇、2026-09-11 人類指示的**事前修訂**（在任何 r460r 資料之前）

⚠ 本節記的是**人類在發射之前**下的兩條運維指示。寫成「修訂」而不是直接改
§一／§四 的表，是因為兩件事的性質不同：**表是「註冊了什麼」，指示是「這次排什麼」**。
把 1003 從槽表上刪掉會讓它那條實測換來的上限（1）跟著消失；把 `REPS` 改成
`(1, 2, 3)` 會讓 r4／r5 看起來沒註冊過。兩者都是用資訊換整潔，不划算。

### 修訂 A：**1003 這一輪完全停用**

人類正在用那台機器。⇒ 本輪**一塊都不准上 1003**，只用
1004（`http://100.86.226.21:1234/v1/chat/completions`），**≤ 3 併發**。

- 表達方式：`--hosts 1004`（`SLOTS` 那張表一個字沒動，`select_slots` 只是篩它）。
- `--hosts` 打錯字 ⇒ **中止**，不是默默退回四個槽
  （默默退回＝把人類的「1003 不要用」變成「照跑」）。
- 1004 的上限仍然是**凍結的 3**：停用一顆卡**不是**在另一顆上加併發的理由。
- 後果寫在 §六-10（單一後端 ⇒ 那顆卡的狀態變成整批資料的共同因子）。

### 修訂 B：**先跑 r1／r2／r3；r4／r5 暫不排隊**

- 表達方式：`--reps 1 2 3`（18 塊；`REPS = (1,2,3,4,5)` 一個字沒動）。
- **r4／r5 仍然是預註冊過的**：§一 的 30 個名字、五顆 seed、
  `SEED_AUTHORIZED_SET` 五行全部留著。要跑它們**不必**另開 DECISION，
  補一次 `--reps 4 5` 就是。
- ⚠ **這不是「跑到三次就結算」的授權。** §二-3 第 6 條逐字照舊：
  少於五次 ⇒ `aggregate.reps_analyzed < 5` ⇒ 宣稱規則**自動**落在
  「逐次照實列」，而且要寫清楚跑了幾次。「先跑三次」與「只跑三次就下結論」
  是兩件事，本節不授權後者。
- ⚠ §三-1 的檢定力預期（五次裡預期只有 2–3 次顯著）在 n=3 之下**更不該**
  被當成訊號：三次裡 1 次顯著完全落在事前預期之內。

### 發射指令（逐字）

```
python3 ops/gain/schedule_harness_reps.py --dry-run --reps 1 2 3 --hosts 1004
setsid nohup python3 ops/gain/schedule_harness_reps.py --reps 1 2 3 --hosts 1004 \
  > /dev/null 2>&1 &
```

第一輪會發的三塊（first-fit、槽位順序 1004#1/#2/#3）：

```
r1a1 (offset 0)  → 1004#1  http://100.86.226.21:1234/v1/chat/completions
r1a2 (offset 20) → 1004#2  http://100.86.226.21:1234/v1/chat/completions
r1a3 (offset 40) → 1004#3  http://100.86.226.21:1234/v1/chat/completions
```

**本節沒有動任何門檻、家族、分母、區間、四狀態、宣稱規則或預測窗。**
動到的只有「這次排哪幾塊、發到哪顆卡」。

---

## 一一、排程器兩次猝死與重啟（2026-09-11，事後補記，**不改任何判準**）

本節記的是**基礎設施事件**，不是實驗條件的修訂：門檻、家族、分母、區間、
四狀態、宣稱規則、預測窗**一個字都沒動**。記下來是因為
「排程器停過」與「那段時間沒有塊在排隊」會改變**牆鐘**與**併發條件**，
而那兩樣要進收官的時間軸。

| 時刻（UTC） | 事件 |
|---|---|
| 03:14 | 初次發射（`--reps 1 2 3 --hosts 1004`，pid 3089647） |
| **07:23** | **排程器猝死**，就在它發完 `g_r460r1_harness_lcb2_b2` 的同一秒。log 最後一行停在 07:22:57，之後 51 分鐘沒有再寫過一行；三個 runner 不受影響、繼續跑完 |
| 08:14 | R529 那一輪的唯讀查證發現它不在了（`ps` 無輸出、log 不再增長） |
| 08:19 | Fable 重啟（pid 3104570）——**當時不知道死因**，只知道它死了 |
| 11:04:01 | R529 的排程器用**同一種寫法**發完第一塊之後**當場死掉**，而且這一次的 stdout 沒有被導到 `/dev/null` ⇒ **留下了 traceback** |
| 13:08 | 死因確認並修掉（commit `e14983b`，兩道防線，見下） |
| **13:09:12** | 依 Fable 授權，**只 kill 排程器那一個 python 行程**（pid 3104570，用 pid 不用 pattern）；`kill` 前後 runner 數都是 6（＝3 塊），**一個 runner 都沒碰到** |
| **13:09:22** | 用修好的碼重啟（pid 3116840，log `~/vacant/logs/schedule_harness_reps_restart_20260911T1309Z.log`）。第一行計畫：**完成 5／佇列 10／佔用 3**（`1004#1 b3`、`1004#2 r2a1`、`1004#3 r2a2`），沒有空槽 ⇒ 這一輪一塊都不發。帳全對。 |

### 死因（實測，不是推測）

發射器 `ops/gain/launch_harness_rep_block.sh` 的
`say "preflight passed; head: $(head -c 600 "$OUT.launch.log" | tr '\n' '|')"`
——`head -c`／`tail -c` 是**按位元組**截斷的，而 `launch.log` 裡全是中文。
切點落在一個 3 byte 字元中間就會吐出**半個字元**，那半個字元沿著發射器的 stdout
傳回排程器，而排程器的 `subprocess.run(..., text=True)` 是**嚴格 UTF-8 解碼**
⇒ `UnicodeDecodeError` 當場把排程器打死。

實測（R529 的那一塊，同一支寫法）：`runs/g_r529_lcb3m_a1.launch.log` 的第 598–600
byte 是 `\xe4\xb8\x80`（「一」），`head -c 600` 正好切成 `\xe4\xb8`。

⚠ **為什麼 07:23 那次看起來像「沒事」**：R460R 的排程器 stdout 被導到 `/dev/null`
（§一〇 的發射指令逐字如此），所以 traceback 整個不見了；磁碟上只看得到
「log 停在發完某一塊的那一秒」。**兩次死法一模一樣，只是第一次沒有留下證據。**
⇒ 這是本輪的一條教訓：**把排程器的 stdout 丟掉，等於把它的死因丟掉。**
R529 的重啟指令已改成導向具名的 `.out` 檔；本檔的 §一〇 發射指令沒有追改，
但**下一次重啟請用具名檔**。

### 修法（commit `e14983b`，兩道防線）

1. **不要產生壞位元組**：兩支發射器（`launch_harness_rep_block.sh`、
   `launch_r529_block.sh`）三處截斷後一律過 `u8()`＝`iconv -c -f UTF-8 -t UTF-8`。
2. **壞位元組不准讓排程器死**：兩支排程器的 `subprocess.run` 改成
   `text=True, errors="replace"`。

`ops/gain/schedule_harness_reps.py` 這次**動了**——改的只有 `launch_block` 的
一個關鍵字參數與 docstring，`SLOTS`／`REPS`／狀態機／作廢規則／idempotency
一個字沒動。回歸測試 4 支在 `tests/test_r529_queue_scheduler.py`。

### 對 R460R 資料的影響（照實講）

- **已收的 5 塊資料不受影響**：排程器死掉不會動到已經在跑的 runner，
  也不會改 rows/summary 的任何一格。
- **受影響的是排隊**：07:23–08:19（56 分鐘）與 13:09:12–13:09:22（10 秒）
  這兩段沒有排程器在看著；第一段裡若有 runner 收工，那個槽會空轉到 08:19。
  ⇒ 收官算牆鐘／吞吐時要把這兩段標出來，**不要**把它讀成「後端變慢了」。
- **併發條件**：1004 上 R460R 的三槽全程不變；R529 從 11:04 起在 1004 用**第 4 格**
  （`q1004#4`），13:08 重發之後同樣只用第 4 格
  （見 `DECISION_20260911_R529_CROSS_BANK_PREREG.md` §八-4）。
