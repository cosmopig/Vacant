# P4 Registry — 防竄改與承諾層研究筆記

> 本文件是 P4_registry.md 設計的 raw research。包含兩段 codex 研究輸出 + 我的綜合判斷。
> 方法：codex CLI（model_reasoning_effort=high）兩個獨立查詢 + 本機交叉檢核 + 對齊 BRIEFING / vacant_current_understanding §3.5 / 責任有效性分析 §3.B.4。

---

## 0. 評估前提 (我的）

Vacant Registry 不解決「壞事件不出現」，它解決：

> **「事件一旦被接受，任何刪除、重排、回填、改寫、分裂視圖（split-view）都能被第三方驗出。」**

這個定位很重要——它把責任從「事前審核」（會違反 BRIEFING §1「無資格審核」原則）轉成「事後不可否認 + 可追溯淘汰」。所有後面的方案比較都依此 frame 評估。

對應的攻防矩陣兩條軸：

| 軸 | 描述 |
|---|---|
| 寫入側 | 誰能寫、寫了什麼能不能事後被改 |
| 讀取側 | 讀者拿到的是不是 Registry 的「全部、未篩選、未捏造」版本 |

Registry 既要防被外部攻擊者改寫，又要防自己（Registry operator）作弊，這兩件事不能合併處理。

---

## Part A — 持久化記憶/記錄的攻擊面（codex 研究）

### A.1 核心威脅模型

持久化記憶把**一次性 prompt injection 變成跨 session 的狀態污染**。攻擊者不一定要改模型權重；只要能讓 agent 把「惡意內容」寫入 memory、RAG corpus、trajectory log 或 registry event，之後讀取端把它當成示範、偏好、事實或指令，就能形成長期影響。對 Vacant 類 Registry 而言，**簽章與 append-only 只能證明「誰寫過、是否被改過」，不能證明「內容不會反向操控讀者」**。

### A.2 MINJA：query-only 記憶注入

**論文**：*Memory Injection Attacks on LLM Agents via Query-Only Interaction*, arXiv:2503.03704，2025 v1 / 2026 v5。

**攻擊者能力 → 效果**：攻擊者只像一般使用者一樣查詢 agent、觀察輸出；不能直接改 memory、不能改受害者 query；效果是讓 shared memory 產生惡意 records，之後 victim query 觸發錯誤 reasoning / action。

**機制三段**（§4 pp.3-5）：

- **bridging steps** (§4.1 p.4)：把 victim term `v` 與 target term `t` 建立「看似合理」的中介推理，例如「A 的資料已存到 B」，使 agent 在後續 victim query 中自然轉向 target reasoning。
- **indication prompts** (§4.2 p.4)：把指示性推理片段接在 benign query 後，誘導 agent 自己生成 bridging steps 與 target reasoning。
- **progressive shortening / PSS** (Appendix A p.21)：逐步刪掉 indication prompt，留下更像正常 query 的惡意 memory record，提高被相似度檢索取回的機率。

**實驗條件**：三類 agent（RAP web shopping、EHRAgent、QA Agent）；資料集 WebShop / MIMIC-III / eICU / MMLU；GPT-4 / GPT-4o；每 victim-target pair 用 10-15 條 attack queries 注入。

**結果** (§5.1-5.3 pp.5-8)：
- 多數設定 ISR (Injection Success Rate) > 90%
- 整體 ISR > 95%
- ASR (Attack Success Rate) 60%-90%+
- RAP GPT-4o WebShop ASR 98.9%
- retrieval noise σ=0.01 下 ASR 從 97.8% → 95.6%（影響輕微）

**可防禦層次** (§5.4 pp.8-9)：MINJA 主要打「語義寫入」與「讀取時作為示範」。**密碼學簽章、hash chain、Merkle 不能阻止合法介面寫入的惡意 record**；schema 能擋格式錯誤，但擋不住 schema-valid 的 victim→target substitution。較有效的：memory write gate、租戶隔離、把 memory 當 untrusted data 而非 instruction、針對性 prompt-level detector、多方 attestation。論文顯示一般 prompt detector 容易高誤報，embedding sanitization 也因 benign / malicious records 混雜而弱。

