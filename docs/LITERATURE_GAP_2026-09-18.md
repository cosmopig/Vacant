# Vacant 文獻缺口調查 — 對著「我們做出來的東西」找 (2026-09-18)

## 這份文件在幹嘛

既有的 236 筆引用備份（`專題/參考文獻/_引用備份/MANIFEST.json`）集中在三個資料夾——
`agent信任` 94、`信任定義` 80、`人類運作邏輯` 62——那是為了**名詞與定義考據**做的，
目的是「不要對觀眾說錯話」。但**我們實際做出來的東西，文獻幾乎是空的**：
防竄改日誌 1 筆、變異測試／測試預言 0 筆、沙箱隔離 0 筆、供應鏈證明 1 筆。

這份就是補那個洞。原則是**對著我們已經成立的結果與已經量到的限制去找**，
不是對著題目去找。每一條都列出支持的與**反駁的**，反駁的更重要——那是誠實邊界的來源。

### 查證紀律

- 每一筆的 title / authors / year / DOI / arXiv id 都經 **arXiv API**、**Crossref REST**、
  **OpenAlex** 或 **Semantic Scholar** 實際查回。查不回來的一律不列。
- 過程中丟掉過至少一筆：我原本認為 *To the Cutoff... and Beyond?* 是 arXiv:2402.16889，
  查回來發現那個 id 是另一篇自浮水印論文，改用查證過的 arXiv:2310.10628
  （同一工作的 arXiv 題名為 *Data Contamination Through the Lens of Time*）。
- **Scopus 走不通**：ezproxy 本身通，但 Elsevier 端強制互動式機構登入（403／`prompt=login`），
  已放棄，全部改走公開來源。

### 取得層級（與既有 MANIFEST 同構，但定義貼合這次的現實）

| 層級 | 定義 | 本批數量 |
|---|---|---|
| `A_全文` | 取得全文 | **0** |
| `B_僅摘要` | 取得摘要（arXiv API） | 55 |
| `C_僅書目` | 僅書目經 API 核回，**未讀全文** | 54 |

> ⚠ 本批**沒有 A 級**。C 級尤其只代表「這篇論文存在、書目正確」，
> 不代表我讀過它。下面的「對應」句對 C 級而言是根據題名、摘要級資訊與該領域共識所寫的
> **預期**用途，引用進展場文案前需要有人實際讀過。

### 總計

**109 筆**（108 個不重複書目；少數同一工作同時列出 arXiv 版與正式版書目，已在條目內註明）。

| 主題 | 筆數 |
|---|---|
| 主張 1 增益主體＝閘門＋重抽 | 23 |
| 主張 2 執行式驗收 vs 模型自評 | 12 |
| 限制 1 測試預言問題 | 20 |
| 限制 2 hash chain 砍尾巴 | 10 |
| 限制 3 收據自簽／金鑰託管 | 3 |
| 限制 4 可究責層是自願的 | 6 |
| 方法 2 污染與樣本外 | 13 |
| 方法 3 預註冊與多重比較 | 22 |

立場分佈：支持 75、背景 17、**反駁 7**、反駁/邊界 6、邊界 3、支持＋自我限制 1。

---

## 主張 1：增益主體是「可執行驗收閘門 ＋ 重抽」，不是回饋迴圈

> 我們的資料：12B 五次複製 CONFORM 對單發 +14.2/+18.3/+17.5 pp（皆過 Holm）；27B CONFORM 對 OFF 合併 +7.89 pp（p<0.0001）。而「迴圈贏重抽」未確立：12B 九個資料點 +0.6～+5.8 pp、0/9 過校正；27B 五組全翻負、合併 −3.23 pp [−5.52,−0.75] p=0.0101。

### Large Language Models Cannot Self-Correct Reasoning Yet (2023) — 支持

- **作者**：Jie Huang et al.
- **出處**：arXiv:2310.01798　|　ICLR 2024
- **取得層級**：`B_僅摘要`（查證來源：arxiv-api）
- **跟我們這一條怎麼對應**：（已在既有 236 筆內，此處重新核過 id）Huang et al. 指出 LLM 在沒有外部回饋時，自我修正後表現往往變差——這正是我們 27B 上「迴圈臂合併 −3.23 pp」的已知形狀。它是我們這一條最直接的先行研究，展場不可宣稱此現象由我們發現。

### When Can LLMs Actually Correct Their Own Mistakes? A Critical Survey of Self-Correction of LLMs (2024) — 支持

- **作者**：Ryo Kamoi et al.
- **出處**：arXiv:2406.01297 · DOI 10.1162/tacl_a_00713/125177　|　Transactions of the Association for Computational Linguistics (2024) 12: 1417-1440
- **取得層級**：`B_僅摘要`（查證來源：arxiv-api）
- **跟我們這一條怎麼對應**：本條最強支持。Kamoi et al. 的臨界綜述明說：**沒有任何先前工作證明「用 prompted LLM 當回饋來源」的自我修正成功**，除非任務本身特別適合；並指出許多正面結果其實偷用了 oracle 回饋或不公平的評測。我們的「閘門（可執行）有效、迴圈（自評）未確立」正是這個結論的獨立複製。

### When Can LLMs Actually Correct Their Own Mistakes? A Critical Survey of Self-Correction of LLMs (2024) — 支持

- **作者**：Ryo Kamoi et al.
- **出處**：DOI 10.1162/tacl_a_00713　|　Transactions of the Association for Computational Linguistics
- **取得層級**：`C_僅書目`（查證來源：crossref-doi）
- **跟我們這一條怎麼對應**：同一篇的 TACL 正式版書目（引用時用這個 DOI）。

### Is Self-Repair a Silver Bullet for Code Generation? (2023) — 支持

- **作者**：Theo X. Olausson et al.
- **出處**：arXiv:2306.09896　|　Accepted to ICLR 2024. Added additional Code Llama experiments and fixed a data processing error harming Code Llama's reported self-repair performance on HumanEval
- **取得層級**：`B_僅摘要`（查證來源：arxiv-api）
- **跟我們這一條怎麼對應**：Olausson et al.：把修復的 token 成本計入後，self-repair 的增益「常常很小、在不同子集差異極大、有時根本不存在」，瓶頸是模型對自己產出的回饋品質。這與我們「迴圈贏重抽 0/9 過校正」在結論與機制上都對得起來——而且他們也做了等預算比較，方法論可直接引用。

### GPT-4 Doesn't Know It's Wrong: An Analysis of Iterative Prompting for Reasoning Problems (2023) — 支持

- **作者**：Kaya Stechly et al.
- **出處**：arXiv:2310.12397　|　18 pages, 3 figures
- **取得層級**：`B_僅摘要`（查證來源：arxiv-api）
- **跟我們這一條怎麼對應**：Stechly et al. 在圖著色上顯示：迭代提示的增益來自外部驗證者，不是模型的自我批判；換成自評即消失。等同我們「增益主體是閘門不是迴圈」。

### Can Large Language Models Really Improve by Self-critiquing Their Own Plans? (2023) — 支持

- **作者**：Karthik Valmeekam et al.
- **出處**：arXiv:2310.08118
- **取得層級**：`B_僅摘要`（查證來源：arxiv-api）
- **跟我們這一條怎麼對應**：Valmeekam et al.：在規劃任務上，self-critique 反而**降低**表現，因為自評產生大量假陰性。這是「迴圈可能是負的」的先行證據，支持我們 27B 五組全翻負不是噪音。

### LLMs cannot find reasoning errors, but can correct them given the error location (2023) — 支持

- **作者**：Gladys Tyen et al.
- **出處**：arXiv:2311.08516　|　ACL 2024 Findings
- **取得層級**：`B_僅摘要`（查證來源：arxiv-api）
- **跟我們這一條怎麼對應**：Tyen et al.：模型找不到自己的推理錯誤，但**一旦被告知錯誤位置就能改對**。我們的可執行閘門做的正是「指出錯誤位置」這件事——這篇替我們解釋了為什麼閘門有效而自評無效。

### LLMs cannot find reasoning errors, but can correct them given the error location (2024) — 支持

- **作者**：Gladys Tyen et al.
- **出處**：DOI 10.18653/v1/2024.findings-acl.826　|　Findings of the Association for Computational Linguistics ACL 2024
- **取得層級**：`C_僅書目`（查證來源：crossref-doi）
- **跟我們這一條怎麼對應**：同一篇的 ACL Findings 正式版書目。

### Large Language Monkeys: Scaling Inference Compute with Repeated Sampling (2024) — 支持

