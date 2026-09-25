"""ledger — **每一個指派任務的終態**，含失敗、作廢、撤回，全部簽進同一條鏈。

這支在架構裡承重什麼（報告 §05「失敗與作廢不能離開可稽核範圍」、§16 必報指標）：

舊版 `vrun/launcher.py::_persist` 遇到 `infra_void` 就**不落簽章鏈**（連同已經簽過的
嘗試一起丟掉），驗章器列舉 run 目錄時那一跑就從分母消失。產品看起來越嚴格，
結果可能只是少收了困難案例。

這裡的規則：**任何事件都上鏈**。作廢是一種型別化的事件（`infra_void`），明示
「這不構成成功證據」，而不是讓整條歷史缺席。`report()` 對每一個開過的任務給一個終態，
分母＝開過的任務數。

一條鏈一個任務：`$VACANT_HOME/intake/ledger/<task_id>.ndjson`，由本機 `verifier`
金鑰簽（`vacant_network/logbook.py` 的 Ed25519 雜湊鏈，格式不變）。

## 終態（`TERMINAL_STATES`）

| 狀態 | 意思 |
|---|---|
| `open` | 開了任務，還沒有任何裁決 |
| `void` | 最後一件事是基礎設施失敗（不是成果的錯，也不是成功） |
| `rejected` / `held` / `escalated` | 最新候選版本的裁決 |
| `accepted` | 裁決接受，**尚未**放行到任何目的端 |
| `released` | 已經放行，目的端讀回成立 |
| `release_unconfirmed` | 放行動作做了，讀回不成立（外部狀態不明，先查不要重做） |
| `withdrawn` | 放行後撤回（讀回確認已不在目的端） |
| `unreadable` | 帳本檔讀不了（損壞、被截到一半）——**仍然算在分母裡** |

目的端的狀態與「最新候選版本」的狀態分開追：放行之後又交了一個被退的版本，目的端上
**仍然是**放行的那一版 ⇒ 狀態仍是 `released`，另外標 `newer_candidate`；契約改版之後
舊契約放行的版本還在目的端 ⇒ `live_under_previous_contract`。

## 誠實邊界

1. 鏈能證明「這把鑰匙簽過這些事件、事後沒被改」，**不能**證明「沒有整條鏈被藏起來」。
   高保證用途要由收件端保存每個任務的鏈頭（`recipients.py` 在放行紀錄裡存 `ledger_head`）。
2. 裁決只對**當時的契約雜湊**有效：契約改了，舊的 accept 不能拿來放行新契約。
"""
from __future__ import annotations

import pathlib
import time
from typing import Any

from ..atomic import file_lock
from ..identity import Identity, PublicIdentity
from ..logbook import Logbook
from . import home as _home
from .keys import Trust, ensure_local, load_or_create, pub_hex

LEDGER_SCHEMA = "vacant-ledger/1"

EVENT_TYPES = frozenset({
    "task_opened",         # 契約雜湊（契約改了會再記一次）
    "contract_locked",     # owner 簽的契約鎖（需求權威）
    "attempt_started",     # 哪個 adapter／agent、argv 雜湊、姿態
    "attempt_ended",       # rc、逾時、牆鐘、是否逃出工作區
    "candidate_frozen",    # 候選成果雜湊、檔案數、來源
    "decision",            # 裁決（含逐項結果雜湊與簽過的裁決文件）
    "review_recorded",     # 人工審查（簽過的審查文件）
    "approval_recorded",   # 放行批准（簽過的批准文件）
    "released",            # 目的端、讀回結果
    "release_refused",     # 放行被拒的理由
    "withdrawn",           # 撤回
    "infra_void",          # 基礎設施失敗：哪一段、錯誤
    "hook_event",          # agent 生命週期事件摘要（觀測，不是裁決）
    "trace_head",          # 可究責追緝的病歷鏈頭＋筆數（收件端會簽，截短看得出來；K3）
    "trace_broken",        # 回合邊界發現病歷驗不過（截短／被換）：記下來，之後的驗證一直看得到
    "trace_error",         # 追緝壞了（不影響裁決）
})

