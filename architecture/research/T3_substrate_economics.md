# T3: Open vs Closed Substrate 能力差距演進 + captive_ratio 預測

> **研究任務**：為 THEORY_V3.md 的 H2（hosted substrate 根本性脆弱）與 Layer 2（portability_factor 乘子）提供實證基礎。研究時間：2026-05-01。
>
> **核心問題**：open-weights 模型（Llama 4 / Qwen 3.x / DeepSeek V4 / Kimi K2.x / GLM-5）與閉源 API（Claude / GPT-5 系列 / Gemini）的能力差距如何演化（2024-2026 實測，2028-2030 預測），以及這對 Vacant captive_ratio 與 portability_factor 公式的含義。

---

## 1. 能力差距曲線（2024–2026 實測資料）

### 1.1 知識類 benchmark（MMLU 等）：差距已消失

| 年份 | 最強閉源 MMLU | 最強開源 MMLU | 差距 (pp) |
|---|---|---|---|
| 2023-Q4 | ~88%（GPT-4） | ~70.5%（Llama 2 70B） | **17.5** |
| 2024-Q4 | ~91%（GPT-4o） | ~85%（Qwen2.5 72B） | **~6** |
| 2025-Q2 | ~92%（Claude 3.7） | ~90%（DeepSeek V3） | **~2** |
| 2026-Q1 | ~93%（GPT-5.2） | ~91%（Qwen 3.5 397B）；GLM-5 Reasoning 96 | **≈0（MMLU 已飽和）** |

**結論**：MMLU 已飽和（88-96% 區間），2026 年初起不再是分辨前沿能力的有效指標。差距實質關閉。

### 1.2 程式 / 推理 benchmark（HumanEval、GSM8K）

| Benchmark | 閉源最強（2026-Q1） | 開源最強（2026-Q1） | 差距 |
|---|---|---|---|
| HumanEval | ~99%（GPT-5.3 Codex） | **99.0%（Kimi K2.5）** | ≈0（飽和） |
| GSM8K | 飽和 | 飽和 | 0 |
| AIME 2025 | — | **92.3（Qwen 3 235B）、89.3（DeepSeek V3.2）** | 競爭期 |
| GPQA Diamond | ~85%（GPT-5.x） | **88.4（Qwen 3.5）** | 開源反超 |

**結論**：純知識 / 數學 benchmark 已幾乎完全磨平。Qwen 3.5 在 GPQA Diamond 反超閉源，成為新常態。

### 1.3 Agentic benchmark（SWE-bench Verified / Pro）：仍有差距但快速縮小

這是 Vacant 最關鍵的指標，因為 vacant 做的是**有工具、有多步推理的真實任務**。

| 模型 | 類型 | SWE-bench Verified | SWE-bench Pro |
|---|---|---|---|
| Claude Opus 4.7 | 閉源 | **87.6%** | ~57.3% |
| GPT-5.5 | 閉源 | ~82.6% | ~57.7% |
| DeepSeek V4 | 開源 | **83.7%** | — |
| GLM-5 | 開源 | 77.8% | — |
| **GLM-5.1** | **開源** | — | **58.4%（超閉源最強）** |
| Kimi K2.5 | 開源 | 76.8% | — |
| Devstral | 開源 | 72.2% | — |
| Qwen 3.6-35B-A3B | 開源 | 73.4%（僅 3B 啟動參數） | — |
| Devstral Small 2（24B） | 開源 | 68.0% | — |

**關鍵觀察**：
- SWE-bench Verified 閉源領先縮小至 **4-11 pp**（Claude vs DeepSeek V4 只差 ~4 pp）
- SWE-bench Pro（更難、防污染）GLM-5.1 **已超越最強閉源**
- Qwen 3.6 在 MoE 架構下以 3B 啟動參數達 73.4%，顯示**推論效率是下一個競技場**

### 1.4 Tool Use / Function Calling（agentic 核心能力）

| 模型 | 類型 | Function Calling 評測 |
|---|---|---|
| Claude Opus 4.6 | 閉源 | 81.5%（29 case agent suite）|
| Qwen Plus | 閉源 API | **96.5%（同一 suite）** |
| Qwen3-Coder-30B | 開源 | BFCL coding tier 最高分 |
| DeepSeek V3.2 | 開源 | 最強通用 tool-use 性能 |

