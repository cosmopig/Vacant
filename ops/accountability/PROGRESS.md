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

## 2026-09-24T19:10Z（UTC 實際約 19:10–20:05）— M8 對抗審查與修正、M9 早上的報告

**做了什麼**
- 對抗審查 workflow：五個鏡頭、47 條、每條附重現腳本，再由另一個 agent 試著推翻（46 條成立、1 條判為既有邊界）。
  全部處理，每條一個回歸測試（`tests/test_trace_hardening.py`，40 條），並用審查者自己的腳本重跑確認。
  逐條表：`ops/accountability/review_m8/FINDINGS.md`；裁決 §七記下改了設計的六條與新增的誠實邊界。
- 完備性批判（理解 workflow 的第七份）另外五條：信譽 stream 帶平台前綴（共用衰減時鐘）、指令檔當成來源、
  子 agent 定義檔的找法、「對的值看不看得到」寫進結論、SessionEnd 不保證觸發（寫進邊界）。
- 四個 agent 的可觀測面底稿補齊（OpenCode、pi）。
- M9：`ops/accountability/MORNING.md`（好消息、壞消息、需要人類決定的四件事）。

**證據**：修正後重跑四個真 agent × 四個埋錯情境仍是 **16/16**，每個 agent 一格、鍵一致；掛鉤 p95 7.1–16.4 ms。
trace＋adapters＋intake 測試全綠；ruff、CI 那組 mypy（94 檔）、check_repo_links 乾淨。全套測試在跑（commit 時未完）。

**下一步**：全套測試失敗集合對基線；之後照 LOOP 的「里程碑之後的改進」往下（更多埋錯情境、子 agent 端到端、
大專案效能、HTTP 收件口接上追緝）。

**偏移檢查**：沒有碰真模型 API；沒有改凍結項；R536 沒發射（等簽字）；給 agent 的文字仍然沒有行動者、逐行過 KS-1。
- 補記（2026-09-24T19:10Z 那一筆）：審查修正之後的全套測試失敗集合**等於基線**（`test_cert_*` 5 條＋
  `test_exhibit_twin_wiring.py` 5 條 setup error，環境造成、與本工作無關，M1 時已對照過）。

## 2026-09-24T19:40Z — 里程碑之後：大專案的掛鉤時間（量了、修了）

**做了什麼**
- 量：`ops/accountability/perf_scan.py`（真的掛鉤進入點，含行程啟動）。4 萬檔的第一次掃描 33.8 秒——超過掛鉤的 30 秒上限
  （被 agent 砍掉＝靜默略過＝更大的缺口）。
- 修（`workspace.py`／`recorder.py`／`blame.py`／`stopcheck.py`／`adapters/hook.py`）：
  1. 掃描變便宜：憑證樣式只編一次、版本庫寫入不 fsync、熱迴圈用字串路徑、沿用的版本不逐檔確認在庫裡。
  2. 掛鉤裡一次掃描最多 8 秒；第一次看超過 ⇒ 背景看（`python -m vacant_network.trace.recorder baseline`），
     背景看的期間掛鉤不重掃；那段時間的步驟「寫了什麼不知道」，背景看完時已經在的值追緝回 UNOBSERVED／gap。
     背景看不完（>5 萬檔）、600 秒沒寫回來、增量掃描也超過 8 秒 ⇒ 關掉逐步掃描，照實記下。Stop 掛鉤也套同一個時限。
  3. 1000 檔以上存差異索引（對上一份完整索引；sha256 綁住）：每一步 0.9 KB（原本 4 萬檔 4.9 MB）。
  4. 追緝重跑只重建繳付物——和收件口的隔離區看同一批檔（原本 `command` 類主張在追緝時看得到收件時看不到的檔）。
- 測試：`tests/test_trace_scale.py` 14 條（時限、背景一次、背景期間不重掃、背景看完恢復逐步、看不到的值是缺口、
  對照組仍 provable、等太久／太大／增量超時都關掉、關掉後連舊索引都不讀、掛鉤有時限命令列沒有、差異索引還原與竄改、
  小專案仍存完整索引、重建只放繳付物且與收件口同判決）。

**證據**：`ops/accountability/evidence_20260924/perf/`——4 萬檔：第一次 8.2 s、之後每次 p95 604 ms、Stop（驗收＋追緝＋重跑）
1.8 s，回饋有 `report.md:2` 與「第一次出現在第幾步」；1 萬檔 2.8 s／271 ms／0.58 s；6 萬檔改到背景、背景看不完 ⇒ 關掉，
回饋只剩驗證器自己的位置。trace 測試 101 條（這一筆原本誤寫 113，20:40Z 更正）＋adapters＋intake 全綠；ruff（CI 那組＋trace 全規則）、CI 那組 mypy、
check_repo_links 乾淨。對抗審查 workflow 與全套測試在跑（commit 時未完；跑完補記）。

**下一步**：審查結果逐條處理；然後子 agent 的端到端（假模型演子 agent：子 agent 寫錯、主 agent 照抄 ⇒ 追緝指到子 agent）。

**偏移檢查**：沒有碰真模型 API；沒有改凍結項；閘門語意沒動；看不到的一律記「沒觀察到」，沒有怪任何人；給 agent 的文字沒變。
- 補記（2026-09-24T19:40Z 那一筆）：全套測試失敗集合**等於基線**（`test_cert_*` 5 條＋`test_exhibit_twin_wiring.py`
  5 條 setup error；逐條 diff 為空）。