### A.3 eTAMP / "Poison Once, Exploit Forever"

**論文**：*Poison Once, Exploit Forever: Environment-Injected Memory Poisoning Attacks on Web Agents*, arXiv:2604.02623。

**攻擊者能力 → 效果**：攻擊者能在 web 內容中放文字（商品描述、論壇貼文）；不能讀寫 agent memory、不能改 system prompt；效果是 agent 瀏覽時把污染 trajectory 存入 memory，未來在另一網站任務中檢索到該 memory 並執行未授權 action。

**攻擊路徑** (§2 pp.1-4)：Task A 中 agent 正常購物或瀏覽，看到 attacker-controlled content → trajectory memory 保存觀察內容 → Task B 幾天後到 Reddit / Shopping / Classifieds，semantic retrieval 取回 Task A → payload 依 URL 或環境狀態觸發。這是 indirect prompt injection，且符合 **lethal trifecta**：untrusted content 進入模型 + agent 有私有/歷史 context + 又能外部行動或通訊。

**持久性**來自 raw trajectory memory 被跨 session 反覆取回；一次污染可多次觸發。

**實驗** (§2.4-3.1 pp.4-5)：WebArena / VisualWebArena，~280 cross-site task pairs；ASR 最高 GPT-5-mini 32.5%、GPT-5.2 23.4%、GPT-OSS-120B 19.5%。Chaos Monkey（製造 click drop / scroll swap / type transform）下 GPT-5-mini 從 3.6% 升到 32.5%——**約 8 倍放大**。

### A.4 相關攻擊比較

| 攻擊 | 論文 | 攻擊者能力 | 結果 |
|---|---|---|---|
| AgentPoison | arXiv:2407.12784, NeurIPS 2024 | 直接污染 memory/KB 少量 records | 三類 agent 平均 ASR > 80%, poison rate < 0.1% |
| BadChain | arXiv:2401.12242 | 提供含 trigger 的 CoT demonstrations | GPT-4 ASR 97.0%, in-context backdoor |
| BadRAG | arXiv:2406.00083 | 往 RAG corpus 放少量 adversarial passages | 10 個 poisoned passages 達 98.2% 檢索；GPT-4 RAG reject ratio 從 0.01% 拉到 74.6% |
| Contagious Jailbreak (ARCJ) | arXiv:2410.16155 | 污染一個 agent 的 independent memory | 透過多 agent 互動傳播 jailbreak |

**對 Vacant 的特殊啟示**：Contagious Jailbreak 的傳播路徑（agent-to-agent message → memory write → retrieval → 再傳播）**正好對應 Vacant 的 peer review / composition link / spawn 機制**。因此 Registry 不能假設「只要每個 vacant 自己沒被攻陷就安全」，必須假設互評網路本身就是傳染路徑。

### A.5 真實 PoC：ChatGPT Memory spAIware (2024)

Johann Rehberger PoC（Ars Technica 2024-09-24 報導）：使用者要求 ChatGPT macOS app 讀取含惡意 image / web link 的內容 → indirect prompt injection 寫入 long-term memory → 後續新對話仍把 user input 與 ChatGPT output 傳到 attacker server。

可植入 false memories（錯誤年齡、信念）、升級成持久 exfiltration channel。OpenAI 後續做了 partial fix。

### A.6 業界風險評級

- **OWASP Agentic Top 10 2026**：**ASI06 Memory & Context Poisoning** 列為 agentic 應用 Top 10。
- **OWASP Agent Memory Guard**：把 persistent agent memory 定義為高價值 attack surface，主張 hash baseline、policy enforcement、snapshot、rollback。
- **Palo Alto Unit 42 (2025) Bedrock Agents PoC**：惡意網頁操控 session summarization → payload 寫入 memory → orchestration prompt 自動包含該 memory → conversation history 透過 web tool 靜默外洩。

