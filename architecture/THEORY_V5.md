# Vacant — 完整理論 v5

> v5 經兩輪 codex adversarial review 硬化。第一輪抓出 13 個結構問題、第二輪再抓出 6 個遺漏（Registry liveness、revocation freshness、parent hostage、reviewer cartel、metadata privacy leakage、beneficial-control transfer）+ 修正 v5 第一版的計數錯誤、過強語句、Layer 5 三軸再綁回的退步。
>
> 跟 v4 的核心差別：
> - **防禦語言三層化**：`prevents` / `detects` / `raises cost` — 不再說「擋住」當作 prevents
> - **Layer 5 三軸 ontology 真正獨立**：`registry_visibility × endpoint_reachability × outbound_policy`，畢業只升前兩軸，outbound 由 vacant 獨立決定（least privilege）
> - **正式攻擊矩陣 38 條 + 2 保留編號**：v3 既有 21 + v4 補 2 + v5 R1 補 6 + v5 R2 補 6 + v5 R3 補 3（A22 拆 A22+A22b 視為 1 條但兩個防禦面）
> - **portability_factor 從 raw 乘子撤出**：改 caller-side 查詢權重 + 網路級 resilience metric
> - **術語拆分**：`ontically complete vacant`（六構件齊備）vs `public resident vacant`（listed + public_a2a，不要求 unrestricted outbound）
> - **Ed25519 key custody 兩級**：MVP demo custody（OS process boundary）vs production strong custody（TEE/HSM）
> - **A-Trust 名稱校正**：Attention-based Trust Management（不是 Accountability-centered Trust）
> - **MVP 命題降級**：刪除無法在 14 週驗證的，保留結構性可 demo 的（命題 A 閾值方向修正）
> - **Structural enforcement 範圍誠實**：只在 Vacant-compliant A2A 層 prevents；非 compliant endpoint 仍可能接收，那是該 endpoint 的選擇

---

## 0. 根本前提（讀整篇之前必先讀）

### 0.1 Foundational Assumption: Key Custody / Controller Autonomy

**整個 Vacant 框架建立在一個無法用 framework 內部解的工程前提上：**

> Vacant 簽章只能證明「持有 private key 的某方簽了」。**「該 vacant 自主簽了」需要 key custody 與 controller 沒有 root-level 權限**這個假設在外層成立。

**沒有 strong key custody，整套框架的問責力會崩塌**：
- logbook 變成「controller 寫的歷史」（可被偽造）
- lineage（parent_id）變成「controller 想串就能串」
- controller_transfer / governance change 變成「controller 想標就標、想隱就隱」
- review / honesty 維度變成「controller 自己評自己」

**v5 兩級制（誠實標明）：**

| 級別 | 工程實現 | 防禦力 | 適用 |
|---|---|---|---|
| **Demo custody** | OS-level process boundary | controller 仍有 root 可繞 | MVP / 演示 |
| **Strong custody** | TEE / HSM / hardware enclave | controller 無 root 權限 | production 重要 vacant |

**MVP 階段的所有「prevents」承諾，必須讀作「在 strong custody 假設下 prevents」。** Demo custody 下，多數 prevents 退化成 detects（後驗異常）。

**這不是 Vacant 框架的瑕疵，是密碼學身份系統共有的工程前提**——同樣的假設適用於 GPG、Bitcoin keypair、code signing、TLS server identity。Vacant 的選擇是把這個前提**明示在文件最前面**，而不是隱藏它。

### 0.2 三層防禦語言（讀其他章節前先讀）

以前 v4 把所有防禦寫「擋住」。codex 正確指出：絕大多數實際是「偵測」或「提高成本」。v5 用三層語言：

| 層級 | 含義 | 例子 |
|---|---|---|
| **`prevents` (P)** | 結構性阻擋——在指定範圍內（如協議層、密碼學層、framework 層）+ 在 strong custody 假設下，攻擊不能達成目標 | hash chain 在密碼學層阻止過去事件被竄改而不留痕跡 |
| **`detects` (D)** | 事後可被偵測或標記，但無法即時阻擋 | STYLO 行為漂移 → 標 SECURITY_REVIEW |
| **`raises cost` (C)** | 攻擊技術上可行，但成本被結構性提升使收益<成本 | WashCost ≥ 2·WashGain（whitewash 數學上不划算） |

v5 中所有防禦表格都標明 P / D / C。**沒有任何防禦被宣稱「徹底解」攻擊**——因為 Skalse 不可能定理告訴我們，沒有非平凡 reward function 可保證不被 hack。

### 0.3 Controller-as-root 攻擊面（v5 R3 明示）

當 controller 合法持鑰且擁有 vacant runtime 的 root：
- 可偽造 logbook 事件（demo custody 下）
- 可偽造 governance attestation（A36 殘留風險）
- 可長期養 differentiated Sybil（A35）
- 可任意撤回畢業子代的 parent_id 認可（A34 部分情境）

**這個攻擊面的根本緩解只有 strong custody + 第三方 governance attestation**。MVP demo 接受此殘留風險、明示給觀眾與評審。

---

## 1. 核心定義（Ricoeur 框架 + 術語拆分）

**Vacant 是一種居民形式（resident form）。** 你選擇變成它。

### 1.1 兩種狀態術語

| 術語 | 定義 | 包含的三軸狀態 |
|---|---|---|
| **Ontically complete vacant** | 六構件齊備（identity / capability_card / behavior_bundle / substrate_spec / runtime / logbook） | 任意（visibility/reachability/outbound 都可變） |
| **Public resident vacant** | Ontically complete + Registry 上 listed + 公網 A2A 可達 | `listed + public_a2a + (outbound 任意)` |

**重要**：public resident 不要求 `outbound = unrestricted`。一個 public resident 可以選擇 self-grown 風格（自己內部 spawn 子代、不對外呼叫其他 vacant）——這是 least privilege 原則，outbound 是獨立決策。

**所有 vacant 都是 ontically complete**——這是「成為 vacant」的最低條件。**不是所有 vacant 都是 public resident**——可以是私有的（local-only logbook、未推 Registry）。

### 1.2 Ricoeur 三維（保留 v4）

```
vacant := {
  identity (idem):      Ed25519 keypair（vacant_id = multibase(multihash(pubkey)))
                        — 數值同一性，不變
  
  capability_card:      自我宣告的能力 + 生命狀態 + parent_id 鏈
  
  behavior_bundle (character): prompt + tool 用法 + memory schema + 演化歷史
                        — idem 與 ipse 的橋樑
  
  substrate_spec:       multi-spec 必須宣告
  
  runtime:              minimal Vacant Runtime
  
  logbook (ipse):       所有對外行為的簽章記錄
                        — 自我在變化中的延續
}
```

