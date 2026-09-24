"""忠實度：**分身演的那件事，要與 Vacant 真做的那件事同形**（v2，2026-09-19；v3，2026-09-24）。

人類的要求逐字：「可能現在的數位分身的邏輯跟我們真實的不太一樣，但就改好來，
改成最終版 VACANT 的邏輯忠實呈現。」對照表與逐條理由在
`decisions/DECISION_20260919_TWIN_V2_FIDELITY.md`。

v3（2026-09-24「刪事後推導，留錄影重播」）：電視事件只剩一個產生者
`live_events.Folder`（吃 `vacant.lifecycle/1`）。這一組原本拿 `to_events` 的
`events_for_cell(pack 的一格)` 改欄位來測；現在改成**手搓一段合乎 lifecycle 契約的
事件流**餵給 `Folder`——手搓的那一段自己先過 `lifecycle.validate_stream`，
不然測的就是一份 Vacant 永遠吐不出來的東西。

`tests/test_twin_events.py` 守的是「生產端不准多說一句話」；這一組守的是
**生產端不准少說、也不准說成別的形狀**：

  · `accepted` 是三值（null ＝ 沒量），不准 `bool()` 壓成兩值
  · `blocked_by` 由 `stop_reason` 推，不准寫死一個字
  · **重試迴圈要看得見**——閘門 → 回饋 → 再 spawn 一次，每一次各說一次話
  · `revised` 的 `reviser` 是**同一個 worker**，不是別人
  · 這條路上不存在的層（評審、抽樣稽核）一個事件都不發
  · 證據等級是**推**出來的（`requests_seen == 0` ⇒ L-none，宣告蓋不過去）
  · `working`：每一通經過中介的模型呼叫一筆，`calls_so_far` 是正整數
  · `mode`：每一筆都說自己是 live 還是 replay

後半段（`pack`）守的是**收據頁**那一份資料包——它不再產生電視事件，
但觀眾拿它在自己的瀏覽器裡重驗簽章鏈，形狀照樣要對。
"""
import json
import re
import pathlib
import sys

import pytest

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from ops.exhibit.twin import build_viewer, pack as packlib  # noqa: E402
from ops.exhibit.twin import live_events as le  # noqa: E402
from ops.exhibit.twin import tv_contract as tv  # noqa: E402
from vacant_network.vrun import lifecycle  # noqa: E402

VIEWER = REPO / "examples" / "twin_viewer.html"
PACK = REPO / "ops" / "exhibit" / "twin" / "twin_pack.json"


# ── 手搓一段合乎 lifecycle 契約的事件流 ─────────────────────────────────
class Run:
    """一跑的 lifecycle 事件。欄位照 `lifecycle.FIELDS` 一個不少。"""

    T = [1_790_000_000_000]

    def __init__(self, out: list, *, arm="RUN-ON", cell="KAL-52__s1_01_addmul__held",
                 resident="KAL-52", retry="revise", declared="", run_id=None):
        self.out, self.arm, self.cell = out, arm, cell
        self.rid = run_id or f"{cell}:{arm}"
        self.seq = 0
        self.retry = retry if arm == "RUN-ON" else "none"
        self.ev("run_started", vacant=int(arm == "RUN-ON"), retry=self.retry,
                max_attempts=3, feedback_into="file", ws_start_sha256="a" * 64,
                caller={"cell_id": cell, "resident": resident,
                        "task_id": "s1_01_addmul", "stratum": cell.rsplit("__", 1)[-1],
                        "prompt": "把兩個數字加起來、乘起來。",
                        "declared_evidence": declared})

    def ev(self, type_, **kw):
        self.seq += 1
        Run.T[0] += 7
        self.out.append({"schema": lifecycle.SCHEMA, "type": type_, "run_id": self.rid,
                         "seq": self.seq, "ts_ms": Run.T[0], "task_id": "s1_01_addmul:held",
                         "arm": self.arm, **kw})
        return self

    def attempt(self, n, *, fb_bytes=0, via="file"):
        return self.ev("attempt_started", attempt=n, max_attempts=3, reset=None,
                       feedback_delivery=via, feedback_in_prompt_bytes=fb_bytes)

    def call(self, n):
        return self.ev("model_call", attempt=n, n_total=None, wire="openai",
                       blocked=False, error=False, elapsed_s=1.5)

    def exited(self, n, *, seen=0, timed_out=False):
        return self.ev("agent_exited", attempt=n, agent_rc=0, timed_out=timed_out,
                       agent_wall_s=3.0, requests_seen=seen, wire_quiesced=True)

    def gate(self, n, passed):
        return self.ev("gate_ran", attempt=n, passed=passed, n_passed=2 if passed else 1,
                       n_tests=2, failed_case=None if passed else "check_02_mul",
                       verdict_sha256="b" * 64)

    def feedback(self, n, *, via="file", nbytes=512):
        return self.ev("feedback_ready", attempt=n, next_attempt=n + 1, retry=self.retry,
                       delivery=via, bytes=nbytes, text_sha256="c" * 64)

    def end(self, *, stop, accepted, seen=0, used=1, infra_void=None, head="d" * 64):
        on = self.arm == "RUN-ON" and not infra_void
        return self.ev("run_ended", stop_reason=stop, accepted=accepted,
                       refused=accepted is False, infra_void=infra_void,
                       attempts_used=used, requests_seen=seen, count_semantics="exact",
                       ws_end_sha256="e" * 64, verdict_sha256="f" * 64 if on else None,
                       has_receipt=on, verdict_hash=head if on else None)


