"""keys — **長期身分＋收件端自己的簽章者清單**。

這支在架構裡承重什麼（報告 §05「收件者還必須以自己的政策決定信任哪些簽署身分，
不能只因產物旁邊附了一把能驗過的公鑰就信任」；§15「簽署金鑰……帳號、憑證、
檔案……要按威脅模型安排」）：

舊版 `vrun/launcher.py` 每一跑產生一把一次性金鑰、驗章器信任鏈旁邊那個 `pub.json`
⇒ 任何人自己造一把鑰匙、自己簽一條鏈，驗章器照樣說 OK（自我認證）。

這裡改成：

- **角色**：`verifier`（簽裁決與帳本）、`approver`（簽放行批准）、`reviewer`（簽人工審查）、
  `owner`（簽**契約**：這份契約雜湊就是這個任務的需求與放行政策——需求權威）。
  每個角色一把長期金鑰，放 `$VACANT_HOME/intake/keys/<role>/`（目錄 0700、私鑰 0600）。
- **簽章者清單** `trust.json`：`{role: {name: pub_hex}}`。收件端只認清單上的公鑰；
  簽章驗得過但不在清單上 ⇒ 不算數。清單屬於**收件端**，可以跟簽章端在不同機器。

## 誠實邊界

1. 同一個 OS 帳號同時持有 verifier 與 approver 的私鑰時，「兩把鑰匙」**不是**兩個信任邊界
   ——拿得到一把就拿得到另一把。本機單人使用是方便模式；要分權，把 approver 的金鑰放在
   另一個帳號／另一台機器，並只把它的公鑰加進收件端的 `trust.json`。
2. agent 跟 Vacant 同一個帳號時，agent 讀得到私鑰檔。`vacant hook` 的預設規則會拒絕
   agent 的工具碰 `$VACANT_HOME`，但那是 agent 自己的工具那條路，不是保證
   （`DECISION_20260920_AGENT_HOOKS_MEASURED.md` §三：agent 拆得掉自己的 hook）。
"""
from __future__ import annotations

import json
import os
import pathlib
from typing import Any

from .. import crypto
from ..atomic import atomic_write_text
from ..canonical import canonical_bytes
from ..identity import Identity, PublicIdentity
from . import home as _home

ROLES = ("verifier", "approver", "reviewer", "owner")


def key_dir(role: str, root: pathlib.Path | None = None) -> pathlib.Path:
    if role not in ROLES:
        raise ValueError(f"unknown role {role!r}")
    return (root or _home()) / "keys" / role


def _create_unlocked(role: str, root: pathlib.Path | None = None) -> Identity:
    d = key_dir(role, root)
    if (d / "identity.key").is_file():
        return Identity.load(d)
    ident = Identity.generate()
    ident.save(d)
    return ident


def load_or_create(role: str, root: pathlib.Path | None = None) -> Identity:
    """有就讀；沒有就**在鎖裡**建——兩個行程同時第一次碰到時，第二個讀到第一個建的，
    不會各生一把、互相覆蓋（2026-09-24 對抗審查：150 次裡 80 次留下不受信任的鑰匙）。"""
    from ..atomic import file_lock
    d = key_dir(role, root)
    if (d / "identity.key").is_file():
        return Identity.load(d)
    with file_lock((root or _home()) / "keys.lock"):
        return _create_unlocked(role, root)


def pub_hex(ident: Identity) -> str:
    return crypto.pub_to_hex(ident.pub)


class Trust:
    """收件端的簽章者清單。檔案不存在 ⇒ 空清單（什麼都不信），不是全信。"""

    def __init__(self, path: pathlib.Path, data: dict[str, dict[str, str]]):
        self.path = path
        self.data = {r: dict(data.get(r) or {}) for r in ROLES}

    @classmethod
    def load(cls, path: pathlib.Path | None = None) -> "Trust":
        p = path or (_home() / "trust.json")
        data: dict[str, Any] = {}
        if p.is_file():
            data = json.loads(p.read_text(encoding="utf-8"))
        return cls(p, data)

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(self.path, json.dumps(self.data, indent=2, sort_keys=True) + "\n")

    def add(self, role: str, name: str, pub: str) -> None:
        if role not in ROLES:
            raise ValueError(f"unknown role {role!r}")
        crypto.pub_from_hex(pub)  # 格式不對就在這裡炸
        self.data[role][name] = pub

    def name_of(self, role: str, pub: str) -> str | None:
        for n, p in self.data.get(role, {}).items():
            if p == pub:
                return n
        return None

    def pub_of(self, role: str, name: str) -> str | None:
        return self.data.get(role, {}).get(name)


