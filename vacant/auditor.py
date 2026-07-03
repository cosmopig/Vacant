"""稽核器 — 確定性再驗（12 §4.3；裁決 B3「抓到的功勞歸確定性 auditor」）。

角色：對交付以機率 p 抽樣稽核，稽核＝在 checks.py 沙箱重跑客觀 check——
不是「再問一次 LLM」，是可執行的環境真值。稽核結論是：
  - X1 記憶通道的寫入源（audited episode 才有資格被 M2 蒸餾）；
  - provable-fault 判定的證據（牙齒 slash 依裁決 B2 後推，事件先記帳）。

抽樣是確定性的（sha256(seed:task_id)），同 seed 同題序完全可重放——
符合 06-30 逐筆 I/O audit 紀律。probation 強制稽核走 forced=True。
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

from .checks import compile_check


@dataclass
class AuditRecord:
    """一筆稽核結果。provable_fault＝交付方宣稱通過、稽核卻 fail（v1 §4.2 牙齒的證據）。"""

    task_id: str
    target_id: str
    ran: bool
    passed: bool | None       # ran=False → None
    provable_fault: bool
    forced: bool              # probation / demo audit_rate=1.0 的強制稽核
    ts_ms: int

    def to_json(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "target_id": self.target_id,
            "ran": self.ran,
            "passed": self.passed,
            "provable_fault": self.provable_fault,
            "forced": self.forced,
            "ts_ms": self.ts_ms,
        }


class Auditor:
    """機率 p 抽樣 ＋ checks.py 沙箱執行。全確定性、可重放。"""

    def __init__(self, rate: float = 0.2, *, seed: str = "audit-v1") -> None:
        if not 0.0 <= rate <= 1.0:
            raise ValueError(f"audit rate 必須在 [0,1]：{rate}")
        self.rate = rate
        self.seed = seed

    def should_audit(self, task_id: str, *, forced: bool = False) -> bool:
        """確定性抽樣：sha256(seed:task_id) 映到 [0,1) 與 rate 比。

        不用 random：同 (seed, task_id) 永遠同結果 → 斷點續跑/重放時抽樣一致。"""
        if forced:
            return True
        if self.rate >= 1.0:
            return True
        if self.rate <= 0.0:
            return False
        h = hashlib.sha256(f"{self.seed}:{task_id}".encode()).digest()
        u = int.from_bytes(h[:8], "big") / 2**64
        return u < self.rate

    def audit(
        self,
        *,
        task_id: str,
        target_id: str,
        answer: str,
        check: dict,
        claimed_pass: bool,
        ts_ms: int,
        forced: bool = False,
    ) -> AuditRecord:
        """抽中（或強制）→ 沙箱重跑 check。claimed_pass＝交付方/互審宣稱的結論。

        provable fault ＝ 宣稱通過但稽核 fail（危險錯誤：誤放行）。
        沒抽中 → ran=False 的空記錄（稽核狀態要如實進信任狀，不可省——12 §2 風險欄）。"""
        if not self.should_audit(task_id, forced=forced):
            return AuditRecord(task_id, target_id, False, None, False, forced, ts_ms)
        verifier = compile_check(check)
        passed = bool(verifier(answer))
        return AuditRecord(
            task_id=task_id,
            target_id=target_id,
            ran=True,
            passed=passed,
            provable_fault=(claimed_pass and not passed),
            forced=forced,
            ts_ms=ts_ms,
        )
