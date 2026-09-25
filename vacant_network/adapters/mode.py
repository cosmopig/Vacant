"""零設定的開關：裝了 Vacant 之後，沒有契約的專案也記錄每一步、在 agent 說做完時查一次。

這支在架構裡承重什麼：產品原則「裝一次、照常用、零設定」（CLAUDE.md〈產品原則〉、
`decisions/DECISION_20260925_ZERO_CONFIG_DESIGN.md` §五）。使用者不需要設定任何東西——
`vacant install` 在 `install.json` 寫下 `mode: evidence`，掛鉤從這裡讀。

決定順序：
1. `VACANT_TRACE=0` ⇒ `off`（歸檔 run 與既有測試靠它關掉記錄）。
2. `VACANT_MODE` 環境變數（`off`／`observe`／`evidence`）——**只給測試用**；評測的 C 組不准設
   （產品原則 3：評測量的必須是使用者真的會得到的設定）。
3. `install.json` 存在 ⇒ 它的 `mode`；舊版沒有這個欄位 ⇒ `evidence`（人裝過，就是要它有作用）。
4. 都沒有（沒跑過 `vacant install`：`vacant do` 每一跑臨時注入的掛鉤、端到端測試）⇒ `off`，
   行為和以前完全一樣。

`observe`＝照樣記錄、照樣寫交件說明，但不把任何文字送回 agent。

誠實邊界：讀不到 `install.json`（權限、壞掉的 JSON）⇒ 當成 `evidence`，因為檔案存在代表人裝過；
這一次的檢查若因此出錯，由掛鉤的「失敗一律放行」接住。
"""
from __future__ import annotations

import json
import os

MODES = ("off", "observe", "evidence")


def current_mode() -> str:
    if os.environ.get("VACANT_TRACE", "").strip() == "0":
        return "off"
    env = os.environ.get("VACANT_MODE", "").strip().lower()
    if env in MODES:
        return env
    from .install import state_root
    p = state_root() / "install.json"
    if not p.is_file():
        return "off"
    try:
        m = json.loads(p.read_text(encoding="utf-8")).get("mode")
    except (OSError, ValueError, AttributeError):
        return "evidence"
    return m if m in MODES else "evidence"
