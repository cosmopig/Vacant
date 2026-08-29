# DECISION round260（2026-08-29）：ONR 路由測不出增益的原因是**池子同質**，不是路由壞掉

決策者：Opus 5（`NEXT_MODEL=opus` 由 round259 指定，理由是「b 側 +2 跳動疑似訊號轉向」）
資料：`runs/g_onr_r212_20260828`(OFF, 179 列，已完成)、
`runs/g_onr_only_r237_20260828`(ONR, 本輪 149-155 列，仍在跑)
新工具：`ops/gain/power_paired.py`（本輪新增，雙向驗證見下）

---

## 1. 先否掉 round259 交棒的那個「訊號」——那是用錯單位

round252-259 把 discordant pair 按**輪次**報，round259 說「b 側 5→7 是監測以來
最大單輪跳動、首次讓 ONR<OFF」，要求本輪判斷是雜訊還是訊號轉向。

**「一輪」是牆鐘窗口，不是證據單位。** 一輪裡冒出幾個 discordant pair，取決於那
500 秒剛好跑完幾題，跟有沒有訊號無關。`analyze_paired.py` 自己的 docstring 早就
寫了「證據單位是 discordant pair」。正確作法是把 discordant pair 按**到達順序**
（ONR `rows.jsonl` 的行序）排成序列，在序列上檢定。

判準在量測之前寫死（`/dev/shm/r260_criterion.md`，時戳 00:06 UTC）：
T1 最近 5 個全同向（單尾 p=0.031）／T2 最近 8 個 ≥7 同向／T3 全序列 p<0.05，
任一成立才算「值得追」。

實測到達序列（12 個）：

```
bbccbbcccbbb
  b（只有 OFF 對）=7   c（只有 ONR 對）=5   全序列 McNemar 精確雙尾 p = 0.7744
  最近 5 個 = ccbbb   同向最多 3/5   單尾 p = 0.5000
  最近 8 個 = bbcccbbb 同向最多 5/8   單尾 p = 0.3633
  觸發的推翻條件：無  ⇒ 判定：noise
```

**裁決：雜訊。** 序列尾端剛好是 `bbb`，所以某一個牆鐘窗口看起來「跳了 +2」——
那是切窗切出來的錯覺。⛔ 下輪起不准再拿「單輪跳動幅度」當訊號候選。

## 2. 終局判決已經被算術鎖死，繼續跑不會改變它

配對上限 n=179（OFF 只有 179 列）。c 已經是 5 且只增不減，
要 p<0.05 需要 b≥15，而目前 b=7、只剩約 30 個配對格、discordant rate 8.05%：

```
剩餘 30 格 × 8.05% ≈ 2.4 個新 discordant
P(跑完 n=179 時 McNemar p<0.05) = 2.513e-05
⇒ 終局判決「兩臂測不出差異」的機率 = 0.999975
```

**⇒ 不 kill 現有 run（讓紀錄完整、$0、已在跑），但不再把每次 checkpoint 當成
「答案可能翻盤」。** round252-259 那 8 輪其實在監測一個答案已定的東西。

## 3. 排除「路由是 no-op」——路由確實在動，動很大

```
OFF n=179 worker 分佈：careful-1 18%  careful-2 12%  hasty-1 18%  hasty-2 24%  plain-1 16%  plain-2 12%（近乎均勻）
ONR n=155 worker 分佈：careful-2 53%  plain-2 34%  hasty-2 7%  careful-1 3%  plain-1 3%  hasty-1 1%（87% 集中在兩個）
```

配對 150 格中，兩臂選到**同一個 worker** 只有 18 格（12%）。所以路由機制本身
是有效的，no-op 假說被否掉。但——

```
同 worker 的 18 格：結果一致 18/18 = 100.0%
異 worker 的 132 格：結果一致 119/132 = 90.2%   ⇒ discordant 只有 13 個
```

**換了 worker，九成的題目答案不變。**

## 4. 真正的原因：池子在「能力」上是同質的，只在 persona 上異質

