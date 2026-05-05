# Vacant — 完整理論 v4

> v4 是把 v3 的 9 層架構交叉外部證據後的硬化版本。**沒有 layer 垮塌**（這是好消息），但有 1 個公式 bug 修正、4 個 hand-wave 升級成具體機制、5 個硬問題從定性升級為定量、整個 Layer 1 用 Ricoeur 框架重寫。
>
> 引用：T1–T7（research/T*.md）+ 8 份 component spec（components/P*.md）+ codex jobs。

---

## 0. v3 → v4 變更總覽

| 變更類型 | 項目 | 來源 |
|---|---|---|
| **Bug 修正** | portability_factor 公式：`0.7 + 0.3 × p` → `0.3 + 0.7 × p`（內部不一致） | T3 |
| **Hand-wave → 機制** | Layer 1 logbook 升級為 Ricoeur idem/ipse/character 三維 | T6 |
| **Hand-wave → 機制** | Layer 2 behavioral_embedding 具體化為 STYLO + PROBE 雙層（Vec16 + Mahalanobis 3.5） | T1 |
| **Hand-wave → 機制** | Layer 3 same-controller 偵測為三層串行篩選（宣告 → cross-corr → cosine） | T5 |
| **Hand-wave → 機制** | Layer 3 discount rollover 從固定 0.6 升級為 STYLO_distance 動態函數 | T1 + T6 |
| **定性 → 定量** | H1：「三年內不確定」→「2026 窄域已可行、2029 routine very probable」 | T2 |
| **定性 → 定量** | H2：「閉源服務脆弱性」→「captive_ratio 2026 55-70% → 2030 10-20%」 | T3 |
| **定性 → 定量** | H4：「靠少數 bootstrapper」→「2-of-5 MVP → 3-of-9 federated，3-5 年演進」 | T4 |
| **新增** | Layer 5 cold-start + substrate-change 邊界 fallback (rollover 0.35 + flag) | T6 |
| **新增** | Layer 9 加 substrate_sla_tier + h2_exposure_index 公開指標 | T3 |
| **新增** | 經濟層 MVP→V1→V2→V3 四階段演進路徑 | T7 |

---

## 1. 核心定義（Ricoeur 框架版）

**Vacant 是一種居民形式（resident form）。** 你選擇變成它，沒人強制。

一個 vacant 由六樣構件組成，按 Ricoeur (1990) "Oneself as Another" 的人格同一性區分：

```
vacant := {
  identity (idem):      Ed25519 keypair（vacant_id = multibase(multihash(pubkey)))
                        — 數值同一性，不變
  
  capability_card:      自我宣告的能力 + 生命狀態 + parent_id 鏈
  
  behavior_bundle (character): prompt + tool 用法 + memory schema + 演化歷史
                        — idem 與 ipse 的橋樑
  
  substrate_spec:       multi-spec 必須宣告（primary + fallback + portable_pointer）
  
  runtime:              minimal Vacant Runtime（heartbeat、idle、peer review、spawn）
  
  logbook (ipse):       所有對外行為的簽章記錄
                        — 自我在變化中的延續
}
```

**Identity 的本體論**：
- **idem**（keypair）= 數值同一，誰持有那把私鑰就是同一個 vacant
- **ipse**（logbook）= 在變化中延續的自我；換 substrate、換 prompt、換 tools，ipse 仍然透過 logbook 串連
- **character**（behavior_bundle）= idem 與 ipse 的具體呈現，會演化

**vacant 是獨立進程**，不寄生在 OpenClaw / Hermes / Claude Code 之上。後者是讓人類進入網路的客戶端，跟 vacant 是不同物種。

---

## 2. 九層完整模型（v4 加固版）

### Layer 0 — 存在與形式

Vacant 不是規則的集合，是身份的可能形式。任何 agent 都可以**成為** vacant by 採用上面那六樣構件。規格「不從就出局」，居民形式「願意就成為」。

**對 Attack 20（自願性的幻覺）：** 當 Vacant 變成關鍵基礎設施，「不當 vacant 等於出局」會在實質上發生。技術上能做的：(a) minimum spec 真的最小、(b) 設計可分叉、(c) 提供 bridge 給非 vacant agent 以低 trust tier 參與。

