# e014 DABStep blocking level 審計報告

**實驗資訊**：
- 名稱：e014_dabstep_block
- 來源：/srv/vlab/runs/e014_dabstep_block
- 狀態：完賽（2026-11-03）

**配對比較統計結果**：
- A vs C: A_only=1, C_only=2
- CB vs C: CB_only=0, C_only=0
- CB vs A: A_only=1, CB_only=2

**Holm–Bonferroni 數值**：
- McNemar p (CB vs C) = 1.0
- Holm p (CB vs C) = 1.0

**審計結論**：
- 成本顯著降低（C/A=0.894×, CB/A=0.522×）。
- 機制偵測命中但停在記錄層，不阻擋交付。
- H1 被否定（增量為 0），落入分支 1/4 之間裁決區。
- L005 結案。

**重算程式路徑**：N/A (本次任務僅同步數據)
