## 2026-11-03 · 主軸 4 · e014 DABStep blocking level 全盤（26 題）ACB 完賽成效與成本判定＋L005 裁決

**規格與來源**：78 格（26 題 × A/C/CB、DABStep、agent=pi、1800 s/格、C/CB 臂 vacant_sha=7c304639）；來源 `/srv/vlab/runs/e014_dabstep_block`；官方重評分 0 不一致。

**成效**：A 13/26（50.00%）、C 14/26（53.85%）、CB 14/26（53.85%）；配對 CB vs C: CB_only=0, C_only=0, McNemar p=1.0, Holm p=1.0；A vs C: A_only=1 (題 17), C_only=2 (題 12, 16); A vs CB: A_only=1, CB_only=2。

**成本**：每成功呼叫數 A 69.23 vs C 40.43 vs CB 36.14（CB/A=0.522×, CB/C=0.894×）；每成功 token 數 A 1,835,838 vs C 1,035,576 vs CB 918,975（CB/A=0.501×, CB/C=0.887×）；逾時 A 1 / C 1 / CB 0。

**機制審計**：CB 臂 12 次 continue 均在 round ≤ 2 被放行（rounds_used ≤ 2），0 次 hold，0 次 refusal；agent 高度依從 kickback 提示。

**裁決**：H1 被否定（CB=C=14/26，增量為 0；落入分支 1/4 之間裁決區）；邊界確認（H-2 同構：查交件存在不保證內容正確）；L005 結案。

**口徑**：可說——在 DABStep 任務上，Vacant 對答案正確性無可測效應（McNemar p=1.0、低力），C/CB 臂成本顯著低於 A 臂；不可說——不能斷言「Vacant 有效/無效」（單模型單 harness 單題組、H-12 類邊界）；機制偵測命中但停在記錄層，不阻擋交付（見 AGENTS.md §1）。
