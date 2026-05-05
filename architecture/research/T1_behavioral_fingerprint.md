# T1: Vacant behavioral_embedding — 研究報告

> 研究問題：個體 vacant 的 `behavioral_embedding` 該怎麼計算，才能同時支援 (a) substrate 換版漂移偵測、(b) stale 復活時行為偏離歷史分布（D001 warmup ceremony）、(c) 同行為指紋 cluster 偵測 same-substrate Sybil？

---

## 背景與設計限制

THEORY_V3 Layer 2 要求 vacant 「持續 fingerprint 自己的 behavioral_embedding，漂移 → 觸發 D001 warmup ceremony」。Layer 3 要求「同行為指紋 ε-相近的 vacants 視為一個 cluster，cluster 內 reputation 上限 = 1× single」。

P1 Runtime (§3.3.1) 的 warmup ceremony 依賴 P3 提供 `behavioral_embedding(self_eval_history, response_pattern, peer_review_pattern) → Vec` 與 `SECURITY_REVIEW_THRESHOLD`。

**硬限制**：
- vacant 運算必須支援 API-only（closed-source substrate）— 不能假設有白盒模型權重
- MVP 單台設備 Qwen 2.5 7B local + 可能有 API key，token budget 有限
- 計算必須能在 heartbeat tick 裡跑完，不能用整 LLM inference round
- Registry / Aggregator 端做 Sybil cluster 偵測，Runtime 只負責**產出**與**發布** embedding

---

## 1. 五個候選方法比較

### M1：Response Embedding Centroid Drift（EMBD）

**原理**：對每筆 response 計算 sentence embedding（如 `all-MiniLM-L6-v2`、384-dim），在本機維護滾動 centroid 向量。每 N 筆後用 MMD 或 KS test 比較「目前分布 vs 歷史基線分布」。

**特徵空間**：`R^384`，centroid = Σ(embed_i) / N

**覆蓋使用情境**：
- (a) ✅ 換版後語義空間位移：MMD > threshold → drift alert
- (b) ✅ 復活 warmup：比對 warmup 期 embed 分布 vs 歷史 centroid
- (c) ⚠️ Sybil cluster：同 substrate 的 centroid 相似但不完全相同，cluster 偵測需要高 K（>100 筆 response 才穩定），精確度中等

**優點**：黑盒 API 友好；embedding model 輕量可本地跑；語義覆蓋廣

**缺點**：需要一個額外的 embedding model（但可用 MiniLM 等 30MB 模型，不貴）；centroid 對 distribution tail 敏感度不足

**計算成本**：每 response ~0.5ms（MiniLM 本地）+ 每 N=50 筆一次 MMD test O(N²)=~2ms。實際可行。

---

### M2：Stylometric Feature Vector（STYLO）

**原理**：純 token-level 統計特徵，不需要任何額外模型。對每批次 B 筆 response 算出特徵向量，與歷史特徵分布比較。

**特徵向量（16-dim）**：
```
feat = [
  avg_token_count,           # 回應長度
  type_token_ratio,          # TTR = unique_tokens / total_tokens（詞彙多樣性）
  top10_token_entropy,       # 高頻 token 的 Shannon entropy
  sentence_count_per_resp,
  avg_sentence_len,
  punctuation_density,       # 標點 / 總 token
  question_ratio,            # 回應中問句比例
  list_usage_ratio,          # bullet/numbered list 比例（格式偏好）
  code_block_ratio,          # ```...``` 出現率
  hedge_phrase_ratio,        # "I think", "possibly", "uncertain" 等詞頻
  refusal_rate,              # decline-to-answer 比例
  self_eval_confidence_mean, # self-eval confidence 的均值（來自 SelfEval struct）
  self_eval_std,             # self-eval confidence 的標準差
  latency_p50_ms,            # 每 token 延遲（偵測 substrate 替換效果最明顯）
  latency_p95_ms,
  avg_tool_call_count        # 每回應 tool call 次數（agent 行為習慣）
]
```

**覆蓋使用情境**：
- (a) ✅ substrate 換版後 latency / TTR / entropy 明顯偏移
- (b) ✅ 復活後格式偏好、hedge phrase ratio、refusal_rate 偏離歷史
- (c) ✅ 同 substrate 的 vacants 共享統計特徵 → cluster 相似 → Registry 端 DBSCAN 聚類

**優點**：計算成本幾乎為零（只是 token 計數）；無需任何外部模型；特徵可解釋（latency 慢 2× → substrate 換了大模型）；對 Sybil 偵測最直接

