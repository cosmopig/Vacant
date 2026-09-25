<!-- 狀態：草稿，待人類核准（2026-09-25）。核准前只准做「閘門 1、閘門 2」與不花錢的施工；
     正式批次要先簽預註冊。研議過程、每個題庫的官方跑法出處、本機實測紀錄：
     ops/eval/evidence_20260925/（notes/ 是逐題庫筆記，study_result.json 是研議的完整結構化輸出，
     ledger.jsonl／summary.json 是記帳代理的逐通帳本）。
     研議方式：4 個題庫類別的網路調查 → 挑 6 個 → 各自讀官方程式碼、在本機跑官方評分的
     oracle／nop 與 1～2 題真模型 → 另一個模型逐條複查 → 寫計畫 → 獨立審查（2 blocker、
     11 major、10 minor）→ 第 2 版。 -->

# Vacant「裝了比沒裝好」評測計畫 第 2 版（給人類核准用，2026-09-25）

這份是第 2 版。第 1 版被一位獨立審查人挑出 2 個必須先解決的問題（blocker）、11 個重大問題（major）、10 個小問題。第 2 版逐條處理；每一條的處理方式寫在第 12 節，有一條我們部分不採納，理由也寫在那裡。

寫法和第 1 版一樣：白話、短句、專有名詞第一次出現就解釋、程式識別碼只放最後的技術附錄。
每個數字後面都標來源：「（本機實測）」＝我們在這台機器真的跑出來的；「（論文）」＝只從論文或官方網頁讀到；「（估）」＝推算，還沒跑過。

---

## 0. 一頁摘要

**要回答的問題**：同一個 agent（會自己讀檔、寫檔、跑指令的 AI 程式）、同一個小模型、同一批公開題目，**只差「有沒有裝 Vacant」**，成績有沒有差？

**做法**：三組比較，同一題三組都跑，一題一題配對比。
- **A 組**：什麼都不裝。
- **B 組**：裝 Vacant，但只給「審稿人角色」的文字、**不給證據**。而且 B 組**什麼時候退回、退回幾次，完全跟 C 組一樣**（由同一套證據檢查決定），只是把證據那幾行拿掉。這樣 B、C 之間唯一的差別就是「有沒有告訴它錯在哪裡」。
- **C 組**：裝 Vacant，交件前看紀錄（哪些檔沒開、哪些數字沒來源、說測過但沒跑），把該重做的地方退回去重做，最後附一張「檢查了什麼／改了什麼／哪些還沒驗證」的說明。

**先跑哪些題庫**（題庫＝公開考題集，附官方的跑題與評分程式）：
1. **DABstep**（付款資料分析，要讀一本商業手冊）：**79 題不重複**（72 題簡單 + 7 題困難）。這是**唯一的正式統計比較**。
2. **SpreadsheetBench Verified**（真人論壇的試算表題）：40 題，**只做展示，不做統計主張**。
3. **Terminal-Bench 2.0 抽樣**（終端機工程題）：8 題，只當「程式類會不會全部 0 分」的邊界檢查。
4. **LiveCodeBench v6**：不比 Vacant，只當「模型有沒有壞掉」的**合理性檢查**（第 1 版寫「再現」，審查人指出 100 題看不出「同等級」，已改口）。

**兩道閘門，過了才准選模型、才准進試點**（第 1 版沒有，這是審查人的兩個 blocker）：
- **閘門 1：模型煙霧測試**。我們推薦的主模型 gemma-3-12b-it **從來沒被呼叫過**——目前 41 次呼叫全部是 qwen3.5-9b（本機帳本）。所以先用三個候選模型各跑 4 題（約 0.15 美元），看它會不會用工具、幾回合、幾個 token、有沒有分。沒過這關，任何模型都不寫進預註冊。
- **閘門 2：C 組的「退回」在 Harbor 裡真的會發生**。用假模型在 Harbor 容器裡證明：故意埋一個錯，C 組會多送 N 次帶著證據文字的模型請求、最後的檔案會變。沒證明之前，C 組可能根本等於 A 組。

**錢**：人類儲值 5 美元，代理程式硬上限 4.80 美元，已花 0.02414 美元（本機帳本）。分配：閘門 0.15、試點 0.70、DABstep 正式 1.60、SpreadsheetBench 1.20、Terminal-Bench 0.60、預留 0.50。**每個題庫的錢用完就停，不挪用。**
**時間**：金鑰約 **2026-10-25** 失效（人類說一個月）。第 9 節有逐週時程和「來不及就砍什麼」的規則：先砍 Terminal-Bench，再砍 SpreadsheetBench，**DABstep 一定要在 10-18 前開跑**。
**什麼時候能說「證明」**：只有人類簽了預註冊（先把規則寫死、簽名，再跑）的正式批次之後。之前的任何數字只能說「看得到差別」。

---

## 1. 名詞解釋（第一次看的人請先讀）

- **題庫（benchmark）**：公開的考題集，附標準答案或評分程式。
- **harness（官方跑題與評分的程式）**：把題目餵給 agent、收答案、打分的程式。
- **Harbor**：Terminal-Bench 2.0 的官方 harness。它內建 pi、OpenCode、Claude Code、Codex 四個 agent 的接法，也能跑其他題庫的「轉接版」。
- **轉接版（adapter）**：Harbor 團隊把別人的題庫改包成 Harbor 能跑的格式。**轉接版不等於論文原版**（第 3 節會逐一講差在哪）。
- **agent**：會自己做事的 AI 程式。這一輪**只評 pi**（理由見第 5.4 節）。
- **模型**：agent 背後在想事情的大語言模型。
- **量化（quantization）**：把模型壓小（fp4、fp8、bf16 由小到大）。壓越小越像家用電腦跑的，可能答得較差。
- **提供者（provider）**：OpenRouter 背後真正跑模型的公司。同一模型不同提供者量化不同，所以要**釘死**。
- **call（一次呼叫）**：agent 問模型一次。一題通常要問多次。
- **token**：計費單位。「推理 token」是模型在想但沒說出來的部分，也要付錢。
- **工具呼叫（tool call）**：模型用固定格式說「幫我跑這個指令／開這個檔」。**模型不會工具呼叫，agent 就什麼都做不了**，這是閘門 1 要驗的事。
- **oracle / nop**：oracle＝把標準答案直接交上去，一定滿分；nop＝什麼都不做，一定 0 分。用來確認評分程式沒壞。
- **trace（紀錄鏈）**：Vacant 記下 agent 每一步做了什麼，有簽章，事後改不了。
- **Stop（做完那一刻）**：agent 說「我做完了」的那個時間點，Vacant 在這裡檢查並可能退回。
- **退回（push-back）／回合（round）**：Vacant 把 agent 叫回來重做一次，算一個回合。
- **同步化（yoked）**：B 組的退回時機與次數**照抄** C 組的決定，只是內容少了證據行。
- **意向治療（intention-to-treat）**：C 組自己出錯（例如掛鉤壞了）也算 C 組的成績，不能當作「沒跑過」丟掉。
- **讀檔見證（read oracle）**：一個獨立於 agent 和 Vacant 的機制（作業系統層），記錄「哪個檔案真的被打開過」。用來檢查 Vacant 的「沒開過」有沒有冤枉 agent。
- **A/A′ 重複**：同一題 A 組跑兩次。兩次結果不一樣的比例就是「純粹運氣造成的差異」。
- **預註冊（pre-registration）**：先把「跑哪些題、看哪個數字、怎麼算才算贏」寫死並簽名，再跑。
- **配對比較 / McNemar 檢定 / bootstrap 信賴區間**：同一題 A、C 各跑一次一題一題比；McNemar 只看「A 對 C 錯」和「A 錯 C 對」的題數；bootstrap 是把題目重抽很多次看差距範圍。
- **infra_void（基礎設施作廢）**：不是模型也不是 Vacant 的錯（網路斷、額度用完、容器建不起來）。**Vacant 自己壞掉不算這一類**（第 6.5 節）。

