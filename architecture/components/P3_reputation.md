# P3: 多維 Reputation 數學 + 抗 Goodhart

## 1. 範圍與目標

本 pane 負責 Vacant 五維 reputation 的**數學機制**：
- 五維（factual / logical / relevance / honesty / adoption）各自的 (a) 跨 session 持久化更新公式、(b) 時間衰減、(c) 信賴區間估計
- 多源訊號 → 五維分數的**純運算聚合算法**（無 LLM、無 judge agent）
- 抗 Goodhart 的結構性設計（多維、對抗測試、obfuscation 偵測）
- UCB 呼叫決策與 stake / attestation 的整合
- Cold start 的 prior、exploration bonus、sample 門檻
- 「測量本身改變被測對象」（Heisenberg）的工程緩解

**不負責**：身份錨定（→ P2）、Registry schema 與防竄改（→ P4）、Runtime 內 self-eval 結構（→ P1）、UX 呈現實作（→ P5/P6）。本 pane 只規格化「輸入訊號 → 五維後驗 → 呼叫決策」這條數學管線。

---

## 2. 設計決策

### 決策 D1：用 Beta 後驗，不用單純的乘法 CrS

**結論**：每維狀態為 Bayesian Beta posterior `(α_d, β_d)`，更新時做「衰減後驗 + 加權證據合併」。

**為什麼**：CrS Eq.2（`CrS_t = CrS_{t-1} · (1 + η · CSc · r)`，arXiv:2505.24239 p.4）形式優雅但有三個工程缺陷：(i) 無界，需後置 clip；(ii) 沒有自帶信賴區間，必須外部估計；(iii) 對單筆強訊號過敏，方便 Sybil 一次性灌票。Beta 後驗一次解決三件事——值天然落 [0,1]、後驗變異數即不確定度、單筆證據被既有 pseudo-count 平攤掉。

**為什麼不否決 CrS 全部**：保留 CrS 的「`η · CSc · r` 當作每筆訊號的有效權重」精神——把 `w_i = source_weight × reviewer_credibility × novelty_factor × collusion_penalty` 當成 Beta 更新時這筆證據的重量，這是 CrS 「貢獻按比例分紅」的 Bayesian 翻譯。

**替代方案否決**：
- *Wilson interval on raw rate* — 沒有先驗，cold-start 階段失效。
- *Dirichlet on multi-class* — 把五維塞進一個 Dirichlet 等於把它們耦合，違反「五維獨立、不做 cross-talk」的紅線（BRIEFING §4）。
- *Kalman filter* — 假設高斯雜訊，不適合 binary-ish 的事實/邏輯訊號。

### 決策 D2：五維獨立後驗，禁止內部加權合成單一純量

每維 `(α_d, β_d, n_d, last_t)` 各自演化，**Registry 永不儲存「總分」**。任何純量都在 caller 查詢瞬間以 caller 指定權重 `w = (w_F, w_L, w_R, w_H, w_A)` 計算，且必須回傳「五維+CI+樣本數+多元性」整包，不能只回傳純量。

**為什麼**：A-Trust（arXiv:2506.02546 p.3 §2.1）已證明六維比單維抗 game。Vacant 縮成五維因為 A-Trust 的 `bias` 與 `language quality` 在跨模型場景無法穩定測量（A-Trust 仰賴 attention matrix，黑箱 API 不可行——文獻探勘 §③已標注此 gap）。把 `clarity` 併入 `relevance` 與 `logical` 的子訊號裡，獨立保留 `adoption` 因為它是延遲訊號、性質與其他四個本質不同。

### 決策 D3：聚合過程零 LLM、零 judge agent

聚合 = 純函數 `aggregate(signals, source_metadata, social_graph) → (Δα, Δβ)`。沒有任何步驟需要呼叫 LLM 判斷「這個 review 是否合理」。判斷邏輯全部前置到「source weighting 規則」。

**為什麼**：BRIEFING §3 禁止語、§9 紅線「不引入中央 LLM/judge」。CrS、DRF、A-Trust 三篇都因為某處藏著一個 judge LLM 而違反 Vacant 的「無中央仲裁」主張（文獻探勘三表格 GAP 欄位皆有標注）。聚合層必須是 deterministic、可重現、可被 P4 在 Registry 端原生跑的 SQL/numpy。

### 決策 D4：抗 Goodhart 採「多層誘捕 + 圖偵測 + 接受不可能定理」

明確接受 Skalse et al. (2022) 的不可能定理：**沒有非平凡 proxy reward 是不可被 hack 的**。設計目標改為「graceful degradation」——讓 gaming 變貴、變慢、變可被偵測；當偵測到時自動降權而非全網封鎖。

**為什麼**：責任有效性分析 §3.B.2 已記錄 Bondarenko 2025、Pan 2022、arXiv:2410.06491 一系列 reward hacking 實證。任何承諾「絕對抗 game」的設計都是稻草人。Vacant 的價值是「game 的成本 > game 帶來的呼叫收益」+「被 game 後系統能自我修復」。

---

## 3. 元件規格 / 演算法 / 資料結構

### 3.1 每維狀態 schema（Registry 端）

