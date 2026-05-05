# T5: Same-Controller 偵測研究

> **研究問題：** 在 pseudonymous 網路中，如何在不揭露真實身份的前提下，偵測「同一控制者操作多個 vacant 身份」？
>
> **背景連結：** THEORY_V3 Layer 3 宣告 same-controller 三軌降權（同 LLM / 同 controller_id / 同行為指紋），但未指定偵測機制。Attack 9（parent-child 共謀）的防禦依賴此偵測能力。本文為其提供技術基底。

---

## 0. 問題精確化

Vacant 設計中 `controller_id` 是 capability card 的顯式欄位。偵測難題分兩類：

| 難題類型 | 描述 | 難度 |
|---|---|---|
| **A 類（宣告驗證）** | 宣告了 controller_id，但如何驗證是真的 | 中等（attestation 問題） |
| **B 類（隱匿偵測）** | 故意不宣告或偽造 controller_id，靠行為偵測 | 高（本文主要對象） |

B 類是核心威脅：攻擊者建立多個 vacant 身份，各自宣告不同 controller_id，靠行為信號繞過聲明式降權。

---

## 1. 五個偵測技術概要

---

### T1 — 評審圖譜分析（Review Graph Clustering）

**核心原理：** 同一控制者旗下的 vacant 傾向在評審圖中形成密集同質叢集（dense homogeneous cluster），叢集內部互評比率異常高，對外連結稀疏。這是 Sybil 節點在社交圖中的典型結構特徵。

**關鍵文獻：**
- Wang, Zhang & Gong (2017). *SybilSCAR: Sybil Detection in Online Social Networks via Local Rule-Based Propagation.* IEEE INFOCOM 2017. arXiv:1803.04321 — 統一 SybilRank（隨機遊走）和 SybilBelief（信念傳播）的框架，使用局部更新規則疊代傳播「Sybil 機率」分數；在 Twitter 4170 萬節點資料上超越兩者；可容忍 40% 種子節點標記噪音。
- Cao et al. (2012). *Aiding the Detection of Fake Accounts in Large Scale Social Online Services.* NSDI 2012. — SybilRank：Personalized PageRank 從受信種子傳播；Facebook 4.5 億用戶資料上 5% FPR 下 precision ≈ 97%，為後續研究基線。
- Yu et al. (2008). *SybilLimit: A Near-Optimal Social Network Defense Against Sybil Attacks.* IEEE S&P 2008. — 奠基性隨機遊走方法，核心假設：攻擊者在受信任區域與 Sybil 區域之間只能建立少量邊。

**訊號：**
- 叢集內互評頻率（normalized mutual review rate）
- 叢集內平均評分 vs 全網平均評分落差
- k-core 分解中異常緊密的核心
- Personalized PageRank / local propagation 得分分布異常

**偵測精度（文獻數字）：** SybilSCAR 在 Twitter 大圖資料上效能優於 SybilRank 和 SybilBelief；可容忍 40% label noise（Facebook），在小型稀疏圖上仍退化。

---

### T2 — 時序相關性分析（Temporal Correlation Analysis）

**核心原理：** 同一控制者管理多個 agent 時，這些 agent 的活動節奏（心跳週期、上線/下線時間、評審提交時間窗口）會呈現統計相關性。即使加入隨機抖動，完美模擬真實多人獨立行為的成本很高。

**關鍵文獻：**
- Wu, Ye & Mou (2023). *BotShape: A Novel Social Bots Detection Approach via Behavioral Patterns.* arXiv:2303.10214 — 把 agent 活動序列轉成時間序列特徵（inter-event 時間分布、burst shape、活躍/閒置週期分布），喂給標準分類器；在多個社交 bot 資料集上平均準確率 **98.52%**，F1 **96.65%**。
- Chavoshi et al. (2016). *DeBot: Twitter Bot Detection via Temporal Patterns.* ICDM 2016. — 根據轉推的精確時間戳對找出時序同步的 bot 叢集；召回率 ~91%，精確率 ~96%。核心觀察：機器行為在毫秒級別有可重現的節律，人類行為沒有。
- Cresci et al. (2018). *Social Fingerprinting: Detection of Spambot Groups Through DNA-Inspired Behavioral Modeling.* IEEE TDSC 15(4). — 把 agent 行動序列編碼成 DNA 字符串，計算序列相似度（alignment score）偵測群組協作。

