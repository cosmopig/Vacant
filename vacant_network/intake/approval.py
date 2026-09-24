"""approval — **綁定內容的批准**，以及驗證者簽的**裁決文件**。

這支在架構裡承重什麼（報告 §11「批准要有 task ID、artifact hash、目標資源、action、
到期與 replay 防護」；§16「核准 A 後替換為 B 應被拒絕；舊收據重播……不得默默變成通過」）：

兩種簽過的文件，都由 `keys.sign_doc` 簽、由收件端依自己的 `trust.json` 驗：

- **裁決** `vacant-decision/1`（verifier 簽）：這份契約 × 這份成果 × 這組逐項結果 ⇒ 這個結論。
- **批准** `vacant-approval/1`（approver 簽）：我批准把**這個雜湊**的成果，
  以**這個動作**送到**這個目的端**，在**這個時間之前**，**只能用一次**（nonce）。

驗證是 fail-closed：缺任何一個欄位、任何一個綁定對不上 ⇒ 列出問題、不放行。

## 誠實邊界

批准證明的是「持有那把 approver 私鑰的人同意了這個具體版本」，不是「這個版本是好的」
——好不好由裁決負責，兩件事分開簽、分開驗，缺一不可。
"""
from __future__ import annotations

import secrets
import time
from typing import Any

from ..identity import Identity
from .keys import Trust, sign_doc, verify_doc

DECISION_SCHEMA = "vacant-decision/1"
LOCK_SCHEMA = "vacant-contract-lock/1"
APPROVAL_SCHEMA = "vacant-approval/1"
DEFAULT_APPROVAL_TTL_S = 24 * 3600.0


def sign_decision(ident: Identity, *, task_id: str, contract_sha256: str,
                  artifact_sha256: str, outcome: str, results_sha256: str,
                  coverage: dict[str, int]) -> dict[str, Any]:
    return sign_doc(ident, {
        "schema": DECISION_SCHEMA, "task_id": task_id, "contract_sha256": contract_sha256,
        "artifact_sha256": artifact_sha256, "outcome": outcome,
        "results_sha256": results_sha256, "coverage": coverage,
        "issued_at": time.time()})


def check_decision(doc: Any, *, trust: Trust, task_id: str, contract_sha256: str,
                   artifact_sha256: str) -> list[str]:
    who, why = verify_doc(doc, trust=trust, role="verifier")
    if who is None:
        return [f"decision: {why}"]
    p = doc["payload"]
    probs = []
    if p.get("schema") != DECISION_SCHEMA:
        probs.append("decision: wrong schema")
    if p.get("task_id") != task_id:
        probs.append("decision: issued for another task")
    if p.get("contract_sha256") != contract_sha256:
        probs.append("decision: issued under another contract version (re-verify)")
    if p.get("artifact_sha256") != artifact_sha256:
        probs.append("decision: issued for another artifact")
    if p.get("outcome") != "accept":
        probs.append(f"decision: outcome is {p.get('outcome')!r}, not accept")
    return probs


def sign_lock(ident: Identity, *, task_id: str, contract_sha256: str,
              release: dict[str, Any]) -> dict[str, Any]:
    """**需求權威的簽名**：owner 說「這個任務的需求與放行政策就是這個契約雜湊」。

    沒有這一張，收件端就只能相信呼叫者手上碰巧拿著的那份契約——同一個 task_id、
    放行政策比較鬆的第二份契約檔就能把版本送進委託者的目的端（2026-09-24 對抗審查重現）。
    """
    return sign_doc(ident, {
        "schema": LOCK_SCHEMA, "task_id": task_id, "contract_sha256": contract_sha256,
        "release": {k: release.get(k) for k in ("destination", "requires_approval",
                                                 "approvers", "replace")},
        "locked_at": time.time()})


def check_lock(doc: Any, *, trust: Trust, task_id: str, contract_sha256: str) -> list[str]:
    if doc is None:
        return ["contract: this contract version was never locked by a trusted owner "
                "(the owner runs `vacant contract lock`)"]
    who, why = verify_doc(doc, trust=trust, role="owner")
    if who is None:
        return [f"contract lock: {why}"]
    p = doc["payload"]
    probs = []
    if p.get("schema") != LOCK_SCHEMA:
        probs.append("contract lock: wrong schema")
    if p.get("task_id") != task_id:
        probs.append("contract lock: issued for another task")
    if p.get("contract_sha256") != contract_sha256:
        probs.append("contract lock: issued for another contract version")
    return probs


def issue(ident: Identity, *, approver: str, task_id: str, contract_sha256: str,
          artifact_sha256: str, destination: str, action: str = "release",
          ttl_s: float = DEFAULT_APPROVAL_TTL_S, now: float | None = None) -> dict[str, Any]:
    t = time.time() if now is None else now
    return sign_doc(ident, {
        "schema": APPROVAL_SCHEMA, "approver": approver, "task_id": task_id,
        "contract_sha256": contract_sha256, "artifact_sha256": artifact_sha256,
        "destination": destination, "action": action,
        "nonce": secrets.token_hex(16), "issued_at": t, "expires_at": t + ttl_s})


def check(doc: Any, *, trust: Trust, task_id: str, contract_sha256: str,
          artifact_sha256: str, destination: str, allowed: list[str],
          used_nonces: set[str], action: str = "release",
          now: float | None = None) -> list[str]:
    who, why = verify_doc(doc, trust=trust, role="approver")
    if who is None:
        return [f"approval: {why}"]
    p = doc["payload"]
    t = time.time() if now is None else now
    probs = []
    if p.get("schema") != APPROVAL_SCHEMA:
        probs.append("approval: wrong schema")
    if allowed and who not in allowed:
        probs.append(f"approval: {who} is not one of the contract's approvers {allowed}")
    for key, want in (("task_id", task_id), ("contract_sha256", contract_sha256),
                      ("artifact_sha256", artifact_sha256), ("destination", destination),
                      ("action", action)):
        if p.get(key) != want:
            probs.append(f"approval: {key} does not match (approved {str(p.get(key))[:24]!r}, "
                         f"releasing {str(want)[:24]!r})")
    if not isinstance(p.get("expires_at"), (int, float)) or t > float(p["expires_at"]):
        probs.append("approval: expired")
    if p.get("nonce") in used_nonces:
        probs.append("approval: already used (replay)")
    return probs