def one_attempt(stop="visible_fail", accepted=False, *, seen=0, declared="",
                passed=None, arm="RUN-ON"):
    out: list = []
    r = Run(out, arm=arm, declared=declared).attempt(1)
    for k in range(seen):
        r.call(1)
    r.exited(1, seen=seen)
    if passed is not None and arm == "RUN-ON":
        r.gate(1, passed)
    r.end(stop=stop, accepted=accepted, seen=seen)
    return out


def two_attempts(*, via="prompt"):
    """第 1 次沒過 ⇒ 回饋 ⇒ 第 2 次過。"""
    out: list = []
    r = Run(out).attempt(1).call(1).exited(1, seen=1).gate(1, False)
    r.feedback(1, via=via).attempt(2, fb_bytes=512, via=via).call(2).call(2)
    r.exited(2, seen=3).gate(2, True).end(stop="visible_pass", accepted=True,
                                          seen=3, used=2)
    Run(out, arm="RUN-OFF").attempt(1).call(1).exited(1, seen=1) \
        .end(stop="ungated", accepted=None, seen=1)
    return out


def fold(stream, mode=tv.MODE_LIVE):
    assert lifecycle.validate_stream(stream) == [], "手搓的事件流自己就不合契約"
    return le.fold(stream, verify_url="/r/{cell}", mode=mode)


def test_the_hand_made_streams_are_contract_true():
    """負控制的前提：手搓的東西是 Vacant **吐得出來**的形狀。"""
    for s in (one_attempt(), two_attempts(), one_attempt("ungated", None)):
        assert lifecycle.validate_stream(s) == []
    # 而 validate_stream 真的會咬：拿掉一個必填欄位就紅
    s = two_attempts()
    s[1].pop("feedback_delivery")
    assert lifecycle.validate_stream(s)


# ── 一、「沒量」不可以長成「量到沒過」 ────────────────────────────

def test_accepted_is_three_valued_not_boolean():
    """`--allow-no-suite` 那一格 `accepted` 是 **null（沒量）**，不是 false。"""
    evs = fold(one_attempt(stop="ungated", accepted=None))
    v = [e for e in evs if e["type"] == "verdict"][0]
    assert v["accepted"] is None, "「沒量」被壓成了「量到沒過」"
    assert v["blocked_by"] is None, "沒量不是被擋下"
    assert v["stop_reason"] == "ungated"


def test_validate_rejects_ungated_with_a_boolean_accepted():
    evs = fold(one_attempt(stop="ungated", accepted=None))
    v = next(e for e in evs if e["type"] == "verdict")
    v["accepted"] = False
    assert tv.validate(evs), "「沒量卻給了布林」必須被擋下"


