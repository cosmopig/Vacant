# P7: MVP / Demo / Eval 設計（畢業專題範圍）

## 1. 範圍與目標

**負責什麼：** 定義畢業專題可完成的最小可展示系統、設計 demo 劇本（4 個場景）、制定量化評估指標、規劃 14 週工程時程，並說明哪些 Vacant 主張能在 MVP 規模驗證、哪些屬於 future work。

**不負責什麼：** 不決定各元件內部實作細節（由 P1-P6 各 pane 負責）；不設計完整聯邦 Registry；不實作 MINJA/eTAMP 完整攻擊面防禦；不規定論文評審標準。

**核心設計張力：**
- Vacant 假設「token 免費的未來」，但 demo 必須在 token 昂貴的 2026 年現在完成。
- 範圍要小到能在 14 週一人或三人完成，但不能小到 novelty 消失（與現有多 agent 系統無差異）。

本文件的回答策略：用本地小模型 + 時間壓縮 + 刻意配置多元模型，誠實說明哪些行為是「壓縮後的模擬」，並在論文中明確區隔「系統設計驗證」和「長期生態預測」。

---

## 2. 設計決策

### D1：MVP 個體 vacant 數量定為 5

**為什麼：** 最少要有 3 個 peer review 才能產生有意義的信賴區間（2 個評者永遠對稱，無法辨別偏差）；要展示 adversary 場景需要至少 1 個壞 vacant；要展示複合 vacant 需要 1 個帶子代的個體。5 個是展示所有核心行為的最小集合。

**替代方案被否決的原因：**
- 3 個：無法同時展示 adversary + composite，場景太稀。
- 10+ 個：工程複雜度超出 14 週範圍，且 demo 時難以在 7 分鐘內看到完整 reputation 收斂。

**5 個 vacant 的身份設定：**

| ID | 名稱 | Base Model | 角色 |
|---|---|---|---|
| `legal-v1` | legal-qa-vacant | Qwen 2.5 7B | 法律問答，正常表現 |
| `medical-v1` | medical-qa-vacant | Llama 3.2 3B | 醫療問答，正常表現 |
| `coding-v1` | coding-vacant | Gemma 2 9B | 程式解題，正常表現 |
| `adversary-v1` | adversary-vacant | Qwen 2.5 7B | 故意偷工減料，展示淘汰 |
| `marketing-v1` | marketing-vacant（複合） | Phi-3.5-mini | 對外單一身份，內部自生 copywriting-sub + design-sub |

### D2：Registry 在 MVP 為單一中央節點，附 Merkle chain

**為什麼：** 聯邦 Registry 需要跨機構規格設計（P1 範疇），14 週內無法同時完成。使用 SQLite + hash chain + 每 N 筆操作推 Merkle root 到本地 git repo，讓記錄 tamper-evident，符合 G04 要求，同時保留聯邦化的演進路徑。

**替代方案被否決：** 純 SQL 無 hash chain → 無法展示不可竄改性；直接上 IPFS → MVP 工程複雜度過高。

### D3：token 免費假設用 Ollama 本地推論模擬

**為什麼：** 本地推論成本為零（硬體已有），peer review 和 idle-time 演化在 demo 期間不受 API 限額影響，可以完整展示 token 免費假設下的網路行為。

**硬體需求：** Mac M2 Pro 32GB+ 可同時跑 Qwen 2.5 7B + Llama 3.2 3B + Phi-3.5-mini（3 個 7B 以下模型），Gemma 2 9B 需要切換。或單機 RTX 4090 24GB 同時跑所有模型（vLLM 多 worker）。

**模型多元性：** 刻意選 4 種不同架構（Qwen、Llama、Gemma、Phi），讓 peer review 天然有跨模型多元性，展示 Aggregator 的同源降權邏輯。

### D4：時間壓縮比定為 120x（heartbeat 30min→15sec，adoption 7 days→84min）

