# D2′ 計畫檔附註（更正事實；不改預註冊本文的判準）

計畫檔一旦開跑就不再改（改了 sha 會變、續跑會被擋）。以下是 2026-11-25 獨立稽核之後的事實更正，**判準一字不動**。

## main_d2_qwen9b_1003.json、main_d2_gemma12b_1003.json、main_d2_gemma12b_1004.json
- `prereg.known_limits` 第 6 條寫「只有本機 1003（1004 離線）」：寫計畫時 1004 已經恢復，12B 有一半就跑在 1004（見 `prereg.models_and_strata`，那一段是對的）。
- 計畫 commit（d9d2c707b）到第一通模型呼叫只隔約 4 秒，當時沒有先推遠端、沒有外部時間戳；推上 `origin/auto/redo` 是開跑之後。之後的批次（sens2、留出、Haiku 以後的）執行器會先檢查 HEAD 已在遠端才開跑，並在 RUN.json 記 HEAD 與各腳本 sha。
- 12B@1003 那一半由等候腳本在 9B 結束後發射，載入的是當時最新的執行器（判準與提示和計畫 commit 時相同，已用程式比對舊教材的四種提示逐字不變；多記的只有 RUN.json 的 HEAD／腳本 sha 與存取紀錄的臂與週期）。

## main_d2_haiku.json
- 從 9B 計畫複製時，`prereg.common` 仍寫「agent＝pi＋掛 `vacant install --agents pi --mode observe`」：實際是 **Claude Code**（`claude -p`，claude-haiku-5-5）＋`vacant install --agents claude --mode observe` 真的寫出的掛鉤（`model` 與 `agentcfg` 欄是對的）。
- `prereg.cost_metric`（主要成本量＝美元）是**看過 Haiku 小量試（s57）之後**才定的；這一點結論檔要寫明。

## 開跑後改過的分析／評分程式（結論檔逐一列出）
| commit | 檔 | 改了什麼 | 會不會改變主批次數字 |
|---|---|---|---|
| a4ecc7749 | score_d2.py | manifest 沒有 `cycles` 時週期類型當 F | 不會（真實 manifest 都有） |
| 8a395e133 | audit_d2.py | 同上（週期數） | 不會 |
| 31bc3d13b | score_d2.py、analyze_d2.py | Claude 的輸入 token 含快取讀寫、加 `cost_usd`；`--cost-metric` | pi 的數字不變（沒有快取欄位） |
| b4d47b4d2、747f2ce33 | run_d2.py、source_server.py | 留出教材、b2／d2／c_every／d_diff、RUN.json 記 HEAD、存取紀錄帶臂與週期 | 已開跑的批次載入的是舊版；12B@1003 載入新版（見上） |
| daaafa7fe | audit_d2.py | 獨立稽核第 1–3 點的修正（歸因、出處、驗鏈） | 不改分數；改歸因表與出處表 |
| efacf883f | report_d2.py | 開跑後新增的報告產生器 | 只產生報告 |
