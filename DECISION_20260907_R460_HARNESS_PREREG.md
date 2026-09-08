# R460：worker harness 六臂——`runs/g_r460_harness_lcb2_{a1,a2,a3,b1,b2,b3}`（LCB v2，120 題切成 6×20，兩顆後端各三塊併發，OFF／CONFORM／OFF5／HPI／HOC／HMIX 交錯）

**日期**：2026-09-07（**round460e 修訂 2026-09-08，仍在任何 r460 資料之前**）
**輪次**：round460e（Opus 修訂、Fable 裁決 A1–A4）
**狀態**：預註冊。**本檔在 run 發射之前、在任何 r460 資料存在之前定稿。**
**授權**：本檔即 R440G 閘門所需的那一份——它授權**恰好六個**階段一 run 名字
`runs/g_r460_harness_lcb2_a1`／`_a2`／`_a3`／`_b1`／`_b2`／`_b3`，以及 seed `g-r440-lcb2`；
其他都不授權（外加 §九-4 那個零 API 的量具 run 名 `r460_probe`，
以及 §十一 事前凍結的階段二 `runs/g_r461h_harness_lcb3_a`／`runs/g_r461h_harness_lcb3_b`）。
⚠ **round460e 之前的名字（`runs/g_r460_harness_lcb2`、`…_a`、`…_b`）都不在授權內。**
R440G 的閘門是子字串比對（`ops/gain/gain_run.py:1268`）⇒ 那些舊名字會**照樣通過**它
（`…_a1` 甚至把 `…_a` 整個含在裡面）；發射器因此自己再擋一次
（`abort_stale_run_name`），§二-5 有理由。
**規格來源**：`docs/HARNESS_STUDY_2026-09-07.md`（§4 三條臂、§5 實驗設計）。
**實作**：branch `feat/v2-four-stages`——
`ops/gain/harness_arms.py`、`ops/gain/harness_vgt_audit.py`、
`ops/gain/brain_cline.py` 的 `chat()` 與 `generate()` 的牆鐘護欄（round460e，A3，純基建）、
`ops/gain/gain_run.py` 的四處（D8 允許的範圍）。
**編號**：`R460` 這個號碼在本 repo 已被兩份文件用過
（`DECISION_20260901_R460_ORPHAN_OFF_RUN_KILL.md`、
`DECISION_20260904_R460_HARD_BANK_FEASIBILITY.md`）；本檔用**日期前綴**區分，
檔名唯一。引用時請連日期一起寫（`DECISION_20260907_R460_…`）。

---

## 〇、Fable 的九條裁決（D1–D9）落在本檔的哪裡

| 裁決 | 內容 | 本檔／實作落點 |
|---|---|---|
| **D1** | `max_calls=5`、`max_tokens=32000`／題、`max_wall_s=900`、sandbox 10 s | §二-3 預算表；`harness_arms.HARNESS_BUDGET` |
| **D2** | 六臂**同一個交錯 run**；bank lcb2、n=120、seed `g-r440-lcb2`（與 r447 同）；**OFF5 不准省** | §二-1／§二-2／§七-3 |
| **D3** | 門檻、顯著性、區間、分母、階段二 | §六（逐字） |
| **D4** | turn 1 用 `gain_run.extract_code` 未改；修訂輪用 harness 取碼器；兩者都落盤並計分歧；`nocode`＝零圍欄；第一塊非 Python 另計；precheck reason 封閉集 | §三 P-H8／§四 E-5；`harness_arms` |
| **D5** | `first_pass_turn` 逐題落盤；Δ(turn1−OFF)＝prompt 效果、Δ(final−turn1)＝迴圈效果，兩個都報 | §三-B 歸因 |
| **D6** | pi 那組逾時比例數字沒有合規引用 ⇒ **刪**（連數字本身都不複述），`max_wall_s` 改綁我們自己的 max 504.9 s × 安全係數 | §二-3；`docs/HARNESS_STUDY` §4.0.6 已改 |
| **D7** | 可見測資**內容**（args／got／want）進 worker prompt 是本 repo 第一次 ⇒ 預註冊、展場文案、稽核腳本 docstring 三處都要寫明 | §八-1；`harness_vgt_audit.py` docstring |
| **D8** | 不動 `vacant/checks.py`／`extract_code`／既有臂；`gain_run` 只准改四處；`brain_cline` 只准加 `chat()`；不加 runtime 依賴 | §四 E-4（發射前逐條驗） |
| **D9** | **兩個後端、六塊、每台三塊、併發**：`_a1`／`_a2`／`_a3`（offset 0／20／40，各 n 20，100.119.113.56:1234）與 `_b1`／`_b2`／`_b3`（offset 60／80／100，各 n 20，100.86.226.21:1234）；同 seed；合併分析事前註冊；P-H0 只在 a1+a2+a3 的聯集、窗不變；端點要落盤；**任何一塊都不准走 hub**；**每顆端點恰好三塊** | §二-1／§二-5／§三 P-H0／§六-(0)／§七／§十-3；`analyze_r460.topology_report`、`launch_harness_lcb2.sh` |

### 〇-B、round460e 的四條修訂（Fable A1–A4，**全部在資料之前**）

| 修訂 | 內容 | 落點 |
|---|---|---|
| **A1** | 拓撲從兩塊改成**六塊**（每台三塊、每塊 20 題），並把 `--request-timeout-s` 提高到 **1200**（牆鐘護欄 1260） | §二-1／§二-5／§四 E-7／§六-(0)；`launch_harness_lcb2.sh`、`analyze_r460.py` |
| **A2** | V/GT 稽核的量具修正：`repr` 落在凍結的瑣碎字面值集合或長度 < 6 ⇒ 跳過並單獨計數（`needles_skipped_trivial`） | §八-1；`harness_vgt_audit.py`＋負控測試 |
| **A3** | `brain_cline.generate()` 也掛牆鐘護欄（純基建，bounds a hang） | §四 E-4；T12 的 `GENERATE_SHA` 隨之更新並註明理由 |
| **A4** | 上面三條在**發射之前**一起提交並推上去 | commit round460e |

**A1 的理由（實測，寫在資料之前）**：R460 的 n=3 冒煙量到這批 LCB 題目**每通呼叫
160–560 s**、單通完成 token 最多 ~13k。一塊 60 題、行程內序列送出 ⇒ 兩塊各 **> 2 天**。
而**直連** LM Studio 後端實測可以同時服務 **3 個請求而每個請求都不變慢**
（1 個 1.3 s／3 個併發各 1.3 s；6 個併發才開始退化）
⇒ 一台後端掛三個序列 runner，吞吐 ×3，**每一題的行為一個字沒變**：
每一題的六條臂仍然在同一塊、同一個行程、同一個後端上跑完，合併仍然按 `task_id`
（R445 先例，已凍結）。P-H0 的錨仍然是前 60 題（r447 的 32/60），
只是它現在讀 **a1+a2+a3 的聯集**。

---

## 一、要解的問題：**選擇規則打不破的天花板，修訂迴圈打不打得破**

`docs/VACANT_ARCHITECTURE_AND_RESULTS_2026-09-07.md` §3.1 逐字：

> 綁定約束不是選擇器，是候選池。17–19% 的題目五個候選全錯，任何選擇機制都救不了。

CONFORM／OFF5／EQ5 都是**選擇規則**——從 k 份既有候選裡挑一份，交付率上限就是
「至少一份對」的比例。**修訂迴圈不是選擇規則**：第 t 輪的候選是用第 t−1 輪的
執行結果生出來的新東西，不在原本那 k 份裡面。
⇒ 迴圈是目前唯一**在原理上**可以越過池子天花板的做法。

「原理上可以」不等於「實際上會」，而且本 run 有三個具體的、事前算得出來的失敗形狀：

- **修理的作用面只有 41 題。** r447 的 OFF 有 79/120 第一輪就通過可見驗收
  ⇒ 那 79 題 H 臂與 OFF 完全一樣（第一輪就停）。剩下 41 題（34.2%）才是迴圈的戰場，
  而那 41 題的 hidden **也全錯**（`hidden 過但可見沒過 = 0/120`）。
- **轉換率是綁定約束。** CONFORM 把可見通過從 79 推到 113（＋34），
  hidden 通過只從 61 推到 84（＋23）⇒ **轉換率 67.6%**，同時假交付從 18 漲到 29。
  若 H 臂把 41 題全修成可見通過而轉換率維持 67.6%，交付率上限約
  `61 + 41×0.676 ≈ 88.7/120 = 73.9%`——**打不到 §六 EFFECTIVE 需要的 80%**。
  要打到，轉換率必須顯著高於 67.6%，也就是**修訂出來的解必須比重抽出來的解更「真的對」，
  而不只是更「通過可見測資」**。這正是本 run 要問的問題，而且它有機會失敗。
- **迴圈是朝著可見測資改的。** LCB v2 每題只有 2–4 條可見測資
  （2 條 59 題、3 條 52 題、4 條 9 題），過擬合風險結構性地高於隨機抽樣（§八-3）。

### 這個 run **不**回答什麼（收官不准借用）

1. **不是「業界證明 harness 才是關鍵」。** 外部證據能證實的只有反面：一旦你有 loop，
   loop 的裝潢不重要（同模型四個 harness 全距 2.7pp）。
   **loop vs 沒有 loop 在外部一份資料都沒有**（`HARNESS_STUDY` §1.3 T2／T3）。
2. **不是「我們的 agent 會自我驗證」。** 量到的是 harness **強迫**它看執行結果，
   不是它自覺要驗。
3. **不是三條臂的因子拆解。** 靜態診斷同時在 H-OC 與 H-MIX ⇒
   計畫輪的獨立效果在本設計裡**不可辨識**（P-H9 的後續條件）。
4. **不能省略前提**：「需求可以被編譯成可執行的驗收測資」。沒有這個前提，
   整條 harness 路線的回饋來源不存在。

---

## 二、run 名字、指令、與「唯一的差別」

### 二-1　run 目錄與指令（D9／A1：**六塊，併發，每台三塊**）

run 目錄：**`runs/g_r460_harness_lcb2_{a1,a2,a3,b1,b2,b3}`**
（本檔只授權這六個名字，外加 §九-4 的 `r460_probe` 與 §十一 的兩個階段二名字）。
seed：**`g-r440-lcb2`**，**六塊同一顆**（與 r447 同一顆，重用的授權與理由見 §二-4）。

| 塊 | `--out` | `--offset` | `--n` | `--gauge-scope` | `VACANT_GAIN_API` |
|---|---|---|---|---|---|
| a1 | `runs/g_r460_harness_lcb2_a1` | `--offset 0` | 20 | `--gauge-scope slice`（3/3） | `http://100.119.113.56:1234/v1/chat/completions` |
| a2 | `runs/g_r460_harness_lcb2_a2` | `--offset 20` | 20 | `--gauge-scope slice`（3/3） | `http://100.119.113.56:1234/v1/chat/completions` |
| a3 | `runs/g_r460_harness_lcb2_a3` | `--offset 40` | 20 | `--gauge-scope slice`（4/4） | `http://100.119.113.56:1234/v1/chat/completions` |
| b1 | `runs/g_r460_harness_lcb2_b1` | `--offset 60` | 20 | **`--gauge-scope bank`（12/12）** | `http://100.86.226.21:1234/v1/chat/completions` |
| b2 | `runs/g_r460_harness_lcb2_b2` | `--offset 80` | 20 | **`--gauge-scope bank`（12/12）** | `http://100.86.226.21:1234/v1/chat/completions` |
| b3 | `runs/g_r460_harness_lcb2_b3` | `--offset 100` | 20 | **`--gauge-scope bank`（12/12）** | `http://100.86.226.21:1234/v1/chat/completions` |

每一塊的指令逐字是（`<OUT>`／`<OFFSET>`／`<GAUGE_SCOPE>` 取上表，其餘六格**六塊完全相同**）：

```
python3 ops/gain/gain_run.py \
  --out <OUT> --n 20 --offset <OFFSET> \
  --decision DECISION_20260907_R460_HARNESS_PREREG.md \
  --seed g-r440-lcb2 --arms OFF,CONFORM,OFF5,HPI,HOC,HMIX --bank lcb2 \
  --models gemma-4-12b-it-qat --probe-sample 0 --gauge-scope <GAUGE_SCOPE> \
  --request-timeout-s 1200 --review-timeout-s 380 --retries 4
```

⚠ **`--gauge-scope` 兩種值都是註冊的，理由與代價見 §四 E-3**（round460f）。
它**不進任何一條臂的執行路徑**：量具跑的是參考解與壞樁，兩者都不經模型、
不寫 rows、不影響 persona 指派與 rng。所以 a\* 用 `slice`、b\* 用 `bank`
**不會**讓兩組資料不可比——配對比較仍然只在塊內或合併後成立。

六塊**同時**跑，各自 `setsid`、各自 `flock`、各自 `launch.log`、各自 `backend.json`。
`VACANT_GAIN_API` 是 `ops/gain/brain_cline.py::endpoint()` 讀的那個環境變數
（`brain_cline.py:36-37`），發射器**逐塊 export**；沒 export 時它會退回模組預設，
而那個預設是 hub ⇒ 漏 export 就是安靜地把六塊都推回同一顆卡。§二-5 有硬擋。

