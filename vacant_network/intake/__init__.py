"""intake — **收件口本體**：任務契約 → 隔離區 → 取證 → 裁決 → 放行 → 讀回 → 帳本。

這支在架構裡承重什麼（`decisions/DECISION_20260924_UNIVERSAL_INTAKE.md`）：

2026-09-24 外部質疑報告的核心判斷是「通用性要放在任務契約、證據、驗收與接受／批准
流程上，不是放在模型通道上」。README 早就把 Vacant 改稱「收件口」，但在這個套件之前，
**沒有任何一條程式路徑是收件口**：`vrun/launcher.py` 在 agent 結束後判決，檔案仍留在
agent 的工作區；`vrun/release.py`＋`vrun/publish.py` 是對的形狀，卻沒有被任何產品路徑呼叫。

本套件把那條路接起來，而且**完全不需要看模型流量**：

    Contract（版本固定、雜湊）          contract.py
      ↓
    候選成果 → 隔離區（內容定址）       artifact.py
      ↓
    逐項主張取證 PASS/FAIL/UNKNOWN/CONFLICT   verifiers.py
      ↓
    政策裁決 accept/reject/hold/escalate     policy.py
      ↓
    （需要時）綁定內容的人工批准         approval.py
      ↓
    收件端發布＋讀回                     recipients.py
      ↓
    每一個指派任務的終態（含失敗、作廢）   ledger.py

**誰說了算拆成四種權威**（報告 §08），寫在每一條主張的 `authority` 欄位上：
`requirement`（需求定義者）、`fact`（事實證據來源）、`quality`（品質評審）、
`approval`（批准者）。硬性條件不通過，不能用品質分數抵銷。

## 誠實邊界（改碼請保留）

1. **判決不等於阻止。** 只有經過 `recipients.py` 的那個目的端，才能說「不合格的版本
   沒有進去」。agent 手上若另有寫入正式系統的憑證，那條路不在本套件的保證範圍內。
2. **同一個使用者帳號下的隔離區是「竄改可偵測」，不是「竄改不可能」。** 放行時會重算
   每個物件的雜湊，對不上就拒絕；要做到不可竄改，收件端要跑在另一個帳號／另一台機器
   （`server.py`）。
3. **驗證器只證明它驗了什麼。** `citations_resolve` 通過不代表引文支持結論；
   `text` 通過不代表文章寫得好。每個驗證器的 docstring 寫明它**不能**推出什麼。
4. **模型流量觀測是選配**（`vrun/`），從不決定收件。
"""
from __future__ import annotations

import os
import pathlib

#: 本套件所有落盤狀態的根目錄。`VACANT_HOME` 可覆寫（測試、另一個帳號的收件端）。
def home() -> pathlib.Path:
    base = os.environ.get("VACANT_HOME")
    root = pathlib.Path(base).expanduser() if base else pathlib.Path.home() / ".vacant"
    return root / "intake"


__all__ = ["home"]