def ensure_local(root: pathlib.Path | None = None) -> None:
    """第一次用到簽章時，確保本機三把鑰匙都在**而且**都在簽章者清單上。

    ⚠ 要加鎖：掛鉤、背景交件、CLI 可能同時第一次碰到它。沒鎖的話兩個行程各生一把
      verifier 鑰匙，其中一條帳本的簽署者不在清單上（2026-09-24 端到端實測抓到：
      掛鉤先建了鑰匙卻沒登記，收件端因此拒絕放行——拒絕是對的，建錯是 bug）。
    """
    from ..atomic import file_lock
    r = root or _home()
    if all((key_dir(role, r) / "identity.key").is_file() for role in ROLES) \
            and (r / "trust.json").is_file():
        return
    with file_lock(r / "keys.lock"):
        t = Trust.load(r / "trust.json")
        if all((key_dir(role, r) / "identity.key").is_file()
               and (t.name_of(role, pub_hex(Identity.load(key_dir(role, r))))
                    or (role != "verifier" and t.data.get(role))) for role in ROLES):
            return
        _init_local_unlocked(r)


def init_local(root: pathlib.Path | None = None, *, name: str | None = None) -> dict[str, str]:
    """本機單人模式：每個角色各一把鑰匙，全部加進本機簽章者清單（見誠實邊界 1）。
    跟 `ensure_local` 用同一把鎖（`vacant keys init` 與掛鉤同時跑時不會互相覆蓋）。"""
    from ..atomic import file_lock
    with file_lock((root or _home()) / "keys.lock"):
        return _init_local_unlocked(root, name=name)


def _init_local_unlocked(root: pathlib.Path | None = None, *,
                         name: str | None = None) -> dict[str, str]:
    who = name or os.environ.get("USER") or "local"
    trust = Trust.load((root or _home()) / "trust.json")
    out = {}
    for role in ROLES:
        ident = _create_unlocked(role, root)
        pub = pub_hex(ident)
        existing = trust.name_of(role, pub)
        # 使用者已經為 owner／approver／reviewer 設了**別的**金鑰（另一個帳號、另一台機器）
        # ⇒ 不要再把本機這把自動加進去：否則同一個帳號自己就能鎖契約、批准、審查，
        # 那個分權設定形同虛設（2026-09-24 對抗審查）。verifier 永遠是本機的。
        if role != "verifier" and existing is None and trust.data.get(role):
            out[role] = pub
            continue
        trust.add(role, existing or (who if role != "verifier" else "local"), pub)
        out[role] = pub
    trust.save()
    return out


def sign_doc(ident: Identity, payload: dict[str, Any]) -> dict[str, Any]:
    """`{"payload", "signer", "sig"}`。簽的是 payload 的 canonical bytes。"""
    return {"payload": payload, "signer": pub_hex(ident),
            "sig": ident.sign(canonical_bytes(payload)).hex()}


def verify_doc(doc: Any, *, trust: Trust, role: str) -> tuple[str | None, str]:
    """回 `(簽署者名稱, 問題)`。問題非空 ⇒ 不可採信。"""
    if not isinstance(doc, dict) or not {"payload", "signer", "sig"} <= set(doc):
        return None, "not a signed document"
    name = trust.name_of(role, str(doc["signer"]))
    if name is None:
        return None, f"signer is not a trusted {role} in {trust.path}"
    try:
        who = PublicIdentity.from_hex(name, str(doc["signer"]))
        ok = who.verify(canonical_bytes(doc["payload"]), bytes.fromhex(str(doc["sig"])))
    except (ValueError, TypeError) as e:
        return None, f"bad signature encoding: {e}"
    if not ok:
        return None, "signature does not verify"
    return name, ""
