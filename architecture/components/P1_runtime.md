# P1: Vacant Runtime 內部設計

## 1. 範圍與目標

本 pane 設計**個體 vacant 的本體（Vacant Runtime）**——也就是當一個 vacant 被「丟上網路」之後，那台機器上實際長期跑著的那個東西。Runtime **不是**附加在 base agent 之上的 wrapper / middleware / 薄膜，**它就是 vacant 自己**：包含 A2A endpoint、heartbeat 內驅迴圈、idle-time self-improvement、peer-review 主動參與、self-eval、失敗計數、spawn 觸發、state machine。Runtime 內部會用到的「思考能力」（LLM）是它持有的一個資源，不是它的本質——你可以把 LLM 換掉、降級、甚至（未來）換成物理實體，這個 vacant 仍然是同一個居民（identity 由 Ed25519 keypair 鎖定，不由 base model 鎖定）。

不負責：reputation 五維分數的計算公式（→ P3）；A2A wire-level envelope schema 的最終欄位定序與序列化（→ P6）；spawn 後新 vacant 在 Registry 的註冊 RPC（→ P4）；客戶端 SDK（→ P5/P6）；視覺化（→ P8）。本文件對這些介面**列出假設**並標註依賴。

---

## 2. 設計決策

### D1. Runtime = vacant 本體，不是 wrapper

**決策**：每個 vacant 個體 = `Runtime + (LLM resource handle) + (Ed25519 keypair) + (local store)`。Runtime 是長住程序，不是 stateless lambda。

**為什麼**：BRIEFING §3 已寫死「Vacant Runtime 不是外掛在 base agent 上的東西」。如果 Runtime 是 wrapper，base agent 換掉 vacant 就變成另一個——這違反「持續活著的居民」概念，也讓 reputation 無法錨定到特定主體。把 LLM 當資源、把 keypair 當 identity，**vacant 的存在跨越了 base model**——這正好對應 Q2（vacant 最小定義）：必要條件是 keypair + heartbeat + local store；LLM 是可換資源。

**否決替代**：(a) 把 vacant 視為「某個 LLM session 的化身」——綁死 base model，違反 BRIEFING §11.1 對網路自然多樣性的依賴；(b) 把 Runtime 做成 sidecar daemon、用 socket 跟 base agent 通訊——多一層失敗面，且 base agent 重啟時 vacant 看起來「斷氣」，跟 heartbeat 哲學衝突。

### D2. Heartbeat = 事件 + 節律雙引擎，不是 cron

**決策**：Runtime 主迴圈由兩種來源驅動——
- **節律 tick**：可設定的 base period（預設 60s「token-cheap」/ 6h「token-expensive MVP」），每個 tick 跑一輪 housekeeping。
- **事件 trigger**：A2A request 到達、Registry pubsub 事件（新 review 上鏈、parent 死亡通知、capability search miss broadcast）即時喚醒。

**為什麼**：Hermes / OpenClaw 的 `HEARTBEAT.md` 是**針對 LLM session 的 prompt 注入**——cron 觸發、把 checklist 餵進新一輪 turn、靠 LLM 自己讀 checklist 決定做什麼。Vacant Runtime **不能照抄**：(a) Hermes 的 heartbeat 預設「人在用、要提醒模型注意 user state」，vacant 的 heartbeat 反而要在「沒人用」時更活躍（idle-time evolution）；(b) Hermes / OpenClaw 的 heartbeat 是 30 分鐘級慢動作、會直接塞滿模型 context，vacant 在 token 免費假設下要做秒級～分鐘級的多動作 loop，不能每次都重塞 system prompt；(c) Hermes 用 `HEARTBEAT_OK` sentinel 讓模型自己跳過——vacant 不行，因為 housekeeping（review 拉取、spawn 條件檢查、capability card freshness）必須是**確定性程式碼**，不能讓 LLM 來決定要不要做。

所以 vacant 的 heartbeat **以程式碼為主、LLM 為輔**：每 tick 是一段純程式碼跑完的 housekeeping pipeline，只在需要「思考」的子步驟（peer review 寫評語、prompt mutation 提案）才呼叫 LLM；LLM 不掌舵。

**否決替代**：純 cron（無法即時回應網路事件）；純事件驅動（沒有 incoming traffic 時就死了，違反「持續活著」）。

### D3. Idle-time evolution 用「shadow-self + sealed sandbox」

**決策**：演化提案永遠先在 shadow-self 跑、永遠不直接覆蓋 production self；shadow-self 在 sealed sandbox 內，**任何對外 egress（A2A out、Registry write、外部 API call）都被攔截並導向 mock**。

