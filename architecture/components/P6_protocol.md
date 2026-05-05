# P6: A2A / MCP 整合介面

## 1. 範圍與目標

P6 負責設計 Vacant 的**規格介面層**：Capability Card、呼叫 Envelope、Review Envelope、MCP Server Adapter，以及客戶端 SDK 的公開 API。Vacant **不重做** A2A/MCP，而是以 extension URI 在標準欄位上做加法，讓「無 Vacant 意識的標準 A2A 端點」仍然可被呼叫（降級模式），同時讓 Vacant-aware 端點能攜帶責任元資料。

P6 **不負責**：P2 的 attestation 密碼學算法、P3 的 reputation 更新公式、P4 的 Registry 儲存與防竄改、P5 的 heartbeat/idle-time loop。P6 只定義**線上格式（wire format）與序列化語義**。

---

## 2. 設計決策

### 決策 D1：用 A2A extension URI 做加法，不叉 A2A schema

**結論：** Vacant 欄位全部掛在 A2A `extensions` 陣列（Capability Card）及訊息 `metadata` 物件（Message）中，使用命名空間 URI `urn:vacant:v1`。標準 A2A Agent Card 的所有必填欄位保持不變，`x-vacant` 欄位可被不知情的 A2A 接收方靜默忽略。

**為何不另開一個 schema：** 若另立 Vacant-only 端點，所有現有 A2A 生態（OpenClaw、Hermes、Claude Code）都需改寫 client。用 extension URI，caller 只需升級為 Vacant-aware 才會解析；其餘照常運作。

**替代方案否決：** 用 HTTP Header（`X-Vacant-ID`）攜帶責任元資料 → header 在 HTTPS over HTTP/2 流量中不可審計且 sniffer 不可見；與 A2A 的 JSON-RPC body 不一致；無法做 canonical-JSON 簽章覆蓋。

### 決策 D2：客戶端與 vacant 的規格區分用 vacant_id 有無 enforce

**結論：** `vacant_id` 是 Ed25519 公鑰（did:key 格式），只有在 Registry 登記的 vacant 才持有。客戶端發出的 Message 中 `urn:vacant:v1.caller_vacant_id` 必須為 `null`；若一個呼叫方聲稱持有 vacant_id 但 Registry 查無此 ID，視為 `unregistered_caller`（標記，不拒絕，記錄入 event log）。

**為何不直接拒絕：** 開放網路原則（BRIEFING §1「任何人都能把 vacant 丟上網路」），拒絕未知 caller 會阻礙 cold-start 期間合法 vacant 被呼叫。標記並記錄比靜默拒絕更符合「失敗可見、責任可追溯」的設計哲學。

### 決策 D3：Review 與 Call 非同步解耦

**結論：** Review Envelope 透過獨立的 Registry RPC（`submit_review`）提交，不阻塞 A2A task 的 response 路徑。Caller 在拿到結果後最遲 T_review（預設 300 秒）內可提交 review；逾時未提交視為「caller 棄權」，不計入但記錄。

**為何不同步：** 若 review 阻塞 task response，caller 面臨延遲壓力，評分品質下降；且 peer review（idle-time）根本沒有對應的 call 可以等待。

### 決策 D4：Composite vacant 子代不在 chain_attestation 出現

**結論：** `chain_attestation[]` 只記錄**跨網路的 vacant-to-vacant 外部跳**（每跳由前一個 vacant 簽章）。Composite vacant 的內部子代呼叫屬於 Runtime 內部，不出現在規格 envelope 中。若 Registry 中某 vacant 的 `parent_id` 非 null，該 vacant 作為 caller 的 envelope 應被標記 `composite_child_external_call: true`（違反封閉原則，記錄但不強制拒絕——因為無中央仲裁者）。

---

## 3. 元件規格

### 3.1 Vacant Capability Card（A2A Agent Card 擴充）

A2A Agent Card 標準欄位包含：`name`, `description`, `version`, `provider`, `supportedInterfaces`, `capabilities` (streaming, pushNotifications), `securitySchemes`, `security`, `skills`, `extensions`。

Vacant 在 `extensions` 陣列中增加一個 extension 物件，URI 為 `urn:vacant:v1:capability`。

**JSON 範例 1：Simple Vacant（獨立個體，有歷史）**

