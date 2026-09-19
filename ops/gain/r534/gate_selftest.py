#!/usr/bin/env python3
"""這支在架構裡承重什麼：**閘門的量具**——零模型呼叫，證明閘門真的會擋。

R534 的整個主張壓在一件事上：「宣告完成那一刻，有沒有人先跑一次可見驗收。」
如果那個閘門其實沒在擋（判準寫反、回饋走錯路、拒交那條路永遠到不了），
四格照樣會跑完、照樣會產出一批數字，而那批數字說的不是我們以為的那件事。

所以在燒任何機時之前，先用一個**假的 agent**（就是這支）把閘門的每一條路徑
走一遍。它不叫模型，它直接對 `sidecar.CellSidecar` 說「我宣告完成了」，
然後檢查 sidecar 回的 action 對不對。

題目是**合成的**（temp 目錄裡一個 `f() == 42` 的小題），刻意不用真題庫：
這支量的是**機制**，不是模型解不解得出 LCB。用真題會讓量具的紅綠取決於
那一題的細節，而那正是量具最不該有的性質。

六條（每一條都是一個會讓 R534 作廢的失敗方式）：

  G1  `vacant`：工作區沒動 ⇒ nudge（額度內），額度用完 ⇒ `nudge_exhausted`
  G2  `vacant`：解是錯的 ⇒ `feedback`，而且回饋裡**不得出現隱藏測資的任何字樣**
  G3  `vacant`：解是對的 ⇒ `visible_pass`、`accepted=True`
  G4  `vacant`：一直錯到閘門輪用完 ⇒ `gate_exhausted`、`accepted=False`、`refused=True`
  G5  `plain`：宣告完成就收 ⇒ `declared_done`、`accepted=True`，
       **而且錯的解也照收**（結構性恆真——這正是四格要量的那個差）
  G6  收據：`ws_attempt`／`ws_verdict` 都簽出來了，而且
       `Logbook.verify_chain(pub)` 為真

⚠ 誠實邊界：這支證明的是「**閘門的判斷邏輯**在這些情境下回對了 action」。
  它**不**證明 pi 那一側真的會照著做——那條由 `run_r534.py` 的真跑與
  `pi_ext.jsonl` 的逐筆紀錄承接。兩件事分開量，不要拿這一支的綠當成那一件的綠。
"""
from __future__ import annotations

import json
import os
import pathlib
import shutil
import socket
import sys
import tempfile
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from ops.gain.r530.openwork_arms import prepare_workspace  # noqa: E402
from ops.gain.r530.sandbox import make_sandbox  # noqa: E402
from ops.gain.r534 import piarms  # noqa: E402
from ops.gain.r534.sidecar import CellSidecar  # noqa: E402
from vacant_network.identity import Identity, PublicIdentity  # noqa: E402
from vacant_network.logbook import Logbook  # noqa: E402

CONTRACT = """# Contract

Write your answer in `solution.py` at the root of this workspace.

- Define a top-level function named `f`. It takes no arguments and returns 42.
"""

GOAL = "Write a function f() that returns the integer 42.\n"

VISIBLE_TEST = '''\
import solution


def check_f_returns_42():
    got = solution.f()
    assert got == 42, "args=() got=%r want=42" % (got,)
'''

GOOD = "def f():\n    return 42\n"
BAD = "def f():\n    return 41\n"


def _make_template(root: pathlib.Path) -> pathlib.Path:
    tpl = root / "template"
    (tpl / "tests_visible").mkdir(parents=True)
    (tpl / "goal.md").write_text(GOAL, encoding="utf-8")
    (tpl / "contract.md").write_text(CONTRACT, encoding="utf-8")
    (tpl / "tests_visible" / "test_visible.py").write_text(VISIBLE_TEST,
                                                           encoding="utf-8")
    return tpl


class FakeAgent:
    """假 agent：直接對 sidecar 講話，不經過 pi、不叫模型。"""

    def __init__(self, sock_path: str) -> None:
        self.sock_path = sock_path

    def ask(self, req: dict) -> dict:
        c = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        c.settimeout(300)
        c.connect(self.sock_path)
        c.sendall(json.dumps(req, ensure_ascii=False).encode("utf-8") + b"\n")
        buf = b""
        while b"\n" not in buf:
            chunk = c.recv(1 << 16)
            if not chunk:
                break
            buf += chunk
        c.close()
        return json.loads(buf.partition(b"\n")[0].decode("utf-8"))


def _cell(root: pathlib.Path, tpl: pathlib.Path, sandbox, *, arm: str,
          name: str) -> tuple[CellSidecar, FakeAgent, pathlib.Path, Logbook,
                              Identity]:
    ws = root / f"ws_{name}"
    start = prepare_workspace(tpl, ws, git_init=False, world_writable=False)
    book, ident = Logbook(), Identity.generate()
    sc = CellSidecar(
        sock_path=str(root / f"{name}.sock"), cell=("A1" if arm == "vacant"
                                                    else "B1"),
        arm=arm, policy="revise", task_id="selftest", workspace=ws,
        visible_dir=tpl / "tests_visible", verify_root=root / f"v_{name}",
        sandbox=sandbox, book=book, ident=ident, book_lock=threading.Lock(),
        calls_path=root / f"calls_{name}.jsonl",
        ws_start_sha256=start["ws_sha256"], attempt=1, t0=time.time())
    sc.start()
    return sc, FakeAgent(sc.sock_path), ws, book, ident


