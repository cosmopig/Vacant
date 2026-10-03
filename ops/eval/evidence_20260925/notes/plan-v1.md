# Vacant「裝了比沒裝好」評測計畫（給老闆核准用，2026-09-25）

這份計畫用白話寫。每個專有名詞第一次出現時都會解釋。程式裡的識別碼只放在最後的「技術附錄」。
所有數字後面都標來源：「（本機實測）」表示我們在這台機器真的跑出來的；「（論文）」表示只從論文或官方網頁讀到，還沒自己跑過。

---

## 0. 一頁摘要

**要回答的問題**：同一個 agent（會自己讀檔、寫檔、跑指令的 AI 程式，例如 pi、OpenCode、Claude Code、Codex），
同一個小模型，同一批公開題目，**只差「有沒有裝 Vacant」**，成績有沒有差？

**做法**：三組比較。A 組＝什麼都不裝。B 組＝裝了 Vacant 但只給「審稿人角色」的自我檢查、不給證據。C 組＝裝了 Vacant，
交件前先看紀錄（哪些檔沒開、哪些數字沒來源、說測過但沒跑），把該重做的地方退回去重做，最後附一張「檢查了什麼／改了什麼／哪些還沒驗證」的說明。

**先跑哪些題庫**（題庫＝公開的考題集，附官方的跑題與評分程式）：
1. **DABstep**（付款資料分析，要讀一本商業手冊才答得對）：82 題（10 題真正標準答案 + 72 題簡單題）。
2. **SpreadsheetBench Verified**（真人論壇的試算表題，要讀給定的 xlsx 才算得出）：先 40 題。
3. **Terminal-Bench 2.0 抽樣**（終端機工程題）：8 題，當作「程式類」的邊界檢查。
4. 另外跑一個「模型本身沒壞掉」的對照：LiveCodeBench v6，用官方程式跑 gemma-3-12b-it，看能不能接近論文的 32.0 分。這個**不比較 Vacant**，只證明我們用的模型與大家發表的是同一個等級。

**錢**：老闆儲值 5 美元，代理程式硬上限 4.80 美元，目前已花 0.024 美元（本機實測）。整個計畫估 **3.5～3.9 美元**，保留約 1 美元給重跑。
**時間**：機器時間約 12～15 小時（單線程），分 2～3 天；Vacant 零設定功能本身要先寫，見第 8 節。
**什麼時候能說「證明」**：只有在老闆簽了預註冊（先把規則寫死、簽名，再跑）的正式批次之後。在那之前，任何數字只能說「看得到差別」。

**老闆要決定的事**（詳見第 10 節）：主要模型選 gemma-3-12b-it 還是 qwen3.5-9b；同不同意「先 DABstep + SpreadsheetBench」；
免費模型只做試點；要不要在自己的電腦跑另外三個題庫；簽預註冊。

---

## 1. 名詞解釋（第一次看的人請先讀）

- **題庫（benchmark）**：公開的考題集，附標準答案或評分程式。大家用同一套題比較模型好壞。
- **harness（官方跑題與評分的程式）**：把題目餵給 agent、收答案、打分的程式。「照官方方式跑」就是用官方的 harness、官方的參數。
- **Harbor**：Terminal-Bench 2.0 的官方 harness。它同時內建了 pi、OpenCode、Claude Code、Codex 四個 agent 的接法，
  也能跑別的題庫（DABstep、SpreadsheetBench、Aider Polyglot）的「轉接版」。這是為什麼我們大量用它。
- **agent**：會自己做事的 AI 程式：讀檔、寫檔、跑指令、再問模型。我們支援四個：pi、OpenCode、Claude Code、Codex。
- **模型**：agent 背後在想事情的大語言模型。老闆要求用「像本機跑得動的小模型」（例如 12B、4-bit 量化）。
- **量化（quantization）**：把模型壓小（例如 fp4、fp8、bf16）。壓越小越像家用電腦跑的，但可能答得比較差。
- **提供者（provider）**：OpenRouter 背後真正跑模型的公司。同一個模型不同提供者可能量化不同，所以要**釘死**提供者。
- **call（一次呼叫）**：agent 問模型一次。一題通常要問很多次（每做一步問一次）。
- **token**：模型計費的單位，大約 0.7 個英文字或 1 個中文字。「推理 token」是模型在想但沒說出來的部分，也要付錢。
- **A / B / C 組（arm）**：同一題跑三種設定。A 沒裝 Vacant；B 裝了但只有「審稿人角色」；C 裝了完整的證據檢查。
- **oracle / nop**：oracle 是「把標準答案直接交上去」，一定要得滿分；nop 是「什麼都不做」，一定要 0 分。用來確認評分程式沒壞。
- **trace（紀錄鏈）**：Vacant 記下 agent 每一步做了什麼（讀了哪個檔、寫了什麼、跑了什麼），有簽章，事後改不了。
- **hook（掛鉤）／Stop hook**：agent 提供的插入點。「Stop hook」是 agent 說「我做完了」那一刻，Vacant 可以在這裡把它退回去重做。
- **預註冊（pre-registration）**：先把「跑幾題、看哪個數字、怎麼算才算贏」寫死並簽名，再跑。防止事後挑好看的數字。
- **配對比較（paired）**：同一題在 A 和 C 各跑一次，一題一題比，而不是比平均。
- **McNemar 檢定**：配對比較用的統計方法，只看「A 對 C 錯」和「A 錯 C 對」的題數。
- **bootstrap 信賴區間**：把題目重抽很多次，看差距會落在什麼範圍。
- **infra_void（基礎設施作廢）**：不是模型或 Vacant 的錯（網路斷、額度用完、容器建不起來）造成的失敗。這種題不算分，三組都重跑。

---

## 2. 哪些是這裡驗證過的，哪些只是讀論文

### 2.1 本機驗證過（有紀錄檔可查）
- 六個題庫的評分程式都做過 oracle＝滿分、nop＝0 分的檢查（Terminal-Bench 2 題、SpreadsheetBench 2 題、DABstep 2 題、
  LiveCodeBench 3 題、Aider 1 題在主機上、GDPval 只跑了假模型管線）。