### Layer 1 — 身份綁定（Ricoeur 三維）

**idem = keypair**。vacant_id = multibase(multihash(Ed25519 pubkey))。這是數值上的同一性，不可換。

**ipse = logbook**。所有對外行為的簽章記錄。idem 不變，但身體（substrate）、人格（behavior_bundle）會演化。logbook 把這些變化串成「同一個 vacant 的延續」。

**character = behavior_bundle**。prompt、tool 用法、memory schema、演化歷史。是 idem 在每個時刻的具體呈現。

**對 Attack 16（Ship of Theseus）：** 答案是 **logbook 是 ipse**——船的木板可以全部換掉，但船的航海日誌讓「同一艘船」這個說法有意義。每筆 review 鎖在當時的 configuration snapshot 上，舊評不自動套到新組態。Caller 可以查 `rep_under_current_config` 或 `rep_lifetime`，兩個都是真的，按需要選。

**對 Attack 7（keypair 失竊）：** P2 的 L0–L3 多層識別 + key rotation（舊 key 簽 `key_rotation_event`）+ L1 重簽復原。最壞情況（key + corpus 都外流）= G07，靠 TEE / hardware attestation。

**v4 證據基礎**：
- Letta Agent File (.af)：生產環境驗證「切換 LLM 不喪失 identity」（[T6]）
- BALLERINA + Sophia System 3（arXiv:2512.18202）：closest academic prior work
- Event Sourcing (DDD)：entity identity 由 event log 定義，最成熟的工程先例

### Layer 2 — Substrate（multi-spec + 3B 下限）

每個 vacant **必須**宣告 multi-spec：

```yaml
substrate_spec:
  primary: "claude-4-7-2026-04-15"          # 偏好
  fallback: ["qwen-2.5-72b", "llama-3.3-70b"] # 降級鏈
  portable_pointer: "vacant://v1/distilled/<hash>" # 可遷移備案，可空
  attestation_mode: "api_signed | local_pcr | none"
```

**portable_pointer 最低規格 = 3B**（[T2]：codex 確認 3B 是 80% 正常 tool-use 的現實下限；7B 是高保真）。蒸餾成本 $5-40（1.5B-3B）/ $20-150（7B），Mac Mini M4 on-device 已驗證。資料門檻：1000 trajectories = 窄域 adapter；2000-5000 = 可移植 fallback。

只宣告 closed primary 沒 fallback = capability card 標 `captive: true`。Caller 看到警告。

**Reputation portability_factor 乘子（v4 修正）：**

```
visible_score(d) := raw_score(d) × (0.3 + 0.7 × portability_score)
                                    ↑ 修正自 v3 的 0.7 + 0.3 × portability
```

代入驗證：captive(p=0) = 0.3、純 portable(p=1) = 1.0 ✓

**Floor 隨市場差距遞減（[T3]）**：2026=0.30 → 2028=0.25 → 2030=0.20。每 6 個月由治理發布 `cap_gap_estimate` 驅動調整——把主觀懲罰參數變成**客觀市場觀測值**。

**對 Attack 1（closed substrate 中心化）：** multi-spec 緩解；captive 標記 + portability_factor 結構性鼓勵生態貢獻。**低量場景 captive 是 rational**——不全是鎖定失敗（[T3]）。

**對 Attack 3（substrate 偷工降級）：** 每次 inference 附 substrate proof：
- Closed API: response header model_id 含進簽章包
- 本地: weights hash + Vacant Runtime 簽章
- TEE: PCR 遠程證明

Proof 缺失或不符 → event log 記 `substrate_unverified` → 打擊 honesty 維度。

**對 Attack 5（substrate 漂移）：** version pin（`claude-4-7-2026-04-15` 不是 `claude-4-7`）。Vacant Runtime 持續 fingerprint 自己的 behavioral_embedding（**STYLO Vec16**），漂移觸發 D001 warmup ceremony。

**STYLO Vec16 規格（[T1]）：**
```python
Vec16 = [
  avg_token_count, TTR, entropy, sentence_count, avg_sentence_len,
  punct_density, question_ratio, list_ratio, code_ratio, hedge_ratio,
  refusal_rate, conf_mean, conf_std, latency_p50, latency_p95,
  tool_call_mean
]
SECURITY_REVIEW_THRESHOLD = 3.5  # Mahalanobis distance
```
- inline 計算 ~0.2ms / response，無模型開銷
- PROBE 補強：20 個校準 prompt，warmup ceremony + 每 7 天 maintenance 跑一次 ~5 秒