# ── 二、四種收尾不可以講成一件事 ──────────────────────────────────

def test_blocked_by_is_derived_from_stop_reason_not_hardcoded():
    got = {}
    for stop, acc in (("visible_fail", False), ("attempts_exhausted", False),
                      ("no_suite", False), ("visible_pass", True)):
        evs = fold(one_attempt(stop=stop, accepted=acc))
        v = [e for e in evs if e["type"] == "verdict"][0]
        got[stop] = v["blocked_by"]
        assert v["stop_reason"] == stop, "壓縮過的那個字旁邊要留著原始理由"
    assert got["visible_pass"] is None
    assert got["visible_fail"] == got["attempts_exhausted"] == got["no_suite"] == "gate"


def test_blocked_by_is_never_review():
    """`review` 永遠不該出現：這條路上沒有評審層。"""
    assert "review" not in set(tv.BLOCKED_BY.values())
    evs = fold(one_attempt())
    next(e for e in evs if e["type"] == "verdict")["blocked_by"] = "review"
    assert tv.validate(evs)


# ── 三、V1 的機制本體要看得見 ─────────────────────────────────────

def test_retry_loop_is_visible_one_gate_per_attempt():
    """**閘門 → 回饋 → 再 spawn 一次**，每一次都要自己說一次話。"""
    evs = fold(two_attempts())
    on = [e for e in evs if e.get("arm") == tv.ARM_ON]
    gates = [e for e in on if e["type"] == "gate_ran"]
    drafts = [e for e in on if e["type"] == "draft_done"]
    revised = [e for e in on if e["type"] == "revised"]
    assert [g["passed"] for g in gates] == [False, True], "兩次閘門要各說各的"
    assert [g["attempt"] for g in gates] == [1, 2]
    assert [d["attempt"] for d in drafts] == [1, 2]
    assert drafts[0]["feedback_bytes"] == 0, \
        "第 1 次的回饋位元組恆為 0 ＝ 與「沒有 Vacant」時逐位元相同"
    assert drafts[1]["feedback_bytes"] == 512
    assert drafts[1]["feedback_delivery"] == "prompt" and drafts[1]["feedback_note"]
    assert len(revised) == 1, "沒過而且還有額度 ⇒ 剛好一次重改"
    assert tv.validate(evs) == []


def test_file_feedback_says_where_it_went():
    """`file` 管道底下 `feedback_bytes` 每次都 0——沒有那句說明，那個 0 會說謊。"""
    evs = fold(two_attempts(via="file"))
    d2 = [e for e in evs if e["type"] == "draft_done" and e.get("arm") == tv.ARM_ON][1]
    assert d2["feedback_delivery"] == "file"
    assert "VACANT_FEEDBACK.md" in d2["feedback_note"]


def test_reviser_is_the_same_worker_never_someone_else():
    evs = fold(two_attempts())
    rv = [e for e in evs if e["type"] == "revised"]
    assert rv and all(e["reviser"] == "KAL-52" for e in rv)
    assert "VACANT_FEEDBACK" in rv[0]["transition"], "哪一條臂要逐字寫出來"
    # 重試臂在 `retry_arm`，`arm` 專職分 ON／OFF。
    assert rv[0]["retry_arm"] == "revise"
    assert rv[0]["arm"] == tv.ARM_ON, "重改是 ON 臂的事，OFF 臂沒有迴圈"


def test_resample_and_revise_do_not_say_the_same_thing():
    """兩條臂的差別**就是**實驗處理本身，不可以共用一句話。"""
    assert tv.TRANSITION["revise"] != tv.TRANSITION["resample"]
    assert "重置" in tv.TRANSITION["resample"]
    assert "保留工作區" in tv.TRANSITION["revise"]


# ── 三之二、`working`：過程中每一通都有一筆 ─────────────────────────