- 用真模型（qwen3.5-9b，fp4）透過記錄代理程式各跑了 1～2 題：DABstep 5 號題答對、70 號題答錯；SpreadsheetBench 10452 號題答錯
  （算對 9 個值只寫進 5 個）；Terminal-Bench regex-log 題 0 分（模型把 16,384 個 token 全用在思考，一個動作都沒做）；
  LiveCodeBench 兩題都沒寫出程式（8,000 個 token 全在思考）；Aider Python 題一次答對、Go 題 2,000 token 全在思考沒答案；
  GDPval 跑到 8 回合上限還在找檔案。
- 每次呼叫的 token 數和費用都在代理程式的帳本裡（總花費 0.02414057 美元，41 次呼叫）。
- Harbor 內建四個 agent 的接法，我們讀了原始碼並用 pi 真的跑通（Terminal-Bench 與 SpreadsheetBench 各一題）。
- 容器（Docker）在這台機器要能上網，需要掛 CA 憑證並設三個環境變數；Ubuntu 系統的 apt 套件庫**連不到**（Aider 與 DABstep 的映像檔要在這裡建就會卡住），Debian 系統的可以。
- 統計功能：樣本數與檢定力用倉庫裡現成的函式算出來（第 6 節的表）。

### 2.2 只讀到、沒自己跑過（引用時要註明）
- 小模型在各題庫的公開成績：SpreadsheetBench 的 Qwen3-8B 15.9%（論文 arXiv:2605.22642 表 1，但那是 912 題舊版，不是我們要跑的 400 題驗證版）；
  DABstep 的 Llama-3.3-70B 簡單題 68%／困難題 3.7%（arXiv:2506.23719 表 1，二手擷取）；Terminal-Bench 2.0 的 Qwen3-8B 約 2.5%（搜尋摘要，**未經原始來源核對**）；
  Aider Polyglot 排行榜最小的模型是 gemma-3-27b（4.9%），沒有 27B 以下的模型。
- gemma-3-12b-it 的 LiveCodeBench 32.0 分（Gemma 3 技術報告 arXiv:2503.19786 表 18；表 21 說是 8 次取樣平均，沒寫題目日期範圍）。
- OpenRouter 免費模型每天 50 次的上限：從金鑰資訊讀到，是真的；「儲值 10 美元以上變 1000 次」是常見說法，**官方表格沒抓到，未驗證**。
- 自我檢查的研究結論：模型自己找自己的錯，沒有外部訊號時幾乎沒用（Huang 等，ICLR 2024）；告訴它錯在哪裡，它就能改（Tyen 等，ACL Findings 2024）；
  比較時要相同起點、相同預算（Kamoi 等，TACL 2024）。這三篇是 C 組設計的依據。

---

## 3. 選哪些題庫、先跑哪些、每個怎麼釘死「官方跑法」

### 3.1 一覽表

| 順序 | 題庫 | 角色 | 這次跑的子集 | 為什麼 | 每題花費（A 組，本機實測） |
|---|---|---|---|---|---|
| 1 | DABstep | 主力（有「給定資料」） | 10 題 dev（真標準答案）＋ 72 題簡單題 | 最像老闆的例子：要讀手冊才對；評分是確定性的；便宜 | 4～8 次呼叫，0.0012～0.0067 美元 |
| 2 | SpreadsheetBench Verified | 主力（有「給定資料」） | 40 題（先 10 題試點） | 讀 xlsx 算 xlsx，逐格比對；觀眾一眼看得懂 | 7 次呼叫，0.0074 美元，2.5 分鐘 |
| 3 | Terminal-Bench 2.0 抽樣 | 程式類邊界檢查 | 10 題中的 8 題（兩題 qemu 太大） | 官方 harness 直接支援我們四個 agent，「完全照官方」做得到；但小模型可能全 0 分 | 1 次呼叫就燒 16k token，0.0023 美元；整題未知 |
| 4 | LiveCodeBench v6 | 模型再現對照（不比 Vacant） | 100 題（Harbor 的種子 42 抽樣）或全部 1,055 題 | 證明我們的模型與論文同等級 | gemma-3-12b-it 估每題 0.0003 美元 |
| 延後 | Aider Polyglot | 備援程式題 | 225 題中挑 20～30 題 | 這台機器建不了映像檔（Ubuntu apt 被擋），要在老闆電腦跑 | 1～3 次呼叫，0.0001～0.0003 美元 |
| 不跑 | GDPval | — | — | 授權沒寫明、官方評分要 OpenAI 帳號、官方映像檔 5～8 GB、沒有 agent 可掛鉤 | — |

### 3.2 DABstep（第一優先）

**是什麼**：Adyen 公司出的付款資料分析題。每題給 7 個檔案（付款紀錄 payments.csv 23.6 MB、費用表 fees.json、**商業手冊 manual.md**、商家資料等），
問一個有標準答案的問題。困難題幾乎都要把手冊的規則和費用表交叉對照才答得對；簡單題有三分之一也要讀手冊（本機實測：3 題簡單 dev 題中 1 題需要手冊，7 題困難題全部需要）。

**為什麼選它**：這正是老闆說的情況——「資料夾裡有手冊，agent 沒開就寫答案」。「有沒有開 manual.md」是一個乾淨的二元訊號。

**官方跑法（釘死）**：
- 資料：HuggingFace `adyen/DABstep`，版本 `51884d33…`，授權 CC BY 4.0。題目檔 all.jsonl 450 題（72 簡單、378 困難，本機直接數的）；dev.jsonl 10 題（3 簡單、7 困難）。7 個資料檔的 sha256 都存在 `scratchpad/study/pin/`。
- 官方 agent：smolagents 的 CodeAgent（一個只能寫 Python 的迷你 agent），最多 10 步，每次回答最多 3,000 token，沒設溫度。要跑它必須釘 `smolagents==1.3.0` 與 `transformers==4.47.1`，否則裝不起來（本機實測）。
- 官方評分：scorer.py，數字允許誤差、字串模糊比對、清單比對；確定性、不用 AI 當評審。
- **注意**：450 題正式集的「答案」是 Harbor 從公開排行榜抽出來的「最短的被接受答案」，**不是官方標準答案**；只有 10 題 dev 是真的標準答案。所以標題數字用 dev 10 題，72 題簡單題另外標示「答案來自排行榜擷取」。

