# 進度紀錄（`/loop` 每一輪追加一筆，新的在下面）

## 2026-09-24T17:00Z — 起點

- 人類確認目標（見 `LOOP.md` §一）並授權整個任務：「我以你們的答案為主直接去做」、
  「明天早上我可以看到好的消息」、用 `/loop` 讓任務不偏移且越來越好。
- 已有的基礎（`e0e19bb1`／`fe4be3cd`／`08bfc873`）：`vacant_network/intake/`（契約、驗證器、
  帳本、收件端）與 `vacant_network/adapters/`（四個 agent 的掛鉤、安裝、`vacant do`）。
  人類的評語：那是「本機多個驗證器」，不是咎責、不是抓錯誤點 ⇒ 這一輪在它上面加**追緝**。
- 背景在跑：
  - workflow `vacant-accountability-understand`：四個 agent 的軌跡可觀測面（真 binary＋假模型）、
    repo 既有的可究責模組、失敗歸因文獻 → `scratchpad/accountability/`
  - workflow `vacant-paper-rationale`：0924 論文研究筆記與文獻卡的「為什麼這樣選、難處」 → `scratchpad/paper/`
  - Fable 設計夥伴：八個取捨問題 → `scratchpad/fable/design_review.md`
- 下一步：三個結果回來後寫 M0 設計裁決，接著 M1。

## 2026-09-24T19:10Z — M0–M5 的第一版落地

**做了什麼**
- M0 裁決 `decisions/DECISION_20260924_ACCOUNTABLE_TRACE.md`（依據：論文取捨 K1–K18、Fable 設計審查、
  Claude Code／Codex 軌跡可觀測面實測，三份底稿都進了 `ops/accountability/`）。與 Fable 不同的一條：
  工作區整個增量掃描（殼層寫檔在兩個平台的每一個通道都只剩指令字串）。
- M1 病歷：`trace/workspace.py`、`recorder.py`（一個專案一條簽章鏈；缺口；平行；post 沒來的步驟；
  拒絕的步驟；任務訊息）、`capture.py`（四個 agent 的原生掛鉤；逐字稿封存＋自稱的模型 id）；
  掛鉤安裝加上 PostToolUse(Failure)／SubagentStop／UserPromptSubmit／SessionEnd（Claude、Codex），
  pi 與 OpenCode 外掛轉送 `tool_result`／`tool.execute.after`（含 call id、子 session）。
- M2 位置：`locate.py`（text／csv_total／json_schema／citations／回溯）；`vacant flag`（owner 簽章的人標記，
  `--dismiss` 撤銷）。
- M3 追緝：`blame.py`（引入它的轉變 → 觀察到的來源 → 往上追 → 重建前後狀態重跑）、`rerun.py`。
- M4 回饋：`feedback.py`＋`stopcheck.py`；Stop 時的回饋改成「哪個檔哪一行、應該是多少、第一次出現在第幾步」，
  沒有行動者（`feedback_ks1_clean` 可執行）；輪數用完／只剩 agent 改不動的 ⇒ Claude `systemMessage` 給人；
  報告寫在病歷目錄；人標記的錯處在契約過了之後也照樣回饋（有輪數上限、不擋收件）。
- M5 後果：`actors.py`（事件化；只有 provable 進信譽、不 slash；撤銷逐位元反轉；輸入錯記來源；缺口記整合覆蓋率；
  `vacant trace actors`；報告尾端的路由建議；`vacant do --agent auto`：n<5 輪流探索、之後 UCB）。
  `vacant do` 也接上：起點、任務訊息、每一次嘗試的追緝回饋取代泛用回饋、最後的結果進帳本。

**證據**
- `tests/test_trace_{workspace,recorder,capture,blame,stop,actors}.py`：47 條全綠。情境 A（輸入錯 ⇒ input／lineage_exact）、
  A′（經 `cat` 讀進）、B（憑空寫錯 ⇒ provable，重跑前 value_here=False、後 FAIL 且值在那裡）、C（腳本錯 ⇒ 指到寫腳本那一步）、
  D（沒被記錄 ⇒ gap，不怪人）、子 agent、平行 ⇒ candidate_set、改好又被改回去 ⇒ 指到改回去的那一步。