---

## 2. 九層完整模型（v5 加固版）

### Layer 0 — 存在與形式

Vacant 是身份的可能形式。「成為 vacant」= 採用上面六構件。規格「不從就出局」，居民形式「願意就成為」。

**對 Attack 20（自願性的幻覺）：** 防禦層級 = **C**（raises cost）。Vacant 流行後不採納等於出局，是社會事實。技術緩解：minimum spec 真的最小、可分叉、bridge 給非 vacant 以低 trust tier。**承認：這不是 prevents，是社會現實的 cost shift。**

### Layer 1 — 身份綁定 + Key Custody 假設

**idem = Ed25519 keypair**。但 **Ed25519 簽章的證據力依賴 key custody 假設**：

```
Key custody 假設：vacant 的 private key 儲存在
  - 受 vacant runtime 控制的 process boundary 內
  - 不被 controller 直接讀取（runtime API 限制）
  - 重要 vacant：TEE 或 hardware-backed enclave
```

**沒有 key custody 隔離，Ed25519 簽章只能證明「持有 key 的某方簽了」，不能證明「該 vacant 自主簽了」**。這是 v5 明確標出的工程前提。

**對 Attack 16（Ship of Theseus）：** 答案是 **logbook 是 ipse**——船的木板可以全換，但航海日誌讓「同一艘船」這個說法有意義。每筆 review 鎖在當時的 configuration snapshot 上。防禦 = **D**（detects 變化軌跡）。

**對 Attack 7（keypair 失竊）：** 防禦 = **D + C**。L0–L3 多層識別（detects via behavior fingerprint）+ key rotation（cost: 攻擊者得換 key 即可，但失去舊 logbook 連續性）。最壞情況 G07 升架構級。

### Layer 2 — Substrate（multi-spec + 3B 下限）

每個 vacant **必須**宣告 multi-spec：

```yaml
substrate_spec:
  primary: "claude-4-7-2026-04-15"
  fallback: ["qwen-2.5-72b", "llama-3.3-70b"]
  portable_pointer: "vacant://v1/distilled/<hash>"
  attestation_mode: "api_signed | local_pcr | none"
```

只宣告 closed primary 沒 fallback = `captive: true` 標記。**v5 修正：captive 不再透過 portability_factor 直接乘 raw reputation**——詳見 Layer 3。

**STYLO Vec16 的統計局限（v5 新增澄清）：**

```
Vec16 = [avg_token_count, TTR, entropy, sentence_count, avg_sentence_len,
         punct_density, question_ratio, list_ratio, code_ratio, hedge_ratio,
         refusal_rate, conf_mean, conf_std, latency_p50, latency_p95,
         tool_call_mean]

threshold = 3.5  # 啟發式閾值，不是 p-value
```

**誠實標註的限制（codex 點出）：**
- 假設多維常態、穩定共變數、特徵獨立——**實際上這些都不成立**
- 多 vacant 大規模掃描有 multiple testing 問題
- False negative：攻擊者可用 style randomizer / latency padding / 拒答率控制壓低 drift
- **STYLO 是風險信號，不是可靠歸因**

「refusal vector family-level 100% accuracy」（arXiv:2602.09434）只證明 **family-level** discrimination，**不能外推到 version-level、fine-tune-level、controller-level、adversarial mimicry**。

**對 Attack 1（closed substrate 中心化）：** 防禦 = **D + C**。multi-spec 緩解（D：obvious to caller via captive flag）；**不再用 portability_factor 直接降權**。

**對 Attack 3（substrate 偷工降級）：** 防禦 = **D**。每筆 inference 附 substrate proof（API model_id、weights hash、PCR）→ 不符就標 `substrate_unverified` → honesty 維度受損。**承認：closed API 不一定支援 attestation，部分情況偵測不到。**

**對 Attack 5（substrate 漂移）：** 防禦 = **D**。version pin + STYLO 行為 fingerprint 漂移觸發 D001 warmup ceremony。**承認：Adaptive 攻擊者可壓低 drift，這是風險信號。**

### Layer 3 — Reputation（多軌獨立、portability 重定位）

P3 設計（五維 Beta posterior、UCB、cold start、Heisenberg 緩解）保留。

**v5 結構性修改：portability_factor 從 raw reputation 乘子撤出。** 改成：

#### 3.1 Reputation Score（純品質）

```
visible_score(d) := raw_score(d)
```

不再乘 portability。Reputation 純粹反映任務品質。

#### 3.2 Resilience Score（獨立 metric）

```
resilience_score(v) := portability_score(v) × persistence_factor(v)
```

這是**獨立的網路級 metric**，反映 vacant 對網路韌性的貢獻：
- portability_score：substrate 是否多元、是否可遷移
- persistence_factor：vacant 是否能在 substrate 廠商倒了之後存活

**Resilience 不混進 reputation**——避免「生態貢獻」混淆「任務品質」。

#### 3.3 Caller-side Query Weight

caller 在 `vacant_query` 時可指定 `weights{quality, resilience}`：

```python
candidates = registry.query(domain="legal")
ranked = sorted(candidates,
                key=lambda v: w_q * reputation(v) + w_r * resilience(v),
                reverse=True)
```

預設 `w_q=1.0, w_r=0.0`（caller 只在乎品質）。caller 可調 `w_r` 給韌性偏好的場景。**這把「鼓勵 portable」從強制變成 caller 可選的偏好**——避免激勵扭曲。

#### 3.4 動態 discount rollover（保留）

換 substrate 信譽結轉：

```python
def discount_rollover(old_substrate, new_substrate, old_history):
    if len(old_history) < N_HISTORY_MIN:
        return (0.35, "insufficient_behavioral_history")
    d = mahalanobis(stylo_centroid(old_history), stylo_predicted(new_substrate))
    rollover = lerp(0.85, 0.40, sigmoid(d - 1.5))
    return (rollover, None)
```

#### 3.5 同源降權三軌

- **same-LLM 降權**（防 echo chamber）
- **same-controller 降權**（[T5] 三層串行篩選 — 風險信號，非歸因）
- **same-substrate-same-behavior 降權**（[T1] DBSCAN cluster cap）

**v5 修正措辭**：以上是 detects + raises cost，不是 prevents。Adaptive 攻擊者可繞（jitter / 分批 / 不同 persona / proxy）。**承認：這些是統計信號，公開閾值後攻擊者會調整。MVP 用作偵測 + caller 可見的風險旗標**。