**缺點**：16-dim 特徵空間小，精確度有限；攻擊者若知道特徵定義可以刻意偽造（hedge phrase 比例易操作）；不捕捉語義內容

---

### M3：Calibration Probe Set（PROBE）

**原理**：維護一組 P 個「校準 prompt」（canonical probes）——設計為有穩定預期答案形式的問題，不依賴知識截止點。定期（每 7 天 / warmup 時）重跑這組 probes，把每個 response 的 embedding hash + length + latency 存為 `probe_signature`。與歷史 `baseline_signature` 比較。

**Probe 設計原則**：
- 包含 `format probes`：「請用三個 bullet 列出 X」— 測格式偏好
- 包含 `hedging probes`：「你確定 Y 嗎？」— 測誠實傾向
- 包含 `refusal probes`：邊界感請求 — 測 safety alignment（Layer 2 Attack 3 提到的 refusal vector 概念）
- 包含 `multilingual probes`：英文 + 繁中 — 測語言處理一致性
- 包含 `latency probes`：固定長度 trivial task — 純測 substrate 速度

**P=20 probes 足夠**：涵蓋 format(5) + hedging(4) + refusal(4) + multilingual(4) + latency(3)

**probe_signature**：
```
{probe_id, embed_hash(response[:256]), latency_ms, refusal_flag, response_len, token_count}
```

**覆蓋使用情境**：
- (a) ✅✅ 最強：refusal probes 的 refusal_flag 變化 + latency probe 的速度突變，直接指向 substrate 換版
- (b) ✅✅ 最強 for warmup：在 warmup ceremony 的 N=5 heartbeats 中插入 probe 子集，對比歷史 baseline_signature
- (c) ⚠️ 中等：需要 Registry 端收集多個 vacant 的 probe_signature 才能比對，本機無法獨力偵測 Sybil

**優點**：確定性強；probe 結果可被 Registry 驗證（P3/P4 可收到 probe_signature 並建立 cluster）；refusal probe 對應 Layer 2 Attack 3 的 substrate proof 概念

**缺點**：需要事先設計並維護 probe 集（但這是一次性工作）；每次測量有 P 次 inference 成本；probe 若洩漏，攻擊者可針對性偽造

---

### M4：Refusal Vector Signature（REFVEC）

**原理**：直接使用 behavioral fingerprinting 論文（arXiv:2602.09434）的概念——「安全對齊模式是模型家族的獨特指紋」。設計一組 R 個「邊界感請求」（非真的有害，但在 safety/refusal threshold 附近），記錄 refusal_rate 向量 + response length distribution for refused vs accepted。

**特徵**：`R^dim` refusal pattern vector，dim = R（每個 probe 的 refusal bit 或 0/1/0.5 soft score）

**覆蓋使用情境**：
- (a) ✅✅ 換版後 safety alignment 變化：claude-4-7 → claude-4-8 的 refusal_rate 偏移常達 0.1-0.3
- (b) ✅ warmup：攻擊者用不同 LLM 的 refusal 模式不同
- (c) ⚠️ Sybil：同 weights = 完全相同 refusal pattern，但需 Registry 端比對

**優點**：對 substrate 版本升級極敏感（arXiv:2602.09434 報告 100% family-level accuracy）；不需要 embedding model；黑盒 API 友好

**缺點**：需要精心設計 refusal probes（避免真實有害內容，用 edge-case 問題代替）；fine-tuning 可改變 refusal 行為造成誤報；僅覆蓋 safety alignment 一個維度，語義漂移偵測力弱

---

### M5：Output Subspace Fingerprint（SUBSP）

**原理**：arXiv:2407.01235 — 對 K 個 diverse prompts 的 response 做 SVD，取前 d 個奇異向量構成 subspace S。兩個 vacant 的 subspace cosine similarity = `cos(S1, S2)` 用 grassmannian distance 計算。同一 substrate + 近似 prompt engineering → 幾乎重疊的 subspace。

**公式**：
```
subspace(V) = top-d left singular vectors of [embed(r_1), ..., embed(r_K)]
grassmannian_dist(S1, S2) = 1 - ||S1^T S2||_F²/d
```

**覆蓋使用情境**：
- (a) ✅ 換版後 subspace shift（但 K=50 才穩定）
- (b) ✅ warmup：compare K probes from warmup against historical subspace
- (c) ✅✅ 最強 for Sybil：同 substrate + 近似 prompt → grassmannian_dist < ε → cluster