---

## 2. 哪些是這裡驗證過的，哪些只是讀論文

### 2.1 本機驗證過（有紀錄檔可查）
- 六個題庫的評分程式都做過 oracle＝滿分、nop＝0 分。
- 用 **qwen3.5-9b（fp4）** 透過記錄代理程式各跑 1～2 題：DABstep 5 號題答對（4 次呼叫、0.0012 美元、26 秒）、70 號題答錯（8 次、0.0067 美元、178 秒）；SpreadsheetBench 10452 號題答錯（7 次、0.0074 美元、146 秒；模型算對 9 個值但只寫進 5 個）；Terminal-Bench regex-log 題 0 分（1 次呼叫把 16,384 個 token 全用在思考，沒下任何指令）；LiveCodeBench 兩題都寫不出程式；Aider Python 題一次答對、Go 題全在思考沒答案；GDPval 8 回合還在找檔案。
- **gemma-3-12b-it、gemma-4-26b-a4b-it、gpt-oss-20b 一次都沒呼叫過。** 這是第 1 版最大的漏洞。
- 費用帳本：41 次呼叫、0.02414057 美元（附錄 B 已和帳本逐筆對齊）。
- Harbor 內建四個 agent 的接法，我們讀了原始碼並用 pi 真的跑通（Terminal-Bench 與 SpreadsheetBench 各一題）。
- Vacant 在 pi 的「無介面模式」下的退回：在倉庫既有的假模型測試裡，pi 的 6 個情境「回饋有送到模型、有改對」（倉庫 evidence_20260924）。**但那是在 Vacant 自己的執行器裡，不是在 Harbor 容器裡**——Harbor 另外會塞它自己的擴充檔、而且預設裝 pi 的最新版。所以閘門 2 仍然要做。
- 統計：樣本數與檢定力用倉庫現成函式算的（第 6.3 節）。
- 這台機器：容器要掛 CA 憑證才能上網；Ubuntu 的 apt 套件庫連不到（Aider、DABstep 映像檔要手動改）；Debian 的可以。

### 2.2 只讀到、沒自己跑過
- 小模型公開成績：SpreadsheetBench 的 Qwen3-8B 15.9%（arXiv:2605.22642 表 1，**912 題舊版**）；DABstep 的 Llama-3.3-70B 簡單 68%／困難 3.7%（arXiv:2506.23719 表 1，二手擷取）；Terminal-Bench 2.0 的 Qwen3-8B 約 2.5%（搜尋摘要，**未核對，不得上展場**）；Aider 排行榜最小的是 gemma-3-27b（4.9%）。
- gemma-3-12b-it 的 LiveCodeBench 32.0（arXiv:2503.19786 表 18；表 21：8 次取樣平均、沒寫題目日期範圍）。
- OpenRouter 免費模型每天 50 次：從金鑰資訊讀到，是真的；「儲值 10 美元以上變 1000 次」**未驗證**。
- 自我檢查的研究：沒外部訊號的自我修正幾乎沒用（Huang 等，ICLR 2024）；告訴它錯在哪就能改（Tyen 等，ACL Findings 2024）；比較要相同起點、相同預算（Kamoi 等，TACL 2024）。

---

## 3. 題庫：跑哪些、怎麼釘死「官方跑法」、和論文原版差在哪

### 3.1 一覽表

| 順序 | 題庫 | 角色 | 子集 | 官方跑法 vs 我們的跑法 | 每題花費（qwen3.5-9b，本機實測） |
|---|---|---|---|---|---|
| 1 | DABstep | **唯一的統計主張** | 79 題不重複（72 簡單 + 7 困難 dev） | 官方＝smolagents 小 agent；我們＝Harbor 轉接版 + pi（**偏離，明講**） | 4～8 次呼叫，0.0012～0.0067 美元 |
| 2 | SpreadsheetBench Verified | 展示用（不做統計） | 40 題 | 官方＝一次問答的腳本；我們＝Harbor 轉接版 + pi（**偏離，明講**） | 7 次呼叫，0.0074 美元，2.5 分 |
| 3 | Terminal-Bench 2.0 抽樣 | 程式類邊界檢查 | 8 題 | Harbor **就是**官方 harness，這裡「完全照官方」是字面上成立的 | 1 次呼叫 0.0023 美元（模型沒動作） |
| 4 | LiveCodeBench v6 | 模型合理性檢查（不比 Vacant） | 100 題、8 次取樣 | 官方 runner，逐字重用提示詞 | gemma-3-12b-it 估 0.26 美元（估） |
| 延後 | Aider Polyglot | 備援 | 20～30 題 | 這台建不了映像檔 → 你的電腦 | 0.0001～0.0003 美元 |
| 不跑 | GDPval | — | — | 授權沒寫、官方評分要 OpenAI 帳號、沒 agent 可掛 | — |

### 3.2 DABstep（第一優先，唯一的正式統計比較）

**是什麼**：Adyen 公司出的付款資料分析題。每題給 7 個檔案（付款紀錄 payments.csv 23.6 MB、費用表、**商業手冊 manual.md**、商家資料等），問一個有標準答案的問題。困難題幾乎都要交叉對照手冊；簡單題也有三分之一要讀手冊（本機實測：3 題簡單 dev 題 1 題需要、7 題困難全部需要）。

**題數修正（審查人指出）**：第 1 版寫「10 題 dev + 72 題簡單 = 82」。Harbor 的說明文件說 dev 的 6 題也在正式集裡（5、49、70、1305、1681、1753）。簡單題 5、49、70 被算了兩次。**正確是 79 題不重複**：72 題簡單 + 7 題困難 dev。重複的 3 題用 dev 的標準答案（內容一樣）。

**主要分析只有一個**：C 組 vs A 組，79 題，McNemar 精確檢定。dev 10 題不再另算標題數字。

**官方跑法（釘死）**：
- 資料：HuggingFace `adyen/DABstep`，版本號釘死（附錄 A），授權 CC BY 4.0。450 題正式集、10 題 dev。7 個資料檔的 sha256 已存檔。
- 官方 agent：smolagents 的 CodeAgent（只能寫 Python 的迷你 agent），最多 10 步、每次回答最多 3,000 token、沒設溫度。安裝要釘舊版套件（本機實測，否則裝不起來）。
- 官方評分：scorer.py，數字允許誤差、字串模糊比對；確定性、不用 AI 當評審。
- **注意**：450 題正式集的答案是 Harbor 從公開排行榜抽出的「最短的被接受答案」，**不是官方標準答案**；只有 dev 10 題是真的。79 題裡的 69 題用的是這種擷取答案，展場要標明。

