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

## 2026-09-24T21:20Z — 情境 F：網頁本身就錯（`curl`）——原本會怪到 agent 頭上

**做了什麼**
- 讀程式碼找到的漏洞：值來自 `curl <網址>` 的輸出時，追緝落到「指令自己算出來的」⇒ agent 背錯。抓網頁的工具
  （WebFetch）早就算外部來源，殼層的 `curl`／`wget` 沒有。修（`blame._fetched_urls`／`_shell_origin`）：值在有紀錄的
  輸出裡 ⇒ 外部來源（`lineage_exact`，記網址）；輸出導進檔案 ⇒ `heuristic`；指令裡還跑了程式 ⇒ 不叫外部。
- 假模型會回假網頁（`GET /web/<名>`，`run` 裡的 `{{port}}` 換成它的埠）；`e2e_trace.py` 情境 F（Codex 這一格開
  `sandbox_workspace_write.network_access`，否則 `curl` 連不到）。
- 單元測試 3 條（`tests/test_trace_blame.py::test_F_*`；前兩條改之前紅、第三條是對照組）。

**證據**：四個 agent × 六個情境重跑 **24/24**（`evidence_20260924/e2e_trace_*`）。F：四個 agent 都是 `input`／`lineage_exact`、
來源是那個網址，網址記進來源帳，agent 不背；給 agent 的回饋是「the same value came from http://…/web/q3.txt」。
有位置的回饋進了模型 15/15 格（Claude／Codex／pi × A／B／C／E／F），改好後 accept 15/15；回饋裡行動者識別 0/24；
鏈 24/24；掛鉤 p95 7.3–13.8 ms。

**下一步**：子 agent 那一輪的全套測試在跑，完成後對基線（這一輪一起算）；再下一個：平行委派（兩個子 agent 同時寫）、
或 HTTP 收件口接上追緝。

**偏移檢查**：沒有碰真模型 API、也沒有連外網（假網頁在本機）；所有改動都是往「不怪錯人」那一邊；給 agent 的文字沒有行動者。
- 補記（子 agent 那一輪，2026-09-24T21:00Z）：`129afe8d` 上的全套測試失敗集合**等於基線**。情境 F 那一輪（`32ad5ea8`）
  的全套測試另外在跑。
- 補記（情境 F 那一輪，2026-09-24T21:20Z）：`32ad5ea8` 上的全套測試失敗集合**等於基線**。子 agent＋`curl` 兩項改動的
  對抗審查在跑。

## 2026-09-24T22:10Z — 子 agent（pi）與 `curl` 的對抗審查：12 條全部成立、全部修掉

**做了什麼**
- 對抗審查 workflow（14 個 agent，兩個鏡頭；pi 那一組用真的 pi＋它隨附的 `subagent` 範例重現）：12 條全部成立。
  逐條：`ops/accountability/review_subagent_curl/FINDINGS.md`。
- pi：第一版的標記跟著每個工具呼叫走、呼叫結束就刪 ⇒ 平行、被擋的呼叫、重載、巢狀、兄弟的類型、tmux、別的專案六種
  情況都會認錯主／子。重新設計：每個行程一個**固定**標記（session、pid、專案），子行程驗過「pid 還活著、是祖先、
  同一個專案」才接受；叫它的是哪一個呼叫、它是哪一種代理人，由 `Recorder.link_child` 用任務文字對父 agent 還在跑的
  呼叫（對到恰好一個才記，否則不猜）；追緝用記下的 `spawned_by` 找任務說明的來源（巢狀也對）。
- `curl`：第一版只要指令裡有抓網頁的字＋網址就算外部 ⇒ 可以洗掉自己算的值。重新規定：整個指令就是抓網頁（逐段看
  指令字）、網址不是本機、自己寫過的檔與打過的值裡沒有這個值，才算外部；代理／來源頁不是來源；多個網址只是推論；
  沒寫 scheme 的網址也算；`@檔` 上傳算讀。
- 情境 F 的網站改成 `portal.vacant-lab.test`，實驗環境用 `http_proxy` 接到假模型（本機的網址現在照規則不算外部）。

**證據**：審查者的真 pi 腳本（chain＋兄弟、兩個平行、巢狀、串接、重載、tmux、別的專案）修正後全部給出對的主／子；
`curl` 那組 20 個「證明有問題」的測試全部轉紅、5 個對照組照舊綠。新回歸測試改之前全紅（pi 7 條、`curl` 17 條＋巢狀 1 條）。
四個 agent × 六個情境重跑仍 **24/24**（F 的來源是 `http://portal.vacant-lab.test/web/q3.txt`、E 的 pi 子 agent 類型 `worker`
由任務文字對到）；有位置的回饋進了模型 15/15、改好後 accept 15/15、回饋裡行動者識別 0/24、鏈 24/24、掛鉤 p95 6.9–16.4 ms。