**訊號：**
- heartbeat 週期的 cross-correlation coefficient（對齊 lag = 0 時是否峰值）
- peer review 提交時間的聯合分布（同窗口的 Kolmogorov–Smirnov 檢定）
- spawn event 的時序叢集（burst 相關性）
- 上線/下線時間（UTC 轉換後）的重疊率
- inter-event 時間分布的 KL divergence 配對（BotShape 風格）

**偵測精度：** BotShape 在社交 bot 資料集 accuracy 98.52%, F1 96.65%；DeBot Twitter AUC ≈ 0.97；對抗性 Gaussian jitter ±60s 後 AUC 降至 ~0.73（Varol et al. 2018）。

---

### T3 — 行為風格測定（Behavioral Stylometry + Pseudonymous Identity Linking）

**核心原理：** 同一控制者使用相同 base model + system prompt，即使 keypair 不同，輸出文本的統計特徵（詞彙多樣性、句法複雜度、function word 分布、token 概率分布）仍高度相似。結合互動圖的結構特徵（跟哪些 vacant 互動、互動模式），可在 pseudonymous 環境中做跨身份連結——這正是暗網論壇遷移用戶識別的問題，與 Vacant 高度類比。

**關鍵文獻：**
- Maneriker, He & Parthasarathy (2021). *SYSML: StYlometry with Structure and Multitask Learning — Implications for Darknet Forum Migrant Analysis.* EMNLP 2021. arXiv:2104.00764 — **最相關**：暗網用戶在論壇被查封後換假名遷移，SYSML 用文體特徵 + GNN 互動圖嵌入的多任務學習，連結不同假名背後的同一真實用戶；Mean Retrieval Rank 提升 2.5×，Recall@10 提升 2×（對比先前 stylometry baseline）。方法無需中央化平台資料，可從公開文字語料直接計算。
- Uchendu et al. (2020). *Authorship Attribution for Neural Text Generation.* EMNLP 2020. — 跨 LLM 的文體識別；Transformer 特徵比 n-gram 更好，精度 ~88%（10 個 LLM × 3 tasks）。需做 within-model normalization 排除 base model 天然相似性。
- Kirchenbauer et al. (2023). *A Watermark for Large Language Models.* ICML 2023. arXiv:2301.10226 — LLM 軟水印：同 system prompt → 隱性統計偏差一致；啟發意義：同控制者即使不同 keypair，其 system prompt 相似性會在輸出中留下可偵測的統計痕跡。

**訊號（適用 Vacant）：**
- capability card 文本的 embedding cosine similarity（Sentence-Transformers）
- 工具呼叫序列（tool call ordering）的 Levenshtein 距離分布
- 回應格式模板（JSON key 習慣、段落長度分布、標點模式）
- `behavior_bundle` 中 prompt template 的 character n-gram 指紋
- 評審互動圖的 GNN 嵌入（SYSML 風格）

**偵測精度：** SYSML 封閉集合 Recall@10 相對提升 2×（暗網論壇資料）；Uchendu 跨 LLM 精度 ~88% 封閉集合，~65% 開放集合。within-model normalized residual 才是有效訊號，raw cosine sim 在同 base model 叢集中信噪比差。

---

### T4 — 網路層 + Latency 指紋（Infrastructure Fingerprinting）

**核心原理：** 同一物理/虛擬基礎設施上運行的多個 agent 共享網路特徵——RTT 到 Registry 的分布、TCP stack 指紋、AS 號、TLS 憑證 subject 資訊。這些特徵難以大規模偽造。

**關鍵文獻：**
- Kohno et al. (2005). *Remote Physical Device Fingerprinting.* IEEE S&P 2005. — 基於 TCP timestamp clock skew 識別特定裝置；不需要 IP 即可追蹤（VPN 後仍有效）。誤差 < 2 裝置/1000。
- Miller et al. (2015). *I Know Why You Went to the Clinic: Risks and Realization of HTTPS Traffic Analysis.* PETS 2015. — 即使加密，流量分析仍可識別行為特徵。
- Vastel et al. (2018). *FP-STALKER: Tracking Browser Fingerprint Evolutions.* IEEE S&P 2018. — 瀏覽器指紋在演化後的追蹤；方法可移植到 agent runtime 指紋。
- Khattak et al. (2016). *A Look at the Consequences of Internet Censorship Through an ISP Lens.* IMC 2016. — AS-level 相關性分析方法。