- **作者**：Bradley Brown et al.
- **出處**：arXiv:2407.21787
- **取得層級**：`B_僅摘要`（查證來源：arxiv-api）
- **跟我們這一條怎麼對應**：Brown et al.（Large Language Monkeys）：重抽讓 coverage 隨樣本數在四個數量級上呈 log-linear 上升；但作者明講**只有在答案能被自動驗證的領域（coding、formal proofs），coverage 的上升才直接轉成表現提升**。這是「重抽 × 可執行驗收」這個組合最正面、也最精確的外部支持，而且它同時說明了為什麼缺了閘門的重抽沒用。

### Training Verifiers to Solve Math Word Problems (2021) — 支持

- **作者**：Karl Cobbe et al.
- **出處**：arXiv:2110.14168
- **取得層級**：`B_僅摘要`（查證來源：arxiv-api）
- **跟我們這一條怎麼對應**：Cobbe et al.：訓練 verifier 再做 best-of-n，是「抽多次＋外部判準挑」這個模式的起點。我們的 CONFORM 臂在結構上就是它的執行式版本（判準＝測試而非學出來的 verifier）。

### Small Language Models Need Strong Verifiers to Self-Correct Reasoning (2024) — 支持

- **作者**：Yunxiang Zhang et al.
- **出處**：arXiv:2404.17140　|　ACL Findings 2024 - Camera Ready
- **取得層級**：`B_僅摘要`（查證來源：arxiv-api）
- **跟我們這一條怎麼對應**：Zhang et al.：小模型要**夠強的驗證器**才自我修正得動。我們用 12B/27B 這個尺度，這篇直接說明為何自評迴圈在這個量級上不該期待增益。

### CRITIC: Large Language Models Can Self-Correct with Tool-Interactive Critiquing (2023) — 邊界

- **作者**：Zhibin Gou et al.
- **出處**：arXiv:2305.11738　|　ICLR 2024
- **取得層級**：`B_僅摘要`（查證來源：arxiv-api）
- **跟我們這一條怎麼對應**：Gou et al.（CRITIC）：沒有外部工具回饋時自我修正一致地無改善，加了工具（含直譯器）才有。支持我們的方向，但也提醒「外部回饋」不限於測試，我們不該把結論說成「只有測試有用」。

### Agentless: Demystifying LLM-based Software Engineering Agents (2024) — 支持

- **作者**：Chunqiu Steven Xia et al.
- **出處**：arXiv:2407.01489
- **取得層級**：`B_僅摘要`（查證來源：arxiv-api）
- **跟我們這一條怎麼對應**：Xia et al.（Agentless）：不用 agentic 迴圈、只用簡單三階段＋測試，在 SWE-bench 上勝過複雜 agent。這是「迴圈不是增益主體」在軟體工程場景的獨立證據。

### Demystifying LLM-Based Software Engineering Agents (2025) — 支持

- **作者**：Chunqiu Steven Xia et al.
- **出處**：DOI 10.1145/3715754　|　Proceedings of the ACM on Software Engineering
- **取得層級**：`C_僅書目`（查證來源：crossref-doi）
- **跟我們這一條怎麼對應**：同一篇的 PACMSE 正式版書目。

### Scaling LLM Test-Time Compute Optimally can be More Effective than Scaling Model Parameters (2024) — 背景

- **作者**：Charlie Snell et al.
- **出處**：arXiv:2408.03314
- **取得層級**：`B_僅摘要`（查證來源：arxiv-api）
- **跟我們這一條怎麼對應**：Snell et al.：test-time compute 怎麼配置比配置多少重要。我們的等預算三臂設計（單發／重抽／迴圈）屬於這個問題族，引用它可說明「等預算比較」不是我們發明的怪規矩。

### Inference Scaling Laws: An Empirical Analysis of Compute-Optimal Inference for Problem-Solving with Language Models (2024) — 背景

- **作者**：Yangzhen Wu et al.
- **出處**：arXiv:2408.00724
- **取得層級**：`B_僅摘要`（查證來源：arxiv-api）
- **跟我們這一條怎麼對應**：Wu et al.：compute-optimal inference 的經驗分析，同上，是我們等預算設計的方法論鄰居。

### Self-Consistency Improves Chain of Thought Reasoning in Language Models (2022) — 背景

- **作者**：Xuezhi Wang et al.
- **出處**：arXiv:2203.11171　|　Published at ICLR 2023. V2: added PaLM results; V3: added UL2 results; V4: camera ready version at ICLR 2023
- **取得層級**：`B_僅摘要`（查證來源：arxiv-api）
- **跟我們這一條怎麼對應**：Wang et al.（Self-Consistency）：多數決式重抽的原型。我們的 OFF5 多數決臂與它同族，引用它可避免把多數決講成自創。

### Training Language Models to Self-Correct via Reinforcement Learning (2024) — **反駁**

- **作者**：Aviral Kumar et al.
- **出處**：arXiv:2409.12917
- **取得層級**：`B_僅摘要`（查證來源：arxiv-api）
- **跟我們這一條怎麼對應**：Kumar et al.（SCoRe）：**用多輪線上 RL 訓練，可以得到真正的內在自我修正**（作者報告在 MATH／HumanEval 上有顯著提升），且明說 SFT 不足、要在模型自己的分佈上訓。⇒ 我們**不能**說「回饋迴圈沒有用」，只能說「**未經訓練的、prompt 層級的**回饋迴圈，在我們量到的尺度上沒有可複製的增益」。這是展場措辭必須改的地方。

### Self-Correction Bench: Uncovering and Addressing the Self-Correction Blind Spot in Large Language Models (2025) — **反駁**

- **作者**：Ken Tsui
- **出處**：arXiv:2507.02778　|　Accepted to COLM 2026
- **取得層級**：`B_僅摘要`（查證來源：arxiv-api）
- **跟我們這一條怎麼對應**：Tsui et al.（Self-Correction Bench）：14 個開源非推理模型平均有 64.5% 的「自我修正盲點」——同一個錯誤，外部給就改得動、自己產的就改不動；而且只要在輸出後接一個 "Wait" 就能把盲點降 89.3%，顯示**能力存在、只是沒被觸發**，成因在 post-training 資料缺少改錯序列。⇒ 我們的「迴圈無效」有可能是**觸發方式**問題而非能力問題，這條必須寫進誠實邊界。

### Self-Refine: Iterative Refinement with Self-Feedback (2023) — **反駁**

- **作者**：Aman Madaan et al.
- **出處**：arXiv:2303.17651　|　Code, data, and demo at https://selfrefine.info/
- **取得層級**：`B_僅摘要`（查證來源：arxiv-api）
- **跟我們這一條怎麼對應**：Madaan et al.（Self-Refine）：報告同一個模型自評自改即可提升。它是我們結論的反例代表，**必須列出**；但可並陳 Kamoi 的批評（評測設計會高估自我修正）。

### Reflexion: Language Agents with Verbal Reinforcement Learning (2023) — **反駁**

- **作者**：Noah Shinn et al.
- **出處**：arXiv:2303.11366　|　v4 contains a few additional experiments
- **取得層級**：`B_僅摘要`（查證來源：arxiv-api）
- **跟我們這一條怎麼對應**：Shinn et al.（Reflexion）：語言化回饋 + 記憶的迴圈有效。同樣是反例，但注意它大量依賴外部環境回饋（含單元測試），與我們「閘門才是主體」其實不衝突——引用時要講清楚這個區分。

### Teaching Large Language Models to Self-Debug (2023) — 邊界

- **作者**：Xinyun Chen et al.
- **出處**：arXiv:2304.05128
- **取得層級**：`B_僅摘要`（查證來源：arxiv-api）
- **跟我們這一條怎麼對應**：Chen et al.（Self-Debug）：有效，但它的回饋來源是**執行結果**。這篇最適合用來說明「所謂自我除錯其實是執行式回饋」，把反例轉成支持。

### Sample, Scrutinize and Scale: Effective Inference-Time Search by Scaling Verification (2025) — **反駁**

- **作者**：Eric Zhao et al.
- **出處**：arXiv:2502.01839
- **取得層級**：`B_僅摘要`（查證來源：arxiv-api）
- **跟我們這一條怎麼對應**：Zhao et al.：把抽樣式搜尋與自我驗證一起放大，能超越單純重抽。⇒ 「自評無用」在**足夠大的抽樣規模**下可能不成立；我們只跑到有限預算，這是外推的邊界。

---

## 主張 2：執行式驗收比模型自評可靠

> 我們的資料：CONFORM（可執行驗收閘門）對 OFF 合併 +7.89 pp；而 27B 上自評式迴圈合併為負。

### Evaluating Large Language Models Trained on Code (2021) — 背景

- **作者**：Mark Chen et al.
- **出處**：arXiv:2107.03374　|　corrected typos, added references, added authors, added acknowledgements
- **取得層級**：`B_僅摘要`（查證來源：arxiv-api）
- **跟我們這一條怎麼對應**：Chen et al.（HumanEval／Codex）：pass@k 這種「跑測試看過不過」的功能正確性評測的起點。我們整套 V/GT 分離的評測法源於此。