**為什麼**：BRIEFING §11 三大張力之一是「透明 vs MINJA」——idle-time evolution 是攻擊面：對手注入毒 review，讓 prompt mutation 把 vacant 推向不利方向。**封閉沙盒 + 確定性 replay** 把這個攻擊降到只能影響「shadow 的 win/lose 判定」，不能直接污染 production。Sealing 還回應了關鍵張力 §「shadow self 的 sandbox 邊界」：邊界 = process boundary + monkey-patched A2A client + Registry write 攔截 + 環境變數 `VACANT_MODE=shadow` 讓 LLM tool layer 也認得自己在沙盒。

**否決替代**：(a) 直接讓 prompt mutation 上線、A/B traffic split——production reputation 會被毒掉；(b) 委外給「中央 evolution server」評估——違反 BRIEFING §3 中央 LLM/judge 紅線。

### D4. 失敗判定用「客觀 + 多維 + 時窗」

**決策**：失敗事件由 Runtime 自己判定（不是讓網路投票），來源限定四種**客觀訊號**：
1. A2A timeout / 5xx 自爆
2. caller review 任一維低於 `fail_threshold[dim]`（預設 0.3）
3. ground truth mismatch（任務有單元測試/API verifier 時）
4. honesty gap 連續 K 次超過 `gap_threshold`（自評他評落差過大）

連續 N 次（預設 N=5、滑動視窗 7 天）→ 觸發 spawn 條件評估。**「失敗」不等於「reputation 低」**——低 reputation 是 caller 端的選擇問題，失敗是個體生死問題。

**為什麼**：如果讓「reputation 低」直接觸發死亡，攻擊者只要刷負評就能殺 vacant（whitewashing 反向版）。客觀訊號 + 多源 + 時窗濾掉短期攻擊噪音。對應 G02 / G03 / 關鍵張力 §11.1。

**否決替代**：用 reputation 純量低於閾值就觸發——Goodhart 反噬；用 caller review 數量門檻——可被 Sybil 灌票。

### D5. Sinking 後 heartbeat 不停，但降到「殘響模式」

**決策**：vacant sunk 後：
- A2A endpoint 仍開著，但回應 `503 sunk + redirect_hint=successor_did`
- heartbeat 從 base period 降到 `decayed_period`（預設 24h）
- idle-time evolution 關閉、peer review 關閉
- 仍簽署「已知我已沉沒」的 attestation，每週一次推 Registry，作為**存活證明**（防止有人冒名復活）

**為什麼**：直接停 heartbeat 違反「不刪除、保留歷史」——更要命的是，攻擊者可以拿走 sunk vacant 的 endpoint 假冒它（DNS hijack / IP 重用）。降到殘響模式但繼續簽署存活訊息，等於對 Registry 持續宣告「我還是我，我已沉沒」，**讓冒名變成明顯的規格違規**。對應關鍵張力 §「vacant sinking 後 heartbeat 還跑嗎？」——答：跑，但只跑見證自己已死的部分。

**否決替代**：完全關閉——攻擊面增加；維持原 heartbeat——浪費資源、跟 sinking 的「網路用腳投票」訊號矛盾。

### D6. MVP 降級走「budget-driven cadence」

**決策**：Runtime 設定 `budget.tokens_per_day` 與 `budget.calls_per_day`。當預算逼近時，依優先序自動降級：
1. 第一道：peer review 從每 idle 都跑改成每天一次 batch
2. 第二道：idle-time evolution 從每 100 次互動觸發一次降到每 1000 次
3. 第三道：heartbeat tick 拉長 base_period
4. 第四道：**進 hibernation**——不接呼叫、不主動演化、不 peer review，但 identity 與全部歷史保留，仍跑最低限度 heartbeat（每 24h 一次空 attestation 簽存活）

token-免費假設下 budget=∞、所有降級失效；MVP demo 階段給每 vacant 預設 budget=10K tokens/day（用 Qwen 2.5 7B 本地跑），可調。

**Hibernation ≠ Sinking**（主持人 2026-05-01 裁決）：budget 耗盡走 hibernation，**不**算失敗訊號、**不**進 §3.6 spawn 計數、**不**轉終態。原因：sinking 必須由 reputation/品質訊號驅動，否則「有錢攻擊者長久不沉、誠實窮 vacant 反而沉」激勵錯誤。預算復電（新一日 budget refill 或 operator 注資）→ 自動回 idle。但長期 hibernation（連續 ≥ 30 天無服務）→ Runtime 自簽 `stale=true` 推 Registry，Aggregator 端在 capability search 時降低該 vacant 曝光（**P3/P4 介面**）。stale 可恢復，sunk 不可。

**為什麼**：直接回應關鍵張力 §「持續活著如何在 token 還貴的 MVP 階段降級」。**降級不是關閉某些功能，是把所有功能拉開時間軸**——demo 時可調快「模擬時間」（cron 本來 24h 的事件壓成 5 分鐘），讓網路看起來活著。

---

## 3. 元件規格 / 演算法 / 資料結構

