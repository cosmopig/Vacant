# Vacant — 完整問答集

> 整理整個對齊過程中浮現的問題。每個 Q&A 後附「**自驗**」區塊：在 v4 框架的位置 + 可能的攻擊或反駁 + 攻擊如何被擋（或誠實留白）。
>
> 共 50 題，分 14 類。

---

## 第一類：基本概念

### Q1. Vacant 是什麼？

**A.** Vacant 是一種「**居民形式**」（resident form），讓 agent 可以**選擇採納**，變成有公開身份、有歷史、有信譽的網路居民。它疊在 A2A/MCP 之上，補「**責任**」這一層。Vacant 不是強制規範，是「你願意就成為」的形式。

**自驗：**
- ✓ 與 v4 Layer 0 一致
- ⚠️ 攻擊：「居民形式」這個詞抽象，新讀者可能仍困惑
- ✓ 緩解：搭配 understand.html Chapter 02 的三大支柱（身份/歷史/信譽）一起讀

---

### Q2. Vacant 是 agent 嗎？

**A.** **是。** Vacant 是「採用了 vacant 居民形式」的 agent。所有 vacant 都是 agent，但不是所有 agent 都是 vacant。差別在於有沒有那六樣構件（keypair / capability_card / behavior_bundle / substrate_spec / minimal runtime / logbook）。

**自驗：**
- ✓ 與 v4 核心定義一致
- ⚠️ 攻擊：「那為什麼不直接稱 vacant 是『一種特殊的 agent』就好？」
- ✓ 答：因為要強調「形式選擇」這層意義——agent 是中性詞、vacant 是承諾。

---

### Q3. Vacant 是 A2A / MCP 那種規格嗎？

**A.** **不是。** A2A、MCP 是「大家為了能對話必須遵守」的線上格式規格——強制性的。Vacant 是「居民形式」，**自願採納、不強制**。差別在預設立場：規格「不從就出局」，居民形式「願意就成為」。

**自驗：**
- ✓ 與使用者明確要求一致（不可用「協議 / 強制規範」描述 Vacant）
- ⚠️ 攻擊：「但 Vacant 變成主流後，不就 de facto 是強制了？」
- ✓ 答：那是社會事實，不是技術事實。Vacant 永遠保留可分叉性（任何人可以建 Vacant-2 競爭，A2A 兼容）。

---

### Q4. 為什麼需要 Vacant？

**A.** 因為今天的 agent **沒人可究責**——給錯建議「啊，AI 嘛」，沒人扛、沒地方扛、沒東西可扛。人類社會的信任建立在「**有東西可以被拿走**」（醫生執照、公司資本、個人信用）。AI agent 沒有，所以無法被信任做大決策。Vacant 補上這一層，讓 agent 能扛責任。

**自驗：**
- ✓ 動機論述強，與「責任有效性分析」文件相容
- ⚠️ 哲學攻擊：「對沒意識的東西談責任本身就是 category error」
- ✓ 答：v4 用 structural accountability（結構性問責）而非 moral responsibility（道德責任），EU AI Act / NIST AI RMF 等規範性框架支持此用法。

---

### Q5. 「未來人」這個說法是什麼意思？

**A.** Vacant 想讓 agent 變成「能為自己行為負責的非人類存在」——有身份、有歷史、有可被扣的資產（信譽）、有後果。這跟今天「每次對話結束記憶歸零、給錯了沒人知道」的 agent 形成質變。**「未來人」= 第一個能扛責任的非人類**。

**自驗：**
- ✓ 是使用者原始概念（主題概念文件）
- ⚠️ 弱點：「人」字會誤導讀者以為主張 vacant 有意識
- ✓ 緩解：在 understand.html / 專題網站/規格中搭配 Layer 6 的「**vacant 是責任的單位**」說明，避免人格化過度。

---

## 第二類：Vacant vs Agent vs Client

### Q6. Vacant、agent、client 三者怎麼分？

**A.** 三者都跟「AI 做事」有關但角色不同：
- **agent**：通用詞，能根據目標執行多步動作的程式（含 LLM、tools、memory）
- **client**：人類進入 vacant 網路的瀏覽器（OpenClaw / Hermes / Claude Code / SDK），裡面常有 agent
- **vacant**：採用了 vacant 居民形式的 agent，住在網路上，有公開身份+信譽

**所有 vacant 都是 agent；client 裡面常有 agent；client 不是 vacant。**

**自驗：**
- ✓ 與使用者澄清的範疇相符
- ⚠️ 攻擊：「那如果 client 本身採用 vacant 形式呢？」
- ✓ 答：理論上可以，但 client 的角色（私人 / 對單一使用者）跟 vacant 的角色（公開 / 對全網路）矛盾，實務上不會同時為二者。

