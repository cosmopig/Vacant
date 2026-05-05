# P4: Registry + 防竄改

## 1. 範圍與目標

Registry 是 Vacant 唯一的有形中央元件——**居民登記處 + 入口指南 + 事後紀錄**。本 pane 設計：

- 完整 **SQLite schema**（capability card / event log / reputation snapshot / composition link / sink record / attestation / merkle epoch / freeze / revocation）
- 完整 **RPC 端點清單**（寫入 + 讀取，全部 paginated 且帶簽章 commitment）
- 多層 **防竄改架構**（hash chain → Merkle root → Git anchor → 多方 attestation → 異常 freeze → OTS 長期錨）
- **MVP → 聯邦 → 分散化** 的遷移路徑（公鑰錨定不換）
- **防 MINJA / eTAMP** 的寫入與讀取流程

**不負責**：reputation 數學（P3）、身份綁定演算法（P2）、A2A envelope 結構（P6）、Vacant Runtime 內部行為（P1）、composite vacant 子網路（P5）。Registry **不思考、不仲裁、不評分、不 ranking**——它只儲存、簽章、發 proof。

---

## 2. 設計決策

### 2.1 Registry 是 trust anchor，不是 trust origin

**決策**：Registry 不對「event 內容」背書，只對「event 存在過、未被改」背書。Event 內容由 vacant 本身簽章。

**為什麼**：BRIEFING §3 禁止中央 LLM/judge；vacant_current_understanding §3.5 明確指出 Registry「不思考、不仲裁」。Registry 即使可以 read-all，它的權力上限是 censorship 與 split-view，**不能偽造**。

**否決替代**：
- ❌「Registry 主動驗證 event 合法性」→ 變成中央仲裁者
- ❌「Registry 可改寫舊 event 修錯」→ 違反 append-only

### 2.2 vacant_id = Ed25519 公鑰的 multihash

**決策**：`vacant_id = multibase(multihash(canonical_public_key))`，不是 Registry 流水號。

**為什麼**：BRIEFING §9「公鑰錨定不換」是聯邦化前提。如果 ID 是 Registry 序號，遷移時客戶端引用會全部失效；公鑰錨定讓 vacant 在 MVP / 聯邦 / 分散化三階段一律可攜。

**否決替代**：
- ❌ INTEGER PK auto-increment → 與聯邦同步衝突
- ❌ UUID → 沒密碼學綁定，不能驗 ownership

### 2.3 兩個獨立的安全屬性必須顯式分離

**決策**：把「**完整性**」（hash chain + Merkle）與「**語義安全**」（多方 attestation + freeze）做成兩條獨立的防線，而不是合併。

**為什麼**：codex Part A 結論——**MINJA 的 95% 注入率在密碼學承諾下完全不被擋住**，因為 MINJA 是合法寫入。設計上必須拒絕「簽了 hash chain 就安全」的誤解。

### 2.4 Layer 1-6 防禦組合

| 層 | 機制 | 阻擋什麼 | 部署階段 |
|---|---|---|---|
| L1 | per-vacant + global hash chain | 單次刪改、插入、重排 | MVP |
| L2 | Merkle root checkpoint + Git append-only push | Registry operator 重寫歷史 | MVP |
| L3 | 多方 attestation finalization (N-of-M) | 單一 vacant 私鑰外洩、collusion 寫入 | MVP（簡化 N=2） |
| L4 | 異常偵測 → auto-freeze + 公示 | reputation 突跳、頻率異常、collusion graph | MVP（規則式） |
| L5 | OpenTimestamps 每日 Bitcoin anchor | Git 平台被攻陷或刪庫 | 第二期 |
| L6 | 多 Registry witness cosign（聯邦期） | split-view, Registry operator 共謀 | 聯邦期 |

L1-L4 為 MVP 必須；L5-L6 為演進。

### 2.5 不存 raw text，存 evidence pointer

**決策**：Registry 只記錄結構化 event（誰呼叫誰、誰評誰、誰生誰）。raw conversation transcript / agent memory **不寫進 Registry**，存外部（IPFS CID / S3 + ETag），Registry 只記錄 hash + URL。

**為什麼**：(a) 大幅縮小 MINJA 注入面（schema-strict，自然語言欄位最小化）；(b) Registry size 可控；(c) raw text 隱私需求可由不同存取控制處理。

### 2.6 寫入採 idempotency + canonical hash