## 2026-09-24T20:40Z — 大專案那一輪的對抗審查：8 條全部成立、全部修掉

**做了什麼**
- 對抗審查 workflow（15 個 agent：3 個鏡頭各找、每條另一個 agent 試著推翻）。8 條不重複的問題全部成立，
  6 條是 `1fa8b6e7` 引進的。逐條：`ops/accountability/review_scale/FINDINGS.md`。
- 最重要的一條（三個審查者各自找到）：背景還在看第一眼時開始、看完之後才結束的步驟，寫入消失又沒有缺口，
  之後**只改了標題那一行的另一個行動者背「可證明」**、還記了一筆信譽後果。修：這種步驟結束時把上一次看到之後的
  改動記成缺口，而且它不擋別人記缺口。
- 其餘：背景還在看時的追緝說「還沒看過」而不是「那裡沒有」；沒被看到的步驟寫的腳本不算本來就在；大檔的雜湊
  也看時限；索引 fsync、殘檔重寫、讀不回上一次的狀態就關掉逐步掃描（不再每次掛鉤都炸）；重建繳付物不放符號連結；
  讀不回來的狀態不再當成空的工作區——碰到就 UNOBSERVED。
- 另外修了我自己的漏洞：`1fa8b6e7` 推上去時 CI 那組 mypy 其實不乾淨（我在最後一個改動之前跑的），`28d46087` 修掉。

**證據**：`test_review*` 10 條＋1 條，改之前全紅、改之後全綠（`git stash` 對照）；審查者自己的重現腳本在修正後
重跑：直接跑的 16 支都變成「不歸給任何人」或和收件口同判決；12 GiB 的檔第一次 8.2 秒改到背景、之後每次 0.14 秒。
效能在修正後重跑（`evidence_20260924/perf/`，4 萬檔第一次 5.7 s、之後 p95 597 ms、Stop 1.9 s）。
trace（112）＋adapters＋intake 測試全綠；ruff、CI 那組 mypy（94 檔）、check_repo_links 乾淨。全套測試在跑。

**下一步**：全套測試對基線；然後子 agent 的端到端。

**偏移檢查**：沒有碰真模型 API；沒有改凍結項；所有修正都是往「不歸給任何人」那一邊收；給 agent 的文字沒變。

## 2026-09-24T21:00Z — 子 agent 的端到端：四個 agent 都指到子 agent 那一步

**做了什麼**
- 假模型（`ops/intake/mock_model.py`）會演子 agent：對話開頭的使用者訊息帶 `ROLE:<角色>` 的照那一份劇本；委派步驟用
  各家自己的工具（Claude `Agent` 前景、OpenCode `task`、Codex `multi_agent_v1` 的 `spawn_agent`→`wait_agent`、
  pi 隨附範例擴充的 `subagent`）。`MOCK_BODIES` 可選地存下每一通請求（除錯用）。
- `e2e_trace.py` 情境 E：子 agent 讀帳本、把 96 寫進 `figure.txt`；主 agent 讀它、寫進報告。
- **pi 的真問題**（第一次跑就露出來）：pi 的子 agent 是另一個 pi 行程，Vacant 把它當成另一個主 agent——
  歸因 UNKNOWN、而且子行程在自己的回合結束被要求交出父 agent 的報告（跑了三輪）。修：Vacant 的 pi 擴充在每個
  工具呼叫期間把 `VACANT_PI_PARENT` 放進環境；子行程讀到就回報成那個工作階段的子 agent，回合結束不跑驗收、
  結束送 `subagent_stop`（不收父 agent 的步驟、不交件）。
- 測試：`tests/test_mock_model_roles.py`（角色只看開頭、四家的委派工具、Codex 的等待、子 agent 照自己的劇本）、
  `tests/test_trace_capture.py` 兩條（pi 子行程＝子 agent、擴充的標記與不跑驗收）。

**證據**：`evidence_20260924/e2e_trace_*`（重跑）——**20/20**：原本四個情境 16/16 不變，情境 E 4/4，指到的行動者
Claude `general-purpose`／Codex `default`／pi `worker`／OpenCode `subagent`，都是寫 `figure.txt` 的那一步。
回饋在 Claude／Codex／pi 進了模型的下一次請求（「從第 2 步抄來的；第 5 步寫進報告」），改好後 accept；
回饋裡行動者識別 0/20；鏈 20/20 驗得過；掛鉤 p95 6.7–11.6 ms。

**下一步**：全套測試（跑在 `ecc2ed6d` 上，還沒完）對基線；再下一個改進：更多埋錯情境（例如網頁來源錯、平行委派）
或 HTTP 收件口接上追緝。

**偏移檢查**：沒有碰真模型 API（假金鑰、假端點、隔離 HOME）；給 agent 的文字沒有行動者；E 是推論層，照規則不進信譽；
pi 的標記只加在 Vacant 自己的擴充裡，沒動使用者的設定。
- 補記（2026-09-24T20:40Z 那一筆）：`ecc2ed6d` 上的全套測試失敗集合**等於基線**（逐條 diff 為空）。
  子 agent 那一輪（`5e4d6f70`／`129afe8d`，動了 pi 擴充與 capture）的全套測試另外在跑。