這個 run 的 `--models` 只給了一個 model：六個 agent 全部是
`qwen/qwen3.6-35b-a3b`，差別只有 `brain_cline.py:245` 的 `POOL` 六段 system prompt
（careful/plain/hasty 各兩個）。**路由選的是人格，不是能力。**

OFF 臂的 worker 是隨機指派 ⇒ OFF 的 per-persona 命中率是無偏估計：

```
careful-1  23/32 = 71.9%  CI95 [54.6, 84.4]
careful-2  18/22 = 81.8%  CI95 [61.5, 92.7]
hasty-1    28/32 = 87.5%  CI95 [71.9, 95.0]
hasty-2    33/43 = 76.7%  CI95 [62.3, 86.8]
plain-1    23/28 = 82.1%  CI95 [64.4, 92.1]
plain-2    20/22 = 90.9%  CI95 [72.2, 97.5]
全距 19.03 pp，全臂平均 81.01%
```

19pp 全距 > n=179 的 MDE 5.59pp，看起來像有搞頭。**但那是雜訊：**

```
檢定一（置換檢定 B=20000，統計量=命中率全距，seed=20260829）
  觀測全距 19.03 pp，置換 p = 0.4685
  ⇒ 無法拒絕「六個 persona 一樣好」
```

而且路由**確實**集中到了 OFF 帳面上最好的兩個（plain-2 90.9%、careful-2 81.8%），
但那個優勢沒有轉移：

```
檢定二（可轉移性，配對格 n=150）
  用 OFF 的 per-persona 率 × ONR 路由分佈，預測 ONR 命中率 = 84.51%
  ONR 實際命中率 = 79.33%    OFF 全臂平均 = 81.01%
  預測誤差 = -5.17 pp
```

這是教科書等級的**回歸均值**：per-persona 的帳面差距是抽樣雜訊，路由追著它跑，
優勢在新題目上沒有兌現。三件事互相印證，指向同一個結論。

### 結論（本輪的答案）

> **不是路由壞掉，是沒有東西可路由。** 六個 persona 的能力在統計上分不開
> （置換 p=0.47），所以**任何**路由器——包含完美的 oracle——在這個池子上都
> 產生不出可偵測的增益。ONR vs OFF 的 p=0.77 是這個結構的必然結果，不是失敗。

⚠ 誠實邊界：置換 p=0.4685 是「無法拒絕齊一」，不等於「已證明齊一」。每個
persona 只有 22-43 個樣本，真有 5-10pp 的差距也照樣測不出來。正確的說法是
**「在這個樣本量下，persona 差異與零無法區分，且路由帳面優勢不可轉移」**。

## 5. MDE 表（提高 discordant rate 不會幫忙，這點反直覺）

```
n=179 固定：dr= 8% ⇒ MDE=5.59pp ／ dr=20% ⇒ 7.82pp ／ dr=50% ⇒ 11.17pp
```

MDE_pp ≈ 1.96·√(dr/n) ⇒ **discordant rate 越高，能解析的 pp 差距反而越粗**。
能救 power 的只有 n。而若真實效果就是觀測值（p_b=0.583），80% power 需要
**281 個 discordant pair ≈ 3,490 個配對任務**，MBPP+ 只有 378 題 ⇒ **不可達**。
⇒ 加大 n 這條路在這個題庫上也是死的。

## 6. 下一個實驗（實驗條件的改變，記在這裡）

**改變：池子從「一個 model × 六種 persona」換成「多個能力不同的 model」。**
`gain_run.py:710` 的 `--models` 本來就支援 comma-separated round-robin 指派，
人類 2026-08-24 的指令也已經寫了 `--models qwen/qwen3.6-35b-a3b,nvidia/nemotron-3-nano-omni`。
這個 run（round237 起）刻意只用了單一 model，所以池子同質。

- **放棄了什麼**：與 round212/237 的 OFF 基準不再可配對（池子變了 ⇒ 條件不同，
  `analyze_paired.py` 的條件比對會直接叫）。新池子要重跑自己的 OFF。
