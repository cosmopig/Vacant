# R440：人類指令——gemma-4-12b 單模型池 ＋ 文獻依據的困難題庫

（2026-09-01，Fable 5 依人類即時指令執行。本文件在 run 發射前寫定＝預註冊；
預測寫在前面，跑完不准改。）

## 人類指令原文（2026-09-01）

> 如果單獨使用 gemma-4-12b 作為單一模型呢？因為 35b 可能過度聰明，且 12b 的
> 工具能力那些也相對好，然後我懷疑你的題目過於簡單，我需要你去找公正的困難
> 題目及或是你自己去做但是必須基於各種文獻基礎。

兩個假說，各自都直指 R438 機制結論的邊界條款（「換 worker 池／換題庫可能翻盤」）：

- **H-A（天花板）**：qwen3.6-35b 太強 ⇒ OFF 失敗率只有 26.44% ⇒ 評審關卡沒有
  足夠的真失敗可攔 ⇒ 量到「無增益」可能是天花板效應，不是機制性質。
- **H-B（題目太簡單）**：MBPP+ 對現代模型過易，同理壓縮了可歸因修正的空間。

## 實驗條件（三個，依序執行，各自 gate）

| 條件 | worker 池 | 題庫 | 改動 | 目的 |
|---|---|---|---|---|
| **E1** | gemma-4-12b-it-qat 單模型 | MBPP+ 179 題（同決定性 run 的 bank/seed） | `--models gemma-4-12b-it-qat`，**零改碼** | 隔離 H-A：只動 worker 強度 |
| **E2** | 混合池（同決定性 run） | **LCB bank v1（91 題 medium+hard）** | `--bank lcb` | 隔離 H-B：只動題目難度 |
| **E3** | gemma-only | LCB bank v1 | 兩參數並用 | 人類的合成假說 |

E1 先跑（最便宜、與決定性 run 直接可比）。每條約 35h（E2/E3 較短：91 題）。
§7 紀律不變：8765 端點同時只跑一個 run。

## 題庫選型（文獻依據，逐一淘汰）

- **採用：LiveCodeBench** code_generation_lite（Jain et al. 2024, arXiv:2403.07974，
  ICLR 2025）。理由：比賽題附**發布日期戳**（污染可定界）、難度標籤由平台原生
  給定（不是我們自選）、隱藏測資齊全、純演算法題只需標準庫——與現行沙箱
  （checks.py，無網、無第三方件）完全相容。
- 淘汰 BigCodeBench（Zhuo et al. 2024, arXiv:2406.15877）：139 個第三方庫＋部分
  題有網路呼叫，沙箱要重做、infra_void 風險大。難度軸也不同（庫組合力），列為
  後續候選而非本輪。
- 淘汰 APPS（Hendrycks et al. 2021）與 CodeContests（Li et al., Science 2022）：
  題齡 4-5 年，幾乎確定在訓練集裡；污染無從定界。
- 基線保留 EvalPlus MBPP+（Liu et al., NeurIPS 2023）＝現行 bank，作為 E1 的
  對照軸。

**自製題（人類給的備選）暫不採**：`vacant/codebench.py` 的六坑型程序生成可以
擴成文獻依據的難題族（EvalPlus 變異測資分類、property-based 不變量），但
「公正性」不如平台原生難度標籤＋日期戳；若 LCB 三條件都撞到天花板/地板再啟用。

## LCB bank v1 規格（可重建、fail-closed）

- 來源：HF `livecodebench/code_generation_lite` `test5.jsonl`＋`test6.jsonl`
  （視窗 2024-08 → 2025-04，本 bank 內 contest_date 全數落在此區間）
- 過濾：functional（LeetCode、有 starter_code）× difficulty ∈ {medium, hard}；
  stdin 型（AtCoder，217 題）**排除**——需要改 worker prompt 慣例與執行模型，
  v1 誠實不做
- 轉換：`class Solution` 方法 → 頂層函式契約；public → visible、private → hidden
  （每題上限 24 筆）；任何一筆測資解析失敗＝整題丟（不產半殘題）