### Program Synthesis with Large Language Models (2021) — 背景

- **作者**：Jacob Austin et al.
- **出處**：arXiv:2108.07732　|　Jacob and Augustus contributed equally
- **取得層級**：`B_僅摘要`（查證來源：arxiv-api）
- **跟我們這一條怎麼對應**：Austin et al.（MBPP）：我們題庫 MBPP+ 的母體。

### Is Your Code Generated by ChatGPT Really Correct? Rigorous Evaluation of Large Language Models for Code Generation (2023) — 支持＋自我限制

- **作者**：Jiawei Liu et al.
- **出處**：arXiv:2305.01210
- **取得層級**：`B_僅摘要`（查證來源：arxiv-api）
- **跟我們這一條怎麼對應**：Liu et al.（EvalPlus）：把 HumanEval 測資擴 80 倍後，26 個模型的 pass@1 普遍下降。**這篇同時支持主張 2 和限制 1**——它證明執行式驗收有效（能抓出模型自評抓不到的錯），也證明執行式驗收的強度完全取決於測資量與質。我們用的正是它的 MBPP+／HumanEval+。

### LiveCodeBench: Holistic and Contamination Free Evaluation of Large Language Models for Code (2024) — 背景

- **作者**：Naman Jain et al.
- **出處**：arXiv:2403.07974　|　Website - https://livecodebench.github.io/
- **取得層級**：`B_僅摘要`（查證來源：arxiv-api）
- **跟我們這一條怎麼對應**：Jain et al.（LiveCodeBench）：我們 LCB v2/v3 的來源；它同時是主張 2（執行式）與方法 2（污染）的共同支點。

### Measuring Coding Challenge Competence With APPS (2021) — 背景

- **作者**：Dan Hendrycks et al.
- **出處**：arXiv:2105.09938　|　NeurIPS 2021. Code and the APPS dataset is available at https://github.com/hendrycks/apps
- **取得層級**：`B_僅摘要`（查證來源：arxiv-api）
- **跟我們這一條怎麼對應**：Hendrycks et al.（APPS）：競賽題 × 測試式評測。

### SWE-bench: Can Language Models Resolve Real-World GitHub Issues? (2023) — 背景

- **作者**：Carlos E. Jimenez et al.
- **出處**：arXiv:2310.06770　|　Data, code, and leaderboard are available at https://www.swebench.com ICLR 2024, https://openreview.net/forum?id=VTF8yNQM66
- **取得層級**：`B_僅摘要`（查證來源：arxiv-api）
- **跟我們這一條怎麼對應**：Jimenez et al.（SWE-bench）：真實 repo 的執行式驗收（跑既有測試套件），是「執行式」能推到多遠的參照點。

### Competition-Level Code Generation with AlphaCode (2022) — 支持

- **作者**：Yujia Li et al.
- **出處**：arXiv:2203.07814 · DOI 10.1126/science.abq1158　|　74 pages
- **取得層級**：`B_僅摘要`（查證來源：arxiv-api）
- **跟我們這一條怎麼對應**：Li et al.（AlphaCode）：大量抽樣後**用測試過濾**再提交，是「重抽＋執行式閘門」在競賽程式上的大規模先例。對展場而言，這是「我們的做法不是怪招」的最好背書。

### Competition-level code generation with AlphaCode (2022) — 支持

- **作者**：Yujia Li et al.
- **出處**：DOI 10.1126/science.abq1158　|　Science
- **取得層級**：`C_僅書目`（查證來源：crossref-doi）
- **跟我們這一條怎麼對應**：同一篇的 Science 正式版書目。

### Execution-Based Evaluation for Open-Domain Code Generation (2023) — 支持

- **作者**：Zhiruo Wang et al.
- **出處**：DOI 10.18653/v1/2023.findings-emnlp.89　|　Findings of the Association for Computational Linguistics: EMNLP 2023
- **取得層級**：`C_僅書目`（查證來源：crossref-doi）
- **跟我們這一條怎麼對應**：Wang et al.（ODEX）：開放領域程式生成的執行式評測，說明執行式評測可離開競賽題設定。

### JudgeBench: A Benchmark for Evaluating LLM-based Judges (2024) — 支持

- **作者**：Sijun Tan et al.
- **出處**：arXiv:2410.12784　|　Published as a conference paper at ICLR 2025
- **取得層級**：`B_僅摘要`（查證來源：arxiv-api）
- **跟我們這一條怎麼對應**：Tan et al.（JudgeBench）：把判斷題做成**客觀可驗證**的難題對後，各種 LLM judge（含 fine-tuned judge 與 reward model）表現大幅下滑、部分僅略高於隨機。這是「模型自評在客觀正確性上不可靠」最乾淨的量化證據，直接支持我們用執行結果而非模型意見當判準。

### From Generation to Judgment: Opportunities and Challenges of LLM-as-a-judge (2024) — 背景

- **作者**：Dawei Li et al.
- **出處**：arXiv:2411.16594　|　EMNLP 2025
- **取得層級**：`B_僅摘要`（查證來源：arxiv-api）
- **跟我們這一條怎麼對應**：Li et al.：LLM-as-a-judge 的綜述，可用來一次交代 judge 的偏誤族（位置、冗長、自我偏好）。**注意既有 236 筆已收錄 MT-Bench、Fair Evaluators、Self-Preference Bias、No Free Labels 等多篇**，這一塊我們其實不缺，別重複買。

### An Empirical Study of the Non-Determinism of ChatGPT in Code Generation (2025) — 邊界

- **作者**：Shuyin Ouyang et al.
- **出處**：DOI 10.1145/3697010　|　ACM Transactions on Software Engineering and Methodology
- **取得層級**：`C_僅書目`（查證來源：crossref-doi）
- **跟我們這一條怎麼對應**：Ouyang et al.：ChatGPT 生碼具非確定性，同題多次抽樣結果差異顯著。⇒ 任何「單次跑就下結論」的執行式評測本身也不穩；這支持我們做多次複製，也提醒展場別把單次 demo 當證據（鐵律 5 的外部依據）。

---

## 限制 1：測試預言問題——「過了寫下來的測試」≠「達成真需求」

> 我們的實測：即使有閘門，假交付率（accepted ∧ ¬hidden）OFF 49.2%、CONFORM 24.2%、OFF5 36.7%（`docs/HARNESS_STUDY_2026-09-07.md`）。`vacant_network/suitegauge.py` docstring 自己寫「單邊保證」。

### The Oracle Problem in Software Testing: A Survey (2015) — 支持

- **作者**：Earl T. Barr et al.
- **出處**：DOI 10.1109/tse.2014.2372785　|　IEEE Transactions on Software Engineering
- **取得層級**：`C_僅書目`（查證來源：crossref-doi）
- **跟我們這一條怎麼對應**：Barr, Harman, McMinn, Shahbaz, Yoo：**這就是我們這條限制的正式名字——test oracle problem**。展場說「我們發現過了測試不等於對」是不誠實的；這篇 2015 年的 survey 是必引。

### Software unit test coverage and adequacy (1997) — 支持

- **作者**：Hong Zhu et al.
- **出處**：DOI 10.1145/267580.267590　|　ACM Computing Surveys
- **取得層級**：`C_僅書目`（查證來源：crossref-doi）
- **跟我們這一條怎麼對應**：Zhu, Hall, May：test adequacy（測試充分性）的經典框架。我們的「單邊保證」在術語上就是 adequacy criterion 的已知弱點，不是新概念。

### An Analysis and Survey of the Development of Mutation Testing (2011) — 支持

- **作者**：Yue Jia & Mark Harman
- **出處**：DOI 10.1109/tse.2010.62　|　IEEE Transactions on Software Engineering
- **取得層級**：`C_僅書目`（查證來源：crossref-doi）
- **跟我們這一條怎麼對應**：Jia & Harman：mutation testing 綜述。**確認了 caller 的猜測**——我們 `suitegauge` 的「已知壞樁」在方法論上就是**手工的變異體（mutants）**，「每個壞樁都要被擋」＝ mutation score 要達標。應該直接改用這個術語。

### Are mutants a valid substitute for real faults in software testing? (2014) — 支持

- **作者**：René Just et al.
- **出處**：DOI 10.1145/2635868.2635929　|　Proceedings of the 22nd ACM SIGSOFT International Symposium on Foundations of Software Engineering
- **取得層級**：`C_僅書目`（查證來源：crossref-doi）
- **跟我們這一條怎麼對應**：Just et al.：實證 mutant 與 real fault 的偵測相關（比覆蓋率好）。這替我們的壞樁法提供「它確實量到東西」的背書。