### A.7 Append-only Registry 的攻擊向量

對 Vacant Registry 的具體攻擊面：

| 攻擊 | 攻擊者能力 | 效果 |
|---|---|---|
| 寫入端注入 | vacant 自己被劫持/誘騙簽 event | 惡意內容取得**合法簽章**——簽章只證明 signer，不證明語義安全 |
| 讀取端污染 | 讀者 agent 把 event body 當 prompt | Registry 變成 prompt-injection delivery network |
| Replay | 攻擊者重送舊 event | 舊授權、舊評價、舊狀態被重新生效 |
| Double spend | 同一 event id / intent 被兩個 vacant 簽不同內容 | 分叉歷史，依讀者看到的版本不同而產生不同狀態 |
| Mutual praise / collusion | 多個 vacant 互相簽好評或 attestation | trust graph 被灌水，Contagious Jailbreak 類傳播更快 |
| Split-view | Registry 給不同客戶看不同 STH | 同一 vacant 在不同地區看似有不同 reputation；外部 gossip/witness 可偵測 |
| Selective hide | Registry 在查詢時不返回某些 events | 客戶端拿不到完整歷史；需要 inclusion-by-key proof + range proof |

### A.8 防禦層級對照

| 層級 | 控制手段 | 可擋什麼 | 對 MINJA 是否有效 |
|---|---|---|---|
| **應用層** | schema validation、structured output、event type allowlist、raw text quarantine | 格式注入、工具參數污染、把 memory 當指令 | **部分有效**；擋不住 schema-valid 語義替換 |
| **密碼學層** | signer key、hash chain、Merkle root、透明日誌 | 篡改、偽造、刪改歷史 | **幾乎不擋**；MINJA 是合法寫入 |
| **規格層** | idempotency key、nonce、sequence、replay window、canonical event hash | replay、double spend、分叉 | **不擋**語義 poisoning |
| **治理層** | freeze、revocation、quarantine、human review、多方 attestation、trust scoring | compromised signer、collusion、事後止血 | **最有用**；可阻斷高風險 event 生效 |

### A.9 Vacant Registry 必備三防線（codex 結論）

1. **把 event payload 當資料，不當指令**：所有讀取端必須使用 typed schema、字段級轉義、tool-call allowlist；自然語言欄位不得直接進入 agent system/developer prompt。
2. **每個 event 必須有不可重放的身份與順序語義**：`event_id + signer + subject + sequence + nonce + previous_hash + expiry/replay_window`，並用 hash chain / Merkle anchoring 公開承諾。
3. **高影響寫入要有治理閘門**：vacant 自簽只能代表「來源」，不能代表「可信」。需要多方 attestation、異常偵測、freeze / revoke / quarantine、以及對互評網路的 Sybil / collusion 控制。

---

## Part B — append-only log 承諾方案比較（codex 研究）

### B.1 學術 lineage

```
Merkle (1989) A Certified Digital Signature
    │
    ├─→ Haber-Stornetta (1991) How to Time-Stamp a Digital Document
    │      └─→ Bayer-Haber-Stornetta (1993) Merkle aggregation
    │
    ├─→ Crosby-Wallach (USENIX 2009) Tamper-Evident Logging
    │
    └─→ Laurie-Langley-Kasper (RFC 6962, 2013) Certificate Transparency
           ├─→ CONIKS (Melara et al., USENIX 2015) Key Transparency
           ├─→ Trillian (Eijdenberg-Laurie-Cutter, 2015) Verifiable DS
           ├─→ RFC 9162 (2021) CT v2
           ├─→ Sigstore/Rekor (Newman et al., CCS 2022)
           └─→ C2SP tile-based / static CT API (2024-2025)
```

### B.2 方案矩陣