⚠ **`--request-timeout-s 1200`（round460e／A1，從 600 提高）**：
一顆後端同時服務三條長生成時，每一條的串流都會變慢；而冒煙在**沒有**併發時
就已經量到單通 160–560 s。600 s 在三併發之下會把正常的長生成誤判成逾時 ⇒
**假的 `infra_void`**，而假 void 會同時污染分母（complete case）與 token 帳。
牆鐘護欄因此是 `timeout + WALL_CLOCK_SLACK_S` ＝ **1260 s**
（`brain_cline._wall_clock_guard`）。這一格是**實驗條件**，
發射器與本檔是同一份真相（發射器 `abort_timeout_not_prereg` 對釘）。

發射器：**`ops/gain/launch_harness_lcb2.sh`**（一支發六塊）。
**發射由稽核 session 之外的人執行；本檔只出檔案與指令。**

`--review-timeout-s 380` 登記在案的理由與 r449c 相同：**本 run 沒有任何臂會發評審呼叫**
（沒有 ON／ONR），這一格對行為零作用；登記它是為了讓 `summary.request_policy`
與 r447 **逐欄相同**（r447 實測 `{timeout_s: 600, retries: 4, backoff_s: 2.0,
review_timeout_s: 380, review_retries: 2}`），P-H0 的後端漂移探針才不會被
「請求政策也不一樣」這件事污染。

### 二-2　與 r447 的逐項對照——**只有臂不同**

| 項 | r447（`runs/g_r447_conform_lcb2`） | **r460（本 run，六塊合起來）** |
|---|---|---|
| `--bank` | lcb2 | **相同** |
| `--n` / `--offset` | 120 / 0（一塊） | **20/0＋20/20＋20/40＋20/60＋20/80＋20/100（六塊）**——§九-1 驗過六塊接起來逐題逐序**等於** r447 的那 120 題 |
| `--seed` | `g-r440-lcb2` | **相同，六塊同一顆**（§二-4 的重用授權） |
| `--arms` | OFF,CONFORM,OFF5 | **OFF,CONFORM,OFF5,HPI,HOC,HMIX**（加三條，既有三條一個字沒動） |
| `--models` | gemma-4-12b-it-qat | 相同 |
| `--probe-sample` | 0（有參考解的全驗） | 相同（**逐塊**驗自己的 20 題） |
| request policy | timeout 600 / retries 4 / backoff 2.0 / review 380×2 | **timeout 1200**（A1，理由見 §二-1），其餘逐欄相同。⚠ 這一格與 r447 **不同** ⇒ P-H0 的橫向比較多背一個差異，寫在 §三 P-H0 的誠實邊界裡 |
| agent pool | 6 個 persona／1 個模型家族（`POOL` 未動） | 相同 |
| **端點** | hub `100.119.113.56:8765` | **兩顆直連，每顆三塊：a1/a2/a3 → `100.119.113.56:1234`、b1/b2/b3 → `100.86.226.21:1234`**（§二-5） |
| 跑的時間 | 2026-09-04 14:22 → 09-05 01:05 | ≥ 3 天之後 ⇒ **後端可能已漂**，見 P-H0 |

**六臂交錯在同一塊之內**（`for task: for arm`，round278）。這是**設計上**消掉後端漂移，
不是統計上假設它不存在：中斷在任何時刻都會留下六臂格數相等的可分析資料。
⇒ **同一題的六條臂一定打同一顆後端**，所以後端是 **task 層級的干擾項，
永遠不是 arm 層級的混淆**。這一句是 D9 成立的全部理由，收官必須原樣帶著。

### 二-3　預算（D1，寫死成模組常數，**不是 CLI 旋鈕**）

```python
HARNESS_BUDGET = {"max_calls": 5, "max_tokens": 32_000, "max_wall_s": 900,
                  "sandbox_timeout_s": 10, "truncation_retries": 1, "doom_threshold": 2}
```

- **`max_calls=5`**：等於 OFF5／EQ5。SPEC_GAIN §3 逐字「OFF-5x 是這個實驗誠實與否的分水嶺」。
  ⇒ H-PI ＝ 1 初稿＋最多 4 次修訂；**H-OC ＝ 1 計畫＋1 初稿＋最多 3 次修訂**
  （計畫輪要跟一次修訂機會競爭——那正是要問的問題，不是設計缺陷）。
- **`max_tokens=32_000`／題**：OFF5 每題平均 14,102；單次 completion p99 13,242、max 33,974。
  ⚠ **不送 `max_tokens` 給端點**——只有 H 臂設輸出上限的話，長答案會被砍而 OFF 不會，
  那是憑空造出來的劣勢。預算只在**呼叫之間**當停止條件。
- **`max_wall_s=900`（D6 改綁自己的實測）**：本專案量到的**成功**呼叫延遲
  p50 20.7 s、p90 90.5 s、**max 504.9 s**（`runs/g_r447_conform_lcb2/calls.jsonl`，n=926，§九-3）。
  **900 ＝ 504.9 × 1.783**。
  初稿引用的那組「pi 的逾時比例」外部數字**已依 D6 整條刪除**，
  本檔與 `HARNESS_STUDY` 都不再出現，**連「原本寫的是多少」都不複述**
  （複述等於用一份沒落盤的來源當事實）。刪除紀錄與唯一的復活路徑
  （`https://mariozechner.at/posts/2025-11-30-pi-coding-agent/` ＋
  `examples/archive_citations.py` 的三級規則：URL＋圖名＋抓取日期＋sha256 快照）
  寫在 `HARNESS_STUDY` §4.0.6。
- ⚠ **誠實邊界：`max_wall_s` 不是每題牆鐘的上界。** 它在**呼叫之間**檢查，而單次呼叫
  在 `--request-timeout-s 1200 --retries 4` 之下最壞可以燒掉 ~6000 s
  （r447 在舊的 600 s 設定下實測有 3 通失敗呼叫各花 600.0／600.0／600.1 s，
  也就是逾時真的會被燒滿；round460e 把逾時提高到 1200 ⇒ **這個上界跟著加倍**）。
  所以「900 s」的意思是 **「不會再發起新的一輪」**，不是「這題最多 900 秒」。
  收官報 `harness_wall_s` 的分佈，不准把它講成硬上界。
  ⚠ 牆鐘護欄（`brain_cline._wall_clock_guard`，1200＋60＝**1260 s**）綁的是
  **單次請求**不是單題，所以它也不是每題的上界；它擋的是「OS 沒兌現 socket 逾時
  ⇒ 一通呼叫四小時不返回」那個死法（round460d 實測）。

### 二-4　**seed 重用的授權**（本 run 與所有前例最大的程序差異）

`g-r440-lcb2` **被用過**——`runs/g_r447_conform_lcb2` 就是它（§九-2 掃過 44 個
`runs/*/summary.json`，命中**恰好一個**）。既有發射器的 `abort_seed_not_fresh`
（掃到任何命中就停）在這裡會擋下一個**我們刻意要的**設定，所以本 run 的發射器
**把新鮮度檢查換成「明文授權檢查」**：

```
SEED_REUSE_AUTHORIZED: g-r440-lcb2 <- runs/g_r447_conform_lcb2
```

發射器 `ops/gain/launch_harness_lcb2.sh` 的規則（比原本的新鮮度檢查**更嚴**，不是更鬆）：

1. seed 必須出現在本 DECISION 內文（沿用 `abort_seed_not_prereg`）；
2. 本 DECISION 內文必須含上面那一行**逐字**的授權句（`abort_seed_reuse_unauthorized`）；
3. 掃過所有 `runs/*/summary.json`，命中集合必須**恰好等於**授權句列出的那一個 run
   ——多一個或少一個都停（`abort_seed_reuse_set_mismatch`）。
   「少一個」也要停：那代表 r447 不見了或 summary 讀不到，
   而「量不到」不是「通過」（沿用 `launch_eq5_lcb3.sh` 的同一條紀律）。

**為什麼重用是對的，而且代價是零**：

- **seed 在這裡不選題。** LCB v2 bank 就是 **120 題**（`ops/gain/data/lcb_bank_v2.jsonl`
  120 行，sha256 前 16 碼 `b98f027213e2469a`），而 `--n 120` 取全部
  ⇒ `LiveCodeBenchLoader` 的 seed **只打亂順序，不做抽樣**。
  換一顆 seed 不會換到別的題，只會換題序。
  ⇒ 「重用 seed ＝ 重複同一次抽樣」這個一般性風險**在這個題庫上不存在**。
- **它買到的是同題同序。** 題序由 `sha256(f"{seed}:{task_id}")` 決定 ⇒ 同 seed ＝ 同題序。
  ⚠ **逐格 persona 對齊在切塊之後只剩一小段（round460e 誠實更正）**：
  每臂的 rng 是 `random.Random(f"{seed}:{arm}")`，而它在**每一塊各自從頭抽**
  （`gain_run.py:1490`）⇒ 兩塊時 block a 的 60 題與 r447 逐格同 persona；
  **六塊時只剩 a1 的前 20 題**還對得上，a2／a3 會與 r447 錯開
  （邊際分佈相同、逐格不同）。P-H0 因此從「配對比較」退化成
  「同一批 60 題上的兩個非配對估計」，噪音變大——**窗不因此再放寬**（§三 P-H0）。
- **它不影響三條 H 臂的隨機性**：`HPI`／`HOC`／`HMIX` 是新的臂名 ⇒
  `Random("g-r440-lcb2:HPI")` 是三串全新的 persona 指派，與任何既有 run 無關。
- ⚠ **代價寫在明處**：本 run 的 OFF／CONFORM／OFF5 **不是** r447 的獨立複製
  ——同題、同序（persona 指派只有 a1 的前 20 題對齊，見上一點與下一節），
  差別是「後端、時間、request timeout」與模型的取樣噪音。
  §七 逐條寫死它們之間准做什麼、不准做什麼。

### 二-5　**D9／A1：兩個後端、六塊、每台三塊、併發**——為什麼切、切了之後什麼變什麼不變

**量到的事實（2026-09-07 15:40）**：

1. **8765 那顆 hub 把 100% 的請求路由到後端 1003**——6 次探針，1003 計數 +6、1004 +0。
   ⇒ 走 hub 等於只用到一張卡，另一張整場閒置。
2. **併發打 hub 吞吐會退化**：n=8 → 12 時 206 → 175 → 144 tok/s。
3. **兩顆直連後端**（`100.119.113.56:1234`、`100.86.226.21:1234`）各自在 n=4 熱身後
   約 **110–120 tok/s**，兩邊服務的都是 `gemma-4-12b-it-qat`。

4. **round460e 補量（2026-09-08）**：R460 的 n=3 冒煙量到這批 LCB 題目
   **每通呼叫 160–560 s**、單通完成 token 最多 ~13k
   ——比 r447 當時貴得多（r447 的成功呼叫 max 是 504.9 s，但中位低很多）。
   ⇒ 一塊 60 題、行程內序列送出要 **> 2 天**。
5. **直連後端的併發特性**（同日實測）：1 個請求 1.3 s、**3 個併發各自仍是 1.3 s**
   （沒有 per-request 變慢）；**6 個併發才開始退化**。

⇒ 把 120 題切成**六塊**（每塊 20 題）、每顆直連後端掛**三個序列 runner**、全部同時跑：
吞吐約 ×6（相對單塊），而**每一個請求的行為一個字沒變**。

**SPEC_GAIN §7「一端點一 run」在 round460e 被明文修訂，修訂的範圍是窄的**：
- 舊規則的實測基礎是 round22/23/262（`DECISION_20260824_SERIALIZE_CONCURRENT_CALLS.md`）
  ——對**同一個端點無上限併發**會觸發 HTTP 500／逾時，而它當年量的是 **8765 那條中轉路徑**。
- 新規則是 **「一顆直連後端最多三個序列 runner」**，依據就是上面第 5 點的實測。
  hub **仍然禁止**（第 1、2 點），> 3 併發**仍然禁止**（第 5 點的退化區）。
- ⚠ 這是**放寬**，所以它必須自己有牙齒：發射器發射前數一次（`abort_endpoint_imbalance`），
  analyzer 收官時再數一次（`endpoint_block_count_not_3` 進 `broken_reasons`，
  由突變體 `M11_endpoint_balance_not_checked` 證明那條會紅）。
  沒有這兩道，「一台四塊、一台兩塊」會全綠通過，而那個世界裡只是**比較慢**——
  沒有任何既有欄位會變紅。

#### 切了之後**變**的三件事（每一件都在別處有對應條文）

| 變的東西 | 後果 | 寫在哪 |
|---|---|---|
| **persona 指派只有 a1 的前 20 題與 r447 對齊** | 每臂的 rng 是 `random.Random(f"{seed}:{arm}")`，**在每一塊各自從頭抽**（`gain_run.py:1490`）⇒ a2 的第 1 題拿到的是 r447 第 1 題的 persona，不是第 21 題的 ⇒ P-H0 從配對比較退化成非配對比較；**錨與窗都不變**（錨仍是 r447 前 60 題的 32/60，窗仍是 ±15pp），但它的噪音變大 | §三 P-H0、§二-4 |
| **六塊的題目難度組成不同** | a1 medium12/hard8、a2 13/7、a3 15/5、b1 10/10、b2 12/8、b3 10/10（§九-8 實測；a* 合計 40/20、b* 合計 32/28）⇒ **塊間的點估計不得互相比較**；`lcb_3026`（2023-08-26 那題）在 **b1** | §六-(0)、§八-11 |
| **request timeout 從 600 變 1200** | 三併發之下 600 會把正常的長生成誤判成逾時 ⇒ 假 `infra_void`。這一格與 r447 不同 ⇒ P-H0 的橫向比較多背一個差異 | §二-1、§三 P-H0 |
| **多一組「合併對不對」的擋門** | 塊間 task_id 交集、聯集不是 120、一塊兩個端點、走 hub、端點數不是 2、**每顆端點塊數不是 3**、seed／臂不一致、塊數不等於 6——全部進 `broken_reasons` | §四 E-7 |

