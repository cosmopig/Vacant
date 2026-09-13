"""peerexec 的確定性測試——不碰模型、不碰 runs/。

每一條都對應 `vacant/peerexec.py` 的一句主張。主張與測試一一對照，
「機制講得出來但測不出來」的東西不准留在 docstring 裡。

⚠ 沙箱：§1–§7 一行沙箱都不碰（探針是注入的替身）。§8（R449 §四-3 的套件量具閘）
  裡有四條**會跑本機沙箱**——量具的主張是「這套驗收擋不擋得住已知壞草稿」，
  用假 runner 測只會測到假 runner。零模型呼叫、零 API 這一條不變。
"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault(
    "VACANT_EVALPLUS_PATH", ".vacant-private/evalplus/MbppPlus-v0.2.0.jsonl.gz"
)

from vacant.identity import Identity, PublicIdentity  # noqa: E402
from vacant.logbook import LogEntry, Logbook  # noqa: E402
from vacant import suitespec as ss  # noqa: E402
from vacant.peerexec import (Attestation, Executor, GaugeRecord,  # noqa: E402
                             ProbeResult, SuiteGaugeError, as_suite_spec,
                             challenge_rerun,
                             commit_suite, commit_suite_with_gauge, form_verdict,
                             gauged_suite_index, open_suite, roster_of,
                             run_suite_gauge, select_by_quorum, sha256_hex,
                             suite_gate, verify_attestation,
                             verify_executor_chain)
from vacant.suitegauge import broken_stub  # noqa: E402
from vacant.suitespec import SuiteSpecError  # noqa: E402

TS = 1_700_000_000_000

#: round452：套件是**資料**。§1–§7 的替身探針不看碼，但每一次 `attest` 都要帶一份
#: spec——因為 `suite_sha256` 現在算在 spec 上，而執行器是拿 spec 自己渲染的。
SPEC = ss.validate({"v": 1, "dialect": "mbpp", "entry_point": "f",
                    "tests": [{"args": "[1]", "expected": "2"},
                              {"args": "[2]", "expected": "3"}],
                    "cmp": {"atol": None}})
#: 另一套驗收（少一條測資）——「換了套件 suite_sha256 就換了」要有東西可比。
SPEC_WEAK = ss.validate({"v": 1, "dialect": "mbpp", "entry_point": "f",
                         "tests": [{"args": "[1]", "expected": "2"}],
                         "cmp": {"atol": None}})
SSHA = SPEC.suite_sha256


def task(task_id="t1", code="assert f(1) == 2\nassert f(2) == 3\n"):
    return {"task_id": task_id, "entry_point": "f",
            "visible_check": {"type": "run_python", "code": code, "timeout": 8}}


def truth_probe(truth: dict[str, ProbeResult]):
    """確定性的『真沙箱』替身：草稿 sha → 結果。誠實執行器全部共用它。"""
    def probe(code, _task):
        return truth[sha256_hex(code)]
    return probe


def liar_probe(truth, bribe_sha):
    def probe(code, _task):
        if sha256_hex(code) == bribe_sha:
            return ProbeResult(True, None, 2, True, None)
        return truth[sha256_hex(code)]
    return probe


def saboteur_probe():
    def probe(_code, _task):
        return ProbeResult(False, 1, 2, True, None)
    return probe


GOOD, BAD = "def f(x):\n    return x + 1\n", "def f(x):\n    return 0\n"
TRUTH = {sha256_hex(GOOD): ProbeResult(True, None, 2, True, None),
         sha256_hex(BAD): ProbeResult(False, 1, 2, True, None)}


def mk(n, probe):
    return [Executor(f"x{i}", Identity.generate(), Logbook(), probe) for i in range(n)]


def rule_runner(fn):
    """量具用的確定性 runner 替身：`fn(code, check_code) -> 通過?`。

    簽章與 `vacant.suitegauge.CheckRunner`／`gain_run.meets_demand` 對齊。
    §8 真正要證明量具有牙齒的那幾條**不用**這個，用真沙箱。
    """
    def run(code, check_code, entry_point=None, timeout_s=10):
        return bool(fn(code, check_code)), ""
    return run


def verdict_for(execs, t, code, quorum=None, spec=SPEC):
    ros = roster_of(execs)
    ssha = spec.suite_sha256
    atts = [e.attest(t, code, suite=spec, ts_ms=TS) for e in execs]
    q = quorum if quorum is not None else len(execs) // 2 + 1
    return form_verdict(atts, ros, task_id=t["task_id"], draft_sha256=sha256_hex(code),
                        suite_sha256=ssha, quorum=q), atts, ros


# ── 1. 誠實的執行器永遠一致 ────────────────────────────────────────────────
@pytest.mark.parametrize("k", [1, 3, 5, 7])
@pytest.mark.parametrize("code", [GOOD, BAD])
def test_honest_executors_always_agree(k, code):
    """確定性驗收套件 ⇒ 誠實執行器必須全票一致、沒有少數方。這是全部主張的地基。"""
    t = task()
    v, _atts, _ros = verdict_for(mk(k, truth_probe(TRUTH)), t, code)
    assert v.n_admitted == k
    assert v.unanimous and not v.contested
    assert v.dissenters == () and v.detail_dissenters == () and v.equivocators == ()
    assert v.visible_ok is (code is GOOD)


def test_honest_chain_verifies_and_is_append_only():
    """證言釘在自己的鏈上：驗鏈過，且抽掉中間一筆就驗不過（不能事後否認）。"""
    t = task()
    execs = mk(1, truth_probe(TRUTH))
    e = execs[0]
    for c in (GOOD, BAD, GOOD):
        e.attest(t, c, suite=SPEC, ts_ms=TS)
    ros = roster_of(execs)
    assert verify_executor_chain("x0", e.book, ros)
    tampered = Logbook([e.book.entries[0], e.book.entries[2]])
    assert not verify_executor_chain("x0", tampered, ros)


# ── 2. 三個裡有一個說謊：被推翻，而且被指名 ────────────────────────────────
def test_single_liar_among_three_is_outvoted_and_named():
    t = task()
    honest = mk(2, truth_probe(TRUTH))
    liar = Executor("liar", Identity.generate(), Logbook(), liar_probe(TRUTH, sha256_hex(BAD)))
    execs = honest + [liar]
    v, atts, ros = verdict_for(execs, t, BAD)
    assert v.visible_ok is False                      # 被推翻
    assert v.dissenters == ("liar",)                  # 被指名
    assert v.n_pass == 1 and v.n_fail == 2
    assert not v.unanimous and v.contested
    # 指名不是標籤，是可獨立核對的證據：那一筆證言驗得過，且內容就是那句謊。
    ev = dict(v.evidence)
    lie = next(a for a in atts if a.executor_id == "liar")
    assert ev["liar"] == lie.entry_hash
    assert verify_attestation(lie, ros, task_id="t1", draft_sha256=sha256_hex(BAD),
                              suite_sha256=SSHA) == (True, "")
    assert lie.payload["visible_ok"] is True


def test_liar_cannot_move_the_verdict_alone_but_leaves_a_trail():
    """說謊者被推翻之後，那份草稿仍然不出貨——被指名不是安慰獎，是機制的產物。"""
    t = task()
    execs = mk(2, truth_probe(TRUTH)) + [
        Executor("liar", Identity.generate(), Logbook(), liar_probe(TRUTH, sha256_hex(BAD)))]
    sel = select_by_quorum(t, [(BAD, "wA"), (GOOD, "wB")], execs, suite=SPEC, ts_ms=TS)
    assert sel.shipped_index == 1 and sel.shipped_worker == "wB"
    assert sel.verdicts[0].dissenters == ("liar",)
    assert sel.verdicts[1].unanimous


# ── 3. 三個裡有兩個共謀：翻掉判決（多數決上界，寫死在這裡）────────────────
def test_two_colluders_among_three_flip_the_verdict_and_invert_attribution():
    """**這是機制的破口，不是 bug。**

    多數決容忍的上界是 ⌊(k-1)/2⌋。k=3 時上界是 1；兩個共謀者過半，於是：
      - 判決翻成他們要的那個（一份 hidden 錯的草稿被判通過）；
      - `dissenters` 反過來指名**誠實的那一位**。
    機制在這裡量到的東西仍然是真的——「有人不一致」——但**歸屬的方向錯了**，
    而機制自己分不出來。任何對外說法都必須帶這一句。
    """
    t = task()
    bribe = sha256_hex(BAD)
    colluders = [Executor(f"c{i}", Identity.generate(), Logbook(), liar_probe(TRUTH, bribe))
                 for i in range(2)]
    honest = Executor("h0", Identity.generate(), Logbook(), truth_probe(TRUTH))
    v, _atts, _ros = verdict_for(colluders + [honest], t, BAD)
    assert v.visible_ok is True                       # 翻掉了
    assert v.dissenters == ("h0",)                    # 歸屬反轉：誠實的被指名
    assert v.n_pass == 2 and v.n_fail == 1
    # 共謀者內部零分歧：除了自己的 id，兩人的判決欄位完全相同 ⇒ 沒有可歸屬的痕跡。
    assert v.camp_pass == ("c0", "c1")


def test_majority_bound_holds_at_the_edge():
    """k=5：兩個共謀者（≤⌊(5-1)/2⌋）擋得住，三個就擋不住。上界是算出來的，不是調出來的。"""
    t = task()
    bribe = sha256_hex(BAD)
    for n_bad, expect_ok in ((2, False), (3, True)):
        bad = [Executor(f"c{i}", Identity.generate(), Logbook(), liar_probe(TRUTH, bribe))
               for i in range(n_bad)]
        good = [Executor(f"h{i}", Identity.generate(), Logbook(), truth_probe(TRUTH))
                for i in range(5 - n_bad)]
        v, _a, _r = verdict_for(bad + good, t, BAD)
        assert v.visible_ok is expect_ok, n_bad


def test_tie_is_undecided_and_the_gate_refuses():
    """偶數人數會平手。平手不是通過的證據 ⇒ 未決 ⇒ 拒交。刻意的不對稱。"""
    t = task()
    execs = [Executor("c0", Identity.generate(), Logbook(), liar_probe(TRUTH, sha256_hex(BAD))),
             Executor("h0", Identity.generate(), Logbook(), truth_probe(TRUTH))]
    v, _a, _r = verdict_for(execs, t, BAD, quorum=2)
    assert v.visible_ok is None and v.contested and v.dissenters == ()
    sel = select_by_quorum(t, [(BAD, "wA")], execs, suite=SPEC, quorum=2, ts_ms=TS)
    assert sel.refused


# ── 4. 竄改證言就驗不過 ────────────────────────────────────────────────────
def test_tampering_an_attestation_breaks_verification():
    t = task()
    execs = mk(1, truth_probe(TRUTH))
    att = execs[0].attest(t, BAD, suite=SPEC, ts_ms=TS)
    ros = roster_of(execs)
    assert verify_attestation(att, ros)[0]
    # (a) 竄改判決本身
    bad_payload = dict(att.payload) | {"visible_ok": True}
    forged = Attestation("x0", LogEntry(att.entry.stream_id, att.entry.branch_id,
                                        att.entry.seq, att.entry.prev_hash,
                                        att.entry.ts_ms, att.entry.type,
                                        bad_payload, att.entry.sig))
    assert verify_attestation(forged, ros) == (False, "bad_signature")
    # (b) 竄改鏈上位置（把同一筆搬到別的 seq）
    moved = Attestation("x0", LogEntry(att.entry.stream_id, att.entry.branch_id,
                                       att.entry.seq + 7, att.entry.prev_hash,
                                       att.entry.ts_ms, att.entry.type,
                                       att.entry.payload, att.entry.sig))
    assert verify_attestation(moved, ros) == (False, "bad_signature")
    # (c) 換一把自己的金鑰重簽同一句話——名冊上的公鑰驗不過，冒名擋掉
    impostor = Executor("x0", Identity.generate(), Logbook(), truth_probe(TRUTH))
    fake = impostor.attest(t, BAD, suite=SPEC, ts_ms=TS)
    assert verify_attestation(fake, ros) == (False, "bad_signature")
    # (d) 名冊外的人投票
    outsider = Executor("nobody", Identity.generate(), Logbook(), truth_probe(TRUTH))
    assert verify_attestation(outsider.attest(t, BAD, suite=SPEC, ts_ms=TS), ros) == (
        False, "unknown_executor")


def test_forged_attestation_is_rejected_from_the_verdict_not_counted():
    """驗不過的證言不是「一張反對票」，是**根本不進計票**，而且理由要進收據。"""
    t = task()
    execs = mk(3, truth_probe(TRUTH))
    ros = roster_of(execs)
    ssha = SSHA
    atts = [e.attest(t, BAD, suite=SPEC, ts_ms=TS) for e in execs]
    a0 = atts[0]
    atts[0] = Attestation("x0", LogEntry(a0.entry.stream_id, a0.entry.branch_id,
                                         a0.entry.seq, a0.entry.prev_hash, a0.entry.ts_ms,
                                         a0.entry.type, dict(a0.payload) | {"visible_ok": True},
                                         a0.entry.sig))
    v = form_verdict(atts, ros, task_id="t1", draft_sha256=sha256_hex(BAD),
                     suite_sha256=ssha, quorum=2)
    assert v.n_admitted == 2 and v.rejected == (("x0", "bad_signature"),)
    assert v.visible_ok is False and v.dissenters == ()
    # 驗不過的證言比「少數方」更硬 ⇒ 必須翻動警報，否則只看 unanimous 的人會漏掉它。
    assert v.contested and not v.unanimous


def test_equivocation_is_a_provable_fault_and_voids_both_votes():
    """同一個執行器對同一份草稿交出兩份不同的簽章證言 ⇒ 兩份都作廢、進 equivocators。

    這比「少數方」強一級：不需要跟任何人比對就已經是自證的過錯。
    """
    t = task()
    honest = mk(2, truth_probe(TRUTH))
    two_faced = Executor("d0", Identity.generate(), Logbook(), truth_probe(TRUTH))
    ros = roster_of(honest + [two_faced])
    ssha = SSHA
    atts = [e.attest(t, BAD, suite=SPEC, ts_ms=TS) for e in honest]
    atts.append(two_faced.attest(t, BAD, suite=SPEC, ts_ms=TS))
    two_faced.probe = liar_probe(TRUTH, sha256_hex(BAD))
    atts.append(two_faced.attest(t, BAD, suite=SPEC, ts_ms=TS))
    v = form_verdict(atts, ros, task_id="t1", draft_sha256=sha256_hex(BAD),
                     suite_sha256=ssha, quorum=2)
    assert v.equivocators == ("d0",) and ("d0", "equivocation") in v.rejected
    assert v.n_admitted == 2 and v.visible_ok is False


# ── 5. 驗收套件雜湊不符 ⇒ 拒收 ────────────────────────────────────────────
def test_suite_hash_mismatch_is_rejected():
    """執行器跑的必須是**這一套**驗收。跑了別套（或跑了改過的那套）＝不進計票。"""
    t = task()
    assert SPEC.suite_sha256 != SPEC_WEAK.suite_sha256
    execs = mk(1, truth_probe(TRUTH))
    ros = roster_of(execs)
    # 同一題、同一份草稿，但執行器渲染跑的是**另一份 spec** ⇒ 不進計票。
    att = execs[0].attest(t, GOOD, suite=SPEC_WEAK, ts_ms=TS)
    assert verify_attestation(att, ros, task_id="t1", draft_sha256=sha256_hex(GOOD),
                              suite_sha256=SSHA) == (False, "suite_mismatch")
    # 換題目的證言同樣擋掉（跨題重放）。
    att2 = execs[0].attest(task("t2"), GOOD, suite=SPEC, ts_ms=TS)
    assert verify_attestation(att2, ros, task_id="t1", draft_sha256=sha256_hex(GOOD),
                              suite_sha256=SSHA) == (False, "task_mismatch")
    # round452 多出來的第三條：spec 相同但**渲染器**產出不同 ⇒ `render_mismatch`。
    # 套件是資料之後，「你跑的碼跟我不一樣」第一次有欄位講得出來。
    att3 = execs[0].attest(t, GOOD, suite=SPEC, ts_ms=TS)
    assert verify_attestation(att3, ros, task_id="t1", draft_sha256=sha256_hex(GOOD),
                              suite_sha256=SSHA,
                              render_sha256=sha256_hex("not what I ran")
                              ) == (False, "render_mismatch")
    assert verify_attestation(att3, ros, suite_sha256=SSHA,
                              render_sha256=sha256_hex(SPEC.render())) == (True, "")


def test_replayed_attestation_from_another_draft_is_rejected():
    """把上一份草稿的『通過』證言貼到這一份 ⇒ draft_mismatch，擋掉重放。"""
    t = task()
    execs = mk(1, truth_probe(TRUTH))
    att = execs[0].attest(t, GOOD, suite=SPEC, ts_ms=TS)
    assert verify_attestation(att, roster_of(execs), task_id="t1",
                              draft_sha256=sha256_hex(BAD),
                              suite_sha256=SSHA) == (False, "draft_mismatch")


# ── 6. 剩下的固定點：套件的 commit-reveal 與重跑權 ─────────────────────────
def test_suite_commit_reveal_binds_the_suite_in_time():
    t = task()
    ident = Identity.generate()
    book = Logbook()
    nonce = "0123456789abcdef0123456789abcdef"
    # round749（R449 §四-3）：commit 現在要求一筆通過的量具紀錄。這一條測的仍然是
    # commit-reveal 的**時間綁定**，所以量具用注入的 runner 算（不碰沙箱）；
    # 量具本身的牙齒在 §8 測。
    gauge = run_suite_gauge(SPEC, GOOD, [BAD],
                            entry_point="f", runner=rule_runner(lambda c, _k: c is GOOD))
    entry = commit_suite(book, ident, task_id="t1", suite=SPEC, nonce=nonce,
                         entry_point="f", gauge=gauge, ts_ms=TS)
    assert open_suite(entry, SPEC, nonce, entry_point="f")
    # 揭露另一份 spec ⇒ 對不上
    assert not open_suite(entry, SPEC_WEAK, nonce, entry_point="f")
    assert not open_suite(entry, SPEC, "f" * 32, entry_point="f")
    assert book.verify_chain(
        __import__("vacant.identity", fromlist=["PublicIdentity"]).PublicIdentity(
            ident.vacant_id, ident.pub))


def test_challenge_rerun_overturns_a_saboteur_majority_with_a_clean_panel():
    """落敗方的重跑權：換一組乾淨的執行器再跑一次，同樣零模型呼叫。

    邊界（測試也要測邊界）：面板本身被腐化時重跑會**一致地覆述原判**，
    `outcome="upheld"` 不等於原判正確。
    """
    t = task()
    sab = [Executor(f"s{i}", Identity.generate(), Logbook(), saboteur_probe())
           for i in range(2)]
    execs = sab + [Executor("h0", Identity.generate(), Logbook(), truth_probe(TRUTH))]
    sel = select_by_quorum(t, [(GOOD, "wA")], execs, suite=SPEC, ts_ms=TS)
    assert sel.refused and sel.verdicts[0].dissenters == ("h0",)

    clean = mk(3, truth_probe(TRUTH))
    ch = challenge_rerun(t, GOOD, clean, sel.verdicts[0], suite=SPEC, ts_ms=TS)
    assert ch.outcome == "overturned" and ch.rerun.visible_ok is True
    assert "h0" in ch.accused          # 聯集：原判指名的人也要留在收據上

    dirty = [Executor(f"d{i}", Identity.generate(), Logbook(), saboteur_probe())
             for i in range(3)]
    assert challenge_rerun(t, GOOD, dirty, sel.verdicts[0], suite=SPEC, ts_ms=TS).outcome == "upheld"


# ── 7. 選擇語意與 CONFORM 逐字相同（k=1 時必須退化成 CONFORM）──────────────
def test_k1_reduces_to_conform():
    """k=1 的法定人數 ＝ 單一執行器 ＝ CONFORM。這是模擬校準檢查的機制側對應物。"""
    t = task()
    execs = mk(1, truth_probe(TRUTH))
    sel = select_by_quorum(t, [(BAD, "wA"), (BAD, "wB"), (GOOD, "wC")], execs, suite=SPEC, ts_ms=TS)
    assert sel.shipped_index == 2 and sel.n_sandbox_runs == 3
    assert not sel.refused
    sel2 = select_by_quorum(t, [(BAD, "wA"), (BAD, "wB")], execs, suite=SPEC, ts_ms=TS)
    assert sel2.refused and sel2.shipped_index is None
    # 拒交的收據仍然列出每一份卡在第幾條——R440P §六 那句話的實作。
    assert [v.as_receipt()["camp_fail"] for v in sel2.verdicts] == [["x0"], ["x0"]]


def test_a_corrupt_executor_that_agrees_with_the_majority_is_never_named():
    """**偵測率的分母紅線**：跟多數方一致的腐化執行器＝零痕跡，必須算成「沒偵測到」。

    這裡的 `sleeper` 買通的是**別的**草稿（GOOD），對本題這一份（BAD）照實跑，
    所以它在收據上與誠實執行器逐位相同。它仍然是腐化的——只是這一票沒有用到。
    `peer_exec_sim` 的 detect_* 分母因此是**全部腐化執行器**，不是「有說謊的那些」。
    """
    t = task()
    sleeper = Executor("sleeper", Identity.generate(), Logbook(),
                       liar_probe(TRUTH, sha256_hex(GOOD)))   # 目標不是這一份
    v, _a, _r = verdict_for(mk(2, truth_probe(TRUTH)) + [sleeper], t, BAD)
    assert v.unanimous and not v.contested
    assert v.dissenters == () and v.detail_dissenters == () and v.equivocators == ()
    assert "sleeper" in v.camp_fail          # 它有投票，而且投得跟誠實的人一樣
    assert v.visible_ok is False


def test_a_weak_suite_ships_a_wrong_draft_with_zero_dissent():
    """**剩下的固定點，寫成測試**：驗收套件覆蓋不足時，去中心化執行零幫助。

    round452 之前這一條用的是「什麼都不驗」的 `visible_check := "pass"`。套件改成
    資料之後那個東西**不可表達**（`tests=[]` 被 validator 以 `empty_suite_rejected`
    拒絕，見 `tests/test_suitespec.py`），所以殘餘換成它現在的形狀：**覆蓋不足**
    ——一份少一條測資的 spec，剛好放行一份錯的草稿。

    執行器一個都沒有腐化、每條鏈都驗得過、`contested` 是 False、`dissenters` 是空的
    ——所有健康指標滿分——而出貨的是一份對真需求錯的草稿。`unanimous` 描述的是
    **觀察到的分佈**，不是真相；收據上不准把它讀成「這份草稿是對的」。
    """
    t = task()
    allpass = {sha256_hex(GOOD): ProbeResult(True, None, 1, True, None),
               sha256_hex(BAD): ProbeResult(True, None, 1, True, None)}
    execs = mk(5, truth_probe(allpass))
    sel = select_by_quorum(t, [(BAD, "wA"), (GOOD, "wB")], execs, suite=SPEC_WEAK,
                           ts_ms=TS)
    assert sel.shipped_index == 0 and sel.shipped_worker == "wA"   # 交了錯的那一份
    v = sel.verdicts[0]
    assert v.unanimous and not v.contested and v.n_pass == 5 and v.dissenters == ()
    # 而且這件事在收據上看得出來——換了 spec，suite_sha256 就換了。
    assert v.suite_sha256 == SPEC_WEAK.suite_sha256 != SSHA

def test_detail_dissent_names_a_saboteur_that_did_not_actually_run():
    """第二條歸屬通道：兩邊都說 FAIL，但『卡在第幾條』不同 ⇒ 有人沒真的跑。

    邊界：一個真的跑、只在布林值上說謊的破壞者不會被這條通道抓到（布林通道會）。
    """
    t = task()
    honest = mk(2, truth_probe(TRUTH))          # 真相：BAD 卡在第 1 條
    truth2 = dict(TRUTH) | {sha256_hex(BAD): ProbeResult(False, 2, 2, True, None)}
    honest = [Executor(f"h{i}", Identity.generate(), Logbook(), truth_probe(truth2))
              for i in range(2)]
    lazy = Executor("lazy", Identity.generate(), Logbook(), saboteur_probe())  # 永遠填 1
    v, _a, _r = verdict_for(honest + [lazy], t, BAD)
    assert v.visible_ok is False and v.dissenters == ()      # 布林票上完全一致
    assert v.detail_dissenters == ("lazy",)                  # 但條號出賣了他
    assert v.contested


# ── 8. 套件量具閘：套件要上鏈，先證明它擋得住已知壞草稿（R449 §四-3）─────────
NONCE = "0123456789abcdef0123456789abcdef"

#: 真 MBPP+ 題目（similar_elements）的參考解與一份壞解——**驗證者側**的物件：
#: 不是任何 worker 的產出、不進任何 prompt、不進 hidden_check 路徑（V/GT 分離）。
REF_SIMILAR = "def similar_elements(a, b):\n    return tuple(sorted(set(a) & set(b)))\n"
STUB_EMPTY = "def similar_elements(*a, **k):\n    return ()\n"


def spec_for(entry_point, tests, **cmp_over):
    cmp = {"atol": None, "set_equivalent": False, "regex_predicate": False}
    cmp.update(cmp_over)
    return ss.validate({"v": 1, "dialect": "mbpp", "entry_point": entry_point,
                        "tests": tests, "cmp": cmp})


@pytest.fixture(scope="module")
def mbpp_task():
    """真 MBPP+ 的 similar_elements（官方包不在場就 skip，不假裝驗過）。"""
    from vacant.codebench import EvalPlusMBPPLoader
    try:
        tasks = EvalPlusMBPPLoader(expose_contract=True).iter_tasks("x")
    except FileNotFoundError:
        pytest.skip("EvalPlus 官方包不在本機（VM 上才有），跳過")
    for t in tasks:
        if t["entry_point"] == "similar_elements":
            return t
    pytest.skip("找不到基準題")


@pytest.fixture(scope="module")
def mbpp_spec(mbpp_task):
    """把真 MBPP+ 那題轉成 `SuiteSpec`（期望值由參考解在子行程算好）。"""
    conv = ss.from_task(mbpp_task)
    assert conv.spec is not None, conv.reason
    return conv.spec


def test_an_empty_suite_is_refused_before_the_gauge_even_runs():
    """**R449 §三-3 的封口，在 round452 往前挪了一層**：「什麼都不驗」連 spec 都不是。

    `visible_check := "pass"` 在資料形態裡的唯一寫法是 `tests: []`，而 validator
    以 `empty_suite_rejected` 拒絕它——連量具都不必跑，因為根本沒有東西可以上鏈。
    這比舊語意嚴格：舊的是「跑量具、量具說不合格」，新的是「這個東西不是一份套件」。
    """
    with pytest.raises(SuiteSpecError) as e:
        spec_for("similar_elements", [])
    assert "empty_suite_rejected" in str(e.value)


def test_a_wrong_expected_suite_is_refused_at_commit(mbpp_task):
    """量具在資料形態裡仍然有牙齒：期望值寫錯 ⇒ 參考解不過、壞樁反而過 ⇒ 上不了鏈。

    真沙箱。這份 spec 說 `similar_elements([3,4,5],[4,5,6])` 應該回 `None`：
      - 參考解回 `(4, 5)` ⇒ **不過**；
      - `return None` 的壞樁 ⇒ **過**。
    兩個方向同時失敗 ⇒ `SuiteGaugeError`，而且**鏈上一筆都沒有**（不是記一筆失敗）。
    """
    bad = spec_for("similar_elements",
                   [{"args": "[[3, 4, 5], [4, 5, 6]]", "expected": "None"}])
    book, ident = Logbook(), Identity.generate()
    with pytest.raises(SuiteGaugeError) as e:
        commit_suite_with_gauge(book, ident, task_id="t1", suite=bad,
                                nonce=NONCE, reference=REF_SIMILAR,
                                entry_point="similar_elements", ts_ms=TS)
    assert "gauge_failed" in str(e.value) and "ref_passed=False" in str(e.value)
    assert book.entries == []


def test_real_mbpp_spec_is_accepted_at_commit(mbpp_task, mbpp_spec):
    """反方向的對照：真的 MBPP+ 可見驗收**轉成 spec 之後**過得了閘（不然閘只是焊死）。"""
    book, ident = Logbook(), Identity.generate()
    entry = commit_suite_with_gauge(
        book, ident, task_id=mbpp_task["task_id"], suite=mbpp_spec, nonce=NONCE,
        reference=REF_SIMILAR, entry_point="similar_elements", ts_ms=TS)
    rec = GaugeRecord.from_payload(entry.payload["gauge"])
    assert rec.ref_passed and rec.all_rejected and rec.n_broken == 1 and rec.ok
    # 紀錄綁的是 **spec 資料的雜湊**，不是某一份渲染出來的碼的雜湊。
    assert rec.suite_sha256 == mbpp_spec.suite_sha256
    assert rec.suite_sha256 != sha256_hex(mbpp_spec.render())
    assert rec.ref_sha256 == sha256_hex(REF_SIMILAR)
    assert entry.payload["suite_sha256"] == mbpp_spec.suite_sha256
    assert entry.payload["entry_point"] == "similar_elements"
    assert open_suite(entry, mbpp_spec, NONCE, entry_point="similar_elements")
    assert suite_gate(entry, mbpp_spec, NONCE, entry_point="similar_elements",
                      who=PublicIdentity(ident.vacant_id, ident.pub)) == (True, "")
    assert book.verify_chain(PublicIdentity(ident.vacant_id, ident.pub))


def test_a_third_party_recomputes_the_gauge_record_from_spec_reference_stubs(mbpp_spec):
    """**紀錄從「因為有簽章所以可信」變成「可重算」**——這是套件變成資料的主要紅利。

    第三方拿到 (spec, 參考解, 壞樁) 就能重跑量具，得到**逐位元組相同**的 payload。
    渲染是確定性的，所以「我信你簽的」可以換成「我自己算一遍」。真沙箱。
    """
    stubs = [broken_stub("similar_elements"), STUB_EMPTY]
    mine = run_suite_gauge(mbpp_spec, REF_SIMILAR, stubs,
                           entry_point="similar_elements")
    theirs = run_suite_gauge(ss.validate(mbpp_spec.to_json()), REF_SIMILAR, stubs,
                             entry_point="similar_elements")
    assert mine.as_payload() == theirs.as_payload() and mine.ok
    # 而且渲染本身是確定性的：同一份 spec ⇒ 同一份碼（不同的 SuiteSpec 物件也一樣）。
    assert mbpp_spec.render() == ss.validate(mbpp_spec.to_json()).render()


def test_a_spec_that_picks_an_easy_input_passes_the_reference_but_admits_a_stub():
    """通過參考解**不夠**：挑一個「參考解剛好回空的」輸入，`return ()` 的壞樁就溜過去。

    真沙箱。這就是資料形態裡**覆蓋不足**的最小樣本：期望值完全正確、參考解通過、
    `return None` 的樁被擋，而 `return ()` 的樁大搖大擺走過去。單樁量具給綠燈，
    多樁量具不給——量具是下界，不是保證。
    """
    easy = spec_for("similar_elements", [{"args": "[[1, 2], [3, 4]]", "expected": "()"}])
    book, ident = Logbook(), Identity.generate()
    one = run_suite_gauge(easy, REF_SIMILAR, [broken_stub("similar_elements")],
                          entry_point="similar_elements")
    assert one.ok            # 只放一個樁 ⇒ 這套爛驗收會被放行（量具是下界）
    with pytest.raises(SuiteGaugeError) as e:
        commit_suite_with_gauge(
            book, ident, task_id="t1", suite=easy, nonce=NONCE,
            reference=REF_SIMILAR, entry_point="similar_elements",
            broken_stubs=[broken_stub("similar_elements"), STUB_EMPTY], ts_ms=TS)
    assert "gauge_failed" in str(e.value) and "ref_passed=True" in str(e.value)
    assert book.entries == []


def test_an_empty_known_bad_set_is_not_a_pass():
    """零個壞樁 ⇒ 「全部被擋」空洞地成立。fail-open 要在 commit 就被擋下來。"""
    rec = run_suite_gauge(SPEC, GOOD, [], entry_point="f",
                          runner=rule_runner(lambda *_: True))
    assert rec.ref_passed and rec.n_broken == 0 and not rec.ok
    with pytest.raises(SuiteGaugeError) as e:
        commit_suite(Logbook(), Identity.generate(), task_id="t1", suite=SPEC,
                     nonce=NONCE, entry_point="f", gauge=rec, ts_ms=TS)
    assert "n_broken=0" in str(e.value)


def test_a_raw_code_suite_cannot_enter_any_door():
    """**這道門被拆掉了**：任何一支吃套件的函式，收到 `str` 都丟例外，不是「盡量試」。

    R451 的裁決是「只要驗收碼是任意 Python，量具就沒有約束力」，所以關閉必須是
    **型別層級**的，不能是一個可以被旗標打開的選項。六個入口逐一釘住。
    """
    raw = "assert f(1) == 2\n"
    book, ident = Logbook(), Identity.generate()
    rec = run_suite_gauge(SPEC, GOOD, [BAD], entry_point="f",
                          runner=rule_runner(lambda c, _k: c is GOOD))
    for call in (
        lambda: as_suite_spec(raw, "f"),
        lambda: commit_suite(book, ident, task_id="t", suite=raw, nonce=NONCE,
                             entry_point="f", gauge=rec),
        lambda: commit_suite_with_gauge(book, ident, task_id="t", suite=raw,
                                        nonce=NONCE, reference=GOOD, entry_point="f"),
        lambda: run_suite_gauge(raw, GOOD, [BAD], entry_point="f",
                                runner=rule_runner(lambda *_: True)),
        lambda: select_by_quorum(task(), [(GOOD, "w")], mk(1, truth_probe(TRUTH)),
                                 suite=raw, ts_ms=TS),
        lambda: mk(1, truth_probe(TRUTH))[0].attest(task(), GOOD, suite=raw, ts_ms=TS),
    ):
        with pytest.raises(SuiteSpecError) as e:
            call()
        assert "raw_code_suite_not_accepted" in str(e.value)
    assert book.entries == []


def _gauged_commit(spec=SPEC, *, task_id="t1"):
    """把一份（假設已驗過的）spec 合法地上鏈，回傳 (entry, book, identity)。"""
    book, ident = Logbook(), Identity.generate()
    rec = run_suite_gauge(spec, GOOD, [BAD], entry_point="f",
                          runner=rule_runner(lambda c, _k: c is GOOD))
    return commit_suite(book, ident, task_id=task_id, suite=spec, nonce=NONCE,
                        entry_point="f", gauge=rec, ts_ms=TS), book, ident


def test_tampering_the_gauge_record_breaks_chain_verification():
    """把 `all_rejected` 從 True 改成 False（或反過來）＝改 payload ＝簽章壞掉。

    量具紀錄不是旁邊的一張紙條，它**在簽章覆蓋的範圍內**：改它就得重簽整條鏈。
    兩個方向都測——調高（假造合格）與調低（事後賴帳）都要驗不過。
    """
    entry, book, ident = _gauged_commit()
    who = PublicIdentity(ident.vacant_id, ident.pub)
    assert book.verify_chain(who) and open_suite(entry, SPEC, NONCE, entry_point="f")

    def mutate(**over):
        p = dict(entry.payload)
        p["gauge"] = dict(p["gauge"]) | over
        return LogEntry(entry.stream_id, entry.branch_id, entry.seq, entry.prev_hash,
                        entry.ts_ms, entry.type, p, entry.sig)

    # (a) 事後賴帳：把 all_rejected 改成 False。鏈驗不過，而且內容本身就已經不合格。
    lowered = mutate(all_rejected=False)
    assert not Logbook([lowered]).verify_chain(who)
    assert suite_gate(lowered, SPEC, NONCE, entry_point="f") == (False, "gauge_failed")
    # (b) 假造更強的合格證：把 n_broken 從 1 灌水成 99。內容檢查**抓不到**這個
    #     （灌水後的紀錄照樣「合格」）——只有簽章抓得到。這條邊界要寫出來：
    #     量具紀錄的可信度來自簽章鏈，不是來自它自己說了什麼。
    inflated = mutate(n_broken=99)
    assert not Logbook([inflated]).verify_chain(who)
    assert suite_gate(inflated, SPEC, NONCE,
                      entry_point="f") == (True, "")                  # 內容看不出來
    assert suite_gate(inflated, SPEC, NONCE, entry_point="f",
                      who=who) == (False, "bad_signature")


def test_open_suite_refuses_a_commit_without_a_gauge_record():
    """沒有量具紀錄的承諾**不是**一套可用的驗收——缺席就是拒，不是「沒查到」。"""
    entry, _book, _ident = _gauged_commit()
    bare = LogEntry(entry.stream_id, entry.branch_id, entry.seq, entry.prev_hash,
                    entry.ts_ms, entry.type,
                    {k: v for k, v in entry.payload.items() if k != "gauge"}, entry.sig)
    assert suite_gate(bare, SPEC, NONCE,
                      entry_point="f") == (False, "gauge_record_missing")
    assert not open_suite(bare, SPEC, NONCE, entry_point="f")
    # 綁錯套件的紀錄也擋掉（拿別題的合格證來用）。
    other = dict(entry.payload)
    other["gauge"] = dict(other["gauge"]) | {"suite_sha256": sha256_hex("pass")}
    assert suite_gate(LogEntry(entry.stream_id, entry.branch_id, entry.seq,
                               entry.prev_hash, entry.ts_ms, entry.type, other,
                               entry.sig), SPEC, NONCE,
                      entry_point="f") == (False, "gauge_suite_mismatch")
    # 揭露的是**另一份 spec** ⇒ 承諾對不上。
    assert suite_gate(entry, SPEC_WEAK, NONCE,
                      entry_point="f") == (False, "commitment_mismatch")


def test_form_verdict_rejects_attestations_against_an_uncommitted_suite():
    """套件沒上鏈（不在白名單）⇒ 每一票都不進計票、判決未決 ⇒ 拒交。"""
    t = task()
    execs = mk(3, truth_probe(TRUTH))
    ros = roster_of(execs)
    ssha = SSHA
    atts = [e.attest(t, GOOD, suite=SPEC, ts_ms=TS) for e in execs]
    v = form_verdict(atts, ros, task_id="t1", draft_sha256=sha256_hex(GOOD),
                     suite_sha256=ssha, quorum=2, gauged_suites={})
    assert v.gauge_status == "suite_not_gauged"
    assert v.visible_ok is None and v.n_admitted == 0 and v.contested
    assert sorted(v.rejected) == [("x0", "suite_not_gauged"), ("x1", "suite_not_gauged"),
                                  ("x2", "suite_not_gauged")]
    assert v.as_receipt()["gauge_status"] == "suite_not_gauged"


def test_form_verdict_rejects_a_suite_whose_gauge_record_failed():
    """白名單裡有這套、但紀錄是不合格的 ⇒ 同樣一票都不採信（理由分開報）。"""
    t = task()
    execs = mk(3, truth_probe(TRUTH))
    ssha = SSHA
    atts = [e.attest(t, GOOD, suite=SPEC, ts_ms=TS) for e in execs]
    failed = GaugeRecord(ssha, sha256_hex(GOOD), 1, False, True)   # 壞樁溜過去了
    v = form_verdict(atts, roster_of(execs), task_id="t1",
                     draft_sha256=sha256_hex(GOOD), suite_sha256=ssha, quorum=2,
                     gauged_suites={ssha: failed})
    assert v.gauge_status == "suite_gauge_failed" and v.visible_ok is None
    assert v.n_admitted == 0 and v.contested
    # 合格的紀錄則放行，判決回到原本的語意。
    good = GaugeRecord(ssha, sha256_hex(GOOD), 1, True, True)
    v2 = form_verdict(atts, roster_of(execs), task_id="t1",
                      draft_sha256=sha256_hex(GOOD), suite_sha256=ssha, quorum=2,
                      gauged_suites={ssha: good})
    assert v2.gauge_status == "ok" and v2.visible_ok is True and v2.unanimous


def test_gauged_suite_index_only_admits_gate_passing_commits():
    """白名單的建構函式自己 fail-closed：揭露對不上的承諾進不了索引。"""
    entry, _b, _i = _gauged_commit()
    idx = gauged_suite_index([(entry, SPEC, NONCE, "f")])
    assert set(idx) == {SSHA} and idx[SSHA].ok
    assert gauged_suite_index([(entry, SPEC, "f" * 32, "f")]) == {}     # nonce 不對
    assert gauged_suite_index([(entry, SPEC_WEAK, NONCE, "f")]) == {}   # 套件不對
    assert gauged_suite_index([(entry, SPEC, NONCE, "g")]) == {}        # 題目不對
    # 餵一段原始碼進來連例外都不會逸出——它就是進不了索引。
    assert gauged_suite_index([(entry, "assert f(1) == 2\n", NONCE, "f")]) == {}
    # 三元組**沒有相容路徑**：省略 entry_point 是型別錯誤，不是「不檢查」。
    with pytest.raises(TypeError):
        gauged_suite_index([(entry, SPEC, NONCE)])


def test_a_weak_suite_no_longer_ships_once_the_gate_is_on():
    """把 §7 那一條（爛套件零爭議地交垃圾）接到閘門後面：現在交不出去。

    同一組誠實執行器、同一份「什麼都放行」的探針。差別只有一個：這一套驗收
    沒有合格的量具紀錄。⇒ 拒交、`refusal_reason` 指名是**套件**不是候選、
    而且 `n_sandbox_runs=0`——連跑都不跑（量具紀錄必須在證言之前）。
    """
    t = task()
    allpass = {sha256_hex(GOOD): ProbeResult(True, None, 1, True, None),
               sha256_hex(BAD): ProbeResult(True, None, 1, True, None)}
    execs = mk(5, truth_probe(allpass))
    # 閘門關著（舊語意）：照樣交出錯的那一份，所有健康指標滿格——R449 §三-3。
    before = select_by_quorum(t, [(BAD, "wA"), (GOOD, "wB")], execs, suite=SPEC_WEAK,
                              ts_ms=TS)
    assert before.shipped_index == 0 and before.verdicts[0].unanimous
    assert before.verdicts[0].gauge_status == "unchecked"
    # 閘門開著：這套驗收根本沒有合格紀錄 ⇒ 拒交。
    after = select_by_quorum(t, [(BAD, "wA"), (GOOD, "wB")], execs, suite=SPEC_WEAK,
                             ts_ms=TS, gauged_suites={})
    assert after.refused and after.shipped_index is None
    assert after.refusal_reason == "suite_gate:suite_not_gauged"
    assert after.verdicts[0].gauge_status == "suite_not_gauged"
    assert after.as_receipt()["refusal_reason"] == "suite_gate:suite_not_gauged"


def test_select_by_quorum_refuses_before_spending_a_single_sandbox_run():
    """`suite_commit` 有給的時候，閘在**第一次沙箱之前**。爛套件不該先燒 k 次執行。"""
    t = task()
    entry, _b, _i = _gauged_commit()
    execs = mk(3, truth_probe(TRUTH))
    # (a) 承諾的是別套驗收 ⇒ 連一次沙箱都不跑
    sel = select_by_quorum(t, [(GOOD, "wA")], execs, suite=SPEC_WEAK,
                           suite_commit=entry, suite_nonce=NONCE, ts_ms=TS)
    assert sel.refused and sel.n_sandbox_runs == 0 and sel.verdicts == ()
    assert sel.refusal_reason == "suite_gate:commitment_mismatch"
    # (b) 對得上的套件則照常出貨，語意與沒有閘門時逐字相同
    sel2 = select_by_quorum(t, [(BAD, "wA"), (GOOD, "wB")], execs, suite=SPEC,
                            suite_commit=entry, suite_nonce=NONCE, ts_ms=TS)
    assert sel2.shipped_index == 1 and sel2.n_sandbox_runs == 6
    assert all(v.gauge_status == "ok" for v in sel2.verdicts)
    assert sel2.refusal_reason is None


def test_select_by_quorum_verifies_the_committers_signature_when_given_the_key():
    """灌水的量具紀錄：內容看不出來，**簽章看得出來**——出貨路徑要帶公鑰。

    `n_broken` 從 1 改成 99 之後這筆紀錄在內容上更「合格」，`suite_gate` 不帶 `who`
    照樣放行（上面已經證明）。這裡把承諾者的公鑰帶進 `select_by_quorum`：
    同一份灌水承諾變成 `suite_gate:bad_signature`，而且**一次沙箱都不花**。
    """
    t = task()
    entry, _b, ident = _gauged_commit()
    who = PublicIdentity(ident.vacant_id, ident.pub)
    execs = mk(3, truth_probe(TRUTH))
    ok = select_by_quorum(t, [(BAD, "wA"), (GOOD, "wB")], execs, suite=SPEC,
                          suite_commit=entry, suite_nonce=NONCE, suite_committer=who,
                          ts_ms=TS)
    assert ok.shipped_index == 1 and ok.refusal_reason is None
    p = dict(entry.payload)
    p["gauge"] = dict(p["gauge"]) | {"n_broken": 99}
    forged = LogEntry(entry.stream_id, entry.branch_id, entry.seq, entry.prev_hash,
                      entry.ts_ms, entry.type, p, entry.sig)
    blind = select_by_quorum(t, [(GOOD, "wB")], execs, suite=SPEC, suite_commit=forged,
                             suite_nonce=NONCE, ts_ms=TS)
    assert not blind.refused                                   # 不帶公鑰＝看不見
    caught = select_by_quorum(t, [(GOOD, "wB")], execs, suite=SPEC, suite_commit=forged,
                              suite_nonce=NONCE, suite_committer=who, ts_ms=TS)
    assert caught.refused and caught.n_sandbox_runs == 0
    assert caught.refusal_reason == "suite_gate:bad_signature"


def test_default_broken_stub_matches_probe_instrument():
    """反漂移：`suitegauge.broken_stub` 必須與 `gain_run.probe_instrument` 的樁逐字相同。

    用 `ops/gain/r474_stub_sweep.py` 那支 AST 抽取器逐字取回來再 eval——兩份實作
    只要有一天分家，這條就會吵，而不是安靜地用兩個不同的樁量兩件事。
    """
    from ops.gain.r474_stub_sweep import stub_expr_source
    src = stub_expr_source()
    for ep in ("f", "similar_elements", None):
        expected = eval(src, {"t": {"entry_point": ep} if ep else {}})  # noqa: S307
        assert broken_stub(ep) == expected


# ── 9. R451 的三種攻擊：改成資料之後**不可表達**（不是被擋）───────────────────
def test_a_suite_can_read_the_candidate_source_from_the_runner():
    """實測（不是假設）：**任意** Python 的驗收碼看得見候選的原始碼，不只是它的行為。

    `vacant/checks.py::_test_runner_source` 把套件原文**內嵌**進 runner 行程，而
    `_worker`（跑候選的那個 `subprocess.Popen`）就在同一個命名空間裡，
    `_worker.args` 帶著 `candidate.py` 的路徑。AST 白名單只掃**候選**，不掃套件。

    這條性質是 round452 那個決定的**理由**，不是一個待修的洞：它證明「驗收碼是
    任意 Python」這個形態下，內容定址的白／黑名單（targeted）與跨呼叫狀態
    （stateful）都是可行的，所以補丁沒有意義，只有換形態有意義。
    改成 `SuiteSpec` 之後供應者交不出這樣一段碼——渲染器是我們自己的
    （下面三條把「交不出來」逐一釘住）。
    """
    from ops.gain.gain_run import meets_demand
    marker = "vacant_r449_marker_" + "8f21c0"
    peek = (
        "_p = next(p for p in _worker.args if str(p).endswith('candidate.py'))\n"
        "with open(_p, encoding='utf-8') as _fh:\n"
        "    _src = _fh.read()\n"
        f"assert {marker!r} in _src\n"
    )
    with_marker = f"def f(x):\n    return x + 1  # {marker}\n"
    without = "def f(x):\n    return x + 1\n"
    assert meets_demand(with_marker, peek, 10, entry_point="f")[0] is True
    # 同一份行為、只差一行註解 ⇒ 判決翻轉。這證明它讀的是原始碼不是行為。
    assert meets_demand(without, peek, 10, entry_point="f")[0] is False


def test_the_r451_attack_suites_have_no_encoding_as_a_spec(mbpp_task):
    """**R452 的主張，寫成測試**：targeted／mimic／stateful 三份驗收碼餵進 validator
    一律被拒，理由字串指得出是哪一條規則。

    「不可表達」不是一句宣稱，是一個可以被釘住的型別性質：`SuiteSpec` 的欄位只有
    entry_point、一串字面值、三個布林／數值旗標，沒有任何一格放得下 `import`、
    `open`、`hashlib`、跨呼叫狀態或「把受測函式換掉」。
    """
    from ops.gain.replay.peer_exec_sim import mimic_suite, targeted_suite
    from ops.gain.replay.r451_stateful_suite_probe import stateful_suite

    ep = mbpp_task["entry_point"]
    real = mbpp_task["visible_check"]["code"]
    attacks = {
        "targeted": targeted_suite(ep),
        "mimic": mimic_suite(real, ep),
        "stateful": stateful_suite(real, ep),
        "trivial": "pass",
    }
    for name, code in attacks.items():
        assert code is not None, name
        with pytest.raises(SuiteSpecError) as e:
            ss.parse_check_code(code)
        assert "unrecognized_suite_shape" in str(e.value), (name, str(e.value))
        # 而且它們連當成一份 spec 遞進來都不行（`str` 就是原始碼那道門）。
        with pytest.raises(SuiteSpecError):
            as_suite_spec(code, ep)
    # 對照：**真的**那一套認得出來，而且轉得成 spec（不是把所有東西都拒掉）。
    parsed = ss.parse_check_code(real)
    assert parsed["dialect"] == "mbpp" and parsed["entry_point"] == ep


def test_the_gauge_still_runs_on_the_rendered_code_not_on_supplier_code(mbpp_spec):
    """量具跑的是**渲染出來的**碼，而渲染出來的碼裡沒有一個位元組來自供應者。

    兩件事一起釘：(a) 渲染結果不含任何攻擊面關鍵字；(b) 量具照樣有效（真沙箱）。
    """
    code = mbpp_spec.render()
    for forbidden in ("import ", "open(", "_worker", "exec(", "hashlib", "__canon"):
        assert forbidden not in code.replace("import re as __vacant_re\n", "", 1), forbidden
    rec = run_suite_gauge(mbpp_spec, REF_SIMILAR,
                          [broken_stub("similar_elements"), STUB_EMPTY],
                          entry_point="similar_elements")
    assert rec.ok and rec.n_broken == 2


# ── 9. round452b：entry_point 綁題目，每一道門都要擋 ────────────────────────
#
# 這一組釘的是一次**已經發生過的**破口：1cfec80 上 entry_point 是套件的欄位，
# `entry_point="exec"` ＋ 一條字串 args 就是任意程式執行，368/371 過 commit、
# 假交付 31.52%（`ops/gain/replay/r452b_smuggle_gate.py`）。修法是把 entry_point
# 綁回題目 ＋ 渲染器改命名空間查找。這裡逐門測第一半。

def _mismatch_doors():
    """每一道吃 SuiteSpec 的門 ＋ 一個「套件驗的不是這一題」的呼叫。

    `SPEC.entry_point == "f"`，題目宣告的是 `"g"`（`task_g`）——一份完全合法、
    量具也過得了的 spec，唯一的問題是它驗的不是客戶要的那個函式。
    """
    def task_g():
        return {"task_id": "t1", "entry_point": "g",
                "visible_check": {"type": "run_python", "code": "pass", "timeout": 8}}

    rec = run_suite_gauge(SPEC, GOOD, [BAD], entry_point="f",
                          runner=rule_runner(lambda c, _k: c is GOOD))
    entry, _b, _i = _gauged_commit()

    def door_commit(book, ident, execs):
        return commit_suite(book, ident, task_id="t1", suite=SPEC, nonce=NONCE,
                            entry_point="g", gauge=rec, ts_ms=TS)

    def door_commit_with_gauge(book, ident, execs):
        return commit_suite_with_gauge(
            book, ident, task_id="t1", suite=SPEC, nonce=NONCE, reference=GOOD,
            entry_point="g", runner=rule_runner(lambda c, _k: c is GOOD), ts_ms=TS)

    def door_run_gauge(book, ident, execs):
        return run_suite_gauge(SPEC, GOOD, [BAD], entry_point="g",
                               runner=rule_runner(lambda c, _k: c is GOOD))

    def door_attest(book, ident, execs):
        return execs[0].attest(task_g(), GOOD, suite=SPEC, ts_ms=TS)

    def door_challenge(book, ident, execs):
        v, _a, _r = verdict_for(execs, task(), GOOD)
        for e in execs:
            e.book = Logbook()
        return challenge_rerun(task_g(), GOOD, execs, v, suite=SPEC, ts_ms=TS)

    return {
        "commit_suite": (door_commit, True),
        "commit_suite_with_gauge": (door_commit_with_gauge, True),
        "run_suite_gauge": (door_run_gauge, True),
        "Executor.attest": (door_attest, True),
        "challenge_rerun": (door_challenge, True),
        "suite_gate": (lambda b, i, e: suite_gate(entry, SPEC, NONCE,
                                                  entry_point="g"), False),
        "open_suite": (lambda b, i, e: open_suite(entry, SPEC, NONCE,
                                                  entry_point="g"), False),
        "gauged_suite_index": (
            lambda b, i, e: gauged_suite_index([(entry, SPEC, NONCE, "g")]), False),
        "select_by_quorum": (
            lambda b, i, e: select_by_quorum(task_g(), [(GOOD, "wA")], e,
                                             suite=SPEC, ts_ms=TS), False),
    }


@pytest.mark.parametrize("door", sorted(_mismatch_doors()))
def test_entry_point_mismatch_is_refused_at_every_door(door):
    """套件的 entry_point ≠ 題目的 ⇒ 每一道門都拒，而且**鏈上一筆都沒有**。

    「沒有預設值可以跳過檢查」這句話的可執行版本：九道門逐一點名。有理由通道的
    （`suite_gate`／`select_by_quorum`／索引）回理由，沒有的丟例外——兩種都不准
    先產生一筆 entry 再說。
    """
    call, raises = _mismatch_doors()[door]
    book, ident = Logbook(), Identity.generate()
    execs = mk(3, truth_probe(TRUTH))
    if raises:
        with pytest.raises(SuiteSpecError) as e:
            call(book, ident, execs)
        assert str(e.value) == "entry_point_mismatch"
    else:
        out = call(book, ident, execs)
        if door == "suite_gate":
            assert out == (False, "entry_point_mismatch")
        elif door == "open_suite":
            assert out is False
        elif door == "gauged_suite_index":
            assert out == {}
        else:
            assert out.refused and out.refusal_reason == "entry_point_mismatch"
            assert out.n_sandbox_runs == 0 and out.verdicts == ()
    assert book.entries == []
    assert all(e.book.entries == [] for e in execs)


@pytest.mark.parametrize("ep", ["exec", "eval", "open", "getattr", "os", "subprocess"])
def test_a_task_whose_entry_point_is_dangerous_is_itself_refused(ep):
    """就算題目自己宣告 `entry_point="exec"`，套件照樣進不了任何一道門。

    這是 R452b 走私的最後一格：攻擊者若能連題目一起換掉，「相符」就不再是保護。
    黑名單（防禦縱深）在這裡把它接住，而真正讓 payload 失效的是渲染器
    （`tests/test_suitespec.py::test_the_r452b_smuggle_payloads_never_execute...`）。
    """
    payload = "import os\nos.system('true')\n"
    raw = {"v": 1, "dialect": "mbpp", "entry_point": ep,
           "tests": [{"args": repr([payload]), "expected": "None"}],
           "cmp": {"atol": 0.0}}
    with pytest.raises(SuiteSpecError) as e:
        ss.validate(raw, entry_point=ep)
    assert str(e.value) == "entry_point_reserved"
    t = {"task_id": "t1", "entry_point": ep,
         "visible_check": {"type": "run_python", "code": "pass", "timeout": 8}}
    book, ident = Logbook(), Identity.generate()
    with pytest.raises(SuiteSpecError):
        commit_suite(book, ident, task_id="t1", suite=raw, nonce=NONCE,
                     entry_point=ep,
                     gauge=GaugeRecord("0" * 64, "0" * 64, 1, True, True), ts_ms=TS)
    execs = mk(3, truth_probe(TRUTH))
    with pytest.raises(SuiteSpecError):
        execs[0].attest(t, GOOD, suite=raw, ts_ms=TS)
    assert book.entries == [] and all(e.book.entries == [] for e in execs)


def test_the_commit_payload_carries_the_task_entry_point():
    """第三方光看鏈就核得到「這筆承諾要驗的是誰」——不必先拿到套件原文。

    `commitment` 本來就綁得住 entry_point（`spec.to_json()` 含它），但那要有 spec
    才驗得出來。明碼欄位讓稽核者少一個相依；缺欄位＝拒（`entry_point_not_committed`）。
    """
    entry, _b, ident = _gauged_commit()
    assert entry.payload["entry_point"] == "f"
    assert entry.payload["v"] == 2
    stripped = LogEntry(entry.stream_id, entry.branch_id, entry.seq, entry.prev_hash,
                        entry.ts_ms, entry.type,
                        {k: v for k, v in entry.payload.items() if k != "entry_point"},
                        entry.sig)
    assert suite_gate(stripped, SPEC, NONCE,
                      entry_point="f") == (False, "entry_point_not_committed")
    lied = LogEntry(entry.stream_id, entry.branch_id, entry.seq, entry.prev_hash,
                    entry.ts_ms, entry.type,
                    dict(entry.payload) | {"entry_point": "g"}, entry.sig)
    assert suite_gate(lied, SPEC, NONCE,
                      entry_point="f") == (False, "entry_point_not_committed")


# ── 10. round452c：壞 spec 是**拒絕**不是 traceback；沒有 entry_point 的題目一律拒 ──
#
# 攻擊者在 b3c8514 上量到的兩件事（`ops/gain/replay/r452c_channel_hunt.py`）：
#   探針 C：`expected = "0x" + "f"*4000` 是一份**合法**的 spec（`literal_eval` 收
#           16 進位、`int_max_str_digits` 只擋十進位轉換），到 `repr()` 才丟**裸
#           ValueError** ⇒ 本模組 11/11 道門噴 traceback。那是誠實邊界 §3 的
#           **相關失效**：k 台執行器吃同一份 spec 會一起倒，而拒絕服務也是一種
#           交不出貨。
#   探針 I：`entry_point=None` 被 validator 當成「跳過檢查」⇒ 一個沒有那個欄位的
#           題目讓 R452b 的綁定整條變回 no-op。

POISON = {"v": 1, "dialect": "mbpp", "entry_point": "f",
          "tests": [{"args": "[1]", "expected": "0x" + "f" * 4000}],
          "cmp": {"atol": None, "set_equivalent": False, "regex_predicate": False}}
#: 沒有 `entry_point` 欄位的題目。`task.get("entry_point")` → `None`。
TASK_NO_EP = {"task_id": "t1",
              "visible_check": {"type": "run_python", "code": "pass", "timeout": 8}}


def _doors(suite, t, *, entry_point):
    """每一道吃套件的門 ＝ 一個 `(名字, 呼叫)`。書都在呼叫端外面，好核對「鏈上沒有」。

    `suite_gate`／`open_suite`／`gauged_suite_index` 需要一筆**乾淨的**承諾當底，
    再拿壞套件去揭露——揭露端才是這幾支真正要驗的東西。
    """
    entry, _b, _i = _gauged_commit()
    rec = GaugeRecord(SPEC.suite_sha256, sha256_hex(GOOD), 1, True, True)

    def mk_book():
        return Logbook(), Identity.generate()

    return {
        "as_suite_spec": lambda b, i, e: as_suite_spec(suite, entry_point),
        "commit_suite": lambda b, i, e: commit_suite(
            b, i, task_id="t1", suite=suite, nonce=NONCE, entry_point=entry_point,
            gauge=rec, ts_ms=TS),
        "commit_suite_with_gauge": lambda b, i, e: commit_suite_with_gauge(
            b, i, task_id="t1", suite=suite, nonce=NONCE, reference=GOOD,
            entry_point=entry_point, runner=rule_runner(lambda c, _k: c is GOOD),
            ts_ms=TS),
        "run_suite_gauge": lambda b, i, e: run_suite_gauge(
            suite, GOOD, [BAD], entry_point=entry_point,
            runner=rule_runner(lambda c, _k: c is GOOD)),
        "Executor.attest": lambda b, i, e: e[0].attest(t, GOOD, suite=suite, ts_ms=TS),
        "select_by_quorum": lambda b, i, e: select_by_quorum(
            t, [(GOOD, "wA")], e, suite=suite, ts_ms=TS),
        "challenge_rerun": lambda b, i, e: challenge_rerun(
            t, GOOD, e, form_verdict([], roster_of(e), task_id="t1",
                                     draft_sha256=sha256_hex(GOOD),
                                     suite_sha256=SSHA),
            suite=suite, ts_ms=TS),
        "suite_gate": lambda b, i, e: suite_gate(entry, suite, NONCE,
                                                 entry_point=entry_point),
        "open_suite": lambda b, i, e: open_suite(entry, suite, NONCE,
                                                 entry_point=entry_point),
        "gauged_suite_index": lambda b, i, e: gauged_suite_index(
            [(entry, suite, NONCE, entry_point)]),
    }


@pytest.mark.parametrize("door", sorted(_doors(POISON, task(), entry_point="f")))
def test_a_poison_literal_is_a_refusal_at_every_door_not_a_traceback(door):
    """本模組十道門，一個 `ValueError` 都不准跑出來——出來的只能是 `SuiteSpecError`。
    （加上 `suitespec.validate` 就是攻擊者量到的那 11/11。）

    這條釘的不是「壞 spec 被擋」（它本來就沒過），是**擋法的型別**：呼叫端
    （`select_by_quorum`／`suite_gate`／實驗 runner）只 catch `SuiteSpecError`，
    所以別的型別等於穿門而過。附帶核對鏈上一筆都沒有——不該存在的證言不准
    先上鏈再說。
    """
    call = _doors(POISON, task(), entry_point="f")[door]
    book, ident = Logbook(), Identity.generate()
    execs = mk(3, truth_probe(TRUTH))
    try:
        out = call(book, ident, execs)
    except SuiteSpecError as exc:
        assert str(exc) == "int_too_large"
    except BaseException as exc:                      # noqa: BLE001
        raise AssertionError(f"{door} 漏出 {type(exc).__name__}: {exc}") from exc
    else:
        # 有理由通道的門：回一個拒絕，不是一個可用的結果。
        if door == "gauged_suite_index":
            assert out == {}
        elif door == "open_suite":
            assert out is False
        elif door == "suite_gate":
            assert out[0] is False
        else:
            assert getattr(out, "refused", False)
    assert book.entries == []
    assert all(e.book.entries == [] for e in execs)


@pytest.mark.parametrize("door", sorted(_doors(SPEC, TASK_NO_EP, entry_point=None)))
def test_a_task_without_an_entry_point_refuses_at_every_door(door):
    """題目沒有 `entry_point` 欄位 ⇒ 沒有東西可以綁 ⇒ 每一道門都拒。

    這裡的套件（`SPEC`）**完全合法**、量具也過得了——唯一的問題是沒有題目可以
    對照。舊行為是**綁定被跳過**，於是套件自己宣告的 entry point 一路走到底
    （攻擊者探針 I：`as_suite_spec`／`commit_suite`／`suite_gate` 全 ACCEPTED）。
    """
    call = _doors(SPEC, TASK_NO_EP, entry_point=None)[door]
    book, ident = Logbook(), Identity.generate()
    execs = mk(3, truth_probe(TRUTH))
    try:
        out = call(book, ident, execs)
    except SuiteSpecError as exc:
        assert str(exc) == "entry_point_unbound"
    except BaseException as exc:                      # noqa: BLE001
        raise AssertionError(f"{door} 漏出 {type(exc).__name__}: {exc}") from exc
    else:
        if door == "gauged_suite_index":
            assert out == {}
        elif door == "open_suite":
            assert out is False
        elif door == "suite_gate":
            assert out == (False, "entry_point_unbound")
        else:
            assert out.refused and out.refusal_reason == "entry_point_unbound"
            assert out.n_sandbox_runs == 0 and out.verdicts == ()
    assert book.entries == []
    assert all(e.book.entries == [] for e in execs)