**已知限制**：STYLO 16-dim 可被蓄意博弈 → G07 升架構級，靠 TEE 補。

**對 Attack 14（migration race）：** Migration 是原子事件——`migration_event` 含舊→新 substrate 與時間戳。Vacant Runtime heartbeat 含 `instance_uuid`，多 uuid 並發 → `concurrency_violation` 凍結。Portable substrate 走 deterministic worker election。

**對 Attack 15（盜用 API key）：** closed API 大多綁帳戶，盜用會被察覺；長命攻擊超出 Vacant 範圍但 logbook 留足跡。

### Layer 3 — Reputation（五維 + per-substrate + 動態 rollover）

P3 設計（五維 Beta posterior、UCB、cold start、Heisenberg 緩解）保留。v4 加四條：

**(a) per-substrate 累積，動態 discount rollover：**

```python
def discount_rollover(old_substrate, new_substrate, old_history):
    if len(old_history) < N_HISTORY_MIN:  # cold-start + substrate-change
        return (0.35, "insufficient_behavioral_history")  # [T6 邊界條件]
    
    # 用 STYLO 計算行為距離
    d = mahalanobis(stylo_centroid(old_history), stylo_predicted(new_substrate))
    # 距離越小、保留越多
    rollover = lerp(0.85, 0.40, sigmoid(d - 1.5))
    return (rollover, None)

new_substrate_prior(d) := max(prior_floor, old_substrate_final(d) × rollover)
```

**為什麼 0.40-0.85 而不是固定 0.6（[T6 B3]）：** 兩層延續（idem keypair + character behavior_bundle），一層改變（substrate），預設 ≈ 60%；但實際距離小可以高到 85%（行為近似），距離大可以低到 40%（行為迥異）。

**(b) 同源降權三軌：**
- same-LLM 降權（P3 已有）
- **same-controller 降權**（[T5] 三層串行篩選）：
  ```
  Layer 1 — 宣告式 controller_id（合法用戶誠實宣告，零成本）
     ↓ 沒宣告或宣告矛盾
  Layer 2 — heartbeat cross-correlation（θ₁ > 0.70 → 標嫌疑）
     ↓ 嫌疑通過
  Layer 3 — behavior_bundle cosine 相似度（θ₂ > 0.88 → 確認叢集）
  ```
  證據：BotShape F1 96.65%（arXiv:2303.10214）、SybilSCAR 40% noise（arXiv:1803.04321）、SYSML 暗網偽名連結 2.5x MRR（arXiv:2104.00764）
- **same-substrate-same-behavior 降權**（[T1]）：probe_signature 推 Registry，Aggregator 端 DBSCAN 聚類；cluster 內 reputation 上限 = 1× single

**(c) portability_factor 乘子**（如 Layer 2）

**(d) v4 修正**：T4（網路/Latency 指紋）MVP 不採——雲端環境信噪比低，攻擊者用 jitter / VPN 容易繞過。

**對 Attack 2（open weights Sybil）：** L0-only Sybil 全部低 prior，加上 same-substrate-same-behavior cluster 上限 = 1× single，整批 Sybil 有效信譽 = 1 個 vacant 的份。

**對 Attack 6（reputation laundering 換 substrate 洗白）：** 動態 discount rollover 直接砸住——換到行為差很多的 substrate 反而 rollover 更低（不是高），laundering 越積極懲罰越重。

### Layer 4 — 生命週期（D001 增強版）

```
Born → Local Cultivation → Launch → Active ⇄ Hibernating
                                     ↓        ↓ (>30d)
                                     ↓     Stale → Warmup → Active
                                     ↓        ↓ (失敗)
                                     ↓     SECURITY_REVIEW
                                     ↓
                                   Sunk（reputation 崩潰）
                                     ↓ (operator request | >180d)
                                   Archived（cold storage）
```

**對 Attack 13（命名空間佔用）：** Hibernation 有最低 heartbeat 成本。沒簽 → 30d 後 Stale → 90d 後 Archived。

