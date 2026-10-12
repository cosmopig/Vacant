<!-- 狀態：施工依據（2026-09-25）。第 1 版設計與審查：ops/eval/evidence_20260925/cdesign/
     （design_v1.md、agent_texts_v1.md、critic_v1.md：4 blocker、15 major、5 minor；acceptance_spec.json；install_audit.json）。
     第 2 版＝把審查的每一條收進來；自動修訂那一步被帳號用量上限打斷，這份由主線程逐條寫。 -->

# 零設定 Vacant（C 組）施工設計 第 2 版

產品原則見 CLAUDE.md〈產品原則〉：裝一次、照常用、零設定、安裝最小；成果要比沒裝好；
**不准把對的東西弄壞**。第 1 版的審查指出，照原樣做會把許多正確的作答退回去（四捨五入的數字、
只讀了需要的那兩個檔、用 `ls` 列過檔名、寫好再回頭核對……）。第 2 版的總原則因此是：

> **只有「幾乎一定是真的問題」才退回；其他一律只寫進交件說明。**

## 一、範圍

**第 1 期**（能公平比較 DABstep，而且不把對的弄壞）：模式開關、沒有契約也記錄、四種退回規則
（下面第二節）、退回的文字、交件說明、失敗一律放行、模擬使用者的驗收、用真實紀錄重播量誤報。
**第 2 期**（之後再做）：漏寫的值（SpreadsheetBench 那種「算出 9 個只寫 5 個」）、敘述和資料日期矛盾、
替人跑專案自己的測試、病歷分段與保留期限、OpenCode／Codex 的細節打磨。

## 二、什麼會退回、什麼只進說明

| 發現 | 退回？ | 條件（全部成立才算） |
|---|---|---|
| 沒有出處的具體值 | **退回**，最多 2 回合 | ① 任務有點名資料（檔案或路徑形式的資料夾）；② 值在這一回合**新增或改過的那幾行**；③ 交付物是文件類（md/txt/rst/adoc/tex/html/csv/tsv；程式碼與 .json 不查）；④ 值是 agent **自己打出來的**（寫檔／編輯工具的內容，或 echo／printf／heredoc 的文字）——由它跑的程式算出來寫進去的不算；⑤ 這個任務看過的東西（每一步的輸出、讀到的內容、人打的話）裡找不到它，比對時會把千分位、幣別、四捨五入（四捨五入／銀行家／截斷）、浮點雜訊、科學記號、×100 的百分比、K／M／B 縮寫、日期的各種寫法都當成同一個值；⑥ 不是由看過的表格簡單算得出來的（欄位加總／平均／筆數／最大最小、按另一欄或按年／月／季分組加總、兩個已知數的比例／百分比／和／差）；⑦ 不在豁免裡：人打的話裡本來就有的值、**今天與這個工作階段的日期**、標了假設／提案的行（只限多行文件）、`Unverified`／`Assumptions` 等標題底下的行 |
| 任務**單獨點名**的檔沒打開 | **退回**，最多 1 回合 | 人打的話裡寫了這個檔（檔名或路徑），這一回合沒有任何一步讀到它。只點名資料夾時，資料夾裡沒讀的檔**只進說明**；同一次若有「沒有出處的值」，就把它們附在那一行 |
| 說測過但紀錄對不上 | **退回**，最多 2 回合 | 最後的訊息有「測試通過／build 成功」這類說法，且：沒跑過任何測試指令；或最後一次跑是失敗的；或最後一次通過之後程式碼又改過 |
| 失敗的步驟被略過 | **退回**，最多 2 回合 | 失敗的是**跑 agent 自己寫的腳本**或**讀給定資料**的那一步；之後才寫出交付物；後來沒有再成功跑過同一件事、也沒有用別的方法成功產出同一個交付物；最後的訊息也沒提到它失敗。安裝套件、import 檢查、`--version`、網路抓取、`which`／`ls`／`grep` 這類探路一律不算 |
| **要求寫出的檔不存在**（第 2.1 版加） | **退回**，最多 2 回合 | 人打的話裡要求寫出某個檔（「write/save/output … to/in PATH」，或 `output path` 這類標籤下一行的路徑；只收有副檔名的路徑），agent 說做完時它不在工作區裡（看紀錄裡最後的工作區狀態）。退回的那一行：`The request asks for {path}, but it does not exist. Finish the task and write it.` |
| 其他（沒讀的資料夾成員、沒點名資料時沒出處的值、看不到的步驟…） | 只進說明 | — |