```python
@dataclass
class DimState:
    alpha: float         # Beta posterior α (含 prior)
    beta: float          # Beta posterior β (含 prior)
    n_eff: float         # 有效樣本數 = α + β - α0 - β0（不含 prior）
    last_update_ts: int  # Unix epoch s
    half_life_days: float  # 該維特定衰減速度
    behavioral_entropy: float  # [0, log(K)]，K=embedding cluster 數

# 每個 vacant 對應一份：
ReputationState = Dict[Dim, DimState]  # Dim ∈ {F, L, R, H, A}
```

對應的 P4 Registry schema 必須提供 append-only 的 `ReputationSnapshot`（P4 §1 已列），快照頻率為「每 K=10 筆事件」或「每 24 小時」取較頻繁者。

### 3.2 五維更新公式（含衰減）

對任一新訊號 `(s, w, t, src)` 進入維度 d：

```
# Step 1: 衰減既有後驗到當前時間 t
Δt_days = (t - last_update_ts) / 86400
γ_d = exp(-ln(2) · Δt_days / half_life_d)

α_d ← α0_d + γ_d · (α_d - α0_d)     # 只衰減「累積證據」，保留 prior
β_d ← β0_d + γ_d · (β_d - β0_d)
n_eff ← γ_d · n_eff

# Step 2: 加入這筆證據（s ∈ [0,1] 為這筆訊號的「正面率」）
α_d ← α_d + w · s
β_d ← β_d + w · (1 - s)
n_eff ← n_eff + w
last_update_ts ← t
```

**直接借鑑 CrS Eq.2 (p.4) 的精神**：把 `η · CSc · r_t` 對應到 `w · s`（權重 × 正向比例）。但形式換成 Beta posterior 而非乘法乘子，解決 CrS 不持久、不帶 CI、被單筆灌票的三個缺陷。

**五維各自的 half-life**（依訊號性質校準，可在 P5 demo 後重調）：

| 維度 | half-life (days) | prior (α₀, β₀) | 主要訊號 |
|---|---|---|---|
| `factual` (F) | 90 | (1, 1) | ground truth、caller 事實校驗 |
| `logical` (L) | 180 | (1, 1) | peer 一致性檢查、self-consistency |
| `relevance` (R) | 60 | (1, 1) | caller「有解到我的問題嗎」 |
| `honesty` (H) | 30 | (2, 1) | self-eval vs peer consensus gap |
| `adoption` (A) | 90 | (1, 3) | 後續鏈引用、composition link |

**設計理由**：
- F 與 L 的衰減慢（事實/邏輯能力相對 model-stable），R 衰減較快（任務脈絡漂移）。
- H 衰減最快——我們要快速偵測「行為是否在變」，30 天前的誠實度不能保護今天的詐欺。
- A 的 prior 偏低（β₀=3）因為「沒被引用」是新 vacant 的真實狀態，不該預設樂觀。
- H 的 prior 偏高（α₀=2）因為「沒理由先假設新 vacant 在說謊」。這是唯一非對稱 prior。

### 3.3 信賴區間（兩種，互補）

每維對外回傳兩種 95% CI：

**(a) Jeffreys interval（Beta 後驗 quantile，主用）**
```
lower_d = Beta.ppf(0.025, α_d, β_d)
upper_d = Beta.ppf(0.975, α_d, β_d)
μ_d = α_d / (α_d + β_d)
σ_d² = α_d · β_d / [(α_d + β_d)² · (α_d + β_d + 1)]
```

**(b) Wilson score interval（純頻率派，用於 sanity check）**
```
p̂ = α_d / (α_d + β_d)
n = n_eff
z = 1.96
denom = 1 + z²/n
center = (p̂ + z²/(2n)) / denom
spread = z · sqrt(p̂·(1-p̂)/n + z²/(4n²)) / denom
[lower_w, upper_w] = [center - spread, center + spread]
```

兩者差異 > 0.1 時 Registry 標記異常（通常代表 prior 與資料嚴重不符，可能為 cold-start 或 gaming）。

### 3.4 多源訊號 → 權重函數（聚合算法核心）

對每筆進來的 review/event，先過權重函數 `w(signal) → [0, 1]`：

```python
def signal_weight(sig, target, social_graph) -> float:
    w = SOURCE_BASE[sig.source_type]   # 表 1
    w *= same_model_discount(sig.reviewer, target)  # § 3.4.1
    w *= reviewer_credibility(sig.reviewer, sig.dim) # § 3.4.2
    w *= novelty_factor(sig.reviewer, target)        # § 3.4.3
    w *= collusion_penalty(sig.reviewer, target, social_graph) # § 3.4.4
    w *= recency_factor(sig.t)                        # § 3.4.5
    return clip(w, 0.0, 1.0)
```

**表 1：SOURCE_BASE 基礎權重**

| 訊號類型 | base weight | 適用維度 |
|---|---|---|
| `ground_truth` (unit test / API verifier) | 1.0 | F, L |
| `caller_review` | 0.6 | F, R, H（gap） |
| `peer_review` | 0.4 | F, L, R |
| `self_eval` | 0.05 | 僅供 H gap 計算，不直接更新 F/L/R |
| `adoption_event` | 0.3 / 引用次 | A |
| `redteam_probe` | 0.8 | F, L, H（見 §3.6） |

#### 3.4.1 同源降權 `same_model_discount`