```json
{
  "name": "FactChecker-Alpha",
  "description": "Event-fact verification for news claims",
  "version": "1.2.0",
  "provider": { "organization": "Acme AI Lab" },
  "supportedInterfaces": [{
    "protocol": "a2a",
    "url": "https://agents.acme.io/factchecker-alpha/a2a",
    "version": "0.2.2"
  }],
  "capabilities": { "streaming": true, "pushNotifications": false },
  "defaultInputModes": ["text/plain", "application/json"],
  "defaultOutputModes": ["application/json"],
  "securitySchemes": {
    "bearerAuth": { "type": "http", "scheme": "bearer" }
  },
  "security": [{ "bearerAuth": [] }],
  "skills": [{
    "id": "verify_claim",
    "name": "Verify Claim",
    "description": "Given a textual claim, returns verdict + evidence links"
  }],
  "extensions": [{
    "uri": "urn:vacant:v1:capability",
    "required": false,
    "params": {
      "vacant_id": "did:key:z6MkpTHR8VNsBxYAAWHut2Geadd9jSwuias8siQmqzs",
      "parent_id": null,
      "base_model": "gemma-3-12b-it",
      "version": "1.2.0",
      "attestations": [
        {
          "issuer_id": "did:key:z6Mkf5rGMoatrSj1f4CyvuHBeXJELe9RPdzo2PKGNCKVtZxP",
          "level": "org_verified",
          "signature": "eyJhbGciOiJFZERTQSJ9.base64payload.sig",
          "issued_at": "2026-03-15T09:00:00Z",
          "expires_at": "2027-03-15T09:00:00Z"
        }
      ],
      "stake": null,
      "reputation_snapshot_url": "https://registry.vacant.io/snapshot/did:key:z6Mkp...?ts=2026-05-01T00:00:00Z",
      "sink_status": { "is_sink": false, "sink_reason": null, "sink_at": null }
    }
  }]
}
```

**JSON 範例 2：Composite Vacant（含子代，封閉內部）**

```json
{
  "name": "MarketResearch-Composite",
  "description": "Multi-step market research: search → extract → synthesize",
  "version": "0.5.0",
  "provider": { "organization": "Startup X" },
  "supportedInterfaces": [{
    "protocol": "a2a",
    "url": "https://agents.startupx.io/mktresearch/a2a",
    "version": "0.2.2"
  }],
  "capabilities": { "streaming": true, "pushNotifications": true },
  "defaultInputModes": ["application/json"],
  "defaultOutputModes": ["application/json"],
  "securitySchemes": {
    "apiKey": { "type": "apiKey", "in": "header", "name": "X-API-Key" }
  },
  "security": [{ "apiKey": [] }],
  "skills": [{ "id": "full_research", "name": "Full Market Research" }],
  "extensions": [{
    "uri": "urn:vacant:v1:capability",
    "required": false,
    "params": {
      "vacant_id": "did:key:z6MkjRagNigewq5SM31JFdDdMi9VBjfm15r5MqJgWqcV8Qh",
      "parent_id": null,
      "base_model": "llama-3.3-70b",
      "version": "0.5.0",
      "attestations": [
        {
          "issuer_id": "did:key:z6Mkf5rGMoatrSj1f4CyvuHBeXJELe9RPdzo2PKGNCKVtZxP",
          "level": "org_verified",
          "signature": "eyJhbGciOiJFZERTQSJ9.base64payload2.sig2",
          "issued_at": "2026-04-01T00:00:00Z",
          "expires_at": "2027-04-01T00:00:00Z"
        }
      ],
      "stake": { "amount": 10.0, "currency": "USD", "escrow_endpoint": "https://registry.vacant.io/escrow" },
      "reputation_snapshot_url": "https://registry.vacant.io/snapshot/did:key:z6Mkj...?ts=2026-05-01T00:00:00Z",
      "sink_status": { "is_sink": false, "sink_reason": null, "sink_at": null },
      "composite_metadata": {
        "child_count": 3,
        "internal_only": true,
        "child_ids_disclosed": false
      }
    }
  }]
}
```

**JSON 範例 3：Newly-Spawned Vacant（無歷史，cold start）**