#### 切了之後**不變**的三件事（這才是 D9 敢切的理由）

1. **配對比較的兩臂永遠在同一顆卡上、同一個行程裡。** 交錯是塊內的 ⇒
   同一 `task_id` 的六格同後端、同 runner。
   後端是 task 層級的干擾項，配對差分把它整個消掉。
2. **合併後的 n 還是 120，題目還是那 120 題。** §九-1 逐項驗過
   六塊各 20 題接起來 ＝ r447 的 120 題，順序也一樣，兩兩交集為空、聯集恰好 120。
   ⇒ §五 的事前檢定力表（n=120）**一個字不改**。
3. **仲裁量是合併後的量。** `per_arm.*`／`paired.*`／`holm.*`／`decision.*` 的欄位路徑
   一個字沒變，讀的都是合併後的報表。塊內數字印出來，但**是描述性的**。

#### 端點身分怎麼落盤（D9 要求，且不准為它改 runner）

- **`calls.jsonl` 逐呼叫已經有 `"api"` 欄位**（`brain_cline.py:160/201/346/387`），
  記的是**真的送去哪裡**，比在 summary 放一個設定值還嚴。
- **`summary.json` 沒有端點欄位**，而 **D8 不准為了加它去改 `gain_run.py`**
  （只准動 import／`KNOWN_ARMS`／`_gate_arms`／dispatch elif 四處）。
  ⇒ 端點的仲裁來源是 `calls.jsonl` 的 `api`，由
  `analyze_r460.endpoints_of()` 讀回、`topology_report()` 判；
  發射器另外把 `/v1/models` 的回應存成 `<OUT>.backend.json` 當第二份旁證。
- 仲裁欄位：`topology.by_block.<block>.endpoints`、`topology.endpoints_all`、
  `topology.violations`、`topology.blocks_n`、`topology.blocks_per_endpoint`、
  `topology.task_ids_union`。

#### 三條硬禁令（違反＝資料不判）

1. **任何一塊都不准走 hub。** 發射器 `abort_hub_endpoint` 擋 `8765` 字面，
   analyzer 的 `block_used_hub` 把它算成 `broken_reasons`。
2. **恰好兩顆端點、每顆恰好三塊。** 發射器 `abort_same_endpoint`／`abort_endpoint_imbalance`，
   analyzer `endpoints_n_not_2`／`endpoint_block_count_not_3`。
   ⚠ 「同端點」在六塊之下**不再是違規、是設計**；要擋的變成**超賣**
   （某台四塊 ⇒ 掉進 6 併發的退化區，而那看起來只是比較慢）。
3. **不准只分析一部分塊就結算。** analyzer 看到授權塊名卻不是六塊時，
   `block_count_not_6` 進 `broken_reasons`；task_id 聯集不是 120 時
   `pooled_task_count_not_120` 也進去——「只跑得完四塊」會安靜地變成
   「n=80 的另一個實驗」，那正是要擋的東西。
   ⚠ 若真的只跑得完一部分，**那是 §十 的中止情形**，要另開 DECISION，不准就地改讀法。

---

## 三、事前註冊的預測（P-H0..P-H9）——先寫死，收官逐條判 HIT／MISS

仲裁量一律取
`python3 ops/gain/analyze_r460.py --run runs/g_r460_harness_lcb2_a1 runs/g_r460_harness_lcb2_a2 runs/g_r460_harness_lcb2_a3 runs/g_r460_harness_lcb2_b1 runs/g_r460_harness_lcb2_b2 runs/g_r460_harness_lcb2_b3 --bank lcb2 --rescore-turn1 --json …`
輸出 JSON 的欄位（**六塊一起餵，合併後的量才是仲裁量**；少餵一塊會拿到
`broken_reasons: ["block_count_not_6:5", "pooled_task_count_not_120:100"]`），
**欄位名逐字寫在下表第三欄**（記憶鐵律：判準要指名它讀哪個 key，
不准靠「工具印了什麼字串」）。`tests/test_r460_launcher_prereg.py` 會逐條驗這些 key
真的存在於 analyzer 的輸出裡。

| # | 預測 | 仲裁欄位 | 窗 | 錨在哪 |
|---|---|---|---|---|
| **P-H0** | 新 OFF 的交付率（後端漂移探針）**只在 a1+a2+a3 的聯集上判** | `prereg.P-H0.value`（＝`ph0_pool.per_arm.OFF.deliv_pp_denom_measured`，`ph0_pool` ＝ a1／a2／a3 三塊合起來的 60 題；`prereg.P-H0.source_field` 與 `ph0_pool_blocks` 逐次印出它讀了哪幾塊） | **[38.3, 68.3]%** | 錨＝r447 **前 60 題**的 32/60 ＝ **53.33%**（§九-8 實測，六塊之下 a1+a2+a3 的聯集逐題逐序仍等於它）；窗＝**±15pp**——n 從 120 掉到 60、二項 SE 從 4.56 漲到 6.44pp，±10×√2 ≈ ±14.1 ⇒ 取 ±15。**放寬的理由是 n 減半，不是為了讓它容易 HIT**。b* 那三塊是另外 60 題 ⇒ **不判、也不併進這一條**；合併後的 OFF 交付率照印在 `prereg.P-H0.pooled_off_deliv_pp_NOT_ARBITER`，但**不是**仲裁量。⚠ **誠實邊界（round460e）**：六塊之下只有 a1 的前 20 題與 r447 逐格同 persona（每塊的 rng 各自從頭抽），而且 request timeout 從 600 變成 1200 ⇒ 這一條背了**兩個**與 r447 不同的條件，是非配對的粗探針；**窗不因此再放寬**（放寬只會讓它更容易 HIT）。MISS 時照 `prereg.P-H0.scope`：只作廢與 r447 的橫向比較，本 run 內部六臂比較仍然有效 |
| **P-H1** | 三條 H 臂都 > OFF | `paired.HPI_vs_OFF.delta_pp`／`paired.HOC_vs_OFF.delta_pp`／`paired.HMIX_vs_OFF.delta_pp` | 三個都 **> 0** | 41 題有修理空間，而且那 41 題 hidden 全錯 ⇒ 只會往上 |
| **P-H2** | 至少一條 H 臂 > CONFORM | `paired.<ARM>_vs_CONFORM.delta_pp` | **至少一個 > 0** | §一：修訂可越過池子天花板，選擇不行 |
| **P-H3** | H 臂的實際呼叫／題 | `per_arm.<ARM>.calls_per_task` | **[1.8, 3.2]**（三條都要） | 79/120 第一輪就停（＝1.0 通），41 題會用到 2–5 通 |
| **P-H4** | H 臂假交付率 | `per_arm.<ARM>.false_delivery_pp` | **> CONFORM 的值** 且 **≤ 35%** | 迴圈朝可見測資修 ⇒ 過擬合升高；r447 CONFORM ＝ 24.17%。**這是預測會變差一點，不是門檻**（門檻是 §六 的 (iv)） |
| **P-H5** | 有靜態診斷的兩條臂，以 `loader` 收尾的輪次比例 | `per_arm.HOC.loader_turn_rate_pp`／`per_arm.HMIX.loader_turn_rate_pp` | **≤ 0.5%** | 診斷會把 reason 直接告訴模型。**HPI 沒有診斷 ⇒ 不判它**，但要印（預期仍在 2% 上下） |
| **P-H6** | H-MIX 的 context 紀律真的省 token | `prereg.P-H6.value`（＝`tokens.HMIX.tokens_per_task ÷ tokens.HPI.tokens_per_task`） | **≤ 0.8** | §4.3 的 context 政策就是為這條設計的 |
| **P-H7** | 撞牆鐘的比例 | `per_arm.<ARM>.stop_reason_pp.budget_wall` | **≤ 5%**（三條都要） | 900 s ＝ 自家實測 max 504.9 s 的 1.78 倍，而一題只有一個函式 |
| **P-H8** | 協定：`nocode` 輪次比例 | `per_arm.<ARM>.nocode_turn_rate_pp` | **≤ 3%**（三條都要） | r447 的 925/925 回應都有圍欄 |
| **P-H9** | **條件性後續**：H-OC 與 H-MIX 是否都顯著贏 H-PI | `prereg.P-H9.followup_h4_required` | 為 true ⇒ **必須追加第四條臂 H-PI＋只加診斷** | 靜態診斷同時在兩條臂裡 ⇒ 計畫輪的獨立效果不可辨識（`HARNESS_STUDY` §4.4） |

⚠ **P-H9 用的兩個檢定（`paired.HOC_vs_HPI`、`paired.HMIX_vs_HPI`）不在 Holm 家族內。**
家族固定是 §六-(2) 的 6 個。那兩個 p 是**未調整的探索量**，只用來觸發後續臂，
**不准**拿去支持任何「哪一條 H 臂比較好」的宣稱。

### 三-B　D5 歸因：prompt 效果與迴圈效果**都要報**

| 量 | 仲裁欄位 | 意義 |
|---|---|---|
| Δ(turn1 − OFF) | `attribution.<ARM>.delta_turn1_minus_off_pp`（＋`_ci95_lo_pp`／`_ci95_hi_pp`／`_p_mcnemar_exact`） | **prompt 效果**：只換 user-turn 文字值多少 |
| Δ(final − turn1) | `attribution.<ARM>.delta_final_minus_turn1_pp` | **迴圈效果**（全 120 題分母） |
| Δ(final − turn1)，只算迴圈題 | `attribution.<ARM>.delta_final_minus_turn1_looponly_pp` | 同上，分母只有 `first_pass_turn != 1` 的題 |
| 第一輪就過的比例 | `attribution.<ARM>.turn1_visible_pass_pp` | 迴圈的作用面有多大 |
| 靠迴圈才交付對的題數 | `attribution.<ARM>.loop_gain_n` | 迴圈真的救回幾題 |

- **兩個分母都要印**：只報全 120 題會把迴圈效果稀釋成「看起來很小」，
  只報迴圈題會放大成「看起來很大」。
- **Δ_O ≈ prompt 效果 ＋ 迴圈效果，不准寫成恆等式**：turn-1 那一份是無條件計分
  （沒有拒交語意，形狀與 OFF 相同），最終那一份有 `accepted`。
- **收官必須帶 `--rescore-turn1`**：turn-1 的碼由 `calls.jsonl` 的全文回應離線重取
  （初稿輪用 `gain_run.extract_code`，D4），再走與 dispatch 端逐字相同的
  `meets_demand(hidden)`。**零模型呼叫，但會跑沙箱。**
  沒帶這個旗標時 analyzer 會把兩個欄位印成 `null` 並附
  `rescore_note`——**`null` 是「沒算」不是「等於 0」**。

### 三-C　無條件一併印、一併判、不准挑一個的次要量

（看過數字之後不准選分母——r444 那次兩個分母給出相反判決。）

- `per_arm.<ARM>.deliv_pp_denom_measured` **與** `per_arm.<ARM>.deliv_pp_denom_accepted_NOT_ARBITER`
- `per_arm.<ARM>.false_delivery_n`（**絕對件數**，SPEC_GAIN §4-5）、`accept_precision_pp`、`refusal_pp`
- `tokens.<ARM>.tokens_per_task` / `multiple_vs_off` / `multiple_vs_conform` /
  `tpc_incl_void` / `tpc_excl_void` / `tpc_ratio_vs_off5`（**token 倍數表，D3 要求貼在 (iii) 旁邊**）
- `paired.<pair>.b` / `.c` / `.n_discordant` / `.n_common` / `.p_mcnemar_exact` /
  `.ci95_lo_pp` / `.ci95_hi_pp` / `.b_only_task_ids` / `.c_only_task_ids`
- `holm.<pair>.p_raw` / `.p_adj` / `.significant`、`holm.family_size`
- `power.<pair>.mde_at_n_pp` / `.n80_if_true_effect_is_observed`
- `per_arm.<ARM>.calls_hist` / `turn_hist` / `first_pass_turn_hist` / `stop_reason_counts` /
  `fail_kind_counts` / `precheck_reason_counts` / `extractor_divergences` /
  `entry_point_missing` / `first_block_non_python` / `truncated_retries` / `wire_modes`
- 守門指標六條，**欄位名逐字**：`gates.G1_false_delivery`、
  `gates.G2_refusal_losslessness`、`gates.G3_loader_artifact`、
  `gates.G4_difficulty_date`、`gates.G5_calls_per_task`、`gates.G6_wire_mode`
  （`HARNESS_STUDY` §5.7；與 §四 的 E-1..E-7 是不同的兩組東西，不要混）
- `decision.<ARM>.verdict` 與它的四個條件旗標（欄位名見 §六-(4) 的表）
- **D9 拓撲**：`topology.blocks_n`、`topology.by_block.<block>.endpoints`、
  `topology.endpoints_all`、`topology.blocks_per_endpoint`、`topology.task_ids_union`、
  `topology.violations`、`block_order`，以及逐塊的 `blocks.<block>.per_arm.*`
  與 `ph0_pool.*`／`ph0_pool_blocks`（描述性，除了 P-H0 讀的那一格）
- `stage2_triggered`（**只讀 H-MIX**）與 `stage2_triggered_any_arm_NOT_TRIGGER`（不是觸發鍵）

---

## 四、效力前提 E-1..E-7（不是預測，是「這份資料算不算數」的擋門）

任一條紅 ⇒ **先修／先揭露，不判裁決**（狀態＝`INVALID`，見 §六）。
⚠ 這一節的 E-1..E-7 是**資料效力**擋門；`HARNESS_STUDY` §5.7 的 **G1–G6 是必須並報的
守門指標**（在 analyzer 的 `gates.*`）。兩組東西不同，不要混。