**我們的跑法與偏離（明講）**：
- 官方 agent 是 smolagents，不是我們四個 agent 之一，而且它是同一支程式裡直接呼叫模型，**沒有可掛鉤的獨立 agent 程序**，Vacant 掛不上去。
- **決定**：用 Harbor 的 DABstep 轉接版 + pi。Harbor 版的差別：題目改成「把答案寫進 /app/answer.txt」而不是呼叫 final_answer；agent 可以用 shell 和任何工具；agent 時限 1,800 秒。
  Harbor 自己用 claude-haiku-4.5 做過對照：原版 37.69 vs Harbor 36.92（130 題×4 次），簡單題兩邊一樣 84.52。這是 Harbor 版和原版「大致等價」的證據，但用的是強模型，不是我們的小模型。
- 另外**用官方 smolagents 跑一次 10 題 dev（A 組，不裝 Vacant）**當作「原版與 Harbor 版在我們的小模型上差多少」的錨。花費約 10 題 × 0.005 美元 = 0.05 美元。
- Harbor 的映像檔在建置時從 HuggingFace 的 `main` 分支抓資料（浮動版本）。我們改成用釘死的版本與 sha256 核對，並記錄。這台機器上還要把 Dockerfile 的 apt 步驟手動改掉（Ubuntu 套件庫被擋）；在老闆電腦上應該不用改。

**小模型基線（論文）**：Llama-3.3-70B 簡單 68.06%／困難 3.70%，Llama-3.2-1B 簡單 1.39%／困難 0%（arXiv:2506.23719 表 1，二手擷取）。沒有 Qwen 或 Gemma 的數字。
我們的 9B 模型在 2 題簡單題答對 1 題（本機實測，n=2 不能推論比例）。

### 3.3 SpreadsheetBench Verified（第二優先）

**是什麼**：從真人論壇收集的 Excel 問題，給一個輸入 xlsx，要求算出答案寫進輸出 xlsx 的指定範圍。400 題是專家驗證過的子集（2025-12 發布），每題 1 個測試案例。
評分：用 LibreOffice 重新計算公式後，逐格比對（小數四捨五入到兩位、日期轉換）。沒有 AI 評審。

**為什麼選它**：「數字是從給定檔案算出來的，還是編的」——這正是 Vacant 要抓的。而且試算表的對錯，觀眾看一眼就懂。
本機實測的那題正好示範：模型讀了檔、算對 9 個值，最後只寫進 5 個。這種「自己算的和自己寫的不一致」，Vacant 從紀錄就能看出來，不需要知道標準答案。

**官方跑法（釘死）**：
- 原始倉庫 RUCKBReasoning/SpreadsheetBench（commit `49b73a9…79`），授權 CC BY-SA 4.0。官方腳本是「一次問模型、執行程式碼、比對」（非 agent），最多 5 輪；沒設溫度。
- Harbor 轉接版：資料釘在 harbor-datasets commit `0ad7209b…`，400 題；容器是 python:3.11-slim + openpyxl 3.1.3 + pandas 2.2.0；agent 與評分各 600 秒；LibreOffice 在評分階段才裝。
  轉接版修了原版評分程式的 11 個 bug（Harbor 作者自述，我們讀碼確認存在）。對照：claude-code + haiku-4.5 原版 68.83 vs Harbor 68.25（400 題×3 次）。
- **決定**：用 Harbor 轉接版 + pi 當「參考跑法」。理由：它才有 agent 迴圈（Vacant 掛得上）、四個 agent 原生支援、評分比原版更正確。明講：這不是論文原本的非 agent 跑法。

**小模型基線（論文）**：Qwen3-4B 11.0、Qwen3-8B 15.9、Qwen3-14B 15.0、Qwen3-32B 17.6（arXiv:2605.22642 表 1）——但那是 **912 題舊版**，不是 400 題驗證版。
400 題驗證版目前**沒有任何**公開的小模型成績。這點要在展場標明。

**子集**：先 10 題試點，再 40 題正式（依 instruction_type 分層抽樣，種子寫進預註冊）。40 題 × 3 組 × 0.0074 美元 ≈ 0.9 美元，加 C 組重做約 1.2 美元。

### 3.4 Terminal-Bench 2.0 抽樣（第三，邊界檢查）

**是什麼**：89 題終端機工程題（修漏洞、設 git 伺服器、寫 regex 等）。官方 harness 就是 Harbor；官方抽樣集 10 題（commit `7e917f35…`）。
每題 agent 900 秒、評分 900 秒；映像檔用預建的 ghcr.io 版本（**用標籤不是用 digest 釘的**，所以要記下每次拉到的 digest）。

**為什麼**：這是唯一一個「官方 harness 原生支援我們四個 agent」的題庫，「完全照官方、只差 Vacant」在這裡是字面上做得到的。
Harbor 自己在 pi 的接法裡就會塞一個擴充檔進 agent 的設定目錄（用來限制回合數），Vacant 走同一條路，不動題目、不動評分。

**風險**：9B 模型第一次呼叫就把 16,384 個輸出 token 全用在「思考」，一個指令都沒下（本機實測）。網路上說 Qwen3-8B 約 2.5%（未核對）。
所以它排在第三，而且**只有在第 5 節的「思考預算」問題解決後才跑**。8 題 × 3 組，估 0.3～0.8 美元。

**子集**：10 題中排除 qemu-alpine-ssh、qemu-startup（建置時要下載幾百 MB 的 ISO 並建 32 GB 稀疏磁碟，這台機器不敢跑）。其餘 8 題映像檔共 3.9 GB（本機實測）。

### 3.5 LiveCodeBench v6（模型再現對照，不比 Vacant）

**是什麼**：程式競賽題，一次問模型、本機跑測資評分，沒有 agent 也沒有檔案。**Vacant 在這裡沒東西可看**，所以它不是 Vacant 的題庫。
它的用途是「harness 驗證」：我們用的模型透過 OpenRouter、量化過、跑出來的分數和論文接近嗎？