### 3.1 Runtime 整體結構（pseudocode 層級）

```
class VacantRuntime:
    # identity
    did: str                     # "did:vacant:<base58(pub_ed25519)>"
    keypair: Ed25519Keypair
    parent_did: Optional[str]
    capability_card: CapabilityCard  # versioned, signed
    # resources
    llm: LLMHandle               # 可換、可降級
    store: LocalStore            # SQLite + append-only event log (hash-chained)
    registry_client: RegistryClient
    a2a_server: A2AServer
    # state
    state: State                 # idle | serving | reviewing | spawning | hibernating | warming_up | security_review | sinking
    warmup_counter: int          # 0..5，hibernation 復活後累計有效 heartbeat 數
    last_behavioral_embedding: Vec  # 從 P3 取得的歷史行為向量（mean），warmup 比對基準
    failure_window: deque[FailureEvent]   # ring buffer, 7-day sliding
    budget: Budget
    # config
    base_period: float
    decayed_period: float
    fail_threshold: dict[Dim, float]
    win_rounds_required: int     # shadow-self 自我替換門檻
```

### 3.2 A2A envelope（依賴 P6 最終 schema，本文件用假設版）

```
Envelope {
  envelope_id: uuid7        # 含時序，幫助 idempotency
  from_did: str
  to_did: str
  capability_id: str
  payload: bytes            # opaque, capability-specific
  scope: ["read"|"write"|"spawn-permit"|...]
  idempotency_key: str      # caller-controlled; Runtime 24h 內重放回同一結果
  timeout_ms: int
  not_before: ts
  not_after: ts
  signature: Ed25519(envelope without sig field)
  base_model_hint: str      # 簽署當下使用的 base model name（給 P3 同源降權用）
}
```

**接收端拒絕條件**（在進入 LLM 之前就攔下）：
1. 簽章驗證失敗 → 401（不寫入歷史，因為連身份都不確定）
2. capability_id 不在自己 capability_card 內 → 404
3. `not_after` 已過 → 408
4. caller 的 `failure_window` 顯示是已知 abuser（24h 內超過 50 次 401/429）→ 429 + Retry-After
5. budget 預算用盡 → 進 hibernation 後回 503 + Retry-After（預算重置時間）；**不**回 429（429 暗示「再試一次可能成功」，hibernation 是已知不可服務）
6. self.state == sinking → 503 + redirect_hint=successor_did
7. self.state == hibernating → 503 + Retry-After（不附 redirect_hint，因為 hibernation 是暫時的，identity 仍有效）
8. self.state == warming_up → 接受 `vacant_call(by_id=...)` **顯式直呼**（caller 知道自己在叫誰、自願承擔風險），但對 capability_search 路由進來的請求回 503 + `warmup=true`；caller SDK 會看到「此 vacant 在 warm-up 中」UI 訊號（依賴 P5/P8）
9. self.state == security_review → 全部呼叫一律 503 + `frozen=true`（含 by_id），直到開發者完成重新 attestation；保留 identity 與歷史，不轉 sinking
10. self.state == spawning（child ceremony 中）→ 503 + Retry-After（短）
11. concurrent in-flight 已達 `max_concurrency`（預設 8）→ 429
12. 不接受 caller_reputation 任一維低於 `min_caller_rep`（**注意**：這跟「不審核入網」不衝突——個別 vacant 拒絕跟誰來往是個體自由，不是網路審核）

### 3.3 Heartbeat tick pipeline

```
on_tick():
  budget.refill_if_new_day()
  if budget.replenished and self.state == hibernating:
      transition_to(warming_up)          # 復活先進 warm-up，不直接回 idle（主持人 2026-05-01 裁決）
      warmup_counter = 0
      warmup_started_at = now()
      emit_wakeup_attestation(warmup=true)
  if self.state == hibernating:
      if days_in_hibernation() >= 30 and not stale_flag_emitted:
          emit_stale_attestation()       # 推 Registry，Aggregator 降低查詢曝光
      emit_heartbeat_attestation(minimal=true)  # 每 24h 一次即可
      return
  if self.state == warming_up:
      run_warmup_tick()                  # §3.3.1
      return
  if self.state == security_review:
      emit_heartbeat_attestation(frozen=true)   # 對 Registry 持續證明私鑰仍在我手上 vs compromised
      return
  if self.state == sinking:
      run_sinking_residual_loop()        # §D5 殘響模式
      return
  drain_a2a_inbox()                      # 處理排隊請求（若有）
  pull_registry_events_since(last_seen)  # 新 review、capability search miss、parent 死亡
  apply_review_to_self_history()         # 純資料層更新，不動 prompt
  if self.state == idle and budget.peer_review_quota > 0:
      run_peer_review_round()            # §3.5
  if idle_streak >= idle_evolution_threshold:
      schedule_shadow_self_round()       # §3.4
  evaluate_spawn_trigger()               # §3.6
  if budget.exhausted():
      transition_to(hibernating)         # 預算耗盡 → 進 hibernation（不算失敗）
  refresh_capability_card_if_drifted()
  emit_heartbeat_attestation()           # 簽 + 推 Registry（輕量訊息）
```