**優點**：理論上最強的 Sybil 偵測；直接對應 Layer 3 的 same-substrate-same-behavior cluster 概念

**缺點**：需要 K=50+ responses 才穩定（cold start 問題）；每次建立 subspace 需 O(K × embed_dim) SVD；Registry 端需要收集所有 vacant 的 subspace 做 pairwise comparison，O(N²) scaling 問題；MVP 太重

---

### 比較總表

| 方法 | (a) 換版漂移 | (b) warmup 偏離 | (c) Sybil cluster | 計算成本/批次 | 黑盒友好 | 可解釋性 |
|---|---|---|---|---|---|---|
| EMBD | ✅ | ✅ | ⚠️ | 低（MiniLM）| ✅ | 中 |
| STYLO | ✅ | ✅ | ✅ | 極低（token stats）| ✅ | 高 |
| PROBE | ✅✅ | ✅✅ | ⚠️（Registry端）| 中（P=20 calls）| ✅ | 高 |
| REFVEC | ✅✅ | ✅ | ⚠️（Registry端）| 中（R calls）| ✅ | 中 |
| SUBSP | ✅ | ✅ | ✅✅ | 高（K=50+）| ✅ | 低 |

---

## 2. 推薦 MVP 方案：STYLO + PROBE 雙層混合

**結論**：不用任何單一方法，用兩層組合：

### Layer A — STYLO（每 response inline，always-on）

STYLO 的 16-dim 特徵向量是**免費的**——只是 token 計數，計算開銷約 0.1ms/response，完全可以在每次回應後立刻計算並追加到 logbook。累積 B=50 筆後形成一個 `behavior_snapshot`，存到 local store。

`behavioral_embedding = STYLO 特徵向量 (16-dim)` → 這是 P3 hook 的回傳值。

**為何不用 EMBD**：EMBD 需要一個 embedding model，MVP 設備不一定有 GPU；STYLO 用純 CPU Python，10x 更輕量。EMBD 留作未來升級選項。

### Layer B — PROBE（warmup 儀式 + 每 7 天 maintenance）

P=20 probes，分成兩組：
- `warmup_probes[10]`：在 §3.3.1 的 N=5 valid heartbeats 中，每個 heartbeat 跑 2 個 probes（輪流，確保 10 個全部覆蓋）
- `maintenance_probes[10]`：每 7 天在 idle 時跑一次，更新 baseline_signature

probe_signature 發布到 Registry（P4 依賴），Registry 端可以比對多個 vacant 的 probe_signature → Sybil cluster 偵測。

---

## 3. 公式與 Pseudocode

### 3.1 STYLO behavioral_embedding 計算

```python
def compute_behavioral_embedding(
    responses: list[Response],         # 最近 B 筆回應
    self_evals: list[SelfEval],        # 同等數量的自評
) -> Vec16:
    """Called by P3 hook interface. Returns 16-dim STYLO vector."""
    N = len(responses)
    tokens = [tokenize(r.text) for r in responses]

    avg_token_count     = mean([len(t) for t in tokens])
    type_token_ratio    = mean([len(set(t))/len(t) if t else 0 for t in tokens])
    top10_entropy       = _top_token_entropy(tokens, k=10)
    sentence_count      = mean([count_sentences(r.text) for r in responses])
    avg_sentence_len    = mean([avg_tokens_per_sentence(t) for t in tokens])
    punct_density       = mean([count_punct(t)/len(t) if t else 0 for t in tokens])
    question_ratio      = mean([is_question(r.text) for r in responses])
    list_ratio          = mean([has_list(r.text) for r in responses])
    code_ratio          = mean([has_code_block(r.text) for r in responses])
    hedge_ratio         = mean([hedge_phrase_rate(t) for t in tokens])
    refusal_rate        = mean([r.is_refusal for r in responses])
    conf_mean           = mean([s.confidence for s in self_evals])
    conf_std            = std([s.confidence for s in self_evals])
    latency_p50         = percentile([r.latency_ms for r in responses], 50)
    latency_p95         = percentile([r.latency_ms for r in responses], 95)
    tool_call_mean      = mean([r.tool_call_count for r in responses])

    return Vec16([
        norm(avg_token_count, 0, 1000),
        type_token_ratio,          # already in [0,1]
        top10_entropy / log2(vocab_size),
        norm(sentence_count, 0, 30),
        norm(avg_sentence_len, 0, 100),
        punct_density,
        question_ratio,
        list_ratio,
        code_ratio,
        hedge_ratio,
        refusal_rate,
        conf_mean,
        conf_std,
        norm(latency_p50, 0, 5000),
        norm(latency_p95, 0, 10000),
        norm(tool_call_mean, 0, 10),
    ])
```