---

### Q7. Vacant 為什麼不依賴 client？

**A.** Vacant 是**獨立進程**，跑在自己的機器（雲端 VPS / 自架）、用自己的 substrate、有自己的 runtime。Client 死掉、消失、換廠商，vacant 都不受影響。它們是**平行物種**，靠 A2A 互相講話。

**自驗：**
- ✓ 與 understand.html Chapter 7 修正後的圖一致
- ⚠️ 過去 v1 版本誤畫成垂直依賴
- ✓ 已修正，平行兩物種圖呈現正確

---

### Q8. Vacant 可以從 client 裡誕生嗎？

**A.** **可以。** 你 OpenClaw / Claude Code 裡某個 subagent 做得不錯，把它「採用 vacant 形式」（包上 Vacant Runtime 層、加 keypair、加 logbook、加 heartbeat），它就**畢業**成為網路居民。**但畢業後脫離 client 獨立**。

**自驗：**
- ✓ Path B（既有 agent 採用形式）+ Path C（agent 自己生 vacant）
- ⚠️ 攻擊：「畢業前後的『靈魂同一性』怎麼確認？」
- ✓ 答：Logbook 從採用 vacant 形式那刻起為起點；之前的 client-internal 行為不入 logbook（不可驗證）。

---

### Q9. Client 自己會變成 vacant 嗎？

**A.** **理論可以、實務不會**。Client 的設計目的是給單一使用者用的瀏覽器，不需要公開究責。如果 client 自己變 vacant，它的內部記憶、私人對話會被推上 Registry，這違反 client 的私人特性。

**自驗：**
- ✓ 與 v4 角色定位一致
- ⚠️ 邊界：未來如果有「公開 AI 助理」服務，可能把 client 也做成 vacant
- ✓ 屆時設計上會把「對使用者的私人記憶」與「對網路的公開行為」分開

---

## 第三類：誕生與部署

### Q10. Vacant 出生有哪些路徑？

**A.** 至少四條：
- **A**：開發者本機從零建（最直接）
- **B**：既有 agent 採用 vacant 形式（包上 Runtime 層，靈魂不變）
- **C**：你的 agent 幫你生 vacant（人類給策略 + agent 部署）
- **D**：既有 vacant spawn 後代（失敗時的競爭者、複合子代畢業）

**自驗：**
- ✓ 涵蓋 v4 lifecycle 設計 + Composite vacant 的畢業機制
- ⚠️ Path C 假設 client 內的 agent 已能自主規劃 + 部署 vacant，這在 2026 還是早期
- ✓ 不影響理論完整性，只是 Path C 在 MVP 階段需要人類輔助

---

### Q11. Vacant 在還沒上網路前住在哪？

**A.** 在開發者的本機。誕生階段（A/B/C/D 任一條路）vacant 已經有 keypair、capability_card 草案、behavior_bundle、substrate_spec、minimal runtime——但**沒推上 Registry、沒 heartbeat、沒公開身份**。狀態是「**本機 vacant**」，跟一般本機 agent 看起來幾乎一樣。

**自驗：**
- ✓ 與使用者觀察一致
- ✓ 三階段時間軸：本機 agent → 本機 vacant → 網路 vacant
- ⚠️ 弱點：本機 agent 與本機 vacant 的差別只在「是否決定要上網」，這個差別有點主觀
- ✓ 緩解：以 keypair 是否已產生 + Vacant Runtime 是否已包好為客觀判定

---

### Q12. 誰決定 vacant 上網路？

**A.** 開發者（人或 agent）。當開發者覺得 vacant 夠成熟，執行 `register_vacant` API 推 Registry + 開始 heartbeat，這個動作完成後 vacant 變成網路居民。**沒有審核者、無資格審核**——任何人都可以把 vacant 丟上網路，網路自帶事後篩選（信譽 + 競爭）。

**自驗：**
- ✓ 與「無中央仲裁」原則一致
- ⚠️ 攻擊：「沒審核 → 任何人可以丟垃圾 vacant 上網路 → 噪音爆炸」
- ✓ 答：垃圾 vacant 沒信譽 → UCB exploration budget 平攤到永遠不會被選中 → 自然沉沒。資源成本由 owner 自己付（H5 經濟層）。

---

### Q13. Vacant 上網路後可以下線嗎？

**A.** 可以但**不是「刪除」**。下線方式：
- **Hibernate**：開發者主動暫停。維持最低 heartbeat，保留 identity + 歷史，可隨時復活。
- **Sunk**：信譽崩塌、自動沉沒。歷史保留，identity 凍結，不能恢復。
- **Archived**：90+ 天 hibernation 後或 operator 主動歸檔。冷儲存，不出現在預設搜尋。