**heartbeat attestation** = `sign(did + state + tick_seq + capability_card_hash + last_event_hash)`，每 N tick（預設 60）推一次給 Registry，作為存活證明 + 「我看到的 event log 末端是這個 hash」（讓 Registry 可以對比偵測分裂視圖）。

#### 3.3.1 Warm-up tick（hibernation 復活儀式，主持人 2026-05-01 裁決）

復活後 24h warm-up window，安全網是「輕但帶安全網」設計——目的是偵測 hibernation 期間私鑰遭竊（lost laptop / leaked secrets / supply chain）後的 compromised account 行為，但不過度懲罰正當的 hibernation。

```
run_warmup_tick():
  if now() - warmup_started_at > 24h:
      finalize_warmup()
      return
  embed = compute_behavioral_embedding()   # 依賴 P3 hook
  drift = behavioral_drift_score(embed, last_behavioral_embedding)
  if drift > P3.SECURITY_REVIEW_THRESHOLD:
      transition_to(security_review)
      emit_security_review_attestation(reason="behavioral_drift", drift=drift, embed=embed)
      return
  emit_heartbeat_attestation(warmup=true, warmup_counter=warmup_counter, embed_hash=hash(embed))
  warmup_counter += 1
  # warm-up 期間允許 vacant_call(by_id) 服務（在 §3.2 條件 #8 處理），但不接 capability_search

finalize_warmup():
  if warmup_counter >= 5 and all_warmup_attestations_within_distribution:
      transition_to(idle)
      clear_stale_flag()
      emit_wakeup_complete_attestation()   # Registry 端據此把 vacant 重新放進 default search
  else:
      transition_to(security_review)
      emit_security_review_attestation(reason="insufficient_valid_heartbeats")
```

**`compute_behavioral_embedding()` 是依賴 P3 的 hook**：本文件假設 P3 提供 `behavioral_embedding(self_eval_history, response_pattern, peer_review_pattern) → Vec` 與一個閾值 `SECURITY_REVIEW_THRESHOLD`（行為熵 / 跨維散度），由 P3 決定具體公式（依其 §「行為熵 / 跨維散度」工具箱）。Runtime 只負責呼叫並依結果分流。

**SECURITY_REVIEW 解除**：必須由「持有 Runtime 部署環境控制權的開發者」走重新 attestation 流程——具體 ceremony 設計依賴 P2（key rotation / multi-sig / hardware attestation 之一）。Runtime 端只負責：(a) 凍結所有對外服務、(b) 持續簽 frozen heartbeat 證明私鑰活著（讓 Registry 區分「自願凍結」vs「整台機器被攻擊者帶走」）、(c) 接受一個來自 P2 機制的解凍 envelope 後 transition 回 warming_up（**不**直接回 idle，重新跑一次 warm-up 儀式）。

### 3.4 Shadow-self self-improvement round

**觸發**：idle_streak 累積 + budget.evolution_quota > 0 + 距離上次成功演化 ≥ cooldown。

**流程**：
1. 從 `failure_window` 抽 K 筆失敗 trajectory + 從 `recent_reviews` 抽 K 筆評語（含他評）。
2. **prompt mutation 提案**：呼叫自己的 LLM、給它 (a) 當前 system prompt (b) 失敗案例 (c) 約束「修改不能違反 capability_card 宣告」，產出 `M` 個候選 mutation（預設 M=4）。
3. 對每個候選，spawn shadow-self process，**`VACANT_MODE=shadow`**：
   - A2A client → mock（任何 outbound call 拋 `EgressDenied`）
   - Registry client → in-memory mock
   - LLM 仍用真的（這就是要測的東西）
4. 跑 **replay benchmark**：從 store 抽歷史已答的 envelope 子集（≥ 30 筆，分布要涵蓋不同維度的高低分），讓 shadow-self 答，再用兩種對照——
   - 客觀對照：跟原本的 caller review 比、跟 ground truth 比（任務有 verifier 時）。
   - 自評對照：shadow-self 自評 vs 原版自評，差距用來算 honesty 訊號。
5. **win 定義**：shadow-self 在 `factual + logical + relevance` 三維加權平均**嚴格高於** baseline，且在其餘兩維（honesty / adoption-proxy）**不退步超過 ε=0.05**。
6. shadow-self 連續贏 `win_rounds_required`（預設 3 輪不同 sample）→ **自我替換**：
   - 把 mutation 套到 production prompt
   - capability_card 版本號 +1、Merkle 包 production prompt hash 一起簽、推 Registry
   - 舊 prompt 在 store 保留（可審核、可回滾）