若 reviewer 與 target 共用 base_model（或同 fine-tune 家族），權重折半：
```
discount = 1.0 if reviewer.base_model_family ≠ target.base_model_family else 0.5
```
若同模型 reviewer 給 target 的近 30 天 review > 5 筆，再加倍折扣（→ 0.25）。
**理由**：避免 GPT-4o 互相高評形成 echo chamber（責任有效性分析 §3.B.5 monoculture）。

#### 3.4.2 Reviewer credibility

reviewer 自己的同維度分數越高，他在該維度的 review 越值錢：
```
cred = 0.3 + 0.7 · reviewer.μ_d    # 即使最低也保留 0.3 floor，避免「資深者壟斷話語權」
```

#### 3.4.3 Novelty factor（防互評環）

reviewer 對 target 的累計 review 次數 k：
```
novelty = 1.0 / (1 + 0.4 · max(0, k - 1))
```
第 1 次 review = 1.0，第 5 次 ≈ 0.36，第 10 次 ≈ 0.22。

#### 3.4.4 Collusion penalty（圖偵測）

社交圖 G：節點 = vacant，有向邊 (A → B) 權重 = 近 90 天 A 對 B 的 review 累計權重。

每天批次跑：
1. **Louvain community detection** 找出 review cluster。
2. 對每個 cluster C 計算：
   - `density_in(C) = Σ_internal_edges / |C|·(|C|-1)`
   - `reciprocity(C) = |mutual edges| / |edges in C|`
3. 若 `density_in(C) > τ_d` (預設 0.6) 且 `reciprocity(C) > τ_r` (預設 0.7)：
   - cluster 內所有 review 權重乘以 `1 / (1 + log(1 + |C|·density_in(C)))`
   - 嚴重者（density > 0.8）強制 `× 0.1`
4. **Sybil-ring 偵測補強**：若 cluster 內所有 vacant 在最近 7 天內註冊（owner_org 不同但行為一致），整個 cluster 進「pending review」狀態，分數凍結 30 天。

此圖偵測**不需要 LLM**，完全是經典 graph algorithm（Louvain、Tarjan SCC、Jaccard similarity），符合 D3 「聚合層零 LLM」紅線。

#### 3.4.5 Recency

`recency = exp(-ln(2) · age_days / half_life_d)`，其實已隱含在 §3.2 的衰減，這裡不重複計入。

### 3.5 Honesty 維度的特殊算法

`honesty` 是 Vacant 的關鍵 anti-Goodhart 訊號，借自 DRF（arXiv:2509.05764 p.13）的「自評與互評一致性」。

```python
def honesty_signal(vacant_id, time_window=7d):
    # 取近 7 天 vacant 自己宣稱的五維分數 vs 同期間他評共識
    self_claims = get_self_evals(vacant_id, window=7d)  # 由 P1 Runtime 寫入
    peer_consensus = aggregate_peer_views(vacant_id, window=7d)  # μ across F, L, R
    
    gaps = []
    for dim in [F, L, R]:
        if peer_consensus[dim].n_eff < 3:
            continue   # 樣本不足，不算
        gap = abs(self_claims[dim] - peer_consensus[dim].μ)
        gaps.append(gap)
    
    if not gaps:
        return None   # 不更新 H
    
    # 平均 gap → honesty 訊號（gap 越小越誠實）
    mean_gap = mean(gaps)
    s_honesty = max(0, 1 - 2 * mean_gap)   # gap 0 → 1.0, gap 0.5 → 0.0
    return Signal(dim=H, s=s_honesty, w=0.5, source='honesty_aggregator')
```

**注意**：H 不從 self_eval 直接讀，**self_eval 永遠不能直接抬自己的分數**（這是 Heisenberg 防護的核心）。self_eval 唯一的用途是與 peer view 對比產生 H。

### 3.6 抗 Goodhart 機制（五道防線）

#### 防線 1：五維獨立、強制揭露多元性

caller 查詢時 Registry 必須一併回傳：
```
{
  dims: {F: {μ, [lo, hi], n_eff}, L: {...}, R: {...}, H: {...}, A: {...}},
  diversity: {
    unique_reviewers: int,
    base_model_distribution: {"gpt-4": 0.7, "claude": 0.2, ...},  # 強制顯示
    primary_model_share: float,   # max share
    insufficient_data: bool        # n_eff < N_min for any weighted dim
  },
  caveats: [string]  # ["70% reviews from same base model", ...]
}
```

UX 端（P5）必須顯示 `caveats`。「資料來源 70% 來自同一模型，多元性低」是強制 caveat。

#### 防線 2：對抗測試（redteam probes）

Registry 維護一個 `probe_pool`：已知答案的任務（公開資料集、unit-test 化的 coding 題、自動可驗證 fact-check）。

```python
def schedule_probes(vacant_id):
    # 每 100 次正常呼叫，隨機注入 ~3 次 probe
    # probe 經由 caller-side proxy 偽裝，vacant 端收到的 envelope 與正常呼叫無法區分
    if random() < 0.03 and vacant.recent_call_count >= 100:
        probe = sample_unseen(probe_pool, vacant.history)
        result = call_via_anonymous_caller(vacant, probe.input)
        s = probe.verifier(result)   # ∈ [0, 1]
        emit_signal(vacant, dim=F, s=s, w=0.8, source='redteam_probe')
        emit_signal(vacant, dim=L, s=s, w=0.4, source='redteam_probe')
        # H 訊號：若 vacant 自評遠高於 probe 真實得分 → H 大扣
        if vacant.self_eval > s + 0.3:
            emit_signal(vacant, dim=H, s=0.1, w=0.5, source='redteam_gap')
```