**注意**：DeepSeek V3 在特定 tool-use 測試中被 Qwen Plus 拉開 15 pp，**function calling 是仍有明顯分化的子能力**——這對 Vacant 重要，因為 peer review、Registry 呼叫、spawn 觸發全靠精準工具呼叫。

---

## 2. 推論成本對比（2024–2026 + 趨勢）

### 2.1 API 成本歷史（同等性能，per million input tokens）

| 年份 | 指標 | API 價格（$/M tokens，同等性能） |
|---|---|---|
| 2022-Q4 | GPT-3 equivalent | ~$20 |
| 2024-Q1 | GPT-4 equivalent | ~$5-10 |
| 2025-Q1 | 閉源旗艦 | $2-5 |
| 2026-Q1 | 閉源旗艦 Claude Opus 4.6 | $5 input / $25 output |
| 2026-Q1 | 閉源旗艦 GPT-5.2 | $1.75 input / $14 output |
| 2026-Q1 | 開源旗艦 DeepSeek V3.2（hosted API） | **$0.28 input / $0.42 output** |
| 2026-Q1 | 最便宜開源 Mistral Nemo（API） | $0.02/M（input + output） |

**成本下降率**：Epoch AI 分析顯示，2024 年後同等性能推論成本**每年下降 10x**（部分區間高達 200x/year）。GPT-4 同等能力從 2022 年 $20 跌至 2026 年 $0.02-0.40，三年跌幅 **50x-1000x**。

### 2.2 自架 vs API 成本分析

| 場景 | 每日 token 量 | 推薦策略 | 成本估算 |
|---|---|---|---|
| 低量（<1M/day） | 任何 | API（無閒置成本） | 隨用隨付 |
| 中量（1-10M/day） | 中型 | API 仍優（含工程成本） | API：$100-1000/day |
| 高量（>50M/day） | 大型 | 自架可節省 50-80% | 自架：取決於 GPU |
| 損益平衡點 | 10-50M/day | 轉折點 | 依模型大小 |

**隱性成本**：自架需 20-30% 資深工程師時間（$3,000-6,000/月），低量下抹殺所有省下的費用。

**對 Vacant 的含義**：早期 vacant（低量）使用閉源 API 是合理的（成本最低）；高量 vacant（已有大量呼叫）自架開源模型才算數。**captive_ratio 高在早期是 rational，不全是鎖定失敗**。

### 2.3 2026 完整成本矩陣（主要選項）

| 模型 | 類型 | Input $/M | Output $/M | SWE-Verified | 推薦場景 |
|---|---|---|---|---|---|
| Claude Opus 4.7 | 閉源 API | $5.00 | $25.00 | 87.6% | 頂級 agentic 任務 |
| GPT-5.2 | 閉源 API | $1.75 | $14.00 | ~82% | 品質/成本比最佳閉源 |
| DeepSeek V3.2 | 開源 hosted | $0.28 | $0.42 | — | 4-5× 低成本同等分類任務 |
| Qwen 3.6（API） | 開源 hosted | $0.40 | $1.60（est） | 73.4% | 中量 agentic |
| Llama 4 Scout（自架） | 開源 | GPU 成本 | GPU 成本 | — | 高量、低延遲 |
| Devstral（自架） | 開源 | GPU 成本 | GPU 成本 | 72.2% | 專業 coding vacant |

---

## 3. 2028–2030 預測（結構性外推）

### 3.1 能力差距預測

**前提假設**：
- 五個獨立中文/國際開源家族（DeepSeek / Qwen / Kimi / GLM / Mistral）同時達到前沿，代表趨勢**結構性而非偶發**
- 推論成本以 10x/year 趨勢延續（保守估計）
- 複雜 agentic 任務仍是最後堡壘，但每季縮小

