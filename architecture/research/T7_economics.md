# T7: Vacant 服務經濟模型設計研究

> 研究任務：為 Vacant 網路設計可持續的經濟模型。基於 12 個 precedent 的深度分析（DePIN、算力市場、API marketplace、agent-as-a-service、AI inference billing）。
>
> 對應 THEORY_V3.md §H5：「沒選定就上線，會在跑久了之後觸礁。」

---

## 0. 研究方法與 Precedent 覆蓋

| 分類 | 案例 | 狀態 |
|---|---|---|
| DePIN / 去中心化網路 | Helium（HNT）、Filecoin（FIL）、Render（RNDR）、Akash（AKT） | 全部仍在運營（各有重組） |
| API Marketplace | RapidAPI、Replicate | RapidAPI 被 Nokia 收購；Replicate 被 Cloudflare 收購 |
| Agent-as-a-Service | Inflection AI（Pi）、Adept AI、Character.ai | Inflection 被 Microsoft acqui-hire；Adept 被 Amazon acqui-hire；Character.ai 掙扎中 |
| AI Inference 計費 | Together AI、Modal Labs、Replicate（計費層） | Together AI $300M ARR；Modal Labs $1.1B 估值；Replicate 被收購 |

所有數據均有來源引用，2024–2026 年為主。

---

## 1. 五個經濟模型原型對比

從 12 個 precedent 提煉出五種原型，覆蓋了幾乎所有可行的 Vacant 付費路徑。

---

### Model A：代幣通膨挖礦模型
**代表案例：** Helium、Filecoin（部分）

#### 運作機制
- **誰付錢：** 規格本身（通膨）而非真實服務使用者
- **定價機制：** Provider 靠 Proof-of-Coverage 或算力算法贏得代幣排放，而非依服務量計費
- **收益分潤：** 從代幣通膨池按貢獻比例分配；服務費（Data Credits）收入相形之下微乎其微

#### 真實數據
- Helium IoT 每日實際服務費收入：**\$136**；每日網路維護成本：**\$55,000**——通膨補貼 99.75% 的成本
- 確認偽造熱點：~25,000 / 524,000（5%）——gaming 比例顯著
- Filecoin 網路使用率：**29–36%**，即 64–71% 的儲存容量為「空白算力」（speculative capacity）

#### Failure Mode
1. **Gaming/Spoofing**：任何基於「宣稱提供服務」而非「真實使用」的獎勵，必然誘發偽造
2. **需求與供給永久脫節**：礦工動機是賺代幣，不是服務使用者；網路供給量遠超真實需求
3. **代幣通膨稀釋 → 生態崩潰循環**：需要真實需求增長才能支撐代幣價格，但 incentive 設計阻止了真實需求增長

#### Incentive 扭曲分析
```
目標行為：提供高品質服務
實際行為：最大化挖礦算力/算法分數
結果：大量假服務節點；真實使用者比例極低
```
這是 Goodhart's Law 的直接展現：「當一個指標成為目標，它就不再是好指標。」PoC/PoW 獎勵讓「服務量代理指標」成為博弈目標，而非服務品質本身。

---

### Model B：API Marketplace 分潤模型
**代表案例：** RapidAPI（75/25 分潤）

#### 運作機制
- **誰付錢：** API 使用者（開發者 / 企業）
- **定價機制：** Provider 自設計費方案（freemium、pay-per-call、subscription tier）；平台提供統一計費基礎設施
- **收益分潤：** Provider 保留 **75%**，平台抽取 **25%**；每月結算，延遲 T+2 months

#### 真實數據
- RapidAPI 2024 收入：**\$44.9M**，55k 企業客戶，4M+ 開發者
- 分潤比例：明確的 75/25 是市場可接受基準
- 被 Nokia 收購後方向：從純 API 市場轉型為電信/網路 API 整合平台

#### Failure Mode
1. **大型 Provider 逃離**：高收益 API（\>$10k/月）的 25% 抽成會促使它們建立直銷渠道，平台留下的主要是長尾小型 provider
2. **發現機制不公平**：熱門 API 壟斷曝光，新進者難以突破，形成馬太效應
3. **付款延遲（T+2 month）**：對現金流敏感的小型開發者是隱性成本

