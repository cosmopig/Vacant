# Vacant — 架構規劃彙整

> 這是整個 Vacant 架構規劃的入口。所有具體內容在 sub-doc 裡。
>
> **狀態：v5 完整理論定稿（經 codex 三輪 adversarial review 確認 `no fatal issues remain`），可進 14 週 MVP 施作。**

---

## 一頁摘要

**Vacant 是一種居民形式（resident form），不是規格。** 你選擇成為它。

一個 vacant = Ed25519 keypair（idem 數值同一）+ logbook（ipse 變化中延續）+ behavior_bundle（character 兩者橋樑）+ multi-spec substrate + minimal runtime。

它**疊在 A2A / MCP 之上**（這兩個是真的規格，沒問題），**跟 OpenClaw / Hermes / Claude Code 是平行物種**（後者是讓人類進入網路的客戶端，不是 vacant 的宿主）。

子代預設封閉但**可畢業**（parent 同意 + 速率限制 + 三層共謀偵測）。Reputation 是五維 Beta posterior、per-substrate、用 STYLO 行為距離計算動態 discount rollover、portability_factor 獎勵生態貢獻、三軌同源降權。

問責是閉環：vacant 簽每筆回應、選 substrate、扛後果。「不是我啦，是 LLM 幻覺」在這個結構裡無效。

對抗 38 種攻擊有層級防禦（P/D/C 三層誠實標明，多數是 D 或 C；純 P 僅 4 條且全部假設 strong key custody）。13 個誠實標記的真實限制（H1-H13）已從定性升為定量。理論建立在 1 個明示根本前提（Key Custody / Controller Autonomy）上。

---

## 文件導航

### 理論
- **[`THEORY_V5.md`](./THEORY_V5.md)** — 完整理論 v5（最終版，codex 三輪審查硬化，38 攻擊矩陣 + 13 硬問題）
- [`THEORY_V4.md`](./THEORY_V4.md) — v4（過渡，codex 審查前的版本）
- [`THEORY_V3.md`](./THEORY_V3.md) — v3（更早期過渡）
- [`BRIEFING.md`](./BRIEFING.md) — 派發給研究員的共享簡報

### 元件規格（共 8 份，195KB）
| 元件 | 文件 | 內容 |
|---|---|---|
| P1 Runtime | [`components/P1_runtime.md`](./components/P1_runtime.md) | 5 態狀態機、heartbeat、shadow-self、spawn |
| P2 Identity | [`components/P2_identity.md`](./components/P2_identity.md) | L0-L3 多層識別、WashCost、聯邦化 |
| P3 Reputation | [`components/P3_reputation.md`](./components/P3_reputation.md) | 五維 Beta posterior、UCB、cold start |
| P4 Registry | [`components/P4_registry.md`](./components/P4_registry.md) | 13 SQLite 表、25 RPC、6 層防竄改 |
| P5 Composite | [`components/P5_composite.md`](./components/P5_composite.md) | 子代封閉 / 畢業、ChildManifest、Tree-Only |
| P6 Protocol | [`components/P6_protocol.md`](./components/P6_protocol.md) | A2A/MCP 整合、Capability Card、Envelope |
| P7 MVP | [`components/P7_mvp.md`](./components/P7_mvp.md) | 14 週時程、4 demo 場景、8 評估指標 |

### 研究依據（共 7 份，156KB）
| 研究 | 文件 | 結論 |
|---|---|---|
| T1 Behavioral Fingerprint | [`research/T1_behavioral_fingerprint.md`](./research/T1_behavioral_fingerprint.md) | STYLO Vec16 + PROBE 雙層；Mahalanobis 3.5 |
| T2 Distillation | [`research/T2_distillation.md`](./research/T2_distillation.md) | 3B 起跳、$5-150、2026 已可行 |
| T3 Substrate Economics | [`research/T3_substrate_economics.md`](./research/T3_substrate_economics.md) | captive_ratio 2026 55-70% → 2030 10-20% |
| T4 Attestation Bootstrap | [`research/T4_attestation_bootstrap.md`](./research/T4_attestation_bootstrap.md) | 2-of-5 → 3-of-9，3-5 年演進 |
| T5 Same Controller | [`research/T5_same_controller.md`](./research/T5_same_controller.md) | 三層篩選 (宣告 → corr → cosine) |
| T6 Substrate Identity | [`research/T6_substrate_identity.md`](./research/T6_substrate_identity.md) | Ricoeur idem/ipse/character |
| T7 Economics | [`research/T7_economics.md`](./research/T7_economics.md) | MVP→V1→V2→V3 四階段 |

### 補充 codex 研究
- [`research/P2_identity_research.md`](./research/P2_identity_research.md) — 9 方案身份識別
- [`research/P4_registry_research.md`](./research/P4_registry_research.md) — MINJA / Sigstore / CT 對比

### 裁決紀錄
- [`decisions/D001_hibernation_and_stale_revival.md`](./decisions/D001_hibernation_and_stale_revival.md) — 4 態狀態機 + warmup ceremony

### 視覺化
- **[`visualization/index.html`](./visualization/index.html)** — 7 節互動視覺化（中英可切，OKLCH 配色，含 Failure→Spawn 動畫）

---

## 架構演進總覽