**決策**：所有 write RPC 必含 `idempotency_key`（UUID）+ `canonical_event_hash`（payload 規範化後 hash）。重複寫同一 key → 直接返回原 event_seq，不重複寫。

**為什麼**：防 replay attack；防 double-spend（同 idempotency_key 簽不同內容 → 第二筆拒絕並公示）。

---

## 3. 元件規格

### 3.1 完整 SQLite schema（CREATE TABLE）

> SQLite + WAL，UTF-8，所有時間戳一律 millis since epoch。文字欄位除非另注皆為 TEXT。

```sql
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

-- =============================================================
-- 1) vacant 主表（capability card 當前快照）
-- =============================================================
CREATE TABLE vacant (
    vacant_id          TEXT PRIMARY KEY,           -- multibase(multihash(pubkey))
    public_key         BLOB NOT NULL UNIQUE,       -- Ed25519 32-byte
    owner_org          TEXT,                       -- 開發者或組織標識
    base_model         TEXT NOT NULL,              -- e.g. "claude-sonnet-4-6", "qwen-2.5-7b"
    base_model_family  TEXT NOT NULL,              -- e.g. "claude", "gemini" (用於同源降權)
    parent_id          TEXT,                       -- 譜系；NULL = root
    version            TEXT NOT NULL,              -- semver
    declared_capabilities_json TEXT NOT NULL,      -- JSON array of domain tags
    capability_card_hash       BLOB NOT NULL,      -- canonical hash of full card
    capability_card_sig        BLOB NOT NULL,      -- self-signature of card by vacant
    stake_amount       INTEGER NOT NULL DEFAULT 0, -- P2 stake/bond
    status             TEXT NOT NULL DEFAULT 'active'
                       CHECK(status IN ('active','frozen','sunk','revoked')),
    registered_at      INTEGER NOT NULL,
    latest_event_seq   INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY(parent_id) REFERENCES vacant(vacant_id)
);
CREATE INDEX idx_vacant_owner ON vacant(owner_org);
CREATE INDEX idx_vacant_parent ON vacant(parent_id);
CREATE INDEX idx_vacant_model ON vacant(base_model_family);
CREATE INDEX idx_vacant_status ON vacant(status);

-- =============================================================
-- 2) attestation（P2 給的身份背書）
-- =============================================================
CREATE TABLE attestation (
    attestation_id     TEXT PRIMARY KEY,           -- UUID
    vacant_id          TEXT NOT NULL,
    attester_kind      TEXT NOT NULL
                       CHECK(attester_kind IN ('developer','org','peer','dev_oracle','sigstore')),
    attester_pubkey    BLOB NOT NULL,
    attester_signature BLOB NOT NULL,
    payload_hash       BLOB NOT NULL,              -- attested capability card hash
    valid_from         INTEGER NOT NULL,
    valid_until        INTEGER,                    -- NULL = no expiry
    revoked_at         INTEGER,
    FOREIGN KEY(vacant_id) REFERENCES vacant(vacant_id)
);
CREATE INDEX idx_att_vacant ON attestation(vacant_id);
CREATE INDEX idx_att_pubkey ON attestation(attester_pubkey);

-- =============================================================
-- 3) event log（append-only；hash chain + Merkle 的核心）
-- =============================================================
CREATE TABLE event (
    seq                INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type         TEXT NOT NULL
                       CHECK(event_type IN
                            ('register','call','review','peer_review',
                             'spawn','self_eval','composition_link',
                             'sink','freeze','revoke','snapshot','attestation_add')),
    actor_vacant_id    TEXT NOT NULL,              -- 簽章者
    subject_vacant_id  TEXT,                       -- 事件對象（review/sink 等）
    payload_json       TEXT NOT NULL,              -- 事件本體 (schema-strict)
    payload_hash       BLOB NOT NULL,              -- canonical hash of payload_json
    idempotency_key    TEXT NOT NULL UNIQUE,       -- 重放保護
    signed_by_pubkey   BLOB NOT NULL,
    signature          BLOB NOT NULL,              -- Ed25519 sig over canonical bytes
    prev_event_hash    BLOB NOT NULL,              -- hash chain：上一筆 event_hash
    event_hash         BLOB NOT NULL UNIQUE,       -- H(prev || type || actor || subject || payload_hash || idem || pubkey || sig || ts)
    ts                 INTEGER NOT NULL,           -- millis
    epoch_id           INTEGER,                    -- nullable until rolled into Merkle epoch
    finalized_at       INTEGER,                    -- nullable until N attestations
    finalization_count INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY(actor_vacant_id)   REFERENCES vacant(vacant_id),
    FOREIGN KEY(subject_vacant_id) REFERENCES vacant(vacant_id),
    FOREIGN KEY(epoch_id)          REFERENCES merkle_epoch(epoch_id)
);
CREATE INDEX idx_event_actor   ON event(actor_vacant_id, seq);
CREATE INDEX idx_event_subject ON event(subject_vacant_id, seq);
CREATE INDEX idx_event_type    ON event(event_type, seq);
CREATE INDEX idx_event_epoch   ON event(epoch_id);
CREATE INDEX idx_event_ts      ON event(ts);

-- =============================================================
-- 4) event finalization（N-of-M 多方簽章）
-- =============================================================
CREATE TABLE event_finalization (
    event_seq          INTEGER NOT NULL,
    attester_vacant_id TEXT NOT NULL,
    attester_pubkey    BLOB NOT NULL,
    signature          BLOB NOT NULL,              -- sig over event_hash
    base_model_family  TEXT NOT NULL,              -- 同源降權需要
    signed_at          INTEGER NOT NULL,
    PRIMARY KEY(event_seq, attester_vacant_id),
    FOREIGN KEY(event_seq) REFERENCES event(seq),
    FOREIGN KEY(attester_vacant_id) REFERENCES vacant(vacant_id)
);
CREATE INDEX idx_final_event ON event_finalization(event_seq);

-- =============================================================
-- 5) Merkle epoch（週期性 Merkle root 與 Git anchor）
-- =============================================================
CREATE TABLE merkle_epoch (
    epoch_id           INTEGER PRIMARY KEY AUTOINCREMENT,
    first_seq          INTEGER NOT NULL,
    last_seq           INTEGER NOT NULL,
    tree_size          INTEGER NOT NULL,
    root_hash          BLOB NOT NULL UNIQUE,
    sealed_at          INTEGER NOT NULL,
    registry_signature BLOB NOT NULL,              -- Registry operator 簽 root
    git_commit_sha     TEXT,                       -- nullable until pushed
    git_repo_url       TEXT,
    git_branch         TEXT DEFAULT 'transparency-log',
    pushed_at          INTEGER,
    ots_proof_hash     BLOB,                       -- nullable until OTS upgraded
    ots_upgraded_at    INTEGER
);
CREATE INDEX idx_epoch_seq_range ON merkle_epoch(first_seq, last_seq);

-- =============================================================
-- 6) witness cosignature（L6，聯邦期可用）
-- =============================================================
CREATE TABLE epoch_witness (
    epoch_id           INTEGER NOT NULL,
    witness_id         TEXT NOT NULL,              -- witness operator id
    witness_pubkey     BLOB NOT NULL,
    cosignature        BLOB NOT NULL,              -- sig over (epoch_id, root_hash)
    cosigned_at        INTEGER NOT NULL,
    PRIMARY KEY(epoch_id, witness_id),
    FOREIGN KEY(epoch_id) REFERENCES merkle_epoch(epoch_id)
);

-- =============================================================
-- 7) reputation snapshot（與 P3 對齊；五維 + CI + 多元性）
-- =============================================================
CREATE TABLE reputation_snapshot (
    snapshot_id        TEXT PRIMARY KEY,           -- UUID
    vacant_id          TEXT NOT NULL,
    epoch_id           INTEGER NOT NULL,           -- 對齊 Merkle epoch
    factual_mean       REAL,
    factual_lo_ci      REAL,
    factual_hi_ci      REAL,
    factual_n          INTEGER,
    logical_mean       REAL,
    logical_lo_ci      REAL,
    logical_hi_ci      REAL,
    logical_n          INTEGER,
    relevance_mean     REAL,
    relevance_lo_ci    REAL,
    relevance_hi_ci    REAL,
    relevance_n        INTEGER,
    honesty_mean       REAL,
    honesty_lo_ci      REAL,
    honesty_hi_ci      REAL,
    honesty_n          INTEGER,
    adoption_mean      REAL,
    adoption_lo_ci     REAL,
    adoption_hi_ci     REAL,
    adoption_n         INTEGER,
    diversity_index    REAL,                       -- 0-1, fraction from non-dominant model family
    sample_status      TEXT NOT NULL
                       CHECK(sample_status IN ('insufficient','partial','sufficient')),
    snapshot_hash      BLOB NOT NULL,              -- canonical hash for inclusion proof
    registry_signature BLOB NOT NULL,
    computed_at        INTEGER NOT NULL,
    FOREIGN KEY(vacant_id) REFERENCES vacant(vacant_id),
    FOREIGN KEY(epoch_id)  REFERENCES merkle_epoch(epoch_id)
);
CREATE INDEX idx_rep_vacant ON reputation_snapshot(vacant_id, epoch_id DESC);

-- =============================================================
-- 8) composition link（產業鏈雙邊綁定）
-- =============================================================
CREATE TABLE composition_link (
    link_id            TEXT PRIMARY KEY,           -- UUID
    vacant_a           TEXT NOT NULL,
    vacant_b           TEXT NOT NULL,
    agreed_payload_json TEXT NOT NULL,             -- domain, weight, callback contract
    sig_a              BLOB NOT NULL,
    sig_b              BLOB NOT NULL,
    created_event_seq  INTEGER NOT NULL,
    created_at         INTEGER NOT NULL,
    terminated_at      INTEGER,                    -- nullable, 雙方解約後填
    terminated_event_seq INTEGER,
    FOREIGN KEY(vacant_a) REFERENCES vacant(vacant_id),
    FOREIGN KEY(vacant_b) REFERENCES vacant(vacant_id),
    FOREIGN KEY(created_event_seq) REFERENCES event(seq)
);
CREATE INDEX idx_link_a ON composition_link(vacant_a);
CREATE INDEX idx_link_b ON composition_link(vacant_b);

-- =============================================================
-- 9) sink record（被沉沒，但歷史保留）
-- =============================================================
CREATE TABLE sink_record (
    vacant_id          TEXT PRIMARY KEY,
    sunk_event_seq     INTEGER NOT NULL,
    sunk_at            INTEGER NOT NULL,
    reason             TEXT NOT NULL,              -- self / quorum / anomaly
    reason_detail_json TEXT,
    replaced_by_vacant_id TEXT,
    quorum_signatures_json TEXT,                   -- 多方 sink 時的 sig 列表
    FOREIGN KEY(vacant_id) REFERENCES vacant(vacant_id),
    FOREIGN KEY(sunk_event_seq) REFERENCES event(seq),
    FOREIGN KEY(replaced_by_vacant_id) REFERENCES vacant(vacant_id)
);

-- =============================================================
-- 10) freeze（暫凍；異常偵測觸發或治理）
-- =============================================================
CREATE TABLE freeze (
    freeze_id          TEXT PRIMARY KEY,           -- UUID
    vacant_id          TEXT NOT NULL,
    frozen_at          INTEGER NOT NULL,
    reason             TEXT NOT NULL,              -- anomaly / governance / self
    anomaly_signal_json TEXT,                      -- {"kind":"rep_jump","delta":0.42,...}
    frozen_by_kind     TEXT NOT NULL CHECK(frozen_by_kind IN ('anomaly_engine','quorum','self')),
    quorum_signatures_json TEXT,
    lifted_at          INTEGER,                    -- nullable
    lifted_by_kind     TEXT,
    FOREIGN KEY(vacant_id) REFERENCES vacant(vacant_id)
);
CREATE INDEX idx_freeze_vacant ON freeze(vacant_id, frozen_at DESC);

-- =============================================================
-- 11) revocation（私鑰外洩等）
-- =============================================================
CREATE TABLE revocation (
    revocation_id      TEXT PRIMARY KEY,
    vacant_id          TEXT NOT NULL,
    revoked_pubkey     BLOB NOT NULL,
    revoked_at         INTEGER NOT NULL,
    by_kind            TEXT NOT NULL CHECK(by_kind IN ('self','dev_oracle','quorum')),
    evidence_event_seq INTEGER,
    signatures_json    TEXT NOT NULL,              -- 證明 by_kind 的簽章束
    FOREIGN KEY(vacant_id) REFERENCES vacant(vacant_id)
);
CREATE INDEX idx_rev_vacant ON revocation(vacant_id);
CREATE INDEX idx_rev_pubkey ON revocation(revoked_pubkey);

-- =============================================================
-- 12) read commitment audit（讀取也留痕，可選）
-- =============================================================
CREATE TABLE read_audit (
    audit_id           TEXT PRIMARY KEY,
    requester_pubkey   BLOB,                       -- nullable (匿名查詢)
    query_kind         TEXT NOT NULL,
    query_hash         BLOB NOT NULL,
    response_root      BLOB NOT NULL,              -- Merkle root used
    response_signature BLOB NOT NULL,              -- Registry sig over (query_hash || response_hash || epoch_id)
    served_at          INTEGER NOT NULL
);

-- =============================================================
-- 13) anomaly detector state（L4 規則式偵測）
-- =============================================================
CREATE TABLE anomaly_window (
    vacant_id          TEXT NOT NULL,
    metric             TEXT NOT NULL,              -- rep_jump, rev_burst, collusion_score...
    window_start       INTEGER NOT NULL,
    window_end         INTEGER NOT NULL,
    value              REAL NOT NULL,
    threshold          REAL NOT NULL,
    triggered          INTEGER NOT NULL DEFAULT 0,  -- 0/1
    PRIMARY KEY(vacant_id, metric, window_start)
);
```