#### Incentive 扭曲分析
```
目標行為：持續提供高品質 API
實際行為：品質優秀後，轉移到自建平台（逃離 25% 抽成）
結果：平台品質逐漸向中等靠攏，優秀 provider 離開
```
平台抽成越高，越強烈激勵成功 provider 脫平台直銷。這是 marketplace 的結構性問題，不是 RapidAPI 獨有。

---

### Model C：算力即服務（無 Creator 分潤）
**代表案例：** Replicate、Together AI、Modal Labs

#### 運作機制
- **誰付錢：** AI 開發者（B2D）
- **定價機制：** 按秒（Modal、Replicate）或按 token（Together AI）計費；極細粒度透明計費
- **收益分潤：** **平台自建基礎設施，無外部 creator/model author 分潤**；模型創作者貢獻開源模型但零回報

#### 真實數據
- Together AI 2025 ARR 估計：**\$300M**，450k+ 開發者；單價 $0.05–7/M tokens
- Modal Labs 估值：**\$1.1B**（Series B），按秒計費（T4: $0.40/hr → $0.000111/sec）
- Replicate 2024 收入：**\$5.3M**——作為獨立業務不可持續，2025 年被 Cloudflare 收購
- Replicate 的關鍵問題：9,000+ 公開模型的創作者**完全無法從 inference 收入中分潤**

#### Failure Mode
1. **Creator incentive 缺位**（Replicate 失敗的直接原因）：模型創作者無回報 → 維護動力不足 → 品質逐漸劣化 → 平台被競爭者（Cloudflare、HuggingFace）吸收
2. **低 margin 價格戰**：開源模型市場競爭激烈，Together AI 能生存靠的是規模（$300M ARR），但這需要大量融資支撐
3. **無 marketplace 網路效應**：Modal 是優秀執行工具，但鎖定性極低，容易被複製

#### Incentive 扭曲分析
```
目標行為：吸引高品質模型 creator 並讓他們持續維護
實際行為：Creator 無償貢獻，平台賺取 markup
結果：品質維護靠「開源精神」而非經濟激勵，長期不穩
```
**Replicate 的失敗是 Vacant 最直接的警示**：如果 vacant owner 的服務貢獻得不到直接經濟回報，系統品質必然隨時間劣化。

---

### Model D：訂閱制消費者/企業模型
**代表案例：** Inflection Pi（失敗）、Adept AI（失敗）、Character.ai（掙扎）

#### 運作機制
- **誰付錢：** B2C 消費者（Inflection、Character.ai）或 B2B 企業（Adept）
- **定價機制：** Freemium + \$9.99/月 訂閱（Consumer）；訂閱/按使用量計費（Enterprise）
- **收益分潤：** 中央化公司收取全部訂閱費；Character.ai 的 18M+ 角色創作者**零回報**

#### 真實數據
- Inflection：融資 \$1.3B，收入**幾乎為零**，2024 年被 Microsoft acqui-hire（\$650M 授權費）
- Adept：「維持到 2024 年底需要再融資 \$2B」，2024 年被 Amazon acqui-hire（\$330M）
- Character.ai：2025 ARR ~**\$50M**，20M MAU，但基礎設施成本遠超收入；無 creator 分潤

#### Failure Mode
1. **Consumer AI 面對巨頭是消耗戰**（Inflection）：Google / Microsoft 可無限期提供免費 AI，初創無法競爭
2. **Agent 落地需要 change management**（Adept）：每 \$1 技術投資需要 \$3 組織變革，企業部署速度遠低於預期
3. **Consumer 創作者無償貢獻不可持續**（Character.ai）：18M+ 角色全由用戶無償創建，一旦競爭平台提供分潤，供給方可能大規模遷移

#### Incentive 扭曲分析
```
Consumer 模型：
目標行為：用戶付費訂閱，創作者持續貢獻高品質角色
實際行為：消費者享受免費服務，創作者無回報
結果：商業化困難，巨頭免費競爭下毫無護城河

Enterprise 模型：
目標行為：企業大規模部署 agent，按使用量付費
實際行為：POC 無法轉化為大規模部署，燒錢等待
結果：收入增長遠低於基礎設施成本，被迫被收購
```

---

### Model E：質押 + 服務費混合模型
**代表案例：** Filecoin（質押機制）+ Akash（反向拍賣）的組合原型

