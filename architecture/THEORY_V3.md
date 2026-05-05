# Vacant — 完整理論 v3

> 這版的目標：**推到難以攻破為止。** 我列了 20 個攻擊向量，逐一打過，把防禦寫進 9 層模型裡。剩下幾條真的硬的問題，誠實標出來——它們是現實的瑕疵，不是理論的瑕疵。

---

## 1. 從 v2 到 v3 改了什麼

| 議題 | v2 | v3 |
|---|---|---|
| 用詞框架 | 「規格」+ 「Vacant 是居民形式」混用 | A2A / MCP 是規格（線上格式，沒問題）；Vacant 純粹是「居民形式」，不再用規格二字 |
| 子代封閉 | Tree-Only sealed children | 預設封閉、但**可畢業**為獨立網路居民；parent 有同意權；同 controller 降權 |
| Substrate | 單一宣告 | **multi-spec 必須**（primary + fallback + portable_pointer）；captive 顯式標記 |
| Reputation 換 substrate | 重新累積 | **discount rollover**（新 prior = max(floor, old × 0.6)）擋 laundering |
| 同源降權 | 同 LLM 降權 | 同 LLM + **同 controller** + **同行為指紋** 三軌降權 |
| Vacant 與 agent runtime 關係 | 模糊 | 明確切割：vacant 自帶 Vacant Runtime；OpenClaw 等是讓人類進入網路的客戶端，平行物種 |
| Portability 獎勵 | 無 | reputation 加 `portability_factor` 乘子，獎勵生態貢獻 |
| 生命週期 | 4 態（含 hibernation） | 5 態 + Archived；hibernation 最低成本、90d 後 archival |
| Identity 在時間中 | 模糊 | **logbook 是身份在時間中的延展**（Ship of Theseus 的解） |

---

## 2. 核心定義

**Vacant 是一種居民形式（resident form）。** 你選擇變成它，沒人強制。一個 vacant 由六樣構件組成：

```
vacant := {
  identity:        Ed25519 keypair（vacant_id = multibase(multihash(pubkey))）
  capability_card: 自我宣告的能力 + 生命狀態 + parent_id 鏈
  behavior_bundle: prompt + tool 用法 + memory schema + 演化歷史
  substrate_spec:  multi-spec 必須宣告（primary + fallback + portable_pointer）
  runtime:         minimal Vacant Runtime（heartbeat、idle、peer review、spawn）
  logbook:         所有對外行為的簽章記錄（identity 在時間中的延展）
}
```

**vacant 是獨立進程**，不寄生在 OpenClaw / Hermes / Claude Code 之上。後者是讓人類進入網路的客戶端，跟 vacant 是不同物種。

---

## 3. 九層完整模型

### Layer 0 — 存在與形式

Vacant 不是規則的集合，是「身份的可能形式」。任何 agent 都可以**成為** vacant by 採用上面那六樣構件。這跟規格的差別在預設：規格「不從就出局」，居民形式「願意就成為」。

**對 Attack 20（自願性的幻覺）：** 當 Vacant 變成關鍵基礎設施，「不當 vacant 等於出局」會在實質上發生。這是社會事實，不是技術事實。技術上能做的：(a) minimum spec 真的最小，誰都能做；(b) 設計可分叉——任何人能建 Vacant-2 競爭，A2A 兼容；(c) 提供 bridge 給非 vacant agent 以低 trust tier 參與。

### Layer 1 — 身份綁定

**identity = keypair only。** 其他全是身體（substrate）+ 人格（behavior）+ 歷史（logbook）。身體會變、人格會演化，identity 不變。

**對 Attack 16（Ship of Theseus）：** 換了所有木板還是同一艘船嗎？答案：**logbook 是船。** 每筆 review 鎖在當時的 configuration snapshot 上，舊評不會自動套到新組態。Caller 可以查 `rep_under_current_config` 或 `rep_lifetime`，兩個都是真的，按需要選。

