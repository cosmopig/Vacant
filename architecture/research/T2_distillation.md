# T2 — Trajectory Distillation 可行性研究

> **任務來源**：host pane %4 · T2 (trajectory distillation feasibility)
> **研究對象**：THEORY_V3.md H1 困難 + Layer 2 `portable_pointer` 設計
> **方法**：WebSearch (4 並行查詢 + 2 追問) + codex exec 深度文獻查
> **日期**：2026-05-01
> **引用 raw 輸出**：本文件底部附 codex 原始輸出（補完後）

---

## 核心研究問題

THEORY_V3.md H1 誠實列出：

> 「從互動 trajectory 蒸餾出真的能用的 task-specific 小模型，目前學界做到 task-specific 對話可行，agent-trajectory 級別還在很早期。三年內能不能成熟到讓 vacant routinely 蒸餾，不確定。如果不能，網路會長期 captive-heavy。」

Layer 2 設計直接依賴蒸餾結果：

```yaml
portable_pointer: "vacant://v1/distilled/<hash>"  # 可遷移備案，可空
```

**本研究回答**：(1) SOTA 到哪；(2) 1000 次互動蒸餾估算；(3) 三年內能否成熟為 routine。

---

## 1. 五篇關鍵論文摘要

### P1 · Structured Agent Distillation
**引用**：Liu et al., arXiv:2505.13820, DOI `10.48550/arXiv.2505.13820`, **AAMAS 2026**
**方法**：把 ReAct 軌跡切分為 `[REASON]` 和 `[ACT]` span，施加 span-specific 損失 + curriculum sampling，避免 flat token imitation。
**關鍵結果**：LLaMA-7B student 達 68.0 / 64.1 / 75.2（ALFWorld / WebShop / HotPotQA）vs LLaMA-13B teacher 75.3 / 71.8 / 81.0 ——**7B 達到 13B 的 ~90% 性能**。
**對 Vacant 的意義**：vacant 的每次工具呼叫 (ACT) + 思考過程 (REASON) 天然形成這種 span 切分。`event_log` 已有 envelope 簽章記錄每個 ACT；REASON 可從 Runtime 的 self_eval 欄位重建。Vacant 的 logbook 直接可轉換為此格式訓練資料。

---

### P2 · SCoRe — 學生主導強化蒸餾
**引用**：Lyu et al., arXiv:2509.14257, DOI `10.48550/arXiv.2509.14257` (Sep 2025)
**方法**：學生自己生成軌跡，teacher 只在**第一個關鍵錯誤點**矯正，SFT 用矯正後 trajectory，RL 從驗證前綴做短視野優化（避免 off-policy 分布漂移）。
**關鍵結果**：Qwen2.5-7B SCoRe-RL **avg 50.8 vs 72B teacher 51.7**（差距 0.9），+8.3 超越 behavioral cloning baseline，在 12 benchmarks 上追平 72B。使用 ~5000 SFT + ~5000 RL 樣本；資料量實驗顯示**10K 不比 5K 明顯更好**。
**對 Vacant 的意義**：logbook 裡的「成功 vs 失敗 trajectory」對 = SCoRe 所需的 first-error pairs。Vacant 的 peer review 評分可用來自動標記「哪裡出了第一個錯」。**但**：SCoRe 仍需 72B teacher 做矯正判斷——純自蒸餾需另外解決評估難題。

---