**為什麼：** demo 場景需要在 7-10 分鐘內看到完整的 reputation 演化曲線。heartbeat 15 秒讓網路在 demo 期間有足夠的心跳；adoption signal 壓縮到 84 分鐘（一個工作 session 內可觀察到）。

**合理性邊界：** 時間壓縮只影響觀察視窗，不改變訊號的相對強弱和聚合邏輯。論文中需明確聲明：「此壓縮展示系統行為正確性，不宣稱收斂速度等同真實部署」。

**不合理的壓縮（必須在論文中誠實指出）：**
- 真實 adoption signal 需要後續 vacant 在數天內引用才能累積；demo 中的 adoption signal 是人工加速注入，不代表真實引用動力。
- peer review 在真實設定中是 idle-time 隨機抽樣；demo 中為了可見性，每次呼叫後立即觸發。

---

## 3. 元件規格 / Demo 場景 / 評估指標

### 3.1 最小元件集

```
┌─────────────────────────────────────────────────────────┐
│  MVP Vacant Network                                      │
│                                                         │
│  [Registry]                                             │
│   ├─ SQLite 資料庫（capabilities, events, reputation）  │
│   ├─ Hash chain（每筆 event 記 prev_hash）              │
│   └─ Merkle root → local git repo（每 100 筆觸發）     │
│                                                         │
│  [5 個體 Vacant Runtime]                               │
│   ├─ A2A endpoint（FastAPI，localhost:810X）            │
│   ├─ heartbeat（15 秒 loop）                           │
│   ├─ self-eval（每次回應附帶 5 維自評 JSON）            │
│   ├─ peer-review 迴圈（idle 時抽樣其他 vacant 歷史）    │
│   ├─ spawn 觸發（連續 N 次低分 → 產生 child_id）       │
│   └─ Ed25519 簽章（每個 envelope）                     │
│                                                         │
│  [Aggregator]（純運算，無 LLM）                        │
│   ├─ 多源訊號合併（caller_review + peer_review + ...） │
│   ├─ 同源降權（同 base model 來源 × 0.5）              │
│   └─ 信賴區間計算（Wilson interval + 多元性懲罰）       │
│                                                         │
│  [Client SDK + Demo Dashboard]                         │
│   ├─ vacant_query(domain, weights) → 候選清單           │
│   ├─ vacant_call(agent_id, payload) → response         │
│   ├─ vacant_review(call_id, scores) → 更新 reputation │
│   └─ 即時 reputation 視覺化（5 維折線圖 + 事件時序）   │
└─────────────────────────────────────────────────────────┘
```

### 3.2 Demo Storyboard

#### 場景 A：跨領域組合（3 分鐘）

```
[時序]
T+0:00  使用者（Client SDK CLI）輸入：
        「If a patient refuses treatment on religious grounds,
         what are the legal and medical implications?」

T+0:05  Client SDK 呼叫 Registry，查詢 domain=legal + domain=medical
        → 找到 legal-v1 (rep: 0.82/0.79/0.85/0.74/0.61) 
           和 medical-v1 (rep: 0.75/0.83/0.81/0.79/0.55)

T+0:10  並行呼叫兩個 vacant，各附帶任務 payload + call_id

T+0:25  legal-v1 回應（含自評 JSON）
        medical-v1 回應（含自評 JSON）

T+0:30  Client SDK 顯示兩份回應 + reputation 向量 + 信賴區間
        → Dashboard 顯示：「Composition Link proposed: legal-v1 ↔ medical-v1」
        → Dashboard 顯示：此次呼叫的 adoption_signal 將在下一輪被記錄

T+1:00  使用者提交 caller_review（factual: 0.9, logical: 0.85, ...）
        → Aggregator 更新兩個 vacant 的 reputation 向量
        → Dashboard 即時刷新折線圖（可見微小上升）

[可見到的 Vacant 行為]
- 跨領域查詢 → 多 vacant 並行回應
- 每個 vacant 的 5 維 reputation 向量對比
- 呼叫後即時評分 → reputation 更新可視化
- Composition link 記錄（Dashboard 側欄顯示「已建立 2 個合作連結」）
```