def test_every_model_call_becomes_one_working_event():
    evs = fold(two_attempts())
    w = [e for e in evs if e["type"] == "working"]
    on = [e for e in w if e["arm"] == tv.ARM_ON]
    off = [e for e in w if e["arm"] == tv.ARM_OFF]
    # ON：第 1 次 1 通、第 2 次 2 通 ⇒ 累計 1,2,3（跨嘗試累計，是這一跑的通數）
    assert [e["calls_so_far"] for e in on] == [1, 2, 3]
    assert [e["attempt"] for e in on] == [1, 2, 2]
    # OFF 那一跑自己從 1 數起
    assert [e["calls_so_far"] for e in off] == [1]
    assert all(e["worker"] == "KAL-52" for e in w)
    # 最後一筆 working 的通數＝那一次 draft_done 的 calls_used（都是 requests_seen 的語意）
    d_on = [e for e in evs if e["type"] == "draft_done" and e.get("arm") == tv.ARM_ON]
    assert on[-1]["calls_so_far"] == d_on[-1]["calls_used"]
    # 不帶內容（lifecycle 誠實邊界 3）
    for e in w:
        assert not {"prompt", "body", "request", "response", "messages"} & set(e)


def test_validate_bites_on_a_bad_working_event():
    base = {"type": "working", "ts": "2026-09-24T00:00:00.000+00:00", "task_id": "x",
            "mode": "live", "arm": "ON", "worker": "KAL-52", "attempt": 1,
            "calls_so_far": 1}
    # 單獨一筆 working 是「還在跑」的片段 ⇒ 不要求收尾，其餘規則照咬
    def check(e):
        return tv.validate([e], require_settled=False)
    assert check(base) == []
    for bad in ({"calls_so_far": 0}, {"calls_so_far": True}, {"calls_so_far": "1"},
                {"arm": "RUN-ON"}, {"arm": "revise"}):
        assert check({**base, **bad}), bad
    for k in ("arm", "worker", "attempt", "calls_so_far"):
        assert check({kk: v for kk, v in base.items() if kk != k}), k


# ── 三之三、`mode`：畫面上要講得出是不是重播 ─────────────────────────

def test_every_event_carries_the_mode_it_was_folded_with():
    for mode in tv.MODES:
        evs = fold(two_attempts(), mode=mode)
        assert evs and {e["mode"] for e in evs} == {mode}


def test_validate_rejects_missing_or_unknown_mode():
    evs = fold(two_attempts())
    evs[0].pop("mode")
    assert tv.validate(evs)
    evs = fold(two_attempts())
    evs[0]["mode"] = "simulation"
    assert tv.validate(evs)


# ── 四、不存在的層，一個事件都不發 ────────────────────────────────

def test_no_event_invents_a_layer_that_does_not_exist():
    kinds = {e["type"] for e in fold(two_attempts())}
    for never in tv.NEVER:
        assert never not in kinds, never
    # lifecycle 裡沒有事後稽核 ⇒ 光吃 lifecycle 轉不出 postaudit（它只從分身的旁註來）；
    # counters 是播放端（serve_twin）數的，Folder 自己不發。
    assert "postaudit" not in kinds and "counters" not in kinds


def test_validate_rejects_the_layers_that_do_not_exist():
    evs = fold(two_attempts())
    for never in tv.NEVER:
        broken = evs + [{"type": never, "ts": "9999", "task_id": "x", "mode": "live"}]
        assert tv.validate(broken), never
    # 2026-09-24「分身側自己記一份補回」：postaudit／counters 回到白名單，但各有自己的規則
    assert "postaudit" in tv.EMITTED and "counters" in tv.EMITTED
    bare_pa = {"type": "postaudit", "ts": "9999", "task_id": "x", "mode": "live",
               "arm": "OFF"}
    assert tv.validate(evs + [bare_pa]), "沒帶三個旗標的 postaudit 要被擋"
    for k in tv.COUNTERS_NEVER:
        ctr = {"type": "counters", "ts": "9999", "task_id": "-", "mode": "live", k: 0}
        assert tv.validate(evs + [ctr]), k