**我們的跑法與偏離（明講）**：
- 官方 smolagents 是同一支程式直接叫模型，**沒有可掛鉤的獨立 agent 程序**，Vacant 掛不上。**決定**：三組都用 Harbor 轉接版 + pi。差別：題目改成「把答案寫進一個檔案」；agent 可用 shell；時限 1,800 秒。
- **Harbor 的「對照數字」要重新標示**（審查人指出第 1 版說過頭）：Harbor 說的「原版 37.69 vs Harbor 36.92」，那個「原版」其實是**一個改過的分支，用 Claude Code 跑的**，不是論文的 smolagents。而且 Harbor 的說明文件和數據檔對「Harbor 那一側用哪個 agent」講法不一致。所以只能說「Harbor 轉接版 ≈ 同一份資料與評分程式的另一個 agent 版」，**不能說「Harbor ≈ 論文原版」**。
- 我們另外用**官方 smolagents 跑一次 dev 10 題（A 組）**當錨（約 0.05 美元）。但 n=10 **不能證明等價**，只能看有沒有離譜。
- Harbor 的映像檔建置時從 HuggingFace 的浮動分支抓資料。我們改成釘死版本並核對 sha256，映像檔只建一次、記 digest（映像檔的指紋），三組同一題用同一個 digest。

**小模型基線（論文）**：Llama-3.3-70B 簡單 68.06%／困難 3.70%（arXiv:2506.23719 表 1，二手擷取）。沒有 Qwen／Gemma 的數字。

**污染風險**（審查人指出）：dev 10 題的答案 2025 年起就在公開資料集裡，模型可能看過。正式集的答案只存在排行榜提交檔裡，比較不會被背。所以主集以正式集為主（69 題）；「第一次交件已經對、退回後改錯」的傷害配對，會按「第一次就對」分開報。

### 3.3 SpreadsheetBench Verified（第二，展示用）

**是什麼**：真人論壇的 Excel 問題，給輸入 xlsx，要求把答案寫進輸出 xlsx 的指定範圍。400 題專家驗證版（2025-12），每題 1 個測試案例。評分：LibreOffice 重算公式後逐格比對，沒有 AI 評審。

**為什麼**：「數字是從給定檔案算出來的，還是編的」。本機實測那題（模型算對 9 個值只寫進 5 個）**是證據檢查「設計要抓」的那種不一致——證據檢查還沒寫，這是設計意圖，不是已觀察到 Vacant 抓到**（審查人要求改口）。

**官方跑法（釘死）**：原始倉庫（授權 CC BY-SA 4.0）的官方腳本是「一次問模型、執行、比對」（非 agent），最多 5 輪；Harbor 轉接版把它改成 agent 任務、拿掉原版塞在提示詞裡的試算表預覽、修了評分程式 11 個 bug（Harbor 作者自述，我們讀碼確認存在）。
**Harbor 的對照數字同樣要重標**：「原版 68.83 vs Harbor 68.25」的「原版」是**用 Claude Code 跑的改版分支**，不是論文那支一次問答的腳本。
**決定**：Harbor 轉接版 + pi。**這是偏離論文的跑法，人類要在第 10 節簽字認可。**

**環境浮動（審查人指出）**：評分階段每次都從網路現裝 LibreOffice，版本可能天天不同。改法：LibreOffice 預裝進一層快取的評分映像檔、記版本與 digest，三組同一題用同一個 digest。

**小模型基線（論文）**：Qwen3-8B 15.9 等（arXiv:2605.22642 表 1）是 **912 題舊版**；400 題驗證版**沒有任何公開小模型成績**。

**子集**：先從 400 題裡**排除**試點用的 10 題，再用記錄的種子按題型分層抽 40 題。40 題**看不出統計顯著**（第 6.3 節），只做展示。

### 3.4 Terminal-Bench 2.0 抽樣（第三，邊界檢查）

**是什麼**：89 題終端機工程題，官方 harness 就是 Harbor。抽樣集 10 題；每題 agent 900 秒、評分 900 秒；映像檔用預建版（**用標籤不是 digest 釘的**，每次拉到的 digest 要記）。
**為什麼**：唯一「官方 harness 原生支援我們的 agent」的題庫。Harbor 自己在 pi 的接法裡就會塞擴充檔進 agent 的設定目錄，Vacant 走同一條路，不動題目、不動評分。
**風險**：9B 推理模型第一次呼叫就把 16,384 個 token 全用在思考（本機實測）。可能三組全 0。所以：只有閘門 1 顯示所選模型能在 regex-log 題做出至少一個動作，才跑；否則砍掉，只在報告裡寫「小模型在這題庫全部 0 分」。
**子集**：10 題排除 2 題 qemu（建置要下載幾百 MB ISO、建 32 GB 稀疏磁碟）。其餘 8 題映像檔共 3.9 GB（本機實測）。8 題只做描述，不做統計。

### 3.5 LiveCodeBench v6（模型合理性檢查，不比 Vacant）

**改口**：第 1 版叫「再現」。審查人指出：100 題單次取樣的標準誤約 4.7 個百分點，「±5 分」只是一個標準誤的寬度；Gemma 3 報告是 2025-03 發布，不可能含 2025-04 的題，題目窗口一定不同；報告用 8 次取樣平均；而且這是單次問答，測不到 agent 的工具呼叫。所以它**只是「模型沒壞掉」的合理性檢查**，不是再現。
**做法**：官方 runner、逐字重用提示詞、官方參數（溫度 0.2、top_p 0.95、輸出 2,000 token）、**8 次取樣**、題目限制在 2025-03 以前的窗口。100 題約 0.26 美元（估）。在你的電腦跑（資料 4.5 GB）。
**工具呼叫的合理性檢查**由閘門 1 負責（真的在 Harbor 題目裡看模型會不會用工具）。Harbor 有 BFCL（工具呼叫題庫）轉接版，但 gemma-3-12b 有沒有公開 BFCL 成績**未查證**。

### 3.6 Aider Polyglot（延後，你的電腦）
225 道 Exercism 練習題。官方 harness 給兩次機會並把測試失敗結果給模型；Harbor 版只給一次、測試藏起來（偏離）。這台機器建不了映像檔。排行榜沒有 27B 以下的模型。若跑：你的電腦、20～30 題、只做描述。

### 3.7 harness 驗證步驟（每個題庫正式跑前都要過）
1. oracle 滿分、nop 零分（六個題庫已做）。
2. 三組第一次模型請求的內容（去掉時間戳、session id）逐位元相同。不同＝Vacant 動到提示詞，該組作廢。
3. 每一題 C 組的紀錄鏈裡有步驟事件和 Stop 事件。
4. **C 組操作檢查（新增）**：有發現的題，代理程式一定看得到多出來的模型請求、且請求內容含證據文字。有發現但沒有多出請求＝**C 組失敗，算 C 組的分數，不是 infra_void**。
5. 讀檔見證（第 6.4 節）在三組都開著且有輸出，否則該題作廢重跑。

---

## 4. 三組（A／B／C）與注入的文字