**訊號（適用 Vacant）：**
- RTT 到 Registry（或共同 benchmark server）的分布（均值 ± σ 配對檢定）
- substrate API 的 response time signature（同 API 金鑰 → 同帳戶 routing 路徑）
- TLS 憑證中的 Organization / CN 欄位（若 vacant 自簽憑證）
- Heartbeat 封包的 TCP timestamp 偏移（若原始 socket 可見）

**侷限：** 雲端環境中同一 cloud provider（GCP / AWS）的大量 vacant 會有相似 RTT，信噪比差。VPN / proxy 繞過。**這個訊號在 Vacant 架構中實用性最低，主要作為次要補強。**

**偵測精度：** 在研究環境（直接 socket 觀測）識別同裝置精度 ~95%；但 cloud + CDN + VPN 環境下降至 ~40–60%，不可靠。

---

### T4b — Logbook 公鑰叢集分析（Blockchain-Heuristic Analogy）

> **附加技術**（研究過程中發現）：不在原始 5 訊號清單中，但對 Vacant 架構有強烈類比意義，值得單獨記錄。

**核心原理：** Bitcoin / Ethereum 中，同一真實持有者控制多個 pseudonymous 地址。關鍵啟發：**Common Input Ownership（CIO）——若多個地址同時出現在同一筆交易的 inputs 中，它們必然由同一密鑰持有者控制**。Vacant 的 logbook（append-only hash chain）本質上就是公開的「行為區塊鏈」：同一控制者簽出的多個 vacant 可能在 spawn 事件、peer review 批次、或 composition link 宣告中留下「共同操作」的痕跡。

**關鍵文獻：**
- Meiklejohn et al. (2013). *A Fistful of Bitcoins: Characterizing Payments Among Men with No Names.* IMC 2013. — 奠基性 CIO heuristic；操作上用於識別交易所、暗網市場等大型實體。
- Möser & Narayanan (2022). *Resurrecting Address Clustering in Bitcoin.* Financial Cryptography 2022. arXiv:2107.05749 — ML 精化（random forest）結合時序指紋（fee pattern、UTXO age、address type）；相比純 heuristic baseline 提升精度 ~10–15%。鏈上資料完全公開，無需平台授權。

**對 Vacant 的類比訊號：**
- 同一控制者 spawn 多個 vacant 時，spawn 事件的時間戳叢集（「共同操作窗口」）
- 同批 composition link 宣告（A 宣告與 B 和 C 同時建立 link，且 B、C 均為新建 vacant）
- 相同 `controller_id` 出現在不同 `parent_id` 鏈中（應該不可能，若發生 = 明確攻擊）

**現實限制：** CIO 在區塊鏈的強力之處在於密碼學**必然性**（共同簽名 = 共同控制），Vacant logbook 中不存在這樣的強約束。Vacant 控制者可以刻意分離 spawn 時序，使「共同操作窗口」訊號消失。因此這個技術在 Vacant 中是弱訊號輔助，不是強訊號。

---

### T5 — 協調不真實行為（Coordinated Inauthentic Behavior, CIB）多訊號融合

**核心原理：** 任何單一訊號都脆弱，同一控制者偵測最有效的方法是多訊號融合——時序 + 內容相似度 + 評審圖 + 行為向量，計算後驗機率 P(same_controller | evidence)。Twitter/Facebook 的 CIB 偵測正是此路徑。

**關鍵文獻：**
- Pacheco et al. (2021). *Uncovering Coordinated Networks on Social Media: Methods and Case Studies.* ICWSM 2021. arXiv:2001.05658 — 融合轉推時序 + 內容相似度 + 追蹤關係，以 pairwise Jaccard 矩陣聚類；在 Twitter 大選/IRA 資料集上無監督方法，validation 基於已封禁帳號集合。
- Nizzoli et al. (2021). *Coordinated Behavior on Social Media in the 2019 UK General Election.* ACM WebSci 2021. — 「URL-sharing window」+ 時序相關性雙軌融合；precision 0.91 @ recall 0.72。
- Sharma et al. (2022). *Characterizing the Spread of Coordinated and Inauthentic Behavior During the 2020 US Elections.* arXiv:2204.08140 — 圖神經網路（GNN）方法：把 account 行為編碼為節點特徵，邊為互動，GAT 模型分類；AUC ≈ 0.91。
- Nimmo et al. (2020). *#OperationNarwhal: Secondary Infektion & Ghostwriter Analysis.* DFRLab / Stanford Internet Observatory. — 操作案例研究，識別同一操作者多帳號的 CIB 跡象（方法論部分可直接參考）。