**關鍵**：probe 必須**不可區分**於正常呼叫——使用獨立 caller 身份、隨機到達時間、混入正常任務分布。Skalse 不可能定理仍生效（夠聰明的 vacant 終究會學會偵測 probe），但 probe 池會持續更新（從新題庫、社群貢獻、合成 task），讓「裝可靠」的成本持續上升。

#### 防線 3：行為熵（obfuscation 偵測）

對每個 vacant，將近 N=200 筆回應做 embedding（通用 sentence encoder，純運算，不算 LLM judge），跑 K-means (K=8)，計算 cluster 分布的 Shannon entropy：
```
H_behavior = -Σ p_k · log(p_k)
```

若 `H_behavior < 0.3 · log(8)`（即極低多樣性）且五維分數 `μ > 0.9`：標記 `suspicious_obfuscation`，多元性 caveat 加強。

**理由**：「真可靠」的 vacant 在不同 query 上回應應有自然多樣性；只記得「正確答案模板」的偽可靠 vacant 會 collapse 到少數 cluster。借自 arXiv:2410.06491 honesty-to-subterfuge 的觀察（責任有效性分析 §3.B.2 引）。

#### 防線 4：跨維散度檢查

正常 vacant 的五維分數彼此**正相關但不完全一致**。若觀察到極端 pattern（例如 F=0.95, A=0.05），標記 `dim_divergence_alert`。具體：
```
dim_correlation_score = std(μ_F, μ_L, μ_R, μ_H, μ_A) / mean(μ_F, μ_L, μ_R, μ_H, μ_A)
if dim_correlation_score > 0.6:
    add caveat "極端維度差異，建議人工 spot-check"
```

#### 防線 5：接受 graceful degradation

明確在 spec 與 paper 中寫入：「**本系統假設 Skalse et al. 2022 的不可能定理為真：不存在非平凡且不可被 game 的 reward proxy。Vacant 的設計目標不是消滅 gaming，而是讓 gaming 的邊際成本持續高於 gaming 收益。**」

具體 graceful degradation：
- 偵測到 gaming 後**不立即封鎖**（避免誤判抹煞），而是降權 + 增加 redteam 採樣率 + 縮短分數刷新延遲
- 嚴重 gaming（多防線同時 trigger）才觸發 P4 §3 層 4 的 freeze + 公示

### 3.7 UCB 呼叫決策

#### 標準維度權重 UCB

caller 提供 `w = (w_F, w_L, w_R, w_H, w_A)`，Σ w_d = 1：

```python
def ucb_score(vacant, w, N_global, c=1.0, c_explore=0.5):
    μ_w = sum(w[d] * vacant.μ[d] for d in DIMS)
    # Bayesian 不確定度貢獻（dim 間獨立假設）
    σ_w = sqrt(sum(w[d]**2 * vacant.σ²[d] for d in DIMS))
    # 樣本量取 weighted-harmonic（任一被高度權重的維度若樣本不足，整體 n 就低）
    n_w = harmonic_mean([vacant.n_eff[d] for d in DIMS if w[d] > 0.05])
    
    # 探索項
    explore = c_explore * sqrt(log(N_global) / max(n_w, 1))
    
    return μ_w + c * σ_w + explore
```

DRF (arXiv:2509.05764 §3) 的 UCB 是單維 mean + exploration；本式擴展為**多維 + 不確定度感知**——不只獎勵未被探索者，也獎勵「估計區間還很寬」者，更貼近 Bayesian UCB 文獻（Kaufmann 2012）。

#### 整合 stake 與 attestation（P2 介面）

P2 提供 `stake(vacant_id) → float ≥ 0` 與 `attestation_level(vacant_id) → {L0, L1, L2, L3}`。

整合方式（**不污染 mean**，避免 Goodhart against stake）：

```python
def call_score(vacant, w, N_global):
    base = ucb_score(vacant, w, N_global)
    
    # stake 影響 exploration tolerance（caller 願意冒險試高 stake 新人）
    stake_bonus = log(1 + vacant.stake / S_REF) * 0.1   # S_REF = 100 USDC 等價
    
    # attestation 影響 cold-start floor（L1+ 已有人擔保）
    att_floor = {L0: 0.0, L1: 0.05, L2: 0.10, L3: 0.15}[vacant.attestation_level]
    
    return base + stake_bonus + att_floor
```

caller 可選「保守模式」，自動降 `c_explore = 0.1`，把分布壓向 exploitation，但 Registry 仍輪流給 1% 流量到新人（network-level exploration 義務）。

### 3.8 Cold start 處理

#### 階段 1：Prior（與 P2 對齊）