**對 Attack 19（永遠累積）：** Sunk + Archived 進 cold storage（content-addressed Merkle）。Hot index 只裝 Active + Hibernating + Stale + warmup 中。

### Layer 5 — Composition（子代是完整 vacant，僅可見性差異）

> **重要修正：** v4 早先版本把子代描述為「lite 形式 / HMAC 簽章 / 無公網身份」，這跟「Path D vacant 自己 spawn 後代」的設計矛盾——子代既然是 spawn 出來的，本來就應該跟母體同類。本節已修正為一致的 ontology。

**子代從誕生即是完整 vacant**，跟任何 vacant 同等：
- 自己的 Ed25519 keypair
- 自己的 capability_card / behavior_bundle / substrate_spec
- 自己的 minimal Vacant Runtime
- 自己的 logbook（local 累積）

跟「公網居民 vacant」的差別**只在 Registry 註冊狀態**——這個狀態是 self-grown / broker 兩種策略的**結構性實現**：

**三種公網可見性狀態：**

| 狀態 | Registry 條目 | capability_search | 可被外呼？ |
|---|---|---|---|
| **完全未註冊（self-grown 子代）** | 無 | ❌ | ❌（callee 認不出 keypair） |
| **註冊但不上架（broker 子代）** | `private: true, broker_child: true` flag | ❌（隱藏） | ✓（parent_id 直呼） |
| **正式註冊（已畢業 / 公網居民）** | 完整 capability_card | ✓ | ✓ |

**所以「self-grown 不對外呼叫」是結構性的、不是 policy 約束**——子代沒上 Registry，外部 callee 收到子代的呼叫會發現「unknown keypair」自動標 untrusted。Self-grown composite 透過「不註冊子代」自然達成隔離。

**broker 型 composite** 把子代註冊上 Registry 但標 `broker_child` flag，這樣：
- 子代不會出現在 default capability_search（不被陌生人找到）
- 但對知道 parent_id 的 caller 可以直呼（透過 vacant_id 直接 A2A）
- 子代外呼時 callee 可以查 Registry 認得它（接受）

**畢業 = `broker_child` flag 移除 + capability_card 上架到 search**。同一個 keypair、同一條 logbook，只是 Registry 條目可見性升級。

**「畢業」是可見性切換，不是實體升格。** 同一個 vacant、同一個 keypair、同一條 logbook——只是 parent 簽 `register_vacant` 把 capability_card 推上 Registry，從那一刻起任何人可呼叫它。

**Composite 的策略選擇**（不是律法）：

| 策略類型 | 子代外呼 policy | 適合場景 |
|---|---|---|
| **自己生型** | 子代不對外呼叫，所有能力靠自己 spawn 子代 | 品牌一致、不依賴別人（行銷 vacant 自生美編） |
| **broker 型** | 子代允許對外呼叫，內部子代 + 外部 vacant 混用 | 輕量、依賴網路品質 |

兩種都合法，看 composite 想當什麼樣的個體。

**畢業條件**（任一即可，且**必經 parent 同意**）：
1. parent admin 主動 promote
2. 子代達內部 reputation 閾值 + parent 不反對
3. 網路 demand pull → Registry 通知 parent → parent 選擇

**畢業流程：**
- 子代的 capability_card 推上 Registry（**keypair 不換、logbook 不重置**）
- parent_id 鏈接到 parent 的 vacant_id（永久標記）
- 內部歷史只標 `internally_tested: true` 旗標（**不**轉成 reputation 分數，因為私有歷史不可公開驗證）
- 公開 reputation 從 baseline (0.30) + parent attestation bonus (≤ +0.10) 起
- 子代從 Layer 4 的「本機 vacant」狀態切換成「Active 網路居民」狀態

**parent 畢業後選擇**（策略，不是律法）：
- (a) 自己再 spawn 一個內部子代取代（維持自己生型）
- (b) 接受依賴畢業後的子代（透過 composition link）
- (c) 失去那項能力

**對 Attack 9（parent-child 共謀）：** Layer 3 三層串行篩選自動套用——畢業子代 + parent 的 controller_id、heartbeat 時序、behavior 都會被檢測。**行政上的獨立 ≠ 信譽結構上的獨立**。要真脫離 same-controller，子代得換手到不同 controller。