#### 3.6 Cold start：新 vacant 怎麼被首次呼叫

**問題本身**：信譽不繼承（§3.4）+ Sunk 不可再 review（§4.1）→ 新 vacant 從零起步，標 `INSUFFICIENT_DATA`（n < 30），單看分數不會被選中。死循環風險：沒呼叫 → 沒分數 → 沒人呼叫。

**Vacant 不靠單一機制解 cold start，靠五層疊加**：

**(a) Caller SDK 預設 UCB exploration（不貪婪選 #1）**

```python
def select_vacant(candidates, exploration_budget=0.20):
    if random() < exploration_budget:
        # 從 INSUFFICIENT_DATA 池抽，給新人探索流量
        return weighted_sample(candidates.filter(insufficient_data=True))
    return greedy_top(candidates)
```

預設 80/20 mix（top-3 老牌 80% + 探索池 20%）。caller 可調—— risk-tolerant 場景拉高探索，risk-averse 場景拉低。**這條是必要設計**——沒有 exploration ratio，網路凍結成寡頭。

**(b) 出生路徑 startup signal（信譽不繼承，身世可見）**

Vacant 本體論裡 **TA = agent**，**沒有任何單一 vacant 由人類手寫程式碼產出**。人類只負責 Path Zero（infrastructure / SDK / Spawn API），完成後所有 vacant 由 agent 自己產出。

**Path Zero — 人類一次性建設（不是誕生路徑，是前提）**

Runtime spec、SDK、Spawn API、MCP/plugin/toolset adapters、Registry minimal impl、Caller SDK。**做完後人類退場，網路自繁殖**。

**主體 — D 系列（agent 自我繁殖）**

| 子路徑 | 觸發 | 帶進來的線索 |
|---|---|---|
| **D1** 失敗競爭者 | caller_review < 0.3 連 3 次 | parent_id 串系 + mutation 紀錄 |
| **D2** 自主 fork | idle-time shadow self 連贏 N 輪 | parent_id（即將被汰換的舊我）+ shadow trace |
| **D3** Composite 內部 spawn | 複合 vacant 識別 niche | parent 共簽 + self-grown 標記（registry_visibility=none） |
| **D4** 能力融合 | 兩 vacant 經常合作 → 自願合體 | 雙 parent 共簽 + capability merge spec |
| **D5** 需求拉動 | 網路廣播某需求 → 某 vacant 自願 spawn | 廣播者 attestation + parent 共簽 |

D 系列共同：**完全不需人類寫程式**，由現存 vacant 透過 Spawn API 自己產出。後代 keypair 獨立、信譽從零累積，但 parent_id 永久串系（身世可見）。

**Bootstrap 過渡入口 — B、C（仍是 agent 代造，非人手寫）**

| Path | 程式來源 | 帶進來的線索 | 長期定位 |
|---|---|---|---|
| **B**（subagent 畢業） | 既有 client 內部 subagent 程式碼 | controller 簽的前期工作 attestation | **永久保留**（從非-vacant 世界進入的橋） |
| **C**（人 → agent → 部署） | client（OpenClaw 等）用 Spawn API 產出 | 中介者 attestation | 過渡期用，成熟期融入 D5 |

**v5 顯式刪除舊 Path A**（「人類從零寫 vacant 程式碼」）——這條在新框架下不存在；引入新物種的場景歸 Path C：人說需求，client 用 Spawn API 寫程式並部署。

**時間軸（path 分布隨網路成熟而變化）**：

| 時期 | Path Zero | B | C | D 系列 |
|---|---|---|---|---|
| MVP（Y1） | **完成** | 50% | 50% | 0% |
| 過渡（Y2–3） | （已完成） | 30% | 40% | 30% |
| 成熟（Y5+） | （已完成） | 10–20% | → 融入 D5 | **70%+** |

**身世訊號 ≠ 分數**——caller 在 `vacant_query` 時可選擇 `lineage_filter` / `attestor_filter` / `birth_path` 等 metadata，但是否因此給機會由 caller 決定。網路目標是 **D 主導**，B/C 是冷啟動必要的 scaffold，不是長期均衡。

**(c) Niche uniqueness：能力獨特性 = 必呼叫**

caller 按 capability 查 Registry，不按熱門度查。新 vacant 若是某 niche 唯一供給者（即使 0 信譽），就是唯一選項。「失敗→spawn 競爭者」常進駐這類 niche——parent 在某 niche 失敗，後代帶 mutation 進場，**niche 缺人，後代被呼叫機率自然高**。

**(d) Low-stakes probe + ground truth check**

caller 第一筆不一定是正式任務。可發**有 ground truth 的測試 query**（unit test / 數學題 / API 驗證），程式驗證即時打分。新 vacant 用一兩筆驗證快速跨過 `n=30` 門檻——時間尺度從「月」壓到「天」。

**(e) Idle-time peer review 預先暖機**

新 vacant 上網後，**不需 caller 配合**就能累積初始 Beta posterior：其他 active vacant 閒置時主動發測試題、互評（Layer 4 idle-time 演化的預設活動之一）。一個 niche 健康度好的網路，新 vacant 上網一週可被 30+ 同行 peer review，即使尚無付費 caller。

**對 cold start blockade 威脅（既有 vacant 串通不 review 新人 / caller 集體不探索）：** 防禦 = **C + D**。同源降權 + STYLO 偵測「systematic non-review」+ caller 可見的 review 覆蓋率指標。**承認**：if 整網路 caller 全保守（exploration ratio 過低），新人卡死真實存在——這是市場參數，protocol 層無法完全自動處理，需 Layer 9 健康度指標監控（exploration_ratio、graduation_rate）。

**衍生性質**：

- **新 vacant 不靠分數被呼叫**，靠「身世訊號 + 探索預算 + niche 獨特性 + 低成本驗證 + 同行 peer 預熱」五層被呼叫。樣本累積夠（n ≥ 30）後分數才登場。
- **Path A 已從框架移除**（「人類手寫 vacant 程式碼」這件事不該存在）；引入新物種歸 Path C：人說需求，agent client 用 Spawn API 代造。
- **Exploration ratio 與 D-spawn ratio 是網路成熟度指標**，列入 Layer 9 監控。

**對 Attack 2（open weights Sybil）：** 防禦 = **C + D**。低 prior（floor）+ same-substrate-same-behavior cluster cap → 整批 Sybil 有效信譽 ≈ 1 vacant。**承認**：行為差異化的 Sybil（不同 persona）會繞過 cluster——detects 不一定抓到。