| # | 前提 | 怎麼驗 | 事前已知的狀況 |
|---|---|---|---|
| **E-1** | analyzer 讀得懂 runner 寫的 rows | `python3 ops/gain/analyze_r460.py --run <六塊> …` 的 `broken_reasons == []`（缺欄位／帳對不上／未 terminal／wire mode 混算／**D9 拓撲全型**都在裡面） | analyzer 的 `--selftest` 已在 r447 的真 rows 上重現 61／84／76（§九-5），並在把 r447 切成多塊的離線重現上驗過**合併是無損的**（§九-9） |
| **E-2** | 帳對得上、且是收官資料 | **每一塊**每臂 `rows + infra_void == processed`；**六塊**的 `summary.run_terminal` 皆 true（合併取 `all()`）；六臂 `complete` 皆 true。⚠ 逐塊的 `broken_reasons` 會以 `block:<name>:…` 往上帶——合併是相加，兩塊反向的帳錯會互相抵銷 | r447 三臂皆 120+0=120 |
| **E-3** | **量具兩個方向都答對，而且本塊每一題都有出貨閘門** | 發射時**每一塊各自**印 `ref_pass == n` 與 `broken_rejected == n`（`n` 依 `--gauge-scope`：`slice` 是該塊有參考解的題數、`bank` 是**整個題庫**有參考解的 12 題）；`visible_ref_pass == visible_n` 與 `visible_stub_rejected == visible_n`；`bank` 模式另外硬擋 `coverage_visible_n == coverage_n`（本塊 20 題每一題都有 `visible_check`）。全部在 `gain_run.py` 的 `_gate_arms` 區塊，H 臂已納入 | 見下面的 **E-3 補述（round460f）** |

**E-3 補述（round460f，2026-09-08，在 b 組任何資料之前）**

發射當天量到的事實：**lcb2 的 120 題裡只有 12 題有官方參考解**，而它們在六塊之間
落得很不平均——

| 塊 | offset | 有參考解 |
|---|---|---|
| a1 | 0 | 3/20 |
| a2 | 20 | 3/20 |
| a3 | 40 | 4/20 |
| **b1** | 60 | **0/20** |
| b2 | 80 | 1/20 |
| b3 | 100 | 1/20 |

b1 因此在 preflight 停住（`參考解通過 0/0` ⇒「量具驗證一題都沒驗到——這不是通過，
是沒接上。停。」）。**那個拒絕是對的**，不准為了發射把它放寬。

⚠ **而且在 b 組內部重新切救不了**：後 60 題總共只有 **2** 題有參考解
（`lcb_3791`、`lcb_3793`）⇒ 任何三等分都至少有一塊是 0。
「六塊、每台三塊、每塊 20 題」與「每塊逐片量具至少驗到一題」在這個題庫上
**結構性不相容**。兩塊時代不會撞到（block a 10/60、block b 2/60），是 A1 把塊變小才浮出來。

**裁決（Fable）：換一條更強的規則，不是放寬。** 量具驗的是**沙箱＋題庫＋計分**
——參考解與壞樁**都不經模型**，也不寫 rows ⇒ 它與「這一塊是哪 20 題」
「打哪一顆後端」**都無關**。六塊跑在同一台機器、同一份沙箱上。
所以正確的規則是「**每一塊都對整個題庫有參考解的 12 題驗兩個方向，12/12 才放行**」：
比逐塊切片（3/3、0/0）**更強**，而且不再受切法影響。

落地（`ops/gain/gain_run.py` 的 `--gauge-scope {slice,bank}`，**預設 `slice`＝現行行為**）：

- `bank`：`probe_instrument` 的對象換成整個題庫裡有參考解的題目，兩個方向都要全過。
  實測 offset=60 那一塊：`slice` → `0/0`（停）、`bank` → **`參考解通過 12/12　壞解被擋 12/12`**、
  可見閘門 `12/12`。
- ⚠ **擴大量具不准順手把擋門弄不見**：`bank` 之下「本塊 20 題每一題都有 `visible_check` 嗎」
  不再被前一條順帶蓋到，所以**獨立量、獨立擋**（`coverage_visible_n == coverage_n`）。
- 本 run 的實際配置：**a1/a2/a3 用 `slice`**（它們在 round460e 的發射裡已經以
  3/3、3/3、4/4 通過並且**正在跑**，不重發、不殺）；**b1/b2/b3 用 `bank`**（12/12）。
  兩種模式**照實記錄在 `summary.json` 的 `gauge_scope`**，收官逐塊印出來。
- **為什麼混用不影響任何比較**：量具不進臂的執行路徑（不呼叫模型、不寫 rows、
  不動 rng 與 persona 指派）⇒ 它改變的只有「我們敢不敢相信這把尺」，
  不是尺量到的東西。配對比較仍然只在塊內或合併後成立（§六-(0)），
  而每一題的六條臂仍然在同一塊、同一行程、同一後端上跑完。
- ⚠ **誠實邊界**：`bank` 讓六塊的量具**答同一份考卷**，所以它證明的是
  「這台機器的沙箱＋題庫＋計分是好的」，**不是**「本塊那 20 題每一題都被驗過」
  ——後者在這個題庫上對任何一塊都不成立（最多的一塊也只有 4/20 有參考解）。
  §八-9 那條「`--probe-sample 0` ＝ 有參考解的全驗，不是 120 題全驗」照舊適用。
| **E-7** | **D9 的拓撲成立**（round460e 改成六塊版） | `topology.violations == []`：`topology.blocks_n == 6`、**恰好 2 個相異端點**、**每個端點恰好 3 塊**、塊間 task_id 兩兩零交集且**聯集 == 120**（即 r447 的那 120 題）、一塊一端點、**沒有一塊走 hub**、seed／臂／offset 一致 | 全部在 `analyze_r460.topology_report()`；`--mutation-check` 的 `M8_topology_not_enforced`（拓撲不判）與 `M11_endpoint_balance_not_checked`（每端點三塊那一格不數）證明它有牙齒 |
| **E-4** | **D8 的邊界沒有被越過** | `git diff 7747ce3b44b410d16b18897376d78747d735108d <r460 的 runner_git.sha> -- ops/gain/gain_run.py ops/gain/brain_cline.py vacant/codebench.py vacant/checks.py`，逐項分類 (a) 只影響分析／文件／基建 (b) 影響臂行為 | 基線＝**r447 的 runner sha `7747ce3b44b410d16b18897376d78747d735108d`**（讀自 `runs/g_r447_conform_lcb2/summary.json`）。**四個檔不是三個**——`vacant/checks.py` 是沙箱本體，在臂的執行路徑上（R449C §四 G-4-α）。本 run 事前已知 diff 非空，**逐項分類寫在下面的 E-4 表**，**收官必須對發射當下的 sha 重跑** |

**E-4 的事前分類表（round460e 更新）**

| `brain_cline.py` 的改動 | 類 | 理由 |
|---|---|---|
| 新增 `chat()`（多輪，H 臂用） | **(a)** | 既有五臂不呼叫它；`generate()` 的呼叫路徑一個字沒動 |
| 新增 `_wall_clock_guard()` 並掛在 `chat()` 上 | **(a)** | 同上，只在 H 臂的路徑上 |
| **round460e／A3：`_wall_clock_guard` 也掛上 `generate()`** | **(a)** | **純基建**：只給「OS 沒兌現 socket 逾時」那條路一個上界（`timeout + 60`），正常路徑上的行為、落盤欄位、重試語意、`InfraVoid` 的定義**逐字不變**；護欄咬到走的就是既有的 `except Exception` → 落盤 → 重試 → 用盡才 void，**不新增 void 種類**。⚠ 它改了 `generate()` 的原始碼 ⇒ T12 的 `GENERATE_SHA` 隨之更新（`130c47c5…` → `b523c15f…`），測試裡逐字註明這一次改動被授權的理由；**既有五臂的行為仍然一個字沒動** |
| 所有 HTTP 請求強制帶逾時上限（round460d） | **(a)** | 純基建，同上 |

| `gain_run.py` 的改動 | 類 | 理由 |
|---|---|---|
| D8 授權的四處（import／`KNOWN_ARMS`／`_gate_arms`／dispatch elif） | **(a)／(b)** | 見 D8；只有 dispatch 新增 H 臂那一格會改行為，而那正是本 run 的處理本身 |
| **round460f：`--gauge-scope {slice,bank}`（D8 之外的第五處改動）** | **(a)** | **量具範圍，不進臂的執行路徑。** `probe_instrument` 多一個可選的 `coverage_tasks` 參數並多回三個鍵；`main()` 在 `bank` 時把量具對象換成整個題庫、另外硬擋本塊的出貨閘門覆蓋；`summary.json` 多一個 `gauge_scope` 欄。**預設 `slice` ＝ 逐字現行行為**（`coverage_tasks=None` 時不算也不擋）⇒ 既有五臂、T12 的 sha 表與 E-5 一格不動。理由與實測見 §四 E-3 補述。⚠ 它是 **D8 之外的第五處**，所以在這裡明列——不列出來就等於偷偷擴大授權範圍 |
| **E-5** | 既有五臂**逐位元沒動**（D8 的可執行版） | `arm_off`／`arm_off5`／`arm_conform`／`arm_eq5`／`arm_on`／`extract_code`／`meets_demand` 七個函式的原始碼字串與 `84d101d` 相同（`tests/test_gain_harness_arms.py::T12` 做這件事） | 本檔寫作時已綠 |
| **E-6** | 不被長得像的旗標騙 | `summary.equal_budget_comparison_valid` **預期是 false** | 它的定義只看 `ON` 與 `OFF5` 兩臂（`gain_run.py:1394-1399`），本 run 沒有 ON ⇒ 結構上永遠 false。**等預算的證據是 P-H3 與 `calls_per_task`，不是這個旗標** |

**E-4 的誠實邊界**：r447 的 `runner_git.dirty` 是 **true**
（`{"sha": "7747ce3b…", "dirty": true, "branch": "feat/v2-four-stages"}`）
⇒ 那一版的位元組**無法只憑 sha 完全還原**。這是既有的設計缺口，
本 run 大機率也會是 dirty＝true。**發射時把 dirty 內容記下來並逐項查證，
不要沿用任何前一輪的結論。**

---

## 五、事前檢定力：**+10pp 這條線就落在可偵測極限上，這件事寫在資料之前**

用 `vacant.research.mcnemar_power`（精確枚舉，非近似）與 `ops/gain/power_paired.mde_at_n`
實算（可重跑指令見 §九-6）。

| p_disc | Δ | ψ | power @ n=120 | power @ n=189（階段二） |
|---|---|---|---|---|
| 0.20 | +5pp | 0.625 | 0.169 | 0.280 |
| 0.20 | **+10pp** | 0.750 | **0.633** | 0.853 |
| 0.25 | **+10pp** | 0.700 | **0.525** | 0.761 |
| 0.325 | **+10pp** | 0.654 | **0.428** | 0.639 |
| 0.325 | +15pp | 0.731 | 0.801 | 0.951 |

r447 的 CONFORM vs OFF 實測 `b=31, c=8` ⇒ `p_disc = 39/120 = 0.325`。

⚠ **這張表的 n 是 120，也就是六塊合併後的 n**（D9）。切塊**不改變檢定力**：
六塊的 `task_id` 兩兩交集為空、聯集恰好 120、配對單位是 task、仲裁一律取合併後的量（§六-(0)）
⇒ 配對檢定的 n 還是 120。
**每一塊各自的 n=60 不是分析單位**，本檔沒有為它註冊任何門檻；
真的只剩一塊可用時走 §六-(6)-i（不判裁決、另開 DECISION 重算），
**不准**把下面這張表當成「n=60 也差不多」。

**MDE（最小可偵測效果）@ n=120**，同一支模組實算：

| p_disc | n_d | α=0.05 的最小 \|b−c\| | MDE | **Holm 最嚴那一格（α=0.05/6）的最小 \|b−c\|** | **Holm 下的 MDE** |
|---|---|---|---|---|---|
| 0.20 | 24 | 12（18/6） | **10.00pp** | 14（19/5） | **11.67pp** |
| 0.25 | 30 | 12（21/9） | **10.00pp** | 16（23/7） | **13.33pp** |
| 0.325 | 39 | 15（27/12） | **12.50pp** | 19（29/10） | **15.83pp** |

**事前結論，寫在資料之前，收官不准改口**：

> **§六 的 +10.0pp 點估計門檻，在 n=120 上落在或低於 MDE。**
> 在 Holm 家族（6 個檢定）之下，任何一格要被判顯著，需要的效果是
> **11.67–15.83pp**，全部**高於** +10pp。
> ⇒ **綁定的其實是條件 (ii)（Holm 後顯著），不是條件 (i)（點估計 ≥ +10pp）**：
> 任何通過 (ii) 的臂，其 Δ_C 的點估計幾乎必然已經 ≥ +10pp。
> 這句話事前就成立，**不是收官時為了解釋結果才算的**。
> 直接後果：**`INCONCLUSIVE` 是本 run 事前最可能的落點**（+10pp 真效果下
> 檢定力 0.43–0.63，還沒扣 Holm），它**不是失敗，也不是「效果不存在」**。

**為什麼明知檢定力不足還要跑**：因為 §一 的算術給了一個**可能大很多**的效果
（Δ_C 若真的越過池子天花板，量級會在 +10 到 +19pp 之間），
而 0.325 的 discordant 率在 +15pp 上的檢定力是 **0.80**。
也就是說：**這一次「量不量得到」取決於效果是不是真的越過了天花板，
而那正是這個 run 要問的事。**