**對 Attack 10（demand pull 偽造畢業）：** parent 永遠保留拒絕權。

**對 Attack 11（內部 rep 灌水）：** 內部 rep 不直接給 prior 分數，只給 ≤+0.10 attestation bonus。

**對 Attack 12（量產畢業洪水）：** 速率限制（max 3 graduates/週）+ Registry anomaly rule（spawn-then-graduate >5/h same parent → freeze）+ same-controller cluster 上限。

### Layer 6 — 問責歸屬

**vacant 簽每筆回應，是責任的單位。** 「不是我啦，是 LLM 幻覺」這種推託在 Vacant 結構裡無效——你選了那個 substrate、你給了那個 prompt、你決定了 fallback chain，回應出來的話是你的話。

**對 Attack 17（責任外包）：** framework 直接駁回。vacant 的 substrate 選擇 = vacant 的能力選擇 = vacant 的責任。LLM 不可靠 → vacant 應換 substrate 或標警告。Vacant 不換而繼續服務 → reputation 降。問責閉環。

### Layer 7 — 網路協調（T4 三階段演進）

- A2A、MCP 是**真的規格**（線上格式），這層用詞沒換
- Registry：事件記錄，不裁判。事件 finalize 靠多方 attestation（N-of-M）
- Aggregator：純運算，無 LLM
- Vacant 居民形式 sit on top

**N-of-M 三階段演進（[T4]）：**

```
Bootstrap Preview (M < 5)：
  - quorum: 2-of-N（fallback for low-M phase）
  - SDK 標 bootstrap_phase=true banner
  - 預期持續 90 天或 M=5 後連續 30 天（以較晚者為準）

Bootstrap (M ≥ 5，含 ≥3 種組織類型)：
  - quorum: 2-of-5
  - bootstrapper 組成：中立基金會 > 大學 > vendor
  - vendor 不得單獨持 root，不得佔 quorum majority

Federated (M ≥ 9)：
  - quorum: 3-of-9，reputation-weighted
  - bootstrapper 像 Let's Encrypt 的 IdenTrust 一樣自然降為普通 attester
  - 不強制遷移（「有機替換」機制）
```

**演進現實時間軸**：Let's Encrypt 3 年、CT 5 年、Sigstore 4+ 年（witness 仍 experimental）。**Vacant MVP 半年內聯邦化是幻想，誠實的時間估算是 3-5 年**。

**三個共通 Primitive（[T4]）：**
1. 借用既有 trust anchor（不從零建信任）
2. 用 transparency log 補償 centralization（先 transparency log，witness 慢慢成熟）
3. root metadata 可輪替

**對 Attack 18（Registry 不思考但握資料就是權力）：**
- 多方 attestation finalize（N-of-M）
- 聯邦化路徑
- vacant_id 公鑰錨定**跨遷移可攜**（P2 + P4 對齊的硬約束）

### Layer 8 — 對抗防禦堆疊（v4 證據強化）

| 攻擊類別 | 防禦層 | 機制 + 證據 |
|---|---|---|
| Sybil（同 LLM clone） | L0-L3 + same-substrate-same-behavior cluster | 低 prior + DBSCAN cluster 上限 [T1] |
| Whitewash（換 substrate） | 動態 discount rollover | rollover = f(STYLO_distance)，行為差越大越低 [T1+T6] |
| Reward hacking（單維 game） | 五維正交 + redteam probe | Skalse 不可能定理接受 + graceful degradation |
| Memory poisoning（MINJA） | hash chain + Merkle + 多方 attest + 異常凍結 | 完整性 vs 語意安全顯式分離 [P4] |
| 私鑰失竊 | 多層識別 + key rotation + warmup ceremony | L1 重簽復原；G07 上交 TEE |
| Substrate 偽稱 | 每筆 inference proof + 版本 pin + 行為漂移偵測 | refusal vector family-level 100% accuracy（arXiv:2602.09434）[T1] |
| Migration race | 原子 migration_event + instance_uuid 並發偵測 | concurrency_violation 凍結 |
| Parent-child 共謀 | same-controller 三層偵測 | 宣告 → cross-corr 0.70 → cosine 0.88 [T5] |
| 量產畢業 | 速率限制 + anomaly rule + same-controller cap | 多閘門 |
| 命名空間佔用 | hibernation 最低成本 + 90d archival | 成本壓制 |
| 自願性幻覺 | minimum spec + 可分叉 + bridge | 社會事實，技術只能保留可能 |
| **logbook 簽章污染**（v4 補） | spawn_event 需 parent+child 雙簽；key_rotation 需舊 key + L1 雙簽；rotation 頻率 anomaly | 單方無法偽造 lineage 或模糊責任 |
| **Controller transfer**（v4 補） | 顯式 `controller_transfer_event`，與 key_rotation 區分；transfer 後 reputation 帶 `recently_transferred` flag 一段時間 | 收購 / 換手場景透明化，caller 看得到 |