### 4.1 定義
- **A 組**：agent 原封不動。
- **B 組（同步化角色組）**：裝 Vacant「角色模式」。Stop 時**同樣跑證據檢查**（純看紀錄、不用模型、確定性），有發現才退回，退回次數與 C 相同，但送給 agent 的文字**只有開頭 + 角色 + 結尾，沒有證據行**。這樣 B、C 唯一的差別就是證據行。（第 1 版的 B「固定退一次」被審查人指出混進了「退不退、退幾次」的差異。）
- **B2 組（選配）**：每題固定退一次、沒證據，即文獻的「純自我修正」。**只在 DABstep 預算還剩時跑**，另立標籤。
- **C 組**：裝 Vacant「證據模式」。Stop 時跑證據檢查；有 agent 能修的發現才退回，最多 2 回合；文字＝開頭 + 同一段角色 + 證據行 + 同一段結尾；最後寫交件說明（Checked／Fixed／Unverified）到 Vacant 的紀錄目錄，**不進題目工作區、不進模型上下文**。
- **一律關掉**「額外請一個模型當審稿人」的選項（審查人指出那會多花錢又多一個變數）。預註冊裡寫死為關。
- B、C 的文字除了證據行**逐位元相同**（KS-1 鐵律）。只裝掛鉤，**不裝技能檔**。
- **回合數與時限**：三組都用官方時限、**都不設回合上限**（官方預設就是不設）。C 組在退回途中被時限砍掉，**以當下工作區的檔案打分，算 C 組成績**。每回合的牆鐘時間都記。試點要確認 C 組多出的時間放得進時限（SpreadsheetBench 600 秒、A 組實測 146 秒）。

### 4.2 注入的文字（英文給 agent；中譯給人類看）

**固定開頭（B、C 共用）**
> Before delivery: a review of the recorded steps of this task.
> （交件前：針對這個任務有紀錄的步驟做一次檢視。）

**審稿人角色（B、C 共用）**
> Take the role of a careful reviewer who reads a draft against the materials given for the task. Check that every specific number, date and name in the deliverable can be traced to a given file, the task message, or a computation done in this task; that every file named in the task was actually opened; and that any claim of testing or verification matches a step that ran. Redo only the parts that do not hold. Anything that remains unverified goes under a heading "Unverified" in the final message.
> （請扮演一位仔細的審稿人，對照任務給的材料讀這份草稿。檢查交付物裡每個具體的數字、日期、名稱都能追到某個給定的檔案、任務訊息、或這次任務裡做過的計算；任務點名的每個檔案都真的打開過；任何「測過／驗證過」的說法都對得上真的跑過的步驟。只重做站不住的部分。仍未驗證的，放在最後訊息的「Unverified」標題下。）

**證據行（只有 C；格式固定，由紀錄產生，例）**
> - report.md line 3, value 999: no source found in the recorded steps; the given file data.csv was not opened. Action: open data.csv and redo lines 3-7, or label the value as an assumption.
> - manual.md: not opened in the recorded steps. Action: open it and re-check the parts of the answer that depend on its rules.
> - Final message says "tests pass"; no test command ran after the last edit at step 9. Action: run the tests and report the result.

**固定結尾（B、C 共用）**
> This note lists what the record shows; it does not say whether the final answer is right. When done, end your message with three headings: Checked, Fixed, Unverified.

**KS-1 檢查與「引文失敗怎麼辦」（審查人指出第 1 版沒說）**：證據行會引用資料檔或 agent 的話，那些字可能剛好含禁止詞或識別碼。規則：引用片段最多 80 字元並轉義；某一行過不了 KS-1 就換成固定的替代行「- <檔名> line <n>: finding withheld (wording check)」，這件事記在紀錄鏈上、每組分開計數。**不會安靜丟掉。**

### 4.3 預算配對（Kamoi 等人的要求）
- 三組的 harness、agent 版本（pi **釘死版本**，不用「最新版」）、模型、提供者、量化、提示詞、時限、評分程式、映像檔 digest 全部相同；只差 Vacant 模式。
- B 與 C 退回次數相同（同步化），所以 B、C 的呼叫數大致相同；A 比它們少。每組每題都報：呼叫次數、輸入／輸出／推理 token、費用、牆鐘時間、回合數、發現數。
- 額外報告「C 組在零發現題目上」與 A 的差，只給信賴區間，**不做等價主張**（審查人指出 20～40 題做不了等價檢定，TOST 已刪）。

---

## 5. 模型

### 5.1 閘門 1：先煙霧測試，再選模型（新增，blocker）
三個候選，各用 pi 跑同樣 4 題（DABstep 5、70；SpreadsheetBench 10452；Terminal-Bench regex-log），每個候選約 0.05 美元，合計 ≤0.15 美元。記錄：工具呼叫格式是否有效（pi 收不收得到）、回合數、token、費用、分數、有沒有「思考用光沒答案」。**沒過這關的模型不進預註冊；所有成本表都用過關模型的實測數字重算。**

| 候選 | 提供者／量化 | 價格（每百萬 token 輸入／輸出） | 為什麼是候選 | 已知風險 |
|---|---|---|---|---|
| google/gemma-3-12b-it | DeepInfra／bf16（唯一提供者） | 0.05／0.15 美元 | 同一份 12B 權重就是大家在家用 Q4 跑的；非推理模型 | **未量化**，和「4-bit」不同要標明；沒有原生工具呼叫格式，靠提供者轉換，**沒測過** |
| google/gemma-4-26b-a4b-it | DeepInfra／fp8 | 0.07／0.34 美元 | 最接近人類說的「gemma 4、量化過」；26B 總參數但每次只用 4B，算力像小模型；可關推理 | 輸出較貴；沒測過 |
| qwen/qwen3.5-9b | Darkbloom／fp4 | 0.08／0.13 美元 | 真的 4-bit；已有 41 次實測 | 6 個題庫裡 4 個「思考用光沒答案」；要試把推理強度調到 low（端點有這參數，沒測過） |
| openai/gpt-oss-20b | AkashML／fp4 | 0.02／0.10 美元 | 最便宜的備援 | 沒測過；只在前三個都不行時才試 |

（價格來源：當日 OpenRouter 端點快照，附錄 A。）

### 5.2 免費模型：只做試點對照
- 這把金鑰每天 50 次免費呼叫（本機從金鑰資訊讀到，是真的）。一題三組約 15～30 次 → **一天 1～2 題**。只夠確認「免費模型能不能用工具、Vacant 掛得上」，學不到統計上的東西。
- 「儲值到 10 美元變 1000 次／天」未驗證；付費小模型不受此限。**建議：主線用付費小模型，免費模型（gemma-4-26b-a4b-it:free）只在試點跑 2 題留紀錄。**
- 免費提供者可能記錄提示詞；題目公開所以可接受，記進環境清單；**展場訪客資料絕不走這些端點**。

### 5.3 取樣參數：跟官方走，並補噪音控制
- Harbor 題庫：官方不設溫度，由 agent 與提供者預設決定；我們不加參數，存第一次請求原文為證。提供者若回傳實際用的溫度和模型版本，記下來。
- **A/A′ 重複**（新增）：試點集 A 組跑兩次，量「純運氣的翻轉率」。這個數字用來估檢定力，也寫進展場說明（「同一題重跑，本來就有 x% 會變」）。
- **順序**：同一題的 A、B、C 三組**連著跑**、組別順序隨機；題目順序也隨機，這樣就算中途錢用完，跑完的仍是隨機子集。
- LiveCodeBench：官方參數照抄，8 次取樣。DABstep 官方 smolagents：輸出 3,000 token、10 步，照抄。

### 5.4 只評 pi
這一輪所有結果都限定「pi + 某模型」。OpenCode 在 Harbor 裡的自訂端點設定只認三家提供者、走 OpenRouter 代理沒測過；Claude Code、Codex 配小模型完全沒碰。它們要先各自過一次假模型的 Harbor 煙霧測試才能加進來；這一輪不加。

---

