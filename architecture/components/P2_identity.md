# P2: 身份錨定 / Sybil / Whitewashing 抗性

> Pane: P2-identity · 主持人: %4 · 版本 v1 · 2026-05-01
> 本文件先行版（codex 學術 raw 輸出見 `research/P2_identity_research.md`）。

## 1. 範圍與目標

**負責**：在「Vacant 是開放網路、無中央仲裁者、無資格審核」三個硬約束下，設計**識別層** (identity layer)，讓 reputation 機制不被 Sybil、whitewashing、collusion 三大經典攻擊在第一週就摧毀。

具體交付：

1. **多層防禦**的 vacant 識別堆疊（L0–L3），每一層獨立且可組合。
2. **Whitewashing 成本函數**——把「換馬甲洗白」這件事用一條公式量化，並證明在合理參數下成本高於收益。
3. **冷啟動 prior**——新 vacant 上線時 reputation 不是 0、不是滿分，而是由 attestation 等級 + 開發者自評（折扣後）+ 探索期 UCB bonus 三部分疊加。
4. **聯邦化路徑**（Q1 答案）——MVP 中央化 → 中期聯邦 → 長期完全分散化的三段路線圖，並要求 vacant_id 在三段之間**可攜**。
5. 對 **P3 reputation 算式** 給出 stake/attestation 訊號接入規格；對 **P4 Registry** 給出身份綁定 schema 草案。
6. 正面回答 BRIEFING §11 的張力 #1（網路淘汰 vs whitewashing）與 #2（無中央 judge vs cold start）。

**不負責**：
- reputation 五維更新公式（→ P3）
- Registry tamper-evident 結構與 SQLite schema 細節（→ P4）
- A2A 規格層 envelope 格式（→ P6）
- 客戶端 SDK 如何呼叫（→ P5）
- vacant Runtime 內部 heartbeat / idle-loop 設計（→ P1）

---

## 2. 設計決策

### D1. 採用「公鑰即身份」(Ed25519) 而非平台帳號

**決策**：每個 vacant 的 `vacant_id` = `multibase(blake3(ed25519_public_key))[:32]`。私鑰由 vacant Runtime 在初始化時生成並本機保存，從未上傳。任何寫入 Registry 的 envelope（review、spawn、self-eval、composition link）必須以私鑰簽章。

**為什麼**：
- 公鑰錨定使 Registry **無法替換 vacant 身份**——Registry 換掉 vacant_id ↔ public_key 對映就能被密碼學發現（簽章驗不過）。這是回應「Registry 雖不思考但握有資料就是權力」的最小機制。
- DID 規格的 `did:key` (W3C DID Core, 2022-07-19 Recommendation) 可直接套用，未來轉聯邦/分散化時 vacant_id 不變。
- Ed25519 比 secp256k1 更快、簽章更短（64 bytes），對「token 免費假設下高頻 peer review」場景友好。

**否決方案**：
- ❌ Registry 內部 incrementing ID：違反聯邦化路徑，且 Registry 換主後 ID 衝突。
- ❌ X.509 證書鏈：太重，需要 CA 信任根，違反「無中央仲裁者」原則。
- ❌ 區塊鏈位址（EVM/Solana）：把整個 vacant 網路綁到一條鏈，gas 成本與「token 免費假設」相衝。

### D2. 防 Sybil 不靠單一機制，靠**深度防禦** (defense in depth)

**決策**：不假設任何單層機制能擋 Sybil。設計四層獨立信號，攻擊者必須同時突破才能 game：

| 層 | 機制 | 抗 Sybil 強度 | MVP 必選？ |
|---|---|---|---|
| L0 | Ed25519 keypair → vacant_id | 弱（只認證一致性，不阻 Sybil） | 必選 |
| L1 | 開發者/組織 sign 的 Capability Card attestation | 中（綁定到 real-world 主體） | 必選 |
| L2 | Stake / Bond（自願抵押） | 強（成本錨點） | 可選，影響 trust weight |
| L3 | Web of Trust (vacant 互簽 not-sock-puppet) | 中-強（社會結構） | 中期啟用 |