| 方案 | (a) tamper-evidence 強度 | (b) 寫入吞吐 | (c) Vacant 適配性 |
|---|---|---|---|
| **純 Hash Chain** | 每筆含 prev_hash 可偵測單次改寫、刪除、插入；但若營運者重寫整條鏈並重發 head，外部無舊 head 就無法證明。**至少需 1 個獨立 witness 定期保存 head**。 | 極高，單機 10k+ ops/s 可行；每筆 O(1)；批次延遲近零。 | 適合 **Layer 1 本地日誌**。單獨不夠：中央 registry 可悄悄重寫歷史；與「無中央仲裁者」原則衝突中等。 |
| **Merkle Tree / Sparse Merkle** | Merkle root 承諾全體資料；inclusion proof O(log n)，consistency proof 證明新 root 是舊 root 的 append-only 延伸。Sparse Merkle 可證明 key 的最新狀態或不存在。仍需外部保存 root 防 split-view。 | append-only tree 1k-10k+ ops/s；SMT 更新 O(log keyspace) 可快取。批次 1-60s 合理。 | **很適合**。Event 流用 dense Merkle log，`vacant_id → current key/state` 用 SMT/Verifiable Map。運維中等。 |
| **CT RFC 6962** | append-only Merkle log + STH + SCT。透過 gossip/monitor 比對 STH 抓 split-view；若 SCT 未納入 MMD 內，auditor 可證明違約。需要多個 monitor/auditor 或至少 1-2 個獨立 witness。 | Trillian 類實作 2k+ writes/s；公開 CT 規模可達網際網路級。批次 MMD 通常分鐘級。 | **很適合做設計基準**。缺點：原 RFC 6962 著重 TLS cert，要自定 personality。 |
| **CT v2 (RFC 9162) / Static CT API** | RFC 9162 增加演算法 agility、TransItem、新 TLS extension（與 v1 不相容）。2024-2025 的 Static CT API/C2SP/tiled API 把 read path 變成靜態 tile/checkpoint，降低監控成本。安全性仍來自 Merkle root + checkpoint + witness。 | tiled read path 對大規模讀取/監控更好；寫入仍由 sequencer 控制。秒級到分鐘級 checkpoint。 | 若 Vacant 要公開可審計，**tiled API 比老 CT API 更適合**。 |
| **Sigstore / Rekor** | Keyless signing：Fulcio 用 OIDC 發短期 cert，Rekor 記錄簽章/attestation。Rekor 是 transparency log，可做 inclusion/consistency audit。若 Fulcio + OIDC + Rekor 串謀只能靠監控偵測。 | 公共服務有 SLO 與大小限制；供應鏈 attestation 足夠，不是任意高頻事件總線。自架 Rekor 成本中等偏高。 | **適合「Vacant 軟體 artifact / agent package / policy release」簽章**，不適合所有 reputation event 直接上公共 Rekor。可作外部 anchor。 |
| **Trillian** | 通用 verifiable log/map 基礎設施。安全性取決於 STH、consistency proof、外部 witness。 | 已被 CT 生產使用；2k+ writes/s。需 DB、sequencer、signer、personality。 | **很適合聯邦期**。但 v1 maintenance mode；新案可看 Tessera/tiled logs。運維成本高於自寫 Merkle log。 |
| **Git timestamp anchor** | Git commit 是內容定址物件，含 tree、parent、time；signed commit/tag 把 root 綁到操作者 key。push 到 public GitHub 後，第三方 clone/fork、Actions log 形成外部觀察點。 | 不適合逐筆；適合每 1-10 分鐘 push 一次 root。 | **MVP 的窮人版 anchor**。弱點：Git 內部 timestamp 可任意設定；branch/tag 可 force-push；GitHub 是單一平台；若無外部 clone/fork，刪庫後證據弱。 |
| **OpenTimestamps / OTS** | Merkle 聚合 + Bitcoin anchor。確認後安全性接近 Bitcoin L1；calendar 只能延遲，不能偽造已確認 timestamp。 | 不適合逐筆；適合每小時/每日 anchor root。確認約 10 分鐘以上。 | **適合長期不可抵賴歸檔**，不適合低延遲 reputation 查詢。成本低、部署簡單。 |
| **L2 commitments (rollup)** | Optimistic：state root + challenge/fraud proof。ZK：state root + validity proof。安全假設是 L1 安全 + 至少 1 個 honest challenger（Optimistic）或 proof system（ZK）。 | 高吞吐，建 rollup 成本極高；批次延遲秒-分鐘，finality 看 L1/挑戰期。 | **MVP 過度設計**。若未來 reputation 影響資產或懲罰，可把 Merkle root 發到現有 L2 合約。 |
| **CRDT logs (RGA/Yjs/Automerge)** | 強在多寫入者、離線合併、eventual convergence；本身**不保證 append-only 或 tamper-evidence**，除非每個 op 簽名並額外 hash-link/Merkle。 | P2P 吞吐好；衝突解決本地完成。 | 適合同步 UX，**不適合作權威 audit log**。若採用，必須把 CRDT op 當事件來源，再進入透明日誌。 |
| **libp2p + IPFS/IPNS** | IPFS CID 內容定址不可改；IPNS 是簽名 mutable pointer。可驗內容完整性，但**不自動提供「完整歷史」或「未刪改」證明**。 | 讀取/分發佳；寫入取決於 pinning/DHT/IPNS propagation。 | **適合分發 log tiles、snapshots、proof bundles**。不能單獨作 registry 承諾層；需 Merkle root/checkpoint。 |