**訊號（適用 Vacant）：**
- 評審內容的 pairwise cosine similarity matrix（同 controller 評同類 vacant 用相似措辭）
- capability card 語意相似度叢集
- spawn 事件的時序叢集
- 互評對（A→B score 高、B→A score 高）的圖異常

**偵測精度（融合模型）：** Pacheco et al. F1 ≈ 0.83；Sharma et al. AUC ≈ 0.91 on labeled social media datasets。在 Vacant 場景（小網路、低評審密度）期望值下降。

---

## 2. 對 Vacant 的適用性評估

| 技術 | 核心訊號 | Vacant 可取得？ | 冷啟動適用？ | 對抗強度 | 去中心化程度 | 總評 |
|---|---|---|---|---|---|---|
| T1 評審圖譜 | peer review 圖結構 | ✅ Registry 有完整記錄 | ❌ 圖稀疏時失效 | 中（攻擊者可建外部連結） | ✅ 純計算 | ★★★ |
| T2 時序相關 | heartbeat / 評審時間戳 | ✅ logbook 中有記錄 | ✅ 少數節點也能算 | 中（加 jitter 可繞） | ✅ 純計算 | ★★★★ |
| T3 行為風格 | 輸出文本 + tool call | △ 需要保存 behavior samples | ✅ 從第一個回應開始 | 低（obfuscation 成本高） | ✅ 本地計算 | ★★★★ |
| T4 網路指紋 | RTT / TCP timestamp | ❌ 雲端環境信噪比低 | ✅ | 低（VPN 繞過） | △ 需要網路層觀測 | ★★ |
| T5 CIB 融合 | 多訊號後驗機率 | ✅ 需要 T1+T2+T3 先就位 | ❌ 需要足夠訊號密度 | 高（最難對抗） | ✅ 純計算 | ★★★★★ |

### Vacant 特有約束

**1. 無中央 LLM / judge**（絕對原則）  
所有偵測演算法必須是純計算（aggregator-compatible）。不能有「讓一個 LLM 判斷 A 和 B 是否像同一個人」的設計。

**2. 去中心化 Registry**  
T1/T2/T5 需要全域評審圖。MVP 階段 Registry 是單一服務，可計算；長期聯邦化後需要跨 Registry 的圖合併，難度升高。

**3. pseudonymous + optional controller declaration**  
controller_id 是自願宣告的欄位。B 類攻擊（不宣告）靠行為訊號偵測，精度永遠低於宣告式驗證。

**4. 評審密度在早期很低**  
新 vacant 互評次數少 → T1 圖太稀疏 → 冷啟動期同源偵測精度很低。T2 的 heartbeat 是更早可用的訊號。

**5. 同 base model 不等於同 controller**  
T3 必須區分「同 LLM 自然相似」和「同控制者刻意相似」。需要控制 base model 後的殘差相似度（within-model normalized similarity）。

---

## 3. 推薦 MVP 訊號組合 + 閾值

### 3.1 設計原則

MVP 要求：(a) 純計算、無 LLM judge；(b) 冷啟動期有基本功能；(c) 實作工程量可在 14 週內完成；(d) 偽陽性代價高於偽陰性（降權是結構性代價，不應對正常 vacant 誤傷）。

因此採取「**三訊號串行篩選 + 後驗閾值**」架構，而非同時啟動所有訊號。

---

### 3.2 三層篩選架構