**為什麼不是單層**：
- Douceur (2002) 的不可能定理明確指出：**沒有 logically-centralized 身份發行者，或某種資源稀缺性的成本錨**，Sybil 攻擊在一般分散式系統中不可阻。Vacant 拒絕中央發行者，所以**必須引入成本錨**（L1/L2）。
- Friedman & Resnick (2001) 的「Cheap Pseudonyms」結論：在「換身份近免費」的環境中，唯一穩定均衡是「對新人不信任」。Vacant 把這個結論工程化為冷啟動 prior 的低初值 + 探索期樣本不足提示（見 D5）。
- 任一層被攻破不會立即崩潰：例如某 attestation issuer 被滲透 → 其發出的 L1 證明只影響「同一 issuer 簇」的 trust，網路其他簇不受影響。

**否決方案**：
- ❌ 強制全網 stake：違反「無資格審核、任何人可上線」原則，且把窮國/個人開發者擋在外面。
- ❌ 全網 KYC：違反 vacant 可以是匿名/化名的設計直覺，且 KYC creep 是已被批判的反模式。
- ❌ 純 PoW 身份（Nostr NIP-13 風格）：和 Vacant 「token 免費」假設衝突——攻擊者也能享受免費算力。

### D3. Whitewashing 成本函數明確化

**決策**：把 whitewashing 的「換馬甲」決策建模為 vacant 的一個經濟選擇，並設計參數使**成本 ≥ 預期收益**。

定義：
- `R_current` ：當前 vacant 的累積 reputation 五維加權平均（在 0..1）
- `R_prior(t)`：新身份上線時的初始 prior（見 D5），會隨 attestation 等級 t 上升
- `T_ramp`：新身份從 prior 爬到 `R_current` 同等水位所需的成功互動次數期望
- `c_attest`：取得 L1 attestation 的成本（時間 + 信譽風險，可金錢化）
- `c_stake`：L2 抵押成本（金額 × 機會成本利率 × 時間）
- `c_history_loss`：放棄舊身份的歷史價值（包括既有客戶、composition link）

**Whitewashing 成本公式：**

```
WashCost(t) = c_attest(t) + c_stake(t) + c_history_loss + opportunity_cost(T_ramp)
WashGain   = R_current × call_volume × per_call_value − R_prior(t) × call_volume × per_call_value
                       (扣回到新身份的低呼叫量)
```

設計目標：**選擇 attestation 等級與 stake 參數使**

```
WashCost(t) ≥ k · WashGain   (對所有 t，k ≥ 2)
```

**為什麼 k ≥ 2**：給「測量誤差」留兩倍 margin（Friedman/Resnick/Sami, 2007 §27.3 對 manipulation-resistant 條件的鬆緊推論）。實務上，一個惡意 vacant 即使能洗白，也至少要等 `T_ramp` 期間的呼叫損失加上 stake 鎖定費，這已經足以把「失敗就洗」這條經濟最優路徑切掉。

**否決方案**：
- ❌ 直接禁止換身份：技術上做不到（私鑰可以隨時生新）。所以只能讓「換」變得不划算。
- ❌ 全網查 IP / 機器指紋：一進雲端 VPS 全失效，且違反開放網路精神。

### D4. 冷啟動 reputation prior 不是 0、不是滿分，而是**結構化低值**

**決策**：新 vacant 上線時的五維 reputation 各維 prior 由三部分組成：

```
prior_d = base(d) + α · attestation_tier(t) + β · self_declared_history_d
```

其中：
- `base(d)` = 0.30（每維固定低水位，符合 Friedman & Resnick 的「對新人不信任」均衡）
- `attestation_tier(t)` ∈ {0, 0.10, 0.20, 0.30}，對應四級 attestation（見 §3.3）
- `self_declared_history_d` ∈ [0, 1]，從本機養成期數據而來，但 `β = 0.05`（極低權重）
- `α = 1.0`（attestation 是主要可信前綴）

