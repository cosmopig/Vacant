# Fable 判斷 #1（2026-09-24）：不包模型端點的中介——設計審查

子代理：Agent 工具 `model: "fable"`，一次呼叫，subagent_tokens 39,804（harness 回報）。
問題全文＝本 session 送出的 prompt（摘要：旁路 sidecar＝hook＋transcript＋工作區三源對帳；
問 Q1 主架構、Q2 級別命名與口徑、Q3 PreToolUse fail-closed 的問題、Q4 漏掉的量測）。
以下為 Fable 回覆**逐字**。採納與否見 `decisions/DECISION_20260924_MEDIATION_WITHOUT_MODEL_WRAP.md` §七。

---

## Q1 主架構＝交付物層；旁路三源對帳＝紀錄品質分級，不是可究責的承重

理由只有一條：三源裡兩源（hook 事件、transcript）都是 agent 自己寫的、agent 自己能關的。它們只能證明「一致」，證明不了「完整」。真正 agent 碰不到的只有兩樣：launcher 自己拍的工作區前後樹雜湊，和 collector 記憶體裡的鏈。所以能承重的句子是「退出那一刻，交付物過了使用者給的驗收，且工作區每個改動都能被解釋」，不是「每一步都被紀錄」。

對展場這反而是好事：交付物層天生離線、Windows、秒級、不看通道，「附身任何 agent」自動成立。旁路照做，但定位寫成「紀錄品質」。

**你會說過頭的地方**：「write-ahead：沒紀錄就不准做」——只在 hook 還掛著時成立，正確講法是「hook 在場時 write-ahead」。

## Q2 命名與口徑

不要再用字母。既有 A/B/B′/C 是「通道級」；新的叫「紀錄級」，收據上兩個欄位並列：`channel_tier`（Windows 一律 `unobserved`，不准留空）＋ `record_tier`：
- **R-full**：canary 燒、transcript checkpoint 鏈連續到退出、tool_use id 雙向 1:1、樹差異全數可歸給 Write/Edit
- **R-opaque**：差異只能歸給 Bash（可歸、不可驗）
- **R-broken**：有無法解釋的差異、或 checkpoint 斷
- **R-none**：canary 沒燒／transcript 關閉 ⇒ 拒發收據

最強一句：「這一跑，工作區每個改動都對得上一個**在改動之前就簽進鏈**的工具事件；交付物通過驗收；模型呼叫數 N 為 agent 自報。」

絕不能說：「每通模型呼叫都經過 Vacant」、「agent 不能繞過」、「這個 agent 是 R-full」（級別屬於這一跑）、「模型呼叫 N 次」不帶自報標記、「有掛 hook＝有紀錄」。

## Q3 exit 2 的問題

1. **偽造比卡死嚴重**：collector 是 localhost 開放 port，agent 用 Bash `curl` 就能塞假事件（例如假造一筆 Write 去「解釋」它用 Bash 偷改的檔）。hook 端的 token 藏不住（agent 讀得到檔和環境變數）。防線只能是交叉：假事件在 transcript 沒對應 tool_use id ⇒ R-broken。但 transcript 也能被 append——所以 checkpoint 要含 **tool_use id 集合**，不只 size＋prefix hash，這樣事後追加會露餡。
2. **timeout ≠ 拒絕**：Claude Code hook 逾時是「不阻擋」不是「阻擋」。collector 吊死（不是被殺）會變成安靜放行。hook 要自設短 timeout（<2s）並把逾時當 exit 2。
3. 五個 agent 對非零退出碼語意不同，有的只當警告，逐一實測，別推論。
4. 卡死本身不算問題：collector 死掉 agent 每一步被擋、燒 token 停不下來，這正是 fail-closed，但 launcher 要偵測「連續 N 次拒絕」就殺 agent，別讓它空轉。

## Q4 漏掉的

**最重要的量測：誠實跑的基線。** 先跑十趟不攻擊的正常任務，看多少比例的差異落進「不透明 Bash」。若誠實跑都有一半是 R-opaque，這個級別沒有解析度，展場講不出東西。這格決定整個方案值不值得。

**最重要的攻擊：上面那個本機 port 偽造。** 另補：MCP 工具與 `Task` 子代理是否觸發 PreToolUse（你只寫了 subagent）；`/compact`／`--resume` 會不會改寫 transcript 前綴讓 checkpoint 誤判；Windows 上 hook 實跑（shell、路徑、退出碼）——你列的實測全是 Linux。

真值格的限制要寫進結論：ANTHROPIC_BASE_URL 只在非託管建置有效，量到的「requestId 準不準」只能講「那一版建置」。