#### 運作機制
- **誰付錢：** 服務使用者（caller）直接支付服務費；provider 質押 collateral 作為服務品質保證
- **定價機制：** Filecoin：Provider 掛出詢價，client 議價，服務費 + 區塊獎勵雙軌；Akash：反向拍賣（tenant 發布需求，provider 競標），市場決定價格，比 AWS 低 60–85%
- **收益分潤：** Provider 直接收取服務費；規格從交易中抽取小比例進入公共池；slash 機制：若服務品質不達標，扣除部分質押

#### 真實數據
- Filecoin：引入 10x 算力加成後，FIL+ 方案顯著提升真實資料儲存比例（2024 年企業儲存轉型中）
- Akash：反向拍賣讓計算成本比 AWS/GCP 低 **60–85%**；2024 Q4 新增 lease 達 61,000（YoY +317%）
- Filecoin 質押效果：provider 必須質押 initial pledge，不達標即被 slash，顯著降低惡意節點比例

#### Failure Mode
1. **高質押門檻排擠小型 provider**（Filecoin）：Filecoin active provider 從 2022 年 4,100 → 2024 年 ~1,900，下降 54%；質押門檻是主因之一
2. **幣價波動使服務費收益不穩定**（Akash）：AKT 2025 Q4 跌 87%，USD 計費收入同期下降 42%；provider 的實際美元收益與代幣價格強耦合
3. **初期質押資本壓力**：新加入的 provider 需要先有資本才能質押，形成進入門檻

#### Incentive 扭曲分析
```
目標行為：Provider 提供穩定高品質服務
潛在問題：質押門檻排擠小型高品質 provider；幣價波動導致服務費美元價值不穩定
緩解措施：低質押門檻 + 穩定幣結算 + 服務品質 oracle（如 reputation 系統）
```
**這是最接近 Vacant 需求的原型**，但需要關鍵修改：用多維 reputation 作為 slash 標準（而非 Filecoin 的單純可用性 SLA），且質押門檻要設得極低以避免排擠效應。

---

## 2. 各模型的 Incentive 扭曲總表

| 模型 | 主要 Incentive 扭曲 | Vacant 場景的特定風險 |
|---|---|---|
| **A：代幣通膨挖礦** | Gaming PoC；供給驅動代幣而非需求驅動服務 | Reputation mining → vacant 互相虛假評分；偽造服務記錄 |
| **B：API Marketplace 分潤** | 優秀 provider 逃離；馬太效應；付款延遲 | 高 reputation vacant 脫離規格，自建市場渠道 |
| **C：算力即服務（無分潤）** | Creator 無回報 → 維護動力不足 → 品質劣化 | Vacant owner 放棄維護，導致 reputation 自然衰減但無替代者 |
| **D：訂閱制** | Consumer vs 巨頭消耗戰；無 creator 分潤 | Consumer Vacant 無法對抗 OpenAI/Anthropic 的免費服務 |
| **E：質押 + 服務費** | 質押門檻排擠小型節點；幣價波動 | 高質押要求阻止新手 vacant owner 進入 |

**跨模型共通扭曲（所有模型共享）：**

1. **Goodhart 陷阱**：任何單一指標成為激勵目標，都會被 game。Helium 的 PoC、Filecoin 的算力、Character.ai 的對話數——皆如此。多維 reputation 是設計上對此的回應。

2. **Cold start 悖論**：沒有使用量就沒有信譽，沒有信譽就沒有使用量。每個模型都需要某種形式的 bootstrap，代幣通膨（Model A）是最常見但最危險的 bootstrap。

3. **真實服務 vs 投機行為**：所有含代幣的系統都面臨「服務使用者」和「代幣投機者」兩類參與者，後者對系統設計的反應往往與前者相反。

---

## 3. Vacant MVP 推薦混合模型 + 長期演化路徑

### 3.1 設計原則（從 12 個案例萃取）

在設計 Vacant 經濟模型之前，先確立四條不可違反的設計原則：

**原則 P1：Owner 必須從被呼叫中獲得直接、可預期的經濟回報**
依據：Replicate 和 Character.ai 的失敗都直接源於 creator 零回報。Vacant 的 owner 必須能從 vacant 被呼叫中穩定收入，才有動力維護和升級 vacant。