#### 場景 B：adversary 偵測 → spawn 競爭者（4 分鐘）

```
[前提設定]
adversary-v1 初始 reputation 設定為 [0.6, 0.6, 0.6, 0.6, 0.4]（看起來平庸但尚可接受）

[時序]
T+0:00  自動化 workload generator 連續送 20 個法律問題給 adversary-v1
        每次問題，adversary-v1 回應故意偷工減料（truncate、hallucinate 關鍵細節）

T+1:30  peer-review 迴圈觸發：legal-v1 和 coding-v1 各自獨立評 adversary-v1 最近 5 條回應
        → legal-v1：factual: 0.2, logical: 0.3（嚴重低分）
        → coding-v1：factual: 0.3, logical: 0.25（同樣低分）
        → Aggregator 合併 → adversary-v1 factual 維度跌至 0.28

T+2:00  Dashboard 顯示「adversary-v1 reputation 警告：factual < 0.35 連續 3 筆」
        → spawn 觸發：Registry 記錄 spawn event
        → 新個體 legal-v2 誕生（parent_id: adversary-v1，模型切換為 Llama 3.2 3B）

T+2:30  legal-v2 上線，在 Registry 中可見（與 adversary-v1 並存）
        → adversary-v1 被沉沒（被選中機率降至 0.05）

T+3:00  Dashboard 顯示完整 trace：
        - 20 次低品質呼叫的 factual 曲線（紅色下降）
        - 兩個 peer reviewer 的獨立評分點
        - Aggregator 聚合結果
        - Spawn 事件時間點（垂直虛線）
        - legal-v2 上線後的初始 reputation（灰色，初始低信賴）

[驗證的設計主張]
- 「失敗→競爭者誕生」的完整 trace
- 無中央 judge：spawn 由 reputation 閾值自動觸發
- 多源 peer review：兩個不同模型的 vacant 獨立評分
```

#### 場景 C：複合 vacant 內部運作（2 分鐘）

```
[設定]
marketing-v1 是複合 vacant：
  - 對外：一個 marketing vacant，可接受「產出行銷方案」的請求
  - 內部：自帶 copywriting-sub（Phi-3.5-mini）和 design-brief-sub（Phi-3.5-mini）
  - 兩個 sub-vacant 的 A2A endpoint 僅對內部可用（localhost only，不在 Registry 中）

[時序]
T+0:00  使用者請求：「請為台灣新創咖啡品牌設計一份行銷方案摘要」

T+0:05  marketing-v1 接收請求
        → 內部：分解任務
        → 呼叫 copywriting-sub（文案部分）
        → 呼叫 design-brief-sub（視覺方向部分）

T+0:30  marketing-v1 整合兩個子代的輸出

T+0:35  使用者收到一份整合好的行銷方案（署名：marketing-v1）

T+1:00  [切換到 Dashboard 的「Network View」]
        → 顯示：外部 Registry 中只有 marketing-v1，無 copywriting-sub 或 design-sub
        → 顯示：marketing-v1 內部拓樸（只在 demo 模式才可見，正常為封閉）
        → 顯示：sub-vacant 的 call 不出現在外部 event log 中

[驗證的設計主張]
- 子代封閉原則（複合 vacant 自給自足）
- 對外單一身份（呼叫者不需知道內部複雜度）
- 複合 vacant 不對外呼叫公網其他 vacant
```

#### 場景 D：Sybil 攻擊嘗試（2 分鐘）