def test_routed_says_out_loud_that_there_is_no_routing_layer():
    routed = [e for e in fold(two_attempts()) if e["type"] == "routed"]
    assert routed
    for e in routed:
        assert e["basis"] == "random"
        assert "沒有路由層" in e["basis_note"], \
            "電視畫面上寫著「依信譽紀錄路由」——事件要帶著反證"


# ── 五、證據等級要跟著走（展場版鐵律 5）────────────────────────────

def test_evidence_is_derived_on_the_verdict_never_declared_at_open():
    """開題那一刻推不出來 ⇒ `task_opened.evidence` 是 null（不寫宣告值）。
    跑完才推：`requests_seen == 0` 一律 L-none，宣告蓋不過去。"""
    zero = fold(one_attempt(seen=0, declared="L-real"))
    real = fold(one_attempt(seen=3, declared="L-real"))
    unk = fold(one_attempt(seen=3, declared=""))
    for evs, want in ((zero, "L-none"), (real, "L-real"), (unk, "L-unknown")):
        assert [e["evidence"] for e in evs if e["type"] == "task_opened"] == [None]
        v = [e for e in evs if e["type"] == "verdict"][0]
        assert v["evidence"] == want
        assert v["evidence_note"], "標籤要附得出理由"


def test_receipt_carries_both_hashes_separately():
    """收據 hash 與題面 hash 是兩個東西，不准共用一個欄位。"""
    evs = fold(two_attempts())
    prompts = {e["task_id"]: e["prompt_sha256"]
               for e in evs if e["type"] == "task_opened"}
    recs = [e for e in evs if e["type"] == "receipt"]
    assert recs
    for e in recs:
        assert e["prompt_sha256"] == prompts[e["task_id"]]
        assert e["sha256"] == e["chain_head"] == "d" * 64
        assert e["sha256"] != e["prompt_sha256"], "兩個 hash 不該相等"


def test_receipt_verify_url_is_per_cell():
    assert tv.cell_verify_url("/r/{cell}", "A__t__held") == "/r/A__t__held"
    # 沒有佔位符就原樣用（離線 `file://` 直開整頁那種用法仍然成立）
    assert tv.cell_verify_url("twin_viewer.html", "A") == "twin_viewer.html"
    evs = fold(two_attempts())
    assert [e["verify_url"] for e in evs if e["type"] == "receipt"] == \
        ["/r/KAL-52__s1_01_addmul__held"]


# ── 五之二、被砍掉的一次 ≠ 自己跑完沒過 ─────────────────────────────

def test_a_killed_attempt_is_distinguishable_from_one_that_just_failed():
    """兩者的 `stop_reason` 都是 `visible_fail`。展場上是兩個故事：
    「它做不出來」與「**我們沒等它**」。"""
    out: list = []
    Run(out).attempt(1).exited(1, timed_out=True).gate(1, False) \
        .end(stop="visible_fail", accepted=False)
    killed = [e for e in fold(out) if e["type"] == "draft_done"][0]
    plain = [e for e in fold(one_attempt(passed=False)) if e["type"] == "draft_done"][0]
    assert killed["timed_out"] is True and killed["timed_out_note"]
    assert plain["timed_out"] is False and plain["timed_out_note"] == ""


# ── 五之三、infra_void 也要收尾 ─────────────────────────────────────

def test_infra_void_still_reaches_a_verdict_and_is_not_a_refusal():
    """鐵律 3：「沒量到」≠「量到 0」。但開了題就要收尾，否則電視佇列卡死。"""
    out: list = []
    Run(out).attempt(1).end(stop="visible_fail", accepted=None,
                            infra_void="agent_spawn_failed")
    evs = fold(out)
    v = [e for e in evs if e["type"] == "verdict"]
    assert len(v) == 1
    assert v[0]["stop_reason"] == "infra_void" and v[0]["accepted"] is None
    assert v[0]["blocked_by"] is None, "基建壞掉不是被擋下"
    assert not [e for e in evs if e["type"] == "receipt"]
    assert tv.validate(evs) == []