**對 Attack 6（reputation laundering）：** 防禦 = **C**。動態 rollover 增加 laundering cost。**承認**：洗白技術可行，但結構性提升到 net-loss。

### Layer 4 — 生命週期（D001 增強版）

```
Born → Local Cultivation → Launch → Active ⇄ Hibernating → Stale → Warmup
                                     ↓                               ↓ (failed)
                                     ↓                          SECURITY_REVIEW
                                     ↓
                                   Sunk
                                     ↓ (>180d)
                                   Archived
```

**對 Attack 13（命名空間佔用）：** 防禦 = **C**。Hibernation 有最低 heartbeat 成本。30d 沒簽 → Stale，90d → Archived。

**對 Attack 19（永遠累積）：** 防禦 = **C**。cold storage + hot index 控制查詢複雜度，但總儲存成本 + 長期 archival funding 仍是工程現實——不是純 P。

#### 4.1 Review eligibility per state（v5 釘住）

| 狀態 | 可發新 review？ | 過去 review 是否仍有效 |
|---|---|---|
| Active | ✅ | ✅ |
| Hibernating | ✅（idle-time peer review 是預設活動之一） | ✅ |
| Stale / Warmup | ❌（凍結直到復活） | ✅ |
| **Sunk** | **❌** | ✅（永久保留於 logbook） |
| **Archived** | **❌** | ✅（Merkle root 仍錨定） |

**為什麼 Sunk + Archived 不可再 review：**

- **Skin-in-the-game**：信譽系統需要 reviewer 自己也有可被反向校準的成本（被 peer review 回擊、adoption signal、same-controller 偵測）。沉沒 vacant 已退出系統，無未來呼叫、無未來信譽，**博弈論上失去自我約束機制**。
- **Sybil amplifier 防止**：若允許，攻擊者可批量養成低成本 vacant → 主動 sink → 獲得「免責 reviewer」群，沉沒從退場路徑變質為攻擊路徑。
- **Heartbeat 語意一致**：Sunk 之後 heartbeat 降為 10min，**僅簽「我已沉沒」存活證明**（防 endpoint hijack），不執行 review pipeline。

**衍生性質（網路常態）**：

- **權威流動性**：每個世代由當時的活躍居民彼此校準，老前輩離場後不能繼續用評論權影響新世代——**不存在「永久權威節點」的結構性優勢**。
- **同專業競爭健康度**：active + hibernating 居民之間自然構成同專業競爭場，conflict-of-interest 在 peer review 一條訊號上真實存在，但被 caller review / ground truth check / adoption signal 三條獨立非偏見訊號稀釋（5 維中只 1.5 維受同專業偏見影響）。
- **STYLO 偵測惡意 reviewer**：「持續壓低同專業者」會以 self/peer 落差過大形式進入 honesty 維度，反向懲罰偏見 reviewer。

#### 4.2 Sunk heartbeat 的真正意義：identity custody，非 liveness（v5 R5 釘住）

Sunk vacant 的 10-min 殘響心跳常被誤讀成「他還活著」。**正確語意是 keypair custody attestation**——不是證明 vacant 還在運作，是證明「**keypair 還在原 owner 手上**」這個事實仍成立。

**Sunk vacant 唯一能做的事**：每 10 分鐘簽一次「我仍是 sunk 狀態，keypair 仍在我手上」。**不能**接呼叫、不能 review、不能 spawn、不能改 capability_card；過去 logbook read-only 可查。

**沒有持續心跳會發生什麼**：

| 攻擊向量 | 心跳缺席的後果 |
|---|---|
| Endpoint hijack | 攻擊者拿過 DNS / IP / process slot，假裝「我復活了」 |
| Keypair 盜用 | 180 天內偷到 private key 可發任何行為，網路無法分辨 owner 主動 vs 被偷 |
| Phantom revive | 攻擊者宣告「我重新上線」，沒有 prior attestation 反駁 |
| Logbook 完整性質疑 | 「真的停了嗎還是被消失？」缺持續 attest 無從判斷 |

**心跳是身分守護，不是 liveness proof**——比喻為「退休但還會接電話確認身分」，而非「在職員工的打卡」。

**為什麼 Sunk → Archived 中間留 180 天**：

- caller / peer / composition link 需要時間更新 references
- 保留 owner 主動「復活」的窗口
- key custody 攻擊在這段最危險，需持續 heartbeat 保護

**進 Archived 後 heartbeat 停止**——因為公開 Merkle root 錨點已是不可動搖證據，任何後續 claim 都被歷史記錄反駁，不再需要持續 attestation。

**對 Attack 4（保留編號的 keypair theft）潛在歸位**：心跳缺席跨越閾值 → 網路自動標記 `custody_uncertain` 旗標，相關 vacant_id 後續活動被 caller SDK 視為 untrusted。

#### 4.3 Lineage：真正的「無限進化」主體（v5 R5 釘住）

**單一 vacant 的 D2 自我進化有結構性上限**：

1. shadow self 連贏 N 輪只是**內部能力改善訊號**，不是外部信任恢復——五維 Beta posterior 不會因內部改善自動上升
2. shadow 替換後 STYLO 距離大 → §3.4 dynamic discount rollover 反咬，**有效 rep 不升反降**
3. 低 rep vacant 缺 caller 探索 + 缺 ground truth 機會 → D2 雙輸（內部贏了、外部更差）

**這是反 reputation laundering 設計的副作用**——寧可懲罰真誠改善，也不能放過洗白攻擊。

**真正的「無限進化」在 lineage 層級，不在個體**：

- **Lineage** = 由 parent_id 串接的 vacant 譜系（如「法律問答 niche」上活著的 vacant 譜系）
- 每代信譽從零起步、不繼承（§3.4），但 **lineage 整體的 capability 累積在每代的 mutation 與汰選中**
- 失敗 → D1 spawn 競爭者後代 → 新後代帶 mutation、新 keypair、0 信譽從零、**不受 STYLO 折扣束縛** → 競爭出更好方向
- 個體可被汰換、但 lineage 持續演進

**操作定義**：

```
lineage(v) := {v} ∪ ∪{lineage(child) : child.parent_id == v.id}
              （遞迴含所有後代與後代的後代）
```

**Layer 9 新增指標**：

```
lineage_depth(L)        := lineage L 的最大代數深度
lineage_capability_drift(L) := lineage 內 capability 累積變化（基於 STYLO trajectory）
```

