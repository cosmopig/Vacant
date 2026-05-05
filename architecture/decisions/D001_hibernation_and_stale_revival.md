# D001 — Hibernation 與 Stale 復活儀式

**日期：** 2026-05-01
**裁決者：** host (主持人)
**影響元件：** P1 Runtime / P3 Reputation / P4 Registry

---

## 背景

P1 提問「budget 耗盡是否算 sinking 訊號」。

## 裁決

### 1. Budget 耗盡 ≠ Sinking

Sinking 必須由 reputation/品質訊號驅動。否則「有錢攻擊者長久不沉、誠實窮 vacant 反而沉」，激勵錯誤。

### 2. 三狀態取代二狀態

| 狀態 | 觸發 | 是否可逆 | 是否進 default search |
|---|---|---|---|
| **Active** | 正常運行 | — | ✅ |
| **Hibernating** | budget 耗盡 / 開發者主動暫停 | ✅ 可恢復 | ❌（除非 stale=false 且通過 warmup）|
| **Stale** (= long hibernation ≥30d) | 連續 hibernation ≥30d | ✅ 可逆但需 warmup | ❌ |
| **Sunk** | reputation 失敗計數觸發 | ❌ 終態 | ❌ |

### 3. Stale 復活儀式（新增）

長期 hibernation 後私鑰可能遭竊（lost laptop / leaked secrets），驟然復活是經典 compromised account 模式。但太重會懲罰正當 hibernation（開發者放假、機器搬遷）。採輕量但帶安全網：

**Warmup window：** 復活後 24h，vacant 必須：
- 產生 **N=5 個有效 heartbeat**
- 每個 heartbeat 的 `behavioral_embedding` 落在歷史分布內（用 P3 的行為熵 / 跨維散度比對）

**Warmup 期間的可見性：**
- ✅ 可被直接 `vacant_call(by_id)` 呼叫（顯式查詢）
- ❌ 不進預設 `capability_search` 結果

**異常處置：**
- 任一 attestation 偏離歷史分布 → 標 `SECURITY_REVIEW`
- 不自動 sink（沉沒不可逆，需保留證據鏈）
- 凍結 default search 直到開發者重新 attestation（L1 簽章）

## 跨 pane 介面要求

| Pane | 必須提供 |
|---|---|
| P1 Runtime | hibernating / warming_up / active / sunk 狀態機；warming_up 期間每個 heartbeat 附 behavioral_embedding |
| P3 Reputation | 暴露 `behavioral_distribution_check(vacant_id, embedding)` API；當 stale=true 時聚合算法降權 |
| P4 Registry | 儲存 `state` enum + `warmup_counter` + `stale_since` + `security_review_flag`；`capability_search` 預設過濾 stale vacant |

## 為什麼這個設計能撐住

- 抗 Sybil 復辟（攻擊者偷私鑰換新身份做不到「歷史分布匹配」）
- 不傷害正當 hibernation（開發者只需保持 base model 一致就過得去）
- 留人類介入空間（SECURITY_REVIEW 不自動沉沒）
- 與 P3 的行為熵設計天然對接（P3 已為 Goodhart 設計過 behavioral_embedding）

## 已知限制 → 升級為 G07

P1 §7.8 誠實指出：**高階對手若能完美模仿 behavioral_embedding（例如取得整段歷史 corpus、用同型 base model 微調出仿冒體），warmup ceremony 會被繞過**。這超出 Runtime 範疇，必須由 hardware attestation（TEE / TPM remote attestation）或 stake-based identity 在 P2 Identity 層解決。

**升級為架構級開放議題 G07：高階模仿攻擊的 hardware attestation 邊界。**