#### Hash chain canonical 規則

```
event_hash = BLAKE3(
    prev_event_hash       (32B)
 || event_type            (utf-8 bytes)
 || actor_vacant_id       (utf-8 bytes)
 || subject_vacant_id?    (utf-8 bytes, empty if NULL)
 || payload_hash          (32B)
 || idempotency_key       (utf-8 bytes)
 || signed_by_pubkey      (32B)
 || signature             (64B)
 || ts_be64               (8B big-endian)
)
```

`payload_hash = BLAKE3(canonicalize_json(payload))`，canonicalize 規則 = JCS (RFC 8785)。

#### Genesis event

`seq=1`, `event_type='register'`, `actor=registry`, `prev_event_hash = 0x00...00 (32B)`, `signed_by_pubkey = registry_operator_key`，作為整條鏈的錨。

### 3.2 RPC 端點清單

規格：HTTPS + JSON over POST，URI 前綴 `/v1/`。所有寫入 RPC 接收 P6 envelope；所有讀取 RPC 回傳 `{data, proof, registry_signature, epoch_id}` 結構，client 可離線驗證。

#### 寫入端

| 端點 | 必要欄位 | 行為 |
|---|---|---|
| `POST /v1/register_vacant` | capability_card, attestations[], self_signature, idempotency_key | 寫 vacant + attestation + emit `register` event；status='active' |
| `POST /v1/submit_event` | event_envelope (P6) | 通用入口；按 event_type dispatch；驗 sig + idem，鏈 prev_hash |
| `POST /v1/submit_review` | review_envelope (P6) | review event 的 sugar；要求 reviewer != reviewee |
| `POST /v1/submit_peer_review` | peer_review_envelope | idle-time 主動評；不關聯 specific call_id |
| `POST /v1/spawn` | parent_id, child_capability_card, parent_signature, attestations[] | 寫新 vacant + lineage edge + emit `spawn` event |
| `POST /v1/submit_composition_link` | link_payload, sig_a, sig_b | 雙邊綁定；單邊不接受 |
| `POST /v1/submit_finalization` | event_seq, attester_vacant_id, signature | L3 多方背書；finalization_count++; 達 N 即 finalized_at = now |
| `POST /v1/submit_attestation` | vacant_id, attester_kind, payload_hash, signature, valid_from/until | 加 attestation row |
| `POST /v1/sink` | target_vacant_id, reason, signatures[] | 自簽 OR quorum；寫 sink_record + emit `sink` event |
| `POST /v1/request_revocation` | vacant_id, revoked_pubkey, by_kind, signatures[], evidence_event_seq? | 寫 revocation + emit `revoke` event |
| `POST /v1/report_anomaly` | vacant_id, anomaly_signal, evidence_pointer | 進 anomaly_window；達閾值由 L4 自動 freeze |
| `POST /v1/seal_epoch` | (internal, registry-signed) | 觸發 Merkle root 計算 + Git push；通常 cron 驅動 |

