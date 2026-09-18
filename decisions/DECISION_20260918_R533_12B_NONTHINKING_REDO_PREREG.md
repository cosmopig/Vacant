# R533 預註冊：12B 全部用**不思考**重做 R529 的四個題組

**立題（人類 2026-09-18 指示）**：R529 的 12B 基線裡，`1003` 那 22 塊是 **100% thinking**、
`1004` 那 15 塊是 **0%**，混在一起當成一條基線去跟 R532（27B，0% thinking）比，
四個題組的跨模型差值裡混著兩個效應，分不開。**把 12B 全部用不思考重做。**

這不是新實驗，是**把既有基線的一個混淆拔掉**。除了推論模式與後端，
其餘一切沿用 R529，**不得順手改別的東西**。

---

## 一、混淆的實證（重做的理由，資料在手）

| 後端 | LM Studio | 成功呼叫 | 有 reasoning | 占比 |
|---|---|---:|---:|---:|
| `1003`（100.119.113.56） | 0.4.24.0 | 1,509 | 1,509 | **100.0%** |
| `1004`（100.86.226.21） | 0.4.17.0 | 1,016 | 0 | **0.0%** |

**同一個 gguf、同一個 `--models gemma-4-12b-it-qat`、請求體裡沒有任何 reasoning 旗標**——
差別純粹來自後端版本。逐塊是全有或全無（沒有一塊是混的），所以歸因乾淨。

逐題組受影響程度（R529 合併值）：MBPP+ 61.7%、HumanEval+ 61.6%、
LCB v3 hard 62.0%、LCB v3 medium 51.2%。

**LCB v2（R460）不受影響**：那輪 1,554 通全在 0%，是五組裡唯一乾淨的同模式對照。
⇒ **R533 不重做 LCB v2。**

---

## 二、凍結條件

| 項目 | 值 | 與 R529 比 |
|---|---|---|
| 模型 | `gemma-4-12b-it-qat` | **相同** |
| 後端 | **只用 1004**（100.86.226.21，LM Studio 0.4.17.0） | R529 用兩台 ⇒ **本輪單後端** |
| context_length | 262,144 | **相同** |
| parallel | 4（每槽 65,536） | **相同** |
| gpu | max ／ flash_attention on ／ ttl `null` | **相同** |
| 題組 | lcb3 medium 135／lcb3 hard 54／HE+ 156／MBPP+ 371 ＝ **716 題** | **相同** |
| 塊 | 37 塊，`(bank, filter, seed, offset, n)` 逐塊照抄 R529 | **相同** |
| seed | `g-r529-lcb3`／`g-r529-he`／`g-r529-mbpp` | **相同** |
| 臂 | `OFF,CONFORM,HMIX` | **相同** |
| temperature | 0.7；top_p／max_tokens／seed 皆未設 | **相同** |
| retries 4／review_retries 2／review_timeout 380／timeout 900 | 同 R529 | **相同** |
| `--reasoning-effort none` | **帶**（1004 本來就 0%，這是雙保險） | R529 未帶 |

**為什麼只用 1004**：`gemma-4-12b-it-qat` **不在 1003 的磁碟上**
（2026-09-18 01:1xZ 查 `/api/v0/models`，1003 只有 `qwen3-27b`）。
在死線內無法把 13 GB 模型弄上去，**且就算弄上去，1003 的 0.4.24 正是製造思考的那一版**。
⇒ 單後端是**正確的選擇不是妥協**：它同時消掉「思考混淆」與「跨後端混淆」。
代價寫明：本輪沒有跨後端的變異估計，牆鐘也較長。

**發射前探針（已做，2026-09-18 01:2xZ）**：1004 載入後對 gemma 打四通
（三通不帶旗標、一通帶 `reasoning_effort=none`），`reasoning_tokens` **四通全為 0**。

---

## 三、事前預測（看到任何資料之前寫死）