- **根據什麼選的**：§4 的三個互相印證的量測（置換檢定、可轉移性、同 worker 100% 一致）。
  這是**量測**，不是判斷。至於「nemotron-3-nano 比較弱所以池子會異質」——
  **那是判斷，還沒量過**，下一輪必須先用 `--arms probe` 或 `calibrate_pool`
  量出 per-model 命中率，證明池子真的異質，再跑正式的三臂。
- **什麼條件下該被推翻**：若新池子的 per-model 置換檢定 p 仍 >0.05（＝換了 model
  還是分不開），那就不是池子的問題，要回頭懷疑 MBPP+ 這個題庫本身
  （§5 已證明它連 281 個 discordant pair 都湊不出來）。

⛔ 本輪**不啟動**新 run：`g_onr_only_r237_20260828` 還在跑，兩個 run 同時打
同一個中轉會互相拖慢，而延遲是實驗條件（SPEC_GAIN §7）。新 run 等它跑完再開。

## 7. 新工具 `ops/gain/power_paired.py` 的雙向驗證（跑過，貼真的輸出）

```
A 對帳 analyze_paired 的 p：全部相同 ✓        （7 組 (b,c) 逐一比對）
B 已知邊界：p(12,3)=0.0352 顯著、p(11,4)=0.1185 不顯著 ✓
C MDE 真的是最小值（小一格就不顯著）✓
D n_needed 單調遞增 ✓ 194 / 783 / 4904；p_b=0.60 需 194（文獻量級 ~190-200）
植入缺陷（造一組最近 5 個全同向的假 run）⇒ 工具必須叫：
  discordant 到達序列（5 個）：bbbbb
  最近 5 個 = bbbbb  同向最多 5/5  單尾 p = 0.0312
  觸發的推翻條件：['T1']  ⇒ 判定：signal_worth_following   ✓ 會叫
```

---

## 8. 補充（00:18 UTC）：下一輪要用的 model ID 跟人類指令寫的**不一樣**

用 `/v1/models` 查中轉（純列表查詢、不是推論呼叫 ⇒ 不會污染在跑的 run 的延遲）：

```
$ curl -s http://100.119.113.56:8765/v1/models
中轉服務的 model 共 4 個：
   qwen_qwen3.6-35b-a3b
   qwen/qwen3.8-27b
   gemma-4-12b-it-qat
   text-embedding-nomic-embed-text-v1.5
```

⛔ **`nvidia/nemotron-3-nano-omni` 不在服務清單裡。** 人類 2026-08-24 的指令範例
寫了這個 model，若下一輪照抄，`gain_run.py:821` 的 preflight 會直接
`SystemExit`（會大聲失敗、不會靜默跑錯，這點是好的），但整輪會白費。

**修正後的候選池**（能力異質，非 persona 異質）：
- `qwen/qwen3.6-35b-a3b`（現行基準，35b）
- `qwen/qwen3.8-27b`（27b，不同世代）
- `gemma-4-12b-it-qat`（12b 且 QAT 量化 ⇒ **先驗上最可能明顯較弱**，
  這是異質性最可能來自的地方）
- `text-embedding-*` 是 embedding model，不能當 worker。

⚠ 兩個還沒解決、下一輪必須先處理的事：
1. **ID 字串大小寫／分隔符不一致**：清單印的是 `qwen_qwen3.6-35b-a3b`（底線），
   但在跑的 run 用的是 `qwen/qwen3.6-35b-a3b`（斜線）且**確實跑得動** ⇒ 中轉
   應該有做正規化，但**不要假設**，下一輪開跑前要對每個候選 ID 各發一次
   preflight（`gain_run.py` 本來就會做）。
2. **「gemma-4-12b 比較弱」是判斷不是量測。** 照 §6 的規格，先量 per-model
   命中率 + 置換檢定證明池子真的異質，才跑正式三臂。