- ruff（trace／adapters 全開＋CI 那組）、mypy（CI 那組 92 檔）、`check_repo_links` 都乾淨。
- 全套測試（M1 快照時跑）：失敗集合＝`test_cert_*` 5 條＋`test_exhibit_twin_wiring.py` 5 條 setup error；
  後者在**把我的改動 stash 掉之後一樣 5 條**（環境：fixture 裡的 subprocess），不是這一輪造成的。

**下一步**：M6——四個真 agent（假模型）跑埋錯情境 A／B／C／D，量歸因正確率、負控制、掛鉤 p95、回饋有沒有進下一次模型請求。

**偏移檢查**：仍對準「每一步進簽章鏈、追到那一步與行動者、事實回饋、未解問題被提出、信譽＋路由」。
沒有碰真模型 API、沒有改凍結項（slash 沒用；B 層六情境沒動）、KS-1 有可執行防呆。

## 2026-09-24T19:55Z — M6（四個真 agent 埋錯端到端）＋M7（R536 預註冊草稿與 harness）

**做了什麼**
- `ops/accountability/e2e_trace.py`：四個真 agent × 四個埋錯情境（B agent 憑空寫錯、A 輸入錯、C 腳本錯、
  D 事後在外面改檔＝負控制），原生地跑（命令列上沒有 `vacant`），`vacant install` 的常駐掛鉤。
- 端到端抓到、已修的真問題：
  1. 用 `printf <base64> | base64 -d > report.md` 寫檔時值不在指令字串裡 ⇒ 誤判「指令自己產生的」。
     改成先看指令點名的資料／腳本，再看行動者之前讀到了什麼（回歸測試）。
  2. 重導向的目標（`> report.md`）被當成「指令執行的腳本」⇒ 歸到上一個寫報告的人。
     改成區分「讀的」與「執行的」（直譯器的引數、`./x`）。
  3. `3` 會配到 `Q3` 裡的 3 ⇒ 數字必須是獨立 token。
  4. 同一個 agent 的「錯」與「這一跑的結果」落在兩格（模型 id 只在部分事件上）⇒ 工作階段記住主 agent 自稱的模型。
  5. OpenCode 的 `dispose` 沒帶工作階段 id ⇒ 四跑疊成一跑。外掛記住主 session。
  6. `opencode run` 沒有 Stop ⇒ 沒有追緝。工作階段結束時背景跑 `trace/finalize.py`。
  7. harness 自己的錯：四個情境共用一個專案路徑，讀到的永遠是第一個情境的結論（第一跑的 3 個 MISS 全是這個）。
- M7：`vacant do --feedback-mode localized|generic|none`（三臂只差這一個）；`ops/accountability/r536/`
  （題庫產生器：一半題目帶誘餌輸入；執行器：斷點續跑、隱藏檢查、收斂曲線；收官計算：照狀態表）；
  預註冊草稿 `decisions/prereg/PREREG_20260924_R536_LOCALIZED_FEEDBACK.md`（**待人類簽字**）。

**證據**：`ops/accountability/evidence_20260924/`——歸因 **16/16**；有位置的回饋在 Claude Code／Codex／pi 進了
下一次模型請求（OpenCode `run` 沒有，既有邊界）；回饋裡行動者識別 0/16；鏈 16/16 驗得過；掛鉤 p95 5.6–10.7 ms。
R536 管線冒煙（L-fake）：RS 三次都錯、RF／RL 第 2 次改對——只證明管線。
`tests/test_trace_*.py` 63 條全綠。

**下一步**：M8 對抗審查（workflow）→ 修 → 文件；M9 早上的報告。

**偏移檢查**：沒有碰真模型 API（假金鑰、假端點、隔離 HOME）；沒有改凍結項；R536 沒有發射（等人類簽字）。