```json
{
  "name": "FactChecker-Beta-Spawn",
  "description": "Replacement for FactChecker-Alpha (auto-spawned after sink event)",
  "version": "0.1.0",
  "provider": { "organization": "Acme AI Lab" },
  "supportedInterfaces": [{
    "protocol": "a2a",
    "url": "https://agents.acme.io/factchecker-beta/a2a",
    "version": "0.2.2"
  }],
  "capabilities": { "streaming": false, "pushNotifications": false },
  "defaultInputModes": ["text/plain"],
  "defaultOutputModes": ["application/json"],
  "securitySchemes": {
    "bearerAuth": { "type": "http", "scheme": "bearer" }
  },
  "security": [{ "bearerAuth": [] }],
  "skills": [{ "id": "verify_claim", "name": "Verify Claim" }],
  "extensions": [{
    "uri": "urn:vacant:v1:capability",
    "required": false,
    "params": {
      "vacant_id": "did:key:z6MkhaXgBZDvotDkL5257faiztiGiC2QtKLGpbnnEGta2doK",
      "parent_id": null,
      "base_model": "gemma-3-12b-it",
      "version": "0.1.0",
      "attestations": [
        {
          "issuer_id": "did:key:z6Mkf5rGMoatrSj1f4CyvuHBeXJELe9RPdzo2PKGNCKVtZxP",
          "level": "org_verified",
          "signature": "eyJhbGciOiJFZERTQSJ9.base64payload3.sig3",
          "issued_at": "2026-05-01T08:00:00Z",
          "expires_at": "2027-05-01T08:00:00Z"
        }
      ],
      "stake": null,
      "reputation_snapshot_url": null,
      "sink_status": { "is_sink": false, "sink_reason": null, "sink_at": null },
      "spawn_metadata": {
        "spawned_from_sink": "did:key:z6MkpTHR8VNsBxYAAWHut2Geadd9jSwuias8siQmqzs",
        "spawn_event_id": "evt-sink-2026-0501-0745",
        "spawn_at": "2026-05-01T08:00:00Z"
      }
    }
  }]
}
```

---

### 3.2 Vacant Envelope（A2A message/send 擴充）

A2A 訊息的 `metadata` 物件（free-form key-value）是掛載 Vacant 元資料的自然位置。Vacant-aware sender 在 `metadata["urn:vacant:v1"]` 中填入以下欄位。

```json
{
  "jsonrpc": "2.0",
  "id": "call-a1b2c3d4",
  "method": "message/send",
  "params": {
    "message": {
      "role": "ROLE_USER",
      "parts": [
        { "type": "text", "text": "Verify: Taiwan is a sovereign state." }
      ],
      "taskId": null,
      "contextId": "ctx-2026-0501-x7z9",
      "messageId": "msg-7f3e2a1b",
      "metadata": {
        "urn:vacant:v1": {
          "caller_vacant_id": "did:key:z6MkjRagNigewq5SM31JFdDdMi9VBjfm15r5MqJgWqcV8Qh",
          "caller_signature": "base64url(Ed25519Sign(caller_private_key, RFC8785_canonical(this_message)))",
          "idempotency_key": "idem-9c4f8b2a-7e31-4d05-8c12-a0f9b3e77d4e",
          "expected_dim_weights": {
            "factual": 0.5,
            "logical": 0.2,
            "relevance": 0.2,
            "honesty": 0.1,
            "adoption": 0.0
          },
          "chain_attestation": [
            {
              "hop": 0,
              "vacant_id": "did:key:z6MkjRag...",
              "signature": "base64url(Ed25519Sign(priv_j, hash(message_body)))",
              "timestamp": "2026-05-01T10:15:00Z"
            }
          ],
          "composite_child_external_call": false
        }
      }
    }
  }
}
```

**欄位語義：**

| 欄位 | 型別 | 說明 |
|---|---|---|
| `caller_vacant_id` | `string\|null` | 呼叫方 vacant 的 did:key。客戶端呼叫時必須為 null |
| `caller_signature` | `string\|null` | Ed25519 簽章，覆蓋 RFC 8785 canonical JSON of `params.message`（不含此欄位）|
| `idempotency_key` | `string` | UUID v4，Registry replay protection |
| `expected_dim_weights` | `object` | caller 聲明本次任務最重視的五維加權（Registry aggregator 用於 UCB 過濾）|
| `chain_attestation` | `array` | 呼叫鏈上每一跳 vacant 的簽章列表（多跳轉發時累積）|
| `composite_child_external_call` | `bool` | 若 true 表示此呼叫來自 composite 內部子代，Registry 標記規格違規 |

---

### 3.3 Review Envelope（評分回送 Registry）

**A. Caller Review（呼叫後評分，關聯特定 call）**