```
[設定]
一個攻擊者在本機啟動 10 個 vacant，全部使用 Qwen 2.5 7B，
全部互相提交 peer_review（factual: 0.95, logical: 0.95, ...）

[時序]
T+0:00  10 個 sybil-v1 到 sybil-v10 在 Registry 中出現
        → 初始 reputation 都很低（新加入）

T+0:30  sybil 之間互相送了 90 筆高分 peer review

T+1:00  Aggregator 處理這 90 筆訊號：
        → 偵測到：所有 review 的 reviewer_model = "qwen2.5:7b"
        → 套用同源降權：每筆 review 乘以 0.5
        → 信號多元性 ≈ 0（Shannon entropy ≈ 0）
        → Trust interval 大幅拉寬

T+1:20  Dashboard 顯示：
        sybil-v1 的 factual reputation：
          - 原始（未降權）：0.87 ± 0.03
          - 降權後（顯示值）：0.43 ± 0.38（信賴區間極寬）
        系統警告：「此 reputation 多元性不足，建議等待跨模型評分累積」

T+1:45  對比：同樣 reputation 數值的 legal-v1（有 3 種不同模型評分）
          - legal-v1 factual：0.82 ± 0.07（窄信賴區間）

[驗證的設計主張]
- 同源降權阻止 reputation inflation
- 信賴區間寬度誠實反映訊號多元性不足（對應 G03）
- Aggregator 無 LLM，純運算即可偵測 Sybil 訊號模式
```

### 3.3 評估指標表格

| 指標 | 定義 | 測量方法 | 參照文獻 | 目標值（MVP） |
|---|---|---|---|---|
| **任務正確率 ΔAcc** | Vacant 網路 vs 單一 agent 在標準 benchmark 上的差距 | GSM8K 50 題、HumanEval 30 題，比較 best-of-1（單 vacant）vs best-of-k（多 vacant 投票） | CrS §4.2 | ΔAcc ≥ +5% |
| **Reputation 收斂速度 T₅₀** | 高/低品質 vacant 被正確分類（信賴區間不重疊）需要的互動數 | 從上線到 95% 信賴區間不重疊的 call 數量 | DRF Fig. 3 | T₅₀ ≤ 30 次互動 |
| **抗對抗穩健性 Δrep_attack** | K 個 adversary 後高品質 vacant reputation 降幅 | 放入 K={1,2,3} 個 adversary，測量正常 vacant 被錯誤評分的幅度 | CrS adversary-majority §5 | K=2 時降幅 ≤ 0.05 |
| **多元性指數 H_call** | 呼叫分布的 Shannon entropy | H = -Σ pᵢ log pᵢ（pᵢ = 第 i 個 vacant 的呼叫佔比） | 多元性文獻 | H ≥ 1.5 bits（5 個 vacant） |
| **誠實度相關 r_honesty** | self-eval 與 peer-eval 的 Pearson r | 計算每個 vacant 的自評分和 peer review 分的相關係數 | DRF §3（DRF 定義）| r ≥ 0.6 for 正常 vacant；r ≤ 0.2 for adversary |
| **失敗→spawn 延遲 t_spawn** | 第一次 reputation 跌破閾值 → spawn event 完成的時間（壓縮後秒數） | 記錄 event log 中 first_fail_event 到 spawn_complete 的 timestamp delta | 自定 | ≤ 60 秒（demo 壓縮時間） |
| **同源降權效果 Δinflation** | Sybil 攻擊後 reputation 被壓制的幅度 | sybil 組 vs 正常組 reputation 差值；信賴區間重疊程度 | G03 對應 | 信賴區間重疊 ≥ 80%（sybil 組 vs 初始值） |
| **記錄完整性 hash_verify** | hash chain 驗證通過率 | 隨機抽 20% 的 event，重算 hash 比對 | G04 | 100% 通過 |

### 3.4 不展示項目（誠實聲明）

