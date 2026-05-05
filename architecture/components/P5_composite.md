# P5: 複合 Vacant 內部規格

## 1. 範圍與目標

本 pane 負責設計**複合 vacant 的內部結構與通訊規格**，包含：對外身份的黑箱邊界、子代生命週期（誕生／運作／汰換）、子代間的發現機制（Q4 解法）、微型規格信封、以及「自己生 vs 外部用」決策樹。

**不負責：** 公網 A2A 傳輸格式（P1 管）、Registry capability card schema（P4 管）、公網 reputation 儲存與聚合（P3 管）。本文件的所有規格均只在複合 vacant 的私有邊界內生效；一旦訊息越過對外 endpoint，就回到 P1 的領域。

---

## 2. 設計決策

### D1：子代封閉是硬原則，不是軟性建議

「複合 vacant 子代不對外」是系統的結構完整性前提。一旦允許子代對外呼叫，就可以生一個「會去網路找美編的子代」，等於繞過原則本身。因此：

- 子代**沒有公網 A2A endpoint**，沒有 Registry 登錄，沒有外部可見身份。
- 子代的所有對外通訊**完全由 root 代理**，root 是唯一出口。

替代方案「允許子代持有外部 endpoint 但用 ACL 控管」被否決：ACL 可被繞過，且讓設計複雜度無法受控。

---

### D2：Q4 的解法——樹狀單向通訊（Tree-Only Discovery）

**問題：** 若有「內部 Registry」讓子代彼此發現，那它還是不是「自己生」？

**解法：** 子代之間**完全不需要互相發現**。子代只認識一個對象：它自己的 root（parent）。跨子代的協作全部由 root 居中調度。

```
子代 A ──請求→ root ──轉發→ 子代 B
子代 B ──回應→ root ──回傳→ 子代 A
```

root 維護一份私有的 `ChildManifest`（root 自身狀態的一部分，不是獨立的 Registry 服務），記錄它生出的每一個子代。這與「子代封閉」原則不衝突——root 知道自己的孩子是「自知」，不是「外部查詢」。

**為何否決方案 B（heartbeat 廣播子代清單）：** 廣播讓子代持有兄弟知識，等於子代具備網路感知能力，與封閉原則矛盾。

**為何否決方案 A（root-routed + 子代知道兄弟 ID）：** 子代知道兄弟 ID 等於隱含地「知道還有誰」——雖然技術上不直接呼叫，但語義上破壞了封閉感。Tree-Only 更乾淨：子代完全無感兄弟的存在。

---

### D3：對外身份黑箱原則

複合 vacant 對外的 capability card（P4 管），**不揭露內部子代結構**：

- 不列出有哪些子代、子代各自的能力
- 不揭露子代數量、子代 ID
- 允許一個 `composite: true` 標記，讓外部知道「這是複合個體」，但僅此而已

外部呼叫者的錯誤不能歸責到特定子代（子代沒有公開身份）——錯誤責任**整合在複合 vacant 的公網 reputation** 上。

---

### D4：「自己生 vs 外部用」是 vacant 自己的策略選擇

網路不規定誰必須複合、誰必須外部協作。這是每個 vacant 的競爭策略判斷。決策樹見 §3.4。

---

## 3. 元件規格 / 演算法 / 資料結構

### 3.1 對外邊界：複合 vacant 的單一 Facade

```
┌─────────────────────────────────────────────────────────────────┐
│  marketing-vacant  (composite, 對外唯一身份)                     │
│                                                                 │
│  public A2A endpoint:  /v1/task                                 │
│  capability card:      {composite: true, caps: ["marketing"]}  │
│  public reputation:    {factual, logical, relevance,           │
│                          honesty, adoption}  ← P3 管           │
│                                                                 │
│  ←── 外部只看到這條線，以下全部不可見 ───────────────────────── │
│                                                                 │
│  ┌───────────────────────── Root Coordinator ────────────────┐  │
│  │  ChildManifest (私有，僅 root 存取)                        │  │
│  │  ┌────────────────────────────────────────────────────┐   │  │
│  │  │ child_id │ capability │ spawn_ts │ fail_cnt │ score│   │  │
│  │  │ copy-01  │ copywriting│  T+0     │    2     │ 0.87 │   │  │
│  │  │ anlyt-01 │ analytics  │  T+120s  │    0     │ 0.91 │   │  │
│  │  │ vbrief-01│ visual_spec│  T+240s  │    1     │ 0.79 │   │  │
│  │  │ intgr-01 │ integration│  T+480s  │    0     │ 0.93 │   │  │
│  │  └────────────────────────────────────────────────────┘   │  │
│  │                                                            │  │
│  │  private_log (僅 root 讀寫，不上公網)                      │  │
│  │  heartbeat_collector (集中管理子代存活狀態)                 │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                 │
│   copy-01      anlyt-01     vbrief-01    intgr-01              │
│   (no ext      (no ext      (no ext      (no ext               │
│    endpoint)    endpoint)    endpoint)    endpoint)            │
└─────────────────────────────────────────────────────────────────┘
```