### Coverage is not strongly correlated with test suite effectiveness (2014) — **反駁/邊界**

- **作者**：Laura Inozemtseva & Reid Holmes
- **出處**：DOI 10.1145/2568225.2568271　|　Proceedings of the 36th International Conference on Software Engineering
- **取得層級**：`C_僅書目`（查證來源：crossref-doi）
- **跟我們這一條怎麼對應**：Inozemtseva & Holmes：**覆蓋率與套件有效性相關性不強**。⇒ 我們若在展場用任何「覆蓋/通過比例」當品質代理，這篇會打臉；量具只能講「擋住了哪些具體壞樁」，不能升格成品質分數。

### State of mutation testing at google (2018) — 支持

- **作者**：Goran Petrović & Marko Ivanković
- **出處**：DOI 10.1145/3183519.3183521　|　Proceedings of the 40th International Conference on Software Engineering: Software Engineering in Practice
- **取得層級**：`C_僅書目`（查證來源：crossref-doi）
- **跟我們這一條怎麼對應**：Petrović & Ivanković：Google 的 mutation testing 工業實踐，說明「產生壞樁、看擋不擋得住」是可規模化的真實做法。

### An Industrial Application of Mutation Testing: Lessons, Challenges, and Research Directions (2018) — 支持

- **作者**：Goran Petrovic et al.
- **出處**：DOI 10.1109/icstw.2018.00027　|　2018 IEEE International Conference on Software Testing, Verification and Validation Workshops (ICSTW)
- **取得層級**：`C_僅書目`（查證來源：crossref-doi）
- **跟我們這一條怎麼對應**：同組作者的工業經驗報告（教訓與挑戰），適合對展場觀眾說明為何工業界也只能做到「下界」。

### Do Automatically Generated Unit Tests Find Real Faults? An Empirical Study of Effectiveness and Challenges (T) (2015) — **反駁/邊界**

- **作者**：Sina Shamshiri et al.
- **出處**：DOI 10.1109/ase.2015.86　|　2015 30th IEEE/ACM International Conference on Automated Software Engineering (ASE)
- **取得層級**：`C_僅書目`（查證來源：crossref-doi）
- **跟我們這一條怎麼對應**：Shamshiri et al.：自動產生的單元測試只找到約一半的真實缺陷。⇒ 我們用自動/半自動產生的驗收套件，**先驗上就應該預期一半左右漏掉**；我們量到的 24.2%～49.2% 假交付率完全落在這個已知範圍內，不該被講成異常或新發現。

### Metamorphic Testing (2019) — 支持

- **作者**：Tsong Yueh Chen et al.
- **出處**：DOI 10.1145/3143561　|　ACM Computing Surveys
- **取得層級**：`C_僅書目`（查證來源：crossref-doi）
- **跟我們這一條怎麼對應**：Chen et al.：metamorphic testing 綜述——在沒有 oracle 時用「輸入變換下輸出關係應保持」繞過 oracle 問題。這是我們限制 1 的**已知緩解路線**，展場可誠實地說「有這條路，我們沒走」。

### TOGA (2022) — 背景

- **作者**：Elizabeth Dinella et al.
- **出處**：DOI 10.1145/3510003.3510141　|　Proceedings of the 44th International Conference on Software Engineering
- **取得層級**：`C_僅書目`（查證來源：crossref-doi）
- **跟我們這一條怎麼對應**：Dinella et al.（TOGA）：神經式測試 oracle 生成。

### Assessing Evaluation Metrics for Neural Test Oracle Generation (2023) — **反駁/邊界**

- **作者**：Jiho Shin et al.
- **出處**：arXiv:2310.07856 · DOI 10.1109/TSE.2024.3433463　|　IEEE Transactions on Software Engineering, 2024
- **取得層級**：`B_僅摘要`（查證來源：arxiv-api）
- **跟我們這一條怎麼對應**：Shin et al.：批評 TOGA 一類神經 oracle 生成的評測指標**高估**了真實效能。⇒ 提醒我們對自家量具的數字保持同樣懷疑；「擋得住 12/12 壞解」是量具自己的尺，不是外部效度。

### Rethinking Verification for LLM Code Generation: From Generation to Testing (2025) — 支持

- **作者**：Zihan Ma et al.
- **出處**：arXiv:2507.06920
- **取得層級**：`B_僅摘要`（查證來源：arxiv-api）
- **跟我們這一條怎麼對應**：Ma et al.：明講 HumanEval／LiveCodeBench 這類評測套件**測資少且同質，細微錯誤測不出來**，因而虛抬表現、也污染 RLVR 的獎勵估計。這是 2025 年對我們這條限制最新、最貼題的外部確認。

### CoderEval: A Benchmark of Pragmatic Code Generation with Generative Pre-trained Models (2024) — 支持

- **作者**：Hao Yu et al.
- **出處**：DOI 10.1145/3597503.3623316　|　Proceedings of the IEEE/ACM 46th International Conference on Software Engineering
- **取得層級**：`C_僅書目`（查證來源：crossref-doi）
- **跟我們這一條怎麼對應**：Yu et al.（CoderEval）：獨立函式式 benchmark 會高估真實專案情境的表現。對應我們「過了寫下來的測試≠達成真需求」的另一個切面。

### ‘Improving ratings’: audit in the British University system (1997) — 支持

- **作者**：Marilyn Strathern
- **出處**：DOI 10.1002/(sici)1234-981x(199707)5:3<305::aid-euro184>3.0.co;2-4　|　European Review
- **取得層級**：`C_僅書目`（查證來源：crossref-doi）
- **跟我們這一條怎麼對應**：Strathern：**「當一個測度變成目標，它就不再是好測度」的原始出處**（Goodhart 的這個常見表述形式）。展場要講「閘門會被當成目標來優化」時引這個，比引二手轉述誠實。

### Defining and Characterizing Reward Hacking (2022) — 支持

- **作者**：Joar Skalse et al.
- **出處**：arXiv:2209.13085　|　23 pages; modified (fix typo in Figure 1, update link to code in Appendix, remove unrendered characters from arXiv abstract)
- **取得層級**：`B_僅摘要`（查證來源：arxiv-api）
- **跟我們這一條怎麼對應**：Skalse et al.：形式化定義 reward hacking。我們的「交付件通過可見驗收卻不過隱藏驗收」就是這個現象在驗收套件上的實例。

### Scaling Laws for Reward Model Overoptimization (2022) — 支持

- **作者**：Leo Gao et al.
- **出處**：arXiv:2210.10760
- **取得層級**：`B_僅摘要`（查證來源：arxiv-api）
- **跟我們這一條怎麼對應**：Gao, Schulman, Hilton：對代理目標過度優化會使真目標先升後降，且有可量化的規模律。⇒ 「把閘門開更嚴」不是無限有效，這是我們對展場承諾的上限。

### The Effects of Reward Misspecification: Mapping and Mitigating Misaligned Models (2022) — 支持

- **作者**：Alexander Pan et al.
- **出處**：arXiv:2201.03544　|　ICLR 2022; 19 pages
- **取得層級**：`B_僅摘要`（查證來源：arxiv-api）
- **跟我們這一條怎麼對應**：Pan, Bhatia, Steinhardt：獎勵誤設的實證地圖，能力越強誤設的代價越大。

### Goodhart's Law in Reinforcement Learning (2023) — 支持

- **作者**：Jacek Karwowski et al.
- **出處**：arXiv:2310.09144
- **取得層級**：`B_僅摘要`（查證來源：arxiv-api）
- **跟我們這一條怎麼對應**：Karwowski et al.：Goodhart 定律在 RL 中的形式化處理。

### Concrete Problems in AI Safety (2016) — 背景

- **作者**：Dario Amodei et al.
- **出處**：arXiv:1606.06565　|　29 pages
- **取得層級**：`B_僅摘要`（查證來源：arxiv-api）
- **跟我們這一條怎麼對應**：Amodei et al.：reward hacking 作為具體 AI 安全問題的經典出處。

### The Surprising Creativity of Digital Evolution: A Collection of Anecdotes from the Evolutionary Computation and Artificial Life Research Communities (2020) — 支持

- **作者**：Joel Lehman et al.
- **出處**：DOI 10.1162/artl_a_00319　|　Artificial Life
- **取得層級**：`C_僅書目`（查證來源：crossref-doi）
- **跟我們這一條怎麼對應**：Lehman et al.：演化計算中「系統滿足了字面規格卻違背意圖」的大量真實軼事。**展場最好用的一篇**——外行看得懂，而且它講的就是我們的限制 1。

---

## 限制 2：hash chain 擋得住改中間、擋不住砍尾巴

> 我實測：砍掉尾巴 2 筆，`vacant_network/logbook.py::verify_chain` 仍回 True（它從創世逐筆檢查 seq/prev_hash/簽章，截斷後的前綴仍然自洽）。原因是**沒有長度承諾與外部錨**。