1. **12B 不思考的交付率會比 12B 思考低**，四組皆然。理由：R529 的思考版每通多燒
   約 3,600 個 reasoning token，那些 token 不是白燒的。
   **若不降反升，要停下來查是不是別的東西被改到。**
2. **Δ_C（HMIX − CONFORM）在 12B 不思考下仍為正**，四組至少三組同號。
   理由：R529 四組是 +0.74／+3.70／+0.64／+1.08，R460（本來就不思考）是 +13.33。
   **若翻負，那代表「Δ_C 為正」本身就依賴思考模式**——那是比原本問題更大的發現，要照實報。
3. **Δ_G（CONFORM − OFF）仍為正且明顯大於 Δ_C**，四組皆然。

## 四、裁決（四狀態，**帶方向守衛**——這是 R532 AMEND1 的教訓）

| 狀態 | 條件 |
|---|---|
| `INVALID` | V/GT 有 violation／事後測到 reasoning ≠ 0／零 void 不成立 |
| `CONFIRMED_POSITIVE` | Δ_C 合併 Holm 後成立 **且點估計為正** |
| `CONFIRMED_NEGATIVE` | Δ_C 合併 Holm 後成立 **且點估計為負** ⇒ 「Δ_C 為正依賴思考模式」 |
| `RULED_OUT` | Δ_C 合併區間上緣 < +2.0 pp |
| `INCONCLUSIVE` | 其餘；必須同報 MDE 與事前檢定力 |

狀態**互斥**，求值順序：`INVALID` → 方向兩態 → `RULED_OUT` → `INCONCLUSIVE`。
（R532 §四-2 沒寫互斥也沒守方向，導致一個負向顯著結果被貼成 `EFFECTIVE`。）

## 五、誠實邊界

- 本輪與 R529 **不得併 n**：不同後端、不同時間、不同推論模式。
- 本輪是**單後端**，沒有跨後端變異估計。
- 重做的是 12B 基線，**不改 R532 的任何內部結論**（Δ_C −3.23 pp 那組是同輪同模型配對，不受影響）。
- 禁語沿用：不准寫「複製失敗」「效果消失」「等價」「多數支持」「複製穩定」。

---

## 附錄 A　逐塊註冊（R440G 閘門逐字比對；37 塊／716 題）