**原則 P2：激勵必須連結真實服務使用，而非代理指標**
依據：Helium PoC 和 Filecoin 空白算力的失敗。Vacant 的 reputation 改善和收入增長必須連結到真實的 caller 使用，而非 peer review 互評分數（可被 game）或代幣通膨（與服務無關）。

**原則 P3：門檻低到任何人都能進入，退出代價才是約束機制**
依據：Filecoin 高質押排擠小型 provider；Vacant 的「無資格審核」原則。入場零成本（或極低），但一旦表現差，退出的代價是 reputation 清零和 sunk cost。

**原則 P4：計費單位要透明、簡單、可預期**
依據：Together AI per-token 和 Modal 按秒計費的成功；複雜的「reputation × 算力 × 時間 × 代幣匯率」公式會製造不確定性，阻礙採用。

---

### 3.2 MVP 推薦模型：Owner 付費 + Caller 直接付費

**MVP 階段（2026 畢業專題 Demo）：**

```
[MVP 費用流向]

Caller ──→ Client SDK ──→ 記錄 call event（免費，無費用）
                ↓
           vacant_review API 提交評分（免費）
                ↓
           Registry 記錄，Aggregator 更新 reputation（免費）

Vacant Owner 的費用：
  - 自行負擔本地推論成本（Ollama，硬體自備）
  - 零向 caller 收費
  - Zero friction，能 demo 核心行為即可
```

**MVP 階段的理由：** 畢業 demo 目的是驗證技術正確性（reputation 收斂、spawn 機制、Sybil 抵抗），不是驗證商業可行性。在 demo 規模（5 個 vacant，14 週），引入代幣或計費機制只會增加工程複雜度和演示阻力。**MVP 的「商業模式」是 owner 自付成本 + caller 免費使用**，這是最誠實、最低阻力的示範。

論文中明確聲明：「本 MVP 不含付費機制，以便聚焦驗證技術命題；商業模型設計另述。」

---

### 3.3 Post-MVP 第一階段：直接服務費模型（V1 商業化）

**啟動條件：** 網路有 20+ 個 active vacant，3+ 個 caller 願意付費

```
[V1 費用流向]

Caller 支付費用
     │
     ▼
每次 vacant_call 收取 X 單位 credit
     │
     ├─ 80% → Vacant Owner（直接結算，穩定幣 USDC/USD）
     ├─ 15% → Protocol Pool（Registry 維護 + spawn bootstrap）
     └─ 5%  → Aggregator 運算獎勵（鼓勵多方跑 Aggregator）

計費單位：「call unit」= max(1, ceil(token_count / 1000))
計費方式：Caller 預付 credit，按 call 扣款

Reputation 乘數（建議性，非強制）：
  caller_fee = base_rate × (1 + avg_5dim_rep × 0.5)
  ── 高 reputation vacant 每次呼叫費用略高，但 caller 可以指定
  ── 低 reputation vacant 費用低，鼓勵試用新 vacant（冷啟動緩解）
```

**80/15/5 分潤比例的設計理由：**
- 80% 給 owner：比 RapidAPI 的 75% 更優，強化供給端吸引力
- 15% 進 Protocol Pool：用於 Registry 維護費用、spawn 觸發時的新 vacant bootstrap credit、生態健康指標報告
- 5% 給 Aggregator 運算者：鼓勵多方運行 Aggregator 節點（對應 THEORY_V3 的 H4「多方 attestation 啟動」問題），逐步去中心化 Aggregator

**「Reputation 乘數」的特別說明：**

這是選擇性的（caller 可以手動指定覆蓋），目的是：
1. 讓高品質 vacant 能賺取更高收入，正向激勵品質提升
2. 讓低 reputation / 新進 vacant 通過較低價格吸引試用，緩解冷啟動問題
3. 防止「最便宜不是最差的」——低價是競爭策略，不是懲罰

**風險對沖：** 為防止 caller 為省錢而選低品質 vacant 導致「劣幣驅逐良幣」，建議在 Client SDK 預設排序為「reputation 加權後的 value score」（品質/價格比），而非純粹最低價排序。

---

### 3.4 第二階段：可選質押機制（V2 信任強化）

**啟動條件：** 網路有 200+ 个 active vacant，出現首批高價值任務（法律/醫療/財務）