### A new approach to secure logging (2009) — 支持

- **作者**：Di Ma & Gene Tsudik
- **出處**：DOI 10.1145/1502777.1502779　|　ACM Transactions on Storage
- **取得層級**：`C_僅書目`（查證來源：crossref-doi）
- **跟我們這一條怎麼對應**：Ma & Tsudik：**這條限制的正式名字是 truncation attack**，定義為「刪除尾端一段連續的 log 紀錄」，並明說一般的 hash-chain／forward-secure MAC 方案擋不住它，要靠 forward-secure sequential aggregate 簽章。我們量到的行為是教科書案例，不是新發現。

### Forward-Secure Sequential Aggregate Authentication (2007) — 支持

- **作者**：Di Ma & Gene Tsudik
- **出處**：（無 DOI／arXiv）　|　IEEE Symposium on Security and Privacy
- **取得層級**：`C_僅書目`（查證來源：openalex）
- **跟我們這一條怎麼對應**：Ma & Tsudik 的 FssAgg 方案（IEEE S&P 2007），即上一條的機制面來源。（僅書目，未讀全文）

### Secure audit logs to support computer forensics (1999) — 支持

- **作者**：Bruce Schneier & John Kelsey
- **出處**：DOI 10.1145/317087.317089　|　ACM Transactions on Information and System Security
- **取得層級**：`C_僅書目`（查證來源：crossref-doi）
- **跟我們這一條怎麼對應**：Schneier & Kelsey：不可信機器上的安全稽核日誌經典，forward security 的來源。我們的 logbook 屬於這一族，該引它當祖先。

### Efficient Data Structures for Tamper-Evident Logging (2009) — 支持

- **作者**：Scott A. Crosby & Dan S. Wallach
- **出處**：（無 DOI／arXiv）　|　USENIX Security Symposium
- **取得層級**：`C_僅書目`（查證來源：openalex）
- **跟我們這一條怎麼對應**：Crosby & Wallach：history tree——用 Merkle 結構同時支援「成員證明」與**「這條 log 沒有被截斷或分叉」的證明**。這是我們要補的東西的具體設計。（僅書目，未讀全文）

### How to time-stamp a digital document (1991) — 支持

- **作者**：Stuart Haber & W. Scott Stornetta
- **出處**：DOI 10.1007/bf00196791　|　Journal of Cryptology
- **取得層級**：`C_僅書目`（查證來源：crossref-doi）
- **跟我們這一條怎麼對應**：Haber & Stornetta：數位時戳。**外部錨**（把 head 週期性公示到我們控制不了的地方）的原始論文。我們限制 2 的第二半「沒有外部錨」就是指這個。

### Certificate Transparency (2013) — 支持

- **作者**：B. Laurie et al.
- **出處**：DOI 10.17487/rfc6962　|　RFC Editor
- **取得層級**：`C_僅書目`（查證來源：crossref-doi）
- **跟我們這一條怎麼對應**：Certificate Transparency（RFC 6962）：STH 內含 `tree_size`，也就是**長度承諾**；加上 consistency proof，就能證明新樹是舊樹的延伸而非截斷。這是我們缺的那一塊的標準答案，而且是部署了十年的真實系統——展場可誠實地說「業界怎麼做我們知道，我們還沒做」。

### Certificate Transparency Version 2.0 (2021) — 支持

- **作者**：B. Laurie et al.
- **出處**：DOI 10.17487/rfc9162　|　RFC Editor
- **取得層級**：`C_僅書目`（查證來源：crossref-doi）
- **跟我們這一條怎麼對應**：CT 2.0，同上的現行版本。

### Transparency Overlays and Applications (2016) — 支持

- **作者**：Melissa Chase & Sarah Meiklejohn
- **出處**：DOI 10.1145/2976749.2978404　|　Proceedings of the 2016 ACM SIGSAC Conference on Computer and Communications Security
- **取得層級**：`C_僅書目`（查證來源：crossref-doi）
- **跟我們這一條怎麼對應**：Chase & Meiklejohn：transparency overlay 的形式化，把 CT 那套抽象成通用的可究責結構。若要把 Vacant 的收據講成 transparency log，這是理論依據。

### CONIKS: Bringing Key Transparency to End Users (2015) — 支持

- **作者**：Marcela S. Melara et al.
- **出處**：（無 DOI／arXiv）　|　USENIX Security Symposium
- **取得層級**：`C_僅書目`（查證來源：openalex）
- **跟我們這一條怎麼對應**：Melara et al.（CONIKS）：把 transparency 用在金鑰目錄、且**不需要使用者信任伺服器**。（僅書目，未讀全文）

### Rethinking Tamper-Evident Logging: A High-Performance, Co-Designed Auditing System (2025) — 支持

- **作者**：Rui Zhao et al.
- **出處**：arXiv:2509.03821 · DOI 10.1145/3719027.3765024　|　Proceedings of the 2025 ACM SIGSAC Conference on Computer and Communications Security
- **取得層級**：`B_僅摘要`（查證來源：arxiv-api）
- **跟我們這一條怎麼對應**：Zhao et al.（CCS 2025）：tamper-evident logging 的最新系統工作，說明這個題目仍在活躍演進，不是 2009 年就收工了。

---

## 限制 3：收據由交付方自簽、私鑰同 uid 可讀 ⇒ 證明的是金鑰不是主體

> 註：這一節與限制 4 有另一支 agent 平行調查，以下只列**我自己查證過**的，避免重複買。

### Reflections on trusting trust (1984) — **反駁/邊界**

- **作者**：Ken Thompson
- **出處**：DOI 10.1145/358198.358210　|　Communications of the ACM
- **取得層級**：`C_僅書目`（查證來源：crossref-doi）
- **跟我們這一條怎麼對應**：Thompson（Reflections on Trusting Trust）：**任何自己簽自己的證明鏈都停不住**——你最終要信任某個你沒檢查的東西。這是我們「可驗證收據」最根本的邊界，展場如果宣稱收據是自足的證明，這篇就是反例。

### Sigstore (2022) — 支持

- **作者**：Zachary Newman et al.
- **出處**：DOI 10.1145/3548606.3560596　|　Proceedings of the 2022 ACM SIGSAC Conference on Computer and Communications Security
- **取得層級**：`C_僅書目`（查證來源：crossref-doi）
- **跟我們這一條怎麼對應**：Newman, Meyers & Torres-Arias（Sigstore）：用 OIDC 身分 + 短期憑證 + 公開透明 log 取代長期私鑰持有，正面回應「簽章證明的是金鑰不是主體」。這是我們限制 3 的已知解法方向。

### in-toto: Providing farm-to-table guarantees for bits and bytes (2019) — 支持

- **作者**：Santiago Torres-Arias et al.
- **出處**：（無 DOI／arXiv）　|　USENIX Security Symposium
- **取得層級**：`C_僅書目`（查證來源：openalex（另一 agent 核過））
- **跟我們這一條怎麼對應**：Torres-Arias et al.（in-toto）：把「誰做了哪一步」綁進可驗證的供應鏈佈局。（由另一支 agent 核回書目；未讀全文）

---

## 限制 4：可究責層在 library/MCP 形態下是自願的，只有偵測力沒有阻止力

> 註：主力由另一支 agent 調查，以下為我獨立查證的書目。

### The protection of information in computer systems (1975) — 支持

- **作者**：J.H. Saltzer & M.D. Schroeder
- **出處**：DOI 10.1109/proc.1975.9939　|　Proceedings of the IEEE
- **取得層級**：`C_僅書目`（查證來源：crossref-doi）
- **跟我們這一條怎麼對應**：Saltzer & Schroeder：**complete mediation（完整中介）**——每一次存取都必須經過檢查——正是我們這條限制的正式名字。library/MCP 形態違反的就是這一條。

### A note on the confinement problem (1973) — 支持

- **作者**：Butler W. Lampson
- **出處**：DOI 10.1145/362375.362389　|　Communications of the ACM
- **取得層級**：`C_僅書目`（查證來源：crossref-doi）
- **跟我們這一條怎麼對應**：Lampson：confinement problem。「把不受信任的程式關住」這件事的邊界（含 covert channel）自 1973 年就被界定過。

### Defeating Prompt Injections by Design (2025) — 支持

- **作者**：Edoardo Debenedetti et al.
- **出處**：arXiv:2503.18813　|　Updated version with newer models and link to the code
- **取得層級**：`B_僅摘要`（查證來源：arxiv-api）
- **跟我們這一條怎麼對應**：Debenedetti et al.（CaMeL）：把控制流從模型手上拿走以硬性防 prompt injection，**並量了代價**（作者報告在 AgentDojo 上以可證明的安全性解出 77% 的任務）。對我們最有用的是它示範了「強制力要付效用代價」可以被量化——這正是我們從自願走向強制時要先講清楚的帳。

