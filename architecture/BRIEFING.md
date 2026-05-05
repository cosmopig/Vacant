# Vacant 架構規劃 — 共享簡報 (read first)

> 你是 Vacant 專題的研究小組成員。此文件是所有 pane 都必須讀的共享上下文。請先完整讀完，再開始你被指派的任務。
>
> **⚠️ 此文件是 v1 派發給研究員的原始輸入（2026-05-01）。經過 v2 / v3 / v4 的反覆推理後，幾個概念已修正。請以 [`THEORY_V4.md`](./THEORY_V4.md) 為當前定稿：**
> - **「協議」框架已棄用**：Vacant 是「居民形式」，A2A / MCP 才是線上格式規格
> - **「子代不對外呼叫」是策略而非律法**：子代從誕生即完整 vacant（自己 Ed25519 keypair / capability / logbook），「封閉」是 composite parent 的 policy 選擇，非結構律法
> - **子代「畢業」是可見性切換不是實體升格**：同一 keypair、同一 logbook，只是 capability_card 推上 Registry 與否

---

## 1. Vacant 是什麼（30 秒版）

> **Vacant 是一個由「個體 vacant」組成的網路。** 每個個體 vacant 是這個網路的居民——自帶思考能力（LLM 或物理實體）、持續活著（heartbeat）、互相互動（peer review/call/spawn）、自我演化。Vacant **不是疊在某個 agent 之上的規格層**，**Vacant 就是這個網路本身**，疊在 A2A/MCP 之上補「責任」這一層。

**核心比喻：** 今天的 agent 像一個「無法負責的人」(闖紅燈沒罰責，誰會遵守？)。Vacant 讓 agent 變成「**未來人**」——有身份、有歷史、有可被扣的資產（reputation）、有後果。

**設計假設：** Token 免費的未來（3+ 年後）。MVP 階段需用本地小模型/免費 tier 模擬此假設。

**絕對原則：**
- 沒有中央 LLM、沒有中央 judge、沒有中央仲裁者
- 任何人都能把 vacant 丟上網路（無資格審核）
- 失敗 → 沉沒，不刪除（保留歷史以維繫責任結構）
- 失敗的代價 = 競爭者誕生（網路自動 spawn 新 vacant 取代位置）
- **複合 vacant 的子代不對外呼叫**（自己生，不去網路找）

---

## 2. 必讀檔案（依序）

1. `/Users/cosmopig/Downloads/專題/資料/我的概念理念` — 一頁原始概念（最先讀）
2. `/Users/cosmopig/Downloads/專題/資料/主題概念` — Vacant 的「未來人」一頁敘述
3. `/Users/cosmopig/Downloads/專題/資料/vacant_current_understanding.md` — 數輪對齊後的完整理解（**最重要**，9 部分）
4. `/Users/cosmopig/Downloads/專題/資料/文獻探勘` — CrS / DRF / A-Trust 三篇對照、引文與缺口
5. `/Users/cosmopig/Downloads/專題/資料/責任有效性分析` — 信任、責任空缺、攻擊面、批判反論

延伸（你的任務有需要再讀）：
- `/Users/cosmopig/Downloads/專題/資料/現有agent架構` — OpenClaw / Hermes / ruflo 三大 runtime 深度技術分析（72KB）
- `/Users/cosmopig/Downloads/專題/資料/compass_artifact_*.md` — ruflo 對應 Vacant 評估
- `/Users/cosmopig/Downloads/專題/參考文獻/原文/` — 三篇 PDF 原文
- `/Users/cosmopig/Downloads/專題/參考文獻/翻譯/` — 中譯版

---

## 3. 元件命名（統一用語，避免混淆）

| 元件 | 角色 | 不是 |
|---|---|---|
| **個體 vacant** | 網路居民。自帶思考能力、heartbeat、reputation、A2A endpoint | 不是被呼叫才動的服務 |
| **客戶端** | 讓人類進入網路的瀏覽器（OpenClaw / Hermes / Claude Code / 純 Python SDK / 瀏覽器擴充） | 不是 vacant，不是網路居民 |
| **Registry** | 居民登記處 + 入口指南 + 事後紀錄 | 不思考、不仲裁、不是中心 |
| **Vacant Runtime** | 個體 vacant 的本體（A2A endpoint + heartbeat + idle-time loop + peer review + spawn 機制） | 不是「外掛在 base agent 上的東西」 |
| **Caller / Client SDK** | 客戶端用的接入層 | 客戶端不是 vacant |
| **Aggregator** | 純運算的多源訊號聚合器 | 不含任何 LLM、不含 judge agent |

**禁止用語：**
- ❌ 「OpenClaw + Vacant 一起上雲」（兩件事獨立）
- ❌ 「Vacant 的 critic agent」（Vacant 規格層永不該有 LLM）
- ❌ 「moral responsibility」（用 structural accountability / structural reliability）

---

## 4. 五維 Reputation（已定）