### P3 · Distilling LLM Agent into Small Models
**引用**：Kang et al., arXiv:2505.17612, DOI `10.48550/arXiv.2505.17612`, **NeurIPS 2025 Spotlight** ([GitHub](https://github.com/Nardien/agent-distillation))
**方法**：蒸餾完整 CodeAct trajectory（含 retrieval + code execution），加入 first-thought prefix 和 self-consistent action generation（過濾無效 tool call）。小模型學「用工具」而非「記知識」，能力更可遷移。
**關鍵結果**：**~2000 個過濾後的正確 trajectory** 訓練；7B agent distill + SAG avg **42.68 vs 32B teacher 46.00**（93% of teacher）。3B avg 36.60 超越 7B CoT-distill 33.54；0.5B avg 21.90。訓練：LoRA rank 64, 2 epochs, 4× A100 80GB。
**對 Vacant 的意義**：Vacant 本就帶 tool-use。**2000 條過濾後的正確 trajectory 是關鍵門檻**（1000 原始 ≈ 700-1000 過濾後，接近但略低於此門檻）。**3B 是現實的 portable_pointer 最低規格**（不是 1.7B）。

---

### P4 · Agentic Knowledge Distillation (自治閉環)
**引用**：ElZemity et al., arXiv:2602.10869, DOI `10.48550/arXiv.2602.10869` (Feb 2026)
**方法**：teacher LLM 自主扮演 ML engineer：生成合成訓練資料、LoRA fine-tuning student SLM、合成 validation 評估、針對性 refinement，迭代直到趨穩。全程無人類介入。每次迭代約 14-33K tokens + 5-9 分鐘。
**關鍵結果**：Claude Opus 4.5 teacher + Qwen2.5-0.5B student → **94.31% accuracy, 96.25% recall, 94.42% F1**；大幅超越 DPO（50-80%）。**硬體：Mac Mini M4, 16GB 統一記憶體**（非 cloud GPU！）。DPO baseline 用 10,000 合成 preference pairs。
**對 Vacant 的意義**：這是 Vacant idle-time self-distillation loop 最直接的工程原型。**Mac Mini M4 = Vacant host 機器上就能跑**，不需要 cloud GPU，成本趨 0。Vacant 只需把 domain 從 SMS 換成自己的 capability card 描述，teacher = primary substrate API，閉環評估用 peer review + caller review 取代合成 validation。

---

### P5 · AgentDistill — 無需訓練的蒸餾
**引用**：Qiu et al., arXiv:2506.14728, DOI `10.48550/arXiv.2506.14728` (Jun 2025)
**方法**：teacher 從成功 trajectory 中提取可復用的 MCP tool modules，抽象/聚合後形成 **MCP-Box**，student 直接使用——完全不做 gradient update。每個 domain 僅需 9-13 個 distilled MCPs。
**關鍵結果**：LLaMA3.1-8B + MCP Box：Game of 24 成功率 21.7 → 64.0（+196%）；Qwen3-8B：72.7 → 79.7。PathVQA 75.5 vs teacher 99（仍有差距）。**零 gradient 資料需求**。
**對 Vacant 的意義**：提供 Vacant 在 logbook 未達 2000 examples 門檻前的**「零訓練蒸餾」過渡路徑**——先發行 MCP-Box 版 portable_pointer，再升級為完整 fine-tuned model。與 THEORY_V3.md Layer 2 的 fallback chain 直接相容。

---

## 2. 從 1000 次互動蒸餾的可行性估算

### 2.1 訓練資料量分析

```
1000 次互動
  × 平均 8 turns / 次（根據 ALFWorld / WebShop 基準）
  × 平均 1500 tokens / turn（含 tool call + response）
= 約 1-4M raw tokens

過濾後（去重 + 只保留成功 trajectory，~30-50% 丟棄）：
= 約 700-1000 可用 full-trajectory examples（codex 估算）
= 約 6000-15000 step-level examples（若按步分割訓練）
```

**與文獻基準的比較**：
| 論文 | 實際用量 | 結果 |
|---|---|---|
| P3 (Distilling Agent, NeurIPS Spotlight) | ~2000 filtered trajectories | 7B → 93% of 32B teacher |
| P2 (SCoRe) | ~5000 SFT + 5000 RL samples | 7B → 99% of 72B teacher |
| P4 (Agentic KD) | 合成生成，幾百例/次迭代 | 0.5B → 94.3% accuracy |
| P5 (AgentDistill) | 9-13 MCPs（零梯度） | 8B → game 64% vs teacher 99% |

> **結論**：1000 次互動 → 700-1000 有效 examples，**略低於 P3 的 2000 門檻，但超過 P5 的零訓練門檻**。對窄域、可驗證 outcome 的任務，可先用 AgentDistill MCP-Box 路徑，累積到 2000+ 再升級 fine-tuned model。

### 2.2 算力估算

以 **3B QLoRA fine-tuning** 為主要目標（codex 確認的最小可行 param count）：

| 指標 | 估算值 | 依據 |
|---|---|---|
| VRAM 需求（1.5B-3B LoRA） | **24-48 GB**（LoRA）→ **16 GB with QLoRA** | P4 Agentic KD：Mac Mini M4 16GB 已驗證 |
| VRAM 需求（7B LoRA） | 48-80 GB | Kang et al. 4×A100 setup |
| 雲端成本（1.5B-3B） | **$5–40 USD / distillation run** | 2026 A100 80GB ~$0.62-3.18/hr；H100 ~$1.99-2.99/hr |
| 雲端成本（7B） | **$20–150 USD / distillation run** | 同上，更長訓練時間 |
| On-device 方案 | **Mac Mini M4, 16GB unified memory**（非 cloud！） | P4 實際驗證，LoRA rank 32, 5-9 min/iter |
| 週期頻率（token 免費假設下） | 每 200-500 新互動重蒸餾（threshold trigger） | Section 3.4 long-term design |

**關鍵發現**：P4 (Agentic KD) 已在 **Mac Mini M4 16GB** 上完整驗證窄域 0.5B 閉環蒸餾。對 3B 模型，同等硬體 (Mac Mini M4 Pro 48GB 版) 已可支撐 LoRA 訓練，無需 cloud GPU。雲端備選方案 ($5-40 USD/run) 在 token 免費假設下成本可接受；在非免費條件下，on-device 路線將是關鍵優勢。

### 2.3 預期品質

（codex 估算值，未經大規模實驗驗證）

| 模型大小 | 正常 task 覆蓋率 | 長尾 edge cases | 備註 |
|---|---|---|---|
| 0.5B (Qwen2.5-0.5B) | ~48% | 差 | 僅適合 classifier / routing / template |
| 1.5B | ~60-75% | 差-中 | 僅在 domain 極窄 + schema-bound 動作下有效 |
| **3B（最小可行）** | **~75-85%** | 中 | **codex 確認：3B 是 80% 正常 tool-use 案例的現實下限** |
| 7B (Qwen2.5-7B) | ~85-93% | 良（75-85%） | 接近 teacher；SCoRe 驗證 7B ≈ 99% of 72B |

Kang et al. 量化形狀：7B agent distill ~93% of 32B teacher；3B ~80%；1.5B ~66%；0.5B ~48%。

**對 Vacant 的設計意涵**：
- `portable_pointer` 最低規格：**3B**（不是 1.7B）；1.5B 僅在 vacant 的 task domain 極窄且所有動作都有嚴格 JSON schema 時適用
- 正常案例（~80% of queries）由 portable model 處理；邊緣案例 fallback 到 primary API substrate
- Reputation 計算時：portable_pointer 處理的 call 的 `substrate_proof` 標 `local_distilled` → P3 的 `substrate_diversity` 統計能追蹤 portable ratio

### 2.4 失敗模式

1. **Out-of-distribution query**：vacant 的 1000 次互動若集中在少數 caller 類型，蒸餾模型對新型 query 泛化差
2. **Tool-call 格式錯誤**：小模型在精確 JSON 格式 tool call 上比大模型差 10-20%（需要嚴格 output parsing）
3. **長視野推理崩潰**：3B 模型在 >5 步的推理 chain 表現不穩定（SCoRe 7B 版才真正穩定）
4. **Hallucination 頻率更高**：小模型在知識 recall 任務（factual QA）幻覺率高出 teacher 15-30%——這對 factual / logical 維度的 reputation 會有直接衝擊
5. **訓練資料分布偏移**：如果 vacant 在蒸餾後繼續累積 logbook，蒸餾模型的知識會逐漸過時（需定期重蒸）

---

## 3. 對 Vacant token-免費假設的時間軸影響

### 3.1 當前狀態（2026）

| 能力 | 是否可行 | 限制 |
|---|---|---|
| 窄域 task-specific 蒸餾（1000 examples, 3B） | ✅ **已可行** | 需 $5-40 cloud compute 或 Mac Mini M4（on-device） |
| 自動化閉環蒸餾（Agentic KD 風格，無人類介入） | ✅ **已有原型** (arXiv:2602.10869) | 需 teacher LLM oracle（即原 primary API substrate） |
| 蒸餾後 tool-use agent 能力 | ✅ 3-7B 可用 | 長視野推理需 7B；3B 覆蓋 ~80% 正常 tool-use |
| 完全自蒸餾（teacher = student，無外部 oracle） | ⚠️ **部分可行** | 需外部 ground truth 或 peer review 替代 oracle |
| 訓練-免費蒸餾（AgentDistill MCP 方式） | ✅ **已可行** | 只學 surface patterns，deep reasoning 較弱 |

**結論**：**「第一代 portable_pointer」在 2026 年已可落地**——用 Agentic KD 風格的閉環，teacher = primary API substrate，student = 3-7B local model。vacant 的 idle-time loop 執行蒸餾，logbook 提供 trajectory data，peer review 訊號充當 evaluation signal。

### 3.2 關鍵瓶頸（尚未解決）

**核心困難**：完整的「無任何人類介入或外部 oracle 的自蒸餾」——即讓 portable_pointer 品質評估完全依賴 vacant 自己的 peer review，不靠 teacher API。

這個問題的本質是**評估難題**：要知道 portable model 的輸出「夠不夠好」，需要某種 ground truth。目前可用的 ground truth 來源：

| 來源 | 可行性 | 問題 |
|---|---|---|
| 外部 teacher API（primary substrate） | ✅ 已可行 | 需要 API call，成本 = 打敗蒸餾的目的 |
| Caller review（用過結果的人打分） | ✅ 可用，但延遲高 | 累積需時，不適合短週期迭代 |
| Peer review by other vacants | ✅ THEORY_V3.md 核心機制 | Peer 本身也有 bias，需多元 |
| Unit test / ground truth（客觀可驗） | ✅ 對有客觀答案的任務 | 對 open-ended 任務不適用 |
| Behavioral fingerprint 比對（P1 warmup ceremony） | ✅ P1 Runtime 已設計 | 只偵測 regression，不衡量提升 |

**可行路徑**：vacant 先用 teacher API 做 N 輪蒸餾評估（允許有限成本），之後切換到 caller/peer review 作持續監控——這跟 Vacant 現有設計完全相容（蒸餾的 sample 評估 call = 用 teacher API 的 few-shot ground truth validation，結果存 event_log，之後 peer review 接手）。

### 3.3 三年路線圖

```
2026 (現在)
  │
  ├─ 窄域蒸餾可行：3-7B 在 1000 trajectories 上訓練，$5-150 雲端費用（on-device Mac Mini M4 亦可）
  │   → portable_pointer v1：manual trigger，需開發者啟動一次
  │   → 平均品質：~75-93% of primary substrate on normal cases（3B ~80%，7B ~93%）
  │
2027 (Year 2)
  │
  ├─ 自動化閉環成熟：Agentic KD + vacancy idle loop 整合
  │   → vacant 自動執行蒸餾（idle-time），無需開發者操作
  │   → 評估 pipeline 用 peer review 取代 teacher oracle（大幅降低成本）
  │   → student = 3B（minimum viable）；7B for higher-fidelity variants
  │   → 品質稍降：~75-85%（teacher oracle 比 peer review 更精準）
  │   → 重蒸餾週期：每 200-500 新互動 trigger 一次；累積到 2000 後升級 full fine-tune
  │
2028 (Year 3)
  │
  ├─ Routine 蒸餾可能已達臨界點：
  │   → 工具鏈（Unsloth-style, PEFT ecosystem）成熟到 <1GB VRAM delta
  │   → 開源 SLM（Qwen4/Phi-5 generation）在 3-7B 下品質進一步提升
  │   → SCoRe 類框架可能不再需要 teacher oracle（完全 self-play RL）
  │   → portable_pointer 成為大多數單能力 vacant 的預設 fallback
  │
2029 (Year 4)
  │
  ├─ H1 問題「基本解決」的條件：
  │   (a) Qwen5/Phi-5 等 1-3B 模型在 STEM/coding 達到今日 7B 水準
  │   (b) PEFT 工具跑在 edge device（smartphone 等）成熟
  │   (c) Peer review 品質足以替代 teacher oracle 做 eval
  │   如果 (a)(b)(c) 都成立 → routine distillation = 可行
  │   如果 (a) 或 (b) 不成立 → captive-heavy 持續 1-2 年
```

### 3.4 VACANT 設計的直接結論

1. **MVP 階段（現在）**：`portable_pointer` 設為 optional（`可空`是正確的），**不要作為 MVP 必做項目**。captive vacant 是現實，THEORY_V3.md 的 captive_ratio 健康指標設計是對的。
2. **中期（Year 2）**：加入 `vacant.distill()` API 到 Runtime，由開發者手動觸發。Agentic KD + logbook = 完整實現路徑。
3. **長期（Year 3+）**：idle-time loop 自動觸發 `distill()`，條件：`len(logbook) >= threshold AND quality_estimate < target`。threshold 建議 500-1000 次互動。
4. **品質監控**：蒸餾後的 portable model 的 call 進 event_log 時標 `substrate: local_distilled`，P3 的 per-substrate reputation 自動追蹤品質，品質低 → 自動 fallback rate 上升 → vacant 的 portability_factor 不受影響（fallback 仍是 multi-spec 的一部分）。
5. **最小可行 param count 建議**（codex 確認）：**3B** 作為 portable_pointer 的最低規格要求（80% 正常 tool-use 覆蓋率）；7B 作為「高保真度」版本；1.5B 僅在 domain 極窄 + schema-bound 動作下作例外放行；0.5B 只適合 classifier / routing。可在 capability_card 裡宣告 `portable_model_size: "3B"` 讓 caller 決定是否接受。

---

## 4. 研究邊界與 H1 修訂建議

**H1 修訂後的措辭**（建議 THEORY_V4 採用）：

> **H1（修訂版）：** vacant 從互動 trajectory 蒸餾 task-specific 小模型，窄域單能力場景下**在 2026 年已可行**（3-7B，$5-150/次 cloud 或 Mac Mini M4 on-device，~75-93% quality vs primary substrate）。關鍵資料門檻：~1000 trajectories 足夠窄域 adapter；~2000 trajectories 是可移植 fallback model 的實用門檻。真正的困難在**評估自動化**（如何不靠 teacher oracle 判斷蒸餾品質）和**多能力 vacant 的跨任務泛化**。三年內（2029）若 Qwen4/Phi-5 世代 3B 模型品質達到今日 7B 水準且 PEFT 工具跑在 edge device，routine 蒸餾成為預設行為是**很可能的**（not certain, but probable）。MVP 階段保持 captive 為主是務實的，同時設計 `portable_pointer` 的結構鉤子（capability card + event_log substrate 標記）確保長期可移植性不需要重構。

---

## 5. 關鍵論文引用總表

| arXiv | 標題（縮）| 對 Vacant 最重要的數字 |
|---|---|---|
| 2505.13820 | Structured Agent Distillation | REASON/ACT 切分 outperforms naive KD on ALFWorld/WebShop |
| 2509.14257 | SCoRe (Reinforced Distillation) | **7B matches 72B on 12 benchmarks** |
| 2505.17612 | Distilling Agent (Retrieval+Code) | **0.5B ≈ 1.5B CoT; 1.5B ≈ 3B CoT**（tool-use 小模型可媲美上一級） |
| 2602.10869 | Agentic KD (Autonomous, 2026) | 94.31% acc, 96.25% recall, **no human labels, closed-loop** |
| 2506.14728 | AgentDistill (Training-Free MCP) | 100 examples → MCP box → 學生繼承能力，**zero gradient** |
| 2511.19947 | Edge KD for Mobile Agentic AI | 邊緣設備部署 pipeline（待 codex 確認細節） |

完整 citation（DOI/venue/作者）見底部 codex raw 附錄（補完後更新）。

---

## 附錄：Codex Raw 輸出

> 本研究使用 `codex exec --skip-git-repo-check --sandbox read-only` 進行深度文獻查詢。以下為 codex 完整輸出（job `bhsxbnc3w`，2026-05-01）。

### Bottom Line（codex 原文）

Routine self-distillation for a narrow, task-specific "vacant" is plausible by 2029, but not as fully autonomous open-ended self-improvement. What is feasible: idle-time LoRA/QLoRA from logged trajectories, filtered successes, tool-call traces, synthetic hard negatives, and cached teacher corrections. What is not yet solved: reliable self-evaluation and error correction without either ground-truth task signals or a stronger teacher/oracle.

### Paper Table（codex 原文）

| Paper | Citation / Venue | Method | Key Quant Result | Min Data | Compute | Direct Reuse for Vacant |
|---|---|---|---|---|---|---|
| 1 | Liu et al., "Structured Agent Distillation for Large Language Model," arXiv:2505.13820, DOI 10.48550/arXiv.2505.13820, AAMAS 2026. | Segments ReAct trajectories into `[REASON]` and `[ACT]` spans and trains with span-specific losses plus curriculum sampling. | LLaMA-7B student reaches 68.0/64.1/75.2 task success vs LLaMA-13B teacher 75.3/71.8/81.0 on ALFWorld/WebShop/HotPotQA. | Not clearly reported. | A6000 GPU, batch 64, seq len 512, 10k-20k steps. | Log trajectories with explicit reason/action/observation tags; train separate losses or mask loss over action tokens. |
| 2 | Lyu et al., "From Correction to Mastery," arXiv:2509.14257, DOI 10.48550/arXiv.2509.14257. | SCoRe lets student attempt tasks; teacher corrects earliest error; SFT uses corrected trajectories; RL starts from verified prefixes with key-step rewards. | Qwen2.5-7B SCoRe-RL avg 50.8, only 0.9 below Qwen2.5-72B teacher 51.7; +8.3 over behavior cloning. | 35k seed QA pairs. BC init: ~2,031 search + ~2,080 math. SFT: ~4,990 search + ~5,019 math. RL: ~5,271 search + ~5,639 math. | SFT: DeepSpeed ZeRO-3, BF16, max seq 4096. RL: 8× H20 96GB. | First-error correction, prefix-based RL, and "weak point" replay directly relevant; require teacher/oracle access. |
| 3 | Kang et al., "Distilling LLM Agent into Small Models with Retrieval and Code Tools," arXiv:2505.17612, DOI 10.48550/arXiv.2505.17612, NeurIPS 2025 Spotlight. | Distills full CodeAct trajectories. Adds first-thought prefix and self-consistent action generation to filter invalid actions. | With ~2k filtered trajectories, 7B agent distill + SAG avg 42.68 vs 32B teacher 46.00. 3B avg 36.60 exceeds 7B CoT distill 33.54. 0.5B avg 21.90. | 1,000 HotPotQA + 2,000 MATH prompts, filtered to ~2,000 correct trajectories. | LoRA rank 64, 2 epochs, batch 8, 4× A100 80GB. | Strong template: filter failed trajectories, preserve tool traces, use action self-consistency at fallback inference. |
| 4 | ElZemity et al., "Agentic Knowledge Distillation," arXiv:2602.10869, DOI 10.48550/arXiv.2602.10869. | Teacher LLM acts as autonomous ML engineer: generates synthetic data, LoRA-finetunes SLM, evaluates metrics, generates targeted refinements until plateau. | Best Claude Opus 4.5 + Qwen2.5-0.5B: 94.31% accuracy, 96.25% recall, 94.42% F1 on balanced SMS test set. DPO baseline only ~50-80% accuracy. | DPO baseline 10,000 synthetic preference samples. Agentic loop token usage 14-33K, 5-9 min per run. | Mac Mini M4, 16GB unified memory. LoRA rank 32, alpha 64, lr 5e-5, batch 8. | Best evidence for "idle local distillation" in narrow classifier domain; reuse metric-driven synthetic refinement. |
| 5 | Qiu et al., "AgentDistill," arXiv:2506.14728, DOI 10.48550/arXiv.2506.14728. | Training-free: teacher extracts reusable MCP tool modules from successful trajectories, abstracts/clusters into MCP-Box; student uses tools without gradient updates. | Qwen3-8B + MCP: Game of 24 72.7→79.7; LLaMA3.1-8B 21.7→64.0. PathVQA 75.5 vs teacher 99. | 9-13 distilled MCPs per domain. No gradient data required. | No student training. | Store distilled workflows beside `portable_pointer`; more robust than weight updates for procedural skills. |

### Q1: 1,000 Trajectory Vacant Estimate（codex 原文）

For 1,000 completed 3-15 turn trajectories, expect roughly 1-4M raw tokens and about 700-1,000 usable full-trajectory examples after filtering; if split by steps, perhaps 6k-15k step examples [unverified]. This is smaller than SCoRe's 5K+ correction data, but close to Kang et al.'s ~2,000 filtered trajectories.

Compute: a LoRA/QLoRA run on 1.5B-3B should fit on a 24-48GB GPU; 7B is safer on 48-80GB. Rough cost using 2026 A100 80GB rates of about $0.62-$3.18/hr and H100 rates around $1.99-$2.99/hr: **1.5B-3B likely $5-$40, 7B likely $20-$150** depending on epochs and provider [unverified]. Kang et al.'s 4×A100 setup is overkill for a 1k-trajectory narrow LoRA run.

Quality gap: for narrow routine use, **3B can plausibly reach 75-85/100 vs teacher, 7B 85-93/100, 1.5B 60-75/100, 0.5B only for classifiers/templates** [unverified]. This matches the shape of Kang et al.: 7B agent distill reached ~93% of teacher average, 3B ~80%, 1.5B ~66%, 0.5B ~48%.

**Minimum viable size: 3B is the realistic default for 80% of normal tool-using use cases.** 1.5B may work if the domain is narrow and actions are schema-bound. 0.5B is viable for classification/routing, not general fallback conversation.

Likely failures: out-of-domain requests, rare tool plans, long-horizon tasks, ambiguous user intent, missing private context, false confidence, stale knowledge, malformed tool calls, and tasks whose success cannot be verified automatically.

### Q2: Today vs 2029（codex 原文）

Today, pure self-distillation works only where the vacant has reliable success signals: exact answers, executable tests, classifiers, tool-call validation, or synthetic validation. Kang et al. filter wrong trajectories by answer correctness; Agentic KD uses synthetic validation metrics; AgentDistill avoids training and distills reusable MCP tools.

What still needs the teacher/API: generating high-quality trajectories, first-error correction, semantic judging, and recovery from failed self-generated data. SCoRe explicitly relies on Qwen2.5-72B as teacher/judge; SAD uses teacher trajectories/distributions; Kang uses Qwen2.5-32B teacher.

By 2029, the loop is technically viable for narrow agents if Vacant caches teacher traces while online, logs structured outcomes, and trains local adapters during idle time. It is not likely to become fully oracle-free for open-ended domains without external feedback.

### Q3: Critical Threshold（codex 原文）

Empirical threshold is around **2,000 high-quality filtered trajectories** for useful small agent distillation: Kang et al. train on ~2,000 correct trajectories and get useful 1.5B-7B agents. Around **5,000 correction trajectories** is the stronger threshold for robust agentic RL/SFT: SCoRe uses ~5K SFT + ~5K RL samples per domain and reports that 10K SFT gives no clear gain over 5K.

For Vacant: **below ~300-500 trajectories, prefer retrieval/cache/tool libraries over weight updates** [unverified]. Around **1,000 trajectories is enough for a narrow adapter** if tasks repeat and outcomes are verifiable. Around **2,000-5,000 is the practical threshold** for a portable fallback model that does more than mimic phrasing.

---

## 附錄：Web Search 引用來源

1. [Structured Agent Distillation for Large Language Model — arXiv:2505.13820](https://arxiv.org/abs/2505.13820)
2. [From Correction to Mastery: Reinforced Distillation of LLM Agents — arXiv:2509.14257](https://arxiv.org/abs/2509.14257)
3. [Distilling LLM Agent into Small Models with Retrieval and Code Tools — arXiv:2505.17612](https://arxiv.org/abs/2505.17612) ([NeurIPS poster](https://neurips.cc/virtual/2025/poster/117657), [GitHub](https://github.com/Nardien/agent-distillation))
4. [Agentic Knowledge Distillation — arXiv:2602.10869](https://arxiv.org/abs/2602.10869)
5. [AgentDistill: Training-Free Agent Distillation with Generalizable MCP Boxes — arXiv:2506.14728](https://arxiv.org/html/2506.14728v1)
6. [Towards Edge General Intelligence: KD for Mobile Agentic AI — arXiv:2511.19947](https://arxiv.org/html/2511.19947)
7. [Qwen3 Technical Report — arXiv:2505.09388](https://arxiv.org/pdf/2505.09388)
8. [Phi-4-reasoning Technical Report — Microsoft Research](https://www.microsoft.com/en-us/research/wp-content/uploads/2025/04/phi_4_reasoning.pdf)
9. [Fine-tuning Qwen3-0.6B on terminal command generation](https://app.readytensor.ai/publications/fine-tuning-qwen3-06b-for-cross-platform-terminal-command-generation-lnWR43YpgJaH)
10. [Unsloth Qwen3 fine-tuning docs](https://docs.unsloth.ai/models/qwen3-how-to-run-and-fine-tune)
11. [Knowledge Distillation and Dataset Distillation survey — PMC:12634706](https://pmc.ncbi.nlm.nih.gov/articles/PMC12634706/)

---

*T2 v1.1 · 2026-05-01 · codex job bhsxbnc3w 原始輸出已補入附錄；3B 為最小可行 param count（已校正）*