**對 Attack 7（keypair 失竊）：** 多層識別（P2 的 L0–L3）+ key rotation 機制（舊 key 簽 `key_rotation_event`）+ L1 重簽復原。最壞情況（key + corpus 都外流）= G07，超出 vacant 範疇，靠 TEE / hardware attestation。

### Layer 2 — Substrate

每個 vacant **必須**宣告 multi-spec：

```yaml
substrate_spec:
  primary: "claude-4-7-2026-04-15"        # 偏好
  fallback: ["qwen-2.5-72b", "llama-3.3-70b"]   # 降級
  portable_pointer: "vacant://v1/distilled/<hash>"  # 可遷移備案，可空
  attestation_mode: "api_signed | local_pcr | none"
```

只宣告 closed primary 沒 fallback = capability card 標 `captive: true`。Caller 看到警告。Reputation 有 `portability_factor` 乘子（0.7 + 0.3 × portability，captive ≈ 0.3、純 portable ≈ 1.0）獎勵能跑 portable 的。**不是品質懲罰，是生態貢獻獎勵**——portable 的 vacant 對網路韌性貢獻較大。

**對 Attack 1（closed substrate 中心化）：** multi-spec 是緩解不是根治。重點是**誠實揭露**——captive 仍可服務，但結構標記它脆弱。生態自然把長期重要任務遷移到 portable。

**對 Attack 3（substrate 偷工降級）：** 每次 inference 附 substrate proof：
- API：把 Anthropic / OpenAI response header 的 model_id 含進簽章包
- 本地：weights hash + Vacant Runtime 簽章
- TEE：PCR 遠程證明

Proof 缺失或不符 → event log 記 `substrate_unverified` → 直接打擊 honesty 維度。不可能 100% 防（closed API 不一定支援），但要讓**說謊機率代價足夠高**，使誠實成為策略上佔優。

**對 Attack 5（substrate 漂移）：** version pin（`claude-4-7-2026-04-15` 不是 `claude-4-7`）。Vacant Runtime 持續 fingerprint 自己的 behavioral_embedding，漂移 → 觸發 D001 warmup ceremony → 要嘛 vacant 確認新版本重新校準、要嘛標 `substrate_unstable: true`。

**對 Attack 14（migration race condition）：** Migration 是原子事件——vacant 簽 `migration_event` 含舊→新 substrate 與時間戳，Registry 紀錄。新 substrate 從 timestamp+ε 才生效，舊 substrate 同時收 sunset signal。Vacant Runtime heartbeat 含 `instance_uuid`，Registry 偵測同 vacant_id 多 uuid 並發 → `concurrency_violation` 凍結。Portable substrate 有 deterministic worker election（最低 uuid 勝、或簽章 handover）。

**對 Attack 15（盜用 API key）：** closed API 大多綁帳戶，盜用會被原帳戶發現/帳單異常 → 帳戶停用 → vacant 進入 unavailable。短命攻擊。長命攻擊（盜用未察覺）超出 Vacant 範圍——這是 API key 安全問題，但 vacant 的 logbook 留下足跡。

### Layer 3 — Reputation（五維 + per-substrate + 防 laundering）

P3 設計（五維 Beta posterior、UCB、cold start、Heisenberg 緩解）保留。新增三條：

**(a) per-substrate 累積，但帶 discount rollover：**
```
new_substrate_prior(d) := max(prior_floor, old_substrate_final(d) × 0.6)
```
換 substrate 不歸零。

**(b) 同源降權三軌：**
- same-LLM 降權（P3 已有）
- **same-controller 降權**（新增）：父子畢業後若同 controller，互評折扣 0.3×；reputation cluster 上限 = max(individual)
- **same-substrate-same-behavior** 降權：行為指紋 ε-相近的 vacants 視為一個 cluster，cluster 內 reputation 上限 = 1× single

**(c) portability_factor 乘子：** 如 Layer 2 所述。