## 6. 指標與統計

### 6.1 唯一的結果指標
- **官方分數**（每題 0/1，官方評分程式決定）。任何「更好」的說法只看這個。

### 6.2 操作檢查（不是「改善」的證據，審查人指出這些指標是循環的）
「沒來源的數值數」「沒讀的給定資料數」是**同一個檢查器**算出來的，C 組當然會降低它們。所以它們改叫「操作檢查」：證明 C 組確實收到並處理了發現。三組都用 **Harbor 存的軌跡**重建輸入、跑同一套離線檢查（不再 A 組用一種工具、C 組用另一種）。

### 6.3 樣本數（倉庫函式算的，α=0.05、檢定力 0.85＝函式預設）
| A、C 不一致比例 | 不一致中 C 贏的比例 | 相當於分數差 | 需要題數 |
|---|---|---|---|
| 30% | 80% | +18 個百分點 | 86 |
| 30% | 75% | +15 | 125 |
| 30% | 70% | +12 | 195 |
| 20% | 80% | +12 | 130 |
| 20% | 75% | +10 | 188 |
| 40% | 75% | +20 | 94 |

反過來：79 題在「不一致 30%、C 贏 80%」時檢定力 0.82；「不一致 20%、C 贏 80%」只有 0.61；10 題 0.01、30 題 0.32、50 題 0.58。
**誠實的結論**：這一輪只可能證明「很大的差」（約 +18 個百分點）；+10 要 190 題，預算做不到。而且表裡的「不一致比例」目前是**假設**——試點後用 A/A′ 翻轉率和 A/C 不一致率**重算一次**，並在預註冊裡寫明「最小可偵測效果」。

### 6.4 讀檔見證與誤報率（新增，審查人 major）
Vacant 的「讀過什麼」是下界：agent 用 Python／pandas 在一個 bash 步驟裡讀檔，Vacant 可能看不到，就會冤枉它「manual.md 沒開」。第 1 版的「離線重放量誤報率」用的是同一個瞎掉的儀器，量不出來。
改法：三組都加一個**獨立的讀檔見證**（作業系統層：優先 strace 追蹤 open 系統呼叫；容器不准的話退而用 Python 的稽核掛鉤加上 shell 指令文字比對），完全在 agent 的上下文之外，三組一模一樣（所以不是治療差異）。用它在試點量：Vacant 讀檔紀錄的召回率、「沒開過」的誤報率。預註冊寫一個**誤報率上限**（提議 10%），超過就不能跑正式。C 組規則：任何 bash 或 python 步驟的指令文字或腳本裡提到的檔案，**不發**「沒開過」。

### 6.5 Vacant 自己壞掉怎麼算（新增，審查人 major）
- **真的 infra_void**：提供者 5xx 重試 4 次仍失敗、每日額度用完、代理程式預算拒絕、容器建不起來。這些題三組全部重跑。
- **不是 infra_void**：Vacant 掛鉤錯誤、Stop 事件遺失、有發現但沒退回、退回時被時限砍掉。這些**以當下工作區打分，算 C 組（或 B 組）成績**（意向治療）。另外報「Vacant 自身失敗率」，預註冊寫上限（提議 10%），超過整個 run 作廢。

### 6.6 檢定（用倉庫現成函式）
- **唯一主要檢定**：C vs A，DABstep 79 題，McNemar 精確檢定；差距的 95% bootstrap 信賴區間（2,000 次）。
- 次要（描述，Holm 校正）：C vs B、B vs A。SpreadsheetBench 40 題、Terminal-Bench 8 題**只做描述**。
- **傷害**：A 對 C 錯的題數；C 組內「第一次交件已對、退回後變錯」的題數（紀錄鏈存有兩個時間點的交付物，可離線用官方評分程式打分），按「第一次是否已對」分開報。只給信賴區間。

### 6.7 三階段與集合分離（審查人 major）
1. **試點**（≈0.70 美元）：**試點題目與正式題目不重疊**。DABstep 試點＝正式集困難題裡不在 79 題內的 10 題（隨機、種子記錄）；SpreadsheetBench 試點＝先排除的 10 題；Terminal-Bench 2 題。每題跑 A、A′、B、C。目的：管線通、量翻轉率、量誤報率、量每題呼叫數與 C 組多出的時間。證據規則的調整**只准在試點集和倉庫的假模型情境**上做。
2. **預註冊**：題目清單與種子、模型與提供者、pi 版本、映像檔 digest、Vacant 的 commit、證據規則檔與三組文字的 sha256、主要指標、檢定、停止規則、誤報率上限、Vacant 失敗率上限；人類簽名後存進倉庫。**看過任何正式題之後，規則不准再改。**
3. **正式批次**：DABstep 79、SpreadsheetBench 40、Terminal-Bench 8。

---

## 7. 記錄什麼（不記＝沒跑過）

1. **記錄代理程式**：每次 HTTP 請求／回應原始位元組、模型、提供者、量化（從當日端點快照對回）、輸入／輸出／推理／快取 token、費用、finish_reason、重試（最多 4 次，每次一列）、標籤（題庫-題號-組別）、**主機 id**。金鑰只在代理程式記憶體，容器用假金鑰。
2. **agent 軌跡**：Harbor 存的 JSON 輸出與 session 檔。
3. **Vacant 紀錄鏈**（B、C）：簽章鏈、每步檔案差異、證據檢查結果（含被豁免的項目與原因、被 KS-1 擋下換成替代行的次數）、退回文字、交件說明。
4. **讀檔見證**（三組）：檔案開啟清單。
5. **harness 與評分**：Harbor 的 job／result、每題 reward、測試輸出、**實際拉到的映像檔 digest、LibreOffice 版本**。
6. **環境清單**：主機、Docker 版本、harness commit、資料版本與題號清單、pi 版本與套件 sha256、Vacant commit、模型／端點快照 sha256、代理程式設定、每組完整指令列、**模型發布日期 vs 資料集日期**（污染風險記錄）。
7. **兩台機器的帳本合併**（新增）：每個代理程式實例標主機 id；每次跑之前和跑完，用 OpenRouter 的額度查詢 API 對帳；最後合成一份總表，列出「我們帳本總額」與「OpenRouter 回報總額」的差。
8. 整個 run 用倉庫的打包規則打包（私鑰排除），登記進 runs 索引。

---

## 8. 施工順序（先做什麼、多大、哪些能用假模型測）

Vacant 今天只有寫了「契約」才會在 Stop 時檢查。零設定要補的東西（行數是估的）：

**現在就能寫、用假模型測（不花錢）**
1. 模式開關（off／observe／persona／evidence）+ 沒契約也記錄：約 80 行 + 15 測試。
2. 讓 Vacant 認得自己的退回文字（否則 OpenCode 會當成人的新要求）：約 10 行 + 4 測試。
3. Harbor 包裝 agent（pi，只覆寫安裝與執行）+ 離線 Vacant 安裝包 + **pi 版本釘死**：約 300 行。
4. **閘門 2**：在 Harbor 容器裡用假模型，埋一個錯，證明 C 組多送 N 次帶證據的請求、最後檔案有變；同時證明「一次 Stop 可要求一次繼續，繼續後會再 Stop 一次」所以 2 回合成立（pi 文件寫的是「每個 Stop 一次繼續」）。約 150 行測試腳本。
5. 證據檢查（純看紀錄鏈，可離線重放）：約 650 行 + 40 測試。含：沒讀的資料、沒來源的數值、先寫後讀、說測過沒跑、失敗步驟被忽略。
6. 衍生值判斷 + 豁免表：約 230 行。
7. 審稿回合（固定文字常數 + 證據渲染 + **同步化 B 的渲染** + KS-1 替代行）：約 240 行 + 24 測試。
8. 交件說明：約 150 行 + 10 測試。
9. Stop 決策 + 定位 + 意向治療的失敗記錄：約 200 行 + 22 測試。
10. **讀檔見證包裝**（三組共用，容器內）：約 120 行 + 8 測試。
11. 環境清單、打包、兩台機器帳本合併：約 250 行。
12. 專案檢查（自動找測試指令，只報退步）：約 250 行。DABstep、SpreadsheetBench 用不到，排最後。
13. 把 agent 最後一段話轉給 Vacant（pi）：約 40 行 JS + 30 行 Python。