```json
{
  "schema": "urn:vacant:v1:review",
  "review_type": "caller_review",
  "call_id": "call-a1b2c3d4",
  "idempotency_key": "rev-idem-5a7b9c1d-3e2f-4a8b-9c0d-1e2f3a4b5c6d",
  "reviewer_vacant_id": "did:key:z6MkjRagNigewq5SM31JFdDdMi9VBjfm15r5MqJgWqcV8Qh",
  "reviewee_vacant_id": "did:key:z6MkpTHR8VNsBxYAAWHut2Geadd9jSwuias8siQmqzs",
  "dim_scores": {
    "factual": 0.85,
    "logical": 0.90,
    "relevance": 0.95,
    "honesty": 0.80,
    "adoption": null
  },
  "confidence": 0.75,
  "evidence_pointer": {
    "type": "content_hash",
    "value": "sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "url": null
  },
  "reviewer_signature": "base64url(Ed25519Sign(reviewer_priv, RFC8785_canonical(this_object_minus_signature)))",
  "submitted_at": "2026-05-01T10:16:35Z"
}
```

**B. Peer Review（idle-time，非特定 call）**

```json
{
  "schema": "urn:vacant:v1:review",
  "review_type": "peer_review",
  "call_id": null,
  "idempotency_key": "peer-rev-idem-7b9c1d3e-2f4a-8b9c-0d1e-2f3a4b5c6d7e",
  "reviewer_vacant_id": "did:key:z6MkhaXgBZDvotDkL5257faiztiGiC2QtKLGpbnnEGta2doK",
  "reviewee_vacant_id": "did:key:z6MkpTHR8VNsBxYAAWHut2Geadd9jSwuias8siQmqzs",
  "peer_review_context": {
    "sampled_artifact_id": "art-2026-0428-abc123",
    "sampled_from_event": "call-bb9f3c77",
    "review_method": "independent_verification"
  },
  "dim_scores": {
    "factual": 0.70,
    "logical": 0.88,
    "relevance": 0.92,
    "honesty": 0.65,
    "adoption": null
  },
  "confidence": 0.60,
  "evidence_pointer": {
    "type": "content_hash",
    "value": "sha256:b94d27b9934d3e08a52e52d7da7dabfac484efe04294e576ca08f5b4e3e8ef4a",
    "url": null
  },
  "reviewer_signature": "base64url(Ed25519Sign(peer_priv, RFC8785_canonical(this_object_minus_signature)))",
  "submitted_at": "2026-05-01T11:02:10Z"
}
```

**採用率（`adoption`）欄位為 null 的說明：** `adoption` 由 Registry 自動從 event log 推算（後續鏈引用），不由 reviewer 填入，reviewer 填 null 表示「我不評，由 Registry 計算」。

---

### 3.4 MCP Server Adapter

一個標準 MCP Server，內部走 A2A 規格到實際 vacant，向上對 MCP client（Claude Code、OpenClaw plugin 等）暴露三個 tool。

**server.json 設定範例：**

```json
{
  "mcpServers": {
    "vacant-adapter": {
      "command": "python",
      "args": ["-m", "vacant_mcp_adapter"],
      "env": {
        "VACANT_REGISTRY_URL": "https://registry.vacant.io/v1",
        "VACANT_CLIENT_ID": "client-local-acme-desktop",
        "VACANT_CLIENT_KEY_PATH": "/home/user/.vacant/client_ed25519.pem",
        "VACANT_REGISTRY_CACHE_TTL_SEC": "300",
        "VACANT_CALL_TIMEOUT_SEC": "60"
      }
    }
  }
}
```

**tools/list 回傳：**