---

## 六、決策規則（D3，**在任何 r460 資料之前寫死**）

前提：E-1..E-7 全綠。任一紅 ⇒ 狀態 `INVALID`，先修或先揭露，**不准**先判。

### 六-(0)　**仲裁的資料是六塊合併後的那一份**（D9／A1，事前註冊）

- 收官指令固定是
  `--run runs/g_r460_harness_lcb2_a1 runs/g_r460_harness_lcb2_a2 runs/g_r460_harness_lcb2_a3 runs/g_r460_harness_lcb2_b1 runs/g_r460_harness_lcb2_b2 runs/g_r460_harness_lcb2_b3`。
  analyzer 依 `offset` 排序、**按 `task_id` 合併**（R445 先例），
  `per_arm.*`／`paired.*`／`holm.*`／`decision.*`／`tokens.*` 全部算在合併後的 120 題上。
- **逐塊的報表照印**（`blocks.<block>.…`，欄位結構與合併版逐字相同），
  它是**描述性的**：用來看有沒有哪一塊整個壞掉，不是拿來比較的。
  逐塊的 `broken_reasons` 以 `block:<name>:…` 往上帶進合併版。
- ⚠ **塊間的點估計不得互相比較**——六塊的難度組成不同
  （a1 12/8、a2 13/7、a3 15/5、b1 10/10、b2 12/8、b3 10/10，medium/hard，§九-8）。
  「a3 的 H-MIX 比 b2 高」這種句子在本檔裡是**禁句**，
  和 §六-(7) 的其他禁令同級。
- ⚠ **不准跨塊配對**。配對單位是 `task_id`，而六塊的 `task_id` 兩兩交集為空
  ⇒ 每一組配對本來就落在同一塊之內、同一顆後端之上、同一個行程之內。
  這是設計，不是巧合。
- ⚠ **少一塊就不判裁決**：`topology.blocks_n != 6`（或聯集不是 120、
  或某顆端點不是三塊）⇒ E-7 紅 ⇒ 狀態 `INVALID`。
- ⚠ **P-H0 例外**：它讀的是 `ph0_pool`（a1+a2+a3 的聯集），不是合併後的 120 題。
  這是本檔**唯一**一條不讀合併值的預測，理由與代價寫在 §三 P-H0。
- ⚠ **合併後每臂的 `wall_s` 是六塊相加＝總算力時間，不是牆鐘經過時間**
  （六塊併發：兩台後端各三個行程，牆鐘大約只有它的六分之一）。
  `wall_s_per_task` 仍然是對的（每題平均算力時間），
  但「這個 run 花了幾小時」要看發射器的 log。analyzer 每次都把這句印在 `notes`。

### 六-(1)　配對單位與分母＝**complete case**

配對單位是 `task_id`；成功的定義是 **`deliv = accepted ∧ meets_demand`**
（R667 凍結口徑，`ops/gain/replay/paired_ci.py:25` 逐字）。
兩臂比較的分母是**兩臂都非 void 的題**：
`n_common = |{task_id ∈ rows[A]} ∩ {task_id ∈ rows[B]}|`
（`gain_run` 只在非 void 的格子寫 rows）。仲裁欄位 `paired.<A>_vs_<B>.n_common`。

⚠ **不准**用聯集、不准用 `processed`、不准用各臂自己的 `measured`。
⚠ **每一對比較各自有自己的 `n_common`**（H 臂彼此 void 的題不一樣），
所以 `n_common` 必須逐對印，不准只印一個「n=120」。

### 六-(2)　顯著性＝**Holm–Bonferroni 調整後的精確 McNemar p**

每一對算 `p = vacant.research.mcnemar_exact(b, c)`；
家族是 **3 條 H 臂 × 2 個對照（OFF、CONFORM）＝ 6 個檢定**，
一次丟進 `vacant.research.holm_bonferroni`，α=0.05。
仲裁欄位 `holm.<pair>.p_adj`、`holm.family_size`（**必須等於 6**）。
⚠ 家族固定 6，**不准**因為某一臂 void 太多就抽掉它再重算 Holm。

### 六-(3)　區間＝**未調整**的 95% Clopper–Pearson 條件區間

用 `ops/gain/replay/paired_ci.py::diff_ci`（`analyze_r447.py` 用的同一支）。
仲裁欄位 `paired.<pair>.ci95_lo_pp` / `ci95_hi_pp`。

> **每一次引用區間都必須逐字附上這一句：**
> **「區間未做多重比較調整；仲裁以 analyzer 為準」**
> （analyzer 把它印在 `ci_note`，逐格也帶一份）。

⚠ 於是「未調整區間排除 0，但 Holm 後 `p_adj ≥ 0.05`」是**事前就知道可能發生**的情形。
那不是矛盾，是多重比較的代價：**顯著性以 `p_adj` 為準**，
而 RULED_OUT 仍讀**未調整**的 `ci95_hi_pp`（D3 逐字）。
**「Holm 後的 CI」這個詞不存在，本檔與 `HARNESS_STUDY` 都已把它刪掉。**

### 六-(4)　四個狀態（**照順序判，先命中者為準**）

| 狀態 | 條件 | 收官准講的話 |
|---|---|---|
| `INVALID` | E-1..E-7 任一紅 | 「這個 run 不當資料用」 |
| **`EFFECTIVE`** | (i) `decision.<ARM>.delta_o_pp` ≥ **+25.0pp** **且** `decision.<ARM>.delta_c_pp` ≥ **+10.0pp**（**點估計**）　(ii) `holm.<ARM>_vs_OFF.p_adj < 0.05` **且** `holm.<ARM>_vs_CONFORM.p_adj < 0.05`　(iii) `tokens.<ARM>.tpc_incl_void ≤ tokens.OFF5.tpc_incl_void`（**同一個 run 的 OFF5**）　(iv) `per_arm.<ARM>.false_delivery_pp ≤ per_arm.CONFORM.false_delivery_pp + 5.0`　——**四條全部成立** | 「在 120 題 LeetCode 中高難度題上、用一顆 12B 本地模型、把五通呼叫花在『跑客戶的驗收測資、把失敗原文貼回去、讓它改』，比花在換人重抽多交付 N 個百分點。」**必須同時講 winner's curse 免責與 §八 的全部誠實邊界** |
| **`COSTLY_BUT_REAL`** | (ii) 的 **CONFORM 那一半**成立（`holm.<ARM>_vs_CONFORM.p_adj < 0.05`），但 (i)(iii)(iv) 任一條不成立 | 「真的有效，但不划算／或是用假交付換來的」。**展場不得宣稱**，只能寫進誠實邊界 |
| **`RULED_OUT`** | `paired.<ARM>_vs_CONFORM.ci95_hi_pp` < **+10.0pp** | 「排除了 ≥10pp 的實務增益」。這是**結論**不是失敗（沿用 R445 對 OFF5 的用法） |
| **`INCONCLUSIVE`** | 其餘 | 「**沒量出來**，不是沒有差異」——必須**同時**報 `power.<pair>.mde_at_n_pp`、`power.<pair>.n80_if_true_effect_is_observed` 與 §五 的事前檢定力表。⇒ 走 §十一 的階段二 |

**四個狀態逐臂寫在 `decision.<ARM>` 底下，欄位名逐字如下**（判準指名欄位，
不准靠「工具印了什麼字串」；`tests/test_r460_launcher_prereg.py` 逐條驗它們真的存在）：

| 條件 | 仲裁欄位 | 判什麼 |
|---|---|---|
| (i) 點估計 | `decision.<ARM>.delta_o_pp` ≥ +25.0　`decision.<ARM>.delta_c_pp` ≥ +10.0 | 旗標 `cond_i_point_estimates` |
| (ii) Holm 後顯著 | `decision.<ARM>.p_adj_vs_off` < 0.05　`decision.<ARM>.p_adj_vs_conform` < 0.05 | 旗標 `cond_ii_holm_both`；只有 CONFORM 那一半成立時 `cond_ii_holm_conform_only` |
| (iii) token | `decision.<ARM>.tpc_incl_void` ≤ `decision.<ARM>.tpc_off5` | 旗標 `cond_iii_tokens`；旁邊必印 `multiple_vs_off`／`multiple_vs_conform`／`tpc_ratio_vs_off5` |
| (iv) 假交付 | `decision.<ARM>.false_delivery_pp` ≤ `decision.<ARM>.false_delivery_conform_pp` + 5.0 | 旗標 `cond_iv_false_delivery` |
| RULED_OUT 的線 | `decision.<ARM>.ci95_hi_pp_vs_conform` < +10.0（＝未調整的 `paired.<ARM>_vs_CONFORM.ci95_hi_pp`） | — |
| 結論 | `decision.<ARM>.verdict` ∈ {EFFECTIVE, COSTLY_BUT_REAL, RULED_OUT, INCONCLUSIVE} | 照上表順序，先命中者為準 |

**主要假設指定為 H-MIX vs CONFORM**（H-MIX 是照證據組出來的成品，H-PI／H-OC 是消融）。
三條 H 臂各自判自己的裁決，但**展場口徑只跟著 H-MIX 走**，
而 §十一 的階段二觸發鍵也只讀 **H-MIX**（`stage2_triggered`）——
「任一臂 INCONCLUSIVE」那個較鬆的讀數另外印在
`stage2_triggered_any_arm_NOT_TRIGGER`，**它不是觸發鍵**，
名字裡就寫著不是，免得收官時被拿來替主要假設決定要不要再花一次機時。

### 六-(5)　**winner's curse 免責聲明是強制的**（不寫＝裁決不得結算）

> n=120 對 +10pp 的檢定力只有 0.43–0.63，Holm 之下可偵測的效果是 11.67–15.83pp（§五）。
> 能被判顯著的點估計本來就被截斷在 MDE 以上 ⇒
> **任何被判 `EFFECTIVE` 的臂，它的點估計是效果量的上偏估計。**
> 跨 run／跨臂比幅度一律報區間重疊，**不報點估計誰大**。

analyzer 把這段話印在 `winners_curse_disclaimer`，每次執行都印。

### 六-(6)　邊界情況（事前寫死，避免收官當場挑）

- **(a) 三條 H 臂全部 `RULED_OUT`** ⇒ 本 repo 對外的說法要改成：
  **「在 12B worker ＋ 可執行驗收測資的設定下，把 5 通呼叫花在修訂迴圈，
  不比花在換人重抽（CONFORM，1.71 通）更好。」**
  這句要進 `examples/verdicts.py` 當一條 refuted 裁決，與
  `gain.equal_budget_on_beats_off5` 並列。
- **(b) P-H0 MISS（後端漂了）**：**只作廢本 run 與 r447 的橫向比較**
  （含「r447 的 22,266 當事前錨」這種引用），**不作廢本 run 內部的六臂比較**。
  §六 的四條門檻裡只有 (iii) 需要 `TPC_OFF5`，而那個值**一律取本 run 的 OFF5**
  ⇒ **P-H0 MISS 不讓 §六 的任何一格失效**。
  ⚠ D9 之後這條探針**只看得到 a* 那三塊所在的後端**（`100.119.113.56:1234`）。
  b* 那顆（`100.86.226.21:1234`）**沒有事前錨**，本 run 對它一句話都不能說
  ——這是切塊的代價，寫在資料之前。要注意的是它**不影響任何配對比較**：
  b* 三塊的六臂全在那顆卡上，差分把它消掉。
- **(c) 某臂 void 率 > 10%**：該臂的比例**不得拿去比較**（SPEC 既有擋門）。
  void 率 > 20% ⇒ §十 的中止準則觸發，資料不進結論。
- **(d) `budget_wall` > 5%（P-H7 MISS）**：必須做敏感度分析——
  把撞牆鐘的題當 missing 重算一次，**兩個數字都報**。
- **(e) G3 的分層讀數掉超過一半**（`gates.G3_loader_artifact.<pair>_shrink_over_half == true`）：
  裁決書必須逐字寫「這條臂買到的主要是我們自己的禁用屬性表太嚴
  （`_FORBIDDEN_ATTRS` 含 `remove`），不是產出變好」。
- **(f) `selftests_parsed` 接近 0**：H-OC 退化成「多花一通講廢話」，
  裁決書要照這樣寫，**不准**把它讀成「計畫沒用」。
- **(g) 兩種 `harness_wire_mode` 同時出現在同一條臂**：`broken_reasons` 會紅（E-1），
  資料不判。**兩種模式的結果不得混算。**
- **(i) 只有一塊跑完**（另一塊 void 掉／後端掛掉／被中止）：**不判裁決**。
  `topology.blocks_n != 2` ⇒ E-7 紅 ⇒ `INVALID`。要用那一塊的資料必須另開 DECISION，
  而且新的那份要把 n=60 的檢定力重算一次（§五 的表是 n=120 的）。
  **不准**就地把 §六 的門檻搬到 60 題上重讀。
- **(h) 有題目所有臂都失敗、且懷疑是量具問題**：先查量具不查模型，
  且**不准**在收官時把那些題挑掉（R440B 那個逆向選擇器死過一次）。
  要報「含」與「排除」兩個版本，主結論用**含**的那個。

### 六-(7)　事前寫死的禁令（違反＝本輪失敗）