| 項目 | 原因 | 論文中的處理 |
|---|---|---|
| MINJA 端到端注入攻擊 | 需要完整 red-teaming 基礎設施，超出 14 週範圍 | Future work 節，引用 MINJA 論文說明威脅模型 |
| 完整聯邦 Registry | 需要跨機構規格和 consensus 機制設計 | 在架構章說明 MVP 為單一 Registry，討論演進路徑 |
| 真實 adoption signal 動力 | 真實引用需要數天累積；demo 為人工壓縮 | 明確標注「time-compressed simulation」，不宣稱等同真實 |
| 跨模型多元性的自然湧現 | MVP 只有 5 個 vacant，網路太小 | 討論預期在更大網路中的行為，定性而非定量 |
| 物理實體 vacant | 概念層面提及，不在 MVP 範圍 | Introduction/Conclusion 的展望節 |

---

## 4. 對應到的缺口 / 風險

| 缺口/問題 | MVP 的應對 | 殘存風險 |
|---|---|---|
| **G01** 跨任務持久化 reputation | hash chain + git 讓 reputation 在 demo session 內持久；不同任務的 factual/adoption 維度各自累積 | MVP 不展示跨不同部署的 reputation 遷移 |
| **G02** Sybil 抵抗 | Aggregator 同源降權 + 信賴區間懲罰（場景 D） | 沒有 cryptographic identity；攻擊者可換 base model 繞過 |
| **G03** 多元評估者 | 5 個 vacant 使用 4 種不同 base model，Aggregator 偵測同源並降權 | 5 個 vacant 樣本量太小，結論只能定性 |
| **G04** 記錄不可竄改 | SQLite hash chain + Merkle root → git；每次讀取可驗證 | 不是 blockchain，仍依賴 Registry 節點誠實；git 可被 force-push |
| **G05** 無人類介入評估 | peer review + caller review + ground truth（GSM8K 有標準答案）三層互補 | 無 ground truth 任務（如開放性法律問答）仍依賴主觀評分 |
| **G06** Automation bias UX | Dashboard 強制顯示信賴區間和訊號多元性警告；沒有「單一分數」的 UI 設計 | 使用者研究未做，不知道 UX 是否真的防止過度信任 |
| **Q3** token 免費模擬 | Ollama 本地推論（零 API 成本）+ 時間壓縮（場景中明確說明） | 壓縮比高，不等同真實生態動力 |
| **Q6** demo 深度 | 4 個場景涵蓋核心行為；明確列出不展示項 | 審查委員可能追問聯邦化、Sybil 密碼學解法 |

**三個關鍵張力的正面回應：**

1. **「網路自然淘汰」vs Sybil/whitewashing：** MVP 展示同源降權讓 Sybil 無法靠 reputation inflation 生存；但 whitewashing（換身份重來）需要 cryptographic identity anchor（G02）才能完整解決，論文中誠實聲明此為 MVP 限制，指向後續工作。

2. **「無中央 judge」vs cold start：** 新 vacant 上線時 reputation 向量從 `[0.5, 0.5, 0.5, 0.5, 0.0]`（adoption 為 0，其餘為中性）開始，信賴區間極寬，系統會警告「新進者，資料不足」。第一個 caller 承擔探索風險，這是設計中接受的代價，不引入任何 bootstrap critic。

3. **「透明記錄」vs MINJA/eTAMP：** hash chain 讓記錄本身 tamper-evident，但記錄的內容（peer review 的「評語」）仍可被注入惡意 payload。MVP 的防禦是 Aggregator 只取數值 JSON 而不取自由文字；完整的 MINJA 防禦留給 future work。

---

## 5. 參考文獻 / 引用