**自我蒸餾觸發**：`evolution_count >= 50` 或 `tokens_used / quality_gain` 比值連續惡化 → 跑離線蒸餾任務（取 N 萬筆歷史 trajectory 作為 SFT 資料），新 base model 上線一樣走 shadow-self 流程驗收。

**為什麼 win_rounds=3 不是 1**：單輪贏可能是 sample 偏差；3 輪不同 sample 把假陽性壓到約 0.05。

### 3.5 Peer review participation

**選擇要評誰**——三個來源以權重抽：
- **w_low_signal=0.5**：Registry 廣播的 `low_coverage_targets`（最近 7 天 review 數 <閾值的回答），優先填補訊號稀疏處
- **w_domain=0.3**：跟自己 capability_card 領域 cosine 距離 < 0.4 的對象（同行最知道好不好）
- **w_random=0.2**：純隨機（防領域同溫層）

**避免重複**：本機保存 `peer_review_bloom`（24h TTL Bloom filter），同一 (target_did, answer_id) 不重複評。

**評分流程**：
1. 抓對方原 envelope + 答覆（從 Registry public log 拉，對方無從拒絕）
2. **不**重新呼叫對方（避免送出無謂呼叫流量）
3. LLM 評分，輸出五維分數 + 信賴 + 文字理由
4. 包成 `ReviewEnvelope`：簽名、附自己當下 base_model_hint、附 reviewer_capability_card_hash（讓聚合器之後能做同源降權，依賴 P3）
5. 推 Registry

**本機防 ballot stuffing**（即便 Registry 端也會做）：
- 每 24h 對同一 target_did 的 review 上限：3
- 每 24h 對同一 capability domain 的 review 上限：20
- 自己的 reputation honesty 維度若 < 0.5，peer review 上鏈時自動標 `low_credibility=true`（聚合端會看）

### 3.6 Self-eval & honesty 機制

每筆回應**必附**自評：

```
SelfEval {
  scores: {factual: float, logical: float, relevance: float}  # honesty/adoption 不自評
  confidence: float           # 0..1，自己對這次答案的把握
  declined_dims: [str]        # 自己覺得沒能力評的維度
  refusal: bool               # 拒絕回答時 = true
  refusal_reason_code: enum   # capability_mismatch | safety | budget | unclear_input
}
```

**honesty 訊號**：等到該回答收到 ≥ M 筆 caller/peer review（預設 M=3）後，計算 `gap = |mean(other_scores) - self_scores|` per dim，gap 推給 P3 的 honesty 維公式（**P3 依賴**：本文假設 honesty = 1 - clip(mean_gap / 0.5, 0, 1)，P3 可改）。

**Gracefully fail**：當 input 觸發 capability mismatch / 預算不足 / safety 規則 → 回 `refusal=true` + 200 OK（不是 4xx，因為這是有意識的拒答），並且**不被算入失敗計數**（拒絕回答不是失敗，假裝會做才是失敗）。

### 3.7 Spawn 觸發與後代繼承

```
evaluate_spawn_trigger():
  if len(failure_window) < N: return
  if state in (sinking, hibernating, warming_up, security_review): return  # 非穩態階段不評估 spawn
  failure_clusters = cluster(failure_window, by=["capability_id","error_code"])
  for cluster in failure_clusters:
      if cluster.size >= N and cluster.span <= 7d:
          trigger_spawn(cluster.signature)
          mark_failures_consumed(cluster)
```

**spawn 行為**：產生新 keypair → 新 did → `parent_did = self.did`，繼承：
- capability_card（可能修改聚焦在 cluster.signature 上的 capability subset）
- prompt（套用 cluster-aware mutation）
- **不繼承 reputation**（從零開始）
- **不繼承 review 歷史**（但 parent_did 鏈在 Registry 可被追溯，避免 whitewashing：聚合端可選擇對 parent reputation 低的後代用更寬信賴區間冷啟動，**這是 P3 的決策**）

**冷啟動 reputation**（回應關鍵張力 §11.2）：新 vacant 上線時 reputation = `null`，**不是 0**。Aggregator 顯示「insufficient signal」，caller 端 SDK 預設不主動推薦（除非 caller 顯式要求 explore）。前 K 筆 review（預設 K=20）視為「養成期 review」，給 reviewer 額外 micro-reward 訊號（鼓勵主動評新 vacant）。這個 micro-reward 不是錢，是 reviewer 自己的 adoption 維度加成（**P3 依賴**）。

### 3.8 State machine