**需要金鑰**
- 記錄代理程式併入倉庫（現在是 lead 自己跑的版本）：約 500 行；先用假模型測，最後用真金鑰跑 2 次確認。
- 閘門 1、試點、正式批次。

**順序**：1→2→3→4（閘門 2）→ 閘門 1（可與 5 並行）→5→6→7→8→9→10→13→11→試點→預註冊→正式→12（有空才做）。

---

## 9. 時程、地點、時間與錢

### 9.1 逐週時程（金鑰約 2026-10-25 失效）
| 週 | 日期 | 做什麼 | 砍線 |
|---|---|---|---|
| 第 1 週 | 09-25～10-01 | 施工 1～4；**閘門 2**；**閘門 1**（0.15 美元）；記錄代理程式併入倉庫 | 閘門 1 全部候選都不會用工具 → 停下來問人類 |
| 第 2 週 | 10-02～10-08 | 施工 5～10、13；試點（0.70 美元）；A/A′、誤報率、每題時間 | 誤報率 >10% → 修規則後在試點集重量，正式延後 |
| 第 3 週 | 10-09～10-12 | 用試點數字重算檢定力；寫預註冊；**人類 10-12 前簽字** | 10-15 沒簽 → 砍 Terminal-Bench；10-18 沒簽 → 砍 SpreadsheetBench |
| 第 3～4 週 | 10-13～10-20 | 正式：**DABstep 最晚 10-18 開跑**（約 6 小時）→ SpreadsheetBench（約 5 小時）→ Terminal-Bench | 錢剩不到「一題 A+B+C 最壞成本」就不再開新題 |
| 第 4 週 | 10-21～10-24 | 打包、對帳、展場素材離線渲染 | — |

### 9.2 地點、時間、錢
| 事項 | 地點 | 時間 | 錢 | 依據 |
|---|---|---|---|---|
| Vacant 零設定功能 + 假模型測試 | 這台機器 | 工程時間（約 2,700 行 + 200 測試） | 0 | 第 8 節估算 |
| 閘門 1：3 候選 × 4 題 | 這台機器 | 約 1 小時 | ≤0.15 | 每題實測 0.001～0.008 × 12 |
| 試點：22 題 × 4 次（A、A′、B、C） | 這台機器 | 約 3 小時 | ≤0.70 | 88 次 × 約 0.007 |
| DABstep smolagents 錨（dev 10，A 組） | 這台機器（主機，不用容器） | 30 分 | ≤0.05 | 實測 4～8 次呼叫／題 |
| 正式 DABstep 79 題三組 | 這台機器 | 約 6 小時 | ≤1.60 | 實測 0.0012～0.0067／題 × 3 × 1.3 |
| 正式 SpreadsheetBench 40 題三組 | 這台機器 | 約 5 小時 | ≤1.20 | 實測 0.0074／題 |
| 正式 Terminal-Bench 8 題三組 | 這台機器 | 1～6 小時 | ≤0.60 | 實測單次 0.0023；整題未知 |
| 預留（真 infra_void 重跑） | — | — | 約 0.48 | 4.80 − 上面各項 − 已花 0.024 |
| LiveCodeBench 合理性檢查（100 題 × 8 次） | **你的電腦** | 約 1 小時 | 0.26（估） | 官方參數 |
| Aider 20～30 題、Terminal-Bench 全集與 qemu 兩題 | **你的電腦** | 未知 | 估 1～2 | 未驗證，延後 |

**所有金額都是用 qwen3.5-9b 的實測算的；閘門 1 之後用選定模型的數字重算，重算後的表附在預註冊裡。**
這台機器：4 核、15 GB 記憶體、約 18 GB 硬碟且與其他工作共用；並行數 1～2。

---

## 10. 人類要提供／決定的事

1. **簽預註冊**（10-12 前）。沒簽之前所有數字只能說「看得到差別」。
2. **選主模型**：閘門 1 跑完會給你三個候選的實測表（會不會用工具、每題幾次、幾分、多少錢）再選。若你要「4-bit」的字面意義：gemma-4-26b-a4b-it（fp8）或 qwen3.5-9b（fp4）；若要最像家用 12B gemma 的權重：gemma-3-12b-it（但它是 bf16，展場要標「未量化」）。
3. **簽字認可「偏離論文跑法」**：DABstep、SpreadsheetBench（和延後的 Aider）都用 Harbor 轉接版，不是論文原版；Harbor 的對照數字是「轉接版 vs 另一個 agent 改版」，不是「vs 論文」。只有 Terminal-Bench 是字面上的官方跑法。
4. **同意「唯一的統計主張只有 DABstep 79 題」**；SpreadsheetBench、Terminal-Bench 只做展示與描述。
5. **同意展場的基線只能當背景**：SpreadsheetBench 400 題版沒有小模型公開成績；DABstep 沒有 Qwen／Gemma；Terminal-Bench 小模型數字未核對。
6. **要不要儲值到 10 美元換免費模型 1000 次／天**：建議不用。
7. **要不要花 Anthropic 額度重跑 Harbor 的對照**：建議不用。
8. **DABstep 官方排行榜提交**（需 HuggingFace 帳號）：你決定。
9. **你的電腦**：Docker、正常網路、約 15 GB 硬碟；跑 LiveCodeBench、Aider、Terminal-Bench 全集；代理程式在你電腦也跑一份（金鑰只放你那裡），帳本按第 7 節合併。
10. **核准展場措辭**（第 11 節）。
11. **確認 5 美元的分配**：閘門 0.15、試點 0.70、DABstep 1.60、SpreadsheetBench 1.20、Terminal-Bench 0.60、預留約 0.48（硬上限 4.80，已花 0.024）。

---

## 11. 風險與誠實邊界

**贏了代表什麼、不代表什麼**
- 贏＝「在 DABstep 這 79 題、pi、這個模型與提供者、這些設定下，裝 Vacant 的那組分數較高，且多花了報告裡的呼叫數」。
- 不代表「Vacant 讓 agent 變聰明」、「抓得到所有錯」、「換模型也贏」、「換 agent 也贏」。
- B 組若比 A 差，是文獻預期，照實報。