def test_every_arm_must_settle_not_just_every_cell():
    """ON 那一跑斷在半路（沒有 run_ended）、OFF 那一跑完整——逐格看「有 verdict」，
    實際上 ON 那一串永遠收不了尾。契約自檢要**逐臂**抓。"""
    out: list = []
    Run(out).attempt(1).exited(1)                       # ON：沒有 run_ended
    Run(out, arm="RUN-OFF").attempt(1).exited(1).end(stop="ungated", accepted=None)
    evs = fold(out)
    assert [e["arm"] for e in evs if e["type"] == "verdict"] == [tv.ARM_OFF]
    bad = tv.validate(evs)
    assert bad and any("（ON）" in b for b in bad)


# ── 六、OFF 臂：沒有閘門、沒有收據、沒有裁決 ─────────────────────────

def test_off_arm_emits_no_gate_and_no_receipt():
    evs = fold(two_attempts())
    off = [e for e in evs if e.get("arm") == tv.ARM_OFF]
    assert [e["type"] for e in off] == ["working", "draft_done", "verdict"]
    assert off[-1]["accepted"] is None and off[-1]["has_receipt"] is False


def test_folder_drops_an_off_gate_even_if_lifecycle_let_one_through():
    """第二道網：lifecycle 的 validate 擋 OFF 的 gate_ran；Folder 自己也丟。"""
    f = le.Folder(verify_url="")
    out: list = []
    Run(out, arm="RUN-OFF").attempt(1).exited(1)
    for e in out:
        f.feed(e)
    fake = {**out[-1], "type": "gate_ran", "seq": 99, "attempt": 1, "passed": False}
    assert f.feed(fake) == []


def test_validate_rejects_an_off_arm_that_claims_a_gate_or_a_receipt():
    """負控制：把 OFF 臂寫成有閘門／有收據／有裁決，契約自檢要咬人。"""
    evs = fold(two_attempts())
    for bad_ev in (
        {"type": "gate_ran", "ts": "9999", "task_id": "x", "mode": "live",
         "arm": tv.ARM_OFF, "passed": False},
        {"type": "receipt", "ts": "9999", "task_id": "x", "mode": "live",
         "arm": tv.ARM_OFF, "sha256": "deadbeef"},
        {"type": "verdict", "ts": "9999", "task_id": "x", "mode": "live",
         "arm": tv.ARM_OFF, "accepted": False, "meets_demand": None},
    ):
        assert tv.validate(evs + [bad_ev]), bad_ev["type"]


def test_same_millisecond_events_do_not_collide_on_the_tv_key():
    """兩筆 lifecycle 同一毫秒 ⇒ 電視事件的 ts 仍然嚴格遞增（去重鍵不撞）。"""
    s = two_attempts()
    for e in s:
        e["ts_ms"] = 1_790_000_000_000
    evs = fold(s)
    keys = [tv.dedup_key(e) for e in evs]
    assert len(set(keys)) == len(keys)
    assert [e["ts"] for e in evs] == sorted(e["ts"] for e in evs)


# ══ 收據頁那一份資料包（`twin_pack.json`）：不產事件，但觀眾拿它重驗 ══════

@pytest.fixture(scope="module")
def pack():
    return json.loads(PACK.read_text(encoding="utf-8"))


def test_pack_visible_is_the_last_attempt_not_the_first(pack):
    """一格「第 1 次沒過、第 3 次過」的 run，不可以在資料上長成
    「驗收沒過 ＋ 收下了」——那正是「收下了，其實漏出」那句話的形狀。
    """
    for c in pack["cells"]:
        assert c["visible"]["attempt"] == c["attempts_used"], c["cell_id"]
        if c["attempts"]:
            last = c["attempts"][-1]
            assert last["visible"]["all_pass"] == c["visible"]["all_pass"], \
                c["cell_id"]
            if c["accepted"] is not None:
                assert bool(c["accepted"]) == bool(c["visible"]["all_pass"]), \
                    c["cell_id"]