**信賴區間預設極寬**：N=0 樣本，Beta(α=2, β=2) prior，95% 區間 [0.20, 0.80]，UI 必須以「★☆☆☆☆ 資料不足」標籤呈現，**不顯示純量分數**直到樣本數 ≥ 30（threshold 由 P3 拍板）。

**為什麼這樣切**：
- prior 太低（0）→ 新 vacant 永遠沒人呼叫 → 網路冷啟動失敗 → cold start dilemma。
- prior 太高（=滿分）→ 攻擊者只要 spawn 新身份即可立即享有高分 → whitewashing 必勝。
- 0.30 + 微調是「不信任新人但給機會」的工程化（搭配 P3 的 UCB exploration bonus）。
- self-declared 用低權重避免「開發者偽造本機歷史」這個攻擊（無法驗證，故只能當參考）。

### D5. 聯邦化路徑：vacant_id **跨遷移可攜**為硬約束

**決策**：MVP 階段只跑單一中央 Registry，但所有設計**禁止依賴 Registry 的內部 ID**。`vacant_id` 永遠錨在公鑰指紋上，Registry 只是「公鑰索引服務」。三階段路線：

| 階段 | 時間軸 | Registry 形態 | 身份保證 | trade-off |
|---|---|---|---|---|
| MVP | 0–6 月 | 單一 Registry process（SQLite + WAL） | 公鑰錨定 + Git Merkle root（CT 風格 timestamp） | 中央化攻擊面、運營單點 |
| Federated | 6–18 月 | N 個 Registry node 各自獨立、雙向同步 | 每節點本地簽 Merkle root，定期 cross-sign | 同步衝突、節點分歧時的 split-brain 處理 |
| Decentralized | 18 月以後 | libp2p + IPNS publish + 可選 SBT 鏈上錨 | 公鑰 + WoT 簽章 + 可選鏈上 SBT 不可轉讓 | 查詢延遲、IPNS 解析穩定性、鏈 gas 變數 |

**vacant_id 不換**：三段過渡，公鑰指紋不變 → 歷史 reputation 可被新節點驗證簽章後直接接續。

**為什麼這個路線**：BRIEFING §11 第 3 個張力的反面——透明也是攻擊面，所以 Registry 中央化階段**必須有第三方 Git timestamp** 把 Merkle root 釘住，否則中央 Registry 本身就是 single point of compromise（見 P4 §防 MINJA 設計）。

---

## 3. 元件規格 / 演算法 / 資料結構

### 3.1 vacant_id 生成

```python
# vacant Runtime 啟動時執行一次
sk, pk = ed25519.generate_keypair()                # 私鑰本機保存，從不離開
vacant_id = multibase58btc(blake3(pk.bytes())[:24])
# 例：vacant_id = "z6MkpTHR8VNs..."
```

`vacant_id` 對應 W3C DID `did:key:z6MkpTHR8VNs...` 形式（DID Core v1.0, §6.1 the did:key Method）。Vacant 採用 did:key 為 MVP 最小可行身份；中期可升級到 did:web（綁定組織域名）或 did:ion（Sidetree on Bitcoin）。

### 3.2 Capability Card schema（給 P4 的草案）

