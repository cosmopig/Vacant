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
   agent 的工具碰 `$VACANT_HOME` 與設定的外部金鑰路徑，但那是 agent 自己的工具那條路，不是保證
   （`DECISION_20260920_AGENT_HOOKS_MEASURED.md` §三：agent 拆得掉自己的 hook）。
3. `VACANT_SIGNING_KEY_PATH`／`VACANT_KEYS_DIR`／`$VACANT_HOME/intake/config.json` 可把
   `verifier`（或各角色）簽署金鑰移出工作區與 `$VACANT_HOME` 之外，並檢查 0600／0700 權限與
   是否可被目前 OS 使用者讀取；但只要 agent 與簽署行程仍在**同一個 OS 帳號**下執行，該帳號
   仍可讀取私鑰。真正的作業系統層隔離需要**另一組系統帳號＋簽署輔助行程（signing helper）**
   ——目前尚未實作，相關警告會由 `signing_key_posture()`／`vacant trace verify`／`vacant dashboard`
   明確呈現。
"""
from __future__ import annotations

import json
import os
import pathlib
import stat
from typing import Any

from .. import crypto
from ..atomic import atomic_write_bytes, atomic_write_text
from ..canonical import canonical_bytes
from ..identity import Identity, PublicIdentity
from . import home as _home
from .statepaths import state_dir

ROLES = ("verifier", "approver", "reviewer", "owner")
SIGNING_KEY_PATH_ENV = "VACANT_SIGNING_KEY_PATH"
KEYS_DIR_ENV = "VACANT_KEYS_DIR"
CONFIG_NAME = "config.json"


def _read_config(root: pathlib.Path | None = None) -> dict[str, Any]:
    """讀取 `$VACANT_HOME/intake/config.json`（唯讀、fail-open）。"""
    p = (root or _home()) / CONFIG_NAME
    if not p.is_file():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _is_default_root(root: pathlib.Path | None) -> bool:
    if root is None:
        return True
    try:
        return pathlib.Path(root).resolve() == _home().resolve()
    except OSError:
        return False


def _resolve_key_file(raw: str) -> pathlib.Path:
    """把使用者設定的路徑正規化為私鑰檔路徑：若是既有目錄或以路徑分隔符結尾，補上 `identity.key`。"""
    p = pathlib.Path(raw).expanduser()
    if raw.endswith(("/", os.sep)) or (p.exists() and p.is_dir()):
        return p / "identity.key"
    return p


def _key_location(role: str, root: pathlib.Path | None = None) -> tuple[pathlib.Path, str]:
    """回傳 `(私鑰檔路徑, 來源標記)`。

    優先順序（僅在預設 root 套用環境變數覆寫；測試傳入顯式獨立 root 時維持隔離）：
    1. `VACANT_SIGNING_KEY_PATH`（僅 `verifier` 角色）
    2. `VACANT_KEYS_DIR`（所有角色：`<dir>/<role>/identity.key`）
    3. `<root>/config.json` 的 `signing_key_path`（`verifier`）或 `keys_dir`（所有角色）
    4. 預設：`<root>/keys/<role>/identity.key`（`$VACANT_HOME/intake/keys/<role>/identity.key`）
    """
    if role not in ROLES:
        raise ValueError(f"unknown role {role!r}")
    r = root or _home()
    if _is_default_root(root):
        env_kp = os.environ.get(SIGNING_KEY_PATH_ENV, "").strip()
        if role == "verifier" and env_kp:
            return _resolve_key_file(env_kp), f"env:{SIGNING_KEY_PATH_ENV}"
        env_kd = os.environ.get(KEYS_DIR_ENV, "").strip()
        if env_kd:
            return pathlib.Path(env_kd).expanduser() / role / "identity.key", f"env:{KEYS_DIR_ENV}"
    cfg = _read_config(r)
    cfg_kp = str(cfg.get("signing_key_path") or "").strip()
    if role == "verifier" and cfg_kp:
        return _resolve_key_file(cfg_kp), "config:signing_key_path"
    cfg_kd = str(cfg.get("keys_dir") or "").strip()
    if cfg_kd:
        return pathlib.Path(cfg_kd).expanduser() / role / "identity.key", "config:keys_dir"
    return r / "keys" / role / "identity.key", "default"


def signing_key_path(role: str = "verifier", root: pathlib.Path | None = None) -> pathlib.Path:
    """指定角色的簽署私鑰檔路徑（尊重 `VACANT_SIGNING_KEY_PATH`／`VACANT_KEYS_DIR`／`config.json`）。"""
    return _key_location(role, root)[0]


def key_dir(role: str, root: pathlib.Path | None = None) -> pathlib.Path:
    return signing_key_path(role, root).parent


def _load_identity_at(key_file: pathlib.Path) -> Identity:
    if key_file.name == "identity.key":
        return Identity.load(key_file.parent)
    sk = crypto.priv_from_pem(key_file.read_bytes())
    pub = sk.public_key()
    return Identity(vacant_id=crypto.vacant_id_from_pubkey(pub), _sk=sk, _pub=pub)


def _save_identity_at(ident: Identity, key_file: pathlib.Path) -> None:
    if key_file.name == "identity.key":
        ident.save(key_file.parent)
        return
    key_file.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        os.chmod(key_file.parent, 0o700)
    except OSError:
        pass
    atomic_write_bytes(key_file, crypto.priv_to_pem(ident._sk))
    os.chmod(key_file, 0o600)


def _path_under(child: pathlib.Path, parent: pathlib.Path) -> bool:
    try:
        c = child.resolve()
        p = parent.resolve()
        return c == p or p in c.parents
    except OSError:
        return False


def signing_key_posture(
    role: str = "verifier",
    root: pathlib.Path | None = None,
    *,
    workspace: pathlib.Path | None = None,
) -> dict[str, Any]:
    """唯讀稽核簽署私鑰的位置與權限姿態（絕不建檔／不建目錄）。

    誠實邊界：只要目前行程所屬的 OS 使用者讀得到這把私鑰，同帳號下的 agent 行程就同樣
    讀得到它——`isolated` 必為 False，且 `warnings` 必須直白指出這一點。"""
    kf, source = _key_location(role, root)
    try:
        resolved = kf.resolve()
    except OSError:
        resolved = kf
    exists = resolved.is_file()
    vh = state_dir()
    in_vh = _path_under(resolved, vh)
    in_ws = _path_under(resolved, workspace) if workspace is not None else False
    cur_uid = os.geteuid() if hasattr(os, "geteuid") else -1
    mode_str: str | None = None
    dir_mode_str: str | None = None
    owner_uid: int | None = None
    gw_readable = False
    dir_gw_access = False
    readable_cur = False
    warnings: list[str] = []

    if exists:
        try:
            st = resolved.stat()
            perm = stat.S_IMODE(st.st_mode)
            mode_str = f"{perm:04o}"
            owner_uid = st.st_uid
            gw_readable = bool(perm & 0o077)
        except OSError:
            pass
        try:
            dst = resolved.parent.stat()
            dperm = stat.S_IMODE(dst.st_mode)
            dir_mode_str = f"{dperm:04o}"
            dir_gw_access = bool(dperm & 0o077)
        except OSError:
            pass
        try:
            readable_cur = os.access(resolved, os.R_OK)
        except OSError:
            readable_cur = False

        if gw_readable:
            warnings.append(
                f"signing key {resolved} has overly broad permissions ({mode_str}); expected 0600"
            )
        if dir_gw_access:
            warnings.append(
                f"signing key directory {resolved.parent} has overly broad permissions "
                f"({dir_mode_str}); expected 0700"
            )
        if in_ws:
            warnings.append(
                f"signing key {resolved} is inside the workspace — the agent can directly read or modify it"
            )
        if in_vh and readable_cur:
            warnings.append(
                f"signing key {resolved} is under VACANT_HOME (default) and readable by the current "
                f"OS user (uid={cur_uid}); an agent running as the same user can read it and forge "
                f"chain entries. Set {SIGNING_KEY_PATH_ENV} to a path outside VACANT_HOME and the "
                f"workspace (true isolation requires a separate OS account with a signing helper, "
                f"not yet implemented)."
            )
        elif readable_cur:
            warnings.append(
                f"signing key {resolved} is readable by the current OS user (uid={cur_uid}); "
                f"an agent running under the same user can still read it "
                f"(separate-account signing helper is not yet implemented)."
            )

    isolated = bool(
        exists
        and not in_vh
        and not in_ws
        and not gw_readable
        and not dir_gw_access
        and not readable_cur
    )
    return {
        "role": role,
        "path": str(resolved),
        "source": source,
        "exists": exists,
        "in_vacant_home": in_vh,
        "in_workspace": in_ws,
        "mode": mode_str,
        "dir_mode": dir_mode_str,
        "group_or_world_readable": gw_readable,
        "dir_group_or_world_accessible": dir_gw_access,
        "owner_uid": owner_uid,
        "current_uid": cur_uid,
        "readable_by_current_user": readable_cur,
        "isolated": isolated,
        "warnings": warnings,
    }


def _create_unlocked(role: str, root: pathlib.Path | None = None) -> Identity:
    kf = signing_key_path(role, root)
    if kf.is_file():
        return _load_identity_at(kf)
    ident = Identity.generate()
    _save_identity_at(ident, kf)
    return ident


def load_or_create(role: str, root: pathlib.Path | None = None) -> Identity:
    """有就讀；沒有就**在鎖裡**建——兩個行程同時第一次碰到時，第二個讀到第一個建的，
    不會各生一把、互相覆蓋（2026-09-24 對抗審查：150 次裡 80 次留下不受信任的鑰匙）。"""
    from ..atomic import file_lock
    kf = signing_key_path(role, root)
    if kf.is_file():
        return _load_identity_at(kf)
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
    if all(signing_key_path(role, r).is_file() for role in ROLES) \
            and (r / "trust.json").is_file():
        # 若使用外部 VACANT_SIGNING_KEY_PATH，需確保該金鑰已登記在 trust.json
        vkf = signing_key_path("verifier", r)
        t_fast = Trust.load(r / "trust.json")
        if t_fast.name_of("verifier", pub_hex(_load_identity_at(vkf))) is not None:
            return
    with file_lock(r / "keys.lock"):
        t = Trust.load(r / "trust.json")
        if all(signing_key_path(role, r).is_file()
               and (t.name_of(role, pub_hex(_load_identity_at(signing_key_path(role, r))))
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