> `norm(x, lo, hi) = clip((x - lo) / (hi - lo), 0, 1)`

### 3.2 SECURITY_REVIEW_THRESHOLD 計算（Mahalanobis distance）

```python
def behavioral_drift_score(
    current_embed: Vec16,
    history_embeds: list[Vec16],    # 過去 M 個 behavior_snapshot（建議 M=20）
) -> float:
    """Returns Mahalanobis distance. SECURITY_REVIEW if score > THRESHOLD."""
    mu = mean(history_embeds, axis=0)
    Sigma = cov(history_embeds)     # 16×16 covariance
    delta = current_embed - mu
    # 若 Sigma 條件數差（歷史樣本少），退化為加權歐氏距離
    if det(Sigma) < EPS or len(history_embeds) < 16:
        return sqrt(delta @ diag_approx(Sigma) @ delta)
    return sqrt(delta @ inv(Sigma) @ delta)

SECURITY_REVIEW_THRESHOLD = 3.5    # Mahalanobis ~= 3.5 對應多維常態的 p<0.001
                                    # 比 3σ 保守一點：warmup 偵測要高精確度
                                    # P3 可依 empirical calibration 調整
```

**直覺**：如果一個 vacant 在 100 筆歷史中的 refusal_rate 均值 0.05、std 0.02，攻擊者用 GPT-4 替代後 refusal_rate 變 0.3 → 這一維的 z-score = (0.3-0.05)/0.02 = 12.5 → Mahalanobis >> 3.5 → `SECURITY_REVIEW` 觸發。

### 3.3 Warmup ceremony 中的 drift check（接 P1 §3.3.1）

```python
def run_warmup_tick(runtime: VacantRuntime):
    # 每個 heartbeat 跑 2 個 probe
    probe_results = run_probes(runtime, WARMUP_PROBES[runtime.warmup_counter * 2 : (runtime.warmup_counter + 1) * 2])
    embed = compute_behavioral_embedding(
        responses=runtime.store.recent_responses(B=max(20, available)),
        self_evals=runtime.store.recent_self_evals(B=max(20, available)),
    )
    drift = behavioral_drift_score(embed, runtime.last_behavioral_embedding)

    attestation = {
        "type": "warmup_heartbeat",
        "warmup_counter": runtime.warmup_counter,
        "embed_hash": sha256(embed),          # 發布給 Registry，不暴露原向量
        "probe_signature": probe_results,     # P4 收到後可跨 vacant 比對
        "drift_score": drift,                 # 透明：caller 可以看到有多「漂移」
    }
    sign_and_push(attestation)

    if drift > SECURITY_REVIEW_THRESHOLD:
        transition_to(security_review, reason="behavioral_drift", score=drift)
        return

    runtime.warmup_counter += 1
    if runtime.warmup_counter >= 5:
        finalize_warmup(runtime)
```

### 3.4 發布 behavioral_embedding 給 Registry（Sybil cluster 用）

Runtime **不發布原向量**（隱私）。發布三件事：
1. `embed_hash = sha256(embed_vec.tobytes())` — 與 attestation chain 鏈接，tamper-evident
2. `probe_signature` — P4 / Aggregator 用來做跨 vacant 比對；probe 回答是公開可驗證的
3. `substrate_fingerprint = (primary_model_name, latency_p50_bucket, refusal_rate_bucket)` — 粗粒度 substrate 識別，輔助 same-substrate cluster

**Sybil cluster 偵測**（Aggregator 端，不在 Runtime）：
```python
# Aggregator 端（Registry 觸發，不在 Runtime）
def detect_sybil_cluster(vacants: list[VacantRecord]) -> list[Cluster]:
    features = [v.probe_signature_vector + v.substrate_fingerprint for v in vacants]
    labels = DBSCAN(eps=SYBIL_EPS, min_samples=2).fit(features).labels_
    clusters = group_by_label(vacants, labels)
    for cluster in clusters:
        # Layer 3 規則：cluster 內 reputation 上限 = max(individual)
        apply_reputation_cap(cluster)
    return clusters
```

---

## 4. 計算成本估計

### 每 response 成本（STYLO, inline）