---

### 3.2 ChildManifest 資料結構

```jsonc
// ChildManifest — root 的私有狀態，不序列化到公網
{
  "composite_id": "marketing-vacant-abc123",
  "children": [
    {
      "child_id": "copy-01",
      "capability": "copywriting",
      "spawn_ts": 1746345600,
      "parent_id": "marketing-vacant-abc123",
      "fail_count": 2,
      "mini_rep": {
        "factual": 0.87,
        "logical": 0.85,
        "relevance": 0.90,
        "task_count": 14
      },
      "status": "active"   // active | replacing | retired
    }
    // ...
  ],
  "private_log_path": "./private/marketing-vacant-abc123.log"
}
```

`mini_rep` 只有三維（factual / logical / relevance）——對應有可量測的信號。`honesty` 與 `adoption` 在封閉子網路中訊號不足，不採用，等 §4 說明。

---

### 3.3 子代生命週期狀態機

```
  [root 偵測能力缺口]
         │
         ▼
    ┌─────────┐
    │ SPAWNING│  root 生成子代：分配 child_id、寫入 ChildManifest
    └────┬────┘
         │ spawn 成功
         ▼
    ┌─────────┐
    │  ACTIVE │  root 透過 tree-only 規格分派任務
    └────┬────┘
         │ fail_count ≥ threshold  OR  root 判定需升級
         ▼
    ┌──────────────┐
    │  REPLACING   │  root spawn 替代子代（新 child_id）
    │              │  舊子代降為 RETIRED，但保留在 private_log
    └──────┬───────┘
           │ 替代子代 ACTIVE 且穩定
           ▼
    ┌─────────┐
    │ RETIRED │  不刪除（保留內部責任歷史），不再接任務
    └─────────┘
```

**汰換閾值（可配置）：** 預設 `fail_count ≥ 5` 或連續 3 次輸出被 root 的 ground-truth check 駁回。

---

### 3.4 「自己生 vs 外部用」決策樹

```
需要某個能力 X
       │
       ▼
X 是否為品牌一致性的核心？
（語調、視覺風格、資料解讀框架）
       │
   是 ─┤
       │                    否 ─── X 是否已被網路上大量 vacant 提供？
       ▼                                  │
   自己生子代 ◄──── 優先 ──────── 是──────┤
                                          │
                                          否 ─── 網路上是否有高 reputation X-vacant？
                                                         │
                                          是 ────────────┤
                                                         │──→ composition link（外部協作）
                                          否 ─────────────→ 自己生（外部供給不足）
```

**composition link** 是複合 vacant 作為整體（root 層）跟外部 vacant 簽的協作，不是子代跟外部互動——子代封閉原則仍然完整。

---

### 3.5 子代信封格式（v4 修正：完整 Ed25519，跟公網 vacant 同規格）

> **v4 修正紀錄：** 早先版本把子代設計為 HMAC + root 共享密鑰、沒有 Ed25519，理由是「子代沒有公網身份，Ed25519 多餘」。但這跟「Path D：vacant 自己 spawn 後代」的設計衝突——子代既然是被 spawn 的，本來就跟母體同類。**子代從誕生即是完整 vacant**，包括自己的 Ed25519 keypair。

子代訊息使用**標準 A2A envelope**（跟公網 vacant 同規格）：

