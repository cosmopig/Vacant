"""rerun — **在重建出來的某一步狀態上重跑一條主張**：追緝的證據是重跑，不是意見。

這支在架構裡承重什麼（`decisions/DECISION_20260924_ACCOUNTABLE_TRACE.md` §4.8 K7）：

`blame.py` 問「第 k 步之前這條主張過不過、之後過不過」。狀態由 `workspace.materialize` 從
內容定址庫重建，這裡用和收件口**同一套**驗證器（`intake/verifiers.run_claim`）、同一份契約、
同一個 include／exclude 選檔規則去跑。只跑驗證器：**不重跑模型、不重跑 agent 的工具步驟**
（有副作用、不冪等）。

## 誠實邊界（改碼請保留）

1. `review` 類主張（人的判斷）重跑不出來 ⇒ 永遠 UNKNOWN；人工審查不會被「重演」。
2. 釘住的輸入從契約所在的**現在的**工作區讀；它被改過（雜湊對不上）⇒ 那條主張 UNKNOWN，
   追緝就不會把它當證據——和收件口同一條規則。
"""
from __future__ import annotations

import pathlib
import shutil
import tempfile
from typing import Any

from ..intake.artifact import collect
from ..intake.verifiers import VerifyContext, run_claim


def manifest_of(contract: Any, state_dir: pathlib.Path) -> dict[str, Any]:
    chosen, skipped = collect(state_dir, contract.include, contract.exclude)
    return {"files": [{"path": rel} for rel, _p in chosen], "skipped": skipped}


def run(contract: Any, state_dir: str | pathlib.Path, claim_ids: list[str] | None = None,
        *, sandbox: str = "auto") -> list[dict[str, Any]]:
    """在 `state_dir` 上跑（部分）主張。回 `ClaimResult.to_json()` 清單（契約順序）。"""
    sd = pathlib.Path(state_dir)
    scratch = pathlib.Path(tempfile.mkdtemp(prefix="vacant-rerun-"))
    try:
        ctx = VerifyContext(contract=contract, artifact_dir=sd, manifest=manifest_of(contract, sd),
                            scratch=scratch, sandbox_name=sandbox)
        return [run_claim(ctx, c).to_json() for c in contract.claims
                if claim_ids is None or c.id in claim_ids]
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


def claim_by_id(contract: Any, claim_id: str) -> Any:
    for c in contract.claims:
        if c.id == claim_id:
            return c
    raise KeyError(claim_id)