#### 讀取端

所有讀取均回傳 `{data, inclusion_proof?, consistency_proof?, registry_signature, epoch_id, served_at}`。

| 端點 | 參數 | 回傳 |
|---|---|---|
| `GET /v1/capability_card/{vacant_id}` | — | 當前 card + 簽章歷史 + 簽章 |
| `POST /v1/query_capability` | domain, dim_weights{}, k, cursor | UCB-aware top-k 候選；附 SMT inclusion proof for each |
| `GET /v1/reputation/{vacant_id}` | dim?, at_epoch? | 五維 snapshot + CI + n + diversity；附 inclusion proof against epoch root |
| `GET /v1/reputation_history/{vacant_id}` | from_epoch, to_epoch, cursor | 時間序列 snapshots |
| `GET /v1/event_log/{vacant_id}` | range_seq, cursor, limit (≤500) | actor 或 subject = vacant_id 的事件；分頁；附 Merkle range proof |
| `GET /v1/event/{seq}` | — | 單筆 event + Merkle inclusion proof |
| `GET /v1/lineage/{vacant_id}` | depth_up?, depth_down? | 譜系樹；parent / descendants |
| `GET /v1/composition_links/{vacant_id}` | active_only? | 該 vacant 的所有 link 列表 |
| `GET /v1/sink_record/{vacant_id}` | — | sunk 詳情；含被誰取代 |
| `GET /v1/freeze_status/{vacant_id}` | — | 當前是否 frozen + 原因 + lifted? |
| `GET /v1/revocation_list` | since_epoch, format=full|bloom | 全部或 bloom filter；附簽章 |
| `GET /v1/epoch/{epoch_id}` | — | epoch 元資料 + Merkle root + Git commit + witness cosigs |
| `GET /v1/epoch_root/latest` | — | 最新 sealed epoch |
| `GET /v1/inclusion_proof/{event_seq}` | epoch_id? | event 對某 epoch root 的 Merkle proof |
| `GET /v1/consistency_proof` | from_epoch, to_epoch | 兩個 root 的 consistency proof（CT 風格） |
| `GET /v1/audit/read_log` | by_pubkey?, since? | （可選公開）讀取記錄 |