```
Layer 0 — 宣告式（零計算成本）
  ↓ if controller_id 相同 OR parent_id 鏈可追溯到共同祖先
  → 直接標記 same_controller_declared
  → 套用降權（不需行為偵測）

Layer 1 — 時序快篩（低成本、早期可用）
  條件：兩個 vacant 的 heartbeat 時序 cross-correlation r > θ₁
  → 進入 Layer 2 深度分析

Layer 2 — 行為指紋驗核（中等成本）
  條件：behavior_bundle 相似度 sim > θ₂ 且 T1 評審圖有 ≥1 條共同邊
  → 標記 same_controller_suspected
  → 套用降權（折扣，非封鎖）

Layer 3 — CIB 融合確認（高成本，按需觸發）
  條件：被 Layer 2 標記的 pair 滿足以下任一：
    (a) 互評對 A→B ≥ 0.8 AND B→A ≥ 0.8 AND ≥ 5 次
    (b) Pacheco pairwise Jaccard (content+timing) > θ₃
  → 標記 same_controller_confirmed
  → 套用 cluster 上限（max individual rep），永久記錄 event
```

---

### 3.3 各閾值建議

| 閾值 | 建議值 | 依據 |
|---|---|---|
| θ₁（heartbeat cross-correlation） | r > 0.70，p < 0.05，觀測窗口 ≥ 7 天 | DeBot 研究中 r > 0.65 對 bot 群有效；Vacant heartbeat 每日一次，7 天 = 7 個觀測點，統計力較弱，需保守 |
| θ₂（behavior_bundle 相似度） | cosine sim > 0.88（within base model normalized） | Uchendu et al. 同作者 LLM 輸出 sim ≈ 0.91；扣掉 base model 基線後殘差 > 0.05 視為可疑；建議 0.88 作為入口 |
| 互評對次數 | ≥ 5 次且 ≥ 60 天 | 避免早期少數互評觸發誤判 |
| θ₃（Pacheco Jaccard fusion） | > 0.35（加權：時序佔 0.4，內容佔 0.6） | Pacheco et al. 在 0.30–0.40 找到最佳 F1；Vacant 內容更豐富，稍高 0.35 |
| 子代畢業後 same-controller 保留期 | 永久（不因畢業時間而失效） | THEORY_V3 Attack 9 設計意圖 |

---

### 3.4 偽陽性管控

same_controller_suspected 狀態（Layer 2 輸出）：
- **降權幅度 0.3×**（per THEORY_V3 Layer 3 設計），但**不封鎖**
- vacant 可提交 `controller_differentiation_challenge`：提供不同 controller 的 attestation（可選，非強制）
- 若 challenge 通過（第三方 N-of-M attestation，≥ 3 個獨立 attester 確認是不同 controller），解除 suspected 標記

same_controller_confirmed 狀態（Layer 3 輸出）：
- 套用 cluster reputation 上限 = max(individual)
- event 記錄進 tamper-evident logbook
- **不刪除、不封鎖**（保留責任歷史，符合 Vacant 設計原則）

---

### 3.5 MVP 最小實作範圍

14 週 MVP 內可驗證的最小集合：

| 模組 | 實作內容 | 週期 |
|---|---|---|
| `same_controller_declared` | parent_id 鏈追溯 + controller_id 宣告比對 | 早期（P4 Registry 配套） |
| `heartbeat_correlation_scanner` | Registry 定時計算 heartbeat 時間序列 cross-correlation，flagging pair 進入 watch list | 中期 |
| `behavior_bundle_similarity` | capability card 文本 embedding（Sentence-BERT 或等效）+ cosine sim 矩陣，batch 計算 | 中期 |
| `mutual_review_detector` | 評審圖中找互評對 + 計分分布異常 | 後期（需要足夠評審密度） |

T4（網路指紋）**不進 MVP**：雲端環境信噪比不足，實作成本高，投資報酬比差。

T5 CIB 融合：Layer 3 的完整實作留 post-MVP，MVP 用 Layer 0–2 的串行篩選替代。

---

## 4. 關鍵設計張力與誠實說明

### 張力 1：偵測精度 vs 偽陽性代價

即使是 Pacheco AUC ≈ 0.91 的最佳模型，在大規模網路中仍會對正常 vacant 誤判。Vacant 的設計選擇（suspected = 降權不封鎖 + challenge 機制）是正確的取捨：降低誤傷的不可逆性。

### 張力 2：去中心化 vs 計算集中