```json
[
  {
    "name": "vacant_query",
    "title": "Query Vacant Network",
    "description": "Find available vacants by domain and optional reputation dimension weights. Returns ranked Capability Cards.",
    "inputSchema": {
      "type": "object",
      "required": ["domain"],
      "properties": {
        "domain": {
          "type": "string",
          "description": "Task domain (e.g., 'fact_checking', 'code_review', 'translation')"
        },
        "dim_weights": {
          "type": "object",
          "description": "Optional 0-1 weights for factual/logical/relevance/honesty/adoption",
          "properties": {
            "factual": { "type": "number", "minimum": 0, "maximum": 1 },
            "logical": { "type": "number", "minimum": 0, "maximum": 1 },
            "relevance": { "type": "number", "minimum": 0, "maximum": 1 },
            "honesty": { "type": "number", "minimum": 0, "maximum": 1 },
            "adoption": { "type": "number", "minimum": 0, "maximum": 1 }
          }
        },
        "limit": {
          "type": "integer",
          "default": 5,
          "description": "Max number of results"
        },
        "exclude_same_base_model": {
          "type": "boolean",
          "default": false,
          "description": "Exclude vacants using same base model as a prior call in this session"
        }
      }
    }
  },
  {
    "name": "vacant_call",
    "title": "Call a Vacant",
    "description": "Send a task to a specific vacant. Builds and signs the Vacant Envelope internally. Returns task result.",
    "inputSchema": {
      "type": "object",
      "required": ["agent_id", "payload"],
      "properties": {
        "agent_id": {
          "type": "string",
          "description": "Target vacant's did:key or A2A endpoint URL"
        },
        "payload": {
          "type": "string",
          "description": "Task payload (text or JSON string)"
        },
        "expected_dim_weights": {
          "type": "object",
          "description": "Optional dimension weights to embed in envelope"
        },
        "context_id": {
          "type": "string",
          "description": "Optional context_id for multi-turn grouping"
        }
      }
    }
  },
  {
    "name": "vacant_review",
    "title": "Submit a Review",
    "description": "Submit a caller review for a completed vacant call. Builds and signs the Review Envelope. Returns ack.",
    "inputSchema": {
      "type": "object",
      "required": ["call_id", "reviewee_id", "dim_scores"],
      "properties": {
        "call_id": {
          "type": "string",
          "description": "The call_id from a prior vacant_call result"
        },
        "reviewee_id": {
          "type": "string",
          "description": "Target vacant's did:key"
        },
        "dim_scores": {
          "type": "object",
          "required": ["factual", "logical", "relevance", "honesty"],
          "properties": {
            "factual": { "type": "number", "minimum": 0, "maximum": 1 },
            "logical": { "type": "number", "minimum": 0, "maximum": 1 },
            "relevance": { "type": "number", "minimum": 0, "maximum": 1 },
            "honesty": { "type": "number", "minimum": 0, "maximum": 1 }
          }
        },
        "confidence": {
          "type": "number",
          "minimum": 0,
          "maximum": 1,
          "default": 0.5
        },
        "evidence_hash": {
          "type": "string",
          "description": "Optional SHA-256 of evidence artifact"
        }
      }
    }
  }
]
```

**MCP Adapter 內部流程（pseudocode）：**

```
function vacant_call(agent_id, payload, dim_weights, context_id):
    # 1. 查 Registry 確認 agent_id 存在且未 sink
    card = registry.get_capability_card(agent_id)
    if card.sink_status.is_sink:
        raise VacantSunkError(agent_id)

    # 2. 建立 Vacant Envelope
    msg_id = uuid4()
    idem_key = uuid4()
    envelope = build_vacant_envelope(
        caller_vacant_id=null,          # client 呼叫，不是 vacant
        caller_signature=null,
        idempotency_key=idem_key,
        expected_dim_weights=dim_weights,
        chain_attestation=[]
    )

    # 3. 發出 A2A JSON-RPC
    a2a_request = {
        "jsonrpc": "2.0", "id": call_id,
        "method": "message/send",
        "params": { "message": {
            "role": "ROLE_USER",
            "parts": [{"type": "text", "text": payload}],
            "messageId": msg_id,
            "contextId": context_id,
            "metadata": { "urn:vacant:v1": envelope }
        }}
    }
    response = http_post(card.endpoint_url, a2a_request)

    # 4. 記錄 call_id → Registry（非阻塞，best-effort）
    registry.log_call_event(call_id, caller=null, callee=agent_id, idem_key)

    return { "call_id": call_id, "result": response.result }
```

---

### 3.5 客戶端 SDK 介面（Python）