def test_pack_carries_every_attempt_not_just_the_count(pack):
    for c in pack["cells"]:
        assert len(c["attempts"]) == c["attempts_used"], c["cell_id"]
        for a in c["attempts"]:
            assert "requests_seen" in a and "feedback_in_prompt_bytes" in a


def test_pack_has_no_absolute_build_paths():
    """建置這台機器的目錄結構不准印上展場螢幕。"""
    raw = PACK.read_text(encoding="utf-8")
    for bad in ("/Users/", "/home/", "/private/var/", "worktrees/agent-"):
        assert bad not in raw, f"{bad} 漏進 twin_pack.json"
    html = VIEWER.read_text(encoding="utf-8")
    embedded = build_viewer.extract_block(html, "twin-pack")
    for bad in ("/Users/", "/home/", "worktrees/agent-"):
        assert bad not in embedded, f"{bad} 漏進展件頁面"


def test_redaction_survives_a_moved_run_dir(tmp_path):
    """路徑清洗必須與「現在在哪」無關——這正是漏出來的那一條。"""
    msg = ("ImportError: cannot import name 'mul' from 'solution' "
           "(/Users/someone/elsewhere/runs/x/_frozen_RUN-ON/solution.py)")
    out = packlib.redact_paths(msg, tmp_path / "a_completely_different_dir")
    assert "/Users/" not in out
    assert "<凍結快照>" in out
    assert "cannot import name 'mul'" in out, "訊息本體一個字都不准少"
    off = msg.replace("_frozen_RUN-ON", "_frozen_RUN-OFF")
    out2 = packlib.redact_paths(off, tmp_path / "elsewhere")
    assert "/Users/" not in out2, "OFF 臂的路徑沒有被清掉"


def test_the_counterfactual_arm_was_actually_run(pack):
    """展場主視覺的那句「同題關掉這層」，底下要真的有一跑。"""
    offs = [c.get("off") for c in pack["cells"]]
    assert all(o and o.get("ran") for o in offs), "有格子沒有 OFF 臂"
    for c in pack["cells"]:
        o = c["off"]
        if o.get("infra_void"):
            continue
        assert o["requests_seen"] > 0, \
            f"{c['cell_id']}：OFF 臂沒有任何一通被中介到，證明不了它真的跑過"
        assert o["same_start_as_on"], \
            f"{c['cell_id']}：兩臂的起點不同 ⇒「唯一差別是那一層」這句話說不出口"


def test_the_off_arm_has_no_verdict_and_no_receipt(pack):
    for c in pack["cells"]:
        o = c["off"]
        assert o["accepted"] is None, c["cell_id"]
        assert o["has_receipt"] is False, c["cell_id"]
        if not o.get("infra_void"):
            assert o["stop_reason"] == "ungated", c["cell_id"]


def test_the_post_hoc_audit_never_pretends_to_be_a_verdict(pack):
    """事後稽核要自己說它是事後的，否則它與當場的裁決在資料上分不開。

    ⚠ 2026-09-24 起它**不上電視**（lifecycle 裡沒有它；見 `live_events` 誠實邊界 3），
      只留在資料包裡給收據頁。電視那一側的判準在
      `test_no_event_invents_a_layer_that_does_not_exist`。
    """
    for c in pack["cells"]:
        pa = (c["off"] or {}).get("postaudit")
        if pa is None:
            continue
        assert pa["when"] == "after_the_run"
        assert pa["is_verdict"] is False and pa["signed"] is False
        assert "事後" in pa["note"]


def test_evidence_level_is_derived_per_cell_never_declared(pack):
    for c in pack["cells"]:
        assert c["evidence"] == packlib.evidence_level(
            requests_seen=c["requests_seen"],
            declared=c["declared_evidence"]), c["cell_id"]
        if c["requests_seen"] == 0:
            assert c["evidence"] == "L-none", c["cell_id"]
    assert packlib.evidence_level(requests_seen=0, declared="L-real") == "L-none"
    assert packlib.evidence_level(requests_seen=3, declared="") == "L-unknown"


