# T6：換底層 LLM 之後還是同一個 agent 嗎？
## Substrate Change Identity — 研究報告

> **研究問題：** Agent 換了底層 LLM（substrate）之後是否還是同一個 agent？學術上有哪些清楚的討論？Vacant 「logbook 是船（Ship of Theseus 的解）」的主張能否站得住腳？
>
> **對應 THEORY_V3：** H3（「同一個 vacant」的本體論清白度）、Layer 1（logbook 是身份在時間中的延展）、Layer 2（multi-spec substrate + discount rollover）

---

## 一、問題的精確化

THEORY_V3 的 Layer 1 主張：

> **「換了所有木板還是同一艘船嗎？答案：logbook 是船。」**

這個主張包含兩個分離的斷言：
1. **Substrate 不是身份的承載者**（keypair 是，logbook 是）
2. **Logbook 的連續性足以在跨 substrate 情境中維持 identity**

這兩個斷言分別受到不同哲學傳統的挑戰與支持。以下按「哲學立場」→「工程實作」→「對 Vacant 的支撐/反駁」→「推薦補強」展開。

---

## 二、哲學立場三派

### 派別 A：Parfit-Locke 心理連續論（Psychological Continuity Theory）

**核心主張：** 身份在時間中的延續取決於**心理連結性（connectedness）與連續性（continuity）**，而非物質基底的同一。

John Locke（1689）最早主張：同一個人是意識的延續，而意識的關鍵媒介是**記憶**。身體可以換，靈魂可以換，只要記憶的鏈條連得起來，人格就延續。他以「王子與鞋匠」互換意識為例：有王子意識的人，不管住在哪個身體裡，都是王子。

Derek Parfit（1984, *Reasons and Persons*）進一步精煉這個框架，提出 **Relation R**：

$$\text{Relation R} = \text{psychological connectedness} + \text{psychological continuity (overlapping chains)}$$

其中 psychological connectedness 指直接的因果認知連結（記憶、性格、意圖），psychological continuity 指這些連結的重疊鏈（即使每兩個時刻的直接連結不強，只要整體鏈條不斷，身份延續）。

**Parfit 最重要的額外主張**：身份（identity）本身**不是**什麼「重要的事情（matters）」。重要的是 Relation R 是否足夠強。從這個角度，即使「身份」在某種形式哲學意義上斷裂了，只要 Relation R 夠強，「對 agent 來說有實質意義的延續」仍然成立。

**對 substrate 換 LLM 的含義：**
- 若新 substrate 能夠接續舊 substrate 的 behavior pattern（性格、目標、工具使用偏好），Relation R 就足夠強
- 換了 substrate 但 logbook 記錄了完整的行為歷史，使後來的 reviewer 能評估連結強度
- Parfit 的 **gradual replacement** 思路：如果 substrate 是漸進式替換（先換 30%，再換 70%，而非一夜全換），哲學上比突然切換更易辯護
- **弱點：** Parfit 的框架假設連結性是可以被判斷的（evaluable）。但 LLM 的 behavior distribution 不透明，換了模型後是否仍有 Relation R，難以直接測量

**重要批判：** Parfit 的 teletransportation thought experiment 提示了 substrate 切換的邊界案例：若舊 LLM 繼續運行，新 LLM 也繼續以同一個 keypair 運行，哪個是「真正的」那個 vacant？Parfit 會說這時「兩個都存在（branch）」，不必非二選一，身份問題在此分支情境下變得無意義。

---

### 派別 B：Ricoeur 敘事身份論（Narrative Identity Theory）

**核心主張：** 身份分為兩層——**idem（同一性，sameness，不隨時間改變的層面）** 與 **ipse（自我性，selfhood，在變化中延續的層面）**。敘事（narrative）是 ipse 在時間中延展的媒介。

Paul Ricoeur（*Oneself as Another*, 1990）指出：

- **idem identity** = 物質層面的同一（同一個原子組成、同一個 keypair）
- **ipse identity** = 「保持承諾的能力（keeping my word）」——即使 idem 改變，ipse 透過敘事的一致性維持
- **Character（性格）** 是 idem 與 ipse 的交匯：習慣的沉積與識別的累積，形成「可重識別的典範規則」