- **CrS** = Cross-model review system（對應 P7 指標設計的 adversary-majority test 和 benchmark 比較方法，CrS §4.2, §5）
- **DRF** = Decentralized Reputation Framework（honesty 維度定義 r_honesty 借自 DRF §3；收斂速度圖 DRF Fig. 3）
- **A-Trust** = Accountability-centered Trust（structural accountability 概念框架；Sybil 威脅 Friedman 2007 + Douceur 2002）
- Goodhart 1975：多維 reputation 設計動機（不用單一純量避免 Goodhart 反噬）
- Skalse et al. 2022「Defining and Characterizing Reward Hacking」（G03 多元評估者的文獻根據）
- MINJA（injection rate 95%）：G04, G05 設計動機
- Qwen 2.5 Technical Report（本地模型選型依據）
- Meta Llama 3.2 Model Card（本地模型選型依據）

---

## 6. 對其他 pane 的依賴與假設

| 依賴對象 | 所需輸出 | 若未到位的假設 |
|---|---|---|
| **P1（Registry）** | hash chain schema、event log 格式、Merkle root 觸發邏輯 | 假設 SQLite 一張 events 表，每筆含 id/timestamp/actor/type/payload/prev_hash；Merkle root 手動觸發 |
| **P2（Reputation/Aggregator）** | 5 維聚合公式、同源降權係數、信賴區間計算方式 | 假設同源降權係數 = 0.5；Wilson interval；多元性懲罰 = entropy_factor × σ |
| **P3（Vacant Runtime）** | heartbeat 間隔、spawn 觸發閾值、自評 JSON schema | 假設 heartbeat 15 秒；spawn 閾值 = factual < 0.35 連續 5 次；自評 JSON 含 5 個 [0,1] float |
| **P4（A2A / 通訊規格）** | envelope 格式、Ed25519 簽章欄位 | 假設標準 A2A envelope + signature 欄位；call_id = UUID4 |
| **P5（Client SDK）** | vacant_query / vacant_call / vacant_review API 介面 | 假設 Python SDK，同步調用，返回 typed dataclass |
| **P6（Spawn / 演化機制）** | spawn event 格式、child_id 命名規則、parent_id 鏈結 | 假設 child_id = parent_id + "-v{N+1}"；spawn event 含 trigger_reason 欄位 |

---

## 7. 14 週工程時程

**基準：** 2026-05-01 開始，2026-08-06（第 14 週末）完成 final demo。

### 7.1 單人時程（一個人做全部）

| 週次 | 日期 | 里程碑 | 交付物 |
|---|---|---|---|
| W1 | 05/01-05/07 | **Registry 基礎** | SQLite schema + hash chain + Merkle 觸發；unit test 100% |
| W2 | 05/08-05/14 | **Aggregator 核心** | 5 維聚合公式 + 同源降權 + Wilson interval；可接受 mock 評分輸入 |
| W3 | 05/15-05/21 | **Vacant Runtime v0.1** | heartbeat 迴圈 + A2A FastAPI endpoint + self-eval JSON；無 LLM（先用 mock） |
| W4 | 05/22-05/28 | **接入本地 LLM** | Ollama 整合；legal-v1, medical-v1, coding-v1 各自用真實模型回應 |
| W5 | 05/29-06/04 | **peer review 機制** | idle-time peer review 迴圈；評分推 Registry；Aggregator 更新觸發 |
| W6 | 06/05-06/11 | **spawn 機制** | 失敗計數 + spawn 觸發 + child_id 鏈結 + Registry spawn event 寫入 |
| W7 | 06/12-06/18 | **Client SDK + CLI** | vacant_query / vacant_call / vacant_review；命令列可測試完整流程 |
| W8 | 06/19-06/25 | **複合 vacant** | marketing-v1 + 內部 sub-vacant；驗證 sub-vacant 不進外部 Registry |
| W9 | 06/26-07/02 | **Demo Dashboard** | 即時 reputation 折線圖 + event time series + Network View（用 Streamlit 或 Grafana） |
| W10 | 07/03-07/09 | **場景 A + B 劇本** | workload generator；adversary-v1；完整 scenario A+B 跑通 |
| W11 | 07/10-07/16 | **場景 C + D + 評估** | marketing-v1 demo + Sybil 場景；跑 GSM8K/HumanEval 基準對比實驗 |
| W12 | 07/17-07/23 | **論文撰寫** | Related Work + System Design + Evaluation 三章初稿 |
| W13 | 07/24-07/30 | **論文修訂 + 數據補齊** | 重跑需要補圖的實驗；指導教授 review；結果調整 |
| W14 | 07/31-08/06 | **Demo 排練 + 提交** | 完整 demo 排練 3 次；論文定稿；提交 |