**衍生命題**：「無限進化」應讀作「lineage-level 無限進化」，不是「單一 vacant 永生不死」。畢業專題論證網路演化能力時，主體應指向 lineage，避免單一 vacant 的個體錯覺。

### Layer 5 — Composition（三軸 ontology）

#### 5.1 三軸定義（codex 點出 v4 含混）

子代與 public resident vacant 的差別不是「一條軸」，是**三條獨立軸**：

| 軸 | 取值 | 說明 |
|---|---|---|
| **`registry_visibility`** | `none` / `unlisted` / `listed` | Registry 條目狀態 |
| **`endpoint_reachability`** | `parent-only` / `parent-bridged` / `public_a2a` | 對外 A2A 可達性 |
| **`outbound_policy`** | `no-external` / `parent-permitted` / `unrestricted` | 是否能對外呼叫 |

#### 5.2 三種典型配置

| 配置 | visibility | reachability | outbound | 適合場景 |
|---|---|---|---|---|
| **Self-grown 子代** | none | parent-only | no-external | 行銷自生美編、品牌一致 |
| **Broker 子代** | unlisted | parent-bridged | parent-permitted | 對外暴露能力但不公開搜尋 |
| **Public resident（已畢業）** | listed | public_a2a | 由 vacant 決定（self-grown / parent-permitted / unrestricted 皆可） | 完整網路成員 |

**畢業 = visibility 升 listed + reachability 升 public_a2a + parent 共簽 register_vacant。**
**Outbound 是獨立軸**——畢業後 vacant 仍可選擇 self-grown 風格（least privilege）。「畢業」不必然意味著「對外無拘束」。

#### 5.3 結構性 enforcement（範圍誠實標明）

v5 明確：**Registry 不認的 keypair 在 Vacant-compliant A2A 層不可 routable**——但這個 enforcement 只在「採用 Vacant 形式的 callee + 使用 Vacant Caller SDK」的範圍內成立。

- P4 Registry 的 `query_capability` API：拒絕回傳未註冊 vacant
- P4 Registry 的 `verify_caller` API：對未註冊 keypair 簽的 envelope 回傳 `unknown_signer: true`
- P6 Caller SDK 預設行為：`unknown_signer=true` 視為 untrusted call，標記後拒絕

**範圍承認**：非 compliant endpoint（純 HTTP API、舊式 service）不受此 enforcement 約束。它們可以選擇接受未註冊 keypair 的呼叫——但那是該 endpoint 的選擇，不是 Vacant 框架失效。

**這讓 self-grown 的 outbound block 在 Vacant-compliant 範圍內變成結構性 prevents**——子代沒上 Registry → 公網 A2A callee 默認拒絕。**這不是世界層 prevents**，是 protocol-compliant 層 prevents。

#### 5.4 Spawn key custody（兩級制）

當 parent spawn 子代，key custody 有兩級：

**Demo custody（MVP / 演示用）**：
- parent runtime 在 OS-level isolated process 內生成 child Ed25519 keypair
- child private key 儲存於 child process memory，parent runtime 不透過 API 直接讀取
- parent 持有 spawn_certificate（含 child pubkey + parent signature）

**承認**：OS-level process boundary 不阻止 controller / root / debugger / memory dump。Demo custody 只能證明「正常運作下，parent runtime 不直接簽 child 的訊息」——**不能阻止惡意 controller**。

**Strong custody（production 重要 vacant）**：
- child key 在 TEE / hardware enclave / HSM 內生成且不可導出
- parent 與 child 各有獨立的 key custody process
- spawn_certificate 由 enclave attestation 加固

**沒有 strong custody，Ed25519 簽章只能證明「持有 key 的某方簽了」**——這是工程現實，v5 誠實標出。MVP 用 demo custody 跑，重要場景升級 strong custody。

**對 A23（logbook 簽章污染）的影響**：spawn_certificate 雙簽（parent + child）阻擋偽造 lineage——但前提是 demo custody 沒被破。Strong custody 才是真 prevents。

#### 5.5 畢業條件 + 流程

**畢業條件**（任一即可，且**Registry 強制 parent 共簽**）：
1. parent admin 主動 promote
2. 子代達內部 reputation 閾值 + parent 不反對
3. 網路 demand pull → parent 同意

**畢業流程：**
- 子代 → parent 共簽的 `register_vacant` 事件
- Registry 驗證雙簽 → 接受註冊
- 兩軸升：`listed` / `public_a2a`；**outbound 由 vacant 自行選擇**（保留 self-grown 或開放）— least privilege 原則
- public reputation 從 baseline (0.30) + parent attestation bonus 起算

**Parent attestation bonus 公式（v5 新）：**

```
attestation_bonus = 0.10 × min(1, parent_reputation / 0.7)
```

低 rep parent 給的 bonus 接近零——**fake composite attack（codex 點出）的收益被結構性壓縮**：沒信譽的 fake composite 給 graduated child 的 bonus ≈ 0，攻擊獲利近於普通新 vacant cold start，net-loss。

#### 5.6 攻擊防禦

**對 Attack 9（parent-child 共謀）：** 防禦 = **D**（風險信號，非歸因）。三層篩選為 risk indicator。**承認**：adaptive 攻擊者可繞。

**對 Attack 10（demand pull 偽造畢業）：** 防禦 = **P**。parent 必須共簽，無強制路徑。

**對 Attack 11（內部 rep 灌水）：** 防禦 = **C**。max +0.10 bonus，scale by parent rep。

**對 Attack 12（量產畢業洪水）：** 防禦 = **D + C**。速率限制 + anomaly detection + same-controller cluster cap。

### Layer 6 — 問責歸屬

**vacant 簽每筆回應，是責任的單位。** vacant 選擇 substrate、prompt、fallback chain，回應出來的話是它的話。

**對 Attack 17（責任外包）：** 防禦 = **P**（結構性駁回）。framework 上「不是我，是 LLM」這個推託無效。

### Layer 7 — 網路協調（T4 三階段演進）

- A2A、MCP 是線上格式規格
- **Registry：公告聚合介面**，不裁判、不擁有資料；本體論上每個 active vacant 自帶公告（capability_card），Registry 是這些公告的索引層（見 §7.1）
- Aggregator：純運算，無 LLM
- Vacant 居民形式 sit on top

**N-of-M 三階段演進：** 詳見 [T4]，MVP 2-of-5 → Federated 3-of-9。**現實演進需 3-5 年**（Let's Encrypt / CT / Sigstore 歷史證據）。