每一行的 `(bank, filter, n, offset, seed)` **逐字照抄 R529 的同名塊**（`source` 欄）。
```
R533_BLOCK: g_r533_hep_a1 bank=humanevalplus filter=- n=20 offset=0 seed=g-r529-he source=g_r529_hep_a1
R533_BLOCK: g_r533_hep_a2 bank=humanevalplus filter=- n=20 offset=20 seed=g-r529-he source=g_r529_hep_a2
R533_BLOCK: g_r533_hep_a3 bank=humanevalplus filter=- n=20 offset=40 seed=g-r529-he source=g_r529_hep_a3
R533_BLOCK: g_r533_hep_a4 bank=humanevalplus filter=- n=20 offset=60 seed=g-r529-he source=g_r529_hep_a4
R533_BLOCK: g_r533_hep_a5 bank=humanevalplus filter=- n=20 offset=80 seed=g-r529-he source=g_r529_hep_a5
R533_BLOCK: g_r533_hep_a6 bank=humanevalplus filter=- n=20 offset=100 seed=g-r529-he source=g_r529_hep_a6
R533_BLOCK: g_r533_hep_a7 bank=humanevalplus filter=- n=20 offset=120 seed=g-r529-he source=g_r529_hep_a7
R533_BLOCK: g_r533_hep_a8 bank=humanevalplus filter=- n=16 offset=140 seed=g-r529-he source=g_r529_hep_a8
R533_BLOCK: g_r533_lcb3h_a1 bank=lcb3 filter=difficulty=hard n=20 offset=0 seed=g-r529-lcb3 source=g_r529_lcb3h_a1
R533_BLOCK: g_r533_lcb3h_a2 bank=lcb3 filter=difficulty=hard n=20 offset=20 seed=g-r529-lcb3 source=g_r529_lcb3h_a2
R533_BLOCK: g_r533_lcb3h_a3 bank=lcb3 filter=difficulty=hard n=14 offset=40 seed=g-r529-lcb3 source=g_r529_lcb3h_a3
R533_BLOCK: g_r533_lcb3m_a1 bank=lcb3 filter=difficulty=medium n=20 offset=0 seed=g-r529-lcb3 source=g_r529_lcb3m_a1
R533_BLOCK: g_r533_lcb3m_a2 bank=lcb3 filter=difficulty=medium n=20 offset=20 seed=g-r529-lcb3 source=g_r529_lcb3m_a2
R533_BLOCK: g_r533_lcb3m_a3 bank=lcb3 filter=difficulty=medium n=20 offset=40 seed=g-r529-lcb3 source=g_r529_lcb3m_a3
R533_BLOCK: g_r533_lcb3m_a4 bank=lcb3 filter=difficulty=medium n=20 offset=60 seed=g-r529-lcb3 source=g_r529_lcb3m_a4
R533_BLOCK: g_r533_lcb3m_a5 bank=lcb3 filter=difficulty=medium n=20 offset=80 seed=g-r529-lcb3 source=g_r529_lcb3m_a5
R533_BLOCK: g_r533_lcb3m_a6 bank=lcb3 filter=difficulty=medium n=20 offset=100 seed=g-r529-lcb3 source=g_r529_lcb3m_a6
R533_BLOCK: g_r533_lcb3m_a7 bank=lcb3 filter=difficulty=medium n=15 offset=120 seed=g-r529-lcb3 source=g_r529_lcb3m_a7
R533_BLOCK: g_r533_mbpp_a1 bank=evalplus filter=- n=20 offset=0 seed=g-r529-mbpp source=g_r529_mbpp_a1
R533_BLOCK: g_r533_mbpp_a10 bank=evalplus filter=- n=20 offset=180 seed=g-r529-mbpp source=g_r529_mbpp_a10
R533_BLOCK: g_r533_mbpp_a11 bank=evalplus filter=- n=20 offset=200 seed=g-r529-mbpp source=g_r529_mbpp_a11
R533_BLOCK: g_r533_mbpp_a12 bank=evalplus filter=- n=20 offset=220 seed=g-r529-mbpp source=g_r529_mbpp_a12
R533_BLOCK: g_r533_mbpp_a13 bank=evalplus filter=- n=20 offset=240 seed=g-r529-mbpp source=g_r529_mbpp_a13
R533_BLOCK: g_r533_mbpp_a14 bank=evalplus filter=- n=20 offset=260 seed=g-r529-mbpp source=g_r529_mbpp_a14
R533_BLOCK: g_r533_mbpp_a15 bank=evalplus filter=- n=20 offset=280 seed=g-r529-mbpp source=g_r529_mbpp_a15
R533_BLOCK: g_r533_mbpp_a16 bank=evalplus filter=- n=20 offset=300 seed=g-r529-mbpp source=g_r529_mbpp_a16
R533_BLOCK: g_r533_mbpp_a17 bank=evalplus filter=- n=20 offset=320 seed=g-r529-mbpp source=g_r529_mbpp_a17
R533_BLOCK: g_r533_mbpp_a18 bank=evalplus filter=- n=20 offset=340 seed=g-r529-mbpp source=g_r529_mbpp_a18
R533_BLOCK: g_r533_mbpp_a19 bank=evalplus filter=- n=11 offset=360 seed=g-r529-mbpp source=g_r529_mbpp_a19
R533_BLOCK: g_r533_mbpp_a2 bank=evalplus filter=- n=20 offset=20 seed=g-r529-mbpp source=g_r529_mbpp_a2
R533_BLOCK: g_r533_mbpp_a3 bank=evalplus filter=- n=20 offset=40 seed=g-r529-mbpp source=g_r529_mbpp_a3
R533_BLOCK: g_r533_mbpp_a4 bank=evalplus filter=- n=20 offset=60 seed=g-r529-mbpp source=g_r529_mbpp_a4
R533_BLOCK: g_r533_mbpp_a5 bank=evalplus filter=- n=20 offset=80 seed=g-r529-mbpp source=g_r529_mbpp_a5
R533_BLOCK: g_r533_mbpp_a6 bank=evalplus filter=- n=20 offset=100 seed=g-r529-mbpp source=g_r529_mbpp_a6
R533_BLOCK: g_r533_mbpp_a7 bank=evalplus filter=- n=20 offset=120 seed=g-r529-mbpp source=g_r529_mbpp_a7
R533_BLOCK: g_r533_mbpp_a8 bank=evalplus filter=- n=20 offset=140 seed=g-r529-mbpp source=g_r529_mbpp_a8
R533_BLOCK: g_r533_mbpp_a9 bank=evalplus filter=- n=20 offset=160 seed=g-r529-mbpp source=g_r529_mbpp_a9
```