T1/T2/T5 都需要全域視角（評審圖、全局 heartbeat 序列）。MVP 單一 Registry 可做；聯邦化後需要 gossip protocol 傳播圖狀態，或接受每個 Registry 只偵測自己範圍內的 same-controller（跨 Registry 的同源偵測有盲區）。

### 張力 3：Base model 相似性的噪音

1000 個 Llama 3 70B 的輸出天生高度相似，T3 必須做 within-model baseline normalization 才不會把所有 Llama vacant 都標為 same-controller。這個 baseline 需要網路有足夠 single-controller Llama 樣本才能估計——又是另一個冷啟動問題。

### 張力 4：攻擊者可以閱讀這份文件

閾值公開 → 攻擊者調整 heartbeat jitter、引入刻意不同的 prompt style、避免互評。這不是理由隱藏閾值（security through obscurity 無效），而是提醒閾值應定期更新，且多訊號融合讓模仿全部訊號的成本高於收益。

---

## 5. 參考文獻

| 縮寫 | 全文引用 |
|---|---|
| SybilLimit | Yu, H., Kaminsky, M., Gibbons, P. B., & Flaxman, A. (2008). SybilLimit: A near-optimal social network defense against sybil attacks. IEEE S&P 2008. |
| SybilRank | Cao, Q., Sirivianos, M., Yang, X., & Pregueiro, T. (2012). Aiding the detection of fake accounts in large scale social online services. NSDI 2012. |
| DeBot | Chavoshi, N., Hamooni, H., & Mueen, A. (2016). DeBot: Twitter bot detection via temporal patterns. ICDM 2016. |
| SocialFingerprint | Cresci, S., Di Pietro, R., Petrocchi, M., Spognardi, A., & Tesconi, M. (2018). Social fingerprinting: Detection of spambot groups through DNA-inspired behavioral modeling. IEEE TDSC 15(4). |
| AuthNeuralText | Uchendu, A., Le, T., Shu, K., & Lee, D. (2020). Authorship attribution for neural text generation. EMNLP 2020. |
| Watermark | Kirchenbauer, J., Geiping, J., Wen, Y., Kautz, J., Miers, I., & Goldstein, T. (2023). A watermark for large language models. ICML 2023. arXiv:2301.10226 |
| Pacheco2021 | Pacheco, D., Hui, P. M., Torres-Lugo, C., Truong, B. T., Flammini, A., & Menczer, F. (2021). Uncovering coordinated networks on social media. ICWSM 2021. arXiv:2001.05658 |
| Nizzoli2021 | Nizzoli, L., Tardelli, S., Avvenuti, M., Cresci, S., & Tesconi, M. (2021). Coordinated behavior on social media in 2019 UK general election. ACM WebSci 2021. |
| ClockSkew | Kohno, T., Broido, A., & Claffy, K. C. (2005). Remote physical device fingerprinting. IEEE S&P 2005. |
| Botometer | Varol, O., Ferrara, E., Davis, C. A., Menczer, F., & Flammini, A. (2017). Online human-bot interactions: Detection, estimation, and characterization. ICWSM 2017. |
| SybilSCAR | Wang, B., Zhang, L., & Gong, N. Z. (2017). SybilSCAR: Sybil detection in online social networks via local rule-based propagation. IEEE INFOCOM 2017. arXiv:1803.04321 |
| BotShape | Wu, J., Ye, X., & Mou, C. (2023). BotShape: A novel social bots detection approach via behavioral patterns. arXiv:2303.10214 |
| SYSML | Maneriker, P., He, Y., & Parthasarathy, S. (2021). SYSML: StYlometry with structure and multitask learning: implications for darknet forum migrant analysis. EMNLP 2021. arXiv:2104.00764 |
| CIOBitcoin | Meiklejohn, S., et al. (2013). A fistful of Bitcoins: Characterizing payments among men with no names. IMC 2013. |
| MoserNarayanan | Möser, M., & Narayanan, A. (2022). Resurrecting address clustering in Bitcoin. Financial Cryptography 2022. arXiv:2107.05749 |
| GNNCoord | Sharma, K., et al. (2022). Characterizing the spread of coordinated and inauthentic behavior during the 2020 US elections. arXiv:2204.08140 |

---

*文件版本：T5 v1 · 2026-05-01 · P5-composite pane*  
*依賴：P3（reputation 儲存）、P4（Registry capability card + controller_id 欄位設計）*