### Progent: Securing AI Agents with Privilege Control (2025) — 支持

- **作者**：Tianneng Shi et al.
- **出處**：arXiv:2504.11703
- **取得層級**：`B_僅摘要`（查證來源：arxiv-api）
- **跟我們這一條怎麼對應**：Shi et al.（Progent）：以權限控制（privilege control）為 agent 加上執行期強制層。

### Systems Security Foundations for Agentic Computing (2025) — 支持

- **作者**：Mihai Christodorescu et al.
- **出處**：arXiv:2512.01295
- **取得層級**：`B_僅摘要`（查證來源：arxiv-api）
- **跟我們這一條怎麼對應**：Christodorescu et al.：agentic computing 的系統安全基礎，可用來說明我們的可究責層在整個堆疊裡的位置（偵測層而非強制層）。

### IsolateGPT: An Execution Isolation Architecture for LLM-Based Agentic Systems (2025) — 支持

- **作者**：Yuhao Wu & et al.
- **出處**：DOI 10.14722/ndss.2025.241131　|　NDSS 2025
- **取得層級**：`C_僅書目`（查證來源：另一 agent 核過，本檔未獨立複核）
- **跟我們這一條怎麼對應**：Wu et al.（IsolateGPT）：LLM agent 的執行隔離架構。（由另一支 agent 核回書目；未讀全文）

---

## 方法 2：benchmark 污染與樣本外

> 我們用 LiveCodeBench 的 contest_date 做樣本外，但自己寫了「v3 全部不晚於 2024-08-10，不能宣稱晚於訓練截止」。

### LiveCodeBench: Holistic and Contamination Free Evaluation of Large Language Models for Code (2024) — 支持

- **作者**：Naman Jain et al.
- **出處**：arXiv:2403.07974　|　Website - https://livecodebench.github.io/
- **取得層級**：`B_僅摘要`（查證來源：arxiv-api）
- **跟我們這一條怎麼對應**：Jain et al.（LiveCodeBench）：**我們用的題庫本身那篇**，以競賽發布日做時間切分來抗污染。必引。

### Data Contamination Through the Lens of Time (2023) — 支持

- **作者**：Manley Roberts et al.
- **出處**：arXiv:2310.10628
- **取得層級**：`B_僅摘要`（查證來源：arxiv-api）
- **跟我們這一條怎麼對應**：Roberts et al.（ICLR 2024 題名 *To the Cutoff... and Beyond?*）：用 GPT 訓練截止當自然實驗，在 Codeforces / Project Euler 上找到 pass rate 與**GitHub 熱門度**、發布日期的顯著趨勢。⇒ 這篇既支持我們的時間切分法，也警告**光有日期還不夠**：同一題在 GitHub 上越紅越可能被記住。我們的 LCB 樣本外若不控制這個變項，結論會被質疑。

### Task Contamination: Language Models May Not Be Few-Shot Anymore (2024) — 支持

- **作者**：Changmao Li & Jeffrey Flanigan
- **出處**：DOI 10.1609/aaai.v38i16.29808　|　Proceedings of the AAAI Conference on Artificial Intelligence
- **取得層級**：`C_僅書目`（查證來源：crossref-doi）
- **跟我們這一條怎麼對應**：Li & Flanigan（Task Contamination）：以時間序列方式顯示 LLM 在訓練截止**之前**發布的資料集上表現明顯較好。我們做樣本外的理由就是這個。

### Rethinking Benchmark and Contamination for Language Models with Rephrased Samples (2023) — **反駁**

- **作者**：Shuo Yang et al.
- **出處**：arXiv:2311.04850
- **取得層級**：`B_僅摘要`（查證來源：arxiv-api）
- **跟我們這一條怎麼對應**：Yang et al.：**改寫過的測資（改述、翻譯）可以輕易繞過 n-gram 去污染**，13B 模型能靠它把 benchmark 刷到接近 GPT-4；他們還在 RedPajama、StarCoder-Data 裡驗出 8–18% 的 HumanEval 重疊。⇒ 我們「用日期窗就算乾淨」的說法必須降級：日期只擋逐字外洩，擋不住改寫外洩。這條要寫進展場的誠實邊界。

### Proving Test Set Contamination in Black Box Language Models (2023) — 支持

- **作者**：Yonatan Oren et al.
- **出處**：arXiv:2310.17623
- **取得層級**：`B_僅摘要`（查證來源：arxiv-api）
- **跟我們這一條怎麼對應**：Oren et al.：不需要知道訓練資料，用交換題目順序的可交換性檢定就能**提供污染的統計證據**。⇒ 這是我們可以真的跑、而且成本低的補強；如果要把「樣本外」講得更硬，這是最短路徑。

### Investigating Data Contamination in Modern Benchmarks for Large Language Models (2024) — 支持

- **作者**：Chunyuan Deng et al.
- **出處**：DOI 10.18653/v1/2024.naacl-long.482　|　Proceedings of the 2024 Conference of the North American Chapter of the Association for Computational Linguistics: Human Language Technologies (Volume 1: Long Papers)
- **取得層級**：`C_僅書目`（查證來源：crossref-doi）
- **跟我們這一條怎麼對應**：Deng et al.：在現代 benchmark 上實測污染。

### Data Contamination: From Memorization to Exploitation (2022) — 支持

- **作者**：Inbal Magar & Roy Schwartz
- **出處**：DOI 10.18653/v1/2022.acl-short.18　|　Proceedings of the 60th Annual Meeting of the Association for Computational Linguistics (Volume 2: Short Papers)
- **取得層級**：`C_僅書目`（查證來源：crossref-doi）
- **跟我們這一條怎麼對應**：Magar & Schwartz：區分「記住」與「利用記住的東西」，這個區分對我們解釋 LCB v2/v3 差異有用。

### Don't Make Your LLM an Evaluation Benchmark Cheater (2023) — 支持

- **作者**：Kun Zhou et al.
- **出處**：arXiv:2311.01964　|　11 pages
- **取得層級**：`B_僅摘要`（查證來源：arxiv-api）
- **跟我們這一條怎麼對應**：Zhou et al.：benchmark 作弊的風險與建議的回報規範。

### Quantifying Memorization Across Neural Language Models (2022) — 背景

- **作者**：Nicholas Carlini et al.
- **出處**：arXiv:2202.07646
- **取得層級**：`B_僅摘要`（查證來源：arxiv-api）
- **跟我們這一條怎麼對應**：Carlini et al.：記憶量隨模型規模、重複次數、上下文長度成長。我們跨 12B/27B 比較時，這是必須承認的混淆項。

### Benchmark Data Contamination of Large Language Models: A Survey (2024) — 背景

- **作者**：Cheng Xu et al.
- **出處**：arXiv:2406.04244　|　31 pages, 7 figures, 3 tables
- **取得層級**：`B_僅摘要`（查證來源：arxiv-api）
- **跟我們這一條怎麼對應**：Xu et al.：污染綜述，可一次交代全景。

### Recent Advances in Large Langauge Model Benchmarks against Data Contamination: From Static to Dynamic Evaluation (2025) — 背景

- **作者**：Simin Chen et al.
- **出處**：arXiv:2502.17521　|　Github Link: https://github.com/SeekingDream/Static-to-Dynamic-LLMEval
- **取得層級**：`B_僅摘要`（查證來源：arxiv-api）
- **跟我們這一條怎麼對應**：Chen et al.：從靜態到動態評測的抗污染進展綜述（2025）。

### The SWE-Bench Illusion: When State-of-the-Art LLMs Remember Instead of Reason (2025) — 支持

- **作者**：Shanchao Liang et al.
- **出處**：arXiv:2506.12286
- **取得層級**：`B_僅摘要`（查證來源：arxiv-api）
- **跟我們這一條怎麼對應**：Liang et al.（SWE-Bench Illusion）：在 SWE-bench 上顯示相當部分表現來自記憶而非推理。

### The SWE-Bench Illusion: When State-of-the-Art LLMs Remember Instead of Reason (2026) — 支持

- **作者**：Shanchao Liang et al.
- **出處**：DOI 10.1145/3786583.3786882　|　Proceedings of the IEEE/ACM 48th International Conference on Software Engineering: Software Engineering in Practice
- **取得層級**：`C_僅書目`（查證來源：crossref-doi）
- **跟我們這一條怎麼對應**：同一篇的 ICSE 2026 正式版書目。

---

## 方法 3：預註冊與多重比較

> 我們做四狀態預註冊、Holm 校正、精確 McNemar、winner's curse 免責。

### The preregistration revolution (2018) — 支持