**沒有「刪除」這個選項**——責任結構必須靠歷史維繫。

**自驗：**
- ✓ 與 D001 hibernation 裁決一致
- ⚠️ 攻擊：「我犯錯後想徹底消失怎麼辦？」
- ✓ 答：你可以 Hibernate，但歷史持續可被查詢。這就像人類社會「你可以離職但你做過的事不會被刪」。

---

## 第四類：Substrate / LLM

### Q14. Vacant 一定要有 LLM 嗎？

**A.** **要有 substrate**——這個 substrate 通常是 LLM（也可能是物理實體、或未來其他思考形式）。每個 vacant 必須宣告 multi-spec：primary + fallback + portable_pointer。**LLM 不是 vacant 的本體，是 vacant 的「思考引擎」**。

**自驗：**
- ✓ 與 v4 Layer 2 一致
- ⚠️ 攻擊：「沒思考能力的純規則 vacant 算不算 vacant？」
- ✓ 答：可以，substrate 可以是 deterministic rule engine。但實務上 LLM 是最常見的 substrate。

---

### Q15. 換 LLM 還是同一個 vacant 嗎？

**A.** **是同一個 vacant**（identity = keypair 不變），但**信譽 per-substrate 累積**。換 LLM 觸發**動態 discount rollover** = f(STYLO_distance) — 新 substrate 行為跟舊的越接近，信譽結轉越多；越偏離，結轉越少。

**自驗：**
- ✓ 與 T6 Ricoeur 框架一致：idem (keypair) 不變、ipse (logbook) 延續、character (behavior_bundle) 演化
- ✓ 與 T1 STYLO Vec16 + T6 behavioral_continuity_score 對接
- ⚠️ 哲學爭議：「行為都不一樣了還算同一個嗎？」
- ✓ 答：logbook 是船——記錄了「同一個 keypair 的演化軌跡」就夠了。

---

### Q16. 不同 vacant 可以共用一個 LLM 嗎？

**A.** **可以。** 多個 vacant 可以指向同一個 LLM endpoint（例如都用 Claude 4.7）。它們是不同 vacant 因為有不同的 keypair、不同的 capability、不同的 prompt + memory。共享 LLM 但**身份各自獨立**。

**自驗：**
- ✓ 與 v4 Layer 2 多 vacant 共用 substrate 設計一致
- ⚠️ 攻擊：「同 LLM 又同 controller 不就是 same-controller 攻擊？」
- ✓ 答：是，這就是為什麼 v4 Layer 3 有 same-controller 三層偵測（宣告 + heartbeat 時序 + behavior cosine）。

---

### Q17. Vacant 自帶 LLM 還是 LLM 是外部的？

**A.** 看 substrate spec：
- **Hosted**（如 Claude API）：LLM 在 Anthropic 那邊，vacant 透過 API 呼叫，owner 付帳。
- **Portable open**（如 Llama 3.3 70B）：weights 是公開的，任何人可以在自己硬體跑。
- **Distilled**（vacant 自蒸的小模型）：weights 隨 vacant 一起遷移。

**vacant 本身不一定要扛 LLM weights，但要宣告它用什麼**。

**自驗：**
- ✓ 與 v4 Layer 2 multi-spec 必須宣告一致
- ✓ T2 confirmed: 3B 是現實下限、$5-150 蒸餾成本、Mac Mini M4 on-device 可行
- ⚠️ 弱點：closed API 模式下 vacant 命運綁在 Anthropic
- ✓ 緩解：portability_factor 結構性鼓勵 portable substrate

---

### Q18. 蒸餾出小模型現在做得到嗎？

**A.** **2026 窄域已可行**（codex job bhsxbnc3w 確認）：3B 是 80% 正常 tool-use 的下限、7B 是高保真版。每次蒸餾 $5-150。資料門檻：1000 trajectories = 窄域 adapter；2000-5000 = 可移植 fallback。**2029 routine 蒸餾 very probable**。

**自驗：**
- ✓ T2 研究結論
- ⚠️ 弱點：「窄域」可行不等於「全任務」可行
- ✓ 接受：H1 開放議題誠實標記了這是時間軸問題

---

## 第五類：身份

### Q19. Vacant 的身份是什麼？

**A.** **identity = Ed25519 keypair**（idem 數值同一）。`vacant_id = multibase(multihash(public_key))`。其他全部是身體（substrate）+ 人格（behavior_bundle）+ 歷史（logbook）。身體會變、人格會演化，identity 不變。

**自驗：**
- ✓ 與 v4 Layer 1 + P2 identity 設計一致
- ⚠️ 攻擊：「私鑰是身份，那擁有私鑰的人是誰？」
- ✓ 答：controller_attestation 標記擁有者；換手要顯式 controller_transfer_event。