回合的算法：人每打一個新要求重新算；Vacant 自己的退回文字、agent 自己排的提示、子 agent 的回覆都不算新要求（沿用 `capture.classify_prompt`）。

**解決怎麼算**：看**現況**，不看發現的編號有沒有再出現——值不在原位置了、那一行標了假設、檔有被讀到了、測試說法拿掉了或之後有通過的測試、失敗的步驟之後成功了。**「在訊息裡承認沒驗證」算揭露，不算修好**；交件說明把兩者分開寫。

## 三、給 agent 的文字（英文；KS-1：沒有責任／懲罰字眼、沒有行動者識別；第二人稱只用在「請做」）

```
Before delivery: a review of the recorded steps of this task found points to redo.
Take the role of a careful reviewer who checks the draft against the materials given for the task. Redo only the parts listed below; leave everything else as it is.
- {path} line {n}: "{value}" was not found in anything this task read or computed. Recompute it from the given files (inspect them with head, or load them in code), or mark it as an assumption on that line.
- {path}: "{value}" was not found in anything this task read or computed. Recompute it from the given files in a command (inspect them with head, or load them in code) and write only the recomputed value to {path}.      ← 單行檔或任務說「只寫答案」時用這一句
  （同一次有沒讀的資料時，行尾加：Given files not opened so far: {a}, {b}.）
- {path} was named in the task but was not opened in the recorded steps. Inspect it (for example with head, or load it in code) and redo the parts that depend on it.
- The final message says "{quote}", but no test or build command ran in the recorded steps. Run it and report the actual result.
- The final message says "{quote}", but the last test run (step {k}: {cmd}) failed. Fix it and re-run, or report that it fails.
- The final message says "{quote}", but {path} changed at step {k} after the last passing run (step {r}). Re-run the tests and report the result.
- Step {k} ({cmd}) failed: "{error line}". The deliverable was written after it without that output. Fix and re-run it, or say in the final message that it failed.
This review lists what the record shows; it does not say whether the answer is right.
```

第 1 版要 agent 在最後訊息加三個標題（Checked／Fixed／Unverified）——**拿掉**：它會改變輸出格式、讓模型用揭露代替修正。交件說明由 Vacant 自己從紀錄產生。
引號內的片段最多 80 字元並跳脫；每一行過 `feedback_ks1_clean`（行動者識別改成**整個字比對**，只收這個工作階段的行動者，免得 `plan.md` 因為曾有叫 Plan 的子 agent 而被擋）；過不了的行換成固定的替代行並計數，不會安靜丟掉。第一行 `Before delivery: a review of the recorded steps` 由 `capture.prompt_source` 認成 Vacant 自己的回饋（不是人的新要求、不是值的來源）。

## 四、交件說明

每次放行都寫 `~/.vacant/trace/projects/<專案>/delivery.md`（與 `.json`）：查了什麼（值：幾個追到檔案或指令、幾個是算出來的、幾個追不到；點名的資料打開了幾個；看到的測試）、修好了什麼（哪一回合）、還沒驗證的（包括揭露的假設、沒讀的資料夾成員、追不到的值）。**不寫進工作區、不送給模型。**
畫面上最多 6 行：Claude 的 `systemMessage`、pi 有介面時的 `ui.notify`、OpenCode 的 toast。**`-p`／print 模式只寫檔**，不動 stdout／stderr（腳本會依賴它們）。沒有寫出任何檔的回合什麼都不顯示。

## 五、機制