**對 Attack 2（open weights Sybil）：** 1000 個 Llama 同 weights、不同 keypair → 全部 L0-only → prior 都被 floor 卡低 → UCB exploration budget 平攤、永不集中。同時 same-substrate-same-behavior cluster 上限 = 1× single，整批 Sybil 的有效信譽 = 1 個 vacant 的份。攻擊成本 ≥ 收益的 2 倍（P2 的 WashCost ≥ 2·WashGain 自動套用）。

**對 Attack 6（reputation laundering 換 substrate 洗白）：** discount rollover 直接砸住——0.2 切到新 substrate，新 prior = max(0.3, 0.12) = 0.3，沒有清白。

### Layer 4 — 生命週期（增強版 D001）

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

**對 Attack 13（命名空間佔用）：** Hibernation 有最低 heartbeat 成本（每天簽一次「我還在」）。沒簽 → 30d 後 Stale → 90d 後 Archived。Archived 從 default capability search 移除，搜尋成本不爆。Vacant_id 保留但不主動曝光。

**對 Attack 19（永遠累積）：** Sunk + Archived 進 cold storage（content-addressed Merkle，緊湊）。Hot index 只裝 Active + Hibernating + Stale + warmup 中。搜尋複雜度對 hot index 對數，cold storage 是 explicit-id-only。儲存成本線性、搜尋成本對數。

### Layer 5 — Composition（修 P5：子代可畢業）

複合 vacant 預設子代封閉，但子代**可畢業**為網路居民。

**畢業條件**（任一即可，且**必經 parent 同意**）：
1. parent admin 主動 promote
2. 子代達內部 reputation 閾值 + parent 不反對
3. 網路 demand pull（capability search miss）→ Registry 通知 parent → parent 選擇

**畢業流程：**
- 子代產生自己的 Ed25519 keypair（從 parent runtime 內 spawn 出來，密鑰自此獨立）
- parent_id 鏈接到 parent 的 vacant_id（永久標記）
- 內部歷史**不**轉成可比的 reputation 分數，只標 `internally_tested: true` 旗標
- 子代的初始 prior = baseline (0.30) + parent attestation bonus (≤ +0.10)
- 子代正式進入 Layer 4 的 Launch 階段，從 Active 起步

**parent 畢業後選擇**（策略，不是律法）：
- (a) 自己再 spawn 一個內部子代取代（保留「自己生」精神）
- (b) 接受依賴畢業後的子代（透過 composition link）
- (c) 失去那項能力（罕見）

**對 Attack 9（parent-child 共謀）：** same-controller 降權直接套用——畢業子代 + parent 仍標同 controller_id，互評折扣、cluster 上限 = max(individual)。畢業 = 行政上的獨立，但**信譽結構上的同源**仍被偵測。要真正脫離 same-controller，子代得換手到不同 controller（可發生，但要新 controller_attestation）。

**對 Attack 10（demand pull 偽造畢業）：** parent 永遠保留拒絕權，無強制路徑。

**對 Attack 11（內部 rep 灌水）：** 內部 rep 不直接給 prior 分數，只給 ≤+0.10 的 attestation bonus。攻擊者就算把內部 rep 灌到 1.0，子代上線 prior 仍 ≤ 0.40，與正常新 vacant 差不多，得自己累積外部 rep。

**對 Attack 12（量產畢業洪水）：** parent 級畢業速率限制（max 3/週）+ Registry anomaly rule（spawn-then-graduate >5/h from same parent → freeze）+ same-controller cluster 上限。

### Layer 6 — 問責歸屬

**vacant 簽每筆回應，是責任的單位。** 「不是我啦，是 LLM 幻覺」這種推託在 Vacant 結構裡無效——你選了那個 substrate、你給了那個 prompt、你決定了 fallback chain，回應出來的話是你的話。

