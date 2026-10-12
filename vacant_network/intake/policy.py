"""policy — **把逐項結果映射成下一步**：accept／reject／hold／escalate。

這支在架構裡承重什麼（報告 §08「建議基本規則」、§12「多維評判，不是一個裝成科學的總分」）：

驗證器只回答「這一條成不成立」；**能不能收**由這裡決定，而且規則寫死、可重算：

1. 任何一條**必要**主張 FAIL ⇒ `reject`。品質分數再高也不能抵銷（沒有加權平均）。
2. 否則任何一條必要主張 CONFLICT ⇒ `escalate`（或契約設 `conflict_policy=reject`）。
3. 否則任何一條必要主張 UNKNOWN ⇒ `hold`（或 `unknown_policy=reject`）。
   **查不到不是不存在，尚未測得不是失敗——更不是成功**（報告 §02）。
4. 全部必要主張 PASS ⇒ `accept`。

另外兩條在映射之前先套用：

- **完整性**：契約裡的必要主張若沒有結果（驗證器沒跑到），補一筆 UNKNOWN。
  分母是契約，不是回報（與 `vrun/acceptance.py` 的 P0 修法同一條）。
- **事實權威不收不獨立的證據**：`authority="fact"` 而 `evidence.independent` 不為真
  （證據是 agent 自己交的檔案）⇒ PASS 降成 UNKNOWN。需求可以由委託者定義，
  事實不行；agent 也不能用自己寫的資料證明事實。

非必要主張（`required=false`）照樣記錄在 `dimensions` 裡，不影響結果——
那是給人看的品質維度，不是閘門。

## 誠實邊界

`accept` 的意思是「在這份契約、這些驗證器能觀測的範圍內，沒有發現不合格」，
不是「任務做得好」。`coverage` 欄位把「可判定的必要主張／全部必要主張」一起報出來，
全部拒絕也能得到零錯誤接受——所以好成果被錯退的比例要另外量（報告 §16）。
"""
from __future__ import annotations

import dataclasses
import hashlib
from typing import Any

from ..canonical import canonical_bytes
from .contract import Contract
from .verifiers import ClaimResult

OUTCOMES = ("accept", "reject", "hold", "escalate")

#: `hidden=true` 的主張在任何 agent 讀得到的輸出裡只說結論（check／submit 的輸出、
#: 裁決理由、帳本）。⚠ 契約本身在 agent 的工作區裡是讀得到的——真正要保密的期望值
#: 放在工作區外面的釘住輸入（例如 `command` 讀的評測資料），`hidden` 只管不在輸出裡洩漏。
HIDDEN_DETAIL = "(hidden claim: details are withheld from the deliverable's author)"


def redact_hidden(results: list[dict[str, Any]], contract: Contract) -> list[dict[str, Any]]:
    hidden = {c.id for c in contract.claims if c.hidden}
    return [({**r, "detail": HIDDEN_DETAIL, "evidence": {}}
             if r.get("claim_id", r.get("id")) in hidden else r) for r in results]


@dataclasses.dataclass
class Decision:
    outcome: str
    reasons: list[str]
    results: list[ClaimResult]
    coverage: dict[str, int]
    contract_sha256: str
    artifact_sha256: str

    def to_json(self, contract: Contract | None = None) -> dict[str, Any]:
        """給 `contract` ⇒ 隱藏主張的細節被遮掉（agent 讀得到的輸出一律這樣呼叫）。"""
        rows = [r.to_json() for r in self.results]
        return {"outcome": self.outcome, "reasons": self.reasons,
                "coverage": self.coverage, "contract_sha256": self.contract_sha256,
                "artifact_sha256": self.artifact_sha256,
                "results": redact_hidden(rows, contract) if contract is not None else rows,
                "results_sha256": results_digest(self.results)}


def results_digest(results: list[ClaimResult]) -> str:
    """判準相關欄位的雜湊（不含說明文字），簽進裁決。"""
    rows = [[r.claim_id, r.status, r.verifier, r.verifier_version, r.required,
             r.authority] for r in results]
    return hashlib.sha256(canonical_bytes(rows)).hexdigest()


def _apply_authority(r: ClaimResult) -> ClaimResult:
    if r.authority == "fact" and r.status == "PASS" and r.evidence.get("independent") is not True:
        return dataclasses.replace(
            r, status="UNKNOWN",
            detail=("fact claim passed only on evidence supplied by the deliverable itself; "
                    "an independent source is required (pin it under contract.inputs). "
                    "Original: " + r.detail)[:2000])
    return r


def decide(contract: Contract, results: list[ClaimResult], *,
           artifact_sha256: str) -> Decision:
    by_id = {r.claim_id: r for r in results}
    fixed: list[ClaimResult] = []
    for c in contract.claims:
        r = by_id.get(c.id)
        if r is None:
            r = ClaimResult(claim_id=c.id, status="UNKNOWN",
                            detail="no result was produced for this claim",
                            evidence={}, verifier=c.verifier, verifier_version="-",
                            required=c.required, authority=c.authority)
        fixed.append(_apply_authority(r))
    req = [r for r in fixed if r.required]
    hidden = {c.id for c in contract.claims if c.hidden}

    def why(r: ClaimResult) -> str:
        return HIDDEN_DETAIL if r.claim_id in hidden else r.detail

    reasons: list[str] = []
    fails = [r for r in req if r.status == "FAIL"]
    confl = [r for r in req if r.status == "CONFLICT"]
    unk = [r for r in req if r.status == "UNKNOWN"]
    if fails:
        outcome = "reject"
        reasons = [f"{r.claim_id}: FAIL — {why(r)}" for r in fails]
    elif confl:
        outcome = "escalate" if contract.conflict_policy == "escalate" else "reject"
        reasons = [f"{r.claim_id}: CONFLICT — {why(r)}" for r in confl]
    elif unk:
        outcome = "hold" if contract.unknown_policy == "hold" else "reject"
        reasons = [f"{r.claim_id}: UNKNOWN — {why(r)}" for r in unk]
    else:
        outcome = "accept"
        reasons = [f"all {len(req)} required claim(s) PASS"]
    coverage = {"required": len(req),
                "decidable": sum(1 for r in req if r.status in ("PASS", "FAIL")),
                "pass": sum(1 for r in req if r.status == "PASS"),
                "fail": len(fails), "unknown": len(unk), "conflict": len(confl),
                "optional": len(fixed) - len(req)}
    return Decision(outcome=outcome, reasons=reasons, results=fixed, coverage=coverage,
                    contract_sha256=contract.sha256, artifact_sha256=artifact_sha256)
