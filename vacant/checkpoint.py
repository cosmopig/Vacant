"""checkpoint — 存檔點認證＋回溯稽核（18 §2 V1；垂直信任 V-B 半邊）。

承重什麼：信任不再只在交付瞬間結算，而是**沿鏈累積**。每 N 筆 episode
（或 wipe 時）對窗口內的交付跑回溯稽核（確定性、本地、離線——不進 delegate
同步路徑，16 §B1），簽發一枚存檔點認證：

    {window:[seq_a,seq_b], entries_hash, chain_head,
     retro_audits:{task_id:passed}, retro_missing:[task_id],
     prev_checkpoint_sig, sig}

- `entries_hash` 把窗口內每一筆 logbook entry 的 hash 滾動串起——**竄改窗口內
  任一 episode → 驗證必失敗**（回溯稽核的「溯及既往」由鏈的累積結構承擔）。
- `prev_checkpoint_sig` 使存檔點**自身成鏈**（斷點可偵測）；一個 Vacant 的
  垂直信任史＝它的存檔點鏈。
- 交付當下信任狀誠實寫「本件未稽核」；事後補稽通過 → 信任狀可驗證地升級
  「存檔點 #k 回溯已驗 ✓」（trustcard.retro_audit 欄位）。
- 「記憶沒了，帳還在」：wipe 前的最後一枚存檔點＋歸檔鏈仍可離線驗證。

誠實邊界（18 §0）：垂直稽核者的評價**錨定在確定性稽核**（checks.py＋隱藏
測資）——錨不能換，換的只是「稽核往哪裡打」；本檔改變的是稽核的**時間
結構**，不是稽核的真值來源。垂直軸的價值 ∝ ground-truth 延遲 × 稽核稀缺。
"""

from __future__ import annotations

import hashlib
from typing import Any

from . import crypto
from .canonical import canonical_bytes
from .checks import compile_check
from .identity import Identity, PublicIdentity
from .logbook import Logbook

CHECKPOINT_VERSION = 1
DEFAULT_WINDOW_EPISODES = 20  # 每 N 筆 episode 簽發一次（vacant.toml 參數位）

_CLAIM_FIELDS = (
    "v", "kind", "vacant_id", "pub", "stream_id", "window", "entries_hash",
    "chain_head", "retro_audits", "retro_missing", "prev_checkpoint_sig", "ts_ms",
)


def entries_hash(entries: list) -> str:
    """窗口內 entry hash 的滾動雜湊（順序敏感）：窗口內容的單一承諾。"""
    h = hashlib.sha256()
    for e in entries:
        h.update(e.hash().encode("ascii"))
    return h.hexdigest()


def retro_audit_window(
    entries: list,
    answers: dict[str, str],
    checks: dict[str, dict],
) -> tuple[dict[str, bool], list[str]]:
    """對窗口內 episode 逐筆重跑確定性稽核（checks.py 沙箱）。

    回 (retro_audits, retro_missing)：缺答案或缺 check 的 episode 如實列入
    missing（「稽核不到」是被斷言的，不是被跳過的——垂直軸的誠實面）。"""
    audits: dict[str, bool] = {}
    missing: list[str] = []
    for e in entries:
        tid = e.payload.get("task_id")
        if not tid:
            continue
        answer, check = answers.get(tid), checks.get(tid)
        if answer is None or check is None:
            missing.append(tid)
            continue
        audits[tid] = bool(compile_check(check)(answer))
    return audits, missing


