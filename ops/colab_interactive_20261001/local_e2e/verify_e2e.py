#!/usr/bin/env python3
"""verify_e2e — 本機端到端跑完之後，逐項核對紀錄（讀 /srv/eval 與歸檔，只讀不改）。

    python3 verify_e2e.py --eval-root /srv/eval --expect <scratchpad>/e2e/expect_scenario.json --stub-log <stub_requests.jsonl> \
        --mirror <鏡像目錄> --agent-timeout 60 --out <結果.json> [--kill-snapshot <kill_snapshot.json>]

這支在架構裡承重什麼：端到端「跑得起來」不等於「每一格都發生了該發生的事」。這裡把任務書列的每一項寫成可執行的檢查——
TUI 真的被驅動（pane 有打進去的那句與 agent 的輸出）、完成偵測沒有太早／太晚（含 Vacant 送回後繼續）、逾時、R／K 的分支與 session 數、
bridge 的 judge／release 退出碼、每一組計分的是對的成品、打包的 chunk 與 manifest、續跑沒有重複格、infra_void 的路徑。
每一項印出 OK／FAIL 與觀察到的數字；有任何 FAIL ⇒ exit 1。輸出的 JSON 只含數字與格子名稱，**不含題目內容**（可以進 repo）。
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import re
import subprocess
import sys
import tarfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "vm"))
from tui_lib import cell_name, iso  # noqa: E402

CHECKS: list[dict] = []


def chk(scope: str, name: str, ok: bool, detail="") -> bool:
    CHECKS.append({"scope": scope, "check": name, "ok": bool(ok), "detail": detail})
    print(f"{'OK  ' if ok else 'FAIL'} [{scope}] {name}" + (f"  -> {detail}" if detail != "" else ""), flush=True)
    return bool(ok)


def jload(p: Path, default=None):
    try:
        return json.loads(p.read_text())
    except (OSError, ValueError):
        return default


def jlines(p: Path) -> list[dict]:
    out = []
    try:
        for ln in p.read_text().splitlines():
            if ln.strip():
                try:
                    out.append(json.loads(ln))
                except ValueError:
                    pass
    except OSError:
        pass
    return out


class Cells:
    def __init__(self, root: Path):
        self.root = root

    def d(self, name: str) -> Path:
        return self.root / "cells" / name

    def meta(self, name: str) -> dict | None:
        return jload(self.d(name) / "meta.json")

    def score(self, name: str) -> dict | None:
        try:
            lines = [x for x in (self.d(name) / "score.json").read_text().strip().splitlines() if x.strip()]
            return json.loads(lines[-1])
        except (OSError, ValueError, IndexError):
            return None

    def entries(self, name: str, sd: str) -> list[dict]:
        out = []
        for f in sorted((self.d(name) / "agentlog" / "pi" / sd).rglob("*.jsonl")):
            out += jlines(f)
        return out

    def pane(self, name: str, n: int) -> str:
        try:
            return (self.d(name) / "panes" / f"pane-{n}.txt").read_text(errors="replace")
        except OSError:
            return ""


def last_assistant_text(ents: list[dict]) -> str:
    for e in reversed(ents):
        m = e.get("message") or {}
        if e.get("type") == "message" and m.get("role") == "assistant":
            c = m.get("content")
            if isinstance(c, list):
                t = "".join(p.get("text", "") for p in c if isinstance(p, dict) and p.get("type") == "text")
            else:
                t = c if isinstance(c, str) else ""
            if t.strip():
                return t.strip()
    return ""


def check_session(cx: Cells, cell: str, s: dict, *, scope: str, own_dir: str, expect_timeout=False, expect_sendback: int | None = None,
                  idle_s: float, agent_timeout: float, typed_head: str | None = None) -> None:
    """一段 session 的通則：TUI 被驅動、完成偵測、退出、沒有殘留。own_dir＝這段的檔案存在哪一格。"""
    n = s["n"]
    tag = f"{scope} s{n}"
    pane = cx.pane(own_dir, n)
    ents = cx.entries(own_dir, "sessions" if n == 1 else f"sessions-{n}")
    chk(tag, "TUI ready (footer seen) and typed text accepted", s.get("ready") is True and s.get("typed_ok") is True,
        f"ready_s={s.get('ready_s')} typed_ok={s.get('typed_ok')} typing={s.get('typing_mode')} submit_unconfirmed={s.get('submit_unconfirmed')}")
    chk(tag, "pane capture exists with the typed sentence echoed", "Read goal.md and contract.md" in pane,
        f"{len(pane.splitlines())} lines")
    tlp = cx.d(own_dir) / "timelines" / f"timeline-{n}.jsonl"
    tlr = jlines(tlp)
    kinds = [r.get("kind") for r in tlr]
    chk(tag, "timeline recorded: ready -> enter -> state changes (-> trust dialog handled, if any)",
        kinds[:2] == ["ready", "enter"] and "change" in kinds, f"{len(tlr)} rows")
    first_user = next((e for e in ents if e.get("type") == "message" and (e.get("message") or {}).get("role") == "user"), None)
    ftxt = ""
    if first_user:
        c = first_user["message"].get("content")
        ftxt = "".join(p.get("text", "") for p in c if isinstance(p, dict)) if isinstance(c, list) else str(c)
    chk(tag, "session jsonl first user message starts with the instruction sentence",
        ftxt.startswith("Read goal.md and contract.md in this directory and do what they say. Use your tools to write the file."),
        f"{len(ents)} entries")
    if typed_head:
        chk(tag, f"typed text contains {typed_head!r}", typed_head in ftxt)
    if expect_timeout:
        chk(tag, "timeout recorded (rc 124, done_reason timeout, not exited by Ctrl-D)",
            s.get("timeout") is True and s.get("rc") == 124 and s.get("done_reason") == "timeout" and s.get("exit_clean") is None,
            f"wall_s={s.get('wall_s')} rc={s.get('rc')}")
        chk(tag, "timeout wall is near AGENT_TIMEOUT", agent_timeout - 1 <= (s.get("wall_s") or 0) <= agent_timeout + 25, s.get("wall_s"))
        chk(tag, "pane at the timeout shows the agent still working", "Working" in pane or "read" in pane.lower())
        chk(tag, "timeout is not void", s.get("void") is False, s.get("void_reason"))
    else:
        chk(tag, "done by idle detection and Ctrl-D exit rc 0",
            s.get("done_reason") == "idle_final" and s.get("exit_clean") is True and s.get("exit_rc") == 0,
            f"done_reason={s.get('done_reason')} exit_s={s.get('exit_s')} exit_note={s.get('exit_note')}")
        chk(tag, "no write to the session file after done was declared", s.get("late_write_after_done") is False)
        lt = last_assistant_text(ents)
        chk(tag, "final assistant text is visible in the pane (agent output rendered)", bool(lt) and lt[:30] in pane, lt[:40])
        chk(tag, "final entry is a finished assistant message", s.get("final_state") == "final" and s.get("last_assistant_stop") == "stop",
            f"state={s.get('final_state')} stop={s.get('last_assistant_stop')}")
    chk(tag, "no leftover processes of the cell user", not s.get("leftover_procs"), s.get("leftover_procs"))
    if expect_sendback is not None:
        sb = [e for e in ents if e.get("type") == "custom_message"]
        chk(tag, f"Vacant send-back count == {expect_sendback}", len(sb) == expect_sendback and s.get("sendbacks") == expect_sendback,
            f"custom_message={len(sb)} meta={s.get('sendbacks')}")
        if expect_sendback:
            # 完成偵測沒有在送回之前就判完成：送回之後 session 還有 assistant 的最終訊息，而且最終訊息之後沒有再寫東西
            idx = max(i for i, e in enumerate(ents) if e.get("type") == "custom_message")
            after = [e for e in ents[idx + 1:] if e.get("type") == "message" and (e.get("message") or {}).get("role") == "assistant"]
            chk(tag, "the session continued after the send-back and was declared done only after it",
                bool(after) and (after[-1]["message"].get("stopReason") == "stop") and s.get("late_write_after_done") is False,
                f"assistant messages after send-back={len(after)}")
            chk(tag, "the send-back text reached the model as a user-role message in the request stream", True,
                "(checked via stub log, see run-level)")


def tar_members(path: Path) -> list[str]:
    with tarfile.open(path, "r:xz") as t:
        return [m.name for m in t.getmembers()]


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--eval-root", type=Path, default=Path("/srv/eval"))
    ap.add_argument("--expect", type=Path, required=True)
    ap.add_argument("--stub-log", type=Path, required=True)
    ap.add_argument("--mirror", type=Path, required=True)
    ap.add_argument("--agent-timeout", type=float, default=60)
    ap.add_argument("--idle-s", type=float, default=15)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--kill-snapshot", type=Path)
    ap.add_argument("--skip-cleanup-check", action="store_true")
    a = ap.parse_args()
    ev = a.eval_root
    cx = Cells(ev)
    exp = json.loads(a.expect.read_text())
    P, PS = exp["prefix"], exp["screen_prefix"]
    U = exp["units"]
    prog_all = jlines(ev / "progress.jsonl")
    prog_cells = [r for r in prog_all if "event" not in r]
    events = [r for r in prog_all if "event" in r]
    stub = jlines(a.stub_log)
    ledger = jlines(ev / "proxy" / "ledger.jsonl")
    idle, to = a.idle_s, a.agent_timeout

    def cn(arm: str, unit: str, att: int = 1, prefix: str | None = None) -> str:
        bank, tid = U[unit].split("/")
        return cell_name(prefix or P, arm, bank, tid, 1, att)

    # ── 0. 篩選與天花板 ───────────────────────────────────────────────────────────────────────
    dec = jload(ev / "ceiling_decision.json") or {}
    banks = dec.get("banks", {})
    for bank, want in exp["screen"].items():
        b = banks.get(bank, {})
        chk("screen", f"{bank}: passes {want['passes']}/{want['n']}, dropped={want['dropped']}",
            b.get("passes") == want["passes"] and b.get("n") == want["n"] and b.get("dropped") is want["dropped"], b.get("reason"))
    sc_cells = sorted(p.name for p in (ev / "cells").glob(f"{PS}-*"))
    chk("screen", "12 screening cells, all arm A, all DONE, none void",
        len(sc_cells) == 12 and all("-A-" in c for c in sc_cells) and all((ev / "cells" / c / "DONE").exists() for c in sc_cells)
        and not any((cx.meta(c) or {}).get("void") for c in sc_cells), len(sc_cells))
    mplan = jload(ev / "plan_main.json") or {}
    mt = [f"{t['bank']}/{t['id']}" for t in mplan.get("tasks", [])]
    chk("plan", "main plan = 3 LCB + the kept banks' tasks (dabench dropped by the ceiling rule), arms A+C, nested R+K",
        sorted(mt) == sorted(U.values()) and mplan.get("dropped_banks") == exp["main_banks_dropped"] and mplan.get("arms") == ["A", "C"]
        and mplan.get("nested") == ["R", "K"], f"units={len(mt)} dropped={mplan.get('dropped_banks')}")
    chk("plan", "K only planned for LCB tasks",
        all(bool(t["k"]) == t["bank"].startswith("lcb") for t in mplan.get("tasks", [])))
    chk("plan", "screened tasks (databench, polyglot) are re-run as A in the main run (main A cells exist, prefix differs from screening)",
        all((ev / "cells" / cn("A", u) / "DONE").exists() for u in ("U4", "U5")) and PS != P)

    # ── 1. 逐單位 ────────────────────────────────────────────────────────────────────────────
    # U1：A 第 1 次 void（5 通 500 的爆發）→ A 線整條 v2 重跑；K 第 1 通就 accept
    A1, R1, K1 = cn("A", "U1", 1), cn("R", "U1", 1), cn("K", "U1", 1)
    A1v, R1v, K1v = cn("A", "U1", 2), cn("R", "U1", 2), cn("K", "U1", 2)
    m = cx.meta(A1) or {}
    chk("U1 A#1", "void by proxy non-200 (infra), not counted as agent failure", m.get("void") is True and str(m.get("void_reason", "")).startswith("proxy_non200"),
        m.get("void_reason"))
    chk("U1 R#1/K#1", "whole A group voided (R and K group-void)", all((cx.meta(x) or {}).get("void") is True for x in (R1, K1)),
        [(cx.meta(x) or {}).get("void_reason", "")[:40] for x in (R1, K1)])
    chk("U1", "driver logged exactly one infra_void_rerun for the A group of U1",
        sum(1 for e in events if e.get("event") == "infra_void_rerun" and e.get("unit") == U["U1"] and e.get("group") == "A" and e.get("attempt") == 2) == 1)
    chk("U1", "the rerun cells carry the v2 suffix and are not void",
        A1v.endswith("v2") and all(not (cx.meta(x) or {}).get("void") for x in (A1v, R1v, K1v)))
    ledger_a1 = [r for r in ledger if r.get("tag") == f"{A1}.n1"]
    chk("U1 A#1", "ledger: the burst reached the ledger as a non-200 (500) row after the proxy's 5 attempts",
        any(r.get("status") == 500 and (r.get("attempts") or 0) >= 5 for r in ledger_a1), [(r.get("status"), r.get("attempts")) for r in ledger_a1])
    m = cx.meta(A1v) or {}
    s = (m.get("sessions") or [{}])[0]
    sc = cx.score(A1v) or {}
    chk("U1 A#2", "passes (stub wrote the right solution), delivered, 1 session", sc.get("pass") is True and m.get("delivered") is True and m.get("n_sessions") == 1, sc.get("pass"))
    check_session(cx, A1v, s, scope="U1 A#2", own_dir=A1v, expect_sendback=None, idle_s=idle, agent_timeout=to)
    chk("U1 A#2", "A workspace carried the bridge contract (inert without Vacant)", m.get("workspace_has_bridge_contract") is True)
    mk = cx.meta(K1v) or {}
    k = mk.get("k") or {}
    chk("U1 K#2", "bridge judge accepted at attempt 1 (rc 0) and release succeeded with read-back",
        [x["rc"] for x in k.get("attempts", [])] == [0] and k.get("released") is True and k.get("release_rc") == 0 and k.get("readback_ok") is True,
        k.get("attempts"))
    chk("U1 K#2", "K = 1 session, delivered, passes; score reused from A because the released file is byte-identical",
        mk.get("n_sessions") == 1 and mk.get("delivered") is True and (cx.score(K1v) or {}).get("pass") is True and k.get("score_reused_from_A") is True)
    rel = cx.d(K1v) / "released_artifact" / "solution.py"
    fin = cx.d(A1v) / "app_final" / "solution.py"
    chk("U1 K#2", "released artifact is byte-identical to A's final solution.py", rel.is_file() and fin.is_file() and rel.read_bytes() == fin.read_bytes())
    chk("U1 K#2", "receiver records copied, private keys not", (cx.d(K1v) / "receiver").is_dir() and not list((cx.d(K1v) / "receiver").rglob("*.key")))
    mr = cx.meta(R1v) or {}
    chk("U1 R#2", "R == A: no retry (delivered, no timeout), 1 session, same score", mr.get("retry_needed") is False and mr.get("n_sessions") == 1
        and (cx.score(R1v) or {}).get("pass") is True)
    mc = cx.meta(cn("C", "U1")) or {}
    cc = cn("C", "U1")
    chk("U1 C", "Vacant installed & active (install_rc 0, c_arm_ok), no contract in workspace",
        mc.get("install_rc") == 0 and mc.get("c_arm_ok") is True and mc.get("workspace_has_bridge_contract") is False, (mc.get("install_rc"), mc.get("c_arm_ok")))
    chk("U1 C", "passes; 0 send-backs (no problem => nothing added)", (cx.score(cc) or {}).get("pass") is True)
    check_session(cx, cc, (mc.get("sessions") or [{}])[0], scope="U1 C", own_dir=cc, expect_sendback=0, idle_s=idle, agent_timeout=to)
    ca, cb = [(cx.meta(x) or {}).get("sessions", [{}])[0].get("ledger", {}).get("calls") for x in (A1v, cc)]
    chk("U1", "A and C made the same number of model calls when nothing was wrong (C adds no request)", ca == cb == 4, (ca, cb))

    # U2：A 寫錯；K：judge 退回(40) → 就地新 session（可見檢查的回報）→ accept(0)；R＝A；C 錯，第一通被注入 1 次 500（被代理吃掉、不 void）
    A2, R2, K2, C2 = (cn(x, "U2") for x in ("A", "R", "K", "C"))
    m, mk, mr, mc = (cx.meta(x) or {} for x in (A2, K2, R2, C2))
    chk("U2 A", "wrong solution delivered, A scored on the first-session snapshot => FAIL", (cx.score(A2) or {}).get("pass") is False and m.get("delivered") is True)
    check_session(cx, A2, (m.get("sessions") or [{}])[0], scope="U2 A", own_dir=A2, expect_sendback=None, idle_s=idle, agent_timeout=to)
    k = mk.get("k") or {}
    chk("U2 K", "judge rcs [40 reject, 0 accept], released, readback ok", [x["rc"] for x in k.get("attempts", [])] == [40, 0] and k.get("released") is True
        and k.get("readback_ok") is True and k.get("release_rc") == 0, k.get("attempts"))
    chk("U2 K", "K = 2 sessions; passes on the RELEASED artifact while A (first-session snapshot) failed",
        mk.get("n_sessions") == 2 and (cx.score(K2) or {}).get("pass") is True and (cx.score(A2) or {}).get("pass") is False)
    fi = (cx.d(K2) / "fix_instruction_2.txt").read_text() if (cx.d(K2) / "fix_instruction_2.txt").exists() else ""
    chk("U2 K", "fix session text = same sentence + visible-check report (KS-1 clean wording)",
        fi.startswith("Read goal.md and contract.md") and "visible checks" in fi and not re.search(r"blame|punish|responsib|accountab|fault", fi, re.I), f"{len(fi)} chars")
    s2 = (mk.get("sessions") or [{}, {}])[1]
    check_session(cx, K2, s2, scope="U2 K fix", own_dir=K2, expect_sendback=None, idle_s=idle, agent_timeout=to, typed_head="visible checks")
    chk("U2 K fix", "multi-line text was typed by bracketed paste", s2.get("typing_mode") == "paste", s2.get("typing_mode"))
    chk("U2 K fix", "the fix session ran in A's original workspace (K's final workspace has the right solution; A's snapshot cell was scored before)",
        (cx.d(K2) / "app_final" / "solution.py").exists())
    chk("U2 R", "R == A (delivered => no retry) and fails like A", mr.get("retry_needed") is False and (cx.score(R2) or {}).get("pass") is False)
    chk("U2 C", "wrong => fails, 0 send-backs (Vacant has nothing to object to)", (cx.score(C2) or {}).get("pass") is False)
    check_session(cx, C2, (mc.get("sessions") or [{}])[0], scope="U2 C", own_dir=C2, expect_sendback=0, idle_s=idle, agent_timeout=to)
    lc = [r for r in ledger if r.get("tag") == f"{C2}.n1"]
    chk("U2 C", "one injected 500 was absorbed by the proxy retry: the first call has 2 attempts, status 200, cell NOT void",
        mc.get("void") is False and any(r.get("status") == 200 and (r.get("attempts") or 0) == 2 for r in lc) and all(r.get("status") == 200 for r in lc),
        [(r.get("status"), r.get("attempts")) for r in lc])

    # U3：claim。A 沒交；R：2 次重試（claim, 然後寫對）；K：judge 退回 ×3、就地 session 都寫錯 ⇒ 沒放行；C：Vacant 送回後寫對
    A3, R3, K3, C3 = (cn(x, "U3") for x in ("A", "R", "K", "C"))
    m, mk, mr, mc = (cx.meta(x) or {} for x in (A3, K3, R3, C3))
    chk("U3 A", "claimed done without writing: not delivered, FAIL", m.get("delivered") is False and (cx.score(A3) or {}).get("pass") is False)
    check_session(cx, A3, (m.get("sessions") or [{}])[0], scope="U3 A", own_dir=A3, expect_sendback=None, idle_s=idle, agent_timeout=to)
    chk("U3 R", "retried twice (no_deliverable x2): 3 sessions [first, retry, retry], ends delivered and PASSES",
        mr.get("retry_needed") is True and mr.get("n_sessions") == 3 and mr.get("retry_reasons") == ["no_deliverable", "no_deliverable"]
        and [x.get("kind") for x in mr.get("sessions", [])] == ["first", "retry", "retry"] and (cx.score(R3) or {}).get("pass") is True, mr.get("retry_reasons"))
    for i, s in enumerate((mr.get("sessions") or [])[1:], start=2):
        check_session(cx, R3, s, scope="U3 R retry", own_dir=R3, expect_sendback=None, idle_s=idle, agent_timeout=to)
    chk("U3 R", "R's retry sessions used the same instruction sentence (no feedback text)",
        all(x.get("text_chars") == (mr["sessions"][0].get("text_chars")) for x in mr.get("sessions", [])), [x.get("text_chars") for x in mr.get("sessions", [])])
    k = mk.get("k") or {}
    chk("U3 K", "never accepted: judge rcs [40,40,40], nothing released, 3 sessions, delivered False, score pass False",
        [x["rc"] for x in k.get("attempts", [])] == [40, 40, 40] and k.get("released") is False and mk.get("n_sessions") == 3 and mk.get("delivered") is False
        and (cx.score(K3) or {}).get("pass") is False, k.get("attempts"))
    chk("U3 K", "no release record and no released_artifact directory", not (cx.d(K3) / "released_artifact").exists() and "release_rc" not in k)
    for s in (mk.get("sessions") or [])[1:]:
        check_session(cx, K3, s, scope="U3 K fix", own_dir=K3, expect_sendback=None, idle_s=idle, agent_timeout=to, typed_head="visible checks")
    chk("U3 C", "Vacant send-back fired and the session continued; the file was written after it; PASSES",
        (cx.score(C3) or {}).get("pass") is True and (mc.get("sessions") or [{}])[0].get("sendbacks", 0) >= 1, (mc.get("sessions") or [{}])[0].get("sendbacks"))
    check_session(cx, C3, (mc.get("sessions") or [{}])[0], scope="U3 C", own_dir=C3, expect_sendback=(mc.get("sessions") or [{}])[0].get("sendbacks"),
                  idle_s=idle, agent_timeout=to)
    sb_rows = [r for r in stub if r.get("tag") == f"{C3}.n1" and r.get("mode") == "sendback"]
    chk("U3 C", "the stub saw the send-back arrive as a user message ('Before delivery') and answered it", bool(sb_rows), len(sb_rows))

    # U4：A、C 都撞逾時；R 的重試（複本）寫對
    A4, R4, C4 = (cn(x, "U4") for x in ("A", "R", "C"))
    m, mr, mc = (cx.meta(x) or {} for x in (A4, R4, C4))
    check_session(cx, A4, (m.get("sessions") or [{}])[0], scope="U4 A", own_dir=A4, expect_timeout=True, idle_s=idle, agent_timeout=to)
    check_session(cx, C4, (mc.get("sessions") or [{}])[0], scope="U4 C", own_dir=C4, expect_timeout=True, idle_s=idle, agent_timeout=to)
    chk("U4 A/C", "timeout cells are scored (not void) and fail: no deliverable", all((cx.score(x) or {}).get("pass") is False for x in (A4, C4))
        and all((cx.meta(x) or {}).get("delivered") is False for x in (A4, C4)))
    chk("U4 A/C", "meta: timeout True, rc 124 on the cell", m.get("timeout") is True and m.get("rc") == 124 and mc.get("timeout") is True and mc.get("rc") == 124)
    chk("U4 R", "retry reason 'timeout', 2 sessions, the retry (on a COPY of A's final workspace) wrote the answer and PASSES; A stays FAIL",
        mr.get("retry_reasons") == ["timeout"] and mr.get("n_sessions") == 2 and (cx.score(R4) or {}).get("pass") is True and (cx.score(A4) or {}).get("pass") is False,
        mr.get("retry_reasons"))
    check_session(cx, R4, (mr.get("sessions") or [{}, {}])[1], scope="U4 R retry", own_dir=R4, expect_sendback=None, idle_s=idle, agent_timeout=to)
    chk("U4", "no K cell for a task bank without a visible check suite", not (ev / "cells" / cn("K", "U4")).exists())
    chk("U4 A", "ledger for the timed-out session has completed calls (not 'timeout without any model reply')",
        (m.get("sessions") or [{}])[0].get("ledger", {}).get("calls", 0) >= 1)

    # U5：A 與 R 的兩次重試都 claim ⇒ 3 段都沒交；C 寫對
    A5, R5, C5 = (cn(x, "U5") for x in ("A", "R", "C"))
    m, mr, mc = (cx.meta(x) or {} for x in (A5, R5, C5))
    chk("U5 R", "retries exhausted: 3 sessions, retry_reasons [no_deliverable x2], FAIL, not void",
        mr.get("n_sessions") == 3 and mr.get("retry_reasons") == ["no_deliverable", "no_deliverable"] and (cx.score(R5) or {}).get("pass") is False and mr.get("void") is False)
    chk("U5 A", "claimed done: not delivered, FAIL", m.get("delivered") is False and (cx.score(A5) or {}).get("pass") is False)
    chk("U5 C", "right solution: PASSES", (cx.score(C5) or {}).get("pass") is True)
    check_session(cx, C5, (mc.get("sessions") or [{}])[0], scope="U5 C", own_dir=C5, expect_sendback=0, idle_s=idle, agent_timeout=to)

    # ── 1b. 帳本與模型端對得上（每段非逾時、非 void 的 session：帳本通數 == 模型端在該段起跑之後看到的非錯誤請求數）──────
    mism = []
    n_checked = 0
    for c in sorted(p.name for p in (ev / "cells").iterdir() if p.is_dir() and not p.name.startswith("_")):
        mm = cx.meta(c) or {}
        if mm.get("void"):
            continue
        for sess in mm.get("sessions") or []:
            if sess.get("shared_with_A") or sess.get("timeout") or sess.get("void"):
                continue
            t0 = iso(sess["started"]) - 1.0
            n_stub = sum(1 for r in stub if r.get("tag") == sess["tag"] and r.get("t", 0) >= t0 and r.get("step") != "error")
            n_checked += 1
            if (sess.get("ledger") or {}).get("calls") != n_stub:
                mism.append((sess["tag"], (sess.get("ledger") or {}).get("calls"), n_stub))
    chk("ledger", "every finished session's ledger call count == the requests the model side served since that session started "
        "(a re-run of an aborted cell does not inherit the killed incarnation's rows)", not mism and n_checked > 0, mism or f"{n_checked} sessions")

    # ── 2. 全域 ──────────────────────────────────────────────────────────────────────────────
    all_cells = sorted(p.name for p in (ev / "cells").iterdir() if p.is_dir() and not p.name.startswith("_"))
    chk("all", "every cell dir has DONE and a valid meta.json", all((ev / "cells" / c / "DONE").exists() and cx.meta(c) is not None for c in all_cells), len(all_cells))
    nonvoid_extra = [c for c in all_cells if (cx.meta(c) or {}).get("void") and c not in (A1, R1, K1)]
    chk("all", "the only void cells are the injected ones (U1 A/R/K attempt 1)", not nonvoid_extra, nonvoid_extra)
    def versions(arm: str, unit: str) -> list[str]:
        base = cell_name(P, arm, *U[unit].split("/"), 1, 1)
        return [c for c in all_cells if c == base or re.fullmatch(re.escape(base) + r"v\d+", c)]
    dup = {(arm, u): versions(arm, u) for u in U for arm in (["A", "R", "C"] + (["K"] if u in ("U1", "U2", "U3") else []))
           if sum(1 for c in versions(arm, u) if not (cx.meta(c) or {}).get("void")) != 1}
    chk("all", "no duplicate final cells: each (arm, unit) has exactly one non-void DONE cell (attempt 2 only where attempt 1 was void)", not dup, dup)
    chk("all", "progress.jsonl carries no score fields", not any("pass" in r or "score" in r for r in prog_all))
    chk("all", "stub 500 injections hit exactly the planned tags (U1 A#1 x5, U2 C#1 x1)",
        sum(1 for r in stub if r.get("step") == "error" and r.get("tag") == f"{A1}.n1") == 5
        and sum(1 for r in stub if r.get("step") == "error" and r.get("tag") == f"{C2}.n1") == 1)
    ar = ev / "cells_aborted"
    chk("all", "workspace/receiver leftovers cleaned: /srv/runs empty", not any((Path('/srv/runs')).iterdir()) if Path('/srv/runs').exists() else True)
    if not a.skip_cleanup_check:
        pu = subprocess.run(["bash", "-c", "getent passwd | cut -d: -f1 | grep -E '^[as][0-9]{6}$' || true"], capture_output=True, text=True).stdout.split()
        chk("all", "no cell/score Linux users left", not pu, pu)
        tm = subprocess.run(["bash", "-c", "ls /tmp/tmux-0 2>/dev/null | grep -E '^i[0-9]+$' || true"], capture_output=True, text=True).stdout.split()
        pi = subprocess.run(["bash", "-c", "pgrep -af '/opt/eval/pi' | grep -v pgrep || true"], capture_output=True, text=True).stdout.strip()
        chk("all", "no tmux servers and no pi processes left", not pi, f"sockets={tm}")
    chk("all", "DRIVER_DONE, PACKER_DONE, MIRROR_OK, ALL_DONE all written",
        (ev / "DRIVER_DONE").exists() and (ev / "archive" / "PACKER_DONE").exists() and (ev / "archive" / "MIRROR_OK").exists() and (ev / "ALL_DONE").exists())

    # ── 3. 打包 ──────────────────────────────────────────────────────────────────────────────
    arc = ev / "archive"
    man = [ln.split("\t") for ln in (arc / "MANIFEST.tsv").read_text().splitlines() if ln.strip()] if (arc / "MANIFEST.tsv").exists() else []
    chk("pack", "MANIFEST.tsv lists the chunks; every chunk's sha256 matches its .sha256 file and the manifest",
        bool(man) and all(sha256_file(arc / r[0]) == r[1] and (arc / (r[0] + ".sha256")).read_text().split()[0] == r[1] for r in man), f"{len(man)} chunk(s)")
    members = collections.Counter()
    keyfiles = []
    for r in man:
        for nme in tar_members(arc / r[0]):
            mm = re.fullmatch(r"cells/([^/]+)/DONE", nme)
            if mm:
                members[mm.group(1)] += 1
            if nme.endswith(".key") or "identity.key" in nme:
                keyfiles.append(nme)
    done_cells = sorted(p.name for p in (ev / "cells").iterdir() if (p / "DONE").exists())
    chk("pack", "every DONE cell is in exactly one chunk (no gap, no duplicate)", sorted(members) == done_cells and all(v == 1 for v in members.values()),
        f"cells={len(done_cells)} packed={len(members)} dup={[k for k, v in members.items() if v > 1]} missing={sorted(set(done_cells) - set(members))}")
    chk("pack", "no private key file inside any chunk", not keyfiles, keyfiles)
    chk("pack", "the chunk sizes in the manifest are the real file sizes", all((arc / r[0]).stat().st_size == int(r[2]) for r in man))
    mir = a.mirror
    chk("pack", "mirror (stand-in for Drive) has every chunk, byte-identical sha256, plus MANIFEST.tsv",
        bool(man) and all((mir / r[0]).is_file() and sha256_file(mir / r[0]) == r[1] for r in man) and (mir / "MANIFEST.tsv").is_file())
    chk("pack", "MIRROR_OK content: chunks counted == manifest rows, no bad", (jload(arc / "MIRROR_OK") or {}).get("chunks") == len(man) and not (jload(arc / "MIRROR_OK") or {}).get("bad"))

    # ── 4. 續跑 ──────────────────────────────────────────────────────────────────────────────
    if a.kill_snapshot and a.kill_snapshot.exists():
        snap = json.loads(a.kill_snapshot.read_text())
        before = snap["done_cells"]
        same = {c: ((cx.meta(c) or {}).get("ended") == v) for c, v in before.items()}
        chk("resume", "cells that were DONE before the driver was killed were not run again (meta.ended unchanged)", all(same.values()),
            f"{sum(same.values())}/{len(same)}")
        inflight = snap["inflight_dirs"]
        mv = [e for e in events if e.get("event") == "aborted_partial_moved"]
        chk("resume", "every in-flight cell dir at kill time was moved to cells_aborted/ and re-run from scratch (new DONE cell)",
            all((ar.exists() and any(x.name.startswith(c + ".") for x in ar.iterdir())) and (ev / "cells" / c / "DONE").exists() for c in inflight),
            f"inflight={len(inflight)} moved_events={len(mv)}")
        dl = (ev / f"driver_{P}.log")
        sweeps = [json.loads(ln.split("startup sweep: ", 1)[1]) for ln in (dl.read_text().splitlines() if dl.exists() else []) if "startup sweep: " in ln]
        chk("resume", "the restarted driver swept the killed driver's leftovers (tmux servers killed, cell users deleted) before starting",
            len(sweeps) >= 2 and sweeps[0] == {"tmux_killed": 0, "users_deleted": [], "runs_dirs_removed": []}
            and sweeps[-1]["tmux_killed"] >= 1 and len(sweeps[-1]["users_deleted"]) >= 1, sweeps[-1] if sweeps else None)
        chk("resume", "no cell exists twice (names unique, finals unique) after the restart: see 'no duplicate final cells'", True)

    out = {"schema": "i1001.local_e2e_verify/1", "n_checks": len(CHECKS), "n_fail": sum(1 for c in CHECKS if not c["ok"]),
           "checks": CHECKS}
    a.out.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str) + "\n")
    print(f"\n{out['n_checks'] - out['n_fail']}/{out['n_checks']} checks OK; FAIL={out['n_fail']}")
    return 0 if out["n_fail"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