#### 寫入流程（含防竄改與防 MINJA）

```
client → POST /v1/submit_event
  1. 驗 envelope 結構（schema-strict; 拒絕未列欄位）
  2. 驗 idempotency_key 唯一；命中既有 event_seq 直接 return
  3. 驗 signed_by_pubkey 有效（vacant 存在 + 未 revoked + 未 frozen 或允許之 event_type）
  4. 驗 signature over canonical bytes
  5. 算 prev_event_hash = (last event_hash)
  6. 算 payload_hash = BLAKE3(canonicalize_json(payload))
  7. 算 event_hash; INSERT event
  8. 觸發 L4 anomaly_engine 檢查（rep_jump 等）
  9. 回傳 {seq, event_hash, ts}
  ── async ──
 10. cron 或 size-trigger seal_epoch:
     - 取所有 epoch_id IS NULL 的 events，按 seq 順序
     - 建 Merkle tree, 算 root_hash
     - registry op key 簽 (epoch_id, first_seq, last_seq, root_hash)
     - INSERT merkle_epoch; UPDATE event SET epoch_id
     - 異步 Git commit + push transparency-log branch
     - 異步 OTS submit（每日 batch）
 11. finalization：當 N 個獨立 vacant submit_finalization
     (要求 attester base_model_family 多元性 ≥ 2/N)
     → finalized_at = now
```