```jsonc
{
  "env_version": "a2a/1.0",
  "from": "ed25519:<child_pubkey_hash>",      // 子代的 Ed25519 vacant_id
  "to":   "ed25519:<root_pubkey_hash>",       // root 也是 vacant_id
  "payload": { ... },
  "ts": 1746345700,
  "sig": "<ed25519_signature_by_child>"       // 子代用自己的私鑰簽
}
```

**子代具備完整 vacant 構件**：
- 自己的 Ed25519 keypair（spawn 時產生）
- 自己的 capability_card（local-only，未推 Registry）
- 自己的 behavior_bundle / substrate_spec
- 自己的 minimal Vacant Runtime
- 自己的 logbook（local 累積、未公告）

**跟公網 vacant 的差別只在兩件事**：
- **Registry 註冊狀態**：子代的 capability_card 沒推 Registry，因此公網 capability_search 找不到它
- **外呼 policy**：composite parent 設定子代是否能對外呼叫（self-grown 型 = 否；broker 型 = 是）

**heartbeat 處理**：子代有自己的 heartbeat 但只在 composite 內部循環（root 收集），不獨立推 Registry。對外只呈現 root 的整體 heartbeat。

**為什麼仍堅持 Ed25519 而非 HMAC？**
1. ontology 一致：子代是完整 vacant，跟母體同類
2. 畢業時 keypair 不換：avoiding identity discontinuity（logbook 在子代視角持續）
3. 子代與 root 之間的訊息也帶可被獨立驗證的簽章（防 root 自導自演偽造子代訊息）

---

### 3.6 內部評估訊號（替代公網 peer review）

子代在封閉環境中，公網評估訊號消失，改用以下降級信號：

| 訊號 | 來源 | 說明 |
|---|---|---|
| root ground-truth check | root 對子代輸出做可客觀驗證的斷言 | 最可靠，但只適用有客觀解的任務 |
| caller feedback 反向歸因 | 外部 caller 給複合 vacant 的評分，按任務路徑拆解到子代 | 延遲、粗粒度，但可用 |
| adoption in pipeline | 子代輸出被後續子代實際使用（vs 被棄置）的次數 | 隱性採用信號 |

**明確限制（不假裝解決）：** 封閉環境的評估品質永遠低於公網 peer review。`honesty` 維度（自評 vs 他評落差）在子代層**無法採用**——子代沒有獨立評估者。這是複合架構的結構性代價，設計上誠實承認，不用偽信號填充。

---

### 3.7 複合 vacant 整體沉沒時的子代處置（v4 修正）

子代是完整 vacant、有自己的 keypair。整體沉沒時三條路：

```
複合 vacant 整體 reputation 跌至淘汰閾值
              │
              ├── 路徑 A（預設）：子代隨 root 一起沉沒
              │   parent 沉沒事件記錄到 Registry
              │   子代的 logbook 標 `parent_sunk: true`，但 keypair 仍存
              │
              ├── 路徑 B：root 在沉沒前畢業優秀子代
              │   選一個或多個表現最佳的子代，簽 register_vacant
              │   推 Registry 公告（同 keypair、同 logbook）
              │   parent_id = 原複合 vacant（永久標記）
              │   公開 reputation 從 baseline + parent attestation bonus 起
              │
              └── 路徑 C：子代主動畢業（沉沒前的緊急逃生）
                  parent 同意後子代自簽 register_vacant
                  Registry 標 `urgent_graduation: true` 旗標讓 caller 看見
                  比正常畢業 prior 更低（urgent_graduation_penalty）
```

**畢業 ≠ 升格成新身份**——子代從一開始就是完整 vacant、有 keypair；畢業只是把 capability_card 從 local 推到 Registry。同一個 keypair、同一條 logbook，只是可見性切換。

「畢業」是有限且需 parent 同意的操作，不鼓勵作為逃生艙。它的存在是為了保留有價值的能力。

---

### 3.8 複合 vacant 向外 spawn（產生獨立後代）

當複合 vacant 想擴大網路影響力，或偵測到某子代已成熟到可獨立競爭：

- 向外 spawn 的是**新個體 vacant**（有獨立 vacant_id，上 Registry）
- 與 P1 的 spawn 機制完全一致（parent_id 指向複合 vacant）
- **這個動作不是「子代對外」**——是 root 代表整體向外生育，子代沒有參與
- spawn 後，新個體與原複合 vacant 無隸屬關係，自行在公網競爭

