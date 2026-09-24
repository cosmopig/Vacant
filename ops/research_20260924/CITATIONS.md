# 引用清單（2026-09-24 研究）

核對方式：本 session 的子代理（sonnet）逐條用 WebFetch 取得，記下**實際讀到的層級**。
原始紀錄在本 session 的 scratchpad（`citations_raw.md`），本檔是整理版。

- **全文**＝讀到論文 HTML／PDF 全文、完整 RFC、或完整官方文件頁
- **摘要**＝只讀到 arXiv `/abs/` 頁、會議摘要頁、或二手頁面
- **間接**＝直接抓取失敗，內容來自搜尋引擎摘錄——**不可當逐字引文**

⚠ 多數 arXiv 條目只讀了摘要頁；下面引到的數字**全部出現在摘要本身**，但沒有對照正文。

## A. 驗證、LLM 評審、成本

| # | 標題 | 作者 | 年 | 網址 | 層級 | 本研究用到的那一句 |
|---|---|---|---|---|---|---|
| A1 | Instruction-Following Evaluation for Large Language Models（IFEval） | Zhou, Lu, Mishra, Brahma, Basu, Luan, Zhou, Hou | 2023 | https://arxiv.org/abs/2311.07911 | 摘要 | 「25 types of those verifiable instructions … around 500 prompts」。**另外**：本研究直接用了它公開的資料與檢查器原始碼（`verifier/data/`，sha256 在 `SHA256SUMS`），GPT-4 strict prompt 層 416/540＝77.0% 由我們重算 |
| A2 | FrugalGPT: How to Use Large Language Models While Reducing Cost and Improving Performance | Chen, Zaharia, Zou | 2023 | https://arxiv.org/abs/2305.05176 | 摘要 | 「up to 98% cost reduction」（級聯的來源概念） |
| A3 | Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena | Zheng et al. | 2023 | https://arxiv.org/abs/2306.05685 | 摘要 | GPT-4 評審與人「over 80% agreement」；位置、冗長、自我偏好偏誤 |
| A4 | RAGTruth: A Hallucination Corpus for Developing Trustworthy Retrieval-Augmented Language Models | Niu, Wu, Zhu, Xu, Shum, Zhong, Song, Zhang | 2024 | https://arxiv.org/abs/2401.00396 | **全文**（HTML v2） | 近 18,000 筆人工標註回應；三任務＝QA、Data-to-text、News Summarization。本研究用它的資料（MIT）當 V2 真值 |
| A5 | HaluEval | Li, Cheng, Zhao, Nie, Wen | 2023 | https://arxiv.org/abs/2305.11747 | 摘要 | 「about 19.5% responses」捏造；外部知識有助辨識（本研究**沒用**它的資料：標註是構造出來的，不是人工） |
| A6 | FActScore | Min et al. | 2023 | https://arxiv.org/abs/2305.14251 | 摘要 | 拆成原子事實逐條驗；自動指標「less than a 2% error rate」（V3「逐句驗」的來源概念） |
| A7 | Enabling Large Language Models to Generate Text with Citations（ALCE） | Gao, Yen, Yu, Chen | 2023 | https://arxiv.org/abs/2305.14627 | 摘要 | 「even the best models lack complete citation support 50% of the time」（V3 要求附引文的動機與風險） |
| A8 | TICKing All the Boxes: Generated Checklists Improve LLM Evaluation and Generation | Cook, Rocktäschel, Foerster, Aumiller, Wang | 2024 | https://arxiv.org/abs/2410.03608 | 摘要 | 檢查清單把 LLM 評估與人的一致率從 46.4% 拉到 52.2% |
| A8b | CheckEval | Lee et al. | 2024 | https://arxiv.org/abs/2403.18771 | 摘要 | 備用：清單式評估降低評審間變異 |
| A9 | Large Language Models are not Fair Evaluators | Wang et al. | 2023 | https://arxiv.org/abs/2305.17926 | 摘要 | 只調換順序，80 題裡 66 題翻盤（位置偏誤） |
| A10 | Language Models (Mostly) Know What They Know | Kadavath et al. | 2022 | https://arxiv.org/abs/2207.05221 | 摘要 | P(True) 有校準；P(IK) 在新任務上校準困難（「不確定就說不確定」的上限） |
| A11 | Large Language Model Cascades with Mixture of Thoughts Representations for Cost-efficient Reasoning | Yue, Zhao, Zhang, Du, Yao | 2023 | https://arxiv.org/abs/2310.03094 | 摘要 | 級聯只要強模型 40% 成本 |
| A12 | G-Eval | Liu, Iter, Xu, Wang, Xu, Zhu | 2023 | https://arxiv.org/abs/2303.16634 | 摘要 | 摘要任務與人的 Spearman 0.514；對 LLM 生成文字可能有偏好 |

## B. 中介、稽核紀錄、agent 擴充點、作業系統觀測