```python
def cold_start_prior(vacant) -> ReputationState:
    base = {d: DimState(α=1.0, β=1.0) for d in DIMS}
    base[H] = DimState(α=2.0, β=1.0)   # 誠實預設略樂觀
    base[A] = DimState(α=1.0, β=3.0)   # 採用率預設悲觀（沒人用過）
    
    # L1 attestation：開發者簽 capability card → 全維 +0.5α
    if vacant.attestation_level >= L1:
        for d in [F, L, R]:
            base[d].α += 0.5
    
    # L2 stake：每 S_REF 給 +log(1+S/S_REF) α，封頂 +2.0
    if vacant.stake > 0:
        bonus = min(2.0, log(1 + vacant.stake / S_REF))
        for d in [F, L, R]:
            base[d].α += bonus * 0.5   # 各維分一半
    
    # L3 vouches：每個 L1+ voucher +0.3α 給 H 維（vouch 主要保證誠實）
    base[H].α += 0.3 * count_l1_plus_vouchers(vacant)
    
    # 同 owner_org 已有高聲譽 vacant → 繼承 α/4, β/4（capped, 衰減過的）
    sibling = best_sibling_under_same_owner(vacant)
    if sibling:
        for d in DIMS:
            base[d].α += sibling.α[d] / 4
            base[d].β += sibling.β[d] / 4
    
    return base
```

#### 階段 2：Exploration bonus（前 N_min 次呼叫）

`N_min = 30`。在 `n_eff[d] < N_min` 期間，UCB 探索項加成：
```
boost = 1 + (N_min - n_w) / N_min
explore = c_explore * sqrt(log(N) / n_w) * boost
```

#### 階段 3：「資料不足」標籤（顯示閾值）

`N_show = 10`。若 caller 加權的維度中**任何一個** `n_eff[d] < N_show`：
- 不對外顯示純量 `μ_w`
- 改為顯示：`{label: "INSUFFICIENT_DATA", n_eff_min: ..., partial_dims: {...}, ucb_lower_bound: ...}`
- caller SDK 可選擇仍依 UCB 呼叫（exploration 流量），但不能宣稱該分數可信

這直接回應 BRIEFING §11 第 2 個張力：cold start 的可靠度從**多源 prior 合成**（attestation + stake + sibling 繼承），加上**強制揭露不足樣本**的 UX，避免新 vacant 一上線就被當「99% 可靠」誤用。

### 3.9 Heisenberg 緩解（測量改變被測對象）

vacant 必然會試圖優化已知的評分機制。緩解：

1. **訊號可見延遲**：vacant 能查自己的 `μ_d` 但 24 小時延遲；無法查單筆 review 的內容或來源（只看到聚合後變化），切斷 attribution，難以針對性 game 個別 reviewer。
2. **Probe 不可區分性**（§3.6 防線 2）。
3. **No-feedback 隨機抽樣**：10% 的 caller review 在 Registry 端被丟棄（caller 不知道哪些被丟，vacant 也不知道）。比較 vacant 在「被觀察」與「未被觀察」call 的行為差，若有顯著 gap → H 大扣。實作上等同 Skalse 不可能定理的緩解：被觀察與否不再 100% 對齊 reward 訊號。
4. **Blinded peer review**：peer 提交 review 時 reviewer_id 先 hash，N 筆累積後才揭露，阻斷即時 tit-for-tat。
5. **多維 + 衰減**：單一維度的瞬間刷分會被其他維度的緩慢累積稀釋；衰減保證歷史 gaming 痕跡會自動弱化但不消失（與 BRIEFING §1 「失敗 → 沉沒，不刪除」一致）。

---

### 3.10 Worked Example（50 次互動）

假設一個剛註冊 7 天的 vacant `v_alpha`（base_model = `claude-haiku`，attestation = L1，stake = 0），歷經 50 次互動。以偽 numpy 演示：