TERMINAL_STATES = ("open", "void", "rejected", "held", "escalated", "accepted",
                   "released", "release_unconfirmed", "withdrawn", "unreadable")

_OUTCOME_STATE = {"accept": "accepted", "reject": "rejected", "hold": "held",
                  "escalate": "escalated"}


def ledger_dir(root: pathlib.Path | None = None) -> pathlib.Path:
    return (root or _home()) / "ledger"


class LedgerError(RuntimeError):
    """帳本檔讀不了。清楚地失敗，不要讓呼叫端拿到一個 JSON 解析錯。"""


class Ledger:
    def __init__(self, task_id: str, root: pathlib.Path | None = None,
                 ident: Identity | None = None):
        self.task_id = task_id
        self.root = root or _home()
        self.path = ledger_dir(self.root) / f"{task_id}.ndjson"
        self._ident = ident

    @property
    def ident(self) -> Identity:
        if self._ident is None:
            ensure_local(self.root)
            self._ident = load_or_create("verifier", self.root)
        return self._ident

    def load(self) -> Logbook:
        try:
            return Logbook.load(self.path)
        except (ValueError, KeyError, TypeError) as e:
            raise LedgerError(f"task ledger {self.path} is unreadable ({e}); `vacant task "
                              f"report` lists it as unreadable — inspect or move it aside") \
                from e

    def append(self, etype: str, payload: dict[str, Any]) -> dict[str, Any]:
        if etype not in EVENT_TYPES:
            raise ValueError(f"unknown ledger event {etype!r}")
        body = {"schema": LEDGER_SCHEMA, "task_id": self.task_id, **payload}
        with file_lock(self.path.with_suffix(".lock")):
            book = self.load()
            if not book.entries:
                genesis = {"schema": LEDGER_SCHEMA, "task_id": self.task_id,
                           "signer": pub_hex(self.ident)}
                book.append("ledger_genesis", genesis, self.ident,
                            ts_ms=int(time.time() * 1000))
            e = book.append(etype, body, self.ident, ts_ms=int(time.time() * 1000))
            book.save(self.path)
            return {"seq": e.seq, "hash": e.hash(), "head": book.head()}

    def head(self) -> str:
        return self.load().head()

    def hashes(self) -> list[str]:
        """每一筆的雜湊，依 seq。收件端用它確認帳本沒有被截短或換掉（見 recipients）。"""
        return [e.hash() for e in self.load().entries]

    def events(self) -> list[dict[str, Any]]:
        return [{"seq": e.seq, "type": e.type, "ts_ms": e.ts_ms, **(e.payload or {})}
                for e in self.load().entries]

    def verify(self, trust: Trust) -> tuple[bool, str]:
        """鏈完整 **且** 簽署者在收件端的簽章者清單上。"""
        try:
            book = self.load()
        except LedgerError as e:
            return False, str(e)
        if not book.entries:
            return False, "empty ledger"
        signer = (book.entries[0].payload or {}).get("signer")
        name = trust.name_of("verifier", str(signer))
        if name is None:
            return False, "ledger signer is not a trusted verifier"
        if not book.verify_chain(PublicIdentity.from_hex(name, str(signer))):
            return False, "chain does not verify (edited, reordered or re-signed)"
        return True, f"{len(book)} entries signed by {name}"


