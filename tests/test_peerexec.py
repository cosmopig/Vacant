"""peerexec 的確定性測試——不碰沙箱、不碰模型、不碰 runs/。

每一條都對應 `vacant/peerexec.py` 的一句主張。主張與測試一一對照，
「機制講得出來但測不出來」的東西不准留在 docstring 裡。
"""

from __future__ import annotations

import pytest

from vacant.identity import Identity
from vacant.logbook import LogEntry, Logbook
from vacant.peerexec import (Attestation, Executor, ProbeResult, challenge_rerun,
                             commit_suite, form_verdict, open_suite, roster_of,
                             select_by_quorum, sha256_hex, suite_hash,
                             verify_attestation, verify_executor_chain)

TS = 1_700_000_000_000


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


def verdict_for(execs, t, code, quorum=None):
    ros = roster_of(execs)
    ssha = suite_hash(t)
    atts = [e.attest(t, code, suite_sha256=ssha, ts_ms=TS) for e in execs]
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
        e.attest(t, c, ts_ms=TS)
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
                              suite_sha256=suite_hash(t)) == (True, "")
    assert lie.payload["visible_ok"] is True


def test_liar_cannot_move_the_verdict_alone_but_leaves_a_trail():
    """說謊者被推翻之後，那份草稿仍然不出貨——被指名不是安慰獎，是機制的產物。"""
    t = task()
    execs = mk(2, truth_probe(TRUTH)) + [
        Executor("liar", Identity.generate(), Logbook(), liar_probe(TRUTH, sha256_hex(BAD)))]
    sel = select_by_quorum(t, [(BAD, "wA"), (GOOD, "wB")], execs, ts_ms=TS)
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
    sel = select_by_quorum(t, [(BAD, "wA")], execs, quorum=2, ts_ms=TS)
    assert sel.refused


# ── 4. 竄改證言就驗不過 ────────────────────────────────────────────────────
def test_tampering_an_attestation_breaks_verification():
    t = task()
    execs = mk(1, truth_probe(TRUTH))
    att = execs[0].attest(t, BAD, ts_ms=TS)
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
    fake = impostor.attest(t, BAD, ts_ms=TS)
    assert verify_attestation(fake, ros) == (False, "bad_signature")
    # (d) 名冊外的人投票
    outsider = Executor("nobody", Identity.generate(), Logbook(), truth_probe(TRUTH))
    assert verify_attestation(outsider.attest(t, BAD, ts_ms=TS), ros) == (
        False, "unknown_executor")


def test_forged_attestation_is_rejected_from_the_verdict_not_counted():
    """驗不過的證言不是「一張反對票」，是**根本不進計票**，而且理由要進收據。"""
    t = task()
    execs = mk(3, truth_probe(TRUTH))
    ros = roster_of(execs)
    ssha = suite_hash(t)
    atts = [e.attest(t, BAD, suite_sha256=ssha, ts_ms=TS) for e in execs]
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
    ssha = suite_hash(t)
    atts = [e.attest(t, BAD, suite_sha256=ssha, ts_ms=TS) for e in honest]
    atts.append(two_faced.attest(t, BAD, suite_sha256=ssha, ts_ms=TS))
    two_faced.probe = liar_probe(TRUTH, sha256_hex(BAD))
    atts.append(two_faced.attest(t, BAD, suite_sha256=ssha, ts_ms=TS))
    v = form_verdict(atts, ros, task_id="t1", draft_sha256=sha256_hex(BAD),
                     suite_sha256=ssha, quorum=2)
    assert v.equivocators == ("d0",) and ("d0", "equivocation") in v.rejected
    assert v.n_admitted == 2 and v.visible_ok is False


# ── 5. 驗收套件雜湊不符 ⇒ 拒收 ────────────────────────────────────────────
def test_suite_hash_mismatch_is_rejected():
    """執行器跑的必須是**這一套**驗收。跑了別套（或跑了改過的那套）＝不進計票。"""
    t = task()
    swapped = {**t, "visible_check": task(code="assert f(1) == 999\n")["visible_check"]}
    assert suite_hash(t) != suite_hash(swapped)
    execs = mk(1, truth_probe(TRUTH))
    ros = roster_of(execs)
    # 同一題、同一份草稿，但執行器跑的是被換掉的驗收套件 ⇒ 不進計票。
    att = execs[0].attest(swapped, GOOD, ts_ms=TS)
    assert verify_attestation(att, ros, task_id="t1", draft_sha256=sha256_hex(GOOD),
                              suite_sha256=suite_hash(t)) == (False, "suite_mismatch")
    # 換題目的證言同樣擋掉（跨題重放）。
    att2 = execs[0].attest(task("t2"), GOOD, ts_ms=TS)
    assert verify_attestation(att2, ros, task_id="t1", draft_sha256=sha256_hex(GOOD),
                              suite_sha256=suite_hash(t)) == (False, "task_mismatch")