**釘死**：官方倉庫 LiveCodeBench/LiveCodeBench commit `28fef95e…`（2025-07-15/16，MIT）；資料 HF `livecodebench/code_generation_lite` 版本 `0fe84c39…`；release_v6 = 1,055 題（2023-05～2025-04）。
官方預設：每題 10 次取樣、溫度 0.2、top_p 0.95、輸出上限 2,000 token、每個測資 6 秒。
提示詞模板是固定的（我們可逐字重用）。安裝時 `anthropic` 套件要釘 0.42.0 否則裝不起來（本機實測）。

**要注意**：(1) 官方載入程式會把 6 個檔全抓，約 4.5 GB，這台機器沒有這個空間，要在老闆電腦跑。(2) Gemma 3 報告的 32.0 是「8 次取樣平均」、沒寫題目日期範圍，所以只能「大致接近」，不能「完全再現」。
(3) qwen3.5-9b 在這裡完全寫不出程式（思考 token 用光），所以這個對照用 **gemma-3-12b-it**（非推理模型）。100 題 × 1 次取樣約 0.03 美元；× 8 次約 0.26 美元。

### 3.6 Aider Polyglot（延後，老闆電腦）

225 道 Exercism 練習題（6 種語言）。官方 harness 是 aider 自己的 benchmark.py：**給兩次機會**，第二次會把測試失敗的輸出給模型。Harbor 轉接版只給一次、測試藏起來。
這台機器建不了它的映像檔（每種語言的 Dockerfile 第一行就 apt，Ubuntu 套件庫被擋）。排行榜上沒有 27B 以下的模型。
若要跑：老闆電腦、Harbor 版 + pi、挑 20～30 題、記錄「一次機會」這個偏離。Vacant 在這裡能抓的主要是「說測試過了但沒跑」。

### 3.7 harness 驗證步驟（每個題庫跑正式前都要過）
1. oracle 滿分、nop 零分（六個題庫本機已做）。
2. 模型再現：LiveCodeBench v6 用 gemma-3-12b-it 跑官方程式，目標在 32.0 附近（±5 分內視為「同等級」；差太多就要查量化或提示詞）。
3. 三組第一次呼叫的請求內容（去掉時間戳、session id）必須逐位元相同。不同就代表 Vacant 動到了提示詞，那一組作廢。
4. 每一題 C 組的紀錄鏈裡必須看得到步驟事件和 Stop 事件，否則代表 Vacant 沒裝上，那題記 infra_void。

---

## 4. 三組（A／B／C）與注入的文字

### 4.1 三組的定義
- **A 組**：agent 原封不動。Harbor 用它內建的 pi（或其他 agent）接法。
- **B 組**：A 組 + Vacant 安裝為「persona（角色）」模式。agent 說做完時，Vacant 退一次回去，附上固定的「審稿人角色」文字，**沒有任何證據行**。這是 Huang 等人說的「內在自我修正」，預期幾乎沒用，有時還會改壞。
- **C 組**：A 組 + Vacant 安裝為「evidence（證據）」模式。agent 說做完時，Vacant 跑證據檢查（純看紀錄，不用模型）；有發現才退回，附上定位好的證據行；最多 2 輪；最後寫一張交件說明。
- B 和 C 的文字**除了證據那一段**逐位元相同（這是倉庫的 KS-1 鐵律：三組模板逐字相同，唯一差異是注入的區塊）。
- 安裝只加掛鉤，**不裝技能檔（SKILL.md）**，因為技能會改模型的系統提示與工具清單，等於多一個差異。
- Vacant 寫的任何東西都不落在題目的工作目錄（評分程式會讀那裡），全部放在 Harbor 會自動收走的記錄目錄。

### 4.2 注入的文字（英文原文給 agent；中譯給老闆看）

**固定開頭（B、C 共用）**
> Before delivery: a review of the recorded steps of this task.
> （交件前：針對這個任務有紀錄的步驟做一次檢視。）

**審稿人角色（B、C 共用）**
> Take the role of a careful reviewer who reads a draft against the materials given for the task. Check that every specific number, date and name in the deliverable can be traced to a given file, the task message, or a computation done in this task; that every file named in the task was actually opened; and that any claim of testing or verification matches a step that ran. Redo only the parts that do not hold. Anything that remains unverified goes under a heading "Unverified" in the final message.
> （請扮演一位仔細的審稿人，對照任務給的材料讀這份草稿。檢查交付物裡每個具體的數字、日期、名稱都能追到某個給定的檔案、任務訊息、或這次任務裡做過的計算；任務點名的每個檔案都真的打開過；任何「測過／驗證過」的說法都對得上真的跑過的步驟。只重做站不住的部分。仍未驗證的，放在最後訊息的「Unverified」標題下。）

**證據區塊（只有 C 有；每行由紀錄產生，格式固定，例）**
> - report.md line 3, value 999: no source found in the recorded steps; the given file data.csv was not opened. Action: open data.csv and redo lines 3-7, or label the value as an assumption.
> - manual.md: not opened in the recorded steps. Action: open it and re-check the parts of the answer that depend on its rules.
> - Final message says "tests pass"; no test command ran after the last edit at step 9. Action: run the tests and report the result.
> （report.md 第 3 行的 999 在紀錄裡找不到來源；給定檔 data.csv 沒開過。動作：開 data.csv 重做第 3～7 行，或標成假設。／manual.md 在紀錄裡沒開過。動作：打開並重看依賴它規則的部分。／最後訊息說「測試通過」，但第 9 步最後一次修改後沒有跑過測試指令。動作：跑測試並回報結果。）

**固定結尾（B、C 共用）**
> This note lists what the record shows; it does not say whether the final answer is right. When done, end your message with three headings: Checked, Fixed, Unverified.
> （這張便條只列出紀錄顯示的事，不判斷最後答案對不對。完成後，訊息結尾請分三個標題：Checked、Fixed、Unverified。）