**方法上的限制**
- Vacant 的「讀過什麼」是下界；措辭一律「在有紀錄的步驟裡找不到」；靠讀檔見證量冤枉率，不是靠 Vacant 自己。
- C 組多用資源；「更好」可能部分是「更多算力」。
- 樣本小：79 題只能看很大的差；40 題與 8 題不做統計。
- 不一致比例是假設，試點後重算；A/A′ 翻轉率會告訴我們「純運氣」有多大。
- DABstep 正式集答案是排行榜擷取的近似值；dev 答案公開可能被背；模型發布日期晚於題庫。
- Harbor 版 ≠ 論文原版；Harbor 的對照數字也不是 vs 論文。
- Terminal-Bench 映像檔用標籤釘、SpreadsheetBench 的 LibreOffice 現裝：都改成記 digest／版本、同一題三組同 digest。
- 小推理模型「思考用光」可能讓 Terminal-Bench 三組全 0。
- 這台機器的 CA 憑證繞過與 Ubuntu apt 被擋是環境差異，全部記錄；你的電腦要重新確認不需要。
- 提供者可能悄悄換量化；每次呼叫記提供者、量化對當日快照。
- 金鑰一個月失效；時程砍線在第 9 節。

**展場措辭（建議）**
- ✅「同一題、同一個小模型、同一個 agent，只差有沒有裝 Vacant。你看到的是 N 題裡的一題，重播自紀錄，不是現場跑。同一題重跑本來就有 x% 會變（我們量過）。」
- ✅「Vacant 不知道標準答案。它只看紀錄：這個數字從哪裡來、這個檔案開過沒、說測過有沒有真的跑。」
- ✅「在 N 題裡，裝了 Vacant 的那組多對 k 題、多錯 j 題、多用了 m 次呼叫。」
- ❌「Vacant 讓 AI 更可靠／更值得信任」、「抓出所有錯」、「證明有提升」（除非預註冊批次已簽已跑）、任何未核對的小模型公開成績。
- 「機制模擬」與「真模型重播」在畫面上分開標。

---

## 12. 審查人的每一條怎麼處理

| 嚴重度 | 問題 | 處理 |
|---|---|---|
| blocker | 主模型 gemma-3-12b-it 從沒呼叫過 | 閘門 1（第 5.1 節）；成本表閘門後重算；未過閘門不進預註冊 |
| blocker | C 組退回在 Harbor 的 pi 無介面模式裡沒證明過；pi 裝最新版會漂 | 閘門 2（第 8 節第 4 項）；pi 釘版本；「有發現但沒多出請求」＝C 組失敗（第 3.7 節第 4 點） |
| major | 試點與正式集重疊（dev 10） | 試點改用不在正式集的困難題 + 排除後的 SBV 10 題；規則與文字 sha256 凍結（第 6.7 節） |
| major | 82 題重複計算、兩個主要指標 | 79 題不重複；唯一主要分析 C vs A McNemar（第 3.2 節） |
| major | Vacant 自身失敗算 infra_void 偏向 C | 意向治療；另報失敗率；上限 10%（第 6.5 節） |
| major | B 組退回時機與次數和 C 不同 | B 改為同步化角色組；原本的固定一次退回改為選配 B2（第 4.1 節） |
| major | 重做回合與時限、回合上限的互動沒說 | 官方時限、三組都不設回合上限；被砍以當下工作區打分算 C（第 4.1 節） |
| major | 沒有噪音控制 | A/A′ 重複；同題三組連跑、順序隨機；記提供者版本（第 5.3 節） |
| major | 「沒開過」是下界、誤報重放沒有真值 | 讀檔見證三組共用；預註冊誤報上限；指令文字提到的檔不發「沒開過」（第 6.4 節） |
| major | 次要指標循環、三組儀器不同 | 改稱操作檢查；三組都由 Harbor 軌跡重建、同一套離線檢查（第 6.2 節） |
| major | Harbor 對照數字說過頭 | 重標為「轉接版 vs 另一個 agent 改版」；列為人類簽字項（第 3.2、3.3、10 節） |
| major | 統計建立在假設、含不可能成功的檢定 | 唯一主要檢定；試點後重算檢定力；刪 TOST；SBV/TB2 只描述（第 6 節） |
| major | 沒有對金鑰失效的時程、沒有預算停止規則 | 逐週時程與砍線；每題庫預算；停止規則；題目順序隨機（第 9.1 節） |
| minor | LCB 不是再現、沒測工具呼叫 | 改稱合理性檢查；8 次取樣；窗口限 2025-03 前；工具呼叫由閘門 1 驗（第 3.5 節） |
| minor | 污染風險 | 記錄發布日期；主集以正式集為主；傷害配對按「第一次已對」分開報（第 3.2 節） |
| minor | 評分環境浮動 | 映像檔建一次、記 digest、LibreOffice 版本、同題同 digest（第 3.3 節） |
| minor | 額外審稿模型呼叫 | 一律關閉，寫進預註冊（第 4.1 節） |
| minor | 附錄 B 對不上帳本；9-vs-5 說法；TB2 2.5% | 附錄 B 補三列已對齊；改口為「設計要抓的那種」；2.5% 不上展場 |
| minor | 模型選擇偏離「gemma 4、量化」 | gemma-4-26b-a4b-it（DeepInfra fp8）列入候選並進閘門 1；bf16 差異要標（第 5.1 節） |
| minor | 只評 pi 卻談四個 agent | 所有結果限定 pi；其他三個這輪不加（第 5.4 節） |
| minor | 證據行 KS-1 失敗怎麼辦 | 截斷轉義 + 固定替代行 + 上鏈計數（第 4.2 節） |
| minor | 兩台機器帳本沒合併規則 | 主機 id + OpenRouter 額度 API 對帳 + 合併總表（第 7 節第 7 點） |

**部分不採納的一條**：審查人建議試點的 DABstep 題目「從正式集裡不在主清單的困難題抽」。我們照做，但要說明代價：小模型在困難題可能接近 0 分，試點估出來的「不一致比例」會偏低，檢定力重算可能偏保守。我們接受這個代價，因為另一個做法（從 72 題簡單題挖 10 題出來當試點）會讓正式集掉到 69 題，檢定力從 0.82 掉到約 0.75。倉庫的假模型情境（埋好的錯）另外補足規則調整所需的正例。

---

## 附錄 A：技術識別碼（給工程用，人類可跳過）