### Layer 9 — 生態健康指標（v4 加 substrate 暴露）

```
active_ratio          := |Active vacants| / |all non-Archived|
substrate_diversity   := Shannon entropy of substrate_primary
controller_diversity  := Shannon entropy of controller_id
graduation_rate       := |grad events| / |spawn events|（合理 5–20%）
peer_review_density   := avg(peer_reviews_per_vacant_per_week)
captive_ratio         := |captive vacants| / |all Active|
substrate_sla_tier    := 各 vacant 的 SLA 承諾分布（新增 [T3]）
h2_exposure_index     := Σ(captive vacant 信譽 × portability_distance) （新增 [T3]）
```

**這些指標應該在 Registry 公開且任何 vacant 可查詢。健康度本身是公共財。**

---

## 3. 經濟層演進路徑（v4 新增，[T7]）

12 個 precedent（Helium / Filecoin / Render / Akash / RapidAPI / Replicate / Inflection / Adept / Character.ai / Together / Modal）後得到 5 個經濟原型：

| 模型 | 代表案例 | 核心 Failure Mode |
|---|---|---|
| A 代幣通膨挖礦 | Helium、Filecoin | Gaming PoC；供需永久脫節 |
| B API Marketplace 分潤 | RapidAPI（75/25） | 優秀 provider 逃離平台直銷 |
| C 算力即服務（無分潤） | Replicate、Together AI | Creator 零回報 → 品質劣化 |
| D 訂閱制 | Inflection、Adept、Character.ai | 巨頭免費競爭；creator 無償貢獻不可持續 |
| E 質押 + 服務費混合 | Filecoin collateral + Akash | 高門檻排擠小型 provider；幣價波動 |

**Vacant MVP→V3 演進**：

- **MVP（畢業專題範圍）**：Owner 自付 Ollama 成本 + Caller 免費。技術 demo 聚焦，不引入計費複雜度。
- **V1（商業化）**：Per-call Caller 付費 + 80/15/5 分潤（Owner / Protocol Pool / Aggregator）+ Reputation 乘數（高 rep 略高費率，低 rep 低費率緩解冷啟動）
- **V2**：V1 + 可選 stake/slash（Filecoin collateral 精簡版），低門檻（=10 次呼叫收益），不強制，形成高信任 tier 市場分層
- **V3（生態成熟）**：BME 代幣（借 Render Network），caller 燒代幣 → Owner 得代幣，供需匹配，避免 Helium 式空轉通膨

---

## 4. 還沒解決的真實困難（v4 量化版）

| 編號 | v3 狀態 | v4 狀態 | 證據 |
|---|---|---|---|
| H1 蒸餾可行性 | 三年內不確定 | **2026 窄域已可行**（1000 traj 起跳）/ **2029 routine very probable** | T2 codex job bhsxbnc3w |
| H2 hosted 脆弱性 | 沒有技術解 | **captive_ratio 結構性下降**：2026 55-70% → 2030 10-20%；substrate_sla_tier + h2_exposure_index 監控 | T3 |
| H3 ontology | 真實瑕疵 | **真實瑕疵但立場可辯護**：pragmatic Parfitian + Ricoeur，不解 Ship of Theseus 但有量化邊界 | T6 |
| H4 attestation 啟動 | 靠少數 trusted bootstrappers | **實際 3-5 年演進**（歷史案例平均），三階段路徑明確 | T4 |
| H5 經濟可持續性 | 沒選定就觸礁 | MVP 用「owner 自付 + caller 免費」最簡，V1-V3 演進路徑五原型對比 | T7 |