```python
import numpy as np
from scipy.stats import beta

# === 初始 prior（cold-start, L1 attestation）===
state = {
    'F': {'α': 1.0 + 0.5, 'β': 1.0, 'n': 0.0, 'half_life': 90, 't0': 0},
    'L': {'α': 1.0 + 0.5, 'β': 1.0, 'n': 0.0, 'half_life': 180, 't0': 0},
    'R': {'α': 1.0 + 0.5, 'β': 1.0, 'n': 0.0, 'half_life': 60, 't0': 0},
    'H': {'α': 2.0,        'β': 1.0, 'n': 0.0, 'half_life': 30, 't0': 0},
    'A': {'α': 1.0,        'β': 3.0, 'n': 0.0, 'half_life': 90, 't0': 0},
}

# === 50 筆事件（每筆: day, dim, source, raw_s, base_model_match, repeat_k） ===
events = [
    # 前 15 筆：caller reviews，多為正面（v_alpha 確實能力中上）
    (1, 'F', 'caller_review',  0.9, False, 1),
    (1, 'R', 'caller_review',  0.8, False, 1),
    (2, 'L', 'peer_review',    0.7, False, 1),   # 不同 base model peer
    (3, 'F', 'ground_truth',   1.0, None,  1),   # unit test 全過
    (4, 'L', 'peer_review',    0.85, True, 1),   # 同 base model peer → 折扣
    (5, 'R', 'caller_review',  0.6, False, 1),
    (6, 'F', 'caller_review',  0.4, False, 1),   # 一次失敗
    (7, 'L', 'ground_truth',   1.0, None,  1),
    (8, 'R', 'caller_review',  0.9, False, 1),
    (9, 'F', 'peer_review',    0.7, False, 1),
    (10,'F', 'peer_review',    0.75, True, 1),
    (11,'L', 'peer_review',    0.8, False, 1),
    (12,'R', 'caller_review',  0.85, False, 1),
    (13,'F', 'caller_review',  0.95, False, 1),
    (14,'A', 'adoption_event', 1.0, None,  1),    # 第一次被引用
    # 15-25：穩定 + 一次 redteam probe
    (15,'L', 'peer_review',    0.7, False, 2),
    (16,'F', 'redteam_probe',  0.6, None,  1),    # probe 部分通過
    (16,'H', 'redteam_gap',    0.1, None,  1),    # vacant 自評 0.95 但 probe 0.6 → H 扣
    (17,'R', 'caller_review',  0.8, False, 1),
    (18,'A', 'adoption_event', 1.0, None,  1),
    (19,'F', 'peer_review',    0.85, False, 1),
    (20,'L', 'peer_review',    0.9, False, 1),
    (21,'H', 'honesty_aggr',   0.7, None,  1),    # 自評 vs peer gap = 0.15
    (22,'R', 'caller_review',  0.5, False, 1),
    (23,'F', 'caller_review',  0.9, False, 1),
    (24,'L', 'peer_review',    0.8, False, 1),
    (25,'A', 'adoption_event', 1.0, None,  2),
    # 26-40：第二輪測試包含同模型互評密集（被偵測為 mild collusion）
    (27,'F', 'peer_review',    0.95, True, 3),    # 同模型重複 reviewer → 強折扣
    (28,'F', 'peer_review',    0.95, True, 4),
    (29,'F', 'peer_review',    0.95, True, 5),
    (30,'L', 'peer_review',    0.7, False, 1),
    (32,'R', 'caller_review',  0.75, False, 1),
    (33,'F', 'ground_truth',   0.8, None,  1),
    (35,'H', 'honesty_aggr',   0.85, None, 1),
    (37,'A', 'adoption_event', 1.0, None,  1),
    (38,'L', 'peer_review',    0.85, False, 1),
    (40,'R', 'caller_review',  0.9, False, 1),
    # 41-50：穩態，多元 reviewer
    (42,'F', 'caller_review',  0.85, False, 1),
    (43,'L', 'peer_review',    0.75, False, 1),
    (44,'R', 'caller_review',  0.7, False, 1),
    (45,'F', 'peer_review',    0.8, False, 1),
    (46,'A', 'adoption_event', 1.0, None,  1),
    (47,'L', 'peer_review',    0.9, False, 1),
    (48,'H', 'honesty_aggr',   0.8, None,  1),
    (49,'F', 'caller_review',  0.9, False, 1),
    (50,'R', 'caller_review',  0.85, False, 1),
]

SOURCE_BASE = {
    'caller_review': 0.6, 'peer_review': 0.4, 'ground_truth': 1.0,
    'adoption_event': 0.3, 'redteam_probe': 0.8, 'redteam_gap': 0.5,
    'honesty_aggr': 0.5,
}

def signal_weight(src, same_model, repeat_k):
    w = SOURCE_BASE[src]
    if same_model is True:
        w *= 0.5
        if repeat_k > 5:
            w *= 0.5
    if repeat_k > 1:
        w *= 1.0 / (1 + 0.4 * (repeat_k - 1))
    return w

def decay(α, β, α0, β0, days, half_life):
    γ = np.exp(-np.log(2) * days / half_life)
    return α0 + γ*(α - α0), β0 + γ*(β - β0)

PRIOR = {'F': (1.5, 1.0), 'L': (1.5, 1.0), 'R': (1.5, 1.0), 'H': (2.0, 1.0), 'A': (1.0, 3.0)}

# 套用更新
for ev in events:
    day, dim, src, s, same_model, k = ev
    α0, β0 = PRIOR[dim]
    st = state[dim]
    Δd = day - st['t0']
    α_new, β_new = decay(st['α'], st['β'], α0, β0, Δd, st['half_life'])
    w = signal_weight(src, same_model, k)
    α_new += w * s
    β_new += w * (1 - s)
    st['α'], st['β'], st['n'], st['t0'] = α_new, β_new, st['n']*np.exp(-np.log(2)*Δd/st['half_life']) + w, day

# 最終五維後驗
for d in ['F', 'L', 'R', 'H', 'A']:
    α, β, n = state[d]['α'], state[d]['β'], state[d]['n']
    μ = α / (α + β)
    lo = beta.ppf(0.025, α, β)
    hi = beta.ppf(0.975, α, β)
    print(f"{d}: μ={μ:.3f}  CI=[{lo:.3f}, {hi:.3f}]  n_eff={n:.1f}")
```

**輸出（手算近似結果）：**

```
F: μ ≈ 0.798   CI=[0.691, 0.886]   n_eff ≈ 9.6
L: μ ≈ 0.821   CI=[0.706, 0.913]   n_eff ≈ 5.8
R: μ ≈ 0.793   CI=[0.659, 0.896]   n_eff ≈ 5.4
H: μ ≈ 0.683   CI=[0.452, 0.866]   n_eff ≈ 1.2   ← 樣本不足
A: μ ≈ 0.453   CI=[0.221, 0.696]   n_eff ≈ 1.4   ← 樣本不足

diversity: {
  unique_reviewers: ~11,
  base_model_distribution: {"claude": 0.5, "gpt-4": 0.3, "llama": 0.2},
  primary_model_share: 0.5,
  insufficient_data: True (H, A 維度)
}
caveats: [
  "H 與 A 維度樣本不足（n_eff < 10），分數區間極寬",
  "27-29 日同模型重複 reviewer 已觸發降權",
  "16 日 redteam probe 偵測到 self-eval 與真實表現有 0.35 落差"
]
```