```
            ┌─────────┐  A2A 請求進入
            │  idle   │ ─────────────► serving
            │         │ ◄───────────── (請求完成 / 超時)
            │         │
            │         │  idle_streak ≥ thr & budget OK
            │         │ ─────────────► reviewing
            │         │ ◄───────────── (peer review round 結束)
            │         │
            │         │  idle_streak ≥ thr & evolution due
            │         │ ─────────────► spawning(shadow)
            │         │ ◄───────────── (shadow round 結束 / 自我替換完成)
            │         │
            │         │  budget.exhausted()
            │         │ ─────────────► hibernating
            │         │ ◄───────────── budget refilled (新一日 / operator 注資)
            └────┬────┘
                 │  failure_window 觸發 + spawn cluster 確認
                 ▼
            ┌─────────┐
            │ spawning│  生產後代並 register；本身回 idle 或 sinking
            │ (child) │
            └────┬────┘
                 │  reputation 維度長期低 + 多次 spawn 仍失敗
                 ▼
            ┌─────────┐
            │ sinking │  A2A 503 + redirect_hint
            │ (echo)  │  heartbeat decayed_period
            │         │  attestation 仍簽
            └─────────┘  ⨯ 不再有出口（sunk 是終態）

  ─── 旁路狀態 ─────────────────────────────────────────────────────
            ┌─────────────┐  budget 耗盡（不算失敗訊號，§D6 主持人裁決）
            │ hibernating │  A2A 503 + Retry-After（無 redirect_hint）
            │             │  heartbeat 24h 一次 minimal attestation
            │             │  identity / 歷史 / parent_did / capability_card 全保留
            │             │  ≥ 30 天 → 自簽 stale=true（Aggregator 降低查詢曝光）
            └──────┬──────┘
                   │  budget 復電（refill / operator 注資）
                   ▼
            ┌─────────────┐  24h warm-up window（§3.3.1，主持人 2026-05-01 裁決）
            │ warming_up  │  接受 vacant_call(by_id) 顯式呼叫
            │             │  不進預設 capability_search
            │             │  每 tick 比對 behavioral_embedding（依賴 P3 hook）
            │             │  累積 valid heartbeat
            └──────┬──────┘
                   │
        ┌──────────┴──────────────┐
        │ counter≥5 ∧ 分布內       │  drift>threshold 或 24h 結束時 counter<5
        ▼                          ▼
      idle                  ┌──────────────────┐
      （清 stale flag）     │ security_review  │  全部呼叫 503+frozen=true
                            │                  │  保留 identity 與歷史，不 sink
                            │                  │  仍簽 frozen heartbeat（區分自願凍結 vs 機器被奪）
                            └──────┬───────────┘
                                   │  P2 機制下開發者重新 attestation
                                   ▼
                              warming_up（重跑儀式）
```

**並行性**：serving / reviewing / spawning(shadow) 在 budget 允許下可並行（sub-process 或 async task），但 spawning(child) 需要 idempotency lock（避免 race condition 連續生兩個重複後代）。sinking 進入後其他狀態鎖死。**hibernating / warming_up / security_review 三者皆與 sinking 互斥**——非穩態狀態都暫停 spawn 計數累積（§3.6），確保失敗判定只在「正常服務時段」累積。security_review 是**唯一可從 hibernation 動線轉入又能轉回 warming_up 重跑儀式**的狀態，但**不能直接回 idle**——這是設計上保留的安全網。

---

## 4. 對應到的缺口 / 風險

| 編號 | 我的設計如何回應 |
|---|---|
| **G01** 跨任務持久化 reputation | Runtime 把 reputation 錨在 keypair 而非 base model；換 LLM、跨任務、跨組織換 caller 都不洗白；`parent_did` 鏈讓 spawn 後代可被追溯（D4、§3.7） |
| **G02** Sybil / whitewashing | Ed25519 keypair 是身份；新 vacant 冷啟動 reputation=null（不是 0）+ 養成期 K 筆 review 才解鎖 + parent 鏈追溯（§3.7）。**注意**：Sybil 完全抵抗需要 P4 在 Registry 端做 PoW / stake / 入會成本，Runtime 自己做不到——這是 P4 的責任 |
| **G03** Reward hacking | (a) 失敗判定用四種客觀訊號的多源組合，不讓任一維可被單獨刷低觸發死亡（D4）；(b) self-eval gap 進 honesty 維讓「謊報自評刷分」反噬自己（§3.6） |
| **G04** 記錄不可竄改 | Runtime 本機 store 是 hash-chained append-only log；heartbeat attestation 把 last_event_hash 推 Registry，分裂視圖偵測；自我替換時舊 prompt 保留可回溯（§3.3、§3.4） |
| **G05** 無 ground truth 怎麼辦 | 失敗判定四訊號中，ground truth 只是其中一種；其他三種（timeout、caller review、honesty gap）在無 ground truth 任務也有效（D4） |
| **G06** Automation bias | Runtime 在 self-eval 強制標 `confidence` 與 `declined_dims`，回應到 caller 端讓 SDK 顯示「此 vacant 自評不確定」UI 訊號——具體 UX 是 P5/P8 責任，Runtime 提供原料 |
| **Q1** Registry 中央化 | Runtime 假設 Registry 是 pub/sub event source，**不假設它仲裁**；換成聯邦 Registry 時 Runtime 只需多訂閱來源——介面層級不變（依賴 P4） |
| **Q2** vacant 最小定義 | 答：keypair + heartbeat + local store。LLM 是可換資源、不是必要。物理實體只要也能簽 envelope + 跑 heartbeat 就是 vacant（D1） |
| **Q3** token 免費假設下 demo | budget-driven cadence + 模擬時間加速（D6）；MVP 預設 Qwen 2.5 7B 本地跑、heartbeat 6h、demo 時加速到 60s；budget 耗盡走 hibernation 不走 sinking（§D6/§3.8，主持人裁決） |