def state_of(events: list[dict[str, Any]]) -> dict[str, Any]:
    """由事件序列推出任務狀態。候選版本的狀態只看最新契約雜湊之後的事件；
    **目的端上活著的那一版**另外追，不被之後的候選裁決蓋掉。"""
    st: dict[str, Any] = {"task_id": events[0].get("task_id") if events else None,
                          "contract_sha256": None, "state": "open",
                          "latest_artifact": None, "latest_outcome": None,
                          "attempts": 0, "void": 0, "decisions": 0, "released": [],
                          "last_event": events[-1]["type"] if events else None}
    live: dict[str, Any] | None = None
    live_seq = -1
    last_decision_seq = -1
    for ev in events:
        t = ev["type"]
        if t == "task_opened":
            # 契約換了 ⇒ 之前的裁決不適用，候選狀態回到 open（計數保留，分母不縮）
            if ev.get("contract_sha256") != st["contract_sha256"]:
                st.update(contract_sha256=ev.get("contract_sha256"), state="open",
                          latest_artifact=None, latest_outcome=None)
            continue
        if t == "attempt_started":
            st["attempts"] += 1
        if t == "withdrawn":
            if ev.get("noop"):
                continue
            if ev.get("readback_ok", True):
                live = None
                st["state"] = "withdrawn"
            else:
                st["state"] = "release_unconfirmed"
            continue
        if ev.get("contract_sha256") not in (None, st["contract_sha256"]):
            continue
        if t == "decision":
            st["decisions"] += 1
            st["latest_artifact"] = ev.get("artifact_sha256")
            st["latest_outcome"] = ev.get("outcome")
            st["state"] = _OUTCOME_STATE.get(str(ev.get("outcome")), "open")
            last_decision_seq = int(ev.get("seq", 0))
        elif t == "infra_void":
            st["void"] += 1
            st["state"] = "void"
            last_decision_seq = int(ev.get("seq", 0))
        elif t == "released":
            st["released"].append({"artifact_sha256": ev.get("artifact_sha256"),
                                   "destination": ev.get("destination")})
            ok = bool(ev.get("readback_ok"))
            st["state"] = "released" if ok else "release_unconfirmed"
            live = {"artifact_sha256": ev.get("artifact_sha256"),
                    "destination": ev.get("destination"),
                    "contract_sha256": ev.get("contract_sha256"), "readback_ok": ok}
            live_seq = int(ev.get("seq", 0))
    if live is not None and st["state"] not in ("released", "release_unconfirmed"):
        if live.get("contract_sha256") == st["contract_sha256"]:
            if last_decision_seq > live_seq:
                st["newer_candidate"] = {"artifact_sha256": st["latest_artifact"],
                                         "state": st["state"]}
            st["state"] = "released" if live["readback_ok"] else "release_unconfirmed"
        else:
            st["live_under_previous_contract"] = live
    st["destination_live"] = live
    return st


def report(root: pathlib.Path | None = None, trust: Trust | None = None) -> dict[str, Any]:
    """每個開過的任務一列＋分母。**作廢與未決都在分母裡。**"""
    d = ledger_dir(root)
    rows: list[dict[str, Any]] = []
    for p in sorted(d.glob("*.ndjson")) if d.is_dir() else []:
        led = Ledger(p.stem, root)
        try:
            evs = led.events()
        except LedgerError as e:
            # 一個壞掉的帳本不可以讓整份報表消失——它自己算一列，留在分母裡
            rows.append({"task_id": p.stem, "state": "unreadable", "attempts": 0,
                         "decisions": 0, "void": 0, "ledger_ok": False,
                         "ledger_note": str(e)[:300]})
            continue
        st = state_of(evs)
        if trust is not None:
            ok, why = led.verify(trust)
            st["ledger_ok"], st["ledger_note"] = ok, why
        rows.append(st)
    counts: dict[str, int] = {s: 0 for s in TERMINAL_STATES}
    for r in rows:
        counts[str(r["state"])] = counts.get(str(r["state"]), 0) + 1
    n = len(rows)
    return {"tasks": rows, "n_tasks": n, "by_state": counts,
            "accepted_or_released": counts["accepted"] + counts["released"],
            "destination_live": sum(1 for r in rows if r.get("destination_live")),
            "note": ("denominator = every task that was opened, including void, held and "
                     "never-decided ones")}