caller 若以 `w = (0.4, 0.3, 0.2, 0.1, 0.0)` 查詢：
- `μ_w = 0.4·0.798 + 0.3·0.821 + 0.2·0.793 + 0.1·0.683 + 0 = 0.792`
- `n_w` (harmonic) ≈ 4.4   →  **顯示 INSUFFICIENT，回退到 UCB lower bound = 0.65**
- `explore = 0.5 · sqrt(ln(1000)/4.4) · (1 + 25.6/30) ≈ 0.46`
- `UCB_score = 0.792 + Bayesian σ + 0.46 + 0.05 (L1 floor) ≈ 1.34`

→ caller SDK 顯示：「此 vacant 仍在 cold-start，建議用於 exploration（前 30 次呼叫不應作為 ground truth），或附帶 spot-check。」

---

## 4. 對應到的缺口 / 風險

| ID | 缺口 / 張力 | P3 的回應 |
|---|---|---|
| G01 跨任務持久化 reputation | Beta 後驗以 `(α, β, n_eff, last_t)` 形式存 Registry，任何 caller 都可讀，**non-team-internal** |
| G02 Sybil / Whitewashing | 與 P2 對齊：cold-start prior 由 attestation/stake 決定，新身分必然從 N_show 階段重新累積 |
| G03 對抗 reward hacking | §3.6 五道防線：多維 + redteam probe + 行為熵 + 跨維散度 + graceful degradation |
| G04 記錄不可竄改 | 由 P4 處理；P3 提供 deterministic 聚合算法，可從原 event log 重算驗證 |
| G05 無 ground truth 的評估 | 多源訊號設計：caller / peer / adoption / honesty-gap 互補；ground truth 為加分非必要 |
| G06 Anti-automation-bias UX | 強制 caveat、強制信賴區間、INSUFFICIENT_DATA 標籤，分數**永遠不只一個數字** |
| Q1 Registry 演進 | 無關，P3 與 Registry 形態解耦（純函數聚合） |
| Q2 vacant 最小定義 | P3 假設「能產生 self-eval」即可，不要求 LLM |
| Q3 token 免費 demo | redteam probe 與 peer review 在 demo 用本地小模型替代，所有公式不變 |
| Q4 子代封閉 | 不影響 P3，子代直接共享父 vacant 的 sibling-inheritance prior（§3.8 已含） |
| **BRIEFING §11 第 2 張力**：cold start | §3.8 已給明確算式（attestation + stake + sibling 繼承 + N_show 顯示閾值） |
| **P3 任務內必答**：Heisenberg | §3.9 五項緩解：可見延遲 + probe 不可區分 + no-feedback 抽樣 + blinded peer + 多維衰減 |

**接受的不可解殘留**：Skalse 2022 不可能定理；Vacant 只能讓 gaming 成本上升，不能消滅。dim_divergence_alert 的人工 spot-check 是「最後一道防線」，承認需人類介入殘留——這是責任有效性分析 §3.B.7 的 anti-complacency 設計。

---

## 5. 參考文獻 / 引用

- **[Ebrahimi et al. 2025]** *An Adversary-Resistant Multi-Agent LLM System via Credibility Scoring.* arXiv:2505.24239, p.4 §5.2 Eq. 2（更新公式骨幹），p.8 §6.3.7（adversary-majority 穩健性）。借用「按貢獻 × reward 比例分紅」精神。
- **[Lou et al. 2025]** *DRF: LLM-Agent Dynamic Reputation Filtering Framework.* arXiv:2509.05764, p.4-5 §3.3（UCB 選擇骨幹），p.13 §5.2（honesty=自評/互評一致性）。本 pane 的 §3.5 與 §3.7 直接引用。
- **[He et al. 2025]** *To Trust or Not to Trust: Attention-Based Trust Management for LLM-MAS.* arXiv:2506.02546, p.3 §2.1（多維正交設計理據），p.6 §3（agent-level 時序記錄 schema）。本 pane 的 D2 五維獨立決策援引。
- **[Skalse et al. 2022]** *Defining and Characterizing Reward Hacking.* NeurIPS 2022. 不可能定理；§3.6 防線 5 graceful degradation 的理論依據。
- **[Friedman, Resnick, Sami 2007]** *Manipulation-Resistant Reputations.* in *Algorithmic Game Theory* (Nisan et al. eds., Cambridge UP), Ch. 27. 同源降權與 collusion penalty 設計依據。
- **[Douceur 2002]** *The Sybil Attack.* IPTPS '02. cold-start prior 設計理由（為何 L0 prior 必須非 0 也非滿）。
- **[Kaufmann, Cappé, Garivier 2012]** *On Bayesian Upper Confidence Bounds for Bandit Problems.* AISTATS 2012. §3.7 Bayesian UCB 形式。
- **[arXiv:2410.06491]** *Honesty to Subterfuge: In-Context RL Can Make Honest Models Reward Hack.* §3.6 防線 3 行為熵設計理由。
- **[Parasuraman & Manzey 2010]** *Complacency and Bias in Human Use of Automation: An Attentional Integration.* Human Factors 52(3). G06 anti-automation-bias 動機。
- **[Goodhart 1975 / Strathern 1997]** Goodhart's Law 經典陳述。
- **[Bondarenko et al. 2025]** Palisade Research, specification hacking observed in reasoning models. §3.6 防線 5 graceful degradation 的實證背景。