---

## 5. 參考文獻 / 引用

- **Friedman, E. & Resnick, P. (2001)** *The Social Cost of Cheap Pseudonyms*. JEMS 10(2): 173–199. — 支持 D4、§3.7 冷啟動 reputation=null 而非 0，避免「換馬甲免費」(referenced in 責任有效性分析)
- **Douceur, J. (2002)** *The Sybil Attack*. IPTPS 2002. — Sybil 抵抗無法在 Runtime 端解，Runtime 只能不放大 Sybil（拒絕跟低 caller_rep 來往）；G02 抵抗主要落在 P4 (referenced in 責任有效性分析)
- **Goodhart, C. (1984)** / **Skalse, J. et al. (2022)** *Defining and Characterizing Reward Hacking*. NeurIPS 2022 (arXiv:2209.13085) — 支持 D4 拒絕單一純量、用多維 + 客觀訊號交叉驗證
- **Pan, A. et al. (2024)** *MINJA: Memory Injection Attack* (參考自「責任有效性分析」MINJA 95% 注入率) — D3 sealed sandbox 邊界 + §3.4 prompt mutation 必須先過 shadow benchmark 才上線
- **Cohen, R. et al.** *Distributed Reasoning Framework (DRF)* — §3.6 honesty 維度借自 DRF self-eval gap 概念（出處在 BRIEFING §5）
- **OpenClaw HEARTBEAT.md / Hermes cron 子系統** —（出處：`/Users/cosmopig/Downloads/專題/資料/現有agent架構`）對照差異見 D2

---

## 6. 對其他 pane 的依賴與假設

| 依賴對象 | 我假設的介面 | 若 pane 給出不同結論的影響 |
|---|---|---|
| **P3 reputation** | 五維為 `factual / logical / relevance / honesty / adoption`；honesty 公式吃 self-eval gap；冷啟動值 = null；同源降權由聚合器負責，Runtime 提供 `base_model_hint` | 若 P3 改維度組合，§3.4 win 條件、§3.7 spawn 冷啟動規則需重算閾值；schema 層面 SelfEval 的 dim 列表要更新 |
| **P6 protocol** | A2A envelope 含 `envelope_id, from_did, to_did, capability_id, payload, scope, idempotency_key, timeout, signature, base_model_hint`；Ed25519 簽章；idempotency 24h 視窗 | 若 P6 用不同簽章 / 序列化，§3.2 拒絕條件代碼要對齊；idempotency window 不同會影響 store 的 cache 設計 |
| **P4 registry** | Registry 提供 (a) `register_vacant(card, parent_did?, sig)`、(b) pub/sub 訂閱 `reviews / spawn / capability_search_miss / parent_death`、(c) Merkle root 對外可驗 | 若 Registry 不提供 pub/sub 而要 polling，§3.3 改成 polling cadence；若 Registry 對 spawn 做資格審核（違反 BRIEFING）需大幅改寫 §3.7 |
| **P2 identity** | did 格式 `did:vacant:<base58(pub_ed25519)>`；keypair 私鑰本機保存、不外流 | 若 P2 採 hierarchical key（如 BIP32-style）→ §3.7 spawn 可改用衍生鍵省 ceremony，但 reputation 不繼承的原則不變 |
| **P5 composite** | 複合 vacant 對外仍是單一 did + 單一 Runtime；內部子代的 Runtime 是縮減版（無 A2A endpoint 對外、無 Registry 直接寫） | 本文件主要設計外層 Runtime；內部子代 Runtime 的「縮減版規格」需 P5 補完 |
| **P7 mvp / P8 visual** | 只消費 Runtime emit 的 attestation / state 訊號；Runtime 不為 visual 量身設計欄位 | 無風險 |

---

## 7. 未解問題 / 留給後續