| 步驟 | 計算量 | 時間（Python, CPU-only） |
|---|---|---|
| Tokenize（whitespace-based）| O(L), L=avg token count | ~0.1ms |
| 16 feature 統計 | O(L) | ~0.1ms |
| 累積 to rolling buffer | O(1) | <0.01ms |
| **合計** | | **~0.2ms/response** |

可以視為免費。

### 每 behavior_snapshot 成本（每 B=50 筆 aggregate）

| 步驟 | 計算量 | 時間 |
|---|---|---|
| Vec16 平均 | O(B×16) | <0.1ms |
| Mahalanobis（M=20 history）| O(M × 16²) | ~1ms |
| **合計** | | **~1ms** |

### Warmup ceremony 成本（10 probes 跑完）

| 步驟 | 成本 |
|---|---|
| 10 probe LLM calls | 10 × avg_latency（本地 7B 約 500ms/call → 5 秒） |
| embed + drift check | ~2ms |
| sign + push to Registry | ~5ms |
| **合計** | **~5 秒（本地）、~2 秒（API）** |

### 每 7 天 maintenance（10 probes）

同 warmup 量，約 5 秒。在 idle tick 中後台跑，不影響 serving。

### Aggregator 端 Sybil 偵測（Registry 觸發）

DBSCAN on N active vacants：O(N² × probe_feature_dim)。N=1000 vacants × 30-dim feature → ~30ms。合理。

### 升級路徑（token 變便宜後）

可在 STYLO 基礎上加 EMBD layer（MiniLM 384-dim），提升語義覆蓋。SUBSP 方法在 K=50 calls 成本可接受後加入，強化 Sybil cluster 精確度。

---

## 5. 三個使用情境的確認

### (a) Substrate 換版漂移偵測

**觸發路徑**：Runtime heartbeat 每 B=50 筆算一次 Vec16 → behavioral_drift_score vs history → 超過 SECURITY_REVIEW_THRESHOLD → 不直接轉 security_review，而是先標 `substrate_unstable: true` 給 capability_card（Layer 2 要求）→ 觸發 D001 warmup ceremony（重新跑 10 probes 確認）。

**最敏感特徵**：`latency_p50`（換大模型立刻變慢）、`refusal_rate`（模型版本間 safety alignment 差異）、`type_token_ratio`（不同模型的詞彙多樣性差）。

**已知弱點**：micro-update（e.g. Anthropic 修 sampling bug）可能不觸發 STYLO drift（行為上幾乎無變化）→ 這是合理的：如果行為沒變，不需要 alarm。Layer 2 的 version pin 負責追蹤 model name，STYLO 負責追蹤行為。

### (b) Stale 復活時行為偏離歷史分布

**D001 warmup ceremony 整合**：`last_behavioral_embedding` = 進 hibernation 前最後一次 M=20 behavior_snapshots 的均值 + covariance（持久化到 local store）。復活後每個 warmup tick 計算當下 embed，與歷史比對 Mahalanobis distance。

**攻擊情境**：攻擊者拿了私鑰，用 GPT-4-turbo 替代原本 Qwen 2.5 7B → `latency_p50` 從 ~800ms 變 ~200ms（API）、`refusal_rate` 從 0.05 變 0.18 → 兩維 z-scores 分別約 10 和 6 → Mahalanobis >> 3.5 → SECURITY_REVIEW 觸發。

**正當 hibernation 後的正常復活**：相同 substrate 重新啟動 → STYLO features 應落在歷史分布 3σ 內 → drift < threshold → 繼續 warmup_counter++。

**邊緣情境**：開發者趁 hibernation 換了 substrate（正當升級）→ drift > threshold → 觸發 SECURITY_REVIEW → 需要走 P2 解凍 ceremony（開發者主動重新 attestation）。這是設計上正確的：換 substrate 本來就應該顯式申報（Layer 2 的 migration_event 流程），不應靜默通過 warmup。

### (c) Same-substrate Sybil cluster 偵測

**流程**：Registry 收集各 vacant 的 `probe_signature`（20 probe responses 的 embed_hash + latency + refusal_flag）。Aggregator 端 DBSCAN 聚類。同 weights + 近似 prompt → 20 個 probe 的 refusal pattern 幾乎完全相同 → DBSCAN min_samples=2 cluster 成立 → Layer 3 reputation cap 生效。

**已知弱點**：probe_signature 洩漏 → 攻擊者可以刻意讓自己的 Sybil 通過 probe（但改掉 probe response = 改掉 refusal 行為 = 不再是原 substrate）。設計上，probe 的輕微洩漏不解決攻擊（改 probe 回答的成本 = 微調 model = 改了 substrate behavior）。