def issue_checkpoint(
    logbook: Logbook,
    identity: Identity,
    *,
    window: tuple[int, int],
    retro_audits: dict[str, bool],
    retro_missing: list[str],
    prev_checkpoint: dict[str, Any] | None,
    ts_ms: int,
) -> dict[str, Any]:
    """對 [seq_a, seq_b] 窗口簽發存檔點認證（複用 attest.py 的簽章慣例）。"""
    seq_a, seq_b = window
    entries = [e for e in logbook.entries if seq_a <= e.seq <= seq_b]
    claim: dict[str, Any] = {
        "v": CHECKPOINT_VERSION,
        "kind": "checkpoint",
        "vacant_id": identity.vacant_id,
        "pub": crypto.pub_to_hex(identity.pub),
        "stream_id": logbook.stream_id() or "",
        "window": [seq_a, seq_b],
        "entries_hash": entries_hash(entries),
        "chain_head": logbook.head(),
        "retro_audits": {k: bool(v) for k, v in retro_audits.items()},
        "retro_missing": list(retro_missing),
        "prev_checkpoint_sig": (prev_checkpoint or {}).get("sig"),
        "ts_ms": int(ts_ms),
    }
    sig = identity.sign(canonical_bytes(claim)).hex()
    return {**claim, "sig": sig}


def _claim_of(ckpt: dict[str, Any]) -> dict[str, Any]:
    return {k: ckpt[k] for k in _CLAIM_FIELDS}


def verify_checkpoint(
    ckpt: dict[str, Any],
    logbook: Logbook,
    *,
    pub_hex: str | None = None,
) -> tuple[bool, str]:
    """離線驗證一枚存檔點：身份綁定 → 簽章 → 窗口內容承諾 → 鏈頭一致性。

    四關全過才承認「存檔點 #k 回溯已驗」；失敗原因逐條回（驗證要可被執行，
    不是可能性——07-06 紀錄紅線同紀律）。"""
    try:
        sig = bytes.fromhex(ckpt["sig"])
        pub = crypto.pub_from_hex(pub_hex or ckpt["pub"])
    except (KeyError, ValueError, TypeError) as e:
        return False, f"欄位缺損或編碼錯：{e}"
    # ① vacant_id 必須由 pub 重算（擋換 pub 冒名）
    if crypto.vacant_id_from_pubkey(pub) != ckpt.get("vacant_id"):
        return False, "vacant_id 與 pub 不符（冒名）"
    # ② 簽章覆蓋整個 claim（擋竄改窗口／結果）
    if not crypto.verify(pub, canonical_bytes(_claim_of(ckpt)), sig):
        return False, "存檔點簽章驗不過"
    # ③ 窗口內容承諾：entries_hash 重算（竄改窗口內任一 episode 即不符）
    seq_a, seq_b = ckpt["window"]
    entries = [e for e in logbook.entries if seq_a <= e.seq <= seq_b]
    if not entries:
        return False, f"窗口 [{seq_a},{seq_b}] 在鏈上找不到任何 entry"
    if entries_hash(entries) != ckpt["entries_hash"]:
        return False, "entries_hash 不符（窗口內 episode 被竄改或不完整）"
    # ④ 鏈頭一致：窗口末 entry 的 hash 必須等於認證時的 chain_head
    if entries[-1].hash() != ckpt["chain_head"]:
        return False, "chain_head 不符（認證時點的鏈頭被事後改寫）"
    return True, "ok"


def verify_checkpoint_chain(checkpoints: list[dict[str, Any]]) -> tuple[bool, str]:
    """存檔點鏈完整性：每枚的 prev_checkpoint_sig 必須等於前一枚的 sig。

    斷點（缺一枚、順序被調換、頭被拔掉）即失敗——「沿鏈累積」若可抽掉中間
    一段，垂直信任史就不成立。空鏈／單枚視為完整（無環可斷）。"""
    for i in range(1, len(checkpoints)):
        prev, cur = checkpoints[i - 1], checkpoints[i]
        if cur.get("prev_checkpoint_sig") != prev.get("sig"):
            return False, f"存檔點鏈斷在第 {i} 環（prev_checkpoint_sig 不接續）"
    if checkpoints and checkpoints[0].get("prev_checkpoint_sig") is not None:
        return False, "首枚存檔點的 prev_checkpoint_sig 應為 null（鏈頭被嫁接）"
    return True, "ok"


def verify_checkpoint_offline(ckpt: dict[str, Any], logbook: Logbook) -> tuple[bool, str]:
    """給外部複核者的單一入口（pub 取自認證本身＝內部自洽驗證）。"""
    return verify_checkpoint(ckpt, logbook)