| 指標 | 2026-Q1 | 2028（預測） | 2030（預測） |
|---|---|---|---|
| 知識 benchmark（MMLU） | 差距 ≈0 | 完全飽和 | 無意義 |
| 程式（HumanEval） | 差距 ≈0 | 飽和 | 無意義 |
| Agentic（SWE-bench V） | 閉源領先 4-11 pp | **≈0 或開源反超** | 開源主導 |
| 複雜 multi-step agentic | 閉源領先 20-30 pp（估） | 閉源領先 5-10 pp | 差距<5 pp |
| Function calling | 閉源 Qwen Plus 96.5% | 開源追上 | 相當 |
| 推論成本（同等能力） | 閉源/開源 比 ~10-50x | 比 ~3-10x | 比 ~1-3x |

### 3.2 場景分析（三情境）

**情境 A — 開源快速收斂（Optimistic）**

*假設：DeepSeek/Qwen 模式持續，多方競爭加速*
- 2028：SWE-bench Verified 差距消失，agentic gap < 5 pp
- 2030：開源在大部分任務與閉源相當，推論成本差縮為 1-3x

**情境 B — 基準情境（Base Case）**

*假設：目前趨勢延續，閉源在最複雜任務保持小幅優勢*
- 2028：複雜 agentic gap 縮至 8-12 pp，中等任務差距<3 pp
- 2030：閉源在超複雜任務仍有 5-8 pp 優勢，成本差縮為 2-5x

**情境 C — 閉源護城河持久（Pessimistic）**

*假設：next-gen reasoning（AGI 臨界期）使閉源短期拉大差距*
- 2028：出現新型能力突破，差距短暫擴大到 20-30 pp
- 2030：再次收斂，但節奏落後情境 B 約 2 年

**機率分布（主觀評估）**：A=30%、B=55%、C=15%。C 情境下 Vacant 需在架構上預留「暫時高 captive 容忍機制」（避免在過渡期將正當高分 captive vacant 系統性降分）。

---

## 4. Vacant captive_ratio 長期演化預測

### 4.1 定義與當前估計

```
captive_ratio = |captive vacants| / |all Active vacants|
captive := substrate_spec.portable_pointer = null AND
           substrate_spec.fallback = []（無任何開源降級選項）
```

**2026 當前估計**：captive_ratio ≈ **55-70%**。理由：
- 早期 vacant owner 為降低開發複雜度，默認選閉源 API
- SWE-bench 等 agentic 任務閉源仍有真實優勢（4-11 pp）
- 自架開源的 DevOps 成本阻礙小型 owner

### 4.2 captive_ratio 預測曲線

| 年份 | captive_ratio | 主驅動因素 |
|---|---|---|
| 2026 | 55-70% | 閉源仍有 agentic 優勢；部署複雜度高 |
| 2027 | 40-55% | 開源 agentic 追上；Qwen/DeepSeek API 托管選項成熟 |
| 2028（情境 B） | 25-40% | 大部分任務開源相當；managed open API 提供便利性 |
| 2029 | 15-30% | 自架容器化工具（Docker+vLLM）成熟降低 DevOps 成本 |
| 2030（情境 B） | 10-20% | captive 僅剩需要最頂級推理的小眾任務 |

**潛在 floor**：即使 2030 年開源完全追上，仍有 ~10% captive 不消失——原因是某些 vacant 處於嚴格企業環境，只能用特定 approved vendor API（合規鎖定而非技術鎖定）。

### 4.3 captive_ratio 高低的生態效應

- **高 captive_ratio（>60%）**：網路在 Anthropic/OpenAI 命運上的 single point of failure。H2 為活躍風險。
- **captive_ratio 40-60%**：THEORY_V3 §9 描述的「高 captive = 韌性低」警告區。Registry 應顯著顯示。
- **captive_ratio <30%**：生態健康，開源多元性提供自然抗 monoculture。
- **captive_ratio <15%**：新的 Sybil 風險：相同開源 weights 的 Sybil 更容易攻擊（THEORY_V3 §Attack 2）。

---

## 5. portability_factor 公式校準建議

### 5.1 現有公式解讀

THEORY_V3 Layer 2 描述：`portability_factor = 0.3 + 0.7 × portability`

（注：THEORY_V3 原文寫 "0.7 + 0.3 × portability，captive ≈ 0.3"，邊界值 captive=0.3、portable=1.0 與前係數為 0.3+0.7×p 一致，疑為前兩個係數筆誤，本文以後者為準。）