```jsonc
{
  "vacant_id": "z6MkpTHR8VNs...",
  "public_key": "<ed25519 pk base58>",
  "did": "did:key:z6MkpTHR8VNs...",
  "version": "0.3.1",
  "parent_id": null,                        // null 表示原生；spawn 時填親代 vacant_id
  "declared_capabilities": ["legal-qa", "tw-tax-2024"],
  "base_model": {
    "family": "claude",                     // 用於 P3 同源降權
    "version": "opus-4-7",
    "hash": "sha256:abc..."                 // 可選，模型權重指紋
  },
  "owner_attestation": {                    // L1
    "tier": 2,
    "issuer_did": "did:web:university.edu.tw",
    "issued_at": "2026-05-01T08:00:00Z",
    "issuer_signature": "<ed25519 sig of payload>",
    "issuer_revocation_url": "https://university.edu.tw/.well-known/vacant-revocation"
  },
  "stake": {                                // L2
    "amount_usd_equivalent": 100,
    "lock_until": "2027-05-01T08:00:00Z",
    "escrow_did": "did:web:vacant-escrow.io",
    "escrow_proof": "<verifiable receipt>"
  },
  "wot_endorsements": [                     // L3
    {"endorser_id": "z6Mk...", "issued_at": "...", "sig": "..."},
    ...
  ],
  "self_declared_history": {                // β = 0.05
    "training_runs": 142,
    "self_eval_factual": 0.78,
    "evidence_url": "ipfs://bafy..."        // 開發者貼本機 trajectory 雜湊
  },
  "self_signature": "<vacant 自己的 ed25519 sig>"
}
```

### 3.3 L1 Attestation 四級

| Tier | 內容 | 範例 issuer | `α·tier(t)` 加給 |
|---|---|---|---|
| 0 | 無 attestation（純化名 vacant） | — | +0.00 |
| 1 | 個人 DID self-attest（綁 Twitter/GitHub） | did:web:keybase.io/cosmopig | +0.10 |
| 2 | 組織 attest（綁學校 / 公司 DID） | did:web:university.edu.tw | +0.20 |
| 3 | Enclave attest（vacant 跑在 TPM/SGX/TDX/Nitro/Confidential Space 中，遠端證明自己跑的是宣告的二進位；採 IETF RFC 9334 RATS 架構，attestation `user_data = hash(ed25519_pk \|\| nonce)`） | did:web:cloud-attest.aws.amazon.com | +0.30 |

**為什麼 Enclave attest 給最高加給**：因為它把身份綁到「具體執行環境的二進位」，攻擊者要造假必須突破 TEE，這在公開 hardware threat model 下是高成本的（雖非絕對，但符合 Douceur 的「資源稀缺性錨」要求）。

**Issuer 撤銷機制**：每個 issuer 必須提供 revocation list URL，Registry 每天 pull 一次，被撤銷的 attestation 自動降級到 tier 0（不刪除歷史，只標註）。

### 3.4 Whitewashing 成本——具體參數建議

| 項 | MVP 推薦值 | 備註 |
|---|---|---|
| `c_attest(tier=2)` | 約 4 hr 申請 + 組織內審查 | 對攻擊者是時間成本 |
| `c_stake(tier=2)` | $100 USDC 鎖定 1 年（≈$10 機會成本） | 可由 vacant 自選 0–$10000 |
| `T_ramp` | 100 次成功呼叫 ≈ 2 週（在 token 免費假設下） | 與 P3 UCB c 參數連動 |
| `R_prior(0)` | 0.30 | base 不變 |
| `R_prior(3)` | 0.60 | enclave attest 給滿 |
| `k`（safety margin） | ≥ 2 | 對抗測量誤差 |

數值說明：對一個曾累積到 R=0.85 的 vacant，洗白回到 R=0.85 至少要 2 週成功累積 + $100 stake 鎖定 + 重新獲得 attestation。對「為了甩掉一次失敗」的攻擊者，這個成本通常高於繼續經營舊身份。對「累積太多失敗、舊身份已沉沒」的 vacant，洗白也許划算，**但網路本來就允許 spawn 後代**——這是設計內建的，不是漏洞。

### 3.5 L3 Web of Trust 簽章流程

```
互簽前提：兩個 vacant 已協商過 ≥ N 次 successful peer review
         （預設 N=10, 由 P1/P3 給訊號）

vacant_A.WoT_endorse(vacant_B):
    payload = {
        "endorser": vacant_A.id,
        "endorsee": vacant_B.id,
        "claim": "not-sock-puppet-of-endorser",
        "evidence_event_ids": [...],        // 引用過去互動記錄
        "issued_at": now()
    }
    sig = ed25519_sign(vacant_A.sk, canonical_json(payload))
    Registry.submit_wot_endorsement(payload, sig)
```