**下一步**：全套測試對基線；再下一個：HTTP 收件口接上追緝，或 Claude 背景子 agent 的端到端。

**偏移檢查**：沒有碰真模型 API、沒有連外網；兩項修正都是往「不怪錯人、也不讓 agent 洗掉自己的錯」收；給 agent 的文字沒有行動者。
- 補記（2026-09-24T22:10Z 那一筆）：`5b44ca86` 上的全套測試失敗集合**等於基線**。

## 2026-09-24T22:45Z — 情境 G：Claude 的背景子 agent（它是預設）——驗收會催主 agent 重做，修了

**做了什麼**
- 假模型會把子 agent 放到背景（`run_in_background`），並能「等通知」（`{"await": "notification"}`：沒看到
  `<task-notification>` 之前只回一句話、結束回合）。`e2e_trace.py` 情境 G（只有 Claude Code）：子 agent 在背景把 96
  寫進 `figure.txt`，主 agent 從通知照抄。
- 第一次跑露出產品問題：主 agent 的回合在子 agent 還在做時結束 ⇒ Stop 掛鉤驗收說「報告還沒有」⇒ 主 agent 照回饋把
  子 agent 的工作重做一遍。修：Claude／Codex 另外掛 `SubagentStart`；病歷狀態記下開始了、還沒結束的子 agent
  （`Recorder.subagent_state`／`running_subagents`）；有子 agent 在做 ⇒ 這次回合結束先不驗收（`stop_check_deferred`），
  一小時沒消息當成結束。
- 測試：`tests/test_trace_capture.py` 兩條（背景子 agent 在做時不催、回報之後照常驗；漏掉 SubagentStop 不會永遠不驗）；
  安裝的掛鉤集合測試加上 `SubagentStart`。

**證據**：情境 G 在真的 Claude Code 上：子 agent 在做時沒有回饋、通知回來後主 agent 照抄 96、回合結束驗收 ⇒ 追到**子 agent**
寫 `figure.txt` 的那一步（`general-purpose`，帶它的 id），回饋「it was copied from step 4 (Bash); step 5 wrote it into report.md」，
改好後 accept。全部重跑 **25/25**（Codex 加了 SubagentStart 之後照常啟動、六個情境照過）；有位置的回饋進了模型 16/16、
改好後 accept 16/16、回饋裡行動者識別 0/25、鏈 25/25、掛鉤 p95 7.0–14.3 ms。

**下一步**：全套測試對基線；之後：平行委派（兩個子 agent 同時寫同一個檔）的端到端，或整理早上報告給人類決定的事。

**偏移檢查**：沒有碰真模型 API；改動是「驗收時機」不是「驗收內容」（等子 agent 回報後照常驗；漏事件一小時後照常驗）；
給 agent 的文字沒有行動者。
- 補記（2026-09-24T22:45Z 那一筆）：`53a6459f` 上的全套測試失敗集合**等於基線**。

## 2026-09-24T23:10Z — 情境 H：人標記了契約檢查不到的錯（四個 agent）

**做了什麼**
- `e2e_trace.py` 情境 H：第一跑總數對、「Region: South」錯（契約沒檢查地區）⇒ 收件 accept；兩跑之間人下
  `vacant flag report.md:4 "the region is North, not South"`；第二跑是新的工作階段，agent 什麼都沒做就要結束。
  假模型認得標記的回饋開頭（`FLAG_MARK`）。
- 回饋裡人的話原本標成「check says:」——那是人說的，不是某個檢查。改成「the task owner says:」（測試加斷言）。

**證據**：H 在四個 agent 都 4/4：Claude／Codex／pi 在第二跑的回合結束收到
「report.md:4 says "Region: South" / the task owner says: the region is North, not South / this value first appeared at step 2」，
改好之後標記解決、收件 accept；OpenCode `run` 收不到（既有邊界），標記留在報告裡。全部重跑 **29/29**；
有位置的回饋進了模型 19/19、改好後 accept 19/19、回饋裡行動者識別 0/29、鏈 29/29、掛鉤 p95 6.5–15.6 ms。

**下一步**：全套測試對基線；之後：平行委派的端到端、或把早上報告整理成給人類決定的最短清單。