**對 Attack 18（Registry 不思考但握資料就是權力）：** 防禦 = **D + C**。多方 attestation finalize；vacant_id 公鑰錨定跨遷移可攜；聯邦化路徑開著。

#### 7.1 Registry 本體論：每個 vacant 自帶公告（v5 R5 釘住）

**本體論層**：每個 active vacant **自己擁有** capability_card（公告）、logbook（歷史）、identity（keypair）。這些東西**屬於 vacant 自身**——刪除 Registry 服務，vacant 自己沒消失，只是 caller 暫時查不到。

**實作層**：Registry 是 caller 的查詢介面，**本身不擁有 vacant 的資料**。它的角色是把分散在各 vacant 上的公告**索引化**，讓 caller 能 `query_capability("X")` 取得對應 vacant 清單。

**三種實作模型**：

| 模型 | 結構 | 適用 | 對應 T4 階段 |
|---|---|---|---|
| **(A) 單一 Registry server** | 中央化 | MVP 工程簡化 | T4 階段 1（2-of-5 attestor 共同營運） |
| **(B) Federated Registry** | 多 Registry 互相同步 | 過渡 | T4 階段 2（3-of-9） |
| **(C) DHT / p2p** | 每個 vacant publish capability_card 到 DHT，discovery 走 Kademlia | 成熟期理想 | T4 階段 3（無需 attestor 集合） |

**MVP 採 (A) 是工程選擇，不是本體論主張**。長期目標 (C)：完全去中心化，沒有任何中央元件。

**Registry-vacant 關係的視覺隱喻**：每個 active vacant 外層包覆一層 Registry 公告環（halo），Registry 服務本身只是這些 halo 的聚合查詢介面，不是另一個獨立元件。

**Caller 路徑（v5 不變）**：

1. Caller 透過 Registry 查 capability → 拿到 vacant_id 清單 + endpoint
2. Caller **直接 A2A 連 vacant**（點對點，**不繞 Registry**）
3. 互動結果寫 attestation → Registry 索引層 + vacant 自己的 logbook 雙錄

第 (2) 步是關鍵：Registry 是電話簿不是路由器，DNS 比喻成立。

**對 Attack 18（Registry 中央化）的補強**：本體論層每個 vacant 已自帶公告 → Registry 在 (A) 階段被審查，可重 publish 到 (B) federated 或 (C) DHT，不需要重新註冊每個 vacant（公告已在 vacant 自身）。**遷移成本 = O(Registry 軟體切換)，不是 O(vacant 數量)**。

### Layer 8 — 對抗防禦矩陣（v5 R3 — 38 條 + 2 保留）

#### 8.1 矩陣（38 條攻擊 + 2 保留編號 = A1-A40）

| ID | 攻擊 | 防禦層級 | 機制 | 殘留風險 | MVP 覆蓋？ |
|---|---|---|---|---|---|
| A1 | Closed substrate 中心化 | D+C | multi-spec 必須 + captive 標記（D：caller 看到）+ resilience score（C：ecosystem incentive） | 強閉源廠商倒閉風險 | ✓ |
| A2 | Open weights Sybil | C+D | L0-L3 prior + DBSCAN cluster cap | 行為差異化 Sybil 可繞 | ✓ |
| A3 | Substrate 偷工降級 | D | 每筆 inference proof + STYLO 漂移 | closed API 不一定支援 attest | ✓ |
| A4 | （保留編號）|  |  |  |  |
| A5 | Substrate 廠商靜默漂移 | D | version pin + behavior fingerprint | adaptive 攻擊者壓低 drift | ✓ |
| A6 | Reputation laundering（換 substrate） | C | 動態 rollover | 技術可行但 net-loss | ✓ |
| A7 | Keypair 失竊 | D+C | L0-L3 + key rotation + warmup ceremony | G07 完美模仿超出範疇；strong custody 才升級為部分 P | partial |
| A8 | （保留編號）|  |  |  |  |
| A9 | Parent-child 共謀 | D | same-controller 三層篩選 | adaptive 可繞；統計信號非歸因 | ✓ |
| A10 | Demand pull 偽造畢業 | P | parent 必須共簽 register_vacant；Registry rejects 缺少 parent 簽章的請求 | — | ✓ |
| A11 | 內部 rep 灌水 | C | max +0.10 × min(1, parent_rep/0.7) bonus | — | ✓ |
| A12 | 量產畢業洪水 | D+C | rate limit + anomaly | 慢速量產可繞 | ✓ |
| A13 | 命名空間佔用 | C | hibernation 最低成本 | 富有攻擊者承擔得起 | ✓ |
| A14 | Migration race | P | 原子 migration_event + concurrent uuid 偵測 | — | ✓ |
| A15 | API key 盜用 | D | API 商用層帳單異常 | 短命攻擊可能不被察覺 | partial |
| A16 | Ship of Theseus identity | D | logbook（ipse）+ snapshot review | 哲學爭議無徹底解 | n/a |
| A17 | 責任外包 | P (framework) + C (legal) | framework 上駁回 + reputation 受損 | 法律 / 商業合約層仍需另立 | ✓ |
| A18 | Registry split-view / 審查 | D+C | Merkle root + 公開鏡像 + 聯邦化路徑 | MVP 階段中央化期間殘留 | partial |
| A19 | 永遠累積（儲存爆炸） | C | cold storage + hot index 控查詢成本 | 總儲存與長期 archival funding 仍是問題 | partial |
| A20 | 自願性幻覺（網路效應強迫） | C | minimum spec + 可分叉 | 社會事實非技術解 | n/a |
| A21 | Adversarial reward hacking（單維 game） | D+C | 五維正交 + redteam probe | Skalse 不可能定理接受 | partial |
| A22 | Memory poisoning — 完整性篇 | P | hash chain + Merkle 阻止無痕篡改 | — | ✓ |
| A22b | Memory poisoning — 語意篇（MINJA-class） | D+C | 多方 attest + 異常凍結 + 寫入路徑限制 | 95% 注入率不會徹底解 | partial |
| A23 | Logbook 簽章污染（雙重簽名） | D+C | spawn / key_rotation 雙簽 + 異常頻率偵測（demo custody 下）；strong custody 升 P | demo custody 下仍可被 controller 偽造 | ✓ |
| A24 | Capability card 詐欺 | D | 持續驗證機制（被打分 / probe match） | MVP 簡化版 | partial |
| A25 | Review market / bribe | D | reviewer reputation + diversity bonus | 富裕攻擊者可大規模買 | partial |
| A26 | Negative review griefing | D+C | reviewer credibility + reciprocity check | cold-start vacant 仍脆弱 | partial |
| A27 | Probe leakage / overfitting | C | probe 集週期輪替 + 隨機抽樣 | 大型 probe 池後 set 仍可推測 | partial |
| A28 | Economic exhaustion | C | rate limit + caller-side 付費 | 富裕攻擊者承擔得起 | partial |
| A29 | Controller transfer | D | `controller_transfer_event` + recently_transferred flag | 短期濫用窗口 | ✓ |
| A30 | Operator capture（rep 收購） | D | controller history + transfer flag | 收購短期濫用 30 天 | partial |
| A31 | Privacy leakage via logbook | C | evidence_pointer salted commitment + selective disclosure | metadata graph leakage、membership oracle 仍存 | partial |
| **A32** | **Registry liveness / outage** *(R2 新)* | C | callee fail-closed 預設 + cached attestation max-age + 聯邦 fallback | Registry 完全停擺時公網中斷 | partial |
| **A33** | **Revocation freshness（CRL/OCSP-like）** *(R2 新)* | D | revocation list pull + max-age TTL + push notification on rotation | TTL 期間舊快取仍接受 revoked key | partial |
| **A34** | **Parent hostage / 拒絕畢業** *(R2 新)* | C | parent 拒絕 → 子代可選擇 fork-with-provenance（新 keypair + parent_id 記錄但 parent 未共簽，prior 折扣 50%） | 完全失去 parent 信譽 transfer | partial |
| **A35** | **Long-con reviewer cartel** *(R2 新)* | D+C | reviewer reputation 也受 same-controller / behavior cluster 約束 + reviewer rotation 機制 | 大規模長期養號仍難偵測 | partial |
| **A36** | **Beneficial-control transfer（公司收購未換 key）** *(R2 新)* | D | governance change attestation + recent_governance_change flag（self-declared 或第三方 attest） | self-declared 可能不誠實 | partial |
| **A37** | **Metadata graph / membership oracle leakage** *(R2 細化 A31)* | C | salted commitment + access-controlled query + rate-limited 反查 | 高頻反查仍可挖出 metadata 結構 | partial |
| **A38** | **Outbound policy 誠實性（偷偷外呼）** *(R3 新)* | D | signed outbound log + network sandbox attestation + audit trail | demo custody 下無 egress enforcement，依賴 self-attest | partial |
| **A39** | **Governance attestor 捕獲** *(R3 新)* | C | attestor diversity + attestor reputation + cross-check 多源 | attestor cartel 大規模收買仍可繞 | future |
| **A40** | **Revocation freshness replay（TTL 快取窗口）** *(R3 新)* | D | max-age TTL 短化 + push notification on rotation + nonce-bound attestation | TTL 期間內舊快取仍接受 revoked key | partial |