def main() -> int:
    root = pathlib.Path(tempfile.mkdtemp(prefix="r534_gate_"))
    results: list[dict] = []

    def rec(gid: str, ok: bool, **detail) -> None:
        results.append({"id": gid, "ok": bool(ok), **detail})

    try:
        sandbox, meta = make_sandbox("auto", workdir=str(root / "sbprobe"))
        tpl = _make_template(root)

        # ── G1 / G2 / G3：vacant 的三條路 ────────────────────────────
        sc, ag, ws, book, ident = _cell(root, tpl, sandbox, arm="vacant",
                                        name="v1")
        r1 = ag.ask({"op": "settled"})
        r2 = ag.ask({"op": "settled"})
        r3 = ag.ask({"op": "settled"})     # 額度 2 用完
        rec("G1_nudge", r1.get("action") == "nudge"
            and r2.get("action") == "nudge"
            and r3.get("action") == "stop"
            and r3.get("stop_reason") == "nudge_exhausted"
            and r3.get("accepted") is False,
            actions=[r1.get("action"), r2.get("action"), r3.get("action")],
            stop=r3.get("stop_reason"), accepted=r3.get("accepted"))
        sc.stop()

        sc, ag, ws, book, ident = _cell(root, tpl, sandbox, arm="vacant",
                                        name="v2")
        (ws / "solution.py").write_text(BAD, encoding="utf-8")
        rb = ag.ask({"op": "settled"})
        msg = str(rb.get("message") or "")
        leak = any(w in msg.lower() for w in ("hidden", "rubric", "test_hidden"))
        rec("G2_feedback", rb.get("action") == "feedback" and not leak
            and "got=41" in msg,
            action=rb.get("action"), leak=leak,
            message_head=msg[:200])

        (ws / "solution.py").write_text(GOOD, encoding="utf-8")
        rg = ag.ask({"op": "settled"})
        rec("G3_pass", rg.get("action") == "stop"
            and rg.get("stop_reason") == "visible_pass"
            and rg.get("accepted") is True,
            stop=rg.get("stop_reason"), accepted=rg.get("accepted"))
        ag.ask({"op": "final"})
        good_book, good_ident = book, ident
        good_state = dict(sc.state)
        sc.stop()

        # ── G4：一直錯到閘門輪用完 ⇒ 拒交 ────────────────────────────
        sc, ag, ws, book, ident = _cell(root, tpl, sandbox, arm="vacant",
                                        name="v3")
        (ws / "solution.py").write_text(BAD, encoding="utf-8")
        seen = []
        for _ in range(int(piarms.R534_BUDGET["max_gate_rounds"]) + 1):
            r = ag.ask({"op": "settled"})
            seen.append(r.get("action"))
            if r.get("action") == "stop":
                break
        rec("G4_refuse", seen[-1] == "stop" and r.get("stop_reason") == "gate_exhausted"
            and r.get("accepted") is False and sc.state["refused"] is True
            and sc.state["gate_rounds"] == int(piarms.R534_BUDGET["max_gate_rounds"]),
            actions=seen, stop=r.get("stop_reason"),
            gate_rounds=sc.state["gate_rounds"], refused=sc.state["refused"])
        sc.stop()

        # ── G5：plain 連錯的解也照收（結構性恆真）──────────────────────
        sc, ag, ws, book, ident = _cell(root, tpl, sandbox, arm="plain",
                                        name="p1")
        (ws / "solution.py").write_text(BAD, encoding="utf-8")
        rp = ag.ask({"op": "settled"})
        rec("G5_plain_accepts_wrong",
            rp.get("action") == "stop"
            and rp.get("stop_reason") == "declared_done"
            and rp.get("accepted") is True
            and sc.state["gate_rounds"] == 0
            and sc.state["visible_pass"] is None,
            stop=rp.get("stop_reason"), accepted=rp.get("accepted"),
            gate_rounds=sc.state["gate_rounds"],
            note="plain 的 accepted 結構性恆真——這是結構差不是量測差")
        sc.stop()

        # ── G6：收據 ────────────────────────────────────────────────
        who = PublicIdentity(vacant_id=good_ident.vacant_id,
                             pub=good_ident.pub)
        etypes = [e.type for e in good_book.entries]
        verified = good_book.verify_chain(who)
        rec("G6_receipts",
            "ws_attempt" in etypes and "ws_verdict" in etypes
            and verified is True and good_state["verdict_hash"] is not None,
            etypes=etypes, n=len(etypes), chain_verified=verified,
            honest_bound=("這條鏈能說的是事後沒被改過，不是由某個已知的人簽的"
                          "——身份是一次性的匿名身份，私鑰不落盤"))

        ok = all(r["ok"] for r in results)
        print(json.dumps({"ok": ok, "sandbox": meta.get("backend"),
                          "checks": results}, ensure_ascii=False, indent=2))
        for r in results:
            print(f"{'OK  ' if r['ok'] else 'FAIL'}  {r['id']}")
        print("GATE SELFTEST " + ("OK" if ok else "FAILED"))
        return 0 if ok else 1
    finally:
        shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