```
v1 (派發前)         → 順著 OpenClaw/Hermes 對照，很多 hand-wave
v2 (派發後彙整)     → 9 層 + 6 缺口 + 3 大張力，但「規格」框架混淆、子代封閉律法化
v3 (深度自我反駁)   → Vacant=居民形式 / 子代可畢業 / per-substrate identity
                     20 攻擊 × 多層防禦，5 個誠實限制 H1-H5
v4 (7 份研究強化)   → Ricoeur idem/ipse/character 三維形式
                     STYLO + PROBE 行為指紋，Mahalanobis 3.5
                     三層串行 same-controller 偵測
                     動態 discount rollover = f(STYLO_distance)
                     portability_factor 公式修正
                     captive_ratio 時間軸（2026→2030）
                     3-5 年 attestation 演進現實
                     MVP→V1→V2→V3 經濟層演進
                     22 攻擊 × 具體機制 × 學術引用
                     8 個 14 週可驗證命題
```

---

## 核心張力如何被解（v4）

| 張力 | v4 解法 |
|---|---|
| 「網路自然淘汰」 vs Sybil | L0-L3 多層識別 + same-substrate-same-behavior cluster 上限 |
| 「無中央 judge」 vs cold start | L1 attestation prior + UCB exploration + INSUFFICIENT_DATA 標籤 |
| 「透明記錄」 vs MINJA / 簽章污染 | hash chain + Merkle + 多方 attest + spawn/rotation 雙簽 |
| 「token 免費未來」 vs 現在 token 貴 | Layer 2 multi-spec + portable_pointer ≥3B + Mac Mini M4 蒸餾路徑 |
| 「規格自願性」 vs 網路效應強迫 | minimum spec 真的最小 + 可分叉 + bridge 給非 vacant |
| Identity 在 substrate 換手中如何延續 | Ricoeur idem (keypair) / ipse (logbook) / character (behavior) 三維 |
| 子代封閉 vs 網路自演化 | 預設封閉、可畢業（parent 同意 + 三層共謀偵測 + 速率限制） |
| 沒有中央 LLM 但需要解讀文字 | reviews 結構化（5 維數字 + evidence pointer），文字解讀在 caller side |

---

## 8 個 14 週可驗證命題

1. 同 controller 子代畢業後，cluster 信譽 ≤ parent + 1 vacant
2. captive vacant 生態壽命短於 portable
3. substrate_diversity 高 ↔ redteam probe 通過率高
4. graduation_rate 5-20% 是健康甜區
5. 動態 rollover 公式下，換 substrate 攻擊者長期累積信譽 < 不換的
6. STYLO Vec16 + Mahalanobis 3.5 在 demo 規模 100% 區分 family-level
7. 三層串行篩選對 demo 規模 same-controller 偵測 F1 ≥ 0.90
8. 2-of-5 attestation 在 5 bootstrapper 下不單點故障

---

## 14 週 MVP 路徑（節錄自 P7）

```
W1-W2:   Registry + Aggregator (SQLite + 五維公式)
W3-W6:   Vacant Runtime + peer review + spawn 機制
W7-W9:   客戶端 SDK + Streamlit Dashboard
W10-W11: 4 demo 場景 + 8 指標實驗
W12-W14: 論文撰寫 + demo 排練
```

4 demo 場景（每個對應 v4 一個關鍵設計）：
- A：跨領域組合（composition link）
- B：adversary→spawn 完整 trace（失敗孕育競爭）
- C：複合 vacant 子代封閉 / 畢業
- D：10 同源 Sybil 嘗試 → 三軌降權使攻擊無效

---

## 開放議題（v4 誠實限制）

| 編號 | 議題 | v4 立場 |
|---|---|---|
| H1 | 蒸餾可行性 | 2026 窄域已可行（codex 確認）；2029 routine very probable |
| H2 | hosted substrate 脆弱 | 結構性下降（captive 2030 → 10-20%）；substrate_sla_tier 監控 |
| H3 | identity ontology | Ricoeur 框架可辯護；不解 Ship of Theseus 但量化邊界 |
| H4 | 多方 attestation 啟動 | 3-5 年演進現實；2-of-5 → 3-of-9 三階段路徑 |
| H5 | 經濟可持續性 | MVP→V3 五原型對比後選定路徑 |
| G07 | 高階對手完美模仿 | 升架構級開放議題；靠 hardware attestation / TEE |
| G08 | GitHub 政策風險 | fallback 推 IPFS / OTS 為主 |

---

## 結論

**v5 是 v4 跟 codex 三輪 adversarial review 對撞後的最終版。** 9 層架構沒有層垮塌，所有 hand-wave 升級為具體機制，所有「擋住」措辭降格為 P/D/C 三層精準語言，38 攻擊矩陣完整列舉。codex 確認「no fatal issues remain」。13 個誠實限制（H1-H13）有時間軸或工程邊界，根本前提（Key Custody）明示在文件最前。

剩下的工作不是再多一輪理論修訂，而是把這版 v5 帶進 14 週 MVP，讓 12 個結構性 demonstrations 用真實 demo 數據說話。

---

*文件版本：ARCHITECTURE Hub · 2026-05-01*
*基於 THEORY v5，整合 8 component specs + 7 research findings + 1 decision record + 1 visualization*