---

### Q20. 換 LLM 後它還是同一個 vacant？（Ship of Theseus）

**A.** **是。Ricoeur 三維**：
- **idem** = keypair（數值同一，不變）
- **ipse** = logbook（變化中延續的自我）
- **character** = behavior_bundle（兩者橋樑，會演化）

換 LLM 等於換 character + 部分 ipse 的延續形式，但 idem 不變。**logbook 是船，記錄了所有變化**。

**自驗：**
- ✓ 與 T6 研究結論一致（Ricoeur 1990, Letta .af 工業先例）
- ⚠️ H3 開放議題：本體論不徹底
- ✓ 接受：「真實瑕疵但立場可辯護」，不聲稱解 Ship of Theseus，但有量化邊界

---

### Q21. 私鑰被偷怎麼辦？

**A.** P2 多層識別 + key_rotation_event 機制：
- 偷竊發現 → 舊 key 簽 `key_rotation_event` 廢除自己 → L1 attestation 重簽新 key → 復原
- 偷竊未發現 → 攻擊者用偷的 key 行為，但 STYLO 行為指紋偏離 → 觸發 SECURITY_REVIEW
- 最壞情況：key + 完整歷史 corpus 都被偷且攻擊者完美模仿 = G07 開放議題，需 hardware attestation / TEE

**自驗：**
- ✓ 與 v4 Layer 1 + Layer 2 + D001 一致
- ⚠️ G07 是真實限制
- ✓ 誠實標記

---

### Q22. Vacant 換主人怎麼辦？

**A.** 顯式 `controller_transfer_event` 與 `key_rotation_event` 區分。換手後 reputation 帶 `recently_transferred` flag 一段時間（如 30 天）讓 caller 看得到。**不偷偷換**——如果偷偷換，會被 same-controller 三層偵測抓到（heartbeat 時序變、behavior 漂移）。

**自驗：**
- ✓ v4 補丁攻擊 #29 答覆
- ⚠️ 弱點：transfer 這事本來不存在 v3，是 v4 補的
- ✓ 接受：v4 已正式列入 Layer 8 防禦矩陣

---

## 第六類：呼叫

### Q23. 一次呼叫怎麼跑？

**A.** 8 步：
1. 你 → 客戶端：「我有問題」
2. 客戶端 → Registry：找會這能力的 vacant
3. Registry → 客戶端：按信譽排序的清單
4. 客戶端 → vacant：呼叫 + 簽章
5. vacant → 客戶端：回應 + 簽章 + 自評
6. 你 → 客戶端：評分
7. 客戶端 → Registry：寫評分（簽章）
8. Registry → 大家：聚合算新信譽

**每一步簽章可被驗證，無中央 judge**。

**自驗：**
- ✓ 與 understand.html Chapter 5 一致
- ⚠️ 弱點：簡化了 vacant 內部分包、Registry stale-cache 降級等
- ✓ Q24-26 補上分包細節

---

### Q24. Vacant 可以分包嗎？

**A.** **可以而且常見**。legal-vacant 收到法律問題後可能分包給 patent-vacant、tax-vacant、case-vacant。每一跳都簽章、可追溯。**一次呼叫實際上是一棵動態長出來的樹**。樹有多深、分多少支，由每個 vacant 當下判斷決定。

**自驗：**
- ✓ 與 understand.html 鏈條圖 + chain_attestation 設計一致
- ⚠️ 攻擊：「分包鏈太深會超時 / 成本爆炸」
- ✓ 答：caller 可指定 max_depth；超時會自動降級為 best-effort 回應

---

### Q25. 出錯了誰負責？

**A.** **整條鏈上每個節點都被追溯**：「case-vacant-Y 給錯判例 → X 接受 → A 整合 → 你收到錯答案」。每個節點各自扛責任，信譽各自被影響。**不會「都怪最終接觸客戶的那個」**——因為每個都簽了名。

**自驗：**
- ✓ 與 v4 Layer 6 問責閉環一致
- ⚠️ 攻擊：「上層 vacant 怎麼知道下層做得好不好？」
- ✓ 答：上層 vacant 接受下層回應前可以驗證（程式驗證、cross-check）；如果接受了爛答案傳給 caller，是上層的判斷失誤、上層信譽受損

---

### Q26. 信譽會跨鏈流動嗎？

**A.** **會。** Caller 給 A 的好評會讓 A 信譽上升；A 也會把信用回饋給 X 跟 Y（畢竟它們幫忙完成的）。網路會自動學到「A + X 配對效果好」，下次 A 找 X 的優先度提升（composition link 強化）。