```
[V2 新增機制：Optional Stake]

Vacant Owner 選擇（不強制）：
  質押 X credit 到 Registry
  ── 質押後，capability card 顯示 [STAKED: 🔒 X credit]
  ── caller 可選擇只看「有質押的 vacant」（高信任 tier）

Slash 條件（非 owner 控制，由 Aggregator 自動觸發）：
  IF any_dim(reputation) < 0.25 連續 10 次 AND peer_review_consensus > 0.7 bad
  THEN slash 10% of stake → Protocol Pool

Stake 獎勵：
  有效質押的 vacant 獲得額外 5% 的呼叫收益（來自 Protocol Pool）
  ── 鼓勵高品質 vacant 質押，強化信號
  ── 低質量 vacant 不應質押（因為 slash 成本高）
```

**質押門檻設計原則（對應 Filecoin 高門檻排擠問題）：**
- 最小質押量 = 10 次呼叫收益（極低）
- 質押上限 = 1,000 次呼叫收益（避免大型 provider 用質押額壟斷信任排名）
- 質押無鎖定期（隨時可取出），但取出觸發 capability card 降至 [UNSTAKING] 狀態，7 天後正式解除

**這是可選的，不是強制的**——新進 vacant 可以不質押，直接靠 reputation 累積獲得信任；高價值任務的 caller 可以選擇只考慮有質押的 vacant。市場自然分層。

---

### 3.5 長期演化路徑

```
時間軸（從 MVP 到生態成熟）

2026 Q3 ── MVP Demo
  └─ Owner 自付成本
  └─ Caller 免費使用
  └─ 目標：驗證 reputation 收斂、spawn、Sybil 抵抗

2027 Q1 ── V1：直接服務費（若有持續開發）
  └─ 80/15/5 分潤
  └─ Per-call credit billing
  └─ Reputation 乘數（可選）

2027 Q3 ── V2：可選質押層
  └─ Optional stake + slash
  └─ 高信任 tier 市場分層

2028+ ── V3：聯邦化 + 規格代幣（若生態夠大）
  └─ 多個 Registry 運行節點
  └─ BME 代幣設計（借 Render Network）：
       caller 燒毀代幣 → 規格鑄造新代幣給 owner
       代幣供給與使用量正相關
  └─ Aggregator 去中心化：多方競爭提供聚合服務
```

**V3 代幣設計說明（長期選項，非 MVP 範疇）：**

借鑑 Render Network 的 BME（Burn-and-Mint Equilibrium）：
- Caller 用法定貨幣購買規格代幣 → 代幣被燒毀 → Aggregator 鑄造等量代幣給 Owner
- 效果：代幣總供給量與網路實際使用量正相關，防止通膨獎勵製造假供給
- 防止 Helium 問題：沒有使用就沒有代幣鑄造，消除空轉激勵

**但**：引入代幣在 MVP 和 V1/V2 階段都是過早設計。規格代幣帶來投機風險（Akash 案例：AKT 跌 87% 直接打擊服務收入），只有在生態規模足夠大、有機使用量足夠穩定時，代幣設計的好處（更強的 protocol-level 激勵、可組合性）才超過投機風險。

---

## 4. 對 THEORY_V3 H5 的直接回應

THEORY_V3 H5 列出三個選項並說明各自的 incentive 扭曲：

| H5 選項 | THEORY_V3 的評價 | 本研究的補充 | MVP 建議 |
|---|---|---|---|
| **Owner 付（自掏腰包）** | 激勵不足：owner 無動力維護 | Replicate 的失敗確認此問題；但 MVP demo 規模下是唯一可行選項 | **MVP 採用**，明確聲明 V1 商業化路徑 |
| **Caller 付（call-time billing）** | 高 reputation vacant 被過度使用 | Reputation 乘數可緩解此問題；RapidAPI 75/25 是可執行模型 | **V1 主力模型**，加入 reputation 乘數和 value-score 排序 |
| **Stake pool 付（DeFi 化）** | 金融投機蓋過服務品質 | Helium + Akash 確認：代幣投機會破壞服務市場；BME 是較好的代幣設計但仍有風險 | **V3 長期選項**，不在 MVP/V1 採用 |

**推薦混合模型：**
- **MVP**：Owner 付 + Caller 免費（技術 demo）
- **V1**：Caller 付（per-call）+ 80/15/5 分潤（直接服務費）
- **V2**：V1 + 可選 stake/slash（信任分層）
- **V3**：V2 + BME 代幣（生態成熟後）