**KS-1 檢查**：以上文字沒有「你有責任／會被懲罰／要負責」（倉庫禁止清單的 7 個詞），沒有「信任、分數、聲譽」字眼，沒有 agent 或模型的識別碼，沒有「你忽略了」這種第二人稱指責。
這些常數在程式載入時就會自動檢查，每一行送出前再檢查一次。

### 4.3 預算配對（Kamoi 等人的要求：起點相同、資源差異要報告）
- 三組的 harness、agent 版本、模型、提供者、量化、提示詞、時限、評分程式全部相同；只差 Vacant 模式。
- B 組固定多 1 輪；C 組 0～2 輪（有發現才退回）。所以 **C 組平均會多用呼叫和 token**。這不是 bug，是設計；但要誠實報告。
- 報告時每組都列：呼叫次數、輸入 token、輸出 token（含推理 token）、費用、牆鐘時間、Vacant 退回輪數、發現數。
- 預註冊一個「配對版」比較：C 組只算第一輪退回後的結果 vs B 組的一輪，讓兩組呼叫數接近。
- 額外報告「C 組在沒有任何發現的題目上」的成績是否等於 A（無害檢查）。

---

## 5. 模型

### 5.1 免費模型先試，但要知道 50 次／天代表什麼
- 這把金鑰目前**每天 50 次**免費模型呼叫（本機從金鑰資訊讀到，真的）。因為儲值不到 10 美元，上限不變。
- 一題 DABstep 要 4～10 次呼叫，SpreadsheetBench 約 7 次，三組加 Vacant 重做約 25～30 次。**所以 50 次／天 = 一天大約 1～2 題（三組）**。
- **50 次／天能學到的**：一個「試點」——確認免費模型（例如 gemma-4-26b-a4b-it:free）能不能用工具、能不能完成一題、Vacant 的掛鉤有沒有裝上。學不到任何統計上的東西。
- **要 1000 次／天才能做的**：40～100 題的正式批次。網路上說儲值滿 10 美元就升到 1000 次／天，**未驗證**；而且付費模型根本不受這個上限影響。
- **結論**：既然老闆已經儲值 5 美元，**主線用付費的小模型**，免費模型只在試點階段跑 1～2 題當對照，並記錄。
- 注意：免費提供者可能會記錄我們送出的提示詞；題目是公開的所以可接受，但要記在環境清單裡；**展場訪客的資料絕不走免費端點**。

### 5.2 付費小模型（釘死提供者與量化）
| 模型 | 提供者／量化 | 價格（每百萬 token，輸入／輸出） | 特性 | 建議 |
|---|---|---|---|---|
| google/gemma-3-12b-it | DeepInfra／bf16 | 0.05／0.15 美元 | 非推理模型，輸出長度可預期，支援工具呼叫，輸出上限 16,384 | **主要模型**。同一份 12B 權重就是大家在家用 Q4 跑的那份，但這裡是未量化版——要標明 |
| qwen/qwen3.5-9b | Darkbloom／fp4 | 0.08／0.13 美元 | 推理模型；本機實測 6 個題庫裡 4 個出現「思考 token 用光、沒有答案」 | 第二模型，**只有在 `reasoning.effort=low`（端點有這個參數，未測）能止血時才用** |
| openai/gpt-oss-20b | AkashML／fp4 | 0.02／0.10 美元 | 推理模型，最便宜 | 備援，沒測過 |
| gemma-4-26b-a4b-it:free | Google AI Studio／量化未知 | 0 | 26B 總參數、4B 啟用；免費 | 只做試點（50 次／天） |

理由：老闆要「像本機的 12B gemma 4-bit」。OpenRouter 沒有 12B 的 gemma-4；gemma-3-12b-it 是最接近的，而且不會像 9B 推理模型那樣把預算燒在思考上。
每一次呼叫，代理程式都把實際的提供者記下來；量化從當天的端點快照對回去（OpenRouter 的回應沒有量化欄位）。

### 5.3 取樣參數：跟官方走
- Harbor 上的題庫（Terminal-Bench、SpreadsheetBench、DABstep 轉接版）：官方不設溫度，由 agent 與提供者預設決定；我們不加任何參數，把第一次請求的原始內容存檔證明。
- LiveCodeBench 官方：溫度 0.2、top_p 0.95、輸出 2,000 token；我們照抄，但取樣次數 n=1（或 8，若預算准）並明講。
- DABstep 官方 smolagents：輸出 3,000 token、最多 10 步；照抄。

---

## 6. 指標與統計

### 6.1 指標
- **主要**：官方分數（每題 0/1，由官方評分程式決定）。
- **次要**（每題都算，三組都算）：
  1. 沒來源的具體數值數：交付物裡的數字／日期，在紀錄裡找不到來源的個數。A 組沒有 Vacant 紀錄，改用 Harbor 自己存的軌跡（每個工具呼叫的輸入輸出）重建，標成「近似」。
  2. 沒讀的給定資料：任務給的檔案裡沒開過的個數（DABstep 的 manual.md、SpreadsheetBench 的輸入 xlsx）。
  3. 費用（美元）、呼叫次數、token（分輸入／輸出／推理）、牆鐘時間。
  4. **傷害**：A 對 C 錯的題數；以及 C 組內「第一次說做完時已經對、退回重做後變錯」的題數（Vacant 的紀錄鏈存有兩個時間點的交付物，都可以用官方評分程式離線打分）。
  5. Vacant 誤報率：在 A 組（用軌跡重建）與正確題上，Vacant 會退回多少題。這個要在正式跑之前用離線重放先量。

### 6.2 配對與檢定（用倉庫現成的函式）
- 主要比較 C vs A：McNemar 精確檢定（只看不一致的題）。
- 差距的 95% bootstrap 信賴區間（2,000 次重抽）。
- 次要比較 C vs B、B vs A，和多個題庫，用 Holm 校正。
- 「無害」用等價檢定（TOST）：C 在無發現題上與 A 的差距落在 ±5 個百分點內。