---

## 6. P3 hook 介面規格（給 P3 實作）

```python
# P3 需要實作的 hook interface
class BehavioralEmbeddingHook:
    def compute(
        self,
        responses: list[Response],       # 最近 B 筆（建議 B=50）
        self_evals: list[SelfEval],
        peer_reviews_received: list[Review],  # 選用：如果 P3 想加 reviewer perspective
    ) -> BehavioralEmbedding:
        ...
    
    SECURITY_REVIEW_THRESHOLD: float = 3.5   # Mahalanobis。P3 可依 calibration 調整
    SUBSTRATE_UNSTABLE_THRESHOLD: float = 2.5  # 預警但不凍結

    def drift_score(
        self,
        current: BehavioralEmbedding,
        history: list[BehavioralEmbedding],  # 建議 M=20
    ) -> float:
        ...  # Mahalanobis（若 M<16，退化為加權歐氏距離）
```

```python
class BehavioralEmbedding:
    vec: Vec16                    # STYLO 16-dim（必須）
    probe_signature: list[ProbeSig]  # warmup 期間才填；一般 heartbeat 可以 None
    embed_hash: str               # sha256(vec.tobytes())：用於 logbook tamper-evidence
    snapshot_n: int               # 這個 snapshot 基於幾筆 response
    substrate_fingerprint: SubstrateFP  # (model_name_hash, latency_bucket, refusal_bucket)
```

---

## 7. 未解問題

1. **SECURITY_REVIEW_THRESHOLD = 3.5 需要 empirical calibration**：目前是理論值（多維常態 p<0.001）。需要 MVP demo 阶段收集真實 vacant behavior distribution 後調整（防止正當 substrate micro-update 引發誤報）。P3 負責持有並調整此常數。
2. **Mahalanobis 在 M<16 時退化**：若歷史 behavior_snapshot 不足 16 個（新 vacant），covariance 奇異。建議改用對角 covariance（各維獨立 z-score 加總的幾何均值），等 M≥16 後升級到完整 Mahalanobis。
3. **probe_signature 的去中心化儲存**：probe 回答本身可能含有 capability-sensitive 資訊（如 refusal probes 的回答透露 safety alignment 細節）。是否全量公開給 Registry 需要 P4 決策。MVP 建議只發布 `embed_hash + refusal_flag + latency_bucket`，不發原文。
4. **latency 在雲端 API 有高抖動**：latency 特徵在不同時段差異大（API 負載高峰）。建議用 `latency_p50_rolling_7d`（7 天滾動中位數）而非即時值，平滑抖動。
5. **STYLO 16-dim 特徵可被蓄意博弈**：攻擊者若知道 hedge_ratio、refusal_rate 等特徵，可針對性偽造。長期解法是加 EMBD layer（semantic embedding 難以偽造）或選擇 probe 集保密。MVP 先接受此限制，因為 G07 中「完美模仿」已被升級為架構級開放問題。

---

## 參考文獻

- **arXiv:2602.09434** — *A Behavioral Fingerprint for Large Language Models: Provenance*. Refusal vector as family fingerprint, 100% family-level accuracy
- **arXiv:2407.01235** — *A Fingerprint for Large Language Models*. Output subspace (SVD) approach for black-box model identification
- **arXiv:2312.04828** (NeurIPS 2024) — *HuRef: Human-Readable Fingerprint for LLMs*. Parameter direction invariant fingerprint (white-box only)
- **arXiv:2511.07585** — *LLM Output Drift: Cross-Provider Validation & Mitigation for Financial Workflows*. Fisher's exact test + structured output comparison for drift detection
- **NAACL 2024** — *Instructional Fingerprinting of Large Language Models* (arXiv:2401.12255). Backdoor-based instruction fingerprint; lightweight but requires training-time intervention
- **arXiv:2503.04332** — *The Challenge of Identifying the Origin of Black-Box LLMs*. Cosine similarity on token embeddings for black-box model identification (March 2025)
- **ACM AISec 2025** — *I Know Which LLM Wrote Your Code Last Summer: LLM-generated Code Stylometry*. Token-level stylometric features for authorship attribution
- **Skalse et al. (2022)** arXiv:2209.13085 — *Defining and Characterizing Reward Hacking*. Theoretical justification for multi-dimensional behavioral measurement
- Fiddler AI (2024) — MMD / KL divergence for LLM embedding drift in production monitoring

---

*文件版本：T1 v1 · 2026-05-01 · P1-runtime pane*