def test_the_withheld_name_really_is_withheld(pack):
    """展件的整個故事都壓在這一句上：**客戶要的那個名字沒寫在需求裡**。

    ⚠ 只讀 `TASK.md`／`TASK_explicit.md` 與 `meta.json`，
      **不讀 `hidden/` 一個 byte**（V/GT 紅線）。
    """
    bank = REPO / "ops" / "gain" / "r535" / "bank"
    seen = 0
    for task_id in sorted({c["task_id"] for c in pack["cells"]}):
        d = bank / task_id
        if not d.is_dir():
            pytest.skip(f"題庫不在這個工作樹裡：{task_id}")
        meta = json.loads((d / "meta.json").read_text(encoding="utf-8"))
        held = (d / "TASK.md").read_text(encoding="utf-8")
        explicit = (d / "TASK_explicit.md").read_text(encoding="utf-8")
        for name in meta["required_names"]:
            word = re.compile(r"\b%s\b" % re.escape(name))
            assert not word.search(held), \
                f"{task_id}：扣住版的題面裡其實寫了 {name!r}，那一格的故事是假的"
            assert word.search(explicit), \
                f"{task_id}：寫明版的題面裡反而沒有 {name!r}"
            seen += 1
    assert seen, "一個名字都沒檢查到"


def test_pack_marks_killed_attempts(pack):
    """資料包那一側也要分得開「被砍掉」與「自己沒過」（收據頁會印）。"""
    for c in pack["cells"]:
        assert "any_attempt_timed_out" in c, c["cell_id"]
        for a in c["attempts"]:
            assert "agent_timed_out" in a, c["cell_id"]
        assert c["any_attempt_timed_out"] == any(
            a["agent_timed_out"] for a in c["attempts"]), c["cell_id"]
    # 負控制：這一批真的有被砍掉的格，這條測試才不是空轉
    assert any(c["any_attempt_timed_out"] for c in pack["cells"]), \
        "這一批沒有任何一次被砍掉——若屬實請改掉這條測試的敘述"


def test_infra_void_cells_are_marked_not_counted_as_refusals(pack):
    """鐵律 3：跑掛的格**不進 `cells`**，進 `void_cells`。"""
    assert "void_cells" in pack, "資料包要說得出哪些格跑掛了"
    for c in pack["cells"]:
        assert not c.get("infra_void"), c["cell_id"]
    for v in pack["void_cells"]:
        assert v["infra_void"] or v["stop_reason"], v["cell_id"]
    assert pack["void"] == len(pack["void_cells"])


def test_delivery_with_a_build_path_is_redacted_and_marked_not_recomputable(tmp_path):
    """`revise` 寫的 `VACANT_FEEDBACK.md` 逐字抄了驗收失敗訊息，裡面有凍結快照的絕對路徑
    （2026-09-24 配對收據時抓到）。遮掉之後位元組就不是 sha256 那一份了 ⇒
    **照實標成不可重算**，不准用遮過的內容算一個看起來很像的雜湊。"""
    run_dir = tmp_path / "runs" / "X"
    frozen = run_dir / "_frozen_RUN-ON"
    frozen.mkdir(parents=True)
    leak = "/private/var/folders/zz/T/tmpabc/runs/X/_frozen_RUN-ON/solution.py"
    (frozen / "VACANT_FEEDBACK.md").write_text(f"ImportError ({leak})\n", encoding="utf-8")
    (frozen / "solution.py").write_text("def f():\n    return 1\n", encoding="utf-8")
    d = packlib.delivery_of(run_dir, "root", None)
    fb = next(f for f in d["files"] if f["path"] == "VACANT_FEEDBACK.md")
    assert "/private/var/" not in fb["text"] and "<凍結快照>" in fb["text"]
    assert d["recomputable"] is False and "佔位符" in fb["note"]
    sol = next(f for f in d["files"] if f["path"] == "solution.py")
    assert sol["text"] == "def f():\n    return 1\n" and "note" not in sol
    # 正控制：沒有路徑的交付物照樣可重算
    (frozen / "VACANT_FEEDBACK.md").unlink()
    assert packlib.delivery_of(run_dir, "root", None)["recomputable"] is True