| # | 標題 | 作者 | 年 | 網址 | 層級 | 用到的那一句 |
|---|---|---|---|---|---|---|
| B1 | Computer Security Technology Planning Study（reference monitor） | J. P. Anderson | 1972 | https://en.wikipedia.org/wiki/Reference_monitor | **摘要（二手頁）** | reference monitor 的四條件：不可繞過、可驗證、恆被呼叫、防竄改。**原報告沒讀** |
| B2 | Secure audit logs to support computer forensics | Schneier, Kelsey | 1999 | https://dl.acm.org/doi/10.1145/317087.317089 | **間接**（ACM 403） | 被入侵之前寫下的紀錄不可被無痕改刪（前向安全紀錄）。**不可逐字引用** |
| B3 | Efficient Data Structures for Tamper-Evident Logging | Crosby, Wallach | 2009 | https://www.usenix.org/conference/usenixsecurity09/technical-sessions/presentation/efficient-data-structures-tamper-evident | **間接**（書目確認，摘要靠搜尋摘錄） | 不受信任的紀錄者由稽核者挑戰來保持誠實。**不可逐字引用** |
| B4 | RFC 6962 Certificate Transparency | Laurie, Langley, Kasper | 2013 | https://www.rfc-editor.org/rfc/rfc6962 | 全文 | append-only Merkle 紀錄；簽發時承諾「會被併入紀錄」（SCT）——與 sidecar「事件當場簽進鏈」同型 |
| B5 | in-toto: Providing farm-to-table guarantees for bits and bytes | Torres-Arias, Afzali, Kuppusamy, Curtmola, Cappos | 2019 | https://www.usenix.org/conference/usenixsecurity19/presentation/torres-arias | 摘要 | 每一步都簽證明、終端使用者端到端驗（「交付物附證據」的供應鏈版本） |
| B6 | Claude Code hooks 文件 | Anthropic | 2026（抓取日） | https://code.claude.com/docs/en/hooks | 全文 | 事件清單（含 ConfigChange、FileChanged、PostToolBatch…）；「`allowManagedHooksOnly` … user, project, local, and plugin hooks are blocked」；使用者層的 `disableAllHooks` **關不掉** managed 層的掛鉤。**Windows 的 managed 路徑：文件頁沒寫，未核實** |
| B7 | OpenCode plugins 文件 | OpenCode | 2026 | https://opencode.ai/docs/plugins | 全文 | `tool.execute.before/after`、`session.*`、`permission.*` 事件 |
| B8 | pi coding agent extensions 文件 | badlogic/pi-mono | 2026 | https://github.com/badlogic/pi-mono/blob/main/packages/coding-agent/docs/extensions.md | 全文 | `tool_call`、`tool_result`、`session_start/shutdown`、`agent_before_settle`；extension 在 pi 行程內以完整 OS 權限執行 |
| B9 | Event Tracing for Windows（ETW） | Microsoft | 2026 | https://learn.microsoft.com/en-us/windows/win32/etw/event-tracing-portal | 全文 | 應用程式與核心的事件追蹤機制 |
| B10 | Sysmon | Microsoft Sysinternals | 2026 | https://learn.microsoft.com/en-us/sysinternals/downloads/sysmon | 全文 | 常駐服務＋驅動；Event ID 1 行程建立（含完整命令列與父行程）、3 網路連線、11 檔案建立 |
| B11 | OpenTelemetry GenAI 屬性註冊表 | OpenTelemetry | 2026 | https://opentelemetry.io/docs/specs/semconv/registry/attributes/gen-ai/ | 全文 | `gen_ai.agent.*`、`invoke_agent` 等（原 agent-spans 頁已搬家，不引舊網址） |

## C. 本 repo 內的既有證據（引用前已讀原檔）

| # | 檔案 | 用到的那一句 |
|---|---|---|
| C1 | `decisions/DECISION_20260920_AGENT_HOOKS_MEASURED.md` | 五個 agent 都攔得到 shell 指令；Claude Code 的 agent 用 Bash 刪掉 hook 設定、下一跑零觸發 |
| C2 | `decisions/DECISION_20260920_COMPLETE_MEDIATION.md` | 「kernel 給有沒有，hook 給是什麼」；A/B/B′/C 分級 |
| C3 | `ops/vacantrun/possess_claude_20260922/README.md` §一 | `CLAUDE_CODE_PROVIDER_MANAGED_BY_HOST=1` 下 settings.json 的 base URL 被忽略 |
| C4 | `decisions/DECISION_20260904_R440T_E3_WRAPUP.md` | 程式題上的 LLM 評審「追蹤的是題目整體難度，不是這一份答案對不對」（原始層貼著常數基線）；grounded 層做事的是執行反例的機器 |
| C5 | `vacant_network/suitegauge.py` docstring | 驗收的單邊保證：擋得住已知壞解 ≠ 涵蓋真需求 |