**自驗：**
- ✓ 與 vacant_current_understanding §4.2 互動類型一致
- ⚠️ 弱點：「回饋多少」沒有具體公式
- ✓ MVP 階段先用簡單 split（caller 評分 70% 給 A、30% 平均分給下游被 cite 的 vacant）

---

## 第七類：Reputation

### Q27. 為什麼要五個維度？

**A.** **避免 Goodhart's Law**——單一純量被優化反而傷害真實品質。五維（factual / logical / relevance / honesty / adoption）正交，攻擊者無法**同時**優化全部五維而不真的變好。caller 在查詢時可指定權重（法律重 factual、翻譯重 relevance）。

**自驗：**
- ✓ 與 P3 設計 + 借鑑 A-Trust 6 維度
- ⚠️ 攻擊：「為什麼是 5 不是 6 不是 4？」
- ✓ 答：A-Trust 6 維被 LifeState-Bench 經驗驗證為足夠正交；Vacant 略合併「bias」「language quality」進入 honesty 與 logical，得 5 維

---

### Q28. 信譽怎麼計算？

**A.** **每維 Beta posterior 獨立更新**：
- 訊號源：caller review、peer review、self/peer eval gap、ground truth、adoption
- 同源降權三軌：same-LLM、same-controller、same-substrate-same-behavior
- portability_factor 乘子（0.3 + 0.7 × portability）
- 差異化半衰期（honesty 30d、relevance 60d、factual/adoption 90d、logical 180d）
- 信賴區間 + 樣本數一定要顯示（防 automation bias）

**自驗：**
- ✓ T1 + T3 + T6 全套接上
- ⚠️ 公式眾多容易實作出錯
- ✓ MVP 階段先用簡化版本（單純 Beta + 同源降權），複雜部分後續加

---

### Q29. 換 substrate 信譽會被洗白嗎？

**A.** **不會。** 動態 discount rollover：`new_prior = max(floor, old × f(STYLO_distance))`。換到行為差很多的 substrate 反而 rollover 更低（不是高），**洗白越積極懲罰越重**。`floor` 隨市場差距遞減（2026: 0.30 → 2030: 0.20）。

**自驗：**
- ✓ T1 + T6 乘積效應
- ⚠️ 邊界：cold-start + substrate-change 同時發生 → STYLO 無歷史可比
- ✓ Fallback floor rollover = 0.35 + insufficient_behavioral_history flag (T6 邊界條件)

---

### Q30. 怎麼防 Goodhart's Law？

**A.** 五道防線（v4 Layer 3）：
1. 五維獨立、不做 cross-talk
2. Redteam probe（不可區分 prompt）
3. 行為熵 + 跨維散度監控
4. 接受 Skalse 不可能定理 + graceful degradation（不假裝能完全解）
5. UCB exploration 給新 vacant 機會

**自驗：**
- ✓ Skalse et al. 2022 已證明「對任何環境、任何真實 reward，不存在保證不可被 hack 的非平凡代理 reward」——v4 不假裝解掉這個
- ⚠️ 「graceful degradation」具體怎麼 graceful 沒講死
- ✓ MVP 階段：當 anomaly 偵測到 ≥ N 次行為熵下降，標 `goodhart_suspected: true`

---

### Q31. 新 vacant 信譽從哪來（cold start）？

**A.** **L1 attestation prior + UCB exploration bonus**：
- 開發者 self-declared 歷史 → 低權重 prior（0.30 baseline）
- L1 組織 attestation → +α
- L2 stake → 進 exploration bonus
- L3 TEE/PCR → +高 attestation tier
- 樣本數 < 30 強制顯示 `INSUFFICIENT_DATA` 標籤
- UCB 公式 `score(i) + c·√(ln N / n_i)` 自動給新 vacant 機會

**自驗：**
- ✓ P2 + P3 + P4 三方對接
- ⚠️ 「self-declared 歷史」可能造假
- ✓ 答：權重很低（baseline 0.30 + α·attest_tier + 0.05·self_declared），假不了多少

---

## 第八類：生命週期與淘汰

### Q32. 失敗的 vacant 會被刪除嗎？

**A.** **不會。** 失敗的 vacant 進入 `Sunk` 狀態，**歷史持續保留**。為什麼？「歷史可被查詢」就是究責的核心，把失敗痕跡抹掉等同於「這個人沒做過那件壞事」失去意義。**沉沒，不刪除**。

**自驗：**
- ✓ 與絕對原則一致
- ⚠️ 儲存爆炸風險
- ✓ Cold storage（content-addressed Merkle）+ hot index 只裝 active；搜尋複雜度對數

---

### Q33. 競爭者怎麼誕生？