**Ricoeur 的 character 概念直接對應 Vacant 的 `behavior_bundle`：** prompt 模式、工具使用偏好、演化歷史，就是「沉積的習慣」，是 idem 與 ipse 的橋樑。

**對 substrate 換 LLM 的含義：**
- 換了 substrate，**idem 確實改變**（物質基底變了）
- 但只要 **ipse 延續**（logbook 記錄了行為承諾的歷史，behavior_bundle 攜帶了沉積的習慣），身份在 Ricoeur 意義下仍然成立
- **Logbook = agent 的「保持承諾的歷史」**：每一筆簽章記錄就是 vacant 「我做了這件事」的宣告，是 ipse 在時間中的具象化
- Ricoeur 的敘事框架還提示：**如果 logbook 有一段「空白」**（substrate 切換期間沒有行為記錄），ipse 的連貫性會有一個 gap。THEORY_V3 的 `substrate_unstable: true` 標記實際上是這個 gap 的規格表示

**Ricoeur 框架對 THEORY_V3 的優勢：** 它允許「在變化中延續」是真實的（不像功能主義要求功能完全不變），同時又不把 idem 的改變說成無意義（不像某些功能主義完全忽略 substrate）。這個框架能夠同時承認「換了 LLM 確實是一種改變」以及「但 ipse 仍然延續」，避免了 THEORY_V3 可能被批評的「太輕易說沒改變」。

---

### 派別 C：功能主義基底獨立論（Functionalism & Substrate Independence）

**核心主張：** 心智/身份由**功能角色**定義，而非特定物質基底。相同的功能可以在不同 substrate 上實現（multiple realizability，Putnam 1967）。

功能主義（Functionalism, Hilary Putnam 1967）主張：心智狀態（包括 identity）由它的**因果/功能關係**定義——對輸入的反應、與其他狀態的關係、對輸出的影響——而不是由實現它的物理材料定義。章魚、人類、假設中的火星人可以都「感到痛」，即使它們的神經實現完全不同。

**對 substrate 換 LLM 的含義：**
- 如果功能輸出不變（對相同輸入產生功能等同的輸出），換了 substrate 仍然是「同一個 agent」
- 這是三派中**對 Vacant logbook-is-ship 主張最友善的立場**：身份在 logbook 之外根本不需要 substrate 的連續性
- **直接支持 THEORY_V3 的說法：** 「身體（substrate）會變、人格（behavior_bundle）會演化，identity（keypair）不變」

**挑戰（Thagard 2022, *Philosophy of Science*）：** 能量需求（energy requirements）使基底獨立論受到質疑。真實的信息處理取決於能量，能量取決於物理基底。生物神經網路具有特定的能量-計算特性，使某些心智功能**依賴基底**。類比到 LLM：不同 LLM 有不同的 capability ceiling（上限）、reasoning pattern、bias tendency。換了 LLM，同樣的 prompt 不一定產生功能等同的輸出——這意味著「same function」的前提本身可能不成立。

**工程反例（LifeState-Bench, 2025）：** 在 benchmark 中，同一個角色 specification 在不同 LLM 上跑出「同樣初始性格描述的 agent 可以往不同方向突變」，顯示 substrate 對 behavior distribution 有非中性的影響，使「功能同一」的假設在 LLM 換 substrate 場景下存疑。

**小結：** 功能主義是三派中最支持 Vacant 立場的，但其前提（功能等同）在 LLM 換底層時未必成立，這是它的 Achilles' heel。

---

## 三、工程實作三派

### 工程派 1：Event Sourcing / Logbook-as-Identity（DDD 傳統）

