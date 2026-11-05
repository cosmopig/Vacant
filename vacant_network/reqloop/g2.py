from typing import Any

# ... (keep other imports and class definitions)

class G2Result:
    # ... (keep existing attributes/methods)

    def to_dict(self) -> dict[str, Any]:
        def _total_active(key: str) -> int | None:
            # P001-20261105-03：任一格的值缺（None）⇒ 總計＝UNKNOWN（None）——
            # 不得把已知部分當完整總和。空清單（無數據可加，完整事實）。
            active_cells = [c for c in self.cells if int(c["cost"].get("calls") or 0) > 0]
            if not active_cells:
                return None
            
            vals = [c["cost"].get(key) for c in active_cells]
            
            # If any value is missing (None), the total is UNKNOWN (None)
            if any(v is None for v in vals):
                return None
            
            # All values are present. Sum them up. 
            # If all were 0, sum is 0 (complete fact).
            return int(sum(vals))

        return {
            "schema": RESULT_SCHEMA,
            "mode": "run",
            "generated_at": self.generated_at,
            "manifest": {"sha256": self.manifest_sha256},
            "model": self.model,
            "budget": self.budget,
            "scoring": self.scoring,
            "hidden_after": AFTER_HIDDEN_UNKNOWN,   # 全格同一口徑
            "cells": self.cells,
            "totals": {
                "cells": len(self.cells),
                "model_calls": _total_active("model_calls"),  # 實際模型 API 呼叫數；任一格缺 ⇒ UNKNOWN（不填 0）
                "tokens": _total_active("tokens"),
                "wall_ms_total": _total_active("wall_ms_total"),
                "repair_sessions": sum(int(c["cost"].get("calls", 0)) for c in self.cells),
            },
        }