def test_replayed_attestation_from_another_draft_is_rejected():
    """把上一份草稿的『通過』證言貼到這一份 ⇒ draft_mismatch，擋掉重放。"""
    t = task()
    execs = mk(1, truth_probe(TRUTH))
    att = execs[0].attest(t, GOOD, ts_ms=TS)
    assert verify_attestation(att, roster_of(execs), task_id="t1",
                              draft_sha256=sha256_hex(BAD),
                              suite_sha256=suite_hash(t)) == (False, "draft_mismatch")


# ── 6. 剩下的固定點：套件的 commit-reveal 與重跑權 ─────────────────────────
def test_suite_commit_reveal_binds_the_suite_in_time():
    t = task()
    ident = Identity.generate()
    book = Logbook()
    nonce = "0123456789abcdef0123456789abcdef"
    entry = commit_suite(book, ident, task_id="t1",
                         check_code=t["visible_check"]["code"], nonce=nonce, ts_ms=TS)
    assert open_suite(entry, t["visible_check"]["code"], nonce)
    assert not open_suite(entry, t["visible_check"]["code"] + "\nassert f(9) == 10\n", nonce)
    assert not open_suite(entry, t["visible_check"]["code"], "f" * 32)
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
    sel = select_by_quorum(t, [(GOOD, "wA")], execs, ts_ms=TS)
    assert sel.refused and sel.verdicts[0].dissenters == ("h0",)

    clean = mk(3, truth_probe(TRUTH))
    ch = challenge_rerun(t, GOOD, clean, sel.verdicts[0], ts_ms=TS)
    assert ch.outcome == "overturned" and ch.rerun.visible_ok is True
    assert "h0" in ch.accused          # 聯集：原判指名的人也要留在收據上

    dirty = [Executor(f"d{i}", Identity.generate(), Logbook(), saboteur_probe())
             for i in range(3)]
    assert challenge_rerun(t, GOOD, dirty, sel.verdicts[0], ts_ms=TS).outcome == "upheld"


# ── 7. 選擇語意與 CONFORM 逐字相同（k=1 時必須退化成 CONFORM）──────────────
def test_k1_reduces_to_conform():
    """k=1 的法定人數 ＝ 單一執行器 ＝ CONFORM。這是模擬校準檢查的機制側對應物。"""
    t = task()
    execs = mk(1, truth_probe(TRUTH))
    sel = select_by_quorum(t, [(BAD, "wA"), (BAD, "wB"), (GOOD, "wC")], execs, ts_ms=TS)
    assert sel.shipped_index == 2 and sel.n_sandbox_runs == 3
    assert not sel.refused
    sel2 = select_by_quorum(t, [(BAD, "wA"), (BAD, "wB")], execs, ts_ms=TS)
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


def test_a_trivial_suite_ships_a_wrong_draft_with_zero_dissent():
    """**剩下的固定點，寫成測試**：驗收套件退化成「什麼都不驗」時，去中心化執行零幫助。

    執行器一個都沒有腐化、每條鏈都驗得過、`contested` 是 False、`dissenters` 是空的
    ——所有健康指標滿分——而出貨的是一份對真需求錯的草稿。`unanimous` 描述的是
    **觀察到的分佈**，不是真相；收據上不准把它讀成「這份草稿是對的」。
    """
    trivial = {"task_id": "t1", "entry_point": "f",
               "visible_check": {"type": "run_python", "code": "pass", "timeout": 8}}
    allpass = {sha256_hex(GOOD): ProbeResult(True, None, 0, True, None),
               sha256_hex(BAD): ProbeResult(True, None, 0, True, None)}
    execs = mk(5, truth_probe(allpass))
    sel = select_by_quorum(trivial, [(BAD, "wA"), (GOOD, "wB")], execs, ts_ms=TS)
    assert sel.shipped_index == 0 and sel.shipped_worker == "wA"   # 交了錯的那一份
    v = sel.verdicts[0]
    assert v.unanimous and not v.contested and v.n_pass == 5 and v.dissenters == ()
    # 而且這件事在收據上看得出來——換了套件，suite_sha256 就換了。
    assert v.suite_sha256 == suite_hash(trivial) != suite_hash(task())


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