### B.3 為什麼 CT 成為 GitHub artifacts trust 的事實標準

供應鏈 provenance 需要三件事：身分綁定、artifact digest 簽章、公開可審計的時間/存在證明。CT 模型給出「不信任 log operator，但能驗 inclusion/consistency」的最低公共機制。

- **Sigstore**：Fulcio 用 OIDC 發短期憑證，Rekor 記錄簽章事件。
- **GitHub artifact attestations**：明確使用 Sigstore，public repo 寫入 Sigstore Public Good Instance。
- **npm provenance**：要求 provenance bundle 簽章上 Rekor。
- **PyPI PEP 740 attestations** (2024 GA)：使用 Sigstore-based attestations。

CT/Rekor 類透明日誌成為 artifact trust 的**共同語言**，而不是單一平台 API。

### B.4 Git push 為何是「窮人版 timestamping」

Git commit hash 承諾 tree、parent、作者/提交者時間與訊息；signed commit/tag 再把 root 綁到操作者 key。push 到 public GitHub 後：
- GitHub API 的 verification record / `verified_at`
- 公開 repo 的第三方 clone/fork
- GitHub Actions log

形成外部觀察點。**便宜、易部署、可人工審計**。

**弱點**：
- Git 內部 timestamp 可任意設定（不可信）
- branch/tag 可被 force-push
- GitHub 可刪庫、封號或配合攻擊者
- 若只有一個 GitHub repo 且沒人 mirror，就**不是強 timestamp**

**正確用法**：push **append-only branch**、禁止 force-push、簽 tag、讓多方 mirror，並定期再用 OTS 或其他 witness 錨定。

### B.5 三層組合的學術根據

「Layer 1 hash chain + Layer 2 週期性 Merkle root push + Layer 3 多方簽章」**不是單篇論文發明**，而是三條脈絡的工程合成：

1. **Hash chaining / timestamping**：Haber & Stornetta (1991), Bayer/Haber/Stornetta (1993)
2. **Merkle audit log**：Merkle (1989), Crosby & Wallach (USENIX 2009), CT RFC 6962 (2013)
3. **Witness / 多方簽章**：CT gossip, CONIKS (Melara et al., USENIX 2015), Trillian VDS (2015), C2SP tlog-checkpoint / tlog-witness / tlog-cosignature (2024+)

學術正當性：本地事件鏈提供低成本順序性；Merkle root 提供批次可驗 inclusion；多方 witness/Git/OTS 提供 anti-equivocation 與外部時間錨。