- **模式**：`install.json` 的 `mode`（`vacant install` 寫 `evidence`）；沒有就是 `evidence`；`VACANT_TRACE=0` 等於關。`VACANT_MODE` 環境變數**只給測試用**，評測的 C 組不准設。
- **沒有契約也記錄**：專案根＝往上找到的 git 根目錄（不越過 `$HOME`），沒有就是 cwd；`$HOME` 本身、`$VACANT_HOME` 不記。
- **一回合的範圍**：這個工作階段裡最後一個「人打的要求」之後的所有步驟（含子 agent）；`vacant do` 的任務訊息也算人的要求。
- **讀到了沒**：讀檔工具的路徑；殼層指令或內嵌程式碼裡出現這個檔的相對路徑、**絕對路徑**、或檔名（左邊界含 `/ { + = , : ( 空白 引號`，所以 `/app/data/fees.json`、`f"{DATA}/manual.md"` 都算）；帶讀內容的動作（python／node／awk／grep／rg／cat／head／sed／jq）作用在它所在的資料夾；這一回合寫的腳本提到它、而且那個腳本有被跑。`ls`／`find`／`tree` 只算看到檔名。
- **Stop 的做法**：父行程先記下最後的訊息，然後在子行程裡跑證據檢查（時限 330 秒，超過就放行並記錯誤）。任何錯誤都放行，畫面最多一行「Vacant check did not run (error recorded)」。
- **病歷的健康**：Stop 時只驗「上次驗過之後新增的那一段」＋接點；驗不過就把舊檔改名留著、從新的一段開始，說明裡講一次，這一次不退回。完整驗證是 `vacant trace verify`。（有契約的路徑維持原本的 `trace_broken` 帳本行為。）
- **安裝**：README 寫一條在乾淨機器上真的會成功的路：`pipx install vacant-network`（或 `uv tool install vacant-network`），再 `vacant install`（撞名時用 `vacant-network install`）。`vacant install` 在自己的指令不在 PATH 上時印出補救那一行；**預設不裝 SKILL.md**（它會改到模型的系統提示，C 組的第一個請求就不再和 A 組相同），要的人加 `--skill`。`vacant --help` 列得出 `install`。要在 ubuntu:24.04 與 debian:12 的乾淨容器裡照 README 實測。

## 六、評測裡的 C 組（產品原則 3）

容器裡只跑使用者會打的安裝指令（wheel 取代 PyPI 下載，其他完全一樣），**不設任何 Vacant 環境變數**。每一跑結束把 `$HOME/.vacant` 複製出來。每一跑都要檢查：`install.json` 有 pi、病歷有步驟事件與 Stop 事件；沒有＝C 組失敗（照算 C 的成績），不是安靜地變成 A 組。

## 七、驗收（產品等級門檻）

沿用第 1 版的 G1–G15（`cdesign/acceptance_spec.json`），改動：
- S2（敘述和資料日期矛盾）、S3（漏寫的值）列為**第 1 期已知抓不到**：要求 0 次誤退回，說明裡不准宣稱查過。
- D1／D2 改用 Harbor 原樣的題目文字與 `/app/data/` 七個檔、cwd＝`/app`。
- 新增負對照（都必須 0 次退回）：D2b（印出 0.5500000000000001、寫 0.55）、D2c（印出 0.08198、寫 8.2%）、D2d（只讀 payments.csv 就答對，手冊與 fees 沒開）、N1b（讀到 1,198,050、寫 $1.2M）、N9（沒給資料的知識文章）、N10（寫了今天日期的報告）、N11（腳本讀 CSV 自己寫出報告）、N12（寫好之後才回頭讀資料核對、內容一致）、N13（pip 安裝失敗、改用標準函式庫完成）、N14（`ls` 之後提到一個檔名）、N15（`grep -rl` 之後改 README）、N16（從候選名單選一個名字當答案）、S8b（下一個要求是無關的小改動，上一輪還開著的值不可以再被退回）、N3b 用原本的提示「…and run the tests.」。
- **用真實紀錄重播量誤報**：把磁碟上已有的真實 pi 紀錄（try1、閘門 1 的 Harbor 軌跡、研究階段的 DABstep 5／70、SBV 10452）轉成病歷再跑證據檢查，逐條人工標記；**答對的紀錄上不可以有任何會退回的發現**，這是花錢試跑之前的門檻。
- G11（第一個請求逐位元相同）、G12（安裝最小，含 PATH 提示）、G5／G6 另外量 4 萬檔。