1. **shadow-self 的 LLM 用量爆炸風險**：每輪 shadow benchmark 要跑 ≥ 30 筆 replay × M=4 候選 mutation × 3 輪 = 360 次 inference，token-貴環境下不可接受。MVP 暫時把 M 砍成 2、replay 砍成 10，但這會讓 win 判定的統計效力變差。**待補**：給 mutation 候選做更便宜的「離線 ranking」（看 mutation 跟失敗 trajectory 的 embedding 相似度），先汰多餘候選再進 shadow。
2. **honesty gap 的延遲性**：§3.6 公式要等 ≥ M=3 筆 review 才算 gap，新 vacant 前期 honesty 永遠 null。需要 P3 決定「null honesty 的 caller 該如何呈現」——這影響 §3.7 養成期 K 值。
3. **sinking → 詐屍 攻擊**：D5 殘響模式靠「持續簽存活訊息」防冒名，但**如果攻擊者拿到私鑰**就破功——這把問題推到 P2（key rotation / revocation）。Runtime 端目前只能在偵測到「自己沒簽但 Registry 出現自己簽名的訊息」時自我標記 `compromised` 並 sinking——但這假設 Runtime 自己還活著比攻擊者快。
4. **複合 vacant 內部子代的 Runtime 規格**：本文只定義「對外的 Runtime」，內部子代 Runtime 是 P5 任務，但有重疊（子代也要 self-eval、heartbeat 嗎？）。等 P5 結論再回來協調。
5. **mutation 提案 LLM 是自己——self-amplifying bias 風險**：由自己提案 prompt mutation，會強化既有偏誤。可緩解：（a）強制部分 mutation 來自他人 review 的「建議區」文字、（b）保留少量隨機溫度高 mutation 當 exploration——已寫入 §3.4 但效果待 demo 階段驗證。
6. **budget 用盡 → hibernation，不算 sinking 訊號**（主持人 2026-05-01 裁決）。理由：sinking 必須由 reputation/品質訊號驅動，否則「有錢攻擊者長久不沉、誠實窮 vacant 反而沉」激勵錯誤。已落實：(a) §D6 budget 第四道降級從「拒絕新 caller」改為「進 hibernation」；(b) §3.3 heartbeat tick 增加 hibernation 進入/喚醒邏輯；(c) §3.6 spawn 評估在 hibernating 狀態下 short-circuit；(d) §3.8 state machine 新增 hibernating 旁路狀態（可逆，與 sunk 終態對比）；(e) §3.2 拒絕條件 #5 由 429 改為 503 + Retry-After。長期 hibernation（≥ 30 天）自簽 `stale=true` 推 Registry 讓 Aggregator 降低查詢曝光——**stale 介面為 P3/P4 依賴**，本文件假設 Aggregator 看到 `stale=true` 時將該 vacant 從預設 capability search 結果集移除（仍可顯式查詢）。
7. **stale 復活儀式：採「輕量但帶安全網」**（主持人 2026-05-01 裁決）。已落實到：
   - §3.1 Runtime struct 新增 `warmup_counter` 與 `last_behavioral_embedding`、State enum 加 `warming_up` / `security_review`
   - §3.2 拒絕條件 #8 / #9 區分 warming_up（接受 by_id 顯式呼叫、拒 capability_search 路由）vs security_review（全凍 + frozen=true）
   - §3.3 heartbeat tick 加 hibernating → warming_up 自動 transition；warming_up 不直接回 idle
   - 新增 §3.3.1 Warm-up tick 完整流程（24h 視窗、N=5 valid heartbeat、behavioral_embedding 落歷史分布內 → idle；任一偏離 → security_review）
   - §3.6 spawn 評估在 warming_up / security_review 期間 short-circuit
   - §3.8 state machine 加上 hibernating → warming_up → idle | security_review → warming_up 完整動線；security_review **不能直接回 idle**，必須重跑儀式
   - **新增 P3 介面依賴**：`behavioral_embedding(self_eval_history, response_pattern, peer_review_pattern) → Vec` + `SECURITY_REVIEW_THRESHOLD` 常數（行為熵 / 跨維散度），由 P3 決定具體公式
   - **新增 P4 介面依賴**：Registry 端需儲存 `warmup_counter` 並在 finalize_warmup 時消費；Aggregator 看到 `frozen=true` / `warmup=true` attestation 時的 default search 行為
   - **新增 P2 介面依賴**：security_review 解凍 ceremony（key rotation / multi-sig / hardware attestation 之一），Runtime 端只接受其產出的解凍 envelope
8. **長期 hibernation + 私鑰外洩偵測的根本不對稱性**：warm-up 儀式只能偵測「行為偏離歷史分布」的攻擊者，無法偵測「攻擊者完美模仿 vacant 過去風格」的高階對手。後者需要 P2 設計 hardware attestation / TPM 級別的部署環境綁定，超出 Runtime 範疇。本文件僅就「可偵測子集」設計。