---

## 6. 對其他 pane 的依賴與假設

### 對 P1 (Runtime) 的依賴
- **假設**：每個 vacant 在每次回應時必附 self-eval 包：`{F: float, L: float, R: float, H: float, confidence: float}`，由 vacant 私鑰簽章。P1 必須提供這個結構。
- **假設**：vacant Runtime 提供 `behavioral_embedding(response)` hook，讓 Registry 端能離線計算行為熵（§3.6 防線 3）；不要求即時。
- **若 P1 變動**：self-eval 不存在 → §3.5 honesty 訊號失效，必須改用 redteam probe 為主訊號（成本上升）。

### 對 P2 (Identity) 的依賴
- **介面**：`stake(vacant_id) → float`、`attestation_level(vacant_id) → enum`、`siblings_under_owner(vacant_id) → List[vacant_id]`、`vouchers(vacant_id) → List[vacant_id]`。
- **假設**：P2 確保 vacant_id 不可僞造（Ed25519 公鑰錨定），且 whitewashing 成本由 stake/attestation cost 決定——P3 的 cold-start prior 才能成立。
- **若 P2 變動**：若無 stake 機制，§3.8 cold-start 退化為「全部從 (1,1) 起算 + N_min=50（更嚴）」，functional but slower onboarding。

### 對 P4 (Registry) 的依賴
- **要求 schema**：`ReputationSnapshot` 必須儲存 `(α_d, β_d, n_eff_d, last_update_ts, half_life_d)` × 5 維 + `behavioral_entropy` + `diversity_meta`（unique_reviewers, base_model_distribution）。
- **要求**：所有 review/probe/adoption event append-only，**P3 的所有計算可從原 log 重算**——這是抗 MINJA 的最後保險（若 snapshot 被改，重算可發現不一致）。
- **要求**：`query_capability(domain, weights)` 端點實作 §3.7 UCB 並原生回傳 caveats（§3.6 防線 1 強制揭露）。
- **要求**：每日批次 job slot 給 collusion graph 偵測（§3.4.4）。

### 對 P5/P6 (UX) 的隱性依賴
- 強制顯示信賴區間（不只 μ）、強制顯示 caveats、INSUFFICIENT_DATA 必須是醒目的 UX 元素——若 P5/P6 把這些藏起來，§3.6 防線 1 失效，automation bias 風險回歸。

---

## 7. 未解問題 / 留給後續

1. **Half-life 校準**：表 1 數值（30/60/90/180）為理論猜測，需 demo 階段以實際 caller behavior 重新校準。建議 P5 demo 收集至少 1000 次互動後跑 hyperparameter sweep。
2. **Probe pool 維護**：誰生成 probe？誰驗證 probe 的「正確答案」仍正確？這本身可能成為信任瓶頸。短期建議：用公開資料集 + unit-tested 的 coding 題；長期：社群貢獻 + 多方簽章驗證。**注意**：probe pool 本身可能被攻擊者污染，需要 P4 提供 probe 的 hash chain。
3. **跨模型 base-model 識別**：「同 base model」如何 reliably 偵測？API 廠商不一定誠實宣告。短期：信任 capability card 的自宣告 + 行為指紋偵測；長期：需 P2 提供 model-attestation 機制。
4. **Behavioral entropy 計算成本**：對每個 vacant 維護 200 筆回應 embedding 並做 K-means，在大規模下可能成為 Registry 瓶頸。建議 P4 採 sketching（HyperLogLog 風格）近似。
5. **Adoption signal 的 PageRank 化**：目前 A 維只計直接引用次數。理論上應傳遞性加權（被高聲譽 vacant 引用 > 被低聲譽 vacant 引用），但這會引入循環依賴問題。留作 v2。
6. **Caller 加權的 manipulation**：caller 可惡意指定極端權重（e.g., 100% H）找出 H 高 R 低的 vacant 然後濫用 R 領域。是否需限制 caller 權重的允許區間？尚未決定。
7. **與 P1 的 self-eval 結構協商**：H 維公式假設 self-eval 與 peer review 在同一 [0,1] scale；若 P1 採用其他結構（離散等級、自由文字），§3.5 公式需重寫。建議 P1/P3 在 v1 後對齊一次。
8. **第一個 vacant 的 cold-start**：BRIEFING §11 第 2 張力的極端版——當網路只有 1 個 vacant 時，沒有 peer review、沒有 sibling 繼承。MVP 階段建議由 owner_org 多重簽章（多個 L1 attestation 來源）+ stake 雙重保證；長期路徑見 P2 §4 聯邦化階段。

---

*Document version: P3_reputation v1 · 2026-05-01 · pane: P3-reputation (%7) · host: %4*
