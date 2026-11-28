# DECISION 2026-11-27 — Haiku 寫的驗收考卷（37 題 Exercism）：產出、凍結、量品質

**性質：探索性前導（exploratory pilot），不是預註冊的檢定。** 沒有 p 值、沒有成敗門檻；只回報量到的數字。
動機（人類方向會議的平行方向）：沒有測試時，由較強的模型只看需求寫一份考卷，小的本機模型（別處跑、不是本任務）
拿那份考卷驗收。本任務只負責**產生並凍結考卷**，並量**未經修改的考卷有多準**。

## 輸入（寫考卷的模型只看得到這些）
- 題庫：`/opt/ctlwork/bm_tasks/ctl37`（37 題，建置見 `ops/redo/results/ctl_haiku_20261127/BANK_REBUILD.md`，
  公開 exercism/python commit 479f11b4）。
- 每題兩份輸入，逐字：
  1. `workspace/goal.md`＝題庫裡工人拿到的需求陳述（＝Exercism `.docs/instructions.md`，有 `instructions.append.md` 就接在後面；
     **不含** `introduction.md`——已核對：goal.md 不含 introduction）；
  2. 存根檔＝公開 repo 該題目錄的 `<slug>.py`（函式／類別簽名）。
- **絕不給**：原測試、`.meta/example.py`、任何模型輸出、`contract.md`（內含測試檔名）。每題輸入清單（含 sha256）寫進 `MANIFEST.json`。

## 考卷種類（每題每種一通 Haiku 呼叫，固定提示詞，提示詞逐字存 `prompts/`）
呼叫：`claude -p --model haiku --output-format json --tools ""`＋`--setting-sources "" --strict-mcp-config --disable-slash-commands
--no-session-persistence`，空的暫存目錄為 cwd、全新 HOME、環境清空（只放 PATH／HOME／LANG 等，同 `claude_sandbox_agent.clean_env`）。
**CLI 沒有溫度設定，用預設值**；Claude Code 自己的系統提示仍在（無法移除），照記。基礎設施錯誤重試×4；每通請求／回應寫 JSONL
（`ops/redo/exams_haiku_20261127/calls.jsonl`）。模型名取 CLI 回報的 canonical 名。
- **XM**：只從需求寫輸入／輸出對的測試，至少 8 個斷言，涵蓋文字寫明的規則與邊界。
- **XMV**：同 XM，但每個斷言上一行要有 `# SRC: "<需求或範例的原句>"`。**確定性後處理器**（`tools/xmv_post.py`，非手動）刪掉：
  沒有 SRC 的斷言、SRC 引文（空白正規化、大小寫敏感）不是 goal.md 子字串的斷言。刪除日誌 `xmv_deletions.json`。
  斷言單位＝每個 `assert` 敘述與每個 `with pytest.raises` 區塊。凍結的 XMV 檔＝後處理後的檔；原始輸出另存 `xmv_raw.py`。
- **PB**：把需求拆成可分開檢查的性質（型別／格式、不變量、寫明的邊界行為、範例）；一性質一個獨立檢查函式（一個 `test_` 函式），
  每個附需求原句（docstring 或註解）。
- **EX**：範例由**確定性抽取器**（`tools/ex_extract.py`，無模型）從 goal.md 逐字搬進測試：只認 (a) 程式碼裡的 doctest
  `>>> expr` ＋下一行期望值；(b) `呼叫(...) == 值` ／ `=> 值` ／ `-> 值` ／ `# => 值` 形式；呼叫根名稱必須是存根定義的名字（或其方法），
  期望值必須能 `ast.literal_eval`。抽不到任何一條＝該題標 `none`，**不手寫**。
所有考卷是 pytest 檔，import 方式與題庫測試相同（`from <module> import ...`，`<module>`＝存根檔名）。
輸出無法解析成 Python 者記為 malformed、原樣保留、不重生。**凍結：寫入後永不編輯；重生一律放新的版本化目錄。**

順序：先交 XM 全 37（commit＋push），再 XMV、PB、EX。

## 品質量測（凍結之後；不改考卷）
環境：沙箱（bwrap、無網路）、釘版 venv `/opt/ctl-venv`（Python／pytest 版本記入報告）；單次執行 30 秒時限。
- **考卷自身正確性**：每份考卷對該題參考解（`.meta/example.py`）跑。參考解沒過的每個斷言／測試＝考卷錯誤（誤拒來源）。
  報告每種：參考解逐測試通過率、逐考卷通過率（整份全過）、平均斷言數。逐斷言通過率用 AST 改寫成「每個斷言獨立記錄」的版本另跑
  （拋例外也算失敗；被前面錯誤擋住沒執行到＝記為 unreached，算失敗並單獨列）。
- **錯解攔截**：每題 3–5 個錯解。來源：(a) Devin 校準（`ops/redo/results/ctl_devin_20261127/`，3 題）的失敗交付，及任何 Haiku 失敗（若存在）；
  (b) Haiku 以固定提示詞寫「看似合理、帶一個細微錯誤」的解，每題 4 通（提示詞內以 k＝1..4 指定錯誤類型：邊界／某條寫明規則讀歪／輸出順序或格式／少見情況），
  同樣只看 goal.md＋存根。**入選條件**：對該題**原始完整** Exercism 測試檔（公開 repo 的 `<slug>_test.py`）至少失敗 1 個測試且至少通過 1 個；
  否則丟棄並記錄。報告每種：被考卷拒絕的錯解占比（任一測試失敗＝拒絕）；並報原始完整測試檔自己的同一指標當參照。
- 報告：`ops/redo/results/ctl_exams_haiku_20261127/REPORT.md`（逐題與逐種表、每個錯誤斷言、缺陷）。

## 限制
- Haiku 呼叫總花費上限 **$5**（`total_cost_usd` 加總）；超過即停並回報。
- 4 CPU 容器共用，工作並行度小。生成與紀錄檔 commit 前掃憑證字串。
- Haiku 可能在訓練中見過 Exercism 測試與解答（無法排除）：考卷「只看需求」是輸入限制，不是對模型記憶的保證。

## 口徑
✅「Haiku 在只看需求的條件下寫的未修改考卷，對參考解的通過率為…、攔下錯解…%（37 題、探索性）」。
❌ 把數字說成考卷「夠用」或可外推到別的題庫／別的寫考卷模型；❌ 錯解攔截率＝考卷強度（錯解是 Haiku 寫的 ＋ Devin 3 題，分布未知）。
