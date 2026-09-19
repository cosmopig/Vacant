"""可攜的簽章通過憑證（attestation）—— 讓「已驗證」離開 vacant 仍可被獨立核對。

問題：`SolveResult.verified` 只是個 bool，留在本地、沒人能驗，等於沒有對外的究責力。
attestation 是一張 Ed25519 簽章小票：

    「答案 X（雜湊）在 T 時通過了檢查 C，由身分 K 產生」

任何人拿到票即可獨立驗證，**不必信任送方**：
  1) vacant_id 必須能由票上的 pub 重算（擋「換一把 pub 冒名」）；
  2) 簽章必須覆蓋整個 claim（擋竄改 verified / answer_sha / check…）；
  3)（可選）把實際答案餵進來，雜湊要對得上（擋「換答案、留好票」）。

誠實邊界（§10）：這在 *key custody 假設下* 是 prevents；私鑰外洩則退化為 detects。
"""

from __future__ import annotations

import hashlib
from typing import Any

from . import crypto
from .canonical import canonical_bytes
from .identity import Identity

ATTEST_VERSION = 1
_CLAIM_FIELDS = ("v", "vacant_id", "pub", "prompt_sha256", "answer_sha256",
                 "check", "verified", "ts_ms")


def _sha(s: str) -> str:
    return hashlib.sha256((s or "").encode("utf-8")).hexdigest()


def make_attestation(identity: Identity, *, prompt: str, answer: str, check: str,
                     verified: bool, ts_ms: int) -> dict[str, Any]:
    """產出一張簽章 attestation（dict，JSON-able，可隨答案一起傳）。"""
    claim = {
        "v": ATTEST_VERSION,
        "vacant_id": identity.vacant_id,
        "pub": crypto.pub_to_hex(identity.pub),
        "prompt_sha256": _sha(prompt),
        "answer_sha256": _sha(answer),
        "check": str(check),
        "verified": bool(verified),
        "ts_ms": int(ts_ms),
    }
    sig = identity.sign(canonical_bytes(claim)).hex()
    return {**claim, "sig": sig}


def verify_attestation(att: dict, *, answer: str | None = None) -> bool:
    """獨立驗票。answer 給定時，額外要求答案雜湊對得上。"""
    if not isinstance(att, dict):
        return False
    try:
        sig = bytes.fromhex(att["sig"])
        pub = crypto.pub_from_hex(att["pub"])
        claim = {k: att[k] for k in _CLAIM_FIELDS}
    except (KeyError, ValueError, TypeError):
        return False
    # 1) vacant_id 必須真的由這把 pub 重算而來
    if crypto.vacant_id_from_pubkey(pub) != att["vacant_id"]:
        return False
    # 2) 簽章覆蓋整個 claim
    if not crypto.verify(pub, canonical_bytes(claim), sig):
        return False
    # 3) 可選：實際答案要對得上雜湊
    if answer is not None and _sha(answer) != att["answer_sha256"]:
        return False
    return True