### B.6 vacant_id 在 MVP → 聯邦 → 分散化遷移的可攜性

`vacant_id` 不應由中央資料庫流水號決定。建議定義：

```
vacant_id = multibase(multihash(canonical_public_key))
```

| 階段 | 核心結構 | trust assumption |
|---|---|---|
| **MVP** | 中央 Registry 接受 vacant 私鑰簽名的 event；事件含 vacant_id, event_hash, prev_event_hash, registry sequence, ts。每分鐘 Merkle root，簽 checkpoint，push Git。 | Registry operator 可被誠實假設，但**有可被 Git 與獨立 witness 偵測**的承諾。 |
| **聯邦** | 多個 registry shard 各自維護 log；每個 shard 的 checkpoint 進入全域 checkpoint log。`vacant_id` key rotation 用 signed rotation event（舊 key 簽新 key，新 key 反簽），進入 SMT/Key Transparency map。 | 客戶端只信任能提供 inclusion + consistency + witness cosignature 的 registry。 |
| **完全分散化** | 事件由 libp2p/IPFS 傳播，CID 分發內容；canonical history 仍以 signed event DAG + Merkle checkpoint 決定。多分支時客戶端按 witness quorum + 時間錨 + policy 選擇。 | 不依賴單一中央仲裁者。 |

`vacant_id` 是 Ed25519 公鑰的 hash → **三階段一律不變**。這滿足 BRIEFING §9「公鑰錨定不換」。

### B.7 codex 對 Vacant 的最終建議

對每秒 10-1000 event 的 vacant 網路，最佳組合：

> **核心**：append-only Merkle log + 每 event signer signature + per-vacant hash chain。
>
> **承諾層**：每 1-10 秒 Merkle checkpoint；每 1-5 分鐘 push Git signed tag；每日 OTS anchor。
>
> **見證層**：3-of-5 或 5-of-9 witness cosign checkpoint（不同組織、社群節點、研究單位、主要 federation operator）。安全假設是 Registry operator 可惡意，但不能同時控制 witness quorum，且至少一個 monitor 保存並比對 checkpoint。
>
> **索引層**：Sparse Merkle / Verifiable Map for `vacant_id → current key/state root`。事件 log 是事實來源；map 是可驗索引，避免查詢者只拿到被挑選過的事件。

**不建議 MVP 直接上 rollup 或全 IPFS/CRDT**：rollup 成本與規格複雜度過高；IPFS/CRDT 解決分發與合併，不解決權威 append-only audit。等 Vacant reputation 具有金融或治理後果時，再把每日 root 發到 L2 合約。

---

## Part C — 我的綜合判斷（給 P4_registry.md 的設計輸入）

### C.1 把 A 跟 B 接起來

A 與 B 的關鍵摩擦：**B 給的所有密碼學承諾都不擋 A 的攻擊**。

```
密碼學承諾   ↘
                Vacant Registry — 兩個獨立的安全屬性
治理閘門     ↗
```

| 屬性 | 由什麼保證 | 攻擊者繞過方式 |
|---|---|---|
| **完整性 / 不可篡改** | hash chain + Merkle root + Git anchor + witness | Registry operator 欲改寫舊資料就必須讓 witness 共謀 |
| **語義安全 / 防 MINJA** | 多方 attestation + 異常偵測 + freeze + read-side schema 強約束 + 治理 quorum | 寫入端被劫持時，需 N 個獨立簽章才 finalize；單一 vacant 私鑰外洩有限 blast radius |

P4 設計**必須把這兩個屬性顯式分離**，不要讓使用者誤以為「簽了 hash chain 就安全」。

### C.2 三個跨 pane 的硬約束

從 P2 / P3 / P6 task 倒推 P4 schema 必有的欄位：