## 八、施工順序

1. 模式、沒有契約也記錄、回合範圍、安裝／移除／help／PATH、預設不裝技能。
2. 退回文字、回饋開頭辨識、假模型的標記。
3. 最後訊息的傳遞（pi 先，Claude／Codex 的 `last_assistant_message`）。
4. 證據檢查核心：範圍、交付物與改過的行、點名的資料、讀到了沒、沒出處的值（自己打的＋比對正規化＋簡單推算）、點名沒讀。
5. 測試說法、失敗步驟。
6. Stop 決策、子行程時限、失敗放行、解決用現況判斷、病歷分段驗證。
7. 交件說明與顯示。
8. 假模型擴充、模擬使用者（pi 先）、真實紀錄重播。
9. Harbor 的 C 組包裝與閘門 2（假模型在容器裡證明會退回、會改檔）。
每一步都有測試、lint、mypy，整套測試失敗集合等於基線才 commit。

## 九、第 2.1 版：用真實紀錄重播之後的修正（2026-09-25）

重播工具：`ops/eval/replay_pi_session.py`（容器裡把一次真的 pi 工作階段的每一步經過真的 `vacant hook pi` 重做一次）＋
`ops/eval/replay_gate.py`（每一跑一個全新、不連網的題目容器，只用 wheel 安裝＋`vacant install --agents pi`）。
結果落盤：`ops/eval/evidence_20260925/replay/`。

- **誤報門檻過了**：Gate 1 的 9 個可重播的工作階段（DABstep 6、SpreadsheetBench 3；Terminal-Bench 的映像沒有 Python，
  這一版沒重播），答對的 3 跑**全部放行**，交件前檢查 0.3–1.0 秒。
- **但第 2 版的四類在這些真實失敗上一次都不會觸發**：失敗的樣子是「沒有真的呼叫工具（格式錯）」「15 回合用完」
  「讀了資料但推理錯」「只寫了 9 個中的 5 個」。沒有一跑是編出沒出處的值或沒打開點名的檔。照第 2 版去花錢跑，
  A／C 幾乎不會有差別——這件事要在花錢之前知道。
- 因此加了第五類 **要求寫出的檔不存在**：真實失敗裡最常見、又確定是「還沒做完」的一種（對的答案一定有那個檔，退回不會弄壞對的東西）。
  重播：沒寫出答案檔的 4 跑都被退回；答對的 3 跑照樣放行。⚠ 其中 DABstep-70（gemma-4）是 15 回合用完被 Harbor 的擴充中止——
  真的跑的時候 pi 中止之後**不會**進 `agent_before_settle`（pi 0.87.1 `_runAgentPrompt`：中止就跳出迴圈），Vacant 也就不會多給回合；
  重播裡會退回只是因為重播一定送 Stop。所以評測裡 C 組**不會**比 A 組多用回合上限。
- 修正「讀到了沒」：`cd data && cut … payments.csv | … | head` 之前被算成整個資料夾都讀過（交件說明因此會說錯話）；
  `cd`／`ls`／`tree`／`du`／`stat` 連同參數不再算讀資料夾（`tests/test_zero_evidence.py::test_cd_into_the_folder_is_not_reading_every_file_in_it`）。
- 修正「只寫答案」的判斷：之前兩行以內就算（`# Sales` 加一行總數的報告會被叫「只寫重算的值」而丟掉標題）；
  改成只有一行、40 字元以內。
- **評測的安裝要注意**：Harbor 的 pi 用自訂端點時以 `PI_CODING_AGENT_DIR=/tmp/harbor-pi-agent` 跑 pi，裝在 `~/.pi/agent` 的擴充
  **不會被載入**。C 組的包裝要在 Harbor 寫設定之前，用同一個 `PI_CODING_AGENT_DIR` 跑 `vacant install`（使用者的 pi 設定目錄在哪，
  `vacant install` 就裝到哪；這是配合評測框架的隔離，記在評測紀錄的偏差欄）。Terminal-Bench 的映像沒有 Python：
  C 組要用 `uv tool install`（自帶 Python）。