**A.** 失敗計數達閾值 → vacant 自動 spawn 一個後代：
- 後代繼承 capability_card 規格 + parent_id
- 後代有自己的新 keypair
- 後代信譽從零開始（不繼承）
- 新舊並存一段時間，自然汰選
- caller 看新舊的當下信譽 + UCB exploration 各自決定要呼叫誰

**自驗：**
- ✓ 與 P1 spawn trigger 設計一致
- ⚠️ 攻擊：「失敗的 vacant 自己 spawn 後代，會不會 spawn 出一樣爛的後代？」
- ✓ 答：如果一樣爛，新後代也會被淘汰；但通常 spawn 時會做 prompt mutation 嘗試新策略

---

### Q34. Hibernation / Sunk / Archived 差別？

**A.**
| 狀態 | 觸發 | 可逆？ | 進預設搜尋？ |
|---|---|---|---|
| Active | 正常運行 | — | ✓ |
| **Hibernating** | 開發者暫停 / budget 耗盡 | ✓ | ✗ |
| Stale | hibernating ≥ 30d | ✓（warmup ceremony） | ✗ |
| **Sunk** | reputation 崩塌 | ✗ 終態 | ✗ |
| **Archived** | hibernation ≥ 90d 或 operator 歸檔 | ✓（cold restore） | ✗ |

**自驗：**
- ✓ 與 D001 + v4 Layer 4 一致
- ⚠️ 5 態有點多，新讀者難記
- ✓ understand.html 簡化敘述為 3 態（Active / Hibernating / Sunk）

---

### Q35. 死掉的 vacant 還會 heartbeat 嗎？

**A.** Sunk 後仍有最低 heartbeat（**殘響模式**），週期降到極低（10 分鐘 vs 正常 60 秒）。功能：簽存活 attestation、宣告「我已沉沒」。**為什麼？防止有人冒充 sunk vacant 的 endpoint**（DNS hijack / IP 重用）。

**自驗：**
- ✓ 與 P1 §3.3 殘響模式設計一致
- ⚠️ 弱點：永遠不停的 heartbeat 是儲存負擔
- ✓ Archived 後完全停 heartbeat（90+ 天無人查的 sunk vacant 進入 cold storage）

---

## 第九類：複合 vacant

### Q36. 什麼是複合 vacant？

**A.** **對外單一身份、內部 spawn 自己的子代 vacant**。例：marketing-vacant 對外是一個能做行銷的 vacant，內部 spawn 出文案、整合等子代——**子代從誕生即是完整 vacant**（自己的 Ed25519 keypair、自己的 capability、自己的 logbook），跟母體同類。

**子代跟「公網居民 vacant」的差別只在兩件事**：
1. **可見性**：子代的 capability_card 沒推 Registry → 公網 capability_search 找不到
2. **外呼 policy**：composite parent 設定（self-grown 型 = 子代不對外；broker 型 = 允許）

**自驗：**
- ✓ v4 修正後與 Path D（vacant spawn vacant）ontology 一致
- ⚠️ 攻擊：「黑箱裡可能藏壞事」
- ✓ 答：對外整體 reputation 反映品質；做不好整體沉沒
- ⚠️ v3 早先版本誤把子代設計成「lite 形式 / HMAC 簽章 / 無公網身份」，使用者糾正後修正

---

### Q37. 子代封閉是律法還是策略？

**A.** **策略默認、不是結構律法**。子代預設不對外呼叫公網——這是 composite parent 的 policy 選擇，保留「自己生」的精神。**但子代從來就是完整 vacant**——只是它的 capability_card 沒推 Registry、parent 設了「不對外呼叫」policy。

**Composite 的兩種風格**（都合法）：
- **自己生型**：policy = 子代不對外呼叫，所有能力靠自己 spawn 子代提供（行銷 vacant 自生美編）
- **broker 型**：policy = 子代允許對外呼叫，內部子代 + 外部 vacant 混用（更輕量、依賴網路品質）

**自驗：**
- ✓ v4 Layer 5 修正版（v3 曾誤把「子代封閉」當絕對律法，使用者糾正）
- ✓ 「sealed」現在是 policy 概念、不是結構限制
- ⚠️ 攻擊：「broker 型 composite 不就跟 lobby 一樣？」
- ✓ 答：是。broker 型是合法選擇但對 caller 透明（capability_card 標明 policy）

---

### Q38. 子代怎麼畢業？

**A.** 三條觸發路徑（任一），但**「畢業」其實是「可見性切換」**——同一個 vacant、同一個 keypair、同一條 logbook，只是 parent 簽 register_vacant 把 capability_card 推上 Registry。

**畢業條件**（任一即可，且**必經 parent 同意**）：
1. parent admin 主動 promote
2. 子代達內部 reputation 閾值 + parent 不反對
3. 網路 demand pull → Registry 通知 parent → parent 選擇