### 6.3 樣本數：多少題才看得出差別（本機用倉庫函式算的，α=0.05、檢定力 0.8）
| A 與 C 不一致的題目比例 | 不一致中 C 贏的比例 | 相當於分數差 | 需要題數 |
|---|---|---|---|
| 30% | 80% | +18 個百分點 | 77 |
| 30% | 75% | +15 | 112 |
| 30% | 70% | +12 | 172 |
| 30% | 66.7% | +10 | 248 |
| 40% | 75% | +20 | 84 |
| 20% | 80% | +12 | 115 |

反過來看：10 題的檢定力只有 1～3%，30 題約 30%，50 題約 55～58%，100 題約 90%（差 +18 個百分點時）。
**所以**：試點（10 題）只是看能不能跑、估「不一致比例」；正式批次每個題庫至少 80～100 題才可能「證明」+15～20 個百分點的差；+10 個百分點要 250 題，這輪預算做不到。
DABstep 82 題勉強夠看 +18 個百分點；SpreadsheetBench 40 題**看不出**統計顯著，只能當「看得到差別」的展示。這要誠實寫進展場說明。

### 6.4 三階段
1. **試點**（約 0.5 美元）：DABstep 10 題 dev + SpreadsheetBench 10 題 + Terminal-Bench 2 題，三組各一次。目的：管線通、估不一致比例、量 Vacant 誤報率、量每題呼叫數。
2. **預註冊**：把題目清單（含抽樣種子）、模型與提供者、三組文字的 sha256、主要指標、檢定方法、停止規則寫成一份文件，老闆簽名後存進 decisions/prereg/。
3. **正式批次**（約 3 美元）：DABstep 82 題、SpreadsheetBench 40 題、Terminal-Bench 8 題。跑完不能改規則。

---

## 7. 記錄什麼（不記＝沒跑過）

1. **記錄代理程式**（已經在跑的 orproxy.py，之後併進倉庫）：每一次 HTTP 請求／回應原始位元組、模型、提供者、量化（從端點快照對回）、輸入／輸出／推理／快取 token、費用、finish_reason、重試次數（最多 4 次，每次各一列）、標籤（題庫-題號-組別）。金鑰只在代理程式記憶體，容器裡用假金鑰。
2. **agent 軌跡**：Harbor 自己存的 JSON 輸出與 session 檔（pi 的 --mode json、OpenCode 的 --format=json、Claude 的 stream-json、Codex 的 rollout）。
3. **Vacant 紀錄鏈**（B、C 組）：簽章鏈、每步的檔案差異、證據檢查結果（含被豁免的項目和原因）、退回文字、交件說明。
4. **harness 與評分**：Harbor 的 job.json／result.json、每題的 reward.txt、測試輸出、映像檔 digest。
5. **環境清單**：主機規格、Docker 版本、harness commit、資料版本與題號清單、四個 agent 的套件版本與 sha256、Vacant commit、模型與端點快照 sha256、代理程式設定、每組的完整指令列。
6. **infra_void 規則**：重試 4 次仍失敗、每日額度用完、代理程式預算拒絕、容器建不起來、agent 崩潰、Vacant 掛鉤錯誤且 Stop 事件遺失——這些題三組全部重跑，原因記在 trials.jsonl，**不安靜丟掉**。
7. 整個 run 用倉庫的 record.py 規則打包，私鑰排除，登記到 runs/INDEX.json。

---

## 8. 施工順序（先做什麼、多大、哪些現在就能用假模型測）

Vacant 今天的狀況：只有寫了「契約」（人先寫好什麼算對）才會在 Stop 時檢查；沒契約就什麼都不查。零設定要補的東西如下（行數是估的）：

**現在就能寫、用假模型（倉庫裡的 mock_model）測的（不花錢）**
1. 模式開關（off／observe／persona／evidence）+ 沒契約也記錄：約 80 行 + 15 個測試。
2. 證據檢查（純看紀錄鏈，可離線重放）：約 650 行 + 40 個測試。含四種檢查：沒讀的資料、沒來源的數值、先寫後讀、說測過沒跑。
3. 衍生值判斷（加總、平均、比例、日期運算不算「沒來源」）：約 150 行 + 15 測試。
4. 豁免表（假設、範例、小整數、年份等）：約 80 行資料。
5. 專案檢查（自動找 pytest／npm test 等，只報退步）：約 250 行 + 15 測試。
6. Stop 決策 + 定位：約 180 行 + 20 測試。
7. 審稿回合（固定文字常數 + 證據渲染；B 組是 C 組去掉證據區塊）：約 220 行 + 20 測試。
8. 交件說明（檢查了／修了／未驗證）：約 150 行 + 10 測試。
9. 把 agent 最後一段話轉給 Vacant（pi、OpenCode 各約 10～20 行 JS；Claude／Codex 已經有）：約 70 行。
10. 讓 Vacant 認得自己的退回文字（否則 OpenCode 會把它當成人的新要求，無限迴圈）：約 10 行 + 4 測試。
11. Harbor 包裝 agent（四個，只覆寫安裝與執行兩個方法）+ 離線 Vacant 安裝包（自帶 Python，不碰題目的 Python）：約 400 行 + 假模型冒煙測試。
12. 環境清單與打包、離線誤報重放：約 230 行。

**需要金鑰才能做的**
- 記錄代理程式併入倉庫（現在是 lead 自己跑的版本）+ 回應解析（提供者、token、費用）：約 500 行。可以先用假模型測，最後用真金鑰跑 2 次確認。
- 試點與正式批次。

**順序**：1→10→2→3→4→7→8→6→5→9→11→12→代理程式→試點→預註冊→正式。
先做 1 和 10 是因為它們小而且保命（沒有 10，OpenCode 會無限迴圈）。5（專案檢查）放後面，因為 DABstep 和 SpreadsheetBench 用不到它。
每一步做完都用倉庫現有的 e2e 情境（假模型、四個 agent）跑一次回歸。

**已知的 agent 差異**：OpenCode 用 `opencode run` 時沒有 Stop 掛鉤（跑完第一次閒置就結束，本機實測 0/N 次收到退回）。在 Harbor 裡只能用「包裝重跑」（跑完再用 --continue 送退回文字）。這在報告裡要另外標「包裝重跑」，不能寫成「掛鉤退回」。

---

## 9. 在哪裡跑、要多久、要多少錢