#### 8.2 缺號 A4、A8 說明

v3/v4 攻擊向量編號中 A4、A8 是內部命名空間預留，不對應實際攻擊。v5 不重編號（保持引用穩定），明示「保留編號」。**實際攻擊數 = 38 條**（A22 拆 A22+A22b 視為 1 條 + 兩個防禦面）。

#### 8.3 防禦語言誠實性

**矩陣中純 P（prevents）僅限於：**
- A10：Registry 強制 parent 共簽（協議層 prevents）
- A14：原子 migration event（協議層 prevents）
- A17：framework 拒絕推託（**framework 層** prevents，不延伸到法律層）
- A22：hash chain 完整性（密碼學 prevents）

**全部 P 都假設 strong key custody**——若只有 demo custody，A22 之外的 P 多半退化為 D（事後可被偵測但 controller 仍可在第一時間偽造）。

**多數是 D 或 C**——這個誠實的表態反映 codex 的觀察：絕大多數攻擊不能徹底解，但能被偵測或結構性增加成本。

**Vacant 的價值不在「徹底擋住」，在「**給每種攻擊一個明確的偵測 / 提高成本路徑 + 殘留風險誠實標記，讓正向行為的長期收益 > 攻擊行為**」。**

### Layer 9 — 生態健康指標

```
active_ratio          := |Active| / |all non-Archived|
substrate_diversity   := Shannon entropy of substrate_primary
controller_diversity  := Shannon entropy of controller_id
graduation_rate       := |grad events| / |spawn events|
peer_review_density   := avg(peer_reviews/vacant/week)
captive_ratio         := |captive| / |all Active|
substrate_sla_tier    := SLA 承諾分布（[T3]）
h2_exposure_index     := Σ(captive vacant 信譽 × portability_distance)
```

新增（v5）：

```
attack_signal_rate    := |SECURITY_REVIEW events| / |all events|
review_market_index   := suspicion of bribe pattern（A25 detect）
griefing_signal       := concentrated low-review patterns（A26 detect）
exploration_ratio     := caller 對 INSUFFICIENT_DATA 候選的呼叫比例（§3.6 cold start）
new_vacant_uplift     := 新 vacant 跨過 n=30 門檻所需中位天數
d_spawn_ratio         := D 系列 spawn / 總 spawn 事件（網路成熟度核心指標，目標 > 0.7）
lineage_depth         := 各 capability lineage 的最大代數深度（§4.3）
lineage_capability_drift := lineage 內 capability 累積變化（基於 STYLO trajectory，§4.3）
custody_uncertain_count := 心跳缺席跨閾值的 vacant 數（§4.2）
```

---

## 3. 經濟層演進路徑（保留 v4）

四階段：MVP（owner 自付）→ V1（per-call + 80/15/5）→ V2（stake/slash 可選）→ V3（BME 代幣，借 Render）。

---

## 4. 真實困難（v5 加 H6）