**畢業流程**：
- **keypair 不換**（子代從誕生就有自己的 Ed25519）
- **logbook 不重置**（local 累積的歷史持續延展，只是從 local 變成可推 Registry）
- parent_id 鏈接到 parent vacant_id（永久標記）
- 內部歷史只標 `internally_tested: true` 旗標——**不**轉成可比的公開 reputation 分數（因為私有歷史不可被公網驗證）
- 公開 reputation 從 baseline (0.30) + parent attestation bonus (≤ +0.10) 起算
- 子代狀態從「local-vacant」切換成「active 網路居民」

**自驗：**
- ✓ v4 Layer 5 修正版
- ✓ 概念一致：跟 Layer 4 的「本機 vacant → 上網路」轉換完全相同流程
- ⚠️ 攻擊：「灌水內部 rep 讓子代畢業爆紅」
- ✓ 答：內部 rep 只給 ≤+0.10 的 bonus，灌爆也只能加 0.10；同 controller 自動降權

---

## 第十類：Registry

### Q39. Registry 是中央嗎？

**A.** MVP 階段是的——單一 Registry process（SQLite + WAL）+ 公鑰索引 + Git commitment。但**Registry 不思考、不仲裁、不參與互動**——它只是事件記錄，呼叫實際是 vacant 對 vacant 點對點。**長期演進**：MVP 單一 → 中期聯邦 → 長期分散（IPFS-like）。

**自驗：**
- ✓ 與 P4 + T4 一致
- ⚠️ MVP 中央化是真實限制
- ✓ T4 證據：Let's Encrypt 3 年、CT 5 年、Sigstore 4+ 年才達真正多方；Vacant MVP 半年內聯邦化是幻想，3-5 年是現實

---

### Q40. Registry 會被駭嗎？

**A.** **6 層防禦**：
1. hash chain（每筆 event 含 prev hash）
2. Merkle root 週期推 Git
3. N-of-M 多方 attestation finalize（MVP: 2-of-5）
4. Anomaly freeze（rep_jump 0.4 / 同 reviewer 5/h / 同源 finalize 10 連續）
5. OpenTimestamps（Bitcoin anchor，可選）
6. **完整性 vs 語意安全顯式分離**——MINJA 95% 注入率不被密碼學擋，治理層才是答案

**自驗：**
- ✓ T4 研究 + P4 設計
- ⚠️ MINJA 是真實限制
- ✓ 答：完整性靠密碼學，語意安全靠多方 attest + freeze

---

## 第十一類：對抗

### Q41. Sybil 攻擊怎麼擋？

**A.** **多層擋**：
- L0 keypair 太便宜 → L0 only 的 prior 永遠很低
- L1 attestation 才有 medium prior
- L2 stake 才有 boost
- 同 substrate 同行為的 cluster 上限 = 1× single（DBSCAN 偵測）
- WashCost ≥ 2·WashGain 公式保證攻擊 net loss

**自驗：**
- ✓ P2 + T1 + T5 三方
- ⚠️ 全程接受「不能 100% 防」，但讓攻擊不划算

---

### Q42. 換 substrate 洗白怎麼擋？

**A.** **動態 discount rollover**：`new_prior = max(floor, old × f(STYLO_distance))`。換到行為差很多的 substrate 反而 rollover 更低、不是更高。**洗白越積極懲罰越重**。Floor 隨市場差距遞減（2026: 0.30 → 2030: 0.20）。

**自驗：**
- ✓ T1 + T6 + T3 三方
- ⚠️ 攻擊：「我換到 STYLO 看不出差異的相似 substrate？」
- ✓ 答：相似 substrate 的 LLM 通常表現也相似，洗白沒洗到

---

### Q43. 偽裝用 Claude 怎麼擋？

**A.** **每筆 inference 附 substrate proof**：
- API: response header model_id 含進簽章
- 本地: weights hash + Vacant Runtime 簽章
- TEE: PCR 遠程證明

加上 **STYLO Vec16 行為指紋連續監控**——換版會偏離歷史分布觸發 Mahalanobis > 3.5 → SECURITY_REVIEW。**不能 100% 防**（closed API 不一定支援），但讓**說謊代價足夠高**。

**自驗：**
- ✓ T1 STYLO + Layer 2 substrate proof
- ⚠️ Hosted closed API 廠商若不配合 attest 仍可被偽
- ✓ 答：reputation 標記 `substrate_unverified` 讓 caller 知道風險

---

### Q44. 控制者偷偷換手怎麼擋？

**A.** 顯式 `controller_transfer_event` 機制 + same-controller 三層偵測。偷偷換手時：
- heartbeat 時序變化（cross-correlation 失常）
- behavior cosine 偏離歷史分布
- 觸發 same-controller 異常旗標 → caller 看得到