佇列 `ops/gain/queues/r533.json` sha256 **d5e767ebfa9c9ec2…**（37 塊／716 題）。

---

## AMEND1（2026-09-18 01:2xZ，發射後 11 分鐘）：**1003 可用，改為兩台八流**

### 我在 §二 寫錯的事實

§二 寫「`gemma-4-12b-it-qat` **不在 1003 的磁碟上**（查 `/api/v0/models`，1003 只有 `qwen3-27b`）」。
**這是錯的。** `/api/v0/models` **只列出已載入的模型**，不是磁碟上有的。
改查 `/api/v1/models` 後，1003 磁碟上有 `gemma-4-12b-it-qat`（7.2 GB），
直接 `POST /api/v1/models/load` 41.8 秒載入成功。

**教訓**：判斷「某台有沒有某個模型」要用 `/api/v1/models`（列全部），
不能用 `/api/v0/models`（只列 loaded）。我用後者下了一個影響拓撲的結論。

### 1003 的思考關得掉（實測）

| 請求 | reasoning_tokens |
|---|---:|
| 不帶旗標 ×2 | **397、397** |
| 帶 `reasoning_effort=none` ×2 | **0、0** |

⇒ **R529 的 100% thinking 是「0.4.24 預設思考 ＋ 當時驅動沒送這個旗標」兩件事湊出來的**，
不是後端不可控。R533 的驅動本來就送 `--reasoning-effort none`，所以 1003 可以用。

### 變更後的凍結條件

- 後端：**1003 ＋ 1004 兩台**（原寫「只用 1004」作廢）。
- 兩台載入參數**逐項相同**：`context_length 262144`／`parallel 4`／每槽 65,536／
  `flash_attention` on／`ttl null`／gpu max。1003 先卸掉 `qwen3-27b` 才載 gemma（VRAM）。
- 並行：每台四條流，**全域八流**。1004 先發（01:13:27Z）、1003 後補（01:24:18Z）。
- 塊分配：1004 四流跑既有 plan；1003 四流接手當時**尚未開始**的 33 塊裡的後 17 塊。
- **跨流保護**：驅動新增「`$OUT` 目錄已存在 ⇒ 跳過」。
  原本只跳過 `run_complete` 的塊，而 `gain_run` 看到目錄存在會拒跑
  ⇒ 兩條流撞同一塊時整條序列會被誤判成失敗停掉。跳過的塊由收官逐塊對帳，不會漏。

### 對「單後端」那條誠實邊界的修正

§五 原寫「本輪是單後端，沒有跨後端變異估計」——**作廢**。
本輪是兩後端，但**兩台的推論模式都實測為 0**（發射後落盤驗證：
1004 233 通、1003 12 通，reasoning 全 0），所以 R529 的那個混淆已經消除。
仍要在收官時**逐後端拆開報交付率**，確認沒有新的跨後端差異。