#### 異常偵測規則（L4，規則式 MVP）

| 訊號 | 閾值 | 動作 |
|---|---|---|
| reputation 任一維度 60s 內變化 > 0.4 | 0.4 | auto-freeze 24h + 公示 |
| 同一 reviewer 對同一 reviewee 1h > 5 次評分 | 5 | reviewer freeze + 該批 review 不計入 |
| 同 base_model_family 連續 N=10 次 finalize 同一 event | 10 | event 改為 unfinalized + 要求重收 |
| spawn rate > 10/h from same parent_id | 10 | 觸發 Sybil 警告（傳 P2） |

freeze 期間 vacant 仍可被讀取但不接受新 review 進入聚合，自簽 sink 與 self-eval 仍允許。

### 3.3 Git anchor 細節（L2）

- 公開 GitHub repo（或 federation 期多 mirror），branch `transparency-log`，**禁止 force-push**（GitHub branch protection + repo-level admin policy）
- 每個 commit 的 tree 含 `epoch_<id>.json`，內容 = `{epoch_id, first_seq, last_seq, root_hash_b64, sealed_at, prev_root_hash_b64, registry_signature_b64}`
- commit message 含 `epoch_id` 與 `root_hash`
- 用 Sigstore keyless signed tag `epoch-<id>`（OIDC 綁 registry operator org）
- 客戶端可 clone repo 自行驗證鏈條完整性