- 結果：**91 題（54 medium／37 hard）**，轉換零丟題；
  `ops/gain/data/lcb_bank_v1.jsonl`，sha256
  `eb2a58760818d54b0a0141aa37e1603f875c53ccc76a2d87a6bf044b39a6c659` 釘死於
  `LiveCodeBenchLoader`（EvalPlus 同款紀律：hash／題數／schema／去重全驗）
- 已驗：91/91 測資參數個數＝函式簽名參數個數；壞候選被 visible check 正確擋下；
  重建指令見 `ops/gain/build_lcb_bank.py` docstring

## 預註冊預測（跑完對答案）

- **P1**：E1 的 OFF 失敗率高於 26.44%（預期 35–60% 窗內）。若仍 <30%，
  H-A 的前提（12b 顯著更弱）不成立，直接記錄。
- **P2**：若 E1 評審票準確率仍 ≈ almost-PASS 基線（±2pp），則「評審不辨真偽」
  與 worker 強度無關 ⇒ ON 等預算仍不會贏 ⇒ R438 機制結論**加強**。
- **P3（翻盤窗）**：若 E1/E3 評審準確率顯著上升（更多真失敗＝更多可攔訊號）
  且 ON>OFF5 配對顯著，R438 結論的邊界條款兌現——增益存在於「弱 worker＋
  真失敗富集」機制帶。
- **P4**：E2 混合池在 LCB 上 OFF 失敗率預期 >50%；若 >70% 觸發地板保護
  （見中止準則）。

## 中止與地板/天花板準則

- infra_void 率 >20%（任一臂）：中止，先修 infra 再跑（R356 教訓）。
- OFF 失敗率 >70%：題庫對這個池太難，配對統計失去意義；照實記錄，
  考慮只取 medium 子集重跑。
- OFF 失敗率 <15%：天花板重現，該條件對假說無資訊量，照實記錄。

## 誠實邊界（先寫死，防止結果出來後被淡化）

1. **污染不可證偽**：worker 模型（qwen3.6、gemma-4）訓練截止未公開，2025-04 前
   的比賽題不能宣稱 zero-contamination。日期戳是**定界工具**不是免罪證明。
2. **平台偏斜**：排除 stdin 後全部是 LeetCode 題，風格單一。
3. **n=91 檢定力**：McNemar 在 91 配對下約可辨 12-15pp 級不對稱；比決定性 run
   的 179 題弱，是首輪探測不是終審。可擴 test4 視窗（+另一批 functional 題）。
4. **「12b 工具能力好」本 harness 測不到**：G 實驗 worker 是純 chat completion
   寫函式，無工具呼叫。此指令中的工具論點留給未來有工具面的實驗，本輪不宣稱。

## 給迭代圈（round441+）的執行序

```
# E1（先跑；與決定性 run 唯一差異＝--models）
python3 ops/gain/gain_run.py --out runs/g_r441_gemma_only_mbpp --n 179 \
  --seed g-r212-route-20260828 --models gemma-4-12b-it-qat \
  --decision DECISION_20260901_R440_HUMAN_DIRECTIVE_GEMMA_ONLY_AND_HARD_BENCH.md

# E2（E1 收完再上）
python3 ops/gain/gain_run.py --out runs/g_r442_mixed_lcb --n 91 \
  --seed g-r442-lcb --bank lcb \
  --decision DECISION_20260901_R440_HUMAN_DIRECTIVE_GEMMA_ONLY_AND_HARD_BENCH.md

# E3（E1/E2 皆有訊號才上）
python3 ops/gain/gain_run.py --out runs/g_r443_gemma_lcb --n 91 \
  --seed g-r442-lcb --bank lcb --models gemma-4-12b-it-qat \
  --decision DECISION_20260901_R440_HUMAN_DIRECTIVE_GEMMA_ONLY_AND_HARD_BENCH.md
```

r439 驗證 run 仍在端點上時**不得**發射（§7）。