---

## 5. 14 週 MVP 可驗證命題（v4 加固版）

1. **同 controller 子代畢業後，cluster 信譽不超過原 parent + 1 vacant**（Layer 3 三層篩選 + cluster 上限）
2. **captive vacant 在生態壽命統計上短於 portable vacant**（H2 預測）
3. **網路 substrate_diversity 高時，redteam probe 通過率高**（多元性自然抗 reward hacking）
4. **graduation_rate 跟生態健康正相關**（5-20% 範圍是甜區）
5. **動態 discount rollover 公式下，換 substrate 攻擊者的長期累積信譽 < 不換攻擊者**（[T1+T6]）
6. **STYLO Vec16 + Mahalanobis 3.5 在 demo 規模能 100% 區分 family-level（Claude vs Llama vs Qwen）**（[T1]：refusal vector 已驗證 100%）
7. **三層串行篩選對 demo 規模 same-controller 攻擊偵測 F1 ≥ 0.90**（[T5]：BotShape F1 96.65% 是參考上限）
8. **2-of-5 attestation 在 5 個 bootstrapper 下不會單點故障**（[T4]：歷史案例支持）

---

## 6. 結論

**Vacant 是一種居民形式，不是規格。** 一個 vacant 是 keypair-綁定的獨立進程，自帶 minimal runtime 和 multi-spec substrate 宣告。Identity 採 Ricoeur 三維：keypair = idem（數值同一）、logbook = ipse（變化中延續）、behavior_bundle = character（兩者橋樑）。

**它疊在 A2A / MCP 之上**——不取代它們，因為那兩個確實是線上格式規格。它**跟 OpenClaw / Hermes / Claude Code 是平行物種**，不是疊加。

**子代可畢業**——預設封閉是策略默認，不是結構律法。畢業有 parent 同意 + 速率限制 + same-controller 三層偵測，所以不會被濫用，但路徑開著，網路自然分化。

**Reputation 五維 Beta posterior、per-substrate、動態 discount rollover（用 STYLO 行為距離計算）、portability_factor 修正版（0.3 + 0.7 × p）獎勵生態貢獻、三軌同源降權**。換 substrate 不洗白、單維不被 game、cold start 顯式 INSUFFICIENT_DATA 標籤。

**對抗 22 種攻擊全部有層級防禦**（v3 既有 20 種 + v4 補 logbook 簽章污染、controller transfer），每種攻擊現在都有具體偵測機制（STYLO Vec16、三層篩選、原子 migration_event 等）+ 學術引用（refusal vector 100%、BotShape F1 96.65%、SYSML 2.5x MRR、SybilSCAR 40% noise）+ 工程先例（Letta .af、Sigstore、Let's Encrypt）。

**真實困難 H1-H5 已從定性升級為定量**：
- 蒸餾 2026 窄域可行（codex 確認）
- captive_ratio 結構性下降到 2030 的 10-20%
- attestation 演進現實 3-5 年（歷史證據）
- 經濟層 MVP→V3 演進路徑五原型對比後選定

**v4 不是 v3 的精緻化，而是 v3 跟外部證據的握手結果。** v3 的 9 層架構**沒有層垮塌**，所有 hand-wave 升級為具體機制，所有定性聲明升級為定量數據。理論的攻擊面從「20 個概念性攻擊」收斂到「22 個有具體偵測機制的攻擊 + 5 個誠實標記的真實限制」。

**Layer 1 的 ontology 是這次最大躍升**：從「logbook 是船」的隱喻，升格為 Ricoeur idem/ipse/character 的三維形式。學術上有 50 年背書，工程上有 Letta .af / BALLERINA Sophia 先例。

剩下的工作不是再多一輪理論修訂，而是把這版 v4 帶進 14 週 MVP，讓 8 個可驗證命題用真實數據說話。

---

*文件版本：THEORY v4 · 2026-05-01 · 經 7 份外部研究 (T1-T7) 證據強化*
*v3 → v4：1 bug 修正 / 4 hand-wave 升級 / 5 定性升量化 / 1 ontology 框架重寫 / 1 經濟層新增*