- **作者**：Brian A. Nosek et al.
- **出處**：DOI 10.1073/pnas.1708274114　|　Proceedings of the National Academy of Sciences
- **取得層級**：`C_僅書目`（查證來源：crossref-doi）
- **跟我們這一條怎麼對應**：Nosek et al.：預註冊革命——把「事前宣告」與「事後探索」分開的標準論述。我們 `docs/PREREG_V2.md` 的做法源流在此。

### Is Preregistration Worthwhile? (2020) — **反駁**

- **作者**：Aba Szollosi et al.
- **出處**：DOI 10.1016/j.tics.2019.11.009　|　Trends in Cognitive Sciences
- **取得層級**：`C_僅書目`（查證來源：crossref-doi）
- **跟我們這一條怎麼對應**：Szollosi et al.（正式題名 *Is Preregistration Worthwhile?*）：**預註冊在理論不成熟的領域幫助有限**，它約束的是統計彈性而非理論品質，甚至可能給弱理論一層科學外觀。⇒ 我們不能把「有預註冊」當成結論可信的憑證；展場若要提預註冊，只能說它擋住了什麼（事後改判準），不能說它證明了什麼。

### False-Positive Psychology (2011) — 支持

- **作者**：Joseph P. Simmons et al.
- **出處**：DOI 10.1177/0956797611417632　|　Psychological Science
- **取得層級**：`C_僅書目`（查證來源：crossref-doi）
- **跟我們這一條怎麼對應**：Simmons, Nelson & Simonsohn：研究者自由度足以讓任何東西顯著。這是我們固定四狀態、事前寫死判準的直接理由。

### The Statistical Crisis in Science (2014) — 支持

- **作者**：Andrew Gelman & Eric Loken
- **出處**：DOI 10.1511/2014.111.460　|　American Scientist
- **取得層級**：`C_僅書目`（查證來源：crossref-doi）
- **跟我們這一條怎麼對應**：Gelman & Loken：分叉路花園——**就算沒有 p-hacking 的意圖，只要分析是看了資料才決定的，p 值就失效**。我們「不 pack ＝ 沒跑過」的紀錄紅線在方法論上對應這一條。

### A Simple Sequentially Rejective Multiple Test Procedure (1979) — 支持

- **作者**：Sture Holm
- **出處**：DOI 10.2307/4615733　|　Scandinavian Journal of Statistics
- **取得層級**：`C_僅書目`（查證來源：semanticscholar）
- **跟我們這一條怎麼對應**：Holm：**我們用的 Holm 校正的原始論文**。（CrossRef 查不到此 DOI，經 Semantic Scholar 核回；僅書目，未讀全文）

### Controlling the False Discovery Rate: A Practical and Powerful Approach to Multiple Testing (1995) — 背景

- **作者**：Yoav Benjamini & Yosef Hochberg
- **出處**：DOI 10.1111/j.2517-6161.1995.tb02031.x　|　Journal of the Royal Statistical Society Series B: Statistical Methodology
- **取得層級**：`C_僅書目`（查證來源：crossref-doi）
- **跟我們這一條怎麼對應**：Benjamini & Hochberg：FDR。與 Holm（控制 FWER）取捨不同；我們選了較保守的 Holm，引這篇可說明為何。

### Note on the Sampling Error of the Difference Between Correlated Proportions or Percentages (1947) — 支持

- **作者**：Quinn McNemar
- **出處**：DOI 10.1007/bf02295996　|　Psychometrika
- **取得層級**：`C_僅書目`（查證來源：crossref-doi）
- **跟我們這一條怎麼對應**：McNemar：**我們用的配對檢定的原始論文**。

### Equivalence Tests (2017) — 支持

- **作者**：Daniël Lakens
- **出處**：DOI 10.1177/1948550617697177　|　Social Psychological and Personality Science
- **取得層級**：`C_僅書目`（查證來源：crossref-doi）
- **跟我們這一條怎麼對應**：Lakens（正式題名 *Equivalence Tests*）：**我們 `tost_equiv_boot` 的方法來源**，也是唯一能把「沒差異」講成結論而非「沒測到」的正規做法。

### Why Most Discovered True Associations Are Inflated (2008) — 支持

- **作者**：John P. A. Ioannidis
- **出處**：DOI 10.1097/ede.0b013e31818131e7　|　Epidemiology
- **取得層級**：`C_僅書目`（查證來源：crossref-doi）
- **跟我們這一條怎麼對應**：Ioannidis：**winner's curse 的正式論述**——首次發現的效果量系統性上偏。我們「+14.2/+18.3/+17.5 pp」是選出來報的，這篇是免責聲明的出處。

### Why Most Published Research Findings Are False (2005) — 背景

- **作者**：John P. A. Ioannidis
- **出處**：DOI 10.1371/journal.pmed.0020124　|　PLoS Medicine
- **取得層級**：`C_僅書目`（查證來源：crossref-doi）
- **跟我們這一條怎麼對應**：Ioannidis 2005：為何多數發表結果是假的。低檢定力 + 多重比較的經典論證。

### Estimating the reproducibility of psychological science (2015) — 背景

- **作者**： 
- **出處**：DOI 10.1126/science.aac4716　|　Science
- **取得層級**：`C_僅書目`（查證來源：crossref-doi）
- **跟我們這一條怎麼對應**：Open Science Collaboration：心理學大規模複製失敗。我們做五次複製的理由在此。

### Leakage and the reproducibility crisis in machine-learning-based science (2023) — 支持

- **作者**：Sayash Kapoor & Arvind Narayanan
- **出處**：DOI 10.1016/j.patter.2023.100804　|　Patterns
- **取得層級**：`C_僅書目`（查證來源：crossref-doi）
- **跟我們這一條怎麼對應**：Kapoor & Narayanan：**ML 為基礎的科學中的洩漏與再現危機**，整理了 17 個領域、329 篇論文的洩漏型態。我們的 V/GT 分離、fail-closed 就是在防這個；這篇是最好的外部背書。

### With Little Power Comes Great Responsibility (2020) — **反駁/邊界**

- **作者**：Dallas Card et al.
- **出處**：arXiv:2010.06595　|　To appear at EMNLP 2020
- **取得層級**：`B_僅摘要`（查證來源：arxiv-api）
- **跟我們這一條怎麼對應**：Card et al.：NLP 的實驗普遍**檢定力不足**，很多宣稱的小幅提升根本測不出來。⇒ 我們 12B 那九個 +0.6～+5.8 pp 的資料點，「0/9 過校正」有可能是檢定力不足而非效果不存在。**這是我們目前說法最需要修正的地方**：應說「未確立」而非「不存在」，並補報檢定力。

### The Hitchhiker’s Guide to Testing Statistical Significance in Natural Language Processing (2018) — 支持

- **作者**：Rotem Dror et al.
- **出處**：DOI 10.18653/v1/p18-1128　|　Proceedings of the 56th Annual Meeting of the Association for Computational Linguistics (Volume 1: Long Papers)
- **取得層級**：`C_僅書目`（查證來源：crossref-doi）
- **跟我們這一條怎麼對應**：Dror et al.：NLP 統計顯著性檢定的實務指南。

### Replicability Analysis for Natural Language Processing: Testing Significance with Multiple Datasets (2017) — 支持

- **作者**：Rotem Dror et al.
- **出處**：DOI 10.1162/tacl_a_00074　|　Transactions of the Association for Computational Linguistics
- **取得層級**：`C_僅書目`（查證來源：crossref-doi）
- **跟我們這一條怎麼對應**：Dror et al.：**跨多個資料集做顯著性的 replicability analysis**，正是我們「跨題組用 Holm」在做的事。這是方法上最貼題的一篇。

### Show Your Work: Improved Reporting of Experimental Results (2019) — 支持

- **作者**：Jesse Dodge et al.
- **出處**：DOI 10.18653/v1/d19-1224　|　Proceedings of the 2019 Conference on Empirical Methods in Natural Language Processing and the 9th International Joint Conference on Natural Language Processing (EMNLP-IJCNLP)
- **取得層級**：`C_僅書目`（查證來源：crossref-doi）
- **跟我們這一條怎麼對應**：Dodge et al.：把運算預算與調參納入回報。我們的等預算設計與 `require_usage` 成本紀律對應這條。

### Deep Reinforcement Learning that Matters (2017) — 支持

- **作者**：Peter Henderson et al.
- **出處**：arXiv:1709.06560　|　Accepted to the Thirthy-Second AAAI Conference On Artificial Intelligence (AAAI), 2018
- **取得層級**：`B_僅摘要`（查證來源：arxiv-api）
- **跟我們這一條怎麼對應**：Henderson et al.：深度 RL 的再現性危機——隨機種子就能翻轉結論。我們每格跑 1000 seeds、做多次複製的理由。

### The Benchmark Lottery (2021) — **反駁/邊界**