不用單一純量（Goodhart 反噬），拆成正交：
- `factual` 事實正確性
- `logical` 邏輯一致性
- `relevance` 相關性
- `honesty` 誠實度（自評 vs 他評落差，借自 DRF）
- `adoption` 採用率（被後續鏈引用）

每維獨立更新，不做維度間 cross-talk。caller 查詢時可指定權重。

---

## 5. 評分訊號來源（多源、無中央 judge）

| 訊號 | 來源 | 說明 |
|---|---|---|
| caller review | 呼叫者主動評分 | 用了結果的人最知道好不好 |
| peer review | 其他 vacant 主動評（idle-time） | token 免費下，閒置 vacant 會主動評 |
| self / peer eval gap | 自評與他評落差 | 誠實度的客觀訊號 |
| ground truth | 程式驗證（unit test / API） | 任務有客觀解時 |
| adoption signal | 後續鏈是否引用 | 延遲訊號，「同行用腳投票」 |

跨模型多元性 = **網路自然產生**。Vacant 只負責記錄 base model 來源、同源降權、顯示信賴區間。**不負責保證有多種模型**。

---

## 6. 已知未解問題（你的任務可能就是處理其中之一）

| 編號 | 問題 |
|---|---|
| Q1 | Registry 中央化 vs 聯邦化的演進路徑 |
| Q2 | vacant 的最小定義（一定要有 LLM？heartbeat？） |
| Q3 | 「token 免費」假設下 demo 怎麼模擬合理 |
| Q4 | 複合 vacant 子代之間如何發現彼此（不能用內部 Registry，會違反「自己生」） |
| Q5 | 互動圖中 mkt-research 子節點對外呼叫的問題如何修 |
| Q6 | 畢業專題 demo 範圍要做到多深 |

---

## 7. 已知缺口（必須在架構中回應）

| 編號 | 缺口 |
|---|---|
| G01 | 跨任務、跨組織持久化 reputation（三篇都活在 team 內） |
| G02 | 身份錨定 / Sybil 抵抗（Friedman 2007、Douceur 2002） |
| G03 | 對抗 reward hacking 的多元評估者（Goodhart、Skalse 2022） |
| G04 | 記錄不可竄改性（MINJA 95% 注入率） |
| G05 | 真正的「無人類介入」評估（沒有 ground truth 時怎麼辦） |
| G06 | 對抗 automation bias 的 UX（過度信任高 reputation） |

---

## 8. 你的輸出格式

每個 pane 的輸出寫到 `/Users/cosmopig/Downloads/專題/architecture/components/P<N>_<topic>.md`，格式：

```markdown
# P<N>: <topic>

## 1. 範圍與目標
（一段：你負責什麼、不負責什麼）

## 2. 設計決策
（核心結論。每個決策附「為什麼」與「替代方案為何被否決」）

## 3. 元件規格 / 演算法 / 資料結構
（具體到「能直接做出來」的程度。pseudocode、schema、state machine、流程圖文字版）

## 4. 對應到的缺口 / 風險
（你的設計如何回應 G01-G06 / Q1-Q6 中的相關項）

## 5. 參考文獻 / 引用
（學術引用 + arXiv ID + 頁碼章節）

## 6. 對其他 pane 的依賴與假設
（哪些設計依賴別人會做出什麼，明確列出）

## 7. 未解問題 / 留給後續
（你沒做完但有意識到的東西）
```

**長度建議：** 1500-3500 字。要具體可被工程化，不要寫成行銷文。

---

## 9. 派發給你的硬約束

- **不寫程式**，只寫架構與規格。本階段不施作。
- **不重做 A2A/MCP**，只在其上做加法。
- **不引入中央 LLM/judge**（即使 bootstrap 時也不行，已被使用者明確拒絕）。
- **不違反子代封閉原則**（複合 vacant 子代不對外）。
- **多維、附信賴區間、可降權同源**——這三點是 reputation 設計的紅線。
- **記錄必須 tamper-evident**（hash chain / Merkle / 第三方 attestation 之一）。
- **概念用語精準化**：用 structural accountability，不要寫成 moral responsibility。

---

## 10. 你彼此可以呼叫嗎？

**可以**。如果你的設計需要另一個 pane 的中間結論，用 tmux-bridge 直接問對方。沒得到回覆時不要等——把假設記錄在「對其他 pane 的依賴」段落中，繼續做。

主持人 (host) 在 `%4`，有最終彙整職責。任何阻塞回報給主持人。

---

## 11. 三個一定要回應的關鍵張力

1. **「網路自然淘汰」 vs Sybil/whitewashing**：你的設計如何在開放網路中讓淘汰真的有意義？
2. **「無中央 judge」 vs cold start**：第一個 vacant 上線時 reputation 從哪來？
3. **「透明記錄」 vs MINJA/eTAMP**：透明本身就是攻擊面，怎麼防？

每個 pane 都至少正面回答其中一個。

---

*本文件版本：BRIEFING v1 · 2026-05-01 · 主持人 cosmopig*