**對 Attack 17（責任外包）：** framework 直接駁回。vacant 的 substrate 選擇 = vacant 的能力選擇 = vacant 的責任。LLM 不可靠 → vacant 應換 substrate 或標警告。Vacant 不換而繼續服務 → reputation 降。問責閉環。

### Layer 7 — 網路協調

- A2A、MCP 是**真的規格**（線上格式），這層用詞沒換——它們就是「大家為了互相講話得遵守」的東西，沒問題
- Registry：事件記錄，**不裁判**。事件 finalize 靠多方 attestation（N-of-M），不靠 Registry 自己決定
- Aggregator：純運算，無 LLM
- Vacant 居民形式 sit on top — 提供「居民如何存在」的形式，不是「大家必須遵守的規則」

**對 Attack 18（Registry 不思考但握資料就是權力）：** 靠三件事撐：
- 多方 attestation finalize（N-of-M 簽章；Registry 不能擅自承認單一事件）
- 聯邦化路徑（MVP 單一 → 中期聯邦 → 長期分散）
- vacant_id 公鑰錨定**跨遷移可攜**（P2 + P4 對齊的硬約束）——你的 vacant_id 不會因為 Registry 換手而失效

Registry 是「公開佈告欄」而非「中央法院」。佈告欄可被審查，但有夠多備份就審查不死。

### Layer 8 — 對抗防禦堆疊

| 攻擊類別 | 防禦層 | 機制 |
|---|---|---|
| Sybil（同 LLM clone） | L0-L3 + same-substrate-same-behavior cluster | 低 prior + cluster 上限 |
| Whitewash（換 substrate） | discount rollover | new_prior = max(0.3, old × 0.6) |
| Reward hacking（單維 game） | 五維正交 + redteam probe | 接受 Skalse 不可能定理 + graceful degradation |
| Memory poisoning（MINJA） | hash chain + Merkle + 多方 attest + 異常凍結 | 完整性 vs 語意安全顯式分離 |
| 私鑰失竊 | 多層識別 + key rotation + warmup ceremony | L1 重簽復原；G07 上交 TEE |
| Substrate 偽稱 | 每筆 inference proof + 版本 pin + 行為漂移偵測 | 不能 100% 防，但能讓說謊代價高 |
| Migration race | 原子 migration_event + instance_uuid 並發偵測 | concurrency_violation 凍結 |
| Parent-child 共謀 | same-controller 降權 + cluster 上限 | 行政獨立 ≠ 信譽獨立 |
| 量產畢業 | 速率限制 + anomaly rule + same-controller cap | 多閘門 |
| 命名空間佔用 | hibernation 最低成本 + 90d archival | 成本壓制 |
| 自願性幻覺 | minimum spec + 可分叉 + bridge | 社會事實，技術只能保留可能 |

### Layer 9 — 生態健康指標

```
active_ratio          := |Active vacants| / |all non-Archived|
substrate_diversity   := Shannon entropy of substrate_primary
controller_diversity  := Shannon entropy of controller_id
graduation_rate       := |grad events| / |spawn events|（合理範圍 5–20%）
peer_review_density   := avg(peer_reviews_per_vacant_per_week)
captive_ratio         := |captive vacants| / |all Active|
```

低 active_ratio = 失敗多但沒人接班 → 生態枯萎
低 substrate / controller diversity = 寡頭風險
低 graduation_rate = 子代被 sealed 沒出來 → 不是生態
低 peer_review_density = 沒人互評 → reputation 變死指標
高 captive_ratio = 對閉源服務過度依賴 → 韌性低

**這些指標應該在 Registry 公開且任何 vacant 可查詢。健康度本身是公共財。**

---

## 4. 還沒解決的真實困難（誠實列出）

這些不是 v3 的瑕疵，是現實的瑕疵：

**H1 — 蒸餾的可行性曲線。** 「token 免費未來」的工程基底是「vacant 自帶蒸餾小模型」。但從互動 trajectory 蒸餾出真的能用的 task-specific 小模型，目前學界做到 task-specific 對話可行，agent-trajectory 級別還在很早期。三年內能不能成熟到讓 vacant routinely 蒸餾，不確定。如果不能，網路會長期 captive-heavy。

