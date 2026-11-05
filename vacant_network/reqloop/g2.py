    def to_dict(self) -> dict[str, Any]:
        def _total(key: str) -> int | None:
            # P001-20261105-03：任一格的值缺（None）⇒ 總計＝UNKNOWN（None）——
            # 不得把已知部分當完整總和。空清單（無數據可加，完整事實）。
            vals = [c["cost"].get(key) for c in self.cells]
            if not vals:
                return 0
            if all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in vals):
                return int(sum(vals))
            return None

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
                "model_calls": _total("model_calls"),  # 實際模型 API 呼叫數；任一格缺 ⇒ UNKNOWN（不填 0）
                "tokens": _total("tokens"),
                "wall_ms_total": _total("wall_ms_total"),
                "repair_sessions": sum(int(c["cost"].get("calls", 0)) for c in self.cells),
            },
        }