- **P2**：`vacant_id` 必為 Ed25519 pubkey 推導；`attestations[]` 含 attester_kind (developer/org/peer/dev_oracle)；`stake` 數值；whitewashing cost 公式需 Registry 提供 「reputation-loss-on-rebirth」查詢。
- **P3**：reputation snapshot 是五維 + lower_ci + upper_ci + n_samples + diversity_index；snapshot 必須由 Registry 簽章（含 `snapshot_hash`）讓客戶端驗證；歷次 snapshot 要可查（時間序列）。
- **P6**：所有寫入經 envelope，envelope 必含 `caller_vacant_id` + `caller_signature` + `idempotency_key` + `chain_attestation[]`；Registry RPC 是 P6 envelope 的**接收端**，所以 schema 必須與 envelope JSON 一一對應。

### C.3 Registry 中央化權力的具體邊界

Registry 在 MVP 是 trust anchor，不是 trust origin。它能與不能做的事：

| 行為 | Registry 能否做？ | 偵測機制 |
|---|---|---|
| 拒絕接受 event（censorship） | **能**，但有 SLA + Git 缺口可見 | 客戶端帶 idempotency_key 重試另一 Registry（聯邦期） |
| 偽造 event 內容 | **不能**：event 由 vacant 簽章 | 簽章驗證即破 |
| 修改舊 event | **能在 Merkle root 推送前**，之後**不能** | Git anchor + witness cosign |
| 重排 event 順序 | **能在 finalization 前** | 多方 attestation 鎖定 sequence |
| Split-view（給不同人看不同 STH） | **能**（短時間內） | gossip / witness cosign + cross-checkpoint |
| Selective hide 查詢結果 | **能**，但讀者拿不到 inclusion-by-key proof 即起疑 | 強制讀取端要 inclusion proof + Merkle range proof |
| Freeze 某 vacant | **不能單方面**，需要 quorum N-of-M attesters | 治理層；否則公示違規 |
| Sink 某 vacant | **不能**，需要 vacant 自簽 OR quorum | 同上 |
| Read-all（看到全部資料） | **能**，因為 event 設計上是公開的 | 不視為攻擊；改用 zero-knowledge 派生欄位若有隱私需求 |

### C.4 對 BRIEFING §11.3「透明 vs MINJA」的具體答案

> **「透明本身就是攻擊面，怎麼防？」**

核心回答：

1. **把 transparency 範圍最小化到「完整性」，不延伸到「語義授權」**：透明日誌只證明「event 存在過、未被改」，不證明「event 內容對讀者安全」。讀取端必須把 event payload 當 untrusted data。
2. **寫入閘門 + 讀取閘門分離**：
   - 寫入閘門：簽章 + idempotency + 多方 attestation finalization
   - 讀取閘門：schema-strict 反序列化、自然語言欄位禁止直接進 prompt、評分聚合是純運算（與 P3 一致）
3. **針對 MINJA 的具體防禦**：
   - vacant memory 不是 Registry 的職責；Registry 只記錄「結果型 event」（call_event 紀錄誰呼叫誰、review_event 記錄誰評了誰），不記錄 raw conversation memory
   - 想存 raw transcript 的，用 evidence_pointer (URL + hash) 指向外部 immutable storage（IPFS CID / S3 + ETag / sigstore bundle），Registry 只存 hash
   - 任何 vacant 把 Registry 的歷史 event 當 demonstration 餵給自己 LLM 時，本機 Vacant Runtime 必須通過 schema 萃取結構化欄位，不能直接 paste 自然語言
4. **異常偵測 + freeze 是兜底**：reputation 突跳 → auto-freeze + 公示。即使 MINJA 成功污染若干 review，freeze 機制可阻止「污染 → 改變呼叫流量 → 進一步污染」的反饋迴圈。
5. **revocation list 是私鑰外洩的唯一解**：第三方 dev_oracle（vacant 的擁有者）有單方 revoke 權，受影響 events 在 finalization 前可被撤銷。

### C.5 對 BRIEFING §11.1 / §11.2 的部分回答