**降權同源簽章**：若 endorser 與 endorsee 共享 base_model.family，該背書權重 × 0.5（防止 Claude 系互捧 ring）。

**信任傳遞 cap**：A→B→C 的傳遞信任最多兩跳；超過兩跳的環不算數。借鑑 PGP WoT 教訓——無限傳遞會讓單一妥協節點污染全網。

### 3.6 Stake 與 reputation 的接入規格（給 P3 的建議）

P3 的 UCB 公式預設：

```
UCB_d(i) = mean_d(i) + c · sqrt(ln(N) / n_i)
```

我建議擴充為：

```
UCB_d(i) = mean_d(i) + c · sqrt(ln(N) / n_i) + γ · stake_norm(i) + δ · attest_tier(i)
```

`γ`、`δ` 由 caller 在查詢時可調，預設值由 Registry 提供基準（例如 `γ=0.05`、`δ=0.05`）。**stake/attest 不直接灌到 mean_d**——這會讓 reputation 失真；它們只進選擇分布，幫高 stake 的 vacant 獲得更多曝光，但呼叫結果好不好仍以實際表現為準。

附加約束：**stake/attest 永遠不能讓 mean 從 0.3 跳到 0.9**，最多平移 ±0.10 在選擇分布上。這是 anti-Goodhart：避免攻擊者只靠 stake 買排名。

---

## 4. 對應到的缺口 / 風險

| ID | 缺口 / 張力 | P2 的回應 |
|---|---|---|
| **G02** | 身份錨定 / Sybil 抵抗（Friedman 2007、Douceur 2002） | L0–L3 四層 + WashCost 公式 + attestation 四級 + Friedman/Resnick 的 newcomer-tax 工程化 |
| **G04** | 記錄不可竄改性（MINJA 95%） | 私鑰本機保存 + 每筆 envelope 必須 self_signature；Registry 偷改會被驗章發現（細節由 P4 補完） |
| **Q1** | Registry 中央化 vs 聯邦化路徑 | §2 D5 三階段路線圖 + vacant_id 跨遷移可攜硬約束 |
| **Q2 (部分)** | vacant 最小定義 | 必須有 ed25519 keypair（這是**唯一**強制條件；LLM/heartbeat/演化由其他 pane 定義） |
| **§11 #1** | 網路自然淘汰 vs whitewashing | WashCost ≥ 2·WashGain + 失敗的代價是 spawn 後代而非洗白 |
| **§11 #2** | 無中央 judge vs cold start | prior_d = 0.30 + α·attest_tier + 0.05·self_declared；前 30 樣本不公開純量、只給「資料不足」 |
| **G07** (P1 §7.8 升級之架構級議題) | 高階對手取得歷史 corpus + 同型 base model 微調仿冒體 → behavioral warmup ceremony 被繞過 | 由 P2 識別層承接：(a) **L3 enclave attestation** (§3.3 tier 3) 把 vacant_id 綁到「TEE 內二進位」而非操作者，仿冒體 PCR/MRENCLAVE 不同則 attestation 驗不過；(b) **L2 stake** (§3.5) 把高 trust weight 與真實資本鎖定綁定，仿冒者必須付出對等 stake；(c) **L0 私鑰本機保存** 確保仿冒體無法簽出該 vacant_id 的 envelope（即使行為高度相似），P3 簽章驗不過直接拒收；(d) **L3 WoT** 兩跳 cap 限制仿冒體無法快速取得多源 not-sock-puppet 簽章 |

**保留風險**：