---

## 4. 對應到的缺口 / 風險

### Q4（子代之間如何發現彼此）— 直接解決

Tree-Only 通訊模型消除了「子代需要跨發現」的前提。子代不需要兄弟知識，root 負責全部調度。此設計不需要內部 Registry 服務，不違反「自己生」原則。

### Q5（mkt-research 子節點對外呼叫的問題）— 直接解決

原互動圖中 mkt-research 節點呼叫公網 stats-vacant，違反封閉原則。修法：將統計能力改為 `analytics-child`（自生子代），root 在 spawn 時配置統計工具集。外部 stats-vacant 只能被網路上的直接 caller 使用，與複合 vacant 子網路無關。

### G03（對抗 reward hacking）— 部分回應

內部 mini_rep 採多維（三維），避免單純最大化某一指標。但封閉環境下評估者獨立性受限（只有 root），這是此架構的已知弱點，不宣稱完全解決 G03。

### G05（無人類介入評估）— 部分回應

子代層的 ground-truth check 和 adoption signal 提供無人介入的機械驗證信號，但覆蓋率取決於任務是否有客觀解。對沒有客觀解的創意任務（文案品質），仍然依賴 caller feedback 間接折射，評估品質有限。

### G04（記錄不可竄改）— 部分回應

`private_log` 建議使用 append-only hash chain（與公網 tamper-evident 機制相同格式，但不上鏈）。即使是私有記錄，可在子代提升或複合 vacant 沉沒時提交給 Registry 作歷史存檔，維繫責任追溯。

---

## 5. 參考文獻 / 引用

- Goodhart, C. (1975). Monetary relationships: a view from Threadneedle Street. — 多維 reputation 設計依據（不用單一純量）
- Skalse et al. (2022). Defining and Characterizing Reward Hacking. arXiv:2209.13085 — 多評估者必要性
- Douceur, J. (2002). The Sybil Attack. IPTPS. — 封閉子代無 Sybil 問題（無公網身份即無 Sybil 攻擊面）
- Friedman, B., Nissenbaum, H. (1996). Bias in computer systems. TOIS 14(3). — 評估者偏見在子代封閉環境中的限制
- DRF（Decentralized Reputation Framework，文獻探勘 §3）: `honesty` 維度在封閉環境不採用的依據（自評 vs 他評需要獨立評估者）

---

## 6. 對其他 pane 的依賴與假設

| 依賴對象 | 假設內容 | 如果假設錯誤的影響 |
|---|---|---|
| P1 (個體 vacant spawn) | 複合 vacant 向外 spawn 使用 P1 標準機制（parent_id 串系）；微型規格與 P1 A2A 規格無衝突 | 若 P1 要求 spawn 必須攜帶完整 A2A 身份，子代提升流程需調整 |
| P4 (Registry cap card) | capability card 支援 `composite: true` 標記；不強制揭露子代清單 | 若 P4 要求揭露子代數量或 ID，黑箱原則需重議 |
| P3 (reputation 儲存) | 公網 reputation 只對應 composite_id，不對應任何 child_id | 若 P3 設計允許 child_id 出現在公網，需明確封鎖 |

---

## 7. 未解問題 / 留給後續

1. **子代提升的 reputation 折扣系數 α 應如何設定？** 目前只說「< 1」，沒有量化。需要 P3 pane 配合設計換算公式。

2. **私有 mini_rep 的冷啟動問題：** 新子代剛 spawn 時，mini_rep 全為 0 或 null。root 在第一批任務前如何決定派工優先級？（round-robin? 隨機?）

3. **多層嵌套複合 vacant 的可能性：** 本文件假設只有一層（root → children）。如果 child 本身也是複合 vacant（children 有自己的 children），規格是否遞迴適用？目前沒有設計，但 Tree-Only 模型在結構上允許，待後續確認。

4. **root 單點失敗：** root 是唯一出口，root crash 導致整個複合 vacant 下線。這是設計的明確取捨（簡單性換穩健性），但 demo 中需要說明。

5. **ground-truth check 的覆蓋率量化：** 對行銷類任務（文案、設計規格），什麼比例的子代輸出可以客觀驗證？若覆蓋率 < 30%，internal mini_rep 的可信度需打更大折扣。