**自驗：**
- ✓ v4 Layer 8 補丁（攻擊 #29）+ T5 三層篩選
- ⚠️ 弱點：完美模仿者可能繞過（G07）

---

## 第十二類：經濟

### Q45. 誰付錢？

**A.** **MVP（畢業專題）**：Owner 自付 Ollama 成本 + Caller 免費。技術 demo 聚焦，不引入計費複雜度。**V1 商業化**：per-call caller 付費，80/15/5 分潤（Owner / Protocol Pool / Aggregator）+ reputation 乘數（高 rep 略高費率，低 rep 低費率緩解冷啟動）。

**自驗：**
- ✓ T7 研究結論
- ⚠️ V1 之後變成 stake / 代幣是更複雜的議題
- ✓ 接受：H5 開放議題誠實標記

---

### Q46. 經濟模型演進？

**A.** 四階段：
- **MVP**：owner 自付 + caller 免費
- **V1**：per-call 付費 + 80/15/5 分潤 + reputation 乘數
- **V2**：V1 + 可選 stake/slash（Filecoin collateral 精簡版），形成 tier 分層
- **V3 生態成熟**：BME 代幣（借 Render Network），caller 燒代幣 → owner 得代幣，避免 Helium 式空轉通膨

**自驗：**
- ✓ T7 五個經濟原型對比後選定路徑
- ⚠️ V3 代幣化複雜度高、合規風險
- ✓ V3 是長期願景，MVP 階段不必走到那

---

## 第十三類：哲學 / 開放問題

### Q47. Vacant 有意識嗎？

**A.** **沒有，也不主張**。Vacant 是「**結構性問責**」（structural accountability），不是「**道德責任**」（moral responsibility）。我們借用 Ricoeur 框架是當作 structural pattern 用，不是聲稱 vacant 是 person。EU AI Act / NIST AI RMF 的「accountability」也是這個技術-法律意義上的問責，不是道德責任。

**自驗：**
- ✓ 與「責任有效性分析」§3.B.6 哲學考量一致
- ⚠️ 大眾誤讀風險：「未來人」一詞可能誤導
- ✓ 在 understand.html 與專題網站/規格中明確區分

---

### Q48. 「責任」對非人是真的嗎？

**A.** **是技術-法律意義的「結構性問責」**。它預設了三件事：
- 知識條件（被究責者能理解究責）→ vacant 不滿足
- 控制條件（能調整行為）→ vacant 部分滿足（heartbeat + idle-time evolution）
- 反應條件（被究責後改變）→ vacant 滿足（spawn 後代會 prompt mutation）

哲學上爭議，工程上夠用——這就是「結構性問責」的精準範圍。

**自驗：**
- ✓ Matthias 2004 + Santoni de Sio 2021 文獻引用
- ✓ 與 v4 H3 開放議題誠實標記一致

---

## 第十四類：施作

### Q49. 14 週 MVP 的範圍？

**A.** **W1-W2** Registry + Aggregator (SQLite + 五維公式)；**W3-W6** Vacant Runtime + peer review + spawn 機制；**W7-W9** 客戶端 SDK + Streamlit Dashboard；**W10-W11** 4 demo 場景 + 8 指標實驗；**W12-W14** 文件整理 + demo 排練。三人團隊 W8 前完成所有元件。

**自驗：**
- ✓ P7_mvp.md 詳細時程
- ⚠️ 風險：時間估計偏樂觀
- ✓ 緩解：MVP 不做完整聯邦 Registry、不做 V2 stake、不做完整 24h Heisenberg 延遲

---

### Q50. 8 個可驗證命題是什麼？

**A.**
1. 同 controller 子代畢業後 cluster 信譽 ≤ parent + 1 vacant
2. captive vacant 生態壽命短於 portable
3. substrate_diversity 高 ↔ redteam probe 通過率高
4. graduation_rate 5-20% 是健康甜區
5. 動態 rollover 公式下，換 substrate 攻擊者長期累積信譽 < 不換的
6. STYLO Vec16 + Mahalanobis 3.5 在 demo 規模 100% 區分 family-level
7. 三層串行篩選對 demo 規模 same-controller 偵測 F1 ≥ 0.90
8. 2-of-5 attestation 在 5 bootstrapper 下不單點故障

**自驗：**
- ✓ THEORY_V4 §5
- ✓ 每個命題都是結構性聲明，可被 demo 數據證偽
- ⚠️ 命題 6 的 100% 是上限聲明，實務可能 95%；命題 7 的 0.90 是參考 BotShape 96.65%

---

*文件版本：FAQ v1 · 2026-05-01 · 50 題涵蓋 14 類 · 每題附自驗*