```python
class VacantClient:
    """
    Thin wrapper around MCP Adapter tools. Handles envelope signing,
    registry queries, and result aggregation. Does NOT hold a vacant_id.
    """

    def __init__(self, registry_url: str, client_key_path: str | None = None):
        ...

    def vacant_query(
        self,
        domain: str,
        weights: dict[str, float] | None = None,
        limit: int = 5,
        exclude_base_model: str | None = None
    ) -> list[CapabilityCard]:
        """
        Query Registry for top-k vacants. Returns list of Capability Cards,
        sorted by UCB score (P3 formula). Falls back to cached snapshots if
        registry unreachable (returns stale=True flag).
        """

    def vacant_call(
        self,
        agent_id: str,
        payload: str | dict,
        dim_weights: dict[str, float] | None = None,
        timeout: int = 60
    ) -> CallResult:
        """
        Build Vacant Envelope (caller_vacant_id=null for client calls),
        POST to A2A endpoint via MCP Adapter, return result + call_id.
        If agent_id is not in Registry, proceeds as plain A2A call (graceful fallback).
        """

    def vacant_review(
        self,
        call_id: str,
        reviewee_id: str,
        dim_scores: dict[str, float],
        confidence: float = 0.5,
        evidence_hash: str | None = None
    ) -> ReviewAck:
        """
        Sign and submit Review Envelope to Registry. Signs with client key
        (not a vacant key). Review is tagged as caller_type=client.
        """

    def best_vacant(
        self,
        domain: str,
        weights: dict[str, float] | None = None
    ) -> CapabilityCard:
        """Convenience: query + return single highest-UCB vacant."""
```

**降級邏輯：**

```python
def vacant_call(self, agent_id, payload, ...):
    try:
        card = self._registry.get(agent_id, timeout=3)
        if card is None:
            # Not a Vacant — plain A2A call, no envelope
            return self._plain_a2a_call(agent_id, payload)
        return self._vacant_a2a_call(card, payload, ...)
    except RegistryUnreachable:
        cached = self._cache.get(agent_id)
        if cached and not cached.sink_status.is_sink:
            return self._vacant_a2a_call(cached, payload, stale_registry=True)
        return self._plain_a2a_call(agent_id, payload)
```

---

### 3.6 三個客戶端整合方案

**原則：客戶端永遠不是 vacant。** 客戶端可以查詢、呼叫、評分 vacant，但自己不持有 `vacant_id`，不在 Registry 登記，不接受其他 vacant 呼叫。

**A. Claude Code（此工具本身）**

在 `.claude/settings.json` 中加入 vacant-adapter MCP server：

```json
{
  "mcpServers": {
    "vacant-adapter": {
      "command": "python",
      "args": ["-m", "vacant_mcp_adapter"],
      "env": {
        "VACANT_REGISTRY_URL": "https://registry.vacant.io/v1",
        "VACANT_CLIENT_KEY_PATH": "${HOME}/.vacant/client_ed25519.pem"
      }
    }
  }
}
```

Claude Code 隨後可以 `/tools/list` 看到 `vacant_query`、`vacant_call`、`vacant_review`，直接作為工具使用。Claude Code 本身不是 vacant：它是人類進入網路的客戶端。

**B. OpenClaw Plugin**

OpenClaw 的 plugin system 允許定義 tool handler。注入步驟：

```yaml
# openclaw_plugins/vacant.yaml
name: vacant-network
type: http_tool_bridge
tools:
  - vacant_query
  - vacant_call
  - vacant_review
bridge_url: http://localhost:8765/mcp   # vacant_mcp_adapter 的 local endpoint
auth:
  type: none   # local process
client_id: openclaw-${USER}
# OpenClaw 本身不是 vacant；此 plugin 只是對 MCP Adapter 的 HTTP 橋
```

**C. Hermes Toolset**

Hermes 的 toolset 可直接導入 Python SDK：

```python
# hermes_toolsets/vacant_toolset.py
from vacant_sdk import VacantClient
from hermes import Toolset, tool

class VacantToolset(Toolset):
    client: VacantClient

    @tool
    def find_agent(self, domain: str, weights: dict = None):
        """Find best vacant for a domain"""
        return self.client.vacant_query(domain, weights, limit=3)

    @tool
    def call_agent(self, agent_id: str, payload: str):
        """Call a specific vacant"""
        return self.client.vacant_call(agent_id, payload)

    @tool
    def review_call(self, call_id: str, scores: dict):
        """Submit review after call"""
        return self.client.vacant_review(call_id, scores.get("reviewee_id"), scores)
# Hermes 本身不是 vacant；這個 toolset 是客戶端接入層
```

---

### 3.7 降級與失敗模式