§11.1（網路淘汰 vs Sybil）由 P2 主答，但 P4 提供：
- **沉沒不刪除**：sink_record 表保留所有失敗者歷史 → whitewashing 仍會留下 lineage 痕跡
- **lineage 表**：parent_id chain 讓「同一開發者反覆生新 vacant」可被聚類偵測
- **同源降權**所需的 base_model 欄位明確 schema 化

§11.2（cold start）由 P3 主答，但 P4 提供：
- prior 計算所需的 attestation_strength 欄位
- 「不公開純量分數直到樣本足夠」的 reputation_snapshot.n_samples 欄位 + status flag

### C.6 我的最終建議組合（給 P4_registry.md）

採用 codex Part B.7 的核心組合，加上 Part A 的治理層：

```
Layer 1: per-vacant hash chain + global hash chain (寫入即時)
Layer 2: 每 N 秒 Merkle root checkpoint，簽 + push 到 public Git append-only branch
Layer 3: 每 event 需 ≥ 3 個獨立 vacant cosign 才 finalized（finalization gate）
Layer 4: 異常偵測（rep 突跳 / 同源串謀 / 寫入頻率異常）→ auto-freeze + 公示
Layer 5: 每日 Merkle root 推 OpenTimestamps（Bitcoin 錨）
Layer 6 (聯邦期): 多 Registry 互相 cosign checkpoint；客戶端要求 N-of-M witness signature
```

**MVP 落地範圍**：Layer 1 + Layer 2 + Layer 3（簡化版 N=2，主持人可調）+ Layer 4（規則式 anomaly detector，不用 ML）。Layer 5 / 6 在第二期。

---

## D. 引用

### 攻擊面
- arXiv:2503.03704 — *MINJA: Memory Injection Attacks on LLM Agents via Query-Only Interaction* (2025/2026)
- arXiv:2604.02623 — *Poison Once, Exploit Forever: eTAMP Memory Poisoning on Web Agents*
- arXiv:2407.12784 — *AgentPoison: Red-teaming LLM Agents via Poisoning Memory or Knowledge Bases* (NeurIPS 2024)
- arXiv:2401.12242 — *BadChain: Backdoor Chain-of-Thought Prompting*
- arXiv:2406.00083 — *BadRAG: Vulnerabilities in Retrieval Augmented Generation*
- arXiv:2410.16155 — *A Troublemaker with Contagious Jailbreak Makes Chaos in Honest Towns*
- Johann Rehberger (2024) ChatGPT Memory spAIware PoC, Ars Technica 2024-09-24
- OWASP Agentic Top 10 (2026), ASI06 Memory & Context Poisoning
- OWASP Agent Memory Guard
- Palo Alto Unit 42 (2025) Bedrock Agents PoC

### 承諾層
- Ralph Merkle (1989) *A Certified Digital Signature*
- Haber & Stornetta (1991) *How to Time-Stamp a Digital Document*
- Bayer, Haber, Stornetta (1993) *Improving the Efficiency and Reliability of Digital Time-Stamping*
- Crosby & Wallach (USENIX 2009) *Efficient Data Structures for Tamper-Evident Logging*
- Laurie, Langley, Kasper (2013) RFC 6962 — Certificate Transparency
- Laurie, Messeri, Stradling (2021) RFC 9162 — Certificate Transparency v2
- Melara et al. (USENIX 2015) *CONIKS: Bringing Key Transparency to End Users*
- Eijdenberg, Laurie, Cutter (2015) *Verifiable Data Structures* (Trillian)
- Newman, Meyers, Torres-Arias et al. (CCS 2022) *Sigstore*
- Peter Todd (2016) OpenTimestamps
- C2SP tlog-checkpoint / tlog-witness / tlog-cosignature specs (2024+)

### 治理 / 哲學
- 責任有效性分析 §3.B.4 (memory poisoning)
- 責任有效性分析 §2.6 (DRF, attention-based trust)
- vacant_current_understanding §3.5 (Registry 角色)