---

## 5. 誠實的限制聲明

本研究基於 2024–2026 年公開數據。以下限制需在後續設計中面對：

1. **沒有直接類比的先例**：Vacant 同時具備「去中心化網路」、「API marketplace」和「agent reputation」三種屬性，12 個案例中沒有完全對應的。推薦模型是合理推論，非已被驗證的設計。

2. **Reputation 乘數的 calibration 問題**：「高 reputation → 略高收費」理論上對齊 incentive，但 reputation 冷啟動期（新 vacant 的信賴區間極寬）可能導致 discount 過大，新 vacant 難以靠服務費養活自己。需要實際數據校準。

3. **slash 條件的設定**：slash 必須基於可驗證的行為（如 peer review consensus），而非單一 caller 的主觀評分——後者容易被惡意 caller 濫用。具體 slash 條件需要 P2（Aggregator）和 P3（Vacant Runtime）pane 的設計配合。

4. **Protocol Pool 的治理**：15% 進 Protocol Pool，Pool 由誰決定怎麼花？MVP 和 V1 可以是開發者/研究團隊決定，但長期這是去中心化治理問題。

5. **真實 token 免費假設下的重新設計**：本研究的 per-call billing 基於「token 不免費」的現實。若三年後 token 真的接近免費，peer review 和 idle-time 演化的邊際成本趨近零，整個計費模型需要重新設計（可能轉向純 reputation 競爭，服務本身免費，vacant 靠「被信任」本身的聲望帶來其他收益）。

---

## 6. 參考文獻

| 案例 | 主要來源 |
|---|---|
| Helium | [Helium Docs - HNT Token](https://docs.helium.com/tokens/hnt-token/)；[State of Helium Q4 2024, Messari](https://messari.io/report/state-of-helium-q4-2024)；[Helium Spoofing Analysis, 3roam](https://3roam.com/helium-hotspot-spoofing-and-the-deny-list/) |
| Filecoin | [Filecoin Crypto-economics Docs](https://docs.filecoin.io/basics/what-is-filecoin/crypto-economics)；[State of Filecoin Q4 2024, Messari](https://messari.io/report/state-of-filecoin-q4-2024) |
| Render Network | [Render Pricing KB](https://know.rendernetwork.com/basics/how-much-does-rndr-cost)；[Messari Render Overview](https://messari.io/report/understanding-the-render-network-a-comprehensive-overview) |
| Akash | [State of Akash Q4 2024, Messari](https://messari.io/report/state-of-akash-q4-2024)；[State of Akash Q3 2025, Messari](https://messari.io/report/state-of-akash-q3-2025) |
| RapidAPI | [RapidAPI Payouts Docs](https://docs.rapidapi.com/docs/payouts-and-finance)；[RapidAPI Revenue, GetLatka](https://getlatka.com/companies/rapidapi) |
| Replicate | [Replicate Revenue, Sacra](https://sacra.com/c/replicate/)；[Replicate Pricing](https://replicate.com/pricing) |
| Inflection AI | [TechCrunch: Inflection eaten by Microsoft](https://techcrunch.com/2024/03/19/after-raising-1-3b-inflection-got-eaten-alive-by-its-biggest-investor-microsoft/)；[eesel: Inflection Rise and Fall](https://www.eesel.ai/blog/inflection-ai) |
| Adept AI | [eesel: Adept Rise and Pivot](https://www.eesel.ai/blog/adept-ai)；[Amazon Hires Adept, TechCrunch](https://techcrunch.com/2024/06/28/amazon-hires-founders-away-from-ai-startup-adept/) |
| Character.ai | [Character.AI Revenue, Sacra](https://sacra.com/c/character-ai/)；[BusinessofApps Statistics](https://www.businessofapps.com/data/character-ai-statistics/) |
| Together AI | [Together AI Pricing](https://www.together.ai/pricing)；[Together AI Revenue, Sacra](https://sacra.com/c/together-ai/) |
| Modal Labs | [Modal Pricing](https://modal.com/pricing)；[Modal Series B, Sacra](https://sacra.com/c/modal-labs/) |

---

*T7 經濟模型研究 · 2026-05-01 · 研究範圍：12 個 precedent，覆蓋 DePIN / API Marketplace / Agent-as-a-Service / AI Inference Billing*