- Harbor：github.com/laude-institute/harbor @ `6cb9ff3167596c456e0b24622d473b59fc9ab6c7`；agent 接法 `src/harbor/agents/installed/{pi,opencode,claude_code,codex}.py`；自訂 agent `--agent module:Class`；pi 版本用 `--ak version=<x>` 釘（pi.py L179 預設 `@latest`）；`--ak max_turns` 一律不設。
- Terminal-Bench 2.0 抽樣：`terminal-bench-sample@2.0`，terminal-bench-2-0-sample @ `7e917f35c281188532772312d4ad91ca9274febc`；全集 `terminal-bench@2.0` @ `69671fbaac6d67a7ef0dfec016cc38a64ef7a77c`。這台機器要 `--mounts`（CA 憑證）與 `--ae/--ve SSL_CERT_FILE、CURL_CA_BUNDLE、NODE_EXTRA_CA_CERTS`；pi 要 `--ak model_api=openai-completions`；代理程式從容器看是 `http://172.17.0.1:18900/t/<tag>/api/v1`。
- SpreadsheetBench Verified：`spreadsheetbench-verified@1.0`，harbor-datasets @ `0ad7209b09780e78c6c80f194e49e353191be1cc`；原倉庫 RUCKBReasoning/SpreadsheetBench @ `49b73a94775fb489063f60ca1865e3a650079a79`；parity 的「original」＝Rebabit/SpreadsheetBench@harbor-parity（claude-code）。
- DABstep：`dabstep@1.0`；HF `adyen/DABstep` revision `51884d3339cbc1f05d0e2e02bac7995ea605d69a`；all.jsonl sha256 `d776385a…`、dev.jsonl `c1da755a…`；dev 與正式集重疊 6 題（5,49,70,1305,1681,1753；adapters/dabstep/README.md L13、L58）；主集 79 題＝正式集 72 easy ∪ dev 7 hard；官方 baseline `smolagents==1.3.0`、`transformers==4.47.1`、`--max-steps 10`、`max_tokens=3000`；parity 的「original」＝harvenstar/DABstep harbor-adapter（claude -p），README 與 parity_experiment.json 對 Harbor 側 agent 記載不一致（terminus-2 vs claude-code@2.1.39）。
- LiveCodeBench：LiveCodeBench/LiveCodeBench @ `28fef95ea8c9f7a547c8329f2cd3d32b92c1fa24`；HF `livecodebench/code_generation_lite` @ `0fe84c3912ea0c4d4a78037083943e8f0c4dd505`；`anthropic==0.42.0`；`custom_evaluator.py` 路徑；`SYSTEM_MESSAGE_GENERIC` + `get_generic_question_template_answer`；n=8、T=0.2、top_p=0.95、max_tokens=2000、timeout 6 s；`--end_date 2025-02-28`。
- Aider Polyglot：`aider-polyglot@1.0`；polyglot-benchmark @ `7e0611e77b54e2dea774cdc0aa00cf9f7ed6144f`（無 LICENSE 檔）；aider @ `5dc9490bb35f9729ef2c95d00a19ccd30c26339c`（tries=2 在 benchmark.py L200）。
- 模型端點（orq/ 快照 2026-09-25）：`google/gemma-3-12b-it` @ deepinfra/bf16 0.05/0.15、max_out 16384、tools 有、無 reasoning 參數；`google/gemma-4-26b-a4b-it` @ deepinfra/fp8 0.07/0.34、max_out 16384、tools 有、reasoning 可關；`qwen/qwen3.5-9b` @ darkbloom/fp4 0.08/0.13、reasoning 參數有；`openai/gpt-oss-20b` @ akashml/fp4 0.02/0.10、reasoning_effort 有；`google/gemma-4-26b-a4b-it:free` @ Google AI Studio。
- 代理程式：`ops/eval/orproxy.py`（現行）→ `ops/zeroeval/orproxy.py`（以 `vrun/wireproxy.WireProxy` 為基底，加 `host_id`）；帳本 `scratchpad/evalrun/ledger/{io.jsonl,ledger.jsonl,summary.json}`；對帳用 `GET /api/v1/credits`。
- Vacant：`VACANT_MODE=off|observe|persona|evidence`（persona＝同步化 B；`VACANT_PERSONA_ALWAYS=1`＝B2）；`VACANT_HOME=/logs/agent/vacant`；`VACANT_REVIEWER_CALL=0` 寫死；新檔 `trace/evidence.py`、`trace/derive.py`、`trace/evidence_rules.json`、`trace/review.py`、`trace/delivery.py`、`trace/readoracle.py`；`hookpolicy.decide_stop_zero`、`stopcheck.localize_evidence`；pi 擴充 `agent_before_settle` 回 `{continue:true}`（adapters/agents.py L326；pi docs/extensions.md L66、L109：每個 settle 一次繼續）；閘門 2 腳本 `ops/zeroeval/gate_pushback.py`（`ops/intake/mock_model.py`）。
- 讀檔見證：`strace -f -e trace=openat,open -o /logs/agent/reads.log` 包住 pi 程序；容器不允許 ptrace 時退用 `sitecustomize` + `sys.addaudithook("open")` 與 shell 指令文字掃描；三組同一設定。
- 統計：`vacant_network/research.py` 的 `mcnemar_exact`、`boot_ci`、`holm_bonferroni`、`mcnemar_power`、`mcnemar_n_required`（預設 power 0.85）、`stratified_mcnemar_exact`；`tost_equiv_boot` 這輪不用。
- KS-1：`vacant_network/memory.py::KS1_FORBIDDEN`（7 個詞）、`trace/feedback.py::feedback_ks1_clean`；替代行常數 `WITHHELD_LINE`。
- 預註冊範本：`decisions/prereg/PREREG_20260924_R536_LOCALIZED_FEEDBACK.md`（未簽）。

## 附錄 B：本輪費用與呼叫數（代理程式帳本 summary.json，2026-09-25；已逐筆對齊，41 次、0.02414057 美元）
| 標籤 | 呼叫 | 費用（美元） |
|---|---|---|
| smoke-proxy | 2 | 0.00001904 |
| live-test-ping | 1 | 0.00000226 |
| try1-pi-qwen9b | 4 | 0.00079356 |
| live-lcb-lcb_3594 / 3607 | 2 / 1 | 0.00137248 / 0.00106920 |
| live-tb2-regex-log | 1 | 0.00226728 |
| live-aider-polyglot python / go | 2 / 1 | 0.00092075 / 0.00028024 |
| live-sbv-10452 | 7 | 0.00740026 |
| live-dabstep-5 / 70 | 4 / 8 | 0.00120645 / 0.00673689 |
| live-gdpval-83d10b06 | 8 | 0.00207216 |
| **總計（全部 qwen3.5-9b @ darkbloom/fp4）** | **41** | **0.02414057 / 4.80** |

token 總計：輸入 212,244、輸出 55,085（其中推理 47,318）。
（研議證據：`ops/eval/evidence_20260925/`；第 1 版計畫：`ops/eval/evidence_20260925/notes/plan-v1.md`；審查意見：`study_result.json` 的 `critic`。）

---

## 人類裁決（2026-09-25，覆蓋上面第 4、5 節的對應部分）

- **模型只用兩個家族**：Qwen3.8 與 Gemma 4。OpenRouter 上 8–27B 的 Qwen3.8 只有 27B，Gemma 4 沒有 12B。
  定為 **qwen/qwen3.8-27b @ darkbloom/fp4** 與 **google/gemma-4-26b-a4b-it @ deepinfra/fp8**；代理白名單只剩這兩個。
  gemma-3-12b-it（閘門 1：0/4，工具呼叫寫成文字）、qwen3.5-9b 不再使用。
- **思考開與關都跑**；人類偏好「開思考」＝比較像平常的用法，所以開思考是主要比較、關思考是次要。
  開關由記帳代理依條件強制（`/t/<tag>/think/on|off/`：on＝reasoning enabled、effort medium；off＝disabled），
  實測：兩個模型關思考時每一通推理 token 都是 0（`ops/eval/evidence_20260925` 帳本的 thinkprobe-*、proxytest-* 標籤）。
- **組別**：A（不裝）與 C（Vacant 零設定）。**B 先不做**，留給以後。條件＝2 模型 × 2 思考 × {A, C}＝8 種。
- **回合上限 15**（pi 的 `max_turns=15`），所有條件一樣；官方沒有這個上限，這是寫明的偏離。
  另外每一跑有 0.30 美元的安全上限（代理的 `tag_cap_usd`），所有條件一樣。
- **平行**：同時 4 個容器；每一跑一個全新容器；題目與條件順序隨機交錯。
- **錢**：這把金鑰不再加值（約 2026-10-25 失效）；剩約 4.70 美元，設計要放得進去。
