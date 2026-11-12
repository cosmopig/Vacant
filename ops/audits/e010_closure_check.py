#!/usr/bin/env python3
"""e010 大工作區用量格子結案機械複核與 BACKLOG 對賬（2026-11-11 人類常設定案 2.b）。

背景：
BACKLOG / 決策記錄未結項目（對應 2026-11-11 人類常設定案第 2.b 條與 BACKLOG.md line 96）
目的：落實 2026-11-11 人類常設定案第 2.b 條與 `BACKLOG.md` line 96（`e010_bigwork_pi_AC 大工作區格子`）。建立大工作區格子 e010 結案機械複核工具 `ops/audits/e010_closure_check.py` 與單元測試 `tests/test_e010_closure_check.py`（對齊 `l007_closure_check.py` 架構），對真實完賽產物（`/srv/vlab/runs/e010_bigwork_pi_AC`）、封頂量具 `envelope_compliance.py`、研究封包 `ops/packets/e010_bigwork.md` 及 `BACKLOG.md` 執行可重複核算的正負控制核驗，以機械證據正式結案 BACKLOG 第 96 行待辦。

只讀受測檔，不寫任何共享狀態；0 model calls。
判準（全部必須成立）：
  e010 封包：
    (1) C-r1 `vacant_home_bytes` ≤256MiB 且 <149.5M（≤ 268,435,456 B 且 < 149,500,000 B）；
    (2) `vacant_objects_bytes` == 1062407；
    (3) §5 完賽段落與各項核取方塊皆已勾選 `[x]`；
  BACKLOG.md：
    (4) 「e010_bigwork_pi_AC 大工作區格子」項已勾選 `[x]`；
    (5) 該項含結案註記（round 1482、票 P20261112_0320-1）。

判準數值來源：
- C-r1 cell.json: vacant_home_bytes=1077331, vacant_objects_bytes=1062407
- 封頂線：256MiB (268,435,456 B), 149.5M (149,500,000 B)
- BACKLOG 註記：round 1482、票 P20261112_0320-1