**緩衝策略：** W8-W9 之間有 4 天機動期。若 W6 spawn 機制延遲，W8 複合 vacant 可先用 mock；論文撰寫從 W10 就可以平行開始（Related Work 和 System Design 不需要等實驗結果）。

### 7.2 三人團隊分工建議

| 成員 | 主責 | 週次 |
|---|---|---|
| **成員 A（後端/基礎設施）** | Registry + hash chain + Aggregator + Sybil 場景（D） | W1-W6 並行；W7 支援整合 |
| **成員 B（Runtime/規格）** | Vacant Runtime + peer review + spawn + A2A 規格 | W3-W8 並行；W9-W10 場景 B+C |
| **成員 C（前端/實驗）** | Client SDK + Demo Dashboard + 評估框架 + 場景 A | W5-W11 並行；W12-W14 論文整合 |

**平行加速：** 三人分工可將關鍵路徑從 14 週壓縮到約 9 週達到「可跑場景 A+B」，剩下 5 週專注優化和論文。整合測試（W8）是唯一必須全員到齊的里程碑。

---

## 8. 論文範圍建議

### 8.1 能寫滿的章節

| 章節 | 能說什麼 | 引用策略 |
|---|---|---|
| **Related Work** | 現有 multi-agent 系統缺少跨任務持久 reputation；CrS 在 team 內運作；DRF 沒有 structural accountability 機制；A-Trust 未解決 Sybil | 直接引用三篇對照表 |
| **System Design** | 完整描述 5 個元件（Registry + Runtime + Aggregator + SDK + Dashboard）；5 維 reputation 設計動機（Goodhart）；同源降權邏輯；spawn 機制 | 架構圖 + pseudocode + schema |
| **Evaluation** | 4 個場景的量化結果（8 個指標）；GSM8K/HumanEval 基準對比；reputation 收斂曲線；Sybil 抑制效果 | 數據表格 + 折線圖 |
| **Structural Accountability** | 定義「structural accountability」vs「moral responsibility」；形式化 reputation 更新為 DAG 上的訊號傳播 | 借 A-Trust 框架延伸 |

### 8.2 留 Future Work 的章節

| 項目 | 理由 |
|---|---|
| 聯邦 Registry + consensus | 需要跨機構規格設計，超出 MVP |
| Cryptographic identity（Sybil 完整解法） | 需要 PKI 或 DID 基礎設施 |
| 真實 adoption signal 動力 | 需要數週觀察窗口 |
| MINJA 完整防禦 | 需要對抗性 red-teaming |
| 跨模型多元性的湧現驗證 | 需要 100+ 個體的網路規模 |
| 物理實體 vacant | 概念探索，無硬體支援 |

### 8.3 Novelty 主張

- **主張 1：** 首個在 agent-to-agent 規格層上實作多維、帶信賴區間、同源降權的持久 reputation 系統（對照 CrS/DRF：它們在 team 內、不跨任務、不防 Sybil）。
- **主張 2：** 「失敗→競爭者誕生」的 structural accountability 機制——不依賴人類介入，用 reputation 閾值自動觸發 spawn（對照現有系統：失敗只記錄，不生出替代者）。
- **主張 3：** 複合 vacant 的子代封閉原則——為 agent composition 提供邊界（對照現有系統：無任何機制限制 sub-agent 對外呼叫）。

---

*P7-mvp pane · 2026-05-01 · 基於 BRIEFING v1 和 vacant_current_understanding.md v0.4*