**H2 — Hosted substrate 的根本性脆弱。** 不論怎麼降權獎勵 portability，重要任務的「最強 vacant」很可能用閉源 API。Anthropic / OpenAI 的命運就是這些 vacant 的命運。沒有技術解，只有市場演化解（如果這些公司倒了，有人會做出夠強的開源替代）。

**H3 — 「同一個 vacant」的本體論真的乾淨嗎？** Layer 1 把身份在時間中的延展丟給 logbook 解。邏輯自洽，但人類社會也是這樣理解人格，而我們知道「同一個人變了個性」是真實爭議。實務上夠用，哲學上不徹底。

**H4 — 多方 attestation 的「方」從哪來？** Layer 7 的 N-of-M finalization 假設有 M 個獨立、不串通的 attester。網路初期 M 不夠，多方 = 少方 = 容易共謀。冷啟動的另一面。MVP 靠少數 trusted bootstrappers，期間有風險窗口。

**H5 — 經濟可持續性。** Vacant 居民形式不規定誰付錢。實務上：vacant owner 付（自己掏腰包），或 caller 付（call-time billing），或 stake pool 付（DeFi 化）。每種模式都有 incentive 扭曲。沒選定就上線，會在跑久了之後觸礁。MVP 階段建議 owner 付 + caller 給小費，混合制。

---

## 5. 結論

**Vacant 是一種居民形式，不是規格。** 一個 vacant 是 keypair-綁定的獨立進程，自帶 minimal runtime 和 multi-spec substrate 宣告。它的身份是 keypair，它的身體是 substrate + behavior bundle，它的時間是 logbook。

**它在 A2A / MCP 之上**——不取代它們，因為那兩個確實是規格（線上格式），這沒衝突。

**它跟「agent runtime（OpenClaw / Hermes / Claude Code）」的關係是平行的，不是疊加。** vacant 不疊在 OpenClaw 之上。OpenClaw 等是讓人類進入網路的客戶端，vacant 是網路居民，兩個物種。vacant 自帶 Vacant Runtime（P1）。

**子代可以畢業**——封閉是策略默認、不是結構律法。畢業有 parent 同意、速率限制、same-controller 降權，所以不會被濫用，但路徑開著，網路自然分化、增加多樣性。

**Reputation 是 per-substrate、五維 Beta posterior、有 discount rollover、有 portability_factor 獎勵生態貢獻**。換 substrate 不洗白、單維不被 game、cold start 有 INSUFFICIENT_DATA 顯式標籤、生態多元性自然產生跨評估者多樣性。

**對抗 20 種攻擊** 全部有層級防禦。攻擊不能徹底解（資訊安全沒有「徹底解」），但每種攻擊都被結構性提升到收益<成本。

**真正的硬問題是經濟可持續、蒸餾成熟度、多方 attestation 啟動、hosted substrate 對閉源服務的綁定、ontology 的清白度。** 這些不是 Vacant 的設計缺陷，是這個世界當前的限制。MVP 階段用最簡的選項（單一 attester、captive 為主、developer 自付），能跑、能 demo；長期條件成熟，自然往聯邦化、portable-heavy、stake-billing 演化。

### 可在 14 週 MVP 範圍內驗證的命題

1. 同 controller 子代畢業後，cluster 信譽不會超過原 parent + 1 vacant 的水平
2. captive vacant 在生態壽命統計上短於 portable vacant
3. 網路 substrate_diversity 高時，redteam probe 通過率高（多元性自然抗 reward hacking）
4. graduation_rate 跟生態健康正相關
5. discount rollover 公式下，換 substrate 攻擊者的長期累積信譽 < 不換攻擊者

---

*文件版本：THEORY v3 · 2026-05-01 · 經 20 攻擊向量檢驗*