1. **看到數字之後改窗、改仲裁欄位、改分母、改家族、改狀態定義** ⇒ 一律不准。
2. **不准**把三條 H 臂合併成一個「harness 臂」再檢定。
3. **不准**跨 **實驗** 合併 n（沿用 R449C §六-2 的禁令）——
   本 run 不准與 r447／r449b／r461 或任何別的 run 併 n。
   ⚠ **本 run 自己的六塊不在這條禁令內，而且差別是可驗的、不是修辭上的**：
   `_a` 與 `_b` 是**同一個預註冊實驗**切出來的兩半——同 seed、同臂、同預算、
   同 `--decision`、`task_id` 交集為空（§九-1 驗過），
   而且合併規則**在資料之前**就寫死在 §六-(0) 與 `analyze_r460.pool_runs()` 裡。
   被禁的那件事是「兩個獨立實驗事後湊 n」：題目重疊、設計不同、
   合併與否在看過數字之後才決定。**這兩件事不准混為一談，也不准反過來
   拿本條當藉口去併別的 run。**
4. **D9 專屬三條**：不准比較塊間的點估計（§六-(0)）；不准跨塊配對；
   不准只用一塊結算（§六-(6)-i）。
5. **不准**在 `INCONCLUSIVE` 的情況下寫「等價」「打平」「迴圈沒用」。
6. **不准**用 `paired.HOC_vs_HPI` / `paired.HMIX_vs_HPI`（探索量、不在家族內）
   去支持任何「哪一條 H 臂比較好」的宣稱；它們只觸發 P-H9 的後續臂。
7. **不准**改 `ops/gain/analyze_r447.py` 的 `PREREG` 常數——那是 R440Z 的事前註冊，
   改別人的事前註冊等於改事前註冊。本 run 的仲裁者是 `analyze_r460.py` 與本檔。
8. **不准**把 `attribution.*` 的 `null` 讀成 0（那代表沒帶 `--rescore-turn1`）。
9. **不准**把任何一塊改成走 hub、或把某一顆後端塞超過三塊
   ——那會讓「兩顆卡併發」安靜地變回「一顆卡塞兩個 run」，
   而那看起來只是比較慢（§二-5 的三條硬禁令）。

---

## 七、與 r447 的關係：同題、同序、同 seed、**不是獨立樣本**

`CRITERION_20260903_R680_POOL_PRECONDITIONS.md` 的 **Q1** 要求可併的兩個 run
`task_id` 交集＝∅。本 run 與 r447 的交集是 **120（完全重疊）** ⇒ **Q1 MISS**。

**准做的（描述性，且必須標成描述性）**：

1. **P-H0 的後端漂移探針**——這是重用 seed 的唯一目的，也是它的正確用法。
   ⚠ **D9／A1 之後只在 a1+a2+a3 的聯集上成立**：那 60 題就是 r447 的前 60 題、同序。
   ⚠ 而且**連 persona 都只剩 a1 的前 20 題對得上**：每臂的 rng 在**每一塊**各自從頭抽，
   所以 a2 的第 1 題拿到的是 r447 第 1 題的 persona、不是第 21 題的。
   ⇒ P-H0 是**非配對**的粗探針（§三 P-H0 的誠實邊界），窗不因此再放寬。
   **b* 那三塊是另外 60 題** ⇒ 拿它們當對 r447 的漂移探針是錯的，本檔禁止。
2. **逐題跨 run 對照**：同一個 `task_id` 在 r447 與 r460 的 OFF 臂各自的成敗。
   這是完全重疊帶來的唯一好處（r449b 對 r447 做過同一件事）。
   ⚠ 在 a1 的前 20 題以外做這件事時要**同時標明 persona 已經不同**
   （而且 request timeout 也不同：600 → 1200），
   否則「同一題、同一顆 seed」會被讀成「同一個條件」。
3. 把 r447 的 CONFORM−OFF ＝ +19.17pp [+8.80, +26.46] 與本 run 的同一格並列，
   說明後端與時間的穩定度。**方法學陳述，不是效果宣稱。**

**不准做的**：把兩者的 n 加起來；把 r447 當成 r460 的「先前證據」做任何合併推論；
說「lcb2 上量了兩次都同號」（那是同一批題目、同一顆 seed 量了兩次）；
把 r447 的 OFF5 token 常數當成本 run 的 (iii) 門檻（**D2：一律用同 run 的 OFF5**）。

---

## 八、誠實邊界（收官必須原樣帶著，一條都不准掉）

1. **D7：可見測資的內容會進 worker prompt——本 repo 第一次。**
   H 臂的回饋訊息裡有 `args=[…] got=… want=…`，那三個欄位全部來自 `visible_tests`，
   是**客戶自己交出來的驗收測資**。既有的 OFF／CONFORM／OFF5 只把題目敘述送進 prompt，
   **從來沒有把可見測資的 args／expected 逐字送進去過。**
   這是設計要的（整條 harness 路線的機制就是「把執行結果貼回去」），
   V/GT 分離（SPEC_GAIN §2）分的是 `visible` 與 `hidden`，可見的部分本來就允許給模型看。
   ⇒ 三個後果：(a) 動態稽核的對象是 **`hidden_tests \ visible_tests`**，
   不是「所有測資」（斷言 visible 沒出現會**必然失敗**，因為它按設計就在裡面）；
   (b) **展場文案必須講**「模型看得到那幾條驗收測資的輸入與期望值」，
   不准只說「把錯誤貼回去」讓人以為它是憑空修對的；
   (c) 這件事本身就是第 3 條過擬合風險的機制來源。
   `ops/gain/harness_vgt_audit.py` 的 docstring 已逐字寫明這一點。
2. **12B 的協定遵循是真的風險。** r447 的 925/925 回應都有圍欄（好消息），
   但 **19.4% 有兩塊以上**（1 塊 746、2 塊 112、3 塊 31、≥4 塊 36，最多一份 56 塊）。
   迴圈會放大它。D4 的修訂輪取碼器就是為此而設，
   而**分歧數逐輪落盤**（`extractor_divergences`）正是為了讓「優勢有多少來自取碼器」
   事後扣得掉。若 P-H8 大幅 MISS，那本身就是一個結論（「12B 撐不住多輪協定」），
   不是要偷偷修掉的 bug。
3. **過擬合可見測資（最重要的一條）。** LCB v2 每題只有 **2–4 條**可見測資
   （2 條 59 題、3 條 52 題、4 條 9 題）。「反覆改到 2 條測資通過」與「寫對」的距離
   比 MBPP+ 大。r447 的 CONFORM 已經示範過：可見 +34 換 hidden +23（轉換率 67.6%），
   假交付從 18 漲到 29。
   ⚠ **若 H 臂交付率上升而假交付的絕對件數也上升，展場一個字都不准講。**
4. **牆鐘的不對稱對 H 臂不利。** OFF 只有 1 通，永遠不會撞牆鐘；H 臂每題最多 5 通。
   `budget_wall` 單獨計數並在裁決書單獨一行（§六-(6)-d）。
   而且 `max_wall_s` 只在呼叫之間檢查 ⇒ 它不是每題牆鐘的硬上界（§二-3）。
5. **void 的不對稱對 H 臂有利。** H 臂每題最多 5 次呼叫，任何一次重試用盡都會 void 掉
   整格（含前面已成功的幾輪）⇒ **void 曝險比 OFF 高 3–5 倍**，
   而 void 格的呼叫已經燒掉 token 卻不進分母 ⇒ **tokens／題會被低估**。
   ⇒ 兩個 token 數字都要報，**(iii) 的仲裁用 `tpc_incl_void`（較嚴的那個）**。
   r447 的 void 是 0，但 `g_off60_relay_20260824` 曾經 30%。
6. **載入器拒收的量具偏誤對 H 臂有利。** r447 的 925 份草稿有 25 份（2.7%）在跑任何
   驗收之前就被沙箱載入器擋掉，其中 16 份是 `list.remove()`
   （`vacant/checks.py:191` 的 `_FORBIDDEN_ATTRS` 含 `remove`，AST 分不出 `os.remove`
   與 `list.remove`）。**OFF 臂有 7 題（5.83%）就這樣輸掉**（本 run 的 analyzer
   在 r447 上重算，命中同樣 7 題：`lcb_3550`／`lcb_3563`／`lcb_3580`／`lcb_3637`／
   `lcb_3654`／`lcb_3751`／`lcb_3776`）。有靜態診斷的 H 臂會**免費**修掉它們，
   最多 +5.83pp——超過 §六 (i) 那條 +10pp 的一半。
   ⇒ **G3 必須分層並報**（ITT 為主、artifact-excluded 為必報次要）。
   ⚠ 本 run **不改** `_FORBIDDEN_ATTRS`（改它會動到 `vacant/checks.py` 這個承重件、
   要重跑 B 層與一批測試，也違反 D8）。另開 DECISION 處理。
7. **汙染定界。** LCB v2 的日期視窗是 **2023-08-26 → 2025-04-05**，
   其中 **`lcb_3026` 是 2023-08-26**，比其餘題目早一年多。
   迴圈臂**不會**改變汙染的性質（同一批題目、同一個模型），
   但**會**改變它的表現方式：若模型「記得」某題的解，多給幾輪只會讓它更快收斂到
   記得的答案。⇒ G4 逐題附難度與日期分層（medium 72／hard 48）；
   對外一律用 `docs/…RESULTS…` §5.2 的口徑，**不宣稱「未汙染」**。
8. **一題一個 worker，H 臂不繼承 CONFORM 的換人紅利。**
   `worker = rng.choice(agents)` 只抽一次，整題所有輪次同一個 persona。
   這是設計要的（要把「同一個人看著執行結果改」與「換人重抽」切乾淨），不是遺漏。
9. **量具覆蓋率**：`--probe-sample 0` 的意思是「不抽樣、**有參考解的**全驗」，
   不是「120 題全驗」。收官引用覆蓋率時要寫實際的 `instrument.n`，
   不要把「工具印了 N/N」講成「這個題庫每一題都驗過」。
10. **這個 run 不證明「harness 才是關鍵」。** 見 §一「不回答什麼」與
    `HARNESS_STUDY` §1.3 的九條傳說（T1／T2／T3 的引用更正見該節的稽核更正表）。
11. **六塊不是六次複製，是同一個實驗的六等分（D9／A1）。** 合併之後 n=120，
    但那 120 題**只被跑過一次**——六塊是**不同的題**，不是重跑。
    ⚠ 收官不准寫「在兩顆後端上都成立」：每一題只在**一顆**後端上跑過，
    「跨後端複製」這件事本 run 一次都沒做。
    ⚠ 也不准寫「a3 的效果比 b2 大／小」：六塊的難度組成不同
    （a1 12/8、a2 13/7、a3 15/5、b1 10/10、b2 12/8、b3 10/10），
    塊間點估計沒有可比性（§六-(0)）。
    六塊唯一被設計成可比的東西是**塊內的配對差分**，而那個已經併進主結果了。
12. **b* 那顆後端沒有事前錨。** P-H0 只探得到 a* 那顆
    （`100.119.113.56:1234`）。若 b* 那顆卡的行為與 a* 差很多，
    本 run **量不到**——它只會表現成「合併後的估計比較吵」。
    這件事寫在資料之前，收官不准當成沒有。
13. **三併發的代價沒有被量過（round460e 新增）。** 「3 個併發各 1.3 s」那組實測
    用的是**短**請求；本 run 的請求是 160–560 s 的長生成。三併發之下每一條會不會
    變慢、變多少，**本 run 沒有事前資料**。它的後果是牆鐘變長與逾時風險，
    已經用 `--request-timeout-s 1200` 買了緩衝；但**「吞吐真的 ×3」是估計不是量測**，
    收官報機時時要照實寫成估計。

---

## 九、自我驗證（發射前做完，指令逐條可重跑；全部零 API、零 ssh）

**(1) 題目集合：六塊合起來就是 r447 的那 120 題、同一個順序，而且塊間兩兩零交集**

```bash
cd /Users/cosmopig/Documents/GitHub/Vacant && .venv/bin/python - <<'PY'
import sys, json, hashlib; sys.path.insert(0,'.')
from ops.gain.gain_run import load_tasks
OFFS=[0,20,40,60,80,100]
full=[t["task_id"] for t in load_tasks("lcb2","g-r440-lcb2",120,offset=0)]
blk={o:[t["task_id"] for t in load_tasks("lcb2","g-r440-lcb2",20,offset=o)] for o in OFFS}
cat=[x for o in OFFS for x in blk[o]]
rows=[json.loads(l) for l in open("runs/g_r447_conform_lcb2/rows.jsonl",encoding="utf-8") if l.strip()]
off=[r["task_id"] for r in rows if r["arm"]=="OFF"]
print("n per block:", [len(blk[o]) for o in OFFS])
print("concat == full order:", cat==full)
print("pairwise disjoint:", all(not (set(blk[a])&set(blk[b])) for i,a in enumerate(OFFS) for b in OFFS[i+1:]))
print("union size:", len(set(cat)), "== r447 set:", set(cat)==set(r["task_id"] for r in rows))
print("a1+a2+a3 == r447 OFF first 60:", cat[:60]==off[:60])
print("b1+b2+b3 == r447 OFF last 60:", cat[60:]==off[60:])
print("bank_sha16", hashlib.sha256(open("ops/gain/data/lcb_bank_v2.jsonl","rb").read()).hexdigest()[:16])
PY
```

實測輸出（2026-09-08）：

```
n per block: [20, 20, 20, 20, 20, 20]
concat == full order: True
pairwise disjoint: True
union size: 120 == r447 set: True
a1+a2+a3 == r447 OFF first 60: True
b1+b2+b3 == r447 OFF last 60: True
bank_sha16 b98f027213e2469a
```

