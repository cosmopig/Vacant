"""i1001（Colab 互動式 pi ± Vacant）的純函式測試：計畫建構與天花板規則、錄好的 pi session 檔上的完成偵測、分析的統計與配對、
排程狀態（續跑／void 重跑）、位置池、本機同步／自動關機腳本（假的 colab）、bundle 與重用檔 MANIFEST。

不依賴 root／tmux／bwrap／pi：那一半（真的 TUI、bridge、K／R、void 重跑、C 的送回）由
`ops/colab_interactive_20261001/vm/vm_selfcheck.py` 在有這些東西的機器上走一遍（見該資料夾的 RUNBOOK.md）。
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import pathlib
import subprocess
import sys
import tarfile
import threading
import time

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
CI = ROOT / "ops" / "colab_interactive_20261001"
FIX = pathlib.Path(__file__).resolve().parent / "fixtures" / "colab_interactive_20261001"
for p in (str(CI / "vm"), str(CI)):
    if p not in sys.path:
        sys.path.insert(0, p)

import analyze_i1001 as an  # noqa: E402
import build_manifest  # noqa: E402
import driver_i1001  # noqa: E402
import feasibility_i1001  # noqa: E402
import finalize_vm  # noqa: E402
import plan_builder as pb  # noqa: E402
import tui_cell  # noqa: E402
import tui_lib as tl  # noqa: E402

from vacant_network import research  # noqa: E402


def entries(name: str) -> list[dict]:
    return [json.loads(x) for x in (FIX / f"session_{name}.jsonl").read_text().splitlines() if x.strip()]


# ── tail_state：pi 0.87.1 實測錄下的六種結尾 ───────────────────────────────────────────────────

@pytest.mark.parametrize("name,want", [("plain-A", "final"), ("claim-A", "final"), ("claim-C", "final"), ("error-A", "final"),
                                       ("errorfinal-A", "error_final"), ("length-A", "final"), ("abort-A", "final")])
def test_tail_state_on_recorded_sessions(name, want):
    assert tl.tail_state(entries(name)) == want


def test_tail_state_prefixes_are_running_or_retrying():
    es = entries("claim-C")
    # 第一個最終 stop 之後、Vacant 的 custom_message 到之前：看起來是 final（這就是為什麼要安靜 IDLE_S 秒）
    i_stop = next(i for i, e in enumerate(es) if (e.get("message") or {}).get("stopReason") == "stop")
    assert tl.tail_state(es[:i_stop + 1]) == "final"
    # custom_message 到了：又在跑
    assert tl.tail_state(es[:i_stop + 2]) == "running"
    # 沒有任何 message 條目（session 檔還沒有第一則 assistant）
    assert tl.tail_state(es[:2]) == "empty"
    # error 後面接 context_edit ＝ pi 會重試
    ef = entries("errorfinal-A")
    i_ce = next(i for i, e in enumerate(ef) if e.get("type") == "context_edit")
    assert tl.tail_state(ef[:i_ce + 1]) == "retrying"
    assert tl.tail_state(ef[:i_ce]) == "error_final"        # error 條目剛寫、context_edit 還沒寫的那 7 毫秒


def test_tail_state_works_on_summaries():
    assert [tl.tail_state([tl.summarize(e) for e in entries(n)]) for n in ("plain-A", "errorfinal-A")] == ["final", "error_final"]


def test_max_gap_after_final_matches_the_measured_sendback_delay():
    g = tl.max_gap_after_final(entries("claim-C"))
    assert 0.40 < g < 0.47                                  # PI_INTERACTIVE_NOTES：0.37–0.48 s
    assert tl.max_gap_after_final(entries("plain-A")) is None


# ── DoneDetector：在錄好的 session 檔上重播（時間取條目自己的 timestamp）──────────────────────

def replay(ents, idle_s, hook_busy=lambda t: 0, poll=0.2, tail_s=60.0):
    ts = [tl.iso(e["timestamp"]) for e in ents]
    det = tl.DoneDetector(idle_s)
    t = ts[0]
    while t <= ts[-1] + tail_s:
        vis = [e for e, x in zip(ents, ts) if x <= t]
        if det.update(t, tl.tail_state([tl.summarize(e) for e in vis]), (len(vis),), hook_busy(t)):
            return {"t": t, "visible": len(vis), "state": tl.tail_state([tl.summarize(e) for e in vis]), "t_last": ts[-1]}
        t += poll
    return None


@pytest.mark.parametrize("name,state", [("plain-A", "final"), ("error-A", "final"), ("length-A", "final"), ("abort-A", "final"),
                                        ("errorfinal-A", "error_final"), ("claim-A", "final")])
def test_done_only_after_idle_and_sees_all_entries(name, state):
    ents = entries(name)
    r = replay(ents, 15.0)
    assert r is not None and r["state"] == state
    assert r["visible"] == len(ents)                         # 整個檔都出現之後才算
    assert r["t"] - r["t_last"] >= 15.0 - 1e-6                # 且安靜了 IDLE_S 秒
    assert r["t"] - r["t_last"] <= 15.0 + 0.5


def test_vacant_sendback_is_waited_for_with_idle_15():
    ents = entries("claim-C")
    r = replay(ents, 15.0)
    assert r["visible"] == len(ents) == 14                    # Vacant 送回之後的第二輪也等到了
    assert sum(1 for e in ents if e.get("type") == "custom_message") == 1


def test_negative_control_too_short_idle_declares_done_before_the_sendback():
    """對照：IDLE_S 比 Vacant 送回的間隔（0.435 s）還短，就會在第一個最終 stop 那一刻判完成、漏掉整個 C 組的作用。
    這個負控制證明上面的測試抓得到「判太早」。"""
    r = replay(entries("claim-C"), 0.2)
    assert r is not None and r["visible"] < 14


def test_retrying_state_never_counts_as_done():
    ef = entries("errorfinal-A")
    i_ce = next(i for i, e in enumerate(ef) if e.get("type") == "context_edit")
    assert replay(ef[:i_ce + 1], 5.0, tail_s=120.0) is None   # pi 退避重試中：安靜再久也不算


def test_live_hook_process_delays_done():
    ents = entries("plain-A")
    t_last = tl.iso(ents[-1]["timestamp"])
    r = replay(ents, 5.0, hook_busy=lambda t: 1 if t < t_last + 20 else 0, tail_s=80.0)
    assert r["t"] >= t_last + 20 + 5.0 - 1e-6                 # hook 行程結束之後再安靜 IDLE_S


def test_any_activity_resets_the_quiet_timer():
    det = tl.DoneDetector(10.0)
    assert not det.update(0.0, "final", (1,), 0)
    assert not det.update(9.0, "final", (1,), 0)
    assert not det.update(9.5, "final", (2,), 0)              # 帳本多了一通
    assert not det.update(19.0, "final", (2,), 0)
    assert det.update(19.6, "final", (2,), 0)


# ── SessionTail：只吃寫完的整行 ───────────────────────────────────────────────────────────────

def test_session_tail_incremental_and_partial_lines(tmp_path):
    raw = (FIX / "session_plain-A.jsonl").read_bytes()
    lines = raw.splitlines(keepends=True)
    f = tmp_path / "2026_x.jsonl"
    t = tl.SessionTail(tmp_path)
    assert t.poll() == 0 and t.state == "empty"
    f.write_bytes(b"".join(lines[:5]) + lines[5][:20])        # 第 6 行只寫了一半
    assert t.poll() == 5
    assert len(t.summ) == 5
    f.write_bytes(raw)
    assert t.poll() == len(lines) - 5
    assert t.state == "final" and len(t.summ) == len(lines)
    assert t.first_user_text and "goal.md" in t.first_user_text
    assert t.poll() == 0


# ── 錯誤分類與 void 判斷 ──────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("msg,infra", [('500: {"error":"x"}', True), ("503: busy", True), ("429: rate", True), ("402: budget", True),
                                       ("408: timeout", True), ("400: context length exceeded", False), ("404: nope", False),
                                       ("fetch failed", True), ("terminated", True), (None, True)])
def test_error_is_infra(msg, infra):
    assert tl.error_is_infra(msg) is infra


def _cls(**kw):
    base = dict(ready=True, trust_unhandled=False, typed_ok=True, final_state="final", last_error=None,
                ledger={"calls": 5, "non200": 0, "stream_errors": 0}, session_file=True, timeout=False,
                pane_rc_early=None, exited_before_done=False)
    base.update(kw)
    return tl.classify_session(**base)


def test_classify_session_void_rules():
    assert _cls() == (False, None)
    assert _cls(ready=False)[1] == "footer_timeout"
    assert _cls(ready=False, trust_unhandled=True)[1] == "trust_dialog_unhandled"
    assert _cls(typed_ok=False)[1] == "input_mismatch"
    assert _cls(typed_ok=None) == (False, None)                           # session 檔還沒有 user 訊息：不判
    v, why = _cls(final_state="error_final", last_error="500: x")
    assert v and why.startswith("model_error_final")
    assert _cls(final_state="error_final", last_error="400: context length", ledger={"calls": 3, "non200": 0, "stream_errors": 0}) == (False, None)
    assert _cls(ledger={"calls": 5, "non200": 1, "stream_errors": 0})[0] is True
    assert _cls(ledger={"calls": 5, "non200": 0, "stream_errors": 2})[0] is True
    assert _cls(ledger={"calls": 0, "non200": 0, "stream_errors": 0}, session_file=False)[1] == "no_model_call"
    assert _cls(ledger={"calls": 0, "non200": 0, "stream_errors": 0}, session_file=False, exited_before_done=True)[1] == "pi_died_before_first_request"
    assert _cls(timeout=True, ledger={"calls": 0, "non200": 0, "stream_errors": 0}, session_file=True)[1] == "timeout_without_any_model_reply"
    assert _cls(timeout=True) == (False, None)                             # 逾時但有模型回覆：是 agent 的結果，不是 void


# ── 打字、交付物、重試條件、信任對話框 ──────────────────────────────────────────────────────────

def test_typing_plan_and_match():
    assert tl.typing_plan("Read goal.md.") == ("line", "Read goal.md.")
    mode, t = tl.typing_plan("a\n\tb\r\nc")
    assert mode == "paste" and "\t" not in t and t == "a\n    b\nc"
    assert tl.typing_plan("a\x1b[201~b\x00c\x7f") == ("line", "a[201~bc")                  # 控制字元（含 ESC）去掉
    with pytest.raises(ValueError):
        tl.typing_plan("/quit")
    with pytest.raises(ValueError):
        tl.typing_plan("!ls")
    assert tl.typed_matches("hello \n", "hello") is True
    assert tl.typed_matches("hellx", "hello") is False
    assert tl.typed_matches(None, "hello") is None


def test_deliverables_and_retry_condition(tmp_path):
    assert tl.deliverable_name("lcb_v2") == "solution.py"
    assert tl.deliverable_name("dabench") == "answer.txt" and tl.deliverable_name("databench") == "answer.txt"
    td = tmp_path / "pg"
    (td / "hidden").mkdir(parents=True)
    (td / "hidden" / "expected.json").write_text(json.dumps({"solution_file": "pov.py"}))
    assert tl.deliverable_name("polyglot_py", td) == "pov.py"
    ws = tmp_path / "ws"
    ws.mkdir()
    assert not tl.has_deliverable(ws, "solution.py")
    (ws / "solution.py").write_text("")
    assert not tl.has_deliverable(ws, "solution.py")                       # 空檔不算交件
    (ws / "solution.py").write_text("x=1\n")
    assert tl.has_deliverable(ws, "solution.py")
    assert tl.needs_retry({"timeout": False}, ws, "solution.py") == (False, None)
    assert tl.needs_retry({"timeout": True}, ws, "solution.py") == (True, "timeout")
    (ws / "solution.py").unlink()
    assert tl.needs_retry({"timeout": False}, ws, "solution.py") == (True, "no_deliverable")


def test_trust_triggers(tmp_path):
    ws = tmp_path / "app"
    ws.mkdir()
    assert tl.trust_triggers(ws, ancestors=()) == []
    (ws / ".pi").mkdir()
    assert tl.trust_triggers(ws, ancestors=()) == []                        # 空的 .pi 不觸發
    (ws / ".pi" / "settings.json").write_text("{}")
    (ws / ".agents" / "skills").mkdir(parents=True)
    got = tl.trust_triggers(ws, ancestors=())
    assert str(ws / ".pi" / "settings.json") in got and str(ws / ".agents" / "skills") in got
    (ws / "AGENTS.md").write_text("x")                                      # AGENTS.md／CLAUDE.md 不觸發
    assert len(tl.trust_triggers(ws, ancestors=())) == 2


def test_footer_and_dialog_detection():
    assert tl.footer_ready("x\n  /app\n   (harbor-endpoint) gemma-4-12b-it-qat\n")
    assert not tl.footer_ready(" pi v0.87.1  ")
    assert tl.trust_dialog_present("Trust project folder?\n 1. Trust")
    assert tl.pane_exit_rc("....\n__PANE_EXIT_0__\n") == 0 and tl.pane_exit_rc("__PANE_EXIT_137__") == 137 and tl.pane_exit_rc("x") is None


# ── K 組的回報文字（KS-1）─────────────────────────────────────────────────────────────────────

def test_failure_text_uses_visible_check_details_only_and_ks1_clean():
    j = json.loads((FIX / "judge_reject.json").read_text())["result"]
    ft = tl.failure_text(j)
    assert "check_visible_01" in ft and "got=-1 want=5" in ft
    assert "deliverable_present" not in ft                                   # PASS 的主張不放進去
    instr = "Read goal.md and contract.md in this directory and do what they say. Use your tools to write the file."
    text = tl.k_instruction(instr, j)
    assert text.startswith(instr) and ft in text
    assert "visible checks" in text and tl.ks1_clean(text) == text
    mode, typed = tl.typing_plan(text)
    assert mode == "paste"
    # 沒有細節時不編造
    assert "did not report any detail" in tl.failure_text({"results": [], "reasons": []})
    # 太長要截
    big = {"results": [{"status": "FAIL", "detail": "x" * 10000}]}
    assert len(tl.failure_text(big, limit=2400)) < 2600


def test_ks1_guard_negative_control():
    for bad in ("You are responsible for this.", "you will be punished", "It was your fault", "who is to blame", "你有責任"):
        with pytest.raises(ValueError):
            tl.ks1_clean(bad)
    assert tl.ks1_clean("The visible checks report: args=(2, 3) got=-1 want=5") .startswith("The visible")


# ── 名字 ──────────────────────────────────────────────────────────────────────────────────────

def test_names():
    assert tl.cell_name("i1", "A", "lcb_v1", "lcb_3487", 1) == "i1-A-lcb_v1-lcb_3487-s1"
    assert tl.cell_name("i1", "A", "lcb_v1", "lcb_3487", 1, 2) == "i1-A-lcb_v1-lcb_3487-s1v2"
    assert tl.cell_name("i1", "C", "polyglot_py", "pg/odd id", 1) == "i1-C-polyglot_py-pg_odd_id-s1"
    assert tl.session_tag("i1-K-x-s1", 3) == "i1-K-x-s1.n3"
    assert tl.sessions_dir_name(1) == "sessions" and tl.sessions_dir_name(2) == "sessions-2"


# ── 位置池 ────────────────────────────────────────────────────────────────────────────────────

def test_slot_pool_never_exceeds_capacity():
    pool = tl.SlotPool(3)
    live, peak, lock = [0], [0], threading.Lock()

    def work(k, prio):
        with pool.slot(k, priority=prio):
            with lock:
                live[0] += k
                peak[0] = max(peak[0], live[0])
            time.sleep(0.01)
            with lock:
                live[0] -= k
    ths = [threading.Thread(target=work, args=(1 + (i % 2), i % 3 == 0), daemon=True) for i in range(24)]
    [t.start() for t in ths]
    [t.join() for t in ths]
    assert peak[0] <= 3 and pool.used == 0 and pool.peak <= 3


def test_slot_pool_continuation_beats_new_admission():
    pool = tl.SlotPool(2)
    pool.acquire(2)
    order = []

    def admission():
        pool.acquire(1)
        order.append("admission")

    def continuation():
        pool.acquire(1, priority=True)
        order.append("continuation")
    a = threading.Thread(target=admission, daemon=True)
    a.start()
    time.sleep(0.2)                                                          # 新單位先在排隊
    c = threading.Thread(target=continuation, daemon=True)
    c.start()
    time.sleep(0.2)
    pool.release(1)                                                          # 只釋出一個位置：接續段優先
    c.join(2)
    assert order == ["continuation"]
    pool.release(1)
    a.join(2)
    assert order == ["continuation", "admission"]


def test_slot_pool_clamps_group_request_to_capacity():
    pool = tl.SlotPool(1)
    assert pool.acquire(2) == 1                                              # slots=1 時 A、C 無法同時，不會死鎖
    pool.release(1)


# ── 代理帳本 ──────────────────────────────────────────────────────────────────────────────────

def test_ledger_tail_incremental_and_stats(tmp_path):
    p = tmp_path / "ledger.jsonl"
    lt = tl.LedgerTail(p, min_interval_s=0)
    assert lt.stats("a.n1")["calls"] == 0
    rows = [{"tag": "a.n1", "status": 200, "ts": 100.0, "latency_s": 2.0, "usage": {"prompt_tokens": 10, "completion_tokens": 3}},
            {"tag": "a.n1", "status": 500, "ts": 110.0, "latency_s": 1.0, "usage": {}},
            {"tag": "b.n1", "status": 200, "stream_error": "boom", "ts": 111.0, "latency_s": 1.0, "usage": {}}]
    p.write_text("".join(json.dumps(r) + "\n" for r in rows[:2]))
    s = lt.stats("a.n1")
    assert s["calls"] == 2 and s["non200"] == 1 and s["prompt_tokens"] == 10 and s["last_end_ts"] == 111.0
    with p.open("a") as f:
        f.write(json.dumps(rows[2]) + "\n")
    assert lt.stats("b.n1")["stream_errors"] == 1 and lt.stats("a.n1")["calls"] == 2


# ── 計畫建構與天花板規則 ──────────────────────────────────────────────────────────────────────

def make_index(tmp_path):
    idx, screen = [], {}
    for b, n_screen, n_rest in (("dabench", 10, 20), ("databench", 10, 20), ("polyglot_py", 10, 24)):
        screen[b] = []
        for i in range(n_screen + n_rest):
            tid = f"{b[:3]}_{i:03d}"
            d = tmp_path / "staged" / b / tid
            (d / "hidden").mkdir(parents=True)
            (d / "hidden" / "expected.json").write_text(json.dumps({"solution_file": f"{tid}.py"}))
            idx.append({"bank": b, "id": tid, "dir": str(d), "role": "screen_sample" if i < n_screen else "task_bank_rest"})
            if i < n_screen:
                screen[b].append(tid)
    for b, nf, nc in (("lcb_v1", 3, 1), ("lcb_v2", 2, 2)):
        for i in range(nf + nc):
            idx.append({"bank": b, "id": f"lcb_{b[-1]}{i}", "dir": f"/x/{b}/{i}", "role": "a_failed" if i < nf else "a_passed_control"})
    return idx, {"screen_sample": screen}


def test_screening_plan_is_a_only_and_uses_manifest_sample(tmp_path):
    idx, man = make_index(tmp_path)
    plan = pb.screening_plan(idx, man, 20261001)
    assert plan["kind"] == "screen" and plan["arms"] == ["A"] and plan["nested"] == []
    assert len(plan["tasks"]) == 30
    assert {t["bank"] for t in plan["tasks"]} == {"dabench", "databench", "polyglot_py"}
    assert all(t["screened"] and not t["k"] for t in plan["tasks"])
    assert plan["estimate"]["max_sessions"] == 30                           # 每題一段 A
    assert plan == pb.screening_plan(idx, man, 20261001)                    # 決定論
    assert [t["id"] for t in plan["tasks"]] != sorted(t["id"] for t in plan["tasks"])   # 種子洗牌過
    man_bad = {"screen_sample": {"dabench": ["dab_000", "no_such_task"]}}
    with pytest.raises(ValueError):
        pb.screening_plan(idx, man_bad, 1)
    pg = next(t for t in plan["tasks"] if t["bank"] == "polyglot_py")
    assert pg["deliverable"].endswith(".py") and pg["deliverable"] != "solution.py"   # 從 expected.json 讀
    assert "read_dir" not in pg
    # 讀不到 polyglot 的 expected.json 時寧可停下來（不要把 solution.py 寫進計畫）
    broken = [dict(t, dir=str(tmp_path / "nowhere" / t["id"])) if t["bank"] == "polyglot_py" else t for t in idx]
    with pytest.raises(FileNotFoundError):
        pb.screening_plan(broken, man, 1)
    # 預覽：dir 讀不到（VM 路徑）但 read_dir 在本機 ⇒ 可以
    preview = [dict(t, dir="/srv/eval/staged/x/" + t["id"], read_dir=t["dir"]) if t["bank"] == "polyglot_py" else t for t in idx]
    assert pb.screening_plan(preview, man, 1)["tasks"][0]["id"]


def test_ceiling_rule_drops_at_9_of_10_and_records_everything():
    def rows(passes, voids=0, missing=0, n=10):
        out = []
        for i in range(n):
            if i < missing:
                out.append({"task": f"t{i}", "cell": None, "void": False, "pass": None})
            elif i < missing + voids:
                out.append({"task": f"t{i}", "cell": f"c{i}", "void": True, "pass": None})
            elif i < missing + voids + passes:
                out.append({"task": f"t{i}", "cell": f"c{i}", "void": False, "pass": True})
            else:
                out.append({"task": f"t{i}", "cell": f"c{i}", "void": False, "pass": False})
        return out
    d = pb.ceiling_decision({"at_ceiling": rows(9), "full": rows(10), "edge": rows(8), "floor": rows(0), "voidy": rows(8, voids=2),
                             "incomplete": rows(9, missing=1), "undecided": rows(8, missing=2), "cannot": rows(5, missing=2)},
                            {k: 10 for k in ("at_ceiling", "full", "edge", "floor", "voidy", "incomplete", "undecided", "cannot")})
    b = d["banks"]
    assert b["at_ceiling"]["dropped"] and b["full"]["dropped"]
    assert not b["edge"]["dropped"] and len(b["edge"]["unsolved"]) == 2
    assert not b["floor"]["dropped"] and len(b["floor"]["unsolved"]) == 10         # 地板：不丟（還是有解不開的題）
    assert not b["voidy"]["dropped"] and "void" in b["voidy"]["reason"]            # void 算沒過（保守）
    assert b["incomplete"]["dropped"] and b["incomplete"]["missing"] == ["t0"]       # 看到 9 勝就決定了，沒跑的格子不會讓它變少
    assert not b["undecided"]["dropped"] and "undecided" in b["undecided"]["reason"]  # 8 勝＋2 沒跑：還可能到 9
    assert not b["cannot"]["dropped"] and "undecided" not in b["cannot"]["reason"]    # 到不了 9
    assert d["dropped_banks"] == ["at_ceiling", "full", "incomplete"]
    assert d["rule"] == {"n": 10, "pass_ge": 9}


def test_main_plan_applies_decision_and_flags(tmp_path):
    idx, man = make_index(tmp_path)
    dec = {"dropped_banks": ["databench"]}
    plan = pb.main_plan(idx, man, dec, 20261001)
    banks = {t["bank"] for t in plan["tasks"]}
    assert banks == {"lcb_v1", "lcb_v2", "dabench", "polyglot_py"} and "databench" not in banks
    assert plan["arms"] == ["A", "C"] and plan["nested"] == ["R", "K"]
    lcb = [t for t in plan["tasks"] if t["bank"].startswith("lcb")]
    assert len(lcb) == 8 and all(t["k"] and t["deliverable"] == "solution.py" for t in lcb)
    assert all(not t["k"] for t in plan["tasks"] if not t["bank"].startswith("lcb"))
    assert sum(1 for t in plan["tasks"] if t["bank"] == "dabench" and t["screened"]) == 10      # 篩選過的題也在池裡（主跑重跑 A）
    assert len(plan["tasks"]) == 8 + 30 + 34
    est = plan["estimate"]
    assert est["first_sessions"] == 2 * 72 and est["max_extra_R_sessions"] == 2 * 72 and est["max_extra_K_sessions"] == 2 * 8
    assert est["max_session_minutes"] == est["max_sessions"] * 30.0
    only_ac = pb.main_plan(idx, man, dec, 1, nested=())
    assert only_ac["nested"] == [] and not any(t["k"] for t in only_ac["tasks"])
    assert [t["id"] for t in plan["tasks"]] == [t["id"] for t in pb.main_plan(idx, man, dec, 20261001)["tasks"]]


def _cell(root, name, *, void=False, passed=None, attempt=1, done=True, extra=None):
    d = root / name
    d.mkdir(parents=True)
    (d / "meta.json").write_text(json.dumps({"cell": name, "void": void, "attempt": attempt, **(extra or {})}))
    if passed is not None:
        (d / "score.json").write_text("noise\n" + json.dumps({"pass": passed}) + "\n")
    if done:
        (d / "DONE").write_text("x")


def test_screen_outcomes_latest_attempt_wins(tmp_path):
    plan = {"tasks": [{"bank": "dabench", "id": f"t{i}"} for i in range(5)]}
    cells = tmp_path / "cells"
    cells.mkdir()
    n = lambda i, a=1: tl.cell_name("i1s", "A", "dabench", f"t{i}", 1, a)           # noqa: E731
    _cell(cells, n(0), void=True)                                                  # attempt 1 void → attempt 2 通過
    _cell(cells, n(0, 2), passed=True, attempt=2)
    _cell(cells, n(1), passed=False)                                               # 沒過
    _cell(cells, n(3), void=True)                                                  # 兩次都 void
    _cell(cells, n(3, 2), void=True, attempt=2)
    _cell(cells, n(4), passed=True, done=False)                                    # 沒有 DONE ＝ 還沒跑完 ＝ 缺
    out = pb.screen_outcomes(cells, "i1s", plan)["dabench"]
    by = {r["task"]: r for r in out}
    assert by["t0"]["pass"] is True and by["t0"]["attempt"] == 2
    assert by["t1"]["pass"] is False
    assert by["t2"]["cell"] is None
    assert by["t3"]["pass"] is None and by["t3"]["void"] is True
    assert by["t4"]["cell"] is None


# ── driver：續跑／void 重跑的狀態判斷 ────────────────────────────────────────────────────────

def _cfg(tmp_path):
    c = tui_cell.Cfg(eval_root=tmp_path / "eval")
    c.cells.mkdir(parents=True)
    return c


def test_group_status_resume_and_rerun_rules(tmp_path):
    cfg = _cfg(tmp_path)
    plan = {"nested": ["R", "K"], "arms": ["A", "C"]}
    task = {"bank": "lcb_v1", "id": "t1", "k": True}
    N = lambda arm, a=1: tl.cell_name("i1", arm, "lcb_v1", "t1", 1, a)               # noqa: E731
    assert driver_i1001.group_status(cfg, plan, task, "A", "i1", 1) == ("todo", 1)
    # 中斷的殘骸：A 有目錄但沒有 DONE ⇒ 整條線搬走、attempt 1 重跑
    _cell(cfg.cells, N("A"), done=False)
    _cell(cfg.cells, N("R"), done=False)
    assert driver_i1001.group_status(cfg, plan, task, "A", "i1", 1) == ("todo", 1)
    assert not (cfg.cells / N("A")).exists() and len(list((cfg.eval_root / "cells_aborted").iterdir())) == 2
    ev = [json.loads(x) for x in (cfg.eval_root / "progress.jsonl").read_text().splitlines()]
    assert [e["event"] for e in ev] == ["aborted_partial_moved"] * 2 and "pass" not in json.dumps(ev)
    # 完整、非 void ⇒ done
    for arm in ("A", "R", "K"):
        _cell(cfg.cells, N(arm), passed=True, extra={"k_on": True})
    assert driver_i1001.group_status(cfg, plan, task, "A", "i1", 1) == ("done", 1)
    # A 的 DONE 在、K 缺 ⇒ 殘骸，重跑
    import shutil
    shutil.rmtree(cfg.cells / N("K"))
    assert driver_i1001.group_status(cfg, plan, task, "A", "i1", 1) == ("todo", 1)
    # K 起不來（A.meta.k_on＝False）時 K 缺是正常的
    cfg2 = _cfg(tmp_path / "second")
    for arm in ("A", "R"):
        _cell(cfg2.cells, N(arm), passed=True, extra={"k_on": False})
    assert driver_i1001.group_status(cfg2, plan, task, "A", "i1", 1) == ("done", 1)
    # void 的 attempt 1 ⇒ 下一次是 attempt 2；attempt 2 不論結果都到此為止
    cfg3 = _cfg(tmp_path / "third")
    for arm in ("A", "R", "K"):
        _cell(cfg3.cells, N(arm), void=True, extra={"k_on": True})
    assert driver_i1001.group_status(cfg3, plan, task, "A", "i1", 1) == ("todo", 2)
    for arm in ("A", "R", "K"):
        _cell(cfg3.cells, N(arm, 2), void=True, attempt=2, extra={"k_on": True})
    assert driver_i1001.group_status(cfg3, plan, task, "A", "i1", 1) == ("done", 2)
    # A 自己沒 void、但 R／K 有 void（group_void）也算要重跑一次
    cfg4 = _cfg(tmp_path / "fourth")
    _cell(cfg4.cells, N("A"), passed=True, extra={"k_on": True, "group_void": True})
    for arm in ("R", "K"):
        _cell(cfg4.cells, N(arm), void=True, extra={"k_on": True})
    assert driver_i1001.group_status(cfg4, plan, task, "A", "i1", 1) == ("todo", 2)
    # C 線
    cfg5 = _cfg(tmp_path / "fifth")
    assert driver_i1001.group_status(cfg5, plan, task, "C", "i1", 1) == ("todo", 1)
    _cell(cfg5.cells, tl.cell_name("i1", "C", "lcb_v1", "t1", 1), passed=False)
    assert driver_i1001.group_status(cfg5, plan, task, "C", "i1", 1) == ("done", 1)


def test_progress_rows_carry_no_scores():
    meta = {"cell": "c", "unit": "b/t", "bank": "b", "task": "t", "arm": "A", "sample": 1, "attempt": 1, "void": False, "pass": True,
            "score": {"pass": True}, "timeout": False, "rc": 0, "wall_s": 1.0, "n_sessions": 1}
    row = driver_i1001.progress_row(meta)
    assert "pass" not in row and "score" not in row and row["cell"] == "c"


def test_parse_deadline():
    assert driver_i1001.parse_deadline(None) is None
    assert driver_i1001.parse_deadline("1970-01-02T00:00:00Z") == 86400.0


# ── 可行性護欄與收尾 ───────────────────────────────────────────────────────────────────────────

def test_feasibility_ignores_timeouts_but_catches_infra(tmp_path):
    led = tl.LedgerTail(tmp_path / "ledger.jsonl", min_interval_s=0)
    rows = [{"cell": f"c{i}", "arm": "A", "timeout": True, "void": False, "at": f"2026-10-01T00:00:{i:02d}Z"} for i in range(30)]
    (tmp_path / "ledger.jsonl").write_text("".join(json.dumps({"tag": f"c{i}.n1", "status": 200, "ts": 1.0}) + "\n" for i in range(30)))
    res = feasibility_i1001.evaluate(rows + [{"event": "infra_void_rerun", "unit": "b/t"}], led, 30)     # 事件列被略過
    assert res["timeouts"] == 30 and not res["triggered"]                  # 逾時率 100% 也不觸發（題池本來就會撞）
    rows2 = [dict(r, void=(i % 2 == 0)) for i, r in enumerate(rows)]
    assert feasibility_i1001.evaluate(rows2, led, 30)["triggered"]         # void 率 50%
    (tmp_path / "ledger.jsonl").write_text("".join(json.dumps({"tag": f"c{i % 30}.n1", "status": 500 if i % 5 == 0 else 200, "ts": 1.0}) + "\n"
                                                    for i in range(100)))
    assert feasibility_i1001.evaluate(rows, tl.LedgerTail(tmp_path / "ledger.jsonl", 0), 30)["triggered"]   # 非 200 率 20%
    c_rows = rows[:3] + [{"cell": f"cc{i}", "arm": "C", "install_rc": 1, "at": "2026-10-01T01:00:00Z"} for i in range(3)]
    assert feasibility_i1001.evaluate(c_rows, tl.LedgerTail(tmp_path / "none.jsonl", 0), 30)["triggered"]   # C 安裝失敗 ≥ 3


def test_packer_wrapper_finishes_right_after_driver_done(tmp_path, monkeypatch):
    """packer_i1001：driver 一寫 DRIVER_DONE 就收尾（packer.py 自己的迴圈會多睡最多一個 interval）；打包內容仍是 packer.py 的原函式。"""
    import packer
    import packer_i1001
    ev = tmp_path / "eval"
    (ev / "cells" / "c1").mkdir(parents=True)
    (ev / "cells" / "c1" / "meta.json").write_text("{}")
    (ev / "cells" / "c1" / "DONE").write_text("x")
    (ev / "cells" / "c2").mkdir()                          # 沒有 DONE：不打包
    (ev / "cells" / "c2" / "meta.json").write_text("{}")
    (ev / "progress.jsonl").write_text("{}\n")
    monkeypatch.setattr(packer, "EVAL", ev)
    monkeypatch.setattr(packer, "ARC", ev / "archive")
    monkeypatch.setattr(packer, "PROXY", ev / "proxy")
    mir = tmp_path / "mirror"
    th = threading.Thread(target=packer_i1001.run, kwargs={"interval": 600, "mirror": mir, "poll_s": 0.1, "final_sleep": 0.2}, daemon=True)
    th.start()
    time.sleep(1.0)                                         # 第一包（c1）已經打好、現在在睡 600 秒的 interval 裡
    assert (ev / "archive" / "chunk_0001.tar.xz").exists() and not (ev / "archive" / "PACKER_DONE").exists()
    t0 = time.time()
    (ev / "DRIVER_DONE").write_text("x")
    th.join(20)
    assert not th.is_alive() and time.time() - t0 < 10     # 不是等 600 秒
    assert (ev / "archive" / "PACKER_DONE").exists()
    rows = (ev / "archive" / "MANIFEST.tsv").read_text().splitlines()
    assert rows[0].startswith("chunk_0001.tar.xz\t") and len(rows) == 2
    with tarfile.open(ev / "archive" / "chunk_0001.tar.xz") as t:
        names = t.getnames()
    assert "cells/c1/DONE" in names and not any(n.startswith("cells/c2") for n in names) and "progress.jsonl" in names
    assert (mir / "chunk_0001.tar.xz").exists() and (mir / "MANIFEST.tsv").exists()            # Drive 鏡像
    assert finalize_vm.verify_mirror(ev / "archive" / "MANIFEST.tsv", mir)["bad"] == []


def test_finalize_verify_mirror(tmp_path):
    arc, mir = tmp_path / "arc", tmp_path / "mir"
    arc.mkdir()
    mir.mkdir()
    rows = []
    for i in (1, 2):
        data = f"chunk{i}".encode()
        (mir / f"chunk_000{i}.tar.xz").write_bytes(data)
        rows.append(f"chunk_000{i}.tar.xz\t{hashlib.sha256(data).hexdigest()}\t{len(data)}\t3\tT")
    (arc / "MANIFEST.tsv").write_text("\n".join(rows) + "\n")
    (mir / "MANIFEST.tsv").write_text("x")
    assert finalize_vm.verify_mirror(arc / "MANIFEST.tsv", mir) == {"mirror": str(mir), "chunks": 2, "bad": []}
    (mir / "chunk_0002.tar.xz").write_bytes(b"tampered")
    (mir / "chunk_0001.tar.xz").unlink()
    bad = finalize_vm.verify_mirror(arc / "MANIFEST.tsv", mir)["bad"]
    assert any("chunk_0001" in b and "missing" in b for b in bad) and any("chunk_0002" in b and "differs" in b for b in bad)
    assert finalize_vm.verify_mirror(arc / "MANIFEST.tsv", tmp_path / "nodrive")["bad"]       # Drive 沒掛


# ── 分析：統計 ────────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("b,c", [(0, 0), (5, 0), (0, 5), (10, 2), (3, 3), (7, 1), (1, 0), (25, 14)])
def test_mcnemar_matches_research_module(b, c):
    assert an.binom_two_sided(b, c) == pytest.approx(research.mcnemar_exact(b, c), abs=1e-12)


def test_mcnemar_known_values():
    assert an.binom_two_sided(0, 0) == 1.0
    assert an.binom_two_sided(5, 0) == pytest.approx(2 / 32)
    assert an.binom_two_sided(3, 3) == 1.0
    assert an.binom_two_sided(10, 0) == pytest.approx(2 / 1024)


@pytest.mark.parametrize("ps", [[0.001, 0.04], [0.04, 0.001], [0.03, 0.03], [1.0, 0.5], [0.2, 0.01, 0.03], [0.0]])
def test_holm_matches_research_module(ps):
    assert an.holm(ps) == pytest.approx(research.holm_bonferroni(ps), abs=1e-12)


def test_holm_two_hypotheses_example():
    assert an.holm([0.01, 0.04]) == pytest.approx([0.02, 0.04])
    assert an.holm([0.03, 0.03]) == pytest.approx([0.06, 0.06])
    assert an.holm([0.5, 0.001]) == pytest.approx([0.5, 0.002])


# ── 分析：配對與主要檢定 ───────────────────────────────────────────────────────────────────────

def raw(arm, task, *, bank="lcb_v1", phase="main", attempt=1, void=False, passed=True, delivered=True, released=None,
        role="a_failed", sessions=None, k_attempts=None, retry_needed=None, k_on=None, c_ok=None, void_reason=None):
    sfx = "" if attempt == 1 else f"v{attempt}"
    pfx = "i1s" if phase == "screen" else "i1"
    cell = f"{pfx}-{arm}-{bank}-{task}-s1{sfx}"
    meta = {"cell": cell, "unit": f"{bank}/{task}", "bank": bank, "task": task, "arm": arm, "sample": 1, "attempt": attempt, "phase": phase,
            "role": role, "void": void, "void_reason": void_reason or ("infra" if void else None), "delivered": delivered, "timeout": False,
            "n_sessions": len(sessions or [1]), "wall_s": 100.0, "sessions": sessions if sessions is not None else
            [{"n": 1, "ledger": {"calls": 4, "prompt_tokens": 100, "completion_tokens": 10}, "done_reason": "idle_final", "idle_s": 15.0,
              "late_write_after_done": False, "max_gap_after_final_s": None, "submit_unconfirmed": False}],
            "k_on": k_on, "retry_needed": retry_needed, "c_arm_ok": c_ok}
    if arm == "K":
        meta["k"] = {"attempts": [{"attempt": i + 1, "rc": rc} for i, rc in enumerate(k_attempts or [0])], "released": bool(released)}
    return {"cell": cell, "done": True, "meta": meta, "score": {"pass": passed, "visible_pass": passed}}


def raws(*items):
    return {r["cell"]: r for r in items}


def test_k_vs_r_metric_and_pairing():
    items = []
    # u1: R 沒過、K 放行且過（b）  u2: R 過、K 沒放行（c）  u3: 都過  u4: 都沒過  u5: K void（排除）  u6: R void（排除）
    plan = {"u1": (False, (True, True)), "u2": (True, (False, False)), "u3": (True, (True, True)), "u4": (False, (False, False)),
            "u5": (True, None), "u6": (None, (True, True))}
    for u, (r_pass, k) in plan.items():
        items.append(raw("A", u, passed=bool(r_pass)))
        items.append(raw("R", u, passed=bool(r_pass), void=r_pass is None))
        if k is None:
            items.append(raw("K", u, void=True, passed=False, released=False))
        else:
            items.append(raw("K", u, passed=k[0], released=k[1], k_attempts=[0] if k[1] else [40, 40, 40]))
    res = an.analyze(raws(*items))
    kr = res["primary"]["K_vs_R"]
    assert (kr["pairs"], kr["b_y_only"], kr["c_x_only"], kr["both"], kr["neither"]) == (4, 1, 1, 1, 1)
    assert kr["p_mcnemar_exact_two_sided"] == 1.0
    assert {e["unit"] for e in kr["excluded"]} == {"lcb_v1/u5", "lcb_v1/u6"}
    assert res["K_diagnostics"]["never_released"] == 2 and res["K_diagnostics"]["released"] == 3


def test_k_pass_requires_release():
    """K 的 pass 指標＝被放行 AND 隱藏全過：隱藏過了但沒放行（不該發生，但資料可能這樣）算沒過。"""
    r = an.row_of(raw("K", "u", passed=True, released=False))
    assert r["metric"] is False and r["pass"] is True and r["delivered"] is False
    r2 = an.row_of(raw("K", "u", passed=False, released=True))
    assert r2["metric"] is False and r2["wrong_delivery"] is True        # 放行了但隱藏沒過＝錯交
    r3 = an.row_of(raw("R", "u", passed=False, delivered=True))
    assert r3["wrong_delivery"] is True
    r4 = an.row_of(raw("R", "u", passed=False, delivered=False))
    assert r4["wrong_delivery"] is False


def test_c_vs_a_excludes_void_and_screening_phase():
    items = []
    for i in range(10):                                    # 10 題：C 過 A 沒過
        items += [raw("A", f"d{i}", bank="dabench", passed=False), raw("C", f"d{i}", bank="dabench", passed=True)]
    items += [raw("A", "v1", bank="dabench", void=True), raw("C", "v1", bank="dabench", passed=True)]      # A void：排除
    items += [raw("A", "s1", bank="dabench", phase="screen", passed=False)]                                # 篩選階段：不進主檢定
    res = an.analyze(raws(*items))
    ca = res["primary"]["C_vs_A"]
    assert (ca["pairs"], ca["b_y_only"], ca["c_x_only"]) == (10, 10, 0)
    assert ca["p_mcnemar_exact_two_sided"] == pytest.approx(2 / 1024)
    assert [e["unit"] for e in ca["excluded"]] == ["dabench/v1"]
    assert res["screening"]["dabench"] == {"n": 1, "void": 0, "pass": 0, "unsolved": ["s1"]}
    # Holm：兩個主要檢定的家族（K 對 R 沒有資料 ⇒ p＝1）
    assert res["primary"]["K_vs_R"]["pairs"] == 0 and res["primary"]["K_vs_R"]["p_mcnemar_exact_two_sided"] == 1.0
    assert res["primary"]["C_vs_A"]["p_holm"] == pytest.approx(2 * 2 / 1024)
    assert res["primary"]["significant_after_holm"] == {"K_vs_R": False, "C_vs_A": True}
    assert res["vs_A_descriptive"]["C_rescues_A_failure"] == 10 and "C_loses_A_success" not in res["vs_A_descriptive"]


def test_rerun_supersedes_void_and_is_listed():
    items = [raw("A", "t", void=True, void_reason="proxy_non200"), raw("A", "t", attempt=2, passed=True), raw("C", "t", passed=True),
             raw("C", "t2", void=True, void_reason="vacant_install_failed")]
    res = an.analyze(raws(*items))
    assert res["primary"]["C_vs_A"]["pairs"] == 1                                    # 用的是 attempt 2 的 A
    assert [x["reason"] for x in res["void_superseded_by_rerun"]] == ["proxy_non200"]
    assert [x["cell"] for x in res["void_final"]] == ["i1-C-lcb_v1-t2-s1"]


def test_arms_descriptive_and_audit():
    s_late = [{"n": 1, "ledger": {"calls": 3, "prompt_tokens": 50, "completion_tokens": 5}, "done_reason": "idle_final", "idle_s": 15.0,
               "late_write_after_done": True, "max_gap_after_final_s": 0.43, "submit_unconfirmed": True, "typed_ok": False}]
    items = [raw("A", "t1", passed=False, delivered=True), raw("C", "t1", passed=True, sessions=s_late, c_ok=True),
             raw("A", "t2", passed=True), raw("C", "t2", passed=True, c_ok=True)]
    res = an.analyze(raws(*items))
    assert res["arms"]["A"]["pass"] == 1 and res["arms"]["A"]["wrong_deliveries"] == 1
    assert res["arms"]["C"]["prompt_tokens"] == 50 + 100
    au = res["audit"]
    assert au["late_write_after_done"] == 1 and au["max_gap_after_final_s"] == 0.43 and au["submit_unconfirmed"] == 1 and au["typed_mismatch"] == 1
    assert res["C_diagnostics"]["c_arm_ok"] == 2
    md = an.markdown({k: v for k, v in res.items() if k != "_rows"})
    assert "McNemar" in md and "Holm" in md and "沒有量到差別" in md


def test_by_bank_and_role_sections():
    items = []
    for bank in ("lcb_v1", "dabench"):
        for i in range(3):
            items += [raw("A", f"{bank}{i}", bank=bank, passed=bool(i), role="a_failed" if bank == "lcb_v1" else "task_bank_rest"),
                      raw("C", f"{bank}{i}", bank=bank, passed=True, role="a_failed" if bank == "lcb_v1" else "task_bank_rest")]
    items += [raw("R", f"lcb_v1{i}", passed=bool(i)) for i in range(3)] + [raw("K", f"lcb_v1{i}", passed=True, released=True) for i in range(3)]
    res = an.analyze(raws(*items))
    assert res["by_bank"]["lcb_v1"]["K_vs_R"]["pairs"] == 3 and res["by_bank"]["dabench"]["K_vs_R"] is None
    assert res["by_bank"]["dabench"]["C_vs_A"]["pairs"] == 3 and res["by_bank"]["dabench"]["C_vs_A"]["b_y_only"] == 1
    assert set(res["by_role"]) == {"a_failed", "task_bank_rest"}


def test_load_from_dir_and_chunks_roundtrip(tmp_path):
    cells = tmp_path / "cells"
    items = [raw("A", "t1", passed=False), raw("C", "t1", passed=True)]
    for r in items:
        d = cells / r["cell"]
        d.mkdir(parents=True)
        (d / "meta.json").write_text(json.dumps(r["meta"]))
        (d / "score.json").write_text("junk line\n" + json.dumps(r["score"]) + "\n")
        (d / "DONE").write_text("x")
        (d / "agentlog").mkdir()
        (d / "agentlog" / "big.jsonl").write_text("x" * 1000)
    (cells / "_run_i1").mkdir()
    (cells / "_run_i1" / "ceiling_decision.json").write_text(json.dumps({"dropped_banks": ["databench"], "banks": {}}))
    raw_dir = an.load_from_dir(cells)
    assert set(raw_dir) == {r["cell"] for r in items} and raw_dir[items[0]["cell"]]["score"] == {"pass": False, "visible_pass": False}
    # 同一批格子放進兩個 chunk（chunk 之間格子不重複；_run_ 在最後一個）
    chunks = tmp_path / "chunks"
    chunks.mkdir()
    for i, name in enumerate(["i1-A-lcb_v1-t1-s1", "i1-C-lcb_v1-t1-s1"], 1):
        with tarfile.open(chunks / f"chunk_{i:04d}.tar.xz", "w:xz") as t:
            t.add(cells / name, arcname=f"cells/{name}")
            if i == 2:
                t.add(cells / "_run_i1", arcname="cells/_run_i1")
    raw_chunks, runrec = an.load_from_chunks(chunks)
    assert set(raw_chunks) == set(raw_dir)
    assert all(v["done"] and v["meta"] and v["score"] for v in raw_chunks.values())
    assert runrec["_run_i1"]["ceiling_decision.json"]["dropped_banks"] == ["databench"]
    res = an.analyze(raw_chunks, runrec)
    assert res["primary"]["C_vs_A"]["pairs"] == 1 and res["primary"]["C_vs_A"]["b_y_only"] == 1


def test_prefix_filter_separates_runs_on_the_same_vm():
    a = raw("A", "t1", passed=False)
    c = raw("C", "t1", passed=True)
    a["meta"]["prefix"], c["meta"]["prefix"] = "i1", "i1"
    a2, c2 = raw("A", "t1", passed=True), raw("C", "t1", passed=False)
    a2["cell"] = a2["meta"]["cell"] = "t9-A-lcb_v1-t1-s1"
    c2["cell"] = c2["meta"]["cell"] = "t9-C-lcb_v1-t1-s1"
    a2["meta"]["prefix"], c2["meta"]["prefix"] = "t9", "t9"
    allraw = {r["cell"]: r for r in (a, c, a2, c2)}
    only_i1 = an.analyze(allraw, None, "i1")["primary"]["C_vs_A"]
    assert (only_i1["pairs"], only_i1["b_y_only"], only_i1["c_x_only"]) == (1, 1, 0)
    only_t9 = an.analyze(allraw, None, "t9")["primary"]["C_vs_A"]
    assert (only_t9["pairs"], only_t9["b_y_only"], only_t9["c_x_only"]) == (1, 0, 1)


def test_cell_without_done_is_not_analyzed(tmp_path):
    r = raw("A", "t")
    r["done"] = False
    assert an.row_of(r) is None


# ── 本機同步與自動關機（假的 colab CLI）────────────────────────────────────────────────────────

FAKE_COLAB = """#!/usr/bin/env bash
cmd=$1; shift
case "$cmd" in
  download) shift 2; src="$FAKE_VM$1"; [ -f "$src" ] || exit 1; cp "$src" "$2";;
  stop) echo "$*" >> "$FAKE_VM/stopped.log";;
  *) exit 9;;