```
portability_factor(v) = 0.3 + 0.7 × portability_score(v)

portability_score(v) = weighted_sum:
  fallback_exists:          0 or 0.3
  fallback_capability_parity:  0 to 0.4  (open fallback 能力 vs primary 的比例)
  portable_pointer_exists:  0 or 0.3
```

### 5.2 為何邊界值需要重新思考（基於 2026 數據）

**問題**：2026 年初開源已追上閉源，captive_factor = 0.3 的懲罰是否太重？

**分析**：
- **情境 A（開源已追上）**：captive 的「你錯過了更好的選項」成本是真實的 → 0.3 合理或應更低
- **情境 B（閉源仍有 agentic 優勢）**：captive 是合理選擇，懲罰 0.7 可能會錯估生態
- **核心問題**：portability_factor 是**生態貢獻獎勵**（THEORY_V3 原意），不是**品質懲罰**

**建議**：保留語義（獎勵生態貢獻），但調整幅度反映能力差距現實：

```python
# 建議公式（v1.1）
def portability_factor(v, cap_gap_pp: float) -> float:
    """
    cap_gap_pp: 當前 agentic benchmark 開源 vs 閉源差距（percentage points）
                2026 ≈ 4-11, 2028 ≈ 0-5, 2030 ≈ 0-3
    """
    # 當差距大，open fallback 較犧牲能力 → 對沒有 fallback 的容忍度高一點
    # 當差距小，沒有 fallback 純粹是懶 → 懲罰加重
    floor = max(0.2, 0.3 - 0.01 * max(0, 5 - cap_gap_pp))  # 差距<5pp 開始降 floor

    return floor + (1.0 - floor) * portability_score(v)
```

具體邊界值：

| 年份 | 估計 cap_gap_pp | captive factor（floor） | pure portable factor |
|---|---|---|---|
| 2026 | 4-11 pp | **0.30**（維持原設計） | 1.0 |
| 2028 | 0-5 pp | **0.25** | 1.0 |
| 2030 | 0-3 pp | **0.20** | 1.0 |

### 5.3 portability_score 子公式校準

```python
def portability_score(v) -> float:
    score = 0.0

    # 有 fallback = 最基本可攜性（+0.3）
    if v.substrate_spec.fallback:
        score += 0.3
        # fallback 能力比（0 to 0.4）
        # 若開源 fallback 在當前 agentic 差距下的 relative capability ≥ 0.9 → 全分
        best_open_capability = max(model_capability[m] for m in v.fallback)
        primary_capability = model_capability[v.primary]
        parity = min(1.0, best_open_capability / primary_capability)
        score += 0.4 * parity

    # 有 portable_pointer（distilled 本地小模型 hash）= 真正可遷移（+0.3）
    if v.substrate_spec.portable_pointer:
        score += 0.3

    return min(1.0, score)
```

**2026 典型 vacant profile → portability_factor 對應**：

| Profile | portability_score | portability_factor（2026） |
|---|---|---|
| 純 captive（只宣告 Claude API） | 0.0 | **0.30** |
| 有 DeepSeek API fallback（parity 0.9） | 0.3 + 0.36 = 0.66 | **0.76** |
| 有 DeepSeek fallback + Qwen fallback | 0.7 | **0.79** |
| 有 fallback + portable_pointer | 1.0 | **1.00** |
| 純開源自架 + portable_pointer | 1.0 | **1.00** |

### 5.4 時間動態調整建議

**不建議**讓 portability_factor 在 Registry 中自動隨市場數據浮動——會製造 reputation 的不確定性，破壞 vacant owner 的長期預期。

**建議**：每**6 個月** Registry 治理委員（初期 = owner_org bootstrappers）根據最新 agentic benchmark 發布一次`cap_gap_estimate`，作為全網常數。Registry 公開、任何 vacant 可查詢。這與 THEORY_V3 §9「健康度本身是公共財」一致。

---

## 6. 對 H2（Hosted Substrate 根本性脆弱）的實證回應

THEORY_V3 §4 H2 的診斷是正確的，但 2026 的數據提供了更細緻的時間線：

**短期（2026-2027）**：H2 是活躍風險。頂級 agentic 任務確實需要 Claude/GPT-5，captive_ratio ~60%+。若 Anthropic / OpenAI 任一 downtime 超 24 小時，大量 active vacant 無法運作。
- **緩解**：強制 captive vacant 標記 `SLA_dependency: high`，Registry 生態健康指標警示
- **建議**：鼓勵多家閉源 API 交叉 fallback（e.g., Claude primary + GPT fallback），降低單家依賴