⇒ 同 seed ＝ 同題、同序（bank 只有 120 題、六塊 `--n 20` 合起來取全部
⇒ seed 只打亂順序，不抽樣）；**塊間兩兩交集為空、聯集恰好 120**
（`CRITERION_20260903_R680` 的 Q1 通過），而且 **a1+a2+a3 逐題逐序等於 r447 的前 60 題**
⇒ P-H0 的錨（32/60）在六塊之下仍然成立。

**(2) seed 重用的範圍：`g-r440-lcb2` 恰好被一個 run 用過**

```bash
cd /Users/cosmopig/Documents/GitHub/Vacant && python3 - <<'PY'
import glob, json
files=sorted(glob.glob("runs/*/summary.json")); hits=[]
for f in files:
    try:
        if json.load(open(f,encoding="utf-8")).get("seed")=="g-r440-lcb2": hits.append(f)
    except Exception: pass
print("summary.json 檔數:", len(files)); print("g-r440-lcb2 用過:", hits)
PY
```

實測：**44 個** `summary.json`，命中 **`['runs/g_r447_conform_lcb2/summary.json']`**——
**恰好一個**，與 §二-4 的授權句一致。發射器把「命中集合 == 授權集合」做成硬擋
（`abort_seed_reuse_set_mismatch`），多一個或少一個都停。

**(3) 牆鐘上限的依據（D6）：延遲分佈只算成功呼叫**

```bash
cd /Users/cosmopig/Documents/GitHub/Vacant && python3 - <<'PY'
import json
ok=[];bad=[]
for l in open("runs/g_r447_conform_lcb2/calls.jsonl"):
    if not l.strip(): continue
    r=json.loads(l); v=(r.get("latency_ms") or 0)/1000
    (ok if r.get("ok") else bad).append(v)
ok.sort(); bad.sort()
print("ok n",len(ok),"p50",round(ok[len(ok)//2],1),"p90",round(ok[int(len(ok)*.9)],1),
      "p99",round(ok[int(len(ok)*.99)],1),"max",round(ok[-1],1))
print("failed calls:",[round(x,1) for x in bad])
print("900/504.9 =", round(900/504.9,3))
PY
```

實測：`ok n 926 p50 20.7 p90 90.5 p99 258.3 max 504.9`；
失敗呼叫 6 通（`0.0, 292.6, 341.3, 600.0, 600.0, 600.1`）；`900/504.9 = 1.783`。
⇒ 900 s ＝ **自家實測 max 的 1.78 倍**；同時證實 §二-3 那條誠實邊界
（單通呼叫可以燒到 600 s 才失敗，`max_wall_s` 不是每題硬上界）。

**(4) 量具（零 API，跑到模型呼叫之前就退出）**

```bash
cd /Users/cosmopig/Documents/GitHub/Vacant && .venv/bin/python \
  ops/gain/gain_run.py --out /tmp/r460_probe --n 120 --arms probe --bank lcb2 \
  --seed g-r440-lcb2 --probe-sample 0 --decision DECISION_20260907_R460_HARNESS_PREREG.md
```

（`r460_probe` 這個名字也由本檔授權；R440G 檢查的是 `--out` 的 basename。）
判準：`ref_pass == n` **且** `broken_rejected == n` **且** `visible_n == n`
——第三格是 `_gate_arms` 對 CONFORM／EQ5／**H 臂**的硬擋（`gain_run.py:1349-1361`），
量具沒驗過的話「閘門根本沒有閘」會長得跟「機制很便宜」一模一樣。
⚠ 這一支是**零 API 的事前抽驗，一次涵蓋 120 題**（`--arms probe` 不跑臂、沒有 offset）。
**發射時每一塊還會各自再跑一次同一道閘門**，那時的 `n` 是**該塊的 60**（E-3）
——兩者不是同一件事，收官引用覆蓋率時要寫清楚引的是哪一個。

**(5) analyzer 先答已知答案：在 r447 的真 rows 上重現 61／84／76**

```bash
cd /Users/cosmopig/Documents/GitHub/Vacant && .venv/bin/python ops/gain/analyze_r460.py --selftest
cd /Users/cosmopig/Documents/GitHub/Vacant && .venv/bin/python ops/gain/analyze_r460.py --mutation-check
```

`--selftest` 釘住的 r447 已知答案（**全部實測通過**）：
交付 `OFF 61`／`CONFORM 84`／`OFF5 76`；
token 總量 `322,963`／`732,086`／`1,692,219`（N4）；
OFF 臂被載入器擋掉 **7** 題（N3）。
`--mutation-check` 逐個突變體重跑 selftest，要求**指名的那一條**檢查變紅
（**10 個**突變體全部 CAUGHT）：

| 突變體 | 拿掉什麼 | 必須變紅的檢查 |
|---|---|---|
| `M1_deliv_ignores_accepted` | `deliv` 不再要求 `accepted` | `L_deliv_requires_accepted` |
| `M2_union_denominator` | complete-case 分母改成聯集 | `N_complete_case_excludes_void` |
| `M3_tpc_ignores_void_calls` | TPC 不算 void 格燒掉的呼叫 | `O_tpc_incl_void_is_larger` |
| `M4_ignore_missing_fields` | 缺欄位不再 BROKEN | `H_missing_field_caught` |
| `M5_holm_family_drops_nonsignificant` | 家族丟掉不顯著的檢定 | `B_family_size_6` |
| `M6_costly_swallows_effective` | 判定順序調換且拿掉守衛 | `D_verdict_effective` |
| `M7_widen_windows` | 事前窗放到無限寬 | `P_window_ph0_miss` |
| **`M8_topology_not_enforced`**（D9） | 拓撲違規只描述不判 | `Q4_hub_use_is_caught`（連帶 Q5／Q6／Q7 也紅） |
| **`M9_stage2_any_arm`**（D9） | 階段二觸發鍵改成「任一臂 INCONCLUSIVE」 | `R_stage2_follows_hmix_only` |
| **`M10_block_broken_not_propagated`**（D9） | 逐塊的 BROKEN 不往上帶 | `Q8_block_accounting_errors_do_not_cancel` |
| **`M11_endpoint_balance_not_checked`**（A1） | 不數每顆端點掛了幾塊 | `Q9_endpoint_imbalance_is_caught` |

⚠ M10 擋的是一個**只有切塊才會出現**的失敗形狀：合併是相加，
而相加會讓兩塊**反向**的帳錯互相抵銷（某塊的 `processed` 多一題、
另一塊少一題 ⇒ 合併帳剛好對得上）。所以帳要逐塊查、違規往上冒
（`broken_reasons` 裡長成 `block:<塊名>:row_accounting:…`）。

⚠ M11 擋的是 round460e 這次**放寬**帶進來的失敗形狀：端點還是兩顆、塊數還是六，
但被塞成 4／2。那台四塊的後端會掉進「6 併發開始退化」的區間，
而那個世界裡**沒有任何既有欄位會變紅**——只會比較慢。
所以逐端點數塊數（`endpoint_block_count_not_3`），發射器發射前也數一次
（`abort_endpoint_imbalance`）。

**(6) 事前檢定力與 MDE（§五 的兩張表）**

```bash
cd /Users/cosmopig/Documents/GitHub/Vacant && .venv/bin/python - <<'PY'
import sys; sys.path.insert(0,'.')
from vacant.research import mcnemar_power, mcnemar_exact
from ops.gain.power_paired import mde_at_n
for n,q,psi in [(120,.20,.75),(120,.25,.70),(120,.325,.654),(189,.325,.654)]:
    print(n,q,psi,round(mcnemar_power(n,q,psi),3))
def min_gap(nd, alpha):
    for gap in range(0, nd+1):
        if (nd-gap)%2: continue
        b=(nd+gap)//2
        if mcnemar_exact(b,nd-b) < alpha: return gap, b, nd-b
for q in (.20,.25,.325):
    nd=round(120*q)
    print(q, mde_at_n(120,q), "holm:", min_gap(nd,0.05/6),
          "MDE_holm_pp", round(100*min_gap(nd,0.05/6)[0]/120,2))
PY
```

實測輸出即 §五 的兩張表（power 0.633／0.525／0.428／0.640；
MDE 10.00／10.00／12.50pp；Holm 下 11.67／13.33／15.83pp）。

**(7) D8 的邊界：既有五臂逐位元沒動**

```bash
cd /Users/cosmopig/Documents/GitHub/Vacant && .venv/bin/python -m pytest \
  tests/test_gain_harness_arms.py tests/test_r460_launcher_prereg.py -q
```

`tests/test_gain_harness_arms.py::T12` 比對 `arm_off`／`arm_off5`／`arm_conform`／
`arm_eq5`／`arm_on` 的原始碼 sha256；`tests/test_r460_launcher_prereg.py`
比對本檔、發射器、analyzer 三邊的旗標與仲裁欄位。

**(8) D9／A1：六塊的難度組成與 r447 的逐塊錨（P-H0 的窗就是從這裡來的）**

```bash
cd /Users/cosmopig/Documents/GitHub/Vacant && .venv/bin/python - <<'PY'
import sys, json, collections; sys.path.insert(0,'.')
from ops.gain.gain_run import load_tasks
bank={json.loads(l)["task_id"]: json.loads(l)
      for l in open("ops/gain/data/lcb_bank_v2.jsonl",encoding="utf-8") if l.strip()}
BLK={n:[t["task_id"] for t in load_tasks("lcb2","g-r440-lcb2",20,offset=o)]
     for n,o in (("a1",0),("a2",20),("a3",40),("b1",60),("b2",80),("b3",100))}
rows=[json.loads(l) for l in open("runs/g_r447_conform_lcb2/rows.jsonl",encoding="utf-8") if l.strip()]
deliv=lambda r: bool(r.get("accepted", True)) and bool(r.get("meets_demand"))
groups=list(BLK.items())+[("a1+a2+a3", BLK["a1"]+BLK["a2"]+BLK["a3"]),
                          ("b1+b2+b3", BLK["b1"]+BLK["b2"]+BLK["b3"]),
                          ("all", [x for v in BLK.values() for x in v])]
for nm, ids in groups:
    ids=set(ids)
    diff=collections.Counter(bank[i]["difficulty"] for i in ids)
    s={arm: (sum(deliv(r) for r in rows if r["arm"]==arm and r["task_id"] in ids),
             len([r for r in rows if r["arm"]==arm and r["task_id"] in ids]))
       for arm in ("OFF","CONFORM","OFF5")}
    print(f"{nm:9}", {k:diff[k] for k in ('medium','hard')}, s)
PY
```

實測（2026-09-08）：

```
a1        {'medium': 12, 'hard': 8} {'OFF': (7, 20), 'CONFORM': (10, 20), 'OFF5': (9, 20)}
a2        {'medium': 13, 'hard': 7} {'OFF': (15, 20), 'CONFORM': (18, 20), 'OFF5': (18, 20)}
a3        {'medium': 15, 'hard': 5} {'OFF': (10, 20), 'CONFORM': (12, 20), 'OFF5': (10, 20)}
b1        {'medium': 10, 'hard': 10} {'OFF': (12, 20), 'CONFORM': (14, 20), 'OFF5': (13, 20)}
b2        {'medium': 12, 'hard': 8} {'OFF': (8, 20), 'CONFORM': (17, 20), 'OFF5': (15, 20)}
b3        {'medium': 10, 'hard': 10} {'OFF': (9, 20), 'CONFORM': (13, 20), 'OFF5': (11, 20)}
a1+a2+a3  {'medium': 40, 'hard': 20} {'OFF': (32, 60), 'CONFORM': (40, 60), 'OFF5': (37, 60)}
b1+b2+b3  {'medium': 32, 'hard': 28} {'OFF': (29, 60), 'CONFORM': (44, 60), 'OFF5': (39, 60)}
all       {'medium': 72, 'hard': 48} {'OFF': (61, 120), 'CONFORM': (84, 120), 'OFF5': (76, 120)}
```

⇒ 三件事同時定下來：
1. **P-H0 的錨 ＝ 32/60 ＝ 53.33%**——`a1+a2+a3` 那一列，與兩塊版逐字相同
   （切法變了，那 60 題沒變）。
2. **塊間難度組成不同**（a3 只有 5 題 hard，b1／b3 各 10 題）⇒ §六-(0) 的
   「塊間點估計不得互相比較」不是客套話，是這張表逼出來的。
3. ⚠ **逐塊的 r447 OFF 交付率散得很開**（7/20 到 15/20，即 35% 到 75%）——
   n=20 的區塊本來就吵。**這正是 P-H0 不逐塊判、只在 a1+a2+a3 的聯集上判的理由**；
   收官也不准拿逐塊的 OFF 交付率去說任何「這一塊的卡比較好／比較差」。

**(9) 合併是無損的：把 r447 切成**六塊**再合併，逐字重現 61／84／76 與 token 總量**