### 3.4 聯邦化路徑

| 階段 | 結構 | vacant_id 可攜性 |
|---|---|---|
| MVP | 單 Registry process + SQLite WAL + Git anchor + L4 規則式 anomaly | 公鑰錨定，已 OK |
| 中期（聯邦） | M 個 Registry shard（按 region / org），各自 SQLite；shard 之間 gossip checkpoint；client 要求 N-of-M witness cosign 才接受 read | vacant 可在 shard 間遷移：簽 rotation event（舊 key 簽新 shard 的 hosting record），新 shard 上線 + Key Transparency map 記錄 |
| 長期（分散化） | 事件 DAG（per-vacant signed log）+ libp2p 同步 + Merkle checkpoint anchor 到 L2/Bitcoin；無中央 sequencer | vacant_id 不變；客戶端按 witness quorum + 時間錨選 canonical history |

每階段 schema 不必整體換，只新增/廢用欄位（向後相容）。

---

## 4. 對應到的缺口 / 風險

| 編號 | 缺口 / 問題 | 本設計如何回應 |
|---|---|---|
| **G04** | 記錄不可竄改（MINJA 95%） | L1 hash chain + L2 Merkle/Git + L3 N-of-M attestation + L4 freeze + L5 OTS 是六層獨立防線；MINJA 主要被 L3 + L4 + 應用層 schema-strict 擋（L1/L2 不擋 MINJA，但擋 Registry operator 重寫） |
| G02 | 身份/Sybil（P2 主答） | 提供 base_model_family 欄位 + lineage 表 + revocation list，給 P2 算 whitewashing cost 用 |
| G01 | 跨任務、跨組織持久化 reputation | reputation_snapshot + event_log 同 vacant_id 終身；聯邦遷移有 rotation 機制 |
| G03 | 多元評估者 | event_finalization 要求 base_model_family 多元性 ≥ 2/N；anomaly 規則偵測同源 collusion |
| G05 | 無 ground truth 的評估（P3 主答） | Registry 只儲存，不評估 |
| G06 | Anti-complacency UX（P3 主答） | reputation_snapshot 強制存 CI + n + diversity_index + sample_status='insufficient' 三態，read RPC 直接回傳，客戶端可顯示「資料不足」 |
| **Q1** | Registry 中央化 vs 聯邦化 | §3.4 三階段路徑；公鑰錨定保證可攜 |
| BRIEFING §11.3 | 透明 vs MINJA | §C.4 五點答案；schema-strict 寫入 + evidence_pointer 不存 raw text + L3/L4 兜底 |
| Registry 權力邊界 | — | §C.3 表：Registry 能 censor 與 split-view，但不能偽造；對 read-all 不視為攻擊（events 設計上公開）；freeze/sink 一律需要 quorum 或 vacant 自簽 |

---

## 5. 參考文獻

- Merkle, R. (1989) *A Certified Digital Signature*
- Haber, S., Stornetta, W. (1991) *How to Time-Stamp a Digital Document*
- Bayer, D., Haber, S., Stornetta, W. (1993) *Improving the Efficiency and Reliability of Digital Time-Stamping*
- Crosby, S., Wallach, D. (USENIX 2009) *Efficient Data Structures for Tamper-Evident Logging*
- Laurie, B., Langley, A., Kasper, E. (2013) **RFC 6962** — Certificate Transparency
- Laurie, B., Messeri, E., Stradling, R. (2021) **RFC 9162** — Certificate Transparency v2
- Melara, M. et al. (USENIX 2015) *CONIKS: Bringing Key Transparency to End Users*
- Eijdenberg, A., Laurie, B., Cutter, A. (2015) *Verifiable Data Structures* (Trillian)
- Newman, Z., Meyers, J., Torres-Arias, S. et al. (CCS 2022) *Sigstore: Software Signing for Everybody*
- Todd, P. (2016) *OpenTimestamps*
- C2SP (2024+) tlog-checkpoint, tlog-witness, tlog-cosignature specs
- Dong, S. et al. arXiv:**2503.03704** (2025) *MINJA: Memory Injection Attacks on LLM Agents via Query-Only Interaction*
- arXiv:**2604.02623** *Poison Once, Exploit Forever* (eTAMP)
- Chen, Z. et al. arXiv:**2407.12784** (NeurIPS 2024) *AgentPoison*
- Xiang, Z. et al. arXiv:**2401.12242** *BadChain*
- Xue, J. et al. arXiv:**2406.00083** *BadRAG*
- arXiv:**2410.16155** *Contagious Jailbreak (ARCJ)*
- OWASP (2026) Agentic Top 10 — ASI06 Memory & Context Poisoning
- Friedman, E. et al. (2007) *Manipulation-Resistant Reputations* (Algorithmic Game Theory ch.)
- Douceur, J. (2002) *The Sybil Attack*
- 責任有效性分析 §3.B.4 (memory poisoning)
- vacant_current_understanding §3.5 (Registry 角色)
- BRIEFING.md v1 §3, §9, §11