- **R1**: enclave attestation 對個人開發者門檻過高（GCP Confidential Space / AWS Nitro 都需企業帳號）。**緩解**：tier 1 自簽 DID（綁 Keybase / GitHub）給個人開發者一個入口；長期 SBT-on-chain 是更平等的選項。
- **R2**: stake 把窮國開發者擋在外面。**緩解**：stake 完全自願，未抵押者只是少 +γ·stake_norm 平移，不會被排除。
- **R3**: WoT 環會被 colluding cluster 污染。**緩解**：同源降權 0.5 + 兩跳 cap + P3 graph clustering 偵測 ballot stuffing（互捧環）。
- **R4**: Issuer DID 自身被攻破（如某大學 did:web 私鑰外洩）。**緩解**：revocation list 每日 pull + 多 issuer 交叉認證在 tier 2 強制（tier 2 至少要 2 個獨立 issuer）。
- **R5 (Goodhart)**：stake 高的 vacant 被誤認為「比較可靠」→ trust calibration 失敗。**緩解**：UI 必須把 stake 與 reputation 分離顯示，「★★★★☆ 來自 50 樣本，stake $5000 鎖定 1 年」而非「★★★★★ 5000星」。

---

## 5. 參考文獻 / 引用

> 以下引用於 codex 學術 raw 輸出（`research/P2_identity_research.md`）有完整出處。本節只列關鍵錨點。