```bash
cd /Users/cosmopig/Documents/GitHub/Vacant && .venv/bin/python - <<'PY'
import sys, pathlib; sys.path.insert(0,'.')
import ops.gain.analyze_r460 as A
from ops.gain.gain_run import load_tasks
API={"a":"http://100.119.113.56:1234/v1/chat/completions",
     "b":"http://100.86.226.21:1234/v1/chat/completions"}
rows, summ, calls = A.load_run(pathlib.Path("runs/g_r447_conform_lcb2"))
blocks=[]
for name, off in zip(A.AUTHORIZED_BLOCKS, (0,20,40,60,80,100)):
    ids={t["task_id"] for t in load_tasks("lcb2","g-r440-lcb2",20,offset=off)}
    api=API[name[-2]]
    rs=[r for r in rows if r["task_id"] in ids]
    cs=[dict(c, api=api) for c in calls if (c.get("meta") or {}).get("task_id","") in ids]
    n=len({r["task_id"] for r in rs})
    s={"run_terminal":True,"seed":"g-r440-lcb2","n":n,"offset":off,
       "arms":{x:{"processed":n,"infra_void":0,"wall_s":1.0,"complete":True,"terminal":True}
               for x in ("OFF","CONFORM","OFF5")}}
    blocks.append({"name":name,"path":"runs/"+name,"rows":rs,"summary":s,"calls":cs,
                   "endpoints":A.endpoints_of(cs),"offset":off,"n":n,"seed":"g-r440-lcb2",
                   "arms":sorted(("OFF","CONFORM","OFF5")),"task_ids":{r["task_id"] for r in rs}})
o=A.analyze([r for b in blocks for r in b["rows"]],
            A.merge_summaries([b["summary"] for b in blocks]),
            [c for b in blocks for c in b["calls"]], blocks=blocks)
print("broken:", o["broken_reasons"])
print("pooled deliv:", {a:o["per_arm"][a]["deliv_n"] for a in ("OFF","CONFORM","OFF5")})
print("pooled tokens:", {a:o["tokens"][a]["tokens_total_incl_void"] for a in ("OFF","CONFORM","OFF5")})
print("topology:", o["topology"]["blocks_n"], o["topology"]["task_ids_union"],
      {k: len(v) for k,v in o["topology"]["blocks_per_endpoint"].items()})
print("P-H0:", round(o["prereg"]["P-H0"]["value"],2), o["prereg"]["P-H0"]["hit"],
      o["prereg"]["P-H0"]["source_field"], o["ph0_pool_blocks"])
PY
```

實測（2026-09-08）：

```
broken: []
pooled deliv: {'OFF': 61, 'CONFORM': 84, 'OFF5': 76}
pooled tokens: {'OFF': 322963, 'CONFORM': 732086, 'OFF5': 1692219}
topology: 6 120 {'http://100.119.113.56:1234/v1/chat/completions': 3, 'http://100.86.226.21:1234/v1/chat/completions': 3}
P-H0: 53.33 HIT ph0_pool.per_arm.OFF.deliv_pp_denom_measured ['g_r460_harness_lcb2_a1', 'g_r460_harness_lcb2_a2', 'g_r460_harness_lcb2_a3']
```

⇒ **合併路徑不改變任何一個既有數字**（交付數與 token 總量都與 §九-5 的單塊 selftest
逐字相同，也與兩塊版逐字相同），拓撲六塊／聯集 120／每顆端點三塊全綠，
而且 P-H0 真的讀的是 `ph0_pool`（a1+a2+a3），不是合併值。
`--mutation-check` 的 `M8_topology_not_enforced` 與 `M11_endpoint_balance_not_checked`
另外證明拓撲擋門有牙齒（拿掉前者，走 hub／塊間交集／端點數／塊數／端點超賣／聯集
六條檢查同時變紅；拿掉後者，只有超賣那一條漏掉，而那一條**沒有別的欄位會抓到**）。

---

## 十、中止準則（發射之後，什麼情況要停）

1. **任一臂 `infra_void` 率 > 20%** ⇒ 停，資料不進結論（SPEC 既有擋門）。
2. **`harness_wire_mode` 在同一條臂裡出現兩種值** ⇒ 停（兩種模式不得混算）。
   ⚠ `probe_wire_mode` 只在端點回 400/422 時才退回攤平；**連不上／逾時照 `InfraVoid`
   往外拋**，不讓一次瞬斷改變整個 run 的實驗條件。
   本階段的線路探針實測：`/v1/chat/completions`、四則訊息（system／user／assistant／user）、
   HTTP 200、`finish_reason="stop"`、content `OK`、latency 652 ms、
   `server_model=gemma-4-12b-it-qat` ⇒ `harness_wire_mode="multiturn"`。
   ⚠ **攤平模式雖然實作了、也有兩個單元測試，但沒有在真端點上跑過**——
   若本 run 真的退回攤平，那條路徑是第一次上線，收官必須標明。
3. **`gain_run` 沒有續跑**（輸出目錄有產物就 `SystemExit` 拒絕 append）。
   一塊 20 題，中斷一次那一塊就得從頭——**這正是切成六塊的附帶好處**：
   重跑的代價從 60 題掉到 20 題。
   ⚠ **切塊在 D9／A1 之後不是應變方案，是本 run 的設計本身**（§二-5），
   而它的代價已經逐條登記：persona 對齊只剩 a1 的前 20 題
   （每塊的 `random.Random(f"{seed}:{arm}")` 各自從頭開始）
   ⇒ **P-H0 是非配對的粗探針**（§三 P-H0）。
   ⚠ **不准再切第七刀**：切成別的塊數需要另一份 DECISION，
   而且要重寫 P-H0 的錨塊池與 §六-(0) 的合併規則。
4. **有任何一塊沒跑完** ⇒ 停，**不判裁決**（§六-(6)-i）。
   跑完那幾塊的資料留著、照樣落盤，但要用它必須另開 DECISION 並重算該 n 的檢定力。
5. **拓撲違規**（走 hub／端點數不是 2／某顆端點不是三塊／一塊兩個端點／
   塊間 task_id 有交集／聯集不是 120）⇒ 停，E-7 紅。
   發射器在發射前擋一次（`abort_hub_endpoint`／`abort_same_endpoint`／
   `abort_endpoint_imbalance`／`abort_block_count`），
   analyzer 在收官時再擋一次（`topology.violations`）。**兩道都不准繞過。**
6. **V/GT 動態稽核任何一條命中** ⇒ **整個 run 作廢**，照 SPEC_GAIN §7 落盤並公開，
   不得只修不報。收官必跑（**六塊各跑一次，六塊都要 CLEAN**）：
   `for b in a1 a2 a3 b1 b2 b3; do python3 ops/gain/harness_vgt_audit.py --run runs/g_r460_harness_lcb2_$b --bank lcb2; done`
   ⚠ 讀結果時要**一起看** `needles_skipped_trivial`：那是被判成沒有鑑別力而跳過的
   needle 數（A2），「沒有違規」不等於「每一個 needle 都檢查過」。

**預估機時**：用 r447 的實測外推——單塊六臂 ≈11 h／60 題 ⇒ **每 20 題約 3.7 h**；
六塊併發、每台三塊 ⇒ 牆鐘 **≈4 h（估計，不是量測）**、合計算力仍是 ≈22 h。$0（本地後端）。
⚠ **「吞吐 ×3」是從短請求的併發實測外推的**（1 個 1.3 s／3 個併發各 1.3 s），
本 run 的請求是 160–560 s 的長生成，**三併發之下每條會不會變慢沒有事前資料**（§八-13）。
所以上面那個牆鐘是估計；收官報機時要照實寫成估計，而且要用發射器 log 的真牆鐘更正它。
**worker 行程內併發：`gain_run` 沒有旋鈕，也不准加**——round22/23/262 已量到對
**同一個端點無上限併發**會觸發 500／逾時（`DECISION_20260824_SERIALIZE_CONCURRENT_CALLS.md`）。
⇒ runner **行程內**支援的最大併發度就是 **1（依序送出）**，發射器把這個值寫在明處
（`WORKER_CONCURRENCY=1`），並且在 `gain_run.py` 裡出現 `ThreadPoolExecutor(` 時直接中止
（`abort_concurrency_knob_appeared`），逼下一個人回來重新裁決這一格。
⚠ **本 run 的平行度不是來自那個旋鈕**，而是來自「六個行程、每顆 GPU 三個」
（發射器的 `BLOCK_PARALLELISM=6`、`BLOCKS_PER_ENDPOINT=3`）：
**每一個行程仍然是一次一個請求**。這一格與 round22/23/262 的關係寫在 §二-5：
那條裁決擋的是 hub 與無上限併發，本輪把上限明文寫死成 3 並且雙重檢查。

---

## 十一、階段二（**現在就凍結，門檻不得在看到階段一之後修改**）

| 項 | 值 |
|---|---|
| 觸發條件 | 階段一的 **H-MIX** 落在 `INCONCLUSIVE`（§六-(4)），`analyze_r460.py` 印 `stage2_triggered`。⚠ 觸發鍵**只讀 H-MIX**；`stage2_triggered_any_arm_NOT_TRIGGER` 不是觸發鍵 |
| run 名 | **`runs/g_r461h_harness_lcb3_a`**（`--offset 0 --n 95`）＋ **`runs/g_r461h_harness_lcb3_b`**（`--offset 95 --n 94`）（本檔一併授權這兩個名字；**不帶 `_a`／`_b` 的 `runs/g_r461h_harness_lcb3` 不在授權內**）。切法與端點指派沿用 D9：**兩顆直連後端、不准走 hub、一塊一端點**；若發射當下的機時拓撲已經不同（例如 hub 修好了、或只剩一顆卡），**要另開 DECISION 改這一格**，不准就地改 |
| 題庫／題數 | **LCB v3、189 題**（`ops/gain/data/lcb_bank_v3.jsonl`），與 lcb2 的 120 題 **零交集**；兩塊 95＋94 合起來取全部，塊間零交集。⚠ 階段二的**切法沒有跟著改成六塊**：本檔凍結的是 `_a`／`_b` 兩塊，要改成別的切法必須另開 DECISION（改切法會改 P-H0 的錨塊池、每端點塊數與檢定力表的讀法） |
| seed | **`g-r461-lcb3`**——取的是 **r461 那批 189 題**（v3 bank 就是 189 題、`--n 189` 取全部 ⇒ seed 只決定題序）。**這顆 seed 已被 `runs/g_r461_lcb3_three_arm` 與 `runs/g_r461_off_gate_lcb3` 用過**，理由與 §二-4 同構：重用買到與 r461 的逐格對齊，而它不造成重複抽樣（bank 全取）。發射時必須用同一套「授權集合相等」檢查，授權句是 `SEED_REUSE_AUTHORIZED: g-r461-lcb3 <- runs/g_r461_lcb3_three_arm, runs/g_r461_off_gate_lcb3` |
| 臂 | **與階段一逐字相同的六條**：OFF,CONFORM,OFF5,HPI,HOC,HMIX |
| 預算 | D1，一個字不改 |
| 門檻 | **§六 逐字**（+25.0pp／+10.0pp／Holm 6 個檢定／未調整 CI／(iii)(iv)），**不得修改** |
| 檢定力 | n=189 對 +10pp 是 0.64–0.85（§五 右欄）——**仍不是充足，是比 120 好** |
| ⚠ | **lcb3 不是難題題庫**（R461 稽核 §二-2：OFF 失敗率 27.5%，MBPP+ 量級 31.8%，lcb2 是 49.2%）。階段二是「第二個題庫的確認」，**不是**「更難的題目上也成立」。狀態名不准帶 `HARD` |
| ⚠ | 階段二是**預註冊的確認不是探索**。它的 `runner_git.sha` 與階段一大機率不同 ⇒ E-4 要重跑一次 |
| ⚠ | **階段二沒有 P-H0**。lcb3 的 seed 是重用 r461 的，但階段二**也切塊** ⇒ 只有 block a 的前 95 題與 r461 的 persona 指派對齊；階段二的漂移探針要在發射前照 §九-8 的做法重算 r461 前 95 題的 OFF 交付率當錨，**窗一樣是 ±15pp**，而且要寫進階段二自己的那一段。**不准沿用本檔的 [38.3, 68.3]**——那個窗是 lcb2 前 60 題的 |

階段二的 seed 授權句（發射器 grep 得到的逐字版本，行首）：

```
SEED_REUSE_AUTHORIZED: g-r461-lcb3 <- runs/g_r461_lcb3_three_arm, runs/g_r461_off_gate_lcb3
```

---

## 十二、這份預註冊自己的邊界

- 本檔**不授權**任何其他 run 名字、其他 seed、其他題庫、其他臂組合、**其他端點拓撲**。
  階段一恰好六個名字（`…_a1`／`…_a2`／`…_a3`／`…_b1`／`…_b2`／`…_b3`），
  階段二恰好兩個名字，加上零 API 的 `r460_probe`。
  **round460e 之前的名字（`runs/g_r460_harness_lcb2`、`…_a`、`…_b`）不在授權內**
  ——R440G 的子字串比對擋不掉它們（`…_a1` 甚至整個含著 `…_a`），
  所以發射器自己擋（`abort_stale_run_name`）。
- 本檔**不預測** H 臂會贏。§五 事前算出最可能的落點是 `INCONCLUSIVE`，
  §一 算出即使把 41 題全修好、轉換率不變，交付率上限也只有 73.9%——
  **打不到 EFFECTIVE 需要的 80%**。這兩件事寫在資料之前。
- 本檔的三條 H 臂**是三點比較，不是因子拆解**（§一-3）。
- 本檔引用的所有外部事實都在 `docs/HARNESS_STUDY_2026-09-07.md` §1，
  並且**該節的三條引用更正（60 個 entry、`as of Dec 1, 2025` 的快照口徑、
  `agent/agent.ts:121`）標明「稽核者核對、本機無該倉庫、本輪未一手重驗」**。
  引用它們時要連這句話一起帶。

- 本檔的 A1（六塊）**放寬了一條既有的紀律**（一端點一 run）。放寬的依據是短請求的
  併發實測，而本 run 跑的是長請求 ⇒ **「三併發不掉速」在本 run 的工作負載上沒有被驗證過**
  （§八-13）。若收官發現逐塊牆鐘遠超估計、或 `infra_void` 率上升，
  那**先是**拓撲假設的問題，不是 H 臂的問題——不准把它讀成臂的效果。

**Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>**