**偏移檢查**：沒有碰真模型 API；標記仍然不擋收件（那是人類要決定的事，MORNING 第 2 項）；給 agent 的文字沒有行動者。
- 補記（2026-09-24T23:10Z 那一筆）：`e4eb3d55` 上的全套測試失敗集合**等於基線**。
- 早上的報告（`MORNING.md`）整份重寫成現況：八種錯的來源與結論一張表、三輪審查 67 條、大專案的時間、九條邊界、四件要你決定的事。

## 2026-09-24T23:50Z — 情境 I：平行委派兩個子 agent——先收尾的委派把兄弟的寫入掃走，修了

**做了什麼**
- 假模型能在同一則回覆裡叫好幾個工具（`{"parallel": [...]}`；三種協定都支援），Codex 的 `wait_agent` 在第一個
  做完時就回來，所以逐一等。`e2e_trace.py` 情境 I：A 寫 `count.txt`（對）、B 寫 `figure.txt`（96，錯），主 agent 兩個都讀、
  照抄；接受「指到 B」或「B 在裡面的候選集合」，只怪 A 就算錯。
- 第一次跑：Claude 與 pi 給了候選集合，候選是**委派呼叫本身**（「子 agent 跑的時候、它的步驟以外改的」）。原因：
  先收尾的委派呼叫的前後差異掃到了兄弟子 agent 還沒收尾的那一步寫的 `figure.txt`。修（`Trace._credit_delegated_writes`）：
  委派呼叫自己不寫檔；同一個路徑、同一個內容雜湊的版本若是另一個真正的步驟寫的，歸那一步。
- 測試：`tests/test_trace_blame.py::test_a_delegation_that_finishes_first_does_not_take_its_siblings_write`
  （照真的 Claude 跑出來的交錯順序；改之前紅）。

**證據**：I 在四個 agent 都 4/4，而且都是**精確**指到 B 寫 `figure.txt` 的那一步（不再是候選集合）。全部重跑 **33/33**；
有位置的回饋進了模型 22/22、改好後 accept 22/22、回饋裡行動者識別 0/33、鏈 33/33；掛鉤 p95 7.2–16 ms
（Codex 的 F、H 各有一次 40–50 ms，那兩格只有 12–13 次掛鉤，p50 5–6 ms）。

**下一步**：全套測試對基線。之後可做：Codex multi-agent v2、或兩個子 agent 寫同一個檔的候選集合端到端。

**偏移檢查**：沒有碰真模型 API；改動讓追緝更準（從「候選集合」到「那一步」），沒有讓任何人多背；給 agent 的文字沒有行動者。
- 補記（2026-09-24T23:50Z 那一筆）：`de3bb2bf` 上的全套測試失敗集合**等於基線**。

## 2026-09-25T00:30Z — 延後驗收與委派寫入的對抗審查：成立的 5 條＋既有的 2 條，都修了

**做了什麼**
- 對抗審查 workflow（10 個 agent，兩個鏡頭）：8 條，5 條是 `53a6459f`／`de3bb2bf` 引進的、成立；另 3 條判為既有或低度，
  其中 2 條照樣修。逐條：`ops/accountability/review_defer_credit/FINDINGS.md`。
- 延後驗收：工作階段結束時清掉沒回報的子 agent（`--resume` 之後不會一小時不驗）；延後時作廢這個工作階段上一次的結果
  （信譽不會記成過時的成功）；連續延後最多 3 次（`Recorder.should_defer`）；回合結束只收這個行動者自己的步驟
  （背景子 agent 正在跑的那一步不會被收掉、錯不會變成「不知道」）。
- 委派寫入：只認委派之後才收尾、前後版本都一模一樣的步驟（版本鏈不會被接錯、無辜的後來者不會背「可證明」）。
- 標記：要有 owner 金鑰的簽章、簽的就是事件的內容，才回饋給 agent（任何能寫檔的步驟原本都能偽造一個「你的」標記）。

**證據**：新回歸測試 6 條改之前全紅、改之後全綠；審查者的重現全部轉紅（問題消失），對照組照舊綠。四個 agent 全部重跑
**33/33**；回饋進了模型 22/22、改好後 accept 22/22、回饋裡行動者識別 0/33、鏈 33/33；掛鉤 p95 6.4–12.6 ms（Codex 的 H 一次 59 ms）。

**下一步**：全套測試對基線。之後：可以停下來等人類決定（MORNING 四件事），或做 Codex multi-agent v2。

**偏移檢查**：沒有碰真模型 API；修正都往「不錯怪、不讓驗收被躲掉、不讓 agent 冒充你」收；給 agent 的文字沒有行動者。
- 補記（2026-09-25T00:30Z 那一筆）：`f8f51aae` 上的全套測試失敗集合**等於基線**。