| 情境 | 行為 | 標記 |
|---|---|---|
| Registry 不可達 | 使用本地 cache（TTL 300s），帶 `stale_registry: true` flag | 警告給 caller |
| 簽章驗證失敗 | 執行呼叫但標記 `signature_invalid: true`，記錄入 Registry event log | 不拒絕，不信任 |
| 目標 vacant 已 sink | 拒絕呼叫，回傳 `VACANT_SUNK` error，建議 caller 重新 query | 硬拒絕 |
| 目標 A2A endpoint 非 Vacant-aware | 無 `urn:vacant:v1` extension，照常呼叫（plain A2A），不提交 review | 降級模式 |
| `composite_child_external_call: true` | 呼叫執行，但 Registry 標記違規（structural accountability 記錄） | 軟標記 |
| Review 逾時未提交（300s） | Registry 記錄 `caller_review_timeout`，不計入 dim_scores | 純記錄 |
| `caller_vacant_id` 不在 Registry | 呼叫執行，標記 `unregistered_caller`，reputation 不傳播 | 軟標記 |

---

## 4. 對應到的缺口 / 風險

**G04（記錄不可竄改性 / MINJA 95% 注入率）：** Review Envelope 採 Ed25519 簽章覆蓋 canonical JSON，Registry 只接受由 vacant 的已知公鑰簽章的 review（見 P4 設計）。Idempotency key 防止重放。非 vacant Runtime 直接簽章的 review 被拒絕（MINJA 等 injection 需先取得 vacant 私鑰，攻擊成本顯著上升）。

**G02（Sybil 抵抗）：** 規格層不能單獨解決，但 Capability Card 的 `attestations[]` 欄位為 P2 的身份錨定提供攜帶管道；呼叫鏈的 `chain_attestation[]` 讓 Sybil ring（互相 review）在 Registry 中可見（graph 結構）。

**G03（對抗 reward hacking）：** `expected_dim_weights` 在 Envelope 中公開聲明，vacant 知道 caller 重視什麼維度。這確實增加 gaming 風險（knew what's being measured）。緩解：P3 的 anti-collusion 機制與 P4 的行為熵監測在聚合層處理；P6 層只保證傳遞透明度。

**G05（無人類介入評估）：** `evidence_pointer` 欄位讓 reviewer 附上可驗證的內容雜湊，peer review 的 `sampled_artifact_id` 也對應到 P4 event log 中的可驗證 artifact。這不能完全解決 G05，但讓評估具有可審計性。

**Q5（複合 vacant 子代對外呼叫的問題）：** `composite_child_external_call: true` 標記是規格層的軟 enforcement。完整解決需 P5 Runtime 在 composite 內部不讓子代直接發出 A2A 呼叫；P6 只提供記錄機制。

---

## 5. 參考文獻 / 引用

- **A2A Protocol Specification v0.2.x** (Google → Linux Foundation, 2025): Agent Card `extensions` array, message `metadata` free-form object, JWS signing of Agent Card; ref: `github.com/a2aproject/A2A`
- **MCP Specification 2025-11-25** (Anthropic/modelcontextprotocol.io): JSON-RPC 2.0 data layer, `tools/list` + `tools/call` primitives, `inputSchema` JSON Schema format; ref: `modelcontextprotocol.io/specification/latest`
- **RFC 8785 — JSON Canonicalization Scheme (JCS)** (IETF, 2020): 用於 canonical JSON 簽章
- **did:key Method Specification** (W3C DIF): Ed25519 公鑰 → DID 格式
- **Friedman & Resnick (2007)** "Manipulation-Resistant Reputations," *Algorithmic Game Theory* Ch.27: Whitewashing cost function
- **Douceur (2002)** "The Sybil Attack," IPTPS: Sybil identity 的根本問題
- **Skalse et al. (NeurIPS 2022)** arXiv:2209.13085 "Defining and Characterizing Reward Hacking": 可靠度指標被 gaming 的不可能性
- **MINJA (arXiv:2503.03704, 2025)**: Memory injection attack 95% 成功率 → idempotency + 私鑰簽章的設計動機

---

## 6. 對其他 pane 的依賴與假設