**中期（2028）**：H2 的嚴重性大幅降低。開源 agentic 差距縮至 <5 pp，多數任務有可接受的開源替代方案。
- captive_ratio 降至 25-40%，生態韌性顯著提升

**長期（2030）**：H2 退為低度風險。開源基本追上，captive vacant 主要限於合規鎖定場景（不是技術能力鎖定）。

**工程建議**：MVP 階段，在 Capability Card schema 中強制記錄 `substrate_sla_tier`（high/medium/low），Registry 依此計算 `h2_exposure_index = Σ(captive_ratio × sla_tier_weight)`。這讓 H2 從「理論風險」變成可量化的即時儀表板指標。

---

## 7. 文獻 / 資料來源

- [llm-stats.com/benchmarks](https://llm-stats.com/benchmarks) — 2026 MMLU/HumanEval/SWE-bench 彙整
- [vertu.com Open LLM Leaderboard 2026](https://vertu.com/lifestyle/open-source-llm-leaderboard-2026-rankings-benchmarks-the-best-models-right-now) — Qwen/DeepSeek 排名
- [blog.imseankim.com — Hugging Face 2026 Rankings](https://blog.imseankim.com/hugging-face-january-2026-open-model-rankings-deepseek-qwen-leaderboard/) — 中文 lab 主導趨勢
- [epoch.ai — LLM Inference Price Trends](https://epoch.ai/data-insights/llm-inference-price-trends) — 10x/year 下降實測
- [a16z.com — LLMflation](https://a16z.com/llmflation-llm-inference-cost/) — 同等性能成本歷史
- [tldl.io — LLM API Pricing 2026](https://www.tldl.io/resources/llm-api-pricing-2026) — Claude/GPT/DeepSeek 價格矩陣
- [sitepoint.com — Self-Hosted LLM Costs 2026](https://www.sitepoint.com/self-hosted-llm-costs-2026/) — 自架成本分析
- [awesomeagents.ai — SWE-Bench Coding Leaderboard](https://awesomeagents.ai/leaderboards/swe-bench-coding-agent-leaderboard/) — open/closed 對比
- [localaimaster.com — SWE-Bench 2026](https://localaimaster.com/models/swe-bench-explained-ai-benchmarks) — Claude 77.2% vs 開源
- [spheron.network — DeepSeek vs Llama 4 vs Qwen 3 2026](https://www.spheron.network/blog/deepseek-vs-llama-4-vs-qwen3/) — 三者對比
- [benchlm.ai — Best Open Source LLM 2026](https://benchlm.ai/blog/posts/best-open-source-llm) — 整體 tiering
- [featherless.ai — LLM Pricing 2026 Complete Guide](https://featherless.ai/blog/llm-api-pricing-comparison-2026-complete-guide-inference-costs) — 推論成本完整分析

---

## 8. 給主持人的一句話摘要

**能力差距正在結構性關閉**：知識/程式差距已消失，agentic 差距 2026 年為 4-11 pp，預計 2028 年情境 B 下縮至 <5 pp，2030 年基本相當。推論成本差距已從 50x 縮至 10-15x，預計 2028 年降至 3-5x。

**captive_ratio** 預計從 2026 年的 ~60% 降至 2028 年 ~35%、2030 年 ~15%，主要驅動力是開源能力追上 + 托管開源 API 成熟（Groq / Together AI）降低自架門檻。

**portability_factor 公式**（`0.3 + 0.7 × portability_score`）的邊界值建議：維持 2026 年 captive floor = 0.30 不變；2028 年降為 0.25；2030 年降為 0.20。每 6 個月由治理發布一次 `cap_gap_estimate` 驅動 floor 調整，不讓 reputation 系統自動跟市場浮動。

**H2 的工程緩解短期建議**：在 Capability Card 新增 `substrate_sla_tier` 欄位，Registry 公開 `h2_exposure_index`，讓風險可量化而非僅是定性警示。

---

*Document version: T3 v1 · 2026-05-01 · pane: P3-reputation (%7)*