| 事項 | 地點 | 時間 | 錢 | 依據 |
|---|---|---|---|---|
| Vacant 零設定功能 + 假模型測試 | 這台機器 | 工程時間，依第 8 節行數（約 2,900 行程式 + 200 測試） | 0 | arch 設計估算 |
| 試點：DABstep 10 + SBV 10 + TB2 2，三組 | 這台機器（DABstep 映像檔要手動改 apt；SBV、TB2 要掛 CA 憑證） | 約 2 小時機器時間 | 約 0.5 美元 | 每題實測費用 × 題數 × 3 組 × 1.3 |
| DABstep 官方 smolagents 錨（10 題 dev，A 組） | 這台機器（主機上跑，不用容器） | 30 分鐘 | 約 0.05 美元 | 實測 4～8 次呼叫／題 |
| 正式：DABstep 82 題三組 | 這台機器 | 82×3×約 1.5 分 ≈ 6 小時 | 約 1.3 美元 | 實測 0.0012～0.0067／題 |
| 正式：SBV 40 題三組 | 這台機器 | 40×3×2.5 分 ≈ 5 小時 | 約 1.2 美元 | 實測 0.0074／題，146 秒 |
| 正式：TB2 8 題三組 | 這台機器（3.9 GB 映像檔） | 8×3×最多 15 分 ≈ 1～6 小時 | 0.3～0.8 美元 | 實測單次呼叫 0.0023；上限 15 回合 |
| LiveCodeBench 模型錨（gemma-3-12b-it） | **老闆電腦**（資料 4.5 GB） | 100 題約 1 小時 | 0.03（n=1）～0.26（n=8）美元 | 官方參數估算 |
| Aider Polyglot 20～30 題 | **老闆電腦**（Ubuntu apt 被擋） | 2～3 小時 | 約 0.05 美元 | 實測 0.0001～0.0003／題 |
| Terminal-Bench 全 89 題、qemu 兩題 | **老闆電腦** | 未知 | 估 1～2 美元 | 未驗證，延後 |

合計這輪（這台機器）：約 **3.4～3.9 美元**，加上已花的 0.024，留約 1 美元給 infra_void 重跑。時間約 12～15 小時機器時間，單線程，分 2～3 天。
這台機器：4 核、15 GB 記憶體、約 18 GB 可用硬碟且與其他工作共用；並行數維持 1～2。

---

## 10. 老闆要提供／決定的事

1. **簽預註冊**（試點後、正式前）。沒簽之前所有數字只能說「看得到差別」。
2. **主要模型**：建議 gemma-3-12b-it（bf16，非推理）。若堅持 4-bit，選 qwen3.5-9b（fp4）但要先接受「可能大量燒思考 token、答不出」的風險，或允許我們把它的推理強度調低（偏離預設，要記錄）。
3. **同意題庫順序**：DABstep → SpreadsheetBench → Terminal-Bench 抽樣；Aider、LiveCodeBench 在你的電腦跑；GDPval 這輪不跑。
4. **同意小模型基線只能「當背景」**：SpreadsheetBench 400 題版沒有任何小模型公開成績；DABstep 沒有 Qwen／Gemma 的成績。展場只能寫「同類模型在舊版約 X%」並標明版本不同。
5. **要不要儲值到 10 美元換免費模型 1000 次／天**：建議不用（付費小模型夠便宜，且免費上限的說法未驗證）。
6. **要不要花 Anthropic 額度重跑 Harbor 的對照數字**（claude-haiku-4.5，1,200 次試驗）：建議不用，太貴、而且不是我們的模型。
7. **DABstep 官方排行榜**：要正式提交需要 HuggingFace 帳號；由你決定。
8. **你的電腦**：需要 Docker、正常網路、約 15 GB 硬碟，跑 LiveCodeBench 錨、Aider、Terminal-Bench 全集。代理程式在你電腦上也要跑一份（金鑰只放你那裡）。
9. **展場措辭核准**（第 11 節）。

---

## 11. 風險與誠實邊界

**贏了代表什麼、不代表什麼**
- 贏＝「在這幾個題庫、這個 agent、這個模型、這些題上，裝 Vacant 的那一組分數較高，而且多花了這麼多呼叫」。
- 不代表「Vacant 讓 agent 變聰明」、「Vacant 抓得到所有錯」、「換個模型也會贏」。
- B 組（只有角色、沒證據）若比 A 更差，這是文獻預期的結果，要照實報，不能調到它「有用」為止。

**方法上的限制**
- Vacant 的「讀過什麼」是下界（shell 腳本、圖片、MCP 工具可能漏記）。「沒來源」的措辭一律是「在有紀錄的步驟裡找不到」，不是「你沒讀」。這些發現不進信譽。
- C 組多用資源；「更好」可能部分是「更多算力」。所以要報配對版與資源。
- 樣本小：40 題看不出顯著；82 題只能看很大的差。
- DABstep 450 題正式集的答案是排行榜擷取的近似值；只有 10 題 dev 是真的。
- Harbor 版 ≠ 論文原版（DABstep、SpreadsheetBench、Aider 都是），所以不能直接和論文分數比。
- Terminal-Bench 映像檔用標籤不是 digest 釘的；每次要記 digest。
- 9B 推理模型的「思考 token 用光」是真實風險，可能讓 Terminal-Bench 三組全是 0。
- OpenCode 在 Harbor 裡是「包裝重跑」不是「掛鉤退回」。
- 這台機器的容器要靠 CA 憑證繞過 TLS 攔截，Ubuntu apt 被擋；這些是環境差異，不是題庫差異，全部記錄；在老闆電腦要重新確認不需要這些。
- 免費／付費提供者可能記錄提示詞；量化可能被提供者悄悄換掉（每次呼叫都記提供者，量化對當日快照）。