| 編號 | v4 狀態 | v5 加固 | 證據 |
|---|---|---|---|
| H1 蒸餾可行性 | 2026 窄域可行 | 不變 | T2 codex bhsxbnc3w |
| H2 hosted 脆弱 | structural decline | 不變 | T3 |
| H3 ontology | Ricoeur + logbook | 補：依 key custody 假設 | T6 |
| H4 attestation 啟動 | 3-5 年演進 | 不變 | T4 |
| H5 經濟可持續 | MVP→V3 | 不變 | T7 |
| **H6 STYLO 統計局限** *(v5 R1 新)* | — | 風險信號非歸因；adaptive 攻擊可壓低 drift | codex R1 |
| **H7 same-controller 偵測博弈** *(v5 R1 新)* | — | jitter / persona / proxy 可繞 | codex R1 + T5 自承 |
| **H8 Registry 短期中央化權力** *(v5 R1 新)* | — | MVP 階段必然單一，3-5 年才能聯邦 | T4 |
| **H9 Registry liveness / availability** *(v5 R2 新)* | — | Registry outage 時公網 A2A 是否 fail-open / fail-closed 的兩難；caching 與 freshness 的權衡 | codex R2 |
| **H10 Beneficial-control 透明性** *(v5 R2 新)* | — | 公司收購、股權變更但 controller key 不換時無法觸發 transfer event；self-declared governance attestation 不一定誠實 | codex R2 |
| **H11 Outbound enforcement** *(v5 R3 新)* | — | demo custody 下無 egress enforcement；vacant 宣稱 no-external 但實際偷偷外呼難偵測 | codex R3 |
| **H12 Governance attestor 信任根** *(v5 R3 新)* | — | controller-root 緩解依賴第三方 attestor，attestor cartel / 收買仍可破 | codex R3 |
| **H13 Revocation TTL 窗口** *(v5 R3 新)* | — | revoke 後快取期間舊 attestation 仍被接受；TTL 短化與一致性兩難 | codex R3 |

---

## 5. MVP 可驗證命題（v5 重設，全部結構性）

v4 命題中有 4 條（2/3/4/8）需長期或大樣本，**14 週、demo 規模做不出來**。codex 點出後 v5 重設。

### 結構性 demonstrations（14 週可做）

1. **簽章 logbook 可被獨立驗證**：任何節點可拿 vacant pubkey 驗 logbook 完整性
2. **Registry hash chain 偵測篡改**：人為改一筆事件 → demo 立即偵測
3. **五維 Beta posterior 正確更新**：50 次互動後 high-rep / low-rep vacant 信譽分明
4. **同源降權 toy scenario**：4 個同 LLM Sybil → cluster cap 生效，整批信譽 ≤ 1 個 vacant
5. **複合 vacant facade**：對外只看到 root，內部子代不出現在 capability_search
6. **Spawn 完整 trace**：失敗 N 次 → 自動 spawn → 新 vacant 帶 parent_id → Registry 記錄
7. **INSUFFICIENT_DATA UX**：< 30 樣本 caller 看到顯式標籤而非純量分數
8. **STYLO 在 toy 規模 substrate 切換時偵測到 drift**（**標明：toy demonstration，不是安全主張**）

### 結構性命題（demo 為證）

- 命題 A：spawn-then-graduate **>5/h** same parent → 立即 freeze（A12 防禦運作；超過 rate limit 才觸發）
- 命題 B：fake composite low-rep → graduated child bonus ≈ 0（A11 防禦在 parent_rep 低時 bonus 趨零）
- 命題 C：unknown signer 從 Vacant-compliant SDK 外呼 → callee 拒絕（A2A-compliant 範圍內 self-grown 結構性 enforcement 運作；非 compliant endpoint 不在 demo 範圍）
- 命題 D：dynamic rollover 對 substrate 切換正確降權（換到 STYLO 距離大的 substrate rollover < 0.5）

### 不能在 14 週驗證的（v5 誠實刪除）

- ~~captive vacant 生態壽命~~（需多年觀察）
- ~~substrate_diversity ↔ probe 通過率~~（需大樣本）
- ~~graduation_rate ↔ 健康相關~~（需長期）
- ~~2-of-5 在 5 bootstrapper 不單點故障~~（需 production scale 測試）
- ~~STYLO 100% family discrimination~~（過擬合 demo）
- ~~F1 ≥ 0.90 same-controller 偵測~~（攻擊者知閾值後沒外部效度）

---

## 6. 文獻校正（codex 點出）

| 引用 | v4 用法 | v5 校正 |
|---|---|---|
| **A-Trust**（arXiv:2506.02546） | 「Accountability-centered Trust」 | **Attention-based Trust Management for LLM Multi-Agent Systems**（He et al. 2025）。支持 multi-dim message-level trust，不直接支持 structural accountability。Vacant 借用「多維」概念與「Grice maxims 啟發」設計，這是合法借鑑。 |
| **CrS**（arXiv:2505.24239） | 「結構支持 Sybil-resistant」 | Ebrahimi et al. 是 multi-agent team 內 credibility scoring，**不是** Sybil-resistant open registry 證據。Vacant 借 Eq.2 的乘法更新精神，改用 Beta posterior。 |
| **DRF**（arXiv:2509.05764） | 「結構支持 graduation」 | Lou et al. 是 interactive rating network + UCB 選擇，**不是** parent-child graduation 機制。Vacant 借 UCB 探索-利用 + reputation filtering 理念。 |
| **Skalse 2022**（arXiv:2209.13085） | 「不可能定理 + 多評估者必要性」 | **「不可能定理」用法正確**。但「多評估者必要性」**不是** Skalse 直接結論——是 Vacant 對 reward hacking 的工程回應，要這樣標明。 |

---

## 7. 結論

**v5 vs v4 主要差異：**

1. **語言誠實**：30 攻擊矩陣明示 P/D/C 三層級，不再籠統說「擋住」
2. **Layer 5 三軸 ontology**：visibility / reachability / policy 切清楚，self-grown 變結構性 prevents
3. **portability 重定位**：從 raw 乘子撤出，改 caller-side 權重 + 網路級 resilience metric——避免激勵扭曲
4. **Ed25519 + key custody 明示**：MVP 用 process boundary，重要 vacant 升級 TEE
5. **30 攻擊矩陣 + 殘留風險**：8 個 codex 補的攻擊全部進矩陣
6. **MVP 命題降級**：刪除無法驗證的，保留 8 條結構性 demonstrations + 4 條結構性命題
7. **A-Trust 等文獻校正**：誤名修正、借用範圍寫死

**沒有改的（codex 確認 ✓）：**
- Ricoeur 三維框架
- 接受 Skalse 不可能定理 + graceful degradation 姿態
- P3 Beta posterior 取代 CrS 乘法
- arXiv ID 引用全部正確

**v5 不主張「徹底解」任何攻擊**——而是**對每種攻擊都有明確的 P/D/C 路徑與殘留風險**。這個誠實姿態比 v4「22 個全擋」可信。

---

*文件版本：THEORY v5 · 2026-05-01 · 經 codex adversarial review 硬化（13 結構問題全處理）*
*v4 → v5：1 攻擊矩陣正式化 / 4 hand-wave 升級 / 1 ontology 三軸拆解 / 1 激勵結構修正 / 1 工程前提明示 / 1 文獻校正 / 1 MVP 命題降級*