---

## 6. 對其他 pane 的依賴與假設

| Pane | 我假設你會給 | 我提供你 |
|---|---|---|
| **P2 (identity)** | Capability Card 完整欄位 + attestation 結構 + cold start prior 公式 + whitewashing cost 公式 + revocation 觸發條件 | Schema 草案（vacant + attestation + revocation 三表）、lineage / sink_record 給你算 whitewashing cost 用、`base_model_family` 欄位給同源降權 |
| **P3 (reputation)** | 五維 snapshot 結構 + CI / n / diversity_index 計算 + 同源降權公式 + Goodhart graceful degradation 規則 | reputation_snapshot 表（含 CI、n、diversity、sample_status）；event_log 是 P3 聚合的事實來源；anomaly 規則的 rep_jump 閾值要與 P3 對齊 |
| **P6 (protocol)** | A2A envelope + Review envelope 完整 JSON schema | Registry RPC 端點清單（與 envelope 1:1）；read RPC 一律帶 inclusion/consistency proof 與簽章 |
| **P1 (runtime)** | Vacant Runtime 簽章機制 + idle-time peer review 觸發 + spawn 觸發 + self-eval 結構 | submit_event 接受 Runtime 簽章；finalization endpoint 給其他 vacant 對 event 做背書用 |
| **P5 (composite)** | 子代封閉原則的 schema 表達（子代不出現在 Registry，或出現但 visibility=internal） | 目前 schema 假設「對外 vacant 才登記」；如 P5 要存內部結構，需新增 internal_subgraph 表（待對齊） |

**未對齊假設**（會以本文為準直到 P2/P3/P6 推翻）：
- `vacant_id` 格式 = `multibase(multihash(Ed25519_pubkey))`
- 五維名稱 = factual / logical / relevance / honesty / adoption
- envelope 必含 idempotency_key（P6 預設這條）
- attestation kind 列舉 = developer / org / peer / dev_oracle / sigstore

---

## 7. 未解問題 / 留給後續

1. **N-of-M 的 N 預設值**：MVP 簡化為 N=2（任意 2 個獨立 vacant）；正式版本由 P3 + P2 共同定，依 reputation 加權的 N。
2. **anomaly 規則的閾值**：本文寫了 placeholder（rep_jump 0.4 / window 60s / spawn 10/h），要 P3 給統計依據。
3. **Registry operator 自身誠實度**：MVP 假設 operator 誠實；中期靠多 witness cosign；長期才能完全去信任。論文敘述要明說此 trust assumption 而非掩蓋。
4. **read_audit 是否預設開啟**：開啟可防 selective hide 但增 storage；建議 MVP 預設關閉，僅針對特定 query_kind（如 `query_capability`）開啟。
5. **隱私 / 商業敏感**：Registry 設計假設所有 events 公開；若客戶端有合規需求，需 P5 / P6 設計 zero-knowledge proof 變體（例如「reputation 在 X 之上」而不公開實際分數）。
6. **聯邦期 shard 同步策略**：用 push gossip 還是 pull / DHT，待 P2 + P6 決議。
7. **GitHub 政策風險**：GitHub 可封號或刪庫；正式版需多 mirror（GitLab + Codeberg + 自架），並把每日 root 推到 OpenTimestamps 作 fallback。
8. **schema migration**：欄位增刪必對應 event_type=`schema_migration` 的特殊 event 寫入鏈中，使歷史 schema 可被驗證。