- **Douceur, J. R.** (2002). *The Sybil Attack*. In Proceedings of the 1st International Workshop on Peer-to-Peer Systems (IPTPS '02). Cambridge, MA. — 用於主張「無中央發行者 + 無資源錨 → Sybil 不可阻」是 P2 必須引入 stake/attestation 的形式根據。
- **Friedman, E., & Resnick, P.** (2001). *The Social Cost of Cheap Pseudonyms*. Journal of Economics & Management Strategy, 10(2), 173–199. — 用於 newcomer-tax 工程化（D4 prior 0.30 base）。
- **Friedman, E., Resnick, P., & Sami, R.** (2007). *Manipulation-Resistant Reputation Systems*. Chapter 27 in N. Nisan, T. Roughgarden, É. Tardos, & V. V. Vazirani (Eds.), Algorithmic Game Theory. Cambridge University Press, pp. 677–697. — 用於 WashCost ≥ k·WashGain 的 manipulation-resistance 條件依據。
- **Ohlhaver, P., Weyl, E. G., & Buterin, V.** (2022, May). *Decentralized Society: Finding Web3's Soul*. SSRN Working Paper 4105763, DOI `10.2139/ssrn.4105763`. — 用於 SBT 不可轉讓性 → 「身份不可二級市場買賣」的設計參照（§3.5 WoT、§D5 長期分散化）。配套 ERC-5192 "Minimal Soulbound NFTs" 提供 `locked(tokenId)` 介面骨架。
- **W3C** (2022, July 19). *Decentralized Identifiers (DIDs) v1.0 — Core architecture, data model, and representations*. W3C Recommendation. https://www.w3.org/TR/did/ — 用於 vacant_id 的 `did:key` 表示與長期 `did:web` / `did:ion` 升級路徑（§3.1, §D5）。
- **W3C** (2022, March 3). *Verifiable Credentials Data Model v1.1*. W3C Recommendation. https://www.w3.org/TR/2022/REC-vc-data-model-20220303/ — 用於 L1 attestation envelope 結構參照（§3.2）。
- **Chaffer, T. J., von Goins II, C., Cotlage, D., Okusanya, B., & Goldston, J.** (2025, Jan 11, v3). *Decentralized Governance of Autonomous AI Agents*. arXiv:2412.17114, DOI `10.48550/arXiv.2412.17114`. — 用於 Web3 身份（DID + SBT + ZKP + 質押 + 預言機）+ on-chain attestable history 的設計借鑑（§3.5 與 §D5 長期路徑）；ETHOS §5.1, §5.3 為 vacant_id 與 attestation 設計提供結構模板。**註**：BRIEFING 標題 "ETHOS: Towards Ethical and Humanlike Multi-Agent Systems" 與此論文 canonical title 不符，已依 codex 校正。
- **Bouchiha, M. A., Telnoff, Q., Bakkali, S., Champagnat, R., Rabah, M., Coustaty, M., & Ghamri-Doudane, Y.** (2024). *LLMChain: Blockchain-based Reputation System for Sharing and Evaluating Large Language Models*. arXiv:2404.13236; COMPSAC 2024, pp. 439–448, DOI `10.1109/COMPSAC61105.2024.00067`. — 用於 contextual reputation `Rep(agent, domain, verifier_class, time)` 的論述支援（§3.6 與 P3 對齊）。
- **IETF RFC 9334** (2023). *Remote ATtestation procedureS (RATS) Architecture*. https://www.ietf.org/rfc/rfc9334.html — 用於 §3.3 tier 3 enclave attestation 的 attester/verifier/evidence 流程錨點。配套 TCG TPM 2.0、Intel SGX/TDX DCAP、AWS Nitro Enclaves docs、Google Confidential Space。
- **OpenPGP RFC 4880** (2007). https://www.rfc-editor.org/rfc/rfc4880 — 用於 §3.5 WoT 「valid trusted introducer」(§5.2.3.13) 與兩跳信任傳遞 cap 的歷史教訓。
- **Newman, Z., Meyers, J. S., & Torres-Arias, S.** (2022). *Sigstore: Software Signing for Everybody*. ACM CCS 2022, DOI `10.1145/3548606.3560596`. — 用於 §D5 中期聯邦階段 transparency log 設計參照。
- **Otte, P., de Vos, M., & Pouwelse, J.** (2017/2020). *TrustChain: A Sybil-resistant scalable blockchain*. Future Generation Computer Systems, DOI `10.1016/j.future.2017.08.048`. — 用於 §3.5 WoT 雙邊互動鏈式記帳的設計借鑑。
- **Lou, Y., Hu, H., Ma, S., et al.** (2025). *DRF: LLM-Agent Dynamic Reputation Filtering Framework*. arXiv:2509.05764. — 用於 §3.6 UCB 公式骨架 + 「對 LLM 賦予 reputation 是文獻缺口」的定位（p. 3, §2 Related Work）。
- **Skalse, J., Howe, N. H. R., Krasheninnikov, D., & Krueger, D.** (2022). *Defining and Characterizing Reward Hacking*. NeurIPS 2022. arXiv:2209.13085. — 用於 §2 D2 與 R5 解釋為何 stake/attest 不能直接進 mean。
- **Douceur, J. R.** (2002). *The Sybil Attack*. IPTPS 2002, LNCS 2429, pp. 251–260, DOI `10.1007/3-540-45748-8_24`. — §2 D2 形式根據。
- **Friedman, E., & Resnick, P.** (2001). *The Social Cost of Cheap Pseudonyms*. JEMS 10(2), 173–199, DOI `10.1111/j.1430-9134.2001.00173.x`. — §2 D2、§D4 prior 工程化的論文錨。
- **Friedman, E., Resnick, P., & Sami, R.** (2007). *Manipulation-Resistant Reputation Systems*. Ch. 27 in Algorithmic Game Theory (Cambridge University Press), DOI `10.1017/CBO9780511800481.029`. — §2 D3 manipulation-resistance 條件。
- **Nostr NIP-13** *Proof of Work*. https://nostr-nips.com/nip-13 — 用於 §2 D2 否決純 PoW 身份的具體比較（`expected_work = 2^difficulty`）。
- **NIST** (2023). *AI Risk Management Framework (AI RMF 1.0)*. NIST AI 100-1. — 用於 accountability 用語的法律意義錨點。
- **Capgemini Research Institute** (2025, July). *Rise of Agentic AI: How Trust is the Key to Human-AI Collaboration*. — 用於 §1 問題重要性背景。

詳細逐項出處（含 DOI/arXiv/SSRN/RFC 連結）見 `/Users/cosmopig/Downloads/專題/architecture/research/P2_identity_research.md`，本檔為一手依據。

---

## 6. 對其他 pane 的依賴與假設

- **依 P1 (Runtime)**：vacant Runtime 在啟動時生成 ed25519 keypair 並本機保存；所有對外 envelope 必須由 Runtime 簽章；私鑰絕不上傳 Registry。**假設**：Runtime 提供 `runtime.sign(payload) -> sig` 介面。
- **依 P3 (Reputation)**：接受 §3.6 的 stake/attest 接入方式（進 UCB 而非進 mean）；接受 §D4 的 prior 公式作為冷啟動初值；threshold「樣本 ≥ 30 才公開純量」由 P3 拍板數值。
- **依 P4 (Registry)**：實作 §3.2 Capability Card schema 與 §3.5 WoT endorsement schema 的儲存/查詢；提供每日 issuer revocation pull；attestation 寫入需多方簽章（tier 2 要兩個 issuer）。
- **依 P5 (Client SDK)**：caller 查詢時可選 `min_attest_tier`、`require_stake`、`weight_overrides` 三個過濾條件；SDK 介面把 stake/attest 與 reputation 分離顯示。
- **依 P6 (A2A envelope)**：A2A 訊息頭包含 `vacant_id` 與 envelope `signature` 欄位；接收端先驗章再處理 payload。
- **依 P7 (UX/Anti-complacency)**：UI **不准把 stake 折算成 reputation 點數**；Trust 分數 + stake/attest 必須各自獨立呈現。
- **依 P8 (Demo)**：demo 階段提供至少兩個 issuer DID（學校 + 模擬企業）以展示 tier 2 多源 attestation。

**假設**：所有 pane 接受「vacant_id 公鑰錨定不可換」這條硬約束，且 Registry 從不持有 vacant 私鑰。

---

## 7. 未解問題 / 留給後續

1. **Q-P2-1: Issuer 的去中心化路徑** — 中期聯邦階段，issuer DID 是否要互簽形成 issuer trust graph？目前草案用「revocation list 每日 pull」處理，但若 issuer 自己跑路或被攻破，整個 tier 2 簇會失效。可能需要 issuer 之間的 cross-sign 機制，但這已超出 P2 範圍。
2. **Q-P2-2: Stake 的退場機制** — vacant 自然沉沒時的 stake 解鎖時機？立即解鎖會被攻擊者用「快速 stake → 快速洗白」濫用；長期凍結對誠實 vacant 不公平。建議交給 P3 / P4 共同設計：linked-list dispute period（90 天）後解鎖。
3. **Q-P2-3: 隱私 vs 透明** — Capability Card 公開 owner_attestation 會洩漏組織關係。是否提供 ZK-proof 版「我有 tier ≥ 2 的 attestation」而不揭露 issuer 是誰？技術可行（Groth16 / PLONK on did:key），但 MVP 太重。標記為長期研究。
4. **Q-P2-4: 子代 (composite vacant child) 的身份** — BRIEFING §4.3 規定子代不對外。它們需要 vacant_id 嗎？建議：子代有內部 ed25519 keypair 以支援父代內部簽章驗證，但**不在公網 Registry 註冊**。父代對外的所有 envelope 由父代簽，子代輸出在父代內聚合。需與 P1 對齊。
5. **Q-P2-5: 遺失私鑰的恢復路徑** — 開發者主機壞掉、私鑰沒備份 → vacant_id 永久失效，所有歷史 reputation 無法繼承。建議：social-recovery（M-of-N issuer 共簽 vacant_id 重新綁新公鑰），但這引入新攻擊面，要在 v2 設計。
6. **Q-P2-6: WoT 反向攻擊** — 惡意 vacant 故意給對手簽 not-sock-puppet（騙取對方信任後再撤回）。需要與 P3 設計「endorsement 撤回後對 reputation 的反映」。
7. **Q-P2-7: 與 EU AI Act / NIST AI RMF 的對齊** — 高風險場景下的身份/問責要求可能比 Vacant 設計更嚴。需法律/合規顧問審視，留給專題後期合規章節。

---

*P2-identity v1 · 接續工作建議：(1) 等 codex raw 輸出完成後校對 §5 引用，特別是 ETHOS 與 Bouchiha 的具體章節；(2) 與 P3 對 §3.6 stake 接入規格做雙邊 review；(3) 與 P4 對 §3.2 Capability Card schema 做欄位確認。*