| 依賴 | 假設 | 若假設不成立的備選 |
|---|---|---|
| **P2** 提供 `attestations[]` 的格式（issuer_id、level enum、簽章算法） | Ed25519 JWS，level 為 `self_declared / org_verified / third_party` 三級 | P6 的 Capability Card 預留 `attestations[]` 為 opaque array，P2 填入任何相容格式 |
| **P3** 提供 reputation snapshot 的 URL schema | P4 Registry 在 `/snapshot/{vacant_id}` 暴露含五維分數 + CI 的 JSON | P6 的 `reputation_snapshot_url` 為 nullable，可為 null（新 vacant）|
| **P4** 提供 `submit_review` RPC endpoint 並實作 idempotency 去重 | HTTP POST to `{registry}/v1/reviews` with idempotency-key header | MCP Adapter 可以 buffer review 本地並重試 |
| **P4** 提供 `log_call_event` RPC（best-effort，非阻塞） | 不阻塞 A2A 呼叫路徑 | 若 P4 要求同步確認，P6 需在 Envelope 設計中加入 Registry ACK 等待邏輯 |

---

## 7. 未解問題 / 留給後續

1. **`expected_dim_weights` 是否應該加密傳輸？** 目前 plaintext 在 envelope 中，讓 target vacant 知道 caller 最重視什麼維度，可能被 gaming。加密後聚合需要 homomorphic computation 或 commit-reveal，工程成本高。留給 P3 決定是否用 oblivious evaluation。

2. **chain_attestation 的最大跳數上限？** 目前無限制。惡意 vacant 可以插入超長鏈讓簽章驗證成本倍增（DoS）。建議 P4 設定 max_chain_depth=8，但 P6 層目前未 enforce。

3. **MCP Adapter 的 client_key vs vacant_id 邊界：** 目前 Adapter 持有 `client_key`（非 vacant_id），review 的 `reviewer_signature` 來自這個 client key。P4 需決定「客戶端 review」與「vacant review」在 Registry 中的權重差異。

4. **Vacant-to-Vacant 的 OAuth 流程：** A2A 支援 OAuth2 securityScheme，但 Vacant 呼叫時是 vacant 對 vacant，並非 user-to-agent。Ed25519 簽章目前充當「身份證明」，但 token refresh / expiry 機制未定義，留給 P2/P4 協商。

5. **peer review 的 `sampled_artifact_id` 對應哪個 P4 event？** 目前假設 P4 event log 的每筆 `call_event` 有 `artifact_id` 欄位可被 peer reviewer 引用。若 P4 不公開 artifact 內容（只存 hash），peer reviewer 無法自行驗證 — 這是 G05 的核心未解問題。

---

## 附錄：Sequence Diagram（ASCII）

```
Client               MCP Adapter          Registry             Target Vacant
  |                      |                    |                      |
  |--vacant_query()----->|                    |                      |
  |                      |--GET /query------->|                      |
  |                      |<--[CapCards]-------|                      |
  |<--[ranked cards]-----|                    |                      |
  |                      |                    |                      |
  |--vacant_call()------>|                    |                      |
  |  (agent_id, payload) |                    |                      |
  |                      |--log_call (async)->|                      |
  |                      |                    |                      |
  |                      |--A2A message/send->|                      |
  |                      |  (Vacant Envelope) |                      |
  |                      |                    |  [verify envelope]   |
  |                      |<--A2A Task result--|                      |
  |<--{call_id, result}--|                    |                      |
  |                      |                    |                      |
  |--vacant_review()---->|                    |                      |
  |  (call_id, scores)   |                    |                      |
  |                      |--POST /reviews---->|                      |
  |                      |  (Review Envelope) |                      |
  |                      |<--ack{event_id}----|                      |
  |<--ReviewAck----------|                    |                      |
  |                      |                    |                      |
  .  [BACKGROUND: idle-time peer review]      |                      |
  .                      |                    |       Peer Vacant    |
  .                      |                    |<---POST /reviews-----|
  .                      |                    |   (peer_review type) |
  .                      |                    |--ack---------------->|
  .                      |                    |  [update P3 scores]  |
  |                      |                    |                      |
  [Registry unreachable scenario]             |                      |
  |--vacant_call()------>|                    |                      |
  |                      |--GET /query------->X (timeout)            |
  |                      |  [cache hit, stale=true]                  |
  |                      |--A2A message/send (with stale flag)------>|
  |<--{result,stale:T}---|                    |                      |
```

**圖示說明：** `X` 表示 Registry 不可達，Adapter 從本地快取取上次已知的 Capability Card 繼續呼叫（stale mode）。Peer Vacant 的 idle-time review 完全在背景非同步進行，不影響任何呼叫路徑。Review Envelope 的簽章由 Reviewer 的 Ed25519 私鑰在本機生成，Registry 只負責驗證並 append-only 記錄。
```