- **作者**：Mostafa Dehghani et al.
- **出處**：arXiv:2107.07002
- **取得層級**：`B_僅摘要`（查證來源：arxiv-api）
- **跟我們這一條怎麼對應**：Dehghani et al.（Benchmark Lottery）：模型排名對 benchmark 與題目選擇極度敏感，「誰贏」有相當成分是抽籤。⇒ 我們跨 MBPP+/LCB/HumanEval+ 的結論若在不同題庫上不一致（27B 翻負就是一例），要先考慮這個解釋。

### We Need To Talk About Random Splits (2021) — 支持

- **作者**：Anders Søgaard et al.
- **出處**：DOI 10.18653/v1/2021.eacl-main.156　|　Proceedings of the 16th Conference of the European Chapter of the Association for Computational Linguistics: Main Volume
- **取得層級**：`C_僅書目`（查證來源：crossref-doi）
- **跟我們這一條怎麼對應**：Søgaard et al.：隨機切分會高估表現。與我們用 contest_date 做時間切分的選擇一致。

### Pre-registration for Predictive Modeling (2023) — 支持

- **作者**：Jake M. Hofman et al.
- **出處**：arXiv:2311.18807
- **取得層級**：`B_僅摘要`（查證來源：arxiv-api）
- **跟我們這一條怎麼對應**：Hofman et al.：**預測建模的預註冊**——把預註冊落到 ML 情境的具體提案。我們的四狀態預註冊可以直接引它當體例。

### Position: Why We Must Rethink Empirical Research in Machine Learning (2024) — 支持

- **作者**：Moritz Herrmann et al.
- **出處**：arXiv:2405.02200　|　20 pages, accepted for publication at ICML 2024, camera-ready version
- **取得層級**：`B_僅摘要`（查證來源：arxiv-api）
- **跟我們這一條怎麼對應**：Herrmann et al.（ICML 2024 position）：為何必須重思 ML 的實證研究，含多重比較與基準選擇。

### Perspectives on Machine Learning from Psychology's Reproducibility Crisis (2021) — 支持

- **作者**：Samuel J. Bell & Onno P. Kampman
- **出處**：arXiv:2104.08878　|　Added acknowledgements; assorted minor edits
- **取得層級**：`B_僅摘要`（查證來源：arxiv-api）
- **跟我們這一條怎麼對應**：Bell & Kampman：把心理學再現危機的教訓對照到 ML。對展場解說「為什麼我們這麼囉嗦」很好用。

---

## 找不到文獻支持的主張

以下是我**認真找過但沒找到**對應先行研究的。兩種可能：要嘛我們是真的新，
要嘛我們講錯了——兩種都要人類知道。

1. **「同源非線性降權 ＋ 行為推斷同源」這個組合**。
   既有 236 筆裡有 Sybil attack、cheap pseudonyms、sybilproof reputation、behavioral fingerprinting，
   但「**用鑑別題一致率在零 `controller_id` 的條件下推斷同源，再據以非線性降權**」
   我找不到直接對應。最接近的是既有清單裡的 behavioral fingerprinting 與
   *Dissociative Identity: Language Model Agents Lack Grounding for Reputation Mechanisms*。
   ⇒ 這可能是真的窄縫，但也**可能只是我搜尋詞不對**；它不影響展場，建議不要在展場宣稱新穎。

2. **「驗收套件是資料不是程式」（R452 / `vacant_network/suitespec.py`）當作安全性論證**。
   「限制表達力讓某類攻擊不可表達」在能力安全（capability security）與 DSL 設計裡是老觀念，
   但我找不到把它專門用在**去中心化執行的驗收套件**上的文獻。
   相鄰的 in-toto / SLSA 走的是簽章與佈局，不是表達力限制。
   ⇒ 值得記一筆，但同樣不建議在展場當成「我們發現」。

3. **展覽情境下「互動者同意」的可執行機制**。
   倫理面的規範主張（Hollanek 2024、Öhman & Floridi 2018）既有清單裡有，
   但「**用系統自己展示的可究責機制去證明自己守約**（同意／刪除證明）」
   這個做法，我沒找到先例。這是展覽設計的核心賣點之一，
   ⇒ 建議由人類判斷是否值得再找一輪（關鍵詞可試 consent receipts、GDPR 刪除證明、
   proof of erasure），我這一輪沒查到可靠對應就不編。

4. **`entrycost` 的結論「評審準確率才是綁定約束，外生入場費反而有害」**。
   機制設計那邊有大量入場費／押金文獻（既有清單已有 TrueBit、Proof of Diligence、
   verifier's dilemma 等），但**「入場費在評審不準時反而有害」這個方向性結論**
   我沒找到直接對應的先行研究。⇒ 這條若要在展場講，建議講成
   「我們的模擬顯示」而不是「已知」。

### 另外：這幾塊其實**不缺**，別重複買

- **LLM-as-judge 的可靠性問題**：既有 236 筆已收 MT-Bench、
  *Large Language Models are not Fair Evaluators*、*Self-Preference Bias*、
  *Justice or Prejudice*、*No Free Labels*、*LLM Evaluators Recognize and Favor Their Own Generations*
  等多篇。我這次只補了 JudgeBench（客觀可驗證任務上的硬證據）與一篇綜述。
- **Huang et al. 2023**（*LLMs Cannot Self-Correct Reasoning Yet*）**已經在既有 236 筆裡**，
  而且收了兩次（`agent信任` 與 `人類運作邏輯` 各一）。我這次做的是找**它之後**的後續，
  見主張 1 的 Kamoi 2024（TACL 綜述）、SCoRe 2024、Self-Correction Bench 2025。

---

## 我們的說法要怎麼改（給人類的行動清單）

按重要性排序。每一條都是**現在的措辭會被文獻打臉**的地方。

1. **「迴圈沒有用」→「未經訓練的、prompt 層級的迴圈，在我們量到的尺度上沒有可複製的增益」**。
   理由：SCoRe（arXiv:2409.12917）用 RL 訓練得到了真的自我修正；
   Self-Correction Bench（arXiv:2507.02778）顯示盲點是觸發問題（加個 "Wait" 降 89.3%）。
   我們量的是**一種**迴圈，不是全部的迴圈。

2. **「0/9 過校正」不能講成「效果不存在」，要講「未確立」並補報檢定力**。
   理由：Card et al.（arXiv:2010.06595）證明這類實驗普遍檢定力不足，
   小幅提升本來就測不出來。這是我們目前最容易被戳破的一句。

3. **「用日期窗做樣本外 ⇒ 乾淨」要降級**。
   理由：Yang et al.（arXiv:2311.04850）證明改寫過的測資可輕易繞過去污染，
   且在 StarCoder-Data 等預訓練集裡驗出 8–18% 的 HumanEval 重疊；
   Roberts et al.（arXiv:2310.10628）證明 GitHub 熱門度是獨立的污染管道。
   ⇒ 日期只擋逐字外洩。repo 裡「v3 全部不晚於 2024-08-10」那句自我限制是對的，要保留並加強。

4. **「壞樁」改叫「手工變異體（mutants）」，「每個壞樁都要被擋」改叫 mutation score**。
   理由：Jia & Harman（DOI 10.1109/TSE.2010.62）。這不是修辭問題——
   用對術語，`suitegauge` 的「單邊保證」立刻有一整個領域的既有結果可以撐，
   包括 Just et al. 的「mutant 是 real fault 的有效代理」。

5. **假交付率 24.2%～49.2% 不要講成異常發現**。
   理由：Shamshiri et al.（DOI 10.1109/ASE.2015.86）早就量到自動產生的測試只找到約一半真缺陷。
   我們的數字落在已知範圍內。講「我們複製到了這個已知現象」比講「我們發現」誠實，
   而且對觀眾一樣有力。

6. **hash chain 砍尾巴要用正式名字：truncation attack**，並明講已知解法。
   理由：Ma & Tsudik（DOI 10.1145/1502777.1502779）定義了它；
   CT（RFC 6962）的 STH 帶 `tree_size` 就是長度承諾。
   ⇒ 展場可以誠實說「業界怎麼解我們知道（長度承諾＋外部錨），我們還沒做」，
   這比不提強，也比講成「我們發現」誠實。

7. **「可究責層是自願的」用 complete mediation 這個詞**（Saltzer & Schroeder 1975）。
   而且 CaMeL（arXiv:2503.18813）已經示範「要強制力就要付效用代價」可以被量化——
   我們從自願走向強制之前，要先講清楚這筆帳。

8. **提預註冊時不要把它當成可信度憑證**。
   理由：Szollosi et al.（DOI 10.1016/j.tics.2019.11.009）：
   預註冊約束的是統計彈性，不是理論品質。只能說它擋住了什麼，不能說它證明了什麼。