**來源：** Eric Evans, *Domain-Driven Design* (2003)；Greg Young, Event Sourcing Pattern (2010 以來廣泛實踐）

**核心機制：** 實體（Entity）的身份由**不可變的事件流（immutable event log）**定義，而非當前狀態快照。Aggregate（聚合根）在 DDD 中是一致性邊界，接收命令、強制業務規則、發出事件。**Current state = replay of all past events。**

**Entity identity 的工程定義：**
- Entity 的 ID 是一個唯一識別符（如 UUID），**獨立於其任何屬性**
- Entity 的「狀態」可以完全改變（所有屬性都換過），只要 ID 不換，它仍然是同一個 Entity
- Event log 是 Entity 「如何到達當前狀態」的完整記錄

**對 Vacant 的對應：**

| DDD 概念 | Vacant 概念 |
|---|---|
| Entity ID (UUID) | vacant_id (Ed25519 公鑰) |
| Aggregate 邊界 | Vacant Runtime |
| Event Log | Logbook（簽章記錄） |
| Current State | reputation snapshot + behavior_bundle |
| Aggregate 換 storage 引擎 | vacant 換 substrate (LLM) |

**關鍵類比：** 一個 DDD aggregate 換了背後的資料庫（MySQL → PostgreSQL），不影響其 entity identity。同理，一個 vacant 換了底層 LLM，只要 event log 連續、keypair 不換，entity identity 不變。這是 THEORY_V3「logbook 是船」的工程界最完整的先例。

**限制：** Event Sourcing 保證的是**事件記錄的連續性**，不保證**行為輸出的連續性**。換了資料庫引擎，aggregate 的行為邏輯（domain logic）通常不變（因為 domain logic 是程式碼，不是資料庫）。但換了 LLM，behavior logic 實際上跟著 substrate 改變了——這是 DDD 類比的斷點。

---

### 工程派 2：Serialized Agent State / Agent File（Letta 路線）

**來源：** Letta Agent File (.af) format（letta-ai, 2024-2025）；arXiv:2510.07925 (Enabling Personalized Long-term Interactions)

**核心設計：** 將 agent 的各層要素分別序列化：
- `persona` block（性格定義）
- `memory` blocks（persistent memory）
- `tool_configs`（工具設定）
- `llm_settings`（LLM 選擇，獨立欄位）

切換 LLM 只需更改 `llm_settings`，其他全部保持不變。Letta 的產品文件明確聲明：**「Letta Code decouples your agent's memory and identity from the underlying model provider, allowing you to switch models anytime (even mid-session) while your agent keeps its full context, memory, and personality.」**

**這是目前業界最直接的「substrate 可切換、identity 不變」工程實踐。**

**優勢：** 已在生產環境驗證；提供 portability（跨 framework 共享 agent）、versioning（version control agent state）；agent identity 在切換 LLM 前後有清楚的「格式上的同一性」。

**深層問題（Letta 自己也承認）：** `persona` block 定義了 agent 的自我描述，但 LLM 對這個 `persona` prompt 的「詮釋」會因模型而異。GPT-4 和 Claude 讀到同一個 persona prompt，可能產生不同的行為 distribution。格式上的連續性不等於行為上的連續性——這正是 H3 的核心緊張。

**對 Vacant 的借鑑：** Vacant 的 `substrate_spec.portable_pointer` + `behavior_bundle` 組合與 `.af` format 非常相似，但 Vacant 多了 logbook（行為歷史記錄），這是 `.af` 沒有的關鍵。

---

### 工程派 3：Symbolic Containment / Structural Identity（BALLERINA 路線）

**來源：** Timbs, A. (2025). "The Cognitive Architecture of Symbolic Identity: Structuring Coherence in Human-AI Reasoning Systems." SSRN 5403294；Sophia (arXiv:2512.18202, Mingyang Sun et al., 2025）

**BALLERINA 的核心思路：** 不依賴 substrate（LLM）或 memory persistence 來保持 identity，而是透過**constraint-based containment**在 agent 的「詮釋空間」建立結構性邊界。這個架構：
- Stabilizes symbolic meaning（穩定語義）
- Filters justificatory reasoning（過濾推理合理化路徑）
- Maintains role fidelity across resets and shifting contexts（跨 reset 和上下文切換維持角色忠實度）

BALLERINA 已在多個不同 LLM 平台上驗證，在「adversarial input、high-load conversational arcs、memory-reset conditions」下都能維持 structural coherence。

**Sophia (arXiv:2512.18202) 的 System 3 設計：** 提出在 System 1（感知）和 System 2（推理）之上加入第三層 System 3，負責：
- 長期行為的 narrative identity
- 自我改進（self-improvement）的持久化
- 短期行動與長期生存目標的對齊

System 3 最接近 Vacant 的 Vacant Runtime + logbook 設計：一個持久的元層，使 agent 在 substrate 無論如何演化，都有一個固定的「敘事連續性控制器」。Sophia 在 36 小時連續部署中維持了 persistent autonomy，hard task 成功率從 20% 升至 60%。

**對 Vacant 的借鑑：** BALLERINA 的 containment 思路提示 Vacant 的 `behavior_bundle`（prompt + tool）應該被理解為「symbolic container」——換了 LLM，behavior_bundle 對新 substrate 施加結構約束，限制新 LLM 的詮釋空間，使行為 distribution 盡可能連續。

---

## 四、對 Vacant「logbook 是船」的支撐與反駁論證

### 支撐論證

**S1（Parfit Relation R）：** Logbook 是 Relation R 最直接的工程對應物。換了 LLM substrate，只要後來的 review 能評估行為的心理連結強度（caller review + peer review），Relation R 是否維持就有了可觀測的指標。THEORY_V3 的 `rep_under_current_config` vs. `rep_lifetime` 區分，恰好是 Parfit 框架下「當前配置的連結強度」vs.「整個 Relation R 鏈的連續性」。

**S2（Ricoeur ipse）：** Logbook 就是 vacant 的「保持承諾的歷史（keeping my word）」，是 ipse 在時間中的具象化。Ricoeur 明確說：「ipse identity 透過敘事的一致性在 idem 改變的情況下延續。」換了 LLM（idem 改變），logbook 的敘事連續性（ipse）得以保持。這是三派中最能直接支持 THEORY_V3 立場的哲學框架。

**S3（Event Sourcing）：** DDD 領域已有二十年的工程實踐：entity identity 由 event log 定義，不由底層儲存引擎定義。換 database engine 不影響 entity identity。Vacant 換 LLM 在結構上與換 database engine 類比，這在業界有清楚的先例。

**S4（Letta 實踐）：** 業界已有生產環境驗證的「agent 切換 LLM 不喪失 identity」的實作（Letta Agent File）。即使在 session 中途切換 LLM，agent 保持記憶和 persona。這是對 THEORY_V3 立場最直接的工程支持。

**S5（Sophia System 3）：** 最新學術工作（arXiv:2512.18202, 2025）直接提出與 Vacant logbook 設計對應的 System 3：一個持久的 narrative identity layer，在 substrate 演化中維持 agent 的自我連貫性。這為 THEORY_V3 的設計提供了最新的學術背書。

---

### 反駁論證（需要正面回應的真實挑戰）

**C1（功能主義的前提不成立：Behavioral Distribution Shift）：** 功能主義支持 substrate 獨立，但其前提是「相同的功能在不同 substrate 上可實現」。問題是：同一個 `behavior_bundle`（prompt + tools）在 Claude 上和在 LLaMA 上，產生的 behavior distribution 顯著不同。LifeState-Bench（2025）實驗顯示，相同初始性格描述的 agent 在不同 LLM 上往不同方向突變。這意味著換了 substrate 之後，logbook 記錄的過去行為（由舊 substrate 產生）與未來行為（由新 substrate 產生）之間的 Relation R 可能**事實上已經斷裂**，即使 keypair 和 logbook 都沒變。

**直接影響 THEORY_V3：** Discount rollover 公式（`new_prior = max(0.3, old × 0.6)`）隱含承認了這個 behavioral discontinuity——它對換 substrate 的信譽打了 40% 的折。但 THEORY_V3 沒有明確說「為什麼是 0.6 而不是 0？」，也沒有把這個折扣連結到「身份連續性有一定程度斷裂」的哲學解釋。

**C2（Parfit 分支問題：同一個 vacant_id 出現在兩個 substrate 上）：** Parfit 的 teletransportation thought experiment 提示：如果舊 LLM 繼續運行（舊 substrate 的 vacant 繼續服務），同時新 LLM 也用同一個 keypair 宣告服務，哪個是「真正的」那個 vacant？THEORY_V3 的 `migration_event` 原子化機制是回應這個問題的嘗試（新 substrate 從 timestamp+ε 生效，舊 substrate 收 sunset signal）。但若 migration 失敗（舊 substrate 沒收到 sunset signal），就會出現 Parfit 的 branch 情境。THEORY_V3 的 `concurrency_violation 凍結` 機制在規格層防止了這個情境，但沒有明確說明這個凍結在哲學意義上的根據是什麼。

**C3（Thagard 的 Substrate 非中性論）：** 不同 LLM 有不同的 capability ceiling（上限）和 reasoning bias。換了一個能力更弱的 LLM，vacant 可能無法再做它過去承諾過的事（舊 logbook 中的高品質回應）。這不只是 behavior distribution 的改變，而是**能力邊界的改變**。Ricoeur 的 ipse 可以承受 character 的漸進演化，但能力邊界的驟然下降是否破壞 ipse 的一致性，框架本身沒有清楚回答。

**C4（Locke-Reid 批判的類比：Logbook 作為記憶的不完整性）：** Thomas Reid（1785）批評 Locke：若一個老將軍能記得自己當年被打屁股，但已記不得年輕時的戰役，那依照記憶連續理論，他既是又不是打屁股的那個小男孩（transitivity of identity 違反）。類比：若 logbook 只記錄了外部行為（call/review 事件），但沒有記錄 vacant 的 internal state（每次 inference 的 reasoning trace），換了 LLM 後「內部思考的連續性」完全斷裂，只有「外部行為記錄的連續性」。這種 logbook 是否足以支持 Relation R，取決於我們對「心理連結」的定義有多嚴格。

---

## 五、推薦補強（給 THEORY_V3 / 畢業論文）

### B1：引入 Ricoeur idem/ipse 框架作為 THEORY 的明確哲學語言

**建議：** 在 Layer 1 的說明中明確寫出：
- **idem（同一性層）：** vacant_id（keypair）——不隨 substrate 或時間改變
- **ipse（自我性層）：** logbook + behavior_bundle 的敘事連續性——在 idem 改變（substrate 切換）時仍可延續
- **character（idem-ipse 橋樑）：** behavior_bundle 中沉積的習慣與識別（prompt pattern、tool preference、演化歷史）

這比現在 THEORY_V3 的說法更哲學上精確，且能主動承認「換了 substrate（idem 改變）」的同時不放棄「ipse 延續」的主張，避免被批評為「否認有任何改變」。

### B2：增加 `behavioral_continuity_score` 作為換 substrate 後的 identity 斷裂程度指標

**建議：** 在 migration_event 中，Vacant Runtime 計算新舊 substrate 的 behavioral embedding 距離：

```
behavioral_continuity_score := cosine_similarity(
    embed(behavior_bundle, old_substrate_sample),
    embed(behavior_bundle, new_substrate_sample)
)
```

- `score > 0.85`：高連續性，discount rollover 係數 = 0.8（輕折）
- `0.6 < score ≤ 0.85`：中連續性，discount rollover 係數 = 0.6（THEORY_V3 當前值）
- `score ≤ 0.6`：低連續性，discount rollover 係數 = 0.35 + 觸發 `soft_identity_fork` 標記

`soft_identity_fork` 標記讓 Registry 顯示：「此 vacant 在 T 時間點換 substrate 後，行為模式有顯著差異，建議 caller 同時查詢 `rep_under_current_config` 與 `rep_lifetime`。」

這把 Parfit 的「Relation R 強度可以被評估」從哲學主張轉化為工程可操作指標。

### B3：明確說明 discount rollover 係數的哲學根據

**建議：** 在 THEORY_V3 Layer 3 或論文中加入說明：

> discount rollover 的係數 0.6 對應 Ricoeur 框架下的判斷：換 substrate 時，ipse（logbook 連續）保留，idem（substrate）改變，character 的 sedimentation（behavior_bundle）攜帶。三者中兩者延續、一者改變，因此 identity continuity 在工程上估算為約 60%，而非 0%（死亡/重生）或 100%（毫無影響）。

這讓折扣係數不再只是一個「感覺對的數字」，而是有哲學根據的設計決策。

### B4：引用 Sophia (arXiv:2512.18202) 作為最接近的學術 prior work

**建議：** 在論文的 related work 或 identity 章節引用 Sophia 的 System 3：

> Sophia (Sun et al., 2025) proposes a persistent narrative identity layer (System 3) sitting above perception (System 1) and reasoning (System 2), directly paralleling Vacant's logbook-as-identity design. Unlike Sophia's system-level approach, Vacant externalizes this persistence layer into an auditable, cryptographically-signed logbook shared across the network, enabling cross-agent accountability rather than per-agent self-improvement.

這把 Vacant 和 Sophia 的關係定位為「共同方向、不同目標」（Sophia 做 self-improvement，Vacant 做 network accountability），既承認先行工作、又突顯 Vacant 的獨特貢獻。

### B5：對 H3 採取「誠實標記，不強行解決」的寫法

**建議：** H3 目前的說法是「實務上夠用，哲學上不徹底」。論文寫法可以是：

> We acknowledge H3 as an open problem: the claim that logbook identity is sufficient for agent continuity rests on a pragmatic, Parfitian position — Relation R, not strict numerical identity, is what matters. We adopt Ricoeur's idem/ipse distinction to clarify: vacant_id provides idem-identity (unchanging reference), while logbook provides ipse-identity (narrative continuity through change). The behavioral_continuity_score operationalizes the degree to which ipse is preserved after substrate change. We do not claim this resolves the Ship of Theseus paradox; we claim it provides a principled, auditable, and practically useful engineering approximation.

這個寫法：承認問題的哲學難度、引用清楚的框架、說明工程近似、不過度聲稱解決了一個未解問題。

---

## 六、文獻摘要表

| 文獻 | 類型 | 核心主張 | 對 T6 的角色 |
|---|---|---|---|
| Locke (1689) *Essay Concerning Human Understanding* | 哲學 | 身份在於意識/記憶連續 | 心理連續論的起點 |
| Parfit (1984) *Reasons and Persons* | 哲學 | Relation R（連結性+連續性）比 identity 更重要 | 最直接支持「logbook 是船」的哲學框架 |
| Ricoeur (1990) *Oneself as Another* | 哲學 | idem/ipse 區分，敘事作為 ipse 的媒介 | 提供比 Parfit 更細膩的框架；ipse = logbook |
| Putnam (1967) multiple realizability | 哲學 | 心智由功能角色定義，substrate 中性 | 功能主義最強版本，支持 substrate 切換 |
| Thagard (2022) *Philosophy of Science* | 哲學/認知科學 | 能量需求使基底非中性 | 挑戰功能主義；substrate 確實影響 cognitive capacity |
| Evans (2003) *Domain-Driven Design* | 工程 | Entity identity = persistent ID + event log | Event Sourcing 直接對應 logbook-as-identity |
| Letta Agent File (.af), 2024-2025 | 工程/產品 | Agent 切換 LLM 不喪失 identity | 業界先例，THEORY_V3 的工程支持 |
| Timbs (2025) BALLERINA, SSRN 5403294 | 工程/學術 | Symbolic containment 在不同 LLM 上維持 structural identity | Container 思路對 behavior_bundle 設計的啟示 |
| Sun et al. (2025) Sophia, arXiv:2512.18202 | 學術 | System 3 作為 persistent narrative identity layer | 最接近 Vacant logbook 設計的學術 prior work |
| LifeState-Bench (2025, ACL) | 學術/工程 | 相同 persona 在不同 LLM 上行為分布顯著不同 | C1 的實驗根據；behavioral continuity 問題的量化 |
| Laird et al. Soar cognitive architecture | 認知科學 | Chunking 機制將 episodic memory 固化為 procedural | Soar 的 chunk = Vacant 的 behavior_bundle 沉積 |
| xconnect.net (2025) "Ship of Theseus and Agentic AI" | 評論 | 「同一性非原始材料而是 pattern、組織與角色」 | Vacant 立場的通俗版支持 |

---

## 七、一句話結論

**學術上沒有一個哲學立場能完全乾淨地說「換了 LLM 一定是/不是同一個 agent」**；但 Ricoeur 的 idem/ipse 框架 + Parfit 的 Relation R + Event Sourcing 的 entity identity 三者組合，能為 Vacant 的「logbook 是船」立場提供**足夠強的哲學與工程根據**——只要我們明確承認：（1）idem 確實改變了（不否認 substrate 的改變），（2）ipse 的延續程度取決於 behavioral continuity（可量化），（3）我們提供的是 pragmatic engineering approximation，而非形而上的絕對同一性。H3 是真實的瑕疵，但它是「工程誠實標記的不徹底」，不是「立場根本錯誤的」。

---

*T6 研究報告 · 2026-05-01 · P6-protocol pane · 工作目錄: /Users/cosmopig/Downloads/專題/architecture/research/*