esac
"""


def fake_vm(tmp_path, *, chunks=2, done=True, corrupt=None, mirror_ok=False):
    vm = tmp_path / "vm"
    arc = vm / "srv" / "eval" / "archive"
    arc.mkdir(parents=True)
    rows = []
    for i in range(1, chunks + 1):
        data = f"payload-{i}".encode() * 50
        name = f"chunk_{i:04d}.tar.xz"
        (arc / name).write_bytes(data if corrupt != i else b"corrupt")
        rows.append(f"{name}\t{hashlib.sha256(data).hexdigest()}\t{len(data)}\t5\t20261001T000000Z")
    (arc / "MANIFEST.tsv").write_text("\n".join(rows) + "\n")
    if done:
        (vm / "srv" / "eval" / "DRIVER_DONE").write_text("t")
        (arc / "PACKER_DONE").write_text("t")
    if mirror_ok:
        (arc / "MIRROR_OK").write_text("{}")
    colab = tmp_path / "colab"
    colab.write_text(FAKE_COLAB)
    colab.chmod(0o755)
    return vm, colab


def run_sh(script, args, vm, colab, timeout=60):
    env = {**os.environ, "COLAB": str(colab), "FAKE_VM": str(vm)}
    # errors="replace"：腳本的錯誤訊息若含被截斷的多位元組字，測試要看到訊息本身，不是解碼例外。
    return subprocess.run(["bash", str(CI / script), *args], capture_output=True, text=True,
                          errors="replace", env=env, timeout=timeout)


def test_shell_scripts_brace_variables_before_non_ascii():
    # macOS 的 /bin/bash 是 3.2：`$pk（` 會把全形括號的第一個位元組吃進變數名，
    # `set -u` 之下當場 `pk\xef: unbound variable`（2026-10-01 macOS CI）。一律寫成 `${pk}（`。
    import re
    bad = []
    for f in sorted(CI.rglob("*.sh")):
        for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            if re.search(r"\$[A-Za-z_][A-Za-z0-9_]*[^\x00-\x7F]", line):
                bad.append(f"{f.relative_to(CI)}:{i}: {line.strip()}")
    assert not bad, "\n".join(bad)


def test_sync_pulls_verifies_and_reports_done(tmp_path):
    vm, colab = fake_vm(tmp_path)
    d = tmp_path / "local"
    r = run_sh("sync_i1001.sh", ["sess", str(d), "1", "--once"], vm, colab)
    assert r.returncode == 0 and "SYNC_ALL_DONE" in r.stdout, r.stdout + r.stderr
    verified = (d / "VERIFIED.tsv").read_text().splitlines()
    assert [x.split("\t")[0] for x in verified] == ["chunk_0001.tar.xz", "chunk_0002.tar.xz"]
    assert (d / "PACKER_DONE").exists() and (d / "DRIVER_DONE").exists() and not (d / "MIRROR_OK").exists()


def test_sync_rejects_a_chunk_whose_sha_differs_and_does_not_finish(tmp_path):
    vm, colab = fake_vm(tmp_path, corrupt=2)
    d = tmp_path / "local"
    r = run_sh("sync_i1001.sh", ["sess", str(d), "1", "--once"], vm, colab)
    assert r.returncode == 4 and "SYNC_ALL_DONE" not in r.stdout and "sha256 不符" in r.stdout
    assert [x.split("\t")[0] for x in (d / "VERIFIED.tsv").read_text().splitlines()] == ["chunk_0001.tar.xz"]
    assert not (d / "chunk_0002.tar.xz").exists()                               # 壞的刪掉等重拉


def test_sync_without_manifest_exits_3(tmp_path):
    vm, colab = fake_vm(tmp_path)
    (vm / "srv" / "eval" / "archive" / "MANIFEST.tsv").unlink()
    r = run_sh("sync_i1001.sh", ["sess", str(tmp_path / "local"), "1", "--once"], vm, colab)
    assert r.returncode == 3


def test_autostop_waits_for_everything_then_stops(tmp_path):
    # (a) 還沒 DRIVER_DONE ⇒ 不關
    vm, colab = fake_vm(tmp_path / "a", done=False)
    d = tmp_path / "a" / "local"
    run_sh("sync_i1001.sh", ["sess", str(d), "1", "--once"], vm, colab)
    r = run_sh("autostop_i1001.sh", ["sess", str(d), "--max-loops", "1", "--interval", "1"], vm, colab)
    assert r.returncode == 0 and not (vm / "stopped.log").exists() and "還在跑" in r.stdout
    # (b) 都收完、本機最後一個 chunk 驗過 ⇒ 關
    vm, colab = fake_vm(tmp_path / "b")
    d = tmp_path / "b" / "local"
    run_sh("sync_i1001.sh", ["sess", str(d), "1", "--once"], vm, colab)
    r = run_sh("autostop_i1001.sh", ["sess", str(d), "--max-loops", "1", "--interval", "1"], vm, colab)
    assert r.returncode == 0 and (vm / "stopped.log").read_text().strip() == "-s sess" and "STOPPED" in r.stdout
    # (c) 都收完、但本機最後一個 chunk 沒驗（壞的）⇒ 不關
    vm, colab = fake_vm(tmp_path / "c", corrupt=2)
    d = tmp_path / "c" / "local"
    run_sh("sync_i1001.sh", ["sess", str(d), "1", "--once"], vm, colab)
    r = run_sh("autostop_i1001.sh", ["sess", str(d), "--max-loops", "1", "--interval", "1"], vm, colab)
    assert not (vm / "stopped.log").exists() and "1 個 chunk 沒驗" in r.stdout


def test_autostop_drive_grace_only_with_mirror_ok(tmp_path):
    vm, colab = fake_vm(tmp_path / "x", corrupt=2, mirror_ok=False)
    d = tmp_path / "x" / "local"
    run_sh("sync_i1001.sh", ["sess", str(d), "1", "--once"], vm, colab)
    r = run_sh("autostop_i1001.sh", ["sess", str(d), "--max-loops", "3", "--interval", "1", "--drive-grace-s", "1"], vm, colab)
    assert not (vm / "stopped.log").exists()                                     # 沒有 MIRROR_OK：不敢靠 Drive
    vm, colab = fake_vm(tmp_path / "y", corrupt=2, mirror_ok=True)
    d = tmp_path / "y" / "local"
    run_sh("sync_i1001.sh", ["sess", str(d), "1", "--once"], vm, colab)
    r = run_sh("autostop_i1001.sh", ["sess", str(d), "--max-loops", "4", "--interval", "1", "--drive-grace-s", "1"], vm, colab)
    assert (vm / "stopped.log").exists() and "drive-only backup" in r.stdout and "WARN" in r.stdout
    # --dry-run 不呼叫 stop
    vm, colab = fake_vm(tmp_path / "z")
    d = tmp_path / "z" / "local"
    run_sh("sync_i1001.sh", ["sess", str(d), "1", "--once"], vm, colab)
    r = run_sh("autostop_i1001.sh", ["sess", str(d), "--max-loops", "1", "--dry-run"], vm, colab)
    assert "DRY-RUN" in r.stdout and not (vm / "stopped.log").exists()


# ── bundle 與重用檔 MANIFEST ──────────────────────────────────────────────────────────────────

def test_reused_files_match_manifest_and_a_tampered_copy_is_caught():
    m = json.loads((CI / "MANIFEST_REUSED.json").read_text())
    assert build_manifest.check(m) == []
    assert len(m["rows"]) == len(build_manifest.REUSED)
    # 逐字複本；唯一登記過的差異是 MODIFIED 裡的（改了什麼、為什麼都寫在 manifest 的 `modification`）
    assert all(r["verbatim"] for r in m["rows"] if r["source_checked"] and r["copy"] not in build_manifest.MODIFIED)
    assert {r["copy"] for r in m["rows"] if r.get("modification")} == set(build_manifest.MODIFIED)
    undeclared = json.loads(json.dumps(m))
    undeclared["rows"][0]["source_checked"], undeclared["rows"][0]["verbatim"] = True, False         # 負控制：沒登記的差異要被擋
    assert any("not declared" in x for x in build_manifest.check(undeclared))
    bad = json.loads(json.dumps(m))
    bad["rows"][0]["copy_sha256"] = "0" * 64
    assert any("sha256 differs" in x for x in build_manifest.check(bad))
    assert {x["campaign_file"] for x in m["replaced_not_reused"]} >= {"cell.sh", "driver.py", "feasibility.py", "analyze.py"}


def test_build_bundle_contents_and_checksums(tmp_path):
    staged = tmp_path / "staged"
    (staged / "dabench" / "t1").mkdir(parents=True)
    (staged / "tasks_index.json").write_text("[]")
    (staged / "MANIFEST.json").write_text("{}")
    (staged / "dabench" / "t1" / "instruction.txt").write_text("x")
    wheel = tmp_path / "vacant_network-0-py3-none-any.whl"
    wheel.write_bytes(b"wheel-bytes")
    out = tmp_path / "bundle.tgz"
    r = subprocess.run(["bash", str(CI / "build_bundle.sh"), str(staged), str(wheel), str(out)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    ex = tmp_path / "ex"
    ex.mkdir()
    with tarfile.open(out) as t:
        t.extractall(ex)
    for rel in ("bin/tui_cell.py", "bin/tui_lib.py", "bin/driver_i1001.py", "bin/plan_builder.py", "bin/vm_selfcheck.py", "bin/smoke_stub.py",
                "bin/stub_model.py", "bin/sandbox.sh", "bin/packer.py", "bin/deploy_i1001.sh", "bin/launch_i1001.sh", "bin/scorers/code_suite.py",
                "bridge/ops/eval/native_acceptance_bridge.py", "wheel/wheel.sha256", "staged/tasks_index.json", "staged/dabench/t1/instruction.txt"):
        assert (ex / rel).is_file(), rel
    assert not list(ex.rglob("__pycache__"))
    chk = subprocess.run(["sha256sum", "-c", "SHA256SUMS", "--quiet"], cwd=ex, capture_output=True, text=True)
    assert chk.returncode == 0, chk.stdout + chk.stderr
    assert (ex / "wheel" / "wheel.sha256").read_text().split()[0] == hashlib.sha256(b"wheel-bytes").hexdigest()


def test_shell_scripts_parse():
    for s in ("sync_i1001.sh", "autostop_i1001.sh", "build_bundle.sh", "vm/deploy_i1001.sh", "vm/launch_i1001.sh", "vm/sandbox.sh", "vm/cu_guard.sh"):
        assert subprocess.run(["bash", "-n", str(CI / s)], capture_output=True).returncode == 0, s


# ── tui_cell 的小函式（不碰系統）──────────────────────────────────────────────────────────────

def test_tui_cell_helpers(tmp_path):
    cfg = tui_cell.Cfg(eval_root=tmp_path / "e", proxy="http://127.0.0.1:18900")
    assert tui_cell.base_url(cfg, "tag.n1") == "http://127.0.0.1:18900/t/tag.n1/up/g4/think/off/api/v1"
    assert cfg.cells == tmp_path / "e" / "cells" and cfg.receivers == tmp_path / "e" / "receivers"
    box = tui_cell.Box(user="a000001", seq=7, C=tmp_path / "c")
    cmd = tui_cell.pane_command(cfg, box, "sessions-2", "http://b")
    assert "sandbox.sh" in cmd and "PI_OFFLINE=1" in cmd and "--session-dir /logs/agent/pi/sessions-2" in cmd and "exec pi" in cmd
    assert "--print" not in cmd                                              # 互動式：不是 `pi --print`
    assert "TERM=xterm-256color" in cmd and "OPENROUTER_API_KEY=sk-dummy" in cmd
    ws = tmp_path / "ws"
    (ws / "sub").mkdir(parents=True)
    (ws / "a.txt").write_text("a")
    (ws / "sub" / "b.txt").write_text("b")
    lines = tui_cell.tree_sha_lines(ws).splitlines()
    assert lines == sorted(lines, key=lambda x: x.split("  ", 1)[1]) and len(lines) == 2
    before = tmp_path / "before.sha256"
    before.write_text(lines[0].split("  ")[0] + "  " + lines[0].split("  ")[1] + "\n")
    L = tmp_path / "L"
    L.mkdir()
    (ws / "a.txt").write_text("changed")
    tui_cell.save_app_final(ws, before, L)
    kept = sorted(p.relative_to(L / "app_final").as_posix() for p in (L / "app_final").rglob("*") if p.is_file())
    assert "a.txt" in kept and "sub/b.txt" in kept
    assert tui_cell.parse_score(tmp_path / "nope") is None
    (tmp_path / "s.json").write_text("log\n{\"pass\": true}\n")
    assert tui_cell.parse_score(tmp_path / "s.json") == {"pass": True}
    (tmp_path / "s2.json").write_text("{\"nopass\": 1}\n")
    assert tui_cell.parse_score(tmp_path / "s2.json") is None