**展場措辭（建議）**
- ✅「同一題、同一個小模型、同一個 agent，只差有沒有裝 Vacant。左邊沒裝，右邊裝了。你看到的是 N 題裡的一題，重播自紀錄，不是現場跑。」
- ✅「Vacant 不知道標準答案。它只看紀錄：這個數字從哪裡來、這個檔案開過沒、說測過有沒有真的跑。」
- ✅「在 N 題裡，裝了 Vacant 的那組多對 k 題、多錯 j 題、多用了 m 次呼叫。」
- ❌「Vacant 讓 AI 更可靠／更值得信任」、「Vacant 抓出所有錯」、「證明有提升」（除非預註冊批次已簽已跑）。
- 「機制模擬」與「真模型重播」在畫面上要分開標。

---

## 附錄 A：技術識別碼（給工程用，老闆可跳過）

- Harbor：github.com/laude-institute/harbor @ `6cb9ff3167596c456e0b24622d473b59fc9ab6c7`；agent 接法在 `src/harbor/agents/installed/{pi,opencode,claude_code,codex}.py`；自訂 agent 用 `--agent module:Class`。
- Terminal-Bench 2.0 抽樣：`terminal-bench-sample@2.0`，github.com/laude-institute/terminal-bench-2-0-sample @ `7e917f35c281188532772312d4ad91ca9274febc`；全集 `terminal-bench@2.0` @ `69671fbaac6d67a7ef0dfec016cc38a64ef7a77c`。task.toml：agent/verifier 900 s。這台機器要加 `--mounts`（CA 憑證）與 `--ae/--ve SSL_CERT_FILE、CURL_CA_BUNDLE、NODE_EXTRA_CA_CERTS`；pi 要 `--ak model_api=openai-completions`，代理程式從容器看是 `http://172.17.0.1:18900/t/<tag>/api/v1`。
- SpreadsheetBench Verified：`spreadsheetbench-verified@1.0`，harbor-datasets @ `0ad7209b09780e78c6c80f194e49e353191be1cc`；原倉庫 RUCKBReasoning/SpreadsheetBench @ `49b73a94775fb489063f60ca1865e3a650079a79`。
- DABstep：`dabstep@1.0`；HF `adyen/DABstep` revision `51884d3339cbc1f05d0e2e02bac7995ea605d69a`；all.jsonl sha256 `d776385a…`（450 題）、dev.jsonl `c1da755a…`（10 題：easy 5,49,70；hard 1273,1305,1464,1681,1753,1871,2697）；官方 baseline 需 `smolagents==1.3.0`、`transformers==4.47.1`，`--max-steps 10`，`max_tokens=3000`。
- LiveCodeBench：github.com/LiveCodeBench/LiveCodeBench @ `28fef95ea8c9f7a547c8329f2cd3d32b92c1fa24`；HF `livecodebench/code_generation_lite` @ `0fe84c3912ea0c4d4a78037083943e8f0c4dd505`；`anthropic==0.42.0`；走 `custom_evaluator.py` 路徑，提示詞 `SYSTEM_MESSAGE_GENERIC` + `get_generic_question_template_answer`；預設 n=10、T=0.2、top_p=0.95、max_tokens=2000、timeout 6 s。
- Aider Polyglot：`aider-polyglot@1.0`；Aider-AI/polyglot-benchmark @ `7e0611e77b54e2dea774cdc0aa00cf9f7ed6144f`；aider @ `5dc9490bb35f9729ef2c95d00a19ccd30c26339c`（benchmark.py 預設 tries=2）；Harbor 版 n_attempts=1、timeout 1800 s。
- 模型：`qwen/qwen3.5-9b` @ darkbloom/fp4（0.08/0.13）；`google/gemma-3-12b-it` @ deepinfra/bf16（0.05/0.15，max_out 16384，有 tools，無 reasoning 參數）；`openai/gpt-oss-20b` @ akashml/fp4（0.02/0.10）；`google/gemma-4-26b-a4b-it:free` @ Google AI Studio。
- 代理程式：`ops/eval/orproxy.py`（現行）→ 併入 `ops/zeroeval/orproxy.py`（以 `vrun/wireproxy.WireProxy` 為基底）；帳本 `scratchpad/evalrun/ledger/{io.jsonl,ledger.jsonl,summary.json}`。
- Vacant 模式：`VACANT_MODE=off|observe|persona|evidence`；`VACANT_HOME=/logs/agent/vacant`；新檔 `trace/evidence.py`、`trace/derive.py`、`trace/evidence_rules.json`、`trace/projectchecks.py`、`trace/review.py`、`trace/delivery.py`；`hookpolicy.decide_stop_zero`、`stopcheck.localize_evidence`；`capture.prompt_source` 需加新標頭前綴。
- 統計：`vacant_network/research.py` 的 `mcnemar_exact`、`boot_ci`、`holm_bonferroni`、`tost_equiv_boot`、`mcnemar_power`、`mcnemar_n_required`、`stratified_mcnemar_exact`。
- KS-1：`vacant_network/memory.py::KS1_FORBIDDEN`、`trace/feedback.py::feedback_ks1_clean`。
- 預註冊範本：`decisions/prereg/PREREG_20260924_R536_LOCALIZED_FEEDBACK.md`（未簽）。

## 附錄 B：本輪費用與呼叫數來源（代理程式帳本，2026-09-25）
| 標籤 | 呼叫 | 輸入 token | 輸出 token（其中推理） | 費用（美元） |
|---|---|---|---|---|
| live-dabstep-5 | 4 | 12,934 | 1,321（359） | 0.00120645 |
| live-dabstep-70 | 8 | 78,288 | 3,645（1,093） | 0.00673689 |
| live-sbv-10452 | 7 | 85,116 | 4,546（1,807） | 0.00740026 |
| live-tb2-regex-log | 1 | 1,717 | 16,384（16,384） | 0.00226728 |
| live-lcb-lcb_3594 / 3607 | 2 / 1 | 906 / 365 | 10,000 / 8,000（全部推理） | 0.00137248 / 0.00106920 |
| live-aider-polyglot python / go | 2 / 1 | 656 / 253 | 6,679 / 2,000 | 0.00092075 / 0.00028024 |
| live-gdpval-83d10b06 | 8 | 23,640 | 1,392（543） | 0.00207216 |
| 總計（41 次，全部 qwen3.5-9b） | 41 | 212,244 | 55,085（47,318） | 0.02414057 / 4.80 |
